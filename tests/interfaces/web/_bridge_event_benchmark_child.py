"""Installed-wheel child for the opt-in 60-second bridge event benchmark."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import sqlite3
import sys
import threading
from contextlib import ExitStack
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, perf_counter, sleep
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from _startup_test_support import headed_command_extension


_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258


@dataclass(frozen=True, slots=True)
class _Payload:
    kind: str
    value: object


class _Recorder:
    def __init__(self, output: Path) -> None:
        self._output = output
        self._samples_output = output.with_suffix(output.suffix + ".samples.jsonl")
        self._lock = threading.Lock()
        self._sample_digest = hashlib.sha256()
        self._sample_batch_count = 0
        self._sample_count = 0
        self._producer_timing_digests: dict[int, Any] = {}
        self._producer_timing_batch_counts: dict[int, int] = {}
        self._producer_timing_progress_counts: dict[int, int] = {}
        self._producer_timing_reliable_counts: dict[int, int] = {}
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "complete": False,
            "producer_streams": {},
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def append_samples(self, samples: list[dict[str, object]]) -> None:
        if not samples or len(samples) > 100:
            raise ValueError("benchmark sample batches must contain 1..100 items")
        encoded = (
            json.dumps(samples, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        with self._lock:
            with self._samples_output.open("ab") as stream:
                stream.write(encoded)
            self._sample_digest.update(encoded)
            self._sample_batch_count += 1
            self._sample_count += len(samples)

    def startup_error(self, message: str) -> None:
        with self._lock:
            self._data["startup_errors"].append(message)

    def append_producer_timings(
        self,
        task_index: int,
        *,
        progress: list[float],
        reliable: list[float],
    ) -> None:
        if not progress or len(progress) > 125 or len(reliable) > 125:
            raise ValueError(
                "producer timing batches must contain 1..125 progress items"
            )
        encoded = (
            json.dumps(
                {"progress": progress, "reliable": reliable},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        path = self._output.with_suffix(
            self._output.suffix + f".producer-{task_index}.timings.jsonl"
        )
        with self._lock:
            with path.open("ab") as stream:
                stream.write(encoded)
            digest = self._producer_timing_digests.setdefault(
                task_index,
                hashlib.sha256(),
            )
            digest.update(encoded)
            self._producer_timing_batch_counts[task_index] = (
                self._producer_timing_batch_counts.get(task_index, 0) + 1
            )
            self._producer_timing_progress_counts[task_index] = (
                self._producer_timing_progress_counts.get(task_index, 0)
                + len(progress)
            )
            self._producer_timing_reliable_counts[task_index] = (
                self._producer_timing_reliable_counts.get(task_index, 0)
                + len(reliable)
            )

    def write_producer(self, task_index: int, value: dict[str, object]) -> None:
        encoded = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        path = self._output.with_suffix(
            self._output.suffix + f".producer-{task_index}.json"
        )
        with self._lock:
            digest = self._producer_timing_digests.get(task_index)
            if digest is None:
                raise RuntimeError("producer timing stream is missing")
            path.write_bytes(encoded)
            self._data["producer_streams"][str(task_index)] = {
                "byte_count": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "timings": {
                    "batch_count": self._producer_timing_batch_counts[task_index],
                    "progress_count": self._producer_timing_progress_counts[task_index],
                    "reliable_count": self._producer_timing_reliable_counts[task_index],
                    "sha256": digest.hexdigest(),
                },
            }

    def write(self) -> None:
        with self._lock:
            self._data["sample_stream"] = {
                "batch_count": self._sample_batch_count,
                "sample_count": self._sample_count,
                "sha256": self._sample_digest.hexdigest(),
            }
            encoded = json.dumps(self._data, indent=2, sort_keys=True)
            temporary = self._output.with_suffix(self._output.suffix + ".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(self._output)


class _FixtureClock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at: float | None = None

    def begin(self) -> None:
        with self._lock:
            if self._started_at is not None:
                raise RuntimeError("benchmark fixture clock started twice")
            self._started_at = perf_counter()

    def started_at(self) -> float:
        with self._lock:
            if self._started_at is None:
                raise RuntimeError("benchmark fixture clock has not started")
            return self._started_at


class _BenchmarkInvocation:
    def __init__(
        self,
        task_index: int,
        start_barrier: threading.Barrier,
        fixture_clock: _FixtureClock,
        recorder: _Recorder,
    ) -> None:
        self._task_index = task_index
        self._start_barrier = start_barrier
        self._fixture_clock = fixture_clock
        self._recorder = recorder

    def run(self, context):
        from namisync.core.events import ItemOutcome, Progress
        from namisync.core.evidence import Outcome
        from namisync.core.session import OperationResult, SessionState

        reliable_per_second = (3, 3, 2, 2)
        self._start_barrier.wait(10)
        started = self._fixture_clock.started_at()
        progress_emissions = 0
        reliable_emissions = 0
        first_emission_at: float | None = None
        last_emission_at: float | None = None
        reliable_by_second = [0] * 60
        pending_progress_offsets = []
        pending_reliable_offsets = []
        for tick in range(1_500):
            due = started + (tick * 0.04)
            remaining = due - perf_counter()
            if remaining > 0:
                sleep(remaining)
            completed = tick + 1
            context.emit(
                Progress(
                    items_done=completed,
                    items_total=1_500,
                    bytes_done=completed,
                    bytes_total=1_500,
                    current_path=f"task-{self._task_index}/progress-{completed}",
                )
            )
            emitted_at = perf_counter()
            pending_progress_offsets.append(emitted_at - started)
            progress_emissions += 1
            if first_emission_at is None:
                first_emission_at = emitted_at
            last_emission_at = emitted_at
            second, within_second = divmod(tick, 25)
            reliable_count = reliable_per_second[
                (self._task_index + second) % 4
            ]
            reliable_ticks = {
                ((item_index + 1) * 25) // (reliable_count + 1)
                for item_index in range(reliable_count)
            }
            if within_second in reliable_ticks:
                item_index = sorted(reliable_ticks).index(within_second)
                context.emit(
                    ItemOutcome(
                        item_id=(
                            f"task-{self._task_index}-item-"
                            f"{second:02d}-{item_index}"
                        ),
                        kind="copy",
                        path=(
                            f"task-{self._task_index}/"
                            f"file-{second:02d}-{item_index}.bin"
                        ),
                        outcome=Outcome.SUCCEEDED,
                    )
                )
                reliable_emissions += 1
                reliable_by_second[second] += 1
                last_emission_at = perf_counter()
                pending_reliable_offsets.append(
                    last_emission_at - started
                )
            if completed % 125 == 0:
                self._recorder.append_producer_timings(
                    self._task_index,
                    progress=pending_progress_offsets,
                    reliable=pending_reliable_offsets,
                )
                pending_progress_offsets = []
                pending_reliable_offsets = []
        finished_at = perf_counter()
        self._recorder.write_producer(
            self._task_index,
            {
                "elapsed_seconds": finished_at - started,
                "first_emission_offset_seconds": (
                    first_emission_at - started
                    if first_emission_at is not None
                    else None
                ),
                "last_emission_offset_seconds": (
                    last_emission_at - started
                    if last_emission_at is not None
                    else None
                ),
                "progress_emissions": progress_emissions,
                "reliable_by_second": reliable_by_second,
                "reliable_emissions": reliable_emissions,
            },
        )
        return OperationResult(
            SessionState.COMPLETED,
            bytes_done=1_500,
            bytes_total=1_500,
        )

    def snapshot(self) -> bytes:
        return str(self._task_index).encode("ascii")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission-gate", required=True)
    parser.add_argument("--admission-timeout-ms", required=True, type=int)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _wait_for_named_gate(name: str, *, timeout_ms: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenEventW(_SYNCHRONIZE, False, name)
    if not handle:
        return False
    try:
        result = int(kernel32.WaitForSingleObject(handle, timeout_ms))
        if result == _WAIT_OBJECT_0:
            return True
        if result == _WAIT_TIMEOUT:
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def _benchmark_specs(
    registry: object,
    roots: tuple[tuple[str, str], ...],
    recorder: _Recorder,
    begin_marker: Path,
    ready_marker: Path,
    report_marker: Path,
    failure_marker: Path,
    presented_marker: Path,
):
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandPayloadError,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )

    def validate_start(payload: object) -> _Payload:
        if type(payload) is not dict or payload:
            raise CommandPayloadError("benchmark start payload is invalid")
        return _Payload("start", None)

    def start(payload: object) -> object:
        if type(payload) is not _Payload or payload.kind != "start":
            raise TypeError("benchmark start received unvalidated data")
        starts = []
        for index, (source, target) in enumerate(roots):
            starts.append(
                registry.start_plan(
                    source,
                    target,
                    deletion_policy=None,
                    command_id=f"{index + 1:032x}",
                )
            )
        return tuple(starts)

    def validate_report(payload: object) -> _Payload:
        if type(payload) is not dict or set(payload) != {"kind", "value"}:
            raise CommandPayloadError("benchmark report payload is invalid")
        kind = payload["kind"]
        value = payload["value"]
        if (
            kind == "samples"
            and type(value) is list
            and 1 <= len(value) <= 100
        ):
            for sample in value:
                if (
                    type(sample) is not dict
                    or set(sample) != {
                        "class",
                        "event_id",
                        "event_result",
                        "latency_ms",
                        "observed_offset_ms",
                        "position",
                        "record_state",
                        "session_id",
                        "sequence",
                    }
                    or sample["class"] not in {
                        "progress",
                        "reliable",
                        "terminal_event",
                        "terminal_record",
                    }
                    or (
                        sample["event_id"] is not None
                        and type(sample["event_id"]) is not str
                    )
                    or type(sample["latency_ms"]) not in {int, float}
                    or type(sample["observed_offset_ms"]) not in {int, float}
                    or (
                        sample["position"] is not None
                        and type(sample["position"]) is not int
                    )
                    or type(sample["session_id"]) is not str
                    or (
                        sample["record_state"] is not None
                        and type(sample["record_state"]) is not str
                    )
                    or (
                        sample["sequence"] is not None
                        and type(sample["sequence"]) is not int
                    )
                ):
                    raise CommandPayloadError("benchmark sample is invalid")
            return _Payload(kind, value)
        if kind == "ready" and value is None:
            return _Payload(kind, value)
        if kind == "presented" and value is None:
            return _Payload(kind, value)
        if kind == "complete" and type(value) is dict:
            return _Payload(kind, MappingProxyType(dict(value)))
        raise CommandPayloadError("benchmark report payload is invalid")

    def report(payload: object) -> object:
        if type(payload) is not _Payload:
            raise TypeError("benchmark report received unvalidated data")
        if payload.kind == "samples":
            recorder.append_samples(payload.value)
            return {"accepted": len(payload.value)}
        if payload.kind == "ready":
            recorder.set("browser_ready", True)
            ready_marker.write_bytes(b"")
            deadline = monotonic() + 10
            while not begin_marker.exists():
                if monotonic() >= deadline:
                    raise TimeoutError("benchmark start handshake timed out")
                sleep(0.02)
            return {"accepted": True}
        if payload.kind == "presented":
            recorder.set("browser_presented", True)
            presented_marker.write_bytes(b"")
            return {"accepted": True}
        recorder.set("browser", dict(payload.value))
        recorder.set("browser_report_received", True)
        marker = (
            failure_marker
            if "failure" in payload.value
            else report_marker
        )
        marker.write_bytes(b"")
        return {"accepted": True}

    common = {
        "command_id": FieldRequirement.FORBIDDEN,
        "revision": FieldRequirement.FORBIDDEN,
        "timeout": CommandTimeout.INTERACTIVE,
        "retry": CommandRetry.NONE,
    }
    return {
        "benchmark_start": CommandSpec(
            validate_payload=validate_start,
            handler=start,
            access=CommandAccess.MUTATING,
            **common,
        ),
        "benchmark_report": CommandSpec(
            validate_payload=validate_report,
            handler=report,
            access=CommandAccess.READ_ONLY,
            **common,
        ),
    }


def main() -> int:
    arguments = _arguments()
    if not _wait_for_named_gate(
        arguments.admission_gate,
        timeout_ms=max(1, arguments.admission_timeout_ms),
    ):
        return 65
    recorder = _Recorder(arguments.output)
    recorder.set(
        "runtime",
        {
            "python": sys.version,
            "sqlite": sqlite3.sqlite_version,
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("bottle", "namisync", "pywebview", "pythonnet")
            },
        },
    )
    recorder.write()

    from namisync.dispatcher import Dispatcher, PreparedSession, WorkflowRegistration
    from namisync.interfaces import service as service_module
    from namisync.interfaces.service import NamiSyncService
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths
    from namisync.workflows import PLAN_KIND

    roots = []
    task_by_payload: dict[bytes, int] = {}
    for index in range(4):
        source = arguments.data_dir / "sources" / f"task-{index}"
        target = arguments.data_dir / "targets" / f"task-{index}"
        source.mkdir(parents=True)
        target.mkdir(parents=True)
        roots.append((str(source), str(target)))
        task_by_payload[str(source).encode("utf-8")] = index
    fixture_clock = _FixtureClock()
    start_barrier = threading.Barrier(4, action=fixture_clock.begin)
    begin_marker = arguments.data_dir / "benchmark.begin"
    ready_marker = arguments.data_dir / "benchmark.ready"
    report_marker = arguments.data_dir / "benchmark.report"
    failure_marker = arguments.data_dir / "benchmark.failure"
    presented_marker = arguments.data_dir / "benchmark.presented"

    def prepare(request) -> PreparedSession:
        payload = str(request.source_path).encode("utf-8")
        return PreparedSession(payload)

    def open_invocation(payload: bytes) -> _BenchmarkInvocation:
        return _BenchmarkInvocation(
            task_by_payload[payload],
            start_barrier,
            fixture_clock,
            recorder,
        )

    dispatcher = Dispatcher(
        {PLAN_KIND: WorkflowRegistration(prepare, open_invocation)}
    )
    original_create_service = host._create_service
    original_task_registry = host._task_registry
    original_log_renderer = host._log_startup_renderer

    def create_service(paths: AppPaths) -> NamiSyncService:
        with patch.object(service_module, "_dispatcher", lambda _runtime: dispatcher):
            return original_create_service(paths)

    def task_registry(service: object) -> object:
        return original_task_registry(service)

    def extension(_document: object, registry: object) -> object:
        return _benchmark_specs(
            registry,
            tuple(roots),
            recorder,
            begin_marker,
            ready_marker,
            report_marker,
            failure_marker,
            presented_marker,
        )

    def observe_composition(production: object, combined: object) -> None:
        recorder.set("production_command_names", sorted(production))
        recorder.set("combined_command_names", sorted(combined))
        recorder.write()

    def log_renderer(browser_version: str) -> None:
        import pythonnet

        recorder.set("clr_runtime", str(pythonnet.get_runtime_info()))
        recorder.set("webview2", browser_version)
        recorder.write()
        original_log_renderer(browser_version)

    exit_code = 1
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(host, "_create_service", create_service))
            stack.enter_context(patch.object(host, "_task_registry", task_registry))
            stack.enter_context(
                headed_command_extension(
                    host,
                    extension,
                    observe_composition=observe_composition,
                )
            )
            stack.enter_context(
                patch.object(host, "_log_startup_renderer", log_renderer)
            )
            exit_code = host.run_desktop(
                AppPaths.from_root(arguments.data_dir),
                DesktopInstanceIdentity(arguments.mutex, arguments.title),
                startup_error=recorder.startup_error,
                index_path=arguments.index,
            )
    finally:
        recorder.set("exit_code", exit_code)
        recorder.set("complete", True)
        recorder.write()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
