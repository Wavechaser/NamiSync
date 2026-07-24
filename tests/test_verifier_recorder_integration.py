"""Cross-layer integrity evidence transaction regression tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from xxhash import xxh3_128

import namisync.modules.executor as executor_module
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Provenance,
    RecordingStatus,
)
from namisync.core.integrity import (
    IntegrityReason,
    IntegrityResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    ReadStrategy,
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
from namisync.core.planning import OperationKind
from namisync.core.recording import InventoryCommand
from namisync.core.session import RunContext
from namisync.db.connections import connect_ledger_reader, connect_ledger_writer
from namisync.modules.executor import NativeCopyBackend, NativeFileSystem
from namisync.modules.verifier import WindowsUnbufferedReader, verify

from _db_fixtures import NOW, operation, plan, setup_recorder


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


@pytest.mark.skipif(os.name != "nt", reason="Windows copy/verify integration")
def test_copy_record_then_unbuffered_verify_round_trips_one_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    relative_path = "payload.bin"
    source_path = source_root / relative_path
    target_path = target_root / relative_path
    temp_path = target_root / "payload.bin.roundtrip.tmp"
    payload = b"NamiSync copy-to-verify XXH3 round trip"
    source_path.write_bytes(payload)
    source_open_flags: list[int] = []
    real_open = executor_module.os.open

    def recording_open(path_value, flags, *args):
        if Path(path_value) == source_path:
            source_open_flags.append(flags)
        return real_open(path_value, flags, *args)

    monkeypatch.setattr(executor_module.os, "open", recording_open)
    filesystem = NativeFileSystem()
    source_stat = filesystem.stat_path(source_path)
    assert source_stat is not None
    factory = xxh3_128
    backend = NativeCopyBackend(hasher_factory=factory)
    with filesystem.open_source(source_path) as source, filesystem.create_temp(
        temp_path, allocation_size=None
    ) as target:
        copied = backend.copy(
            source,
            target,
            chunk_size=256 * 1024,
            checkpoint=lambda: None,
            on_chunk=lambda _size: None,
        )
    finalized = filesystem.finalize_temp(
        temp_path,
        source_stat,
        preserve_created=True,
        acl_source=None,
    )
    filesystem.publish_new(temp_path, target_path)
    published = filesystem.ensure_published_metadata(
        target_path,
        finalized,
        source_stat,
        preserve_created=True,
        apply_readonly=True,
    )
    filesystem.flush_directory(target_root)
    assert source_open_flags and source_open_flags[0] & os.O_SEQUENTIAL

    copy_operation = operation(
        OperationKind.COPY,
        source_path=relative_path,
        target_path=relative_path,
        source=source_stat,
        target=None,
        intended=published,
    )
    setup = setup_recorder(
        tmp_path / "ledger.db", plan((copy_operation,))
    )
    copied_attestation = Attestation(
        ContentEvidence(
            "xxh3_128",
            copied.digest,
            copied.size,
            Provenance.COPY_ATTESTED,
            NOW,
        ),
        published,
    )
    try:
        setup.run.record_copied(copy_operation.op_id, copied_attestation)
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            before = connection.execute(
                """SELECT * FROM inventory
                    WHERE location_id = ? AND rel_path_key = ?""",
                (
                    setup.target_location_id,
                    normalize_relative_path(relative_path),
                ),
            ).fetchone()
        finally:
            connection.close()
        assert bytes(before["content_digest"]) == copied.digest
        assert before["last_verified_at"] is None

        item = IntegritySelectionItem(
            item_id="copy-roundtrip",
            row_id=str(before["id"]),
            location_id=str(setup.target_location_id),
            root=target_root,
            rel_path_key=normalize_relative_path(relative_path),
            display_path=relative_path,
            expected_state=InventoryState.PRESENT,
            expected_stat=published,
            baseline=copied_attestation,
            scope_token=str(before["scope_token"]),
        )
        context = VerifierContext(
            run=RunContext(lambda _event: None, lambda: None),
            clock=_Clock(),
            hasher_factory=factory,
        )
        assert backend._hasher_factory is context.hasher_factory is factory

        result = verify(
            IntegritySelection((item,)),
            context,
            setup.recorder,
            WindowsUnbufferedReader(),
        )

        assert result.outcomes[0].result is IntegrityResult.VERIFIED
        assert (
            result.outcomes[0].read_strategy
            is ReadStrategy.WINDOWS_UNBUFFERED
        )
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            after = connection.execute(
                "SELECT * FROM inventory WHERE id = ?",
                (before["id"],),
            ).fetchone()
        finally:
            connection.close()
        assert bytes(after["content_digest"]) == copied.digest
        assert after["hash_provenance"] == Provenance.VERIFY_ATTESTED.value
        assert after["last_verified_at"] == "2026-01-02T03:04:05.123456Z"
    finally:
        setup.recorder.close()


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
            hasher_factory=xxh3_128,
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

