"""Deterministic walking and path-scoped filesystem scanner."""

from __future__ import annotations

import os
import stat as stat_module
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Iterator, Protocol

from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    FileStat,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    ScanScopeKind,
    ScanWarning,
    ScanWarningCode,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import join_under_root, normalize_relative_path, to_extended_length_path
from namisync.core.session import RunContext


FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
FILE_NAMED_STREAMS = 0x00040000
FILE_SUPPORTS_HARD_LINKS = 0x00400000


@dataclass(frozen=True)
class VolumeSnapshot:
    volume_id: VolumeId
    evidence: VolumeEvidence
    profile: CapabilityProfile


class DirectoryEntry(Protocol):
    name: str
    path: str

    def is_dir(self, *, follow_symlinks: bool = True) -> bool: ...

    def is_file(self, *, follow_symlinks: bool = True) -> bool: ...

    def stat(self, *, follow_symlinks: bool = True) -> os.stat_result: ...


class ScannerBackend(Protocol):
    def resolve_root(self, path: str) -> str: ...

    def volume_snapshot(self, root: str) -> VolumeSnapshot: ...

    def lstat(self, path: str) -> os.stat_result: ...

    def scandir(self, path: str) -> AbstractContextManager[Iterator[DirectoryEntry]]: ...


def _granularity_for(fs_type: str) -> int:
    normalized = fs_type.upper()
    if normalized in {"NTFS", "REFS"}:
        return 100
    if normalized == "EXFAT":
        return 10_000_000
    if normalized in {"FAT", "FAT32"}:
        return 2_000_000_000
    return 2_000_000_000


def _identity_supported(fs_type: str) -> bool:
    return fs_type.upper() in {"NTFS", "REFS"}


class NativeScannerBackend:
    """Native Windows metadata backend; it never opens ordinary file content."""

    def resolve_root(self, path: str) -> str:
        resolved = os.path.abspath(path)
        native = to_extended_length_path(resolved)
        if not os.path.isdir(native):
            raise FileNotFoundError(resolved)
        return resolved

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        if os.name != "nt":
            stat = os.stat(root, follow_symlinks=False)
            serial = f"{stat.st_dev:x}"
            fs_type = "UNKNOWN"
            return VolumeSnapshot(
                VolumeId(serial, fs_type),
                VolumeEvidence(device_id=os.path.splitdrive(root)[0] or root),
                CapabilityProfile(fs_type, _granularity_for(fs_type), False, None, 32767, False, False),
            )

        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        volume_path = ctypes.create_unicode_buffer(32768)
        if not kernel32.GetVolumePathNameW(root, volume_path, len(volume_path)):
            raise OSError(ctypes.get_last_error(), "GetVolumePathNameW failed", root)

        label = ctypes.create_unicode_buffer(261)
        filesystem = ctypes.create_unicode_buffer(261)
        serial = wintypes.DWORD()
        max_component = wintypes.DWORD()
        flags = wintypes.DWORD()
        if not kernel32.GetVolumeInformationW(
            volume_path.value,
            label,
            len(label),
            ctypes.byref(serial),
            ctypes.byref(max_component),
            ctypes.byref(flags),
            filesystem,
            len(filesystem),
        ):
            raise OSError(ctypes.get_last_error(), "GetVolumeInformationW failed", root)

        fs_type = filesystem.value.upper() or "UNKNOWN"
        volume_id = VolumeId(f"{serial.value:08X}", fs_type)
        return VolumeSnapshot(
            volume_id,
            VolumeEvidence(label.value or None, volume_path.value),
            CapabilityProfile(
                fs_type=fs_type,
                mtime_granularity_ns=_granularity_for(fs_type),
                stable_file_identity=_identity_supported(fs_type),
                incurs_seek_penalty=None,
                max_path=32767,
                supports_ads=bool(flags.value & FILE_NAMED_STREAMS),
                supports_hardlinks=bool(flags.value & FILE_SUPPORTS_HARD_LINKS),
            ),
        )

    def lstat(self, path: str) -> os.stat_result:
        return os.stat(to_extended_length_path(path), follow_symlinks=False)

    def scandir(self, path: str) -> AbstractContextManager[Iterator[DirectoryEntry]]:
        return os.scandir(to_extended_length_path(path))  # type: ignore[return-value]


def _attributes(stat: os.stat_result) -> int:
    return int(getattr(stat, "st_file_attributes", 0))


def _created_ns(stat: os.stat_result) -> int | None:
    value = getattr(stat, "st_birthtime_ns", None)
    if value is None and os.name == "nt":
        value = getattr(stat, "st_ctime_ns", None)
    return int(value) if value is not None and value >= 0 else None


def _file_identity(stat: os.stat_result, volume: VolumeSnapshot) -> FileIdentity | None:
    if not volume.profile.stable_file_identity:
        return None
    index = getattr(stat, "st_ino", None)
    if index is None or int(index) <= 0:
        return None
    return FileIdentity(volume.volume_id.serial, int(index))


def _to_stat(stat: os.stat_result, kind: EntryKind, volume: VolumeSnapshot) -> FileStat:
    return FileStat(
        kind=kind,
        size=int(stat.st_size) if kind is EntryKind.FILE else 0,
        mtime_ns=int(stat.st_mtime_ns),
        file_identity=_file_identity(stat, volume),
        nlink=max(1, int(getattr(stat, "st_nlink", 1))),
        metadata=MetadataSnapshot(_attributes(stat), _created_ns(stat)),
    )


def _is_placeholder(stat: os.stat_result) -> bool:
    attributes = _attributes(stat)
    return bool(
        attributes & FILE_ATTRIBUTE_REPARSE_POINT
        and attributes
        & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
    )


def _is_reparse(stat: os.stat_result) -> bool:
    return bool(_attributes(stat) & FILE_ATTRIBUTE_REPARSE_POINT or getattr(stat, "st_reparse_tag", 0))


class WalkingScanner:
    def __init__(self, backend: ScannerBackend | None = None) -> None:
        self._backend = backend or NativeScannerBackend()

    def scan(
        self,
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        scope: ScanScope | None = None,
    ) -> ScanResult:
        requested_scope = scope or ScanScope.full()
        try:
            resolved = self._backend.resolve_root(root.path)
        except (OSError, PermissionError) as error:
            return self._offline_result(root, ignores, requested_scope, error, ScanWarningCode.ROOT_UNAVAILABLE)

        resolved_root = Root(resolved, root.root_id)
        try:
            volume = self._backend.volume_snapshot(resolved)
        except (OSError, PermissionError) as error:
            return self._offline_result(
                resolved_root,
                ignores,
                requested_scope,
                error,
                ScanWarningCode.VOLUME_UNAVAILABLE,
            )

        files: list[FileRecord] = []
        directories: list[DirRecord] = []
        unsupported: list[UnsupportedRecord] = []
        warnings: list[ScanWarning] = []
        complete = requested_scope.kind is ScanScopeKind.FULL

        if requested_scope.kind is ScanScopeKind.PATHS:
            self._scan_selected(
                resolved,
                volume,
                ignores,
                requested_scope,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
            )
            complete = False
        else:
            complete = self._scan_full(
                resolved,
                volume,
                ignores,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
            )

        collision_complete = self._append_collision_warnings(files, directories, unsupported, warnings)
        self._append_identity_warnings(files, directories, warnings)
        complete = complete and collision_complete
        return ScanResult(
            root=resolved_root,
            volume_id=volume.volume_id,
            volume_evidence=volume.evidence,
            profile=volume.profile,
            files=tuple(sorted(files, key=lambda item: (item.rel_path_key, item.rel_path))),
            directories=tuple(sorted(directories, key=lambda item: (item.rel_path_key, item.rel_path))),
            unsupported=tuple(sorted(unsupported, key=lambda item: (item.rel_path_key, item.rel_path))),
            warnings=tuple(sorted(warnings, key=self._warning_sort_key)),
            ignore_snapshot=ignores,
            scope=requested_scope,
            complete=complete,
        )

    def _scan_full(
        self,
        root: str,
        volume: VolumeSnapshot,
        ignores: IgnoreSet,
        ctx: RunContext,
        files: list[FileRecord],
        directories: list[DirRecord],
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
    ) -> bool:
        try:
            root_stat = self._backend.lstat(root)
        except (OSError, PermissionError) as error:
            warnings.append(ScanWarning(ScanWarningCode.ROOT_UNAVAILABLE, None, str(error)))
            return False

        root_snapshot = _to_stat(root_stat, EntryKind.DIRECTORY, volume)
        directories.append(
            DirRecord("", "", root_snapshot.mtime_ns, root_snapshot.metadata, root_snapshot.file_identity, root_snapshot.nlink)
        )
        visited = {root_snapshot.file_identity} if root_snapshot.file_identity is not None else set()
        pending: list[tuple[str, str]] = [(root, "")]
        complete = True

        while pending:
            absolute_directory, relative_directory = pending.pop()
            ctx.checkpoint()
            ordered: list[DirectoryEntry] = []
            enumeration_error: OSError | None = None
            try:
                with self._backend.scandir(absolute_directory) as entries:
                    try:
                        for entry in entries:
                            ctx.checkpoint()
                            ordered.append(entry)
                    except (OSError, PermissionError) as error:
                        enumeration_error = error
            except (OSError, PermissionError) as error:
                enumeration_error = error
            if enumeration_error is not None:
                warnings.append(ScanWarning(ScanWarningCode.ENUMERATION_ERROR, relative_directory, str(enumeration_error)))
                complete = False
            ordered.sort(key=lambda item: (normalize_relative_path(item.name), item.name))

            child_directories: list[tuple[str, str]] = []
            for entry in ordered:
                ctx.checkpoint()
                rel_path = entry.name if not relative_directory else f"{relative_directory}\\{entry.name}"
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                except (OSError, PermissionError) as error:
                    warnings.append(ScanWarning(self._error_code(error), rel_path, str(error)))
                    unsupported.append(
                        UnsupportedRecord(rel_path, normalize_relative_path(rel_path), self._unsupported_error(error))
                    )
                    complete = False
                    continue
                if ignores.excludes(rel_path, is_directory=is_directory):
                    continue

                try:
                    stat = entry.stat(follow_symlinks=False)
                except (OSError, PermissionError) as error:
                    warnings.append(ScanWarning(self._error_code(error), rel_path, str(error)))
                    unsupported.append(
                        UnsupportedRecord(
                            rel_path,
                            normalize_relative_path(rel_path),
                            self._unsupported_error(error),
                            EntryKind.DIRECTORY if is_directory else None,
                        )
                    )
                    complete = False
                    continue

                if _is_placeholder(stat):
                    kind = EntryKind.DIRECTORY if is_directory else EntryKind.FILE
                    unsupported.append(
                        UnsupportedRecord(rel_path, normalize_relative_path(rel_path), UnsupportedReason.PLACEHOLDER, kind)
                    )
                    warnings.append(ScanWarning(ScanWarningCode.PLACEHOLDER, rel_path))
                    if is_directory:
                        complete = False
                    continue
                if _is_reparse(stat):
                    kind = EntryKind.DIRECTORY if is_directory else EntryKind.FILE
                    unsupported.append(
                        UnsupportedRecord(rel_path, normalize_relative_path(rel_path), UnsupportedReason.REPARSE_POINT, kind)
                    )
                    warnings.append(ScanWarning(ScanWarningCode.REPARSE_POINT, rel_path))
                    if is_directory:
                        complete = False
                    continue

                if is_directory:
                    snapshot = _to_stat(stat, EntryKind.DIRECTORY, volume)
                    directories.append(
                        DirRecord(
                            rel_path,
                            normalize_relative_path(rel_path),
                            snapshot.mtime_ns,
                            snapshot.metadata,
                            snapshot.file_identity,
                            snapshot.nlink,
                        )
                    )
                    if snapshot.file_identity is not None and snapshot.file_identity in visited:
                        warnings.append(
                            ScanWarning(ScanWarningCode.DUPLICATE_IDENTITY, rel_path, "directory identity already visited")
                        )
                        complete = False
                    else:
                        if snapshot.file_identity is not None:
                            visited.add(snapshot.file_identity)
                        child_directories.append((entry.path, rel_path))
                    continue

                try:
                    is_file = entry.is_file(follow_symlinks=False)
                except (OSError, PermissionError) as error:
                    warnings.append(ScanWarning(self._error_code(error), rel_path, str(error)))
                    is_file = False
                if is_file:
                    snapshot = _to_stat(stat, EntryKind.FILE, volume)
                    files.append(
                        FileRecord(
                            rel_path,
                            normalize_relative_path(rel_path),
                            snapshot.size,
                            snapshot.mtime_ns,
                            snapshot.file_identity,
                            snapshot.nlink,
                            snapshot.metadata,
                        )
                    )
                else:
                    unsupported.append(
                        UnsupportedRecord(rel_path, normalize_relative_path(rel_path), UnsupportedReason.UNKNOWN_TYPE)
                    )
                    warnings.append(ScanWarning(ScanWarningCode.UNKNOWN_TYPE, rel_path))
                    complete = False

            pending.extend(reversed(child_directories))
        return complete

    def _scan_selected(
        self,
        root: str,
        volume: VolumeSnapshot,
        ignores: IgnoreSet,
        scope: ScanScope,
        ctx: RunContext,
        files: list[FileRecord],
        directories: list[DirRecord],
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
    ) -> None:
        for rel_path in scope.selected_paths:
            ctx.checkpoint()
            absolute = join_under_root(root, rel_path)
            try:
                stat = self._backend.lstat(absolute)
            except (OSError, PermissionError) as error:
                warnings.append(ScanWarning(self._error_code(error), rel_path, str(error)))
                unsupported.append(
                    UnsupportedRecord(rel_path, normalize_relative_path(rel_path), self._unsupported_error(error))
                )
                continue
            is_directory = stat_module.S_ISDIR(stat.st_mode) and not _is_reparse(stat)
            if ignores.excludes(rel_path, is_directory=is_directory):
                continue
            if _is_placeholder(stat):
                unsupported.append(
                    UnsupportedRecord(rel_path, normalize_relative_path(rel_path), UnsupportedReason.PLACEHOLDER)
                )
                warnings.append(ScanWarning(ScanWarningCode.PLACEHOLDER, rel_path))
            elif _is_reparse(stat):
                unsupported.append(
                    UnsupportedRecord(rel_path, normalize_relative_path(rel_path), UnsupportedReason.REPARSE_POINT)
                )
                warnings.append(ScanWarning(ScanWarningCode.REPARSE_POINT, rel_path))
            elif is_directory:
                snapshot = _to_stat(stat, EntryKind.DIRECTORY, volume)
                directories.append(
                    DirRecord(rel_path, normalize_relative_path(rel_path), snapshot.mtime_ns, snapshot.metadata, snapshot.file_identity, snapshot.nlink)
                )
            else:
                snapshot = _to_stat(stat, EntryKind.FILE, volume)
                files.append(
                    FileRecord(rel_path, normalize_relative_path(rel_path), snapshot.size, snapshot.mtime_ns, snapshot.file_identity, snapshot.nlink, snapshot.metadata)
                )

    @staticmethod
    def _error_code(error: OSError) -> ScanWarningCode:
        if isinstance(error, PermissionError):
            return ScanWarningCode.ACCESS_DENIED
        if isinstance(error, FileNotFoundError):
            return ScanWarningCode.DISAPPEARED
        return ScanWarningCode.ENUMERATION_ERROR

    @staticmethod
    def _unsupported_error(error: OSError) -> UnsupportedReason:
        if isinstance(error, PermissionError):
            return UnsupportedReason.ACCESS_DENIED
        if isinstance(error, FileNotFoundError):
            return UnsupportedReason.DISAPPEARED
        return UnsupportedReason.UNKNOWN_TYPE

    @staticmethod
    def _append_collision_warnings(
        files: list[FileRecord],
        directories: list[DirRecord],
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
    ) -> bool:
        grouped: dict[str, list[str]] = {}
        for record in (*files, *directories, *unsupported):
            if record.rel_path == "":
                continue
            grouped.setdefault(record.rel_path_key, []).append(record.rel_path)
        complete = True
        for paths in grouped.values():
            distinct = sorted(set(paths))
            if len(distinct) > 1:
                warnings.append(
                    ScanWarning(ScanWarningCode.CASE_COLLISION, distinct[0], " | ".join(distinct))
                )
                complete = False
        return complete

    @staticmethod
    def _append_identity_warnings(
        files: list[FileRecord], directories: list[DirRecord], warnings: list[ScanWarning]
    ) -> None:
        grouped: dict[FileIdentity, list[str]] = {}
        for record in (*files, *directories):
            if record.file_identity is not None:
                grouped.setdefault(record.file_identity, []).append(record.rel_path)
            if isinstance(record, FileRecord) and record.nlink > 1:
                warnings.append(ScanWarning(ScanWarningCode.MULTI_LINK, record.rel_path, str(record.nlink)))
        for paths in grouped.values():
            if len(paths) > 1:
                ordered = sorted(paths)
                warnings.append(
                    ScanWarning(ScanWarningCode.DUPLICATE_IDENTITY, ordered[0], " | ".join(ordered))
                )

    @staticmethod
    def _warning_sort_key(warning: ScanWarning) -> tuple[str, str, str]:
        key = normalize_relative_path(warning.rel_path, allow_root=True) if warning.rel_path is not None else ""
        return warning.code.value, key, warning.detail

    @staticmethod
    def _offline_result(
        root: Root,
        ignores: IgnoreSet,
        scope: ScanScope,
        error: OSError,
        code: ScanWarningCode,
    ) -> ScanResult:
        return ScanResult(
            root=root,
            volume_id=None,
            volume_evidence=None,
            profile=CapabilityProfile("UNKNOWN", 2_000_000_000, False, None, 32767, False, False),
            files=(),
            directories=(),
            unsupported=(),
            warnings=(ScanWarning(code, None, str(error)),),
            ignore_snapshot=ignores,
            scope=scope,
            complete=False,
        )


def scan(
    root: Root,
    ignores: IgnoreSet,
    ctx: RunContext,
    scope: ScanScope | None = None,
) -> ScanResult:
    return WalkingScanner().scan(root, ignores, ctx, scope)
