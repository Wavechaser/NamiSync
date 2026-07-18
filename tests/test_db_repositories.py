from __future__ import annotations

from pathlib import Path

from namisync.core.planning import OperationKind, OperationReason
from namisync.core.recording import InventoryCommand
from namisync.db.repositories import LedgerRepository

from _db_fixtures import NOW, file_stat, operation, plan, setup_recorder
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
