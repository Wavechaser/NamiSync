"""Cross-layer integrity evidence transaction regression tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.integrity import (
    IntegrityReason,
    IntegrityResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    VerifierContext,
)
from namisync.core.models import (
    CapabilityProfile,
    FileRecord,
    IgnoreSet,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.recording import InventoryCommand
from namisync.core.session import RunContext
from namisync.db.connections import connect_ledger_reader, connect_ledger_writer
from namisync.modules.verifier import WindowsUnbufferedReader, verify

from _db_fixtures import NOW, plan, setup_recorder


class _Clock:
    def now(self) -> datetime:
        return NOW


def _scan(
    root: Root,
    volume_id: VolumeId,
    record: FileRecord | None,
) -> ScanResult:
    return ScanResult(
        root=root,
        volume_id=volume_id,
        volume_evidence=VolumeEvidence("Source", root.path),
        profile=CapabilityProfile("NTFS", 100, True, False, 32767, True, True),
        files=() if record is None else (record,),
        directories=(),
        unsupported=(),
        warnings=(),
        ignore_snapshot=IgnoreSet(),
        scope=ScanScope.full(),
        complete=True,
    )


def _row(path: Path, rel_path_key: str):
    connection = connect_ledger_reader(path)
    try:
        return connection.execute(
            "SELECT * FROM inventory WHERE rel_path_key = ?", (rel_path_key,)
        ).fetchone()
    finally:
        connection.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows unbuffered verifier integration")
def test_reappeared_baseline_and_clear_are_atomic_across_recorder_rollback(
    tmp_path: Path,
) -> None:
    payload = b"atomic integrity evidence"
    managed_root = tmp_path / "managed"
    managed_root.mkdir()
    relative_path = "payload.bin"
    (managed_root / relative_path).write_bytes(payload)

    reader = WindowsUnbufferedReader()
    with reader.open(managed_root, relative_path) as stream:
        expected = stream.stat()

    root = Root(str(managed_root), "integrity-root")
    key = normalize_relative_path(relative_path)
    record = FileRecord(
        rel_path=relative_path,
        rel_path_key=key,
        size=expected.size,
        mtime_ns=expected.mtime_ns,
        file_identity=expected.file_identity,
        nlink=expected.nlink,
        metadata=expected.metadata,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(root, VolumeId("source-serial", "NTFS"), record),
                "scope-present",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(root, VolumeId("source-serial", "NTFS"), None),
                "scope-missing",
                NOW,
            )
        )
        setup.recorder.record_inventory(
            InventoryCommand(
                setup.source_location_id,
                setup.host_id,
                _scan(root, VolumeId("source-serial", "NTFS"), record),
                "scope-reappeared",
                NOW,
            )
        )

        before = _row(setup.recorder.path, key)
        assert before is not None
        assert before["content_digest"] is None
        assert before["reappeared_at"] is not None

        item = IntegritySelectionItem(
            item_id="item-reappeared",
            row_id=str(before["id"]),
            location_id=str(setup.source_location_id),
            root=managed_root,
            rel_path_key=key,
            display_path=relative_path,
            expected_state=InventoryState.PRESENT,
            expected_stat=expected,
            baseline=None,
            scope_token="scope-reappeared",
            reappeared_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        context = VerifierContext(
            run=RunContext(emit=lambda event: None, checkpoint=lambda: None),
            clock=_Clock(),
        )

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute(
                """CREATE TRIGGER fail_integrity_update
                   BEFORE UPDATE OF content_digest ON inventory
                   BEGIN SELECT RAISE(ABORT, 'forced integrity rollback'); END"""
            )
        finally:
            writer.close()

        failed = verify(
            IntegritySelection((item,)), context, setup.recorder, reader
        )
        assert failed.outcomes[0].result is IntegrityResult.BASELINED
        assert failed.outcomes[0].reason is IntegrityReason.RECORDING_ERROR
        assert failed.recording is RecordingStatus.DEGRADED

        rolled_back = _row(setup.recorder.path, key)
        assert rolled_back["content_digest"] is None
        assert rolled_back["reappeared_at"] == before["reappeared_at"]

        writer = connect_ledger_writer(setup.recorder.path)
        try:
            writer.execute("DROP TRIGGER fail_integrity_update")
        finally:
            writer.close()

        applied = verify(
            IntegritySelection((item,)), context, setup.recorder, reader
        )
        assert applied.outcomes[0].result is IntegrityResult.BASELINED
        assert applied.recording is RecordingStatus.OK

        committed = _row(setup.recorder.path, key)
        assert bytes(committed["content_digest"]) != b""
        assert committed["reappeared_at"] is None
        assert committed["last_verified_at"] is None
    finally:
        setup.recorder.close()

