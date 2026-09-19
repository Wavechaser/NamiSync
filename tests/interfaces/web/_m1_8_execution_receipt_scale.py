"""Independent validator for the scoped M1-8 execution receipt evidence."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Final, Mapping
import zipfile

import _plan_review_scale as plan_scale


AUTHORITY_SCHEMA: Final = "namisync-m1-8-execution-receipt-authority-v1"
RECEIPTS_SCHEMA: Final = "namisync-m1-8-execution-receipt-receipts-v1"
RESULT_SCHEMA: Final = "namisync-m1-8-execution-receipt-result-v1"
METRIC_IDS: Final = (
    "ui_get_plan_window_one_row_receipt",
    "ui_start_execution_receipt",
)
SOURCE_ONLY_PATHS: Final = (
    "tests/m1_8_execution_receipt_benchmark.py",
    "tests/interfaces/web/_m1_8_execution_receipt_scale.py",
    "tests/interfaces/web/test_m1_8_execution_receipt_scale.py",
)
PRODUCT_PATHS: Final = (
    "namisync/core/execution.py",
    "namisync/workflows/execution_review.py",
    "namisync/interfaces/web/assets/task_status.js",
    "namisync/interfaces/web/assets/components.css",
    "namisync/interfaces/web/assets/tokens.css",
)


def _authority_receipt(content: bytes, git_blob_oid: str) -> dict[str, object]:
    return {
        "byte_length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "git_blob_oid": git_blob_oid,
    }


def _metrics(contract: object) -> dict[str, dict[str, object]]:
    plan_scale._validate_contract(contract)
    assert type(contract) is dict
    metrics = {metric["id"]: metric for metric in contract["metrics"]}
    if tuple(metric_id for metric_id in METRIC_IDS if metric_id in metrics) != METRIC_IDS:
        raise ValueError("M1-8 execution receipt metric membership is invalid")
    selected = {metric_id: metrics[metric_id] for metric_id in METRIC_IDS}
    for metric in selected.values():
        if (
            metric["surface"] != "installed-headed"
            or metric["sample_kind"] != "warm"
            or metric["statistic"] != "nearest-rank-p95"
            or metric["budget_ns"] != 100_000_000
            or metric["maximum_budget_ns"] != 250_000_000
        ):
            raise ValueError("M1-8 execution receipt metric premise changed")
    return selected


def validate_authority(
    contract: object,
    compact_authority: object,
    compact_authority_bytes: bytes,
    compact_authority_git_blob_oid: str,
    authority: object,
) -> None:
    """Validate the scoped authority and its compact M1-7 parent authority."""

    metrics = _metrics(contract)
    plan_scale._validate_authority(contract, compact_authority)
    if type(compact_authority_bytes) is not bytes:
        raise TypeError("M1-8 compact authority bytes are invalid")
    try:
        if json.loads(compact_authority_bytes) != compact_authority:
            raise ValueError("M1-8 compact authority bytes do not encode authority")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("M1-8 compact authority bytes are invalid") from error
    if type(authority) is not dict or set(authority) != {
        "compact_authority",
        "compact_authority_receipt",
        "contract_sha256",
        "product_files",
        "schema",
        "source_files",
    }:
        raise ValueError("M1-8 execution receipt authority shape is invalid")
    if authority["schema"] != AUTHORITY_SCHEMA or authority["contract_sha256"] != plan_scale.canonical_sha256(contract):
        raise ValueError("M1-8 execution receipt authority contract is invalid")
    if authority["compact_authority"] != compact_authority:
        raise ValueError("M1-8 bundled compact authority is invalid")
    if compact_authority_git_blob_oid != plan_scale.git_blob_oid(compact_authority_bytes):
        raise ValueError("M1-8 compact authority Git identity is invalid")
    if authority["compact_authority_receipt"] != _authority_receipt(
        compact_authority_bytes, compact_authority_git_blob_oid
    ):
        raise ValueError("M1-8 compact authority receipt is invalid")
    expected_sources = set((*SOURCE_ONLY_PATHS, *PRODUCT_PATHS))
    source_files = authority["source_files"]
    if type(source_files) is not dict or set(source_files) != expected_sources:
        raise ValueError("M1-8 supplemental source population is invalid")
    for path, record in source_files.items():
        if (
            type(record) is not dict
            or set(record) != {"git_blob_oid", "sha256"}
            or not isinstance(record["sha256"], str)
            or plan_scale._HEX64.fullmatch(record["sha256"]) is None
            or not isinstance(record["git_blob_oid"], str)
            or plan_scale._HEX40.fullmatch(record["git_blob_oid"]) is None
        ):
            raise ValueError(f"M1-8 supplemental source record is invalid: {path}")
    product_files = authority["product_files"]
    if type(product_files) is not dict or set(product_files) != set(PRODUCT_PATHS):
        raise ValueError("M1-8 supplemental product population is invalid")
    for path, record in product_files.items():
        if (
            type(record) is not dict
            or set(record) != {"installed_sha256", "source_sha256", "wheel_member_sha256"}
            or any(
                not isinstance(record[name], str)
                or plan_scale._HEX64.fullmatch(record[name]) is None
                for name in record
            )
            or record["source_sha256"] != source_files[path]["sha256"]
        ):
            raise ValueError(f"M1-8 supplemental product record is invalid: {path}")
    if set(metrics) != set(METRIC_IDS):
        raise ValueError("M1-8 execution receipt authority metrics are invalid")


def validate_authority_workspace(
    contract: object,
    compact_authority: object,
    compact_authority_bytes: bytes,
    compact_authority_git_blob_oid: str,
    authority: object,
    source_root: Path,
    installed_root: Path,
    installed_wheel: Path,
) -> None:
    """Verify the supplementary source-only and product byte bindings."""

    validate_authority(
        contract, compact_authority, compact_authority_bytes,
        compact_authority_git_blob_oid, authority,
    )
    source_root = source_root.resolve()
    plan_scale.validate_authority_workspace(
        contract,
        compact_authority,
        source_root,
        installed_root,
        installed_wheel,
        {
            role: Path(record["path"])
            for role, record in compact_authority["runtime_files"].items()
        },
        compact_authority["headed_runtime"],
        bytes.fromhex(compact_authority["native_profile"]["utf8_hex"]),
        compact_authority["fixture_manifests"],
    )
    source_files = authority["source_files"]
    for path, record in source_files.items():
        content = (source_root / path).read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != record["sha256"]
            or plan_scale._git_filtered_blob_oid(source_root, path, content)
            != record["git_blob_oid"]
        ):
            raise ValueError("M1-8 supplemental source bytes are not authoritative")
    try:
        with zipfile.ZipFile(io.BytesIO(installed_wheel.read_bytes())) as archive:
            members = {path: archive.read(path) for path in PRODUCT_PATHS}
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError("M1-8 supplemental wheel bytes are unavailable") from error
    for path, record in authority["product_files"].items():
        source = (source_root / path).read_bytes()
        installed = (installed_root / path).read_bytes()
        wheel = members[path]
        if (
            source != wheel
            or wheel != installed
            or hashlib.sha256(source).hexdigest() != record["source_sha256"]
            or hashlib.sha256(wheel).hexdigest() != record["wheel_member_sha256"]
            or hashlib.sha256(installed).hexdigest() != record["installed_sha256"]
        ):
            raise ValueError("M1-8 supplemental product bytes are not authoritative")


def validate_receipts(
    contract: object,
    compact_authority: object,
    compact_authority_bytes: bytes,
    compact_authority_git_blob_oid: str,
    authority: object,
    authority_bytes: bytes,
    authority_git_blob_oid: str,
    receipts: object,
) -> tuple[plan_scale.MetricObservation, ...]:
    """Validate the two selected readiness receipts and ten measurement children."""

    metrics = _metrics(contract)
    validate_authority(
        contract, compact_authority, compact_authority_bytes,
        compact_authority_git_blob_oid, authority,
    )
    if type(authority_bytes) is not bytes:
        raise TypeError("M1-8 authority bytes are invalid")
    try:
        if json.loads(authority_bytes) != authority:
            raise ValueError("M1-8 authority bytes do not encode authority")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("M1-8 authority bytes are invalid") from error
    if type(receipts) is not dict or set(receipts) != {
        "authority_receipt", "children", "collection", "failures", "readiness", "schema"
    }:
        raise ValueError("M1-8 receipt artifact shape is invalid")
    if receipts["schema"] != RECEIPTS_SCHEMA:
        raise ValueError("M1-8 receipt artifact schema is invalid")
    if authority_git_blob_oid != plan_scale.git_blob_oid(authority_bytes):
        raise ValueError("M1-8 authority Git identity is invalid")
    if receipts["authority_receipt"] != _authority_receipt(authority_bytes, authority_git_blob_oid):
        raise ValueError("M1-8 receipt authority is invalid")
    _validate_failures(receipts["failures"], receipts["readiness"], receipts["children"])
    if receipts["failures"]:
        raise ValueError("M1-8 receipt collection stopped on retained failure")

    child_ids: set[str] = set()
    launch_tokens: set[str] = set()
    processes: set[tuple[int, int]] = set()
    headed_identifiers: set[tuple[str, str]] = set()
    _validate_readiness(
        metrics, compact_authority["headed_runtime"], receipts["readiness"], child_ids,
        launch_tokens, processes, headed_identifiers,
    )
    observations = _validate_children(
        metrics, compact_authority["headed_runtime"], receipts["children"], child_ids,
        launch_tokens, processes, headed_identifiers,
    )
    _validate_collection(receipts["collection"], receipts)
    return observations


def _validate_failures(
    failures: object, readiness: object, children: object
) -> None:
    """Retain at most the first failed child; replacements need a new collection."""

    if type(failures) is not list or len(failures) > 1:
        raise ValueError("M1-8 retained failure population is invalid")
    if not failures:
        return
    failure = failures[0]
    if type(failure) is not dict or set(failure) != {
        "error", "error_class", "error_truncated", "exit_code", "launch_token",
        "metric_id", "raw_log", "stage", "timed_out",
    }:
        raise ValueError("M1-8 retained failure shape is invalid")
    if (
        failure["stage"] not in {"readiness", "measurement"}
        or failure["metric_id"] not in METRIC_IDS
        or not isinstance(failure["launch_token"], str)
        or plan_scale._HEX32.fullmatch(failure["launch_token"]) is None
        or type(failure["timed_out"]) is not bool
        or (failure["exit_code"] is not None and type(failure["exit_code"]) is not int)
        or type(failure["error"]) is not str
        or not failure["error"]
        or len(failure["error"]) > 4096
        or type(failure["error_class"]) is not str
        or not failure["error_class"]
        or len(failure["error_class"]) > 128
        or type(failure["error_truncated"]) is not bool
    ):
        raise ValueError("M1-8 retained failure details are invalid")
    raw_log = failure["raw_log"]
    if (
        type(raw_log) is not dict
        or set(raw_log) != {"byte_length", "sha256"}
        or type(raw_log["byte_length"]) is not int
        or raw_log["byte_length"] < 0
        or not isinstance(raw_log["sha256"], str)
        or plan_scale._HEX64.fullmatch(raw_log["sha256"]) is None
    ):
        raise ValueError("M1-8 retained failure log is invalid")
    if failure["timed_out"]:
        if failure["exit_code"] is not None:
            raise ValueError("M1-8 retained timeout has an exit code")
    elif failure["exit_code"] is None:
        raise ValueError("M1-8 retained failure lacks an exit code")
    for wrapper in (*readiness, *children) if type(readiness) is list and type(children) is list else ():
        receipt = wrapper.get("receipt") if type(wrapper) is dict else None
        if type(receipt) is dict and receipt.get("launch_token") == failure["launch_token"]:
            raise ValueError("M1-8 retained failure launch token is reused")


def _prior_group_node_id(request_id: str) -> str:
    digest = hashlib.blake2b(digest_size=16, person=b"NamiSyncPriorV1")
    encoded = request_id.encode("utf-8")
    digest.update(len(encoded).to_bytes(4, "big"))
    digest.update(encoded)
    return f"node-{digest.hexdigest()}"


def _validate_rootless_headed_fixture(
    metric: Mapping[str, object], fixture: object,
    retained_identifiers: set[tuple[str, str]],
) -> None:
    expected_count = 7 if metric["id"] == "ui_start_execution_receipt" else 1
    if (
        type(fixture) is not dict
        or set(fixture) != {"published_plan_count", "rows"}
        or fixture["published_plan_count"] != expected_count
        or type(fixture["rows"]) is not list
        or len(fixture["rows"]) != expected_count
    ):
        raise ValueError("M1-8 rootless headed fixture population is invalid")
    local_paths: set[tuple[str, str]] = set()
    for row in fixture["rows"]:
        expected_fields = {
            "execution_unused", "initial_view_settlement", "plan_session_id",
            "request_id", "session_released", "session_state", "source_path",
            "target_path", "task_id", "task_kind",
        }
        if type(row) is not dict or set(row) != expected_fields:
            raise ValueError("M1-8 rootless headed fixture row shape is invalid")
        identity = (row["task_id"], row["request_id"], row["plan_session_id"])
        if (
            not isinstance(identity[0], str)
            or plan_scale._TASK_ID.fullmatch(identity[0]) is None
            or any(plan_scale._HEX32.fullmatch(value) is None for value in identity[1:])
            or any((kind, value) in retained_identifiers for kind, value in zip(("task", "request", "session"), identity, strict=True))
            or row["task_kind"] != "sync-plan"
            or row["session_state"] != "completed"
            or row["session_released"] is not True
            or row["execution_unused"] is not True
        ):
            raise ValueError("M1-8 rootless headed fixture identity is invalid or reused")
        paths = (row["source_path"], row["target_path"])
        if (
            any(type(path) is not str or not path for path in paths)
            or paths[0] == paths[1] or paths in local_paths
        ):
            raise ValueError("M1-8 rootless headed fixture paths are invalid")
        _validate_rootless_settlement(row["initial_view_settlement"], row)
        retained_identifiers.update(zip(("task", "request", "session"), identity, strict=True))
        local_paths.add(paths)


def _validate_rootless_settlement(settlement: object, row: Mapping[str, object]) -> None:
    expected = {
        "first_row", "open_disposition", "plan_session_id", "projection_node_count",
        "request_id", "source_path", "target_path", "task_id", "view_revision",
        "window_disposition", "window_limit", "window_offset", "window_row_count",
        "window_total", "window_view_revision",
    }
    if type(settlement) is not dict or set(settlement) != expected:
        raise ValueError("M1-8 rootless settlement shape is invalid")
    first = settlement["first_row"]
    expected_first = {
        "blocked_reason", "dependency_count", "depth", "display", "execution", "expanded",
        "first_child_visible_index", "highlighted", "is_container", "move_peer_id",
        "mtime_ns", "node_id", "notice", "operation_count", "operation_id",
        "operation_kind", "parent_visible_index", "position_in_set", "reason", "risk",
        "row_kind", "selectable_operation_count", "selected_operation_count", "selection",
        "selection_exclusion_reason", "set_size", "size", "visible_index",
    }
    if (
        type(first) is not dict or set(first) != expected_first
        or settlement["open_disposition"] != "opened"
        or any(settlement[name] != row[name] for name in ("plan_session_id", "request_id", "source_path", "target_path", "task_id"))
        or settlement["projection_node_count"] != 120_000
        or settlement["view_revision"] != 0 or settlement["window_view_revision"] != 0
        or settlement["window_disposition"] != "current" or settlement["window_limit"] != 256
        or settlement["window_offset"] != 0 or settlement["window_row_count"] != 256
        or settlement["window_total"] != 119_999
        or first["node_id"] != _prior_group_node_id(row["request_id"])
        or first["display"] != "Previous paths" or first["row_kind"] != "prior-group"
        or first["operation_id"] is not None or first["operation_kind"] is not None
        or first["depth"] != 0 or first["visible_index"] != 0
        or first["parent_visible_index"] is not None or first["first_child_visible_index"] != 1
        or first["position_in_set"] != 1 or first["set_size"] != 19_937
        or first["is_container"] is not True or first["expanded"] is not True
        or first["selection"] != "disabled" or first["risk"] != "none"
        or any(first[name] != 0 for name in ("dependency_count", "operation_count", "selectable_operation_count", "selected_operation_count"))
        or any(first[name] is not None for name in ("blocked_reason", "execution", "move_peer_id", "mtime_ns", "notice", "reason", "selection_exclusion_reason", "size"))
        or first["highlighted"] is not False
    ):
        raise ValueError("M1-8 rootless headed fixture settlement is invalid")


def _validate_collection(collection: object, receipts: Mapping[str, object]) -> None:
    if type(collection) is not dict or set(collection) != {"accepted", "planned", "state"}:
        raise ValueError("M1-8 collection index shape is invalid")
    planned = collection["planned"]
    expected = [
        ("readiness", metric_id) for metric_id in METRIC_IDS
    ] + [("measurement", metric_id) for metric_id in METRIC_IDS for _ in range(5)]
    if type(planned) is not list or len(planned) != len(expected):
        raise ValueError("M1-8 collection plan is incomplete")
    tokens: set[str] = set()
    for ordinal, (item, (stage, metric_id)) in enumerate(zip(planned, expected, strict=True), start=1):
        if (
            type(item) is not dict or set(item) != {"attempt", "launch_token", "metric_id", "stage"}
            or item["attempt"] != ordinal or item["stage"] != stage or item["metric_id"] != metric_id
            or not isinstance(item["launch_token"], str) or plan_scale._HEX32.fullmatch(item["launch_token"]) is None
            or item["launch_token"] in tokens
        ):
            raise ValueError("M1-8 collection planned attempt is invalid")
        tokens.add(item["launch_token"])
    accepted = collection["accepted"]
    if type(accepted) is not list or len(accepted) != len(planned):
        raise ValueError("M1-8 collection accepted attempts are incomplete")
    wrappers = [*receipts["readiness"], *receipts["children"]]
    if len(wrappers) != len(planned):
        raise ValueError("M1-8 collection receipt population is incomplete")
    for attempt, (item, planned_item, wrapper) in enumerate(zip(accepted, planned, wrappers, strict=True), start=1):
        receipt = wrapper["receipt"] if type(wrapper) is dict else None
        expected_path = f"children/{attempt:02d}.json"
        if (
            type(item) is not dict or set(item) != {"attempt", "child_id", "launch_token", "metric_id", "process_identity", "receipt_path", "receipt_sha256", "stage"}
            or item["attempt"] != attempt or item["stage"] != planned_item["stage"]
            or item["metric_id"] != planned_item["metric_id"] or item["launch_token"] != planned_item["launch_token"]
            or item["receipt_path"] != expected_path or type(receipt) is not dict
            or item["receipt_sha256"] != hashlib.sha256(plan_scale.canonical_json_bytes(receipt)).hexdigest()
            or item["child_id"] != receipt.get("child_id") or item["process_identity"] != receipt.get("process_identity")
        ):
            raise ValueError("M1-8 collection accepted attempt is invalid")
    if collection["state"] != {"status": "complete"}:
        raise ValueError("M1-8 collection is not complete")


def _validate_identity(
    receipt: dict[str, object],
    child_ids: set[str],
    launch_tokens: set[str],
    processes: set[tuple[int, int]],
) -> None:
    if (
        not isinstance(receipt["child_id"], str)
        or plan_scale._HEX32.fullmatch(receipt["child_id"]) is None
        or receipt["child_id"] in child_ids
        or not isinstance(receipt["launch_token"], str)
        or plan_scale._HEX32.fullmatch(receipt["launch_token"]) is None
        or receipt["launch_token"] in launch_tokens
        or not plan_scale._is_process_identity(receipt["process_identity"])
    ):
        raise ValueError("M1-8 receipt child identity is invalid or reused")
    process = receipt["process_identity"]
    assert type(process) is dict
    key = (process["pid"], process["creation_filetime_100ns"])
    if key in processes:
        raise ValueError("M1-8 receipt process identity is reused")
    child_ids.add(receipt["child_id"])
    launch_tokens.add(receipt["launch_token"])
    processes.add(key)


def _validate_wrapper(wrapper: object, expected_schema: str) -> dict[str, object]:
    if type(wrapper) is not dict or set(wrapper) != {"receipt", "receipt_sha256"}:
        raise ValueError("M1-8 receipt wrapper is invalid")
    receipt = wrapper["receipt"]
    if (
        not isinstance(wrapper["receipt_sha256"], str)
        or plan_scale._HEX64.fullmatch(wrapper["receipt_sha256"]) is None
        or wrapper["receipt_sha256"] != plan_scale.canonical_sha256(receipt)
        or type(receipt) is not dict
        or receipt.get("schema") != expected_schema
    ):
        raise ValueError("M1-8 receipt wrapper digest is invalid")
    return receipt


def _validate_readiness(
    metrics: Mapping[str, dict[str, object]],
    headed_runtime: object,
    wrappers: object,
    child_ids: set[str], launch_tokens: set[str], processes: set[tuple[int, int]],
    headed_identifiers: set[tuple[str, str]],
) -> None:
    if type(wrappers) is not list or len(wrappers) != len(METRIC_IDS):
        raise ValueError("M1-8 readiness membership is incomplete")
    for wrapper, metric_id in zip(wrappers, METRIC_IDS, strict=True):
        receipt = _validate_wrapper(wrapper, plan_scale.READINESS_CHILD_SCHEMA)
        metric = metrics[metric_id]
        if (
            not plan_scale._is_readiness_receipt(receipt)
            or receipt["surface"] != "installed-headed"
            or receipt["metric_ids"] != [metric_id]
            or receipt["correctness"] != {metric_id: metric["correctness"]}
            or receipt["headed_runtime"] != headed_runtime
        ):
            raise ValueError("M1-8 readiness receipt is invalid")
        _validate_identity(receipt, child_ids, launch_tokens, processes)
        _validate_rootless_headed_fixture(
            metric, receipt["headed_fixture"], headed_identifiers
        )


def _validate_children(
    metrics: Mapping[str, dict[str, object]],
    headed_runtime: object,
    wrappers: object,
    child_ids: set[str], launch_tokens: set[str], processes: set[tuple[int, int]],
    headed_identifiers: set[tuple[str, str]],
) -> tuple[plan_scale.MetricObservation, ...]:
    if type(wrappers) is not list:
        raise ValueError("M1-8 measurement receipts are invalid")
    grouped = {metric_id: [] for metric_id in METRIC_IDS}
    for wrapper in wrappers:
        receipt = _validate_wrapper(wrapper, plan_scale.CHILD_RECEIPT_SCHEMA)
        if not plan_scale._is_measurement_receipt(receipt):
            raise ValueError("M1-8 measurement receipt shape is invalid")
        metric_id = receipt["metric_id"]
        if metric_id not in metrics:
            raise ValueError("M1-8 measurement metric is invalid")
        metric = metrics[metric_id]
        if (
            receipt["fixture_case"] != metric["fixture_case"]
            or receipt["sample_kind"] != metric["sample_kind"]
            or receipt["headed_runtime"] != headed_runtime
        ):
            raise ValueError("M1-8 measurement receipt contract is invalid")
        _validate_identity(receipt, child_ids, launch_tokens, processes)
        _validate_rootless_headed_fixture(
            metric, receipt["headed_fixture"], headed_identifiers
        )
        grouped[metric_id].append(receipt)
    observations = []
    for metric_id in METRIC_IDS:
        metric = metrics[metric_id]
        metric_receipts = grouped[metric_id]
        if len(metric_receipts) != 5:
            raise ValueError("M1-8 measurement child membership is incomplete")
        values: list[int] = []
        within_ranges: list[int] = []
        child_maxima: list[int] = []
        for receipt in metric_receipts:
            samples = receipt["samples"]
            if type(samples) is not list or len(samples) != 6:
                raise ValueError("M1-8 measurement sample membership is incomplete")
            child_values = []
            for iteration, sample in enumerate(samples, start=1):
                issue = plan_scale._measurement_sample_issue(
                    sample, iteration, metric["correctness"], "elapsed_ns", "retained_bytes"
                )
                if issue == "shape":
                    raise ValueError("M1-8 measurement sample shape is invalid")
                if issue == "correctness":
                    raise ValueError("M1-8 measurement correctness receipt is invalid")
                if issue == "value":
                    raise ValueError("M1-8 measurement sample value is invalid")
                assert type(sample) is dict
                child_values.append(sample["elapsed_ns"])
            values.extend(child_values)
            child_maxima.append(max(child_values))
            within_ranges.append(max(child_values) - min(child_values))
        statistic = plan_scale.nearest_rank_p95(values)
        maximum = max(values)
        if maximum > metric["maximum_budget_ns"]:
            raise ValueError("M1-8 measurement maximum exceeds its fixed budget")
        if statistic > metric["budget_ns"]:
            raise ValueError("M1-8 measurement statistic exceeds its fixed budget")
        observations.append(plan_scale.MetricObservation(
            metric_id, statistic, maximum, metric["budget_ns"],
            metric["budget_ns"] - statistic, tuple(within_ranges),
            max(child_maxima) - min(child_maxima),
        ))
    return tuple(observations)


def derive_result(
    receipts_bytes: bytes,
    observations: tuple[plan_scale.MetricObservation, ...],
) -> dict[str, object]:
    """Derive a compact result without adding a verdict to raw receipts."""

    if type(receipts_bytes) is not bytes:
        raise TypeError("M1-8 receipt bytes are invalid")
    return {
        "metrics": [
            {
                "across_child_maxima_range_ns": observation.across_child_range,
                "budget_ns": observation.budget,
                "headroom_ns": observation.headroom,
                "maximum_ns": observation.maximum,
                "metric_id": observation.metric_id,
                "p95_ns": observation.statistic,
                "within_child_ranges_ns": list(observation.within_child_ranges),
            }
            for observation in observations
        ],
        "receipts_sha256": hashlib.sha256(receipts_bytes).hexdigest(),
        "schema": RESULT_SCHEMA,
    }


def validate_result(
    receipts_bytes: bytes,
    observations: tuple[plan_scale.MetricObservation, ...],
    result: object,
) -> None:
    if result != derive_result(receipts_bytes, observations):
        raise ValueError("M1-8 derived execution receipt result is invalid")


def validate_committed_sources(
    source_root: Path,
    compact_authority: object,
    authority: object,
    *,
    authority_path: Path,
    receipts_path: Path,
    result_path: Path,
) -> None:
    """Require supplemental inputs and promoted evidence to be clean HEAD bytes."""

    if (
        type(authority) is not dict
        or type(authority.get("source_files")) is not dict
        or type(compact_authority) is not dict
        or type(compact_authority.get("source_files")) is not dict
    ):
        raise ValueError("M1-8 committed authority is invalid")
    source_root = source_root.resolve()
    authority_bytes = authority_path.read_bytes()
    receipts_bytes = receipts_path.read_bytes()
    try:
        if json.loads(authority_bytes) != authority:
            raise ValueError("M1-8 committed authority bytes changed")
        raw = json.loads(receipts_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("M1-8 committed evidence bytes are invalid") from error
    source_records = {**compact_authority["source_files"], **authority["source_files"]}
    paths = [*source_records, *(
        str(path.resolve().relative_to(source_root)).replace("\\", "/")
        for path in (authority_path, receipts_path, result_path)
    )]
    for path, record in source_records.items():
        content = (source_root / path).read_bytes()
        if plan_scale._head_blob_oid(source_root, path) != record["git_blob_oid"]:
            raise ValueError("M1-8 committed source identity changed")
        if hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise ValueError("M1-8 committed source bytes changed")
    for path in paths[-3:]:
        content = (source_root / path).read_bytes()
        if plan_scale._head_blob_oid(source_root, path) != plan_scale._git_filtered_blob_oid(source_root, path, content):
            raise ValueError("M1-8 committed evidence identity changed")
    authority_relative = paths[-3]
    if (
        type(raw) is not dict
        or raw.get("authority_receipt") != _authority_receipt(
            authority_bytes, plan_scale._head_blob_oid(source_root, authority_relative)
        )
    ):
        raise ValueError("M1-8 committed raw authority binding changed")
    status = subprocess.run(
        ("git", "status", "--porcelain=v1", "--", *paths),
        cwd=source_root, capture_output=True, text=True, check=False, timeout=30,
    )
    if status.returncode or status.stdout:
        raise ValueError("M1-8 measured inputs and evidence are not clean")


__all__ = (
    "AUTHORITY_SCHEMA", "METRIC_IDS", "PRODUCT_PATHS", "RECEIPTS_SCHEMA",
    "RESULT_SCHEMA", "SOURCE_ONLY_PATHS", "derive_result", "validate_authority",
    "validate_authority_workspace", "validate_committed_sources", "validate_receipts",
    "validate_result",
)
