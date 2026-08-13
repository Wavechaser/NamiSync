"""Ordinary contract checks for the opt-in installed-wheel event benchmark."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[2]
PARENT = ROOT / "bridge_event_benchmark.py"
CHILD = Path(__file__).with_name("_bridge_event_benchmark_child.py")
ASSETS = ROOT / "assets" / "bridge_event_benchmark"


def _benchmark_module():
    specification = importlib.util.spec_from_file_location(
        "bridge_event_benchmark_contract",
        PARENT,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_bridge_event_benchmark_sources_compile_and_keep_test_seams_external() -> None:
    parent = PARENT.read_text(encoding="utf-8")
    child = CHILD.read_text(encoding="utf-8")
    browser = (ASSETS / "benchmark.js").read_text(encoding="utf-8")

    compile(parent, str(PARENT), "exec")
    compile(child, str(CHILD), "exec")
    assert "git archive" in parent
    assert "pip\",\n            \"wheel" in parent
    assert "WorkflowRegistration" in child
    assert "TaskRegistry" not in browser
    assert 'from "./bridge.js"' in browser
    assert 'from "./render.js"' in browser
    assert "evaluate_js" not in parent
    assert "evaluate_js" not in child
    assert "evaluate_js" not in browser
    assert "SAMPLE_REPORT_BATCH_SIZE = 250" in browser
    assert 'sampleClass === "terminal_event"' in browser
    assert "retainedBytes" not in browser
    assert "PrivateUsage" in parent
    assert 'kind: "ready"' in browser


def test_bridge_event_benchmark_full_ordinary_sample_batch_fits_ingress() -> None:
    samples = [
        {
            "class": "progress",
            "event_id": "Progress",
            "event_result": None,
            "latency_ms": 1_999.999,
            "observed_offset_ms": 59_999.999,
            "position": 1_500,
            "record_state": None,
            "session_id": "f" * 32,
            "sequence": 2_000,
        }
        for _ in range(250)
    ]
    request = {
        "schema_version": 1,
        "request_id": "f" * 32,
        "command": "benchmark_report",
        "payload": {"kind": "samples", "value": samples},
    }

    encoded = json.dumps(
        request,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    assert len(encoded) <= 65_536


def test_bridge_event_benchmark_reads_current_process_private_memory() -> None:
    benchmark = _benchmark_module()

    private_bytes = benchmark._process_private_bytes(os.getpid())

    assert type(private_bytes) is int
    assert private_bytes > 0


def test_bridge_event_benchmark_sanitizes_every_python_child_environment(
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    monkeypatch.setenv("PYTHONPATH", "host-contamination")
    monkeypatch.setenv("PYTHONHOME", "host-contamination")

    environment = benchmark._clean_python_environment()

    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert environment["PYTHONNOUSERSITE"] == "1"


def test_bridge_event_benchmark_builds_the_named_archive_with_clean_python_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    commands = []

    def run(command, *, cwd, timeout, environment=None):
        commands.append((tuple(command), Path(cwd), timeout, environment))
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return "a" * 40
        if command[:3] == ["git", "status", "--porcelain=v1"]:
            return "?? M1_SHELL.md\n?? S0-S3_REALIGNMENT.md"
        if command[:2] == ["git", "archive"]:
            output_argument = next(
                argument for argument in command if argument.startswith("--output=")
            )
            with zipfile.ZipFile(output_argument.removeprefix("--output="), "w") as archive:
                archive.writestr("pyproject.toml", "[build-system]\n")
            return ""
        if command[1:4] == ["-m", "pip", "wheel"]:
            wheel_directory = Path(command[command.index("--wheel-dir") + 1])
            (wheel_directory / "namisync-0.1-py3-none-any.whl").write_bytes(b"wheel")
            return ""
        raise AssertionError(command)

    monkeypatch.setattr(benchmark, "_run", run)
    monkeypatch.setenv("PYTHONPATH", "host-contamination")
    monkeypatch.setenv("PYTHONHOME", "host-contamination")

    wheel, commit, status = benchmark._build_archived_wheel(tmp_path)

    assert wheel.name == "namisync-0.1-py3-none-any.whl"
    assert commit == "a" * 40
    assert status == ("?? M1_SHELL.md", "?? S0-S3_REALIGNMENT.md")
    archive_command = commands[2][0]
    assert archive_command[-1] == commit
    build_environment = commands[-1][3]
    assert build_environment is not None
    assert "PYTHONPATH" not in build_environment
    assert "PYTHONHOME" not in build_environment
    assert build_environment["PYTHONNOUSERSITE"] == "1"


def test_bridge_event_benchmark_installs_with_clean_python_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    wheel = tmp_path / "namisync-0.1-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    install_root = tmp_path / "install"
    install_root.mkdir()
    calls = []

    def run(command, *, cwd, timeout, environment=None):
        calls.append((tuple(command), Path(cwd), timeout, environment))
        if command[1:4] == ["-m", "venv", "--clear"]:
            python = Path(command[-1]) / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
        return ""

    monkeypatch.setattr(benchmark, "_run", run)
    monkeypatch.setenv("PYTHONPATH", "host-contamination")
    monkeypatch.setenv("PYTHONHOME", "host-contamination")

    python = benchmark._install_wheel(install_root, wheel)

    assert python == tmp_path / "install" / "venv" / "Scripts" / "python.exe"
    assert len(calls) == 3
    for _command, _cwd, _timeout, environment in calls:
        assert environment is not None
        assert "PYTHONPATH" not in environment
        assert "PYTHONHOME" not in environment
        assert environment["PYTHONNOUSERSITE"] == "1"


def _passing_evidence(benchmark):
    samples = []
    session_ids = [f"{index + 1:032x}" for index in range(4)]
    terminal_event_latencies = []
    terminal_record_latencies = []
    for task_index, session_id in enumerate(session_ids):
        sequence = 1
        for state in ("pending", "running"):
            samples.append(
                {
                    "class": "reliable",
                    "event_id": "StateChanged",
                    "event_result": {"state": state},
                    "latency_ms": 10,
                    "observed_offset_ms": 0 if state == "pending" else 1,
                    "position": None,
                    "record_state": None,
                    "session_id": session_id,
                    "sequence": sequence,
                }
            )
            sequence += 1
        reliable_ids = []
        pattern = (3, 3, 2, 2)
        for tick in range(1_500):
            progress_sequence = sequence
            sequence += 1
            position = tick + 1
            if position % 50 == 0:
                samples.append(
                    {
                        "class": "progress",
                        "event_id": "Progress",
                        "event_result": None,
                        "latency_ms": 30,
                        "observed_offset_ms": tick * 40,
                        "position": position,
                        "record_state": None,
                        "session_id": session_id,
                        "sequence": progress_sequence,
                    }
                )
            second, within_second = divmod(tick, 25)
            reliable_count = pattern[(task_index + second) % 4]
            reliable_ticks = sorted(
                ((item_index + 1) * 25) // (reliable_count + 1)
                for item_index in range(reliable_count)
            )
            if within_second in reliable_ticks:
                item_index = reliable_ticks.index(within_second)
                event_id = (
                    f"task-{task_index}-item-{second:02d}-{item_index}"
                )
                reliable_ids.append(event_id)
                samples.append(
                    {
                        "class": "reliable",
                        "event_id": event_id,
                        "event_result": "succeeded",
                        "latency_ms": 10,
                        "observed_offset_ms": tick * 40 + 1,
                        "position": None,
                        "record_state": None,
                        "session_id": session_id,
                        "sequence": sequence,
                    }
                )
                sequence += 1
        assert reliable_ids == benchmark._expected_reliable_ids(task_index)
        samples.append(
            {
                "class": "reliable",
                "event_id": "StateChanged",
                "event_result": {"state": "completed"},
                "latency_ms": 10,
                "observed_offset_ms": 59_970,
                "position": None,
                "record_state": None,
                "session_id": session_id,
                "sequence": sequence,
            }
        )
        sequence += 1
        samples.append(
            {
                "class": "terminal_event",
                "event_id": "Terminal",
                "event_result": {
                    "status": "completed",
                    "recording": "ok",
                    "audit": "ok",
                    "disposition": "ran",
                    "canceled": False,
                    "phase_count": 0,
                    "bytes_done": 1_500,
                    "bytes_total": 1_500,
                    "items": [
                        [event_id, "succeeded"] for event_id in reliable_ids
                    ],
                    "error": None,
                },
                "latency_ms": 20,
                "observed_offset_ms": 59_980,
                "position": None,
                "record_state": None,
                "session_id": session_id,
                "sequence": sequence,
            }
        )
        terminal_event_latencies.append(20)
        samples.append(
            {
                "class": "terminal_record",
                "event_id": "record",
                "event_result": {
                    "headline": "success",
                    "filesystem": "completed",
                    "integrity": "not-run",
                    "recording": "ok",
                    "audit": "ok",
                    "disposition": "ran",
                    "canceled": False,
                    "phase_count": 0,
                    "bytes_done": 1_500,
                    "bytes_total": 1_500,
                    "items": [
                        [event_id, "succeeded"] for event_id in reliable_ids
                    ],
                    "error": None,
                },
                "latency_ms": 20,
                "observed_offset_ms": 59_990,
                "position": None,
                "record_state": "completed",
                "session_id": session_id,
                "sequence": None,
            }
        )
        terminal_record_latencies.append(20)
    producers = []
    for task_index in range(4):
        producers.append(
            {
                "elapsed_seconds": 59.97,
                "first_emission_offset_seconds": 0.01,
                "last_emission_offset_seconds": 59.96,
                "progress_emissions": 1_500,
                "progress_emission_offsets_seconds": [
                    tick * 0.04 for tick in range(1_500)
                ],
                "reliable_by_second": [
                    (3, 3, 2, 2)[(task_index + second) % 4]
                    for second in range(60)
                ],
                "reliable_emissions": 150,
                "reliable_emission_offsets_seconds": (
                    benchmark._expected_reliable_offsets(task_index)
                ),
            }
        )
    evidence = {
        "samples": samples,
        "browser": {
            "gap_events": [],
            "progress_monotonic": True,
            "session_ids": session_ids,
            "task_count": 4,
            "terminal_event_latencies_ms": terminal_event_latencies,
            "terminal_record_latencies_ms": terminal_record_latencies,
            "terminal_record_count": 4,
        },
        "python_queue_memory": {
            "error": None,
            "max_sample_interval_seconds": 0.021,
            "peak_bytes": 3_000,
            "sample_count": 3_000,
        },
        "producer_task_0": producers[0],
        "producer_task_1": producers[1],
        "producer_task_2": producers[2],
        "producer_task_3": producers[3],
        "runtime": {
            "python": "3.13.14 (test)",
            "sqlite": "3.50.4",
            "packages": {
                "bottle": "0.13.4",
                "namisync": "0.1.0",
                "pywebview": "6.2.1",
                "pythonnet": "3.1.0",
            },
        },
        "clr_runtime": "Runtime: .NET Framework",
        "webview2": "test",
        "startup_errors": [],
        "exit_code": 0,
        "production_command_names": [
            "close_task",
            "next_events",
            "pick_folder",
            "release_terminal_session",
            "start_plan",
        ],
        "combined_command_names": [
            "benchmark_report",
            "benchmark_start",
            "close_task",
            "next_events",
            "pick_folder",
            "release_terminal_session",
            "start_plan",
        ],
    }
    raw_memory = [
        {
            "elapsed_seconds": index * 0.02,
            "missing_process_ids": [],
            "phase": "baseline" if index < 50 else "fixture",
            "private_bytes": 100_000 if index < 50 else 104_000,
            "process_ids": [123],
        }
        for index in range(3_050)
    ]
    job_memory = benchmark._job_memory_result(
        raw_memory,
        fixture_ended_at_seconds=60.99,
        root_process_id=123,
    )
    return evidence, job_memory


def test_bridge_event_benchmark_summary_enforces_all_fixed_ceilings(
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    monkeypatch.setattr(
        benchmark,
        "_machine",
        lambda _root: {"machine": "test", "reference_profile_match": True},
    )
    evidence, job_memory = _passing_evidence(benchmark)

    result = benchmark._summarize(
        evidence,
        benchmark_root=ROOT,
        commit="a" * 40,
        status=(),
        job_memory=job_memory,
    )

    assert result["passed"] is True
    assert result["fixture"] == {
        "seed": 0,
        "wall_seconds": 60,
        "task_count": 4,
        "progress_emissions": 6_000,
        "reliable_emissions": 600,
    }
    assert (
        result["memory"]["job_private_memory"]
        ["incremental_peak_private_bytes"]
        == 4_000
    )

    refused_evidence = copy.deepcopy(evidence)
    refused_evidence["browser"]["gap_events"] = [
        {"session_id": "1" * 32, "first_missed_seq": 1}
    ]
    refused = benchmark._summarize(
        refused_evidence,
        benchmark_root=ROOT,
        commit="a" * 40,
        status=(),
        job_memory=job_memory,
    )
    assert refused["passed"] is False


def test_bridge_event_benchmark_rejects_incomplete_or_untrusted_evidence(
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    monkeypatch.setattr(
        benchmark,
        "_machine",
        lambda _root: {"machine": "test", "reference_profile_match": True},
    )
    evidence, job_memory = _passing_evidence(benchmark)

    corruptions = []
    negative = copy.deepcopy(evidence)
    negative["samples"][0]["latency_ms"] = -1
    corruptions.append((negative, job_memory))
    malformed = copy.deepcopy(evidence)
    malformed["samples"][0].pop("session_id")
    corruptions.append((malformed, job_memory))
    one_session = copy.deepcopy(evidence)
    one_session["browser"]["session_ids"] = ["1" * 32] * 4
    corruptions.append((one_session, job_memory))
    unhashable_sessions = copy.deepcopy(evidence)
    unhashable_sessions["browser"]["session_ids"][0] = []
    corruptions.append((unhashable_sessions, job_memory))
    browser_failure = copy.deepcopy(evidence)
    browser_failure["browser"]["failure"] = "BridgeTransportError"
    corruptions.append((browser_failure, job_memory))
    startup_failure = copy.deepcopy(evidence)
    startup_failure["startup_errors"] = ["failed"]
    corruptions.append((startup_failure, job_memory))
    incomplete_memory = dict(job_memory, all_samples_complete=False)
    corruptions.append((evidence, incomplete_memory))
    blind_memory = dict(job_memory, max_sample_interval_seconds=0.5)
    corruptions.append((evidence, blind_memory))
    hidden_blind_interval = copy.deepcopy(job_memory)
    for index in range(100, len(hidden_blind_interval["samples"])):
        hidden_blind_interval["samples"][index]["elapsed_seconds"] += 0.2
    corruptions.append((evidence, hidden_blind_interval))
    hidden_tail_interval = copy.deepcopy(job_memory)
    hidden_tail_interval["fixture_ended_at_seconds"] += 0.2
    corruptions.append((evidence, hidden_tail_interval))
    empty_membership = copy.deepcopy(job_memory)
    empty_membership["samples"][0]["process_ids"] = []
    corruptions.append((evidence, empty_membership))
    failed_terminal = copy.deepcopy(evidence)
    terminal = next(
        sample
        for sample in failed_terminal["samples"]
        if sample["class"] == "terminal_record"
    )
    terminal["record_state"] = "failed"
    terminal["event_result"]["filesystem"] = "failed"
    terminal["event_result"]["headline"] = "failed"
    corruptions.append((failed_terminal, job_memory))
    bunched_reliable = copy.deepcopy(evidence)
    bunched_reliable["producer_task_0"]["reliable_by_second"] = [150, *([0] * 59)]
    corruptions.append((bunched_reliable, job_memory))
    wrong_runtime = copy.deepcopy(evidence)
    wrong_runtime["runtime"]["packages"]["pywebview"] = "6.2.2"
    corruptions.append((wrong_runtime, job_memory))
    missing_server = copy.deepcopy(evidence)
    missing_server["runtime"]["packages"]["bottle"] = ""
    corruptions.append((missing_server, job_memory))
    over_memory = copy.deepcopy(job_memory)
    for sample in over_memory["samples"]:
        if sample["phase"] == "fixture":
            sample["private_bytes"] = 100_000 + 16 * 1024 * 1024 + 1
    over_memory = benchmark._job_memory_result(
        over_memory["samples"],
        fixture_ended_at_seconds=over_memory["fixture_ended_at_seconds"],
        root_process_id=123,
    )
    corruptions.append((evidence, over_memory))
    slow_reliable = copy.deepcopy(evidence)
    reliable_sample = next(
        sample
        for sample in slow_reliable["samples"]
        if sample["class"] == "reliable"
    )
    reliable_sample["latency_ms"] = 251
    corruptions.append((slow_reliable, job_memory))
    slow_progress = copy.deepcopy(evidence)
    progress_sample = next(
        sample
        for sample in slow_progress["samples"]
        if sample["class"] == "progress"
    )
    progress_sample["latency_ms"] = 2_001
    corruptions.append((slow_progress, job_memory))
    slow_reliable_p95 = copy.deepcopy(evidence)
    reliable_samples = [
        sample
        for sample in slow_reliable_p95["samples"]
        if sample["class"]
        in {"reliable", "terminal_event", "terminal_record"}
    ]
    for sample in reliable_samples[: max(1, len(reliable_samples) // 10)]:
        sample["latency_ms"] = 101
    corruptions.append((slow_reliable_p95, job_memory))
    slow_progress_p95 = copy.deepcopy(evidence)
    progress_samples = [
        sample
        for sample in slow_progress_p95["samples"]
        if sample["class"] == "progress"
    ]
    for sample in progress_samples[: max(1, len(progress_samples) // 10)]:
        sample["latency_ms"] = 1_001
    corruptions.append((slow_progress_p95, job_memory))
    late_completion = copy.deepcopy(evidence)
    completed_index = next(
        index
        for index, sample in enumerate(late_completion["samples"])
        if sample["event_id"] == "StateChanged"
        and sample["event_result"] == {"state": "completed"}
    )
    completed = late_completion["samples"].pop(completed_index)
    progress_index = max(
        index
        for index, sample in enumerate(late_completion["samples"])
        if sample["session_id"] == completed["session_id"]
        and sample["class"] == "progress"
    )
    late_completion["samples"].insert(progress_index, completed)
    session_samples = [
        sample
        for sample in late_completion["samples"]
        if sample["session_id"] == completed["session_id"]
    ]
    next_event = session_samples[session_samples.index(completed) + 1]
    completed["observed_offset_ms"] = next_event["observed_offset_ms"] - 1
    next_sequence = 1
    for sample in session_samples:
        if sample["class"] != "terminal_record":
            sample["sequence"] = next_sequence
            next_sequence += 1
    corruptions.append((late_completion, job_memory))

    for corrupted_evidence, corrupted_memory in corruptions:
        result = benchmark._summarize(
            corrupted_evidence,
            benchmark_root=ROOT,
            commit="a" * 40,
            status=(),
            job_memory=corrupted_memory,
        )
        assert result["passed"] is False
