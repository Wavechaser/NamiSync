from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from threading import Event, Lock, Thread

import pytest

import namisync.db.history as history_module
import namisync.db.repositories as repositories_module
import namisync.db.schema as schema_module
import namisync.workflows.runtime as runtime_module
from namisync.core.events import CORE_EVENT_SCHEMA_VERSION, Envelope, PhaseChanged
from namisync.core.planning import OperationKind, OperationReason
from namisync.core.session import SessionId, SessionRecord, SessionState
from namisync.db.connections import connect_history_writer, connect_ledger_writer
from namisync.db.history import HistoryContext, HistoryRepository, HistoryStore
from namisync.db.repositories import LedgerRepository
from namisync.db.schema import SchemaResetRequired, initialize_history, initialize_ledger
from namisync.interfaces.service import NamiSyncService
from namisync.workflows.runtime import LocalWorkflowRuntime

from _db_fixtures import FakeClock, NOW, file_stat, operation, plan, setup_recorder


@dataclass
class _ReaderCalls:
    admissions: list[Path] = field(default_factory=list)
    opened: list[LedgerRepository | HistoryRepository] = field(default_factory=list)
    closed: list[LedgerRepository | HistoryRepository] = field(default_factory=list)


@pytest.fixture
def readers(monkeypatch: pytest.MonkeyPatch) -> dict[str, _ReaderCalls]:
    calls = {role: _ReaderCalls() for role in ("ledger", "history")}

    def install(role, repository_type, owner) -> None:
        require = owner.require_database_file_contract

        def admit(path, *, history):
            calls[role].admissions.append(Path(path))
            return require(path, history=history)

        def construct(*args, **kwargs):
            repository = repository_type(*args, **kwargs)
            calls[role].opened.append(repository)
            close = repository.close

            def close_counted() -> None:
                calls[role].closed.append(repository)
                close()

            monkeypatch.setattr(repository, "close", close_counted)
            return repository

        monkeypatch.setattr(owner, "require_database_file_contract", admit)
        monkeypatch.setattr(runtime_module, repository_type.__name__, construct)

    install("ledger", LedgerRepository, repositories_module)
    install("history", HistoryRepository, history_module)
    return calls


@pytest.fixture
def runtime(tmp_path: Path):
    value = LocalWorkflowRuntime(
        tmp_path / "ledger.db", tmp_path / "history.db", clock=FakeClock()
    )
    try:
        yield value
    finally:
        thread, done, errors = _thread(value.close)
        thread.join(2)
        assert done.is_set(), "runtime reader cleanup did not finish"
        assert not errors, f"runtime reader cleanup failed: {errors}"


def _record() -> SessionRecord:
    return SessionRecord(
        SessionId("a" * 32), "inventory", SessionState.RUNNING, (),
        b"payload", False, 0, NOW, started_at=NOW,
    )


def _event(record: SessionRecord, sequence: int) -> Envelope:
    return Envelope(
        record.session_id, sequence, NOW, CORE_EVENT_SCHEMA_VERSION,
        PhaseChanged("inventory"),
    )


def _seed_history(path: Path) -> None:
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("reader-run", "host"))
        for sequence in range(1, 6):
            observer.on_event(_event(record, sequence))
        observer.flush()


def _make_database(path: Path, role: str, page_size: int = 4096) -> None:
    script = (
        schema_module._LEDGER_SCHEMA if role == "ledger"
        else schema_module._HISTORY_SCHEMA
    )
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute(f"PRAGMA page_size = {page_size}")
        connection.executescript(script)
        assert connection.execute("PRAGMA page_size").fetchone()[0] == page_size
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    if role == "history":
        _seed_history(path)


def _reads(runtime: LocalWorkflowRuntime, role: str) -> tuple[Callable[[], object], ...]:
    if role == "ledger":
        return (
            lambda: runtime.list_inventory(1, ("file.txt",)),
            lambda: runtime.mapping_ids_for_location(1),
            lambda: runtime.list_stale_inventory(1, NOW),
            lambda: runtime.list_unacknowledged_missing(1),
        )
    return (
        lambda: runtime.list_history(),
        lambda: runtime.get_history_summary("reader-run"),
        lambda: runtime.get_history_items("reader-run"),
        lambda: runtime.get_history_events("reader-run"),
    )


def _read(runtime: LocalWorkflowRuntime, role: str) -> object:
    return runtime.list_inventory(1) if role == "ledger" else runtime.list_history()


def _thread(call: Callable[[], object]) -> tuple[Thread, Event, list[BaseException]]:
    done = Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            call()
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread, done, errors


def _observe_second_lock_attempt(
    runtime: LocalWorkflowRuntime, role: str, monkeypatch: pytest.MonkeyPatch,
) -> Event:
    attempted = Event()
    role_lock = getattr(runtime, f"_{role}_reader_lock")
    count_lock = Lock()
    count = 0

    class ObservedLock:
        def __enter__(self):
            nonlocal count
            with count_lock:
                count += 1
                if count == 2:
                    attempted.set()
            role_lock.acquire()
            return self

        def __exit__(self, *args) -> None:
            role_lock.release()

    monkeypatch.setattr(runtime, f"_{role}_reader_lock", ObservedLock())
    return attempted


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize("page_size", [1024, 8192])
@pytest.mark.parametrize("with_wal", [False, True], ids=["no-sidecars", "wal"])
def test_repeated_runtime_reads_admit_once_per_owned_handle(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    role: str, page_size: int, with_wal: bool,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role, page_size)
    writer = None
    if with_wal:
        connect = connect_ledger_writer if role == "ledger" else connect_history_writer
        writer = connect(path)
        writer.execute("PRAGMA user_version = 99")
        assert Path(f"{path}-wal").stat().st_size > 0
    else:
        assert not Path(f"{path}-wal").exists()
        assert not Path(f"{path}-shm").exists()
    try:
        for _ in range(3):
            for read in _reads(runtime, role):
                read()
            assert readers[role].admissions == [path]
            assert len(readers[role].opened) == 1
            assert readers[role].closed == []
            assert not readers[role].opened[0]._connection.in_transaction

        runtime.close()
        assert readers[role].closed == readers[role].opened
        with closing(LocalWorkflowRuntime(runtime.ledger_path, runtime.history_path)) as reopened:
            _reads(reopened, role)[0]()
            assert readers[role].admissions == [path, path]
        assert readers[role].closed == readers[role].opened

        repository_type = LedgerRepository if role == "ledger" else HistoryRepository
        with repository_type(path):
            assert readers[role].admissions == [path, path, path]
    finally:
        runtime.close()
        if writer is not None:
            writer.close()


def test_service_history_summary_and_pages_share_one_admitted_reader(
    tmp_path: Path, readers: dict[str, _ReaderCalls],
) -> None:
    history = tmp_path / "history.db"
    _seed_history(history)
    with NamiSyncService(tmp_path / "ledger.db", history) as service:
        assert service.get_history_summary("reader-run").run_token == "reader-run"
        after = 0
        sequences = []
        for _ in range(3):
            page = service.get_history_events("reader-run", after_seq=after, limit=2)
            sequences.extend(event.sequence for event in page.events)
            after = page.next_after_seq
        assert sequences == [1, 2, 3, 4, 5]
        assert not page.has_more
        assert service.get_history_items("reader-run").items == ()
        assert len(service.list_history()) == 1
        assert readers["history"].admissions == [history]
    assert readers["history"].closed == readers["history"].opened


def test_retained_ledger_reader_observes_later_commits(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
) -> None:
    source = file_stat(identity_index=51)
    target = file_stat(identity_index=52, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP, source=source, target=target, intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(runtime.ledger_path, plan((noop,)))
    try:
        assert runtime.list_inventory(setup.target_location_id) == ()
        setup.run.record_noop(noop.op_id, source, target)
        rows = runtime.list_inventory(setup.target_location_id)
        assert len(rows) == 1
        assert rows[0].observed == target
        assert readers["ledger"].admissions == [runtime.ledger_path]
        assert not readers["ledger"].opened[0]._connection.in_transaction
    finally:
        setup.recorder.close()


def test_retained_history_reader_ends_each_request_transaction(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
) -> None:
    record = _record()
    with HistoryStore(runtime.history_path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("reader-run", "host"))
        observer.on_event(_event(record, 1))
        observer.flush()
        first = runtime.get_history_events("reader-run")
        observer.on_event(_event(record, 2))
        observer.flush()
        second = runtime.get_history_events("reader-run", after_seq=first.next_after_seq)
        assert [event.sequence for event in first.events] == [1]
        assert [event.sequence for event in second.events] == [2]
        assert second.through_seq == 2
        assert readers["history"].admissions == [runtime.history_path]
        assert not readers["history"].opened[0]._connection.in_transaction


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_failed_reader_admission_leaves_no_handle_and_retry_admits_fully(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls], role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    path.write_bytes(b"not a database")
    with pytest.raises(SchemaResetRequired):
        _read(runtime, role)
    assert readers[role].opened == []
    assert readers[role].closed == []
    path.unlink()
    initialize = initialize_ledger if role == "ledger" else initialize_history
    initialize(path)
    assert _read(runtime, role) == ()
    assert readers[role].admissions == [path, path]
    assert len(readers[role].opened) == 1


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_post_open_contract_refusal_closes_the_allocated_connection_before_retry(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    owner = repositories_module if role == "ledger" else history_module
    connect_name = f"connect_{role}_reader"
    validate_name = f"validate_{role}_reader_contract"
    connect = getattr(owner, connect_name)
    validate = getattr(owner, validate_name)
    connections = []
    failure = SchemaResetRequired("post-open contract refusal")
    refused = False

    def track_connection(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    def refuse_once(connection) -> None:
        nonlocal refused
        if not refused:
            refused = True
            raise failure
        validate(connection)

    monkeypatch.setattr(owner, connect_name, track_connection)
    monkeypatch.setattr(owner, validate_name, refuse_once)
    with pytest.raises(SchemaResetRequired) as raised:
        _read(runtime, role)
    assert raised.value is failure
    assert readers[role].opened == []
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    _read(runtime, role)
    assert len(connections) == 2
    assert readers[role].admissions == [path, path]
    assert len(readers[role].opened) == 1


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_new_runtime_refuses_an_incompatible_database_after_prior_owner_closed(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls], role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    _read(runtime, role)
    runtime.close()
    with closing(sqlite3.connect(path, isolation_level=None)) as writer:
        writer.execute(
            "UPDATE schema_metadata SET value = 'incompatible' WHERE key = 'contract_id'"
        )
    before = path.read_bytes()
    with closing(LocalWorkflowRuntime(runtime.ledger_path, runtime.history_path)) as reopened:
        with pytest.raises(SchemaResetRequired):
            _read(reopened, role)
    assert readers[role].admissions == [path, path]
    assert len(readers[role].opened) == 1
    assert readers[role].closed == readers[role].opened
    assert path.read_bytes() == before


def test_missing_history_does_not_create_or_cache_an_absent_database(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
) -> None:
    assert runtime.list_history() == ()
    for read in _reads(runtime, "history")[1:]:
        with pytest.raises(KeyError, match="reader-run"):
            read()
    assert not runtime.history_path.exists()
    assert readers["history"].admissions == []
    _seed_history(runtime.history_path)
    assert len(runtime.list_history()) == 1
    assert readers["history"].admissions == [runtime.history_path]


def test_closed_runtime_refuses_history_even_when_database_is_absent(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
) -> None:
    runtime.close()
    for read in _reads(runtime, "history"):
        with pytest.raises(RuntimeError, match="workflow runtime is closed"):
            read()
    assert readers["history"].admissions == []


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_reader_lock_covers_the_whole_query(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    repository_type = LedgerRepository if role == "ledger" else HistoryRepository
    method_name = "get_inventory" if role == "ledger" else "list_summaries"
    original = getattr(repository_type, method_name)
    entered = Event()
    second_entered = Event()
    release = Event()
    count_lock = Lock()
    count = 0
    attempted = _observe_second_lock_attempt(runtime, role, monkeypatch)

    def blocked(repository, *args, **kwargs):
        nonlocal count
        with count_lock:
            count += 1
            ordinal = count
        if ordinal == 1:
            entered.set()
            assert release.wait(2)
        else:
            second_entered.set()
        return original(repository, *args, **kwargs)

    monkeypatch.setattr(repository_type, method_name, blocked)
    threads = [_thread(lambda: _read(runtime, role))]
    try:
        assert entered.wait(2)
        threads.append(_thread(lambda: _read(runtime, role)))
        assert attempted.wait(2)
        assert not second_entered.wait(0.1)
    finally:
        release.set()
        for thread, _, _ in threads:
            thread.join(2)
    assert all(done.is_set() and not errors for _, done, errors in threads)
    assert second_entered.is_set()
    assert len(readers[role].opened) == 1


def test_ledger_query_does_not_hold_the_history_reader_lock(
    runtime: LocalWorkflowRuntime, monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize_ledger(runtime.ledger_path)
    initialize_history(runtime.history_path)
    entered = Event()
    release = Event()
    original = LedgerRepository.get_inventory

    def blocked(repository, *args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(repository, *args, **kwargs)

    monkeypatch.setattr(LedgerRepository, "get_inventory", blocked)
    threads = [_thread(lambda: runtime.list_inventory(1))]
    try:
        assert entered.wait(2)
        threads.append(_thread(runtime.list_history))
        assert threads[-1][1].wait(2)
        assert threads[-1][2] == []
        assert not threads[0][1].is_set()
    finally:
        release.set()
        for thread, _, _ in threads:
            thread.join(2)
    assert all(done.is_set() and not errors for _, done, errors in threads)


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_close_quiesces_queued_reads_and_waits_for_the_active_query(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    entered = Event()
    release = Event()
    queued = _observe_second_lock_attempt(runtime, role, monkeypatch)
    store_closed = Event()
    repository_type = LedgerRepository if role == "ledger" else HistoryRepository
    method_name = "get_inventory" if role == "ledger" else "list_summaries"
    original = getattr(repository_type, method_name)

    class Store:
        def close(self) -> None:
            store_closed.set()

    runtime._history_store = Store()

    def blocked(repository, *args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(repository, *args, **kwargs)

    monkeypatch.setattr(repository_type, method_name, blocked)
    threads = [_thread(lambda: _read(runtime, role))]
    try:
        assert entered.wait(2)
        threads.append(_thread(lambda: _read(runtime, role)))
        assert queued.wait(2)
        threads.append(_thread(runtime.close))
        assert store_closed.wait(2)
        assert not threads[2][1].wait(0.1)
    finally:
        release.set()
        for thread, _, _ in threads:
            thread.join(2)
    assert all(done.is_set() for _, done, _ in threads)
    assert threads[0][2] == []
    assert threads[2][2] == []
    assert len(threads[1][2]) == 1
    assert isinstance(threads[1][2][0], RuntimeError)
    assert str(threads[1][2][0]) == "workflow runtime is closed"
    assert len(readers[role].opened) == 1
    assert readers[role].closed == readers[role].opened


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_close_waits_for_a_real_reader_constructor_and_closes_its_late_handle(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    entered = Event()
    release = Event()
    store_closed = Event()
    name = "LedgerRepository" if role == "ledger" else "HistoryRepository"
    construct = getattr(runtime_module, name)

    def blocked_constructor(*args, **kwargs):
        reader = construct(*args, **kwargs)
        entered.set()
        assert release.wait(2)
        return reader

    class Store:
        def close(self) -> None:
            store_closed.set()

    runtime._history_store = Store()
    monkeypatch.setattr(runtime_module, name, blocked_constructor)
    threads = [_thread(lambda: _read(runtime, role))]
    try:
        assert entered.wait(2)
        threads.append(_thread(runtime.close))
        assert store_closed.wait(2)
        assert not threads[1][1].wait(0.1)
        assert len(readers[role].opened) == 1
        assert readers[role].closed == []
    finally:
        release.set()
        for thread, _, _ in threads:
            thread.join(2)
    assert all(done.is_set() and not errors for _, done, errors in threads)
    assert readers[role].closed == readers[role].opened
    with pytest.raises(RuntimeError, match="workflow runtime is closed"):
        _read(runtime, role)


@pytest.mark.parametrize("role", ["ledger", "history"])
def test_failed_close_retains_ownership_and_cannot_reopen_a_partial_reader(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str,
) -> None:
    initialize_ledger(runtime.ledger_path)
    initialize_history(runtime.history_path)
    runtime.list_inventory(1)
    runtime.list_history()
    reader = readers[role].opened[0]
    close = reader.close
    attempts = 0
    failure = OSError("reader close failed")

    def partial_close() -> None:
        nonlocal attempts
        attempts += 1
        close()
        if attempts == 1:
            raise failure

    monkeypatch.setattr(reader, "close", partial_close)
    with pytest.raises(OSError) as raised:
        runtime.close()
    assert raised.value is failure
    assert not runtime._closed
    for selected_role in ("ledger", "history"):
        with pytest.raises(RuntimeError, match="workflow runtime is closed"):
            _read(runtime, selected_role)
        assert len(readers[selected_role].opened) == 1
    runtime.close()
    runtime.close()
    assert runtime._closed
    assert attempts == 2
    peer = "history" if role == "ledger" else "ledger"
    assert readers[peer].closed == readers[peer].opened
    assert readers[role].closed == [reader, reader]


def test_query_failure_retires_reader_before_a_fully_admitted_retry(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
) -> None:
    _seed_history(runtime.history_path)
    assert len(runtime.list_history()) == 1
    with pytest.raises(KeyError, match="unknown"):
        runtime.get_history_summary("unknown")
    assert readers["history"].closed == [readers["history"].opened[0]]
    assert len(runtime.list_history()) == 1
    assert len(readers["history"].opened) == 2
    assert readers["history"].admissions == [runtime.history_path] * 2


@pytest.mark.parametrize("close_failure", [False, True])
def test_failed_read_rollback_retires_the_open_transaction(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, close_failure: bool,
) -> None:
    initialize_history(runtime.history_path)
    runtime.list_history()
    reader = readers["history"].opened[0]
    failure = OSError("read rollback failed")
    original = HistoryRepository._end_read
    failed = False
    close = reader.close
    close_attempts = 0

    def partial_close() -> None:
        nonlocal close_attempts
        close_attempts += 1
        close()
        if close_failure and close_attempts == 1:
            raise OSError("reader retirement close failed")

    def fail_once(repository) -> None:
        nonlocal failed
        if not failed:
            failed = True
            assert repository._connection.in_transaction
            raise failure
        original(repository)

    monkeypatch.setattr(HistoryRepository, "_end_read", fail_once)
    monkeypatch.setattr(reader, "close", partial_close)
    with pytest.raises(OSError) as raised:
        runtime.get_history_summary("unknown")
    assert raised.value is failure
    assert isinstance(failure.__context__, KeyError)
    assert failure.__context__.args == ("unknown",)
    assert readers["history"].closed == [reader]
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        reader._connection.execute("SELECT 1")
    if close_failure:
        assert "runtime database reader close was incomplete" in failure.__notes__
        with pytest.raises(RuntimeError, match="workflow runtime is closed"):
            runtime.list_history()
        runtime.close()
        with closing(LocalWorkflowRuntime(runtime.ledger_path, runtime.history_path)) as reopened:
            assert reopened.list_history() == ()
        assert close_attempts == 2
    else:
        assert runtime.list_history() == ()
    assert len(readers["history"].opened) == 2
    assert readers["history"].admissions == [runtime.history_path] * 2


@pytest.mark.parametrize("role", ["ledger", "history"])
@pytest.mark.parametrize(
    ("query_control", "close_control"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_query_and_retirement_close_failure_preserve_error_and_handle_ownership(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch, role: str, query_control: bool, close_control: bool,
) -> None:
    path = runtime.ledger_path if role == "ledger" else runtime.history_path
    _make_database(path, role)
    _read(runtime, role)
    reader = readers[role].opened[0]
    close = reader.close
    query_error = KeyboardInterrupt() if query_control else ValueError("query failed")
    close_error = SystemExit(23) if close_control else OSError("close failed")
    attempts = 0

    def failed_query(*args, **kwargs):
        raise query_error

    def partial_close() -> None:
        nonlocal attempts
        attempts += 1
        close()
        if attempts == 1:
            raise close_error

    repository_type = LedgerRepository if role == "ledger" else HistoryRepository
    method_name = "get_inventory" if role == "ledger" else "list_summaries"
    monkeypatch.setattr(repository_type, method_name, failed_query)
    monkeypatch.setattr(reader, "close", partial_close)
    expected = close_error if close_control and not query_control else query_error
    with pytest.raises(type(expected)) as raised:
        _read(runtime, role)
    assert raised.value is expected
    if expected is query_error:
        assert "runtime database reader close was incomplete" in expected.__notes__
    else:
        assert expected.__cause__ is query_error
    with pytest.raises(RuntimeError, match="workflow runtime is closed"):
        _read(runtime, role)
    assert len(readers[role].opened) == 1
    assert readers[role].closed == [reader]
    runtime.close()
    assert attempts == 2
    assert readers[role].closed == [reader, reader]


def test_quiescing_runtime_cannot_recreate_history_writer_after_close_failure(
    runtime: LocalWorkflowRuntime, monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class Store:
        def close(self) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("writer close failed")

    store = Store()
    runtime._history_store = store
    with pytest.raises(OSError, match="writer close failed"):
        runtime.close()
    assert not runtime._closed
    assert runtime._history_store is store
    with pytest.raises(RuntimeError, match="workflow runtime is closed"):
        runtime._ensure_history_store(())
    runtime.close()
    assert attempts == 2
    assert runtime._history_store is None


def test_reader_close_failure_cannot_recreate_a_successfully_closed_history_store(
    runtime: LocalWorkflowRuntime, readers: dict[str, _ReaderCalls],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize_ledger(runtime.ledger_path)
    runtime.list_inventory(1)
    reader = readers["ledger"].opened[0]
    close = reader.close
    attempts = 0
    stores_closed = []

    class Store:
        def close(self) -> None:
            stores_closed.append(self)

    store = Store()
    runtime._history_store = store

    def partial_close() -> None:
        nonlocal attempts
        attempts += 1
        close()
        if attempts == 1:
            raise OSError("reader close failed")

    def forbidden_store(*args, **kwargs):
        raise AssertionError("quiescing runtime recreated a history writer")

    monkeypatch.setattr(reader, "close", partial_close)
    monkeypatch.setattr(runtime_module, "HistoryStore", forbidden_store)
    with pytest.raises(OSError, match="reader close failed"):
        runtime.close()
    assert runtime._history_store is None
    with pytest.raises(RuntimeError, match="workflow runtime is closed"):
        runtime._ensure_history_store(())
    assert not runtime.history_path.exists()
    runtime.close()
    assert stores_closed == [store]
    assert attempts == 2
