"""Scoped M1-8 adapter for the two rootless execution-receipt cases.

This is deliberately a small wrapper around the protected M1-7 headed child:
only its test-owned initial fixture settlement is replaced.  It retains the
legacy page script, workload, warmup, timing interval, samples, and profile.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterator, Mapping
from unittest.mock import patch
from uuid import uuid4

import plan_review_benchmark as legacy

sys.path.insert(0, str(Path(__file__).resolve().parent / "interfaces" / "web"))
import _m1_8_execution_receipt_scale as scoped
import _plan_review_scale as plan_scale


CONTRACT_PATH = Path(__file__).resolve().parent / "interfaces" / "web" / "m1_7_plan_compact_contract.json"
METRIC_IDS = scoped.METRIC_IDS


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
        or first["node_id"] != scoped._prior_group_node_id(row["request_id"])
        or first["row_kind"] != "prior-group" or first["display"] != "Previous paths"
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
        legacy._HeadedFixtureController,
        "_settle_initial_view",
        staticmethod(_rootless_settlement),
    ):
        yield


def run_headed_child(metric_id: str, launch_token: str, *, contract_path: Path,
                     benchmark_root: Path, installed_root: Path) -> dict[str, object]:
    if metric_id not in METRIC_IDS:
        raise ValueError("scoped adapter metric is invalid")
    with _rootless_fixture_adapter():
        return legacy.run_headed_child(
            metric_id, launch_token, contract_path=contract_path,
            benchmark_root=benchmark_root, installed_root=installed_root,
        )


def run_headed_readiness(metric_id: str, launch_token: str, *, contract_path: Path,
                         benchmark_root: Path, installed_root: Path) -> dict[str, object]:
    if metric_id not in METRIC_IDS:
        raise ValueError("scoped adapter metric is invalid")
    with _rootless_fixture_adapter():
        return legacy.run_headed_readiness_child(
            metric_id, launch_token, contract_path=contract_path,
            benchmark_root=benchmark_root, installed_root=installed_root,
        )


def build_authority(*, contract_path: Path, source_root: Path, installed_root: Path,
                    installed_wheel: Path, benchmark_root: Path,
                    no_unrelated_sustained_workload: bool) -> dict[str, object]:
    compact = legacy.build_authority(
        contract_path=contract_path, source_root=source_root, installed_root=installed_root,
        installed_wheel=installed_wheel, benchmark_root=benchmark_root,
        no_unrelated_sustained_workload=no_unrelated_sustained_workload,
    )
    compact_bytes = plan_scale.canonical_json_bytes(compact)
    source_files: dict[str, dict[str, str]] = {}
    for relative in (*scoped.SOURCE_ONLY_PATHS, *scoped.PRODUCT_PATHS):
        content = (source_root / relative).read_bytes()
        source_files[relative] = {
            "git_blob_oid": plan_scale._git_filtered_blob_oid(source_root, relative, content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    product_files: dict[str, dict[str, str]] = {}
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(installed_wheel.read_bytes())) as wheel:
        for relative in scoped.PRODUCT_PATHS:
            source = (source_root / relative).read_bytes()
            installed = (installed_root / relative).read_bytes()
            member = wheel.read(relative)
            product_files[relative] = {
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "wheel_member_sha256": hashlib.sha256(member).hexdigest(),
                "installed_sha256": hashlib.sha256(installed).hexdigest(),
            }
    contract = json.loads(contract_path.read_bytes())
    return {
        "compact_authority": compact,
        "compact_authority_receipt": {
            "byte_length": len(compact_bytes),
            "git_blob_oid": plan_scale.git_blob_oid(compact_bytes),
            "sha256": hashlib.sha256(compact_bytes).hexdigest(),
        },
        "contract_sha256": plan_scale.canonical_sha256(contract),
        "product_files": product_files,
        "schema": scoped.AUTHORITY_SCHEMA,
        "source_files": source_files,
    }


def _write_once(path: Path, value: object) -> bytes:
    if path.exists() or not path.parent.is_dir():
        raise FileExistsError("scoped evidence output already exists or parent is unavailable")
    content = plan_scale.canonical_json_bytes(value)
    path.write_bytes(content)
    return content


def _write_index(path: Path, value: object) -> None:
    content = plan_scale.canonical_json_bytes(value)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _output_bytes(value: object) -> bytes:
    if value is None:
        return b""
    if type(value) is bytes:
        return value
    return str(value).encode("utf-8", errors="replace")


def _validate_child_receipt(
    receipt: object, planned: Mapping[str, object], metric: Mapping[str, object],
    headed_runtime: object, child_ids: set[str], tokens: set[str], processes: set[tuple[int, int]],
    fixture_ids: set[tuple[str, str]],
) -> None:
    expected_schema = plan_scale.READINESS_CHILD_SCHEMA if planned["stage"] == "readiness" else plan_scale.CHILD_RECEIPT_SCHEMA
    if type(receipt) is not dict or receipt.get("schema") != expected_schema:
        raise ValueError("scoped child receipt schema is invalid")
    if planned["stage"] == "readiness":
        if (
            not plan_scale._is_readiness_receipt(receipt)
            or receipt["metric_ids"] != [planned["metric_id"]]
            or receipt["correctness"] != {planned["metric_id"]: metric["correctness"]}
            or receipt["surface"] != "installed-headed"
        ):
            raise ValueError("scoped readiness receipt is invalid")
    else:
        if (
            not plan_scale._is_measurement_receipt(receipt)
            or receipt["metric_id"] != planned["metric_id"]
            or receipt["fixture_case"] != metric["fixture_case"]
            or receipt["sample_kind"] != "warm"
            or type(receipt["samples"]) is not list or len(receipt["samples"]) != 6
        ):
            raise ValueError("scoped measurement receipt is invalid")
        for iteration, sample in enumerate(receipt["samples"], start=1):
            if plan_scale._measurement_sample_issue(sample, iteration, metric["correctness"], "elapsed_ns", "retained_bytes"):
                raise ValueError("scoped measurement sample is invalid")
    if receipt["launch_token"] != planned["launch_token"] or receipt["headed_runtime"] != headed_runtime:
        raise ValueError("scoped child receipt provenance is invalid")
    scoped._validate_identity(receipt, child_ids, tokens, processes)
    scoped._validate_rootless_headed_fixture(metric, receipt["headed_fixture"], fixture_ids)


def _planned_attempts() -> list[dict[str, object]]:
    rows = [("readiness", metric) for metric in METRIC_IDS]
    rows.extend(("measurement", metric) for metric in METRIC_IDS for _ in range(5))
    return [
        {"attempt": ordinal, "launch_token": uuid4().hex, "metric_id": metric, "stage": stage}
        for ordinal, (stage, metric) in enumerate(rows, start=1)
    ]


def collect(*, python: Path, authority_path: Path, output: Path, collection_root: Path,
            contract_path: Path, benchmark_root: Path, installed_root: Path) -> None:
    """Run the fixed two-readiness/ten-child sequence with retained prelaunch state."""

    index_path = collection_root / "collection.json"
    child_root = collection_root / "children"
    log_root = collection_root / "logs"
    failed_raw_path = collection_root / "failed-receipts.json"
    if (
        output.exists() or index_path.exists() or child_root.exists() or log_root.exists()
        or failed_raw_path.exists() or not collection_root.is_dir()
    ):
        raise FileExistsError("scoped collection already exists or root is unavailable")
    authority_bytes = authority_path.read_bytes()
    authority = json.loads(authority_bytes)
    compact = authority["compact_authority"]
    compact_bytes = plan_scale.canonical_json_bytes(compact)
    scoped.validate_authority(
        json.loads(contract_path.read_bytes()), compact, compact_bytes,
        authority["compact_authority_receipt"]["git_blob_oid"], authority,
    )
    planned = _planned_attempts()
    child_root.mkdir()
    log_root.mkdir()
    index: dict[str, object] = {"accepted": [], "planned": planned, "state": {**planned[0], "status": "next"}}
    _write_index(index_path, index)
    wrappers: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    child_ids: set[str] = set()
    tokens: set[str] = set()
    processes: set[tuple[int, int]] = set()
    fixture_ids: set[tuple[str, str]] = set()
    metrics = {metric["id"]: metric for metric in json.loads(contract_path.read_bytes())["metrics"]}
    for planned_item in planned:
        index["state"] = {**planned_item, "status": "launching"}
        _write_index(index_path, index)
        attempt = planned_item["attempt"]
        receipt_path = child_root / f"{attempt:02d}.json"
        log_path = log_root / f"{attempt:02d}.log"
        mode = "--readiness" if planned_item["stage"] == "readiness" else "--child"
        command = [str(python), str(Path(__file__).resolve()), mode, planned_item["metric_id"], "--launch-token", planned_item["launch_token"], "--contract", str(contract_path), "--benchmark-root", str(benchmark_root), "--installed-root", str(installed_root), "--output", str(receipt_path)]
        completed: subprocess.CompletedProcess[str] | None = None
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
            log = (completed.stdout + completed.stderr).encode("utf-8", errors="replace")
            log_path.write_bytes(log)
            if completed.returncode:
                raise RuntimeError(f"child exited {completed.returncode}")
            receipt = json.loads(receipt_path.read_bytes())
            _validate_child_receipt(
                receipt, planned_item, metrics[planned_item["metric_id"]], compact["headed_runtime"],
                child_ids, tokens, processes, fixture_ids,
            )
        except BaseException as error:
            if not log_path.exists():
                if isinstance(error, subprocess.TimeoutExpired):
                    log_path.write_bytes(_output_bytes(error.stdout) + _output_bytes(error.stderr))
                else:
                    log_path.write_text(str(error), encoding="utf-8")
            log = log_path.read_bytes()
            failure = {
                "error": str(error)[:4096], "error_class": type(error).__name__, "error_truncated": len(str(error)) > 4096,
                "exit_code": None if isinstance(error, subprocess.TimeoutExpired) else (None if completed is None else completed.returncode), "launch_token": planned_item["launch_token"],
                "metric_id": planned_item["metric_id"], "raw_log": {"byte_length": len(log), "sha256": hashlib.sha256(log).hexdigest()},
                "stage": planned_item["stage"], "timed_out": isinstance(error, subprocess.TimeoutExpired),
            }
            failures.append(failure)
            index["state"] = {**planned_item, "failure": failure, "status": "failed"}
            _write_index(index_path, index)
            _write_once(failed_raw_path, {"failures": failures, "receipts": wrappers})
            raise RuntimeError("scoped collection stopped after its first failure") from error
        wrappers.append({"receipt": receipt, "receipt_sha256": plan_scale.canonical_sha256(receipt)})
        index["accepted"].append({
            "attempt": attempt, "child_id": receipt["child_id"], "launch_token": planned_item["launch_token"],
            "metric_id": planned_item["metric_id"], "process_identity": receipt["process_identity"],
            "receipt_path": f"children/{attempt:02d}.json", "receipt_sha256": hashlib.sha256(plan_scale.canonical_json_bytes(receipt)).hexdigest(), "stage": planned_item["stage"],
        })
        index["state"] = ({"status": "complete"} if attempt == len(planned) else {**planned[attempt], "status": "next"})
        _write_index(index_path, index)
    raw = {
        "authority_receipt": {"byte_length": len(authority_bytes), "git_blob_oid": plan_scale.git_blob_oid(authority_bytes), "sha256": hashlib.sha256(authority_bytes).hexdigest()},
        "children": wrappers[2:], "collection": index, "failures": failures, "readiness": wrappers[:2], "schema": scoped.RECEIPTS_SCHEMA,
    }
    _write_once(output, raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze-authority", action="store_true")
    mode.add_argument("--child", choices=METRIC_IDS)
    mode.add_argument("--readiness", choices=METRIC_IDS)
    mode.add_argument("--collect", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--installed-wheel", type=Path)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--collection-root", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--launch-token")
    parser.add_argument("--confirm-no-unrelated-sustained-workload", action="store_true")
    arguments = parser.parse_args()
    if arguments.freeze_authority:
        if (
            arguments.source_root is None or arguments.installed_wheel is None
            or not arguments.confirm_no_unrelated_sustained_workload
        ):
            raise ValueError("authority freeze requires source root and wheel")
        _write_once(arguments.output, build_authority(
            contract_path=arguments.contract, source_root=arguments.source_root,
            installed_root=arguments.installed_root, installed_wheel=arguments.installed_wheel,
            benchmark_root=arguments.benchmark_root,
            no_unrelated_sustained_workload=arguments.confirm_no_unrelated_sustained_workload,
        ))
        return 0
    if arguments.collect:
        if arguments.authority is None or arguments.collection_root is None:
            raise ValueError("collection requires authority and collection root")
        collect(python=Path(sys.executable), authority_path=arguments.authority, output=arguments.output,
                collection_root=arguments.collection_root, contract_path=arguments.contract,
                benchmark_root=arguments.benchmark_root, installed_root=arguments.installed_root)
        return 0
    if arguments.launch_token is None:
        raise ValueError("child mode requires a launch token")
    receipt = (
        run_headed_child(arguments.child, arguments.launch_token, contract_path=arguments.contract,
                         benchmark_root=arguments.benchmark_root, installed_root=arguments.installed_root)
        if arguments.child else run_headed_readiness(arguments.readiness, arguments.launch_token,
                         contract_path=arguments.contract, benchmark_root=arguments.benchmark_root,
                         installed_root=arguments.installed_root)
    )
    _write_once(arguments.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
