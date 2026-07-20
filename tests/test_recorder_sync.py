from __future__ import annotations

from pathlib import Path

import pytest

from namisync.core.evidence import Provenance
from namisync.core.planning import OperationKind, OperationReason
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import StaleRecordingError
from namisync.db.writer import TokenConflictError

from _db_fixtures import attestation, file_stat, operation, plan, setup_recorder


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
