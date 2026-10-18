"""Production inventory pane and task routing, with bounded browser probes."""

from __future__ import annotations

import json
from pathlib import Path

from _frontend_test_support import ASSET_ROOT, _node_executable, run_node_probe
from _review_fixtures import inventory_probe_fixture


PROJECT_ROOT = Path(__file__).parents[3]


def _run(probe: str, fixture: Path) -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the inventory desktop witness"
    completed = run_node_probe([
        str(node), str(PROJECT_ROOT / "tests/assets" / probe),
        str(PROJECT_ROOT / ASSET_ROOT), str(fixture),
    ], timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == "ok\n"
    assert completed.stderr == ""


def test_inventory_pane_browses_server_views_and_current_evidence(tmp_path: Path) -> None:
    fixture = tmp_path / "inventory.json"
    fixture.write_text(json.dumps(inventory_probe_fixture()), encoding="utf-8")
    _run("inventory_review_probe.mjs", fixture)


def test_inventory_app_routes_released_tasks_and_rejects_stale_reads(tmp_path: Path) -> None:
    fixture = tmp_path / "inventory.json"
    fixture.write_text(json.dumps(inventory_probe_fixture()), encoding="utf-8")
    _run("inventory_app_probe.mjs", fixture)
