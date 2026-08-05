from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from namisync.db.writer import RecordingBusyError, SerializedWriter


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _BusyConnection:
    def __init__(self, clock: _FakeClock) -> None:
        self._clock = clock
        self.begin_times: list[float] = []
        self.busy_timeouts: list[int] = []
        self.closed = False

    def execute(self, statement: str):
        if statement.startswith("PRAGMA busy_timeout = "):
            self.busy_timeouts.append(int(statement.rsplit(" ", 1)[-1]))
            return self
        assert statement == "BEGIN IMMEDIATE"
        self.begin_times.append(self._clock.now)
        raise sqlite3.OperationalError("database is locked")

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def test_writer_caps_busy_wait_and_sleep_to_one_retry_deadline(
    tmp_path: Path,
) -> None:
    clock = _FakeClock()
    connection = _BusyConnection(clock)
    writer = SerializedWriter(
        tmp_path / "ledger.db",
        lambda path, *, busy_timeout_ms: connection,
        busy_timeout_ms=5_000,
        retry_timeout_seconds=0.1,
        retry_interval_seconds=1.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    with pytest.raises(RecordingBusyError):
        writer.transact(lambda database: None)

    assert connection.begin_times == [0.0]
    assert connection.busy_timeouts == [100]
    assert clock.sleeps == [pytest.approx(0.1)]
    writer.close()
    assert connection.closed


def test_writer_applies_retry_deadline_to_in_process_lock_wait(
    tmp_path: Path,
) -> None:
    class UnavailableLock:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def acquire(self, *, timeout: float) -> bool:
            self.timeouts.append(timeout)
            return False

        def release(self) -> None:
            raise AssertionError("an unacquired lock cannot be released")

    clock_values = iter((10.0, 10.025))
    connection = _BusyConnection(_FakeClock())
    writer = SerializedWriter(
        tmp_path / "ledger.db",
        lambda path, *, busy_timeout_ms: connection,
        retry_timeout_seconds=0.1,
        monotonic=lambda: next(clock_values),
    )
    lock = UnavailableLock()
    original_lock = writer._lock
    writer._lock = lock
    try:
        with pytest.raises(RecordingBusyError):
            writer.transact(lambda database: None)

        assert lock.timeouts == [pytest.approx(0.075)]
        assert connection.begin_times == []
    finally:
        writer._lock = original_lock
        writer.close()


def test_writer_does_not_begin_after_positive_budget_expires_in_lock_wait(
    tmp_path: Path,
) -> None:
    class DeadlineLock:
        def __init__(self, clock: _FakeClock) -> None:
            self._clock = clock
            self.released = False

        def acquire(self, *, timeout: float) -> bool:
            assert timeout == pytest.approx(0.1)
            self._clock.now += timeout
            return True

        def release(self) -> None:
            self.released = True

    clock = _FakeClock()
    connection = _BusyConnection(clock)
    writer = SerializedWriter(
        tmp_path / "ledger.db",
        lambda path, *, busy_timeout_ms: connection,
        retry_timeout_seconds=0.1,
        monotonic=clock.monotonic,
    )
    lock = DeadlineLock(clock)
    original_lock = writer._lock
    writer._lock = lock
    try:
        with pytest.raises(RecordingBusyError):
            writer.transact(lambda database: None)

        assert lock.released
        assert connection.begin_times == []
    finally:
        writer._lock = original_lock
        writer.close()


def test_zero_retry_budget_still_allows_one_immediate_attempt(
    tmp_path: Path,
) -> None:
    writer = SerializedWriter(
        tmp_path / "ledger.db",
        lambda path, *, busy_timeout_ms: sqlite3.connect(
            path,
            isolation_level=None,
        ),
        retry_timeout_seconds=0,
    )
    try:
        assert writer.transact(
            lambda database: database.execute("SELECT 1").fetchone()[0]
        ) == 1
    finally:
        writer.close()
