"""M0 process-local dispatcher session storage."""

from __future__ import annotations

from threading import RLock

from namisync.core.session import SessionId, SessionRecord


class InMemorySessionStore:
    """Retain live records without claiming restart durability.

    ``load_all`` deliberately returns no records. Reusing this object is not a
    simulated restart contract; M2 supplies a durable implementation behind the
    same protocol.
    """

    def __init__(self) -> None:
        self._records: dict[SessionId, SessionRecord] = {}
        self._lock = RLock()

    def put(self, record: SessionRecord) -> None:
        with self._lock:
            self._records[record.session_id] = record

    def load_all(self) -> tuple[SessionRecord, ...]:
        return ()

    def drop(self, session_id: SessionId) -> None:
        with self._lock:
            self._records.pop(session_id, None)

    def snapshot(self) -> tuple[SessionRecord, ...]:
        """Testing/diagnostic view of the current process-local table."""

        with self._lock:
            return tuple(
                sorted(self._records.values(), key=lambda record: record.admission_order)
            )
