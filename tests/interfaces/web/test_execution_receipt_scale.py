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
    destination = "\\".join(f"target{index:02d}" for index in range(31))
    for value in (request_id, "", destination.upper()):
        encoded = value.encode()
        expected.update(len(encoded).to_bytes(4, "big"))
        expected.update(encoded)
    first = {
        "node_id": "node-" + expected.hexdigest(),
        "row_kind": "prior-group", "display": "1 item moved to …\\target30",
        "operation_id": None, "operation_kind": None,
        "visible_index": 0, "depth": 0,
        "parent_visible_index": None, "first_child_visible_index": None, "expanded": False,
    }
    summary = {
        "disposition": "opened", "task_id": row["task_id"],
        "request_id": request_id, "source_path": row["source_path"],
        "target_path": row["target_path"], "view_revision": 0,
    }
    window = {
        "disposition": "current", "view_revision": 0, "offset": 0,
        "total": 119_968, "rows": [first, *({"node_id": str(i)} for i in range(255))],
    }
    if wrong == "prior-id":
        first["node_id"] = "node-" + "0" * 32
    elif wrong == "public-total":
        window["total"] = 120_000
    elif wrong == "first-row-kind":
        first["row_kind"] = "folder"
    elif wrong == "label":
        first["display"] = "1 item moved to root"
    elif wrong == "first-child":
        first["first_child_visible_index"] = 1
    elif wrong == "expanded":
        first["expanded"] = True
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
    assert observed["window_total"] == 119_968
    assert observed["projection_node_count"] == 120_000
    assert observed["first_row"]["display"] == "1 item moved to …\\target30"
    assert observed["first_row"]["expanded"] is False
    assert observed["first_row"]["first_child_visible_index"] is None


@pytest.mark.parametrize("wrong", ("prior-id", "public-total", "first-row-kind", "label", "first-child", "expanded", "view"))
def test_rootless_fixture_rejects_false_public_geometry(wrong: str) -> None:
    registry, row = _registry(wrong=wrong)
    with pytest.raises(AssertionError, match="initial view"):
        adapter._rootless_settlement(registry, row)


def test_rootless_patch_is_scoped_to_measurement() -> None:
    original = adapter.legacy._HeadedFixtureController._settle_initial_view
    with adapter._rootless_fixture_adapter():
        assert adapter.legacy._HeadedFixtureController._settle_initial_view is adapter._rootless_settlement
    assert adapter.legacy._HeadedFixtureController._settle_initial_view is original


def test_rootless_helper_accepts_real_published_base_view(tmp_path: Path) -> None:
    from namisync.interfaces.service import NamiSyncService
    from namisync.interfaces.web.drain import TaskRegistry
    from namisync.interfaces.web.commands import production_command_specs

    service = NamiSyncService(tmp_path / "ledger.db", tmp_path / "history.db", settings_path=tmp_path / "settings.json")
    try:
        service.initialize_database_contracts()
        registry = TaskRegistry(service)
        production_command_specs(picker=lambda: None, slots=SimpleNamespace(), registry=registry,
            cosmetics=SimpleNamespace(), shell_ready=lambda _payload: None, readiness_echo=lambda *_args: True)
        with adapter._rootless_fixture_adapter():
            controller = adapter.legacy._HeadedFixtureController({"id": "rootless-helper-control"}, tmp_path / "fixture", 1)
            controller.bind(registry)
        row = controller.published_fixture["rows"][0]
        observed = row["initial_view_settlement"]
        assert row["session_state"] == "completed" and row["session_released"]
        assert observed["first_row"]["display"] == "1 item moved to …\\target30"
        assert observed["window_total"] == 119_968 and observed["window_row_count"] == 256
        window = registry.get_plan_window(row["task_id"], expected_revision=0, offset=0, limit=256)
        _check_published_browser_window(tmp_path, window)
    finally:
        assert service.close().complete


def _check_published_browser_window(tmp_path: Path, window: dict) -> None:
    from _frontend_test_support import _node_executable, run_node_probe

    node = _node_executable()
    assert node is not None, "Node.js is required for the published-window validator witness"
    assets = Path(__file__).parents[3] / "namisync/interfaces/web/assets"
    (tmp_path / "bridge.mjs").write_text(
        (assets / "bridge.js").read_text(encoding="utf-8") + "\nexport {validatePlanWindow};\n", encoding="utf-8",
    )
    (tmp_path / "window.json").write_text(json.dumps(window), encoding="utf-8")
    probe = tmp_path / "published-window.mjs"
    probe.write_text("""import assert from 'node:assert/strict';
import fs from 'node:fs';
globalThis.window = {addEventListener() {}};
const {validatePlanWindow} = await import('./bridge.mjs');
const window = JSON.parse(fs.readFileSync(new URL('./window.json', import.meta.url), 'utf8'));
assert.equal(validatePlanWindow(window), true, 'real published fixture window must pass production validation');
const renamed = window.rows.find(row => row.operation_kind === 'recase');
assert.ok(renamed?.prior_name);
renamed.prior_name = null;
assert.equal(validatePlanWindow(window), false, 'missing prior name must remain rejected');
""", encoding="utf-8")
    result = run_node_probe((node, probe), timeout=10)
    assert result.returncode == 0, result.stderr


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
