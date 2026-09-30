"""Bounded one-file byte pipeline for the executor component."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
from queue import Empty, Full, Queue, ShutDown, SimpleQueue
import stat
from threading import TIMEOUT_MAX, Event, Lock, Thread
import traceback
import math
import time
from typing import BinaryIO, cast

from namisync.core.evidence import (
    HasherFactory,
    finish_content_hasher,
    new_content_hasher,
    update_content_hasher,
)
from namisync.core.execution import CopyDigest, CopyWriteCapabilities, DirectWriteFallback
from namisync.core.scalars import checked_add_signed_64
from namisync.core.session import Canceled, PauseRequested


_PIPELINE_BYTE_BUDGET = 32 * 1024 * 1024
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
    write_mode: str = "buffered"
    fallback_reason: DirectWriteFallback | None = None


@dataclass(slots=True)
class _PipelineDiagnostics:
    reader_blocked_seconds: float = 0.0
    writer_starved_seconds: float = 0.0
    payload_high_water: int = 0


@dataclass(slots=True)
class _PipelineAccounting:
    reserved_bytes: int = 0


@dataclass(slots=True)
class _BorrowedChunk:
    backing: bytearray
    view: memoryview
    size: int

    @property
    def allocation_size(self) -> int:
        return len(self.backing)


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
        queue_items: int = 32,
        poll_seconds: float = 0.01,
    ) -> None:
        if not callable(hasher_factory):
            raise TypeError("content hasher factory must be callable")
        if not isinstance(collect_metrics, bool):
            raise TypeError("collect_metrics must be a bool")
        if type(queue_items) is not int:
            raise TypeError("queue_items must be an integer")
        if not 1 <= queue_items <= 32:
            raise ValueError("queue_items must be between 1 and 32")
        if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)):
            raise TypeError("poll_seconds must be numeric")
        if poll_seconds <= 0 or (
            isinstance(poll_seconds, float) and not math.isfinite(poll_seconds)
        ):
            raise ValueError("poll_seconds must be finite and positive")
        self._queue_items = queue_items
        self._poll_seconds = float(min(poll_seconds, TIMEOUT_MAX))
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
        if chunk_size > _PIPELINE_BYTE_BUDGET:
            raise ValueError("copy chunk size exceeds the pipeline byte budget")

        capabilities = target if isinstance(target, CopyWriteCapabilities) else None
        alignment = 1 if capabilities is None else capabilities.copy_alignment
        if alignment <= 0:
            raise ValueError("copy writer alignment must be positive")
        fallback_reason = (
            None if capabilities is None else capabilities.copy_fallback_reason
        )
        direct = alignment > 1
        write_mode = "direct" if direct else "buffered"
        slot_cost = chunk_size + alignment - 1 if direct else chunk_size
        if slot_cost > _PIPELINE_BYTE_BUDGET:
            raise ValueError("aligned copy chunk exceeds the pipeline byte budget")

        self._last_metrics = None
        if self._collect_metrics:
            self._last_metrics = CopyPipelineMetrics(
                write_mode=write_mode, fallback_reason=fallback_reason,
            )
        prefetched: list[bytes] = []
        if (
            not direct and chunk_size <= _PIPELINE_BYTE_BUDGET // 2
            and _single_chunk_candidate(source, chunk_size)
        ):
            checkpoint()
            first = source.read(chunk_size)
            if not isinstance(first, bytes) or len(first) > chunk_size:
                raise TypeError("copy source read() must return bounded bytes")
            if not first:
                digest = finish_content_hasher(new_content_hasher(self._hasher_factory))
                return CopyDigest(digest=digest, size=0)
            checkpoint()
            second = source.read(chunk_size)
            if not isinstance(second, bytes) or len(second) > chunk_size:
                raise TypeError("copy source read() must return bounded bytes")
            if not second:
                hasher = new_content_hasher(self._hasher_factory)
                if self._collect_metrics:
                    self._last_metrics = CopyPipelineMetrics(
                        payload_high_water=len(first),
                        write_mode=write_mode, fallback_reason=fallback_reason,
                    )
                update_content_hasher(hasher, first)
                _write_all(target, first, "copy backend")
                checkpoint()
                on_chunk(len(first))
                return CopyDigest(
                    digest=finish_content_hasher(hasher), size=len(first)
                )
            prefetched = [first, second]
            del first, second

        hash_queue: Queue[bytes | _BorrowedChunk | object] = Queue(maxsize=self._queue_items)
        write_queue: Queue[bytes | _BorrowedChunk | object] = Queue(maxsize=self._queue_items)
        completions: SimpleQueue[tuple[int, _BorrowedChunk | None]] = SimpleQueue()
        abort = Event()
        first_error = _FirstPipelineError()
        writer_done = Event()
        accounting = _PipelineAccounting(
            reserved_bytes=sum(len(part) for part in prefetched)
        )
        diagnostics = (
            _PipelineDiagnostics() if self._collect_metrics else None
        )
        if diagnostics is not None:
            diagnostics.payload_high_water = accounting.reserved_bytes
        digest_result: list[bytes] = []
        total_read = 0
        free_buffers: list[_BorrowedChunk] = []
        all_buffers: list[_BorrowedChunk] = []
        allocated_bytes = 0
        coordinator_error: BaseException | None = None

        def shut_down() -> None:
            abort.set()
            hash_queue.shutdown(immediate=True)
            write_queue.shutdown(immediate=True)

        def fail(error: BaseException) -> None:
            first_error.store(error)
            shut_down()

        def put_worker(
            queue: Queue[bytes | _BorrowedChunk | object],
            value: bytes | _BorrowedChunk | object,
        ) -> None:
            while not abort.is_set():
                try:
                    queue.put(value, timeout=self._poll_seconds)
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
                        item = hash_queue.get(timeout=self._poll_seconds)
                    except Empty:
                        continue
                    except ShutDown:
                        return
                    if item is _PIPELINE_EOF:
                        digest_result.append(finish_content_hasher(hasher))
                        put_worker(write_queue, _PIPELINE_EOF)
                        return
                    chunk = cast(bytes | _BorrowedChunk, item)
                    hash_bytes = (
                        chunk.view[:chunk.size].toreadonly()
                        if isinstance(chunk, _BorrowedChunk) else chunk
                    )
                    update_content_hasher(hasher, hash_bytes)
                    del hash_bytes
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
                        item = write_queue.get(timeout=self._poll_seconds)
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
                    chunk = cast(bytes | _BorrowedChunk, item)
                    write_bytes = (
                        chunk.view[:chunk.size]
                        if isinstance(chunk, _BorrowedChunk) else chunk
                    )
                    _write_all(target, write_bytes, "copy backend")
                    del write_bytes
                    if abort.is_set():
                        return
                    completed_size = (
                        chunk.size if isinstance(chunk, _BorrowedChunk) else len(chunk)
                    )
                    borrowed = chunk if isinstance(chunk, _BorrowedChunk) else None
                    del chunk
                    del item
                    completions.put((completed_size, borrowed))
                    del borrowed
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
                    completed, borrowed = completions.get_nowait()
                except Empty:
                    return
                if abort.is_set():
                    return
                accounting.reserved_bytes -= (
                    borrowed.allocation_size if borrowed is not None else completed
                )
                if accounting.reserved_bytes < 0:
                    raise RuntimeError("pipeline payload accounting underflow")
                if abort.is_set():
                    return
                poll_coordinator()
                if abort.is_set():
                    return
                on_chunk(completed)
                if borrowed is not None:
                    free_buffers.append(borrowed)

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
                time.sleep(self._poll_seconds)
            if wait_started is not None:
                diagnostics.reader_blocked_seconds += (
                    time.perf_counter() - wait_started
                )

        def put_coordinator(
            queue: Queue[bytes | _BorrowedChunk | object],
            value: bytes | _BorrowedChunk | object,
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
                    queue.put(value, timeout=self._poll_seconds)
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
                precharged = bool(prefetched)
                reservation = 0 if precharged else slot_cost
                if reservation:
                    wait_for_capacity(reservation)
                    accounting.reserved_bytes += reservation
                if diagnostics is not None:
                    diagnostics.payload_high_water = max(
                        diagnostics.payload_high_water,
                        accounting.reserved_bytes,
                    )
                try:
                    if direct:
                        if free_buffers:
                            borrowed = free_buffers.pop()
                        else:
                            if allocated_bytes + slot_cost > _PIPELINE_BYTE_BUDGET:
                                raise RuntimeError("aligned pool exceeded its byte budget")
                            borrowed = _allocate_borrowed_chunk(chunk_size, alignment)
                            allocated_bytes += borrowed.allocation_size
                            all_buffers.append(borrowed)
                        size = 0
                        while size < chunk_size:
                            count = source.readinto(borrowed.view[size:])
                            if type(count) is not int or not 0 <= count <= chunk_size - size:
                                raise OSError("copy source readinto() returned an invalid count")
                            if count == 0:
                                break
                            size += count
                        borrowed.size = size
                        chunk: bytes | _BorrowedChunk = borrowed
                    else:
                        chunk = prefetched.pop(0) if precharged else source.read(chunk_size)
                except BaseException:
                    accounting.reserved_bytes -= reservation
                    raise
                if not isinstance(chunk, (bytes, _BorrowedChunk)):
                    accounting.reserved_bytes -= reservation
                    raise TypeError("copy source read() must return bytes")
                actual_size = chunk.size if isinstance(chunk, _BorrowedChunk) else len(chunk)
                if not actual_size:
                    accounting.reserved_bytes -= reservation
                    if isinstance(chunk, _BorrowedChunk):
                        free_buffers.append(chunk)
                    put_coordinator(hash_queue, _PIPELINE_EOF)
                    break
                if actual_size > chunk_size:
                    accounting.reserved_bytes -= reservation
                    raise OSError("copy source returned more bytes than requested")
                if not direct and not precharged:
                    accounting.reserved_bytes -= chunk_size - actual_size
                total_read = checked_add_signed_64(
                    total_read,
                    actual_size,
                    "copied bytes",
                )
                put_coordinator(hash_queue, chunk)
                del chunk
                if direct:
                    del borrowed

            while not writer_done.is_set():
                try:
                    checkpoint()
                except BaseException as error:
                    raise_checkpoint_failure(error)
                raise_worker_error()
                drain_completions()
                if writer_done.wait(self._poll_seconds):
                    break
            drain_completions()
            try:
                checkpoint()
            except BaseException as error:
                raise_checkpoint_failure(error)
            raise_worker_error()
        except BaseException as error:
            coordinator_error = error
            shut_down()
            raise
        finally:
            if abort.is_set():
                shut_down()
            for thread in started:
                thread.join()
            if direct:
                worker_error = first_error.get()
                if worker_error is not None:
                    _clear_inactive_error_frames(worker_error)
                if coordinator_error is not None:
                    _clear_inactive_error_frames(coordinator_error)
                chunk = b""
                borrowed = None
                while True:
                    try:
                        completions.get_nowait()
                    except Empty:
                        break
                free_buffers.clear()
                for slot in all_buffers:
                    slot.view.release()
                    slot.backing = bytearray()
                all_buffers.clear()
            if abort.is_set():
                accounting.reserved_bytes = 0
            if diagnostics is not None:
                self._last_metrics = CopyPipelineMetrics(
                    reader_blocked_seconds=diagnostics.reader_blocked_seconds,
                    writer_starved_seconds=diagnostics.writer_starved_seconds,
                    payload_high_water=diagnostics.payload_high_water,
                    reserved_bytes=accounting.reserved_bytes,
                    write_mode=write_mode,
                    fallback_reason=fallback_reason,
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


def _allocate_borrowed_chunk(size: int, alignment: int) -> _BorrowedChunk:
    backing = bytearray(size + alignment - 1)
    address = ctypes.addressof(ctypes.c_char.from_buffer(backing))
    offset = -address % alignment
    return _BorrowedChunk(backing, memoryview(backing)[offset:offset + size], 0)


def _single_chunk_candidate(source: BinaryIO, chunk_size: int) -> bool:
    """Use the synchronous shortcut only for a regular file currently this short."""

    try:
        info = os.fstat(source.fileno())
        position = source.tell()
    except (AttributeError, OSError, ValueError):
        return False
    return stat.S_ISREG(info.st_mode) and 0 <= info.st_size - position <= chunk_size


def _clear_inactive_error_frames(error: BaseException) -> None:
    """Keep error identity and causes while releasing borrowed worker views."""

    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if current.__traceback__ is not None:
            traceback.clear_frames(current.__traceback__)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)


def _write_all(target: BinaryIO, chunk: bytes | memoryview, owner: str) -> None:
    view = memoryview(chunk)
    while view:
        written = target.write(view)
        if written is None or written <= 0:
            raise OSError(f"{owner} made no forward write progress")
        view = view[written:]
