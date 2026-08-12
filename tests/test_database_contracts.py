from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import namisync.workflows.database_pair as database_pair
from namisync.db.connections import connect_history_writer, connect_ledger_writer
from namisync.db.schema import (
    HISTORY_CONTRACT_ID,
    LEDGER_CONTRACT_ID,
    initialize_history,
    initialize_ledger,
)
from namisync.interfaces.service import NamiSyncService
from namisync.workflows.database_pair import DatabasePairInitializationError


_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _artifacts(path: Path) -> tuple[Path, ...]:
    return (path, *(Path(f"{path}{suffix}") for suffix in _SIDECAR_SUFFIXES))


def _snapshot(*paths: Path) -> dict[Path, bytes]:
    return {
        artifact: artifact.read_bytes()
        for path in paths
        for artifact in _artifacts(path)
        if artifact.exists()
    }


def _service(tmp_path: Path) -> tuple[NamiSyncService, Path, Path]:
    ledger = tmp_path / "ledger.db"
    history = tmp_path / "history.db"
    return NamiSyncService(ledger, history), ledger, history


def test_database_contract_preflight_is_read_only_for_fresh_pair(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing"
    ledger = root / "ledger.db"
    history = root / "history.db"
    service = NamiSyncService(ledger, history)

    first = service.validate_database_contracts()
    second = service.validate_database_contracts()

    assert first == second
    assert first.state == "fresh"
    assert first.reason is None
    assert first.reset_direction is None
    assert not root.exists()
    service.close()


@pytest.mark.parametrize("role", ("ledger", "history"))
@pytest.mark.parametrize("suffix", _SIDECAR_SUFFIXES)
def test_orphan_database_sidecar_refuses_without_mutation(
    tmp_path: Path,
    role: str,
    suffix: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    path = ledger if role == "ledger" else history
    sidecar = Path(f"{path}{suffix}")
    sidecar.write_bytes(b"orphan-sidecar")
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize("present_role", ("ledger", "history"))
def test_exactly_one_database_main_refuses_without_creating_peer(
    tmp_path: Path,
    present_role: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    present = ledger if present_role == "ledger" else history
    missing = history if present_role == "ledger" else ledger
    present.write_bytes(b"existing-main")
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    assert not missing.exists()
    service.close()


def test_empty_database_pair_refuses_read_only(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    ledger.touch()
    history.touch()
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "ledger-contract"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize("wrong_role", ("ledger", "history"))
def test_wrong_role_contract_marker_refuses_read_only(
    tmp_path: Path,
    wrong_role: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    changed = ledger if wrong_role == "ledger" else history
    with closing(sqlite3.connect(changed)) as connection:
        with connection:
            connection.execute(
                "UPDATE schema_metadata SET value = ? WHERE key = 'contract_id'",
                ("wrong-role-contract",),
            )
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == f"{wrong_role}-contract"
    assert result.reset_direction is not None
    assert _snapshot(ledger, history) == before
    service.close()


def test_matching_database_pair_is_ready_and_read_only(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "ready"
    assert result.reason is None
    assert result.reset_direction is None
    assert _snapshot(ledger, history) == before
    service.close()


@pytest.mark.parametrize(
    ("role", "connect_writer"),
    (
        ("ledger", connect_ledger_writer),
        ("history", connect_history_writer),
    ),
)
def test_live_wal_sidecars_are_not_changed_by_contract_preflight(
    tmp_path: Path,
    role: str,
    connect_writer,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    selected = ledger if role == "ledger" else history
    connection = connect_writer(selected)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA user_version = 99")
        connection.execute("COMMIT")
        wal = Path(f"{selected}-wal")
        shm = Path(f"{selected}-shm")
        assert wal.is_file() and wal.stat().st_size > 0
        assert shm.is_file() and shm.stat().st_size > 0
        before = _snapshot(ledger, history)

        result = service.validate_database_contracts()
        after = _snapshot(ledger, history)
    finally:
        connection.close()

    assert result.state == "ready"
    assert after == before
    service.close()


def test_ready_database_initialization_is_a_byte_exact_noop(
    tmp_path: Path,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    initialize_history(history)
    ledger_writer = connect_ledger_writer(ledger)
    history_writer = connect_history_writer(history)
    try:
        for value, connection in enumerate((ledger_writer, history_writer), start=1):
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"PRAGMA user_version = {value}")
            connection.execute("COMMIT")
        for path in (ledger, history):
            assert Path(f"{path}-wal").is_file()
            assert Path(f"{path}-shm").is_file()
        before = _snapshot(ledger, history)

        first = service.initialize_database_contracts()
        second = service.initialize_database_contracts()
        after = _snapshot(ledger, history)
    finally:
        history_writer.close()
        ledger_writer.close()

    assert first.state == second.state == "ready"
    assert after == before
    service.close()


@pytest.mark.parametrize("role", ("ledger", "history"))
@pytest.mark.parametrize("shape", ("malformed", "unversioned", "swapped-marker"))
def test_role_contract_counterexamples_refuse_without_mutation(
    tmp_path: Path,
    role: str,
    shape: str,
) -> None:
    service, ledger, history = _service(tmp_path)
    selected = ledger if role == "ledger" else history
    other = history if role == "ledger" else ledger
    initialize_other = initialize_history if role == "ledger" else initialize_ledger
    initialize_other(other)

    if shape == "malformed":
        selected.write_bytes(b"not a SQLite database")
    elif shape == "unversioned":
        with closing(sqlite3.connect(selected)) as connection:
            with connection:
                connection.execute("CREATE TABLE legacy_marker(value TEXT)")
                connection.execute(
                    "INSERT INTO legacy_marker(value) VALUES ('preserve')"
                )
    else:
        initialize_selected = (
            initialize_ledger if role == "ledger" else initialize_history
        )
        initialize_selected(selected)
        swapped = HISTORY_CONTRACT_ID if role == "ledger" else LEDGER_CONTRACT_ID
        with closing(sqlite3.connect(selected)) as connection:
            with connection:
                connection.execute(
                    "UPDATE schema_metadata SET value = ? "
                    "WHERE key = 'contract_id'",
                    (swapped,),
                )
    before = _snapshot(ledger, history)

    first = service.validate_database_contracts()
    second = service.validate_database_contracts()

    assert first == second
    assert first.state == "refused"
    assert first.reason == f"{role}-contract"
    assert _snapshot(ledger, history) == before
    service.close()


def test_fresh_database_pair_initializes_coordinately(tmp_path: Path) -> None:
    service, ledger, history = _service(tmp_path)
    assert service.validate_database_contracts().state == "fresh"

    initialized = service.initialize_database_contracts()
    repeated = service.initialize_database_contracts()

    assert initialized.state == "ready"
    assert repeated.state == "ready"
    assert service.validate_database_contracts().state == "ready"
    assert ledger.exists()
    assert history.exists()
    assert set(_snapshot(ledger, history)) == {ledger, history}
    service.close()


def test_caught_partial_database_initialization_removes_owned_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)

    def fail_history(path: str | Path, **_kwargs: object) -> Path:
        assert Path(path) == history
        Path(f"{path}-wal").write_bytes(b"attempt-owned-sidecar")
        raise OSError("injected history publication failure")

    monkeypatch.setattr(database_pair, "initialize_history", fail_history)

    with pytest.raises(
        DatabasePairInitializationError,
        match="coordinated database initialization failed",
    ):
        service.initialize_database_contracts()

    assert _snapshot(ledger, history) == {}
    service.close()


def test_initialization_cleanup_preserves_unproven_raced_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    sidecar = Path(f"{ledger}-wal")
    reserve = database_pair._reserve

    def reserve_with_race(path: Path, owned: dict[Path, tuple[int, int]]) -> None:
        reserve(path, owned)
        if path == ledger:
            sidecar.write_bytes(b"foreign-sidecar")

    monkeypatch.setattr(database_pair, "_reserve", reserve_with_race)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert not history.exists()
    assert sidecar.read_bytes() == b"foreign-sidecar"
    service.close()


def test_initialization_cleanup_preserves_replaced_reserved_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)
    sidecar = Path(f"{ledger}-wal")
    displaced = tmp_path / "attempt-owned-ledger-wal"

    def fail_ledger_after_sidecar_write(
        path: str | Path,
        **_kwargs: object,
    ) -> Path:
        sidecar.write_bytes(b"attempt-owned-sidecar")
        raise OSError(f"injected ledger failure for {path}")

    retract = database_pair._retract_owned

    def replace_before_retract(
        owned: dict[Path, tuple[int, int]],
    ) -> tuple[OSError, ...]:
        assert sidecar in owned
        sidecar.rename(displaced)
        sidecar.write_bytes(b"foreign-replacement")
        return retract(owned)

    monkeypatch.setattr(
        database_pair,
        "initialize_ledger",
        fail_ledger_after_sidecar_write,
    )
    monkeypatch.setattr(database_pair, "_retract_owned", replace_before_retract)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert not history.exists()
    assert sidecar.read_bytes() == b"foreign-replacement"
    assert displaced.read_bytes() == b"attempt-owned-sidecar"
    service.close()


def test_initialization_cleanup_never_deletes_raced_preexisting_peer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ledger, history = _service(tmp_path)

    def fail_ledger(path: str | Path, **_kwargs: object) -> Path:
        assert Path(path) == ledger
        history.write_bytes(b"created outside this attempt")
        raise OSError("injected ledger publication failure")

    monkeypatch.setattr(database_pair, "initialize_ledger", fail_ledger)

    with pytest.raises(DatabasePairInitializationError):
        service.initialize_database_contracts()

    assert not ledger.exists()
    assert history.read_bytes() == b"created outside this attempt"
    service.close()


def test_crash_shaped_single_publication_refuses_next_launch(
    tmp_path: Path,
) -> None:
    service, ledger, history = _service(tmp_path)
    initialize_ledger(ledger)
    before = _snapshot(ledger, history)

    result = service.validate_database_contracts()

    assert result.state == "refused"
    assert result.reason == "inconsistent-pair"
    assert _snapshot(ledger, history) == before
    assert not history.exists()
    service.close()
