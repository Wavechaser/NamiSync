"""Pure plan, operation, policy, selection, and capacity contracts."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Mapping, NewType, Protocol, Sequence

from .models import (
    CapabilityProfile,
    FileIdentity,
    FileRecord,
    FileStat,
    MetadataSnapshot,
    Root,
    ScanResult,
    VolumeEvidence,
    VolumeId,
    capability_profile_projection,
    file_stat_projection,
    metadata_projection,
    root_projection,
    volume_evidence_projection,
    volume_id_projection,
)
from .pathing import (
    fold_validated_path,
    normalize_relative_path,
    validate_relative_path,
)
from .review import (
    MAX_PLAN_DOMAIN_RETAINED_BYTES,
    MAX_PLAN_REVIEW_ROWS,
    ReviewFactLimitExceeded,
    _PlanReviewLimitSignal,
)
from .scalars import (
    ScalarDomainError,
    checked_add_signed_64,
    require_signed_64,
    require_utf8_text,
)


OpId = NewType("OpId", str)
PlanFingerprint = NewType("PlanFingerprint", str)
FILTER_PATTERN_LIMIT = 64
FILTER_PATTERN_UTF8_LIMIT = 1_024
FILTER_TOTAL_UTF8_LIMIT = 16_384
ASSIGNMENT_ITEM_LIMIT = MAX_PLAN_REVIEW_ROWS
# A one-way plan can name only its source and target volumes.
PLAN_REQUIRED_VOLUME_LIMIT = 2
ASSIGNMENT_TEXT_UTF8_LIMIT = MAX_PLAN_DOMAIN_RETAINED_BYTES


class DeletionPolicy(StrEnum):
    TRASH = "trash"
    ADDITIVE = "additive"
    MIRROR = "mirror"


class OperationKind(StrEnum):
    COPY = "copy"
    UPDATE = "update"
    MOVE = "move"
    MOVE_UPDATE = "move_update"
    RECASE = "recase"
    MKDIR = "mkdir"
    TRASH = "trash"
    DELETE = "delete"
    NOOP = "noop"


class OperationReason(StrEnum):
    SOURCE_ONLY = "source_only"
    METADATA_CHANGED = "metadata_changed"
    METADATA_MATCH = "metadata_match"
    IDENTITY_RENAME = "identity_rename"
    IDENTITY_RENAME_CHANGED = "identity_rename_changed"
    REQUIRED_DIRECTORY = "required_directory"
    EMPTY_DIRECTORY = "empty_directory"
    TARGET_ONLY = "target_only"
    DIRECTORY_CLEANUP = "directory_cleanup"
    UNSUPPORTED = "unsupported"
    CASE_MISMATCH = "case_mismatch"
    UNICODE_NORMALIZATION_MISMATCH = "unicode_normalization_mismatch"
    CASE_COLLISION = "case_collision"
    TYPE_COLLISION = "type_collision"
    POLICY_COLLISION = "policy_collision"


class BlockedReason(StrEnum):
    UNSUPPORTED = "unsupported"
    CASE_MISMATCH = "case_mismatch"
    CASE_COLLISION = "case_collision"
    TYPE_COLLISION = "type_collision"
    DESTINATION_COLLISION = "destination_collision"
    BLOCKED_DEPENDENCY = "blocked_dependency"


@dataclass(frozen=True, slots=True)
class PreservationPolicy:
    preserve_ads: bool = False
    preserve_created: bool = True
    preserve_acl: bool = False

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.preserve_ads,
                self.preserve_created,
                self.preserve_acl,
            )
        ):
            raise TypeError("preservation fields must be bools")


@dataclass(frozen=True, slots=True)
class FilterSet:
    patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_filter_patterns(self.patterns)
        canonical = tuple(
            sorted({pattern.replace("/", "\\") for pattern in self.patterns})
        )
        if canonical != self.patterns:
            object.__setattr__(self, "patterns", canonical)

    def excludes(self, rel_path: str) -> bool:
        key = normalize_relative_path(rel_path)
        candidate_keys = [key]
        parent = str(PureWindowsPath(rel_path).parent)
        while parent != ".":
            candidate_keys.append(normalize_relative_path(parent))
            parent = str(PureWindowsPath(parent).parent)
        for pattern in self.patterns:
            pattern_key = "".join(
                character.upper() if len(character.upper()) == 1 else character
                for character in pattern
            )
            if any(fnmatch.fnmatchcase(candidate, pattern_key) for candidate in candidate_keys):
                return True
        return False


@dataclass(frozen=True, slots=True)
class DestinationAssignment:
    source_rel_path: str
    source_rel_path_key: str
    target_rel_path: str
    target_rel_path_key: str
    group_id: str | None = None
    conflict: str | None = None

    def __post_init__(self) -> None:
        _require_destination_assignment_fields(self)


def _require_filter_patterns(patterns: object) -> None:
    if type(patterns) is not tuple:
        raise TypeError("filter patterns must be a tuple")
    if len(patterns) > FILTER_PATTERN_LIMIT:
        raise ValueError("filter patterns exceed the 64-pattern limit")
    total_bytes = 0
    for pattern in patterns:
        require_utf8_text(
            pattern,
            "filter pattern",
            minimum_bytes=1,
            maximum_bytes=FILTER_PATTERN_UTF8_LIMIT,
        )
        # The individual guard makes this bounded temporary at most 1,024
        # bytes. Charge the supplied spelling before slash normalization,
        # duplicate removal, or sorting can change its shape.
        total_bytes += len(pattern.encode("utf-8"))
        if total_bytes > FILTER_TOTAL_UTF8_LIMIT:
            raise ValueError("filter patterns exceed the UTF-8 total limit")


def validate_filter_set(value: object) -> FilterSet:
    """Re-admit one exact, canonical filter snapshot without copying it."""

    if type(value) is not FilterSet:
        raise TypeError("filter snapshot requires FilterSet")
    _require_filter_patterns(value.patterns)
    if tuple(
        sorted({pattern.replace("/", "\\") for pattern in value.patterns})
    ) != value.patterns:
        raise ValueError("filter snapshot is not canonical")
    return value


def _require_assignment_text(
    value: object,
    field_name: str,
    *,
    allow_none: bool = False,
    require_nonempty: bool = False,
) -> str | None:
    if value is None and allow_none:
        return None
    return require_utf8_text(
        value,
        field_name,
        minimum_bytes=1 if require_nonempty else 0,
        maximum_bytes=ASSIGNMENT_TEXT_UTF8_LIMIT,
    )


def _require_destination_assignment_fields(
    value: DestinationAssignment,
) -> None:
    for field_name, path in (
        ("source assignment path", value.source_rel_path),
        ("source assignment key", value.source_rel_path_key),
        ("target assignment path", value.target_rel_path),
        ("target assignment key", value.target_rel_path_key),
    ):
        if type(path) is not str:
            raise TypeError(f"{field_name} must be text")
    _require_assignment_text(
        value.group_id,
        "assignment group id",
        allow_none=True,
    )
    _require_assignment_text(
        value.conflict,
        "assignment conflict",
        allow_none=True,
    )
    if value.source_rel_path_key != normalize_relative_path(
        value.source_rel_path
    ):
        raise ValueError("source assignment key is not canonical")
    if value.target_rel_path_key != normalize_relative_path(
        value.target_rel_path
    ):
        raise ValueError("target assignment key is not canonical")


@dataclass(frozen=True, slots=True)
class Assignment:
    policy_name: str
    policy_version: str
    items: tuple[DestinationAssignment, ...]

    def __post_init__(self) -> None:
        _require_assignment_fields(self)


def _require_assignment_fields(value: Assignment) -> None:
    _require_assignment_text(
        value.policy_name,
        "assignment policy name",
        require_nonempty=True,
    )
    _require_assignment_text(
        value.policy_version,
        "assignment policy version",
        require_nonempty=True,
    )
    if type(value.items) is not tuple:
        raise TypeError("assignment items must be a tuple")
    if len(value.items) > ASSIGNMENT_ITEM_LIMIT:
        raise ValueError("assignment items exceed the plan row limit")
    for item in value.items:
        if type(item) is not DestinationAssignment:
            raise TypeError(
                "assignment items must contain DestinationAssignment values"
            )
        _require_destination_assignment_fields(item)


def validate_assignment(value: object) -> Assignment:
    """Re-admit an exact assignment returned by a policy or codec."""

    if type(value) is not Assignment:
        raise TypeError("destination policy must return an Assignment")
    _require_assignment_fields(value)
    return value


class DestinationPolicy(Protocol):
    name: str
    version: str

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> Assignment: ...


@dataclass(frozen=True, slots=True)
class IdentityDestinationPolicy:
    name: str = "identity"
    version: str = "1"

    def __post_init__(self) -> None:
        _require_assignment_text(
            self.name,
            "destination policy name",
            require_nonempty=True,
        )
        _require_assignment_text(
            self.version,
            "destination policy version",
            require_nonempty=True,
        )

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> Assignment:
        del meta, target
        items: list[DestinationAssignment] = []
        for record in sorted(
            records,
            key=lambda item: (item.rel_path_key, item.rel_path),
        ):
            canonical = validate_relative_path(record.rel_path)
            items.append(
                DestinationAssignment(
                    record.rel_path,
                    record.rel_path_key,
                    canonical,
                    fold_validated_path(canonical),
                )
            )
        return Assignment(self.name, self.version, tuple(items))


@dataclass(frozen=True, slots=True)
class SyncOptions:
    deletion_policy: DeletionPolicy = DeletionPolicy.TRASH
    preservation: PreservationPolicy = PreservationPolicy()
    filters: FilterSet = FilterSet()
    destination_policy: DestinationPolicy = IdentityDestinationPolicy()
    trash_on_update: bool = True
    propagate_source_casing: bool = False
    internal_mirror_authorized: bool = False

    def __post_init__(self) -> None:
        if type(self.deletion_policy) is not DeletionPolicy:
            raise TypeError("deletion policy has the wrong type")
        if type(self.preservation) is not PreservationPolicy:
            raise TypeError("preservation policy has the wrong type")
        PreservationPolicy(
            self.preservation.preserve_ads,
            self.preservation.preserve_created,
            self.preservation.preserve_acl,
        )
        validate_filter_set(self.filters)
        for field_name, value in (
            ("trash_on_update", self.trash_on_update),
            ("propagate_source_casing", self.propagate_source_casing),
            ("internal_mirror_authorized", self.internal_mirror_authorized),
        ):
            if type(value) is not bool:
                raise TypeError(f"{field_name} must be a bool")
        if self.deletion_policy is DeletionPolicy.MIRROR and not self.internal_mirror_authorized:
            raise ValueError("mirror deletion requires explicit internal authorization")


@dataclass(frozen=True, slots=True)
class MappingPair:
    source_rel_path_key: str
    target_rel_path: str
    target_rel_path_key: str
    source_identity: FileIdentity
    target_identity: FileIdentity | None

    def __post_init__(self) -> None:
        canonical = validate_relative_path(self.target_rel_path)
        if self.target_rel_path_key != fold_validated_path(canonical):
            raise ValueError("mapping target key is not canonical")


@dataclass(frozen=True, slots=True)
class MappingSnapshot:
    source_volume_id: VolumeId | None = None
    target_volume_id: VolumeId | None = None
    pairs: tuple[MappingPair, ...] = ()
    ambiguous_source_keys: frozenset[str] = frozenset()
    disqualified_source_identities: frozenset[FileIdentity] = frozenset()
    disqualified_target_identities: frozenset[FileIdentity] = frozenset()

    @classmethod
    def empty(
        cls,
        source_volume_id: VolumeId | None = None,
        target_volume_id: VolumeId | None = None,
    ) -> MappingSnapshot:
        return cls(source_volume_id, target_volume_id)


class ScopeKind(StrEnum):
    EVERYTHING = "everything"
    PATTERN = "pattern"
    EXPLICIT = "explicit"
    RECORDED_RUN = "recorded_run"


@dataclass(frozen=True, slots=True)
class Scope:
    kind: ScopeKind
    value: str | tuple[str, ...] | None = None

    @classmethod
    def everything(cls) -> Scope:
        return cls(ScopeKind.EVERYTHING)

    @classmethod
    def pattern(cls, pattern: str) -> Scope:
        return cls(ScopeKind.PATTERN, pattern)

    @classmethod
    def explicit(cls, candidate_ids: Sequence[str]) -> Scope:
        return cls(ScopeKind.EXPLICIT, tuple(sorted(set(candidate_ids))))

    @classmethod
    def from_run(cls, token: str) -> Scope:
        return cls(ScopeKind.RECORDED_RUN, token)


@dataclass(frozen=True, slots=True)
class PlanOperation:
    op_id: OpId
    kind: OperationKind
    source_rel_path: str | None
    target_rel_path: str
    source_expected: FileStat | None
    target_expected: FileStat | None
    intended: FileStat | None
    prior_target_rel_path: str | None = None
    prior_target_expected: FileStat | None = None
    metadata: MetadataSnapshot | None = None
    content_bytes: int = 0
    dependencies: tuple[OpId, ...] = ()
    reason: OperationReason = OperationReason.SOURCE_ONLY
    blocked_reason: BlockedReason | None = None

    def __post_init__(self) -> None:
        if not re_fullmatch_op_id(str(self.op_id)):
            raise ValueError("operation id must be 32 lowercase hexadecimal characters")
        if self.source_rel_path is not None:
            validate_relative_path(self.source_rel_path)
        validate_relative_path(self.target_rel_path)
        if self.prior_target_rel_path is not None:
            validate_relative_path(self.prior_target_rel_path)
        require_signed_64(self.content_bytes, "operation content bytes")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("operation dependencies must be unique")

    @property
    def blocked(self) -> bool:
        return self.blocked_reason is not None


@dataclass(frozen=True, slots=True)
class Plan:
    source_root: Root
    target_root: Root
    source_volume_id: VolumeId | None
    target_volume_id: VolumeId | None
    source_volume_evidence: VolumeEvidence | None
    target_volume_evidence: VolumeEvidence | None
    source_profile: CapabilityProfile
    target_profile: CapabilityProfile
    source_complete: bool
    target_complete: bool
    operations: tuple[PlanOperation, ...]
    assignment: Assignment
    preservation: PreservationPolicy
    filter_snapshot: FilterSet
    deletion_policy: DeletionPolicy
    trash_on_update: bool
    policy_fingerprint: str
    required_volumes: frozenset[VolumeId]
    required_bytes: int
    fingerprint: PlanFingerprint

    def __post_init__(self) -> None:
        require_signed_64(self.required_bytes, "plan required bytes")
        if type(self.required_volumes) is not frozenset:
            raise TypeError("plan required volumes must be a frozenset")
        if len(self.required_volumes) > PLAN_REQUIRED_VOLUME_LIMIT:
            raise ValueError("plan required volumes exceed the endpoint limit")
        for volume in self.required_volumes:
            if type(volume) is not VolumeId:
                raise TypeError("plan required volumes must contain VolumeId values")
            VolumeId(volume.serial, volume.fs_type)
        known_ids: set[OpId] = set()
        for operation in self.operations:
            if operation.op_id in known_ids:
                raise ValueError("duplicate operation id")
            if any(dependency not in known_ids for dependency in operation.dependencies):
                raise ValueError("operations must be dependency ordered")
            known_ids.add(operation.op_id)


def re_fullmatch_op_id(value: str) -> bool:
    return len(value) == 32 and all(character in "0123456789abcdef" for character in value)


def _require_json_tree(value: object) -> None:
    if value is None or type(value) in (str, bool, int, float):
        return
    if type(value) is list:
        for item in value:
            _require_json_tree(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("canonical JSON keys must be plain strings")
            _require_json_tree(item)
        return
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Encode an explicitly projected, closed JSON tree without coercion.

    Strings and keys must contain Unicode scalar values, not surrogate code
    units. Strict UTF-8 preserves established bytes for every accepted string.
    """

    _require_json_tree(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")


def preservation_policy_projection(value: PreservationPolicy) -> dict[str, object]:
    if type(value) is not PreservationPolicy:
        raise TypeError("preservation projection requires PreservationPolicy")
    PreservationPolicy(
        value.preserve_ads,
        value.preserve_created,
        value.preserve_acl,
    )
    return {
        "preserve_ads": value.preserve_ads,
        "preserve_created": value.preserve_created,
        "preserve_acl": value.preserve_acl,
    }


def filter_set_projection(value: FilterSet) -> dict[str, object]:
    validate_filter_set(value)
    return {"patterns": list(value.patterns)}


def destination_assignment_projection(value: DestinationAssignment) -> dict[str, object]:
    if type(value) is not DestinationAssignment:
        raise TypeError("destination projection requires DestinationAssignment")
    _require_destination_assignment_fields(value)
    return {
        "source_rel_path": value.source_rel_path,
        "source_rel_path_key": value.source_rel_path_key,
        "target_rel_path": value.target_rel_path,
        "target_rel_path_key": value.target_rel_path_key,
        "group_id": value.group_id,
        "conflict": value.conflict,
    }


def assignment_projection(value: Assignment) -> dict[str, object]:
    validate_assignment(value)
    return {
        "policy_name": value.policy_name,
        "policy_version": value.policy_version,
        "items": [destination_assignment_projection(item) for item in value.items],
    }


# Retain the established private names used by the frozen identity-contract
# tests while exposing descriptive public projection helpers to codecs.
_preservation_projection = preservation_policy_projection
_filter_projection = filter_set_projection
_destination_assignment_projection = destination_assignment_projection
_assignment_projection = assignment_projection


def operation_projection(value: PlanOperation) -> dict[str, object]:
    if type(value) is not PlanOperation:
        raise TypeError("operation projection requires PlanOperation")
    if (
        type(value.kind) is not OperationKind
        or type(value.reason) is not OperationReason
        or (value.blocked_reason is not None and type(value.blocked_reason) is not BlockedReason)
        or type(value.dependencies) is not tuple
    ):
        raise TypeError("operation projection requires typed reasons and tuple dependencies")
    return {
        "op_id": value.op_id,
        "kind": value.kind.value,
        "source_rel_path": value.source_rel_path,
        "target_rel_path": value.target_rel_path,
        "source_expected": file_stat_projection(value.source_expected),
        "target_expected": file_stat_projection(value.target_expected),
        "intended": file_stat_projection(value.intended),
        "prior_target_rel_path": value.prior_target_rel_path,
        "prior_target_expected": file_stat_projection(value.prior_target_expected),
        "metadata": metadata_projection(value.metadata),
        "content_bytes": value.content_bytes,
        "dependencies": list(value.dependencies),
        "reason": value.reason.value,
        "blocked_reason": None if value.blocked_reason is None else value.blocked_reason.value,
    }


def plan_projection(value: Plan) -> dict[str, object]:
    if type(value) is not Plan:
        raise TypeError("plan projection requires Plan")
    if (
        type(value.deletion_policy) is not DeletionPolicy
        or type(value.operations) is not tuple
        or type(value.required_volumes) is not frozenset
    ):
        raise TypeError("plan projection requires typed policy, operations, and volumes")
    if len(value.required_volumes) > PLAN_REQUIRED_VOLUME_LIMIT:
        raise ValueError("plan required volumes exceed the endpoint limit")
    volumes = [volume_id_projection(volume) for volume in value.required_volumes]
    # Retain the existing JSON sort key, not VolumeId's dataclass ordering.
    volumes.sort(key=lambda item: json.dumps(item, sort_keys=True))
    return {
        "source_root": root_projection(value.source_root),
        "target_root": root_projection(value.target_root),
        "source_volume_id": volume_id_projection(value.source_volume_id),
        "target_volume_id": volume_id_projection(value.target_volume_id),
        "source_volume_evidence": volume_evidence_projection(value.source_volume_evidence),
        "target_volume_evidence": volume_evidence_projection(value.target_volume_evidence),
        "source_profile": capability_profile_projection(value.source_profile),
        "target_profile": capability_profile_projection(value.target_profile),
        "source_complete": value.source_complete,
        "target_complete": value.target_complete,
        "operations": [operation_projection(operation) for operation in value.operations],
        "assignment": assignment_projection(value.assignment),
        "preservation": preservation_policy_projection(value.preservation),
        "filter_snapshot": filter_set_projection(value.filter_snapshot),
        "deletion_policy": value.deletion_policy.value,
        "trash_on_update": value.trash_on_update,
        "policy_fingerprint": value.policy_fingerprint,
        "required_volumes": volumes,
        "required_bytes": value.required_bytes,
        "fingerprint": value.fingerprint,
    }


def deterministic_operation_id(
    kind: OperationKind,
    source_rel_path: str | None,
    target_rel_path: str,
    prior_target_rel_path: str | None,
    reason: OperationReason,
) -> OpId:
    if type(kind) is not OperationKind or type(reason) is not OperationReason:
        raise TypeError("operation intent requires typed kind and reason")
    intent = {
        "kind": kind.value,
        "source": source_rel_path,
        "target": target_rel_path,
        "prior_target": prior_target_rel_path,
        "reason": reason.value,
    }
    return OpId(hashlib.sha256(canonical_json_bytes(intent)).hexdigest()[:32])


def calculate_required_bytes(
    operations: Sequence[PlanOperation],
    *,
    target_profile: CapabilityProfile,
    trash_on_update: bool,
) -> int:
    """Return a conservative start-of-run free-space requirement."""

    required = 0
    try:
        for operation in operations:
            if operation.blocked:
                continue
            if operation.kind in {
                OperationKind.COPY,
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
            }:
                required = checked_add_signed_64(
                    required,
                    operation.content_bytes,
                    "plan logical bytes",
                )
            if (
                trash_on_update
                and not target_profile.supports_hardlinks
                and operation.kind
                in {OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
            ):
                displaced = (
                    operation.target_expected
                    or operation.prior_target_expected
                )
                if displaced is not None:
                    required = checked_add_signed_64(
                        required,
                        displaced.size,
                        "plan logical bytes",
                    )
    except ScalarDomainError as error:
        raise _PlanReviewLimitSignal(
            ReviewFactLimitExceeded.plan_logical_bytes()
        ) from error
    return required


def policy_fingerprint(options: SyncOptions) -> str:
    if type(options) is not SyncOptions or type(options.deletion_policy) is not DeletionPolicy:
        raise TypeError("policy fingerprint requires SyncOptions with DeletionPolicy")
    policy_name = _require_assignment_text(
        options.destination_policy.name,
        "destination policy name",
        require_nonempty=True,
    )
    policy_version = _require_assignment_text(
        options.destination_policy.version,
        "destination policy version",
        require_nonempty=True,
    )
    payload = {
        "deletion_policy": options.deletion_policy.value,
        "preservation": preservation_policy_projection(options.preservation),
        "filters": filter_set_projection(options.filters),
        "destination_policy": {
            "name": policy_name,
            "version": policy_version,
        },
        "trash_on_update": options.trash_on_update,
        "propagate_source_casing": options.propagate_source_casing,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def plan_fingerprint(plan: Plan) -> PlanFingerprint:
    payload = plan_projection(plan)
    del payload["fingerprint"]
    return PlanFingerprint(hashlib.sha256(canonical_json_bytes(payload)).hexdigest())


def serialize_plan(plan: Plan) -> bytes:
    return canonical_json_bytes(plan_projection(plan))


def selection_digest(selection: Sequence[OpId] | frozenset[OpId]) -> bytes:
    return hashlib.sha256(canonical_json_bytes(sorted(selection))).digest()


def quarantined_operation_ids(
    operations: Sequence[PlanOperation],
) -> frozenset[OpId]:
    """Return nonblocked operations whose paths overlap blocked correspondence."""

    blocked_source_paths = {
        normalize_relative_path(operation.source_rel_path)
        for operation in operations
        if operation.blocked and operation.source_rel_path is not None
    }
    blocked_target_paths = {
        normalize_relative_path(path)
        for operation in operations
        if operation.blocked
        for path in (operation.target_rel_path, operation.prior_target_rel_path)
        if path is not None
    }
    quarantined: set[OpId] = set()
    for operation in operations:
        if operation.blocked:
            continue
        if operation.source_rel_path is not None and _inside_any_region(
            normalize_relative_path(operation.source_rel_path),
            blocked_source_paths,
        ):
            quarantined.add(operation.op_id)
            continue
        target_paths = {normalize_relative_path(operation.target_rel_path)}
        if operation.prior_target_rel_path is not None:
            target_paths.add(normalize_relative_path(operation.prior_target_rel_path))
        if any(
            _inside_any_region(path, blocked_target_paths)
            for path in target_paths
        ):
            quarantined.add(operation.op_id)
            continue
        destructive_paths: set[str] = set()
        if operation.kind in {OperationKind.TRASH, OperationKind.DELETE}:
            destructive_paths.add(normalize_relative_path(operation.target_rel_path))
        elif (
            operation.kind in {OperationKind.MOVE, OperationKind.MOVE_UPDATE}
            and operation.prior_target_rel_path is not None
        ):
            destructive_paths.add(
                normalize_relative_path(operation.prior_target_rel_path)
            )
        if any(
            _same_or_descendant(blocked, destructive)
            for destructive in destructive_paths
            for blocked in blocked_target_paths
        ):
            quarantined.add(operation.op_id)
    return frozenset(quarantined)


def _inside_any_region(path: str, regions: set[str]) -> bool:
    return any(_same_or_descendant(path, region) for region in regions)


def _same_or_descendant(path: str, ancestor: str) -> bool:
    return path == ancestor or path.startswith(ancestor + "\\")
