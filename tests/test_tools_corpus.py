from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat

import pytest

from tools import corpus
from namisync.core.pathing import to_extended_length_path


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_generate_replaces_owned_contents_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "generated"

    with corpus.claim(root) as workspace:
        first = corpus.generate(workspace, "3@17B", seed=42)
        expected = _files(root)
        (root / "stale.txt").write_text("stale", encoding="utf-8")

        second = corpus.generate(workspace, "3@17B", seed=42)

    assert first.files == second.files == 3
    assert first.bytes_written == second.bytes_written == 51
    assert _files(root) == expected
    assert corpus.is_owned(root)
    assert corpus.marker_for(root).exists()


def test_claim_refuses_a_nonempty_unowned_directory(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "user-data.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(corpus.CorpusError, match="nonempty directory"):
        corpus.claim(root)

    assert (root / "user-data.txt").read_text(encoding="utf-8") == "keep"
    assert not corpus.marker_for(root).exists()
    assert not corpus.lease_for(root).exists()


def test_marker_is_bound_to_the_resolved_path_and_directory_identity(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root):
        pass

    payload = json.loads(corpus.marker_for(root).read_text(encoding="utf-8"))
    details = root.stat()
    assert payload == {
        "schema": corpus.MARKER_SCHEMA,
        "owner": corpus.MARKER_OWNER,
        "path": str(root.resolve()),
        "device": details.st_dev,
        "inode": details.st_ino,
    }

    replacement = tmp_path / "replacement"
    replacement.mkdir()
    assert replacement.stat().st_ino != details.st_ino
    shutil.rmtree(root)
    replacement.rename(root)

    assert not corpus.is_owned(root)
    with pytest.raises(corpus.CorpusError, match="does not describe"):
        corpus.claim(root)


def test_claim_refuses_a_malformed_marker(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root):
        pass
    corpus.marker_for(root).write_text('{"schema": 1}\n', encoding="utf-8")

    assert not corpus.is_owned(root)
    with pytest.raises(corpus.CorpusError, match="unsupported schema"):
        corpus.claim(root)


def test_claim_refuses_a_concurrent_claim(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    first = corpus.claim(root)
    try:
        with pytest.raises(corpus.CorpusError, match="already claimed"):
            corpus.claim(root)
    finally:
        first.close()

    assert not corpus.lease_for(root).exists()


def test_claim_preserves_an_unrecognized_lease_file(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    lease = corpus.lease_for(root)
    lease.write_bytes(b"user sentinel" * 8192)

    with pytest.raises(corpus.CorpusError, match="unrecognized workspace lease"):
        corpus.claim(root)

    assert lease.stat().st_size == len(b"user sentinel") * 8192
    assert not corpus.marker_for(root).exists()


def test_claim_refuses_an_oversized_marker_without_reading_it_as_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root):
        pass
    marker = corpus.marker_for(root)
    marker.write_bytes(b"{" + b" " * corpus.MARKER_MAX_BYTES + b"}")

    with pytest.raises(corpus.CorpusError, match="marker is too large"):
        corpus.claim(root)

    assert marker.stat().st_size > corpus.MARKER_MAX_BYTES


def test_claim_adopts_and_removes_a_stale_tools_lease(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    lease = corpus.lease_for(root)
    lease.write_bytes(corpus.LEASE_MAGIC)

    with corpus.claim(root):
        assert lease.exists()

    assert not lease.exists()


def test_claim_detects_reparse_point_replacement_before_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "owned"
    moved = tmp_path / "moved"
    workspace = corpus.claim(root)
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    root.rename(moved)
    try:
        try:
            os.symlink(moved, root, target_is_directory=True)
        except OSError as error:
            moved.rename(root)
            corpus.teardown(workspace)
            pytest.skip(f"directory symlinks are unavailable: {error}")

        with pytest.raises(corpus.CorpusError, match="reparse point"):
            corpus.empty(workspace)
        assert (moved / "keep.txt").read_text(encoding="utf-8") == "keep"
    finally:
        if root.is_symlink() or root.is_junction():
            root.unlink()
        if moved.exists() and not root.exists():
            moved.rename(root)
        if root.exists():
            corpus.teardown(workspace)
        workspace.close()


def test_mutation_checks_reparse_state_before_deleting_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "owned"
    workspace = corpus.claim(root)
    sentinel = root / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        corpus,
        "_is_reparse_point",
        lambda path: Path(path) == root,
    )
    try:
        with pytest.raises(corpus.CorpusError, match="reparse point"):
            corpus.empty(workspace)
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        monkeypatch.undo()
        corpus.teardown(workspace)
        workspace.close()


def test_mutations_require_a_live_claim(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    workspace = corpus.claim(root)
    workspace.close()

    with pytest.raises(TypeError, match="WorkspaceClaim"):
        corpus.empty(root)  # type: ignore[arg-type]
    with pytest.raises(corpus.CorpusError, match="no longer live"):
        corpus.generate(workspace, "1@1B")


def test_materialize_rejects_overlap_in_both_directions(tmp_path: Path) -> None:
    target = tmp_path / "target"
    with corpus.claim(target) as workspace:
        nested_template = target / "template"
        nested_template.mkdir()
        with pytest.raises(corpus.CorpusError, match="must not overlap"):
            corpus.materialize(nested_template, workspace)

    template = tmp_path / "template"
    template.mkdir()
    nested_target = template / "target"
    with corpus.claim(nested_target) as workspace:
        with pytest.raises(corpus.CorpusError, match="must not overlap"):
            corpus.materialize(template, workspace)


def test_materialize_fails_when_template_walk_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    target = tmp_path / "target"

    def fail_walk(path: str, *, onerror):
        del path
        onerror(PermissionError("denied"))

    with corpus.claim(target) as workspace:
        monkeypatch.setattr(corpus.os, "walk", fail_walk)
        with pytest.raises(corpus.CorpusError, match="could not walk"):
            corpus.materialize(template, workspace)


def test_teardown_removes_read_only_contents_marker_and_lease(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    workspace = corpus.claim(root)
    marker = corpus.marker_for(root)
    lease = corpus.lease_for(root)
    try:
        corpus.generate(workspace, "1@8B")
        generated = next(root.rglob("*.bin"))
        generated.chmod(stat.S_IREAD)
        deep = root
        while len(str(deep)) < 270:
            deep /= "long-path-segment"
        os.makedirs(to_extended_length_path(str(deep)))
        with open(to_extended_length_path(str(deep / "data.bin")), "wb") as handle:
            handle.write(b"data")
        corpus.teardown(workspace)
    finally:
        workspace.close()

    assert not root.exists()
    assert not marker.exists()
    assert not lease.exists()


@pytest.mark.parametrize("value", ["inf", "nan", "1e309", "1e309GiB"])
def test_parse_size_reports_nonfinite_values_as_value_errors(value: str) -> None:
    with pytest.raises(ValueError):
        corpus.parse_size(value)
