"""M1-9 fixture checks and verdict-free cold inventory projection collection."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
OUTPUT_ROOT = REPOSITORY / "build" / "m1-9-20261001"
MODULE = "tools.performance.inventory"

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.models import EntryKind, FileStat, MetadataSnapshot, ScanWarning, ScanWarningCode
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.workflows.inventory_projection import build_inventory_projection

SEED = 0x4E414D49
NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
CASES = {"base": (120_000, 0), "information-heavy": (240_000, 120_000)}
SOURCE_PATHS = (
    "tools/performance/inventory.py", "tools/performance/validate_inventory.py",
    "namisync/workflows/inventory_projection.py", "namisync/workflows/node_tree.py",
    "namisync/core/models.py", "namisync/core/evidence.py", "namisync/core/integrity.py",
    "namisync/core/pathing.py", "namisync/core/scalars.py", "namisync/core/review.py",
    "namisync/db/repositories.py",
)


def fixture(case: str):
    stat = FileStat(EntryKind.FILE, 7, 11, None, 1, MetadataSnapshot(0, 3))
    evidence = Attestation(ContentEvidence("xxh3_128", bytes([SEED & 255]) * 16, 7, Provenance.VERIFY_ATTESTED, NOW), stat)
    rows = tuple(InventorySnapshot(
        str(index + 1), 1, f"folder{index // 5:05d}\\file{index:06d}",
        f"FOLDER{index // 5:05d}\\FILE{index:06d}", EntryKind.FILE,
        InventoryPresence.PRESENT, stat, evidence if index % 5 == 0 else None,
        NOW, NOW if index % 5 == 0 else None, "m1-9-cold-fixture", None, None,
        None, None, None,
    ) for index in range(100_000))
    codes = tuple(ScanWarningCode)
    warnings = tuple(ScanWarning(codes[index % len(codes)], rows[index % len(rows)].rel_path,
        f"inventory fixture warning {index:06d}") for index in range(CASES[case][1]))
    return rows, warnings


def correctness(projection, rows, warnings, case: str):
    expected_public, expected_warnings = CASES[case]
    assert len(rows) == 100_000 and len(warnings) == expected_warnings
    assert len(projection.nodes) - 1 == expected_public
    assert len(projection.position_by_path_key) == 120_001
    assert len(projection.node_id_by_row_id) == 100_000
    root = projection.nodes[0]
    assert root.rollup.domain_count == root.rollup.file_count == 100_000
    assert root.rollup.verified == 20_000 and root.rollup.unverified == 80_000
    assert root.rollup.size == 700_000 and not root.rollup.size_overflow and not root.rollup.size_partial
    assert projection.warning_count == expected_warnings
    domain_ids = set()
    domain_node_ids = set(projection.node_id_by_row_id.values())
    evidence_rows = 0
    warning_ordinal = 0
    for node in projection.nodes:
        if node.warning is not None:
            assert node.warning is warnings[warning_ordinal]
            warning_ordinal += 1
            assert node.parent_index == 0 and node.row is None
            assert node.rollup.domain_count == node.rollup.file_count == node.rollup.size == 0
            assert node.node_id not in domain_node_ids
            continue
        assert projection.position_by_path_key[node.rel_path_key] == node.position
        if node.row is None:
            assert node.size is None and node.mtime_ns is None
            continue
        row = node.row
        domain_ids.add(row.row_id)
        assert projection.row_for_id(row.row_id) is rows[int(row.row_id) - 1]
        assert row.observed.size == node.size == 7 and row.observed.mtime_ns == node.mtime_ns == 11
        if row.attestation is not None:
            evidence_rows += 1
            assert row.attestation.subject is row.observed
            assert row.attestation.content.digest == bytes([SEED & 255]) * 16
            assert row.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert domain_ids == {str(index + 1) for index in range(100_000)}
    assert evidence_rows == 20_000 and warning_ordinal == expected_warnings
    # Folder membership is an independent path-derived oracle, excluding warnings.
    for folder in ("FOLDER00000", "FOLDER09999", "FOLDER19999"):
        node = projection.nodes[projection.position_by_path_key[folder]]
        expected = tuple(row.row_id for row in rows if row.rel_path_key.startswith(folder + "\\"))
        assert projection.domain_row_ids(node.node_id) == expected
        assert node.rollup.domain_count == node.rollup.file_count == 5 and node.rollup.size == 35
    if warnings:
        warning_node = projection.nodes[-1]
        try:
            projection.domain_row_ids(warning_node.node_id)
        except ValueError:
            pass
        else:
            raise AssertionError("warning acquired domain scope")
    return {"public_rows": expected_public, "domain_rows": 100_000,
        "synthetic_folders": 20_000, "warning_rows": expected_warnings,
        "evidence_rows": evidence_rows, "known_bytes": 700_000,
        "warning_domain_exclusion": True, "raw_evidence_retained": True}


def source_hashes():
    return {relative: hashlib.sha256((REPOSITORY / relative).read_bytes()).hexdigest()
        for relative in SOURCE_PATHS}


def runtime():
    return {"python": sys.version, "executable": sys.executable,
        "sqlite": sqlite3.sqlite_version, "platform": platform.platform(),
        "machine": platform.machine(), "gc_enabled": gc.isenabled(),
        "gc_thresholds": list(gc.get_threshold())}


def child(case: str, timed: bool, invocation_id: str):
    if sys.flags.optimize:
        raise ValueError("Inventory fixture correctness requires a normal, non-optimized interpreter")
    before = source_hashes()
    rows, warnings = fixture(case)
    gc.collect()
    if timed:
        from time import perf_counter_ns
        started = perf_counter_ns()
        projection = build_inventory_projection(1, rows, warnings)
        elapsed = perf_counter_ns() - started
    else:
        projection = build_inventory_projection(1, rows, warnings)
        elapsed = None
    facts = correctness(projection, rows, warnings, case)
    assert source_hashes() == before, "source changed during child"
    return {"case": case, "fixture_seed": SEED, "correctness": facts,
        "elapsed_ns": elapsed, "source_hashes": before, "runtime": runtime(),
        "invocation_id": invocation_id, "process_id": os.getpid(),
        "parent_process_id": os.getppid()}


def write_new(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write("\n")


def collect(profile_path: Path):
    if sys.flags.optimize:
        raise ValueError("Inventory fixture correctness requires a normal, non-optimized interpreter")
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    if profile.get("reference_profile_confirmed") is not True or profile.get("no_unrelated_sustained_workload") is not True or profile.get("ac_power") is not True:
        raise ValueError("Confirm the actual reference profile, AC power and idle workload before timing")
    if not all(profile.get(field) for field in ("captured_at", "os_name", "os_build", "cpu", "physical_cores", "logical_processors", "memory_gib", "repository_device")):
        raise ValueError("Record actual profile fields before timing")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / f"measurement-inventory-cold-{stamp}-{uuid4().hex[:8]}"
    output.mkdir()
    before = source_hashes()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True, capture_output=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPOSITORY, text=True, capture_output=True, check=True).stdout
    raw = {"schema": "namisync-m1-9-inventory-cold-raw-v1", "started_at": stamp,
        "revision": revision, "dirty": dirty, "source_hashes": before,
        "runtime": runtime(), "profile": profile,
        "profile_file_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "fixture_seed": SEED, "statistic": "maximum", "thresholds_seconds": {"base": 3, "information-heavy": 6},
        "collector_process_id": os.getpid(), "child_launches": [],
        "samples": [], "collection_complete": False}
    try:
        for case in CASES:
            for index in range(5):
                prefix = output / f"{case}-{index + 1}"
                invocation_id = uuid4().hex
                command = [sys.executable, "-m", MODULE, "--child", case, "--timed", "--invocation-id", invocation_id]
                launch = {"case": case, "child_index": index + 1, "invocation_id": invocation_id,
                    "command": command, "cwd": str(REPOSITORY), "returncode": None}
                raw["child_launches"].append(launch)
                with prefix.with_suffix(".stdout.log").open("x", encoding="utf-8") as stdout, prefix.with_suffix(".stderr.log").open("x", encoding="utf-8") as stderr:
                    with subprocess.Popen(command, cwd=REPOSITORY, stdout=stdout, stderr=stderr) as process:
                        launch["launched_process_id"] = process.pid
                        try:
                            process.wait(timeout=180)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                            raise
                launch["returncode"] = process.returncode
                if process.returncode:
                    raise RuntimeError(f"{case} child {index + 1} failed; inspect raw logs")
                sample = json.loads(prefix.with_suffix(".stdout.log").read_text(encoding="utf-8"))
                assert sample["source_hashes"] == before and sample["runtime"] == raw["runtime"], "child provenance drift"
                direct_child = sample["process_id"] == launch["launched_process_id"] and sample["parent_process_id"] == raw["collector_process_id"]
                redirector_child = sample["parent_process_id"] == launch["launched_process_id"] and sample["process_id"] != launch["launched_process_id"]
                assert sample["invocation_id"] == invocation_id and (direct_child or redirector_child), "child launch identity drift"
                sample["child_index"] = index + 1
                raw["samples"].append(sample)
        assert source_hashes() == before, "source changed during collection"
        raw["collection_complete"] = True
        raw["maximum_seconds"] = {case: max(item["elapsed_ns"] for item in raw["samples"] if item["case"] == case) / 1_000_000_000 for case in CASES}
        raw["dispersion_seconds"] = {case: {"minimum": min(item["elapsed_ns"] for item in raw["samples"] if item["case"] == case) / 1_000_000_000,
            "maximum": raw["maximum_seconds"][case]} for case in CASES}
    except Exception as error:
        raw["failure"] = {"type": type(error).__name__, "message": str(error)}
        write_new(output / "raw.json", raw)
        print(str(output / "raw.json"))
        raise
    write_new(output / "raw.json", raw)
    print(str(output / "raw.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--collect", action="store_true")
    mode.add_argument("--child", choices=tuple(CASES))
    parser.add_argument("--timed", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--invocation-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if args.invocation_id is None:
            parser.error("child launch requires its collector invocation id")
        print(json.dumps(child(args.child, args.timed, args.invocation_id), ensure_ascii=True))
    elif args.check:
        if args.timed:
            parser.error("--check never collects timing")
        facts = [child(case, False, uuid4().hex) for case in CASES]
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        output = OUTPUT_ROOT / f"measurement-inventory-fixture-check-{uuid4().hex}.json"
        write_new(output, {"status": "correctness-only", "timing_collected": False, "cases": facts})
        print(str(output))
    else:
        if args.profile is None:
            parser.error("--collect requires --profile with verified runtime and workload facts")
        collect(args.profile.resolve())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
