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
from namisync.core.planning import OperationKind, OperationReason
from namisync.core.recording import InventoryCommand
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import StaleRecordingError, _payload_hash
from namisync.db.writer import TokenConflictError

from _db_fixtures import (
    NOW,
    attestation,
    file_stat,
    operation,
    plan,
    setup_recorder,
)


def _target_scan(sync_plan, records: tuple[FileRecord, ...]) -> ScanResult:
    return ScanResult(
        sync_plan.target_root,
        sync_plan.target_volume_id,
        VolumeEvidence("Target", "D:"),
        sync_plan.target_profile,
        records,
        (),
        (),
        (),
        IgnoreSet(),
        ScanScope.full(),
        True,
    )


def _record(path: str, stat) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        stat.size,
        stat.mtime_ns,
        stat.file_identity,
        stat.nlink,
        stat.metadata,
    )


def _seed_verified_target(setup, sync_plan, path: str, stat):
    scope_token = "verified-target"
    setup.recorder.record_inventory(
        InventoryCommand(
            setup.target_location_id,
            setup.host_id,
            _target_scan(sync_plan, (_record(path, stat),)),
            scope_token,
            NOW,
        )
    )
    connection = connect_ledger_reader(setup.recorder.path)
    try:
        row_id = str(
            connection.execute(
                """SELECT id FROM inventory
                     WHERE location_id = ? AND rel_path_key = ?""",
                (setup.target_location_id, normalize_relative_path(path)),
            ).fetchone()[0]
        )
    finally:
        connection.close()

    baseline = attestation(
        stat,
        digest_byte=7,
        provenance=Provenance.READBACK_ATTESTED,
    )
    baseline_command = IntegrityRecordCommand(
        IntegrityMode.BASELINE,
        f"baseline-{path}",
        row_id,
        str(setup.target_location_id),
        normalize_relative_path(path),
        scope_token,
        InventoryState.PRESENT,
        stat,
        None,
        baseline,
        False,
        False,
    )
    assert (
        setup.recorder.record_integrity(baseline_command)
        is RecordDisposition.APPLIED
    )
    verified = attestation(
        stat,
        digest_byte=7,
        provenance=Provenance.VERIFY_ATTESTED,
    )
    verify_command = replace(
        baseline_command,
        mode=IntegrityMode.VERIFY,
        item_id=f"verify-{path}",
        expected_baseline=baseline,
        attestation=verified,
        advances_last_verified=True,
    )
    assert (
        setup.recorder.record_integrity(verify_command)
        is RecordDisposition.APPLIED
    )
    return row_id, verified


def test_recorder_payload_hash_escapes_unpaired_surrogates_defensively() -> None:
    assert len(_payload_hash({"detail": "bad_\udcff"})) == 32


def test_copy_records_only_attested_target_evidence_and_is_idempotent(tmp_path: Path) -> None:
    source = file_stat(identity_index=1)
    published = file_stat(
        identity_index=2, volume_serial="target-serial"
    )
    copy = operation(
        OperationKind.COPY,
        source=source,
        target=None,
        intended=published,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    evidence = attestation(published)
    try:
        setup.run.record_copied(copy.op_id, evidence)
        setup.run.record_copied(copy.op_id, evidence)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            rows = connection.execute(
                "SELECT * FROM inventory ORDER BY location_id"
            ).fetchall()
            assert len(rows) == 2
            target = rows[1]
            assert bytes(target["content_digest"]) == evidence.content.digest
            assert target["hash_provenance"] == Provenance.COPY_ATTESTED.value
            assert target["attested_file_identity_volume_serial"] == "target-serial"
            assert target["last_verified_at"] is None
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    "kind",
    [OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE],
)
def test_copy_producing_records_clear_prior_verification_freshness(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source = file_stat(size=9, identity_index=30)
    old_target = file_stat(
        size=7,
        identity_index=40,
        volume_serial="target-serial",
    )
    published = file_stat(
        size=9,
        identity_index=41,
        volume_serial="target-serial",
    )
    if kind is OperationKind.COPY:
        prior_path = target_path = "a.txt"
        planned = operation(
            kind,
            source=source,
            target=None,
            intended=published,
        )
    elif kind is OperationKind.UPDATE:
        prior_path = target_path = "a.txt"
        planned = operation(
            kind,
            source=source,
            target=old_target,
            intended=published,
        )
    else:
        prior_path = "old.txt"
        target_path = "new.txt"
        planned = replace(
            operation(
                kind,
                source_path=target_path,
                target_path=target_path,
                source=source,
                target=old_target,
                intended=published,
                prior_target_path=prior_path,
            ),
            target_expected=None,
        )
    sync_plan = plan((planned,))
    setup = setup_recorder(tmp_path / f"{kind.value}.db", sync_plan)
    try:
        _seed_verified_target(setup, sync_plan, prior_path, old_target)
        if kind is OperationKind.COPY:
            setup.recorder.record_inventory(
                InventoryCommand(
                    setup.target_location_id,
                    setup.host_id,
                    _target_scan(sync_plan, ()),
                    "target-missing",
                    NOW,
                )
            )

        copied = attestation(
            published,
            digest_byte=9,
            provenance=Provenance.COPY_ATTESTED,
        )
        if kind is OperationKind.COPY:
            setup.run.record_copied(planned.op_id, copied)
        elif kind is OperationKind.UPDATE:
            setup.run.record_updated(planned.op_id, copied)
        else:
            setup.run.record_move_updated(planned.op_id, copied)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row = connection.execute(
                """SELECT content_digest, hash_provenance, last_verified_at
                     FROM inventory
                    WHERE location_id = ? AND rel_path_key = ?""",
                (
                    setup.target_location_id,
                    normalize_relative_path(target_path),
                ),
            ).fetchone()
        finally:
            connection.close()

        assert bytes(row["content_digest"]) == copied.content.digest
        assert row["hash_provenance"] == Provenance.COPY_ATTESTED.value
        assert row["last_verified_at"] is None
    finally:
        setup.recorder.close()


def test_rebaseline_clears_freshness_even_when_evidence_is_identical(
    tmp_path: Path,
) -> None:
    sync_plan = plan(())
    setup = setup_recorder(tmp_path / "rebaseline.db", sync_plan)
    target = file_stat(identity_index=50, volume_serial="target-serial")
    try:
        row_id, verified = _seed_verified_target(
            setup, sync_plan, "a.txt", target
        )
        command = IntegrityRecordCommand(
            IntegrityMode.REBASELINE,
            "rebaseline-1",
            row_id,
            str(setup.target_location_id),
            normalize_relative_path("a.txt"),
            "verified-target",
            InventoryState.PRESENT,
            target,
            verified,
            verified,
            False,
            False,
        )

        assert (
            setup.recorder.record_integrity(command)
            is RecordDisposition.APPLIED
        )
        assert (
            setup.recorder.record_integrity(
                replace(command, item_id="rebaseline-2")
            )
            is RecordDisposition.NOOP
        )
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute(
                "SELECT last_verified_at FROM inventory WHERE id = ?",
                (row_id,),
            ).fetchone()[0] is None
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_operation_token_reuse_with_different_evidence_is_rejected(tmp_path: Path) -> None:
    source = file_stat()
    published = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=source, intended=published)
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    try:
        setup.run.record_copied(copy.op_id, attestation(published, digest_byte=1))
        with pytest.raises(TokenConflictError):
            setup.run.record_copied(copy.op_id, attestation(published, digest_byte=2))
    finally:
        setup.recorder.close()


def test_noop_requires_both_live_snapshots_and_persists_correspondence(tmp_path: Path) -> None:
    source = file_stat(identity_index=5)
    target = file_stat(identity_index=6, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP,
        source=source,
        target=target,
        intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((noop,)))
    try:
        with pytest.raises(StaleRecordingError):
            setup.run.record_noop(
                noop.op_id,
                file_stat(size=source.size + 1, identity_index=5),
                target,
            )
        setup.run.record_noop(noop.op_id, source, target)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            correspondence = connection.execute(
                "SELECT * FROM mapping_correspondence"
            ).fetchall()
            assert len(correspondence) == 1
            assert correspondence[0]["source_identity_file_index"] == 5
            assert correspondence[0]["target_identity_file_index"] == 6
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        setup.recorder.close()
