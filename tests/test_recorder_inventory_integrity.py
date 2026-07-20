from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
from namisync.core.recording import InventoryCommand
from namisync.db.connections import connect_ledger_reader

from _db_fixtures import NOW, attestation, file_stat, plan, setup_recorder


def _scan(setup, records: tuple[FileRecord, ...], *, complete: bool = True) -> ScanResult:
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
        scope=ScanScope.full(),
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
            assert evidence == {"A.TXT": "sha256", "B.TXT": None}
        finally:
            connection.close()
    finally:
        setup.recorder.close()
