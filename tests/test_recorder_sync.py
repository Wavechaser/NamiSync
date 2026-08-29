from __future__ import annotations

from dataclasses import dataclass, fields, make_dataclass, replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import pytest

import namisync.db.recorder as recorder_module
from namisync.core.evidence import Provenance, RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityRecordCommand,
    InventoryState,
    RecordDisposition,
    VerificationInvalidationCommand,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    FileRecord,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind, OperationReason, canonical_json_bytes
from namisync.core.recording import (
    InventoryCommand,
    InventoryVisibilityAction,
    InventoryVisibilityCommand,
    LocationCommand,
    SyncRunCommand,
    VolumeCommand,
)
from namisync.db.connections import connect_ledger_reader, connect_ledger_writer
from namisync.db.recorder import StaleRecordingError, _payload_hash
from namisync.db.writer import RecordingError, TokenConflictError

from _db_fixtures import (
    NOW,
    attestation,
    file_stat,
    operation,
    plan,
    setup_recorder,
)
from _identity_epoch5 import frozen_vector
from _identity_hash_fixtures import MAX_FILE_INDEX, hash_fixtures


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


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_recorder_payload_hash_rejects_surrogate_code_units(text: str) -> None:
    with pytest.raises(UnicodeEncodeError):
        _payload_hash({"detail": text})


@dataclass(frozen=True)
class _UnprojectedHashValue:
    file_index: int = MAX_FILE_INDEX


@pytest.mark.parametrize(
    "value",
    (
        pytest.param(_UnprojectedHashValue(), id="dataclass"),
        pytest.param({"nested": [_UnprojectedHashValue()]}, id="nested-dataclass"),
        pytest.param({"nested": object()}, id="unknown-type"),
        pytest.param({"nested": Path("unprojected-path")}, id="unprojected-path"),
        pytest.param({1: "value"}, id="integer-key"),
        pytest.param({"nested": {False: "value"}}, id="nested-boolean-key"),
        pytest.param({"number": float("nan")}, id="nan"),
        pytest.param({"number": float("inf")}, id="infinity"),
        pytest.param({"number": -float("inf")}, id="negative-infinity"),
    ),
)
def test_recorder_hash_refuses_unprojected_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _payload_hash(value)


def test_historical_surrogate_hash_is_distinct_but_no_longer_accepted() -> None:
    surrogate = {"text": "bad-\udcff"}
    literal = {"text": r"bad-\udcff"}
    surrogate_bytes = frozen_vector("recorder/surrogate")
    literal_bytes = frozen_vector("recorder/literal_escape")

    assert json.loads(surrogate_bytes) == surrogate
    assert json.loads(literal_bytes) == literal
    assert surrogate_bytes != literal_bytes
    assert hashlib.sha256(surrogate_bytes).digest() != hashlib.sha256(literal_bytes).digest()
    with pytest.raises(UnicodeEncodeError):
        _payload_hash(surrogate)
    assert _payload_hash(literal) == hashlib.sha256(literal_bytes).digest()


def test_inventory_receipt_hash_uses_explicit_identity_text(tmp_path: Path) -> None:
    plans, inputs = hash_fixtures(True)
    command = inputs["inventory"]
    setup = setup_recorder(tmp_path / "ledger.db", plans["two_copy"])
    expected = json.loads(frozen_vector("recorder/inventory/full128"))
    for record in (*expected["scan"]["files"], *expected["scan"]["directories"]):
        identity = record["file_identity"]
        identity["file_index"] = str(identity["file_index"])
    # The immutable old capture retains invalid diagnostic text. Derive only
    # its explicitly omitted current detail; do not regenerate historical bytes.
    assert expected["scan"]["warnings"][1]["detail"] == "bad-\udcff"
    expected["scan"]["warnings"][1]["detail"] = ""
    assert command.scan.warnings[1].detail == ""
    canonical = json.dumps(
        expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    try:
        assert setup.source_location_id == command.location_id == 1
        assert setup.host_id == command.host_id == 1
        assert setup.recorder.record_inventory(command).disposition is RecordDisposition.APPLIED
        connection = connect_ledger_reader(setup.recorder.path)
        try:
            receipt = connection.execute(
                "SELECT payload_hash FROM recording_commands WHERE command_key = ?",
                (f"inventory:{command.location_id}:{command.scope_token}",),
            ).fetchone()
            assert bytes(receipt[0]) == hashlib.sha256(canonical).digest()
        finally:
            connection.close()
    finally:
        setup.recorder.close()


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
def test_recorder_command_projections_match_frozen_fields_and_encodings(
    with_identity: bool,
) -> None:
    _, inputs = hash_fixtures(with_identity)
    commands = (
        ("start", recorder_module._sync_run_projection, SyncRunCommand(**inputs["start"])),
        ("finish", recorder_module._finish_run_projection, inputs["finish"]),
        ("inventory", recorder_module._inventory_projection, inputs["inventory"]),
        ("visibility", recorder_module._visibility_projection, inputs["visibility"]),
        ("integrity", recorder_module._integrity_projection, inputs["integrity"]),
        ("invalidation", recorder_module._verification_invalidation_projection, inputs["invalidation"]),
    )
    suffix = "full128" if with_identity else "identityless"
    for name, project, command in commands:
        old_bytes = frozen_vector(f"recorder/{name}/{suffix}")
        expected = json.loads(old_bytes)
        if name == "inventory":
            assert expected["scan"]["warnings"][1]["detail"] == "bad-\udcff"
            expected["scan"]["warnings"][1]["detail"] = ""
            assert command.scan.warnings[1].detail == ""
        if with_identity:
            # Only these explicit fields of the fixed captured DTOs carry IDs.
            if name == "start":
                stats = [
                    operation[field]
                    for operation in expected["plan"]["operations"]
                    for field in ("source_expected", "target_expected", "intended", "prior_target_expected")
                ]
            elif name == "inventory":
                stats = [*expected["scan"]["files"], *expected["scan"]["directories"]]
            elif name in {"integrity", "invalidation"}:
                stats = [expected["expected_stat"], expected["expected_baseline"]["subject"]]
                if name == "integrity":
                    stats.append(expected["attestation"]["subject"])
            else:
                stats = []
            for stat in stats:
                if stat is not None and stat["file_identity"] is not None:
                    identity = stat["file_identity"]
                    identity["file_index"] = str(identity["file_index"])
            if name == "start":
                plan_input = dict(expected["plan"])
                del plan_input["fingerprint"]
                plan_bytes = json.dumps(
                    plan_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
                expected["plan"]["fingerprint"] = hashlib.sha256(plan_bytes).hexdigest()
        expected_bytes = json.dumps(
            expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        actual = canonical_json_bytes(project(command))
        assert actual == expected_bytes, name
        assert _payload_hash(project(command)) == hashlib.sha256(expected_bytes).digest(), name
        if name != "inventory" and (not with_identity or name in {"finish", "visibility"}):
            assert actual == old_bytes, name
        else:
            assert actual != old_bytes, name


def test_recorder_hash_projections_cover_exact_known_dataclasses() -> None:
    _, inputs = hash_fixtures(True)
    scan = inputs["inventory"].scan
    integrity = inputs["integrity"]
    cases = (
        (recorder_module._file_record_projection, scan.files[0]),
        (recorder_module._directory_record_projection, scan.directories[0]),
        (recorder_module._unsupported_record_projection, scan.unsupported[0]),
        (recorder_module._scan_warning_projection, scan.warnings[0]),
        (recorder_module._scan_scope_projection, scan.scope),
        (recorder_module._scan_projection, scan),
        (recorder_module._content_projection, integrity.attestation.content),
        (recorder_module._attestation_projection, integrity.attestation),
        (recorder_module._invalidation_projection, integrity.expected_invalidation),
        (recorder_module._sync_run_projection, SyncRunCommand(**inputs["start"])),
        (recorder_module._finish_run_projection, inputs["finish"]),
        (recorder_module._inventory_projection, inputs["inventory"]),
        (recorder_module._visibility_projection, inputs["visibility"]),
        (recorder_module._integrity_projection, integrity),
        (recorder_module._verification_invalidation_projection, inputs["invalidation"]),
    )
    for project, value in cases:
        # Test-only reflection detects a new field without adding a serializer.
        declared = {field.name for field in fields(value)}
        assert set(project(value)) == declared, type(value).__name__
        lookalike_type = make_dataclass("Unprojected" + type(value).__name__, sorted(declared))
        lookalike = lookalike_type(**{name: getattr(value, name) for name in declared})
        with pytest.raises(TypeError):
            project(lookalike)
        subclass_type = make_dataclass(
            "Extended" + type(value).__name__,
            [("future_file_index", int, MAX_FILE_INDEX)],
            bases=(type(value),), frozen=True,
        )
        extended = object.__new__(subclass_type)
        for name in declared:
            object.__setattr__(extended, name, getattr(value, name))
        object.__setattr__(extended, "future_file_index", MAX_FILE_INDEX)
        with pytest.raises(TypeError):
            project(extended)
    assert _payload_hash({"kind": "recorder", "item": 7}) == hashlib.sha256(
        frozen_vector("recorder/existing_primitive")
    ).digest()


def _ledger_state(path: Path) -> tuple[str, ...]:
    connection = connect_ledger_reader(path)
    try:
        return tuple(connection.iterdump())
    finally:
        connection.close()


def _install_epoch5_command_hash(path: Path, key: str, vector: str) -> None:
    # Simulate a persisted old receipt in an admitted current schema. Actual
    # old/mixed database markers are refused separately by admission tests.
    old_hash = hashlib.sha256(frozen_vector(vector)).digest()
    connection = connect_ledger_writer(path)
    try:
        cursor = connection.execute(
            "UPDATE recording_commands SET payload_hash = ? WHERE command_key = ?",
            (old_hash, key),
        )
        assert cursor.rowcount == 1
        connection.commit()
    finally:
        connection.close()


def _seed_captured_guarded_subject(setup, sync_plan, command) -> None:
    assert command.row_id == "1"
    assert command.location_id == str(setup.target_location_id)
    assert setup.recorder.record_inventory(
        InventoryCommand(
            setup.target_location_id, setup.host_id,
            _target_scan(sync_plan, (_record("a.txt", command.expected_stat),)),
            command.scope_token, NOW,
        )
    ).disposition is RecordDisposition.APPLIED
    assert setup.recorder.record_integrity(
        IntegrityRecordCommand(
            IntegrityMode.BASELINE, "seed-baseline", command.row_id,
            command.location_id, command.rel_path_key, command.scope_token,
            command.expected_state, command.expected_stat, None,
            command.expected_baseline, False, False,
        )
    ) is RecordDisposition.APPLIED
    assert setup.recorder.record_verification_invalidation(
        VerificationInvalidationCommand(
            "seed-invalidation", command.row_id, command.location_id,
            command.rel_path_key, command.scope_token, command.expected_state,
            command.expected_stat, command.expected_baseline, None,
            command.expected_invalidation.reason, command.expected_invalidation.at,
        )
    ) is RecordDisposition.APPLIED


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
def test_run_start_consumes_persisted_epoch5_hash_without_rewriting_it(
    tmp_path: Path, with_identity: bool,
) -> None:
    plans, inputs = hash_fixtures(with_identity)
    command = SyncRunCommand(**inputs["start"])
    setup = setup_recorder(tmp_path / "ledger.db", plans["two_copy"])
    try:
        before = _ledger_state(setup.recorder.path)
        replay = setup.recorder.begin_sync_run(command)
        assert replay._run_row_id == setup.run._run_row_id
        assert _ledger_state(setup.recorder.path) == before
        with pytest.raises(TokenConflictError):
            setup.recorder.begin_sync_run(replace(command, started_at=NOW + timedelta(microseconds=1)))
        assert _ledger_state(setup.recorder.path) == before

        suffix = "full128" if with_identity else "identityless"
        old_bytes = frozen_vector(f"recorder/start/{suffix}")
        connection = connect_ledger_writer(setup.recorder.path)
        try:
            cursor = connection.execute(
                "UPDATE runs SET start_payload_hash = ?, plan_fingerprint = ? WHERE run_token = ?",
                (hashlib.sha256(old_bytes).digest(), json.loads(old_bytes)["plan"]["fingerprint"], command.run_token),
            )
            assert cursor.rowcount == 1
            connection.commit()
        finally:
            connection.close()
        before = _ledger_state(setup.recorder.path)
        if with_identity:
            with pytest.raises(TokenConflictError):
                setup.recorder.begin_sync_run(command)
        else:
            assert setup.recorder.begin_sync_run(command)._run_row_id == setup.run._run_row_id
        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
def test_run_finish_consumes_unchanged_persisted_epoch5_hash(
    tmp_path: Path, with_identity: bool,
) -> None:
    plans, inputs = hash_fixtures(with_identity)
    command = inputs["finish"]
    setup = setup_recorder(tmp_path / "ledger.db", plans["two_copy"])
    try:
        assert setup.recorder.finish_run(command) is RecordDisposition.APPLIED
        suffix = "full128" if with_identity else "identityless"
        old_hash = hashlib.sha256(frozen_vector(f"recorder/finish/{suffix}")).digest()
        connection = connect_ledger_writer(setup.recorder.path)
        try:
            stored = connection.execute(
                "SELECT finish_payload_hash FROM runs WHERE run_token = ?", (command.run_token,),
            ).fetchone()[0]
            assert bytes(stored) == old_hash
            assert connection.execute(
                "UPDATE runs SET finish_payload_hash = ? WHERE run_token = ?",
                (old_hash, command.run_token),
            ).rowcount == 1
            connection.commit()
        finally:
            connection.close()
        before = _ledger_state(setup.recorder.path)
        assert setup.recorder.finish_run(command) is RecordDisposition.NOOP
        assert _ledger_state(setup.recorder.path) == before
        with pytest.raises(TokenConflictError):
            setup.recorder.finish_run(replace(command, recording=RecordingStatus.DEGRADED))
        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


@pytest.mark.parametrize("name", ("inventory", "integrity", "invalidation"))
@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
def test_applied_command_receipts_replay_or_refuse_the_frozen_epoch5_hash(
    tmp_path: Path, name: str, with_identity: bool,
) -> None:
    plans, inputs = hash_fixtures(with_identity)
    command = inputs[name]
    setup = setup_recorder(tmp_path / "ledger.db", plans["two_copy"])
    try:
        if name == "inventory":
            record = lambda value: setup.recorder.record_inventory(value).disposition
            key = f"inventory:{command.location_id}:{command.scope_token}"
            changed = replace(command, observed_at=NOW + timedelta(microseconds=1))
        else:
            _seed_captured_guarded_subject(setup, plans["two_copy"], command)
            if name == "integrity":
                record = setup.recorder.record_integrity
                key = f"integrity:{command.scope_token}:{command.item_id}"
                changed = replace(command, clear_reappeared=False)
            else:
                record = setup.recorder.record_verification_invalidation
                key = f"verification-invalidation:{command.scope_token}:{command.item_id}"
                changed = replace(command, reason=VerificationInvalidationReason.METADATA_DRIFT)
        assert record(command) is RecordDisposition.APPLIED
        before = _ledger_state(setup.recorder.path)
        assert record(command) is RecordDisposition.NOOP
        assert _ledger_state(setup.recorder.path) == before
        with pytest.raises(TokenConflictError):
            record(changed)
        assert _ledger_state(setup.recorder.path) == before

        suffix = "full128" if with_identity else "identityless"
        _install_epoch5_command_hash(
            setup.recorder.path, key, f"recorder/{name}/{suffix}",
        )
        before = _ledger_state(setup.recorder.path)
        if with_identity or name == "inventory":
            # Even identityless inventory now omits the captured malformed
            # optional detail. Its old receipt must conflict without mutation.
            with pytest.raises(TokenConflictError):
                record(command)
        else:
            assert record(command) is RecordDisposition.NOOP
        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
def test_captured_visibility_receipt_retains_its_stale_disposition(
    tmp_path: Path, with_identity: bool,
) -> None:
    plans, inputs = hash_fixtures(with_identity)
    command = inputs["visibility"]
    setup = setup_recorder(tmp_path / "ledger.db", plans["two_copy"])
    try:
        # The captured row-é key is deliberately not a real numeric row id.
        assert setup.recorder.change_inventory_visibility(command) is RecordDisposition.STALE
        suffix = "full128" if with_identity else "identityless"
        _install_epoch5_command_hash(
            setup.recorder.path, f"inventory-visibility:{command.command_id}",
            f"recorder/visibility/{suffix}",
        )
        before = _ledger_state(setup.recorder.path)
        assert setup.recorder.change_inventory_visibility(command) is RecordDisposition.STALE
        assert _ledger_state(setup.recorder.path) == before
        with pytest.raises(TokenConflictError):
            setup.recorder.change_inventory_visibility(
                replace(command, action=InventoryVisibilityAction.RESTORE)
            )
        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


def test_applied_visibility_receipt_replays_and_rejects_changed_input(tmp_path: Path) -> None:
    plans, _ = hash_fixtures(False)
    reviewed = plans["two_copy"]
    setup = setup_recorder(tmp_path / "ledger.db", reviewed)
    try:
        present = InventoryCommand(
            setup.target_location_id, setup.host_id,
            _target_scan(reviewed, (_record("a.txt", reviewed.operations[0].source_expected),)),
            "present", NOW,
        )
        assert setup.recorder.record_inventory(present).disposition is RecordDisposition.APPLIED
        assert setup.recorder.record_inventory(
            replace(present, scan=_target_scan(reviewed, ()), scope_token="missing")
        ).missing_count == 1
        command = InventoryVisibilityCommand(
            "visibility-replay", setup.target_location_id, "1",
            InventoryVisibilityAction.ACKNOWLEDGE, NOW,
        )
        assert setup.recorder.change_inventory_visibility(command) is RecordDisposition.APPLIED
        before = _ledger_state(setup.recorder.path)
        assert setup.recorder.change_inventory_visibility(command) is RecordDisposition.NOOP
        assert _ledger_state(setup.recorder.path) == before
        with pytest.raises(TokenConflictError):
            setup.recorder.change_inventory_visibility(
                replace(command, action=InventoryVisibilityAction.RESTORE)
            )
        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


def test_volume_and_location_commands_are_readmitted_before_ledger_mutation(
    tmp_path: Path,
) -> None:
    reviewed, _inputs = hash_fixtures(False)
    setup = setup_recorder(tmp_path / "ledger.db", reviewed["two_copy"])
    try:
        volume = VolumeCommand(
            VolumeId("extra-volume", "NTFS"),
            VolumeEvidence("Extra", "X:\\"),
            NOW,
        )
        object.__setattr__(volume.evidence, "label", "v" * 261)
        location = LocationCommand(1, "managed", NOW)
        object.__setattr__(location, "volume_relative_path", "p" * 32_768)
        before = _ledger_state(setup.recorder.path)

        with pytest.raises(ValueError, match="UTF-16 text bound"):
            setup.recorder.observe_volume(volume)
        with pytest.raises(ValueError, match="UTF-16 path bound"):
            setup.recorder.ensure_location(location)

        assert _ledger_state(setup.recorder.path) == before
    finally:
        setup.recorder.close()


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
        identity = setup.run.record_copied(copy.op_id, evidence)
        replayed_identity = setup.run.record_copied(copy.op_id, evidence)

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
            assert identity.row_id == str(target["id"])
        finally:
            connection.close()
        assert replayed_identity == identity
        assert identity.location_id == str(setup.target_location_id)
        assert identity.scope_token == setup.run_token
        assert identity.rel_path_key == normalize_relative_path(
            copy.target_rel_path
        )
    finally:
        setup.recorder.close()


def test_copy_identity_is_not_returned_when_its_transaction_rolls_back(
    tmp_path: Path,
) -> None:
    source = file_stat(identity_index=1)
    published = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(
        OperationKind.COPY,
        source=source,
        target=None,
        intended=published,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    writer = connect_ledger_writer(setup.recorder.path)
    try:
        writer.execute(
            """CREATE TRIGGER force_operation_failure
               BEFORE INSERT ON operations
               BEGIN
                   SELECT RAISE(ABORT, 'forced operation failure');
               END"""
        )
        writer.commit()
    finally:
        writer.close()

    try:
        with pytest.raises(RecordingError, match="forced operation failure"):
            setup.run.record_copied(copy.op_id, attestation(published))

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute(
                "SELECT count(*) FROM operations"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM inventory"
            ).fetchone()[0] == 0
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_sync_run_recorder_conditionally_records_linked_readback(
    tmp_path: Path,
) -> None:
    source = file_stat(identity_index=1)
    published = file_stat(identity_index=2, volume_serial="target-serial")
    copy = operation(
        OperationKind.COPY,
        source=source,
        target=None,
        intended=published,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((copy,)))
    copy_evidence = attestation(published)
    try:
        identity = setup.run.record_copied(copy.op_id, copy_evidence)
        readback = attestation(
            published,
            provenance=Provenance.READBACK_ATTESTED,
        )
        command = IntegrityRecordCommand(
            mode=IntegrityMode.VERIFY,
            item_id=str(copy.op_id),
            row_id=identity.row_id,
            location_id=identity.location_id,
            rel_path_key=identity.rel_path_key,
            scope_token=identity.scope_token,
            expected_state=InventoryState.PRESENT,
            expected_stat=published,
            expected_baseline=copy_evidence,
            attestation=readback,
            advances_last_verified=True,
            clear_reappeared=False,
        )

        assert (
            setup.run.record_integrity(command)
            is RecordDisposition.APPLIED
        )

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            row = connection.execute(
                """SELECT last_verified_at, hash_provenance
                     FROM inventory
                    WHERE id = ?""",
                (int(identity.row_id),),
            ).fetchone()
            assert row["last_verified_at"] is not None
            assert (
                row["hash_provenance"]
                == Provenance.READBACK_ATTESTED.value
            )
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
            assert correspondence[0]["source_identity_file_index"] == "5"
            assert correspondence[0]["target_identity_file_index"] == "6"
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_noop_without_reviewed_source_path_is_typed_stale_recording(
    tmp_path: Path,
) -> None:
    source = file_stat(identity_index=5)
    target = file_stat(identity_index=6, volume_serial="target-serial")
    noop = operation(
        OperationKind.NOOP,
        source_path=None,
        source=source,
        target=target,
        intended=target,
        reason=OperationReason.METADATA_MATCH,
    )
    setup = setup_recorder(tmp_path / "ledger.db", plan((noop,)))
    try:
        with pytest.raises(
            StaleRecordingError,
            match="reviewed operation has no source path",
        ):
            setup.run.record_noop(noop.op_id, source, target)

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM mapping_correspondence"
            ).fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0
        finally:
            connection.close()
    finally:
        setup.recorder.close()
