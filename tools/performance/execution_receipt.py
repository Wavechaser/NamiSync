"""Selected installed M1-8 execution receipt measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping
from unittest.mock import patch
from uuid import uuid4

from . import plan as legacy


CONTRACT_PATH = legacy.CONTRACT_PATH
CASES = ("ui_get_plan_window_one_row_receipt", "ui_start_execution_receipt")


def _prior_group_node_id(request_id: str) -> str:
    digest = hashlib.blake2b(digest_size=16, person=b"NamiSyncPriorV1")
    encoded = request_id.encode("utf-8")
    digest.update(len(encoded).to_bytes(4, "big"))
    digest.update(encoded)
    digest.update((0).to_bytes(4, "big"))
    digest.update((0).to_bytes(4, "big"))
    return f"node-{digest.hexdigest()}"


def _rootless_settlement(registry: object, row: Mapping[str, object]) -> dict[str, object]:
    summary = registry.open_plan_view(row["task_id"])
    window = registry.get_plan_window(
        row["task_id"], expected_revision=summary["view_revision"], offset=0, limit=256,
    )
    view = registry._plan_views[row["task_id"]]
    rows = window["rows"]
    first = rows[0] if rows else None
    if (
        summary["disposition"] != "opened" or summary["task_id"] != row["task_id"]
        or summary["request_id"] != row["request_id"]
        or summary["source_path"] != row["source_path"] or summary["target_path"] != row["target_path"]
        or summary["view_revision"] != 0 or window["disposition"] != "current"
        or window["view_revision"] != 0 or window["offset"] != 0
        or len(view.projection.nodes) != 120_000 or window["total"] != 119_999
        or len(rows) != 256 or not isinstance(first, dict)
        or first["node_id"] != _prior_group_node_id(row["request_id"])
        or first["row_kind"] != "prior-group" or first["display"] != "1 item moved to root"
        or first["operation_id"] is not None or first["operation_kind"] is not None
        or first["visible_index"] != 0 or first["depth"] != 0
        or first["parent_visible_index"] is not None or first["first_child_visible_index"] != 1
    ):
        raise AssertionError("rootless headed fixture initial view was not settled exactly")
    return {
        "first_row": first,
        "open_disposition": summary["disposition"],
        "plan_session_id": row["plan_session_id"],
        "projection_node_count": len(view.projection.nodes),
        "request_id": summary["request_id"],
        "source_path": summary["source_path"],
        "target_path": summary["target_path"],
        "task_id": summary["task_id"],
        "view_revision": summary["view_revision"],
        "window_disposition": window["disposition"],
        "window_limit": 256,
        "window_offset": window["offset"],
        "window_row_count": len(rows),
        "window_total": window["total"],
        "window_view_revision": window["view_revision"],
    }


@contextmanager
def _rootless_fixture_adapter() -> Iterator[None]:
    with patch.object(
        legacy._HeadedFixtureController, "_settle_initial_view",
        staticmethod(_rootless_settlement),
    ):
        yield


def run_headed_child(
    metric_id: str, launch_token: str, *, contract_path: Path,
    benchmark_root: Path, installed_root: Path,
) -> dict[str, object]:
    if metric_id not in CASES:
        raise ValueError("execution receipt case is invalid")
    with _rootless_fixture_adapter():
        return legacy.run_headed_child(
            metric_id, launch_token, contract_path=contract_path,
            benchmark_root=benchmark_root, installed_root=installed_root,
        )


def run_case(
    case: str, *, output: Path, installed_root: Path | None = None,
) -> dict[str, object]:
    from ._child import run_child

    if case not in CASES:
        raise ValueError(f"unknown execution receipt case: {case}")
    if installed_root is None:
        raise ValueError("execution receipt case requires --installed-root")
    token = uuid4().hex
    receipt = run_child(
        "tools.performance.execution_receipt",
        [
            "--child", case, "--launch-token", token,
            "--contract", str(CONTRACT_PATH),
            "--benchmark-root", str(output.parent),
            "--installed-root", str(installed_root),
        ],
        output=output, installed_root=installed_root,
    )
    metric = next(item for item in json.loads(CONTRACT_PATH.read_bytes())["metrics"] if item["id"] == case)
    samples = receipt.get("samples")
    fixture = receipt.get("headed_fixture")
    runtime = receipt.get("installed_runtime")
    if (
        receipt.get("metric_id") != case or receipt.get("launch_token") != token
        or type(samples) is not list or len(samples) != 6
        or any(type(sample) is not dict or sample.get("correctness") != metric["correctness"]
               or type(sample.get("elapsed_ns")) is not int or sample["elapsed_ns"] < 0
               for sample in samples)
        or type(fixture) is not dict
        or not fixture.get("published_plan_count")
        or type(runtime) is not dict
        or runtime.get("root") != str(installed_root.resolve())
        or runtime.get("namisync_file") != str((installed_root / "namisync" / "__init__.py").resolve())
        or not runtime.get("namisync_version")
    ):
        raise RuntimeError("execution receipt child returned an incomplete or false observation")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=CASES, required=True)
    parser.add_argument("--launch-token", required=True)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_headed_child(
        args.child, args.launch_token, contract_path=args.contract,
        benchmark_root=args.benchmark_root, installed_root=args.installed_root,
    )
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
