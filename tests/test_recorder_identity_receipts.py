"""Public receipt producers and isolated replay gates for frozen epoch-5 hashes.

The rich capture is not an executable workflow fixture. In particular its MOVE
target timestamp differs from the reviewed prior target. That captured envelope
can exercise the receipt hash gate, but cannot claim a valid historical write.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from namisync.core.execution import RecordedCopyIdentity
from namisync.core.models import FileRecord, ScanResult, ScanScope
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import plan_fingerprint
from namisync.core.recording import InventoryCommand
from namisync.db.connections import connect_ledger_reader, connect_ledger_writer
import namisync.db.recorder as recorder_module
from namisync.db.recorder import StaleRecordingError
from namisync.db.writer import TokenConflictError

from _db_fixtures import NOW, attestation, setup_recorder
from _identity_epoch5 import frozen_vector
from _identity_hash_fixtures import RUN_TOKEN, hash_fixtures


RECEIPT_NAMES = ("attestation", "target", "trash", "prior", "noop")


def _frozen_preimage(name: str, with_identity: bool) -> bytes:
    variant = "full128" if with_identity else "identityless"
    return frozen_vector(f"recorder/receipt_{name}/{variant}")


def _current_projection(name: str, with_identity: bool) -> dict:
    payload = json.loads(_frozen_preimage(name, with_identity))
    # These are the declared FileStat positions, not a recursive key heuristic.
    stats = [
        payload["operation"][field]
        for field in (
            "source_expected", "target_expected", "intended",
            "prior_target_expected",
        )
    ]
    evidence = payload["evidence"]
    if name == "attestation":
        stats.append(evidence["attestation"]["subject"])
    elif name == "prior":
        stats.append(evidence["prior"])
    elif name == "noop":
        stats.extend((evidence["source"], evidence["target"]))
    else:
        stats.append(evidence["target"])
    for stat in stats:
        identity = stat["file_identity"]
        if identity is not None:
            assert type(identity["file_index"]) is int
            identity["file_index"] = str(identity["file_index"])
    return payload


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8", errors="backslashreplace")


@contextmanager
def _receipt_run(path: Path, name: str, with_identity: bool):
    plans, inputs = hash_fixtures(with_identity)
    envelope = inputs[f"receipt_{name}"]
    operation = envelope["operation"]
    base = plans["two_copy"]
    dependency = base.operations[1]
    assert operation.dependencies == (dependency.op_id,)
    # Retain the captured operation verbatim in a dependency-ordered run
    # context. This does not turn the all-fields capture into a workflow plan.
    assignment = replace(
        base.assignment,
        items=tuple(
            replace(
                item, target_rel_path=operation.target_rel_path,
                target_rel_path_key=normalize_relative_path(operation.target_rel_path),
            )
            if item.source_rel_path == operation.source_rel_path else item
            for item in base.assignment.items
        ),
    )
    reviewed = replace(
        base, operations=(dependency, operation), assignment=assignment,
        required_bytes=dependency.content_bytes + operation.content_bytes,
    )
    reviewed = replace(reviewed, fingerprint=plan_fingerprint(reviewed))
    setup = setup_recorder(path, reviewed, run_token=RUN_TOKEN)
    try:
        moving = name in {"attestation", "target"}
        prior_path = (
            operation.prior_target_rel_path if moving else operation.target_rel_path
        )
        prior = (
            operation.prior_target_expected if moving else operation.target_expected
        )
        record = FileRecord(
            prior_path, normalize_relative_path(prior_path), prior.size,
            prior.mtime_ns, prior.file_identity, prior.nlink, prior.metadata,
        )
        scan = ScanResult(
            reviewed.target_root, reviewed.target_volume_id,
            reviewed.target_volume_evidence, reviewed.target_profile,
            (record,), (), (), (), ScanScope.full(), True,
        )
        setup.recorder.record_inventory(InventoryCommand(
            setup.target_location_id, setup.host_id, scan, "prior-inventory", NOW,
        ))
        setup.run.record_copied(
            dependency.op_id,
            attestation(replace(dependency.intended, file_identity=None)),
        )
        yield setup, envelope
    finally:
        setup.recorder.close()


def _producer_envelope(name: str, captured: dict) -> dict:
    if name != "target":
        return captured
    return {
        **captured,
        "evidence": {"target": captured["operation"].prior_target_expected},
    }


def _record(run, name: str, envelope: dict):
    op_id = envelope["operation"].op_id
    evidence = envelope["evidence"]
    if name == "attestation":
        return run.record_move_updated(op_id, evidence["attestation"])
    if name == "target":
        return run.record_moved(op_id, evidence["target"])
    if name == "trash":
        return run.record_trashed(
            op_id, envelope["trash_relative_path"], evidence["target"],
        )
    if name == "prior":
        return run.record_deleted(op_id, evidence["prior"])
    assert name == "noop"
    return run.record_noop(op_id, evidence["source"], evidence["target"])


def _changed_envelope(name: str, envelope: dict) -> dict:
    changed = {**envelope, "evidence": dict(envelope["evidence"])}
    evidence = changed["evidence"]
    if name == "attestation":
        original = evidence["attestation"]
        evidence["attestation"] = replace(
            original, content=replace(original.content, digest=b"\xff" * 16),
        )
    elif name == "trash":
        evidence["trash"] = changed["trash_relative_path"] = r"run\other.txt"
    else:
        field = "source" if name == "noop" else "prior" if name == "prior" else "target"
        original = evidence[field]
        evidence[field] = replace(
            original,
            metadata=replace(original.metadata, attributes=original.metadata.attributes + 1),
        )
    return changed


def _rows(path: Path) -> dict[str, tuple]:
    connection = connect_ledger_reader(path)
    try:
        return {
            table: tuple(tuple(row) for row in connection.execute(
                f"SELECT * FROM {table} ORDER BY rowid"
            ))
            for table in (
                "inventory", "mapping_correspondence", "operations", "runs",
                "recording_commands",
            )
        }
    finally:
        connection.close()


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
@pytest.mark.parametrize("name", RECEIPT_NAMES)
def test_public_operation_receipt_first_write_replay_and_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, with_identity: bool,
) -> None:
    path = tmp_path / "ledger.db"
    with _receipt_run(path, name, with_identity) as (setup, captured):
        emitted = []
        encode = recorder_module.canonical_json_bytes

        def observe_preimage(payload):
            serialized = encode(payload)
            emitted.append(serialized)
            return serialized

        monkeypatch.setattr(recorder_module, "canonical_json_bytes", observe_preimage)
        captured_projection = _current_projection(name, with_identity)
        before = _rows(path)
        if name == "target":
            # The frozen MOVE has target mtime +11 but prior target mtime +9.
            # It is a valid hash input, not a valid first-write result. Pin both
            # the exact preimage and the absence of partially applied state.
            assert captured["evidence"]["target"].mtime_ns == (1 << 53) + 11
            assert captured["operation"].prior_target_expected.mtime_ns == (1 << 53) + 9
            with pytest.raises(StaleRecordingError, match="reviewed target version"):
                _record(setup.run, name, captured)
            assert emitted == [_json_bytes(captured_projection)]
            assert _rows(path) == before
            emitted.clear()

        producer = _producer_envelope(name, captured)
        producer_projection = _current_projection(name, with_identity)
        if name == "target":
            # Only this separate fresh-producer control uses the reviewed prior
            # stat. Neither the captured operation nor frozen bytes are edited.
            producer_projection["evidence"]["target"] = (
                producer_projection["operation"]["prior_target_expected"]
            )
        expected_preimage = _json_bytes(producer_projection)
        result = _record(setup.run, name, producer)
        assert emitted == [expected_preimage]
        after = _rows(path)
        assert after != before
        assert len(after["operations"]) == len(before["operations"]) + 1

        operation = producer["operation"]
        connection = connect_ledger_reader(path)
        try:
            receipt = connection.execute(
                """SELECT kind, outcome, content_bytes, trash_rel_path, payload_hash
                     FROM operations WHERE op_token = ?""",
                (str(operation.op_id),),
            ).fetchone()
            assert tuple(receipt) == (
                operation.kind.value, "skipped" if name == "noop" else "succeeded",
                (1 << 53) + 7, producer["trash_relative_path"],
                hashlib.sha256(expected_preimage).digest(),
            )
            target = connection.execute(
                """SELECT id, presence, observed_size, observed_mtime_ns,
                          file_identity_file_index, scope_token
                     FROM inventory WHERE location_id = ? AND rel_path_key = ?""",
                (setup.target_location_id, normalize_relative_path(operation.target_rel_path)),
            ).fetchone()
            assert target["presence"] == (
                "missing" if name in {"trash", "prior"} else "present"
            )
            assert target["observed_size"] == (1 << 53) + 7
            assert target["observed_mtime_ns"] == (1 << 53) + (9 if name == "target" else 11)
            assert target["file_identity_file_index"] == ("0" if with_identity else None)
            assert target["scope_token"] == RUN_TOKEN
            if name == "attestation":
                assert result == RecordedCopyIdentity(
                    str(target["id"]), str(setup.target_location_id), RUN_TOKEN,
                    normalize_relative_path(operation.target_rel_path),
                )
            else:
                assert result is None
            correspondence_count = connection.execute(
                "SELECT count(*) FROM mapping_correspondence WHERE op_token = ?",
                (str(operation.op_id),),
            ).fetchone()[0]
            assert correspondence_count == int(
                with_identity and name in {"attestation", "target", "noop"}
            )
        finally:
            connection.close()

        assert _record(setup.run, name, producer) == result
        assert emitted[-1] == expected_preimage
        assert _rows(path) == after
        # These are well-formed DTOs, not malformed serializer inputs. Changed
        # evidence for a committed token must conflict before semantic apply.
        with pytest.raises(TokenConflictError, match="different evidence"):
            _record(setup.run, name, _changed_envelope(name, producer))
        assert _rows(path) == after


@pytest.mark.parametrize("with_identity", (False, True), ids=("identityless", "full128"))
@pytest.mark.parametrize("name", RECEIPT_NAMES)
def test_frozen_operation_receipt_hash_gates_public_replay_without_writes(
    tmp_path: Path, name: str, with_identity: bool,
) -> None:
    path = tmp_path / "ledger.db"
    with _receipt_run(path, name, with_identity) as (setup, captured):
        result = _record(setup.run, name, _producer_envelope(name, captured))
        old_preimage = _frozen_preimage(name, with_identity)
        current_preimage = _json_bytes(_current_projection(name, with_identity))
        assert (old_preimage == current_preimage) is (not with_identity)
        old_hash = hashlib.sha256(old_preimage).digest()

        # Isolated consumer compatibility: replace just the hash of a receipt
        # produced by a legitimate current public write. The database still has
        # current markers. This is not old-database admission, historical
        # execution, or (for MOVE) a claim that the captured result can apply.
        connection = connect_ledger_writer(path)
        try:
            changed = connection.execute(
                """UPDATE operations SET payload_hash = ?
                     WHERE op_token = ? AND run_id = (
                         SELECT id FROM runs WHERE run_token = ?
                     )""",
                (old_hash, str(captured["operation"].op_id), RUN_TOKEN),
            )
            assert changed.rowcount == 1
            assert bytes(connection.execute(
                "SELECT payload_hash FROM operations WHERE op_token = ?",
                (str(captured["operation"].op_id),),
            ).fetchone()[0]) == old_hash
        finally:
            connection.close()

        before = _rows(path)
        if with_identity:
            with pytest.raises(TokenConflictError, match="different evidence"):
                _record(setup.run, name, captured)
        else:
            assert _record(setup.run, name, captured) == result
        assert _rows(path) == before
