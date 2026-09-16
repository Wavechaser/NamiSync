"""Independent validator for the fixed M1-7 plan-review scale gate."""

from __future__ import annotations

import argparse
import hashlib
import io
import importlib.util
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Final, Mapping


LEGACY_CONTRACT_SCHEMA: Final = "namisync-m1-7-plan-review-scale-contract-v4"
LEGACY_AUTHORITY_SCHEMA: Final = "namisync-m1-7-plan-review-scale-authority-v3"
LEGACY_RAW_ARTIFACT_SCHEMA: Final = "namisync-m1-7-plan-review-scale-run-v4"
CONTRACT_SCHEMA: Final = "namisync-m1-7-plan-review-scale-contract-v5"
AUTHORITY_SCHEMA: Final = "namisync-m1-7-plan-review-scale-authority-v4"
RAW_ARTIFACT_SCHEMA: Final = "namisync-m1-7-plan-review-scale-run-v5"
CHILD_RECEIPT_SCHEMA: Final = "namisync-m1-7-plan-review-child-v3"
READINESS_SCHEMA: Final = "namisync-m1-7-plan-review-readiness-v1"
READINESS_CHILD_SCHEMA: Final = "namisync-m1-7-plan-review-readiness-child-v1"
COLLECTION_SCHEMA: Final = "namisync-m1-7-plan-review-collection-index-v1"
LEGACY_FIXTURE_SCHEMA: Final = "namisync-m1-7-plan-fixture-manifest-v1"
FIXTURE_SCHEMA: Final = "namisync-m1-7-plan-fixture-manifest-v2"
LEGACY_CONTRACT_SHA256: Final = "0c82a7044348193af2d68b25c6645263e15c4f532f4015257324c33227b930c3"
CONTRACT_SHA256: Final = "4cb4aeee68f4e846f2b74771fbebbdd74004d6f76162da495e1bc5a53757aa9b"


def _contract_family(contract: Mapping[str, object]) -> tuple[str, str, str, str]:
    if contract.get("schema") == CONTRACT_SCHEMA:
        return CONTRACT_SHA256, AUTHORITY_SCHEMA, RAW_ARTIFACT_SCHEMA, FIXTURE_SCHEMA
    if contract.get("schema") == LEGACY_CONTRACT_SCHEMA:
        return (
            LEGACY_CONTRACT_SHA256,
            LEGACY_AUTHORITY_SCHEMA,
            LEGACY_RAW_ARTIFACT_SCHEMA,
            LEGACY_FIXTURE_SCHEMA,
        )
    raise ValueError("plan-review contract schema is invalid")

_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")

_EXPECTED_SAMPLING = {
    "cold": {"fresh_children": 5, "samples_per_child": 1},
    "warm": {"fresh_children": 5, "samples_per_child": 6},
    "p95": "nearest-rank ceil(0.95*n)-1 over all 30 samples",
    "dispersion": "report each child range and the range of per-child maxima",
    "headroom": "fixed budget minus observed statistic; budgets are not derived or retuned",
}

_EXPECTED_HEADED_FIXTURE = {
    "default_published_plan_count": 1,
    "fresh_execution_plan_count": {"cold": 2, "warm": 7},
    "fresh_execution_metric_ids": [
        "ui_start_execution_click_feedback",
        "ui_confirm_execution_click_feedback",
        "ui_start_execution_nondestructive_click_feedback",
        "ui_control_pause_click_feedback",
        "ui_control_resume_click_feedback",
        "ui_control_cancel_click_feedback",
        "ui_start_execution_receipt",
        "ui_control_pause_receipt",
        "ui_control_resume_receipt",
        "ui_control_cancel_receipt",
    ],
    "initial_view_settlement": {
        "open_disposition": "opened",
        "view_revision": 0,
        "window_disposition": "current",
        "window_limit": 256,
        "window_offset": 0,
        "window_rows": 256,
        "window_total": 120_000,
        "first_row_operation_id": None,
        "first_row_visible_index": 0,
        "first_row_node_identity": (
            "request-scoped plan root BLAKE2b-128 NamiSyncNodeV1"
        ),
    },
    "published_row_fields": [
        "execution_unused",
        "initial_view_settlement",
        "plan_session_id",
        "request_id",
        "session_released",
        "session_state",
        "source_path",
        "target_path",
        "task_id",
        "task_kind",
    ],
}

_EXPECTED_READINESS = {
    "schema": READINESS_SCHEMA,
    "child_schema": READINESS_CHILD_SCHEMA,
    "child_count": 15,
    "component_metric_ids": [
        "projection_cold_base",
        "projection_cold_information_heavy",
        "projection_unchanged_window",
        "projection_unchanged_after_sort_filename_ascending",
        "projection_unchanged_after_sort_filename_descending",
        "projection_unchanged_after_sort_size_ascending",
        "projection_unchanged_after_sort_size_descending",
        "projection_unchanged_after_sort_mtime_ascending",
        "projection_unchanged_after_sort_mtime_descending",
        "projection_changed_search_window",
        "projection_changed_filter_window",
        "projection_changed_collapse_window",
        "projection_changed_reset_window",
        "projection_changed_sort_filename_ascending_window",
        "projection_changed_sort_filename_descending_window",
        "projection_changed_sort_size_ascending_window",
        "projection_changed_sort_size_descending_window",
        "projection_changed_sort_mtime_ascending_window",
        "projection_changed_sort_mtime_descending_window",
        "selection_freeze_normalize_100000",
        "selection_preview_depth_32",
    ],
    "memory_metric_id": "projection_incremental_retained_memory_staging_overlap",
    "headed_metric_ids": [
        "ui_mutate_plan_selection_click_feedback",
        "ui_update_plan_view_click_feedback",
        "ui_start_execution_click_feedback",
        "ui_confirm_execution_click_feedback",
        "ui_start_execution_nondestructive_click_feedback",
        "ui_control_pause_click_feedback",
        "ui_control_resume_click_feedback",
        "ui_control_cancel_click_feedback",
        "ui_get_plan_window_one_row_receipt",
        "ui_start_execution_receipt",
        "ui_control_pause_receipt",
        "ui_control_resume_receipt",
        "ui_control_cancel_receipt",
    ],
}

# Independently maintained acceptance table: id, surface, fixture, sampling,
# statistic, primary budget, maximum budget (or None).
_EXPECTED_METRICS = (
    ("projection_cold_base", "component", "base", "cold", "maximum", 2_000_000_000, None),
    ("projection_cold_information_heavy", "component", "information-heavy", "cold", "maximum", 4_000_000_000, None),
    ("projection_unchanged_window", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_filename_ascending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_filename_descending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_size_ascending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_size_descending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_mtime_ascending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_unchanged_after_sort_mtime_descending", "component", "information-heavy", "warm", "nearest-rank-p95", 250_000_000, 500_000_000),
    ("projection_changed_search_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_filter_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_collapse_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_reset_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_filename_ascending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_filename_descending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_size_ascending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_size_descending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_mtime_ascending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("projection_changed_sort_mtime_descending_window", "component", "information-heavy", "warm", "nearest-rank-p95", 1_500_000_000, 3_000_000_000),
    ("selection_freeze_normalize_100000", "component", "base", "warm", "nearest-rank-p95", 500_000_000, 1_000_000_000),
    ("selection_preview_depth_32", "component", "base", "warm", "nearest-rank-p95", 500_000_000, 1_000_000_000),
    ("projection_incremental_retained_memory_staging_overlap", "component", "information-heavy", "cold", "maximum", 335_544_320, None),
    ("ui_update_plan_view_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_mutate_plan_selection_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_start_execution_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_confirm_execution_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_start_execution_nondestructive_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_control_pause_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_control_resume_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_control_cancel_click_feedback", "installed-headed", "base", "cold", "maximum", 50_000_000, None),
    ("ui_get_plan_window_one_row_receipt", "installed-headed", "base", "warm", "nearest-rank-p95", 100_000_000, 250_000_000),
    ("ui_start_execution_receipt", "installed-headed", "base", "warm", "nearest-rank-p95", 100_000_000, 250_000_000),
    ("ui_control_pause_receipt", "installed-headed", "base", "warm", "nearest-rank-p95", 100_000_000, 250_000_000),
    ("ui_control_resume_receipt", "installed-headed", "base", "warm", "nearest-rank-p95", 100_000_000, 250_000_000),
    ("ui_control_cancel_receipt", "installed-headed", "base", "warm", "nearest-rank-p95", 100_000_000, 250_000_000),
)

_EXPECTED_PROFILE = {
    "operating_system": "Windows 11 Pro build 26200",
    "cpu": "i7-13700K (16 cores/24 logical processors)",
    "memory": "63.7 GiB RAM",
    "disk": "WD_BLACK SN850X 4 TB NVMe for repository/fixtures/SQLite",
    "power": "AC",
    "python": "CPython 3.13.14",
    "sqlite": "SQLite 3.50.4",
    "workload": "no unrelated sustained workload",
}


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """One validator-derived result; raw artifacts contain no verdict."""

    metric_id: str
    statistic: int
    maximum: int
    budget: int
    headroom: int
    within_child_ranges: tuple[int, ...]
    across_child_range: int


def canonical_json_bytes(value: object) -> bytes:
    """Encode JSON independently of the benchmark runner."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    """Hash canonical JSON independently of the benchmark runner."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def git_blob_oid(content: bytes) -> str:
    """Calculate Git's canonical blob identity without invoking or writing Git."""

    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def nearest_rank_p95(values: list[int]) -> int:
    """Calculate the predeclared nearest-rank P95 independently."""

    if len(values) != 30:
        raise ValueError("plan-review P95 requires exactly 30 samples")
    ordered = sorted(values)
    return ordered[(95 * len(ordered) + 99) // 100 - 1]


def validate_artifact(
    contract: object,
    authority: object,
    authority_bytes: bytes,
    authority_git_blob_oid: str,
    raw: object,
) -> tuple[MetricObservation, ...]:
    """Validate one terminal verdict-free artifact and derive gate results."""

    _validate_contract(contract)
    _validate_authority(contract, authority)
    if type(authority_bytes) is not bytes:
        raise TypeError("plan-review authority bytes are invalid")
    try:
        decoded_authority = json.loads(authority_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("plan-review authority bytes are invalid") from error
    if decoded_authority != authority:
        raise ValueError("plan-review authority bytes do not encode the authority")
    if type(raw) is not dict or set(raw) != {
        "authority_receipt",
        "children",
        "contract_sha256",
        "fixture_manifest_sha256",
        "native_profile_sha256",
        "schema",
    }:
        raise ValueError("plan-review artifact shape is invalid")
    contract_sha256, _authority_schema, raw_schema, _fixture_schema = _contract_family(contract)
    if raw["schema"] != raw_schema:
        raise ValueError("plan-review artifact schema is invalid")
    if raw["contract_sha256"] != contract_sha256:
        raise ValueError("plan-review artifact contract authority is invalid")
    expected_receipt = {
        "byte_length": len(authority_bytes),
        "sha256": hashlib.sha256(authority_bytes).hexdigest(),
        "git_blob_oid": authority_git_blob_oid,
    }
    if not _is_hex(authority_git_blob_oid, _HEX40):
        raise ValueError("plan-review authority Git identity is invalid")
    if raw["authority_receipt"] != expected_receipt:
        raise ValueError("plan-review artifact authority receipt is invalid")
    if raw["native_profile_sha256"] != authority["native_profile"]["sha256"]:
        raise ValueError("plan-review artifact native profile is invalid")
    expected_fixtures = {
        name: canonical_sha256(manifest)
        for name, manifest in authority["fixture_manifests"].items()
    }
    if raw["fixture_manifest_sha256"] != expected_fixtures:
        raise ValueError("plan-review artifact fixture authority is invalid")
    return _validate_children(
        contract, raw["children"], authority["headed_runtime"]
    )


def _readiness_plan(
    contract: Mapping[str, object],
) -> list[tuple[str, list[str]]]:
    readiness = contract["readiness"]
    headed = readiness["headed_metric_ids"]
    return [
        ("installed-headed", [headed[0]]),
        ("component", list(readiness["component_metric_ids"])),
        ("component", [readiness["memory_metric_id"]]),
        *(("installed-headed", [metric_id]) for metric_id in headed[1:]),
    ]


def validate_readiness(
    contract: object,
    authority: object,
    authority_bytes: bytes,
    readiness: object,
) -> None:
    """Validate the complete untimed readiness receipt independently."""

    _validate_contract(contract)
    _validate_authority(contract, authority)
    if type(authority_bytes) is not bytes:
        raise TypeError("plan-review readiness authority bytes are invalid")
    try:
        decoded_authority = json.loads(authority_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("plan-review readiness authority bytes are invalid") from error
    if decoded_authority != authority:
        raise ValueError("plan-review readiness authority bytes do not match")
    if type(readiness) is not dict or set(readiness) != {
        "authority_sha256", "children", "contract_sha256", "coverage", "schema",
    }:
        raise ValueError("plan-review readiness shape is invalid")
    contract_sha256, _authority_schema, _raw_schema, _fixture_schema = _contract_family(contract)
    if (
        readiness["schema"] != READINESS_SCHEMA
        or readiness["authority_sha256"]
        != hashlib.sha256(authority_bytes).hexdigest()
        or readiness["contract_sha256"] != contract_sha256
    ):
        raise ValueError("plan-review readiness authority is invalid")
    plan = _readiness_plan(contract)
    expected_coverage = [metric_id for _surface, ids in plan for metric_id in ids]
    children = readiness["children"]
    if (
        readiness["coverage"] != expected_coverage
        or type(children) is not list
        or len(children) != _EXPECTED_READINESS["child_count"]
    ):
        raise ValueError("plan-review readiness coverage is invalid")
    metrics = {metric["id"]: metric for metric in contract["metrics"]}
    child_ids: set[str] = set()
    launch_tokens: set[str] = set()
    processes: set[tuple[int, int]] = set()
    headed_plan_ids: set[tuple[str, str]] = set()
    for wrapper, (surface, metric_ids) in zip(children, plan, strict=True):
        if type(wrapper) is not dict or set(wrapper) != {"receipt", "receipt_sha256"}:
            raise ValueError("plan-review readiness child wrapper is invalid")
        receipt = wrapper["receipt"]
        if (
            not _is_hex(wrapper["receipt_sha256"], _HEX64)
            or wrapper["receipt_sha256"] != canonical_sha256(receipt)
            or type(receipt) is not dict
            or set(receipt) != {
                "child_id", "correctness", "headed_fixture", "headed_runtime",
                "launch_token", "metric_ids", "process_identity", "schema", "surface",
            }
        ):
            raise ValueError("plan-review readiness child shape is invalid")
        expected_correctness = {
            metric_id: metrics[metric_id]["correctness"] for metric_id in metric_ids
        }
        if (
            receipt["schema"] != READINESS_CHILD_SCHEMA
            or receipt["surface"] != surface
            or receipt["metric_ids"] != metric_ids
            or receipt["correctness"] != expected_correctness
        ):
            raise ValueError("plan-review readiness child contract is invalid")
        if (
            not _is_hex(receipt["child_id"], _HEX32)
            or not _is_hex(receipt["launch_token"], _HEX32)
            or receipt["child_id"] in child_ids
            or receipt["launch_token"] in launch_tokens
        ):
            raise ValueError("plan-review readiness child identity is invalid")
        process = receipt["process_identity"]
        if (
            type(process) is not dict
            or set(process) != {"creation_filetime_100ns", "pid"}
            or type(process["pid"]) is not int
            or process["pid"] <= 0
            or type(process["creation_filetime_100ns"]) is not int
            or process["creation_filetime_100ns"] <= 0
        ):
            raise ValueError("plan-review readiness process identity is invalid")
        process_key = (process["pid"], process["creation_filetime_100ns"])
        if process_key in processes:
            raise ValueError("plan-review readiness process is reused")
        child_ids.add(receipt["child_id"])
        launch_tokens.add(receipt["launch_token"])
        processes.add(process_key)
        if surface == "installed-headed":
            if receipt["headed_runtime"] != authority["headed_runtime"]:
                raise ValueError("plan-review readiness headed runtime is invalid")
            _validate_child_headed_fixture(
                metrics[metric_ids[0]], receipt["headed_fixture"], headed_plan_ids
            )
        elif receipt["headed_runtime"] is not None or receipt["headed_fixture"] is not None:
            raise ValueError("plan-review component readiness retained headed evidence")


def validate_collection_index(
    contract: object,
    authority_bytes: bytes,
    readiness_bytes: bytes,
    collection: object,
    collection_root: Path,
) -> None:
    """Validate durable partial child evidence without treating it as terminal."""

    _validate_contract(contract)
    if type(authority_bytes) is not bytes or type(readiness_bytes) is not bytes:
        raise TypeError("plan-review collection evidence bytes are invalid")
    try:
        authority = json.loads(authority_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("plan-review collection authority bytes are invalid") from error
    _validate_authority(contract, authority)
    if type(collection) is not dict or set(collection) != {
        "accepted", "authority_sha256", "collection_kind", "contract_sha256",
        "next_or_failed", "planned_child_count", "readiness_sha256", "schema",
    }:
        raise ValueError("plan-review collection index shape is invalid")
    if collection["collection_kind"] == "measurement":
        planned = [
            (metric["id"], ordinal)
            for metric in contract["metrics"]
            for ordinal in range(
                contract["sampling"][metric["sample_kind"]]["fresh_children"]
            )
        ]
        expected_readiness_hash = hashlib.sha256(readiness_bytes).hexdigest()
        try:
            readiness = json.loads(readiness_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("plan-review collection readiness bytes are invalid") from error
        validate_readiness(contract, authority, authority_bytes, readiness)
    elif collection["collection_kind"] == "readiness":
        readiness_plan = _readiness_plan(contract)
        planned = [
            (
                metric_ids[0] if surface == "installed-headed" else (
                    "component" if len(metric_ids) > 1 else "memory"
                ),
                ordinal,
            )
            for ordinal, (surface, metric_ids) in enumerate(readiness_plan)
        ]
        expected_readiness_hash = None
    else:
        raise ValueError("plan-review collection kind is invalid")
    contract_sha256, _authority_schema, _raw_schema, _fixture_schema = _contract_family(contract)
    if (
        collection["schema"] != COLLECTION_SCHEMA
        or collection["authority_sha256"]
        != hashlib.sha256(authority_bytes).hexdigest()
        or collection["contract_sha256"] != contract_sha256
        or collection["readiness_sha256"] != expected_readiness_hash
        or collection["planned_child_count"] != len(planned)
        or type(collection["accepted"]) is not list
        or len(collection["accepted"]) > len(planned)
    ):
        raise ValueError("plan-review collection index authority is invalid")
    child_ids: set[str] = set()
    tokens: set[str] = set()
    processes: set[tuple[int, int]] = set()
    headed_plan_ids: set[tuple[str, str]] = set()
    for position, item in enumerate(collection["accepted"]):
        if type(item) is not dict or set(item) != {
            "case_id", "child_ordinal", "launch_token", "process_identity",
            "receipt_path", "receipt_sha256",
        }:
            raise ValueError("plan-review collection member shape is invalid")
        if (item["case_id"], item["child_ordinal"]) != planned[position]:
            raise ValueError("plan-review collection member order is invalid")
        if (
            not _is_hex(item["launch_token"], _HEX32)
            or item["launch_token"] in tokens
            or not _is_hex(item["receipt_sha256"], _HEX64)
            or type(item["receipt_path"]) is not str
            or Path(item["receipt_path"]).is_absolute()
            or ".." in Path(item["receipt_path"]).parts
        ):
            raise ValueError("plan-review collection member identity is invalid")
        receipt_path = collection_root / item["receipt_path"]
        try:
            receipt_bytes = receipt_path.read_bytes()
            receipt = json.loads(receipt_bytes)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("plan-review collection receipt is unavailable") from error
        if hashlib.sha256(receipt_bytes).hexdigest() != item["receipt_sha256"]:
            raise ValueError("plan-review collection receipt hash is invalid")
        if type(receipt) is not dict:
            raise ValueError("plan-review collection receipt is invalid")
        expected_schema = (
            CHILD_RECEIPT_SCHEMA
            if collection["collection_kind"] == "measurement"
            else READINESS_CHILD_SCHEMA
        )
        if receipt.get("schema") != expected_schema:
            raise ValueError("plan-review collection receipt schema is invalid")
        if collection["collection_kind"] == "measurement":
            case_matches = receipt.get("metric_id") == item["case_id"]
            metric = next(
                row for row in contract["metrics"] if row["id"] == item["case_id"]
            )
            if type(receipt) is not dict or set(receipt) != {
                "child_id", "fixture_case", "headed_fixture", "headed_runtime",
                "launch_token", "metric_id", "process_identity", "sample_kind",
                "samples", "schema",
            }:
                raise ValueError("plan-review collection measurement receipt is invalid")
            sampling = contract["sampling"][metric["sample_kind"]]
            samples = receipt["samples"]
            if (
                receipt["fixture_case"] != metric["fixture_case"]
                or receipt["sample_kind"] != metric["sample_kind"]
                or type(samples) is not list
                or len(samples) != sampling["samples_per_child"]
                or receipt["headed_runtime"] != (
                    authority["headed_runtime"]
                    if metric["surface"] == "installed-headed" else None
                )
            ):
                raise ValueError("plan-review collection measurement case is invalid")
            _validate_child_headed_fixture(
                metric, receipt["headed_fixture"], headed_plan_ids
            )
            measured_field = (
                "retained_bytes" if "budget_bytes" in metric else "elapsed_ns"
            )
            other_field = (
                "elapsed_ns" if measured_field == "retained_bytes" else "retained_bytes"
            )
            for iteration, sample in enumerate(samples, start=1):
                if (
                    type(sample) is not dict
                    or set(sample) != {
                        "correctness", "elapsed_ns", "iteration", "retained_bytes"
                    }
                    or sample["iteration"] != iteration
                    or sample["correctness"] != metric["correctness"]
                    or type(sample[measured_field]) is not int
                    or sample[measured_field] < 0
                    or sample[other_field] is not None
                ):
                    raise ValueError("plan-review collection measurement sample is invalid")
        else:
            expected_surface, expected_ids = _readiness_plan(contract)[position]
            case_matches = receipt.get("metric_ids") == expected_ids
            if type(receipt) is not dict or set(receipt) != {
                "child_id", "correctness", "headed_fixture", "headed_runtime",
                "launch_token", "metric_ids", "process_identity", "schema", "surface",
            }:
                raise ValueError("plan-review collection readiness receipt is invalid")
            expected_correctness = {
                metric_id: next(
                    row["correctness"]
                    for row in contract["metrics"]
                    if row["id"] == metric_id
                )
                for metric_id in expected_ids
            }
            if (
                receipt["surface"] != expected_surface
                or receipt["correctness"] != expected_correctness
                or receipt["headed_runtime"] != (
                    authority["headed_runtime"]
                    if expected_surface == "installed-headed" else None
                )
            ):
                raise ValueError("plan-review collection readiness case is invalid")
            if expected_surface == "installed-headed":
                metric = next(
                    row for row in contract["metrics"] if row["id"] == expected_ids[0]
                )
                _validate_child_headed_fixture(
                    metric, receipt["headed_fixture"], headed_plan_ids
                )
            elif receipt["headed_fixture"] is not None:
                raise ValueError("plan-review component readiness fixture is invalid")
        if (
            not case_matches
            or receipt.get("launch_token") != item["launch_token"]
            or receipt.get("process_identity") != item["process_identity"]
        ):
            raise ValueError("plan-review collection receipt identity is invalid")
        process = item["process_identity"]
        if (
            type(process) is not dict
            or set(process) != {"creation_filetime_100ns", "pid"}
            or type(process["pid"]) is not int
            or process["pid"] <= 0
            or type(process["creation_filetime_100ns"]) is not int
            or process["creation_filetime_100ns"] <= 0
            or not _is_hex(receipt.get("child_id"), _HEX32)
        ):
            raise ValueError("plan-review collection process shape is invalid")
        process_key = (process["pid"], process["creation_filetime_100ns"])
        if (
            receipt.get("child_id") in child_ids
            or process_key in processes
        ):
            raise ValueError("plan-review collection child identity is reused")
        child_ids.add(receipt["child_id"])
        tokens.add(item["launch_token"])
        processes.add(process_key)
    marker = collection["next_or_failed"]
    if marker == {"status": "complete"}:
        if len(collection["accepted"]) != len(planned):
            raise ValueError("plan-review collection completeness is invalid")
        return
    allowed = {"case_id", "child_ordinal", "launch_token", "status"}
    if type(marker) is not dict or marker.keys() - {
        "error", "error_class", "error_truncated"
    } != allowed:
        raise ValueError("plan-review collection attempt shape is invalid")
    if marker["status"] not in {"next", "launching", "failed"}:
        raise ValueError("plan-review collection attempt status is invalid")
    next_position = len(collection["accepted"])
    if next_position >= len(planned) or (
        marker["case_id"], marker["child_ordinal"]
    ) != planned[next_position] or not _is_hex(marker["launch_token"], _HEX32):
        raise ValueError("plan-review collection attempt identity is invalid")
    if marker["launch_token"] in tokens:
        raise ValueError("plan-review collection attempt launch is reused")
    if marker["status"] == "failed":
        _validate_collection_error(marker)
    elif set(marker) != allowed:
        raise ValueError("plan-review collection nonfailure retained an error")


def _validate_collection_error(value: Mapping[str, object]) -> None:
    if (
        type(value.get("error")) is not str
        or not value["error"]
        or len(value["error"]) > 4096
        or type(value.get("error_class")) is not str
        or not value["error_class"]
        or len(value["error_class"]) > 128
        or type(value.get("error_truncated")) is not bool
    ):
        raise ValueError("plan-review collection failure is invalid")


def validate_authority_bytes(
    contract: object,
    authority: object,
    *,
    source_bytes: Mapping[str, bytes],
    source_git_blob_oids: Mapping[str, str],
    installed_bytes: Mapping[str, bytes],
    installed_wheel_name: str,
    installed_wheel_bytes: bytes,
    runtime_bytes: Mapping[str, tuple[str, bytes]],
    headed_runtime: object,
    native_profile_bytes: bytes,
    fixture_manifests: Mapping[str, object],
) -> None:
    """Require authority to describe all actual measured bytes and fixtures."""

    _validate_contract(contract)
    _validate_authority(contract, authority)
    _validate_source_bytes(
        authority["source_files"], source_bytes, source_git_blob_oids
    )
    wheel = authority["installed_wheel"]
    if (
        type(installed_wheel_name) is not str
        or installed_wheel_name != wheel["name"]
        or type(installed_wheel_bytes) is not bytes
        or len(installed_wheel_bytes) != wheel["byte_length"]
        or hashlib.sha256(installed_wheel_bytes).hexdigest() != wheel["sha256"]
    ):
        raise ValueError("plan-review installed wheel bytes are not authoritative")
    _validate_installed_product_bytes(
        authority["installed_files"],
        authority["source_files"],
        source_bytes,
        installed_bytes,
        installed_wheel_bytes,
    )
    if headed_runtime != authority["headed_runtime"]:
        raise ValueError("plan-review headed runtime identity is not authoritative")
    if set(runtime_bytes) != set(authority["runtime_files"]):
        raise ValueError("plan-review runtime population is not authoritative")
    for role, (path, content) in runtime_bytes.items():
        expected = authority["runtime_files"][role]
        if (
            type(path) is not str
            or path != expected["path"]
            or type(content) is not bytes
            or hashlib.sha256(content).hexdigest() != expected["sha256"]
        ):
            raise ValueError("plan-review runtime bytes are not authoritative")
    if (
        type(native_profile_bytes) is not bytes
        or len(native_profile_bytes) != authority["native_profile"]["byte_length"]
        or hashlib.sha256(native_profile_bytes).hexdigest()
        != authority["native_profile"]["sha256"]
        or native_profile_bytes.hex() != authority["native_profile"]["utf8_hex"]
    ):
        raise ValueError("plan-review native profile bytes are not authoritative")
    if fixture_manifests != authority["fixture_manifests"]:
        raise ValueError("plan-review realized fixtures are not authoritative")


def validate_authority_workspace(
    contract: object,
    authority: object,
    source_root: Path,
    installed_root: Path,
    installed_wheel: Path,
    runtime_paths: Mapping[str, Path],
    headed_runtime: object,
    native_profile_bytes: bytes,
    fixture_manifests: Mapping[str, object],
) -> None:
    """Hash the exact source, installed, wheel, runtime and profile inputs."""

    source_paths = contract["authority"]["source_paths"]
    installed_paths = contract["authority"]["installed_paths"]
    validate_authority_bytes(
        contract,
        authority,
        source_bytes={path: (source_root / path).read_bytes() for path in source_paths},
        source_git_blob_oids={
            path: _git_filtered_blob_oid(
                source_root, path, (source_root / path).read_bytes()
            )
            for path in source_paths
        },
        installed_bytes={path: (installed_root / path).read_bytes() for path in installed_paths},
        installed_wheel_name=installed_wheel.name,
        installed_wheel_bytes=installed_wheel.read_bytes(),
        runtime_bytes={role: (str(path), path.read_bytes()) for role, path in runtime_paths.items()},
        headed_runtime=headed_runtime,
        native_profile_bytes=native_profile_bytes,
        fixture_manifests=fixture_manifests,
    )


def validate_committed_source_workspace(
    contract: object,
    authority: object,
    source_root: Path,
    *,
    contract_path: Path,
    authority_path: Path,
    raw_path: Path,
    raw: object,
) -> None:
    """Verify measured inputs and evidence became exact clean HEAD blobs."""

    _validate_contract(contract)
    _validate_authority(contract, authority)
    if type(raw) is not dict or type(raw.get("authority_receipt")) is not dict:
        raise ValueError("plan-review committed artifact receipt is invalid")
    source_root = source_root.resolve()
    source_paths = tuple(contract["authority"]["source_paths"])
    for relative in source_paths:
        content = (source_root / relative).read_bytes()
        record = authority["source_files"][relative]
        if hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise ValueError("plan-review committed source physical bytes changed")
        if _head_blob_oid(source_root, relative) != record["git_blob_oid"]:
            raise ValueError("plan-review committed source Git identity changed")

    terminal_paths = {
        "contract": contract_path,
        "authority": authority_path,
        "measurements": raw_path,
    }
    terminal_relatives = {
        name: _repository_relative_path(source_root, path)
        for name, path in terminal_paths.items()
    }
    terminal_oids = {
        name: _git_filtered_blob_oid(
            source_root, terminal_relatives[name], path.read_bytes()
        )
        for name, path in terminal_paths.items()
    }
    for name, relative in terminal_relatives.items():
        if _head_blob_oid(source_root, relative) != terminal_oids[name]:
            raise ValueError(f"plan-review committed {name} Git identity changed")
    if terminal_oids["authority"] != raw["authority_receipt"].get("git_blob_oid"):
        raise ValueError("plan-review committed authority receipt identity changed")

    measured_paths = (*source_paths, *terminal_relatives.values())
    status = subprocess.run(
        ("git", "status", "--porcelain=v1", "--", *measured_paths),
        cwd=source_root,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if status.returncode or status.stdout:
        raise ValueError("plan-review measured and evidence paths are not clean")


def _repository_relative_path(source_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(source_root)).replace("\\", "/")
    except ValueError as error:
        raise ValueError("plan-review evidence path is outside the repository") from error


def _head_blob_oid(source_root: Path, relative: str) -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "--verify", f"HEAD:{relative}"),
        cwd=source_root,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    oid = completed.stdout.strip()
    if completed.returncode or not _is_hex(oid, _HEX40):
        raise ValueError("plan-review committed Git identity cannot be resolved")
    return oid


def validate_terminal_files(
    *,
    contract_path: Path,
    authority_path: Path,
    readiness_path: Path,
    raw_path: Path,
    source_root: Path,
    installed_root: Path,
    installed_wheel: Path,
    require_committed_source: bool = False,
) -> tuple[MetricObservation, ...]:
    """Load and validate the actual gate files and their current byte authorities."""

    _validate_loaded_installed_root(installed_root)
    contract = json.loads(contract_path.read_bytes())
    authority_bytes = authority_path.read_bytes()
    authority = json.loads(authority_bytes)
    readiness = json.loads(readiness_path.read_bytes())
    raw = json.loads(raw_path.read_bytes())
    runtime_paths = {
        role: Path(record["path"])
        for role, record in authority["runtime_files"].items()
    }
    native_profile_bytes = bytes.fromhex(authority["native_profile"]["utf8_hex"])
    validate_authority_workspace(
        contract,
        authority,
        source_root,
        installed_root,
        installed_wheel,
        runtime_paths,
        authority["headed_runtime"],
        native_profile_bytes,
        authority["fixture_manifests"],
    )
    validate_readiness(contract, authority, authority_bytes, readiness)
    observations = validate_artifact(
        contract,
        authority,
        authority_bytes,
        _git_filtered_blob_oid(
            source_root,
            str(authority_path.resolve().relative_to(source_root.resolve())).replace(
                "\\", "/"
            ),
            authority_bytes,
        ),
        raw,
    )
    if require_committed_source:
        validate_committed_source_workspace(
            contract,
            authority,
            source_root,
            contract_path=contract_path,
            authority_path=authority_path,
            raw_path=raw_path,
            raw=raw,
        )
    return observations


def _validate_loaded_installed_root(installed_root: Path) -> None:
    specification = importlib.util.find_spec("namisync")
    expected = (installed_root / "namisync" / "__init__.py").resolve()
    origin = None if specification is None else specification.origin
    if origin is None or Path(origin).resolve() != expected:
        raise ValueError(
            "plan-review terminal validator did not resolve the installed package root"
        )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the actual M1-7 plan-review scale artifacts."
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--readiness", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--installed-root", required=True, type=Path)
    parser.add_argument("--installed-wheel", required=True, type=Path)
    parser.add_argument("--require-committed-source", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    validate_terminal_files(
        contract_path=arguments.contract,
        authority_path=arguments.authority,
        readiness_path=arguments.readiness,
        raw_path=arguments.measurements,
        source_root=arguments.source_root,
        installed_root=arguments.installed_root,
        installed_wheel=arguments.installed_wheel,
        require_committed_source=arguments.require_committed_source,
    )
    return 0


def _validate_contract(contract: object) -> None:
    if type(contract) is not dict or set(contract) != {
        "artifacts", "authority", "fixture", "gate", "memory_method",
        "headed_fixture", "metrics", "profile", "readiness", "sampling", "schema",
    }:
        raise ValueError("plan-review contract shape is invalid")
    contract_sha256, _authority_schema, _raw_schema, fixture_schema = _contract_family(contract)
    if canonical_sha256(contract) != contract_sha256:
        raise ValueError("plan-review contract authority is not frozen")
    if contract["profile"] != _EXPECTED_PROFILE:
        raise ValueError("plan-review contract profile is invalid")
    if contract["sampling"] != _EXPECTED_SAMPLING:
        raise ValueError("plan-review contract sampling is invalid")
    if contract["headed_fixture"] != _EXPECTED_HEADED_FIXTURE:
        raise ValueError("plan-review contract headed fixture is invalid")
    if contract["readiness"] != _EXPECTED_READINESS:
        raise ValueError("plan-review contract readiness is invalid")
    compact = contract["schema"] == CONTRACT_SCHEMA
    if contract["artifacts"] != {
        "authority": (
            "tests/interfaces/web/m1_7_plan_compact_authority.json"
            if compact
            else "tests/interfaces/web/m1_7_plan_authority.json"
        ),
        "measurements": (
            "tests/interfaces/web/m1_7_plan_compact_measurements.json"
            if compact
            else "tests/interfaces/web/m1_7_plan_measurements.json"
        ),
    }:
        raise ValueError("plan-review contract artifact paths are invalid")
    if contract["authority"].get("fixture_manifest_schema") != fixture_schema:
        raise ValueError("plan-review contract fixture authority is invalid")
    fixture = contract["fixture"]
    if (
        type(fixture) is not dict
        or fixture.get("seed") != 0x4E414D49
        or fixture.get("window_limit") != 256
        or fixture.get("depth") != 32
        or fixture.get("dependency_depth") != 32
        or fixture.get("base") != {
            "operations": 100_000,
            "structural_group_ghost_rows": 20_000,
            "warnings": 0,
            "projection_rows": 120_000,
        }
        or fixture.get("information_heavy") != {
            "operations": 100_000,
            "structural_group_ghost_rows": 20_000,
            "warnings": 120_000,
            "repeated_warning_occurrences": 20_000,
            "projection_rows": 240_000,
        }
    ):
        raise ValueError("plan-review contract fixture is invalid")
    metrics = contract["metrics"]
    if type(metrics) is not list or len(metrics) != len(_EXPECTED_METRICS):
        raise ValueError("plan-review contract metric population is invalid")
    actual_rows = []
    for metric in metrics:
        if type(metric) is not dict or metric.get("tier") != 2:
            raise ValueError("plan-review contract metric is invalid")
        budget_key = "budget_bytes" if "budget_bytes" in metric else "budget_ns"
        actual_rows.append(
            (
                metric.get("id"), metric.get("surface"), metric.get("fixture_case"),
                metric.get("sample_kind"), metric.get("statistic"),
                metric.get(budget_key), metric.get("maximum_budget_ns"),
            )
        )
        required = {
            "id", "surface", "fixture_case", "initial_state", "untimed_setup",
            "timed_transition", "endpoint", "correctness", "sample_kind",
            "statistic", budget_key, "tier",
        }
        if metric.keys() - {"maximum_budget_ns"} != required:
            raise ValueError("plan-review contract metric shape is invalid")
        if metric["statistic"] == "nearest-rank-p95" and "maximum_budget_ns" not in metric:
            raise ValueError("plan-review contract metric maximum is missing")
    if tuple(actual_rows) != _EXPECTED_METRICS:
        raise ValueError("plan-review contract metric table is invalid")


def _validate_authority(contract: dict[str, object], authority: object) -> None:
    if type(authority) is not dict or set(authority) != {
        "contract_sha256", "fixture_manifests", "installed_files",
        "installed_wheel", "headed_runtime", "native_profile", "runtime_files", "schema",
        "source_files",
    }:
        raise ValueError("plan-review authority shape is invalid")
    contract_sha256, authority_schema, _raw_schema, fixture_schema = _contract_family(contract)
    if authority["schema"] != authority_schema or authority["contract_sha256"] != contract_sha256:
        raise ValueError("plan-review authority contract is invalid")
    expected_sources = set(contract["authority"]["source_paths"])
    expected_installed = set(contract["authority"]["installed_paths"])
    expected_runtime = set(contract["authority"]["runtime_roles"])
    if set(authority["source_files"]) != expected_sources:
        raise ValueError("plan-review source population is not authoritative")
    if set(authority["installed_files"]) != expected_installed:
        raise ValueError("plan-review installed population is not authoritative")
    if set(authority["runtime_files"]) != expected_runtime:
        raise ValueError("plan-review runtime population is not authoritative")
    _validate_source_manifest(authority["source_files"])
    _validate_installed_manifest(authority["installed_files"])
    _validate_runtime_manifest(authority["runtime_files"])
    _validate_headed_runtime(
        authority["headed_runtime"], authority["runtime_files"]
    )
    wheel = authority["installed_wheel"]
    if (
        type(wheel) is not dict or set(wheel) != {"byte_length", "name", "sha256"}
        or type(wheel["name"]) is not str or not wheel["name"].endswith(".whl")
        or type(wheel["byte_length"]) is not int or wheel["byte_length"] <= 0
        or not _is_hex(wheel["sha256"], _HEX64)
    ):
        raise ValueError("plan-review authority wheel is invalid")
    profile = authority["native_profile"]
    if (
        type(profile) is not dict
        or set(profile) != {"byte_length", "sha256", "utf8_hex"}
        or type(profile["byte_length"]) is not int or profile["byte_length"] <= 0
        or not _is_hex(profile["sha256"], _HEX64)
        or type(profile["utf8_hex"]) is not str
    ):
        raise ValueError("plan-review authority native profile is invalid")
    try:
        profile_bytes = bytes.fromhex(profile["utf8_hex"])
        profile_value = json.loads(profile_bytes)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("plan-review authority native profile is invalid") from error
    if (
        len(profile_bytes) != profile["byte_length"]
        or hashlib.sha256(profile_bytes).hexdigest() != profile["sha256"]
        or canonical_json_bytes(profile_value) != profile_bytes
    ):
        raise ValueError("plan-review authority native profile bytes are invalid")
    _validate_native_profile_semantics(profile_value, contract["profile"])
    if (
        profile_value["observed"]["python"]["executable"]
        != authority["runtime_files"]["python_executable"]["path"]
    ):
        raise ValueError("plan-review native profile runtime is not authoritative")
    manifests = authority["fixture_manifests"]
    if type(manifests) is not dict or set(manifests) != {"base", "information-heavy"}:
        raise ValueError("plan-review authority fixture population is invalid")
    _validate_fixture_manifest(manifests["base"], heavy=False, schema=fixture_schema)
    _validate_fixture_manifest(
        manifests["information-heavy"], heavy=True, schema=fixture_schema
    )


def _validate_source_manifest(value: object) -> None:
    if type(value) is not dict:
        raise ValueError("plan-review source files are invalid")
    for path, digest in value.items():
        _validate_relative_path(path, "source")
        if (
            type(digest) is not dict
            or set(digest) != {"git_blob_oid", "sha256"}
            or not _is_hex(digest["git_blob_oid"], _HEX40)
            or not _is_hex(digest["sha256"], _HEX64)
        ):
            raise ValueError("plan-review source files are invalid")


def _validate_installed_manifest(value: object) -> None:
    if type(value) is not dict:
        raise ValueError("plan-review installed files are invalid")
    for path, record in value.items():
        _validate_relative_path(path, "installed")
        if (
            type(record) is not dict
            or set(record) != {
                "installed_sha256", "source_sha256", "wheel_member_sha256"
            }
            or not _is_hex(record["installed_sha256"], _HEX64)
            or not _is_hex(record["source_sha256"], _HEX64)
            or not _is_hex(record["wheel_member_sha256"], _HEX64)
        ):
            raise ValueError("plan-review installed files are invalid")


def _validate_runtime_manifest(value: object) -> None:
    if type(value) is not dict:
        raise ValueError("plan-review runtime files are invalid")
    for role, record in value.items():
        if (
            type(role) is not str or not role
            or type(record) is not dict or set(record) != {"path", "sha256"}
            or type(record["path"]) is not str or not record["path"]
            or not _is_hex(record["sha256"], _HEX64)
        ):
            raise ValueError("plan-review runtime files are invalid")


def _validate_headed_runtime(value: object, runtime_files: object) -> None:
    if (
        type(value) is not dict
        or set(value) != {"browser", "clr"}
        or type(runtime_files) is not dict
    ):
        raise ValueError("plan-review headed runtime identity is invalid")
    browser = value["browser"]
    clr = value["clr"]
    if (
        type(browser) is not dict
        or set(browser) != {"executable_path", "version"}
        or type(browser["executable_path"]) is not str
        or type(browser["version"]) is not str
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", browser["version"]) is None
        or PureWindowsPath(browser["executable_path"]).name.casefold()
        != "msedgewebview2.exe"
        or browser["version"] not in PureWindowsPath(browser["executable_path"]).parts
        or runtime_files.get("webview2_browser_executable", {}).get("path")
        != browser["executable_path"]
    ):
        raise ValueError("plan-review WebView2 runtime identity is invalid")
    if (
        type(clr) is not dict
        or set(clr) != {
            "module_path", "runtime_directory", "runtime_version", "system_version"
        }
        or any(type(clr[name]) is not str or not clr[name] for name in clr)
        or PureWindowsPath(clr["module_path"]).name.casefold() != "clr.dll"
        or PureWindowsPath(clr["module_path"]).parent
        != PureWindowsPath(clr["runtime_directory"])
        or re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", clr["system_version"]) is None
        or not clr["runtime_version"].startswith(clr["system_version"][1:])
        or runtime_files.get("netfx_clr_module", {}).get("path")
        != clr["module_path"]
    ):
        raise ValueError("plan-review netfx CLR identity is invalid")


def _validate_fixture_manifest(value: object, *, heavy: bool, schema: str) -> None:
    if type(value) is not dict or set(value) != {
        "artifact_digest", "case", "counts", "depth", "operation_kind_counts",
        "plan_fingerprint", "raw_key_witnesses", "retained_representation",
        "schema", "seed", "selection_facts", "siblings", "warning_code_counts",
        "warning_cycle",
    }:
        raise ValueError("plan-review fixture manifest shape is invalid")
    if value["schema"] != schema or value["seed"] != 0x4E414D49:
        raise ValueError("plan-review fixture manifest identity is invalid")
    if not _is_hex(value["artifact_digest"], _HEX64) or not _is_hex(value["plan_fingerprint"], _HEX64):
        raise ValueError("plan-review fixture digests are invalid")
    expected_counts = {
        "operations": 100_000,
        "operation_rows": 100_000,
        "prior_rows": 32,
        "structural_group_ghost_rows": 20_000,
        "warnings": 120_000 if heavy else 0,
        "unique_warning_occurrences": 100_000 if heavy else 0,
        "repeated_warning_occurrences": 20_000 if heavy else 0,
        "projection_rows": 240_000 if heavy else 120_000,
    }
    if value["case"] != ("information-heavy" if heavy else "base") or value["counts"] != expected_counts:
        raise ValueError("plan-review fixture populations are invalid")
    if value["depth"] != {"dependency": 32, "path": 32}:
        raise ValueError("plan-review fixture depth is invalid")
    if type(value["operation_kind_counts"]) is not dict or sum(value["operation_kind_counts"].values()) != 100_000:
        raise ValueError("plan-review fixture operation kinds are invalid")
    if value["selection_facts"] != {
        "destructive": {
            "destructive_operation_count": 49_998,
            "destructive_operation_counts": {
                "delete": 16_666,
                "move_update": 0,
                "trash": 16_665,
                "update": 16_667,
            },
            "irreversible_operation_count": 16_666,
            "irreversible_update_count": 0,
            "required_bytes": "9007200168568816",
            "selected_operations": 100_000,
        },
        "nondestructive": {
            "destructive_operation_count": 0,
            "destructive_operation_counts": {
                "delete": 0,
                "move_update": 0,
                "trash": 0,
                "update": 0,
            },
            "irreversible_operation_count": 0,
            "irreversible_update_count": 0,
            "required_bytes": "456905413",
            "selected_operations": 49_986,
            "user_deselected": 49_998,
        },
    }:
        raise ValueError("plan-review fixture selection facts are invalid")
    if type(value["warning_code_counts"]) is not dict or sum(value["warning_code_counts"].values()) != (120_000 if heavy else 0):
        raise ValueError("plan-review fixture warning kinds are invalid")
    cycle = value["warning_cycle"]
    if type(cycle) is not list or len(cycle) != 13 or len(set(cycle)) != 13:
        raise ValueError("plan-review fixture warning cycle is invalid")
    siblings = value["siblings"]
    if (
        type(siblings) is not dict
        or siblings.get("generated_directory_child_min") != 5
        or siblings.get("generated_directory_child_max") != 6
        or type(siblings.get("widest")) is not int
        or siblings["widest"] < 19_000
    ):
        raise ValueError("plan-review fixture sibling distribution is invalid")
    _validate_raw_key_witnesses(value["raw_key_witnesses"])
    rows = 240_000 if heavy else 120_000
    if schema == FIXTURE_SCHEMA:
        _validate_compact_retained_representation(value["retained_representation"], rows)
    else:
        _validate_retained_representation(value["retained_representation"], rows)


def _validate_raw_key_witnesses(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "canonical_ids", "expected_orders", "operation_value_cases", "rows"
    }:
        raise ValueError("plan-review fixture raw-key witnesses are invalid")
    rows = value["rows"]
    if type(rows) is not list or len(rows) != 15:
        raise ValueError("plan-review fixture raw-key witnesses are invalid")
    identities = []
    for row in rows:
        if type(row) is not dict or set(row) != {
            "display", "mtime_ns", "node_id", "operation_id", "rel_path_key", "size"
        }:
            raise ValueError("plan-review fixture raw-key row is invalid")
        identity = row["operation_id"] or row["node_id"]
        if type(identity) is not str or not identity:
            raise ValueError("plan-review fixture raw-key identity is invalid")
        identities.append(identity)
    if value["canonical_ids"] != identities:
        raise ValueError("plan-review fixture canonical witness order is invalid")
    expected_orders = {}
    for column in ("filename", "size", "mtime"):
        for direction in ("ascending", "descending"):
            expected_orders[f"{column}-{direction}"] = _independent_row_order(
                rows, identities, column, direction
            )
    if value["expected_orders"] != expected_orders:
        raise ValueError("plan-review fixture expected raw-key order is invalid")
    cases = value["operation_value_cases"]
    if type(cases) is not dict or set(cases) != {
        f"{index:032x}" for index in (0, 5, 6, 10, 15)
    }:
        raise ValueError("plan-review fixture operation value cases are invalid")
    if (
        cases[f"{0:032x}"]["kind"] != "move"
        or cases[f"{5:032x}"]["kind"] != "delete"
        or cases[f"{6:032x}"]["kind"] != "noop"
        or cases[f"{10:032x}"]["kind"] != "mkdir"
        or any(cases[f"{index:032x}"]["size"] in {None, 0} for index in (0, 5, 6))
        or cases[f"{10:032x}"]["size"] is not None
    ):
        raise ValueError("plan-review fixture operation value cases are invalid")


def _independent_row_order(
    rows: list[dict[str, object]],
    identities: list[str],
    column: str,
    direction: str,
) -> list[str]:
    canonical = {identity: ordinal for ordinal, identity in enumerate(identities)}

    def identity(row: dict[str, object]) -> str:
        return row["operation_id"] or row["node_id"]

    def primary(row: dict[str, object]) -> object:
        if column == "filename":
            return row["display"].casefold()
        return row["size"] if column == "size" else row["mtime_ns"]

    available = [row for row in rows if primary(row) is not None]
    unavailable = [row for row in rows if primary(row) is None]
    available.sort(key=primary, reverse=direction == "descending")
    start = 0
    while start < len(available):
        end = start + 1
        while end < len(available) and primary(available[end]) == primary(available[start]):
            end += 1
        available[start:end] = sorted(available[start:end], key=lambda row: canonical[identity(row)])
        start = end
    unavailable.sort(key=lambda row: canonical[identity(row)])
    return [identity(row) for row in (*available, *unavailable)]


def _validate_retained_representation(value: object, rows: int) -> None:
    if type(value) is not dict or set(value) != {
        "mapping_families", "plan_projection_fields",
        "plan_projection_field_population",
        "plan_projection_node_non_null_counts", "selected_operation_ids",
        "visible_sequence_field_population", "visible_sequence_fields",
    }:
        raise ValueError("plan-review retained representation is invalid")
    mappings = value["mapping_families"]
    if type(mappings) is not dict or set(mappings) != {
        "operation_node_id_by_id", "position_by_node_id",
        "source_position_by_node_id", "visible_index_by_node_id",
    }:
        raise ValueError("plan-review retained mapping families are invalid")
    expected_counts = {
        "operation_node_id_by_id": 100_000,
        "position_by_node_id": rows,
        "source_position_by_node_id": rows,
        "visible_index_by_node_id": rows,
    }
    expected_descriptors = {
        "operation_node_id_by_id": ("operation_id:str", "node_id:str"),
        "position_by_node_id": ("node_id:str", "position:int"),
        "source_position_by_node_id": ("node_id:str", "position:int"),
        "visible_index_by_node_id": ("node_id:str", "visible_index:int"),
    }
    for name, expected_count in expected_counts.items():
        key, mapped_value = expected_descriptors[name]
        if mappings[name] != {
            "count": expected_count,
            "key": key,
            "value": mapped_value,
        }:
            raise ValueError("plan-review retained mapping populations are invalid")
    if value["selected_operation_ids"] != 100_000:
        raise ValueError("plan-review retained selection population is invalid")
    if value["plan_projection_fields"] != [
        "request_id", "nodes", "position_by_node_id", "operation_node_id_by_id",
        "selected_operation_ids", "preflight_ready", "preflight_refusal_count",
        "warning_count",
    ]:
        raise ValueError("plan-review retained projection fields are invalid")
    if value["visible_sequence_fields"] != [
        "nodes", "visible_positions", "source_position_by_node_id",
        "visible_index_by_node_id", "parent_visible_indexes",
        "first_child_visible_indexes", "has_retained_children", "positions_in_set",
        "set_sizes", "collapsed_node_ids", "filtered_item_count",
    ]:
        raise ValueError("plan-review retained visible-sequence fields are invalid")
    def scalar(value_type: str, population: str = "populated") -> dict[str, object]:
        return {
            "classification": "scalar",
            "population": population,
            "type": value_type,
        }

    def container(value_type: str, count: int) -> dict[str, object]:
        return {
            "classification": "container",
            "count": count,
            "type": value_type,
        }

    def mapping(count: int) -> dict[str, object]:
        return {
            "classification": "mapping",
            "count": count,
            "type": "mappingproxy",
        }
    expected_projection_population = {
        "request_id": scalar("str"),
        "nodes": container("tuple", rows),
        "position_by_node_id": mapping(rows),
        "operation_node_id_by_id": mapping(100_000),
        "selected_operation_ids": container("frozenset", 100_000),
        "preflight_ready": scalar("bool"),
        "preflight_refusal_count": scalar("int"),
        "warning_count": scalar("int"),
    }
    if value["plan_projection_field_population"] != expected_projection_population:
        raise ValueError("plan-review retained projection populations are invalid")
    expected_visible_population = {
        "nodes": container("tuple", rows),
        "visible_positions": container("tuple", rows),
        "source_position_by_node_id": mapping(rows),
        "visible_index_by_node_id": mapping(rows),
        "parent_visible_indexes": container("tuple", rows),
        "first_child_visible_indexes": container("tuple", rows),
        "has_retained_children": container("tuple", rows),
        "positions_in_set": container("tuple", rows),
        "set_sizes": container("tuple", rows),
        "collapsed_node_ids": container("frozenset", 0),
        "filtered_item_count": scalar("NoneType", "intentionally-absent"),
    }
    if value["visible_sequence_field_population"] != expected_visible_population:
        raise ValueError("plan-review retained visible-sequence populations are invalid")
    expected_node_counts = {
        "blocked_reason": 0,
        "dependency_count": rows,
        "depth": rows,
        "display": rows,
        "filename_key": 119_998,
        "is_container": rows,
        "move_peer_id": 2,
        "mtime_ns": 100_000,
        "node_id": rows,
        "notice": rows - 120_000,
        "operation_count": rows,
        "operation_id": 100_000,
        "operation_kind": 100_001,
        "parent_index": rows - 1,
        "position": rows,
        "reason": 100_001,
        "rel_path_key": rows,
        "risk": rows,
        "row_kind": rows,
        "selectable_operation_count": rows,
        "selected_operation_count": rows,
        "selection": rows,
        "selection_exclusion_reason": 0,
        "size": 99_999,
        "subtree_end": rows,
    }
    if value["plan_projection_node_non_null_counts"] != expected_node_counts:
        raise ValueError("plan-review retained field population is invalid")


def _validate_compact_retained_representation(value: object, rows: int) -> None:
    if type(value) is not dict or set(value) != {
        "plan_projection_fields", "plan_projection_node_fields",
        "plan_review_state", "visible_sequence",
    }:
        raise ValueError("plan-review compact retained representation is invalid")
    if value["plan_projection_fields"] != [
        "request_id", "nodes", "position_by_node_id", "operation_node_id_by_id",
        "selected_operation_ids", "preflight_ready", "preflight_refusal_count",
        "warning_count",
    ]:
        raise ValueError("plan-review compact projection fields are invalid")
    node_fields = value["plan_projection_node_fields"]
    if node_fields != [
        "node_id", "display", "rel_path_key", "position", "depth",
        "parent_index", "subtree_end", "is_container", "row_kind",
        "operation_id", "operation_kind", "reason", "blocked_reason",
        "selection", "selectable_operation_count", "selected_operation_count",
        "operation_count", "size", "mtime_ns", "dependency_count", "risk",
        "move_peer_id", "notice", "selection_exclusion_reason", "filename_key",
    ]:
        raise ValueError("plan-review compact node fields are invalid")
    state = value["plan_review_state"]
    if type(state) is not dict or set(state) != {
        "canonical_order", "current_order", "distinct_order_objects",
        "projection_identity_shared",
    }:
        raise ValueError("plan-review compact state representation is invalid")
    if state["distinct_order_objects"] is not True or state["projection_identity_shared"] is not True:
        raise ValueError("plan-review compact state sharing is invalid")
    canonical = _validate_compact_order(state["canonical_order"], rows)
    current = _validate_compact_order(state["current_order"], rows)
    if (
        canonical["ordered_source_positions"]["values_sha256"]
        == current["ordered_source_positions"]["values_sha256"]
    ):
        raise ValueError("plan-review compact current order is not realized")
    visible = value["visible_sequence"]
    if type(visible) is not dict or set(visible) != {
        "filtered_item_count", "retained_direct_child_counts", "sibling_ordinals",
        "source_position_by_node_id_count", "visible_index_by_source_position",
        "visible_source_positions",
    }:
        raise ValueError("plan-review compact visible representation is invalid")
    if visible["filtered_item_count"] is not None or visible["source_position_by_node_id_count"] != rows:
        raise ValueError("plan-review compact visible population is invalid")
    visible_positions = _validate_compact_buffer(
        visible["visible_source_positions"], rows, permutation=True
    )
    visible_inverse = _validate_compact_buffer(
        visible["visible_index_by_source_position"], rows, permutation=True
    )
    sibling_ordinals = _validate_compact_buffer(visible["sibling_ordinals"], rows)
    child_counts = _validate_compact_buffer(
        visible["retained_direct_child_counts"], rows
    )
    widest = 139_937 if rows == 240_000 else 19_937
    if (
        sibling_ordinals["minimum"] != 1
        or sibling_ordinals["maximum"] != widest
        or child_counts["minimum"] != 0
        or child_counts["maximum"] != widest
    ):
        raise ValueError("plan-review compact accessibility population is invalid")
    if (
        visible_positions["values_sha256"]
        != current["ordered_source_positions"]["values_sha256"]
        or visible_inverse["values_sha256"]
        != current["order_rank_by_source_position"]["values_sha256"]
    ):
        raise ValueError("plan-review compact visible order is not current")


def _validate_compact_order(value: object, rows: int) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "inverse_valid", "ordered_source_positions",
        "order_rank_by_source_position", "projection_rows",
    } or value["projection_rows"] != rows or value["inverse_valid"] is not True:
        raise ValueError("plan-review compact order is invalid")
    ordered = _validate_compact_buffer(
        value["ordered_source_positions"], rows, permutation=True
    )
    inverse = _validate_compact_buffer(
        value["order_rank_by_source_position"], rows, permutation=True
    )
    return {"ordered_source_positions": ordered, "order_rank_by_source_position": inverse}


def _validate_compact_buffer(
    value: object,
    rows: int,
    *,
    permutation: bool = False,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "byte_length", "byte_width", "count", "maximum", "minimum",
        "unique_count", "values_sha256",
    }:
        raise ValueError("plan-review compact buffer is invalid")
    width = value["byte_width"]
    if (
        type(width) is not int
        or width not in {1, 2, 4, 8}
        or value["count"] != rows
        or value["byte_length"] != rows * width
        or not _is_hex(value["values_sha256"], _HEX64)
        or type(value["minimum"]) is not int
        or type(value["maximum"]) is not int
        or type(value["unique_count"]) is not int
        or value["unique_count"] < 1
        or value["unique_count"] > rows
        or not 0 <= value["minimum"] <= value["maximum"]
        or value["maximum"] >= 2 ** (8 * width)
        or width
        != (
            1
            if value["maximum"] < 2**8
            else 2
            if value["maximum"] < 2**16
            else 4
            if value["maximum"] < 2**32
            else 8
        )
    ):
        raise ValueError("plan-review compact buffer population is invalid")
    if permutation and (
        value["minimum"] != 0
        or value["maximum"] != rows - 1
        or value["unique_count"] != rows
    ):
        raise ValueError("plan-review compact buffer is not a permutation")
    return value


def _validate_source_bytes(
    expected: object,
    actual: Mapping[str, bytes],
    actual_git_blob_oids: Mapping[str, str],
) -> None:
    if (
        type(expected) is not dict
        or set(actual) != set(expected)
        or set(actual_git_blob_oids) != set(expected)
    ):
        raise ValueError("plan-review source population is not authoritative")
    for path, content in actual.items():
        record = expected[path]
        if (
            type(content) is not bytes
            or hashlib.sha256(content).hexdigest() != record["sha256"]
            or actual_git_blob_oids[path] != record["git_blob_oid"]
            or not _is_hex(actual_git_blob_oids[path], _HEX40)
        ):
            raise ValueError("plan-review source bytes are not authoritative")


def _validate_installed_product_bytes(
    expected: object,
    source_manifest: object,
    source_bytes: Mapping[str, bytes],
    installed_bytes: Mapping[str, bytes],
    wheel_bytes: bytes,
) -> None:
    if (
        type(expected) is not dict
        or type(source_manifest) is not dict
        or set(installed_bytes) != set(expected)
        or not set(expected) <= set(source_manifest)
    ):
        raise ValueError("plan-review installed population is not authoritative")
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as archive:
            names = archive.namelist()
            if any(names.count(path) != 1 for path in expected):
                raise ValueError("plan-review wheel product population is invalid")
            wheel_product_bytes = {
                path: archive.read(path)
                for path in expected
            }
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise ValueError("plan-review wheel product bytes are invalid") from error
    for path, installed_content in installed_bytes.items():
        wheel_content = wheel_product_bytes[path]
        source_content = source_bytes[path]
        record = expected[path]
        if (
            type(installed_content) is not bytes
            or installed_content != wheel_content
            or wheel_content != source_content
            or hashlib.sha256(installed_content).hexdigest()
            != record["installed_sha256"]
            or hashlib.sha256(source_content).hexdigest()
            != record["source_sha256"]
            or record["source_sha256"] != source_manifest[path]["sha256"]
            or hashlib.sha256(wheel_content).hexdigest()
            != record["wheel_member_sha256"]
        ):
            raise ValueError(
                "plan-review source, wheel and installed product bytes are not authoritative"
            )


def _validate_children(
    contract: dict[str, object], children: object, headed_runtime: object
) -> tuple[MetricObservation, ...]:
    if type(children) is not list:
        raise ValueError("plan-review child receipts are invalid")
    metrics = {metric["id"]: metric for metric in contract["metrics"]}
    grouped: dict[str, list[dict[str, object]]] = {metric_id: [] for metric_id in metrics}
    child_ids: set[str] = set()
    launch_tokens: set[str] = set()
    process_identities: set[tuple[int, int]] = set()
    headed_plan_identifiers: set[tuple[str, str]] = set()
    for wrapper in children:
        if type(wrapper) is not dict or set(wrapper) != {"receipt", "receipt_sha256"}:
            raise ValueError("plan-review child receipt wrapper is invalid")
        receipt = wrapper["receipt"]
        if not _is_hex(wrapper["receipt_sha256"], _HEX64) or wrapper["receipt_sha256"] != canonical_sha256(receipt):
            raise ValueError("plan-review child receipt digest is invalid")
        if type(receipt) is not dict or set(receipt) != {
            "child_id", "fixture_case", "headed_fixture", "headed_runtime",
            "launch_token", "metric_id", "process_identity", "sample_kind",
            "samples", "schema",
        }:
            raise ValueError("plan-review child receipt shape is invalid")
        if receipt["schema"] != CHILD_RECEIPT_SCHEMA:
            raise ValueError("plan-review child receipt schema is invalid")
        metric = metrics.get(receipt["metric_id"])
        if metric is None:
            raise ValueError("plan-review child metric is invalid")
        if receipt["fixture_case"] != metric["fixture_case"] or receipt["sample_kind"] != metric["sample_kind"]:
            raise ValueError("plan-review child case is invalid")
        expected_runtime = (
            headed_runtime if metric["surface"] == "installed-headed" else None
        )
        if receipt["headed_runtime"] != expected_runtime:
            raise ValueError("plan-review child headed runtime identity is invalid")
        _validate_child_headed_fixture(
            metric,
            receipt["headed_fixture"],
            headed_plan_identifiers,
        )
        if not _is_hex(receipt["child_id"], _HEX32) or receipt["child_id"] in child_ids:
            raise ValueError("plan-review child identity is reused")
        if not _is_hex(receipt["launch_token"], _HEX32) or receipt["launch_token"] in launch_tokens:
            raise ValueError("plan-review child launch is reused")
        child_ids.add(receipt["child_id"])
        launch_tokens.add(receipt["launch_token"])
        process = receipt["process_identity"]
        if (
            type(process) is not dict or set(process) != {"creation_filetime_100ns", "pid"}
            or type(process["pid"]) is not int or process["pid"] <= 0
            or type(process["creation_filetime_100ns"]) is not int
            or process["creation_filetime_100ns"] <= 0
        ):
            raise ValueError("plan-review child process identity is invalid")
        process_identity = (process["pid"], process["creation_filetime_100ns"])
        if process_identity in process_identities:
            raise ValueError("plan-review child process is reused")
        process_identities.add(process_identity)
        grouped[receipt["metric_id"]].append(receipt)

    observations = []
    for metric_id, metric in metrics.items():
        receipts = grouped[metric_id]
        sampling = contract["sampling"][metric["sample_kind"]]
        if len(receipts) != sampling["fresh_children"]:
            raise ValueError("plan-review child case membership is incomplete")
        measured_field = "retained_bytes" if "budget_bytes" in metric else "elapsed_ns"
        other_field = "elapsed_ns" if measured_field == "retained_bytes" else "retained_bytes"
        values: list[int] = []
        child_maxima: list[int] = []
        within_ranges: list[int] = []
        for receipt in receipts:
            samples = receipt["samples"]
            if type(samples) is not list or len(samples) != sampling["samples_per_child"]:
                raise ValueError("plan-review child sample count is invalid")
            child_values = []
            for expected_iteration, sample in enumerate(samples, start=1):
                if type(sample) is not dict or set(sample) != {
                    "correctness", "elapsed_ns", "iteration", "retained_bytes"
                }:
                    raise ValueError("plan-review child sample shape is invalid")
                if sample["iteration"] != expected_iteration or sample["correctness"] != metric["correctness"]:
                    raise ValueError("plan-review child correctness receipt is invalid")
                measured = sample[measured_field]
                if type(measured) is not int or measured < 0 or sample[other_field] is not None:
                    raise ValueError("plan-review child measurement is invalid")
                child_values.append(measured)
            values.extend(child_values)
            child_maxima.append(max(child_values))
            within_ranges.append(max(child_values) - min(child_values))
        maximum = max(values)
        statistic = maximum if metric["statistic"] == "maximum" else nearest_rank_p95(values)
        if metric["statistic"] == "nearest-rank-p95" and maximum > metric["maximum_budget_ns"]:
            raise ValueError("plan-review maximum exceeds its fixed budget")
        budget = metric.get("budget_bytes", metric.get("budget_ns"))
        if type(budget) is not int or statistic > budget:
            raise ValueError("plan-review statistic exceeds its fixed budget")
        observations.append(
            MetricObservation(
                metric_id, statistic, maximum, budget, budget - statistic,
                tuple(within_ranges), max(child_maxima) - min(child_maxima),
            )
        )
    return tuple(observations)


def _validate_child_headed_fixture(
    metric: dict[str, object],
    fixture: object,
    retained_identifiers: set[tuple[str, str]],
) -> None:
    if metric["surface"] != "installed-headed":
        if fixture is not None:
            raise ValueError("component child retained a headed fixture")
        return
    expected_count = (
        _EXPECTED_HEADED_FIXTURE["fresh_execution_plan_count"][
            metric["sample_kind"]
        ]
        if metric["id"]
        in _EXPECTED_HEADED_FIXTURE["fresh_execution_metric_ids"]
        else _EXPECTED_HEADED_FIXTURE["default_published_plan_count"]
    )
    if type(fixture) is not dict or set(fixture) != {
        "published_plan_count",
        "rows",
    }:
        raise ValueError("headed child fixture shape is invalid")
    rows = fixture["rows"]
    if (
        fixture["published_plan_count"] != expected_count
        or type(rows) is not list
        or len(rows) != expected_count
    ):
        raise ValueError("headed child fixture population is invalid")
    local_task_ids: set[str] = set()
    local_request_ids: set[str] = set()
    local_session_ids: set[str] = set()
    local_paths: set[tuple[str, str]] = set()
    expected_fields = set(_EXPECTED_HEADED_FIXTURE["published_row_fields"])
    for row in rows:
        if type(row) is not dict or set(row) != expected_fields:
            raise ValueError("headed child fixture row shape is invalid")
        identity = (
            row["task_id"],
            row["request_id"],
            row["plan_session_id"],
        )
        if (
            type(identity[0]) is not str
            or _TASK_ID.fullmatch(identity[0]) is None
            or not _is_hex(identity[1], _HEX32)
            or not _is_hex(identity[2], _HEX32)
            or identity[0] in local_task_ids
            or identity[1] in local_request_ids
            or identity[2] in local_session_ids
            or any(
                (name, value) in retained_identifiers
                for name, value in zip(
                    ("task", "request", "session"),
                    identity,
                    strict=True,
                )
            )
        ):
            raise ValueError("headed child fixture identity is invalid or reused")
        paths = (row["source_path"], row["target_path"])
        if (
            any(type(path) is not str or not path for path in paths)
            or paths[0] == paths[1]
            or paths in local_paths
            or row["task_kind"] != "sync-plan"
            or row["session_state"] != "completed"
            or row["session_released"] is not True
            or row["execution_unused"] is not True
        ):
            raise ValueError("headed child fixture publication is invalid")
        settlement = row["initial_view_settlement"]
        settlement_spec = _EXPECTED_HEADED_FIXTURE["initial_view_settlement"]
        expected_settlement_fields = {
            "first_row", "open_disposition", "plan_session_id", "request_id",
            "source_path", "target_path", "task_id", "view_revision",
            "window_disposition", "window_limit", "window_offset", "window_row_count",
            "window_total", "window_view_revision",
        }
        first = settlement.get("first_row") if type(settlement) is dict else None
        if (
            type(settlement) is not dict
            or set(settlement) != expected_settlement_fields
            or settlement["open_disposition"]
            != settlement_spec["open_disposition"]
            or settlement["task_id"] != row["task_id"]
            or settlement["request_id"] != row["request_id"]
            or settlement["plan_session_id"] != row["plan_session_id"]
            or settlement["source_path"] != row["source_path"]
            or settlement["target_path"] != row["target_path"]
            or settlement["view_revision"] != settlement_spec["view_revision"]
            or settlement["window_view_revision"]
            != settlement_spec["view_revision"]
            or settlement["window_disposition"]
            != settlement_spec["window_disposition"]
            or settlement["window_limit"] != settlement_spec["window_limit"]
            or settlement["window_offset"] != settlement_spec["window_offset"]
            or settlement["window_total"] != settlement_spec["window_total"]
            or settlement["window_row_count"] != settlement_spec["window_rows"]
            or type(first) is not dict
            or set(first) != {"node_id", "operation_id", "visible_index"}
            or first["node_id"]
            != _independent_plan_root_node_id(row["request_id"])
            or first["operation_id"]
            is not settlement_spec["first_row_operation_id"]
            or first["visible_index"]
            != settlement_spec["first_row_visible_index"]
        ):
            raise ValueError("headed child initial view settlement is invalid")
        local_task_ids.add(identity[0])
        local_request_ids.add(identity[1])
        local_session_ids.add(identity[2])
        retained_identifiers.update(
            zip(
                ("task", "request", "session"),
                identity,
                strict=True,
            )
        )
        local_paths.add(paths)


def _independent_plan_root_node_id(request_id: str) -> str:
    digest = hashlib.blake2b(digest_size=16, person=b"NamiSyncNodeV1")
    for value in ("plan", request_id, ""):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"


def _validate_relative_path(path: object, name: str) -> None:
    if (
        type(path) is not str or not path or path.startswith(("/", "\\"))
        or ".." in path.replace("\\", "/").split("/")
    ):
        raise ValueError(f"plan-review {name} path is invalid")


def _validate_native_profile_semantics(value: object, reference: object) -> None:
    if type(value) is not dict or set(value) != {
        "declared_reference", "observed", "schema"
    }:
        raise ValueError("plan-review native profile semantics are invalid")
    if value["schema"] != "namisync-m1-7-native-profile-v1":
        raise ValueError("plan-review native profile semantics are invalid")
    if value["declared_reference"] != reference:
        raise ValueError("plan-review native profile reference is false")
    observed = value["observed"]
    if type(observed) is not dict or set(observed) != {
        "cpu", "disk", "memory", "operating_system", "power", "python",
        "runtime_dependencies", "sqlite", "workload"
    }:
        raise ValueError("plan-review native profile observations are invalid")
    operating_system = observed["operating_system"]
    cpu = observed["cpu"]
    memory = observed["memory"]
    disk = observed["disk"]
    power = observed["power"]
    python = observed["python"]
    sqlite = observed["sqlite"]
    workload = observed["workload"]
    runtime_dependencies = observed["runtime_dependencies"]
    if (
        type(operating_system) is not dict
        or operating_system.get("product") != "Windows 11 Pro"
        or operating_system.get("build") != 26_200
        or type(cpu) is not dict
        or "i7-13700K" not in cpu.get("name", "")
        or cpu.get("physical_cores") != 16
        or cpu.get("logical_processors") != 24
        or type(memory) is not dict
        or type(memory.get("total_physical_bytes")) is not int
        or round(memory["total_physical_bytes"] / (1024**3), 1) != 63.7
        or type(disk) is not dict
        or "WD_BLACK SN850X" not in disk.get("model", "")
        or disk.get("bus_type") != "NVMe"
        or type(disk.get("size_bytes")) is not int
        or not 3_500_000_000_000 <= disk["size_bytes"] <= 4_500_000_000_000
        or type(power) is not dict
        or power.get("ac_online") is not True
        or type(python) is not dict
        or python.get("implementation") != "CPython"
        or python.get("version") != "3.13.14"
        or type(python.get("executable")) is not str
        or not python["executable"]
        or type(sqlite) is not dict
        or sqlite.get("version") != "3.50.4"
        or type(workload) is not dict
        or workload.get("no_unrelated_sustained_workload") is not True
        or type(runtime_dependencies) is not dict
        or set(runtime_dependencies) != {
            "bottle", "pythonnet", "pywebview", "xxhash"
        }
        or any(
            type(version) is not str or not version
            for version in runtime_dependencies.values()
        )
    ):
        raise ValueError("plan-review native profile does not match the reference")


def _git_filtered_blob_oid(source_root: Path, path: str, content: bytes) -> str:
    result = subprocess.run(
        ("git", "hash-object", f"--path={path}", "--stdin"),
        cwd=source_root,
        input=content,
        capture_output=True,
        check=False,
    )
    oid = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode or not _is_hex(oid, _HEX40):
        raise ValueError("plan-review canonical source blob cannot be resolved")
    return oid


def _is_hex(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


__all__ = [
    "AUTHORITY_SCHEMA", "CHILD_RECEIPT_SCHEMA", "COLLECTION_SCHEMA", "CONTRACT_SCHEMA",
    "CONTRACT_SHA256", "FIXTURE_SCHEMA", "MetricObservation",
    "RAW_ARTIFACT_SCHEMA", "READINESS_CHILD_SCHEMA", "READINESS_SCHEMA",
    "canonical_json_bytes", "canonical_sha256",
    "git_blob_oid", "nearest_rank_p95", "validate_artifact",
    "validate_authority_bytes", "validate_authority_workspace",
    "validate_collection_index", "validate_committed_source_workspace",
    "validate_readiness", "validate_terminal_files",
]


if __name__ == "__main__":
    raise SystemExit(main())
