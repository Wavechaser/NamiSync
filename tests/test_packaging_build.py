"""Release input identity and repeatable archive boundaries."""

import io
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.packaging import build
from tools.packaging.notices import write_notices


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.name", "Packaging test")
    git("config", "user.email", "packaging@example.invalid")
    git("config", "core.autocrlf", "false")
    for name in build.SOURCE_PATHS:
        path = tmp_path / name
        if "." not in path.name and name != "LICENSE":
            path.mkdir(parents=True)
            path = path / "sample.txt"
        path.write_bytes(b"committed\n")
    git("add", ".")
    git("commit", "-m", "Fixture")
    return tmp_path


def test_snapshot_uses_committed_bytes_not_checkout_newlines(repository: Path) -> None:
    subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=repository, check=True)
    (repository / "README.md").write_bytes(b"committed\r\n")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    revision, epoch, data = build.source_snapshot(repository)
    assert len(revision) == 40
    assert epoch > 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read("README.md") == b"committed\n"


def test_source_archive_preserves_verbatim_notices_with_autocrlf(repository: Path) -> None:
    (repository / ".gitattributes").write_text("/tools/packaging/notices/*.txt -text\n", encoding="utf-8")
    notice = repository / "tools/packaging/notices/example.txt"
    notice.parent.mkdir()
    notice.write_bytes(b"upstream\r\nnotice\r\n")
    subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=repository, check=True)
    subprocess.run(["git", "add", ".gitattributes", str(notice)], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "Exact notice bytes"], cwd=repository, check=True, capture_output=True)
    _, _, data = build.source_snapshot(repository)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read("tools/packaging/notices/example.txt") == notice.read_bytes()
        assert b"/tools/packaging/notices/*.txt -text" in archive.read(".gitattributes")


@pytest.mark.parametrize("kind", ["tracked", "staged", "untracked"])
def test_snapshot_refuses_uncommitted_inputs(repository: Path, kind: str) -> None:
    name = "unexpected.txt" if kind == "untracked" else "README.md"
    (repository / name).write_text("changed", encoding="utf-8")
    if kind == "staged":
        subprocess.run(["git", "add", name], cwd=repository, check=True)
    with pytest.raises(RuntimeError, match="clean checkout"):
        build.source_snapshot(repository)


def test_archive_ignores_input_order_and_file_timestamps(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"first")
    (tmp_path / "b").write_bytes(b"second")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    build.write_archive(first, tmp_path, ["b", "a"], 1_700_000_000)
    (tmp_path / "a").touch()
    build.write_archive(second, tmp_path, ["a", "b"], 1_700_000_000)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["a", "b"]
        assert archive.read("a") == b"first"
    with pytest.raises(FileExistsError):
        build.write_archive(first, tmp_path, ["a"], 1_700_000_000)


@pytest.mark.parametrize("extra", [None, ("pip", "2"), ("unexpected", "1")])
def test_environment_requires_exact_lock(tmp_path: Path, monkeypatch, extra) -> None:
    (tmp_path / "bootstrap.txt").write_text("pip==1 --hash=sha256:example\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("-r bootstrap.txt\n", encoding="utf-8")
    versions = {"pip": "1", "namisync": "0.1.0"}
    if extra:
        versions[extra[0]] = extra[1]
    monkeypatch.setattr(build, "distributions", lambda: [
        SimpleNamespace(metadata={"Name": name}, version=version)
        for name, version in versions.items()
    ])
    if extra:
        with pytest.raises(RuntimeError, match="differs from lock"):
            build.check_environment(tmp_path)
    else:
        assert build.check_environment(tmp_path) == {"pip": "1"}


def test_freezer_path_excludes_ambient_applications(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "unrelated-app"))
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    monkeypatch.setattr(build.sys, "prefix", str(tmp_path / "env"))
    monkeypatch.setattr(build.sys, "base_prefix", str(tmp_path / "Python"))
    environment = build.freezer_environment()
    assert environment["PATH"].split(os.pathsep) == [str(tmp_path / path) for path in (
        "env/Scripts", "Python", "Python/DLLs", "Windows/System32", "Windows",
    )]
    assert os.environ["PATH"] == str(tmp_path / "unrelated-app")


@pytest.mark.parametrize("case", ["accepted", "ambient", "changed", "ucrt"])
def test_native_origin_receipt_rejects_unreviewed_inputs(tmp_path: Path, monkeypatch, case: str) -> None:
    environment = tmp_path / "env"
    environment.mkdir()
    monkeypatch.setattr(build.sys, "prefix", str(environment))
    monkeypatch.setattr(build.sys, "base_prefix", str(tmp_path / "Python"))
    name = "ucrtbase.dll" if case == "ucrt" else "VCRUNTIME140.dll"
    source = (tmp_path if case == "ambient" else environment) / name
    source.write_bytes(b"native input")
    work = tmp_path / "work"
    work.mkdir()
    table = repr(([(name, str(source), "BINARY")],))
    (work / "COLLECT-00.toc").write_text(table, encoding="utf-8")
    (work / "Analysis-00.toc").write_text("[]", encoding="utf-8")
    bundle = tmp_path / "bundle"
    (bundle / "_internal").mkdir(parents=True)
    (bundle / "_internal" / name).write_bytes(b"changed" if case == "changed" else source.read_bytes())
    if case != "accepted":
        with pytest.raises(RuntimeError, match={
            "ambient": "outside build environment", "changed": "differ from input",
            "ucrt": "must not be bundled",
        }[case]):
            build.record_native_origins(work, bundle, tmp_path)
        assert not (tmp_path / "native-origins.json").exists()
        return
    build.record_native_origins(work, bundle, tmp_path)
    receipt = json.loads((tmp_path / "native-origins.json").read_text(encoding="utf-8"))
    assert receipt["native_files"] == [{
        "path": name, "source": str(source.resolve()), "kind": "BINARY", "sha256": build.digest(source),
    }]
    assert (tmp_path / "freezer-tables/COLLECT-00.toc").read_text(encoding="utf-8") == table
    assert (tmp_path / "freezer-tables/Analysis-00.toc").read_text(encoding="utf-8") == "[]"


def test_distribution_notices_export_app_and_runtime_corpora(tmp_path: Path) -> None:
    write_notices(build.ROOT, tmp_path)
    output = (tmp_path / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")
    legal = (build.ROOT / "namisync/interfaces/web/assets/legal_content.js").read_text(encoding="utf-8")
    records = json.loads(legal.split("const notices = ", 1)[1].split("\n];", 1)[0] + "\n]")
    for record in records:
        assert record["text"].replace("\r\n", "\n") in output
        assert record["source"] in output
        if record.get("note"):
            assert record["note"] in output
    directory = build.ROOT / "tools/packaging/notices"
    supplements = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert {record["file"] for record in supplements} == {
        path.name for path in directory.glob("*.txt") if path.name != "README.txt"
    }
    for record in supplements:
        assert (directory / record["file"]).read_text(encoding="utf-8") in output
        assert record["source"] in output
        if record.get("note"):
            assert record["note"] in output
    assert "Notice text SHA-256:" in output
    assert "Upstream notice SHA-256:" not in output
    assert "Microsoft binary conditions" in output
    assert "Mozilla Public License, version 2.0" in output
    assert "PyInstaller bootloader zlib — 1.3.2" in output
    assert "(C) 1995-2026 Jean-loup Gailly and Mark Adler" in output
    assert "HACL* hash implementations in CPython" in output
    assert "INRIA, CMU and Microsoft Corporation" in output
    assert "HACL* KaRaMeL support headers in CPython" in output
    assert "Copyright (c) 2008-2012 Stefan Krah" in output
    assert "Copyright (c) 2004 by Secret Labs AB" in output
    assert "Copyright 1992-1994, David Gottner" in output


def test_distribution_notices_refuse_changed_supplement(tmp_path: Path) -> None:
    source = tmp_path / "source"
    legal = source / "namisync/interfaces/web/assets/legal_content.js"
    legal.parent.mkdir(parents=True)
    shutil.copyfile(build.ROOT / "namisync/interfaces/web/assets/legal_content.js", legal)
    directory = source / "tools/packaging/notices"
    shutil.copytree(build.ROOT / "tools/packaging/notices", directory)
    record = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))[0]
    (directory / record["file"]).write_bytes(b"altered notice")
    with pytest.raises(ValueError, match="Notice identity mismatch"):
        write_notices(source, tmp_path)
    assert not (tmp_path / "THIRD-PARTY-NOTICES.txt").exists()
