"""Guarded M0 single-worker execution for reviewed sync plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat as stat_module
import time
from typing import BinaryIO, cast

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import ItemOutcome, PhaseChanged, Progress
from namisync.core.execution import (
    Clock,
    Continue,
    CopyBackend,
    CopyDigest,
    ExecutionReason,
    ExecutionSet,
    ExecutorFileSystem,
    FailureDecision,
    FailurePolicy,
    Recorder,
    Retry,
    RunId,
    Stop,
)
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot
from namisync.core.pathing import validate_relative_path
from namisync.core.planning import OpId, OperationKind, PlanOperation
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)


_READONLY = 0x00000001
_HIDDEN = 0x00000002
_SYSTEM = 0x00000004
_STANDARD_ATTRIBUTE_MASK = _READONLY | _HIDDEN | _SYSTEM
_REPARSE_POINT = 0x00000400
_SHARING_VIOLATIONS = {32, 33}


class UnsafeExecutionPath(OSError):
    """A planned path cannot be resolved safely beneath its reviewed root."""


class OperationFailure(Exception):
    """A typed, user-actionable operation failure."""

    def __init__(
        self,
        reason: ExecutionReason,
        detail: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.cause = cause


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class NativeCopyBackend:
    """Bounded native byte streaming with inline SHA-256 attestation."""

    def copy(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        chunk_size: int,
        checkpoint,
        on_chunk,
    ) -> CopyDigest:
        digest = hashlib.sha256()
        size = 0
        while True:
            checkpoint()
            chunk = source.read(chunk_size)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = target.write(view)
                if written is None or written <= 0:
                    raise OSError("copy backend made no forward write progress")
                view = view[written:]
            digest.update(chunk)
            size += len(chunk)
            on_chunk(len(chunk))
        return CopyDigest(digest=digest.digest(), size=size)


class BoundedFailurePolicy:
    """Retry Windows sharing violations; continue past every other failure."""

    def __init__(self, *, retries: int = 3, initial_delay: float = 0.05) -> None:
        if retries < 0:
            raise ValueError("retry count cannot be negative")
        if initial_delay < 0:
            raise ValueError("retry delay cannot be negative")
        self._retries = retries
        self._initial_delay = initial_delay

    def on_item_failed(
        self, operation: PlanOperation, error: Exception, attempt: int
    ) -> FailureDecision:
        del operation
        winerror = _find_winerror(error)
        if winerror in _SHARING_VIOLATIONS and attempt <= self._retries:
            return Retry(self._initial_delay * (2 ** (attempt - 1)))
        return Continue()


@dataclass(frozen=True, slots=True)
class ExecutorPolicies:
    """Snapshotted executor policy implementations and bounded pacing."""

    failure: FailurePolicy = field(default_factory=BoundedFailurePolicy)
    copy_backend: CopyBackend = field(default_factory=NativeCopyBackend)
    clock: Clock = field(default_factory=SystemClock)
    chunk_size: int = 4 * 1024 * 1024
    max_retries: int = 3
    progress_interval_seconds: float = 0.1
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("copy chunk size must be positive")
        if self.max_retries < 0:
            raise ValueError("maximum retries cannot be negative")
        if self.progress_interval_seconds < 0:
            raise ValueError("progress interval cannot be negative")
        if not callable(self.monotonic) or not callable(self.sleep):
            raise TypeError("executor timing collaborators must be callable")


class NativeFileSystem:
    """Native local-filesystem primitives retained by the executor machine."""

    def resolve(self, root: Path, relative_path: str, *, must_exist: bool) -> Path:
        canonical = validate_relative_path(relative_path)
        root_path = root.resolve(strict=True)
        self._reject_reparse(root_path)
        candidate = root_path.joinpath(*PureWindowsPath(canonical).parts)
        self._validate_existing_chain(root_path, candidate)
        if must_exist and not os.path.lexists(candidate):
            raise FileNotFoundError(candidate)
        resolved = candidate.resolve(strict=must_exist)
        try:
            if os.path.commonpath((root_path, resolved)) != str(root_path):
                raise UnsafeExecutionPath(f"path escapes reviewed root: {relative_path}")
        except ValueError as error:
            raise UnsafeExecutionPath(
                f"path is not on the reviewed root volume: {relative_path}"
            ) from error
        return candidate

    def stat(self, root: Path, relative_path: str) -> FileStat | None:
        path = self.resolve(root, relative_path, must_exist=False)
        if not os.path.lexists(path):
            return None
        self._reject_reparse(path)
        info = path.stat(follow_symlinks=False)
        mode = info.st_mode
        if stat_module.S_ISREG(mode):
            kind = EntryKind.FILE
            size = info.st_size
        elif stat_module.S_ISDIR(mode):
            kind = EntryKind.DIRECTORY
            size = 0
        else:
            raise UnsafeExecutionPath(f"unsupported filesystem entry: {path}")
        attributes = int(getattr(info, "st_file_attributes", 0))
        identity = FileIdentity(
            volume_serial=self._volume_serial(path), file_index=int(info.st_ino)
        )
        return FileStat(
            kind=kind,
            size=size,
            mtime_ns=info.st_mtime_ns,
            file_identity=identity,
            nlink=info.st_nlink,
            metadata=MetadataSnapshot(
                attributes=attributes,
                created_ns=self._created_ns(info),
            ),
        )

    def stat_path(self, path: Path) -> FileStat | None:
        if not os.path.lexists(path):
            return None
        self._reject_reparse(path)
        info = path.stat(follow_symlinks=False)
        if stat_module.S_ISREG(info.st_mode):
            kind = EntryKind.FILE
            size = info.st_size
        elif stat_module.S_ISDIR(info.st_mode):
            kind = EntryKind.DIRECTORY
            size = 0
        else:
            raise UnsafeExecutionPath(f"unsupported filesystem entry: {path}")
        return FileStat(
            kind=kind,
            size=size,
            mtime_ns=info.st_mtime_ns,
            file_identity=FileIdentity(self._volume_serial(path), int(info.st_ino)),
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
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def open_source(self, path: Path) -> BinaryIO:
        return cast(BinaryIO, path.open("rb", buffering=0))

    def create_temp(self, path: Path) -> BinaryIO:
        return cast(BinaryIO, path.open("xb", buffering=0))

    def flush_file(self, stream: BinaryIO) -> None:
        stream.flush()
        os.fsync(stream.fileno())

    def flush_path(self, path: Path) -> None:
        with path.open("r+b", buffering=0) as stream:
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
        os.utime(path, ns=(stat.mtime_ns, stat.mtime_ns))
        if preserve_created and stat.metadata.created_ns is not None and os.name == "nt":
            self._set_creation_time(path, stat.metadata.created_ns)
        desired = stat.metadata.attributes & _STANDARD_ATTRIBUTE_MASK
        if not apply_readonly:
            desired &= ~_READONLY
        self._set_standard_attributes(path, desired)

    def copy_security(self, source: Path, target: Path) -> None:
        if os.name != "nt":
            shutil.copystat(source, target, follow_symlinks=False)
            return
        security_information = 0x1 | 0x2 | 0x4
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        get_security = advapi.GetFileSecurityW
        get_security.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_security.restype = wintypes.BOOL
        needed = wintypes.DWORD()
        get_security(str(source), security_information, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not get_security(
            str(source),
            security_information,
            buffer,
            needed,
            ctypes.byref(needed),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        set_security = advapi.SetFileSecurityW
        set_security.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        set_security.restype = wintypes.BOOL
        if not set_security(str(target), security_information, buffer):
            raise ctypes.WinError(ctypes.get_last_error())

    def publish_new(self, temp: Path, target: Path) -> None:
        os.rename(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        os.replace(temp, target)

    def hardlink(self, source: Path, target: Path) -> None:
        os.link(source, target)

    def copy_backup(
        self,
        source: Path,
        temp: Path,
        target: Path,
        checkpoint: Callable[[], None],
    ) -> None:
        with source.open("rb", buffering=0) as reader, temp.open("xb", buffering=0) as writer:
            while True:
                checkpoint()
                chunk = reader.read(4 * 1024 * 1024)
                if not chunk:
                    break
                view = memoryview(chunk)
                while view:
                    written = writer.write(view)
                    if written is None or written <= 0:
                        raise OSError("backup copy made no forward write progress")
                    view = view[written:]
            writer.flush()
            os.fsync(writer.fileno())
        source_stat = self.stat_path(source)
        if source_stat is None:
            raise FileNotFoundError(source)
        self.apply_metadata(
            temp,
            source_stat,
            preserve_created=True,
            apply_readonly=False,
        )
        self.flush_path(temp)
        self.publish_new(temp, target)
        self.apply_metadata(
            target,
            source_stat,
            preserve_created=True,
            apply_readonly=True,
        )

    def clear_readonly(self, path: Path) -> None:
        current = self._get_attributes(path)
        self._set_attributes(path, current & ~_READONLY)

    def rename_new(self, source: Path, target: Path) -> None:
        os.rename(source, target)

    def mkdir_new(self, path: Path) -> None:
        os.mkdir(path)

    def remove_file(self, path: Path) -> None:
        os.unlink(path)

    def remove_directory(self, path: Path) -> None:
        os.rmdir(path)

    def trash_destination(
        self, target_root: Path, run_id: RunId, relative_path: str
    ) -> Path:
        canonical = validate_relative_path(relative_path)
        root = target_root.resolve(strict=True)
        self._reject_reparse(root)
        current = root
        for part in (".synctrash", str(run_id), *PureWindowsPath(canonical).parts[:-1]):
            current = current / part
            try:
                os.mkdir(current)
            except FileExistsError:
                if not current.is_dir():
                    raise UnsafeExecutionPath(f"trash parent is not a directory: {current}")
            self._reject_reparse(current)
            if current.stat().st_dev != root.stat().st_dev:
                raise UnsafeExecutionPath("trash path leaves the target volume")
        destination = current / PureWindowsPath(canonical).name
        self._validate_existing_chain(root, destination)
        return destination

    def flush_directory(self, path: Path) -> bool:
        if os.name != "nt":
            try:
                descriptor = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                return True
            except OSError:
                return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            str(path),
            0x80000000,
            0x1 | 0x2 | 0x4,
            None,
            3,
            0x02000000,
            None,
        )
        invalid = wintypes.HANDLE(-1).value
        if handle == invalid:
            return False
        try:
            flush = kernel32.FlushFileBuffers
            flush.argtypes = [wintypes.HANDLE]
            flush.restype = wintypes.BOOL
            return bool(flush(handle))
        finally:
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            close(handle)

    def _validate_existing_chain(self, root: Path, candidate: Path) -> None:
        try:
            relative = candidate.relative_to(root)
        except ValueError as error:
            raise UnsafeExecutionPath(f"path escapes reviewed root: {candidate}") from error
        current = root
        for part in relative.parts:
            current = current / part
            if os.path.lexists(current):
                self._reject_reparse(current)
            else:
                break

    def _reject_reparse(self, path: Path) -> None:
        info = path.lstat()
        attributes = int(getattr(info, "st_file_attributes", 0))
        if stat_module.S_ISLNK(info.st_mode) or attributes & _REPARSE_POINT:
            raise UnsafeExecutionPath(f"reparse points are not executable: {path}")

    def _get_attributes(self, path: Path) -> int:
        if os.name != "nt":
            return _READONLY if not os.access(path, os.W_OK) else 0
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_attributes = kernel32.GetFileAttributesW
        get_attributes.argtypes = [wintypes.LPCWSTR]
        get_attributes.restype = wintypes.DWORD
        value = get_attributes(str(path))
        if value == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(value)

    def _set_attributes(self, path: Path, value: int) -> None:
        if os.name != "nt":
            mode = path.stat().st_mode
            if value & _READONLY:
                path.chmod(mode & ~stat_module.S_IWUSR)
            else:
                path.chmod(mode | stat_module.S_IWUSR)
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        set_attributes = kernel32.SetFileAttributesW
        set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        set_attributes.restype = wintypes.BOOL
        if not set_attributes(str(path), value):
            raise ctypes.WinError(ctypes.get_last_error())

    def _set_standard_attributes(self, path: Path, desired: int) -> None:
        current = self._get_attributes(path)
        self._set_attributes(path, (current & ~_STANDARD_ATTRIBUTE_MASK) | desired)

    def _set_creation_time(self, path: Path, created_ns: int) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            str(path),
            0x0100,
            0x1 | 0x2 | 0x4,
            None,
            3,
            0x02000000 if path.is_dir() else 0x00000080,
            None,
        )
        invalid = wintypes.HANDLE(-1).value
        if handle == invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        intervals = created_ns // 100 + 116444736000000000
        filetime = wintypes.FILETIME(intervals & 0xFFFFFFFF, intervals >> 32)
        try:
            set_file_time = kernel32.SetFileTime
            set_file_time.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            ]
            set_file_time.restype = wintypes.BOOL
            if not set_file_time(handle, ctypes.byref(filetime), None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            close(handle)

    def _volume_serial(self, path: Path) -> str:
        if os.name != "nt":
            return f"{path.stat(follow_symlinks=False).st_dev:x}"
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        volume_path = ctypes.create_unicode_buffer(32768)
        if not kernel32.GetVolumePathNameW(
            str(path), volume_path, len(volume_path)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        serial = wintypes.DWORD()
        if not kernel32.GetVolumeInformationW(
            volume_path.value,
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return f"{serial.value:08X}"

    @staticmethod
    def _created_ns(info: os.stat_result) -> int | None:
        value = getattr(info, "st_birthtime_ns", None)
        if value is None and os.name == "nt":
            value = getattr(info, "st_ctime_ns", None)
        return None if value is None else int(value)


def _find_winerror(error: Exception) -> int | None:
    current: BaseException | None = error
    while current is not None:
        winerror = getattr(current, "winerror", None)
        if isinstance(winerror, int):
            return winerror
        current = current.__cause__
    return None


@dataclass(frozen=True, slots=True)
class _Settled:
    outcome: Outcome
    reason: ExecutionReason | None = None
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _PreparedCopy:
    source: Path
    target: Path
    temp: Path
    digest: CopyDigest
    intended: FileStat


@dataclass(slots=True)
class _UpdateContinuation:
    prepared: _PreparedCopy
    prepared_stat: FileStat
    live_stat: FileStat
    trash: Path | None
    backup_stat: FileStat | None
    detail: dict[str, object]
    published: bool = False


@dataclass(slots=True)
class _MoveUpdateContinuation:
    prepared: _PreparedCopy
    old_relative_path: str
    old_expected: FileStat
    published_stat: FileStat
    trash: Path | None = None
    attestation: Attestation | None = None


@dataclass(slots=True)
class _ExecutionState:
    outcomes: dict[OpId, ItemOutcome]
    recording: RecordingStatus = RecordingStatus.OK
    inflight_temp: Path | None = None
    pending_directories: list[PlanOperation] = field(default_factory=list)
    ready_directories: set[OpId] = field(default_factory=set)
    restore_directories: set[OpId] = field(default_factory=set)
    retry_continuations: dict[
        OpId, _UpdateContinuation | _MoveUpdateContinuation
    ] = field(default_factory=dict)
    filesystem_failed: bool = False


class _ProgressTracker:
    def __init__(
        self,
        xset: ExecutionSet,
        ctx: RunContext,
        policies: ExecutorPolicies,
    ) -> None:
        self._ctx = ctx
        self._policies = policies
        self.items_total = len(xset.selection)
        self.items_done = len(xset.status)
        self.bytes_total = sum(
            operation.content_bytes
            for operation in xset.plan.operations
            if operation.op_id in xset.selection
            and operation.kind
            in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        )
        settled_ids = set(xset.status)
        self._committed_bytes = sum(
            operation.content_bytes
            for operation in xset.plan.operations
            if operation.op_id in settled_ids
            and xset.status[operation.op_id] is Outcome.SUCCEEDED
            and operation.kind
            in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        )
        self.bytes_done = min(self._committed_bytes, self.bytes_total)
        self._file_bytes = 0
        self._current: PlanOperation | None = None
        self._last_emitted_at = float("-inf")

    def start(self, operation: PlanOperation) -> None:
        self._current = operation
        self._file_bytes = 0
        self.emit(force=False)

    def copied(self, size: int) -> None:
        self._file_bytes += size
        candidate = min(
            self.bytes_total,
            self._committed_bytes + min(self._file_bytes, self._current.content_bytes),
        )
        self.bytes_done = max(self.bytes_done, candidate)
        self.emit(force=False)

    def settled(self, operation: PlanOperation, outcome: Outcome) -> None:
        self.items_done += 1
        if outcome is Outcome.SUCCEEDED and operation.kind in {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }:
            self._committed_bytes = min(
                self.bytes_total, self._committed_bytes + operation.content_bytes
            )
            self.bytes_done = max(self.bytes_done, self._committed_bytes)
        self._current = operation
        self.emit(force=False)

    def emit(self, *, force: bool) -> None:
        now = self._policies.monotonic()
        if (
            not force
            and now - self._last_emitted_at
            < self._policies.progress_interval_seconds
        ):
            return
        self._last_emitted_at = now
        self._ctx.emit(
            Progress(
                items_done=self.items_done,
                items_total=self.items_total,
                bytes_done=min(self.bytes_done, self.bytes_total),
                bytes_total=self.bytes_total,
                current_path=(
                    None if self._current is None else self._current.target_rel_path
                ),
            )
        )


def execute(
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
) -> OperationResult:
    """Apply remaining selected operations without emitting a terminal event.

    Commitment matching and fresh observe/preflight are workflow obligations.
    This function assumes they succeeded and retains the operation-local live
    guards that remain necessary at every point of touch.
    """

    source_root = Path(xset.plan.source_root.path)
    target_root = Path(xset.plan.target_root.path)
    state = _ExecutionState(
        outcomes={},
        restore_directories={
            operation.op_id
            for operation in xset.plan.operations
            if operation.kind is OperationKind.MKDIR
            and xset.status.get(operation.op_id) is Outcome.SUCCEEDED
        },
    )
    progress = _ProgressTracker(xset, ctx, policies)
    ctx.emit(PhaseChanged("execute"))
    progress.emit(force=True)
    current: PlanOperation | None = None

    try:
        stop_requested = False
        for operation in xset.plan.operations:
            if operation.op_id not in xset.selection or operation.op_id in xset.status:
                continue
            current = operation
            ctx.checkpoint()
            progress.start(operation)

            if stop_requested:
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.CANCELED, ExecutionReason.POLICY_STOP),
                )
                continue
            if operation.blocked:
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(
                        Outcome.FAILED,
                        ExecutionReason.BLOCKED,
                        {"blocked_reason": operation.blocked_reason.value},
                    ),
                )
                continue
            if not _dependencies_succeeded(xset, state, operation):
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.DEFERRED, ExecutionReason.DEPENDENCY_FAILED),
                )
                continue
            if operation.kind is OperationKind.MKDIR:
                try:
                    _start_directory(operation, xset, fs, target_root, state)
                except (Canceled, PauseRequested):
                    raise
                except Exception as error:
                    _settle_failure(xset, state, progress, ctx, operation, error)
                continue

            attempt = 0
            while True:
                attempt += 1
                try:
                    settled = _execute_operation(
                        operation,
                        xset,
                        ctx,
                        recorder,
                        policies,
                        fs,
                        source_root,
                        target_root,
                        state,
                        progress,
                    )
                except (Canceled, PauseRequested):
                    raise
                except Exception as error:
                    decision = policies.failure.on_item_failed(operation, error, attempt)
                    if (
                        isinstance(decision, Retry)
                        and attempt <= policies.max_retries
                    ):
                        if operation.op_id not in state.retry_continuations:
                            _cleanup_inflight(state, fs)
                        ctx.checkpoint()
                        policies.sleep(decision.after)
                        ctx.checkpoint()
                        continue
                    cleanup_error = _cleanup_inflight(state, fs)
                    state.retry_continuations.pop(operation.op_id, None)
                    if cleanup_error is not None:
                        error = OperationFailure(
                            ExecutionReason.CLEANUP_FAILED,
                            f"operation failed and its owned temp could not be removed: {cleanup_error}",
                            cause=error,
                        )
                    _settle_failure(xset, state, progress, ctx, operation, error)
                    if isinstance(decision, Stop):
                        stop_requested = True
                    break
                else:
                    state.retry_continuations.pop(operation.op_id, None)
                    _settle(xset, state, progress, ctx, operation, settled)
                    break

        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        _restore_completed_directory_metadata(xset, fs, target_root, state)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
    except Canceled:
        cleanup_error = _cleanup_inflight(state, fs)
        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        for operation in xset.plan.operations:
            if operation.op_id in xset.selection and operation.op_id not in xset.status:
                detail = {}
                if cleanup_error is not None and operation is current:
                    detail["cleanup_error"] = str(cleanup_error)
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.CANCELED, ExecutionReason.CANCELED, detail),
                )
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise
    except PauseRequested:
        _cleanup_inflight(state, fs)
        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        _restore_completed_directory_metadata(xset, fs, target_root, state)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise
    except BaseException:
        _cleanup_inflight(state, fs)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise

    operations = tuple(
        state.outcomes.get(operation.op_id)
        or ItemOutcome(
            item_id=str(operation.op_id),
            kind=operation.kind.value,
            path=operation.target_rel_path,
            outcome=xset.status[operation.op_id],
            reason="previously-settled",
            detail={"continued": True},
        )
        for operation in xset.plan.operations
        if operation.op_id in xset.selection
    )
    failed = state.filesystem_failed or any(
        outcome
        in {Outcome.FAILED, Outcome.CANCELED, Outcome.DEFERRED}
        for outcome in xset.status.values()
    )
    progress.emit(force=True)
    return OperationResult(
        status=SessionState.FAILED if failed else SessionState.COMPLETED,
        recording=state.recording,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        canceled=False,
        operations=operations,
        bytes_done=min(progress.bytes_done, progress.bytes_total),
        bytes_total=progress.bytes_total,
    )


def _execute_operation(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    if operation.kind is OperationKind.COPY:
        return _copy(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.UPDATE:
        return _update(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.MOVE:
        return _move(operation, xset, recorder, fs, target_root, state)
    if operation.kind is OperationKind.MOVE_UPDATE:
        return _move_update(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.TRASH:
        return _trash(operation, xset, recorder, fs, target_root, state)
    if operation.kind is OperationKind.DELETE:
        return _delete(operation, recorder, fs, target_root, state)
    if operation.kind is OperationKind.NOOP:
        return _noop(operation, recorder, fs, source_root, target_root, state)
    raise OperationFailure(
        ExecutionReason.IO_ERROR, f"unsupported operation kind: {operation.kind}"
    )


def _prepare_copy(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _PreparedCopy:
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING, "copy operation has no source evidence"
        )
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    _guard_expected_target(fs, target_root, operation)
    source = fs.resolve(source_root, operation.source_rel_path, must_exist=True)
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    temp = fs.owned_temp(target, xset.run_id, operation.op_id)
    try:
        fs.remove_owned_temp(temp)
    except Exception as error:
        raise OperationFailure(
            ExecutionReason.CLEANUP_FAILED,
            f"cannot recover owned temp: {temp}",
            cause=error,
        ) from error
    state.inflight_temp = temp
    try:
        with fs.open_source(source) as reader, fs.create_temp(temp) as writer:
            digest = policies.copy_backend.copy(
                reader,
                writer,
                chunk_size=policies.chunk_size,
                checkpoint=ctx.checkpoint,
                on_chunk=progress.copied,
            )
            fs.flush_file(writer)
        intended = operation.intended or operation.source_expected
        if policies.copy_backend is not None and digest.size != operation.source_expected.size:
            raise OperationFailure(
                ExecutionReason.SOURCE_DRIFT,
                "source byte count changed during copy",
            )
        if xset.plan.preservation.preserve_acl:
            try:
                fs.copy_security(source, temp)
            except Exception as error:
                raise OperationFailure(
                    ExecutionReason.ACL_COPY_FAILED,
                    "security descriptor copy failed before publish",
                    cause=error,
                ) from error
        fs.apply_metadata(
            temp,
            intended,
            preserve_created=xset.plan.preservation.preserve_created,
            apply_readonly=False,
        )
        fs.flush_path(temp)
        ctx.checkpoint()
        _guard_present(
            fs,
            source_root,
            operation.source_rel_path,
            operation.source_expected,
            missing=ExecutionReason.SOURCE_MISSING,
            drift=ExecutionReason.SOURCE_DRIFT,
        )
        _guard_expected_target(fs, target_root, operation)
        return _PreparedCopy(source, target, temp, digest, intended)
    except BaseException:
        raise


def _copy(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    prepared = _prepare_copy(
        operation,
        xset,
        ctx,
        policies,
        fs,
        source_root,
        target_root,
        state,
        progress,
    )
    try:
        fs.publish_new(prepared.temp, prepared.target)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "destination appeared before conditional publish",
            cause=error,
        ) from error
    state.inflight_temp = None
    fs.apply_metadata(
        prepared.target,
        prepared.intended,
        preserve_created=xset.plan.preservation.preserve_created,
        apply_readonly=True,
    )
    detail = _durability_detail(fs, prepared.target.parent)
    published = _profiled_stat(
        _require_stat_path(fs, prepared.target),
        xset.plan.target_profile.stable_file_identity,
    )
    attestation = _attestation(prepared.digest, published, policies.clock)
    _record(state, detail, lambda: recorder.record_copied(operation.op_id, attestation))
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _update(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "update has no displaced target evidence"
        )
    existing = state.retry_continuations.get(operation.op_id)
    if existing is None:
        prepared = _prepare_copy(
            operation,
            xset,
            ctx,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
        _guard_present(
            fs,
            target_root,
            operation.target_rel_path,
            operation.target_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )
        detail: dict[str, object] = {}
        trash: Path | None = None
        backup_error: Exception | None = None
        if xset.plan.trash_on_update:
            trash = fs.trash_destination(
                target_root, xset.run_id, operation.target_rel_path
            )
            if fs.stat_path(trash) is not None:
                raise OperationFailure(
                    ExecutionReason.TRASH_COLLISION, f"update trash exists: {trash}"
                )
            try:
                if xset.plan.target_profile.supports_hardlinks:
                    fs.hardlink(prepared.target, trash)
                    detail["backup"] = "hardlink"
                else:
                    backup_temp = fs.owned_temp(trash, xset.run_id, operation.op_id)
                    try:
                        fs.remove_owned_temp(backup_temp)
                    except Exception as error:
                        raise OperationFailure(
                            ExecutionReason.CLEANUP_FAILED,
                            f"cannot recover exact backup temp: {backup_temp}",
                            cause=error,
                        ) from error
                    fs.copy_backup(prepared.target, backup_temp, trash, ctx.checkpoint)
                    detail["backup"] = "copy"
            except (Canceled, PauseRequested):
                raise
            except Exception as error:
                if fs.stat_path(trash) is None:
                    raise
                backup_error = error
                detail["backup"] = (
                    "hardlink"
                    if xset.plan.target_profile.supports_hardlinks
                    else "copy"
                )
        continuation = _UpdateContinuation(
            prepared=prepared,
            prepared_stat=_require_stat_path(fs, prepared.temp),
            live_stat=_require_stat_path(fs, prepared.target),
            trash=trash,
            backup_stat=None if trash is None else _require_stat_path(fs, trash),
            detail=detail,
        )
        state.retry_continuations[operation.op_id] = continuation
        if backup_error is not None:
            raise backup_error
    elif isinstance(existing, _UpdateContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match update")

    if not continuation.published:
        temp_stat = fs.stat_path(prepared.temp)
        if temp_stat is None:
            published = _require_stat_path(fs, prepared.target)
            if not _same_file_version(published, continuation.prepared_stat):
                raise OperationFailure(
                    ExecutionReason.TARGET_DRIFT,
                    "update temp disappeared without the prepared file being published",
                )
            continuation.published = True
            state.inflight_temp = None
        else:
            _guard_present(
                fs,
                source_root,
                operation.source_rel_path,
                operation.source_expected,
                missing=ExecutionReason.SOURCE_MISSING,
                drift=ExecutionReason.SOURCE_DRIFT,
            )
            _guard_path_stat(
                temp_stat,
                continuation.prepared_stat,
                ExecutionReason.TARGET_DRIFT,
                "prepared update temp drifted before retry",
            )
            live = _require_stat_path(fs, prepared.target)
            _guard_path_stat(
                live,
                continuation.live_stat,
                ExecutionReason.TARGET_DRIFT,
                "live update target drifted after its backup was created",
            )
            if continuation.trash is not None:
                backup = _require_stat_path(fs, continuation.trash)
                assert continuation.backup_stat is not None
                _guard_path_stat(
                    backup,
                    continuation.backup_stat,
                    ExecutionReason.TRASH_COLLISION,
                    "update backup drifted before retry",
                )

            readonly_cleared = bool(
                operation.target_expected.metadata.attributes & _READONLY
            )
            try:
                if readonly_cleared:
                    fs.clear_readonly(prepared.target)
                _flush_before_destructive(recorder, state)
                fs.replace(prepared.temp, prepared.target)
                state.inflight_temp = None
                continuation.published = True
            finally:
                live = fs.stat_path(prepared.target)
                if (
                    readonly_cleared
                    and not continuation.published
                    and live is not None
                    and _same_file_version(live, continuation.live_stat)
                ):
                    fs.apply_metadata(
                        prepared.target,
                        operation.target_expected,
                        preserve_created=xset.plan.preservation.preserve_created,
                        apply_readonly=True,
                    )

    if continuation.trash is not None:
        fs.apply_metadata(
            continuation.trash,
            operation.target_expected,
            preserve_created=xset.plan.preservation.preserve_created,
            apply_readonly=True,
        )
    fs.apply_metadata(
        prepared.target,
        prepared.intended,
        preserve_created=xset.plan.preservation.preserve_created,
        apply_readonly=True,
    )
    continuation.detail.update(
        _durability_detail(
            fs,
            prepared.target.parent,
            *(
                ()
                if continuation.trash is None
                else (continuation.trash.parent,)
            ),
        )
    )
    published_stat = _profiled_stat(
        _require_stat_path(fs, prepared.target),
        xset.plan.target_profile.stable_file_identity,
    )
    attestation = _attestation(prepared.digest, published_stat, policies.clock)
    _record(
        state,
        continuation.detail,
        lambda: recorder.record_updated(operation.op_id, attestation),
    )
    return _Settled(Outcome.SUCCEEDED, detail=continuation.detail)


def _move(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    old_rel, old_expected = _prior_target(operation)
    _guard_present(
        fs,
        target_root,
        old_rel,
        old_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    _guard_absent(fs, target_root, operation.target_rel_path)
    old = fs.resolve(target_root, old_rel, must_exist=True)
    new = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    _flush_before_destructive(recorder, state)
    try:
        fs.rename_new(old, new)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "move destination appeared before conditional rename",
            cause=error,
        ) from error
    detail = _durability_detail(fs, old.parent, new.parent)
    moved = _profiled_stat(
        _require_stat_path(fs, new),
        xset.plan.target_profile.stable_file_identity,
    )
    _record(state, detail, lambda: recorder.record_moved(operation.op_id, moved))
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _move_update(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    existing = state.retry_continuations.get(operation.op_id)
    if existing is None:
        old_rel, old_expected = _prior_target(operation)
        _guard_present(
            fs,
            target_root,
            old_rel,
            old_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )
        prepared = _prepare_copy(
            operation,
            xset,
            ctx,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
        try:
            fs.publish_new(prepared.temp, prepared.target)
        except FileExistsError as error:
            raise OperationFailure(
                ExecutionReason.DESTINATION_OCCUPIED,
                "move-update destination appeared before conditional publish",
                cause=error,
            ) from error
        state.inflight_temp = None
        continuation = _MoveUpdateContinuation(
            prepared=prepared,
            old_relative_path=old_rel,
            old_expected=old_expected,
            published_stat=_require_stat_path(fs, prepared.target),
        )
        state.retry_continuations[operation.op_id] = continuation
    elif isinstance(existing, _MoveUpdateContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match move-update")

    published_actual = _require_stat_path(fs, prepared.target)
    if not _same_file_version(published_actual, continuation.published_stat):
        raise OperationFailure(
            ExecutionReason.TARGET_DRIFT,
            "published move-update target drifted before completion",
        )
    fs.apply_metadata(
        prepared.target,
        prepared.intended,
        preserve_created=xset.plan.preservation.preserve_created,
        apply_readonly=True,
    )
    if continuation.attestation is None:
        published = _profiled_stat(
            _require_stat_path(fs, prepared.target),
            xset.plan.target_profile.stable_file_identity,
        )
        continuation.attestation = _attestation(
            prepared.digest, published, policies.clock
        )
    if continuation.trash is None:
        continuation.trash = fs.trash_destination(
            target_root, xset.run_id, continuation.old_relative_path
        )
    trash = continuation.trash
    old = fs.resolve(
        target_root, continuation.old_relative_path, must_exist=False
    )
    old_actual = fs.stat(target_root, continuation.old_relative_path)
    trash_actual = fs.stat_path(trash)
    if old_actual is None:
        if trash_actual is None or not _matches_expected(
            trash_actual, continuation.old_expected
        ):
            raise OperationFailure(
                ExecutionReason.TARGET_MISSING,
                "move-update old path vanished without reaching owned trash",
            )
    else:
        _guard_path_stat(
            old_actual,
            continuation.old_expected,
            ExecutionReason.TARGET_DRIFT,
            "move-update old path drifted before trash",
        )
        if trash_actual is not None:
            raise OperationFailure(
                ExecutionReason.TRASH_COLLISION,
                f"move-update trash exists: {trash}",
            )
        _flush_before_destructive(recorder, state)
        try:
            fs.rename_new(old, trash)
        except FileExistsError as error:
            raise OperationFailure(
                ExecutionReason.TRASH_COLLISION,
                "move-update trash destination appeared before conditional rename",
                cause=error,
            ) from error
    detail = _durability_detail(fs, prepared.target.parent, old.parent, trash.parent)
    assert continuation.attestation is not None
    _record(
        state,
        detail,
        lambda: recorder.record_move_updated(
            operation.op_id, continuation.attestation
        ),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _trash(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "trash operation has no target evidence"
        )
    _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    source = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
    destination = fs.trash_destination(
        target_root, xset.run_id, operation.target_rel_path
    )
    if fs.stat_path(destination) is not None:
        raise OperationFailure(
            ExecutionReason.TRASH_COLLISION, f"trash destination exists: {destination}"
        )
    _flush_before_destructive(recorder, state)
    try:
        fs.rename_new(source, destination)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.TRASH_COLLISION,
            "trash destination appeared before conditional rename",
            cause=error,
        ) from error
    detail = _durability_detail(fs, source.parent, destination.parent)
    moved = _profiled_stat(
        _require_stat_path(fs, destination),
        xset.plan.target_profile.stable_file_identity,
    )
    trash_relative = str(destination.relative_to(target_root)).replace(os.sep, "\\")
    _record(
        state,
        detail,
        lambda: recorder.record_trashed(operation.op_id, trash_relative, moved),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _delete(
    operation: PlanOperation,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "delete operation has no target evidence"
        )
    _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
    _flush_before_destructive(recorder, state)
    readonly_cleared = bool(
        operation.target_expected.metadata.attributes & _READONLY
    )
    removed = False
    try:
        if readonly_cleared:
            fs.clear_readonly(target)
        if operation.target_expected.kind is EntryKind.DIRECTORY:
            fs.remove_directory(target)
        else:
            fs.remove_file(target)
        removed = True
    finally:
        if readonly_cleared and not removed and fs.stat_path(target) is not None:
            fs.apply_metadata(
                target,
                operation.target_expected,
                preserve_created=True,
                apply_readonly=True,
            )
    detail = _durability_detail(fs, target.parent)
    _record(
        state,
        detail,
        lambda: recorder.record_deleted(operation.op_id, operation.target_expected),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _noop(
    operation: PlanOperation,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if (
        operation.source_rel_path is None
        or operation.source_expected is None
        or operation.target_expected is None
    ):
        raise OperationFailure(
            ExecutionReason.SOURCE_DRIFT, "noop lacks matching two-sided evidence"
        )
    source = _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    target = _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    detail: dict[str, object] = {}
    _record(
        state,
        detail,
        lambda: recorder.record_noop(
            operation.op_id,
            _normalized_live_stat(source, operation.source_expected),
            _normalized_live_stat(target, operation.target_expected),
        ),
    )
    return _Settled(Outcome.SKIPPED, ExecutionReason.NOOP, detail)


def _start_directory(
    operation: PlanOperation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> None:
    del xset
    _guard_absent(fs, target_root, operation.target_rel_path)
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    try:
        fs.mkdir_new(target)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "directory appeared before conditional create",
            cause=error,
        ) from error
    state.pending_directories.append(operation)
    state.ready_directories.add(operation.op_id)


def _finalize_directories(
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> None:
    pending = sorted(
        state.pending_directories,
        key=lambda operation: len(PureWindowsPath(operation.target_rel_path).parts),
        reverse=True,
    )
    state.pending_directories.clear()
    for operation in pending:
        try:
            intended = operation.intended or operation.source_expected
            if intended is None or intended.kind is not EntryKind.DIRECTORY:
                raise OperationFailure(
                    ExecutionReason.WRONG_TYPE,
                    "mkdir operation lacks intended directory metadata",
                )
            target = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
            fs.apply_metadata(
                target,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                apply_readonly=True,
            )
            detail = _durability_detail(fs, target.parent)
            actual = _profiled_stat(
                _require_stat_path(fs, target),
                xset.plan.target_profile.stable_file_identity,
            )
            _record(
                state,
                detail,
                lambda operation=operation, actual=actual: recorder.record_mkdir(
                    operation.op_id, actual
                ),
            )
            _settle(
                xset,
                state,
                progress,
                ctx,
                operation,
                _Settled(Outcome.SUCCEEDED, detail=detail),
            )
        except (Canceled, PauseRequested):
            raise
        except Exception as error:
            _settle_failure(xset, state, progress, ctx, operation, error)
        finally:
            state.ready_directories.discard(operation.op_id)


def _restore_completed_directory_metadata(
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> None:
    for operation in reversed(xset.plan.operations):
        if (
            operation.kind is not OperationKind.MKDIR
            or operation.op_id not in xset.selection
            or operation.op_id not in state.restore_directories
        ):
            continue
        intended = operation.intended or operation.source_expected
        if intended is None:
            continue
        try:
            target = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
            fs.apply_metadata(
                target,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                apply_readonly=True,
            )
        except Exception:
            state.filesystem_failed = True


def _dependencies_succeeded(
    xset: ExecutionSet, state: _ExecutionState, operation: PlanOperation
) -> bool:
    return all(
        xset.status.get(dependency) is Outcome.SUCCEEDED
        or dependency in state.ready_directories
        for dependency in operation.dependencies
    )


def _settle(
    xset: ExecutionSet,
    state: _ExecutionState,
    progress: _ProgressTracker,
    ctx: RunContext,
    operation: PlanOperation,
    settled: _Settled,
) -> None:
    if operation.op_id in xset.status:
        return
    event = ItemOutcome(
        item_id=str(operation.op_id),
        kind=operation.kind.value,
        path=operation.target_rel_path,
        outcome=settled.outcome,
        reason=None if settled.reason is None else settled.reason.value,
        detail=settled.detail,
    )
    xset.status[operation.op_id] = settled.outcome
    state.outcomes[operation.op_id] = event
    ctx.emit(event)
    progress.settled(operation, settled.outcome)


def _settle_failure(
    xset: ExecutionSet,
    state: _ExecutionState,
    progress: _ProgressTracker,
    ctx: RunContext,
    operation: PlanOperation,
    error: Exception,
) -> None:
    if isinstance(error, OperationFailure):
        reason = error.reason
        detail = error.detail
    elif isinstance(error, UnsafeExecutionPath):
        reason = ExecutionReason.UNSAFE_PATH
        detail = str(error)
    else:
        reason = (
            ExecutionReason.SHARING_VIOLATION
            if _find_winerror(error) in _SHARING_VIOLATIONS
            else ExecutionReason.IO_ERROR
        )
        detail = str(error)
    _settle(
        xset,
        state,
        progress,
        ctx,
        operation,
        _Settled(
            Outcome.FAILED,
            reason,
            {"error_type": type(error).__name__, "message": detail},
        ),
    )


def _cleanup_inflight(
    state: _ExecutionState, fs: ExecutorFileSystem
) -> Exception | None:
    if state.inflight_temp is None:
        return None
    temp = state.inflight_temp
    state.inflight_temp = None
    try:
        fs.remove_owned_temp(temp)
    except Exception as error:
        return error
    return None


def _guard_present(
    fs: ExecutorFileSystem,
    root: Path,
    relative_path: str,
    expected: FileStat,
    *,
    missing: ExecutionReason,
    drift: ExecutionReason,
) -> FileStat:
    try:
        actual = fs.stat(root, relative_path)
    except Exception as error:
        if isinstance(error, UnsafeExecutionPath):
            raise OperationFailure(
                ExecutionReason.UNSAFE_PATH, str(error), cause=error
            ) from error
        raise
    if actual is None:
        raise OperationFailure(missing, f"planned path is missing: {relative_path}")
    if not _matches_expected(actual, expected):
        reason = ExecutionReason.WRONG_TYPE if actual.kind is not expected.kind else drift
        raise OperationFailure(reason, f"planned evidence drifted: {relative_path}")
    return actual


def _matches_expected(actual: FileStat, expected: FileStat) -> bool:
    """Match every planned fact, without inventing absent identity evidence."""

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


def _guard_path_stat(
    actual: FileStat,
    expected: FileStat,
    reason: ExecutionReason,
    detail: str,
) -> None:
    if not _matches_expected(actual, expected):
        raise OperationFailure(
            ExecutionReason.WRONG_TYPE if actual.kind is not expected.kind else reason,
            detail,
        )


def _same_file_version(actual: FileStat, expected: FileStat) -> bool:
    """Recognize one prepared file across rename and partial metadata steps."""

    return (
        actual.kind is expected.kind
        and actual.size == expected.size
        and actual.mtime_ns == expected.mtime_ns
        and (
            expected.file_identity is None
            or actual.file_identity == expected.file_identity
        )
    )


def _guard_absent(
    fs: ExecutorFileSystem, root: Path, relative_path: str
) -> None:
    if fs.stat(root, relative_path) is not None:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            f"planned absent destination is occupied: {relative_path}",
        )


def _guard_expected_target(
    fs: ExecutorFileSystem,
    target_root: Path,
    operation: PlanOperation,
) -> None:
    if operation.target_expected is None:
        _guard_absent(fs, target_root, operation.target_rel_path)
    else:
        _guard_present(
            fs,
            target_root,
            operation.target_rel_path,
            operation.target_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )


def _prior_target(operation: PlanOperation) -> tuple[str, FileStat]:
    if (
        operation.prior_target_rel_path is None
        or operation.prior_target_expected is None
    ):
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING,
            "move operation lacks prior-target evidence",
        )
    return operation.prior_target_rel_path, operation.prior_target_expected


def _require_stat_path(fs: ExecutorFileSystem, path: Path) -> FileStat:
    result = fs.stat_path(path)
    if result is None:
        raise OperationFailure(
            ExecutionReason.IO_ERROR, f"filesystem result disappeared: {path}"
        )
    return result


def _profiled_stat(stat: FileStat, stable_file_identity: bool) -> FileStat:
    if stable_file_identity or stat.file_identity is None:
        return stat
    return replace(stat, file_identity=None)


def _normalized_live_stat(actual: FileStat, expected: FileStat) -> FileStat:
    """Drop evidence the reviewed capability profile intentionally omitted."""

    if expected.file_identity is None and actual.file_identity is not None:
        return replace(actual, file_identity=None)
    return actual


def _attestation(
    digest: CopyDigest, subject: FileStat, clock: Clock
) -> Attestation:
    return Attestation(
        content=ContentEvidence(
            algorithm="sha256",
            digest=digest.digest,
            size=digest.size,
            provenance=Provenance.COPY_ATTESTED,
            observed_at=clock.now(),
        ),
        subject=subject,
    )


def _record(
    state: _ExecutionState,
    detail: dict[str, object],
    command: Callable[[], None],
) -> None:
    try:
        command()
    except Exception as error:
        state.recording = RecordingStatus.DEGRADED
        detail["recording"] = RecordingStatus.DEGRADED.value
        detail["recording_error"] = f"{type(error).__name__}: {error}"


def _flush_before_destructive(
    recorder: Recorder, state: _ExecutionState
) -> None:
    try:
        recorder.flush()
    except Exception as error:
        state.recording = RecordingStatus.DEGRADED
        raise OperationFailure(
            ExecutionReason.RECORDER_FAILED,
            "recorder flush failed before destructive operation",
            cause=error,
        ) from error


def _durability_detail(
    fs: ExecutorFileSystem, *directories: Path
) -> dict[str, object]:
    warnings: list[str] = []
    seen: set[Path] = set()
    for directory in directories:
        if directory in seen:
            continue
        seen.add(directory)
        try:
            flushed = fs.flush_directory(directory)
        except Exception:
            flushed = False
        if not flushed:
            warnings.append(f"parent directory flush unsupported: {directory}")
    return {} if not warnings else {"durability_warnings": tuple(warnings)}
