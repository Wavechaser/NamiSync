"""Pure deterministic M0 sync planner."""

from __future__ import annotations

from dataclasses import replace
from pathlib import PureWindowsPath
from typing import Iterable, Sequence

from namisync.core.models import (
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    FileStat,
    MetadataSnapshot,
    ScanResult,
)
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    MappingPair,
    MappingSnapshot,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    Scope,
    ScopeKind,
    SyncOptions,
    calculate_required_bytes,
    deterministic_operation_id,
    plan_fingerprint,
    policy_fingerprint,
)


def _depth(path: str) -> int:
    return len(PureWindowsPath(path).parts)


def _parent(path: str) -> str | None:
    parent = str(PureWindowsPath(path).parent)
    return None if parent == "." else parent


def _is_descendant(path: str, directory: str) -> bool:
    path_key = normalize_relative_path(path)
    directory_key = normalize_relative_path(directory)
    return path_key.startswith(directory_key + "\\")


def _metadata_equal(source: FileStat, target: FileStat, granularity_ns: int) -> bool:
    return (
        source.size == target.size
        and abs(source.mtime_ns - target.mtime_ns) <= granularity_ns
        and source.metadata.attributes == target.metadata.attributes
    )


def _group_by_key(records: Iterable[object]) -> dict[str, list[object]]:
    grouped: dict[str, list[object]] = {}
    for record in records:
        grouped.setdefault(record.rel_path_key, []).append(record)  # type: ignore[attr-defined]
    for values in grouped.values():
        values.sort(key=lambda item: item.rel_path)  # type: ignore[attr-defined]
    return grouped


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
    parent = _parent(path)
    while parent is not None:
        operation = created.get(normalize_relative_path(parent))
        if operation is not None:
            return operation
        parent = _parent(parent)
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
) -> Plan:
    """Transform immutable observations and policy into immutable intent."""

    if scope.kind is not ScopeKind.EVERYTHING:
        raise NotImplementedError(f"scope {scope.kind.value!r} is declared but not implemented in M0")

    source_files_all = sorted(source.files, key=lambda item: (item.rel_path_key, item.rel_path))
    target_files_all = sorted(target.files, key=lambda item: (item.rel_path_key, item.rel_path))
    source_files = tuple(record for record in source_files_all if not options.filters.excludes(record.rel_path))
    target_files = tuple(record for record in target_files_all if not options.filters.excludes(record.rel_path))
    source_dirs = tuple(
        record
        for record in sorted(source.directories, key=lambda item: (_depth(item.rel_path) if item.rel_path else 0, item.rel_path_key, item.rel_path))
        if record.rel_path and not options.filters.excludes(record.rel_path)
    )
    target_dirs = tuple(
        record
        for record in sorted(target.directories, key=lambda item: (_depth(item.rel_path) if item.rel_path else 0, item.rel_path_key, item.rel_path))
        if record.rel_path
    )

    assignment = options.destination_policy.assign(source_files, {}, target)
    assignments = _validate_assignment(assignment, source_files)
    source_files_by_key = _group_by_key(source_files)
    target_files_by_key = _group_by_key(target_files)
    target_dirs_by_key = _group_by_key(target_dirs)
    source_dirs_by_key = _group_by_key(source_dirs)

    assigned_target_groups: dict[str, list[DestinationAssignment]] = {}
    for item in assignment.items:
        assigned_target_groups.setdefault(item.target_rel_path_key, []).append(item)
    assigned_target_keys = set(assigned_target_groups)

    required_directory_paths: set[str] = {record.rel_path for record in source_dirs}
    for item in assignment.items:
        parent = _parent(item.target_rel_path)
        while parent is not None:
            required_directory_paths.add(parent)
            parent = _parent(parent)

    mkdir_operations: list[PlanOperation] = []
    created_directories: dict[str, PlanOperation] = {}
    for directory_path in sorted(required_directory_paths, key=lambda value: (_depth(value), normalize_relative_path(value), value)):
        directory_key = normalize_relative_path(directory_path)
        existing_dirs = target_dirs_by_key.get(directory_key, [])
        existing_files = target_files_by_key.get(directory_key, [])
        source_candidates = source_dirs_by_key.get(directory_key, [])
        source_directory = source_candidates[0] if len(source_candidates) == 1 and isinstance(source_candidates[0], DirRecord) else None
        parent_operation = _nearest_created_parent(directory_path, created_directories)
        dependencies = (parent_operation.op_id,) if parent_operation is not None else ()
        if existing_dirs:
            target_directory = (
                existing_dirs[0]
                if len(existing_dirs) == 1 and isinstance(existing_dirs[0], DirRecord)
                else None
            )
            if (
                source_directory is not None
                and target_directory is not None
                and source_directory.rel_path != target_directory.rel_path
            ):
                operation = _blocked_operation(
                    kind=OperationKind.NOOP,
                    source_rel_path=source_directory.rel_path,
                    target_rel_path=target_directory.rel_path,
                    source_expected=source_directory.stat,
                    target_expected=target_directory.stat,
                    intended=source_directory.stat,
                    reason=OperationReason.CASE_MISMATCH,
                    blocked_reason=BlockedReason.CASE_MISMATCH,
                    dependencies=dependencies,
                )
                mkdir_operations.append(operation)
                created_directories[directory_key] = operation
            continue
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
    content_operations: list[PlanOperation] = []
    claimed_target_keys: set[str] = set()
    moved_from_keys: set[str] = set()

    for item in sorted(assignment.items, key=lambda value: (value.target_rel_path_key, value.target_rel_path, value.source_rel_path)):
        source_values = source_files_by_key[item.source_rel_path_key]
        source_record = source_values[0]
        if not isinstance(source_record, FileRecord):
            raise TypeError("source file index contained a non-file record")
        target_values = target_files_by_key.get(item.target_rel_path_key, [])
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
            if source_record.rel_path != target_record.rel_path:
                content_operations.append(
                    _blocked_operation(
                        kind=OperationKind.NOOP,
                        source_rel_path=source_record.rel_path,
                        target_rel_path=target_record.rel_path,
                        source_expected=source_record.stat,
                        target_expected=target_record.stat,
                        intended=source_record.stat,
                        reason=OperationReason.CASE_MISMATCH,
                        blocked_reason=BlockedReason.CASE_MISMATCH,
                        dependencies=dependencies,
                    )
                )
                claimed_target_keys.add(item.target_rel_path_key)
                continue
            matched = _metadata_equal(source_record.stat, target_record.stat, granularity)
            kind = OperationKind.NOOP if matched else OperationKind.UPDATE
            reason = OperationReason.METADATA_MATCH if matched else OperationReason.METADATA_CHANGED
            content_operations.append(
                PlanOperation(
                    op_id=deterministic_operation_id(kind, source_record.rel_path, item.target_rel_path, None, reason),
                    kind=kind,
                    source_rel_path=source_record.rel_path,
                    target_rel_path=item.target_rel_path,
                    source_expected=source_record.stat,
                    target_expected=target_record.stat,
                    intended=source_record.stat,
                    metadata=source_record.metadata,
                    content_bytes=0 if matched else source_record.size,
                    dependencies=dependencies,
                    reason=reason,
                )
            )
            claimed_target_keys.add(item.target_rel_path_key)
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

    removal_operations: list[PlanOperation] = []
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

    blocked_operations: list[PlanOperation] = []
    visible_unsupported: dict[tuple[str, str], object] = {}
    for record in (*source.unsupported, *target.unsupported):
        if options.filters.excludes(record.rel_path):
            continue
        visible_unsupported[(record.rel_path_key, record.rel_path)] = record
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

    cleanup_operations: list[PlanOperation] = []
    cleanup_by_key: dict[str, PlanOperation] = {}
    desired_directory_keys = {normalize_relative_path(path) for path in required_directory_paths}
    removal_by_path: dict[str, PlanOperation] = {}
    for operation in (*content_operations, *removal_operations):
        if operation.kind in {OperationKind.TRASH, OperationKind.DELETE}:
            removal_by_path[operation.target_rel_path] = operation
        elif operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE} and operation.prior_target_rel_path:
            removal_by_path[operation.prior_target_rel_path] = operation
    for directory in sorted(target_dirs, key=lambda item: (-_depth(item.rel_path), item.rel_path_key, item.rel_path)):
        if (
            options.deletion_policy is DeletionPolicy.ADDITIVE
            or directory.rel_path_key in desired_directory_keys
            or options.filters.excludes(directory.rel_path)
        ):
            continue
        excluded_child = any(
            bool(record.rel_path)
            and _is_descendant(record.rel_path, directory.rel_path)
            and options.filters.excludes(record.rel_path)
            for record in (*target.files, *target.directories)
            if record.rel_path != directory.rel_path
        )
        unsupported_child = any(_is_descendant(record.rel_path, directory.rel_path) for record in target.unsupported)
        remaining_file = any(
            _is_descendant(record.rel_path, directory.rel_path) and record.rel_path_key not in removed_file_keys
            for record in target.files
        )
        remaining_directory = any(
            _parent(child.rel_path) == directory.rel_path
            and child.rel_path_key not in cleanup_by_key
            and child.rel_path_key not in desired_directory_keys
            for child in target_dirs
        )
        if excluded_child or unsupported_child or remaining_file or remaining_directory:
            continue
        dependencies = [
            operation.op_id
            for path, operation in removal_by_path.items()
            if path == directory.rel_path or _is_descendant(path, directory.rel_path)
        ]
        dependencies.extend(
            operation.op_id
            for key, operation in cleanup_by_key.items()
            if _parent(operation.target_rel_path) == directory.rel_path
        )
        dependencies = sorted(set(dependencies), key=str)
        cleanup = PlanOperation(
            op_id=deterministic_operation_id(OperationKind.DELETE, None, directory.rel_path, None, OperationReason.DIRECTORY_CLEANUP),
            kind=OperationKind.DELETE,
            source_rel_path=None,
            target_rel_path=directory.rel_path,
            source_expected=None,
            target_expected=directory.stat,
            intended=None,
            dependencies=tuple(dependencies),
            reason=OperationReason.DIRECTORY_CLEANUP,
        )
        cleanup_operations.append(cleanup)
        cleanup_by_key[directory.rel_path_key] = cleanup

    operations = tuple((*mkdir_operations, *content_operations, *removal_operations, *blocked_operations, *cleanup_operations))
    required_bytes = calculate_required_bytes(
        operations,
        target_profile=target.profile,
        trash_on_update=options.trash_on_update,
    )
    required_volumes = frozenset(
        volume for volume in (source.volume_id, target.volume_id) if volume is not None
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
        worker_count=options.worker_count,
        required_volumes=required_volumes,
        required_bytes=required_bytes,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))
