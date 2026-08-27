"""Pure deterministic M0 sync planner."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from itertools import chain
from pathlib import PureWindowsPath
from typing import Callable, Iterable, Mapping, Sequence

from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    FileStat,
    MANAGED_FILE_ATTRIBUTE_MASK,
    MetadataSnapshot,
    Root,
    ScanResult,
    VolumeEvidence,
    VolumeId,
    validate_scan_result,
)
from namisync.core.pathing import (
    is_relative_path_descendant,
    normalize_relative_path,
    relative_path_depth,
    relative_path_parent,
    validate_relative_path,
)
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    FilterSet,
    IdentityDestinationPolicy,
    MappingPair,
    MappingSnapshot,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    Scope,
    ScopeKind,
    SyncOptions,
    calculate_required_bytes,
    deterministic_operation_id,
    plan_fingerprint,
    policy_fingerprint,
    re_fullmatch_op_id,
    validate_assignment,
    validate_filter_set,
)
from namisync.core.review import (
    PLAN_SOURCE_REFERENCE_BYTES,
    PlanReviewAdmission,
    snapshot_plan_file_records,
    snapshot_plan_scan_result,
)


@dataclass(frozen=True, slots=True)
class _DestinationPolicyIdentity:
    """Immutable policy identity safe to retain after callback disposal."""

    name: str
    version: str

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> Assignment:
        del records, meta, target
        raise RuntimeError("a retained policy identity cannot assign destinations")


@dataclass(frozen=True, slots=True)
class _DestinationPolicyCallback:
    """Disposable callback paired with one captured policy identity.

    Destination policies are trusted synchronous collaborators and must not
    retain or export the detached records or target scan supplied to ``assign``.
    Python cannot prevent a callback from publishing those aliases, so planner
    custody drops every local callback-input owner before retaining its result.
    """

    name: str
    version: str
    callback: Callable[..., object]

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> object:
        return self.callback(records, meta, target)


def _capture_destination_policy(
    value: object,
) -> tuple[_DestinationPolicyIdentity, Callable[..., object]]:
    try:
        name = value.name  # type: ignore[attr-defined]
        version = value.version  # type: ignore[attr-defined]
        callback = value.assign  # type: ignore[attr-defined]
    except AttributeError as error:
        raise TypeError("destination policy has an incomplete contract") from error
    validate_assignment(Assignment(name, version, ()))
    if not callable(callback):
        raise TypeError("destination policy assign must be callable")
    return _DestinationPolicyIdentity(name, version), callback


def _copy_sync_options(value: object, destination_policy: object) -> SyncOptions:
    if type(value) is not SyncOptions:
        raise TypeError("planner options must be an exact SyncOptions")
    if type(value.preservation) is not PreservationPolicy:
        raise TypeError("planner preservation must be an exact PreservationPolicy")
    validate_filter_set(value.filters)
    return SyncOptions(
        deletion_policy=value.deletion_policy,
        preservation=PreservationPolicy(
            value.preservation.preserve_ads,
            value.preservation.preserve_created,
            value.preservation.preserve_acl,
        ),
        filters=FilterSet(tuple(value.filters.patterns)),
        destination_policy=destination_policy,  # type: ignore[arg-type]
        trash_on_update=value.trash_on_update,
        propagate_source_casing=value.propagate_source_casing,
        internal_mirror_authorized=value.internal_mirror_authorized,
    )


def snapshot_plan_options(value: object) -> tuple[SyncOptions, SyncOptions]:
    """Capture disposable callback options and a callback-free retained copy."""

    if type(value) is not SyncOptions:
        raise TypeError("planner options must be an exact SyncOptions")
    identity, callback = _capture_destination_policy(value.destination_policy)
    retained_identity: object = identity
    if type(value.destination_policy) is IdentityDestinationPolicy:
        retained_identity = IdentityDestinationPolicy(identity.name, identity.version)
    return (
        _copy_sync_options(
            value,
            _DestinationPolicyCallback(identity.name, identity.version, callback),
        ),
        _copy_sync_options(value, retained_identity),
    )


def _snapshot_retained_options(value: object) -> SyncOptions:
    """Copy option identity without retaining its live callback."""

    if type(value) is not SyncOptions:
        raise TypeError("planner options must be an exact SyncOptions")
    identity, _ = _capture_destination_policy(value.destination_policy)
    retained_identity: object = identity
    if type(value.destination_policy) is IdentityDestinationPolicy:
        retained_identity = IdentityDestinationPolicy(identity.name, identity.version)
    return _copy_sync_options(value, retained_identity)


def _snapshot_identity(value: FileIdentity | None) -> FileIdentity | None:
    if value is None:
        return None
    if type(value) is not FileIdentity:
        raise TypeError("mapping file identity has the wrong type")
    return FileIdentity(value.volume_serial, value.file_index)


def _snapshot_volume(value: VolumeId | None) -> VolumeId | None:
    if value is None:
        return None
    if type(value) is not VolumeId:
        raise TypeError("mapping volume identity has the wrong type")
    return VolumeId(value.serial, value.fs_type)


def snapshot_mapping_snapshot(
    value: object,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> MappingSnapshot:
    """Return an exact detached correspondence under independent source gates."""

    admission = (
        PlanReviewAdmission()
        if review_admission is None
        else review_admission
    )
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    populations = _validate_plan_mapping_source(value, admission)
    pairs_source = populations[0][1]
    ambiguous_source = populations[1][1]
    disqualified_source = populations[2][1]
    disqualified_target = populations[3][1]
    assert type(value) is MappingSnapshot
    pairs: list[MappingPair] = []
    for pair in pairs_source:
        if type(pair) is not MappingPair:
            raise TypeError(
                "planner correspondence pairs must contain exact MappingPair values"
            )
        if type(pair.source_rel_path_key) is not str:
            raise TypeError("mapping source path key must be text")
        validate_relative_path(pair.source_rel_path_key)
        if pair.source_rel_path_key != normalize_relative_path(
            pair.source_rel_path_key
        ):
            raise ValueError("mapping source path key is not canonical")
        source_identity = _snapshot_identity(pair.source_identity)
        target_identity = _snapshot_identity(pair.target_identity)
        if source_identity is None:
            raise TypeError("mapping source identity must be a FileIdentity")
        pairs.append(
            MappingPair(
                pair.source_rel_path_key,
                pair.target_rel_path,
                pair.target_rel_path_key,
                source_identity,
                target_identity,
            )
        )

    def snapshot_ambiguous_key(key: object) -> str:
        if type(key) is not str:
            raise TypeError("mapping ambiguous source keys must be text")
        validate_relative_path(key)
        if key != normalize_relative_path(key):
            raise ValueError("mapping ambiguous source key is not canonical")
        return key

    def snapshot_identities(
        population: frozenset[FileIdentity],
    ) -> frozenset[FileIdentity]:
        copied: list[FileIdentity] = []
        for identity in population:
            snapshot = _snapshot_identity(identity)
            if snapshot is None:
                raise TypeError(
                    "mapping disqualified identities must be FileIdentity values"
                )
            copied.append(snapshot)
        return frozenset(copied)

    return MappingSnapshot(
        _snapshot_volume(value.source_volume_id),
        _snapshot_volume(value.target_volume_id),
        tuple(pairs),
        frozenset(snapshot_ambiguous_key(key) for key in ambiguous_source),
        snapshot_identities(disqualified_source),
        snapshot_identities(disqualified_target),
    )


def _validate_plan_mapping_source(
    value: object,
    admission: PlanReviewAdmission,
) -> tuple[tuple[str, object, type], ...]:
    """Validate and source-gate the mapping populations without allocation."""

    if type(value) is not MappingSnapshot:
        raise TypeError("planner correspondence must be an exact MappingSnapshot")
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    populations = (
        ("pairs", value.pairs, tuple),
        ("ambiguous source keys", value.ambiguous_source_keys, frozenset),
        (
            "disqualified source identities",
            value.disqualified_source_identities,
            frozenset,
        ),
        (
            "disqualified target identities",
            value.disqualified_target_identities,
            frozenset,
        ),
    )
    for name, population, expected_type in populations:
        if type(population) is not expected_type:
            raise TypeError(f"planner correspondence {name} has the wrong type")
    for _, population, _ in populations:
        admission.require_source_rows(len(population))
    return populations


def _snapshot_assignment(
    value: object,
    admission: PlanReviewAdmission,
) -> Assignment:
    if type(value) is not Assignment:
        raise TypeError("destination policy must return an exact Assignment")
    if type(value.items) is not tuple:
        raise TypeError("assignment items must be an exact tuple")
    admission.require_source_rows(len(value.items))
    validate_assignment(value)
    snapshot = Assignment(
        value.policy_name,
        value.policy_version,
        tuple(
            DestinationAssignment(
                item.source_rel_path,
                item.source_rel_path_key,
                item.target_rel_path,
                item.target_rel_path_key,
                item.group_id,
                item.conflict,
            )
            for item in value.items
        ),
    )
    return snapshot


class _OperationAdmission:
    """Gate one combined operation source population before every append."""

    __slots__ = ("admission", "count")

    def __init__(
        self,
        admission: PlanReviewAdmission,
    ) -> None:
        self.admission = admission
        self.count = 0

    def admit(self) -> None:
        next_count = self.count + 1
        self.admission.require_source_rows(next_count)
        self.count = next_count


class _OperationList(list[PlanOperation]):
    """List whose shared gate runs before an operation becomes retained."""

    __slots__ = ("_gate",)

    def __init__(self, gate: _OperationAdmission | None) -> None:
        super().__init__()
        self._gate = gate

    def append(self, operation: PlanOperation) -> None:
        if self._gate is not None:
            self._gate.admit()
        super().append(operation)


def _cleanup_operation_dependencies(
    candidates: Iterable[str],
) -> tuple[str, ...]:
    """Deduplicate and freeze one cleanup operation's dependency ids."""

    dependency_ids: set[str] = set()
    for dependency in candidates:
        dependency_ids.add(dependency)
    return tuple(sorted(dependency_ids, key=str))


def _metadata_equal(source: FileStat, target: FileStat, granularity_ns: int) -> bool:
    return (
        source.size == target.size
        and abs(source.mtime_ns - target.mtime_ns) <= granularity_ns
        and (
            source.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
            == target.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
        )
    )


def _group_by_key(records: Iterable[object]) -> dict[str, list[object]]:
    grouped: dict[str, list[object]] = {}
    for record in records:
        grouped.setdefault(record.rel_path_key, []).append(record)  # type: ignore[attr-defined]
    for values in grouped.values():
        values.sort(key=lambda item: item.rel_path)  # type: ignore[attr-defined]
    return grouped


def _normalization_signature(path: str) -> tuple[str, str]:
    parsed = PureWindowsPath(path)
    return str(parsed.parent), unicodedata.normalize("NFC", parsed.name)


def _normalization_pairs(
    assignment: Assignment,
    target_files: Sequence[FileRecord],
    target_files_by_key: dict[str, list[object]],
) -> dict[tuple[str, str], FileRecord]:
    directly_matched_target_keys = {
        item.target_rel_path_key
        for item in assignment.items
        if target_files_by_key.get(item.target_rel_path_key)
    }
    desired_groups: dict[tuple[str, str], list[DestinationAssignment]] = {}
    for item in assignment.items:
        if target_files_by_key.get(item.target_rel_path_key):
            continue
        desired_groups.setdefault(
            _normalization_signature(item.target_rel_path), []
        ).append(item)

    target_groups: dict[tuple[str, str], list[FileRecord]] = {}
    for record in target_files:
        if record.rel_path_key in directly_matched_target_keys:
            continue
        target_groups.setdefault(
            _normalization_signature(record.rel_path), []
        ).append(record)

    pairs: dict[tuple[str, str], FileRecord] = {}
    for signature, desired in desired_groups.items():
        targets = target_groups.get(signature, ())
        if len(desired) != 1 or len(targets) != 1:
            continue
        item = desired[0]
        target = targets[0]
        if item.target_rel_path == target.rel_path:
            continue
        pairs[(item.source_rel_path_key, item.source_rel_path)] = target
    return pairs


def _identity_counts(records: Iterable[FileRecord]) -> dict[FileIdentity, int]:
    counts: dict[FileIdentity, int] = {}
    for record in records:
        if record.file_identity is not None:
            counts[record.file_identity] = counts.get(record.file_identity, 0) + 1
    return counts


def _blocked_operation(
    *,
    kind: OperationKind,
    source_rel_path: str | None,
    target_rel_path: str,
    source_expected: FileStat | None,
    target_expected: FileStat | None,
    intended: FileStat | None,
    reason: OperationReason,
    blocked_reason: BlockedReason,
    dependencies: tuple = (),
) -> PlanOperation:
    return PlanOperation(
        op_id=deterministic_operation_id(kind, source_rel_path, target_rel_path, None, reason),
        kind=kind,
        source_rel_path=source_rel_path,
        target_rel_path=target_rel_path,
        source_expected=source_expected,
        target_expected=target_expected,
        intended=intended,
        metadata=intended.metadata if intended is not None else None,
        dependencies=dependencies,
        reason=reason,
        blocked_reason=blocked_reason,
    )


def _validate_assignment(
    assignment: Assignment,
    source_files: Sequence[FileRecord],
) -> dict[tuple[str, str], DestinationAssignment]:
    source_identities = {(record.rel_path_key, record.rel_path) for record in source_files}
    items: dict[tuple[str, str], DestinationAssignment] = {}
    for item in assignment.items:
        validate_relative_path(item.target_rel_path)
        source_identity = (item.source_rel_path_key, item.source_rel_path)
        if source_identity not in source_identities:
            raise ValueError("destination policy assigned an unknown source")
        if source_identity in items:
            raise ValueError("destination policy assigned a source more than once")
        items[source_identity] = item
    if set(items) != source_identities:
        raise ValueError("destination policy did not assign every source")
    return items


def _nearest_created_parent(path: str, created: dict[str, PlanOperation]) -> PlanOperation | None:
    parent = relative_path_parent(path)
    while parent is not None:
        operation = created.get(normalize_relative_path(parent))
        if operation is not None:
            return operation
        parent = relative_path_parent(parent)
    return None


def _move_pair(
    source_record: FileRecord,
    desired_key: str,
    correspondence: MappingSnapshot,
    source: ScanResult,
    target: ScanResult,
    target_files_by_key: dict[str, list[object]],
    assigned_target_keys: set[str],
    source_identity_counts: dict[FileIdentity, int],
    target_identity_counts: dict[FileIdentity, int],
) -> tuple[MappingPair, FileRecord] | None:
    identity = source_record.file_identity
    if (
        identity is None
        or source_record.nlink != 1
        or not source.profile.stable_file_identity
        or not target.profile.stable_file_identity
        or source.volume_id is None
        or target.volume_id is None
        or correspondence.source_volume_id != source.volume_id
        or correspondence.target_volume_id != target.volume_id
        or identity.volume_serial != source.volume_id.serial
        or source_identity_counts.get(identity) != 1
        or identity in correspondence.disqualified_source_identities
        or source_record.rel_path_key in correspondence.ambiguous_source_keys
    ):
        return None
    candidates = [pair for pair in correspondence.pairs if pair.source_identity == identity]
    if len(candidates) != 1:
        return None
    pair = candidates[0]
    if pair.target_rel_path_key == desired_key or pair.target_rel_path_key in assigned_target_keys:
        return None
    old_values = target_files_by_key.get(pair.target_rel_path_key, [])
    if len(old_values) != 1 or not isinstance(old_values[0], FileRecord):
        return None
    old_target = old_values[0]
    if (
        old_target.nlink != 1
        or old_target.file_identity is None
        or old_target.file_identity.volume_serial != target.volume_id.serial
        or target_identity_counts.get(old_target.file_identity) != 1
        or old_target.file_identity in correspondence.disqualified_target_identities
        or (pair.target_identity is not None and old_target.file_identity != pair.target_identity)
    ):
        return None
    return pair, old_target


def plan(
    source: ScanResult,
    target: ScanResult,
    correspondence: MappingSnapshot,
    options: SyncOptions,
    scope: Scope,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> Plan:
    """Transform immutable observations and policy into immutable intent."""

    admission = review_admission
    assign_destinations: Callable[..., object] | None = None
    policy_identity: _DestinationPolicyIdentity | None = None
    if admission is not None:
        if type(admission) is not PlanReviewAdmission:
            raise TypeError("plan review admission has the wrong type")
        if type(scope) is not Scope or type(scope.kind) is not ScopeKind:
            raise TypeError("planner scope must be an exact typed Scope")
        if scope.kind is ScopeKind.EVERYTHING and scope.value is not None:
            raise ValueError("everything scope must not carry a value")
        validate_scan_result(source)
        validate_scan_result(target)
        _validate_plan_mapping_source(correspondence, admission)
        policy_identity, assign_destinations = _capture_destination_policy(
            options.destination_policy
        )

    if scope.kind is not ScopeKind.EVERYTHING:
        raise NotImplementedError(f"scope {scope.kind.value!r} is declared but not implemented in M0")

    source_files_all = sorted(source.files, key=lambda item: (item.rel_path_key, item.rel_path))
    target_files_all = sorted(target.files, key=lambda item: (item.rel_path_key, item.rel_path))
    source_files = tuple(record for record in source_files_all if not options.filters.excludes(record.rel_path))
    target_files = tuple(record for record in target_files_all if not options.filters.excludes(record.rel_path))
    source_dirs = tuple(
        record
        for record in sorted(source.directories, key=lambda item: (relative_path_depth(item.rel_path) if item.rel_path else 0, item.rel_path_key, item.rel_path))
        if record.rel_path and not options.filters.excludes(record.rel_path)
    )
    target_dirs = tuple(
        record
        for record in sorted(target.directories, key=lambda item: (relative_path_depth(item.rel_path) if item.rel_path else 0, item.rel_path_key, item.rel_path))
        if record.rel_path
    )

    if admission is None:
        assignment = options.destination_policy.assign(source_files, {}, target)
    else:
        callback_source_files = snapshot_plan_file_records(
            source_files,
            admission,
        )
        callback_target = snapshot_plan_scan_result(target, admission)
        assert assign_destinations is not None
        raw_assignment = assign_destinations(
            callback_source_files,
            {},
            callback_target,
        )
        assignment = _snapshot_assignment(
            raw_assignment,
            admission,
        )
        del (
            assign_destinations,
            callback_target,
            callback_source_files,
            raw_assignment,
        )
        assert policy_identity is not None
        if (
            assignment.policy_name != policy_identity.name
            or assignment.policy_version != policy_identity.version
        ):
            raise ValueError("destination assignment policy identity changed")
    _validate_assignment(assignment, source_files)
    source_files_by_key = _group_by_key(source_files)
    target_files_by_key = _group_by_key(target_files)
    target_dirs_by_key = _group_by_key(target_dirs)
    source_dirs_by_key = _group_by_key(source_dirs)
    normalization_pairs = _normalization_pairs(
        assignment, target_files, target_files_by_key
    )

    assigned_target_groups: dict[str, list[DestinationAssignment]] = {}
    for item in assignment.items:
        assigned_target_groups.setdefault(item.target_rel_path_key, []).append(item)
    assigned_target_keys = set(assigned_target_groups)

    required_directory_paths: set[str] = set()
    for record in source_dirs:
        required_directory_paths.add(record.rel_path)
    for item in assignment.items:
        parent = relative_path_parent(item.target_rel_path)
        while parent is not None:
            required_directory_paths.add(parent)
            parent = relative_path_parent(parent)

    operation_admission = (
        None
        if admission is None
        else _OperationAdmission(admission)
    )
    mkdir_operations: list[PlanOperation] = _OperationList(operation_admission)
    created_directories: dict[str, PlanOperation] = {}
    for directory_path in sorted(required_directory_paths, key=lambda value: (relative_path_depth(value), normalize_relative_path(value), value)):
        directory_key = normalize_relative_path(directory_path)
        existing_dirs = target_dirs_by_key.get(directory_key, [])
        existing_files = target_files_by_key.get(directory_key, [])
        if existing_dirs:
            continue
        source_candidates = source_dirs_by_key.get(directory_key, [])
        source_directory = source_candidates[0] if len(source_candidates) == 1 and isinstance(source_candidates[0], DirRecord) else None
        parent_operation = _nearest_created_parent(directory_path, created_directories)
        dependencies = (parent_operation.op_id,) if parent_operation is not None else ()
        if len(source_candidates) > 1 or existing_files or source_directory is None:
            operation = _blocked_operation(
                kind=OperationKind.MKDIR,
                source_rel_path=source_directory.rel_path if source_directory else directory_path,
                target_rel_path=directory_path,
                source_expected=source_directory.stat if source_directory else None,
                target_expected=existing_files[0].stat if len(existing_files) == 1 and isinstance(existing_files[0], FileRecord) else None,
                intended=source_directory.stat if source_directory else None,
                reason=OperationReason.TYPE_COLLISION if existing_files else OperationReason.POLICY_COLLISION,
                blocked_reason=BlockedReason.TYPE_COLLISION if existing_files else BlockedReason.DESTINATION_COLLISION,
                dependencies=dependencies,
            )
        else:
            operation = PlanOperation(
                op_id=deterministic_operation_id(OperationKind.MKDIR, source_directory.rel_path, directory_path, None, OperationReason.REQUIRED_DIRECTORY),
                kind=OperationKind.MKDIR,
                source_rel_path=source_directory.rel_path,
                target_rel_path=directory_path,
                source_expected=source_directory.stat,
                target_expected=None,
                intended=source_directory.stat,
                metadata=source_directory.metadata,
                dependencies=dependencies,
                reason=OperationReason.REQUIRED_DIRECTORY,
            )
        mkdir_operations.append(operation)
        created_directories[directory_key] = operation

    granularity = max(source.profile.mtime_granularity_ns, target.profile.mtime_granularity_ns)
    source_identity_counts = _identity_counts(source_files)
    target_identity_counts = _identity_counts(target_files)
    content_operations: list[PlanOperation] = _OperationList(operation_admission)
    claimed_target_keys: set[str] = set()
    moved_from_keys: set[str] = set()

    for item in sorted(assignment.items, key=lambda value: (value.target_rel_path_key, value.target_rel_path, value.source_rel_path)):
        source_values = source_files_by_key[item.source_rel_path_key]
        source_record = source_values[0]
        if not isinstance(source_record, FileRecord):
            raise TypeError("source file index contained a non-file record")
        target_values = target_files_by_key.get(item.target_rel_path_key, [])
        normalization_target = normalization_pairs.get(
            (item.source_rel_path_key, item.source_rel_path)
        )
        normalization_mismatch = not target_values and normalization_target is not None
        if normalization_mismatch:
            target_values = [normalization_target]
        target_directory_values = target_dirs_by_key.get(item.target_rel_path_key, [])
        parent_operation = _nearest_created_parent(item.target_rel_path, created_directories)
        dependencies = (parent_operation.op_id,) if parent_operation is not None else ()
        inherited_block = parent_operation is not None and parent_operation.blocked
        assignment_collision = len(assigned_target_groups[item.target_rel_path_key]) > 1 or item.conflict is not None
        if len(source_values) > 1 or len(target_values) > 1 or assignment_collision:
            case_collision = len(source_values) > 1 or len(target_values) > 1
            content_operations.append(
                _blocked_operation(
                    kind=OperationKind.COPY,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=target_values[0].stat if len(target_values) == 1 and isinstance(target_values[0], FileRecord) else None,
                    intended=source_record.stat,
                    reason=OperationReason.CASE_COLLISION if case_collision else OperationReason.POLICY_COLLISION,
                    blocked_reason=BlockedReason.CASE_COLLISION if case_collision else BlockedReason.DESTINATION_COLLISION,
                    dependencies=dependencies,
                )
            )
            claimed_target_keys.add(item.target_rel_path_key)
            continue
        if target_directory_values:
            content_operations.append(
                _blocked_operation(
                    kind=OperationKind.COPY,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=target_directory_values[0].stat if len(target_directory_values) == 1 and isinstance(target_directory_values[0], DirRecord) else None,
                    intended=source_record.stat,
                    reason=OperationReason.TYPE_COLLISION,
                    blocked_reason=BlockedReason.TYPE_COLLISION,
                    dependencies=dependencies,
                )
            )
            claimed_target_keys.add(item.target_rel_path_key)
            continue
        if inherited_block:
            content_operations.append(
                _blocked_operation(
                    kind=OperationKind.COPY,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=None,
                    intended=source_record.stat,
                    reason=OperationReason.SOURCE_ONLY,
                    blocked_reason=BlockedReason.BLOCKED_DEPENDENCY,
                    dependencies=dependencies,
                )
            )
            continue

        if target_values:
            target_record = target_values[0]
            if not isinstance(target_record, FileRecord):
                raise TypeError("target file index contained a non-file record")
            matched = _metadata_equal(source_record.stat, target_record.stat, granularity)
            kind = OperationKind.NOOP if matched else OperationKind.UPDATE
            target_path = item.target_rel_path
            prior_target_path: str | None = None
            prior_target_expected: FileStat | None = None
            intended = source_record.stat
            if normalization_mismatch:
                reason = OperationReason.UNICODE_NORMALIZATION_MISMATCH
                target_path = target_record.rel_path
            elif item.target_rel_path != target_record.rel_path:
                reason = OperationReason.CASE_MISMATCH
                target_path = target_record.rel_path
                desired_name = PureWindowsPath(item.target_rel_path).name
                observed_path = PureWindowsPath(target_record.rel_path)
                if options.propagate_source_casing and desired_name != observed_path.name:
                    target_path = str(observed_path.parent / desired_name)
                    if matched:
                        kind = OperationKind.RECASE
                        prior_target_path = target_record.rel_path
                        prior_target_expected = target_record.stat
                        intended = target_record.stat
            else:
                reason = OperationReason.METADATA_MATCH if matched else OperationReason.METADATA_CHANGED
            content_operations.append(
                PlanOperation(
                    op_id=deterministic_operation_id(
                        kind,
                        source_record.rel_path,
                        target_path,
                        prior_target_path,
                        reason,
                    ),
                    kind=kind,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=target_path,
                    source_expected=source_record.stat,
                    target_expected=target_record.stat,
                    intended=intended,
                    prior_target_rel_path=prior_target_path,
                    prior_target_expected=prior_target_expected,
                    metadata=intended.metadata,
                    content_bytes=(
                        source_record.size
                        if kind is OperationKind.UPDATE
                        else 0
                    ),
                    dependencies=dependencies,
                    reason=reason,
                )
            )
            claimed_target_keys.add(target_record.rel_path_key)
            continue

        move = _move_pair(
            source_record,
            item.target_rel_path_key,
            correspondence,
            source,
            target,
            target_files_by_key,
            assigned_target_keys,
            source_identity_counts,
            target_identity_counts,
        )
        if move is not None:
            pair, old_target = move
            matched = _metadata_equal(source_record.stat, old_target.stat, granularity)
            kind = OperationKind.MOVE if matched else OperationKind.MOVE_UPDATE
            reason = OperationReason.IDENTITY_RENAME if matched else OperationReason.IDENTITY_RENAME_CHANGED
            content_operations.append(
                PlanOperation(
                    op_id=deterministic_operation_id(kind, source_record.rel_path, item.target_rel_path, pair.target_rel_path, reason),
                    kind=kind,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=None,
                    intended=source_record.stat,
                    prior_target_rel_path=pair.target_rel_path,
                    prior_target_expected=old_target.stat,
                    metadata=source_record.metadata,
                    content_bytes=0 if matched else source_record.size,
                    dependencies=dependencies,
                    reason=reason,
                )
            )
            moved_from_keys.add(pair.target_rel_path_key)
            claimed_target_keys.add(item.target_rel_path_key)
        else:
            content_operations.append(
                PlanOperation(
                    op_id=deterministic_operation_id(OperationKind.COPY, source_record.rel_path, item.target_rel_path, None, OperationReason.SOURCE_ONLY),
                    kind=OperationKind.COPY,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=None,
                    intended=source_record.stat,
                    metadata=source_record.metadata,
                    content_bytes=source_record.size,
                    dependencies=dependencies,
                    reason=OperationReason.SOURCE_ONLY,
                )
            )
            claimed_target_keys.add(item.target_rel_path_key)

    removal_operations: list[PlanOperation] = _OperationList(operation_admission)
    removed_file_keys = set(moved_from_keys)
    for target_record in target_files:
        if target_record.rel_path_key in claimed_target_keys or target_record.rel_path_key in moved_from_keys:
            continue
        if options.deletion_policy is DeletionPolicy.ADDITIVE:
            continue
        kind = OperationKind.TRASH if options.deletion_policy is DeletionPolicy.TRASH else OperationKind.DELETE
        operation = PlanOperation(
            op_id=deterministic_operation_id(kind, None, target_record.rel_path, None, OperationReason.TARGET_ONLY),
            kind=kind,
            source_rel_path=None,
            target_rel_path=target_record.rel_path,
            source_expected=None,
            target_expected=target_record.stat,
            intended=None,
            reason=OperationReason.TARGET_ONLY,
        )
        removal_operations.append(operation)
        removed_file_keys.add(target_record.rel_path_key)

    blocked_operations: list[PlanOperation] = _OperationList(operation_admission)
    visible_unsupported: dict[tuple[str, str], object] = {}
    for record in (*source.unsupported, *target.unsupported):
        if options.filters.excludes(record.rel_path):
            continue
        visible_key = (record.rel_path_key, record.rel_path)
        visible_unsupported[visible_key] = record
    for record in sorted(visible_unsupported.values(), key=lambda item: (item.rel_path_key, item.rel_path)):  # type: ignore[attr-defined]
        blocked_operations.append(
            _blocked_operation(
                kind=OperationKind.NOOP,
                source_rel_path=record.rel_path,  # type: ignore[attr-defined]
                target_rel_path=record.rel_path,  # type: ignore[attr-defined]
                source_expected=None,
                target_expected=None,
                intended=None,
                reason=OperationReason.UNSUPPORTED,
                blocked_reason=BlockedReason.UNSUPPORTED,
            )
        )

    cleanup_operations: list[PlanOperation] = _OperationList(operation_admission)
    cleanup_by_key: dict[str, PlanOperation] = {}
    desired_directory_keys = {normalize_relative_path(path) for path in required_directory_paths}
    removal_by_path: dict[str, PlanOperation] = {}
    for operation in (*content_operations, *removal_operations):
        if operation.kind in {OperationKind.TRASH, OperationKind.DELETE}:
            removal_by_path[operation.target_rel_path] = operation
        elif operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE} and operation.prior_target_rel_path:
            removal_by_path[operation.prior_target_rel_path] = operation
    for directory in sorted(target_dirs, key=lambda item: (-relative_path_depth(item.rel_path), item.rel_path_key, item.rel_path)):
        if (
            options.deletion_policy is DeletionPolicy.ADDITIVE
            or directory.rel_path_key in desired_directory_keys
            or options.filters.excludes(directory.rel_path)
        ):
            continue
        excluded_child = any(
            bool(record.rel_path)
            and is_relative_path_descendant(record.rel_path, directory.rel_path)
            and options.filters.excludes(record.rel_path)
            for record in (*target.files, *target.directories)
            if record.rel_path != directory.rel_path
        )
        unsupported_child = any(is_relative_path_descendant(record.rel_path, directory.rel_path) for record in target.unsupported)
        remaining_file = any(
            is_relative_path_descendant(record.rel_path, directory.rel_path) and record.rel_path_key not in removed_file_keys
            for record in target.files
        )
        remaining_directory = any(
            relative_path_parent(child.rel_path) == directory.rel_path
            and child.rel_path_key not in cleanup_by_key
            and child.rel_path_key not in desired_directory_keys
            for child in target_dirs
        )
        if excluded_child or unsupported_child or remaining_file or remaining_directory:
            continue
        dependencies = _cleanup_operation_dependencies(
            chain(
                (
                    operation.op_id
                    for path, operation in removal_by_path.items()
                    if path == directory.rel_path
                    or is_relative_path_descendant(path, directory.rel_path)
                ),
                (
                    operation.op_id
                    for operation in cleanup_by_key.values()
                    if relative_path_parent(operation.target_rel_path)
                    == directory.rel_path
                ),
            ),
        )
        cleanup = PlanOperation(
            op_id=deterministic_operation_id(OperationKind.DELETE, None, directory.rel_path, None, OperationReason.DIRECTORY_CLEANUP),
            kind=OperationKind.DELETE,
            source_rel_path=None,
            target_rel_path=directory.rel_path,
            source_expected=None,
            target_expected=directory.stat,
            intended=None,
            dependencies=dependencies,
            reason=OperationReason.DIRECTORY_CLEANUP,
        )
        cleanup_operations.append(cleanup)
        cleanup_by_key[directory.rel_path_key] = cleanup

    operation_count = (
        len(mkdir_operations)
        + len(content_operations)
        + len(removal_operations)
        + len(blocked_operations)
        + len(cleanup_operations)
    )
    operations = tuple(
        (
            *mkdir_operations,
            *content_operations,
            *removal_operations,
            *blocked_operations,
            *cleanup_operations,
        )
    )
    if (
        operation_admission is not None
        and operation_admission.count != operation_count
    ):
        raise RuntimeError("plan operation admission did not cover every operation")
    required_bytes = calculate_required_bytes(
        operations,
        target_profile=target.profile,
        trash_on_update=options.trash_on_update,
    )
    required_volumes = frozenset(
        volume
        for volume in (source.volume_id, target.volume_id)
        if volume is not None
    )
    placeholder = Plan(
        source_root=source.root,
        target_root=target.root,
        source_volume_id=source.volume_id,
        target_volume_id=target.volume_id,
        source_volume_evidence=source.volume_evidence,
        target_volume_evidence=target.volume_evidence,
        source_profile=source.profile,
        target_profile=target.profile,
        source_complete=source.complete and source.is_full_scan,
        target_complete=target.complete and target.is_full_scan,
        operations=operations,
        assignment=assignment,
        preservation=options.preservation,
        filter_snapshot=options.filters,
        deletion_policy=options.deletion_policy,
        trash_on_update=options.trash_on_update,
        policy_fingerprint=policy_fingerprint(options),
        required_volumes=required_volumes,
        required_bytes=required_bytes,
        fingerprint=PlanFingerprint("0" * 64),
    )
    result = replace(placeholder, fingerprint=plan_fingerprint(placeholder))
    return result


def _snapshot_root(value: object) -> Root:
    if type(value) is not Root:
        raise TypeError("plan root has the wrong type")
    return Root(value.path, value.root_id)


def _snapshot_evidence(
    value: object,
) -> VolumeEvidence | None:
    if value is None:
        return None
    if type(value) is not VolumeEvidence:
        raise TypeError("plan volume evidence has the wrong type")
    return VolumeEvidence(value.label, value.device_id, value.clone_ambiguous)


def _snapshot_profile(value: object) -> CapabilityProfile:
    if type(value) is not CapabilityProfile:
        raise TypeError("plan capability profile has the wrong type")
    return CapabilityProfile(
        value.fs_type,
        value.mtime_granularity_ns,
        value.stable_file_identity,
        value.incurs_seek_penalty,
        value.max_path,
        value.supports_ads,
        value.supports_hardlinks,
    )


def _snapshot_metadata(
    value: object,
) -> MetadataSnapshot | None:
    if value is None:
        return None
    if type(value) is not MetadataSnapshot:
        raise TypeError("plan metadata has the wrong type")
    return MetadataSnapshot(value.attributes, value.created_ns)


def _snapshot_stat(value: object) -> FileStat | None:
    if value is None:
        return None
    if type(value) is not FileStat:
        raise TypeError("plan file stat has the wrong type")
    metadata = _snapshot_metadata(value.metadata)
    assert metadata is not None
    return FileStat(
        value.kind,
        value.size,
        value.mtime_ns,
        _snapshot_identity(value.file_identity),
        value.nlink,
        metadata,
    )


def _snapshot_operation(
    value: object,
) -> PlanOperation:
    if type(value) is not PlanOperation:
        raise TypeError("plan operations must contain exact PlanOperation values")
    if type(value.dependencies) is not tuple:
        raise TypeError("plan operation dependencies must be an exact tuple")
    if (
        type(value.op_id) is not str
        or not re_fullmatch_op_id(value.op_id)
        or type(value.kind) is not OperationKind
        or type(value.reason) is not OperationReason
        or (
            value.blocked_reason is not None
            and type(value.blocked_reason) is not BlockedReason
        )
    ):
        raise TypeError("plan operation has an invalid typed field")

    for dependency in value.dependencies:
        if type(dependency) is not str or not re_fullmatch_op_id(dependency):
            raise TypeError("plan operation dependency has an invalid id")

    snapshot = PlanOperation(
        op_id=value.op_id,
        kind=value.kind,
        source_rel_path=value.source_rel_path,
        target_rel_path=value.target_rel_path,
        source_expected=_snapshot_stat(value.source_expected),
        target_expected=_snapshot_stat(value.target_expected),
        intended=_snapshot_stat(value.intended),
        prior_target_rel_path=value.prior_target_rel_path,
        prior_target_expected=_snapshot_stat(value.prior_target_expected),
        metadata=_snapshot_metadata(value.metadata),
        content_bytes=value.content_bytes,
        dependencies=tuple(dependency for dependency in value.dependencies),
        reason=value.reason,
        blocked_reason=value.blocked_reason,
    )
    if snapshot.op_id != deterministic_operation_id(
        snapshot.kind,
        snapshot.source_rel_path,
        snapshot.target_rel_path,
        snapshot.prior_target_rel_path,
        snapshot.reason,
    ):
        raise ValueError("operation id does not match canonical intent")
    return snapshot


def snapshot_plan_candidate(
    value: object,
    source: ScanResult,
    target: ScanResult,
    options: SyncOptions,
    *,
    review_admission: PlanReviewAdmission | None = None,
) -> Plan:
    """Validate and detach one planner result before review publication."""

    if type(value) is not Plan:
        raise TypeError("planner must return an exact Plan")
    if type(value.operations) is not tuple:
        raise TypeError("plan operations must be an exact tuple")
    if type(value.assignment) is not Assignment:
        raise TypeError("plan assignment must be an exact Assignment")
    if type(value.assignment.items) is not tuple:
        raise TypeError("plan assignment items must be an exact tuple")
    if type(value.required_volumes) is not frozenset:
        raise TypeError("plan required volumes must be an exact frozenset")
    if type(value.required_bytes) is not int:
        raise TypeError("plan required bytes must be an exact integer")
    if type(value.policy_fingerprint) is not str:
        raise TypeError("plan policy fingerprint must be text")
    if (
        type(value.fingerprint) is not str
        or len(value.fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value.fingerprint
        )
    ):
        raise ValueError("plan fingerprint must be lowercase SHA-256 text")

    admission = (
        PlanReviewAdmission()
        if review_admission is None
        else review_admission
    )
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    admission.require_source_rows(len(value.operations))
    if len(value.required_volumes) > 2:
        raise ValueError("plan required volumes exceed the endpoint limit")

    validate_scan_result(source)
    validate_scan_result(target)
    retained_options = _snapshot_retained_options(options)
    assignment = _snapshot_assignment(value.assignment, admission)
    filtered_source_files = tuple(
        record
        for record in source.files
        if not retained_options.filters.excludes(record.rel_path)
    )
    _validate_assignment(assignment, filtered_source_files)
    if (
        assignment.policy_name != retained_options.destination_policy.name
        or assignment.policy_version
        != retained_options.destination_policy.version
    ):
        raise ValueError(
            "plan assignment policy does not match requested policy"
        )

    operations = tuple(
        _snapshot_operation(operation) for operation in value.operations
    )

    source_root = _snapshot_root(value.source_root)
    target_root = _snapshot_root(value.target_root)
    source_volume = _snapshot_volume(value.source_volume_id)
    target_volume = _snapshot_volume(value.target_volume_id)
    source_evidence = _snapshot_evidence(value.source_volume_evidence)
    target_evidence = _snapshot_evidence(value.target_volume_evidence)
    source_profile = _snapshot_profile(value.source_profile)
    target_profile = _snapshot_profile(value.target_profile)
    if (
        source_root != source.root
        or target_root != target.root
        or source_volume != source.volume_id
        or target_volume != target.volume_id
        or source_evidence != source.volume_evidence
        or target_evidence != target.volume_evidence
        or source_profile != source.profile
        or target_profile != target.profile
    ):
        raise ValueError("plan endpoint evidence does not match admitted scans")
    if (
        type(value.source_complete) is not bool
        or type(value.target_complete) is not bool
    ):
        raise TypeError("plan completeness fields must be bools")
    if (
        value.source_complete != (source.complete and source.is_full_scan)
        or value.target_complete != (target.complete and target.is_full_scan)
    ):
        raise ValueError("plan completeness does not match admitted scans")
    if type(value.preservation) is not PreservationPolicy:
        raise TypeError("plan preservation must be an exact PreservationPolicy")
    preservation = PreservationPolicy(
        value.preservation.preserve_ads,
        value.preservation.preserve_created,
        value.preservation.preserve_acl,
    )
    filter_snapshot = FilterSet(
        tuple(validate_filter_set(value.filter_snapshot).patterns)
    )
    if (
        preservation != retained_options.preservation
        or filter_snapshot != retained_options.filters
        or type(value.deletion_policy) is not DeletionPolicy
        or value.deletion_policy is not retained_options.deletion_policy
        or type(value.trash_on_update) is not bool
        or value.trash_on_update != retained_options.trash_on_update
    ):
        raise ValueError("plan policy snapshot does not match requested options")

    required_volume_items: set[VolumeId] = set()
    for volume in value.required_volumes:
        snapshot_volume = _snapshot_volume(volume)
        if snapshot_volume is None:
            raise TypeError("plan required volumes must contain VolumeId values")
        required_volume_items.add(snapshot_volume)
    required_volumes = frozenset(required_volume_items)
    expected_volumes = frozenset(
        volume
        for volume in (source.volume_id, target.volume_id)
        if volume is not None
    )
    if required_volumes != expected_volumes:
        raise ValueError("plan required volumes do not match admitted scans")
    required_bytes = calculate_required_bytes(
        operations,
        target_profile=target_profile,
        trash_on_update=retained_options.trash_on_update,
    )
    if value.required_bytes != required_bytes:
        raise ValueError("plan required bytes do not match operations")
    expected_policy_fingerprint = policy_fingerprint(retained_options)
    if value.policy_fingerprint != expected_policy_fingerprint:
        raise ValueError(
            "plan policy fingerprint does not match requested options"
        )

    snapshot = Plan(
        source_root=source_root,
        target_root=target_root,
        source_volume_id=source_volume,
        target_volume_id=target_volume,
        source_volume_evidence=source_evidence,
        target_volume_evidence=target_evidence,
        source_profile=source_profile,
        target_profile=target_profile,
        source_complete=value.source_complete,
        target_complete=value.target_complete,
        operations=operations,
        assignment=assignment,
        preservation=preservation,
        filter_snapshot=filter_snapshot,
        deletion_policy=value.deletion_policy,
        trash_on_update=value.trash_on_update,
        policy_fingerprint=expected_policy_fingerprint,
        required_volumes=required_volumes,
        required_bytes=required_bytes,
        fingerprint=value.fingerprint,
    )
    if value.fingerprint != plan_fingerprint(snapshot):
        raise ValueError("plan fingerprint does not match canonical plan")
    if snapshot != value:
        raise ValueError("plan candidate is not canonical")
    return snapshot


def admit_retained_plan_candidate(
    value: object,
    admission: PlanReviewAdmission,
) -> None:
    """Atomically commit one already validated authoritative plan shape."""

    if type(value) is not Plan:
        raise TypeError("retained plan must be an exact Plan")
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    if type(value.operations) is not tuple:
        raise TypeError("plan operations must be an exact tuple")
    if type(value.assignment) is not Assignment:
        raise TypeError("plan assignment must be an exact Assignment")
    if type(value.assignment.items) is not tuple:
        raise TypeError("plan assignment items must be an exact tuple")
    if type(value.required_volumes) is not frozenset:
        raise TypeError("plan required volumes must be an exact frozenset")

    operation_slots = 0
    for operation in value.operations:
        if type(operation) is not PlanOperation:
            raise TypeError("plan operations must contain exact PlanOperation values")
        if type(operation.dependencies) is not tuple:
            raise TypeError("plan operation dependencies must be an exact tuple")
        operation_slots += 1 + len(operation.dependencies)
    reference_slots = (
        operation_slots
        + len(value.assignment.items)
        + len(value.required_volumes)
    )
    admission.admit(
        domain_rows=len(value.operations),
        domain_bytes=reference_slots * PLAN_SOURCE_REFERENCE_BYTES,
    )
