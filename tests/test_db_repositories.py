from __future__ import annotations

from pathlib import Path

import pytest

from namisync.core.evidence import Provenance
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
)
from namisync.core.planning import OperationKind, OperationReason
from namisync.core.recording import InventoryCommand
from namisync.db.connections import connect_ledger_writer
from namisync.db.repositories import LedgerRepository

from _db_fixtures import (
    NOW,
    attestation,
    file_stat,
    operation,
    plan,
    setup_recorder,
)
from test_recorder_inventory_integrity import _file, _scan


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


def test_large_inventory_selection_uses_bounded_queries(tmp_path: Path) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    records = tuple(_file(f"folder\\file-{index:04d}.bin", index) for index in range(1_001))
    statements: list[str] = []
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
        with LedgerRepository(
            setup.recorder.path, trace_callback=statements.append
        ) as repository:
            selected = repository.get_inventory(
                setup.source_location_id,
                (record.rel_path for record in reversed(records)),
            )

        selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT * FROM INVENTORY")
        ]
        assert len(selected) == 1_001
        assert len(selects) == 3
        assert [row.rel_path_key for row in selected] == sorted(
            row.rel_path_key for row in selected
        )
    finally:
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
