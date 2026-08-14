"""Ordinary contract checks for the opt-in installed-wheel event benchmark."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Condition, Lock
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[2]
PARENT = ROOT / "bridge_event_benchmark.py"
CHILD = Path(__file__).with_name("_bridge_event_benchmark_child.py")
RETAINED = Path(__file__).with_name("_bridge_retained_memory.py")
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


def _child_module():
    specification = importlib.util.spec_from_file_location(
        "bridge_event_benchmark_child_contract",
        CHILD,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _retained_module():
    specification = importlib.util.spec_from_file_location(
        "bridge_retained_memory_contract",
        RETAINED,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_bridge_event_benchmark_sources_compile_and_keep_test_seams_external() -> None:
    parent = PARENT.read_text(encoding="utf-8")
    child = CHILD.read_text(encoding="utf-8")
    retained = RETAINED.read_text(encoding="utf-8")
    browser = (ASSETS / "benchmark.js").read_text(encoding="utf-8")

    compile(parent, str(PARENT), "exec")
    compile(child, str(CHILD), "exec")
    compile(retained, str(RETAINED), "exec")
    assert "git archive" in parent
    assert "pip\",\n            \"wheel" in parent
    assert "WorkflowRegistration" in child
    assert "TaskRegistry" not in browser
    assert 'from "./bridge.js"' in browser
    assert 'from "./render.js"' in browser
    assert "evaluate_js" not in parent
    assert "evaluate_js" not in child
    assert "evaluate_js" not in browser
    assert "SAMPLE_REPORT_BATCH_SIZE = 100" in browser
    assert "MAX_PENDING_ORDINARY_SAMPLE_REPORTS = 4" in browser
    assert "MAX_PENDING_SAMPLE_REPORTS = 16" in browser
    assert 'sampleClass === "terminal_event"' in browser
    assert "failure_source:" in browser
    assert "report_completed:" in browser
    assert "retainedBytes" not in browser
    assert "PrivateUsage" in parent
    assert "_QueueMemorySampler" not in child
    assert "append_producer_timings" in child
    assert "start_headed_process" not in parent
    assert '"--admission-gate"' in parent
    assert 'kind: "ready"' in browser
    assert 'void enqueueReport("presented", null).catch' in browser
    assert "wait_for_accessible_text" not in parent
    complete = browser.index('await enqueueReport("complete"')
    rendered = browser.index('renderText(status, "Benchmark complete', complete)
    presented = browser.index('void enqueueReport("presented"', rendered)
    assert complete < rendered < presented
    terminal_preflush = browser.index(
        'sampleClass === "terminal_event" || sampleClass === "terminal_record"'
    )
    assert terminal_preflush < browser.index("samples.push(sample)")
    assert browser.count("flushSamples(true)") == 1
    assert 'sampleClass === "terminal_event" || sampleClass === "terminal_record",' in browser


def test_bridge_event_benchmark_assigns_actual_child_before_admission(
    monkeypatch,
    tmp_path: Path,
) -> None:
    benchmark = _benchmark_module()

    class Kernel:
        def __init__(self) -> None:
            self.calls = []

        def CreateEventW(self, *_args):
            self.calls.append("create-event")
            return 10

        def CreateJobObjectW(self, *_args):
            self.calls.append("create-job")
            return 20

        def SetInformationJobObject(self, *_args):
            self.calls.append("configure-job")
            return True

        def AssignProcessToJobObject(self, *_args):
            self.calls.append("assign")
            return True

        def SetEvent(self, *_args):
            self.calls.append("signal")
            return True

        def CloseHandle(self, handle):
            self.calls.append(("close", handle))
            return True

    class Process:
        pid = 123
        _handle = 30

        def poll(self):
            return None

    kernel = Kernel()
    process = Process()
    launched = {}

    def popen(command, **options):
        launched["command"] = command
        launched["options"] = options
        return process

    monkeypatch.setattr(benchmark, "_kernel32", lambda: kernel)
    monkeypatch.setattr(benchmark.subprocess, "Popen", popen)
    headed = benchmark._start_direct_job_process(
        ["python.exe", "child.py"],
        cwd=tmp_path,
        environment={"PYTHONUTF8": "1"},
        deadline=SimpleNamespace(remaining=lambda: 30.0),
    )

    assert headed.process is process
    assert launched["command"][:2] == ("python.exe", "child.py")
    assert "--admission-gate" in launched["command"]
    assert kernel.calls.index("assign") < kernel.calls.index("signal")
    assert launched["options"]["cwd"] == tmp_path


def test_bridge_event_benchmark_checks_deadline_before_allocating_handles(
    monkeypatch,
    tmp_path: Path,
) -> None:
    benchmark = _benchmark_module()
    kernel_requested = False

    def kernel32():
        nonlocal kernel_requested
        kernel_requested = True
        raise AssertionError("kernel APIs must not be reached")

    def expired():
        raise AssertionError("deadline expired")

    monkeypatch.setattr(benchmark, "_kernel32", kernel32)

    with pytest.raises(AssertionError, match="deadline expired"):
        benchmark._start_direct_job_process(
            ["python.exe", "child.py"],
            cwd=tmp_path,
            environment={},
            deadline=SimpleNamespace(remaining=expired),
        )

    assert kernel_requested is False


@pytest.mark.parametrize("failure", ["early-exit", "assignment"])
def test_bridge_event_benchmark_direct_admission_cleans_up_failures(
    monkeypatch,
    tmp_path: Path,
    failure: str,
) -> None:
    benchmark = _benchmark_module()

    class Kernel:
        def __init__(self) -> None:
            self.calls = []

        def CreateEventW(self, *_args):
            return 10

        def CreateJobObjectW(self, *_args):
            return 20

        def SetInformationJobObject(self, *_args):
            return True

        def AssignProcessToJobObject(self, *_args):
            self.calls.append("assign")
            return failure != "assignment"

        def SetEvent(self, *_args):
            self.calls.append("signal")
            return True

        def CloseHandle(self, handle):
            self.calls.append(("close", handle))
            return True

    class Process:
        pid = 123
        _handle = 30

        def __init__(self) -> None:
            self.killed = False
            self.communicated = False

        def poll(self):
            if failure == "early-exit":
                return 9
            return -9 if self.killed else None

        def kill(self):
            self.killed = True

        def communicate(self, *, timeout):
            assert timeout == 5.0
            self.communicated = True
            return "", ""

    kernel = Kernel()
    process = Process()
    monkeypatch.setattr(benchmark, "_kernel32", lambda: kernel)
    monkeypatch.setattr(
        benchmark.subprocess,
        "Popen",
        lambda *_args, **_kwargs: process,
    )

    expected = RuntimeError if failure == "early-exit" else OSError
    with pytest.raises(expected):
        benchmark._start_direct_job_process(
            ["python.exe", "child.py"],
            cwd=tmp_path,
            environment={},
            deadline=SimpleNamespace(remaining=lambda: 30.0),
        )

    assert process.communicated is True
    assert process.killed is (failure == "assignment")
    assert ("close", 10) in kernel.calls
    assert ("close", 20) in kernel.calls
    assert "signal" not in kernel.calls


def test_retained_state_sizer_separates_terminal_results_and_queue_roots() -> None:
    from namisync.core.events import SCHEMA_VERSION, Envelope, ItemOutcome, Terminal
    from namisync.core.evidence import Outcome
    from namisync.core.session import OperationResult, SessionState
    from namisync.workflows.views import (
        SessionEventView,
        SessionRecordView,
        operation_result_view,
    )

    retained = _retained_module()

    def measure(shared_text: str, terminal_text: str):
        result = OperationResult(
            SessionState.COMPLETED,
            items=(
                ItemOutcome(
                    item_id="item-1",
                    kind="copy",
                    path="terminal/path.bin",
                    outcome=Outcome.SUCCEEDED,
                    detail={"message": terminal_text},
                ),
            ),
        )
        terminal_envelope = Envelope(
            session_id=shared_text,
            seq=2,
            at=datetime.now(timezone.utc),
            schema_version=SCHEMA_VERSION,
            body=Terminal(result),
        )
        nonterminal = SessionEventView(
            shared_text,
            1,
            "2026-08-14T00:00:00+00:00",
            "Progress",
            {
                "current_path": shared_text,
                "items_done": 1,
                "items_total": 2,
            },
        )
        terminal_event = SessionEventView(
            shared_text,
            2,
            "2026-08-14T00:00:01+00:00",
            "Terminal",
            {"result": {"items": [terminal_text]}},
        )
        record = SessionRecordView(
            shared_text,
            "sync-plan",
            "completed",
            False,
            "2026-08-14T00:00:00+00:00",
            "2026-08-14T00:00:00+00:00",
            "2026-08-14T00:00:01+00:00",
            operation_result_view(result),
        )
        task = SimpleNamespace(
            condition=Condition(),
            queue=deque((nonterminal, terminal_event, record)),
            terminal_record=record,
        )
        stream = SimpleNamespace(
            _condition=Condition(),
            _items=deque((terminal_envelope,)),
        )
        hub = SimpleNamespace(
            _lock=Lock(),
            _replay=deque((terminal_envelope,)),
            _subscribers=[stream],
        )
        registry = SimpleNamespace(
            _condition=Condition(),
            _tasks={"task": task},
        )
        dispatcher = SimpleNamespace(
            _condition=Condition(),
            _hubs={"session": hub},
        )
        return retained.measure_retained_bridge_state(dispatcher, registry)

    small = measure("shared-session", "terminal")
    large_terminal = measure("shared-session", "terminal" * 2_000)
    shared_long = measure("shared-session" * 300, "terminal")

    assert large_terminal["transport_custody_bytes"] == small[
        "transport_custody_bytes"
    ]
    assert large_terminal["terminal_artifact_bytes"] > small[
        "terminal_artifact_bytes"
    ]
    assert shared_long["transport_custody_bytes"] > small[
        "transport_custody_bytes"
    ]
    assert shared_long["terminal_artifact_bytes"] > small[
        "terminal_artifact_bytes"
    ]
    assert small["transport_custody_bytes"] < sum(
        small[name]
        for name in (
            "adapter_queue_bytes",
            "replay_queue_bytes",
            "subscriber_queue_bytes",
        )
    )
    assert all(
        small[name] > 0
        for name in (
            "adapter_queue_bytes",
            "replay_queue_bytes",
            "subscriber_queue_bytes",
            "terminal_artifact_bytes",
            "transport_custody_bytes",
        )
    )


def test_retained_state_sizer_refuses_unknown_graph_types() -> None:
    retained = _retained_module()

    class Unsupported:
        pass

    task = SimpleNamespace(
        condition=Condition(),
        queue=deque((Unsupported(),)),
        terminal_record=None,
    )
    registry = SimpleNamespace(
        _condition=Condition(),
        _tasks={"task": task},
    )
    dispatcher = SimpleNamespace(
        _condition=Condition(),
        _hubs={},
    )

    with pytest.raises(TypeError, match=r"\.Unsupported$"):
        retained.measure_retained_bridge_state(dispatcher, registry)

    class RetainedText(str):
        pass

    task.queue = deque((RetainedText("scalar subclass with hidden state"),))
    with pytest.raises(TypeError, match=r"\.RetainedText$"):
        retained.measure_retained_bridge_state(dispatcher, registry)


def test_retained_state_sizer_requires_a_quiescent_fixture() -> None:
    retained = _retained_module()
    queue = deque(("first",))

    class MutatingCondition:
        def __init__(self) -> None:
            self.exits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.exits += 1
            if self.exits == 1:
                queue.append("second")

    task = SimpleNamespace(
        condition=MutatingCondition(),
        queue=queue,
        terminal_record=None,
    )
    registry = SimpleNamespace(
        _condition=Condition(),
        _tasks={"task": task},
    )
    dispatcher = SimpleNamespace(
        _condition=Condition(),
        _hubs={},
    )

    with pytest.raises(RuntimeError, match="not quiescent: adapter queues"):
        retained.measure_retained_bridge_state(dispatcher, registry)


def test_bridge_event_benchmark_uses_immutable_handshake_markers(
    tmp_path: Path,
) -> None:
    child = _child_module()
    output = tmp_path / "evidence.json"
    recorder = child._Recorder(output)
    begin = tmp_path / "benchmark.begin"
    ready = tmp_path / "benchmark.ready"
    report = tmp_path / "benchmark.report"
    failure = tmp_path / "benchmark.failure"
    presented = tmp_path / "benchmark.presented"
    begin.write_bytes(b"")
    spec = child._benchmark_specs(
        object(),
        (),
        recorder,
        begin,
        ready,
        report,
        failure,
        presented,
    )["benchmark_report"]

    sample = {
        "class": "progress",
        "event_id": "Progress",
        "event_result": None,
        "latency_ms": 1,
        "observed_offset_ms": 1,
        "position": 1,
        "record_state": None,
        "session_id": "f" * 32,
        "sequence": 1,
    }
    with pytest.raises(ValueError, match="benchmark report payload is invalid"):
        spec.validate_payload({"kind": "samples", "value": []})
    with pytest.raises(ValueError, match="benchmark report payload is invalid"):
        spec.validate_payload({"kind": "samples", "value": [sample] * 101})

    assert spec.invoke({"kind": "ready", "value": None}) == {"accepted": True}
    assert spec.invoke({"kind": "complete", "value": {}}) == {"accepted": True}
    assert spec.invoke({"kind": "presented", "value": None}) == {
        "accepted": True
    }

    assert ready.is_file()
    assert report.is_file()
    assert presented.is_file()
    assert not failure.exists()
    assert not output.exists()

    failed_report = tmp_path / "failed.report"
    failed_marker = tmp_path / "failed.failure"
    failed_spec = child._benchmark_specs(
        object(),
        (),
        child._Recorder(tmp_path / "failed-evidence.json"),
        begin,
        tmp_path / "failed.ready",
        failed_report,
        failed_marker,
        tmp_path / "failed.presented",
    )["benchmark_report"]
    assert failed_spec.invoke(
        {"kind": "complete", "value": {"failure": "BridgeTransportError"}}
    ) == {"accepted": True}
    assert failed_marker.is_file()
    assert not failed_report.exists()


def test_bridge_event_benchmark_streams_and_authenticates_live_evidence(
    tmp_path: Path,
) -> None:
    child = _child_module()
    benchmark = _benchmark_module()
    output = tmp_path / "evidence.json"
    recorder = child._Recorder(output)
    first = {"sample": 1}
    second = {"sample": 2}

    recorder.append_samples([first, second])
    for task_index in range(4):
        recorder.append_producer_timings(
            task_index,
            progress=[task_index + 0.1],
            reliable=[task_index + 0.2],
        )
        recorder.write_producer(task_index, {"task_index": task_index})
    recorder.set("complete", True)
    recorder.write()

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert "samples" not in manifest
    assert not any(name.startswith("producer_task_") for name in manifest)
    attached = benchmark._attach_streamed_evidence(manifest, output)
    assert attached["samples"] == [first, second]
    assert [attached[f"producer_task_{index}"]["task_index"] for index in range(4)] == [
        0,
        1,
        2,
        3,
    ]
    assert attached["producer_task_3"]["progress_emission_offsets_seconds"] == [
        3.1
    ]
    assert attached["producer_task_3"]["reliable_emission_offsets_seconds"] == [
        3.2
    ]

    sample_stream = output.with_suffix(output.suffix + ".samples.jsonl")
    sample_stream.write_bytes(sample_stream.read_bytes() + b"{}")
    with pytest.raises(RuntimeError, match="partial batch"):
        benchmark._attach_streamed_evidence(manifest, output)
    with pytest.raises(ValueError, match="1..100"):
        recorder.append_samples([])


def test_bridge_event_benchmark_worst_case_report_batches_fit_ingress() -> None:
    ordinary_samples = [
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
        for _ in range(100)
    ]
    terminal_result = {
        "headline": "completed",
        "filesystem": "succeeded",
        "integrity": "not-run",
        "recording": "succeeded",
        "audit": "not-run",
        "disposition": "completed",
        "canceled": False,
        "phase_count": 0,
        "bytes_done": 1_500,
        "bytes_total": 1_500,
        "items": [
            [f"task-3-item-{item // 3:02d}-{item % 3}", "succeeded"]
            for item in range(150)
        ],
        "error": None,
    }
    terminal_sample = {
        "class": "terminal_record",
        "event_id": "record",
        "event_result": terminal_result,
        "latency_ms": 249.999,
        "observed_offset_ms": 59_999.999,
        "position": None,
        "record_state": "completed",
        "session_id": "f" * 32,
        "sequence": None,
    }

    def encoded(samples):
        request = {
            "schema_version": 1,
            "request_id": "f" * 32,
            "command": "benchmark_report",
            "payload": {"kind": "samples", "value": samples},
        }
        return json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    assert len(encoded(ordinary_samples)) <= 65_536
    assert len(encoded([terminal_sample])) <= 65_536
    assert len(encoded([*ordinary_samples, terminal_sample])) <= 65_536
    legacy_residue = [ordinary_samples[0]] * 249
    assert len(encoded([*legacy_residue, *([terminal_sample] * 8)])) > 65_536


def test_bridge_event_benchmark_reads_current_process_resource_evidence() -> None:
    benchmark = _benchmark_module()
    process_id = os.getpid()

    private_bytes = benchmark._process_private_bytes(process_id)
    metadata = benchmark._process_metadata(
        process_id,
        root_process_id=process_id,
    )
    resources = benchmark._process_resource_snapshot((process_id,))

    assert type(private_bytes) is int
    assert private_bytes > 0
    assert metadata is not None
    assert metadata["command_role"] == "python-host"
    assert metadata["creation_time_100ns"] > 0
    assert resources is not None
    assert resources[process_id]["handle_count"] > 0
    assert resources[process_id]["thread_count"] > 0
    assert benchmark._classify_process_role(
        process_id + 1,
        root_process_id=process_id,
        image_path=r"C:\WebView2\msedgewebview2.exe",
        command_line="msedgewebview2.exe --type=renderer",
    ) == "webview2-renderer"
    assert benchmark._classify_process_role(
        process_id + 1,
        root_process_id=process_id,
        image_path=r"C:\WebView2\msedgewebview2.exe",
        command_line=None,
    ) == "unknown:webview2-command-line-unavailable"
    assert benchmark._classify_process_role(
        process_id + 1,
        root_process_id=process_id,
        image_path=r"C:\WebView2\msedgewebview2.exe",
        command_line="msedgewebview2.exe",
    ) == "webview2-browser"


def test_bridge_event_benchmark_sampler_contains_diagnostic_api_failures() -> None:
    benchmark = _benchmark_module()

    class Process:
        pid = 123

        @staticmethod
        def process_ids():
            raise OSError("job query unavailable")

    sampler = benchmark._JobPrivateMemorySampler(Process())

    sampler.sample("baseline")
    sampler.sample("fixture")
    result = sampler.result()

    assert result["all_samples_complete"] is False
    assert result["diagnostic_errors"] == [
        {
            "elapsed_seconds": result["samples"][0]["elapsed_seconds"],
            "error": "OSError: job query unavailable",
            "phase": "baseline",
        }
    ]
    assert result["samples"][1]["diagnostic_error"] is None


def test_bridge_event_benchmark_resource_failure_retries_at_one_hz(
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    calls = 0

    class Process:
        pid = 123

        @staticmethod
        def process_ids():
            return {123}

    def resources(_process_ids):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(benchmark, "_process_private_bytes", lambda _pid: 100)
    monkeypatch.setattr(
        benchmark,
        "_process_metadata",
        lambda _pid, *, root_process_id: {
            "command_role": "python-host",
            "creation_time_100ns": 1,
            "image_name": "python.exe",
            "process_id": root_process_id,
        },
    )
    monkeypatch.setattr(benchmark, "_process_resource_snapshot", resources)
    sampler = benchmark._JobPrivateMemorySampler(Process())

    sampler.sample("baseline")
    sampler.sample("baseline")

    assert calls == 1


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
        "browser_presented": True,
        "complete": True,
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
            "diagnostic_error": None,
            "elapsed_seconds": index * 0.02,
            "missing_process_ids": [],
            "phase": "baseline" if index < 50 else "fixture",
            "private_bytes": 100_000 if index < 50 else 104_000,
            "private_bytes_by_process": {
                "123": 100_000 if index < 50 else 104_000,
            },
            "process_ids": [123],
        }
        for index in range(3_050)
    ]
    job_memory = benchmark._job_memory_result(
        raw_memory,
        fixture_ended_at_seconds=60.99,
        processes={
            "123": {
                "command_role": "python-host",
                "creation_time_100ns": 1,
                "image_name": "python.exe",
                "process_id": 123,
            },
        },
        resource_samples=[
            {
                "elapsed_seconds": index * 0.02,
                "phase": "baseline" if index < 50 else "fixture",
                "processes": {
                    "123": {"handle_count": 10, "thread_count": 2},
                },
            }
            for index in range(0, 3_050, 50)
        ],
        root_process_id=123,
        topology_transitions=[
            {
                "elapsed_seconds": 0.0,
                "exited_process_ids": [],
                "joined_process_ids": [123],
            },
        ],
    )
    return evidence, job_memory


def test_bridge_event_benchmark_requires_resource_cadence_across_fixture() -> None:
    benchmark = _benchmark_module()
    _evidence, complete = _passing_evidence(benchmark)
    sparse = benchmark._job_memory_result(
        complete["samples"],
        fixture_ended_at_seconds=complete["fixture_ended_at_seconds"],
        processes=complete["processes"],
        resource_samples=[
            complete["resource_samples"][0],
            complete["resource_samples"][-1],
        ],
        root_process_id=complete["root_process_id"],
        topology_transitions=complete["topology_transitions"],
    )

    assert complete["all_samples_complete"] is True
    assert sparse["all_samples_complete"] is False


def test_bridge_event_benchmark_summary_enforces_event_contract(
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
    assert result["event_passed"] is True
    assert result["gate"] == (
        "SH-G-8 event limb / BR-G-42 bridge event envelope"
    )
    assert result["sh_g_8_acceptance"] == "incomplete-without-custody"
    assert result["memory"]["whole_runtime_diagnostics_complete"] is True
    assert result["memory"]["whole_runtime_acceptance"] == "not-defined"
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


def test_bridge_event_benchmark_reports_runtime_diagnostic_refusal_separately(
    monkeypatch,
) -> None:
    benchmark = _benchmark_module()
    monkeypatch.setattr(
        benchmark,
        "_machine",
        lambda _root: {"machine": "test", "reference_profile_match": True},
    )
    evidence, job_memory = _passing_evidence(benchmark)
    diagnostic_refusals = []

    incomplete = dict(job_memory, all_samples_complete=False)
    diagnostic_refusals.append(incomplete)
    blind = dict(job_memory, max_sample_interval_seconds=0.5)
    diagnostic_refusals.append(blind)
    per_process_mismatch = copy.deepcopy(job_memory)
    per_process_mismatch["samples"][0]["private_bytes_by_process"]["123"] += 1
    diagnostic_refusals.append(per_process_mismatch)
    missing_role = copy.deepcopy(job_memory)
    missing_role["processes"]["123"].pop("command_role")
    diagnostic_refusals.append(missing_role)
    missing_resource = copy.deepcopy(job_memory)
    missing_resource["resource_samples"] = []
    diagnostic_refusals.append(missing_resource)
    wrong_topology = copy.deepcopy(job_memory)
    wrong_topology["topology_transitions"][0]["joined_process_ids"] = []
    diagnostic_refusals.append(wrong_topology)

    for refused_memory in diagnostic_refusals:
        result = benchmark._summarize(
            evidence,
            benchmark_root=ROOT,
            commit="a" * 40,
            status=(),
            job_memory=refused_memory,
        )
        assert result["passed"] is True
        assert result["event_passed"] is True
        assert result["memory"]["whole_runtime_diagnostics_complete"] is False
        assert result["memory"]["whole_runtime_acceptance"] == "not-defined"

    large = copy.deepcopy(job_memory)
    large_private_bytes = 100_000 + 64 * 1024 * 1024
    for sample in large["samples"]:
        if sample["phase"] == "fixture":
            sample["private_bytes"] = large_private_bytes
            sample["private_bytes_by_process"]["123"] = large_private_bytes
    large = benchmark._job_memory_result(
        large["samples"],
        fixture_ended_at_seconds=large["fixture_ended_at_seconds"],
        processes=large["processes"],
        resource_samples=large["resource_samples"],
        root_process_id=123,
        topology_transitions=large["topology_transitions"],
    )
    result = benchmark._summarize(
        evidence,
        benchmark_root=ROOT,
        commit="a" * 40,
        status=(),
        job_memory=large,
    )
    assert result["passed"] is True
    assert result["memory"]["whole_runtime_diagnostics_complete"] is True
    assert large["incremental_peak_private_bytes"] == 64 * 1024 * 1024


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
    unpresented = copy.deepcopy(evidence)
    unpresented["browser_presented"] = False
    corruptions.append((unpresented, job_memory))
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
