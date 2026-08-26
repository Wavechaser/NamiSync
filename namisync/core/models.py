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
    MAX_FILE_INDEX_128,
    file_index_128_to_text,
    require_safe_int,
    require_signed_64,
)


# Windows attributes that execution deliberately propagates from source to target.
MANAGED_FILE_ATTRIBUTE_MASK = 0x00000001 | 0x00000002 | 0x00000004 | 0x00002000


class EntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True, order=True)
class VolumeId:
    serial: str
    fs_type: str

    def __post_init__(self) -> None:
        if not self.serial or not self.fs_type:
            raise ValueError("volume identity requires serial and filesystem type")


@dataclass(frozen=True)
class VolumeEvidence:
    label: str | None = None
    device_id: str | None = None
    clone_ambiguous: bool = False


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
        require_signed_64(
            self.mtime_granularity_ns,
            "mtime granularity",
        )
        if self.mtime_granularity_ns == 0:
            raise ValueError("mtime granularity must be positive")
        require_safe_int(self.max_path, "maximum path")
        if self.max_path == 0:
            raise ValueError("maximum path must be positive")


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
        require_signed_64(self.size, "file size")
        require_signed_64(self.mtime_ns, "file modification time")
        require_safe_int(self.nlink, "file link count")
        if self.nlink < 1:
            raise ValueError("link count must be positive")


@dataclass(frozen=True)
class Root:
    path: str
    root_id: str

    def __post_init__(self) -> None:
        if not self.path or "\x00" in self.path:
            raise ValueError("root path is invalid")
        if not self.root_id:
            raise ValueError("root id is required")


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
        if self.rel_path is not None:
            validate_relative_path(self.rel_path, allow_root=True)
        if not isinstance(self.detail, str):
            raise TypeError("scan warning detail must be a string")
        try:
            self.detail.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
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
        return cls(ScanScopeKind.PATHS, _canonical_scope_paths(paths))

    @classmethod
    def subtrees(
        cls,
        roots: tuple[str, ...] | list[str],
        *,
        selected_paths: tuple[str, ...] | list[str] = (),
    ) -> ScanScope:
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
    by_key: dict[str, str] = {}
    for path in paths:
        canonical = validate_relative_path(path, allow_root=allow_root)
        key = normalize_relative_path(canonical, allow_root=allow_root)
        retained = by_key.get(key)
        if retained is None or canonical < retained:
            by_key[key] = canonical
    return tuple(by_key[key] for key in sorted(by_key))


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

    @property
    def is_full_scan(self) -> bool:
        return self.scope.kind is ScanScopeKind.FULL


def file_identity_projection(value: FileIdentity | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not FileIdentity:
        raise TypeError("file identity projection requires FileIdentity")
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
    return {"path": value.path, "root_id": value.root_id}


def volume_id_projection(value: VolumeId | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not VolumeId:
        raise TypeError("volume projection requires VolumeId")
    return {"serial": value.serial, "fs_type": value.fs_type}


def volume_evidence_projection(value: VolumeEvidence | None) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not VolumeEvidence:
        raise TypeError("volume evidence projection requires VolumeEvidence")
    return {
        "label": value.label,
        "device_id": value.device_id,
        "clone_ambiguous": value.clone_ambiguous,
    }


def capability_profile_projection(value: CapabilityProfile) -> dict[str, object]:
    if type(value) is not CapabilityProfile:
        raise TypeError("capability projection requires CapabilityProfile")
    return {
        "fs_type": value.fs_type,
        "mtime_granularity_ns": value.mtime_granularity_ns,
        "stable_file_identity": value.stable_file_identity,
        "incurs_seek_penalty": value.incurs_seek_penalty,
        "max_path": value.max_path,
        "supports_ads": value.supports_ads,
        "supports_hardlinks": value.supports_hardlinks,
    }
