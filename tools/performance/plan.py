"""Plan fixtures and selected real-endpoint observations for optional measurements."""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from contextlib import ExitStack
from copy import deepcopy
from ctypes import wintypes
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from uuid import uuid4
from unittest.mock import patch
from namisync.core.models import CapabilityProfile, EntryKind, FileStat, MetadataSnapshot, Root, ScanResult, ScanScope, ScanWarning, ScanWarningCode
from namisync.core.planning import Assignment, DeletionPolicy, FilterSet, OpId, OperationKind, Plan, PlanFingerprint, PlanOperation, PreservationPolicy, plan_fingerprint
from namisync.core.preflight import ObservedWorld, Verdict
from namisync.interfaces.web.plan_review import PlanReviewState
from namisync.interfaces.web.visible_sequence import VisibleSequenceParameters, derive_visible_sequence, window_visible_sequence
from namisync.workflows.models import PlanArtifact, PlanRequest
from namisync.workflows.plan_projection import CompactUnsignedIntegers, PlanProjection, PlanProjectionNode, PlanProjectionOrder, PlanSortColumn, SortDirection, build_plan_projection, sort_plan_projection
from namisync.workflows.runtime import execution_selection_digest_hex
from namisync.workflows.selection import derive_execution_selection


FIXTURE_SCHEMA: Final = "namisync-m1-7-plan-fixture-manifest-v2"


FIXTURE_SEED: Final = 0x4E414D49


FIXTURE_OPERATIONS: Final = 100_000


FIXTURE_WARNINGS: Final = 120_000


FIXTURE_DEPTH: Final = 32


FIXTURE_WINDOW_LIMIT: Final = 256


CHILD_RECEIPT_SCHEMA: Final = "namisync-m1-7-plan-review-child-v3"


CONTRACT_PATH: Final = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "interfaces"
    / "web"
    / "m1_7_plan_compact_contract.json"
)


_META = MetadataSnapshot(0, None)


_PROFILE = CapabilityProfile("NTFS", 100, True, False, 32_767, False, True)


_SOURCE_ROOT = Root(r"C:\m1-7-source", "m1-7-source")


_TARGET_ROOT = Root(r"D:\m1-7-target", "m1-7-target")


_GENERATED_TOP_LEVEL_DIRECTORIES = 19_934


_DEPENDENCY_CHAIN_EDGES = FIXTURE_DEPTH


_RAW_WITNESS_INDEXES = tuple(range(1, 15))


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


_DESTRUCTIVE_OPERATION_KINDS = frozenset(
    {
        OperationKind.UPDATE,
        OperationKind.MOVE_UPDATE,
        OperationKind.TRASH,
        OperationKind.DELETE,
    }
)


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    )


def canonical_json_bytes(value: object) -> bytes:
    """Encode one observation in stable JSON form."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def build_plan_fixture(*, information_heavy: bool) -> PlanArtifact:
    """Build the exact 120k/240k actual plan fixture."""

    operations = tuple(_fixture_operation(index) for index in range(FIXTURE_OPERATIONS))
    placeholder = Plan(
        source_root=_SOURCE_ROOT,
        target_root=_TARGET_ROOT,
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=_PROFILE,
        target_profile=_PROFILE,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    plan = replace(placeholder, fingerprint=plan_fingerprint(placeholder))
    warnings = (
        tuple(_warning(index) for index in range(FIXTURE_WARNINGS))
        if information_heavy
        else ()
    )
    source_scan = ScanResult(
        _SOURCE_ROOT, None, None, _PROFILE, (), (), (), warnings, ScanScope.full(), True
    )
    target_scan = ScanResult(
        _TARGET_ROOT, None, None, _PROFILE, (), (), (), (), ScanScope.full(), True
    )
    request = PlanRequest("f" * 32, _SOURCE_ROOT.path, _TARGET_ROOT.path)
    observed = ObservedWorld(
        {}, {}, frozenset(), {}, 0, 0, None,
        datetime(2026, 9, 14, tzinfo=timezone.utc),
    )
    return PlanArtifact(request, source_scan, target_scan, plan, Verdict(True, (), observed))


def build_diagnostic_plan_fixture() -> PlanArtifact:
    """Build a tiny actual artifact for runner-wiring tests, never acceptance."""

    operations = tuple(_diagnostic_operation(index) for index in range(12))
    placeholder = Plan(
        source_root=_SOURCE_ROOT,
        target_root=_TARGET_ROOT,
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=_PROFILE,
        target_profile=_PROFILE,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    plan = replace(placeholder, fingerprint=plan_fingerprint(placeholder))
    source_scan = ScanResult(
        _SOURCE_ROOT, None, None, _PROFILE, (), (), (), (), ScanScope.full(), True
    )
    target_scan = replace(source_scan, root=_TARGET_ROOT)
    request = PlanRequest("e" * 32, _SOURCE_ROOT.path, _TARGET_ROOT.path)
    observed = ObservedWorld(
        {}, {}, frozenset(), {}, 0, 0, None,
        datetime(2026, 9, 14, tzinfo=timezone.utc),
    )
    return PlanArtifact(request, source_scan, target_scan, plan, Verdict(True, (), observed))


def build_fixture_manifest(*, information_heavy: bool) -> dict[str, object]:
    """Derive a compact manifest from the realized artifact and projection."""

    artifact = build_plan_fixture(information_heavy=information_heavy)
    projection = build_plan_projection(artifact.request.request_id, artifact)
    return fixture_manifest(artifact, projection)


def fixture_manifest(
    artifact: PlanArtifact,
    projection: PlanProjection,
) -> dict[str, object]:
    """Describe actual fixture populations and correctness witnesses."""

    operations = artifact.plan.operations
    warnings = artifact.source_scan.warnings + artifact.target_scan.warnings
    operation_rows = sum(node.operation_id is not None for node in projection.nodes)
    notice_rows = sum(node.row_kind == "notice" for node in projection.nodes)
    prior_rows = sum(node.row_kind.startswith("prior-") for node in projection.nodes)
    warning_occurrences = Counter((item.code.value, item.rel_path) for item in warnings)
    kind_counts = Counter(item.kind.value for item in operations)
    code_counts = Counter(item.code.value for item in warnings)
    direct_children = Counter(node.parent_index for node in projection.nodes[1:])
    dependency_depths: dict[str, int] = {}
    for operation in operations:
        dependency_depths[str(operation.op_id)] = 0 if not operation.dependencies else (
            1 + max(dependency_depths[str(item)] for item in operation.dependencies)
        )
    directory_child_counts = _generated_directory_child_counts(projection)
    return {
        "schema": FIXTURE_SCHEMA,
        "case": "information-heavy" if warnings else "base",
        "seed": FIXTURE_SEED,
        "artifact_digest": _artifact_digest(artifact),
        "plan_fingerprint": str(artifact.plan.fingerprint),
        "counts": {
            "operations": len(operations),
            "operation_rows": operation_rows,
            "prior_rows": prior_rows,
            "structural_group_ghost_rows": len(projection.nodes) - operation_rows - notice_rows,
            "warnings": len(warnings),
            "unique_warning_occurrences": len(warning_occurrences),
            "repeated_warning_occurrences": sum(value - 1 for value in warning_occurrences.values()),
            "projection_rows": len(projection.nodes),
        },
        "depth": {
            "path": max(node.depth for node in projection.nodes),
            "dependency": max(dependency_depths.values()),
        },
        "siblings": {
            "widest": max(direct_children.values()),
            "generated_directory_child_min": min(directory_child_counts),
            "generated_directory_child_max": max(directory_child_counts),
        },
        "operation_kind_counts": dict(sorted(kind_counts.items())),
        "selection_facts": _fixture_selection_facts(artifact),
        "warning_code_counts": dict(sorted(code_counts.items())),
        "warning_cycle": [item.value for item in ScanWarningCode],
        "raw_key_witnesses": _raw_key_witnesses(projection),
    }


def make_plan_review_state(artifact: PlanArtifact) -> PlanReviewState:
    """Construct the actual server-side view from one already-built artifact."""

    projection = build_plan_projection(artifact.request.request_id, artifact)
    selection = derive_execution_selection(artifact.plan)
    return PlanReviewState(
        task_id="task-" + "1" * 32,
        request_id=artifact.request.request_id,
        projection=projection,
        selection_revision=0,
        selection_state="reviewing",
        source_path=artifact.plan.source_root.path,
        target_path=artifact.plan.target_root.path,
        requires_destructive_confirmation=(
            selection.requires_destructive_confirmation
        ),
        irreversible_update_count=selection.irreversible_update_count,
        destructive_operation_count=selection.destructive_operation_count,
        irreversible_operation_count=selection.irreversible_operation_count,
        destructive_operation_counts=_selection_count_mapping(selection),
        required_bytes=selection.required_bytes,
    )


def component_window(
    artifact: PlanArtifact,
    *,
    column: PlanSortColumn = PlanSortColumn.PATH,
    direction: SortDirection = SortDirection.ASCENDING,
    parameters: VisibleSequenceParameters = VisibleSequenceParameters(),
) -> tuple[PlanProjectionOrder, object]:
    """Exercise projection, sibling order, visible sequence and 256-row window."""

    projection = build_plan_projection(artifact.request.request_id, artifact)
    order = sort_plan_projection(projection, column, direction)
    sequence = derive_visible_sequence(
        projection.nodes,
        parameters,
        ordered_source_positions=order.ordered_source_positions,
    )
    return order, window_visible_sequence(
        sequence, offset=0, limit=FIXTURE_WINDOW_LIMIT
    )


def freeze_execution_scope(artifact: PlanArtifact) -> tuple[int, str]:
    """Exercise the real selection normalization and commitment-digest seams."""

    decision = derive_execution_selection(artifact.plan)
    return len(decision.selection), execution_selection_digest_hex(decision)


def depth_32_selection_preview(artifact: PlanArtifact) -> tuple[int, int]:
    """Exercise dependency closure through the fixture's depth-32 chain."""

    decision = derive_execution_selection(
        artifact.plan,
        user_deselected=frozenset({artifact.plan.operations[0].op_id}),
    )
    return len(decision.selection), len(decision.exclusions)


def _fixture_operation(index: int) -> PlanOperation:
    target = _fixture_target(index)
    kind = _fixture_kind(index)
    stat = FileStat(
        EntryKind.DIRECTORY if kind is OperationKind.MKDIR else EntryKind.FILE,
        0 if kind is OperationKind.MKDIR else _fixture_size(index),
        _fixture_mtime(index), None, 1, _META,
    )
    dependencies = (
        (OpId(f"{index - 1:032x}"),)
        if 1 <= index <= _DEPENDENCY_CHAIN_EDGES
        else ()
    )
    prior = _deep_path("prior", "old.bin", directory_count=30) if index == 0 else None
    return PlanOperation(
        op_id=OpId(f"{index:032x}"),
        kind=kind,
        source_rel_path=None if kind in {OperationKind.DELETE, OperationKind.TRASH} else target,
        target_rel_path=target,
        source_expected=None if kind in {OperationKind.DELETE, OperationKind.TRASH} else stat,
        target_expected=stat if kind in {OperationKind.DELETE, OperationKind.TRASH} else None,
        intended=None,
        prior_target_rel_path=prior,
        prior_target_expected=stat if prior is not None else None,
        content_bytes=0 if stat.kind is EntryKind.DIRECTORY else stat.size,
        dependencies=dependencies,
    )


def _diagnostic_operation(index: int) -> PlanOperation:
    stat = FileStat(EntryKind.FILE, index + 1, index + 1, None, 1, _META)
    target = f"d{index % 3}\\f{index:02d}.bin"
    return PlanOperation(
        OpId(f"{index:032x}"), OperationKind.COPY, target, target,
        stat, None, None, content_bytes=stat.size,
        dependencies=(OpId(f"{index - 1:032x}"),) if 1 <= index <= 4 else (),
    )


def _fixture_target(index: int) -> str:
    if index == 0:
        return _deep_path("target", "move.bin")
    witness_names = (
        "file2", "file10", "0", "9", "10", "100", "Straße", "STRASSE",
        "\u202ehostile", "own-directory", "size-maximum", "size-2pow53",
        "size-2pow53-plus-1", "mtime-ns", "structural\\child.bin",
    )
    if index <= len(witness_names):
        return "witness\\" + witness_names[index - 1]
    directory = (index - len(witness_names) - 1) % _GENERATED_TOP_LEVEL_DIRECTORIES
    return f"d{directory:05d}\\f{index:06d}.bin"


def _deep_path(prefix: str, leaf: str, *, directory_count: int = 31) -> str:
    return "\\".join(
        (*tuple(f"{prefix}{level:02d}" for level in range(directory_count)), leaf)
    )


def _fixture_kind(index: int) -> OperationKind:
    if index == 0:
        return OperationKind.MOVE
    if index == 10:
        return OperationKind.MKDIR
    cycle = (
        OperationKind.COPY, OperationKind.UPDATE, OperationKind.RECASE,
        OperationKind.TRASH, OperationKind.DELETE, OperationKind.NOOP,
    )
    return cycle[(index - 1) % len(cycle)]


def _fixture_size(index: int) -> int:
    explicit = {
        0: 41, 1: 43, 2: 47, 3: 0, 4: 9, 5: 10, 6: 100,
        7: 53, 8: 53, 10: 61, 11: 2**63 - 1, 12: 2**53,
        13: 2**53 + 1, 14: 67, 15: 71,
    }
    return explicit.get(index, index % 65_537 + 1)


def _fixture_mtime(index: int) -> int:
    if index in {14, 15}:
        return 1_000_000_000 + index - 14
    return 2_000_000_000 + index


def _warning(index: int) -> ScanWarning:
    codes = tuple(ScanWarningCode)
    occurrence = index % FIXTURE_OPERATIONS
    path_index = (occurrence * 65_537 + FIXTURE_SEED) % FIXTURE_OPERATIONS
    return ScanWarning(
        codes[(occurrence + FIXTURE_SEED) % len(codes)],
        f"notice\\n{path_index:06d}.txt",
    )


def _artifact_digest(artifact: PlanArtifact) -> str:
    digest = hashlib.sha256()
    _digest_values(
        digest,
        (
            artifact.request.request_id,
            artifact.plan.source_root.path,
            artifact.plan.target_root.path,
            str(artifact.plan.fingerprint),
        ),
    )
    for operation in artifact.plan.operations:
        stat = operation.intended or operation.source_expected or operation.target_expected
        _digest_values(
            digest,
            (
                str(operation.op_id), operation.kind.value,
                operation.source_rel_path, operation.target_rel_path,
                operation.prior_target_rel_path,
                None if stat is None else stat.kind.value,
                None if stat is None else stat.size,
                None if stat is None else stat.mtime_ns,
                tuple(str(item) for item in operation.dependencies),
            ),
        )
    for warning in (*artifact.source_scan.warnings, *artifact.target_scan.warnings):
        _digest_values(digest, (warning.code.value, warning.rel_path, warning.detail))
    return digest.hexdigest()


def _fixture_selection_facts(artifact: PlanArtifact) -> dict[str, object]:
    operations = artifact.plan.operations
    destructive_ids = frozenset(
        operation.op_id
        for operation in operations
        if operation.kind in _DESTRUCTIVE_OPERATION_KINDS
    )
    nondestructive = derive_execution_selection(
        artifact.plan,
        user_deselected=destructive_ids,
    )
    selected_ids = nondestructive.selection
    selected_operations = tuple(
        operation for operation in operations if operation.op_id in selected_ids
    )

    def required_bytes(population: Iterable[PlanOperation]) -> int:
        # This fixed fixture supports hardlinks, so the production calculation's
        # displaced-update allowance is zero. Sum the named byte-bearing kinds
        # independently for the authority witness.
        return sum(
            operation.content_bytes
            for operation in population
            if operation.kind in {
                OperationKind.COPY,
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
            }
        )

    def facts(population: tuple[PlanOperation, ...]) -> dict[str, object]:
        counts = {
            kind.value: sum(operation.kind is kind for operation in population)
            for kind in (
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
                OperationKind.TRASH,
                OperationKind.DELETE,
            )
        }
        irreversible_updates = 0 if artifact.plan.trash_on_update else counts["update"]
        return {
            "destructive_operation_count": sum(counts.values()),
            "destructive_operation_counts": counts,
            "irreversible_operation_count": counts["delete"] + irreversible_updates,
            "irreversible_update_count": irreversible_updates,
            "required_bytes": str(required_bytes(population)),
            "selected_operations": len(population),
        }

    return {
        "destructive": facts(operations),
        "nondestructive": {
            **facts(selected_operations),
            "user_deselected": len(destructive_ids),
        },
    }


def _selection_count_mapping(selection: object) -> dict[str, int]:
    counts = selection.destructive_operation_counts
    return {
        "update": counts.update,
        "move_update": counts.move_update,
        "trash": counts.trash,
        "delete": counts.delete,
    }


def _digest_values(digest: object, values: Iterable[object]) -> None:
    for value in values:
        encoded = canonical_json_bytes(value)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)


def _generated_directory_child_counts(projection: PlanProjection) -> tuple[int, ...]:
    counts = Counter(node.parent_index for node in projection.nodes[1:])
    values = tuple(
        counts[node.position]
        for node in projection.nodes
        if node.depth == 1 and node.display.startswith("d") and node.display[1:].isdigit()
    )
    if len(values) != _GENERATED_TOP_LEVEL_DIRECTORIES:
        raise AssertionError("generated directory population drifted")
    return values


def _raw_key_witnesses(projection: PlanProjection) -> dict[str, object]:
    wanted = {f"{index:032x}" for index in _RAW_WITNESS_INDEXES}
    witness = next(
        node
        for node in projection.nodes
        if node.rel_path_key == "WITNESS" and node.row_kind == "folder"
    )
    nodes = tuple(
        node
        for node in projection.nodes
        if node.parent_index == witness.position
        and (node.operation_id in wanted or node.rel_path_key == "WITNESS\\STRUCTURAL")
    )
    expected: dict[str, list[str]] = {}
    for column in (PlanSortColumn.FILENAME, PlanSortColumn.SIZE, PlanSortColumn.MTIME):
        for direction in (SortDirection.ASCENDING, SortDirection.DESCENDING):
            ordered = _independent_witness_order(nodes, column, direction)
            expected[f"{column.value}-{direction.value}"] = [
                _witness_identity(node) for node in ordered
            ]
    operation_values = {}
    for index in (0, 5, 6, 10, 15):
        operation_id = f"{index:032x}"
        node = projection.node_for_id(projection.operation_node_id_by_id[operation_id])
        operation_values[operation_id] = {
            "kind": node.operation_kind,
            "display": node.display,
            "size": node.size,
            "mtime_ns": node.mtime_ns,
        }
    return {
        "rows": [
            {
                "operation_id": node.operation_id,
                "node_id": node.node_id,
                "display": node.display,
                "rel_path_key": node.rel_path_key,
                "size": node.size,
                "mtime_ns": node.mtime_ns,
            }
            for node in nodes
        ],
        "canonical_ids": [_witness_identity(node) for node in nodes],
        "expected_orders": expected,
        "operation_value_cases": operation_values,
    }


def _independent_witness_order(
    nodes: tuple[PlanProjectionNode, ...],
    column: PlanSortColumn,
    direction: SortDirection,
) -> tuple[PlanProjectionNode, ...]:
    canonical = {_witness_identity(node): ordinal for ordinal, node in enumerate(nodes)}

    def primary(node: PlanProjectionNode) -> object:
        if column is PlanSortColumn.FILENAME:
            return node.display.casefold()
        if column is PlanSortColumn.SIZE:
            return node.size
        return node.mtime_ns

    if column is not PlanSortColumn.SIZE:
        groups = {0: list(nodes), 1: [], 2: []}
    else:
        groups = {0: [], 1: [], 2: [], 3: []}
        for node in nodes:
            directory = bool(getattr(node, "is_directory", False)) or node.row_kind == "folder"
            if directory:
                groups[2 if primary(node) is not None else 3].append(node)
            else:
                groups[0 if primary(node) is not None else 1].append(node)
    ordered: list[PlanProjectionNode] = []
    for bucket in range(len(groups)):
        values = groups[bucket]
        available = [node for node in values if primary(node) is not None]
        unavailable = [node for node in values if primary(node) is None]
        available.sort(key=lambda node: primary(node), reverse=direction is SortDirection.DESCENDING)
        start = 0
        while start < len(available):
            end = start + 1
            while end < len(available) and primary(available[end]) == primary(available[start]):
                end += 1
            available[start:end] = sorted(
                available[start:end], key=lambda node: canonical[_witness_identity(node)]
            )
            start = end
        unavailable.sort(key=lambda node: canonical[_witness_identity(node)])
        ordered.extend((*available, *unavailable))
    return tuple(ordered)


def _witness_identity(node: PlanProjectionNode) -> str:
    return node.operation_id or node.node_id


def run_component_child(
    metric_id: str,
    launch_token: str,
    *,
    contract_path: Path = CONTRACT_PATH,
    installed_root: Path | None = None,
) -> dict[str, object]:
    """Run one fixed component case and return its genuine child receipt."""

    if installed_root is not None:
        _require_installed_runtime(installed_root)
    contract = json.loads(contract_path.read_bytes())
    metrics = {
        item["id"]: item
        for item in contract["metrics"]
        if item["surface"] == "component"
    }
    try:
        metric = metrics[metric_id]
    except KeyError as error:
        raise ValueError("component metric is not in the fixed contract") from error
    if not _is_hex_identifier(launch_token):
        raise ValueError("launch token must be 32 lowercase hexadecimal characters")

    samples = _measure_component_metric(metric)
    expected_count = contract["sampling"][metric["sample_kind"]]["samples_per_child"]
    if len(samples) != expected_count:
        raise AssertionError("component sample population drifted")
    if any(sample["correctness"] != _current_correctness(metric) for sample in samples):
        raise AssertionError("component result did not satisfy its fixed correctness receipt")
    return {
        "child_id": uuid4().hex,
        "fixture_case": metric["fixture_case"],
        "headed_fixture": None,
        "headed_runtime": None,
        "launch_token": launch_token,
        "metric_id": metric_id,
        "process_identity": _current_process_identity(),
        "sample_kind": metric["sample_kind"],
        "samples": samples,
        "schema": CHILD_RECEIPT_SCHEMA,
    }


def _current_correctness(metric: Mapping[str, object]) -> object:
    expected = metric["correctness"]
    metric_id = metric["id"]
    if metric_id not in {
        "projection_unchanged_window",
        "projection_changed_search_window",
        "projection_changed_collapse_window",
        "projection_incremental_retained_memory_staging_overlap",
    }:
        return expected
    adjusted = deepcopy(expected)
    if metric_id == "projection_unchanged_window":
        if adjusted["total"] != 240_000:
            raise ValueError("historical unchanged-window fixture changed")
        adjusted["total"] = 239_999
        return adjusted
    if metric_id == "projection_changed_search_window":
        if adjusted["returned_rows"] != 3:
            raise ValueError("historical search fixture changed")
        adjusted["returned_rows"] = 2
        return adjusted
    if metric_id == "projection_changed_collapse_window":
        if adjusted["returned_rows"] != 1:
            raise ValueError("historical collapse fixture changed")
        adjusted["returned_rows"] = FIXTURE_WINDOW_LIMIT
        return adjusted
    for case in ("base", "staged"):
        view = adjusted[case]
        if view["window_total"] != view["projection_rows"]:
            raise ValueError("historical memory fixture changed unexpectedly")
        view["window_total"] = view["projection_rows"] - 1
    return adjusted


def run_diagnostic_child(launch_token: str) -> dict[str, object]:
    """Exercise child identity and timing wiring without an acceptance fixture."""

    if not _is_hex_identifier(launch_token):
        raise ValueError("launch token must be 32 lowercase hexadecimal characters")
    artifact = build_diagnostic_plan_fixture()
    started = time.perf_counter_ns()
    projection = build_plan_projection(artifact.request.request_id, artifact)
    elapsed = time.perf_counter_ns() - started
    correctness = {
        "operations": len(artifact.plan.operations),
        "projection_rows": len(projection.nodes),
    }
    return {
        "child_id": uuid4().hex,
        "fixture_case": "diagnostic",
        "headed_fixture": None,
        "headed_runtime": None,
        "launch_token": launch_token,
        "metric_id": "diagnostic_component_projection",
        "process_identity": _current_process_identity(),
        "sample_kind": "diagnostic",
        "samples": [{
            "correctness": correctness,
            "elapsed_ns": elapsed,
            "iteration": 1,
            "retained_bytes": None,
        }],
        "schema": CHILD_RECEIPT_SCHEMA,
    }


def _measure_component_metric(metric: Mapping[str, object]) -> list[dict[str, object]]:
    metric_id = str(metric["id"])
    information_heavy = metric["fixture_case"] == "information-heavy"

    if metric_id == "projection_incremental_retained_memory_staging_overlap":
        correctness, retained_bytes = _measure_projection_memory()
        return [_sample(1, correctness, retained_bytes=retained_bytes)]

    artifact = build_plan_fixture(information_heavy=information_heavy)
    _assert_fixture_input(artifact, information_heavy=information_heavy)
    if metric_id.startswith("projection_cold_"):
        started = time.perf_counter_ns()
        projection = build_plan_projection(artifact.request.request_id, artifact)
        elapsed = time.perf_counter_ns() - started
        correctness = _cold_projection_correctness(
            artifact, projection, information_heavy=information_heavy
        )
        return [_sample(1, correctness, elapsed_ns=elapsed)]

    transition_factory = _component_transition_factory(metric_id, artifact)
    transition_factory()()  # exactly one untimed equivalent transition
    samples: list[dict[str, object]] = []
    for iteration in range(1, 7):
        transition = transition_factory()
        started = time.perf_counter_ns()
        correctness = transition()
        elapsed = time.perf_counter_ns() - started
        samples.append(_sample(iteration, correctness, elapsed_ns=elapsed))
    return samples


def _component_transition_factory(
    metric_id: str,
    artifact: PlanArtifact,
    *,
    projection: PlanProjection | None = None,
) -> Callable[[], Callable[[], dict[str, object]]]:
    if metric_id == "selection_freeze_normalize_100000":
        def factory() -> Callable[[], dict[str, object]]:
            def transition() -> dict[str, object]:
                count, digest = freeze_execution_scope(artifact)
                return {
                    "selected_operations": count,
                    "selection_digest_hex_length": len(digest),
                }
            return transition
        return factory
    if metric_id == "selection_preview_depth_32":
        def factory() -> Callable[[], dict[str, object]]:
            def transition() -> dict[str, object]:
                selected, excluded = depth_32_selection_preview(artifact)
                return {
                    "dependency_depth": _dependency_depth(artifact),
                    "selected_operations": selected,
                    "excluded_operations": excluded,
                }
            return transition
        return factory

    if projection is None:
        projection = build_plan_projection(artifact.request.request_id, artifact)
    if metric_id == "projection_unchanged_window":
        state = _state_from_projection(artifact, projection)

        def factory() -> Callable[[], dict[str, object]]:
            return lambda: _unchanged_window_receipt(state, total=True)
        return factory
    if metric_id.startswith("projection_unchanged_after_sort_"):
        column, direction = _sort_from_metric(metric_id, "projection_unchanged_after_sort_")
        state = _state_from_projection(artifact, projection)
        _apply_view(state, column=column, direction=direction)

        def factory() -> Callable[[], dict[str, object]]:
            return lambda: _unchanged_sorted_window_receipt(state, column, direction)
        return factory
    if metric_id.startswith("projection_changed_sort_"):
        column, direction = _sort_from_metric(
            metric_id, "projection_changed_sort_", suffix="_window"
        )

        def factory() -> Callable[[], dict[str, object]]:
            state = _state_from_projection(artifact, projection)
            return lambda: _changed_sort_receipt(state, column, direction)
        return factory
    if metric_id == "projection_changed_search_window":
        def factory() -> Callable[[], dict[str, object]]:
            state = _state_from_projection(artifact, projection)
            return lambda: _changed_search_receipt(state)
        return factory
    if metric_id == "projection_changed_filter_window":
        def factory() -> Callable[[], dict[str, object]]:
            state = _state_from_projection(artifact, projection)
            return lambda: _changed_filter_receipt(state)
        return factory
    if metric_id == "projection_changed_collapse_window":
        def factory() -> Callable[[], dict[str, object]]:
            state = _state_from_projection(artifact, projection)
            visible_index, source_position = next(
                (index, position)
                for index, position in enumerate(state.current_sequence.visible_positions)
                if position != 0 and projection.nodes[position].is_container
            )
            folder_node_id = projection.nodes[source_position].node_id
            return lambda: _changed_collapse_receipt(
                state, folder_node_id, visible_index - 1,
            )
        return factory
    if metric_id == "projection_changed_reset_window":
        def factory() -> Callable[[], dict[str, object]]:
            state = _state_from_projection(artifact, projection)
            _apply_view(
                state,
                column=PlanSortColumn.FILENAME,
                direction=SortDirection.DESCENDING,
            )
            return lambda: _changed_reset_receipt(state)
        return factory
    raise ValueError("component metric has no transition implementation")


def _state_from_projection(
    artifact: PlanArtifact,
    projection: PlanProjection,
) -> PlanReviewState:
    selection = derive_execution_selection(artifact.plan)
    return PlanReviewState(
        task_id="task-" + "1" * 32,
        request_id=artifact.request.request_id,
        projection=projection,
        selection_revision=0,
        selection_state="reviewing",
        source_path=artifact.plan.source_root.path,
        target_path=artifact.plan.target_root.path,
        requires_destructive_confirmation=(
            selection.requires_destructive_confirmation
        ),
        irreversible_update_count=selection.irreversible_update_count,
        destructive_operation_count=selection.destructive_operation_count,
        irreversible_operation_count=selection.irreversible_operation_count,
        destructive_operation_counts=_selection_count_mapping(selection),
        required_bytes=selection.required_bytes,
    )


def _apply_view(
    state: PlanReviewState,
    *,
    search_query: str = "",
    filters: frozenset[str] = frozenset(),
    column: PlanSortColumn = PlanSortColumn.PATH,
    direction: SortDirection = SortDirection.ASCENDING,
    collapse_node_id: str | None = None,
    collapsed: bool | None = None,
) -> dict[str, object]:
    return state.update(
        expected_revision=state.view_revision,
        search_query=search_query,
        filters=filters,
        sort_column=column,
        sort_direction=direction,
        collapse_node_id=collapse_node_id,
        collapsed=collapsed,
    )


def _window(state: PlanReviewState, *, offset: int = 0) -> dict[str, object]:
    return state.window(
        expected_revision=state.view_revision,
        offset=offset,
        limit=FIXTURE_WINDOW_LIMIT,
    )


def _unchanged_window_receipt(
    state: PlanReviewState,
    *,
    total: bool,
) -> dict[str, object]:
    result = _window(state)
    receipt = {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "returned_rows": len(result["rows"]),
    }
    if total:
        receipt["total"] = result["total"]
    return receipt


def _unchanged_sorted_window_receipt(
    state: PlanReviewState,
    column: PlanSortColumn,
    direction: SortDirection,
) -> dict[str, object]:
    receipt = _unchanged_window_receipt(state, total=False)
    receipt["sort"] = f"{column.value}-{direction.value}"
    return receipt


def _changed_search_receipt(state: PlanReviewState) -> dict[str, object]:
    summary = _apply_view(state, search_query="\u202ehostile")
    result = _window(state)
    return {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "search_query": summary["search_query"],
        "returned_rows": len(result["rows"]),
    }


def _changed_filter_receipt(state: PlanReviewState) -> dict[str, object]:
    summary = _apply_view(state, filters=frozenset({"notice"}))
    result = _window(state)
    return {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "filters": summary["filters"],
        "returned_rows": len(result["rows"]),
    }


def _changed_collapse_receipt(
    state: PlanReviewState,
    folder_node_id: str,
    folder_offset: int,
) -> dict[str, object]:
    summary = _apply_view(state, collapse_node_id=folder_node_id, collapsed=True)
    result = _window(state, offset=folder_offset)
    if not result["rows"] or result["rows"][0]["node_id"] != folder_node_id:
        raise AssertionError("collapsed public folder disappeared from its window")
    return {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "collapsed_count": summary["collapsed_count"],
        "returned_rows": len(result["rows"]),
    }


def _changed_reset_receipt(state: PlanReviewState) -> dict[str, object]:
    summary = _apply_view(state)
    result = _window(state)
    return {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "sort": f"{summary['sort_column']}-{summary['sort_direction']}",
        "returned_rows": len(result["rows"]),
    }


def _changed_sort_receipt(
    state: PlanReviewState,
    column: PlanSortColumn,
    direction: SortDirection,
) -> dict[str, object]:
    summary = _apply_view(state, column=column, direction=direction)
    result = _window(state)
    return {
        "disposition": result["disposition"],
        "view_revision": result["view_revision"],
        "requested_limit": FIXTURE_WINDOW_LIMIT,
        "sort": f"{summary['sort_column']}-{summary['sort_direction']}",
        "returned_rows": len(result["rows"]),
    }


def _sort_from_metric(
    metric_id: str,
    prefix: str,
    *,
    suffix: str = "",
) -> tuple[PlanSortColumn, SortDirection]:
    value = metric_id.removeprefix(prefix)
    if suffix:
        value = value.removesuffix(suffix)
    column_value, direction_value = value.rsplit("_", 1)
    return PlanSortColumn(column_value), SortDirection(direction_value)


def _assert_fixture_input(
    artifact: PlanArtifact,
    *,
    information_heavy: bool,
) -> None:
    warnings = artifact.source_scan.warnings + artifact.target_scan.warnings
    if len(artifact.plan.operations) != FIXTURE_OPERATIONS:
        raise AssertionError("fixture operation population drifted")
    if len(warnings) != (FIXTURE_WARNINGS if information_heavy else 0):
        raise AssertionError("fixture warning population drifted")
    if _dependency_depth(artifact) != FIXTURE_DEPTH:
        raise AssertionError("fixture dependency depth drifted")


def _dependency_depth(artifact: PlanArtifact) -> int:
    depths: dict[str, int] = {}
    for operation in artifact.plan.operations:
        depths[str(operation.op_id)] = 0 if not operation.dependencies else (
            1 + max(depths[str(item)] for item in operation.dependencies)
        )
    return max(depths.values())


def _cold_projection_correctness(
    artifact: PlanArtifact,
    projection: PlanProjection,
    *,
    information_heavy: bool,
) -> dict[str, object]:
    if information_heavy:
        return {
            "projection_rows": len(projection.nodes),
            "operations": len(artifact.plan.operations),
            "warnings": len(artifact.source_scan.warnings + artifact.target_scan.warnings),
        }
    return {
        "projection_rows": len(projection.nodes),
        "operations": len(artifact.plan.operations),
        "path_depth": max(node.depth for node in projection.nodes),
        "dependency_depth": _dependency_depth(artifact),
    }


def _measure_projection_memory() -> tuple[dict[str, object], int]:
    base_artifact = build_plan_fixture(information_heavy=False)
    heavy_artifact = build_plan_fixture(information_heavy=True)
    _assert_fixture_input(base_artifact, information_heavy=False)
    _assert_fixture_input(heavy_artifact, information_heavy=True)
    gc.collect()
    baseline = _current_private_bytes()
    samples = [baseline]
    ready = threading.Event()
    stop = threading.Event()

    def sample() -> None:
        samples.append(_current_private_bytes())
        ready.set()
        while not stop.wait(0.002):
            samples.append(_current_private_bytes())

    sampler = threading.Thread(target=sample, name="m1-7-private-bytes", daemon=True)
    sampler.start()
    if not ready.wait(5.0):
        raise RuntimeError("private-byte sampler did not start")
    try:
        base_state = make_plan_review_state(base_artifact)
        _apply_view(
            base_state,
            column=PlanSortColumn.FILENAME,
            direction=SortDirection.DESCENDING,
        )
        base_window = _window(base_state)
        staged_state = make_plan_review_state(heavy_artifact)
        _apply_view(
            staged_state,
            column=PlanSortColumn.FILENAME,
            direction=SortDirection.DESCENDING,
        )
        staged_window = _window(staged_state)
        correctness = _memory_correctness(
            base_state,
            base_window,
            staged_state,
            staged_window,
        )
        samples.append(_current_private_bytes())
    finally:
        stop.set()
        sampler.join(5.0)
    if sampler.is_alive():
        raise RuntimeError("private-byte sampler did not stop")
    return correctness, max(samples) - baseline


def _memory_correctness(
    base_state: PlanReviewState,
    base_window: Mapping[str, object],
    staged_state: PlanReviewState,
    staged_window: Mapping[str, object],
) -> dict[str, object]:
    def facts(state: PlanReviewState, window: Mapping[str, object]) -> dict[str, object]:
        canonical = state.canonical_order
        current = state.current_order
        sequence = state.current_sequence
        projection = canonical.projection
        return {
            "projection_rows": len(projection.nodes),
            "window_rows": len(window["rows"]),
            "window_total": window["total"],
            "window_revision": window["view_revision"],
            "state_revision": state.view_revision,
            "state_projection_identity": (
                state.projection is projection
                and current.projection is projection
                and sequence.nodes is projection.nodes
            ),
            "distinct_canonical_current_orders": canonical is not current,
            "canonical_order": _order_memory_facts(canonical),
            "current_order": _order_memory_facts(current),
            "visible_buffers": {
                "visible_source_positions": _buffer_memory_facts(sequence.visible_source_positions),
                "visible_index_by_source_position": _buffer_memory_facts(sequence.visible_index_by_source_position),
                "sibling_ordinals": _buffer_memory_facts(sequence.sibling_ordinals),
                "retained_direct_child_counts": _buffer_memory_facts(sequence.retained_direct_child_counts),
            },
        }

    base = facts(base_state, base_window)
    staged = facts(staged_state, staged_window)
    return {
        "base": base,
        "staged": staged,
        "simultaneously_retained": base_state is not staged_state,
        "distinct_projections": (
            base_state.canonical_order.projection
            is not staged_state.canonical_order.projection
        ),
        "no_cross_state_buffer_sharing": all(
            base is not staged
            for base, staged in (
                *(
                    (
                        getattr(base_state.current_sequence, name),
                        getattr(staged_state.current_sequence, name),
                    )
                    for name in (
                        "visible_source_positions",
                        "visible_index_by_source_position",
                        "sibling_ordinals",
                        "retained_direct_child_counts",
                    )
                ),
                (
                    base_state.canonical_order.ordered_source_positions,
                    staged_state.canonical_order.ordered_source_positions,
                ),
                (
                    base_state.canonical_order.order_rank_by_source_position,
                    staged_state.canonical_order.order_rank_by_source_position,
                ),
                (
                    base_state.current_order.ordered_source_positions,
                    staged_state.current_order.ordered_source_positions,
                ),
                (
                    base_state.current_order.order_rank_by_source_position,
                    staged_state.current_order.order_rank_by_source_position,
                ),
            )
        ),
        "final_witness_accessed": all(
            type(value) is int
            for value in (
                base_state.current_order.ordered_source_positions[-1],
                staged_state.current_sequence.visible_source_positions[-1],
            )
        ),
    }


def _buffer_memory_facts(value: CompactUnsignedIntegers) -> dict[str, int]:
    return {
        "byte_length": value.byte_length,
        "byte_width": value.byte_width,
        "count": len(value),
    }


def _order_memory_facts(order: PlanProjectionOrder) -> dict[str, object]:
    return {
        "ordered": _buffer_memory_facts(order.ordered_source_positions),
        "inverse": _buffer_memory_facts(order.order_rank_by_source_position),
        "inverse_valid": all(
            order.order_rank_by_source_position[source_position] == rank
            for rank, source_position in enumerate(order.ordered_source_positions)
        ),
    }


def _current_private_bytes() -> int:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        ctypes.sizeof(counters),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PrivateUsage)


def _current_process_identity() -> dict[str, int]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    created = wintypes.FILETIME()
    exited = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    if not kernel32.GetProcessTimes(
        kernel32.GetCurrentProcess(),
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    creation = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    return {"pid": os.getpid(), "creation_filetime_100ns": creation}


def _process_image_path(process_id: int) -> str:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
    )
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        capacity = wintypes.DWORD(32_768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(capacity)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return str(Path(buffer.value).resolve())
    finally:
        kernel32.CloseHandle(handle)


def _sample(
    iteration: int,
    correctness: Mapping[str, object],
    *,
    elapsed_ns: int | None = None,
    retained_bytes: int | None = None,
) -> dict[str, object]:
    if (elapsed_ns is None) == (retained_bytes is None):
        raise ValueError("one and only one component measurement value is required")
    return {
        "correctness": dict(correctness),
        "elapsed_ns": elapsed_ns,
        "iteration": iteration,
        "retained_bytes": retained_bytes,
    }


def _is_hex_identifier(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_installed_runtime(installed_root: Path) -> None:
    """Bind an installed observation to the supplied package tree."""

    loaded = Path(importlib.import_module("namisync").__file__).resolve()
    expected = (installed_root / "namisync" / "__init__.py").resolve()
    records = tuple(installed_root.glob("namisync-*.dist-info/RECORD"))
    if len(records) != 1 or not expected.is_file() or loaded != expected:
        raise RuntimeError(
            "observation interpreter did not import NamiSync from the installed root"
        )


def _installed_runtime_identity(installed_root: Path) -> dict[str, str]:
    package = importlib.import_module("namisync")
    return {
        "root": str(installed_root.resolve()),
        "namisync_file": str(Path(package.__file__).resolve()),
        "namisync_version": importlib.metadata.version("namisync"),
    }


class _BlockingExecutionInvocation:
    def __init__(self, release: threading.Event, checkpoint: object) -> None:
        self._release = release
        self._checkpoint = checkpoint

    def run(self, context: object) -> object:
        from namisync.core.session import OperationResult, SessionState

        while not self._release.wait(0.005):
            context.checkpoint()
        context.checkpoint()
        return OperationResult(SessionState.COMPLETED)

    def snapshot(self) -> object:
        return self._checkpoint


def _expected_plan_root_node_id(request_id: str) -> str:
    digest = hashlib.blake2b(digest_size=16, person=b"NamiSyncNodeV1")
    for value in ("plan", request_id, ""):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"


class _HeadedFixtureController:
    def __init__(
        self,
        metric: Mapping[str, object],
        fixture_root: Path,
        published_plan_count: int,
    ) -> None:
        if (
            type(published_plan_count) is not int
            or not 1 <= published_plan_count <= 7
        ):
            raise ValueError("headed fixture publication count is invalid")
        self.metric = metric
        self.fixture_root = fixture_root
        self.published_plan_count = published_plan_count
        self.release = threading.Event()
        self.metadata: dict[str, object] | None = None
        self.published_fixture: dict[str, object] | None = None
        self._fixed: PlanArtifact | None = None
        self._registry: object | None = None

    def bind(self, registry: object) -> None:
        self._registry = registry
        self._fixed = build_plan_fixture(information_heavy=False)
        metric_id = str(self.metric["id"])
        count = self.published_plan_count
        review_rows = [self._create_review(registry) for _ in range(count)]
        summaries = {task.task_id: task for task in registry.list_tasks().tasks}
        published_rows = []
        for row in review_rows:
            summary = summaries[row["task_id"]]
            if (
                summary.task_kind != "sync-plan"
                or summary.request_id != row["request_id"]
                or summary.session_id != row["plan_session_id"]
                or summary.session_state != "completed"
                or summary.session_released is not True
            ):
                raise AssertionError("headed fixture plan was not published exactly")
            settlement = self._settle_initial_view(registry, row)
            published_rows.append({
                "execution_unused": True,
                "initial_view_settlement": settlement,
                "plan_session_id": row["plan_session_id"],
                "request_id": row["request_id"],
                "session_released": summary.session_released,
                "session_state": summary.session_state,
                "source_path": row["source_path"],
                "target_path": row["target_path"],
                "task_id": row["task_id"],
                "task_kind": summary.task_kind,
            })
        self.published_fixture = {
            "published_plan_count": count,
            "rows": published_rows,
        }
        self.metadata = {
            "metric_id": metric_id,
            "published_plan_count": count,
            "rows": review_rows,
        }

    @staticmethod
    def _settle_initial_view(
        registry: object,
        row: Mapping[str, object],
    ) -> dict[str, object]:
        summary = registry.open_plan_view(row["task_id"])
        window = registry.get_plan_window(
            row["task_id"],
            expected_revision=summary["view_revision"],
            offset=0,
            limit=256,
        )
        rows = window["rows"]
        first = rows[0] if rows else None
        if (
            summary["disposition"] != "opened"
            or summary["task_id"] != row["task_id"]
            or summary["request_id"] != row["request_id"]
            or summary["source_path"] != row["source_path"]
            or summary["target_path"] != row["target_path"]
            or summary["view_revision"] != 0
            or window["disposition"] != "current"
            or window["view_revision"] != 0
            or window["offset"] != 0
            or window["total"] != 120_000
            or len(rows) != 256
            or first is None
            or first["node_id"]
            != _expected_plan_root_node_id(row["request_id"])
            or first["operation_id"] is not None
            or first["visible_index"] != 0
        ):
            raise AssertionError("headed fixture initial view was not settled exactly")
        return {
            "first_row": {
                "node_id": first["node_id"],
                "operation_id": first["operation_id"],
                "visible_index": first["visible_index"],
            },
            "open_disposition": summary["disposition"],
            "plan_session_id": row["plan_session_id"],
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

    def command(self, payload: object) -> object:
        if type(payload) is not dict or self.metadata is None:
            raise ValueError("headed fixture metadata is unavailable")
        if self._registry is None:
            raise RuntimeError("headed fixture registry is unavailable")
        if payload != {}:
            raise ValueError("headed fixture command is invalid")
        summaries = {
            task.task_id: task
            for task in self._registry.list_tasks().tasks
        }
        return {
            **self.metadata,
            "rows": [
                {
                    **row,
                    "fresh_execution_unused": (
                        summaries[row["task_id"]].task_kind == "sync-plan"
                        and summaries[row["task_id"]].request_id
                        == row["request_id"]
                        and summaries[row["task_id"]].session_state
                        == "completed"
                        and summaries[row["task_id"]].session_id
                        == row["plan_session_id"]
                        and summaries[row["task_id"]].session_released is True
                    ),
                    "session_id": summaries[row["task_id"]].session_id,
                }
                for row in self.metadata["rows"]
            ],
        }

    def _create_review(self, registry: object) -> dict[str, object]:
        # A unique real root pair gives the headed probe an identity witness in
        # the rendered summary before every fresh-plan timing sample.
        review_root = self.fixture_root / uuid4().hex
        source = review_root / "source"
        target = review_root / "target"
        source.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        command_id = uuid4().hex
        start = registry.start_plan(
            str(source),
            str(target),
            deletion_policy=None,
            command_id=command_id,
            wire_intent=(str(source), str(target), None),
        )
        self._drain_and_release(registry, start)
        service = registry._lifecycle
        actual = service.get_plan(start.request_id)
        if self._fixed is None:
            raise RuntimeError("headed fixture was not built")
        fixed = _rebind_fixture(self._fixed, actual)
        service.save_plan(fixed)
        preview = service.preview_selection(start.request_id)
        if "nondestructive" in str(self.metric["id"]):
            destructive_ids = tuple(
                str(operation.op_id)
                for operation in fixed.plan.operations
                if operation.kind in _DESTRUCTIVE_OPERATION_KINDS
            )
            mutation = service.mutate_selection(
                start.request_id,
                preview.revision,
                deselect=destructive_ids,
                command_id=uuid4().hex,
            )
            if mutation.disposition != "applied":
                raise AssertionError("nondestructive headed selection was not applied")
            preview = mutation.preview
        selected_ids = frozenset(preview.selected_operation_ids)
        selected_operations = tuple(
            operation
            for operation in fixed.plan.operations
            if str(operation.op_id) in selected_ids
        )
        expected_destructive_counts = {
            kind.value: sum(
                operation.kind is kind for operation in selected_operations
            )
            for kind in (
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
                OperationKind.TRASH,
                OperationKind.DELETE,
            )
        }
        expected_destructive = sum(expected_destructive_counts.values())
        expected_irreversible_updates = (
            0 if fixed.plan.trash_on_update
            else expected_destructive_counts["update"]
        )
        expected_irreversible = (
            expected_destructive_counts["delete"]
            + expected_irreversible_updates
        )
        expected_required_bytes = sum(
            operation.content_bytes
            for operation in selected_operations
            if operation.kind in {
                OperationKind.COPY,
                OperationKind.UPDATE,
                OperationKind.MOVE_UPDATE,
            }
        )
        if (
            preview.destructive_operation_count != expected_destructive
            or dict(preview.destructive_operation_counts)
            != expected_destructive_counts
            or preview.irreversible_update_count != expected_irreversible_updates
            or preview.irreversible_operation_count != expected_irreversible
            or preview.required_bytes != str(expected_required_bytes)
            or preview.requires_destructive_confirmation
            is not bool(expected_destructive)
        ):
            raise AssertionError("headed selection facts are not authoritative")
        return {
            "destructive_operation_count": expected_destructive,
            "destructive_operation_counts": expected_destructive_counts,
            "irreversible_operation_count": expected_irreversible,
            "irreversible_update_count": expected_irreversible_updates,
            "plan_session_id": start.session_id,
            "task_id": start.task_id,
            "request_id": start.request_id,
            "required_bytes": str(expected_required_bytes),
            "selection_revision": preview.revision,
            "source_path": fixed.plan.source_root.path,
            "target_path": fixed.plan.target_root.path,
            "view_revision": 0,
        }

    @staticmethod
    def _drain_and_release(registry: object, start: object) -> None:
        deadline = time.monotonic() + 60.0
        terminal = False
        while not terminal:
            if time.monotonic() >= deadline:
                raise TimeoutError("headed fixture plan did not become terminal")
            drained = registry.drain(
                start.task_id,
                start.session_id,
                uuid4().hex,
                replay_from=None,
            )
            terminal = any(
                getattr(update, "update_type", None) == "record"
                and getattr(update.record, "state", None)
                in {"completed", "failed", "canceled", "refused"}
                for update in drained.updates
            )
        registry.release_terminal_session(start.task_id, start.session_id)


def _rebind_fixture(fixed: PlanArtifact, actual: PlanArtifact) -> PlanArtifact:
    plan = replace(
        fixed.plan,
        source_root=actual.plan.source_root,
        target_root=actual.plan.target_root,
        fingerprint=PlanFingerprint("0" * 64),
    )
    plan = replace(plan, fingerprint=plan_fingerprint(plan))
    return replace(
        fixed,
        request=actual.request,
        source_scan=replace(fixed.source_scan, root=actual.source_scan.root),
        target_scan=replace(fixed.target_scan, root=actual.target_scan.root),
        plan=plan,
    )


def _headed_test_spec(handler: Callable[[object], object]) -> object:
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandRetry,
        CommandSpec,
        CommandResponsePolicy,
        FieldRequirement,
    )

    return CommandSpec(
        validate_payload=lambda payload: payload,
        handler=handler,
        # Activation mutates only the test fixture's visible-task selection;
        # classify the combined metadata/activation command conservatively.
        access=CommandAccess.MUTATING,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        response_policy=CommandResponsePolicy.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _headed_runtime_identity(window: object) -> dict[str, object]:
    from System import Environment
    from System.Runtime.InteropServices import RuntimeEnvironment

    core = window.native.browser.webview.CoreWebView2
    browser_path = _process_image_path(int(core.BrowserProcessId))
    runtime_directory = Path(str(RuntimeEnvironment.GetRuntimeDirectory())).resolve()
    clr_module = (runtime_directory / "clr.dll").resolve()
    if not clr_module.is_file():
        raise RuntimeError("loaded netfx CLR module is unavailable")
    return {
        "browser": {
            "executable_path": browser_path,
            "version": str(core.Environment.BrowserVersionString),
        },
        "clr": {
            "module_path": str(clr_module),
            "runtime_directory": str(runtime_directory),
            "runtime_version": str(Environment.Version),
            "system_version": str(RuntimeEnvironment.GetSystemVersion()),
        },
    }


def run_headed_child(
    metric_id: str,
    launch_token: str,
    *,
    contract_path: Path,
    benchmark_root: Path | None,
    installed_root: Path | None,
) -> dict[str, object]:
    """Measure one installed production page/bridge/registry case."""

    if benchmark_root is None:
        raise ValueError("headed child requires its benchmark root")
    if installed_root is None:
        raise ValueError("headed child requires its installed root")
    benchmark_root = benchmark_root.resolve()
    _require_installed_runtime(installed_root)
    if not _is_hex_identifier(launch_token):
        raise ValueError("launch token must be 32 lowercase hexadecimal characters")
    contract = json.loads(contract_path.read_bytes())
    metrics = {
        item["id"]: item
        for item in contract["metrics"]
        if item["surface"] == "installed-headed"
    }
    try:
        metric = metrics[metric_id]
    except KeyError as error:
        raise ValueError("headed metric is not in the fixed contract") from error

    headed_spec = contract["headed_fixture"]
    published_plan_count = (
        headed_spec["fresh_execution_plan_count"][metric["sample_kind"]]
        if metric_id in headed_spec["fresh_execution_metric_ids"]
        else headed_spec["default_published_plan_count"]
    )
    samples, headed_runtime, headed_fixture = _run_headed_page(
        metric,
        benchmark_root,
        published_plan_count,
    )
    expected_sample_count = 1 if metric["sample_kind"] == "cold" else 6
    if len(samples) != expected_sample_count:
        raise AssertionError("headed result changed its fixed sample count")
    if any(sample["correctness"] != metric["correctness"] for sample in samples):
        raise AssertionError("headed result did not satisfy fixed correctness")
    return {
        "child_id": uuid4().hex,
        "fixture_case": metric["fixture_case"],
        "headed_fixture": headed_fixture,
        "headed_runtime": headed_runtime,
        "installed_runtime": _installed_runtime_identity(installed_root),
        "launch_token": launch_token,
        "metric_id": metric_id,
        "process_identity": _current_process_identity(),
        "sample_kind": metric["sample_kind"],
        "samples": samples,
        "schema": CHILD_RECEIPT_SCHEMA,
    }


def _run_headed_page(
    metric: Mapping[str, object],
    benchmark_root: Path,
    published_plan_count: int,
) -> tuple[
    object,
    dict[str, object],
    dict[str, object],
]:
    """Load one fresh installed page and perform the exact warmup/sample series."""

    web_test_root = Path(__file__).resolve().parents[2] / "tests" / "interfaces" / "web"
    if str(web_test_root) not in sys.path:
        sys.path.insert(0, str(web_test_root))
    from _startup_test_support import headed_command_extension
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths
    from namisync.workflows.models import ExecutionCheckpoint
    from namisync.workflows.runtime import LocalWorkflowRuntime, WorkflowPreparation
    from namisync.core.session import OperationResult, SessionState

    data_root = benchmark_root / "headed" / uuid4().hex
    controller = _HeadedFixtureController(
        metric,
        data_root / "fixture",
        published_plan_count,
    )
    result: dict[str, object] = {}
    errors: list[BaseException] = []
    retained: list[object] = []
    original_appearance = host._configure_window_appearance

    def extension(_document: object, registry: object) -> dict[str, object]:
        controller.bind(registry)
        return {"plan_scale_fixture": _headed_test_spec(controller.command)}

    def prepare_execution(_runtime: object, request: object) -> object:
        return WorkflowPreparation(ExecutionCheckpoint(request), ())

    def open_execution(_runtime: object, checkpoint: object) -> object:
        return _BlockingExecutionInvocation(controller.release, checkpoint)

    def settle_canceled(
        _runtime: object, _checkpoint: object, _disposition: object
    ) -> object:
        return OperationResult(SessionState.CANCELED, canceled=True)

    def configure(window: object, *args: object, **kwargs: object) -> object:
        appearance = original_appearance(window, *args, **kwargs)

        def loaded() -> None:
            from System import Action

            def begin() -> None:
                try:
                    _begin_headed_probe(
                        window, metric, result, errors, retained
                    )
                except BaseException as error:
                    errors.append(error)
                    controller.release.set()
                    window.destroy()

            action = Action(begin)
            retained.append(action)
            window.native.BeginInvoke(action)

        retained.append(loaded)
        window.events.loaded += loaded
        return appearance

    startup_errors: list[str] = []
    with ExitStack() as stack:
        stack.enter_context(headed_command_extension(host, extension))
        stack.enter_context(patch.object(host, "_configure_window_appearance", configure))
        stack.enter_context(
            patch.object(LocalWorkflowRuntime, "prepare_execution", prepare_execution)
        )
        stack.enter_context(
            patch.object(LocalWorkflowRuntime, "open_execution", open_execution)
        )
        stack.enter_context(
            patch.object(
                LocalWorkflowRuntime,
                "settle_canceled_execution",
                settle_canceled,
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(data_root),
            DesktopInstanceIdentity(
                rf"Local\NamiSync.PlanScale.{uuid4().hex}",
                f"NamiSync plan scale {uuid4().hex}",
            ),
            startup_error=startup_errors.append,
        )
    controller.release.set()
    if startup_errors:
        raise RuntimeError(f"headed plan-review startup failed: {startup_errors}")
    if errors:
        raise errors[0]
    expected_result = {"headed_runtime", "samples"}
    if exit_code != 0 or set(result) != expected_result:
        raise RuntimeError("headed plan-review probe did not complete")
    if controller.published_fixture is None:
        raise RuntimeError("headed plan-review fixture receipt is unavailable")
    return (
        result["samples"],
        result["headed_runtime"],
        controller.published_fixture,
    )


def _begin_headed_probe(
    window: object,
    metric: Mapping[str, object],
    result: dict[str, object],
    errors: list[BaseException],
    retained: list[object],
) -> None:
    from System import Action

    native = window.native
    if native.InvokeRequired:
        raise RuntimeError("headed plan-review probe left the UI thread")
    settings = json.dumps({
        "expression": _headed_probe_script(str(metric["id"])),
        "awaitPromise": True,
        "returnByValue": True,
    })
    task = native.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
        "Runtime.evaluate", settings
    )

    def completed() -> None:
        def finish() -> None:
            try:
                envelope = json.loads(str(task.Result))
                if type(envelope) is not dict or "exceptionDetails" in envelope:
                    detail = json.dumps(
                        envelope.get("exceptionDetails"),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    raise RuntimeError(
                        f"headed page probe returned an exception: {detail}"
                    )
                value = envelope.get("result", {}).get("value")
                if type(value) is not dict or set(value) != {"samples"}:
                    raise RuntimeError("headed page probe returned invalid evidence")
                result.update(value)
                result["headed_runtime"] = _headed_runtime_identity(window)
            except BaseException as error:
                errors.append(error)
            finally:
                window.destroy()

        action = Action(finish)
        retained.append(action)
        native.BeginInvoke(action)

    completion = Action(completed)
    retained.append(completion)
    task.GetAwaiter().OnCompleted(completion)


def _headed_probe_script(metric_id: str) -> str:
    encoded_metric = json.dumps(metric_id)
    script = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 1200; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  async function rawFixture(payload = {}) {
    const requestId = crypto.randomUUID().replaceAll("-", "");
    const native = await window.pywebview.api.dispatch(JSON.stringify({
      schema_version: 1,
      request_id: requestId,
      command: "plan_scale_fixture",
      payload,
    }));
    const response = JSON.parse(JSON.stringify(native.response));
    if (native.response_token !== null) {
      await window.pywebview.api.dispatch(`ack:${native.response_token}`);
    }
    if (response.request_id !== requestId || response.ok !== true) {
      throw new Error("headed fixture metadata was refused");
    }
    return response.result;
  }
  function taskButton(index) {
    const title = `Task ${index + 1}`;
    return Array.from(document.querySelectorAll(".nami-task-card")).find(
      (button) => button.dataset.taskLabel === title,
    );
  }
  async function selectTask(index, expectedSource, action = null, diagnostic = null) {
    const button = await until(() => taskButton(index), `Task ${index + 1}`);
    button.click();
    await until(() => button.getAttribute("aria-current") === "page", "task selection");
    const initialReview = await until(
      () => document.querySelector(".nami-plan-review"),
      "plan review",
    );
    let selectionRecoveryUsed = false;
    let review = null;
    try {
      review = await until(
        () => {
          const currentReview = document.querySelector(".nami-plan-review");
          if (
            currentReview?.isConnected === true
            && currentReview.querySelector(".nami-plan-review__paths")
              ?.textContent.includes(expectedSource)
          ) return currentReview;
          const selected = document.querySelector('.nami-task-card[aria-current="page"]');
          const selectedTaskStatus = selected
            ?.querySelector(".nami-task-card__status")?.textContent ?? "";
          if (
            selectionRecoveryUsed === false
            && selected === button
            && selectedTaskStatus
              === "Plan review could not be loaded. Select the task to retry."
            && currentReview === null
          ) {
            selectionRecoveryUsed = true;
            button.click();
          }
          return null;
        },
        "exact plan review identity",
      );
    } catch (error) {
      if (diagnostic === null) throw error;
      const selected = document.querySelector('.nami-task-card[aria-current="page"]');
      const selectedTaskStatus = selected
        ?.querySelector(".nami-task-card__status")?.textContent ?? "";
      const currentReview = document.querySelector(".nami-plan-review");
      const paths = currentReview
        ?.querySelector(".nami-plan-review__paths")?.textContent ?? "";
      const facts = currentReview?.querySelector(
        ".nami-plan-review__summary .nami-shell__guidance",
      )?.textContent ?? "";
      const snapshot = {
        expected_index: index,
        expected_request_id: diagnostic.row.request_id,
        expected_source_path: expectedSource,
        expected_task_id: diagnostic.row.task_id,
        expected_target_path: diagnostic.row.target_path,
        selected_task_matches_expected: selected === button,
        selected_task_title: selected?.dataset.taskLabel ?? "",
        selected_task_status: selectedTaskStatus,
        actual_paths: paths,
        actual_facts: facts,
        actual_status: currentReview
          ?.querySelector(".nami-plan-review__status")?.textContent ?? "",
        toolbar_hidden: currentReview
          ?.querySelector(".nami-plan-review__toolbar")?.hidden ?? null,
        footer_hidden: currentReview
          ?.querySelector(".nami-plan-review__actions")?.hidden ?? null,
        review_connected: currentReview?.isConnected ?? false,
        captured_review_connected: initialReview.isConnected,
        task_card_count: document.querySelectorAll(".nami-task-card").length,
        bridge_attempt: null,
      };
      if (
        selected === button
        && initialReview.isConnected === false
        && currentReview === null
        && selectedTaskStatus
          === "Plan review could not be loaded. Select the task to retry."
      ) {
        let bridgeStage = "open-plan-view";
        try {
          const summary = await diagnostic.bridge.openPlanView(diagnostic.row.task_id);
          bridgeStage = "get-plan-window";
          const window = await diagnostic.bridge.getPlanWindow(
            diagnostic.row.task_id, summary.view_revision, 0, 256,
          );
          const first = window.rows[0] ?? null;
          snapshot.bridge_attempt = {
            outcome: "success",
            summary_disposition: summary.disposition,
            summary_request_id: summary.request_id,
            summary_source_path: summary.source_path,
            summary_target_path: summary.target_path,
            summary_view_revision: summary.view_revision,
            window_disposition: window.disposition,
            window_view_revision: window.view_revision,
            window_offset: window.offset,
            window_total: window.total,
            window_row_count: window.rows.length,
            first_row: first === null ? null : {
              node_id: first.node_id,
              operation_id: first.operation_id,
              visible_index: first.visible_index,
            },
          };
        } catch (bridgeError) {
          const errorName = bridgeError?.name;
          const classification = errorName === "BridgeTransportError"
            ? "bridge-transport"
            : errorName === "BridgeCommandError"
              ? "bridge-command"
              : errorName === "TypeError" ? "type-error" : "unexpected";
          snapshot.bridge_attempt = {
            outcome: "error",
            stage: bridgeStage,
            classification,
            code: classification === "bridge-command"
              && typeof bridgeError.code === "string" ? bridgeError.code : null,
          };
        }
      }
      throw new Error(
        `timed out waiting for exact plan review identity: ${JSON.stringify(snapshot)}`,
      );
    }
    if (action !== null) {
      await until(
        () => review.querySelector(`[data-action="${action}"]`)?.disabled === false,
        `${action} control`,
      );
    }
    await sleep(25);
    return review;
  }
  async function selectFreshTask(index, action = null) {
    const fixture = await rawFixture();
    const row = fixture.rows[index];
    if (row?.fresh_execution_unused !== true) {
      throw new Error("headed fixture plan is not fresh for execution");
    }
    return selectTask(index, row.source_path, action);
  }
  const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));
  async function timedClick(element, pending) {
    const started = performance.now();
    element.click();
    await nextFrame();
    const elapsedNs = Math.round((performance.now() - started) * 1000000);
    const review = document.querySelector(".nami-plan-review");
    if (review?.dataset.pending !== pending) {
      throw new Error(`${pending} did not commit a pending frame`);
    }
    return elapsedNs;
  }
  async function timedReceipt(callback) {
    const started = performance.now();
    const value = await callback();
    return { elapsedNs: Math.round((performance.now() - started) * 1000000), value };
  }
  function observeStartReceipt(row) {
    const channel = globalThis.chrome?.webview;
    if (typeof channel?.addEventListener !== "function"
        || typeof channel.removeEventListener !== "function") {
      throw new Error("production document message channel is unavailable");
    }
    let started = null;
    let timeout = null;
    let receive = null;
    const promise = new Promise((resolve, reject) => {
      const finish = (callback, value) => {
        channel.removeEventListener("message", receive);
        if (timeout !== null) clearTimeout(timeout);
        callback(value);
      };
      receive = (event) => {
        const message = event?.data;
        const response = message?.response;
        const value = response?.result;
        if (message?.kind !== "namisync.command-completion.v1"
            || Object.keys(message).sort().join(",") !== "completion_token,generation,kind,phase,request_id,response"
            || message.phase !== "completion"
            || !Number.isSafeInteger(message.generation)
            || message.generation < 0
            || !/^[0-9a-f]{32}$/.test(message.request_id)
            || !/^[0-9a-f]{32}$/.test(message.completion_token)
            || Object.keys(response ?? {}).sort().join(",") !== "ok,request_id,result,schema_version"
            || response.schema_version !== 1
            || response.request_id !== message.request_id
            || response?.ok !== true
            || value?.task_id !== row.task_id
            || Object.keys(value).sort().join(",") !== "request_id,session_id,task_id") {
          return;
        }
        if (started === null
            || !/^[0-9a-f]{32}$/.test(value.request_id)
            || !/^[0-9a-f]{32}$/.test(value.session_id)) {
          finish(reject, new Error("typed execution receipt is invalid"));
          return;
        }
        finish(resolve, {
          elapsedNs: Math.round((performance.now() - started) * 1000000),
          value,
        });
      };
      channel.addEventListener("message", receive);
      timeout = setTimeout(
        () => finish(reject, new Error("timed out waiting for typed execution receipt")),
        30000,
      );
    });
    return {
      promise,
      start: () => {
        if (started !== null) throw new Error("execution receipt timer repeated");
        started = performance.now();
      },
    };
  }
  async function openExecutionConfirmation(index) {
    const review = await selectFreshTask(index, "execute");
    review.querySelector('[data-action="execute"]').click();
    const row = (await rawFixture()).rows[index];
    const dialog = await requireExecutionConfirmation(review, row);
    return { dialog, review, row };
  }
  async function requireExecutionConfirmation(review, row) {
    const dialog = await until(
      () => {
        const value = document.querySelector("#execution-confirmation");
        return value?.open === true ? value : null;
      },
      "execution confirmation",
    );
    validateExecutionConfirmation(dialog, review, row);
    return dialog;
  }
  function validateExecutionConfirmation(dialog, review, row) {
    const count = dialog?.querySelector("#execution-confirmation-count")?.textContent ?? "";
    const expectedCount = `${row.destructive_operation_count} selected destructive operation${
      row.destructive_operation_count === 1 ? "" : "s"
    }`;
    if (dialog?.open !== true
        || document.querySelector("#app")?.inert !== true
        || document.querySelector("#theme-options")?.inert !== true
        || review.dataset.pending !== "confirmation"
        || count !== expectedCount) {
      throw new Error("execution confirmation facts changed");
    }
  }
  async function cancelExecutionConfirmation(prepared) {
    prepared.dialog.querySelector("[data-cancel-execution]").click();
    await until(
      () => prepared.dialog.open === false && prepared.review.dataset.pending === "",
      "execution confirmation cancellation",
    );
  }
  async function settleStartedExecution(prepared, observation) {
    const receipt = await observation.promise;
    await until(
      () => prepared.review.dataset.pending === ""
        && prepared.review.querySelector('[data-action="pause"]')?.disabled === false
        && document.querySelector("#execution-confirmation")?.open === false,
      "execution admission settlement",
    );
    const current = await rawFixture();
    const row = current.rows.find((value) => value.task_id === prepared.row.task_id);
    if (row?.session_id !== receipt.value.session_id) {
      throw new Error("execution receipt did not become the current session");
    }
    return receipt;
  }
  async function prepareExecutionControl(index, action) {
    const prepared = await openExecutionConfirmation(index);
    const observation = observeStartReceipt(prepared.row);
    observation.start();
    prepared.dialog.querySelector("[data-confirm-execution]").click();
    await settleStartedExecution(prepared, observation);
    const review = prepared.review;
    if (action === "resume") {
      review.querySelector('[data-action="pause"]').click();
      await until(
        () => review.querySelector('[data-action="resume"]')?.disabled === false,
        "paused execution control",
      );
    }
    const current = await rawFixture();
    return { review, row: current.rows[index] };
  }
  function sample(iteration, elapsedNs, correctness) {
    return { iteration, elapsed_ns: elapsedNs, retained_bytes: null, correctness };
  }

  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "Ready");
  const fixture = await rawFixture();
  const metric = __METRIC__;
  const repetitions = 6;
  if (fixture.metric_id !== metric) throw new Error("headed fixture metric changed");
  const rows = fixture.rows;
  if (fixture.published_plan_count !== rows.length) {
    throw new Error("headed fixture publication count changed");
  }
  const bridge = await import(new URL("./bridge.js", document.baseURI).href);
  for (let index = 0; index < rows.length; index += 1) {
    await selectTask(index, rows[index].source_path, null, { bridge, row: rows[index] });
  }
  const samples = [];

  if (metric === "ui_update_plan_view_click_feedback") {
    const review = await selectTask(0, rows[0].source_path);
    const filenameSort = await until(
      () => review.querySelector('[data-sort-column="filename"]:not(:disabled)'),
      "filename sort control",
    );
    const sort = review.querySelector('[data-sort-column="size"]');
    filenameSort.click();
    await until(() => review.dataset.pending === "", "sort warmup settlement");
    const started = performance.now();
    sort.click();
    await nextFrame();
    const elapsed = Math.round((performance.now() - started) * 1000000);
    if (review.dataset.pending !== "view") throw new Error("sort pending frame missing");
    await until(
      () => review.dataset.pending === "" && sort.parentElement?.ariaSort === "ascending",
      "sort command settlement",
    );
    samples.push(sample(1, elapsed, { pending_frame: true, action: "sort" }));
  } else if (metric === "ui_mutate_plan_selection_click_feedback") {
    const review = await selectTask(0, rows[0].source_path);
    const fixtureRow = rows[0];
    const initialSummary = await bridge.openPlanView(fixtureRow.task_id);
    const initialWindow = await bridge.getPlanWindow(
      fixtureRow.task_id, initialSummary.view_revision, 0, 256,
    );
    if (
      initialSummary.disposition !== "current"
      || initialSummary.task_id !== fixtureRow.task_id
      || initialSummary.request_id !== fixtureRow.request_id
      || initialSummary.source_path !== fixtureRow.source_path
      || initialSummary.target_path !== fixtureRow.target_path
      || initialSummary.selection_state !== "reviewing"
      || initialWindow.disposition !== "current"
      || initialWindow.view_revision !== initialSummary.view_revision
      || initialWindow.offset !== 0
      || initialWindow.total !== 120000
      || initialWindow.rows.length !== 256
    ) throw new Error("selection initial public view is not exact");
    const targetRow = initialWindow.rows.find(
      (row) => typeof row.operation_id === "string" && row.selection === "selected",
    );
    if (targetRow === undefined) throw new Error("eligible selection operation is unavailable");
    const operationCheckbox = (checked) => {
      const currentReview = document.querySelector(".nami-plan-review");
      const row = Array.from(currentReview?.querySelectorAll("[data-node-id]") ?? []).find(
        (candidate) => candidate.dataset.nodeId === targetRow.node_id,
      );
      const checkbox = row?.querySelector(".nami-checkbox") ?? null;
      return row?.isConnected === true && checkbox?.isConnected === true
        && checkbox.disabled === false && checkbox.indeterminate === false
        && checkbox.checked === checked ? checkbox : null;
    };
    const warmupCheckbox = await until(
      () => operationCheckbox(true), "eligible selected operation",
    );
    warmupCheckbox.click();
    if (document.querySelector(".nami-plan-review")?.dataset.pending !== "selection") {
      throw new Error("selection warmup did not publish pending state");
    }
    await until(
      () => document.querySelector(".nami-plan-review")?.dataset.pending === "",
      "selection warmup settlement",
    );
    const warmupSummary = await bridge.openPlanView(fixtureRow.task_id);
    const warmupWindow = await bridge.getPlanWindow(
      fixtureRow.task_id, warmupSummary.view_revision, 0, 256,
    );
    const warmupRow = warmupWindow.rows.find(
      (row) => row.node_id === targetRow.node_id,
    );
    if (
      warmupSummary.disposition !== "current"
      || warmupSummary.task_id !== fixtureRow.task_id
      || warmupSummary.request_id !== fixtureRow.request_id
      || warmupSummary.source_path !== fixtureRow.source_path
      || warmupSummary.target_path !== fixtureRow.target_path
      || warmupSummary.selection_state !== "reviewing"
      || warmupSummary.selection_revision !== initialSummary.selection_revision + 1
      || warmupWindow.disposition !== "current"
      || warmupWindow.view_revision !== warmupSummary.view_revision
      || warmupRow?.operation_id !== targetRow.operation_id
      || warmupRow.selection !== "unselected"
    ) throw new Error("selection warmup public settlement is not exact");
    const measuredCheckbox = await until(
      () => operationCheckbox(false), "eligible unselected operation",
    );
    const elapsed = await timedClick(measuredCheckbox, "selection");
    await until(
      () => {
        const currentReview = document.querySelector(".nami-plan-review");
        if (currentReview?.dataset.pending !== "") return false;
        const row = Array.from(currentReview.querySelectorAll("[data-node-id]")).find(
          (candidate) => candidate.dataset.nodeId === targetRow.node_id,
        );
        const checkbox = row?.querySelector(".nami-checkbox");
        return checkbox?.checked === true && checkbox.indeterminate === false;
      },
      "selection command settlement",
    );
    const measuredSummary = await bridge.openPlanView(fixtureRow.task_id);
    const measuredWindow = await bridge.getPlanWindow(
      fixtureRow.task_id, measuredSummary.view_revision, 0, 256,
    );
    const measuredRow = measuredWindow.rows.find(
      (row) => row.node_id === targetRow.node_id,
    );
    if (
      measuredSummary.disposition !== "current"
      || measuredSummary.task_id !== fixtureRow.task_id
      || measuredSummary.request_id !== fixtureRow.request_id
      || measuredSummary.source_path !== fixtureRow.source_path
      || measuredSummary.target_path !== fixtureRow.target_path
      || measuredSummary.selection_state !== "reviewing"
      || measuredSummary.selection_revision !== warmupSummary.selection_revision + 1
      || measuredWindow.disposition !== "current"
      || measuredWindow.view_revision !== measuredSummary.view_revision
      || measuredRow?.operation_id !== targetRow.operation_id
      || measuredRow.selection !== "selected"
    ) throw new Error("selection measured public settlement is not exact");
    samples.push(sample(1, elapsed, { pending_frame: true, action: "selection" }));
  } else if (metric === "ui_start_execution_click_feedback") {
    let prepared = await openExecutionConfirmation(0);
    await cancelExecutionConfirmation(prepared);
    const review = await selectFreshTask(1, "execute");
    const row = (await rawFixture()).rows[1];
    const started = performance.now();
    review.querySelector('[data-action="execute"]').click();
    await nextFrame();
    const dialog = document.querySelector("#execution-confirmation");
    validateExecutionConfirmation(dialog, review, row);
    const elapsed = Math.round((performance.now() - started) * 1000000);
    prepared = { dialog, review, row };
    await cancelExecutionConfirmation(prepared);
    samples.push(sample(1, elapsed, {
      modal_visible: true,
      action: "execute",
      destructive_selection: true,
      fresh_eligible_plan: true,
    }));
  } else if (metric === "ui_confirm_execution_click_feedback") {
    let prepared = await openExecutionConfirmation(0);
    let observation = observeStartReceipt(prepared.row);
    observation.start();
    prepared.dialog.querySelector("[data-confirm-execution]").click();
    await settleStartedExecution(prepared, observation);
    prepared = await openExecutionConfirmation(1);
    observation = observeStartReceipt(prepared.row);
    observation.start();
    const elapsed = await timedClick(
      prepared.dialog.querySelector("[data-confirm-execution]"),
      "execute",
    );
    if (prepared.dialog.open !== true
        || document.querySelector("#app")?.inert !== true
        || document.querySelector("#theme-options")?.inert !== true) {
      throw new Error("confirmed execution lost its modal pending frame");
    }
    await settleStartedExecution(prepared, observation);
    samples.push(sample(1, elapsed, {
      busy_frame: true,
      action: "confirm",
      snapshot_exact: true,
      fresh_eligible_plan: true,
    }));
  } else if (metric === "ui_start_execution_nondestructive_click_feedback") {
    let review = await selectFreshTask(0, "execute");
    let row = (await rawFixture()).rows[0];
    if (row.destructive_operation_count !== 0) {
      throw new Error("nondestructive selection changed");
    }
    let prepared = { review, row };
    let observation = observeStartReceipt(row);
    observation.start();
    review.querySelector('[data-action="execute"]').click();
    await settleStartedExecution(prepared, observation);
    review = await selectFreshTask(1, "execute");
    row = (await rawFixture()).rows[1];
    if (row.destructive_operation_count !== 0) {
      throw new Error("nondestructive selection changed");
    }
    prepared = { review, row };
    observation = observeStartReceipt(row);
    observation.start();
    const elapsed = await timedClick(
      review.querySelector('[data-action="execute"]'),
      "execute",
    );
    if (document.querySelector("#execution-confirmation")?.open === true) {
      throw new Error("nondestructive Execute opened confirmation");
    }
    await settleStartedExecution(prepared, observation);
    samples.push(sample(1, elapsed, {
      busy_frame: true,
      action: "execute",
      destructive_selection: false,
      modal_bypassed: true,
      fresh_eligible_plan: true,
    }));
  } else if (metric.endsWith("_click_feedback")) {
    const action = metric.includes("pause") ? "pause"
        : metric.includes("resume") ? "resume" : "cancel";
    let review = (await prepareExecutionControl(0, action)).review;
    review.querySelector(`[data-action="${action}"]`).click();
    await until(() => review.dataset.pending === "", `${action} warmup settlement`);
    review = (await prepareExecutionControl(1, action)).review;
    const elapsed = await timedClick(
      review.querySelector(`[data-action="${action}"]`),
      action,
    );
    await until(
      () => {
        if (review.dataset.pending !== "") return false;
        if (action === "pause") {
          return review.querySelector('[data-action="resume"]')?.hidden === false;
        }
        if (action === "resume") {
          return review.querySelector('[data-action="pause"]')?.hidden === false;
        }
        return review.querySelector('[data-action="cancel"]')?.disabled === true;
      },
      `${action} command settlement`,
    );
    samples.push(sample(1, elapsed, { pending_frame: true, action }));
  } else if (metric === "ui_get_plan_window_one_row_receipt") {
    const row = rows[0];
    await selectTask(0, row.source_path);
    await bridge.getPlanWindow(row.task_id, row.view_revision, 0, 1);
    for (let iteration = 1; iteration <= repetitions; iteration += 1) {
    const receipt = await timedReceipt(
      () => bridge.getPlanWindow(row.task_id, row.view_revision, 0, 1),
    );
    samples.push(sample(iteration, receipt.elapsedNs, {
      disposition: receipt.value.disposition,
      requested_limit: 1,
      returned_rows: receipt.value.rows.length,
    }));
    }
  } else if (metric === "ui_start_execution_receipt") {
    let prepared = await openExecutionConfirmation(0);
    let observation = observeStartReceipt(prepared.row);
    observation.start();
    prepared.dialog.querySelector("[data-confirm-execution]").click();
    await settleStartedExecution(prepared, observation);
    for (let iteration = 1; iteration <= repetitions; iteration += 1) {
      prepared = await openExecutionConfirmation(iteration);
      observation = observeStartReceipt(prepared.row);
      observation.start();
      prepared.dialog.querySelector("[data-confirm-execution]").click();
      const receipt = await settleStartedExecution(prepared, observation);
      samples.push(sample(iteration, receipt.elapsedNs, {
        accepted: receipt.value.task_id === prepared.row.task_id,
        confirmed_destructive: true,
        snapshot_exact: true,
        fresh_eligible_plan: true,
      }));
    }
  } else if (metric.startsWith("ui_control_") && metric.endsWith("_receipt")) {
    const action = metric.includes("pause") ? "pause"
      : metric.includes("resume") ? "resume" : "cancel";
    let prepared = await prepareExecutionControl(0, action);
    await bridge.controlExecution(
      prepared.row.task_id, prepared.row.session_id, action,
    );
    for (let iteration = 1; iteration <= repetitions; iteration += 1) {
      prepared = await prepareExecutionControl(iteration, action);
      const controlRow = prepared.row;
      const receipt = await timedReceipt(
        () => bridge.controlExecution(
          controlRow.task_id, controlRow.session_id, action,
        ),
      );
      samples.push(sample(iteration, receipt.elapsedNs, {
        accepted: receipt.value.session_id === controlRow.session_id,
        action,
      }));
    }
  } else {
    throw new Error(`unknown headed plan-review metric ${metric}`);
  }
  return { samples };
})()
"""
    return script.replace("__METRIC__", encoded_metric)


CASES = tuple(
    metric["id"] for metric in json.loads(CONTRACT_PATH.read_bytes())["metrics"]
    if metric["surface"] == "component"
)


def run_case(
    case: str, *, output: Path, installed_root: Path | None = None,
) -> dict[str, object]:
    """Run one real Plan endpoint in a bounded child, without a timing verdict."""

    from ._child import run_child

    contract = json.loads(CONTRACT_PATH.read_bytes())
    metrics = {item["id"]: item for item in contract["metrics"]}
    if case not in CASES:
        raise ValueError(f"unknown Plan case: {case}")
    metric = metrics[case]
    launch_token = uuid4().hex
    arguments = [
        "--component-child", case,
        "--launch-token", launch_token,
        "--contract", str(CONTRACT_PATH),
    ]
    receipt = run_child(
        "tools.performance.plan", arguments, output=output,
        installed_root=None,
    )
    samples = receipt.get("samples")
    expected_count = 1 if metric["sample_kind"] == "cold" else 6
    memory_case = "budget_bytes" in metric
    value_field = "retained_bytes" if memory_case else "elapsed_ns"
    other_field = "elapsed_ns" if memory_case else "retained_bytes"
    if (
        receipt.get("metric_id") != case
        or receipt.get("launch_token") != launch_token
        or receipt.get("fixture_case") != metric["fixture_case"]
        or type(samples) is not list or len(samples) != expected_count
        or any(
            type(sample) is not dict
            or sample.get("correctness") != _current_correctness(metric)
            or type(sample.get(value_field)) is not int
            or sample[value_field] < 0
            or sample.get(other_field) is not None
            for sample in samples
        )
    ):
        raise RuntimeError("Plan child returned an incomplete or false observation")
    return receipt


def _write_canonical_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--component-child", metavar="METRIC_ID")
    group.add_argument("--diagnostic-child", action="store_true")
    group.add_argument("--headed-child", metavar="METRIC_ID")
    parser.add_argument("--launch-token", required=True)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--benchmark-root", type=Path)
    arguments = parser.parse_args()
    if arguments.headed_child is not None:
        receipt = run_headed_child(
            arguments.headed_child, arguments.launch_token,
            contract_path=arguments.contract,
            benchmark_root=arguments.benchmark_root,
            installed_root=arguments.installed_root,
        )
    elif arguments.diagnostic_child:
        receipt = run_diagnostic_child(arguments.launch_token)
    else:
        receipt = run_component_child(
            arguments.component_child, arguments.launch_token,
            contract_path=arguments.contract,
            installed_root=arguments.installed_root,
        )
    _write_canonical_json(arguments.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
