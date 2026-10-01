from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from namisync.workflows.inventory_projection import build_inventory_projection
from tools.performance import inventory, validate_inventory


def _synthetic_report():
    """Checker control data; these durations and launch identities are invented."""
    sources = inventory.source_hashes()
    runtime = inventory.runtime()
    report = {
        "schema": "namisync-m1-9-inventory-cold-raw-v1", "collection_complete": True,
        "fixture_seed": 0x4E414D49, "statistic": "maximum",
        "thresholds_seconds": {"base": 3, "information-heavy": 6},
        "revision": "synthetic-checker-control", "source_hashes": sources,
        "runtime": runtime, "collector_process_id": 123,
        "profile": {"reference_profile_confirmed": True, "ac_power": True,
            "no_unrelated_sustained_workload": True, "captured_at": "synthetic",
            "os_name": "synthetic", "os_build": "synthetic", "cpu": "synthetic",
            "physical_cores": 16, "logical_processors": 24, "memory_gib": 63.7,
            "repository_device": "synthetic"},
        "samples": [], "child_launches": [], "maximum_seconds": {"base": 2.0, "information-heavy": 5.0},
        "dispersion_seconds": {"base": {"minimum": 2.0, "maximum": 2.0}, "information-heavy": {"minimum": 5.0, "maximum": 5.0}},
        "purpose": "synthetic checker controls; never measurement evidence",
    }
    for case, public_rows, warning_rows, elapsed in (
        ("base", 120_000, 0, 2_000_000_000),
        ("information-heavy", 240_000, 120_000, 5_000_000_000),
    ):
        for index in range(1, 6):
            invocation_id = f"{len(report['samples']) + 1:032x}"
            report["child_launches"].append({"case": case, "child_index": index,
                "invocation_id": invocation_id, "returncode": 0, "launched_process_id": 456, "cwd": str(inventory.REPOSITORY),
                "command": [runtime["executable"], "-m", "tools.performance.inventory", "--child", case, "--timed", "--invocation-id", invocation_id]})
            report["samples"].append({"case": case, "child_index": index,
                "invocation_id": invocation_id, "process_id": 456, "parent_process_id": 123,
                "fixture_seed": 0x4E414D49, "source_hashes": sources, "runtime": runtime,
                "elapsed_ns": elapsed, "correctness": {"public_rows": public_rows,
                    "domain_rows": 100_000, "synthetic_folders": 20_000,
                    "warning_rows": warning_rows, "evidence_rows": 20_000,
                    "known_bytes": 700_000, "warning_domain_exclusion": True,
                    "raw_evidence_retained": True}})
    return report


def _write_report(tmp_path: Path, report) -> Path:
    path = tmp_path / "synthetic-checker-control.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_inventory_checker_accepts_complete_synthetic_control_without_pid_uniqueness(tmp_path) -> None:
    path = _write_report(tmp_path, _synthetic_report())
    assert validate_inventory.validate(path) == {"base": 2.0, "information-heavy": 5.0}


def test_inventory_checker_accepts_windows_redirector_launch_relation(tmp_path) -> None:
    report = _synthetic_report()
    for launch in report["child_launches"]:
        launch["launched_process_id"] = 789
    for sample in report["samples"]:
        sample["parent_process_id"] = 789
    assert validate_inventory.validate(_write_report(tmp_path, report)) == {"base": 2.0, "information-heavy": 5.0}


@pytest.mark.parametrize("launched_pid,child_pid,parent_pid", (
    (789, 456, 123), (456, 456, 789), (123, 456, 123), (789, 123, 789),
))
def test_inventory_checker_rejects_unrelated_launch_processes(tmp_path, launched_pid, child_pid, parent_pid) -> None:
    report = _synthetic_report()
    report["child_launches"][0]["launched_process_id"] = launched_pid
    report["samples"][0].update(process_id=child_pid, parent_process_id=parent_pid)
    with pytest.raises(ValueError, match="process identity"):
        validate_inventory.validate(_write_report(tmp_path, report))


def test_inventory_native_untimed_child_belongs_to_popen_launch(tmp_path) -> None:
    invocation_id = "native-untimed-launch-check"
    command = [sys.executable, "-m", "tools.performance.inventory", "--child", "base", "--invocation-id", invocation_id]
    with subprocess.Popen(command, cwd=inventory.REPOSITORY, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        stdout, stderr = process.communicate(timeout=180)
    assert process.returncode == 0, stderr
    sample = json.loads(stdout)
    assert sample["elapsed_ns"] is None and sample["invocation_id"] == invocation_id
    import os
    direct = sample["process_id"] == process.pid and sample["parent_process_id"] == os.getpid()
    redirected = sample["parent_process_id"] == process.pid and sample["process_id"] != process.pid
    assert direct or redirected
    (tmp_path / "native-untimed-child.json").write_text(json.dumps({"launched_process_id": process.pid, "collector_process_id": os.getpid(), "sample": sample}), encoding="utf-8")


@pytest.mark.parametrize("case,limit", (("base", 3_000_000_000), ("information-heavy", 6_000_000_000)))
def test_inventory_checker_rejects_one_nanosecond_over_fixed_maximum(tmp_path, case, limit) -> None:
    report = _synthetic_report()
    sample = next(item for item in report["samples"] if item["case"] == case)
    sample["elapsed_ns"] = limit + 1
    report["maximum_seconds"][case] = (limit + 1) / 1_000_000_000
    report["dispersion_seconds"][case]["maximum"] = (limit + 1) / 1_000_000_000
    with pytest.raises(ValueError, match="exceeds"):
        validate_inventory.validate(_write_report(tmp_path, report))


@pytest.mark.parametrize("mutation,reason", (
    (lambda report: report.update(collection_complete=False), "incomplete"),
    (lambda report: report["samples"].pop(), "ten fresh"),
    (lambda report: report["child_launches"].pop(), "ten fresh"),
    (lambda report: report["samples"][0]["correctness"].update(public_rows=119_999), "population"),
    (lambda report: report["samples"][0].update(source_hashes={}), "child source"),
    (lambda report: report["samples"][0].update(runtime={}), "runtime"),
    (lambda report: report["child_launches"][0].update(invocation_id="different"), "command"),
    (lambda report: report["profile"].update(no_unrelated_sustained_workload=False), "unconfirmed"),
))
def test_inventory_checker_rejects_incomplete_wrong_population_and_provenance(tmp_path, mutation, reason) -> None:
    report = _synthetic_report()
    mutation(report)
    with pytest.raises(ValueError, match=reason):
        validate_inventory.validate(_write_report(tmp_path, report))


def test_inventory_checker_rejects_changed_source_digest(tmp_path) -> None:
    report = _synthetic_report()
    report["source_hashes"] = dict(report["source_hashes"])
    report["source_hashes"]["namisync/workflows/inventory_projection.py"] = "0" * 64
    with pytest.raises(ValueError, match="source drift"):
        validate_inventory.validate(_write_report(tmp_path, report))


def test_inventory_checker_stays_fail_closed_under_optimized_python(tmp_path) -> None:
    report = _synthetic_report()
    report["collection_complete"] = False
    path = _write_report(tmp_path, report)
    result = subprocess.run([sys.executable, "-O", "-m", "tools.performance.validate_inventory", str(path)],
        cwd=inventory.REPOSITORY, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and "collection is incomplete" in result.stderr
    assert not (tmp_path / "validation.json").exists()


def test_inventory_fixture_populations_and_raw_evidence_are_correct_without_timing() -> None:
    for case in ("base", "information-heavy"):
        rows, warnings = inventory.fixture(case)
        projection = build_inventory_projection(1, rows, warnings)
        facts = inventory.correctness(projection, rows, warnings, case)
        assert facts["public_rows"] == (120_000 if case == "base" else 240_000)
        assert facts["raw_evidence_retained"] and facts["warning_domain_exclusion"]


def test_inventory_write_new_never_overwrites_existing_report(tmp_path) -> None:
    path = tmp_path / "report.json"
    inventory.write_new(path, {"old": True})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        inventory.write_new(path, {"replacement": True})
    assert path.read_bytes() == before


def test_inventory_collector_rejects_unconfirmed_profile_before_child_work(tmp_path, monkeypatch) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"reference_profile_confirmed": False}), encoding="utf-8")
    monkeypatch.setattr(inventory.subprocess, "run", lambda *args, **kwargs: pytest.fail("unconfirmed profile reached child work"))
    with pytest.raises(ValueError, match="Confirm"):
        inventory.collect(profile)


def test_inventory_collector_keeps_failed_child_raw_records_and_module_launch(tmp_path, monkeypatch) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(_synthetic_report()["profile"]), encoding="utf-8")
    monkeypatch.setattr(inventory, "OUTPUT_ROOT", tmp_path / "output")
    commands = []

    def run(command, **kwargs):
        if command[:2] == ["git", "rev-parse"]:
            return SimpleNamespace(stdout="synthetic\n", returncode=0)
        if command[:2] == ["git", "status"]:
            return SimpleNamespace(stdout="", returncode=0)

    class FailedChild:
        pid = 456
        returncode = 1

        def __init__(self, command, **kwargs):
            commands.append(command)
            kwargs["stdout"].write("synthetic child failure; no measurement\n")
            kwargs["stderr"].write("controlled failed launch\n")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(inventory.subprocess, "run", run)
    monkeypatch.setattr(inventory.subprocess, "Popen", FailedChild)
    with pytest.raises(RuntimeError, match="child 1 failed"):
        inventory.collect(profile)
    output = next((tmp_path / "output").iterdir())
    raw = json.loads((output / "raw.json").read_text(encoding="utf-8"))
    assert raw["collection_complete"] is False and raw["samples"] == []
    assert raw["child_launches"][0]["returncode"] == 1
    assert raw["child_launches"][0]["launched_process_id"] == 456
    assert commands[0][:3] == [sys.executable, "-m", "tools.performance.inventory"]
    assert raw["child_launches"][0]["command"] == commands[0]
    assert (output / "base-1.stdout.log").read_text(encoding="utf-8").startswith("synthetic")
    assert (output / "base-1.stderr.log").read_text(encoding="utf-8") == "controlled failed launch\n"
