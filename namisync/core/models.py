"""Immutable filesystem observation contracts shared by domain modules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PureWindowsPath

from .pathing import (
    is_relative_path_descendant,
    normalize_relative_path,
    validate_relative_path,
)


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
    PATH_UNREPRESENTABLE = "path_unrepresentable"
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
        retained_paths = tuple(
            path
            for path in paths
            if not any(
                normalize_relative_path(path)
                == normalize_relative_path(root)
                or is_relative_path_descendant(path, root)
                for root in retained_roots
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
            if any(
                normalize_relative_path(path)
                == normalize_relative_path(root)
                or is_relative_path_descendant(path, root)
                for path in selected_paths
                for root in subtree_roots
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
    retained: list[str] = []
    for root in sorted(
        roots,
        key=lambda path: (
            len(PureWindowsPath(path).parts),
            normalize_relative_path(path, allow_root=True),
            path,
        ),
    ):
        if any(
            parent == ""
            or normalize_relative_path(root, allow_root=True)
            == normalize_relative_path(parent, allow_root=True)
            or is_relative_path_descendant(root, parent)
            for parent in retained
        ):
            continue
        retained.append(root)
    return tuple(
        sorted(
            retained,
            key=lambda path: normalize_relative_path(
                path, allow_root=True
            ),
        )
    )


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
