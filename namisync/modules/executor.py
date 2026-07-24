"""Guarded M0 single-worker execution for reviewed sync plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
import ctypes
from ctypes import wintypes
import os
from pathlib import Path, PureWindowsPath
from queue import Empty, Full, Queue, ShutDown, SimpleQueue
import shutil
import stat as stat_module
from threading import Event, Lock, Thread
import time
from typing import BinaryIO, cast

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherContractError,
    HasherFactory,
    Outcome,
    Provenance,
    RecordingStatus,
    StreamingHasher,
    require_content_digest,
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
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    owned_temp_run_id,
)
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.planning import OpId, OperationKind, OperationReason, PlanOperation
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
_NOT_CONTENT_INDEXED = 0x00002000
_STANDARD_ATTRIBUTE_MASK = _READONLY | _HIDDEN | _SYSTEM
_PRESERVED_ATTRIBUTE_MASK = _STANDARD_ATTRIBUTE_MASK | _NOT_CONTENT_INDEXED
_REPARSE_POINT = 0x00000400
_SHARING_VIOLATIONS = {32, 33}
_PIPELINE_BYTE_BUDGET = 32 * 1024 * 1024
_PIPELINE_QUEUE_ITEMS = 32
_PIPELINE_POLL_SECONDS = 0.01
_PIPELINE_EOF = object()
_SMALL_CHUNK_SIZE = 256 * 1024
_MEDIUM_CHUNK_SIZE = 1024 * 1024
_LARGE_CHUNK_SIZE = 4 * 1024 * 1024
_MEDIUM_CHUNK_THRESHOLD = 8 * 1024 * 1024
_LARGE_CHUNK_THRESHOLD = 32 * 1024 * 1024
# The cross-volume M1 sweep found the first repeatable HDD benefit at 8 MiB;
# solid-state targets were neutral, so smaller files avoid the setup cost.
_PREALLOCATION_THRESHOLD = 8 * 1024 * 1024

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


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
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

        self.get_file_information = kernel32.GetFileInformationByHandle
        self.get_file_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        self.get_file_information.restype = wintypes.BOOL

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


@dataclass(slots=True)
class _PipelineMetrics:
    reader_blocked_seconds: float = 0.0
    writer_starved_seconds: float = 0.0
    payload_high_water: int = 0
    reserved_bytes: int = 0


class _FirstPipelineError:
    def __init__(self) -> None:
        self._lock = Lock()
        self._error: BaseException | None = None

    def store(self, error: BaseException) -> bool:
        with self._lock:
            if self._error is not None:
                return False
            self._error = error
            return True

    def get(self) -> BaseException | None:
        with self._lock:
            return self._error


def _new_content_hasher(factory: HasherFactory) -> StreamingHasher:
    try:
        hasher = factory()
    except Exception as error:
        raise HasherContractError("content hasher factory failed") from error
    if not callable(getattr(hasher, "update", None)):
        raise HasherContractError("content hasher must provide update(bytes)")
    if not callable(getattr(hasher, "digest", None)):
        raise HasherContractError("content hasher must provide digest()")
    return hasher


def _update_content_hasher(hasher: StreamingHasher, chunk: bytes) -> None:
    try:
        hasher.update(chunk)
    except Exception as error:
        raise HasherContractError("content hasher update failed") from error


def _finish_content_hasher(hasher: StreamingHasher) -> bytes:
    try:
        digest = hasher.digest()
    except Exception as error:
        raise HasherContractError("content hasher digest failed") from error
    return require_content_digest(digest)


class NativeCopyBackend:
    """Bounded immutable reader -> hasher -> writer byte pipeline."""

    def __init__(self, *, hasher_factory: HasherFactory) -> None:
        if not callable(hasher_factory):
            raise TypeError("content hasher factory must be callable")
        self._hasher_factory = hasher_factory
        self._last_metrics: _PipelineMetrics | None = None

    def copy(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        chunk_size: int,
        checkpoint,
        on_chunk,
    ) -> CopyDigest:
        if chunk_size <= 0:
            raise ValueError("copy chunk size must be positive")

        hash_queue: Queue[bytes | object] = Queue(maxsize=_PIPELINE_QUEUE_ITEMS)
        write_queue: Queue[bytes | object] = Queue(maxsize=_PIPELINE_QUEUE_ITEMS)
        completions: SimpleQueue[int] = SimpleQueue()
        abort = Event()
        first_error = _FirstPipelineError()
        writer_done = Event()
        metrics = _PipelineMetrics()
        digest_result: list[bytes] = []
        total_read = 0

        def shut_down() -> None:
            abort.set()
            hash_queue.shutdown(immediate=True)
            write_queue.shutdown(immediate=True)

        def fail(error: BaseException) -> None:
            first_error.store(error)
            shut_down()

        def put_worker(queue: Queue[bytes | object], value: bytes | object) -> None:
            while not abort.is_set():
                try:
                    queue.put(value, timeout=_PIPELINE_POLL_SECONDS)
                    return
                except Full:
                    continue
                except ShutDown:
                    return

        def hasher_worker() -> None:
            try:
                hasher = _new_content_hasher(self._hasher_factory)
                while not abort.is_set():
                    try:
                        item = hash_queue.get(timeout=_PIPELINE_POLL_SECONDS)
                    except Empty:
                        continue
                    except ShutDown:
                        return
                    if item is _PIPELINE_EOF:
                        digest_result.append(_finish_content_hasher(hasher))
                        put_worker(write_queue, _PIPELINE_EOF)
                        return
                    chunk = cast(bytes, item)
                    _update_content_hasher(hasher, chunk)
                    if abort.is_set():
                        return
                    put_worker(write_queue, chunk)
                    del chunk
                    del item
            except BaseException as error:
                fail(error)

        def writer_worker() -> None:
            try:
                while not abort.is_set():
                    started_waiting = time.perf_counter()
                    try:
                        item = write_queue.get(timeout=_PIPELINE_POLL_SECONDS)
                    except Empty:
                        metrics.writer_starved_seconds += (
                            time.perf_counter() - started_waiting
                        )
                        continue
                    except ShutDown:
                        return
                    metrics.writer_starved_seconds += (
                        time.perf_counter() - started_waiting
                    )
                    if item is _PIPELINE_EOF:
                        writer_done.set()
                        return
                    chunk = cast(bytes, item)
                    _write_all(target, chunk, "copy backend")
                    if abort.is_set():
                        return
                    completed_size = len(chunk)
                    del chunk
                    del item
                    completions.put(completed_size)
            except BaseException as error:
                fail(error)

        hasher_thread = Thread(
            target=hasher_worker,
            name="namisync-copy-hasher",
            daemon=False,
        )
        writer_thread = Thread(
            target=writer_worker,
            name="namisync-copy-writer",
            daemon=False,
        )
        threads = (hasher_thread, writer_thread)

        def raise_worker_error() -> None:
            error = first_error.get()
            if error is not None:
                raise error

        def raise_checkpoint_failure(error: BaseException) -> None:
            if isinstance(error, (Canceled, PauseRequested)):
                raise error
            raise_worker_error()
            raise error

        def poll_coordinator() -> None:
            try:
                checkpoint()
            except BaseException as error:
                raise_checkpoint_failure(error)
            raise_worker_error()

        def drain_completions() -> None:
            while True:
                if abort.is_set():
                    return
                try:
                    completed = completions.get_nowait()
                except Empty:
                    return
                if abort.is_set():
                    return
                metrics.reserved_bytes -= completed
                if metrics.reserved_bytes < 0:
                    raise RuntimeError("pipeline payload accounting underflow")
                if abort.is_set():
                    return
                poll_coordinator()
                if abort.is_set():
                    return
                on_chunk(completed)

        def wait_for_capacity(reservation: int) -> None:
            wait_started: float | None = None
            while metrics.reserved_bytes + reservation > _PIPELINE_BYTE_BUDGET:
                if wait_started is None:
                    wait_started = time.perf_counter()
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                if metrics.reserved_bytes + reservation <= _PIPELINE_BYTE_BUDGET:
                    break
                time.sleep(_PIPELINE_POLL_SECONDS)
            if wait_started is not None:
                metrics.reader_blocked_seconds += time.perf_counter() - wait_started

        def put_coordinator(
            queue: Queue[bytes | object], value: bytes | object
        ) -> None:
            wait_started: float | None = None
            while True:
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                try:
                    queue.put(value, timeout=_PIPELINE_POLL_SECONDS)
                    if wait_started is not None:
                        metrics.reader_blocked_seconds += (
                            time.perf_counter() - wait_started
                        )
                    return
                except Full:
                    if wait_started is None:
                        wait_started = time.perf_counter()
                except ShutDown:
                    try:
                        checkpoint()
                    except BaseException as error:
                        raise_checkpoint_failure(error)
                    raise_worker_error()
                    raise RuntimeError("copy pipeline shut down without an error")

        started: list[Thread] = []
        try:
            for thread in threads:
                thread.start()
                started.append(thread)

            while True:
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                wait_for_capacity(chunk_size)
                metrics.reserved_bytes += chunk_size
                metrics.payload_high_water = max(
                    metrics.payload_high_water, metrics.reserved_bytes
                )
                try:
                    chunk = source.read(chunk_size)
                except BaseException:
                    metrics.reserved_bytes -= chunk_size
                    raise
                if not chunk:
                    metrics.reserved_bytes -= chunk_size
                    put_coordinator(hash_queue, _PIPELINE_EOF)
                    break
                if not isinstance(chunk, bytes):
                    metrics.reserved_bytes -= chunk_size
                    raise TypeError("copy source read() must return bytes")
                if len(chunk) > chunk_size:
                    metrics.reserved_bytes -= chunk_size
                    raise OSError("copy source returned more bytes than requested")
                metrics.reserved_bytes -= chunk_size - len(chunk)
                total_read += len(chunk)
                put_coordinator(hash_queue, chunk)
                del chunk

            while not writer_done.is_set():
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                if writer_done.wait(_PIPELINE_POLL_SECONDS):
                    break
            drain_completions()
            try:
                checkpoint()
            except BaseException as error:
                raise_checkpoint_failure(error)
            raise_worker_error()
        except BaseException:
            shut_down()
            raise
        finally:
            if abort.is_set():
                shut_down()
            for thread in started:
                thread.join()
            if abort.is_set():
                metrics.reserved_bytes = 0
            self._last_metrics = metrics

        if len(digest_result) != 1:
            raise RuntimeError("copy pipeline did not produce one digest")
        if metrics.reserved_bytes != 0:
            raise RuntimeError("copy pipeline leaked payload reservations")
        return CopyDigest(digest=digest_result[0], size=total_read)


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

    copy_backend: CopyBackend
    failure: FailurePolicy = field(default_factory=BoundedFailurePolicy)
    clock: Clock = field(default_factory=SystemClock)
    max_chunk_size: int = 4 * 1024 * 1024
    max_retries: int = 3
    progress_interval_seconds: float = 0.1
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.max_chunk_size <= 0:
            raise ValueError("maximum copy chunk size must be positive")
        if self.max_retries < 0:
            raise ValueError("maximum retries cannot be negative")
        if self.progress_interval_seconds < 0:
            raise ValueError("progress interval cannot be negative")
        if not callable(self.monotonic) or not callable(self.sleep):
            raise TypeError("executor timing collaborators must be callable")


def _copy_chunk_size(reviewed_size: int, max_chunk_size: int) -> int:
    if reviewed_size < 0:
        raise ValueError("reviewed copy size cannot be negative")
    if max_chunk_size <= 0:
        raise ValueError("maximum copy chunk size must be positive")
    if reviewed_size < _MEDIUM_CHUNK_THRESHOLD:
        selected = _SMALL_CHUNK_SIZE
    elif reviewed_size < _LARGE_CHUNK_THRESHOLD:
        selected = _MEDIUM_CHUNK_SIZE
    else:
        selected = _LARGE_CHUNK_SIZE
    return min(selected, max_chunk_size)


def _allocation_size(reviewed_size: int) -> int | None:
    return reviewed_size if reviewed_size >= _PREALLOCATION_THRESHOLD else None


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
        return self.stat_path(path)

    def stat_path(self, path: Path) -> FileStat | None:
        observation = self._stat_path_and_access(path)
        return None if observation is None else observation[0]

    def _stat_path_and_access(
        self, path: Path
    ) -> tuple[FileStat, int] | None:
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
        return (
            FileStat(
                kind=kind,
                size=size,
                mtime_ns=info.st_mtime_ns,
                file_identity=FileIdentity(
                    self._volume_serial(path), int(info.st_ino)
                ),
                nlink=info.st_nlink,
                metadata=MetadataSnapshot(
                    attributes=int(getattr(info, "st_file_attributes", 0)),
                    created_ns=self._created_ns(info),
                ),
            ),
            info.st_atime_ns,
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

    def remove_orphaned_temps(
        self,
        target_root: Path,
        parent_paths: frozenset[str],
        current_run_id: RunId,
    ) -> None:
        """Remove exact prior-run temps from preflight's touched parents."""

        current = str(current_run_id)
        target_root = target_root.resolve(strict=True)
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
                if not os.path.lexists(parent):
                    continue
                self._reject_reparse(parent)
                if not parent.is_dir():
                    continue
            else:
                parent = target_root
                self._reject_reparse(parent)
            if self._volume_serial(parent) != target_volume:
                continue
            with os.scandir(parent) as entries:
                for entry in entries:
                    owner = owned_temp_run_id(entry.name)
                    if (
                        owner is not None
                        and owner != current
                        and entry.is_file(follow_symlinks=False)
                    ):
                        self.remove_owned_temp(Path(entry.path))

    def open_source(self, path: Path) -> BinaryIO:
        flags = os.O_RDONLY
        if os.name == "nt":
            flags |= os.O_BINARY | os.O_SEQUENTIAL
        descriptor = os.open(path, flags)
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
        descriptor = os.open(path, flags, 0o666)
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
        desired = stat.metadata.attributes & _PRESERVED_ATTRIBUTE_MASK
        if not apply_readonly:
            desired &= ~_READONLY
        self._set_standard_attributes(path, desired)

    def copy_security(self, source: Path, target: Path) -> None:
        if os.name != "nt":
            shutil.copystat(source, target, follow_symlinks=False)
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
            with path.open("r+b", buffering=0) as held:
                if acl_source is not None:
                    try:
                        self.copy_security(acl_source, path)
                    except Exception as error:
                        raise _SecurityCopyFailure(str(error)) from error
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
                    raise _SecurityCopyFailure(str(error)) from error
            current = self._basic_info(handle)
            desired_attributes = (
                current.FileAttributes & ~_PRESERVED_ATTRIBUTE_MASK
            ) | (
                intended.metadata.attributes
                & (_PRESERVED_ATTRIBUTE_MASK & ~_READONLY)
            )
            creation = current.CreationTime
            if preserve_created and intended.metadata.created_ns is not None:
                creation = _windows_ticks(intended.metadata.created_ns)
            modified = _windows_ticks(intended.mtime_ns)
            self._set_basic_info(
                handle,
                _FileBasicInfo(
                    creation,
                    modified,
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

        observation = self._stat_path_and_access(path)
        if observation is None:
            raise FileNotFoundError(path)
        observed, observed_access_ns = observation
        repair_mtime = observed.mtime_ns != finalized_temp.mtime_ns
        repair_access = observed_access_ns != finalized_temp.mtime_ns
        repair_created = (
            preserve_created
            and intended.metadata.created_ns is not None
            and observed.metadata.created_ns != finalized_temp.metadata.created_ns
        )
        desired_managed = (
            intended.metadata.attributes & _PRESERVED_ATTRIBUTE_MASK
        )
        if not apply_readonly:
            desired_managed &= ~_READONLY
        repair_attributes = (
            observed.metadata.attributes & _PRESERVED_ATTRIBUTE_MASK
        ) != desired_managed
        if not (
            repair_mtime
            or repair_access
            or repair_created
            or repair_attributes
        ):
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
                            & ~_PRESERVED_ATTRIBUTE_MASK
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
            last_access = (
                _windows_ticks(finalized_temp.mtime_ns)
                if repair_access
                else current.LastAccessTime
            )
            last_write = (
                _windows_ticks(finalized_temp.mtime_ns)
                if repair_mtime
                else current.LastWriteTime
            )
            attributes = (
                (current.FileAttributes & ~_PRESERVED_ATTRIBUTE_MASK)
                | desired_managed
                if repair_attributes
                else current.FileAttributes
            )
            self._set_basic_info(
                handle,
                _FileBasicInfo(
                    creation,
                    last_access,
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
        published = False
        try:
            with self.open_source(source) as reader, self.create_temp(
                temp, allocation_size=None
            ) as writer:
                while True:
                    checkpoint()
                    chunk = reader.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    _write_all(writer, chunk, "backup copy")
            source_stat = self.stat_path(source)
            if source_stat is None:
                raise FileNotFoundError(source)
            finalized = self.finalize_temp(
                temp,
                source_stat,
                preserve_created=True,
                acl_source=None,
            )
            self.publish_new(temp, target)
            published = True
            self.ensure_published_metadata(
                target,
                finalized,
                source_stat,
                preserve_created=True,
                apply_readonly=True,
            )
        except BaseException as error:
            if not published:
                try:
                    self.remove_owned_temp(temp)
                except Exception as cleanup_error:
                    error.add_note(
                        f"backup temp cleanup failed: {cleanup_error!r}"
                    )
            raise

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
        information = _ByHandleFileInformation()
        if not _WINDOWS.get_file_information(
            handle, ctypes.byref(information)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        observed_basic = (
            NativeFileSystem._basic_info(handle) if basic is None else basic
        )
        size = (information.nFileSizeHigh << 32) | information.nFileSizeLow
        file_index = (
            information.nFileIndexHigh << 32
        ) | information.nFileIndexLow
        return FileStat(
            kind=EntryKind.FILE,
            size=size,
            mtime_ns=_unix_ns(observed_basic.LastWriteTime),
            file_identity=FileIdentity(
                f"{information.dwVolumeSerialNumber:08X}", file_index
            ),
            nlink=information.nNumberOfLinks,
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
        assert _WINDOWS is not None
        value = _WINDOWS.get_attributes(_win32_path(path))
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
        assert _WINDOWS is not None
        if not _WINDOWS.set_attributes(_win32_path(path), value):
            raise ctypes.WinError(ctypes.get_last_error())

    def _set_standard_attributes(self, path: Path, desired: int) -> None:
        current = self._get_attributes(path)
        self._set_attributes(
            path, (current & ~_PRESERVED_ATTRIBUTE_MASK) | desired
        )

    def _set_creation_time(self, path: Path, created_ns: int) -> None:
        assert _WINDOWS is not None
        handle = _WINDOWS.create_file(
            _win32_path(path),
            _FILE_WRITE_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS if path.is_dir() else _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        intervals = _windows_ticks(created_ns)
        filetime = wintypes.FILETIME(intervals & 0xFFFFFFFF, intervals >> 32)
        try:
            if not _WINDOWS.set_file_time(
                handle, ctypes.byref(filetime), None, None
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            _WINDOWS.close_handle(handle)

    def _volume_serial(self, path: Path) -> str:
        if os.name != "nt":
            return f"{path.stat(follow_symlinks=False).st_dev:x}"
        assert _WINDOWS is not None
        volume_path = ctypes.create_unicode_buffer(32768)
        if not _WINDOWS.get_volume_path(
            _win32_path(path), volume_path, len(volume_path)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        serial = wintypes.DWORD()
        if not _WINDOWS.get_volume_information(
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


def _write_all(target: BinaryIO, chunk: bytes, owner: str) -> None:
    view = memoryview(chunk)
    while view:
        written = target.write(view)
        if written is None or written <= 0:
            raise OSError(f"{owner} made no forward write progress")
        view = view[written:]


def _win32_path(path: Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def _windows_ticks(unix_ns: int) -> int:
    return unix_ns // 100 + _WINDOWS_EPOCH_TICKS


def _unix_ns(windows_ticks: int) -> int:
    return (windows_ticks - _WINDOWS_EPOCH_TICKS) * 100


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
    finalized: FileStat


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

    items = tuple(
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
        items=items,
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
    if operation.kind is OperationKind.RECASE:
        return _recase(
            operation,
            xset,
            recorder,
            fs,
            source_root,
            target_root,
            state,
        )
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
        reviewed_size = operation.source_expected.size
        chunk_size = _copy_chunk_size(reviewed_size, policies.max_chunk_size)
        with fs.open_source(source) as reader, fs.create_temp(
            temp, allocation_size=_allocation_size(reviewed_size)
        ) as writer:
            digest = policies.copy_backend.copy(
                reader,
                writer,
                chunk_size=chunk_size,
                checkpoint=ctx.checkpoint,
                on_chunk=progress.copied,
            )
        intended = operation.intended or operation.source_expected
        if digest.size != reviewed_size:
            raise OperationFailure(
                ExecutionReason.SOURCE_DRIFT,
                "source byte count changed during copy",
            )
        try:
            finalized = fs.finalize_temp(
                temp,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                acl_source=source if xset.plan.preservation.preserve_acl else None,
            )
        except _SecurityCopyFailure as error:
            raise OperationFailure(
                ExecutionReason.ACL_COPY_FAILED,
                "security descriptor copy failed before publish",
                cause=error.__cause__ if isinstance(error.__cause__, Exception) else error,
            ) from error
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
        return _PreparedCopy(source, target, temp, digest, intended, finalized)
    except BaseException:
        raise


def _published_copy_stat(
    prepared: _PreparedCopy,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
) -> FileStat:
    observed = fs.ensure_published_metadata(
        prepared.target,
        prepared.finalized,
        prepared.intended,
        preserve_created=xset.plan.preservation.preserve_created,
        apply_readonly=True,
    )
    return _profiled_stat(
        observed, xset.plan.target_profile.stable_file_identity
    )


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
    published = _published_copy_stat(prepared, xset, fs)
    detail = _durability_detail(fs, prepared.target.parent)
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

    if (
        continuation.trash is not None
        and continuation.backup_stat is not None
        and continuation.detail.get("backup") == "hardlink"
    ):
        fs.ensure_published_metadata(
            continuation.trash,
            continuation.backup_stat,
            operation.target_expected,
            preserve_created=xset.plan.preservation.preserve_created,
            apply_readonly=True,
        )
    published_stat = _published_copy_stat(prepared, xset, fs)
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


def _recase(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    old_rel, old_expected = _prior_target(operation)
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING,
            "recase operation lacks source evidence",
        )
    if (
        old_rel == operation.target_rel_path
        or normalize_relative_path(old_rel)
        != normalize_relative_path(operation.target_rel_path)
    ):
        raise OperationFailure(
            ExecutionReason.UNSAFE_PATH,
            "recase paths must differ only by Windows filename casing",
        )
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    _guard_present(
        fs,
        target_root,
        old_rel,
        old_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    old = fs.resolve(target_root, old_rel, must_exist=True)
    new = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    _flush_before_destructive(recorder, state)
    try:
        fs.rename_new(old, new)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "recase destination is a distinct occupied entry",
            cause=error,
        ) from error
    detail = _durability_detail(fs, old.parent, new.parent)
    recased = _profiled_stat(
        _require_stat_path(fs, new),
        xset.plan.target_profile.stable_file_identity,
    )
    _record(
        state,
        detail,
        lambda: recorder.record_recased(operation.op_id, recased),
    )
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
        published_stat = _published_copy_stat(prepared, xset, fs)
        continuation = _MoveUpdateContinuation(
            prepared=prepared,
            old_relative_path=old_rel,
            old_expected=old_expected,
            published_stat=published_stat,
        )
        state.retry_continuations[operation.op_id] = continuation
    elif isinstance(existing, _MoveUpdateContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match move-update")

    if existing is not None:
        published_actual = _require_stat_path(fs, prepared.target)
        if not _same_file_version(published_actual, continuation.published_stat):
            raise OperationFailure(
                ExecutionReason.TARGET_DRIFT,
                "published move-update target drifted before completion",
            )
    if continuation.attestation is None:
        continuation.attestation = _attestation(
            prepared.digest, continuation.published_stat, policies.clock
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
    directory_cleanup = (
        operation.target_expected.kind is EntryKind.DIRECTORY
        and operation.reason is OperationReason.DIRECTORY_CLEANUP
    )
    _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
        matcher=_matches_directory_cleanup if directory_cleanup else None,
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
    matcher: Callable[[FileStat, FileStat], bool] | None = None,
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
    if not (matcher or _matches_expected)(actual, expected):
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


def _matches_directory_cleanup(actual: FileStat, expected: FileStat) -> bool:
    """Match an emptied planned directory while ignoring child-induced churn."""

    return (
        actual.kind is EntryKind.DIRECTORY
        and expected.kind is EntryKind.DIRECTORY
        and actual.size == expected.size
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
    if subject.size != digest.size:
        raise OperationFailure(
            ExecutionReason.PUBLISHED_SIZE_MISMATCH,
            (
                "published target size does not match copied content: "
                f"{subject.size} != {digest.size}"
            ),
        )
    return Attestation(
        content=ContentEvidence(
            algorithm="xxh3_128",
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
        flushed = fs.flush_directory(directory)
        if not flushed:
            warnings.append(f"parent directory flush unsupported: {directory}")
    return {} if not warnings else {"durability_warnings": tuple(warnings)}
