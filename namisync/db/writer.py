"""Serialized explicit SQLite transactions with bounded lock retry."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from .connections import DEFAULT_BUSY_TIMEOUT_MS


T = TypeVar("T")


class RecordingError(RuntimeError):
    """A ledger/history transaction could not be recorded."""


class RecordingBusyError(RecordingError):
    """Cross-process SQLite contention outlasted the configured bound."""


class TokenConflictError(RecordingError):
    """An idempotency token was reused for a different immutable payload."""


def _is_busy(error: sqlite3.OperationalError) -> bool:
    message = str(error).lower()
    return "locked" in message or "busy" in message


class SerializedWriter:
    """One in-process owner for a writable SQLite connection."""

    def __init__(
        self,
        path: str | Path,
        connect: Callable[..., sqlite3.Connection],
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        retry_timeout_seconds: float = 10.0,
        retry_interval_seconds: float = 0.025,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retry_timeout_seconds < 0 or retry_interval_seconds < 0:
            raise ValueError("retry bounds cannot be negative")
        self.path = Path(path).resolve()
        self._connection = connect(self.path, busy_timeout_ms=busy_timeout_ms)
        self._retry_timeout = retry_timeout_seconds
        self._retry_interval = retry_interval_seconds
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.RLock()
        self._closed = False

    def transact(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        deadline = self._monotonic() + self._retry_timeout
        with self._lock:
            self._require_open()
            while True:
                try:
                    self._connection.execute("BEGIN IMMEDIATE")
                    result = operation(self._connection)
                    self._connection.commit()
                    return result
                except sqlite3.OperationalError as error:
                    self._connection.rollback()
                    if not _is_busy(error):
                        raise RecordingError(str(error)) from error
                    if self._monotonic() >= deadline:
                        raise RecordingBusyError(
                            f"database remained busy for {self._retry_timeout:.3f}s"
                        ) from error
                    self._sleep(self._retry_interval)
                except sqlite3.Error as error:
                    self._connection.rollback()
                    raise RecordingError(str(error)) from error
                except BaseException:
                    self._connection.rollback()
                    raise

    def flush(self) -> None:
        """M0 commands commit eagerly; retaining this boundary freezes the API."""

        with self._lock:
            self._require_open()
            self._connection.execute("SELECT 1").fetchone()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise RecordingError("database writer is closed")

    def __enter__(self) -> SerializedWriter:
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
