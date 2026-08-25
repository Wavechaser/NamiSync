from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest

import namisync.modules.verifier.engine as verifier_engine
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import Progress
from namisync.core.integrity import (
    AuthorityBoundVerificationReader,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileRecord,
    FileStat,
    MetadataSnapshot,
    ScanWarning,
    ScanWarningCode,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.root_authority import RootAuthority
from tools import sidecar, verifier_rig
from tools.seams import AuthorityBoundTappedReader, Tape, TappedReader


def _stat(*, identity: bool = True, index: int = 1) -> FileStat:
    return FileStat(
        kind=EntryKind.FILE,
        size=3,
        mtime_ns=100,
        file_identity=FileIdentity("volume", index) if identity else None,
        nlink=1,
        metadata=MetadataSnapshot(attributes=0, created_ns=50),
    )


def _attestation(*, identity: bool = True, index: int = 1) -> Attestation:
    subject = _stat(identity=identity, index=index)
    return Attestation(
        content=ContentEvidence(
            algorithm="xxh3_128",
            digest=bytes(range(16)),
            size=subject.size,
            provenance=Provenance.VERIFY_ATTESTED,
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        subject=subject,
    )


def _file_record(path: str, *, index: int = 1) -> FileRecord:
    stat = _stat(index=index)
    return FileRecord(
        rel_path=path,
        rel_path_key=normalize_relative_path(path),
        size=stat.size,
        mtime_ns=stat.mtime_ns,
        file_identity=stat.file_identity,
        nlink=stat.nlink,
        metadata=stat.metadata,
    )


def _replace_document(path: Path, header: object, rows: list[object]) -> None:
    path.write_text(
        "\n".join(json.dumps(value) for value in (header, *rows)) + "\n",
        encoding="utf-8",
    )


def _read_document(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    values = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    return values[0], values[1:]


def test_tapped_readers_preserve_the_wrapped_reader_authority_capability(
    tmp_path: Path,
) -> None:
    bound_opened: list[tuple[str, RootAuthority]] = []
    unbound_opened: list[tuple[Path, str]] = []

    class BoundReader:
        @contextmanager
        def open(self, root: Path, relative_path: str) -> Iterator[object]:
            raise AssertionError("bound dispatch must not use the legacy open seam")
            yield object()

        @contextmanager
        def open_with_authority(
            self,
            relative_path: str,
            authority: RootAuthority,
        ) -> Iterator[object]:
            bound_opened.append((relative_path, authority))
            yield SimpleNamespace(strategy=ReadStrategy.WINDOWS_UNBUFFERED)

    class UnboundReader:
        @contextmanager
        def open(self, root: Path, relative_path: str) -> Iterator[object]:
            unbound_opened.append((root, relative_path))
            yield SimpleNamespace(strategy=ReadStrategy.WINDOWS_UNBUFFERED)

    authority = RootAuthority(str(tmp_path))
    bound_reader = AuthorityBoundTappedReader(BoundReader())
    assert isinstance(bound_reader, AuthorityBoundVerificationReader)
    with pytest.raises(ValueError, match="authority-bound verification reader"):
        verifier_engine._reader_for_context(
            SimpleNamespace(root_authority=None),
            bound_reader,
        )

    with verifier_engine._open_reader(
        bound_reader,
        tmp_path,
        "A.TXT",
        SimpleNamespace(root_authority=authority),
    ):
        pass

    assert bound_opened == [("A.TXT", authority)]
    assert len(bound_reader.samples) == 1
    assert bound_reader.samples[0].relative_path == "A.TXT"

    unbound_reader = TappedReader(UnboundReader())
    assert not isinstance(unbound_reader, AuthorityBoundVerificationReader)
    selected = verifier_engine._reader_for_context(
        SimpleNamespace(root_authority=None),
        unbound_reader,
    )
    with verifier_engine._open_reader(
        selected,
        tmp_path,
        "B.TXT",
        SimpleNamespace(root_authority=None),
    ):
        pass

    assert unbound_opened == [(tmp_path, "B.TXT")]
    assert isinstance(verifier_rig._reader(True), AuthorityBoundTappedReader)


def test_batch_fixture_requires_exact_membership_and_portable_stat_fidelity() -> None:
    portable = _stat(identity=False)
    run = SimpleNamespace(fixture=(("A.TXT", _stat(index=99)),))

    verifier_rig.require_fixture(run, {"A.TXT": portable}, portable=True)

    with pytest.raises(verifier_rig.VerifierRigError, match="membership changed"):
        verifier_rig.require_fixture(run, {"B.TXT": portable}, portable=True)
    with pytest.raises(verifier_rig.VerifierRigError, match="file stats changed"):
        verifier_rig.require_fixture(run, {"A.TXT": _stat(index=1)}, portable=False)


def test_sidecar_bound_round_trip_preserves_identity(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    file_index = (1 << 127) + 17
    expected = {"A.TXT": _attestation(index=file_index)}

    assert sidecar.write(path, expected, identity_mode=sidecar.BOUND) == 1

    header, rows = _read_document(path)
    assert header["format"] == "namisync-rig-baseline-2"
    assert rows[0]["file_index"] == str(file_index)
    actual, identity_mode = sidecar.read(path)
    assert identity_mode == sidecar.BOUND
    assert actual == expected


def test_sidecar_bound_write_rejects_missing_identity_without_replacing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "baseline.jsonl"
    path.write_text("existing", encoding="utf-8")

    with pytest.raises(sidecar.SidecarError, match="has no file identity"):
        sidecar.write(
            path,
            {"A.TXT": _attestation(identity=False)},
            identity_mode=sidecar.BOUND,
        )

    assert path.read_text(encoding="utf-8") == "existing"


def test_sidecar_refuses_existing_destination_without_explicit_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "baseline.jsonl"
    path.write_text("existing", encoding="utf-8")

    with pytest.raises(sidecar.SidecarError, match="--replace-sidecar"):
        sidecar.write(path, {"A.TXT": _attestation()})

    assert path.read_text(encoding="utf-8") == "existing"

    details = path.stat()
    assert sidecar.write(
        path,
        {"A.TXT": _attestation()},
        replace=True,
        expected_identity=(details.st_dev, details.st_ino),
    ) == 1
    assert sidecar.read(path)[0] == {"A.TXT": _attestation(identity=False)}


@pytest.mark.parametrize(
    ("serial", "index"),
    [(None, None), ("volume", None), (None, "1")],
)
def test_sidecar_bound_read_rejects_missing_or_partial_identity(
    tmp_path: Path, serial: str | None, index: object
) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()}, identity_mode=sidecar.BOUND)
    header, rows = _read_document(path)
    rows[0]["volume_serial"] = serial
    rows[0]["file_index"] = index
    _replace_document(path, header, rows)

    with pytest.raises(
        sidecar.SidecarError, match="file identity|requires file identity"
    ):
        sidecar.read(path)


@pytest.mark.parametrize(
    "file_index",
    [True, 1, "", "01", "-1", str(1 << 128)],
)
def test_sidecar_rejects_noncanonical_file_index(
    tmp_path: Path,
    file_index: object,
) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()}, identity_mode=sidecar.BOUND)
    header, rows = _read_document(path)
    rows[0]["file_index"] = file_index
    _replace_document(path, header, rows)

    with pytest.raises(sidecar.SidecarError, match="line 2.*file_index"):
        sidecar.read(path)


@pytest.mark.parametrize(
    "header",
    [
        [],
        {"format": sidecar.FORMAT},
        {"identity_mode": sidecar.PORTABLE},
        {
            "format": sidecar.FORMAT,
            "identity_mode": sidecar.PORTABLE,
            "extra": True,
        },
    ],
)
def test_sidecar_requires_object_header_with_explicit_fields(
    tmp_path: Path, header: object
) -> None:
    path = tmp_path / "baseline.jsonl"
    _replace_document(path, header, [])

    with pytest.raises(sidecar.SidecarError, match="header"):
        sidecar.read(path)


def test_sidecar_rejects_duplicate_header_fields(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    path.write_text(
        '{"format":"namisync-rig-baseline-2",'
        '"format":"namisync-rig-baseline-2",'
        '"identity_mode":"portable"}\n',
        encoding="utf-8",
    )

    with pytest.raises(sidecar.SidecarError, match="duplicate JSON field"):
        sidecar.read(path)


def test_sidecar_decodes_and_validates_stored_algorithm(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()}, identity_mode=sidecar.PORTABLE)
    header, rows = _read_document(path)
    rows[0]["algorithm"] = "sha256"
    _replace_document(path, header, rows)

    with pytest.raises(sidecar.SidecarError, match="unsupported content algorithm"):
        sidecar.read(path)


@pytest.mark.parametrize(
    "malformation", ["non_object", "missing_field", "extra_field", "wrong_type"]
)
def test_sidecar_normalizes_malformed_row_schemas(
    tmp_path: Path, malformation: str
) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()}, identity_mode=sidecar.PORTABLE)
    header, rows = _read_document(path)
    row: object = rows[0]
    if malformation == "non_object":
        row = []
    elif malformation == "missing_field":
        rows[0].pop("digest")
    elif malformation == "extra_field":
        rows[0]["extra"] = True
    else:
        rows[0]["size"] = True
    _replace_document(path, header, [row])

    with pytest.raises(sidecar.SidecarError, match="line 2"):
        sidecar.read(path)


def test_sidecar_rejects_duplicate_row_fields(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()})
    header, row = path.read_text(encoding="utf-8").splitlines()
    row = row[:-1] + ',"digest":"00000000000000000000000000000000"}'
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")

    with pytest.raises(sidecar.SidecarError, match="line 2.*duplicate JSON field"):
        sidecar.read(path)


def test_sidecar_normalizes_write_errors_and_keeps_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "baseline.jsonl"
    path.write_text("existing", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("replace failed")

    monkeypatch.setattr(sidecar.os, "replace", fail_replace)

    details = path.stat()
    with pytest.raises(sidecar.SidecarError, match="cannot write sidecar"):
        sidecar.write(
            path,
            {"A.TXT": _attestation()},
            replace=True,
            expected_identity=(details.st_dev, details.st_ino),
        )

    assert path.read_text(encoding="utf-8") == "existing"
    assert list(tmp_path.glob(".baseline.jsonl.*.tmp")) == []


def test_sidecar_normalizes_read_errors(tmp_path: Path) -> None:
    with pytest.raises(sidecar.SidecarError, match="cannot read sidecar"):
        sidecar.read(tmp_path / "missing.jsonl")


def test_load_baselines_returns_portable_evidence_after_strict_validation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(path, {"A.TXT": _attestation()}, identity_mode=sidecar.PORTABLE)
    live = {"A.TXT": _stat(index=99)}

    evidence, report = verifier_rig.load_baselines(path, live)

    assert report.usable
    assert set(evidence) == set(live)
    assert evidence["A.TXT"].subject.file_identity is None


def test_load_baselines_refuses_extra_evidence_instead_of_restricting_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "baseline.jsonl"
    sidecar.write(
        path,
        {
            "A.TXT": _attestation(index=1),
            "B.TXT": _attestation(index=2),
        },
    )

    with pytest.raises(sidecar.SidecarError, match="missing from disk"):
        verifier_rig.load_baselines(path, {"A.TXT": _stat(index=99)})


@pytest.mark.parametrize(
    ("complete", "unsupported", "warnings", "message"),
    [
        (False, (), (), "incomplete"),
        (True, (object(),), (), "unsupported"),
        (
            True,
            (),
            (ScanWarning(ScanWarningCode.CASE_COLLISION, "a.txt"),),
            "canonical path collisions",
        ),
    ],
)
def test_scan_stats_refuses_incomplete_or_corrupted_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    complete: bool,
    unsupported: tuple[object, ...],
    warnings: tuple[ScanWarning, ...],
    message: str,
) -> None:
    result = SimpleNamespace(
        files=(_file_record("a.txt"),),
        unsupported=unsupported,
        warnings=warnings,
        complete=complete,
    )
    monkeypatch.setattr(verifier_rig, "scan_root", lambda *args, **kwargs: result)

    with pytest.raises(verifier_rig.VerifierRigError, match=message):
        verifier_rig.scan_stats(tmp_path)


def test_scan_stats_refuses_collapsed_canonical_key_cardinality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = SimpleNamespace(
        files=(_file_record("a.txt"), _file_record("A.TXT", index=2)),
        unsupported=(),
        warnings=(),
        complete=True,
    )
    monkeypatch.setattr(verifier_rig, "scan_root", lambda *args, **kwargs: result)

    with pytest.raises(
        verifier_rig.VerifierRigError, match="one canonical key per file"
    ):
        verifier_rig.scan_stats(tmp_path)


def _baseline_run(
    *, dispositions: tuple[RecordDisposition, ...], duplicate_key: bool = False
) -> SimpleNamespace:
    item_ids = tuple(f"item-{number}" for number in range(len(dispositions)))
    outcomes = tuple(
        SimpleNamespace(
            item_id=item_id,
            result=IntegrityResult.BASELINED,
            record_disposition=disposition,
            recording=RecordingStatus.OK,
        )
        for item_id, disposition in zip(item_ids, dispositions, strict=True)
    )
    keys = tuple(
        "A.TXT" if duplicate_key else f"{number}.TXT"
        for number in range(len(item_ids))
    )
    commands = tuple(
        SimpleNamespace(item_id=item_id, rel_path_key=key)
        for item_id, key in zip(item_ids, keys, strict=True)
    )
    evidence = {
        key: _attestation(index=number + 1) for number, key in enumerate(keys)
    }
    tape = Tape()
    tape.emit(
        Progress(
            "verify",
            items_done=len(item_ids),
            items_total=len(item_ids),
            bytes_done=3 * len(item_ids),
            bytes_total=3 * len(item_ids),
            current_path=None,
        )
    )
    return SimpleNamespace(
        items=len(item_ids),
        expected_item_ids=frozenset(item_ids),
        expected_bytes=3 * len(item_ids),
        result=SimpleNamespace(outcomes=outcomes, recording=RecordingStatus.OK),
        recorder=SimpleNamespace(commands=commands),
        tape=tape,
        attestations=lambda: evidence,
    )


def test_prime_baselines_requires_every_recording_to_be_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _baseline_run(
        dispositions=(RecordDisposition.APPLIED, RecordDisposition.STALE)
    )
    monkeypatch.setattr(verifier_rig, "run_verifier", lambda *args, **kwargs: run)

    with pytest.raises(verifier_rig.VerifierRigError, match="applied 1"):
        verifier_rig.prime_baselines(tmp_path)


def test_prime_baselines_requires_one_distinct_attestation_per_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _baseline_run(
        dispositions=(RecordDisposition.APPLIED, RecordDisposition.APPLIED),
        duplicate_key=True,
    )
    monkeypatch.setattr(verifier_rig, "run_verifier", lambda *args, **kwargs: run)

    with pytest.raises(verifier_rig.VerifierRigError, match="evidence 1"):
        verifier_rig.prime_baselines(tmp_path)


@pytest.mark.parametrize(
    "progress",
    [
        Progress("verify", 2, 3, 6, 6, None),
        Progress("verify", 2, 2, 3, 3, None),
    ],
)
def test_prime_baselines_requires_exact_progress_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    progress: Progress,
) -> None:
    run = _baseline_run(
        dispositions=(RecordDisposition.APPLIED, RecordDisposition.APPLIED)
    )
    run.tape = Tape()
    run.tape.emit(progress)
    monkeypatch.setattr(verifier_rig, "run_verifier", lambda *args, **kwargs: run)

    with pytest.raises(verifier_rig.VerifierRigError, match="did not record"):
        verifier_rig.prime_baselines(tmp_path)


def test_prime_baselines_returns_complete_applied_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _baseline_run(
        dispositions=(RecordDisposition.APPLIED, RecordDisposition.APPLIED)
    )
    monkeypatch.setattr(verifier_rig, "run_verifier", lambda *args, **kwargs: run)

    evidence = verifier_rig.prime_baselines(tmp_path)

    assert set(evidence) == {"0.TXT", "1.TXT"}
