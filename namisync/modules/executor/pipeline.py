"""Bounded one-file byte pipeline for the executor component."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue, ShutDown, SimpleQueue
from threading import Event, Lock, Thread
import time
from typing import BinaryIO, cast

from namisync.core.evidence import (
    HasherFactory,
    finish_content_hasher,
    new_content_hasher,
    update_content_hasher,
)
from namisync.core.execution import CopyDigest
from namisync.core.scalars import checked_add_signed_64
from namisync.core.session import Canceled, PauseRequested


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


@dataclass(frozen=True, slots=True)
class CopyPipelineMetrics:
    """Opt-in diagnostic snapshot from the most recent copy."""

    reader_blocked_seconds: float = 0.0
    writer_starved_seconds: float = 0.0
    payload_high_water: int = 0
    reserved_bytes: int = 0


@dataclass(slots=True)
class _PipelineDiagnostics:
    reader_blocked_seconds: float = 0.0
    writer_starved_seconds: float = 0.0
    payload_high_water: int = 0


@dataclass(slots=True)
class _PipelineAccounting:
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


class NativeCopyBackend:
    """Bounded immutable reader -> hasher -> writer byte pipeline."""

    def __init__(
        self,
        *,
        hasher_factory: HasherFactory,
        collect_metrics: bool = False,
    ) -> None:
        if not callable(hasher_factory):
            raise TypeError("content hasher factory must be callable")
        if not isinstance(collect_metrics, bool):
            raise TypeError("collect_metrics must be a bool")
        self._hasher_factory = hasher_factory
        self._collect_metrics = collect_metrics
        self._last_metrics: CopyPipelineMetrics | None = None

    @property
    def last_metrics(self) -> CopyPipelineMetrics | None:
        """Return the last opt-in snapshot, or None when collection is off."""

        return self._last_metrics

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
        accounting = _PipelineAccounting()
        diagnostics = (
            _PipelineDiagnostics() if self._collect_metrics else None
        )
        self._last_metrics = None
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
                hasher = new_content_hasher(self._hasher_factory)
                while not abort.is_set():
                    try:
                        item = hash_queue.get(timeout=_PIPELINE_POLL_SECONDS)
                    except Empty:
                        continue
                    except ShutDown:
                        return
                    if item is _PIPELINE_EOF:
                        digest_result.append(finish_content_hasher(hasher))
                        put_worker(write_queue, _PIPELINE_EOF)
                        return
                    chunk = cast(bytes, item)
                    update_content_hasher(hasher, chunk)
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
                    started_waiting = (
                        time.perf_counter()
                        if diagnostics is not None
                        else None
                    )
                    try:
                        item = write_queue.get(timeout=_PIPELINE_POLL_SECONDS)
                    except Empty:
                        if started_waiting is not None:
                            diagnostics.writer_starved_seconds += (
                                time.perf_counter() - started_waiting
                            )
                        continue
                    except ShutDown:
                        return
                    if started_waiting is not None:
                        diagnostics.writer_starved_seconds += (
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
                accounting.reserved_bytes -= completed
                if accounting.reserved_bytes < 0:
                    raise RuntimeError("pipeline payload accounting underflow")
                if abort.is_set():
                    return
                poll_coordinator()
                if abort.is_set():
                    return
                on_chunk(completed)

        def wait_for_capacity(reservation: int) -> None:
            wait_started: float | None = None
            while (
                accounting.reserved_bytes + reservation
                > _PIPELINE_BYTE_BUDGET
            ):
                if wait_started is None and diagnostics is not None:
                    wait_started = time.perf_counter()
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                if (
                    accounting.reserved_bytes + reservation
                    <= _PIPELINE_BYTE_BUDGET
                ):
                    break
                time.sleep(_PIPELINE_POLL_SECONDS)
            if wait_started is not None:
                diagnostics.reader_blocked_seconds += (
                    time.perf_counter() - wait_started
                )

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
                        diagnostics.reader_blocked_seconds += (
                            time.perf_counter() - wait_started
                        )
                    return
                except Full:
                    if wait_started is None and diagnostics is not None:
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
                accounting.reserved_bytes += chunk_size
                if diagnostics is not None:
                    diagnostics.payload_high_water = max(
                        diagnostics.payload_high_water,
                        accounting.reserved_bytes,
                    )
                try:
                    chunk = source.read(chunk_size)
                except BaseException:
                    accounting.reserved_bytes -= chunk_size
                    raise
                if not chunk:
                    accounting.reserved_bytes -= chunk_size
                    put_coordinator(hash_queue, _PIPELINE_EOF)
                    break
                if not isinstance(chunk, bytes):
                    accounting.reserved_bytes -= chunk_size
                    raise TypeError("copy source read() must return bytes")
                if len(chunk) > chunk_size:
                    accounting.reserved_bytes -= chunk_size
                    raise OSError("copy source returned more bytes than requested")
                accounting.reserved_bytes -= chunk_size - len(chunk)
                total_read = checked_add_signed_64(
                    total_read,
                    len(chunk),
                    "copied bytes",
                )
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
                accounting.reserved_bytes = 0
            if diagnostics is not None:
                self._last_metrics = CopyPipelineMetrics(
                    reader_blocked_seconds=diagnostics.reader_blocked_seconds,
                    writer_starved_seconds=diagnostics.writer_starved_seconds,
                    payload_high_water=diagnostics.payload_high_water,
                    reserved_bytes=accounting.reserved_bytes,
                )

        if len(digest_result) != 1:
            raise RuntimeError("copy pipeline did not produce one digest")
        if accounting.reserved_bytes != 0:
            raise RuntimeError("copy pipeline leaked payload reservations")
        return CopyDigest(digest=digest_result[0], size=total_read)


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


def _write_all(target: BinaryIO, chunk: bytes, owner: str) -> None:
    view = memoryview(chunk)
    while view:
        written = target.write(view)
        if written is None or written <= 0:
            raise OSError(f"{owner} made no forward write progress")
        view = view[written:]
