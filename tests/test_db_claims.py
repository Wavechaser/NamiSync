from __future__ import annotations

from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
from queue import Empty, Queue
import signal
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
from typing import Iterator

import pytest

import namisync.db.claims as claims_module
from namisync.core.events import CORE_EVENT_SCHEMA_VERSION, Envelope, StateChanged
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.claims import (
    DatabaseClaimRefused,
    DatabaseInUse,
    DatabaseMaintenanceActive,
    acquire_database_claim,
    claim_path,
    hold_maintenance_claims,
)
from namisync.db.contracts import (
    DatabaseConnectionOwner,
    probe_database_file_contract,
)
from namisync.db.history import HistoryContext, HistoryRepository, HistoryStore
from namisync.db.recorder import LedgerRecorder
from namisync.db.repositories import LedgerRepository
from namisync.db.schema import DatabaseAdmissionError, initialize_history, initialize_ledger
from namisync.db.writer import RecordingError, TokenConflictError
from namisync.workflows.database_pair import (
    DatabasePairState,
    initialize_database_pair,
    validate_database_pair,
)

from _db_fixtures import FakeClock, NOW


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows LockFileEx claims")

_PROJECT_ROOT = Path(__file__).parents[1]
_WAIT_SECONDS = 10.0
_HOLDER = """
import sys
from namisync.db.claims import DatabaseClaimRefused, acquire_database_claim
try:
    claim = acquire_database_claim(sys.argv[1], exclusive=sys.argv[2] == "exclusive")
except DatabaseClaimRefused as error:
    print("refused " + type(error).__name__, flush=True)
    sys.exit(0)
print("acquired", flush=True)
sys.stdin.readline()
claim.release()
print("released", flush=True)
sys.stdin.read()
"""
_SLEEPING_HOLDER = """
import sys, time
from namisync.db.claims import acquire_database_claim
claim = acquire_database_claim(sys.argv[1], exclusive=False)
print("acquired", flush=True)
time.sleep(60)
"""
_SPAWNING_HOLDER = """
import subprocess, sys
from namisync.db.claims import acquire_database_claim
claim = acquire_database_claim(sys.argv[1], exclusive=True)
child = subprocess.Popen(
    [sys.executable, "-c", sys.argv[3], sys.argv[2]],
    stdin=subprocess.DEVNULL, close_fds=False,
)
print(f"grandchild {child.pid}", flush=True)
sys.stdin.read()
"""


class _Process:
    """A claim-holding child with pipe-synchronized, bounded reads."""

    def __init__(self, *arguments: str) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-c", *arguments],
            cwd=_PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._lines: Queue[str] = Queue()
        Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line.strip())

    def read(self) -> str:
        try:
            return self._lines.get(timeout=_WAIT_SECONDS)
        except Empty:
            pytest.fail("claim child did not answer within the bound")

    def release(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write("release\n")
        self.process.stdin.flush()
        assert self.read() == "released"

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(_WAIT_SECONDS)


@contextmanager
def _holder(main: Path, mode: str, *, expect: str = "acquired") -> Iterator[_Process]:
    child = _Process(_HOLDER, str(main), mode)
    try:
        assert child.read() == expect
        yield child
    finally:
        child.kill()


def _eventually_exclusive(main: Path) -> None:
    # Windows may unlock a dead holder's range slightly after the process exits.
    deadline = monotonic() + _WAIT_SECONDS
    while True:
        try:
            acquire_database_claim(main, exclusive=True).release()
            return
        except DatabaseInUse:
            if monotonic() >= deadline:
                raise
            sleep(0.02)


def _record(session_id: str = "1" * 32) -> SessionRecord:
    return SessionRecord(
        SessionId(session_id), "sync", SessionState.PENDING, (), b"opaque", True, 1, NOW,
    )


def _paused(record: SessionRecord) -> Envelope:
    # A pause is a flush barrier, so the observer writes its run row here.
    return Envelope(
        record.session_id, 1, NOW, CORE_EVENT_SCHEMA_VERSION,
        StateChanged(SessionState.PAUSED),
    )


def _sqlite_artifacts(main: Path) -> list[Path]:
    return [
        Path(f"{main}{suffix}") for suffix in ("", "-wal", "-shm", "-journal")
        if os.path.lexists(f"{main}{suffix}")
    ]


def test_refusals_are_typed_database_admission_errors() -> None:
    assert issubclass(DatabaseClaimRefused, DatabaseAdmissionError)
    assert issubclass(DatabaseMaintenanceActive, DatabaseClaimRefused)
    assert issubclass(DatabaseInUse, DatabaseClaimRefused)
    assert not issubclass(DatabaseMaintenanceActive, DatabaseInUse)
    assert not issubclass(DatabaseInUse, DatabaseMaintenanceActive)


def test_two_processes_hold_shared_claims_together(tmp_path: Path) -> None:
    main = tmp_path / "ledger.db"
    with _holder(main, "shared"), _holder(main, "shared"):
        with pytest.raises(DatabaseInUse, match="in use by NamiSync work") as refused:
            acquire_database_claim(main, exclusive=True)
        assert refused.value.path == main
    assert claim_path(main).is_file()
    assert _sqlite_artifacts(main) == []


def test_exclusive_is_refused_under_a_shared_holder_and_granted_after_release(
    tmp_path: Path,
) -> None:
    main = tmp_path / "ledger.db"
    with _holder(main, "shared") as holder:
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(main, exclusive=True)
        holder.release()
        claim = acquire_database_claim(main, exclusive=True)
        try:
            assert claim.exclusive
        finally:
            claim.release()


def test_shared_is_refused_without_waiting_under_an_exclusive_holder(tmp_path: Path) -> None:
    main = tmp_path / "history.db"
    with _holder(main, "exclusive"):
        # A waiting acquisition would block forever; bound it so a regression
        # fails instead of hanging the suite.
        outcome: list[BaseException] = []

        def acquire() -> None:
            try:
                acquire_database_claim(main, exclusive=False).release()
            except BaseException as error:
                outcome.append(error)

        attempt = Thread(target=acquire, daemon=True)
        attempt.start()
        attempt.join(2.0)
        assert not attempt.is_alive(), "a shared claim waited for the exclusive holder"
        assert len(outcome) == 1 and isinstance(outcome[0], DatabaseMaintenanceActive)
        assert "refused, not queued" in str(outcome[0])
        with _holder(main, "shared", expect="refused DatabaseMaintenanceActive"):
            pass
        with _holder(main, "exclusive", expect="refused DatabaseInUse"):
            pass


@pytest.mark.parametrize("mode", ["shared", "exclusive"])
def test_a_killed_holder_releases_its_claim(tmp_path: Path, mode: str) -> None:
    main = tmp_path / "ledger.db"
    with _holder(main, mode) as holder:
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(main, exclusive=True)
        holder.kill()
        _eventually_exclusive(main)


def test_a_claim_handle_is_not_inheritable(tmp_path: Path) -> None:
    with acquire_database_claim(tmp_path / "ledger.db", exclusive=True) as claim:
        assert not os.get_inheritable(claim._file.fileno())


def test_a_claim_dies_with_its_holder_while_the_holders_child_lives(
    tmp_path: Path,
) -> None:
    held, witness = tmp_path / "ledger.db", tmp_path / "witness.db"
    parent = _Process(_SPAWNING_HOLDER, str(held), str(witness), _SLEEPING_HOLDER)
    grandchild_pid: int | None = None
    try:
        first, second = sorted((parent.read(), parent.read()))
        assert second.startswith("grandchild ")
        assert first == "acquired"
        grandchild_pid = int(second.split()[1])
        parent.kill()
        # The grandchild, spawned with handle inheritance enabled, is proven alive
        # by its witness claim, yet the dead holder's claim is free. Windows drops
        # a process's range lock when that process's handle closes even if an
        # inherited duplicate stays open, so this does not detect inheritance;
        # test_a_claim_handle_is_not_inheritable does.
        _eventually_exclusive(held)
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(witness, exclusive=True)
    finally:
        parent.kill()
        if grandchild_pid is not None:
            try:
                os.kill(grandchild_pid, signal.SIGTERM)
            except OSError:
                pass


def test_two_claims_in_one_process_conflict_like_two_processes(tmp_path: Path) -> None:
    main = tmp_path / "ledger.db"
    first = acquire_database_claim(main, exclusive=False)
    second = acquire_database_claim(main, exclusive=False)
    with pytest.raises(DatabaseInUse):
        acquire_database_claim(main, exclusive=True)
    first.release()
    with pytest.raises(DatabaseInUse):
        acquire_database_claim(main, exclusive=True)
    second.release()
    second.release()
    with acquire_database_claim(main, exclusive=True):
        with pytest.raises(DatabaseMaintenanceActive):
            acquire_database_claim(main, exclusive=False)
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(main, exclusive=True)
    acquire_database_claim(main, exclusive=False).release()


def test_recorder_holds_its_claim_exactly_for_its_connection_life(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.db"
    recorder = LedgerRecorder(ledger, clock=FakeClock())
    with pytest.raises(DatabaseInUse):
        acquire_database_claim(ledger, exclusive=True)
    recorder.close()
    acquire_database_claim(ledger, exclusive=True).release()
    with LedgerRecorder(ledger, clock=FakeClock()):
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(ledger, exclusive=True)
    acquire_database_claim(ledger, exclusive=True).release()

    owner = DatabaseConnectionOwner(ledger, history=False)
    try:
        with LedgerRecorder(ledger, clock=FakeClock(), database=owner):
            with pytest.raises(DatabaseInUse):
                acquire_database_claim(ledger, exclusive=True)
        acquire_database_claim(ledger, exclusive=True).release()
    finally:
        owner.close()


def test_recorder_construction_failures_release_or_never_take_the_claim(
    tmp_path: Path,
) -> None:
    ledger = initialize_ledger(tmp_path / "ledger.db")
    # The retained traceback still references the half-built recorder, so only
    # an explicit release frees the claim here.
    with pytest.raises(ValueError, match="retry bounds") as failed:
        LedgerRecorder(ledger, clock=FakeClock(), retry_timeout_seconds=-1)
    acquire_database_claim(ledger, exclusive=True).release()
    del failed

    with _holder(ledger, "exclusive"):
        with pytest.raises(DatabaseMaintenanceActive, match="maintenance is in progress"):
            LedgerRecorder(ledger, clock=FakeClock())
    _eventually_exclusive(ledger)
    with LedgerRecorder(ledger, clock=FakeClock()):
        pass


def test_history_observer_holds_the_claim_from_construction_to_close(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        acquire_database_claim(path, exclusive=True).release()
        observer = store.observer(record, HistoryContext("run-claim", "host-1"))
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(path, exclusive=True)
        observer.on_event(_paused(record))
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(path, exclusive=True)
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(path, exclusive=True)
        observer.close()
        acquire_database_claim(path, exclusive=True).release()

        second = store.observer(_record("2" * 32), HistoryContext("run-second", "host-1"))
        with pytest.raises(DatabaseInUse):
            acquire_database_claim(path, exclusive=True)
        second.close()
        acquire_database_claim(path, exclusive=True).release()

        with _holder(path, "exclusive"):
            with pytest.raises(DatabaseMaintenanceActive):
                store.observer(_record("3" * 32), HistoryContext("run-refused", "host-1"))
        _eventually_exclusive(path)

    with HistoryRepository(path) as repository:
        assert repository.get_summary("run-claim").current_state is SessionState.COMPLETED
        with pytest.raises(KeyError):
            repository.get_summary("run-refused")


def test_history_observer_construction_failure_releases_its_claim(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    with HistoryStore(path, clock=FakeClock()) as store:
        record = _record()
        first = store.observer(record, HistoryContext("run-token", "host-1"))
        first.on_event(_paused(record))
        first.close()
        with pytest.raises(TokenConflictError, match="context changed") as failed:
            store.observer(_record("2" * 32), HistoryContext("run-token", "host-2"))
        acquire_database_claim(path, exclusive=True).release()
        del failed


@pytest.mark.parametrize("history", [False, True])
def test_schema_creation_is_refused_under_any_claim_and_leaves_no_database(
    tmp_path: Path, history: bool,
) -> None:
    main = tmp_path / ("history.db" if history else "ledger.db")
    initialize = initialize_history if history else initialize_ledger
    for mode in ("shared", "exclusive"):
        with _holder(main, mode):
            with pytest.raises(DatabaseInUse):
                initialize(main)
            assert _sqlite_artifacts(main) == []
    _eventually_exclusive(main)
    assert initialize(main) == main
    acquire_database_claim(main, exclusive=True).release()


def test_pair_creation_under_a_claim_retracts_its_reservations(tmp_path: Path) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    with _holder(history, "shared"):
        # Raised as itself once cleanup completed, so admission can report it.
        with pytest.raises(DatabaseInUse):
            initialize_database_pair(ledger, history)
        assert _sqlite_artifacts(ledger) == _sqlite_artifacts(history) == []
    assert validate_database_pair(ledger, history).state is DatabasePairState.FRESH


def test_maintenance_claims_take_both_databases_ledger_first(tmp_path: Path) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    with hold_maintenance_claims(ledger, history):
        for main in (ledger, history):
            with pytest.raises(DatabaseMaintenanceActive):
                acquire_database_claim(main, exclusive=False)
    for main in (ledger, history):
        acquire_database_claim(main, exclusive=False).release()

    with _holder(history, "shared"):
        with pytest.raises(DatabaseInUse) as refused:
            with hold_maintenance_claims(ledger, history):
                pytest.fail("maintenance ran under a History writer")
        acquire_database_claim(ledger, exclusive=True).release()
        del refused

    with _holder(ledger, "shared"):
        with pytest.raises(DatabaseInUse):
            with hold_maintenance_claims(ledger, history):
                pytest.fail("maintenance ran under a ledger writer")
        acquire_database_claim(history, exclusive=True).release()


def test_read_only_classification_never_creates_a_claim_file(tmp_path: Path) -> None:
    ledger, history = tmp_path / "ledger.db", tmp_path / "history.db"
    initialize_database_pair(ledger, history)
    for main in (ledger, history):
        claim_path(main).unlink()

    assert validate_database_pair(ledger, history).state is DatabasePairState.READY
    probe_database_file_contract(ledger, history=False)
    probe_database_file_contract(history, history=True)
    owners = (
        DatabaseConnectionOwner(ledger, history=False),
        DatabaseConnectionOwner(history, history=True),
    )
    try:
        assert validate_database_pair(
            ledger, history, ledger_database=owners[0], history_database=owners[1],
        ).state is DatabasePairState.READY
        owners[0].open_reader(ledger).close()
    finally:
        for owner in owners:
            owner.close()
    with LedgerRepository(ledger) as repository:
        repository.get_recent_sync_activity()
    with HistoryRepository(history) as repository:
        repository.list_summaries(1)

    assert not claim_path(ledger).exists()
    assert not claim_path(history).exists()


def test_claims_resolve_every_spelling_of_one_main_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with acquire_database_claim("ledger.db", exclusive=False) as claim:
        assert claim.path == tmp_path / "ledger.db.claim"
        with pytest.raises(DatabaseInUse) as refused:
            acquire_database_claim(f"{tmp_path}/ledger.db".replace("\\", "/"), exclusive=True)
        assert refused.value.path == tmp_path / "ledger.db"


@pytest.mark.parametrize("shape", ["claim-directory", "missing-parent"])
def test_an_unopenable_claim_file_is_an_os_error_not_a_refusal(
    tmp_path: Path, shape: str,
) -> None:
    main = tmp_path / ("ledger.db" if shape == "claim-directory" else "absent/ledger.db")
    if shape == "claim-directory":
        claim_path(main).mkdir()
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    for exclusive in (False, True):
        with pytest.raises(OSError) as raised:
            acquire_database_claim(main, exclusive=exclusive)
        assert not isinstance(raised.value, DatabaseClaimRefused)
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_a_lock_failure_other_than_contention_is_not_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main = tmp_path / "ledger.db"
    real = claims_module._bindings()

    class FailingLock:
        UnlockFileEx = real.UnlockFileEx

        @staticmethod
        def LockFileEx(*_arguments) -> int:
            ctypes.set_last_error(5)  # ERROR_ACCESS_DENIED
            return 0

    monkeypatch.setattr(claims_module, "_kernel32", FailingLock())
    for exclusive in (False, True):
        with pytest.raises(OSError) as raised:
            acquire_database_claim(main, exclusive=exclusive)
        assert not isinstance(raised.value, DatabaseClaimRefused)
        assert raised.value.winerror == 5
    monkeypatch.setattr(claims_module, "_kernel32", real)
    acquire_database_claim(main, exclusive=True).release()


def test_a_recorder_keeps_its_claim_until_its_writer_really_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = tmp_path / "ledger.db"
    recorder = LedgerRecorder(ledger, clock=FakeClock())
    writer_close = recorder._writer.close
    failures = [OSError("writer close failed")]

    def close_once_failing() -> None:
        if failures:
            raise failures.pop()
        writer_close()

    monkeypatch.setattr(recorder._writer, "close", close_once_failing)
    with pytest.raises(OSError, match="writer close failed"):
        recorder.close()
    with pytest.raises(DatabaseInUse):
        acquire_database_claim(ledger, exclusive=True)
    recorder.close()
    acquire_database_claim(ledger, exclusive=True).release()


def test_an_observer_releases_its_claim_when_its_final_flush_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-flush", "host-1"))
        observer.on_event(Envelope(
            record.session_id, 1, NOW, CORE_EVENT_SCHEMA_VERSION,
            StateChanged(SessionState.RUNNING),
        ))
        assert observer.pending_event_count == 1

        def fail_transaction(_operation):
            raise RecordingError("final flush failed")

        monkeypatch.setattr(store._writer, "transact", fail_transaction)
        with pytest.raises(RecordingError, match="final flush failed"):
            observer.close()
        acquire_database_claim(path, exclusive=True).release()
