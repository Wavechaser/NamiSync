from __future__ import annotations

from dataclasses import replace
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
        second = corpus.generate(workspace, "3@17B", seed=42)

    assert first.files == second.files == 3
    assert first.bytes_written == second.bytes_written == 51
    assert _files(root) == expected
    assert corpus.is_owned(root)
    assert corpus.marker_for(root).exists()
    assert corpus.outputs_for(root).exists()


def test_generate_refuses_unknown_descendants_without_deleting_anything(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated"

    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "3@17B", seed=42)
        expected = _files(root)
        foreign = root / "not-from-the-rig.txt"
        foreign.write_text("keep", encoding="utf-8")

        with pytest.raises(corpus.CorpusError, match="not owned"):
            corpus.generate(workspace, "3@17B", seed=42)

    assert _files(root) == {**expected, "not-from-the-rig.txt": b"keep"}
    assert corpus.outputs_for(root).exists()


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


def test_claim_refuses_a_hard_linked_ownership_marker(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root):
        pass
    marker = corpus.marker_for(root)
    alias = tmp_path / "marker-alias.json"
    os.link(marker, alias)

    with pytest.raises(corpus.CorpusError, match="single-link"):
        corpus.claim(root)

    assert marker.exists()
    assert alias.exists()


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
            corpus.force_teardown(workspace)
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
            corpus.force_teardown(workspace)
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
        corpus.force_teardown(workspace)
        workspace.close()


def test_claim_rejects_every_generic_reparse_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    monkeypatch.setattr(corpus, "is_reparse_stat", lambda observed: True)

    with pytest.raises(corpus.CorpusError, match="reparse point"):
        corpus.claim(root)

    assert root.exists()
    assert not corpus.marker_for(root).exists()


def test_claim_rejects_a_generic_reparse_ancestor_that_keeps_its_spelling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "generic-reparse-parent"
    parent.mkdir()
    parent_inode = parent.stat().st_ino
    root = parent / "owned"
    monkeypatch.setattr(
        corpus,
        "is_reparse_stat",
        lambda observed: observed.st_ino == parent_inode,
    )

    with pytest.raises(corpus.CorpusError, match="must not traverse a reparse point"):
        corpus.claim(root)

    assert not root.exists()
    assert not corpus.marker_for(root).exists()


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


def test_exact_cleanup_refuses_replaced_and_hard_linked_outputs(
    tmp_path: Path,
) -> None:
    replaced_root = tmp_path / "replaced"
    with corpus.claim(replaced_root) as workspace:
        corpus.generate(workspace, "1@8B")
        generated = next(replaced_root.rglob("*.bin"))
        payload = generated.read_bytes()
        generated.unlink()
        generated.write_bytes(payload)

        with pytest.raises(corpus.CorpusError, match="identity changed"):
            corpus.empty(workspace)
        assert generated.read_bytes() == payload

    linked_root = tmp_path / "linked"
    with corpus.claim(linked_root) as workspace:
        corpus.generate(workspace, "1@8B")
        generated = next(linked_root.rglob("*.bin"))
        outside_link = tmp_path / "outside-link.bin"
        os.link(generated, outside_link)

        with pytest.raises(corpus.CorpusError, match="metadata changed"):
            corpus.empty(workspace)
        assert generated.exists()
        assert outside_link.exists()


@pytest.mark.parametrize(
    "malformation",
    ["duplicate_field", "wrong_root", "duplicate_entry", "unsorted_entries"],
)
def test_exact_cleanup_refuses_malformed_output_manifests_before_deletion(
    tmp_path: Path,
    malformation: str,
) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "2@8B", per_directory=1)
        manifest = corpus.outputs_for(root)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if malformation == "duplicate_field":
            text = manifest.read_text(encoding="utf-8")
            manifest.write_text(
                text.replace('"schema":1', '"schema":1,"schema":1', 1),
                encoding="utf-8",
            )
        elif malformation == "wrong_root":
            payload["path"] = str(tmp_path / "different-root")
            manifest.write_text(json.dumps(payload), encoding="utf-8")
        elif malformation == "duplicate_entry":
            payload["entries"].append(payload["entries"][0])
            manifest.write_text(json.dumps(payload), encoding="utf-8")
        else:
            payload["entries"].reverse()
            manifest.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(corpus.CorpusError):
            corpus.empty(workspace)

        assert len(tuple(root.rglob("*.bin"))) == 2


def test_exact_cleanup_refuses_oversized_and_hard_linked_output_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized_root = tmp_path / "oversized"
    with corpus.claim(oversized_root) as workspace:
        corpus.generate(workspace, "1@8B")
        manifest = corpus.outputs_for(oversized_root)
        monkeypatch.setattr(corpus, "OUTPUTS_MAX_BYTES", manifest.stat().st_size - 1)

        with pytest.raises(corpus.CorpusError, match="manifest is too large"):
            corpus.empty(workspace)

        assert next(oversized_root.rglob("*.bin")).exists()
    monkeypatch.undo()

    linked_root = tmp_path / "linked-manifest"
    with corpus.claim(linked_root) as workspace:
        corpus.generate(workspace, "1@8B")
        manifest = corpus.outputs_for(linked_root)
        alias = tmp_path / "manifest-alias.json"
        os.link(manifest, alias)

        with pytest.raises(corpus.CorpusError, match="single-link"):
            corpus.empty(workspace)

        assert next(linked_root.rglob("*.bin")).exists()
        assert alias.exists()


def test_exact_cleanup_refuses_a_generic_reparse_output_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        manifest = corpus.outputs_for(root)
        original = corpus._is_reparse_point
        monkeypatch.setattr(
            corpus,
            "_is_reparse_point",
            lambda path: Path(path) == manifest or original(path),
        )

        with pytest.raises(corpus.CorpusError, match="manifest must not be a reparse"):
            corpus.empty(workspace)

        assert next(root.rglob("*.bin")).exists()


def test_output_manifest_publication_refuses_an_occupant_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "owned"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        manifest = corpus.outputs_for(root)
        replacement = tmp_path / "replacement.json"
        replacement.write_text("replacement occupant", encoding="utf-8")
        original_mkstemp = corpus.tempfile.mkstemp
        original_replace = corpus.os.replace

        def swap_then_create_temp(*args, **kwargs):
            original_replace(replacement, manifest)
            return original_mkstemp(*args, **kwargs)

        monkeypatch.setattr(corpus.tempfile, "mkstemp", swap_then_create_temp)
        files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        directories = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_dir()
        }

        with pytest.raises(corpus.CorpusError, match="replaced before publication"):
            corpus.record_outputs(
                workspace,
                files=files,
                directories=directories,
            )

        assert manifest.read_text(encoding="utf-8") == "replacement occupant"


def test_marker_only_nonempty_workspace_requires_explicit_force_cleanup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy"
    workspace = corpus.claim(root)
    sentinel = root / "inspect-me.txt"
    sentinel.write_text("keep", encoding="utf-8")
    try:
        with pytest.raises(corpus.CorpusError, match="without an exact output manifest"):
            corpus.teardown(workspace)
        assert sentinel.read_text(encoding="utf-8") == "keep"

        plan = corpus.inspect_force_cleanup(workspace)
        assert plan.files == 1
        result = corpus.force_teardown(workspace)
        assert result == corpus.CleanupResult(1, 0, 4, True)
    finally:
        workspace.close()

    assert not root.exists()
    assert not corpus.marker_for(root).exists()


def test_force_cleanup_refuses_entries_added_after_the_inspected_plan(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy"
    workspace = corpus.claim(root)
    displayed = root / "displayed.txt"
    displayed.write_text("displayed", encoding="utf-8")
    try:
        plan = corpus.inspect_force_cleanup(workspace)
        late = root / "late.txt"
        late.write_text("late", encoding="utf-8")

        with pytest.raises(corpus.CorpusError, match="nothing was deleted"):
            corpus.force_teardown(workspace, plan)

        assert displayed.read_text(encoding="utf-8") == "displayed"
        assert late.read_text(encoding="utf-8") == "late"
    finally:
        if root.exists():
            corpus.force_teardown(workspace)
        workspace.close()


def test_exact_cleanup_rejects_a_forged_non_manifest_plan(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    workspace = corpus.claim(root)
    foreign = root / "foreign.txt"
    foreign.write_text("keep", encoding="utf-8")
    try:
        forced = corpus.inspect_force_cleanup(workspace)
        forged = replace(forced, manifest=None, forced=False)

        with pytest.raises(corpus.CorpusError, match="requires the bound output manifest"):
            corpus.empty(workspace, forged)

        assert foreign.read_text(encoding="utf-8") == "keep"
    finally:
        if root.exists():
            corpus.force_teardown(workspace)
        workspace.close()


def test_exact_cleanup_tolerates_already_missing_outputs(tmp_path: Path) -> None:
    root = tmp_path / "retry"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        next(root.rglob("*.bin")).unlink()

        result = corpus.empty(workspace)

    assert result.files == 0
    assert result.directories == 1
    assert not any(root.iterdir())
    assert not corpus.outputs_for(root).exists()


def test_partial_cleanup_retains_manifest_and_reports_completed_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "partial"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "2@8B")
        original_unlink = corpus._unlink_writable
        calls = 0

        def fail_second(path: Path) -> None:
            nonlocal calls
            if path.suffix == ".bin":
                calls += 1
                if calls == 2:
                    raise PermissionError("injected refusal")
            original_unlink(path)

        monkeypatch.setattr(corpus, "_unlink_writable", fail_second)

        with pytest.raises(corpus.CorpusError, match="after removing 1 files"):
            corpus.empty(workspace)

        assert corpus.outputs_for(root).exists()
        assert len(tuple(root.rglob("*.bin"))) == 1


def test_post_delete_validation_failure_reports_exact_removed_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "partial"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        generated = next(root.rglob("*.bin"))
        relative = generated.relative_to(root).as_posix()
        plan = corpus.inspect_cleanup(workspace)
        original_inventory = corpus._inventory
        calls = 0

        def fail_post_delete(target: Path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise corpus.CorpusError("injected post-delete validation failure")
            return original_inventory(target)

        monkeypatch.setattr(corpus, "_inventory", fail_post_delete)

        with pytest.raises(corpus.CorpusError) as error:
            corpus.empty(workspace, plan)

        message = str(error.value)
        assert "after removing 1 files" in message
        assert relative in message
        assert "workspace state could not be validated" in message
        assert corpus.outputs_for(root).exists()


def test_disappeared_manifest_receipt_does_not_claim_it_remains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "partial"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        plan = corpus.inspect_cleanup(workspace)
        manifest = corpus.outputs_for(root)
        original_load = corpus._load_outputs
        calls = 0

        def disappear_after_delete(path: Path, target: Path, identity: tuple[int, int]):
            nonlocal calls
            calls += 1
            if calls == 2:
                manifest.unlink()
            return original_load(path, target, identity)

        monkeypatch.setattr(corpus, "_load_outputs", disappear_after_delete)

        with pytest.raises(corpus.CorpusError) as error:
            corpus.empty(workspace, plan)

        assert "output manifest is missing from" in str(error.value)
        assert "manifest remains" not in str(error.value)


def test_keyboard_interrupt_during_cleanup_is_normalized_to_a_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "partial"
    with corpus.claim(root) as workspace:
        corpus.generate(workspace, "1@8B")
        original_unlink = corpus._unlink_writable

        def interrupt(path: Path) -> None:
            if path.suffix == ".bin":
                raise KeyboardInterrupt()
            original_unlink(path)

        monkeypatch.setattr(corpus, "_unlink_writable", interrupt)

        with pytest.raises(corpus.CorpusError, match="after removing 0 files"):
            corpus.empty(workspace)

        assert next(root.rglob("*.bin")).exists()
        assert corpus.outputs_for(root).exists()


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
        relative_deep = deep.relative_to(root)
        directories = {"d0000"}
        current = Path()
        for part in relative_deep.parts:
            current /= part
            directories.add(current.as_posix())
        corpus.record_outputs(
            workspace,
            files={
                generated.relative_to(root).as_posix(),
                (relative_deep / "data.bin").as_posix(),
            },
            directories=directories,
        )
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
