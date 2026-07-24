"""Pure plan, operation, policy, selection, and capacity contracts."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
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
)
from .pathing import normalize_relative_path, validate_relative_path


OpId = NewType("OpId", str)
PlanFingerprint = NewType("PlanFingerprint", str)


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


@dataclass(frozen=True)
class PreservationPolicy:
    preserve_ads: bool = False
    preserve_created: bool = True
    preserve_acl: bool = False


@dataclass(frozen=True)
class FilterSet:
    patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        canonical = tuple(sorted({pattern.replace("/", "\\") for pattern in self.patterns}))
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


@dataclass(frozen=True)
class DestinationAssignment:
    source_rel_path: str
    source_rel_path_key: str
    target_rel_path: str
    target_rel_path_key: str
    group_id: str | None = None
    conflict: str | None = None

    def __post_init__(self) -> None:
        if self.source_rel_path_key != normalize_relative_path(self.source_rel_path):
            raise ValueError("source assignment key is not canonical")
        if self.target_rel_path_key != normalize_relative_path(self.target_rel_path):
            raise ValueError("target assignment key is not canonical")


@dataclass(frozen=True)
class Assignment:
    policy_name: str
    policy_version: str
    items: tuple[DestinationAssignment, ...]


class DestinationPolicy(Protocol):
    name: str
    version: str

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> Assignment: ...


@dataclass(frozen=True)
class IdentityDestinationPolicy:
    name: str = "identity"
    version: str = "1"

    def assign(
        self,
        records: Sequence[FileRecord],
        meta: Mapping[str, object],
        target: ScanResult,
    ) -> Assignment:
        del meta, target
        items = tuple(
            DestinationAssignment(
                record.rel_path,
                record.rel_path_key,
                validate_relative_path(record.rel_path),
                normalize_relative_path(record.rel_path),
            )
            for record in sorted(records, key=lambda item: (item.rel_path_key, item.rel_path))
        )
        return Assignment(self.name, self.version, items)


@dataclass(frozen=True)
class SyncOptions:
    deletion_policy: DeletionPolicy = DeletionPolicy.TRASH
    preservation: PreservationPolicy = PreservationPolicy()
    filters: FilterSet = FilterSet()
    destination_policy: DestinationPolicy = IdentityDestinationPolicy()
    trash_on_update: bool = True
    propagate_source_casing: bool = False
    internal_mirror_authorized: bool = False

    def __post_init__(self) -> None:
        if self.deletion_policy is DeletionPolicy.MIRROR and not self.internal_mirror_authorized:
            raise ValueError("mirror deletion requires explicit internal authorization")


@dataclass(frozen=True)
class MappingPair:
    source_rel_path_key: str
    target_rel_path: str
    target_rel_path_key: str
    source_identity: FileIdentity
    target_identity: FileIdentity | None

    def __post_init__(self) -> None:
        validate_relative_path(self.target_rel_path)
        if self.target_rel_path_key != normalize_relative_path(self.target_rel_path):
            raise ValueError("mapping target key is not canonical")


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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
        if self.content_bytes < 0:
            raise ValueError("operation content bytes cannot be negative")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("operation dependencies must be unique")

    @property
    def blocked(self) -> bool:
        return self.blocked_reason is not None


@dataclass(frozen=True)
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
        if self.required_bytes < 0:
            raise ValueError("invalid plan capacity snapshot")
        known_ids: set[OpId] = set()
        for operation in self.operations:
            if operation.op_id in known_ids:
                raise ValueError("duplicate operation id")
            if any(dependency not in known_ids for dependency in operation.dependencies):
                raise ValueError("operations must be dependency ordered")
            known_ids.add(operation.op_id)


def re_fullmatch_op_id(value: str) -> bool:
    return len(value) == 32 and all(character in "0123456789abcdef" for character in value)


def _primitive(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {field.name: _primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _primitive(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_primitive(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical JSON while preserving existing valid-Unicode bytes.

    ``backslashreplace`` affects only malformed surrogate code units, which
    JSON can represent with a ``\\uXXXX`` escape. Valid Unicode retains the
    established UTF-8 encoding and therefore its existing fingerprints.
    """

    return json.dumps(
        _primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="backslashreplace")


def deterministic_operation_id(
    kind: OperationKind,
    source_rel_path: str | None,
    target_rel_path: str,
    prior_target_rel_path: str | None,
    reason: OperationReason,
) -> OpId:
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
    for operation in operations:
        if operation.blocked:
            continue
        if operation.kind in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}:
            required += operation.content_bytes
        if (
            trash_on_update
            and not target_profile.supports_hardlinks
            and operation.kind in {OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        ):
            displaced = operation.target_expected or operation.prior_target_expected
            if displaced is not None:
                required += displaced.size
    return required


def policy_fingerprint(options: SyncOptions) -> str:
    payload = {
        "deletion_policy": options.deletion_policy.value,
        "preservation": options.preservation,
        "filters": options.filters,
        "destination_policy": {
            "name": options.destination_policy.name,
            "version": options.destination_policy.version,
        },
        "trash_on_update": options.trash_on_update,
        "propagate_source_casing": options.propagate_source_casing,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def plan_fingerprint(plan: Plan) -> PlanFingerprint:
    payload = asdict(plan)
    payload.pop("fingerprint", None)
    return PlanFingerprint(hashlib.sha256(canonical_json_bytes(payload)).hexdigest())


def serialize_plan(plan: Plan) -> bytes:
    return canonical_json_bytes(plan)


def selection_digest(selection: Sequence[OpId] | frozenset[OpId]) -> bytes:
    return hashlib.sha256(canonical_json_bytes(sorted(str(item) for item in selection))).digest()


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
