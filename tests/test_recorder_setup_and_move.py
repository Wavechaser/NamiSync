from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from namisync.core.models import (
    FileIdentity,
    FileRecord,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind, OperationReason, selection_digest
from namisync.core.recording import (
    LocationCommand,
    MappingCommand,
    SyncRunCommand,
    VolumeCommand,
)
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import (
    AmbiguousVolumeError,
    LedgerRecorder,
    MappingValidationError,
    StaleRecordingError,
    VolumeRebindRequired,
)
from namisync.db.writer import TokenConflictError
from namisync.core.recording import InventoryCommand

from _db_fixtures import FakeClock, NOW, file_stat, operation, plan, setup_recorder


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
        ScanScope.full(),
        True,
    )


def test_volume_relabel_preserves_identity_but_filesystem_change_requires_rebind(
    tmp_path: Path,
) -> None:
    recorder = LedgerRecorder(tmp_path / "ledger.db", clock=FakeClock())
    try:
        first = recorder.observe_volume(
            VolumeCommand(VolumeId("serial", "NTFS"), VolumeEvidence("First", "C:"), NOW)
        )
        relabeled = recorder.observe_volume(
            VolumeCommand(VolumeId("serial", "NTFS"), VolumeEvidence("Second", "Q:"), NOW)
        )
        assert relabeled == first

        with pytest.raises(VolumeRebindRequired):
            recorder.observe_volume(
                VolumeCommand(VolumeId("serial", "exFAT"), VolumeEvidence("Second"), NOW)
            )
        with pytest.raises(AmbiguousVolumeError):
            recorder.observe_volume(
                VolumeCommand(
                    VolumeId("clone", "NTFS"),
                    VolumeEvidence("Clone", clone_ambiguous=True),
                    NOW,
                )
            )

        connection = connect_ledger_reader(recorder.path)
        try:
            row = connection.execute("SELECT * FROM volumes WHERE id = ?", (first,)).fetchone()
            assert row["label"] == "Second"
            assert row["device_id"] == "Q:"
            assert connection.execute("SELECT count(*) FROM volumes").fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        recorder.close()


def test_mapping_rejects_nested_roots_on_one_physical_volume(tmp_path: Path) -> None:
    recorder = LedgerRecorder(tmp_path / "ledger.db", clock=FakeClock())
    try:
        volume = recorder.observe_volume(
            VolumeCommand(VolumeId("serial", "NTFS"), VolumeEvidence(), NOW)
        )
        outer = recorder.ensure_location(LocationCommand(volume, "data", NOW))
        inner = recorder.ensure_location(LocationCommand(volume, "data\\nested", NOW))
        with pytest.raises(MappingValidationError):
            recorder.ensure_mapping(MappingCommand(outer, inner, NOW))
    finally:
        recorder.close()


def test_run_context_reports_missing_joined_location_as_mapping_error(
    tmp_path: Path,
) -> None:
    database = tmp_path / "ledger.db"
    source = file_stat()
    target = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=source, intended=target)
    sync_plan = plan((copy,))
    setup = setup_recorder(database, sync_plan)
    setup.recorder.close()

    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "DELETE FROM locations WHERE id = ?",
            (setup.source_location_id,),
        )
        connection.commit()
    finally:
        connection.close()

    recorder = LedgerRecorder(database, clock=FakeClock())
    selection = frozenset({copy.op_id})
    command = SyncRunCommand(
        "b" * 32,
        setup.host_id,
        setup.mapping_id,
        setup.source_location_id,
        setup.target_location_id,
        sync_plan,
        selection,
        selection_digest(selection),
        NOW,
    )
    try:
        with pytest.raises(MappingValidationError, match="location is unavailable"):
            recorder.begin_sync_run(command)
    finally:
        recorder.close()

    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            "SELECT count(*) FROM runs WHERE run_token = ?",
            (command.run_token,),
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_run_token_is_idempotent_and_conflicting_selection_is_rejected(tmp_path: Path) -> None:
    source = file_stat()
    target = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(OperationKind.COPY, source=source, intended=target)
    sync_plan = plan((copy,))
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    try:
        selected = frozenset({copy.op_id})
        same = SyncRunCommand(
            setup.run_token,
            setup.host_id,
            setup.mapping_id,
            setup.source_location_id,
            setup.target_location_id,
            sync_plan,
            selected,
            selection_digest(selected),
            NOW,
        )
        setup.recorder.begin_sync_run(same)

        empty = frozenset()
        conflict = replace(
            same,
            selection=empty,
            selection_digest=selection_digest(empty),
        )
        with pytest.raises(TokenConflictError):
            setup.recorder.begin_sync_run(conflict)
    finally:
        setup.recorder.close()


def test_move_reconciles_retained_missing_destination_without_rolling_back_prior_write(
    tmp_path: Path,
) -> None:
    stable_source = file_stat(identity_index=10)
    stable_target = file_stat(identity_index=11, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP,
        source_path="stable.txt",
        target_path="stable.txt",
        source=stable_source,
        target=stable_target,
        intended=stable_target,
        reason=OperationReason.METADATA_MATCH,
    )
    moving_source = file_stat(identity_index=20)
    moving_target = file_stat(identity_index=21, volume_serial="target-serial")
    move = operation(
        OperationKind.MOVE,
        source_path="new.txt",
        target_path="new.txt",
        source=moving_source,
        target=moving_target,
        intended=moving_target,
        prior_target_path="old.txt",
        reason=OperationReason.IDENTITY_RENAME,
    )
    move = replace(move, target_expected=None, prior_target_expected=moving_target)
    sync_plan = plan((noop, move))
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    collision = file_stat(identity_index=99, volume_serial="target-serial")
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                _target_scan(
                    sync_plan,
                    (_record("old.txt", moving_target), _record("new.txt", collision)),
                ),
                "target-1",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                _target_scan(sync_plan, (_record("old.txt", moving_target),)),
                "target-2",
                NOW,
            )
        )
        setup.run.record_noop(noop.op_id, stable_source, stable_target)
        setup.run.record_moved(move.op_id, moving_target)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            moved = connection.execute(
                """SELECT rel_path, presence, file_identity_file_index
                     FROM inventory WHERE location_id = ? AND rel_path_key = 'NEW.TXT'""",
                (setup.target_location_id,),
            ).fetchall()
            assert [tuple(row) for row in moved] == [("new.txt", "present", 21)]
            assert connection.execute(
                "SELECT count(*) FROM inventory WHERE location_id = ? AND rel_path_key = 'OLD.TXT'",
                (setup.target_location_id,),
            ).fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 2
            assert connection.execute(
                "SELECT count(*) FROM mapping_correspondence WHERE mapping_id = ?",
                (setup.mapping_id,),
            ).fetchone()[0] == 2
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_move_records_reviewed_target_within_timestamp_granularity(
    tmp_path: Path,
) -> None:
    source = file_stat(mtime_ns=12, identity_index=20)
    reviewed_target = file_stat(
        mtime_ns=11,
        identity_index=21,
        volume_serial="target-serial",
    )
    move = operation(
        OperationKind.MOVE,
        source_path="new.txt",
        target_path="new.txt",
        source=source,
        target=reviewed_target,
        intended=source,
        prior_target_path="old.txt",
        reason=OperationReason.IDENTITY_RENAME,
    )
    move = replace(move, target_expected=None)
    sync_plan = plan((move,))
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                _target_scan(
                    sync_plan,
                    (_record("old.txt", reviewed_target),),
                ),
                "target-1",
                NOW,
            )
        )

        setup.run.record_moved(move.op_id, reviewed_target)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            recorded = connection.execute(
                """SELECT rel_path, observed_mtime_ns
                     FROM inventory
                    WHERE location_id = ? AND rel_path_key = 'NEW.TXT'""",
                (setup.target_location_id,),
            ).fetchone()
            assert tuple(recorded) == ("new.txt", 11)
            assert connection.execute(
                "SELECT count(*) FROM mapping_correspondence"
            ).fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_recase_updates_target_spelling_and_correspondence(tmp_path: Path) -> None:
    source = file_stat(identity_index=20)
    target = file_stat(identity_index=21, volume_serial="target-serial")
    recase = operation(
        OperationKind.RECASE,
        source_path="KEEP.txt",
        target_path="KEEP.txt",
        source=source,
        target=target,
        intended=target,
        prior_target_path="keep.txt",
        reason=OperationReason.CASE_MISMATCH,
    )
    sync_plan = plan((recase,))
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                _target_scan(sync_plan, (_record("keep.txt", target),)),
                "target-1",
                NOW,
            )
        )

        setup.run.record_recased(recase.op_id, target)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            target_row = connection.execute(
                "SELECT rel_path FROM inventory WHERE location_id = ? AND rel_path_key = 'KEEP.TXT'",
                (setup.target_location_id,),
            ).fetchone()
            assert target_row["rel_path"] == "KEEP.txt"
            assert connection.execute(
                "SELECT kind FROM operations"
            ).fetchone()["kind"] == OperationKind.RECASE.value
            assert connection.execute(
                "SELECT count(*) FROM mapping_correspondence WHERE mapping_id = ?",
                (setup.mapping_id,),
            ).fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    ("kind", "source_path", "old_path", "new_path", "reason"),
    (
        (
            OperationKind.MOVE,
            "new.txt",
            "old.txt",
            "new.txt",
            OperationReason.IDENTITY_RENAME,
        ),
        (
            OperationKind.RECASE,
            "KEEP.txt",
            "keep.txt",
            "KEEP.txt",
            OperationReason.CASE_MISMATCH,
        ),
    ),
    ids=("move", "recase"),
)
def test_pure_rename_recording_rejects_substituted_post_rename_identity(
    tmp_path: Path,
    kind: OperationKind,
    source_path: str,
    old_path: str,
    new_path: str,
    reason: OperationReason,
) -> None:
    source = file_stat(identity_index=20)
    reviewed_target = file_stat(
        identity_index=21,
        volume_serial="target-serial",
    )
    rename = operation(
        kind,
        source_path=source_path,
        target_path=new_path,
        source=source,
        target=reviewed_target,
        intended=reviewed_target,
        prior_target_path=old_path,
        reason=reason,
    )
    if kind is OperationKind.MOVE:
        rename = replace(rename, target_expected=None)
    sync_plan = plan((rename,))
    setup = setup_recorder(tmp_path / "ledger.db", sync_plan)
    substituted = replace(
        reviewed_target,
        file_identity=FileIdentity("target-serial", 99),
    )
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.target_location_id,
                setup.host_id,
                _target_scan(
                    sync_plan,
                    (_record(old_path, reviewed_target),),
                ),
                "target-1",
                NOW,
            )
        )

        record = (
            setup.run.record_moved
            if kind is OperationKind.MOVE
            else setup.run.record_recased
        )
        with pytest.raises(
            StaleRecordingError,
            match="reviewed target version",
        ):
            record(rename.op_id, substituted)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            rows = connection.execute(
                """SELECT rel_path, file_identity_file_index
                     FROM inventory WHERE location_id = ?""",
                (setup.target_location_id,),
            ).fetchall()
            assert [tuple(row) for row in rows] == [(old_path, 21)]
            assert connection.execute(
                "SELECT count(*) FROM operations"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM mapping_correspondence"
            ).fetchone()[0] == 0
        finally:
            connection.close()
    finally:
        setup.recorder.close()
