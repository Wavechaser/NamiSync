"""Separate fixed-criterion validator for M1-9 cold projection raw evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
EXPECTED = {
    "base": (120_000, 0, 3_000_000_000),
    "information-heavy": (240_000, 120_000, 6_000_000_000),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    require(raw["schema"] == "namisync-m1-9-inventory-cold-raw-v1", "unknown raw schema")
    require(raw["collection_complete"] is True and "failure" not in raw, "collection is incomplete")
    require(raw["statistic"] == "maximum" and raw["fixture_seed"] == 0x4E414D49, "unexpected statistic or fixture")
    require(raw["thresholds_seconds"] == {"base": 3, "information-heavy": 6}, "criterion changed")
    require(len(raw["samples"]) == 10 and len(raw["child_launches"]) == 10, "ten fresh child samples are required")
    require(bool(raw["revision"] and raw["runtime"]["python"] and raw["runtime"]["sqlite"]), "missing candidate or runtime")
    profile = raw["profile"]
    for field in ("reference_profile_confirmed", "ac_power", "no_unrelated_sustained_workload"):
        require(profile[field] is True, f"unconfirmed {field}")
    for field in ("captured_at", "os_name", "os_build", "cpu", "physical_cores", "logical_processors", "memory_gib", "repository_device"):
        require(bool(profile.get(field)), f"missing actual profile field {field}")
    required_sources = {
        "namisync/workflows/inventory_projection.py", "namisync/workflows/node_tree.py",
        "namisync/core/models.py", "namisync/core/evidence.py", "namisync/db/repositories.py",
        "namisync/core/integrity.py", "namisync/core/pathing.py",
        "namisync/core/scalars.py", "namisync/core/review.py",
        "tools/performance/inventory.py", "tools/performance/validate_inventory.py",
    }
    require(required_sources == raw["source_hashes"].keys(), "source binding is incomplete or unexpected")
    for relative, digest in raw["source_hashes"].items():
        source = (REPOSITORY / relative).resolve()
        require(source.is_relative_to(REPOSITORY), "source path leaves repository")
        require(hashlib.sha256(source.read_bytes()).hexdigest() == digest, f"source drift: {relative}")
    require(len({launch["invocation_id"] for launch in raw["child_launches"]}) == 10, "child launches are duplicated")
    launches = {(launch["case"], launch["child_index"]): launch for launch in raw["child_launches"]}
    require(len(launches) == 10, "child sample membership is duplicated")
    maxima = {}
    for case, (public_rows, warning_rows, limit_ns) in EXPECTED.items():
        samples = [sample for sample in raw["samples"] if sample["case"] == case]
        require(len(samples) == 5 and {sample["child_index"] for sample in samples} == {1, 2, 3, 4, 5}, f"incomplete {case} samples")
        for sample in samples:
            require(sample["source_hashes"] == raw["source_hashes"], "child source drift")
            require(sample["runtime"] == raw["runtime"] and sample["fixture_seed"] == raw["fixture_seed"], "child runtime or fixture drift")
            require(type(sample["elapsed_ns"]) is int and sample["elapsed_ns"] > 0, "invalid elapsed sample")
            launch = launches[(case, sample["child_index"])]
            require(launch["returncode"] == 0 and launch["cwd"] == str(REPOSITORY), "child launch did not complete at the repository")
            require(launch["command"] == [raw["runtime"]["executable"], "-m", "tools.performance.inventory", "--child", case, "--timed", "--invocation-id", launch["invocation_id"]], "child launch command drift")
            require(sample["invocation_id"] == launch["invocation_id"], "child launch identity drift")
            launched_pid = launch["launched_process_id"]
            require(type(launched_pid) is int and launched_pid > 0 and launched_pid != raw["collector_process_id"], "invalid launched process identity")
            require(type(sample["process_id"]) is int and sample["process_id"] > 0 and sample["process_id"] != raw["collector_process_id"], "invalid child process identity")
            direct_child = sample["process_id"] == launched_pid and sample["parent_process_id"] == raw["collector_process_id"]
            redirector_child = sample["parent_process_id"] == launched_pid and sample["process_id"] != launched_pid
            require(direct_child or redirector_child, "child process identity drift")
            require(sample["correctness"] == {
                "public_rows": public_rows, "domain_rows": 100_000,
                "synthetic_folders": 20_000, "warning_rows": warning_rows,
                "evidence_rows": 20_000, "known_bytes": 700_000,
                "warning_domain_exclusion": True, "raw_evidence_retained": True,
            }, "fixture population or evidence correctness failed")
        maximum = max(sample["elapsed_ns"] for sample in samples)
        minimum = min(sample["elapsed_ns"] for sample in samples)
        require(raw["maximum_seconds"][case] == maximum / 1_000_000_000, "maximum aggregation mismatch")
        require(raw["dispersion_seconds"][case] == {"minimum": minimum / 1_000_000_000, "maximum": maximum / 1_000_000_000}, "dispersion aggregation mismatch")
        require(maximum <= limit_ns, f"{case} maximum exceeds its fixed criterion")
        maxima[case] = maximum / 1_000_000_000
    require({sample["case"] for sample in raw["samples"]} == set(EXPECTED), "unknown sample case")
    return maxima


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    args = parser.parse_args()
    maxima = validate(args.raw.resolve())
    verdict = args.raw.resolve().parent / "validation.json"
    with verdict.open("x", encoding="utf-8") as stream:
        json.dump({"status": "pass", "raw_sha256": hashlib.sha256(args.raw.read_bytes()).hexdigest(),
            "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "maximum_seconds": maxima, "uncertainty": "Named reference profile only; five fresh children per case, no universal latency or memory claim."}, stream, indent=2)
        stream.write("\n")
    print(str(verdict))


if __name__ == "__main__":
    main()
