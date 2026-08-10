"""Deterministic walking and path-scoped filesystem scanner."""

from __future__ import annotations

import os
import stat as stat_module
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
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
from namisync.core.pathing import (
    PathValidationError,
    from_extended_length_path,
    join_under_root,
    lexical_absolute_path,
    lexical_path_chain,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    trusted_volume_anchor,
    validate_relative_path,
)
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_existing_relative_chain,
)
from namisync.core.session import RunContext


FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
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
    def resolve_root(
        self, path: str, *, trusted_anchor: str | None = None
    ) -> str: ...

    def volume_snapshot(self, root: str) -> VolumeSnapshot: ...

    def lstat(self, path: str) -> os.stat_result: ...

    def stat(self, path: str) -> os.stat_result: ...

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

    def trusted_anchor(self, path: str) -> str:
        return trusted_volume_anchor(path)

    def resolve_root(
        self, path: str, *, trusted_anchor: str | None = None
    ) -> str:
        logical = lexical_absolute_path(path)
        if trusted_anchor is None:
            anchor = self.trusted_anchor(logical)
        else:
            anchor = lexical_absolute_path(trusted_anchor)
            try:
                current_anchor = self.trusted_anchor(logical)
            except (OSError, ValueError) as error:
                raise OSError(logical_error_text(error)) from error
            if os.path.normcase(os.path.normpath(current_anchor)) != os.path.normcase(
                os.path.normpath(anchor)
            ):
                raise OSError(
                    "location volume anchor changed after binding review"
                )
        for component in lexical_path_chain(
            logical,
            trusted_anchor=anchor,
        ):
            native = to_extended_length_path(component)
            try:
                observed = os.stat(native, follow_symlinks=False)
            except OSError as error:
                raise OSError(logical_error_text(error)) from error
            if (
                not _is_directory_stat(observed)
                or _is_placeholder(observed)
                or _is_reparse(observed)
            ):
                raise NotADirectoryError(
                    "location root chain contains a nonordinary directory: "
                    f"{component}"
                )
        return logical

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        if os.name != "nt":
            stat = os.stat(to_extended_length_path(root), follow_symlinks=False)
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
        native_root = to_extended_length_path(root)
        if not kernel32.GetVolumePathNameW(
            native_root, volume_path, len(volume_path)
        ):
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
            VolumeEvidence(
                label.value or None,
                from_extended_length_path(volume_path.value),
            ),
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

    def stat(self, path: str) -> os.stat_result:
        return os.stat(to_extended_length_path(path), follow_symlinks=True)

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


def _is_directory_stat(stat: os.stat_result) -> bool:
    return bool(
        stat_module.S_ISDIR(stat.st_mode)
        or _attributes(stat) & FILE_ATTRIBUTE_DIRECTORY
    )


def _same_logical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(
        os.path.normpath(right)
    )


def _escaped_path(value: str) -> str:
    """Return terminal- and UTF-8-safe diagnostic text for a raw path."""

    return ascii(value)[1:-1]


def _entry_sort_key(entry: DirectoryEntry) -> tuple[int, str, str]:
    try:
        return 0, normalize_relative_path(entry.name), entry.name
    except PathValidationError:
        return 1, _escaped_path(entry.name), ""


class WalkingScanner:
    def __init__(self, backend: ScannerBackend | None = None) -> None:
        self._backend = backend or NativeScannerBackend()

    def scan(
        self,
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        scope: ScanScope | None = None,
        *,
        trusted_anchor: str | None = None,
    ) -> ScanResult:
        requested_scope = scope or ScanScope.full()
        try:
            if trusted_anchor is None:
                resolved = self._backend.resolve_root(root.path)
            else:
                resolved = self._backend.resolve_root(
                    root.path,
                    trusted_anchor=trusted_anchor,
                )
        except (OSError, PermissionError) as error:
            return self._offline_result(
                root, requested_scope, error, ScanWarningCode.ROOT_UNAVAILABLE
            )

        resolved_root = Root(resolved, root.root_id)
        try:
            reviewed_anchor = self._reviewed_anchor(resolved, trusted_anchor)
        except (OSError, PathValidationError) as error:
            return self._offline_result(
                resolved_root,
                requested_scope,
                error,
                ScanWarningCode.ROOT_UNAVAILABLE,
            )
        root_error = self._root_error(resolved, reviewed_anchor)
        if root_error is not None:
            return self._offline_result(
                resolved_root,
                requested_scope,
                root_error,
                ScanWarningCode.ROOT_UNAVAILABLE,
            )
        try:
            volume = self._backend.volume_snapshot(resolved)
        except (OSError, PermissionError) as error:
            return self._offline_result(
                resolved_root,
                requested_scope,
                error,
                ScanWarningCode.VOLUME_UNAVAILABLE,
            )
        root_error = self._root_error(resolved, reviewed_anchor)
        if root_error is not None:
            return self._offline_result(
                resolved_root,
                requested_scope,
                root_error,
                ScanWarningCode.ROOT_UNAVAILABLE,
            )
        binding_error = self._binding_error(
            resolved,
            reviewed_anchor,
            volume.volume_id,
        )
        if binding_error is not None:
            return self._offline_result(
                resolved_root,
                requested_scope,
                binding_error,
                ScanWarningCode.VOLUME_UNAVAILABLE,
            )
        device_anchor = volume.evidence.device_id
        # The reviewed mount may itself be a folder-volume reparse point. A
        # caller-provided anchor alone is insufficient authority to follow it.
        trusted_mount_root = (
            resolved
            if (
                os.name == "nt"
                and device_anchor is not None
                and _same_logical_path(resolved, reviewed_anchor)
                and _same_logical_path(resolved, device_anchor)
            )
            else None
        )
        authority = (
            None
            if requested_scope.kind is ScanScopeKind.FULL
            else RootAuthority(
                resolved,
                reviewed_anchor,
                volume.volume_id,
            )
        )

        files: list[FileRecord] = []
        directories: list[DirRecord] = []
        unsupported: list[UnsupportedRecord] = []
        warnings: list[ScanWarning] = []
        if requested_scope.kind is ScanScopeKind.FULL:
            complete = self._scan_full(
                volume,
                ignores,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
                starting_points=((resolved, ""),),
                trusted_mount_root=trusted_mount_root,
            )
        elif requested_scope.kind is ScanScopeKind.PATHS:
            assert authority is not None
            complete = self._scan_selected(
                authority,
                volume,
                ignores,
                requested_scope,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
            )
        elif requested_scope.kind is ScanScopeKind.SUBTREES:
            assert authority is not None
            selected_complete = self._scan_selected(
                authority,
                volume,
                ignores,
                requested_scope,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
            )
            scoped_complete = True
            starting_points: list[tuple[str, str]] = []
            for relative in requested_scope.subtree_roots:
                ctx.checkpoint()
                touch_leaf, subject_complete = self._admit_scoped_ancestors(
                    authority,
                    relative,
                    unsupported,
                    warnings,
                )
                scoped_complete = scoped_complete and subject_complete
                if touch_leaf:
                    starting_points.append(
                        (join_under_root(resolved, relative), relative)
                    )
            recursive_complete = self._scan_full(
                volume,
                ignores,
                ctx,
                files,
                directories,
                unsupported,
                warnings,
                starting_points=tuple(starting_points),
            )
            complete = (
                selected_complete
                and scoped_complete
                and recursive_complete
            )
        else:
            raise ValueError(f"unsupported scan scope: {requested_scope.kind}")

        collision_complete = self._append_collision_warnings(files, directories, unsupported, warnings)
        self._append_identity_warnings(files, directories, warnings)
        complete = complete and collision_complete
        root_error = self._root_error(resolved, reviewed_anchor)
        if root_error is not None:
            return self._offline_result(
                resolved_root,
                requested_scope,
                root_error,
                ScanWarningCode.ROOT_UNAVAILABLE,
            )
        binding_error = self._binding_error(
            resolved,
            reviewed_anchor,
            volume.volume_id,
        )
        if binding_error is not None:
            return self._offline_result(
                resolved_root,
                requested_scope,
                binding_error,
                ScanWarningCode.VOLUME_UNAVAILABLE,
            )
        return ScanResult(
            root=resolved_root,
            volume_id=volume.volume_id,
            volume_evidence=volume.evidence,
            profile=volume.profile,
            files=tuple(sorted(files, key=lambda item: (item.rel_path_key, item.rel_path))),
            directories=tuple(sorted(directories, key=lambda item: (item.rel_path_key, item.rel_path))),
            unsupported=tuple(sorted(unsupported, key=lambda item: (item.rel_path_key, item.rel_path))),
            warnings=tuple(sorted(warnings, key=self._warning_sort_key)),
            scope=requested_scope,
            complete=complete,
        )

    def _scan_full(
        self,
        volume: VolumeSnapshot,
        ignores: IgnoreSet,
        ctx: RunContext,
        files: list[FileRecord],
        directories: list[DirRecord],
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
        *,
        starting_points: tuple[tuple[str, str], ...],
        trusted_mount_root: str | None = None,
    ) -> bool:
        visited: set[FileIdentity] = set()
        pending: list[tuple[str, str]] = []
        complete = True
        for absolute_start, relative_start in starting_points:
            ctx.checkpoint()
            try:
                root_stat = self._backend.lstat(absolute_start)
                if (
                    not relative_start
                    and trusted_mount_root is not None
                    and _same_logical_path(
                        absolute_start,
                        trusted_mount_root,
                    )
                    and _is_directory_stat(root_stat)
                    and _is_reparse(root_stat)
                    and not _is_placeholder(root_stat)
                ):
                    # Record the mounted root, not the hosting reparse entry.
                    root_stat = self._backend.stat(absolute_start)
            except FileNotFoundError as error:
                if relative_start:
                    warnings.append(
                        ScanWarning(
                            ScanWarningCode.DISAPPEARED,
                            relative_start,
                            logical_error_text(error),
                        )
                    )
                else:
                    warnings.append(
                        ScanWarning(
                            ScanWarningCode.ROOT_UNAVAILABLE,
                            None,
                            logical_error_text(error),
                        )
                    )
                    complete = False
                continue
            except (OSError, PermissionError) as error:
                warnings.append(
                    ScanWarning(
                        ScanWarningCode.ROOT_UNAVAILABLE,
                        relative_start or None,
                        logical_error_text(error),
                    )
                )
                complete = False
                continue

            if not relative_start:
                if (
                    not _is_directory_stat(root_stat)
                    or _is_placeholder(root_stat)
                    or _is_reparse(root_stat)
                ):
                    warnings.append(
                        ScanWarning(
                            ScanWarningCode.ROOT_UNAVAILABLE,
                            None,
                            "location root is not an ordinary directory",
                        )
                    )
                    complete = False
                    continue
                root_snapshot = _to_stat(
                    root_stat, EntryKind.DIRECTORY, volume
                )
                directories.append(
                    DirRecord(
                        "",
                        "",
                        root_snapshot.mtime_ns,
                        root_snapshot.metadata,
                        root_snapshot.file_identity,
                        root_snapshot.nlink,
                    )
                )
                if root_snapshot.file_identity is not None:
                    visited.add(root_snapshot.file_identity)
                pending.append((absolute_start, ""))
                continue

            is_directory = _is_directory_stat(root_stat)
            if _is_placeholder(root_stat):
                kind = (
                    EntryKind.DIRECTORY if is_directory else EntryKind.FILE
                )
                unsupported.append(
                    UnsupportedRecord(
                        relative_start,
                        normalize_relative_path(relative_start),
                        UnsupportedReason.PLACEHOLDER,
                        kind,
                    )
                )
                warnings.append(
                    ScanWarning(ScanWarningCode.PLACEHOLDER, relative_start)
                )
                if is_directory:
                    complete = False
                continue
            if _is_reparse(root_stat):
                kind = (
                    EntryKind.DIRECTORY if is_directory else EntryKind.FILE
                )
                unsupported.append(
                    UnsupportedRecord(
                        relative_start,
                        normalize_relative_path(relative_start),
                        UnsupportedReason.REPARSE_POINT,
                        kind,
                    )
                )
                warnings.append(
                    ScanWarning(ScanWarningCode.REPARSE_POINT, relative_start)
                )
                if is_directory:
                    complete = False
                continue
            if is_directory:
                root_snapshot = _to_stat(
                    root_stat, EntryKind.DIRECTORY, volume
                )
                directories.append(
                    DirRecord(
                        relative_start,
                        normalize_relative_path(
                            relative_start, allow_root=True
                        ),
                        root_snapshot.mtime_ns,
                        root_snapshot.metadata,
                        root_snapshot.file_identity,
                        root_snapshot.nlink,
                    )
                )
                if (
                    root_snapshot.file_identity is not None
                    and root_snapshot.file_identity in visited
                ):
                    warnings.append(
                        ScanWarning(
                            ScanWarningCode.DUPLICATE_IDENTITY,
                            relative_start,
                            "directory identity already visited",
                        )
                    )
                    complete = False
                    continue
                if root_snapshot.file_identity is not None:
                    visited.add(root_snapshot.file_identity)
                pending.append((absolute_start, relative_start))
                continue
            if stat_module.S_ISREG(root_stat.st_mode):
                root_snapshot = _to_stat(root_stat, EntryKind.FILE, volume)
                files.append(
                    FileRecord(
                        relative_start,
                        normalize_relative_path(relative_start),
                        root_snapshot.size,
                        root_snapshot.mtime_ns,
                        root_snapshot.file_identity,
                        root_snapshot.nlink,
                        root_snapshot.metadata,
                    )
                )
                continue
            unsupported.append(
                UnsupportedRecord(
                    relative_start,
                    normalize_relative_path(relative_start),
                    UnsupportedReason.UNKNOWN_TYPE,
                )
            )
            warnings.append(
                ScanWarning(ScanWarningCode.UNKNOWN_TYPE, relative_start)
            )
            complete = False

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
                warnings.append(
                    ScanWarning(
                        ScanWarningCode.ENUMERATION_ERROR,
                        relative_directory,
                        logical_error_text(enumeration_error),
                    )
                )
                complete = False
            ordered.sort(key=_entry_sort_key)

            child_directories: list[tuple[str, str]] = []
            for entry in ordered:
                ctx.checkpoint()
                candidate = entry.name if not relative_directory else f"{relative_directory}\\{entry.name}"
                try:
                    rel_path = validate_relative_path(candidate)
                except PathValidationError as error:
                    warnings.append(
                        ScanWarning(
                            ScanWarningCode.PATH_UNREPRESENTABLE,
                            relative_directory or None,
                            f"{_escaped_path(candidate)}: {error}",
                        )
                    )
                    complete = False
                    continue
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                except (OSError, PermissionError) as error:
                    warnings.append(
                        ScanWarning(
                            self._error_code(error),
                            rel_path,
                            logical_error_text(error),
                        )
                    )
                    unsupported.append(
                        UnsupportedRecord(rel_path, normalize_relative_path(rel_path), self._unsupported_error(error))
                    )
                    complete = False
                    continue
                provisionally_ignored = ignores.excludes(
                    rel_path, is_directory=is_directory
                )
                needs_directory_confirmation = (
                    provisionally_ignored
                    and not is_directory
                    and not ignores.excludes(
                        rel_path, is_directory=True
                    )
                )
                if (
                    provisionally_ignored
                    and not needs_directory_confirmation
                ):
                    continue

                try:
                    stat = entry.stat(follow_symlinks=False)
                    if (
                        volume.profile.stable_file_identity
                        and int(getattr(stat, "st_ino", 0) or 0) <= 0
                    ):
                        stat = self._backend.lstat(entry.path)
                except (OSError, PermissionError) as error:
                    warnings.append(
                        ScanWarning(
                            self._error_code(error),
                            rel_path,
                            logical_error_text(error),
                        )
                    )
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

                is_directory = is_directory or _is_directory_stat(stat)
                if (
                    provisionally_ignored
                    and ignores.excludes(
                        rel_path, is_directory=is_directory
                    )
                ):
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
                    warnings.append(
                        ScanWarning(
                            self._error_code(error),
                            rel_path,
                            logical_error_text(error),
                        )
                    )
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
        authority: RootAuthority,
        volume: VolumeSnapshot,
        ignores: IgnoreSet,
        scope: ScanScope,
        ctx: RunContext,
        files: list[FileRecord],
        directories: list[DirRecord],
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
    ) -> bool:
        complete = True
        for rel_path in scope.selected_paths:
            ctx.checkpoint()
            touch_leaf, subject_complete = self._admit_scoped_ancestors(
                authority,
                rel_path,
                unsupported,
                warnings,
            )
            complete = complete and subject_complete
            if not touch_leaf:
                continue
            ctx.checkpoint()
            absolute = join_under_root(authority.logical_root, rel_path)
            try:
                stat = self._backend.lstat(absolute)
            except FileNotFoundError as error:
                warnings.append(
                    ScanWarning(
                        ScanWarningCode.DISAPPEARED,
                        rel_path,
                        logical_error_text(error),
                    )
                )
                continue
            except (OSError, PermissionError) as error:
                warnings.append(
                    ScanWarning(
                        self._error_code(error),
                        rel_path,
                        logical_error_text(error),
                    )
                )
                unsupported.append(
                    UnsupportedRecord(rel_path, normalize_relative_path(rel_path), self._unsupported_error(error))
                )
                complete = False
                continue
            is_directory = stat_module.S_ISDIR(stat.st_mode) and not _is_reparse(stat)
            if ignores.excludes(rel_path, is_directory=is_directory):
                complete = False
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
            elif stat_module.S_ISREG(stat.st_mode):
                snapshot = _to_stat(stat, EntryKind.FILE, volume)
                files.append(
                    FileRecord(rel_path, normalize_relative_path(rel_path), snapshot.size, snapshot.mtime_ns, snapshot.file_identity, snapshot.nlink, snapshot.metadata)
                )
            else:
                unsupported.append(
                    UnsupportedRecord(
                        rel_path,
                        normalize_relative_path(rel_path),
                        UnsupportedReason.UNKNOWN_TYPE,
                    )
                )
                warnings.append(ScanWarning(ScanWarningCode.UNKNOWN_TYPE, rel_path))
        return complete

    def _admit_scoped_ancestors(
        self,
        authority: RootAuthority,
        rel_path: str,
        unsupported: list[UnsupportedRecord],
        warnings: list[ScanWarning],
    ) -> tuple[bool, bool]:
        """Admit ancestors while leaving final-subject policy to the scanner."""

        try:
            ancestors_present = admit_existing_relative_chain(
                authority,
                rel_path,
                lstat=self._backend.lstat,
                include_leaf=False,
            )
        except RootAuthorityError as error:
            if error.issue is RootAuthorityIssue.PLACEHOLDER_COMPONENT:
                code = ScanWarningCode.PLACEHOLDER
                reason = UnsupportedReason.PLACEHOLDER
            elif error.issue is RootAuthorityIssue.REPARSE_COMPONENT:
                code = ScanWarningCode.REPARSE_POINT
                reason = UnsupportedReason.REPARSE_POINT
            elif error.issue is RootAuthorityIssue.NON_DIRECTORY_COMPONENT:
                code = ScanWarningCode.UNKNOWN_TYPE
                reason = UnsupportedReason.UNKNOWN_TYPE
            elif error.issue is RootAuthorityIssue.COMPONENT_UNAVAILABLE:
                cause = error.__cause__
                observed_error = (
                    cause if isinstance(cause, OSError) else error
                )
                code = self._error_code(observed_error)
                reason = self._unsupported_error(observed_error)
            else:
                raise RuntimeError(
                    "relative admission returned a root-level authority issue"
                ) from error
            unsupported.append(
                UnsupportedRecord(
                    rel_path,
                    normalize_relative_path(rel_path),
                    reason,
                )
            )
            warnings.append(
                ScanWarning(code, rel_path, logical_error_text(error))
            )
            return False, False
        if not ancestors_present:
            warnings.append(
                ScanWarning(
                    ScanWarningCode.DISAPPEARED,
                    rel_path,
                    "an intermediate path component is absent",
                )
            )
            return False, True
        return True, True

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

    def _root_error(
        self, path: str, trusted_anchor: str | None
    ) -> OSError | None:
        try:
            if trusted_anchor is not None:
                anchor = trusted_anchor
            else:
                anchor_provider = getattr(
                    self._backend,
                    "trusted_anchor",
                    None,
                )
                anchor = (
                    anchor_provider(path)
                    if callable(anchor_provider)
                    else Path(path).anchor
                )
            root_chain = lexical_path_chain(
                path,
                trusted_anchor=anchor,
            )
        except (OSError, PathValidationError) as error:
            return error
        for component in root_chain:
            try:
                root_stat = self._backend.lstat(component)
            except (OSError, PermissionError) as error:
                return error
            if (
                not _is_directory_stat(root_stat)
                or _is_placeholder(root_stat)
                or _is_reparse(root_stat)
            ):
                return NotADirectoryError(
                    "location root chain contains a nonordinary directory: "
                    f"{component}"
                )
        return None

    def _reviewed_anchor(
        self,
        path: str,
        trusted_anchor: str | None,
    ) -> str:
        if trusted_anchor is not None:
            return lexical_absolute_path(trusted_anchor)
        anchor_provider = getattr(self._backend, "trusted_anchor", None)
        if callable(anchor_provider):
            return lexical_absolute_path(anchor_provider(path))
        return lexical_absolute_path(Path(path).anchor)

    def _binding_error(
        self,
        path: str,
        reviewed_anchor: str,
        expected_volume: VolumeId,
    ) -> OSError | None:
        anchor_provider = getattr(self._backend, "trusted_anchor", None)
        if callable(anchor_provider):
            try:
                current_anchor = lexical_absolute_path(anchor_provider(path))
            except (OSError, PathValidationError) as error:
                return error
            if os.path.normcase(os.path.normpath(current_anchor)) != os.path.normcase(
                os.path.normpath(reviewed_anchor)
            ):
                return OSError(
                    "location volume anchor changed after binding review"
                )
        try:
            current_volume = self._backend.volume_snapshot(path)
        except (OSError, PermissionError) as error:
            return error
        if current_volume.volume_id != expected_volume:
            return OSError(
                "location volume identity changed during inventory scan"
            )
        return None

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
            warnings=(ScanWarning(code, None, logical_error_text(error)),),
            scope=scope,
            complete=False,
        )


def scan(
    root: Root,
    ignores: IgnoreSet,
    ctx: RunContext,
    scope: ScanScope | None = None,
    *,
    trusted_anchor: str | None = None,
) -> ScanResult:
    return WalkingScanner().scan(
        root,
        ignores,
        ctx,
        scope,
        trusted_anchor=trusted_anchor,
    )
