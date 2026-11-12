"""M0 process-local dispatcher session storage."""

from __future__ import annotations

from threading import RLock

from namisync.core.session import SessionId, StoredSessionRecord


class InMemorySessionStore:
    """Retain session metadata without claiming restart durability.

    ``load_all`` deliberately returns no records. Reusing this object is not a
    simulated restart contract. Durable metadata alone cannot recover the
    process-local workflow continuation.
    """

    def __init__(self) -> None:
        self._records: dict[SessionId, StoredSessionRecord] = {}
        self._lock = RLock()

    def put(self, record: StoredSessionRecord) -> None:
        if type(record) is not StoredSessionRecord:
            raise TypeError("session store requires exact StoredSessionRecord values")
        with self._lock:
            self._records[record.session_id] = record

    def load_all(self) -> tuple[StoredSessionRecord, ...]:
        return ()

    def drop(self, session_id: SessionId) -> None:
        with self._lock:
            self._records.pop(session_id, None)

    def snapshot(self) -> tuple[StoredSessionRecord, ...]:
        """Testing/diagnostic view of the current process-local table."""

        with self._lock:
            return tuple(
                sorted(self._records.values(), key=lambda record: record.admission_order)
            )
