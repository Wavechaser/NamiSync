"""Focused acceptance tests for the executor's bounded byte pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import gc
import inspect
import io
from queue import Queue as ThreadQueue
import threading
import time
from typing import BinaryIO

import pytest
from xxhash import xxh3_128

from namisync.core.evidence import HasherContractError
from namisync.core.execution import CopyDigest
from namisync.core.session import Canceled, PauseRequested
import namisync.modules.executor as executor_module
from namisync.modules.executor import NativeCopyBackend


_REAL_THREAD = threading.Thread
_WAIT_SECONDS = 3.0


class InjectedPipelineFailure(RuntimeError):
    """Distinguishable failure injected at one pipeline stage."""


class InjectedHasherFailure(InjectedPipelineFailure):
    """Failure owned by the hasher worker."""


class InjectedWriterFailure(InjectedPipelineFailure):
    """Failure owned by the writer worker."""


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = _WAIT_SECONDS,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        threading.Event().wait(0.001)
    return predicate()


def _backend(
    factory: Callable[[], object] = xxh3_128,
) -> NativeCopyBackend:
    return NativeCopyBackend(hasher_factory=factory)  # type: ignore[arg-type]


def _serial_digest(
    data: bytes,
    factory: Callable[[], object] = xxh3_128,
) -> bytes:
    hasher = factory()
    hasher.update(data)  # type: ignore[attr-defined]
    return hasher.digest()  # type: ignore[no-any-return, attr-defined]


def _capture_worker_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> list[threading.Thread]:
    workers: list[threading.Thread] = []

    def tracked_thread(*args: object, **kwargs: object) -> threading.Thread:
        thread = _REAL_THREAD(*args, **kwargs)  # type: ignore[arg-type]
        workers.append(thread)
        return thread

    monkeypatch.setattr(executor_module, "Thread", tracked_thread)
    return workers


def _assert_workers_joined(
    workers: list[threading.Thread],
    *,
    copies: int = 1,
) -> None:
    assert len(workers) == copies * 2
    assert [thread.name for thread in workers] == [
        name
        for _ in range(copies)
        for name in ("namisync-copy-hasher", "namisync-copy-writer")
    ]
    assert all(thread.ident is not None for thread in workers)
    assert all(not thread.is_alive() for thread in workers)


@dataclass
class _AsyncCopy:
    thread: threading.Thread
    done: threading.Event
    results: list[CopyDigest]
    errors: list[BaseException]

    def wait(self, timeout: float = _WAIT_SECONDS) -> None:
        assert self.done.wait(timeout), "copy pipeline did not stop before the deadline"
        self.thread.join(timeout)
        assert not self.thread.is_alive()


def _start_copy(
    backend: NativeCopyBackend,
    source: BinaryIO,
    target: BinaryIO,
    *,
    chunk_size: int,
    checkpoint: Callable[[], None] = lambda: None,
    on_chunk: Callable[[int], None] = lambda _size: None,
) -> _AsyncCopy:
    done = threading.Event()
    results: list[CopyDigest] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            results.append(
                backend.copy(
                    source,
                    target,
                    chunk_size=chunk_size,
                    checkpoint=checkpoint,
                    on_chunk=on_chunk,
                )
            )
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    thread = _REAL_THREAD(target=invoke, name="pipeline-test-caller", daemon=True)
    thread.start()
    return _AsyncCopy(thread, done, results, errors)


class _ReadOnlySource:
    """Binary source deliberately offering read(), but no readinto()."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0
        self.requested_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        self.requested_sizes.append(size)
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class _SequenceSource:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self._index = 0

    def read(self, size: int) -> bytes:
        if self._index == len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        assert 0 < len(chunk) <= size
        return chunk


@pytest.mark.parametrize(
    ("data", "chunk_size"),
    [
        pytest.param(b"", 8, id="empty"),
        pytest.param(b"partial", 16, id="partial"),
        pytest.param(b"12345678", 8, id="exact"),
        pytest.param(b"12345678abcdefgh-tail", 8, id="multi"),
    ],
)
def test_pipeline_matches_serial_digest_and_starts_both_workers_for_every_size(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    chunk_size: int,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    target = io.BytesIO()
    progress: list[int] = []

    result = _backend().copy(
        io.BytesIO(data),
        target,
        chunk_size=chunk_size,
        checkpoint=lambda: None,
        on_chunk=progress.append,
    )

    assert result == CopyDigest(digest=_serial_digest(data), size=len(data))
    assert target.getvalue() == data
    assert sum(progress) == len(data)
    _assert_workers_joined(workers)


class _WrongWidthHasher:
    def update(self, _chunk: bytes) -> None:
        return None

    def digest(self) -> bytes:
        return b"x" * 32


def test_pipeline_rejects_a_wrong_width_hasher_digest_as_contract_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)

    with pytest.raises(
        HasherContractError,
        match="exactly 16 bytes",
    ):
        _backend(_WrongWidthHasher).copy(
            io.BytesIO(b"content"),
            io.BytesIO(),
            chunk_size=8,
            checkpoint=lambda: None,
            on_chunk=lambda _size: None,
        )

    _assert_workers_joined(workers)


def test_pipeline_requires_only_read_on_source() -> None:
    data = b"read-only-source" * 3
    source = _ReadOnlySource(data)
    target = io.BytesIO()

    result = _backend().copy(
        source,  # type: ignore[arg-type]
        target,
        chunk_size=7,
        checkpoint=lambda: None,
        on_chunk=lambda _size: None,
    )

    assert not hasattr(source, "readinto")
    assert source.requested_sizes
    assert set(source.requested_sizes) == {7}
    assert target.getvalue() == data
    assert result.digest == _serial_digest(data)
    assert result.size == len(data)


class _ObservedHasher:
    def __init__(
        self,
        *,
        updated: list[bytes] | None = None,
        second_update: threading.Event | None = None,
        digest_called: threading.Event | None = None,
    ) -> None:
        self._inner = xxh3_128()
        self._updated = updated
        self._second_update = second_update
        self._digest_called = digest_called
        self._updates = 0

    def update(self, chunk: bytes) -> None:
        self._updates += 1
        if self._updated is not None:
            self._updated.append(chunk)
        self._inner.update(chunk)
        if self._updates == 2 and self._second_update is not None:
            self._second_update.set()

    def digest(self) -> bytes:
        if self._digest_called is not None:
            self._digest_called.set()
        return self._inner.digest()


class _OverlapSource:
    def __init__(self, writer_started: threading.Event) -> None:
        self._writer_started = writer_started
        self._chunks = [b"aaaa", b"bbbb", b"cccc"]
        self._index = 0
        self.second_read = threading.Event()

    def read(self, size: int) -> bytes:
        if self._index == len(self._chunks):
            return b""
        if self._index == 1:
            self._writer_started.wait(_WAIT_SECONDS)
            self.second_read.set()
        chunk = self._chunks[self._index]
        self._index += 1
        assert len(chunk) <= size
        return chunk


class _BlockingFirstWriteTarget(io.BytesIO):
    def __init__(
        self,
        writer_started: threading.Event,
        release_writer: threading.Event,
    ) -> None:
        super().__init__()
        self._writer_started = writer_started
        self._release_writer = release_writer
        self._first = True

    def write(self, data: object) -> int:
        if self._first:
            self._first = False
            self._writer_started.set()
            if not self._release_writer.wait(_WAIT_SECONDS):
                raise TimeoutError("test did not release the blocked writer")
        return super().write(data)  # type: ignore[arg-type]


def test_b1_reader_and_hasher_advance_while_first_write_is_blocked() -> None:
    writer_started = threading.Event()
    release_writer = threading.Event()
    second_hash = threading.Event()
    source = _OverlapSource(writer_started)
    target = _BlockingFirstWriteTarget(writer_started, release_writer)
    progress: list[int] = []
    backend = _backend(
        lambda: _ObservedHasher(second_update=second_hash)
    )
    call = _start_copy(
        backend,
        source,  # type: ignore[arg-type]
        target,
        chunk_size=4,
        on_chunk=progress.append,
    )

    try:
        assert writer_started.wait(_WAIT_SECONDS)
        assert source.second_read.wait(_WAIT_SECONDS)
        assert second_hash.wait(_WAIT_SECONDS)
        assert not call.done.is_set()
        assert progress == []
    finally:
        release_writer.set()

    call.wait()
    assert call.errors == []
    assert call.results[0].size == 12
    assert target.getvalue() == b"aaaabbbbcccc"
    assert progress == [4, 4, 4]


class _BudgetSource:
    def __init__(self, chunks: int) -> None:
        self._chunks = chunks
        self.reads = 0

    def read(self, size: int) -> bytes:
        if self.reads == self._chunks:
            return b""
        self.reads += 1
        return bytes([self.reads]) * size


class _DiscardingBlockedTarget:
    def __init__(self, release_writer: threading.Event) -> None:
        self._release_writer = release_writer
        self.writer_started = threading.Event()
        self.written = 0

    def write(self, data: object) -> int:
        size = len(data)  # type: ignore[arg-type]
        if not self.writer_started.is_set():
            self.writer_started.set()
            if not self._release_writer.wait(_WAIT_SECONDS):
                raise TimeoutError("test did not release the blocked writer")
        self.written += size
        return size


def test_b2_blocked_writer_caps_lookahead_at_32_mib_budget() -> None:
    chunk_size = 4 * 1024 * 1024
    release_writer = threading.Event()
    capacity_wait = threading.Event()
    source = _BudgetSource(chunks=20)
    target = _DiscardingBlockedTarget(release_writer)
    backend = _backend()

    def checkpoint() -> None:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if (
            caller is not None
            and caller.f_code.co_name == "wait_for_capacity"
        ):
            capacity_wait.set()

    call = _start_copy(
        backend,
        source,  # type: ignore[arg-type]
        target,  # type: ignore[arg-type]
        chunk_size=chunk_size,
        checkpoint=checkpoint,
    )

    try:
        assert target.writer_started.wait(_WAIT_SECONDS)
        assert capacity_wait.wait(_WAIT_SECONDS)
        assert source.reads == 8
        assert not call.done.is_set()
    finally:
        release_writer.set()

    call.wait(timeout=6.0)
    assert call.errors == []
    assert source.reads == 20
    assert target.written == 20 * chunk_size
    metrics = backend._last_metrics
    assert metrics is not None
    assert metrics.payload_high_water == executor_module._PIPELINE_BYTE_BUDGET
    assert metrics.payload_high_water == 32 * 1024 * 1024
    assert metrics.reserved_bytes == 0


class _PayloadTracker:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.alive = 0
        self.max_alive = 0


class _TrackedPayload(bytes):
    def __new__(cls, size: int, tracker: _PayloadTracker):
        value = super().__new__(cls, size)
        value.tracker = tracker
        with tracker.lock:
            tracker.alive += 1
            tracker.max_alive = max(tracker.max_alive, tracker.alive)
        return value

    def __del__(self) -> None:
        tracker = self.tracker
        with tracker.lock:
            tracker.alive -= 1


class _TrackedPayloadSource:
    def __init__(
        self, chunks: int, chunk_size: int, tracker: _PayloadTracker
    ) -> None:
        self._chunks = chunks
        self._chunk_size = chunk_size
        self._tracker = tracker
        self._reads = 0

    def read(self, size: int) -> bytes:
        assert size == self._chunk_size
        if self._reads == self._chunks:
            return b""
        self._reads += 1
        gc.collect()
        return _TrackedPayload(size, self._tracker)


class _DiscardingTarget:
    def write(self, data: object) -> int:
        return len(data)  # type: ignore[arg-type]


def test_b2_completed_payload_references_release_before_new_admission() -> None:
    chunk_size = 4 * 1024 * 1024
    tracker = _PayloadTracker()

    result = _backend().copy(
        _TrackedPayloadSource(40, chunk_size, tracker),  # type: ignore[arg-type]
        _DiscardingTarget(),  # type: ignore[arg-type]
        chunk_size=chunk_size,
        checkpoint=lambda: None,
        on_chunk=lambda _size: None,
    )
    gc.collect()

    assert result.size == 40 * chunk_size
    assert tracker.max_alive <= 8
    assert tracker.alive == 0


class _ItemCapSource:
    def __init__(self, chunks: int, chunk_size: int) -> None:
        self._chunks = chunks
        self._chunk_size = chunk_size
        self.reads = 0
        self.eof_read = threading.Event()

    def read(self, size: int) -> bytes:
        assert size == self._chunk_size
        if self.reads == self._chunks:
            self.eof_read.set()
            return b""
        self.reads += 1
        return bytes([self.reads]) * size


def test_b2_hash_fifo_independently_plateaus_at_32_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queues: list[ThreadQueue[bytes | object]] = []

    def tracked_queue(maxsize: int = 0) -> ThreadQueue[bytes | object]:
        queue: ThreadQueue[bytes | object] = ThreadQueue(maxsize=maxsize)
        queues.append(queue)
        return queue

    monkeypatch.setattr(executor_module, "Queue", tracked_queue)
    workers = _capture_worker_threads(monkeypatch)
    chunk_size = 256 * 1024
    chunk_count = 96
    release_writer = threading.Event()
    hash_fifo_blocked = threading.Event()
    plateau_reads: list[int] = []
    source = _ItemCapSource(chunk_count, chunk_size)
    target = _DiscardingBlockedTarget(release_writer)
    backend = _backend()

    def checkpoint() -> None:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if (
            caller is not None
            and caller.f_code.co_name == "put_coordinator"
            and len(queues) == 2
            and queues[0].full()
            and queues[1].full()
        ):
            plateau_reads.append(source.reads)
            if len(plateau_reads) >= 3:
                hash_fifo_blocked.set()

    call = _start_copy(
        backend,
        source,  # type: ignore[arg-type]
        target,  # type: ignore[arg-type]
        chunk_size=chunk_size,
        checkpoint=checkpoint,
    )

    try:
        assert target.writer_started.wait(_WAIT_SECONDS)
        assert hash_fifo_blocked.wait(_WAIT_SECONDS)
        assert len(queues) == 2
        assert queues[0].qsize() == executor_module._PIPELINE_QUEUE_ITEMS
        assert queues[1].qsize() == executor_module._PIPELINE_QUEUE_ITEMS
        assert len(set(plateau_reads)) == 1
        assert source.reads == plateau_reads[-1]
        assert source.reads < chunk_count
        assert not source.eof_read.is_set()
        assert not call.done.is_set()
    finally:
        release_writer.set()

    call.wait(timeout=6.0)
    assert call.errors == []
    assert len(call.results) == 1
    assert call.results[0].size == chunk_count * chunk_size
    assert source.reads == chunk_count
    assert source.eof_read.is_set()
    assert target.written == chunk_count * chunk_size
    metrics = backend._last_metrics
    assert metrics is not None
    assert metrics.payload_high_water < executor_module._PIPELINE_BYTE_BUDGET
    assert metrics.reserved_bytes == 0
    _assert_workers_joined(workers)


def test_b3_shallow_grown_source_hits_item_cap_then_hands_off_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queues: list[ThreadQueue[bytes | object]] = []

    def tracked_queue(maxsize: int = 0) -> ThreadQueue[bytes | object]:
        queue: ThreadQueue[bytes | object] = ThreadQueue(maxsize=maxsize)
        queues.append(queue)
        return queue

    monkeypatch.setattr(executor_module, "Queue", tracked_queue)
    workers = _capture_worker_threads(monkeypatch)
    chunk_size = 256 * 1024
    chunk_count = 40
    release_writer = threading.Event()
    source = _ItemCapSource(chunk_count, chunk_size)
    target = _DiscardingBlockedTarget(release_writer)
    progress: list[int] = []
    backend = _backend()
    call = _start_copy(
        backend,
        source,  # type: ignore[arg-type]
        target,  # type: ignore[arg-type]
        chunk_size=chunk_size,
        on_chunk=progress.append,
    )

    try:
        assert target.writer_started.wait(_WAIT_SECONDS)
        assert source.eof_read.wait(_WAIT_SECONDS)
        assert len(queues) == 2
        assert _wait_until(queues[1].full)
        assert queues[1].qsize() == executor_module._PIPELINE_QUEUE_ITEMS
        assert not call.done.is_set()
    finally:
        release_writer.set()

    call.wait(timeout=6.0)
    assert call.errors == []
    assert len(call.results) == 1
    assert call.results[0].size == chunk_count * chunk_size
    assert source.reads == chunk_count
    assert target.written == chunk_count * chunk_size
    assert progress == [chunk_size] * chunk_count
    metrics = backend._last_metrics
    assert metrics is not None
    assert metrics.payload_high_water < executor_module._PIPELINE_BYTE_BUDGET
    assert metrics.reserved_bytes == 0
    _assert_workers_joined(workers)


class _TraceTarget(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.written_chunks: list[bytes] = []
        self.source_object_ids: list[int] = []

    def write(self, data: object) -> int:
        payload = bytes(data)  # type: ignore[arg-type]
        self.written_chunks.append(payload)
        if isinstance(data, memoryview):
            self.source_object_ids.append(id(data.obj))
        return super().write(data)  # type: ignore[arg-type]


def test_b12_progress_is_ordered_hashed_fully_written_and_on_caller_thread() -> None:
    chunks = [b"a", b"bb", b"ccc", b"dddd"]
    hashed_chunks: list[bytes] = []
    callback_sizes: list[int] = []
    callback_threads: list[int] = []
    target = _TraceTarget()
    caller_thread = threading.get_ident()

    def on_chunk(size: int) -> None:
        index = len(callback_sizes)
        assert hashed_chunks[index] == chunks[index]
        assert target.written_chunks[index] == chunks[index]
        callback_sizes.append(size)
        callback_threads.append(threading.get_ident())

    result = _backend(
        lambda: _ObservedHasher(updated=hashed_chunks)
    ).copy(
        _SequenceSource(chunks),  # type: ignore[arg-type]
        target,
        chunk_size=4,
        checkpoint=lambda: None,
        on_chunk=on_chunk,
    )

    assert callback_sizes == [1, 2, 3, 4]
    assert callback_threads == [caller_thread] * len(chunks)
    assert hashed_chunks == chunks
    assert target.written_chunks == chunks
    assert target.source_object_ids == [id(chunk) for chunk in chunks]
    assert target.getvalue() == b"".join(chunks)
    assert result.size == sum(map(len, chunks))
    assert result.digest == _serial_digest(b"".join(chunks))


class _ThirdWriteFailureTarget:
    def __init__(
        self,
        failure: BaseException,
        allow_failure: threading.Event,
    ) -> None:
        self._failure = failure
        self._allow_failure = allow_failure
        self.writes = 0
        self.written_chunks: list[bytes] = []

    def write(self, data: object) -> int:
        self.writes += 1
        payload = bytes(data)  # type: ignore[arg-type]
        if self.writes == 3:
            if not self._allow_failure.wait(_WAIT_SECONDS):
                raise TimeoutError("caller never drained the prior completions")
            raise self._failure
        self.written_chunks.append(payload)
        return len(payload)


def test_b12_failed_write_never_overreports_progress() -> None:
    chunks = [b"a", b"bb", b"ccc", b"dddd", b"eeeee"]
    failure = InjectedPipelineFailure("third write failed")
    allow_failure = threading.Event()
    target = _ThirdWriteFailureTarget(failure, allow_failure)
    callback_sizes: list[int] = []
    callback_threads: list[int] = []
    caller_thread = threading.get_ident()

    def on_chunk(size: int) -> None:
        callback_sizes.append(size)
        callback_threads.append(threading.get_ident())
        if len(callback_sizes) == 2:
            allow_failure.set()

    with pytest.raises(InjectedPipelineFailure) as caught:
        _backend().copy(
            _SequenceSource(chunks),  # type: ignore[arg-type]
            target,  # type: ignore[arg-type]
            chunk_size=5,
            checkpoint=lambda: None,
            on_chunk=on_chunk,
        )

    assert caught.value is failure
    assert target.written_chunks == chunks[:2]
    assert callback_sizes == [1, 2]
    assert callback_threads == [caller_thread, caller_thread]
    assert sum(callback_sizes) == sum(map(len, target.written_chunks))


class _ShortWriteTarget(io.BytesIO):
    def __init__(self, maximum: int) -> None:
        super().__init__()
        self._maximum = maximum
        self.calls = 0

    def write(self, data: object) -> int:
        self.calls += 1
        limited = memoryview(data)[: self._maximum]  # type: ignore[arg-type]
        return super().write(limited)


def test_short_writes_continue_until_each_chunk_is_complete() -> None:
    data = b"short-writes-must-progress"
    target = _ShortWriteTarget(maximum=2)
    progress: list[int] = []

    result = _backend().copy(
        io.BytesIO(data),
        target,
        chunk_size=7,
        checkpoint=lambda: None,
        on_chunk=progress.append,
    )

    assert target.getvalue() == data
    assert target.calls > len(progress)
    assert progress == [7, 7, 7, 5]
    assert result.digest == _serial_digest(data)
    assert result.size == len(data)


class _NoProgressTarget:
    def __init__(self, response: int | None) -> None:
        self._response = response
        self.calls = 0

    def write(self, _data: object) -> int | None:
        self.calls += 1
        return self._response


@pytest.mark.parametrize("response", [pytest.param(0, id="zero"), pytest.param(None, id="none")])
def test_zero_or_none_write_fails_and_joins_workers(
    monkeypatch: pytest.MonkeyPatch,
    response: int | None,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    target = _NoProgressTarget(response)
    progress: list[int] = []

    with pytest.raises(
        OSError,
        match="copy backend made no forward write progress",
    ):
        _backend().copy(
            io.BytesIO(b"payload"),
            target,  # type: ignore[arg-type]
            chunk_size=4,
            checkpoint=lambda: None,
            on_chunk=progress.append,
        )

    assert target.calls == 1
    assert progress == []
    _assert_workers_joined(workers)


class _FailingReadSource:
    def __init__(
        self,
        failure: BaseException,
        first_write_done: threading.Event,
    ) -> None:
        self._failure = failure
        self._first_write_done = first_write_done
        self._first = True

    def read(self, _size: int) -> bytes:
        if self._first:
            self._first = False
            return b"first"
        self._first_write_done.wait(_WAIT_SECONDS)
        raise self._failure


class _SignalingTarget(io.BytesIO):
    def __init__(self, first_write_done: threading.Event) -> None:
        super().__init__()
        self._first_write_done = first_write_done

    def write(self, data: object) -> int:
        written = super().write(data)  # type: ignore[arg-type]
        self._first_write_done.set()
        return written


def test_b5_midstream_oserror_is_preserved_and_joins_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    failure = OSError("injected midstream source read failure")
    first_write_done = threading.Event()
    backend = _backend()

    with pytest.raises(
        OSError,
        match="injected midstream source read failure",
    ) as caught:
        backend.copy(
            _FailingReadSource(failure, first_write_done),  # type: ignore[arg-type]
            _SignalingTarget(first_write_done),
            chunk_size=8,
            checkpoint=lambda: None,
            on_chunk=lambda _size: None,
        )

    assert caught.value is failure
    _assert_workers_joined(workers)
    assert backend._last_metrics is not None
    assert backend._last_metrics.reserved_bytes == 0


class _BlockedFailingTarget:
    def __init__(
        self,
        failure: BaseException,
        fail_now: threading.Event,
    ) -> None:
        self._failure = failure
        self._fail_now = fail_now
        self.started = threading.Event()

    def write(self, _data: object) -> int:
        self.started.set()
        if not self._fail_now.wait(_WAIT_SECONDS):
            raise TimeoutError("coordinator never reached a blocked handoff")
        raise self._failure


def test_writer_failure_wakes_blocked_coordinator_and_preserves_original_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "_PIPELINE_QUEUE_ITEMS", 1)
    workers = _capture_worker_threads(monkeypatch)
    failure = InjectedPipelineFailure("writer failed while caller was blocked")
    fail_now = threading.Event()
    coordinator_blocked = threading.Event()
    target = _BlockedFailingTarget(failure, fail_now)
    backend = _backend()

    def checkpoint() -> None:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if (
            target.started.is_set()
            and caller is not None
            and caller.f_code.co_name == "put_coordinator"
        ):
            coordinator_blocked.set()
            fail_now.set()

    call = _start_copy(
        backend,
        _SequenceSource([bytes([index]) for index in range(1, 12)]),  # type: ignore[arg-type]
        target,  # type: ignore[arg-type]
        chunk_size=1,
        checkpoint=checkpoint,
    )

    try:
        assert target.started.wait(_WAIT_SECONDS)
        assert coordinator_blocked.wait(_WAIT_SECONDS)
        call.wait()
    finally:
        fail_now.set()

    assert call.results == []
    assert call.errors == [failure]
    _assert_workers_joined(workers)


class _BlockedFailingHasher:
    def __init__(
        self,
        failure: BaseException,
        fail_now: threading.Event,
    ) -> None:
        self._inner = xxh3_128()
        self._failure = failure
        self._fail_now = fail_now
        self.started = threading.Event()
        self._updates = 0

    def update(self, chunk: bytes) -> None:
        self._updates += 1
        if self._updates == 2:
            self.started.set()
            if not self._fail_now.wait(_WAIT_SECONDS):
                raise TimeoutError("coordinator never reached a blocked handoff")
            raise self._failure
        self._inner.update(chunk)

    def digest(self) -> bytes:
        return self._inner.digest()


def test_hasher_failure_wakes_blocked_coordinator_and_preserves_original_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "_PIPELINE_QUEUE_ITEMS", 1)
    workers = _capture_worker_threads(monkeypatch)
    failure = InjectedPipelineFailure("hasher failed while caller was blocked")
    fail_now = threading.Event()
    coordinator_blocked = threading.Event()
    hasher = _BlockedFailingHasher(failure, fail_now)
    backend = _backend(lambda: hasher)

    def checkpoint() -> None:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if (
            hasher.started.is_set()
            and caller is not None
            and caller.f_code.co_name == "put_coordinator"
        ):
            coordinator_blocked.set()
            fail_now.set()

    call = _start_copy(
        backend,
        _SequenceSource([bytes([index]) for index in range(1, 12)]),  # type: ignore[arg-type]
        io.BytesIO(),
        chunk_size=1,
        checkpoint=checkpoint,
    )

    try:
        assert hasher.started.wait(_WAIT_SECONDS)
        assert coordinator_blocked.wait(_WAIT_SECONDS)
        call.wait()
    finally:
        fail_now.set()

    assert call.results == []
    assert len(call.errors) == 1
    assert isinstance(call.errors[0], HasherContractError)
    assert call.errors[0].__cause__ is failure
    _assert_workers_joined(workers)


class _BarrierFailingHasher:
    def __init__(
        self,
        barrier: threading.Barrier,
        failure: BaseException,
    ) -> None:
        self._inner = xxh3_128()
        self._barrier = barrier
        self._failure = failure
        self._updates = 0

    def update(self, chunk: bytes) -> None:
        self._updates += 1
        if self._updates == 2:
            self._barrier.wait(timeout=_WAIT_SECONDS)
            raise self._failure
        self._inner.update(chunk)

    def digest(self) -> bytes:
        return self._inner.digest()


class _BarrierFailingTarget:
    def __init__(
        self,
        barrier: threading.Barrier,
        failure: BaseException,
    ) -> None:
        self._barrier = barrier
        self._failure = failure

    def write(self, _data: object) -> int:
        self._barrier.wait(timeout=_WAIT_SECONDS)
        raise self._failure


def test_b9_simultaneous_worker_failures_raise_exactly_first_stored_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    barrier = threading.Barrier(2)
    hasher_failure = InjectedHasherFailure("simultaneous hasher failure")
    writer_failure = InjectedWriterFailure("simultaneous writer failure")
    store_results: list[tuple[BaseException, bool]] = []
    store_lock = threading.Lock()
    original_store = executor_module._FirstPipelineError.store

    def tracked_store(
        slot: object,
        error: BaseException,
    ) -> bool:
        won = original_store(slot, error)  # type: ignore[arg-type]
        with store_lock:
            store_results.append((error, won))
        return won

    monkeypatch.setattr(
        executor_module._FirstPipelineError,
        "store",
        tracked_store,
    )
    backend = _backend(
        lambda: _BarrierFailingHasher(barrier, hasher_failure)
    )

    with pytest.raises(
        (HasherContractError, InjectedWriterFailure)
    ) as caught:
        backend.copy(
            _SequenceSource([b"a", b"b", b"c"]),  # type: ignore[arg-type]
            _BarrierFailingTarget(barrier, writer_failure),  # type: ignore[arg-type]
            chunk_size=1,
            checkpoint=lambda: None,
            on_chunk=lambda _size: None,
        )

    winners = [error for error, won in store_results if won]
    losers = [error for error, won in store_results if not won]
    assert len(store_results) == 2
    assert len(winners) == 1
    assert len(losers) == 1
    assert {type(error) for error, _won in store_results} == {
        HasherContractError,
        InjectedWriterFailure,
    }
    wrapped = next(
        error
        for error, _won in store_results
        if isinstance(error, HasherContractError)
    )
    assert wrapped.__cause__ is hasher_failure
    assert caught.value is winners[0]
    assert not isinstance(caught.value, executor_module.ShutDown)
    _assert_workers_joined(workers)


def test_b9_cancel_racing_worker_error_preserves_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    worker_failure = InjectedWriterFailure("racing writer failure")
    control = Canceled()
    store_entered = threading.Event()
    release_store = threading.Event()
    original_store = executor_module._FirstPipelineError.store

    def delayed_store(
        slot: object,
        error: BaseException,
    ) -> bool:
        store_entered.set()
        release_store.wait(_WAIT_SECONDS)
        return original_store(slot, error)  # type: ignore[arg-type]

    monkeypatch.setattr(
        executor_module._FirstPipelineError,
        "store",
        delayed_store,
    )

    class FailingTarget:
        def write(self, _data: object) -> int:
            raise worker_failure

    def checkpoint() -> None:
        if store_entered.is_set():
            release_store.set()
            raise control

    try:
        with pytest.raises(Canceled) as caught:
            _backend().copy(
                io.BytesIO(b"worker-error-race"),
                FailingTarget(),  # type: ignore[arg-type]
                chunk_size=4,
                checkpoint=checkpoint,
                on_chunk=lambda _size: None,
            )
    finally:
        release_store.set()

    assert caught.value is control
    assert store_entered.is_set()
    _assert_workers_joined(workers)


def test_b9_already_stored_worker_error_does_not_outrank_ready_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    worker_failure = InjectedWriterFailure("stored writer failure")
    control = Canceled()
    stored = threading.Event()
    original_store = executor_module._FirstPipelineError.store

    def tracked_store(
        slot: object,
        error: BaseException,
    ) -> bool:
        won = original_store(slot, error)  # type: ignore[arg-type]
        stored.set()
        return won

    monkeypatch.setattr(
        executor_module._FirstPipelineError,
        "store",
        tracked_store,
    )

    class FailingTarget:
        def write(self, _data: object) -> int:
            raise worker_failure

    def checkpoint() -> None:
        if stored.is_set():
            raise control

    with pytest.raises(Canceled) as caught:
        _backend().copy(
            io.BytesIO(b"already-stored-worker-error"),
            FailingTarget(),  # type: ignore[arg-type]
            chunk_size=4,
            checkpoint=checkpoint,
            on_chunk=lambda _size: None,
        )

    assert caught.value is control
    assert stored.is_set()
    _assert_workers_joined(workers)


class _BurstSource:
    def __init__(
        self,
        chunks: list[bytes],
        release_writer: threading.Event,
        all_written: threading.Event,
    ) -> None:
        self._chunks = chunks
        self._release_writer = release_writer
        self._all_written = all_written
        self._index = 0

    def read(self, size: int) -> bytes:
        if self._index < len(self._chunks):
            chunk = self._chunks[self._index]
            self._index += 1
            assert len(chunk) <= size
            return chunk
        self._release_writer.set()
        self._all_written.wait(_WAIT_SECONDS)
        return b""


class _BurstTarget:
    def __init__(
        self,
        expected_writes: int,
        release_writer: threading.Event,
        all_written: threading.Event,
    ) -> None:
        self._expected_writes = expected_writes
        self._release_writer = release_writer
        self._all_written = all_written
        self.writes = 0

    def write(self, data: object) -> int:
        if self.writes == 0:
            if not self._release_writer.wait(_WAIT_SECONDS):
                raise TimeoutError("source never released the burst writer")
        self.writes += 1
        if self.writes == self._expected_writes:
            self._all_written.set()
        return len(data)  # type: ignore[arg-type]


def test_on_chunk_failure_aborts_and_suppresses_queued_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    chunks = [b"a", b"bb", b"ccc", b"dddd"]
    release_writer = threading.Event()
    all_written = threading.Event()
    target = _BurstTarget(len(chunks), release_writer, all_written)
    failure = InjectedPipelineFailure("progress callback failed")
    callbacks: list[int] = []
    backend = _backend()

    def on_chunk(size: int) -> None:
        callbacks.append(size)
        raise failure

    with pytest.raises(InjectedPipelineFailure) as caught:
        backend.copy(
            _BurstSource(chunks, release_writer, all_written),  # type: ignore[arg-type]
            target,  # type: ignore[arg-type]
            chunk_size=4,
            checkpoint=lambda: None,
            on_chunk=on_chunk,
        )

    assert caught.value is failure
    assert all_written.is_set()
    assert target.writes == len(chunks)
    assert callbacks == [1]
    _assert_workers_joined(workers)
    assert backend._last_metrics is not None
    assert backend._last_metrics.reserved_bytes == 0


class _AbortRaceTarget:
    def __init__(
        self,
        failure: BaseException,
        release_writer: threading.Event,
        two_written: threading.Event,
        allow_failure: threading.Event,
    ) -> None:
        self._failure = failure
        self._release_writer = release_writer
        self._two_written = two_written
        self._allow_failure = allow_failure
        self.writes = 0

    def write(self, data: object) -> int:
        if self.writes == 0:
            if not self._release_writer.wait(_WAIT_SECONDS):
                raise TimeoutError("source never released the race writer")
        self.writes += 1
        if self.writes == 2:
            self._two_written.set()
        if self.writes == 3:
            if not self._allow_failure.wait(_WAIT_SECONDS):
                raise TimeoutError("first callback never released the failure")
            raise self._failure
        return len(data)  # type: ignore[arg-type]


class _AbortRaceSource(_SequenceSource):
    def __init__(
        self,
        chunks: list[bytes],
        release_writer: threading.Event,
        two_written: threading.Event,
    ) -> None:
        super().__init__(chunks)
        self._release_writer = release_writer
        self._two_written = two_written

    def read(self, size: int) -> bytes:
        if self._index == len(self._chunks):
            self._release_writer.set()
            self._two_written.wait(_WAIT_SECONDS)
        return super().read(size)


def test_b11_worker_abort_during_drain_suppresses_remaining_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    internal_events: list[threading.Event] = []

    def tracked_event() -> threading.Event:
        event = threading.Event()
        internal_events.append(event)
        return event

    monkeypatch.setattr(executor_module, "Event", tracked_event)
    failure = InjectedPipelineFailure("writer failed during completion drain")
    release_writer = threading.Event()
    two_written = threading.Event()
    allow_failure = threading.Event()
    target = _AbortRaceTarget(
        failure,
        release_writer,
        two_written,
        allow_failure,
    )
    callbacks: list[int] = []
    backend = _backend()

    def on_chunk(size: int) -> None:
        callbacks.append(size)
        if len(callbacks) == 1:
            allow_failure.set()
            assert internal_events[0].wait(_WAIT_SECONDS)

    with pytest.raises(InjectedPipelineFailure) as caught:
        backend.copy(
            _AbortRaceSource(
                [b"a", b"bb", b"ccc", b"dddd"],
                release_writer,
                two_written,
            ),  # type: ignore[arg-type]
            target,  # type: ignore[arg-type]
            chunk_size=4,
            checkpoint=lambda: None,
            on_chunk=on_chunk,
        )

    assert caught.value is failure
    assert target.writes == 3
    assert callbacks == [1]
    assert backend._last_metrics is not None
    assert backend._last_metrics.reserved_bytes == 0


def test_checkpoint_failure_is_preserved_and_joins_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    first_hash = threading.Event()
    failure = InjectedPipelineFailure("checkpoint failed")

    class SignalingHasher(_ObservedHasher):
        def update(self, chunk: bytes) -> None:
            super().update(chunk)
            first_hash.set()

    class HashGatedSource(_SequenceSource):
        def read(self, size: int) -> bytes:
            if self._index == 1:
                first_hash.wait(_WAIT_SECONDS)
            return super().read(size)

    def checkpoint() -> None:
        if first_hash.is_set():
            raise failure

    with pytest.raises(InjectedPipelineFailure) as caught:
        _backend(SignalingHasher).copy(
            HashGatedSource([b"first", b"second"]),  # type: ignore[arg-type]
            io.BytesIO(),
            chunk_size=8,
            checkpoint=checkpoint,
            on_chunk=lambda _size: None,
        )

    assert caught.value is failure
    _assert_workers_joined(workers)


class _FinalWriteTarget(io.BytesIO):
    def __init__(
        self,
        digest_done: threading.Event,
        final_started: threading.Event,
        release_final: threading.Event,
        failure: BaseException | None,
    ) -> None:
        super().__init__()
        self._digest_done = digest_done
        self._final_started = final_started
        self._release_final = release_final
        self._failure = failure
        self._writes = 0

    def write(self, data: object) -> int:
        self._writes += 1
        if self._writes == 2:
            self._final_started.set()
            self._digest_done.wait(_WAIT_SECONDS)
            if self._failure is not None:
                raise self._failure
            if not self._release_final.wait(_WAIT_SECONDS):
                raise TimeoutError("test did not release the final write")
        return super().write(data)  # type: ignore[arg-type]


def test_b7_final_chunk_writer_failure_wins_after_digest_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    digest_done = threading.Event()
    final_started = threading.Event()
    failure = InjectedPipelineFailure("final write failed")
    target = _FinalWriteTarget(
        digest_done,
        final_started,
        threading.Event(),
        failure,
    )

    with pytest.raises(InjectedPipelineFailure) as caught:
        _backend(
            lambda: _ObservedHasher(digest_called=digest_done)
        ).copy(
            _SequenceSource([b"first", b"last"]),  # type: ignore[arg-type]
            target,
            chunk_size=8,
            checkpoint=lambda: None,
            on_chunk=lambda _size: None,
        )

    assert caught.value is failure
    assert final_started.is_set()
    assert digest_done.is_set()
    assert target.getvalue() == b"first"
    _assert_workers_joined(workers)


def test_b7_return_waits_for_slow_final_write_after_digest_finalization() -> None:
    digest_done = threading.Event()
    final_started = threading.Event()
    release_final = threading.Event()
    target = _FinalWriteTarget(
        digest_done,
        final_started,
        release_final,
        None,
    )
    call = _start_copy(
        _backend(lambda: _ObservedHasher(digest_called=digest_done)),
        _SequenceSource([b"first", b"last"]),  # type: ignore[arg-type]
        target,
        chunk_size=8,
    )

    try:
        assert final_started.wait(_WAIT_SECONDS)
        assert digest_done.wait(_WAIT_SECONDS)
        assert not call.done.is_set()
        assert call.results == []
    finally:
        release_final.set()

    call.wait()
    assert call.errors == []
    assert call.results[0].size == len(b"firstlast")
    assert target.getvalue() == b"firstlast"


class _PerChunkGatedSource:
    def __init__(
        self,
        hashed: list[threading.Event],
        total_chunks: int,
    ) -> None:
        self._hashed = hashed
        self._total_chunks = total_chunks
        self.reads = 0

    def read(self, _size: int) -> bytes:
        if self.reads == self._total_chunks:
            return b""
        if self.reads > 0:
            self._hashed[self.reads - 1].wait(_WAIT_SECONDS)
        self.reads += 1
        return bytes([self.reads])


class _CancelingHasher:
    def __init__(
        self,
        hashed: list[threading.Event],
        cancel_after: int,
        cancel_requested: threading.Event,
    ) -> None:
        self._inner = xxh3_128()
        self._hashed = hashed
        self._cancel_after = cancel_after
        self._cancel_requested = cancel_requested
        self._updates = 0

    def update(self, chunk: bytes) -> None:
        self._inner.update(chunk)
        self._updates += 1
        self._hashed[self._updates - 1].set()
        if self._updates == self._cancel_after:
            self._cancel_requested.set()

    def digest(self) -> bytes:
        return self._inner.digest()


def test_b10_cancel_after_chunk_k_admits_at_most_one_more_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    cancel_after = 4
    total_chunks = 64
    hashed = [threading.Event() for _ in range(total_chunks)]
    cancel_requested = threading.Event()
    source = _PerChunkGatedSource(hashed, total_chunks)
    control = Canceled()

    def checkpoint() -> None:
        if cancel_requested.is_set():
            raise control

    with pytest.raises(Canceled) as caught:
        _backend(
            lambda: _CancelingHasher(
                hashed,
                cancel_after,
                cancel_requested,
            )
        ).copy(
            source,  # type: ignore[arg-type]
            io.BytesIO(),
            chunk_size=1,
            checkpoint=checkpoint,
            on_chunk=lambda _size: None,
        )

    assert caught.value is control
    assert cancel_requested.is_set()
    assert cancel_after <= source.reads <= cancel_after + 1
    _assert_workers_joined(workers)


class _ObservedGetQueue(ThreadQueue[bytes | object]):
    def __init__(
        self,
        maxsize: int,
        get_waiting: threading.Event,
    ) -> None:
        super().__init__(maxsize=maxsize)
        self._get_waiting = get_waiting

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> bytes | object:
        self._get_waiting.set()
        return super().get(block=block, timeout=timeout)


def test_immediate_shutdown_releases_workers_waiting_on_both_empty_handoffs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "_PIPELINE_POLL_SECONDS", 1.0)
    hash_waiting = threading.Event()
    write_waiting = threading.Event()
    waiting = [hash_waiting, write_waiting]

    def observed_queue(maxsize: int = 0) -> _ObservedGetQueue:
        return _ObservedGetQueue(maxsize, waiting.pop(0))

    monkeypatch.setattr(executor_module, "Queue", observed_queue)
    workers = _capture_worker_threads(monkeypatch)
    control = Canceled()

    def checkpoint() -> None:
        assert hash_waiting.wait(_WAIT_SECONDS)
        assert write_waiting.wait(_WAIT_SECONDS)
        raise control

    started = time.perf_counter()
    with pytest.raises(Canceled) as caught:
        _backend().copy(
            io.BytesIO(b"must-not-be-read"),
            io.BytesIO(),
            chunk_size=4,
            checkpoint=checkpoint,
            on_chunk=lambda _size: None,
        )

    assert caught.value is control
    assert time.perf_counter() - started < 0.75
    _assert_workers_joined(workers)


class _ThirdUpdateSignalingHasher(_ObservedHasher):
    def __init__(self, third_update: threading.Event) -> None:
        super().__init__()
        self._third_update = third_update
        self._updates_seen = 0

    def update(self, chunk: bytes) -> None:
        self._updates_seen += 1
        super().update(chunk)
        if self._updates_seen == 3:
            self._third_update.set()


def test_immediate_shutdown_releases_hasher_blocked_on_full_write_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "_PIPELINE_QUEUE_ITEMS", 1)
    monkeypatch.setattr(executor_module, "_PIPELINE_POLL_SECONDS", 1.0)
    queues: list[ThreadQueue[bytes | object]] = []

    def tracked_queue(maxsize: int = 0) -> ThreadQueue[bytes | object]:
        queue: ThreadQueue[bytes | object] = ThreadQueue(maxsize=maxsize)
        queues.append(queue)
        return queue

    monkeypatch.setattr(executor_module, "Queue", tracked_queue)
    internal_events: list[threading.Event] = []

    def tracked_event() -> threading.Event:
        event = threading.Event()
        internal_events.append(event)
        return event

    monkeypatch.setattr(executor_module, "Event", tracked_event)
    workers = _capture_worker_threads(monkeypatch)
    writer_started = threading.Event()
    release_writer = threading.Event()
    third_update = threading.Event()
    target = _BlockingFirstWriteTarget(writer_started, release_writer)
    control = Canceled()
    release_helpers: list[threading.Thread] = []
    handoff_blocked = threading.Event()
    shutdown_released_hasher = threading.Event()

    def checkpoint() -> None:
        if (
            third_update.is_set()
            and len(queues) == 2
            and queues[1].full()
        ):
            handoff_blocked.set()

            def release_after_abort() -> None:
                internal_events[0].wait(_WAIT_SECONDS)
                if _wait_until(
                    lambda: bool(workers) and not workers[0].is_alive(),
                    timeout=0.5,
                ):
                    shutdown_released_hasher.set()
                release_writer.set()

            helper = _REAL_THREAD(
                target=release_after_abort,
                name="pipeline-test-abort-release",
                daemon=True,
            )
            release_helpers.append(helper)
            helper.start()
            raise control

    try:
        with pytest.raises(Canceled) as caught:
            _backend(
                lambda: _ThirdUpdateSignalingHasher(third_update)
            ).copy(
                _SequenceSource(
                    [bytes([index]) for index in range(1, 20)]
                ),  # type: ignore[arg-type]
                target,
                chunk_size=1,
                checkpoint=checkpoint,
                on_chunk=lambda _size: None,
            )
    finally:
        release_writer.set()

    assert caught.value is control
    assert writer_started.is_set()
    assert handoff_blocked.is_set()
    assert shutdown_released_hasher.is_set()
    assert len(release_helpers) == 1
    release_helpers[0].join(_WAIT_SECONDS)
    assert not release_helpers[0].is_alive()
    _assert_workers_joined(workers)


class _ControlStageSource:
    def __init__(
        self,
        selected_stage: threading.Event,
        reader_stage: threading.Event,
    ) -> None:
        self._selected_stage = selected_stage
        self._reader_stage = reader_stage
        self.reads = 0

    def read(self, _size: int) -> bytes:
        self.reads += 1
        if self.reads == 1:
            self._reader_stage.set()
            return b"first"
        if self.reads == 2:
            self._selected_stage.wait(_WAIT_SECONDS)
            return b"second"
        return b""


class _ControlStageHasher(_ObservedHasher):
    def __init__(self, stage: threading.Event) -> None:
        super().__init__()
        self._stage = stage

    def update(self, chunk: bytes) -> None:
        super().update(chunk)
        self._stage.set()


class _ControlStageTarget(io.BytesIO):
    def __init__(self, stage: threading.Event) -> None:
        super().__init__()
        self._stage = stage

    def write(self, data: object) -> int:
        written = super().write(data)  # type: ignore[arg-type]
        self._stage.set()
        return written


@pytest.mark.parametrize(
    "control_type",
    [
        pytest.param(Canceled, id="cancel"),
        pytest.param(PauseRequested, id="pause"),
    ],
)
@pytest.mark.parametrize("stage_name", ["reader", "hasher", "writer"])
def test_control_exception_at_each_stage_is_preserved_and_tears_down(
    monkeypatch: pytest.MonkeyPatch,
    control_type: type[Exception],
    stage_name: str,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    reader_stage = threading.Event()
    hasher_stage = threading.Event()
    writer_stage = threading.Event()
    stages = {
        "reader": reader_stage,
        "hasher": hasher_stage,
        "writer": writer_stage,
    }
    selected_stage = stages[stage_name]
    source = _ControlStageSource(selected_stage, reader_stage)
    target = _ControlStageTarget(writer_stage)
    control = control_type()
    callbacks: list[int] = []

    def checkpoint() -> None:
        if selected_stage.is_set():
            raise control

    with pytest.raises(control_type) as caught:
        _backend(lambda: _ControlStageHasher(hasher_stage)).copy(
            source,  # type: ignore[arg-type]
            target,
            chunk_size=8,
            checkpoint=checkpoint,
            on_chunk=callbacks.append,
        )

    assert caught.value is control
    assert source.reads <= 2
    callbacks_at_return = tuple(callbacks)
    _assert_workers_joined(workers)
    assert tuple(callbacks) == callbacks_at_return


class _StatelessPollingCheckpoint:
    def __init__(
        self,
        state: threading.Event,
        *,
        polls_per_call: int,
        control: BaseException | None = None,
    ) -> None:
        self._state = state
        self._polls_per_call = polls_per_call
        self._control = control

    def __call__(self) -> None:
        for _ in range(self._polls_per_call):
            if self._state.is_set() and self._control is not None:
                raise self._control


def _run_with_poll_frequency(
    polls_per_call: int,
) -> tuple[CopyDigest, bytes, list[int]]:
    data = b"stateless-checkpoint" * 5
    target = io.BytesIO()
    progress: list[int] = []
    checkpoint = _StatelessPollingCheckpoint(
        threading.Event(),
        polls_per_call=polls_per_call,
    )
    result = _backend().copy(
        io.BytesIO(data),
        target,
        chunk_size=7,
        checkpoint=checkpoint,
        on_chunk=progress.append,
    )
    return result, target.getvalue(), progress


def _cancel_with_poll_frequency(
    polls_per_call: int,
) -> tuple[BaseException, int]:
    cancel_after = 4
    total_chunks = 32
    hashed = [threading.Event() for _ in range(total_chunks)]
    cancel_requested = threading.Event()
    source = _PerChunkGatedSource(hashed, total_chunks)
    control = Canceled()
    checkpoint = _StatelessPollingCheckpoint(
        cancel_requested,
        polls_per_call=polls_per_call,
        control=control,
    )

    try:
        _backend(
            lambda: _CancelingHasher(
                hashed,
                cancel_after,
                cancel_requested,
            )
        ).copy(
            source,  # type: ignore[arg-type]
            io.BytesIO(),
            chunk_size=1,
            checkpoint=checkpoint,
            on_chunk=lambda _size: None,
        )
    except BaseException as error:
        return error, source.reads
    raise AssertionError("canceling copy unexpectedly returned")


def test_xv20_doubled_stateless_polling_preserves_copy_and_cancel_outcomes() -> None:
    once = _run_with_poll_frequency(1)
    doubled = _run_with_poll_frequency(2)

    assert doubled == once
    assert once[0].digest == _serial_digest(once[1])
    assert sum(once[2]) == once[0].size

    once_cancel, once_reads = _cancel_with_poll_frequency(1)
    doubled_cancel, doubled_reads = _cancel_with_poll_frequency(2)

    assert isinstance(once_cancel, Canceled)
    assert isinstance(doubled_cancel, Canceled)
    assert once_reads == doubled_reads
    assert once_reads <= 5


def test_b8_repeated_short_final_chunks_release_the_entire_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workers = _capture_worker_threads(monkeypatch)
    backend = _backend()
    chunk_size = 1024
    data = b"x" * (2 * chunk_size + 17)

    for _ in range(5):
        target = io.BytesIO()
        progress: list[int] = []
        result = backend.copy(
            io.BytesIO(data),
            target,
            chunk_size=chunk_size,
            checkpoint=lambda: None,
            on_chunk=progress.append,
        )

        assert target.getvalue() == data
        assert progress == [chunk_size, chunk_size, 17]
        assert result.digest == _serial_digest(data)
        assert result.size == len(data)
        metrics = backend._last_metrics
        assert metrics is not None
        assert metrics.reserved_bytes == 0
        assert metrics.payload_high_water <= executor_module._PIPELINE_BYTE_BUDGET

    _assert_workers_joined(workers, copies=5)
