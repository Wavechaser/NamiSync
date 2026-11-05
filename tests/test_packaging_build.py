"""Release input identity and repeatable archive boundaries."""

import io
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.packaging import build


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
