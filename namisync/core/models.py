"""Immutable filesystem observation contracts shared by domain modules."""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PureWindowsPath

from .pathing import (
    normalize_relative_path,
    relative_path_parent,
    validate_relative_path,
)
from .scalars import (
    MAX_DIAGNOSTIC_UTF8_BYTES,
    MAX_FILE_INDEX_128,
    MAX_REQUEST_ID_UTF8_BYTES,
    MAX_SAFE_INTEGER,
    file_index_128_to_text,
    bounded_utf8_text,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
    require_utf16_text,
    require_utf8_text,
)


# Windows attributes that execution deliberately propagates from source to target.
MANAGED_FILE_ATTRIBUTE_MASK = 0x00000001 | 0x00000002 | 0x00000004 | 0x00002000
MAX_VOLUME_TEXT_UTF16_UNITS = 260
# Inventory root identifiers retain the complete admitted request id plus the
# longest production suffix (``:refresh:`` and one SafeInt generation) and the
# ``inventory:`` namespace. Other production root-id grammars are shorter.
MAX_ROOT_ID_UTF8_BYTES = (
    MAX_REQUEST_ID_UTF8_BYTES
    + len("inventory:".encode("utf-8"))
    + len(":refresh:".encode("utf-8"))
    + len(str(MAX_SAFE_INTEGER).encode("ascii"))
)
SCAN_SCOPE_ENTRY_LIMIT = 120_000


class EntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True, order=True)
class VolumeId:
    serial: str
    fs_type: str

    def __post_init__(self) -> None:
        _require_volume_id_fields(self)


@dataclass(frozen=True)
class VolumeEvidence:
    label: str | None = None
    device_id: str | None = None
    clone_ambiguous: bool = False

    def __post_init__(self) -> None:
        _require_volume_evidence_fields(self)


@dataclass(frozen=True)
class CapabilityProfile:
    fs_type: str
    mtime_granularity_ns: int
    stable_file_identity: bool
    incurs_seek_penalty: bool | None
    max_path: int
    supports_ads: bool
    supports_hardlinks: bool

    def __post_init__(self) -> None:
        _require_capability_profile_fields(self)


def _require_volume_id_fields(value: VolumeId) -> None:
    require_utf16_text(
        value.serial,
        "volume serial",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )
    require_utf16_text(
        value.fs_type,
        "volume filesystem type",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )


def _require_volume_evidence_fields(value: VolumeEvidence) -> None:
    if value.label is not None:
        require_utf16_text(
            value.label,
            "volume label",
            maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        )
    if value.device_id is not None:
        require_utf16_path(value.device_id, "volume device path")
    if type(value.clone_ambiguous) is not bool:
        raise TypeError("volume clone ambiguity must be a bool")


def _require_capability_profile_fields(value: CapabilityProfile) -> None:
    require_utf16_text(
        value.fs_type,
        "capability filesystem type",
        maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
        allow_empty=False,
    )
    for field_name, field_value in (
        ("stable file identity", value.stable_file_identity),
        ("supports ADS", value.supports_ads),
        ("supports hardlinks", value.supports_hardlinks),
    ):
        if type(field_value) is not bool:
            raise TypeError(f"{field_name} must be a bool")
    if (
        value.incurs_seek_penalty is not None
        and type(value.incurs_seek_penalty) is not bool
    ):
        raise TypeError("seek penalty must be a bool or None")
    require_signed_64(
        value.mtime_granularity_ns,
        "mtime granularity",
    )
    if value.mtime_granularity_ns == 0:
        raise ValueError("mtime granularity must be positive")
    require_safe_int(value.max_path, "maximum path")
    if value.max_path == 0:
        raise ValueError("maximum path must be positive")
    if value.max_path > 32_767:
        raise ValueError("maximum path exceeds the UTF-16 path bound")


@dataclass(frozen=True, order=True)
class FileIdentity:
    volume_serial: str
    file_index: int

    def __post_init__(self) -> None:
        if (
            type(self.volume_serial) is not str
            or not self.volume_serial
            or type(self.file_index) is not int
            or not 0 <= self.file_index <= MAX_FILE_INDEX_128
        ):
            raise ValueError("invalid file identity")
        require_utf16_text(
            self.volume_serial,
            "file identity volume serial",
            maximum_units=MAX_VOLUME_TEXT_UTF16_UNITS,
            allow_empty=False,
        )


@dataclass(frozen=True)
class MetadataSnapshot:
    attributes: int
    created_ns: int | None

    def __post_init__(self) -> None:
        require_safe_int(self.attributes, "file attributes")
        if self.created_ns is not None:
            require_signed_64(self.created_ns, "creation time")


@dataclass(frozen=True)
class FileStat:
    kind: EntryKind
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None
    nlink: int
    metadata: MetadataSnapshot

    def __post_init__(self) -> None:
        if type(self.kind) is not EntryKind:
            raise TypeError("file stat kind has the wrong type")
        require_signed_64(self.size, "file size")
        require_signed_64(self.mtime_ns, "file modification time")
        if self.file_identity is not None:
            if type(self.file_identity) is not FileIdentity:
                raise TypeError("file stat identity has the wrong type")
            FileIdentity(
                self.file_identity.volume_serial,
                self.file_identity.file_index,
            )
        require_safe_int(self.nlink, "file link count")
        if self.nlink < 1:
            raise ValueError("link count must be positive")
        if type(self.metadata) is not MetadataSnapshot:
            raise TypeError("file stat metadata has the wrong type")
        MetadataSnapshot(self.metadata.attributes, self.metadata.created_ns)


@dataclass(frozen=True)
class Root:
    path: str
    root_id: str

    def __post_init__(self) -> None:
        try:
            require_utf16_path(self.path, "root path")
        except TypeError:
            raise
        except ValueError as error:
            raise ValueError("root path is invalid") from error
        if not self.path:
            raise ValueError("root path is invalid")
        require_utf8_text(
            self.root_id,
            "root id",
            minimum_bytes=1,
            maximum_bytes=MAX_ROOT_ID_UTF8_BYTES,
        )


@dataclass(frozen=True)
class FileRecord:
    rel_path: str
    rel_path_key: str
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None
    nlink: int
    metadata: MetadataSnapshot

    def __post_init__(self) -> None:
        if type(self.rel_path_key) is not str:
            raise TypeError("file path key must be text")
        canonical = validate_relative_path(self.rel_path)
        if self.rel_path_key != normalize_relative_path(canonical):
            raise ValueError("file path key is not canonical")
        FileStat(EntryKind.FILE, self.size, self.mtime_ns, self.file_identity, self.nlink, self.metadata)

    @property
    def stat(self) -> FileStat:
        return FileStat(
            EntryKind.FILE,
            self.size,
            self.mtime_ns,
            self.file_identity,
            self.nlink,
            self.metadata,
        )


@dataclass(frozen=True)
class DirRecord:
    rel_path: str
    rel_path_key: str
    mtime_ns: int
    metadata: MetadataSnapshot
    file_identity: FileIdentity | None
    nlink: int = 1

    def __post_init__(self) -> None:
        if type(self.rel_path_key) is not str:
            raise TypeError("directory path key must be text")
        canonical = validate_relative_path(self.rel_path, allow_root=True)
        if self.rel_path_key != normalize_relative_path(canonical, allow_root=True):
            raise ValueError("directory path key is not canonical")
        FileStat(EntryKind.DIRECTORY, 0, self.mtime_ns, self.file_identity, self.nlink, self.metadata)

    @property
    def stat(self) -> FileStat:
        return FileStat(
            EntryKind.DIRECTORY,
            0,
            self.mtime_ns,
            self.file_identity,
            self.nlink,
            self.metadata,
        )


class UnsupportedReason(StrEnum):
    PLACEHOLDER = "placeholder"
    REPARSE_POINT = "reparse_point"
    ACCESS_DENIED = "access_denied"
    DISAPPEARED = "disappeared"
    UNKNOWN_TYPE = "unknown_type"


@dataclass(frozen=True)
class UnsupportedRecord:
    rel_path: str
    rel_path_key: str
    reason: UnsupportedReason
    kind: EntryKind | None = None

    def __post_init__(self) -> None:
        if type(self.rel_path_key) is not str:
            raise TypeError("unsupported path key must be text")
        if type(self.reason) is not UnsupportedReason:
            raise TypeError("unsupported record reason has the wrong type")
        if self.kind is not None and type(self.kind) is not EntryKind:
            raise TypeError("unsupported record kind has the wrong type")
        canonical = validate_relative_path(self.rel_path)
        if self.rel_path_key != normalize_relative_path(canonical):
            raise ValueError("unsupported path key is not canonical")


class ScanWarningCode(StrEnum):
    ROOT_UNAVAILABLE = "root_unavailable"
    VOLUME_UNAVAILABLE = "volume_unavailable"
    ACCESS_DENIED = "access_denied"
    DISAPPEARED = "disappeared"
    ENUMERATION_ERROR = "enumeration_error"
    PATH_UNREPRESENTABLE = "path_unrepresentable"
    CASE_COLLISION = "case_collision"
    DUPLICATE_IDENTITY = "duplicate_identity"
    MULTI_LINK = "multi_link"
    PLACEHOLDER = "placeholder"
    REPARSE_POINT = "reparse_point"
    UNKNOWN_TYPE = "unknown_type"
    SCALAR_UNREPRESENTABLE = "scalar_unrepresentable"


@dataclass(frozen=True)
class ScanWarning:
    code: ScanWarningCode
    rel_path: str | None
    detail: str = ""

    def __post_init__(self) -> None:
        if type(self.code) is not ScanWarningCode:
            raise TypeError("scan warning code has the wrong type")
        if self.rel_path is not None:
            validate_relative_path(self.rel_path, allow_root=True)
        if type(self.detail) is not str:
            raise TypeError("scan warning detail must be a string")
        if bounded_utf8_text(
            self.detail,
            "scan warning detail",
            maximum_bytes=MAX_DIAGNOSTIC_UTF8_BYTES,
        ) is None:
            # Optional diagnostics cannot prevent recording valid observations.
            object.__setattr__(self, "detail", "")


class ScanScopeKind(StrEnum):
    FULL = "full"
    PATHS = "paths"
    SUBTREES = "subtrees"


@dataclass(frozen=True)
class ScanScope:
    kind: ScanScopeKind
    selected_paths: tuple[str, ...] = ()
    subtree_roots: tuple[str, ...] = ()

    @classmethod
    def full(cls) -> ScanScope:
        return cls(ScanScopeKind.FULL)

    @classmethod
    def selected(cls, paths: tuple[str, ...] | list[str]) -> ScanScope:
        _require_scope_population(paths, (), "selected scan")
        return cls(ScanScopeKind.PATHS, _canonical_scope_paths(paths))

    @classmethod
    def subtrees(
        cls,
        roots: tuple[str, ...] | list[str],
        *,
        selected_paths: tuple[str, ...] | list[str] = (),
    ) -> ScanScope:
        _require_scope_population(selected_paths, roots, "subtree scan")
        return cls.scoped(
            selected_paths=selected_paths,
            subtree_roots=roots,
        )

    @classmethod
    def scoped(
        cls,
        *,
        selected_paths: tuple[str, ...] | list[str] = (),
        subtree_roots: tuple[str, ...] | list[str] = (),
    ) -> ScanScope:
        _require_scope_population(
            selected_paths,
            subtree_roots,
            "scoped scan",
        )
        paths = _canonical_scope_paths(selected_paths)
        roots = _canonical_scope_paths(subtree_roots, allow_root=True)
        if "" in roots:
            return cls.full()
        retained_roots = _minimal_subtree_roots(roots)
        retained_root_keys = frozenset(
            normalize_relative_path(root) for root in retained_roots
        )
        retained_paths = tuple(
            path
            for path in paths
            if not _key_is_at_or_below(
                normalize_relative_path(path),
                retained_root_keys,
            )
        )
        if retained_roots:
            return cls(
                ScanScopeKind.SUBTREES,
                retained_paths,
                retained_roots,
            )
        if retained_paths:
            return cls(ScanScopeKind.PATHS, retained_paths)
        return cls.full()

    def __post_init__(self) -> None:
        if type(self.kind) is not ScanScopeKind:
            raise TypeError("scan scope kind has the wrong type")
        if type(self.selected_paths) is not tuple:
            raise TypeError("selected scan paths must be a tuple")
        if type(self.subtree_roots) is not tuple:
            raise TypeError("scan subtree roots must be a tuple")
        _require_scope_population(
            self.selected_paths,
            self.subtree_roots,
            "scan scope",
        )
        selected_paths = _canonical_scope_paths(self.selected_paths)
        subtree_roots = _minimal_subtree_roots(
            _canonical_scope_paths(self.subtree_roots, allow_root=True)
        )
        object.__setattr__(self, "selected_paths", selected_paths)
        object.__setattr__(self, "subtree_roots", subtree_roots)
        if self.kind is ScanScopeKind.FULL:
            if selected_paths or subtree_roots:
                raise ValueError("full scan cannot carry scoped paths")
            return
        if self.kind is ScanScopeKind.PATHS:
            if not selected_paths or subtree_roots:
                raise ValueError(
                    "selected scan requires paths and cannot carry subtree roots"
                )
            return
        if self.kind is ScanScopeKind.SUBTREES:
            if not subtree_roots or "" in subtree_roots:
                raise ValueError(
                    "subtree scan requires at least one non-root subtree"
                )
            root_keys = frozenset(
                normalize_relative_path(root) for root in subtree_roots
            )
            if any(
                _key_is_at_or_below(
                    normalize_relative_path(path),
                    root_keys,
                )
                for path in selected_paths
            ):
                raise ValueError(
                    "subtree scan cannot carry covered exact paths"
                )
            return
        raise ValueError(f"unsupported scan scope: {self.kind}")


def _canonical_scope_paths(
    paths: tuple[str, ...] | list[str],
    *,
    allow_root: bool = False,
) -> tuple[str, ...]:
    if type(paths) not in {tuple, list}:
        raise TypeError("scan scope paths must be a tuple or list")
    if len(paths) > SCAN_SCOPE_ENTRY_LIMIT:
        raise ValueError("scan scope exceeds the 120000-entry limit")
    by_key: dict[str, str] = {}
    for path in paths:
        canonical = validate_relative_path(path, allow_root=allow_root)
        key = normalize_relative_path(canonical, allow_root=allow_root)
        retained = by_key.get(key)
        if retained is None or canonical < retained:
            by_key[key] = canonical
    return tuple(by_key[key] for key in sorted(by_key))


def _require_scope_population(
    selected_paths: object,
    subtree_roots: object,
    context: str,
) -> None:
    if type(selected_paths) not in {tuple, list}:
        raise TypeError(f"{context} selected paths must be a tuple or list")
    if type(subtree_roots) not in {tuple, list}:
        raise TypeError(f"{context} subtree roots must be a tuple or list")
    if len(selected_paths) > SCAN_SCOPE_ENTRY_LIMIT - len(subtree_roots):
        raise ValueError("scan scope exceeds the 120000-entry limit")


def _minimal_subtree_roots(roots: tuple[str, ...]) -> tuple[str, ...]:
    keyed = tuple(
        (
            root,
            normalize_relative_path(root, allow_root=True),
        )
        for root in roots
    )
    retained: dict[str, str] = {}
    for root, root_key in sorted(
        keyed,
        key=lambda item: (
            len(PureWindowsPath(item[1]).parts),
            item[1],
            item[0],
        ),
    ):
        if _key_is_at_or_below(root_key, retained.keys()):
            continue
        retained[root_key] = root
    return tuple(
        retained[key]
        for key in sorted(retained)
    )


def _key_is_at_or_below(
    path_key: str,
    ancestor_keys: Collection[str],
) -> bool:
    current: str | None = path_key
    while current is not None:
        if current in ancestor_keys:
            return True
        current = relative_path_parent(current)
    return False


_TEMP_NAME = re.compile(
    r"^.+\.synctmp-(?P<run_id>[0-9a-f]{32})-(?P<op_id>[0-9a-f]{32})$"
)


def owned_temp_run_id(name: str) -> str | None:
    """Return the owning run id for an exact generated temp name."""

    match = _TEMP_NAME.fullmatch(name)
    return None if match is None else match.group("run_id")


@dataclass(frozen=True)
class IgnoreSet:
    """Built-in exact names and generated artifact grammar."""

    exact_names: frozenset[str] = field(
        default_factory=lambda: frozenset({"DESKTOP.INI", "THUMBS.DB"})
    )
    exclude_owned_temps: bool = True
    exclude_sync_trash: bool = True

    def excludes(self, rel_path: str, *, is_directory: bool) -> bool:
        canonical = validate_relative_path(rel_path)
        key = normalize_relative_path(canonical)
        if normalize_relative_path(PureWindowsPath(canonical).name) in self.exact_names:
            return True
        if self.exclude_sync_trash and (key == ".SYNCTRASH" or key.startswith(".SYNCTRASH\\")):
            return True
        name = PureWindowsPath(canonical).name
        return bool(
            self.exclude_owned_temps
            and not is_directory
            and owned_temp_run_id(name) is not None
        )


@dataclass(frozen=True)
class ScanResult:
    root: Root
    volume_id: VolumeId | None
    volume_evidence: VolumeEvidence | None
    profile: CapabilityProfile
    files: tuple[FileRecord, ...]
    directories: tuple[DirRecord, ...]
    unsupported: tuple[UnsupportedRecord, ...]
    warnings: tuple[ScanWarning, ...]
    scope: ScanScope
    complete: bool

    def __post_init__(self) -> None:
        validate_scan_result(self)

    @property
    def is_full_scan(self) -> bool:
        return self.scope.kind is ScanScopeKind.FULL


def validate_scan_warning(value: object) -> ScanWarning:
    """Re-admit one exact warning without retaining a repaired projection."""

    if type(value) is not ScanWarning:
        raise TypeError("scan warning requires ScanWarning")
    snapshot = ScanWarning(value.code, value.rel_path, value.detail)
    if snapshot != value:
        raise ValueError("scan warning is not canonical")
    return value


def validate_scan_scope(value: object) -> ScanScope:
    """Re-admit one exact canonical scan scope."""

    if type(value) is not ScanScope:
        raise TypeError("scan result scope requires ScanScope")
    snapshot = ScanScope(
        value.kind,
        value.selected_paths,
        value.subtree_roots,
    )
    if snapshot != value:
        raise ValueError("scan scope is not canonical")
    return value


def validate_scan_result(value: object) -> ScanResult:
    """Re-admit a complete exact scan graph before downstream allocation."""

    if type(value) is not ScanResult:
        raise TypeError("scanner must return ScanResult")
    if type(value.root) is not Root:
        raise TypeError("scan result root has the wrong type")
    Root(value.root.path, value.root.root_id)
    if value.volume_id is not None:
        if type(value.volume_id) is not VolumeId:
            raise TypeError("scan result volume has the wrong type")
        _require_volume_id_fields(value.volume_id)
    if value.volume_evidence is not None:
        if type(value.volume_evidence) is not VolumeEvidence:
            raise TypeError("scan result volume evidence has the wrong type")
        _require_volume_evidence_fields(value.volume_evidence)
    if type(value.profile) is not CapabilityProfile:
        raise TypeError("scan result capability profile has the wrong type")
    _require_capability_profile_fields(value.profile)
    for population, context in (
        (value.files, "scan files"),
        (value.directories, "scan directories"),
        (value.unsupported, "scan unsupported records"),
        (value.warnings, "scan warnings"),
    ):
        if type(population) is not tuple:
            raise TypeError(f"{context} must be a tuple")
    for item in value.files:
        if type(item) is not FileRecord:
            raise TypeError("scan files must contain FileRecord values")
        FileRecord(
            item.rel_path,
            item.rel_path_key,
            item.size,
            item.mtime_ns,
            item.file_identity,
            item.nlink,
            item.metadata,
        )
    for item in value.directories:
        if type(item) is not DirRecord:
            raise TypeError("scan directories must contain DirRecord values")
        DirRecord(
            item.rel_path,
            item.rel_path_key,
            item.mtime_ns,
            item.metadata,
            item.file_identity,
            item.nlink,
        )
    for item in value.unsupported:
        if type(item) is not UnsupportedRecord:
            raise TypeError(
                "scan unsupported records must contain UnsupportedRecord values"
            )
        UnsupportedRecord(
            item.rel_path,
            item.rel_path_key,
            item.reason,
            item.kind,
        )
    for item in value.warnings:
        validate_scan_warning(item)
    validate_scan_scope(value.scope)
    if type(value.complete) is not bool:
        raise TypeError("scan completeness must be a bool")
    return value


def file_identity_projection(value: FileIdentity | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not FileIdentity:
        raise TypeError("file identity projection requires FileIdentity")
    FileIdentity(value.volume_serial, value.file_index)
    return {
        "volume_serial": value.volume_serial,
        "file_index": file_index_128_to_text(value.file_index),
    }


def metadata_projection(value: MetadataSnapshot | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not MetadataSnapshot:
        raise TypeError("metadata projection requires MetadataSnapshot")
    return {"attributes": value.attributes, "created_ns": value.created_ns}


def file_stat_projection(value: FileStat | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not FileStat or type(value.kind) is not EntryKind:
        raise TypeError("stat projection requires FileStat with EntryKind")
    return {
        "kind": value.kind.value,
        "size": value.size,
        "mtime_ns": value.mtime_ns,
        "file_identity": file_identity_projection(value.file_identity),
        "nlink": value.nlink,
        "metadata": metadata_projection(value.metadata),
    }


def root_projection(value: Root) -> dict[str, object]:
    if type(value) is not Root:
        raise TypeError("root projection requires Root")
    Root(value.path, value.root_id)
    return {"path": value.path, "root_id": value.root_id}


def volume_id_projection(value: VolumeId | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not VolumeId:
        raise TypeError("volume projection requires VolumeId")
    _require_volume_id_fields(value)
    return {"serial": value.serial, "fs_type": value.fs_type}


def volume_evidence_projection(value: VolumeEvidence | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not VolumeEvidence:
        raise TypeError("volume evidence projection requires VolumeEvidence")
    _require_volume_evidence_fields(value)
    return {
        "label": value.label,
        "device_id": value.device_id,
        "clone_ambiguous": value.clone_ambiguous,
    }


def capability_profile_projection(value: CapabilityProfile) -> dict[str, object]:
    if type(value) is not CapabilityProfile:
        raise TypeError("capability projection requires CapabilityProfile")
    _require_capability_profile_fields(value)
    return {
        "fs_type": value.fs_type,
        "mtime_granularity_ns": value.mtime_granularity_ns,
        "stable_file_identity": value.stable_file_identity,
        "incurs_seek_penalty": value.incurs_seek_penalty,
        "max_path": value.max_path,
        "supports_ads": value.supports_ads,
        "supports_hardlinks": value.supports_hardlinks,
    }
