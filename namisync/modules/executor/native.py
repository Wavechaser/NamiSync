"""Native filesystem primitives used by the executor component."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import ctypes
from ctypes import wintypes
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat as stat_module
from typing import BinaryIO, cast

from namisync.core.execution import RunId
from namisync.core.file_identity import (
    file_identity_from_stat,
    file_identity_from_windows_handle,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MANAGED_FILE_ATTRIBUTE_MASK,
    MetadataSnapshot,
    VolumeEvidence,
    VolumeId,
    owned_temp_run_id,
)
from namisync.core.pathing import (
    PathValidationError,
    from_extended_length_path,
    is_path_below,
    lexical_absolute_path,
    lexical_path_chain,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import OpId
from namisync.core.root_authority import (
    NativeVolumeInfo,
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root,
    admit_root_chain,
)


_READONLY = 0x00000001
_REPARSE_POINT = 0x00000400
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_WRITE_ATTRIBUTES = 0x0100
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_BASIC_INFO_CLASS = 0
_FILE_STANDARD_INFO_CLASS = 1
_FILE_ALLOCATION_INFO_CLASS = 5
_WINDOWS_EPOCH_TICKS = 116_444_736_000_000_000
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_ALLOCATION_UNSUPPORTED_ERRORS = frozenset({1, 50, 120})


class _FileBasicInfo(ctypes.Structure):
    _fields_ = [
        ("CreationTime", ctypes.c_longlong),
        ("LastAccessTime", ctypes.c_longlong),
        ("LastWriteTime", ctypes.c_longlong),
        ("ChangeTime", ctypes.c_longlong),
        ("FileAttributes", wintypes.DWORD),
    ]


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", ctypes.c_ubyte),
        ("Directory", ctypes.c_ubyte),
    ]


class _FileAllocationInfo(ctypes.Structure):
    _fields_ = [("AllocationSize", ctypes.c_longlong)]


class _WindowsBindings:
    """Process-lifetime Win32 bindings used by the native executor."""

    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

        self.create_file = kernel32.CreateFileW
        self.create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.create_file.restype = wintypes.HANDLE

        self.close_handle = kernel32.CloseHandle
        self.close_handle.argtypes = [wintypes.HANDLE]
        self.close_handle.restype = wintypes.BOOL

        self.flush_file_buffers = kernel32.FlushFileBuffers
        self.flush_file_buffers.argtypes = [wintypes.HANDLE]
        self.flush_file_buffers.restype = wintypes.BOOL

        self.get_file_information_ex = kernel32.GetFileInformationByHandleEx
        self.get_file_information_ex.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.get_file_information_ex.restype = wintypes.BOOL

        self.set_file_information = kernel32.SetFileInformationByHandle
        self.set_file_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.set_file_information.restype = wintypes.BOOL

        self.get_attributes = kernel32.GetFileAttributesW
        self.get_attributes.argtypes = [wintypes.LPCWSTR]
        self.get_attributes.restype = wintypes.DWORD

        self.set_attributes = kernel32.SetFileAttributesW
        self.set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        self.set_attributes.restype = wintypes.BOOL

        self.set_file_time = kernel32.SetFileTime
        self.set_file_time.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        self.set_file_time.restype = wintypes.BOOL

        self.get_volume_path = kernel32.GetVolumePathNameW
        self.get_volume_path.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.get_volume_path.restype = wintypes.BOOL

        self.get_volume_information = kernel32.GetVolumeInformationW
        self.get_volume_information.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.get_volume_information.restype = wintypes.BOOL

        self.get_security = advapi32.GetFileSecurityW
        self.get_security.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.get_security.restype = wintypes.BOOL

        self.set_security = advapi32.SetFileSecurityW
        self.set_security.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
        ]
        self.set_security.restype = wintypes.BOOL


_WINDOWS = _WindowsBindings() if os.name == "nt" else None


class UnsafeExecutionPath(OSError):
    """A planned path cannot be resolved safely beneath its reviewed root."""


class _SecurityCopyFailure(OSError):
    """A preserved security descriptor could not be applied to the temp."""


class _UpdateBackupDrift(OSError):
    """An open live-target handle no longer matches its reviewed version."""


class _UpdateBackupBeforeCopyDrift(_UpdateBackupDrift):
    """The opened live target differed before backup copying started."""


class _UpdateBackupDuringCopyDrift(_UpdateBackupDrift):
    """The opened live target changed while its backup was copied."""


class _RootChainNotDirectory(OSError):
    """A root component failed the executor's second directory observation."""


class _ExecutorRootStat:
    """No-follow root facts limited to the executor's established policy."""

    def __init__(self, observed: os.stat_result) -> None:
        # The legacy chain guard treated its second ``Path.is_dir`` result as
        # authoritative if the entry changed after the preceding lstat.
        self.st_mode = stat_module.S_IFDIR
        self.st_file_attributes = int(
            getattr(observed, "st_file_attributes", 0)
        )
        # The legacy executor rejected symlink mode and the reparse attribute,
        # but did not independently interpret a tag-only synthetic observation.
        self.st_reparse_tag = 0


class NativeFileSystem:
    """Native local-filesystem primitives retained by the executor machine."""

    def revalidate_root(
        self,
        root: Path,
        *,
        trusted_anchor: Path | None = None,
        expected_volume: VolumeId | None = None,
    ) -> None:
        logical = _lexical_logical_path(root)
        try:
            authority = RootAuthority(
                str(logical),
                (
                    None
                    if trusted_anchor is None
                    else str(_lexical_logical_path(trusted_anchor))
                ),
                expected_volume,
            )
            if expected_volume is None:
                admit_root_chain(
                    authority,
                    lstat=self._observe_root_component,
                    anchor_probe=self._observe_root_anchor,
                )
            else:
                admit_root(
                    authority,
                    lstat=self._observe_root_component,
                    anchor_probe=self._observe_root_anchor,
                    volume_probe=self._observe_root_volume,
                )
        except PathValidationError as error:
            raise UnsafeExecutionPath(
                "reviewed root volume anchor changed before filesystem access"
            ) from error
        except RootAuthorityError as error:
            self._raise_root_authority_error(error)

    def _observe_root_anchor(self, path: str) -> str:
        logical = _lexical_logical_path(path)
        if os.name != "nt":
            anchor = logical.anchor
            if not anchor:
                raise PathValidationError("absolute path lacks a volume anchor")
            return str(_lexical_logical_path(anchor))

        assert _WINDOWS is not None
        volume_path = ctypes.create_unicode_buffer(32768)
        if not _WINDOWS.get_volume_path(
            _win32_path(logical), volume_path, len(volume_path)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        anchor = _lexical_logical_path(
            from_extended_length_path(volume_path.value)
        )
        if not is_path_below(str(logical), str(anchor)):
            raise PathValidationError(
                "native volume root is outside the configured lexical path"
            )
        return str(anchor)

    def _observe_root_component(self, path: str) -> os.stat_result:
        current = Path(path)
        observed = self._reject_reparse(current)
        if not Path(_win32_path(current)).is_dir():
            raise _RootChainNotDirectory(str(current))
        return cast(os.stat_result, _ExecutorRootStat(observed))

    def _raise_root_authority_error(self, error: RootAuthorityError) -> None:
        cause = error.__cause__
        if error.issue is RootAuthorityIssue.ANCHOR_CHANGED:
            raise UnsafeExecutionPath(
                "reviewed root volume anchor changed before filesystem access"
            ) from error
        if error.issue is RootAuthorityIssue.VOLUME_CHANGED:
            raise UnsafeExecutionPath(
                "reviewed root volume changed before filesystem access"
            ) from error
        if error.issue in {
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
            RootAuthorityIssue.REPARSE_COMPONENT,
        }:
            raise UnsafeExecutionPath(
                f"reparse points are not executable: {error.logical_path}"
            ) from error
        if error.issue is RootAuthorityIssue.NON_DIRECTORY_COMPONENT or isinstance(
            cause, _RootChainNotDirectory
        ):
            raise UnsafeExecutionPath(
                "reviewed root chain contains a nondirectory: "
                f"{error.logical_path}"
            ) from error
        if error.issue is RootAuthorityIssue.ANCHOR_UNAVAILABLE:
            raise UnsafeExecutionPath(str(error)) from error
        if cause is not None:
            raise cause
        raise UnsafeExecutionPath(str(error)) from error

    def resolve(self, root: Path, relative_path: str, *, must_exist: bool) -> Path:
        canonical = validate_relative_path(relative_path)
        root_path = _lexical_logical_path(root)
        self.revalidate_root(root_path)
        resolved_root = _resolved_logical_path(root_path, strict=True)
        candidate = root_path.joinpath(*PureWindowsPath(canonical).parts)
        self._validate_existing_chain(root_path, candidate)
        if must_exist and not os.path.lexists(_win32_path(candidate)):
            raise FileNotFoundError(candidate)
        resolved = _resolved_logical_path(candidate, strict=must_exist)
        try:
            common = os.path.commonpath((str(resolved_root), str(resolved)))
            if os.path.normcase(common) != os.path.normcase(
                str(resolved_root)
            ):
                raise UnsafeExecutionPath(f"path escapes reviewed root: {relative_path}")
        except ValueError as error:
            raise UnsafeExecutionPath(
                f"path is not on the reviewed root volume: {relative_path}"
            ) from error
        return candidate

    def stat(self, root: Path, relative_path: str) -> FileStat | None:
        path = self.resolve(root, relative_path, must_exist=False)
        return self.stat_path(path)

    def stat_path(self, path: Path) -> FileStat | None:
        return self._stat_path(path)

    def _stat_path(self, path: Path) -> FileStat | None:
        native = Path(_win32_path(path))
        if not os.path.lexists(native):
            return None
        self._reject_reparse(path)
        info = native.stat(follow_symlinks=False)
        if stat_module.S_ISREG(info.st_mode):
            kind = EntryKind.FILE
            size = info.st_size
        elif stat_module.S_ISDIR(info.st_mode):
            kind = EntryKind.DIRECTORY
            size = 0
        else:
            raise UnsafeExecutionPath(f"unsupported filesystem entry: {path}")
        volume = self._volume_id(path)
        return FileStat(
            kind=kind,
            size=size,
            mtime_ns=info.st_mtime_ns,
            file_identity=file_identity_from_stat(
                volume.serial,
                volume.fs_type,
                getattr(info, "st_ino", None),
            ),
            nlink=info.st_nlink,
            metadata=MetadataSnapshot(
                attributes=int(getattr(info, "st_file_attributes", 0)),
                created_ns=self._created_ns(info),
            ),
        )

    def owned_temp(self, target: Path, run_id: RunId, op_id: OpId) -> Path:
        run_text = str(run_id)
        op_text = str(op_id)
        if len(run_text) != 32 or len(op_text) != 32:
            raise ValueError("owned temp ids must be fixed-format")
        if any(character not in "0123456789abcdef" for character in run_text + op_text):
            raise ValueError("owned temp ids must be lowercase hexadecimal")
        return target.with_name(f"{target.name}.synctmp-{run_text}-{op_text}")

    def remove_owned_temp(self, path: Path) -> None:
        self._reject_reparse_chain(path.parent)
        try:
            self._reject_reparse(path)
            Path(_win32_path(path)).unlink()
        except FileNotFoundError:
            return

    def remove_orphaned_temps(
        self,
        target_root: Path,
        parent_paths: frozenset[str],
        current_run_id: RunId,
    ) -> None:
        """Remove exact prior-run temps from preflight's touched parents."""

        current = str(current_run_id)
        target_root = _lexical_logical_path(target_root)
        self._reject_reparse_chain(target_root)
        target_volume = self._volume_serial(target_root)
        for relative in sorted(
            parent_paths,
            key=lambda value: (
                normalize_relative_path(value, allow_root=True),
                value,
            ),
        ):
            key = normalize_relative_path(relative, allow_root=True)
            if key == ".SYNCTRASH" or key.startswith(".SYNCTRASH\\"):
                continue
            if relative:
                parent = self.resolve(target_root, relative, must_exist=False)
                if not os.path.lexists(_win32_path(parent)):
                    continue
                self._reject_reparse(parent)
                if not Path(_win32_path(parent)).is_dir():
                    continue
            else:
                parent = target_root
                self._reject_reparse(parent)
            if self._volume_serial(parent) != target_volume:
                continue
            with os.scandir(_win32_path(parent)) as entries:
                for entry in entries:
                    owner = owned_temp_run_id(entry.name)
                    if (
                        owner is not None
                        and owner != current
                        and entry.is_file(follow_symlinks=False)
                    ):
                        self.remove_owned_temp(
                            Path(from_extended_length_path(entry.path))
                        )

    def open_source(self, path: Path) -> BinaryIO:
        flags = os.O_RDONLY
        if os.name == "nt":
            flags |= os.O_BINARY | os.O_SEQUENTIAL
        descriptor = os.open(_win32_path(path), flags)
        try:
            return cast(BinaryIO, os.fdopen(descriptor, "rb", buffering=0))
        except BaseException:
            os.close(descriptor)
            raise

    def create_temp(
        self, path: Path, *, allocation_size: int | None
    ) -> BinaryIO:
        if allocation_size is not None and allocation_size < 0:
            raise ValueError("allocation size cannot be negative")
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        if os.name == "nt":
            flags |= os.O_BINARY
        descriptor = os.open(_win32_path(path), flags, 0o666)
        try:
            stream = cast(BinaryIO, os.fdopen(descriptor, "w+b", buffering=0))
        except BaseException:
            os.close(descriptor)
            raise
        if os.name != "nt" or not allocation_size:
            return stream

        import msvcrt

        assert _WINDOWS is not None
        handle = msvcrt.get_osfhandle(stream.fileno())
        allocation = _FileAllocationInfo(allocation_size)
        if not _WINDOWS.set_file_information(
            handle,
            _FILE_ALLOCATION_INFO_CLASS,
            ctypes.byref(allocation),
            ctypes.sizeof(allocation),
        ):
            error = ctypes.get_last_error()
            if error not in _ALLOCATION_UNSUPPORTED_ERRORS:
                stream.close()
                raise ctypes.WinError(error)
        return stream

    def flush_file(self, stream: BinaryIO) -> None:
        stream.flush()
        os.fsync(stream.fileno())

    def flush_path(self, path: Path) -> None:
        with Path(_win32_path(path)).open("r+b", buffering=0) as stream:
            os.fsync(stream.fileno())

    def apply_metadata(
        self,
        path: Path,
        stat: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> None:
        # Reparse points are rejected at resolution, so the Windows build does
        # not need (and does not support) ``follow_symlinks=False`` here.
        # Last-access time is deliberately outside executor metadata policy.
        if os.name == "nt":
            self._set_windows_file_times(
                path,
                created_ns=(
                    stat.metadata.created_ns
                    if preserve_created
                    else None
                ),
                modified_ns=stat.mtime_ns,
            )
        else:
            observed_access_ns = Path(_win32_path(path)).stat(
                follow_symlinks=False
            ).st_atime_ns
            os.utime(
                _win32_path(path),
                ns=(observed_access_ns, stat.mtime_ns),
            )
        desired = stat.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
        if not apply_readonly:
            desired &= ~_READONLY
        self._set_standard_attributes(path, desired)

    def copy_security(self, source: Path, target: Path) -> None:
        if os.name != "nt":
            shutil.copystat(
                _win32_path(source),
                _win32_path(target),
                follow_symlinks=False,
            )
            return
        assert _WINDOWS is not None
        security_information = 0x1 | 0x2 | 0x4
        needed = wintypes.DWORD()
        _WINDOWS.get_security(
            _win32_path(source),
            security_information,
            None,
            0,
            ctypes.byref(needed),
        )
        if needed.value == 0:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not _WINDOWS.get_security(
            _win32_path(source),
            security_information,
            buffer,
            needed,
            ctypes.byref(needed),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not _WINDOWS.set_security(
            _win32_path(target), security_information, buffer
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def finalize_temp(
        self,
        path: Path,
        intended: FileStat,
        *,
        preserve_created: bool,
        acl_source: Path | None,
    ) -> FileStat:
        """Apply final temp metadata and issue its sole durability flush."""

        if os.name != "nt":
            with Path(_win32_path(path)).open("r+b", buffering=0) as held:
                if acl_source is not None:
                    try:
                        self.copy_security(acl_source, path)
                    except Exception as error:
                        raise _SecurityCopyFailure(
                            logical_error_text(error)
                        ) from error
                self.apply_metadata(
                    path,
                    intended,
                    preserve_created=preserve_created,
                    apply_readonly=False,
                )
                os.fsync(held.fileno())
            result = self.stat_path(path)
            if result is None:
                raise FileNotFoundError(path)
            return result

        handle = self._open_metadata_handle(path)
        try:
            if acl_source is not None:
                try:
                    self.copy_security(acl_source, path)
                except Exception as error:
                    raise _SecurityCopyFailure(
                        logical_error_text(error)
                    ) from error
            current = self._basic_info(handle)
            desired_attributes = (
                current.FileAttributes & ~MANAGED_FILE_ATTRIBUTE_MASK
            ) | (
                intended.metadata.attributes
                & (MANAGED_FILE_ATTRIBUTE_MASK & ~_READONLY)
            )
            creation = current.CreationTime
            if preserve_created and intended.metadata.created_ns is not None:
                creation = _windows_ticks(intended.metadata.created_ns)
            modified = _windows_ticks(intended.mtime_ns)
            self._set_basic_info(
                handle,
                _FileBasicInfo(
                    creation,
                    0,
                    modified,
                    0,
                    desired_attributes,
                ),
            )
            normalized = self._basic_info(handle)
            self._flush_handle(handle)
            result = self._stat_handle(handle, normalized)
        except BaseException:
            try:
                self._close_handle(handle)
            except Exception:
                pass
            raise
        else:
            self._close_handle(handle)
            return result

    def ensure_published_metadata(
        self,
        path: Path,
        finalized_temp: FileStat,
        intended: FileStat,
        *,
        preserve_created: bool,
        apply_readonly: bool,
    ) -> FileStat:
        """Observe once and repair only publication-damaged managed fields."""

        observed = self._stat_path(path)
        if observed is None:
            raise FileNotFoundError(path)
        repair_mtime = observed.mtime_ns != finalized_temp.mtime_ns
        repair_created = (
            preserve_created
            and intended.metadata.created_ns is not None
            and observed.metadata.created_ns != finalized_temp.metadata.created_ns
        )
        desired_managed = (
            intended.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
        )
        if not apply_readonly:
            desired_managed &= ~_READONLY
        repair_attributes = (
            observed.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
        ) != desired_managed
        if not (repair_mtime or repair_created or repair_attributes):
            return observed

        if os.name != "nt":
            self.apply_metadata(
                path,
                replace(
                    finalized_temp,
                    metadata=replace(
                        finalized_temp.metadata,
                        attributes=(
                            finalized_temp.metadata.attributes
                            & ~MANAGED_FILE_ATTRIBUTE_MASK
                        )
                        | desired_managed,
                    ),
                ),
                preserve_created=repair_created,
                apply_readonly=apply_readonly,
            )
            self.flush_path(path)
            repaired = self.stat_path(path)
            if repaired is None:
                raise FileNotFoundError(path)
            return repaired

        handle = self._open_metadata_handle(path)
        try:
            current = self._basic_info(handle)
            creation = (
                _windows_ticks(finalized_temp.metadata.created_ns)
                if repair_created
                and finalized_temp.metadata.created_ns is not None
                else current.CreationTime
            )
            last_write = (
                _windows_ticks(finalized_temp.mtime_ns)
                if repair_mtime
                else current.LastWriteTime
            )
            attributes = (
                (current.FileAttributes & ~MANAGED_FILE_ATTRIBUTE_MASK)
                | desired_managed
                if repair_attributes
                else current.FileAttributes
            )
            self._set_basic_info(
                handle,
                _FileBasicInfo(
                    creation,
                    0,
                    last_write,
                    0,
                    attributes,
                ),
            )
            final_basic = self._basic_info(handle)
            self._flush_handle(handle)
            result = self._stat_handle(handle, final_basic)
        except BaseException:
            try:
                self._close_handle(handle)
            except Exception:
                pass
            raise
        else:
            self._close_handle(handle)
            return result

    def publish_new(self, temp: Path, target: Path) -> None:
        os.rename(_win32_path(temp), _win32_path(target))

    def replace(self, temp: Path, target: Path) -> None:
        os.replace(_win32_path(temp), _win32_path(target))

    def hardlink(self, source: Path, target: Path) -> None:
        os.link(_win32_path(source), _win32_path(target))

    def copy_backup(
        self,
        source: Path,
        temp: Path,
        target: Path,
        source_expected: FileStat,
        checkpoint: Callable[[], None],
        validate_destination: Callable[[], None],
    ) -> None:
        published = False
        try:
            with self.open_source(source) as reader:
                source_before = self._stat_open_file(reader)
                if not _matches_backup_source(source_before, source_expected):
                    raise _UpdateBackupBeforeCopyDrift()
                validate_destination()
                copied_size = 0
                with self.create_temp(temp, allocation_size=None) as writer:
                    while True:
                        checkpoint()
                        chunk = reader.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        _write_all(writer, chunk, "backup copy")
                        copied_size += len(chunk)
                validate_destination()
                source_after = self._stat_open_file(reader)
                if not _matches_copied_backup_source(
                    source_before,
                    source_after,
                    copied_size,
                ):
                    raise _UpdateBackupDuringCopyDrift()
            validate_destination()
            self.finalize_temp(
                temp,
                source_before,
                preserve_created=True,
                acl_source=None,
            )
            validate_destination()
            self.publish_new(temp, target)
            published = True
        except BaseException as error:
            if not published:
                try:
                    validate_destination()
                    self.remove_owned_temp(temp)
                except Exception as cleanup_error:
                    error.add_note(
                        "backup temp cleanup failed: "
                        f"{type(cleanup_error).__name__}: "
                        f"{logical_error_text(cleanup_error)}"
                    )
            raise

    def _stat_open_file(self, stream: BinaryIO) -> FileStat:
        if os.name == "nt":
            import msvcrt

            return self._stat_handle(msvcrt.get_osfhandle(stream.fileno()))
        info = os.fstat(stream.fileno())
        if not stat_module.S_ISREG(info.st_mode):
            raise UnsafeExecutionPath("backup source is not a regular file")
        return FileStat(
            kind=EntryKind.FILE,
            size=info.st_size,
            mtime_ns=info.st_mtime_ns,
            file_identity=FileIdentity(f"{info.st_dev:x}", int(info.st_ino)),
            nlink=info.st_nlink,
            metadata=MetadataSnapshot(
                attributes=int(getattr(info, "st_file_attributes", 0)),
                created_ns=self._created_ns(info),
            ),
        )

    def clear_readonly(self, path: Path) -> None:
        current = self._get_attributes(path)
        self._set_attributes(path, current & ~_READONLY)

    def rename_new(self, source: Path, target: Path) -> None:
        os.rename(_win32_path(source), _win32_path(target))

    def mkdir_new(self, path: Path) -> None:
        os.mkdir(_win32_path(path))

    def remove_file(self, path: Path) -> None:
        os.unlink(_win32_path(path))

    def remove_directory(self, path: Path) -> None:
        os.rmdir(_win32_path(path))

    def trash_destination(
        self, target_root: Path, run_id: RunId, relative_path: str
    ) -> Path:
        canonical = validate_relative_path(relative_path)
        root = _lexical_logical_path(target_root)
        self._reject_reparse_chain(root)
        current = root
        for part in (".synctrash", str(run_id), *PureWindowsPath(canonical).parts[:-1]):
            current = current / part
            try:
                os.mkdir(_win32_path(current))
            except FileExistsError:
                if not Path(_win32_path(current)).is_dir():
                    raise UnsafeExecutionPath(f"trash parent is not a directory: {current}")
            self._reject_reparse(current)
            if (
                Path(_win32_path(current)).stat().st_dev
                != Path(_win32_path(root)).stat().st_dev
            ):
                raise UnsafeExecutionPath("trash path leaves the target volume")
        destination = current / PureWindowsPath(canonical).name
        self._validate_existing_chain(root, destination)
        return destination

    def revalidate_trash_destination(
        self,
        target_root: Path,
        run_id: RunId,
        relative_path: str,
        destination: Path,
    ) -> None:
        canonical = validate_relative_path(relative_path)
        root = _lexical_logical_path(target_root)
        self._reject_reparse_chain(root)
        expected = root.joinpath(
            ".synctrash",
            str(run_id),
            *PureWindowsPath(canonical).parts,
        )
        if destination != expected:
            raise UnsafeExecutionPath(
                "trash destination does not match the owned run path"
            )
        root_volume = self._volume_serial(root)
        current = root
        for part in PureWindowsPath(
            str(expected.parent.relative_to(root))
        ).parts:
            current = current / part
            if not os.path.lexists(_win32_path(current)):
                raise UnsafeExecutionPath(
                    f"trash parent disappeared before mutation: {current}"
                )
            self._reject_reparse(current)
            if not Path(_win32_path(current)).is_dir():
                raise UnsafeExecutionPath(
                    f"trash parent is not a directory: {current}"
                )
            if self._volume_serial(current) != root_volume:
                raise UnsafeExecutionPath("trash path leaves the target volume")
        self._validate_existing_chain(root, destination)

    def flush_directory(self, path: Path) -> bool:
        if os.name != "nt":
            try:
                descriptor = os.open(_win32_path(path), os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                return True
            except OSError:
                return False
        assert _WINDOWS is not None
        handle = _WINDOWS.create_file(
            _win32_path(path),
            _GENERIC_WRITE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            return False
        try:
            return bool(_WINDOWS.flush_file_buffers(handle))
        finally:
            _WINDOWS.close_handle(handle)

    def _open_metadata_handle(self, path: Path) -> int:
        assert _WINDOWS is not None
        handle = _WINDOWS.create_file(
            _win32_path(path),
            _GENERIC_WRITE | _FILE_READ_ATTRIBUTES | _FILE_WRITE_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    @staticmethod
    def _close_handle(handle: int) -> None:
        assert _WINDOWS is not None
        if not _WINDOWS.close_handle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    @staticmethod
    def _basic_info(handle: int) -> _FileBasicInfo:
        assert _WINDOWS is not None
        basic = _FileBasicInfo()
        if not _WINDOWS.get_file_information_ex(
            handle,
            _FILE_BASIC_INFO_CLASS,
            ctypes.byref(basic),
            ctypes.sizeof(basic),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return basic

    @staticmethod
    def _set_basic_info(handle: int, basic: _FileBasicInfo) -> None:
        assert _WINDOWS is not None
        if not _WINDOWS.set_file_information(
            handle,
            _FILE_BASIC_INFO_CLASS,
            ctypes.byref(basic),
            ctypes.sizeof(basic),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    @staticmethod
    def _flush_handle(handle: int) -> None:
        assert _WINDOWS is not None
        if not _WINDOWS.flush_file_buffers(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    @staticmethod
    def _stat_handle(
        handle: int, basic: _FileBasicInfo | None = None
    ) -> FileStat:
        assert _WINDOWS is not None
        standard = _FileStandardInfo()
        if not _WINDOWS.get_file_information_ex(
            handle,
            _FILE_STANDARD_INFO_CLASS,
            ctypes.byref(standard),
            ctypes.sizeof(standard),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        observed_basic = (
            NativeFileSystem._basic_info(handle) if basic is None else basic
        )
        return FileStat(
            kind=EntryKind.FILE,
            size=standard.EndOfFile,
            mtime_ns=_unix_ns(observed_basic.LastWriteTime),
            file_identity=file_identity_from_windows_handle(
                handle,
                _WINDOWS.get_file_information_ex,
            ),
            nlink=standard.NumberOfLinks,
            metadata=MetadataSnapshot(
                attributes=observed_basic.FileAttributes,
                created_ns=_unix_ns(observed_basic.CreationTime),
            ),
        )

    def _validate_existing_chain(self, root: Path, candidate: Path) -> None:
        try:
            relative = candidate.relative_to(root)
        except ValueError as error:
            raise UnsafeExecutionPath(f"path escapes reviewed root: {candidate}") from error
        current = root
        for part in relative.parts:
            current = current / part
            if os.path.lexists(_win32_path(current)):
                self._reject_reparse(current)
            else:
                break

    def _reject_reparse(self, path: Path) -> os.stat_result:
        info = Path(_win32_path(path)).lstat()
        attributes = int(getattr(info, "st_file_attributes", 0))
        if stat_module.S_ISLNK(info.st_mode) or attributes & _REPARSE_POINT:
            raise UnsafeExecutionPath(f"reparse points are not executable: {path}")
        return info

    def _reject_reparse_chain(
        self,
        path: Path,
        *,
        trusted_anchor: Path | None = None,
    ) -> None:
        logical = _lexical_logical_path(path)
        try:
            anchor = (
                str(trusted_anchor)
                if trusted_anchor is not None
                else self._observe_root_anchor(str(logical))
            )
            chain = lexical_path_chain(
                logical,
                trusted_anchor=anchor,
            )
        except (OSError, ValueError) as error:
            raise UnsafeExecutionPath(logical_error_text(error)) from error
        for component in chain:
            current = Path(component)
            self._reject_reparse(current)
            if not Path(_win32_path(current)).is_dir():
                raise UnsafeExecutionPath(
                    "reviewed root chain contains a nondirectory: "
                    f"{current}"
                )

    def _get_attributes(self, path: Path) -> int:
        if os.name != "nt":
            return (
                _READONLY if not os.access(_win32_path(path), os.W_OK) else 0
            )
        assert _WINDOWS is not None
        value = _WINDOWS.get_attributes(_win32_path(path))
        if value == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(value)

    def _set_attributes(self, path: Path, value: int) -> None:
        if os.name != "nt":
            native = Path(_win32_path(path))
            mode = native.stat().st_mode
            if value & _READONLY:
                native.chmod(mode & ~stat_module.S_IWUSR)
            else:
                native.chmod(mode | stat_module.S_IWUSR)
            return
        assert _WINDOWS is not None
        if not _WINDOWS.set_attributes(_win32_path(path), value):
            raise ctypes.WinError(ctypes.get_last_error())

    def _set_standard_attributes(self, path: Path, desired: int) -> None:
        current = self._get_attributes(path)
        self._set_attributes(
            path, (current & ~MANAGED_FILE_ATTRIBUTE_MASK) | desired
        )

    def _set_creation_time(self, path: Path, created_ns: int) -> None:
        self._set_windows_file_times(
            path,
            created_ns=created_ns,
            modified_ns=None,
        )

    def _set_windows_file_times(
        self,
        path: Path,
        *,
        created_ns: int | None,
        modified_ns: int | None,
    ) -> None:
        assert _WINDOWS is not None
        handle = _WINDOWS.create_file(
            _win32_path(path),
            _FILE_WRITE_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            (
                _FILE_FLAG_BACKUP_SEMANTICS
                if Path(_win32_path(path)).is_dir()
                else _FILE_ATTRIBUTE_NORMAL
            ),
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        created = (
            None
            if created_ns is None
            else _filetime(created_ns)
        )
        modified = (
            None
            if modified_ns is None
            else _filetime(modified_ns)
        )
        try:
            if not _WINDOWS.set_file_time(
                handle,
                None if created is None else ctypes.byref(created),
                None,
                None if modified is None else ctypes.byref(modified),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            _WINDOWS.close_handle(handle)

    def _observe_root_volume(self, path: str) -> NativeVolumeInfo:
        logical = _lexical_logical_path(path)
        if os.name != "nt":
            observed = Path(_win32_path(logical)).stat(follow_symlinks=False)
            return NativeVolumeInfo(
                VolumeId(f"{observed.st_dev:x}", "UNKNOWN"),
                VolumeEvidence(device_id=self._observe_root_anchor(str(logical))),
                255,
                0,
            )
        assert _WINDOWS is not None
        volume_path = ctypes.create_unicode_buffer(32768)
        if not _WINDOWS.get_volume_path(
            _win32_path(logical), volume_path, len(volume_path)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        serial = wintypes.DWORD()
        max_component = wintypes.DWORD()
        flags = wintypes.DWORD()
        filesystem = ctypes.create_unicode_buffer(261)
        if not _WINDOWS.get_volume_information(
            volume_path.value,
            None,
            0,
            ctypes.byref(serial),
            ctypes.byref(max_component),
            ctypes.byref(flags),
            filesystem,
            len(filesystem),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return NativeVolumeInfo(
            VolumeId(
                f"{serial.value:08X}",
                filesystem.value.upper() or "UNKNOWN",
            ),
            VolumeEvidence(
                device_id=from_extended_length_path(volume_path.value)
            ),
            int(max_component.value),
            int(flags.value),
        )

    def _volume_id(self, path: Path) -> VolumeId:
        return self._observe_root_volume(str(path)).volume_id

    def _volume_serial(self, path: Path) -> str:
        return self._volume_id(path).serial

    @staticmethod
    def _created_ns(info: os.stat_result) -> int | None:
        value = getattr(info, "st_birthtime_ns", None)
        if value is None and os.name == "nt":
            value = getattr(info, "st_ctime_ns", None)
        return None if value is None else int(value)


def _write_all(target: BinaryIO, chunk: bytes, owner: str) -> None:
    view = memoryview(chunk)
    while view:
        written = target.write(view)
        if written is None or written <= 0:
            raise OSError(f"{owner} made no forward write progress")
        view = view[written:]


def _matches_backup_source(actual: FileStat, expected: FileStat) -> bool:
    """Match the reviewed target facts against its one opened handle."""

    return (
        actual.kind is expected.kind
        and actual.size == expected.size
        and actual.mtime_ns == expected.mtime_ns
        and actual.nlink == expected.nlink
        and actual.metadata == expected.metadata
        and (
            expected.file_identity is None
            or actual.file_identity == expected.file_identity
        )
    )


def _matches_copied_backup_source(
    before: FileStat,
    after: FileStat,
    copied_size: int,
) -> bool:
    """Confirm one open source stayed stable through the complete copy."""

    return copied_size == before.size and after == before


def _win32_path(path: Path | str) -> str:
    return to_extended_length_path(str(path))


def _resolved_logical_path(path: Path | str, *, strict: bool) -> Path:
    resolved = Path(_win32_path(path)).resolve(strict=strict)
    return Path(from_extended_length_path(str(resolved)))


def _lexical_logical_path(path: Path | str) -> Path:
    return Path(lexical_absolute_path(path))


def _windows_ticks(unix_ns: int) -> int:
    return unix_ns // 100 + _WINDOWS_EPOCH_TICKS


def _filetime(unix_ns: int) -> wintypes.FILETIME:
    intervals = _windows_ticks(unix_ns)
    return wintypes.FILETIME(intervals & 0xFFFFFFFF, intervals >> 32)


def _unix_ns(windows_ticks: int) -> int:
    return (windows_ticks - _WINDOWS_EPOCH_TICKS) * 100
