"""Immutable filesystem observation contracts shared by domain modules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PureWindowsPath

from .pathing import normalize_relative_path, validate_relative_path


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
        if self.mtime_granularity_ns <= 0:
            raise ValueError("mtime granularity must be positive")
        if self.max_path <= 0:
            raise ValueError("maximum path must be positive")


@dataclass(frozen=True, order=True)
class FileIdentity:
    volume_serial: str
    file_index: int

    def __post_init__(self) -> None:
        if not self.volume_serial or self.file_index < 0:
            raise ValueError("invalid file identity")


@dataclass(frozen=True)
class MetadataSnapshot:
    attributes: int
    created_ns: int | None

    def __post_init__(self) -> None:
        if self.attributes < 0:
            raise ValueError("attributes cannot be negative")
        if self.created_ns is not None and self.created_ns < 0:
            raise ValueError("creation time cannot be negative")


@dataclass(frozen=True)
class FileStat:
    kind: EntryKind
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None
    nlink: int
    metadata: MetadataSnapshot

    def __post_init__(self) -> None:
        if self.size < 0 or self.mtime_ns < 0:
            raise ValueError("file stat size and mtime cannot be negative")
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
    CASE_COLLISION = "case_collision"
    DUPLICATE_IDENTITY = "duplicate_identity"
    MULTI_LINK = "multi_link"
    PLACEHOLDER = "placeholder"
    REPARSE_POINT = "reparse_point"
    UNKNOWN_TYPE = "unknown_type"


@dataclass(frozen=True)
class ScanWarning:
    code: ScanWarningCode
    rel_path: str | None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.rel_path is not None:
            validate_relative_path(self.rel_path, allow_root=True)


class ScanScopeKind(StrEnum):
    FULL = "full"
    PATHS = "paths"


@dataclass(frozen=True)
class ScanScope:
    kind: ScanScopeKind
    selected_paths: tuple[str, ...] = ()

    @classmethod
    def full(cls) -> ScanScope:
        return cls(ScanScopeKind.FULL)

    @classmethod
    def selected(cls, paths: tuple[str, ...] | list[str]) -> ScanScope:
        canonical = tuple(sorted({validate_relative_path(path) for path in paths}, key=normalize_relative_path))
        return cls(ScanScopeKind.PATHS, canonical)

    def __post_init__(self) -> None:
        if self.kind is ScanScopeKind.FULL and self.selected_paths:
            raise ValueError("full scan cannot carry selected paths")
        if self.kind is ScanScopeKind.PATHS and not self.selected_paths:
            raise ValueError("selected scan requires at least one path")


_TEMP_NAME = re.compile(r"^.+\.synctmp-[0-9a-f]{32}-[0-9a-f]{32}$")


@dataclass(frozen=True)
class IgnoreSet:
    """Exact application-owned paths plus exact generated artifact grammar."""

    exact_path_keys: frozenset[str] = field(default_factory=frozenset)
    exact_names: frozenset[str] = field(
        default_factory=lambda: frozenset({"DESKTOP.INI", "THUMBS.DB"})
    )
    exclude_owned_temps: bool = True
    exclude_sync_trash: bool = True

    @classmethod
    def for_owned_paths(cls, paths: tuple[str, ...] | list[str]) -> IgnoreSet:
        keys: set[str] = set()
        for path in paths:
            canonical = validate_relative_path(path)
            keys.add(normalize_relative_path(canonical))
            keys.add(normalize_relative_path(canonical + "-wal"))
            keys.add(normalize_relative_path(canonical + "-shm"))
        return cls(frozenset(keys))

    def excludes(self, rel_path: str, *, is_directory: bool) -> bool:
        canonical = validate_relative_path(rel_path)
        key = normalize_relative_path(canonical)
        if key in self.exact_path_keys:
            return True
        if normalize_relative_path(PureWindowsPath(canonical).name) in self.exact_names:
            return True
        if self.exclude_sync_trash and (key == ".SYNCTRASH" or key.startswith(".SYNCTRASH\\")):
            return True
        name = PureWindowsPath(canonical).name
        return bool(self.exclude_owned_temps and not is_directory and _TEMP_NAME.fullmatch(name))


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
    ignore_snapshot: IgnoreSet
    scope: ScanScope
    complete: bool

    @property
    def is_full_scan(self) -> bool:
        return self.scope.kind is ScanScopeKind.FULL
