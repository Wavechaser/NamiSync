from __future__ import annotations

import _winapi
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import evidence
from tools.evidence import DEFAULT_ROOT, FILE_CAP, check, main, render


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "evidence").mkdir(parents=True)
    (tmp_path / "evidence" / "manifest.json").write_text(
        render({"format": 1, "next_id": 1, "records": []}), encoding="utf-8", newline="\n")
    (tmp_path / "docs").mkdir()
    return tmp_path


def _run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


def _manifest(root: Path) -> dict:
    return json.loads((root / "evidence" / "manifest.json").read_text(encoding="utf-8"))


def _sealed(tmp_path: Path) -> Path:
    root = _repo(tmp_path)
    assert _run(root, "add", "--title", "Cleanup receipts", "--origin", "build/x at abc123", "--date", "2026-11-14") == 0
    folder = root / "evidence" / "EV-0001"
    (folder / "sub").mkdir()
    (folder / "summary.md").write_bytes(b"line\r\nkept bytes\n")
    (folder / "sub" / "raw.json").write_bytes(b"{}")
    assert _run(root, "seal", "EV-0001") == 0
    return root


def test_add_and_seal_produce_canonical_sorted_manifest(tmp_path, capsys):
    root = _sealed(tmp_path)
    data = _manifest(root)
    assert data["next_id"] == 2
    record, = data["records"]
    assert list(record) == ["id", "title", "date", "origin", "files"]
    assert [f["path"] for f in record["files"]] == ["sub/raw.json", "summary.md"]
    assert record["files"][1]["bytes"] == 17
    assert (root / "evidence" / "manifest.json").read_text(encoding="utf-8") == render(data)
    assert check(root) == []
    capsys.readouterr()
    assert _run(root, "add", "--title", "Second", "--origin", "build/y") == 0
    assert "EV-0002 evidence/EV-0002/" in capsys.readouterr().out


def test_ids_are_not_reused_after_a_record_is_removed(tmp_path):
    root = _sealed(tmp_path)
    data = _manifest(root)
    data["records"] = []
    (root / "evidence" / "manifest.json").write_text(render(data), encoding="utf-8", newline="\n")
    (root / "evidence" / "EV-0001" / "summary.md").unlink()
    (root / "evidence" / "EV-0001" / "sub" / "raw.json").unlink()
    (root / "evidence" / "EV-0001" / "sub").rmdir()
    (root / "evidence" / "EV-0001").rmdir()
    assert _run(root, "add", "--title", "Next", "--origin", "build/z") == 0
    assert [r["id"] for r in _manifest(root)["records"]] == ["EV-0002"]


@pytest.mark.parametrize("damage, expected", [
    (lambda r: (r / "evidence/EV-0001/summary.md").write_bytes(b"line\nkept bytes\n"), "EV-0001: changed summary.md"),
    (lambda r: (r / "evidence/EV-0001/extra.txt").write_bytes(b"x"), "EV-0001: unlisted extra.txt"),
    (lambda r: (r / "evidence/EV-0001/sub/raw.json").unlink(), "EV-0001: missing sub/raw.json"),
    (lambda r: (r / "evidence/EV-0009").mkdir(), "unmanifested entry evidence/EV-0009"),
    (lambda r: (r / "evidence/notes.md").write_text("x"), "unmanifested entry evidence/notes.md"),
    (lambda r: (r / "docs/A.md").write_text("See EV-0002.\n"), "docs/A.md:1: unknown EV-0002"),
    (lambda r: (r / "README.md").write_text("x\n[r](evidence/EV-0001/gone.json).\n"), "README.md:2: EV-0001 has no gone.json"),
    (lambda r: (r / "evidence/EV-0001/big.bin").write_bytes(b"0" * (FILE_CAP + 1)), "big.bin is"),
    (lambda r: (r / "evidence/manifest.json").write_text(
        json.dumps(_manifest(r)), encoding="utf-8"), "not in canonical form"),
])
def test_check_reports_each_drift(tmp_path, damage, expected):
    root = _sealed(tmp_path)
    damage(root)
    problems = check(root)
    assert any(expected in problem for problem in problems), problems


def test_valid_citations_to_records_files_and_folders_pass(tmp_path):
    root = _sealed(tmp_path)
    (root / "docs" / "nested").mkdir()
    (root / "docs" / "nested" / "B.md").write_text(
        "EV-0001 and [x](../../evidence/EV-0001/summary.md), `evidence\\EV-0001\\sub\\`.\n"
        "Folder evidence/EV-0001/ and evidence/EV-0001/sub.\n"
        "[a](evidence/EV-0001/summary.md#top) [evidence/EV-0001/summary.md] see evidence/EV-0001/summary.md!\n"
        "Unrelated build/evidence/EV-0001/missing.json is not a record path. EV-0001 EV-0001\n",
        encoding="utf-8")
    (root / "docs" / "obsolete").mkdir()
    (root / "docs" / "obsolete" / "OLD.md").write_text("Archived EV-0042.\n", encoding="utf-8")
    assert check(root) == []
    (root / "docs" / "C.md").write_text("EV-0001 EV-0001 evidence/EV-0001/gone.md\n", encoding="utf-8")
    assert check(root) == ["docs/C.md:1: EV-0001 has no gone.md"]


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(format=2),
    lambda d: d.update(next_id=1),
    lambda d: d["records"][0].update(id="EV-1"),
    lambda d: d["records"][0].update(id="EV-0000"),
    lambda d: d["records"][0].update(date="2026-02-30"),
    lambda d: d["records"][0].update(title=" padded"),
    lambda d: d["records"][0].update(origin=""),
    lambda d: d["records"].append(dict(d["records"][0])),
    lambda d: d["records"][0]["files"][0].update(sha256="ABC"),
    lambda d: d["records"][0]["files"][0].update(bytes="2"),
    lambda d: d["records"][0].pop("origin"),
    lambda d: d["records"][0].update(title="two\rlines"),
    lambda d: d["records"][0]["files"].reverse(),
    lambda d: d["records"][0]["files"].append(dict(d["records"][0]["files"][-1])),
])
def test_structurally_invalid_manifest_fails_closed(tmp_path, mutate):
    root = _sealed(tmp_path)
    data = _manifest(root)
    mutate(data)
    path = root / "evidence" / "manifest.json"
    path.write_text(render(data), encoding="utf-8", newline="\n")
    before = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        _run(root, "check")
    assert error.value.code == 2
    with pytest.raises(SystemExit):
        _run(root, "add", "--title", "t", "--origin", "o")
    assert path.read_bytes() == before


def _refused(capsys, root: Path, *argv: str) -> str:
    capsys.readouterr()
    with pytest.raises(SystemExit) as error:
        _run(root, *argv)
    assert error.value.code == 2
    return capsys.readouterr().err


def test_seal_refuses_oversize_empty_and_altered_records_without_writing(tmp_path, monkeypatch, capsys):
    root = _sealed(tmp_path)
    path = root / "evidence" / "manifest.json"
    before = path.read_bytes()
    big = root / "evidence" / "EV-0001" / "big.bin"
    big.write_bytes(b"0" * (FILE_CAP + 1))
    assert "big.bin is" in _refused(capsys, root, "seal", "EV-0001")
    big.unlink()
    monkeypatch.setattr(evidence, "RECORD_CAP", 10)
    assert "record exceeds 10 bytes" in _refused(capsys, root, "seal", "EV-0001")
    monkeypatch.undo()
    for index in range(evidence.FILE_LIMIT - 1):
        (root / "evidence" / "EV-0001" / f"run-{index:02d}.json").write_bytes(b"{}")
    assert f"limit is {evidence.FILE_LIMIT}" in _refused(capsys, root, "seal", "EV-0001")
    for index in range(evidence.FILE_LIMIT - 1):
        (root / "evidence" / "EV-0001" / f"run-{index:02d}.json").unlink()
    summary = root / "evidence" / "EV-0001" / "summary.md"
    summary.write_bytes(b"tampered")
    assert "sealed files changed or missing (summary.md)" in _refused(capsys, root, "seal", "EV-0001")
    summary.unlink()
    assert "sealed files changed or missing (summary.md)" in _refused(capsys, root, "seal", "EV-0001")
    assert path.read_bytes() == before
    summary.write_bytes(b"line\r\nkept bytes\n")
    (root / "evidence" / "EV-0001" / "added.txt").write_bytes(b"new")
    assert _run(root, "seal", "EV-0001") == 0
    assert check(root) == []
    assert _run(root, "add", "--title", "Empty", "--origin", "o") == 0
    after_add = path.read_bytes()
    assert "EV-0002: record has no files" in _refused(capsys, root, "seal", "EV-0002")
    assert "EV-0002: record has no files" in check(root)
    assert "unknown record EV-0099" in _refused(capsys, root, "seal", "EV-0099")
    (root / "evidence" / "EV-0003").mkdir()
    assert "already exists" in _refused(capsys, root, "add", "--title", "t", "--origin", "o")
    assert path.read_bytes() == after_add


def test_seal_refuses_links(tmp_path):
    root = _sealed(tmp_path)
    _winapi.CreateJunction(str(root / "docs"), str(root / "evidence" / "EV-0001" / "link"))
    with pytest.raises(SystemExit):
        _run(root, "seal", "EV-0001")
    assert any("link not allowed" in problem for problem in check(root))


def test_list_reports_citations(tmp_path, capsys):
    root = _sealed(tmp_path)
    (root / "AGENTS.md").write_text("x\nEV-0001 twice EV-0001\n", encoding="utf-8")
    capsys.readouterr()
    assert _run(root, "list", "--format", "jsonl") == 0
    record = json.loads(capsys.readouterr().out)
    assert record["cited_by"] == ["AGENTS.md:2"]
    assert _run(root, "list") == 0
    assert "EV-0001 — Cleanup receipts (2026-11-14; 2 files, 19 bytes)" in capsys.readouterr().out


def test_real_evidence_tree_is_valid():
    assert check(DEFAULT_ROOT) == []
    assert "/evidence/** -text" in (DEFAULT_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()


def test_cli_from_other_directory(tmp_path):
    root = _sealed(tmp_path / "repo")
    tool = DEFAULT_ROOT / "tools" / "evidence.py"
    result = subprocess.run([sys.executable, str(tool), "--root", str(root), "check"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    (root / "evidence" / "EV-0001" / "summary.md").write_bytes(b"x")
    result = subprocess.run([sys.executable, str(tool), "--root", str(root), "check"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 1
    assert "EV-0001: changed summary.md" in result.stdout
