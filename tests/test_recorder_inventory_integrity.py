from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from namisync.core.evidence import Provenance
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
)
from namisync.core.models import (
    FileRecord,
    IgnoreSet,
    ScanResult,
    ScanScope,
    VolumeEvidence,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import FilterSet
from namisync.core.recording import (
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
    LocationCommand,
    MappingCommand,
    MappingFilterCommand,
    MappingFilterEvaluation,
    VolumeCommand,
)
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import MappingValidationError, StaleRecordingError
from namisync.db.repositories import LedgerRepository

from _db_fixtures import NOW, attestation, file_stat, plan, setup_recorder


def _scan(
    setup,
    records: tuple[FileRecord, ...],
    *,
    complete: bool = True,
    scope: ScanScope | None = None,
) -> ScanResult:
    sync_plan = plan(())
    return ScanResult(
        root=sync_plan.source_root,
        volume_id=sync_plan.source_volume_id,
        volume_evidence=VolumeEvidence("Source", "C:"),
        profile=sync_plan.source_profile,
        files=records,
        directories=(),
        unsupported=(),
        warnings=(),
        ignore_snapshot=IgnoreSet(),
        scope=scope or ScanScope.full(),
        complete=complete,
    )


def _file(path: str, index: int, *, size: int = 7) -> FileRecord:
    stat = file_stat(size=size, identity_index=index)
    return FileRecord(
        path,
        normalize_relative_path(path),
        stat.size,
        stat.mtime_ns,
        stat.file_identity,
        stat.nlink,
        stat.metadata,
    )


def test_complete_inventory_over_33k_marks_missing_without_parameter_overflow(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(_file(f"folder\\file-{index:05d}.bin", index) for index in range(33_010))
    try:
        first = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "scope-1",
                NOW,
            )
        )
        assert first.disposition is RecordDisposition.APPLIED
        assert first.observed_count == 33_010
        assert first.missing_count == 0

        second = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records[:1]),
                "scope-2",
                NOW,
            )
        )
        assert second.missing_count == 33_009

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            counts = dict(
                connection.execute(
                    "SELECT presence, count(*) FROM inventory GROUP BY presence"
                ).fetchall()
            )
            assert counts == {"missing": 33_009, "present": 1}
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_incomplete_and_offline_inventory_never_infer_missing(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = (_file("a.txt", 1), _file("b.txt", 2))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records),
                "complete",
                NOW,
            )
        )
        incomplete = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, records[:1], complete=False),
                "incomplete",
                NOW,
            )
        )
        offline = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "offline",
                NOW,
                online=False,
            )
        )
        assert incomplete.missing_count == 0
        assert offline.disposition is RecordDisposition.NOOP

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute(
                "SELECT count(*) FROM inventory WHERE presence = 'present'"
            ).fetchone()[0] == 2
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_selected_inventory_reconciles_only_its_complete_scope(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    seeded = tuple(_file(f"{name}.txt", index) for index, name in enumerate("ABCD", 1))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, seeded),
                "seed",
                NOW,
            )
        )
        selected = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(
                    setup,
                    (seeded[0],),
                    scope=ScanScope.selected(("A.txt", "B.txt")),
                ),
                "selected",
                NOW,
            )
        )
        interrupted = setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(
                    setup,
                    (),
                    complete=False,
                    scope=ScanScope.selected(("C.txt", "D.txt")),
                ),
                "interrupted",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            rows = {
                row.rel_path: row.presence.value
                for row in repository.get_inventory(setup.source_location_id)
            }

        assert selected.missing_count == 1
        assert interrupted.missing_count == 0
        assert rows == {
            "A.txt": "present",
            "B.txt": "missing",
            "C.txt": "present",
            "D.txt": "present",
        }
    finally:
        setup.recorder.close()


def test_missing_acknowledgement_and_restore_preserve_inventory_evidence(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    row = _file("missing.txt", 1)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (row,)),
                "present",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, ()),
                "missing",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            missing = repository.get_unacknowledged_missing(
                setup.source_location_id
            )[0]

        assert setup.recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                "ack-1",
                setup.source_location_id,
                missing.row_id,
                InventoryVisibilityAction.ACKNOWLEDGE,
                NOW,
            )
        ) is RecordDisposition.APPLIED
        with LedgerRepository(setup.recorder.path) as repository:
            assert repository.get_unacknowledged_missing(
                setup.source_location_id
            ) == ()
            acknowledged = repository.get_inventory(
                setup.source_location_id
            )[0]
        assert acknowledged.observed == row.stat

        assert setup.recorder.change_inventory_visibility(
            InventoryVisibilityCommand(
                "restore-1",
                setup.source_location_id,
                missing.row_id,
                InventoryVisibilityAction.RESTORE,
                NOW,
            )
        ) is RecordDisposition.APPLIED
        with LedgerRepository(setup.recorder.path) as repository:
            restored = repository.get_unacknowledged_missing(
                setup.source_location_id
            )[0]
        assert restored.row_id == missing.row_id
        assert restored.observed == row.stat
    finally:
        setup.recorder.close()


def test_mapping_filter_overlay_isolated_for_shared_location_and_planner_reads(
    tmp_path: Path,
) -> None:
    sync_plan = plan(())
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    shared = _file("shared.tmp", 1)
    late = _file("late.tmp", 3)
    target_only = _file("target-only.tmp", 2)
    try:
        target_volume = setup.recorder.observe_volume(
            VolumeCommand(
                sync_plan.target_volume_id,
                VolumeEvidence("Target", "D:"),
                NOW,
            )
        )
        second_target = setup.recorder.ensure_location(
            LocationCommand(target_volume, "second-target", NOW)
        )
        second_mapping = setup.recorder.ensure_mapping(
            MappingCommand(setup.source_location_id, second_target, NOW)
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (shared,)),
                "source-inventory",
                NOW,
            )
        )
        target_scan = replace(
            _scan(setup, (target_only,)),
            root=sync_plan.target_root,
            volume_id=sync_plan.target_volume_id,
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                target_scan,
                "target-inventory",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            source_row = repository.get_inventory(
                setup.source_location_id
            )[0]
            target_row = repository.get_inventory(
                setup.target_location_id
            )[0]

        filtered = FilterSet(("*.tmp",))
        setup.recorder.record_mapping_filter(
            MappingFilterCommand(
                "mapping-a-filter",
                setup.mapping_id,
                filtered,
                (
                    MappingFilterEvaluation(
                        setup.source_location_id,
                        source_row.row_id,
                        source_row.rel_path_key,
                        True,
                    ),
                    MappingFilterEvaluation(
                        setup.target_location_id,
                        target_row.row_id,
                        target_row.rel_path_key,
                        True,
                    ),
                ),
                (setup.source_location_id, setup.target_location_id),
                NOW,
            )
        )
        setup.recorder.record_mapping_filter(
            MappingFilterCommand(
                "mapping-b-filter",
                second_mapping,
                FilterSet(),
                (
                    MappingFilterEvaluation(
                        setup.source_location_id,
                        source_row.row_id,
                        source_row.rel_path_key,
                        False,
                    ),
                ),
                (setup.source_location_id, second_target),
                NOW,
            )
        )

        # A later role-free refresh updates one physical row and no mapping policy.
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (shared, late)),
                "source-refresh",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            mapping_a = repository.get_mapping_inventory(setup.mapping_id)
            mapping_b = repository.get_mapping_inventory(second_mapping)
            physical = repository.get_inventory(setup.source_location_id)

        assert len(physical) == 2
        assert all(row.presence.value == "present" for row in physical)
        assert all(row.excluded for row in mapping_a.source_rows)
        assert any(
            row.inventory.rel_path == "late.tmp"
            and row.excluded_at is None
            and row.excluded_by_filter
            and not row.projection_current
            for row in mapping_a.source_rows
        )
        assert mapping_a.planner_source_rows == ()
        assert mapping_a.planner_target_rows == ()
        assert not any(row.excluded for row in mapping_b.source_rows)
        assert mapping_b.planner_source_rows == physical

        setup.recorder.record_mapping_filter(
            MappingFilterCommand(
                "mapping-a-include-all",
                setup.mapping_id,
                FilterSet(),
                tuple(
                    MappingFilterEvaluation(
                        row.inventory.location_id,
                        row.inventory.row_id,
                        row.inventory.rel_path_key,
                        False,
                    )
                    for row in (*mapping_a.source_rows, *mapping_a.target_rows)
                ),
                (setup.source_location_id, setup.target_location_id),
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            included = repository.get_mapping_inventory(setup.mapping_id)

        assert included.planner_source_rows == physical
        assert len(included.planner_target_rows) == 1
        assert not any(row.excluded for row in included.source_rows)
        assert all(row.projection_current for row in included.source_rows)
    finally:
        setup.recorder.close()


def test_complete_mapping_filter_rejects_new_row_missing_from_evaluations(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    source = _file("source.tmp", 1)
    target = _file("target.tmp", 2)
    late = _file("late.tmp", 3)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (source,)),
                "source-before-filter",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                replace(
                    _scan(setup, (target,)),
                    root=plan(()).target_root,
                    volume_id=plan(()).target_volume_id,
                ),
                "target-before-filter",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            source_row = repository.get_inventory(setup.source_location_id)[0]
            target_row = repository.get_inventory(setup.target_location_id)[0]

        # The command was prepared, then another inventory row committed first.
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (source, late)),
                "source-raced-filter",
                NOW,
            )
        )
        evaluations = (
            MappingFilterEvaluation(
                source_row.location_id,
                source_row.row_id,
                source_row.rel_path_key,
                True,
            ),
            MappingFilterEvaluation(
                target_row.location_id,
                target_row.row_id,
                target_row.rel_path_key,
                True,
            ),
        )
        with pytest.raises(StaleRecordingError, match="does not cover"):
            setup.recorder.record_mapping_filter(
                MappingFilterCommand(
                    "raced-complete-filter",
                    setup.mapping_id,
                    FilterSet(("*.tmp",)),
                    evaluations,
                    (setup.source_location_id, setup.target_location_id),
                    NOW,
                )
            )

        with LedgerRepository(setup.recorder.path) as repository:
            snapshot = repository.get_mapping_inventory(setup.mapping_id)
        assert snapshot.filter_snapshot == FilterSet()
        assert not any(row.excluded_at for row in snapshot.source_rows)
    finally:
        setup.recorder.close()


def test_mapping_filter_projection_must_match_authoritative_filter(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (_file("excluded.tmp", 1),)),
                "filter-evaluation",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            row = repository.get_inventory(setup.source_location_id)[0]

        setup.recorder.record_mapping_filter(
            MappingFilterCommand(
                "correct-filter-evaluation",
                setup.mapping_id,
                FilterSet(("*.tmp",)),
                (
                    MappingFilterEvaluation(
                        row.location_id,
                        row.row_id,
                        row.rel_path_key,
                        True,
                    ),
                ),
                (setup.source_location_id, setup.target_location_id),
                NOW,
            )
        )
        with pytest.raises(MappingValidationError, match="disagrees"):
            setup.recorder.record_mapping_filter(
                MappingFilterCommand(
                    "wrong-filter-evaluation",
                    setup.mapping_id,
                    FilterSet(("*.tmp",)),
                    (
                        MappingFilterEvaluation(
                            row.location_id,
                            row.row_id,
                            row.rel_path_key,
                            False,
                        ),
                    ),
                    (),
                    NOW,
                )
            )
    finally:
        setup.recorder.close()


def test_mapping_inventory_reads_one_snapshot_across_concurrent_filter_commit(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    source = _file("source.tmp", 1)
    target = _file("target.tmp", 2)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (source,)),
                "snapshot-source",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                replace(
                    _scan(setup, (target,)),
                    root=plan(()).target_root,
                    volume_id=plan(()).target_volume_id,
                ),
                "snapshot-target",
                NOW,
            )
        )
        with LedgerRepository(setup.recorder.path) as repository:
            physical = (
                *repository.get_inventory(setup.source_location_id),
                *repository.get_inventory(setup.target_location_id),
            )
        evaluations = tuple(
            MappingFilterEvaluation(
                row.location_id,
                row.row_id,
                row.rel_path_key,
                True,
            )
            for row in physical
        )
        committed = False

        def commit_between_queries(statement: str) -> None:
            nonlocal committed
            if committed or "FROM mapping_filters" not in statement:
                return
            committed = True
            setup.recorder.record_mapping_filter(
                MappingFilterCommand(
                    "concurrent-filter",
                    setup.mapping_id,
                    FilterSet(("*.tmp",)),
                    evaluations,
                    (setup.source_location_id, setup.target_location_id),
                    NOW,
                )
            )

        with LedgerRepository(
            setup.recorder.path, trace_callback=commit_between_queries
        ) as repository:
            before_commit_snapshot = repository.get_mapping_inventory(
                setup.mapping_id
            )
        assert committed
        assert before_commit_snapshot.filter_snapshot == FilterSet()
        assert len(before_commit_snapshot.planner_source_rows) == 1
        assert len(before_commit_snapshot.planner_target_rows) == 1

        with LedgerRepository(setup.recorder.path) as repository:
            after_commit_snapshot = repository.get_mapping_inventory(
                setup.mapping_id
            )
        assert after_commit_snapshot.filter_snapshot == FilterSet(("*.tmp",))
        assert after_commit_snapshot.planner_source_rows == ()
        assert after_commit_snapshot.planner_target_rows == ()
    finally:
        setup.recorder.close()


def test_integrity_write_is_fully_conditional_and_advances_only_true_verification(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    record = _file("a.txt", 1)
    expected = record.stat
    baseline = attestation(
        expected, digest_byte=3, provenance=Provenance.READBACK_ATTESTED
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(setup, (record,)),
                "scope",
                NOW,
            )
        )
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row_id = str(
                connection.execute(
                    "SELECT id FROM inventory WHERE rel_path_key = 'A.TXT'"
                ).fetchone()[0]
            )
        finally:
            connection.close()

        baseline_command = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "item-baseline",
            row_id,
            str(setup.source_location_id),
            record.rel_path_key,
            "scope",
            InventoryState.PRESENT,
            expected,
            None,
            baseline,
            False,
            False,
        )
        assert setup.recorder.record_integrity(baseline_command) is RecordDisposition.APPLIED
        assert setup.recorder.record_integrity(baseline_command) is RecordDisposition.NOOP

        drifted_stats = (
            replace(expected, size=expected.size + 1),
            replace(expected, mtime_ns=expected.mtime_ns + 1),
            replace(expected, file_identity=replace(expected.file_identity, file_index=9)),
            replace(expected, nlink=2),
            replace(expected, metadata=replace(expected.metadata, attributes=2)),
            replace(expected, metadata=replace(expected.metadata, created_ns=9)),
        )
        for index, drifted in enumerate(drifted_stats):
            stale = replace(
                baseline_command,
                mode=IntegrityMode.VERIFY,
                item_id=f"stale-{index}",
                expected_stat=drifted,
                expected_baseline=baseline,
                attestation=attestation(
                    drifted,
                    digest_byte=3,
                    provenance=Provenance.VERIFY_ATTESTED,
                ),
                advances_last_verified=True,
            )
            assert setup.recorder.record_integrity(stale) is RecordDisposition.STALE

        verified = attestation(
            expected, digest_byte=3, provenance=Provenance.VERIFY_ATTESTED
        )
        verify_command = IntegrityRecordCommand(
            IntegrityMode.VERIFY,
            "item-verify",
            row_id,
            str(setup.source_location_id),
            record.rel_path_key,
            "scope",
            InventoryState.PRESENT,
            expected,
            baseline,
            verified,
            True,
            True,
        )
        assert setup.recorder.record_integrity(verify_command) is RecordDisposition.APPLIED

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row = connection.execute(
                "SELECT * FROM inventory WHERE id = ?", (row_id,)
            ).fetchone()
            assert row["hash_provenance"] == Provenance.VERIFY_ATTESTED.value
            assert row["last_verified_at"] == "2026-01-02T03:04:05.123456Z"
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_late_integrity_stale_result_preserves_earlier_committed_evidence(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = (_file("a.txt", 1), _file("b.txt", 2))
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
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            ids = {
                row["rel_path_key"]: str(row["id"])
                for row in connection.execute("SELECT id, rel_path_key FROM inventory")
            }
        finally:
            connection.close()

        first = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "first",
            ids["A.TXT"],
            str(setup.source_location_id),
            "A.TXT",
            "scope",
            InventoryState.PRESENT,
            records[0].stat,
            None,
            attestation(records[0].stat, provenance=Provenance.READBACK_ATTESTED),
            False,
            False,
        )
        stale = IntegrityRecordCommand(
            IntegrityMode.BASELINE,
            "second",
            ids["B.TXT"],
            str(setup.source_location_id),
            "B.TXT",
            "scope",
            InventoryState.PRESENT,
            replace(records[1].stat, size=999),
            None,
            attestation(
                replace(records[1].stat, size=999),
                provenance=Provenance.READBACK_ATTESTED,
            ),
            False,
            False,
        )
        assert setup.recorder.record_integrity(first) is RecordDisposition.APPLIED
        assert setup.recorder.record_integrity(stale) is RecordDisposition.STALE

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            evidence = dict(
                connection.execute(
                    "SELECT rel_path_key, content_algorithm FROM inventory"
                ).fetchall()
            )
            assert evidence == {"A.TXT": "xxh3_128", "B.TXT": None}
        finally:
            connection.close()
    finally:
        setup.recorder.close()
