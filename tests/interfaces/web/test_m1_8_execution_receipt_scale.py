"""Functional controls for selected installed execution receipt measurements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.performance import execution_receipt as adapter


def _registry(*, wrong: str | None = None):
    request_id = "a" * 32
    row = {
        "task_id": "task-" + "b" * 32,
        "request_id": request_id,
        "plan_session_id": "c" * 32,
        "source_path": r"C:\source",
        "target_path": r"D:\target",
    }
    expected = hashlib.blake2b(digest_size=16, person=b"NamiSyncPriorV1")
    encoded = request_id.encode()
    expected.update(len(encoded).to_bytes(4, "big"))
    expected.update(encoded)
    first = {
        "node_id": "node-" + expected.hexdigest(),
        "row_kind": "prior-group", "display": "Previous paths",
        "operation_id": None, "operation_kind": None,
        "visible_index": 0, "depth": 0,
        "parent_visible_index": None, "first_child_visible_index": 1,
    }
    summary = {
        "disposition": "opened", "task_id": row["task_id"],
        "request_id": request_id, "source_path": row["source_path"],
        "target_path": row["target_path"], "view_revision": 0,
    }
    window = {
        "disposition": "current", "view_revision": 0, "offset": 0,
        "total": 119_999, "rows": [first, *({"node_id": str(i)} for i in range(255))],
    }
    if wrong == "prior-id":
        first["node_id"] = "node-" + "0" * 32
    elif wrong == "public-total":
        window["total"] = 120_000
    elif wrong == "first-row-kind":
        first["row_kind"] = "folder"
    elif wrong == "view":
        summary["view_revision"] = 1

    class Registry:
        _plan_views = {row["task_id"]: SimpleNamespace(projection=SimpleNamespace(nodes=range(120_000)))}

        def open_plan_view(self, task_id):
            assert task_id == row["task_id"]
            return summary

        def get_plan_window(self, task_id, *, expected_revision, offset, limit):
            assert (task_id, expected_revision, offset, limit) == (row["task_id"], summary["view_revision"], 0, 256)
            return window

    return Registry(), row


def test_rootless_fixture_settles_real_public_row_shape() -> None:
    registry, row = _registry()
    observed = adapter._rootless_settlement(registry, row)
    assert observed["window_total"] == 119_999
    assert observed["projection_node_count"] == 120_000
    assert observed["first_row"]["display"] == "Previous paths"


@pytest.mark.parametrize("wrong", ("prior-id", "public-total", "first-row-kind", "view"))
def test_rootless_fixture_rejects_false_public_geometry(wrong: str) -> None:
    registry, row = _registry(wrong=wrong)
    with pytest.raises(AssertionError, match="initial view"):
        adapter._rootless_settlement(registry, row)


def test_rootless_patch_is_scoped_to_measurement() -> None:
    original = adapter.legacy._HeadedFixtureController._settle_initial_view
    with adapter._rootless_fixture_adapter():
        assert adapter.legacy._HeadedFixtureController._settle_initial_view is adapter._rootless_settlement
    assert adapter.legacy._HeadedFixtureController._settle_initial_view is original


def test_selected_receipt_rejects_false_action_even_with_fast_sample(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from tools.performance import _child

    metric = next(row for row in json.loads(adapter.CONTRACT_PATH.read_bytes())["metrics"]
                  if row["id"] == adapter.CASES[0])

    def child(*_args, **_kwargs):
        return {
            "metric_id": adapter.CASES[0], "launch_token": "d" * 32,
            "samples": [{"elapsed_ns": 1, "correctness": {"accepted": False}}] * 6,
            "headed_fixture": {"published_plan_count": 1},
        }

    monkeypatch.setattr(adapter, "uuid4", lambda: SimpleNamespace(hex="d" * 32))
    monkeypatch.setattr(_child, "run_child", child)
    assert metric["correctness"] != {"accepted": False}
    with pytest.raises(RuntimeError, match="false observation"):
        adapter.run_case(adapter.CASES[0], output=tmp_path / "report.json", installed_root=tmp_path)
