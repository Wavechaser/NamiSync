from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re
import sqlite3
from datetime import timedelta

import pytest

import namisync.db.repositories as repository_module
from namisync.core.evidence import Provenance
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
)
from namisync.core.models import FileIdentity, VolumeId
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind, OperationReason
from namisync.core.recording import InventoryCommand
from namisync.core.scalars import MAX_FILE_INDEX_128
from namisync.db.connections import (
    QUERY_SUBJECT_BATCH_SIZE,
    connect_ledger_reader,
    connect_ledger_writer,
)
from namisync.db.repositories import (
    InventoryPopulationLimitError,
    LedgerRepository,
)

from _db_fixtures import (
    NOW,
    _file,
    _scan,
    attestation,
    file_stat,
    operation,
    plan,
    setup_recorder,
)


_SUBJECT_BATCH_CASES = tuple(
    (count, QUERY_SUBJECT_BATCH_SIZE) for count in (0, 1, 399, 400, 401, 801)
) + ((801, 37),)


class _ParameterRecordingConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        calls: list[tuple[str, tuple[object, ...]]],
    ) -> None:
        self._connection = connection
        self._calls = calls

    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        self._calls.append((statement, tuple(parameters)))
        return self._connection.execute(statement, parameters)

    def __getattr__(self, name: str) -> object:
        return getattr(self._connection, name)


def _capture_repository_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, tuple[object, ...]]]:
    calls: list[tuple[str, tuple[object, ...]]] = []
    connect = repository_module.connect_ledger_reader

    def recording_connect(*args: object, **kwargs: object) -> object:
        return _ParameterRecordingConnection(connect(*args, **kwargs), calls)

    monkeypatch.setattr(repository_module, "connect_ledger_reader", recording_connect)
    return calls


def _first_excess(*values: object) -> Iterator[object]:
    yield from values
    raise AssertionError("repository read beyond the first excess request")


_MAPPING_PAIR_QUERY = re.compile(
    r"\bFROM\s+mapping_correspondence\b", re.IGNORECASE
)
_IDENTITY_QUERY = re.compile(
    r"\bWITH\s+requested\s*\(\s*volume_serial\s*,\s*file_index\s*\)",
    re.IGNORECASE,
)
_INVENTORY_SELECTION_QUERY = re.compile(
    r"^\s*SELECT\s+\*\s+FROM\s+inventory\b", re.IGNORECASE
)


def _matching_statements(
    statements: list[str], pattern: re.Pattern[str]
) -> list[str]:
    return [statement for statement in statements if pattern.search(statement)]


def _query_plan(path: Path, statement: str) -> tuple[str, ...]:
    connection = connect_ledger_reader(path)
    try:
        return tuple(
            str(row["detail"])
            for row in connection.execute("EXPLAIN QUERY PLAN " + statement)
        )
    finally:
        connection.close()


def _mapping_rows(
    count: int,
    *,
    descending_source_paths: bool = False,
    null_target_index: int | None = None,
) -> tuple[tuple[str, FileIdentity, str, FileIdentity | None, int, int], ...]:
    return tuple(
        (
            (
                f"source-{count - index if descending_source_paths else index:04d}.bin"
            ),
            FileIdentity("source-serial", index),
            f"target-{index:04d}.bin",
            (
                None
                if index == null_target_index
                else FileIdentity("target-serial", 10_000 + index)
            ),
            1,
            1,
        )
        for index in range(1, count + 1)
    )


def _insert_minimal_inventory_rows(
    path: Path,
    location_id: int,
    *,
    start: int,
    count: int,
) -> None:
    writer = connect_ledger_writer(path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.executemany(
            """INSERT INTO inventory(
                   location_id, rel_path, rel_path_key, entry_kind, presence,
                   scope_token
               ) VALUES (?, ?, ?, 'file', 'present', 'candidate-scope')""",
            (
                (
                    location_id,
                    f"candidate-{index:06d}.bin",
                    f"CANDIDATE-{index:06d}.BIN",
                )
                for index in range(start, start + count)
            ),
        )
        writer.commit()
    finally:
        writer.close()


def _insert_mapping_history(
    path: Path,
    setup,
    rows: tuple[
        tuple[str, FileIdentity, str, FileIdentity | None, int, int], ...
    ],
) -> None:
    """Seed correspondence without routing a large synthetic run through recorder."""

    source_count = len(rows)
    writer = connect_ledger_writer(path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.executemany(
            """INSERT INTO inventory(
                   id, location_id, rel_path, rel_path_key, entry_kind, presence,
                   observed_size, observed_mtime_ns,
                   file_identity_volume_serial, file_identity_file_index,
                   observed_nlink, observed_attributes, scope_token
               ) VALUES (?, ?, ?, ?, 'file', 'present', 1, 1, ?, ?, ?, 0, 'scope')""",
            (
                (
                    index,
                    setup.source_location_id,
                    source_path,
                    normalize_relative_path(source_path),
                    source_identity.volume_serial,
                    str(source_identity.file_index),
                    source_nlink,
                )
                for index, (
                    source_path,
                    source_identity,
                    _target_path,
                    _target_identity,
                    source_nlink,
                    _target_nlink,
                ) in enumerate(rows, start=1)
            ),
        )
        writer.executemany(
            """INSERT INTO inventory(
                   id, location_id, rel_path, rel_path_key, entry_kind, presence,
                   observed_size, observed_mtime_ns,
                   file_identity_volume_serial, file_identity_file_index,
                   observed_nlink, observed_attributes, scope_token
               ) VALUES (?, ?, ?, ?, 'file', 'present', 1, 1, ?, ?, ?, 0, 'scope')""",
            (
                (
                    source_count + index,
                    setup.target_location_id,
                    target_path,
                    normalize_relative_path(target_path),
                    None if target_identity is None else target_identity.volume_serial,
                    None if target_identity is None else str(target_identity.file_index),
                    target_nlink,
                )
                for index, (
                    _source_path,
                    _source_identity,
                    target_path,
                    target_identity,
                    _source_nlink,
                    target_nlink,
                ) in enumerate(rows, start=1)
            ),
        )
        writer.executemany(
            """INSERT INTO mapping_correspondence(
                   mapping_id, source_inventory_id, target_inventory_id,
                   source_identity_volume_serial, source_identity_file_index,
                   target_identity_volume_serial, target_identity_file_index,
                   last_seen_at, run_token, op_token
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                (
                    setup.mapping_id,
                    index,
                    source_count + index,
                    source_identity.volume_serial,
                    str(source_identity.file_index),
                    None if target_identity is None else target_identity.volume_serial,
                    None if target_identity is None else str(target_identity.file_index),
                    NOW.isoformat(),
                    setup.run_token,
                    f"op-{index}",
                )
                for index, (
                    _source_path,
                    source_identity,
                    _target_path,
                    target_identity,
                    _source_nlink,
                    _target_nlink,
                ) in enumerate(rows, start=1)
            ),
        )
        writer.commit()
    finally:
        writer.close()


def _seed_recent_sync_pairs(path: Path):
    setup = setup_recorder(path, plan(()))
    setup.recorder.close()
    writer = connect_ledger_writer(path)
    identities: list[tuple[int, int, int]] = []
    try:
        writer.execute("BEGIN IMMEDIATE")
        volume_id = int(
            writer.execute(
                "SELECT volume_id FROM locations WHERE id = ?",
                (setup.source_location_id,),
            ).fetchone()[0]
        )
        for index in range(1, 8):
            source_id = int(
                writer.execute(
                    """INSERT INTO locations(
                           volume_id, volume_relative_path,
                           volume_relative_path_key, created_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?) RETURNING id""",
                    (
                        volume_id,
                        f"recent-source-{index}",
                        f"RECENT-SOURCE-{index}",
                        NOW.isoformat(),
                        NOW.isoformat(),
                    ),
                ).fetchone()[0]
            )
            target_id = int(
                writer.execute(
                    """INSERT INTO locations(
                           volume_id, volume_relative_path,
                           volume_relative_path_key, created_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?) RETURNING id""",
                    (
                        volume_id,
                        f"recent-target-{index}",
                        f"RECENT-TARGET-{index}",
                        NOW.isoformat(),
                        NOW.isoformat(),
                    ),
                ).fetchone()[0]
            )
            mapping_id = int(
                writer.execute(
                    """INSERT INTO mappings(
                           source_location_id, target_location_id, created_at
                       ) VALUES (?, ?, ?) RETURNING id""",
                    (source_id, target_id, NOW.isoformat()),
                ).fetchone()[0]
            )
            started = NOW + timedelta(days=4 if index == 5 else index)
            writer.execute(
                """INSERT INTO runs(
                       run_token, activity_kind, host_id, mapping_id,
                       source_location_id, target_location_id, started_at,
                       ended_at, filesystem_status, recording_status,
                       start_payload_hash
                   ) VALUES (?, 'sync', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"recent-run-{index}",
                    setup.host_id,
                    mapping_id,
                    source_id,
                    target_id,
                    started.isoformat(),
                    None if index == 3 else started.isoformat(),
                    (
                        None,
                        "failed",
                        "canceled",
                        "partial",
                        "success",
                        "failed",
                        "success",
                    )[index - 1],
                    None if index == 2 else "ok",
                    bytes([index]) * 32,
                ),
            )
            identities.append((mapping_id, source_id, target_id))
        writer.execute(
            "UPDATE mappings SET deleted_at = ? WHERE id = ?",
            ((NOW + timedelta(days=7)).isoformat(), identities[-1][0]),
        )
        writer.commit()
    finally:
        writer.close()
    return identities


def test_recent_sync_activity_is_bounded_ordered_and_provenance_complete(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    identities = _seed_recent_sync_pairs(path)

    statements: list[str] = []
    with LedgerRepository(path, trace_callback=statements.append) as repository:
        recent = repository.get_recent_sync_activity()

    expected = [identities[index] for index in (5, 3, 4, 2, 1)]
    assert len(recent.sources) == len(recent.targets) == len(recent.pairs) == 5
    assert [row.location.location_id for row in recent.sources] == [
        row[1] for row in expected
    ]
    assert [row.location.location_id for row in recent.targets] == [
        row[2] for row in expected
    ]
    assert [row.mapping_id for row in recent.pairs] == [row[0] for row in expected]
    assert identities[-1][0] not in {row.mapping_id for row in recent.pairs}
    recent_selects = [
        statement
        for statement in statements
        if "FROM runs AS run" in statement
    ]
    assert len(recent_selects) == 3
    assert all("LIMIT 5" in statement for statement in recent_selects)


def test_recent_sync_activity_uses_one_read_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    identities = _seed_recent_sync_pairs(path)
    repository = LedgerRepository(path)
    original = repository._connection
    changed = False

    class Connection:
        def execute(self, statement: str, parameters=()):
            nonlocal changed
            if "target.id AS target_location_id" in statement and not changed:
                changed = True
                writer = connect_ledger_writer(path)
                try:
                    mapping_id, source_id, target_id = identities[0]
                    host_id = int(
                        writer.execute("SELECT id FROM hosts ORDER BY id LIMIT 1").fetchone()[0]
                    )
                    started = NOW + timedelta(days=20)
                    writer.execute("BEGIN IMMEDIATE")
                    writer.execute(
                        """INSERT INTO runs(
                               run_token, activity_kind, host_id, mapping_id,
                               source_location_id, target_location_id, started_at,
                               start_payload_hash
                           ) VALUES (?, 'sync', ?, ?, ?, ?, ?, ?)""",
                        (
                            "snapshot-later-run",
                            host_id,
                            mapping_id,
                            source_id,
                            target_id,
                            started.isoformat(),
                            b"s" * 32,
                        ),
                    )
                    writer.commit()
                finally:
                    writer.close()
            return original.execute(statement, parameters)

        def __getattr__(self, name: str):
            return getattr(original, name)

    repository._connection = Connection()  # type: ignore[assignment]
    try:
        recent = repository.get_recent_sync_activity()
    finally:
        repository.close()

    assert changed
    assert [row.location.location_id for row in recent.sources] == [
        row.source.location_id for row in recent.pairs
    ]
    assert [row.location.location_id for row in recent.targets] == [
        row.target.location_id for row in recent.pairs
    ]


def test_integrity_candidate_reader_enforces_complete_population_row_wall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    limit = INTEGRITY_CANDIDATE_ROW_LIMIT
    _insert_minimal_inventory_rows(
        setup.recorder.path,
        setup.source_location_id,
        start=0,
        count=limit,
    )
    monkeypatch.setattr(
        repository_module,
        "_inventory_snapshot",
        lambda row: str(row["id"]),
    )
    paths = tuple(f"candidate-{index:06d}.bin" for index in range(limit))
    try:
        with LedgerRepository(setup.recorder.path) as repository:
            full = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
            )
            assert len(full) == limit
            del full

            selected = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
                path_keys=reversed(paths),
            )
            assert len(selected) == limit
            assert (selected[0], selected[-1]) == ("1", str(limit))
            del selected

            saved_ids = tuple(str(value) for value in range(limit, 0, -1))
            saved = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.BASELINE,
                saved_row_ids=saved_ids,
            )
            assert saved == saved_ids
            del saved

        _insert_minimal_inventory_rows(
            setup.recorder.path,
            setup.source_location_id,
            start=limit,
            count=1,
        )
        excess_paths = paths + (f"candidate-{limit:06d}.bin",)
        with LedgerRepository(setup.recorder.path) as repository:
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory(setup.source_location_id)
            for kwargs in (
                {},
                {"path_keys": excess_paths},
                {
                    "saved_row_ids": tuple(
                        str(value) for value in range(1, limit + 2)
                    )
                },
            ):
                with pytest.raises(IntegrityCandidateLimitError) as raised:
                    repository.get_integrity_candidates(
                        setup.source_location_id,
                        IntegrityMode.VERIFY,
                        **kwargs,
                    )
                assert raised.value.fact == IntegrityCandidateLimitExceeded.rows()

            assert repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.REBASELINE,
            ) == ()
            with pytest.raises(IntegrityCandidateLimitError):
                repository.get_integrity_candidates(
                    setup.source_location_id,
                    IntegrityMode.REBASELINE,
                    path_keys=excess_paths,
                )
    finally:
        setup.recorder.close()


def test_general_inventory_readers_refuse_first_excess_population(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    _insert_minimal_inventory_rows(
        setup.recorder.path,
        setup.source_location_id,
        start=0,
        count=3,
    )
    monkeypatch.setattr(repository_module, "INVENTORY_POPULATION_ROW_LIMIT", 2)
    try:
        with LedgerRepository(setup.recorder.path) as repository:
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory(setup.source_location_id)
            assert repository.get_inventory(
                setup.source_location_id,
                ("absent-a.bin", "absent-b.bin"),
            ) == ()
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory(
                    setup.source_location_id,
                    (
                        "candidate-000000.bin",
                        "candidate-000001.bin",
                        "candidate-000002.bin",
                    ),
                )
            assert repository.get_inventory_by_row_ids(
                setup.source_location_id,
                ("9001", "9002"),
            ) == ()
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory_by_row_ids(
                    setup.source_location_id,
                    ("1", "2", "3"),
                )
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_stale_inventory(
                    setup.source_location_id,
                    NOW,
                )

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                """UPDATE inventory
                      SET presence = 'missing', missing_since = ?
                    WHERE location_id = ?""",
                (NOW.isoformat(), setup.source_location_id),
            )
            writer.commit()
        finally:
            writer.close()

        with LedgerRepository(setup.recorder.path) as repository:
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_unacknowledged_missing(
                    setup.source_location_id
                )
    finally:
        setup.recorder.close()


def test_requested_inventory_scopes_refuse_the_first_raw_excess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    monkeypatch.setattr(repository_module, "INVENTORY_POPULATION_ROW_LIMIT", 2)

    try:
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_inventory(
                setup.source_location_id,
                ("absent.bin", "absent.bin"),
            ) == ()
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory(
                    setup.source_location_id,
                    _first_excess("absent.bin", "absent.bin", "absent.bin"),
                )

            assert repository.get_inventory_by_row_ids(
                setup.source_location_id,
                ("999999", "999999"),
            ) == ()
            with pytest.raises(InventoryPopulationLimitError):
                repository.get_inventory_by_row_ids(
                    setup.source_location_id,
                    _first_excess("999999", "999999", "999999"),
                )
    finally:
        setup.recorder.close()


def test_integrity_request_preprocessing_refuses_the_first_raw_excess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    monkeypatch.setattr(repository_module, "INTEGRITY_CANDIDATE_ROW_LIMIT", 2)

    try:
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
                path_keys=("absent.bin", "absent.bin"),
            ) == ()
            with pytest.raises(IntegrityCandidateLimitError):
                repository.get_integrity_candidates(
                    setup.source_location_id,
                    IntegrityMode.VERIFY,
                    path_keys=_first_excess(
                        "absent.bin", "absent.bin", "absent.bin"
                    ),
                )
            with pytest.raises(IntegrityCandidateLimitError):
                repository.get_integrity_candidates(
                    setup.source_location_id,
                    IntegrityMode.VERIFY,
                    saved_row_ids=_first_excess("1", "2", "3"),
                )
    finally:
        setup.recorder.close()


def test_mapping_request_preprocessing_refuses_first_raw_excess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    monkeypatch.setattr(repository_module, "INVENTORY_POPULATION_ROW_LIMIT", 2)
    identity = FileIdentity("source-serial", 1)

    common = {
        "source_volume": VolumeId("source-serial", "NTFS"),
        "source_relative_root": "source",
        "target_volume": VolumeId("target-serial", "NTFS"),
        "target_relative_root": "target",
    }
    try:
        with LedgerRepository(setup.recorder.path) as repository:
            requests = (
                (_first_excess("a.bin", "a.bin", "a.bin"), (), ()),
                ((), _first_excess(identity, identity, identity), ()),
                ((), (), _first_excess(identity, identity, identity)),
            )
            for target_paths, source_ids, target_ids in requests:
                with pytest.raises(InventoryPopulationLimitError):
                    repository.find_current_mapping(
                        **common,
                        target_path_keys=target_paths,
                        source_identities=source_ids,
                        target_identities=target_ids,
                    )
    finally:
        setup.recorder.close()


def test_stale_integrity_candidate_union_deduplicates_before_row_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    limit = INTEGRITY_CANDIDATE_ROW_LIMIT
    _insert_minimal_inventory_rows(
        setup.recorder.path,
        setup.source_location_id,
        start=0,
        count=limit + 1,
    )
    writer = connect_ledger_writer(setup.recorder.path)
    try:
        writer.execute(
            """UPDATE inventory SET presence = 'missing'
                 WHERE location_id = ? AND id IN (?, ?)""",
            (setup.source_location_id, limit, limit + 1),
        )
    finally:
        writer.close()
    monkeypatch.setattr(
        repository_module,
        "_inventory_snapshot",
        lambda row: str(row["id"]),
    )
    try:
        with LedgerRepository(setup.recorder.path) as repository:
            exact = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
                stale_before=NOW,
                completed_row_ids=(str(limit),),
            )
            assert len(exact) == limit
            assert str(limit) in exact

            with pytest.raises(IntegrityCandidateLimitError):
                repository.get_integrity_candidates(
                    setup.source_location_id,
                    IntegrityMode.VERIFY,
                    stale_before=NOW,
                    completed_row_ids=(str(limit), str(limit + 1)),
                )
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    ("count", "batch_size"),
    _SUBJECT_BATCH_CASES,
)
def test_chunked_integrity_candidate_read_uses_one_snapshot_and_saved_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    batch_size: int,
) -> None:
    monkeypatch.setattr(repository_module, "QUERY_SUBJECT_BATCH_SIZE", batch_size)
    parameter_calls = _capture_repository_parameters(monkeypatch)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(
        _file(f"folder\\file-{index:04d}.bin", index + 1) for index in range(count)
    )
    writer = connect_ledger_writer(setup.recorder.path)
    path_select_count = 0
    statements: list[str] = []

    def update_between_batches(statement: str) -> None:
        nonlocal path_select_count
        statements.append(statement)
        if (
            "SELECT * FROM INVENTORY" not in statement.upper()
            or "REL_PATH_KEY IN" not in statement.upper()
        ):
            return
        path_select_count += 1
        if path_select_count == 2:
            writer.execute(
                "UPDATE inventory SET scope_token = ? WHERE location_id = ?",
                ("scope-new", setup.source_location_id),
            )
            writer.commit()

    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope-old",
                NOW,
            )
        )
        paths = tuple(record.rel_path for record in reversed(records))
        with LedgerRepository(
            setup.recorder.path,
            trace_callback=update_between_batches,
        ) as repository:
            selected = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
                path_keys=paths,
            )
            row_ids = tuple(row.row_id for row in selected)
            saved = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.BASELINE,
                saved_row_ids=tuple(reversed(row_ids)),
            )
            stale = repository.get_integrity_candidates(
                setup.source_location_id,
                IntegrityMode.VERIFY,
                stale_before=NOW,
                completed_row_ids=tuple(reversed(row_ids)),
            )
            if row_ids:
                with pytest.raises(RuntimeError, match="missing inventory rows"):
                    repository.get_integrity_candidates(
                        setup.source_location_id,
                        IntegrityMode.BASELINE,
                        saved_row_ids=(row_ids[0], "999999999"),
                    )

        bounded_calls = [
            parameters
            for statement, parameters in parameter_calls
            if (
                "SELECT * FROM inventory" in statement
                and ("rel_path_key IN" in statement or "id IN" in statement)
                and "LIMIT ?" in statement
            )
        ]
        assert all(len(parameters) <= batch_size + 2 for parameters in bounded_calls)
        assert tuple(row.rel_path_key for row in selected) == tuple(
            sorted(record.rel_path_key for record in records)
        )
        assert tuple(row.row_id for row in saved) == tuple(reversed(row_ids))
        assert tuple(row.rel_path_key for row in stale) == tuple(
            sorted(record.rel_path_key for record in records)
        )

        if count > batch_size:
            assert path_select_count >= 2
            assert {row.scope_token for row in selected} == {"scope-old"}
            with LedgerRepository(setup.recorder.path) as repository:
                durable = repository.get_inventory(setup.source_location_id)
            assert {row.scope_token for row in durable} == {"scope-new"}
    finally:
        writer.close()
        setup.recorder.close()


def test_mapping_repository_round_trips_paired_noop_correspondence(tmp_path: Path) -> None:
    source = file_stat(identity_index=41)
    target = file_stat(identity_index=42, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP,
        source=source,
        target=target,
        intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((noop,)))
    try:
        setup.run.record_noop(noop.op_id, source, target)
        with LedgerRepository(setup.recorder.path) as repository:
            snapshot = repository.get_mapping_snapshot(setup.mapping_id)

        assert snapshot.source_volume_id.serial == "source-serial"
        assert snapshot.target_volume_id.serial == "target-serial"
        assert len(snapshot.pairs) == 1
        pair = snapshot.pairs[0]
        assert pair.source_rel_path_key == "A.TXT"
        assert pair.target_rel_path_key == "A.TXT"
        assert pair.source_identity.file_index == 41
        assert pair.target_identity.file_index == 42
    finally:
        setup.recorder.close()


def test_ledger_round_trips_full_width_file_indexes_as_canonical_text(
    tmp_path: Path,
) -> None:
    source_index = (1 << 64) + 41
    target_index = MAX_FILE_INDEX_128
    source = file_stat(identity_index=source_index)
    target = file_stat(
        identity_index=target_index,
        volume_serial="target-serial",
    )
    noop = operation(
        OperationKind.NOOP,
        source=source,
        target=target,
        intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((noop,)))
    try:
        setup.run.record_noop(noop.op_id, source, target)
        with LedgerRepository(setup.recorder.path) as repository:
            pair = repository.get_mapping_snapshot(setup.mapping_id).pairs[0]
            inventory = repository.get_inventory(setup.target_location_id)

        assert pair.source_identity.file_index == source_index
        assert pair.target_identity.file_index == target_index
        assert inventory[0].observed.file_identity.file_index == target_index

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            raw_pair = connection.execute(
                """SELECT source_identity_file_index,
                          typeof(source_identity_file_index) AS source_type,
                          target_identity_file_index,
                          typeof(target_identity_file_index) AS target_type
                     FROM mapping_correspondence"""
            ).fetchone()
            raw_inventory = connection.execute(
                """SELECT file_identity_file_index,
                          typeof(file_identity_file_index) AS identity_type
                     FROM inventory
                    WHERE location_id = ?""",
                (setup.target_location_id,),
            ).fetchone()
        finally:
            connection.close()

        assert tuple(raw_pair) == (
            str(source_index),
            "text",
            str(target_index),
            "text",
        )
        assert tuple(raw_inventory) == (str(target_index), "text")

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                writer.execute(
                    """UPDATE mapping_correspondence
                          SET source_identity_file_index = '01'"""
                )
            with pytest.raises(sqlite3.IntegrityError):
                writer.execute(
                    """UPDATE mapping_correspondence
                          SET target_identity_file_index = ?""",
                    (str(MAX_FILE_INDEX_128 + 1),),
                )
        finally:
            writer.close()
    finally:
        setup.recorder.close()


def test_current_mapping_read_ignores_large_irrelevant_history_and_keeps_pair_order(
    tmp_path: Path,
) -> None:
    count = 1_201
    rows = _mapping_rows(
        count, descending_source_paths=True, null_target_index=700
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    statements: list[str] = []
    try:
        _insert_mapping_history(setup.recorder.path, setup, rows)
        selected = (900, 300, 700, 1_100)
        source_identities = frozenset(
            rows[index - 1][1] for index in selected[:-1]
        )
        target_identities = frozenset(
            identity
            for index in selected
            if (identity := rows[index - 1][3]) is not None
        ) | {FileIdentity("target-serial", 99_999)}
        target_paths = tuple(rows[index - 1][2] for index in reversed(selected))

        with LedgerRepository(
            setup.recorder.path, trace_callback=statements.append
        ) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=target_paths,
                source_identities=source_identities,
                target_identities=target_identities,
            )

        assert found is not None
        assert [pair.source_rel_path_key for pair in found.snapshot.pairs] == sorted(
            normalize_relative_path(rows[index - 1][0])
            for index in selected[:-1]
        )
        assert {pair.target_rel_path_key for pair in found.snapshot.pairs} == {
            normalize_relative_path(rows[index - 1][2])
            for index in selected[:-1]
        }
        assert any(pair.target_identity is None for pair in found.snapshot.pairs)
        pair_selects = _matching_statements(statements, _MAPPING_PAIR_QUERY)
        assert len(pair_selects) == 1
        assert "pair.target_inventory_id IN" in pair_selects[0]
        assert "current_target.location_id" in pair_selects[0]
    finally:
        setup.recorder.close()


def test_current_mapping_read_preserves_relevant_identity_alias_disqualification(
    tmp_path: Path,
) -> None:
    shared_source = FileIdentity("source-serial", 41)
    shared_target = FileIdentity("target-serial", 51)
    linked_source = FileIdentity("source-serial", 42)
    linked_target = FileIdentity("target-serial", 52)
    irrelevant_source = FileIdentity("source-serial", 99)
    irrelevant_target = FileIdentity("target-serial", 199)
    rows = (
        ("z-source.bin", shared_source, "z-target.bin", shared_target, 1, 1),
        ("a-source.bin", shared_source, "a-target.bin", shared_target, 1, 1),
        ("linked.bin", linked_source, "linked-old.bin", linked_target, 2, 2),
        ("irrelevant-a.bin", irrelevant_source, "irrelevant-a.bin", irrelevant_target, 1, 1),
        ("irrelevant-b.bin", irrelevant_source, "irrelevant-b.bin", irrelevant_target, 1, 1),
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _insert_mapping_history(setup.recorder.path, setup, rows)
        with LedgerRepository(setup.recorder.path) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=("z-target.bin", "linked-old.bin", "a-target.bin"),
                source_identities=frozenset({shared_source, linked_source}),
                target_identities=frozenset({shared_target, linked_target}),
            )

        assert found is not None
        assert [pair.source_rel_path_key for pair in found.snapshot.pairs] == [
            "A-SOURCE.BIN",
            "LINKED.BIN",
            "Z-SOURCE.BIN",
        ]
        assert found.snapshot.disqualified_source_identities == frozenset(
            {shared_source, linked_source}
        )
        assert found.snapshot.disqualified_target_identities == frozenset(
            {shared_target, linked_target}
        )
        assert irrelevant_source not in found.snapshot.disqualified_source_identities
        assert irrelevant_target not in found.snapshot.disqualified_target_identities
    finally:
        setup.recorder.close()


def test_current_mapping_read_excludes_a_stale_nonnull_target_identity(
    tmp_path: Path,
) -> None:
    source_identity = FileIdentity("source-serial", 41)
    stored_target_identity = FileIdentity("target-serial", 51)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _insert_mapping_history(
            setup.recorder.path,
            setup,
            (("renamed.bin", source_identity, "old.bin", stored_target_identity, 1, 1),),
        )
        with LedgerRepository(setup.recorder.path) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=("old.bin",),
                source_identities=(source_identity,),
                target_identities=(FileIdentity("target-serial", 52),),
            )

        assert found is not None
        assert found.snapshot.pairs == ()
    finally:
        setup.recorder.close()


def test_current_mapping_read_skips_pair_query_for_an_empty_target_scope(
    tmp_path: Path,
) -> None:
    source_identity = FileIdentity("source-serial", 41)
    target_identity = FileIdentity("target-serial", 51)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    statements: list[str] = []
    try:
        _insert_mapping_history(
            setup.recorder.path,
            setup,
            (("renamed.bin", source_identity, "old.bin", target_identity, 1, 1),),
        )
        with LedgerRepository(
            setup.recorder.path, trace_callback=statements.append
        ) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=(),
                source_identities=(source_identity,),
                target_identities=(target_identity,),
            )

        assert found is not None
        assert found.snapshot.pairs == ()
        assert not _matching_statements(statements, _MAPPING_PAIR_QUERY)
    finally:
        setup.recorder.close()


def test_current_mapping_queries_use_target_and_identity_indexes(
    tmp_path: Path,
) -> None:
    source_identity = FileIdentity("source-serial", 41)
    target_identity = FileIdentity("target-serial", 51)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    statements: list[str] = []
    try:
        _insert_mapping_history(
            setup.recorder.path,
            setup,
            (("renamed.bin", source_identity, "old.bin", target_identity, 2, 2),),
        )
        with LedgerRepository(
            setup.recorder.path, trace_callback=statements.append
        ) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=("old.bin",),
                source_identities=(source_identity,),
                target_identities=(target_identity,),
            )
        assert found is not None

        pair_statement = _matching_statements(statements, _MAPPING_PAIR_QUERY)[0]
        identity_statement = _matching_statements(statements, _IDENTITY_QUERY)[0]
        pair_plan = _query_plan(setup.recorder.path, pair_statement)
        identity_plan = _query_plan(setup.recorder.path, identity_statement)

        assert any(
            "USING INDEX" in detail
            and "mapping_id=? AND target_inventory_id=?" in detail
            for detail in pair_plan
        )
        assert any(
            "USING COVERING INDEX" in detail
            and "location_id=? AND rel_path_key=?" in detail
            for detail in pair_plan
        )
        assert any("inventory_identity_idx" in detail for detail in identity_plan)
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    ("count", "batch_size"),
    _SUBJECT_BATCH_CASES,
)
def test_current_mapping_read_chunks_keys_and_identities_at_four_hundred(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    batch_size: int,
) -> None:
    monkeypatch.setattr(repository_module, "QUERY_SUBJECT_BATCH_SIZE", batch_size)
    parameter_calls = _capture_repository_parameters(monkeypatch)
    rows = _mapping_rows(count, descending_source_paths=True)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _insert_mapping_history(setup.recorder.path, setup, rows)
        with LedgerRepository(setup.recorder.path) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=tuple(row[2] for row in reversed(rows)),
                source_identities=frozenset(row[1] for row in rows),
                target_identities=frozenset(row[3] for row in rows if row[3] is not None),
            )

        assert found is not None
        assert [pair.source_rel_path_key for pair in found.snapshot.pairs] == sorted(
            normalize_relative_path(row[0]) for row in rows
        )
        assert {pair.target_rel_path_key for pair in found.snapshot.pairs} == {
            normalize_relative_path(row[2]) for row in rows
        }
        assert found.snapshot.disqualified_source_identities == frozenset()
        assert found.snapshot.disqualified_target_identities == frozenset()
        pair_parameters = [
            parameters
            for statement, parameters in parameter_calls
            if _MAPPING_PAIR_QUERY.search(statement)
        ]
        identity_parameters = [
            parameters
            for statement, parameters in parameter_calls
            if _IDENTITY_QUERY.search(statement)
        ]
        assert bool(pair_parameters) is bool(count)
        assert bool(identity_parameters) is bool(count)
        assert all(len(parameters) <= batch_size + 2 for parameters in pair_parameters)
        assert all(
            len(parameters) <= 2 * batch_size + 1
            and (len(parameters) - 1) % 2 == 0
            for parameters in identity_parameters
        )
    finally:
        setup.recorder.close()


def test_current_mapping_read_uses_one_snapshot_across_query_batches(
    tmp_path: Path,
) -> None:
    rows = _mapping_rows(401)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    writer = connect_ledger_writer(setup.recorder.path)
    pair_select_count = 0

    def update_between_batches(statement: str) -> None:
        nonlocal pair_select_count
        if not _MAPPING_PAIR_QUERY.search(statement):
            return
        pair_select_count += 1
        if pair_select_count == 2:
            writer.execute(
                "UPDATE inventory SET observed_nlink = 2 WHERE id = 1"
            )
            writer.commit()

    try:
        _insert_mapping_history(setup.recorder.path, setup, rows)
        source_identities = frozenset(row[1] for row in rows)
        target_identities = frozenset(row[3] for row in rows if row[3] is not None)
        with LedgerRepository(
            setup.recorder.path,
            trace_callback=update_between_batches,
        ) as repository:
            found = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=tuple(row[2] for row in rows),
                source_identities=source_identities,
                target_identities=target_identities,
            )
        assert found is not None
        assert pair_select_count >= 2
        assert found.snapshot.disqualified_source_identities == frozenset()

        with LedgerRepository(setup.recorder.path) as repository:
            current = repository.find_current_mapping(
                VolumeId("source-serial", "NTFS"),
                "source",
                VolumeId("target-serial", "NTFS"),
                "target",
                target_path_keys=tuple(row[2] for row in rows),
                source_identities=source_identities,
                target_identities=target_identities,
            )
        assert current is not None
        assert current.snapshot.disqualified_source_identities == frozenset(
            {FileIdentity("source-serial", 1)}
        )
    finally:
        writer.close()
        setup.recorder.close()


@pytest.mark.parametrize(
    ("count", "batch_size"),
    _SUBJECT_BATCH_CASES,
)
def test_large_inventory_selection_uses_bounded_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    batch_size: int,
) -> None:
    monkeypatch.setattr(repository_module, "QUERY_SUBJECT_BATCH_SIZE", batch_size)
    parameter_calls = _capture_repository_parameters(monkeypatch)
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(
        _file(f"folder\\file-{index:04d}.bin", index + 1) for index in range(count)
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            selected = repository.get_inventory(
                setup.source_location_id,
                (record.rel_path for record in reversed(records)),
            )

        assert len(selected) == count
        select_parameters = [
            parameters
            for statement, parameters in parameter_calls
            if _INVENTORY_SELECTION_QUERY.search(statement)
            and "rel_path_key IN" in statement
        ]
        assert bool(select_parameters) is bool(count)
        assert all(
            len(parameters) <= batch_size + 2
            for parameters in select_parameters
        )
        assert [row.rel_path_key for row in selected] == sorted(
            row.rel_path_key for row in selected
        )
    finally:
        setup.recorder.close()


def test_large_inventory_selection_is_one_read_snapshot(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(
        _file(f"folder\\file-{index:04d}.bin", index) for index in range(401)
    )
    writer = connect_ledger_writer(setup.recorder.path)
    select_count = 0

    def update_between_batches(statement: str) -> None:
        nonlocal select_count
        if not _INVENTORY_SELECTION_QUERY.search(statement):
            return
        select_count += 1
        if select_count == 2:
            writer.execute(
                "UPDATE inventory SET scope_token = ? WHERE location_id = ?",
                ("scope-new", setup.source_location_id),
            )
            writer.commit()

    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope-old",
                NOW,
            )
        )
        with LedgerRepository(
            setup.recorder.path, trace_callback=update_between_batches
        ) as repository:
            selected = repository.get_inventory(
                setup.source_location_id,
                (record.rel_path for record in records),
            )

        assert select_count >= 2
        assert {row.scope_token for row in selected} == {"scope-old"}
        with LedgerRepository(setup.recorder.path) as repository:
            durable = repository.get_inventory(setup.source_location_id)
        assert {row.scope_token for row in durable} == {"scope-new"}
    finally:
        writer.close()
        setup.recorder.close()


def test_readonly_repository_can_browse_during_active_writer_lifetime(tmp_path: Path) -> None:
    source = file_stat(identity_index=51)
    target = file_stat(identity_index=52, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP,
        source=source,
        target=target,
        intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((noop,)))
    try:
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_inventory(setup.target_location_id) == ()
            setup.run.record_noop(noop.op_id, source, target)
            rows = repository.get_inventory(setup.target_location_id)
            assert len(rows) == 1
            assert rows[0].observed == target
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    ("column", "corrupt_value", "error"),
    [
        pytest.param(
            "content_algorithm",
            "sha256",
            "only xxh3_128 evidence is supported",
            id="unsupported-algorithm",
        ),
        pytest.param(
            "content_size",
            8,
            "attestation content size must match its subject",
            id="content-subject-size-mismatch",
        ),
    ],
)
def test_repository_round_trips_self_describing_xxh3_and_rejects_corrupt_rows(
    tmp_path: Path,
    column: str,
    corrupt_value: str | int,
    error: str,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    record = _file("evidence.bin", 61)
    evidence = attestation(
        record.stat,
        digest_byte=0xA5,
        provenance=Provenance.READBACK_ATTESTED,
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (record,)),
                "evidence-scope",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            row = repository.get_inventory(setup.source_location_id)[0]

        command = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "baseline-evidence",
            row.row_id,
            str(setup.source_location_id),
            row.rel_path_key,
            "evidence-scope",
            InventoryState.PRESENT,
            record.stat,
            None,
            evidence,
            False,
            False,
        )
        assert (
            setup.recorder.record_integrity(command)
            is RecordDisposition.APPLIED
        )

        with LedgerRepository(setup.recorder.path) as repository:
            stored = repository.get_inventory(setup.source_location_id)[0]
        assert stored.attestation == evidence
        assert stored.attestation.content.algorithm == "xxh3_128"
        assert len(stored.attestation.content.digest) == 16

        connection = connect_ledger_writer(setup.recorder.path)
        try:
            connection.execute(
                f"UPDATE inventory SET {column} = ? WHERE id = ?",
                (corrupt_value, row.row_id),
            )
            connection.commit()
        finally:
            connection.close()

        with LedgerRepository(setup.recorder.path) as repository:
            with pytest.raises(ValueError, match=error):
                repository.get_inventory(setup.source_location_id)
    finally:
        setup.recorder.close()
