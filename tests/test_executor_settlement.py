"""Executor settlement, retry, and cancellation regression tests."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PureWindowsPath
from threading import Event
from typing import Callable

import pytest
from xxhash import xxh3_128

import namisync.modules.executor.runtime as executor_runtime
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome, Progress, Terminal, result_item_to_dict
from namisync.core.execution import (
    CopyDigest,
    ExecutionReason,
    ExecutionSet,
    RecordedCopyIdentity,
    Retry,
    Stop,
)
from namisync.core.models import FileStat
from namisync.core.pathing import to_extended_length_path
from namisync.core.planning import (
    OpId,
    OperationKind,
    OperationReason,
    PlanOperation,
)
from namisync.core.session import Canceled, PauseRequested, RunContext, SessionState
from namisync.modules.executor import (
    BoundedFailurePolicy,
    NativeCopyBackend,
    NativeFileSystem,
    execute,
)

from _executor_fixtures import (
    RUN_ID,
    FakeRecorder,
    _ControlLatch,
    _create_directory_reparse,
    _item_outcome,
    _make_readonly,
    _operation,
    _plan,
    _policies,
    _recorder_names,
    _nonbyte_mutation_operation,
    _require_directory_reparse,
    _readonly_update_setup,
    _reviewed_byte_operation,
    _roots,
    _run,
    _sharing_violation,
    _xset,
)


class FailingDirectoryFlushFileSystem(NativeFileSystem):
    def flush_directory(self, path: Path) -> bool:
        raise OSError("injected parent-directory flush failure")


def test_parent_directory_flush_error_records_nothing_after_publish(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"durable-content")
    fs = FailingDirectoryFlushFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.reason == "io-error"
    assert (target / "file.bin").read_bytes() == b"durable-content"
    assert recorder.calls == []


class ReplaceFaultFileSystem(NativeFileSystem):
    def __init__(self, *, after: bool) -> None:
        self.after = after

    def replace(self, temp: Path, target: Path) -> None:
        if self.after:
            super().replace(temp, target)
        raise OSError("injected replace fault")


class UnverifiableReplaceFaultFileSystem(NativeFileSystem):
    def __init__(self, target: Path) -> None:
        self.target = target
        self.published = False

    def replace(self, temp: Path, target: Path) -> None:
        super().replace(temp, target)
        self.published = True
        raise OSError("injected replace fault")

    def stat_path(self, path: Path) -> FileStat | None:
        if self.published and path == self.target:
            raise PermissionError("injected publication state probe failure")
        return super().stat_path(path)


@pytest.mark.parametrize("after", [False, True])
def test_update_fault_never_leaves_live_target_absent(tmp_path: Path, after: bool) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceFaultFileSystem(after=after)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == (
        b"new-version" if after else b"old-version"
    )
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []
    assert result.recording is (
        RecordingStatus.DEGRADED if after else RecordingStatus.OK
    )
    if after:
        item = _item_outcome(events)
        assert item.detail["publish_state"] == "published"
        assert item.detail["target_state"] == "published"
        assert item.detail["durable_state"] == "target-published-with-backup"


def test_unverifiable_publish_failure_degrades_recording(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    published_target = target / "file.bin"
    published_target.write_bytes(b"old-version")
    fs = UnverifiableReplaceFaultFileSystem(published_target)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert published_target.read_bytes() == b"new-version"
    assert recorder.calls == []
    assert item.detail["publish_state"] == "unverified"
    assert item.detail["durable_state"] == "publication-unverified"
    assert item.detail["state_error_type"] == "PermissionError"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value


class ReadObservedStream:
    def __init__(self, stream, observed: Event) -> None:
        self.stream = stream
        self.observed = observed
        self.read_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.read_calls += 1
        chunk = self.stream.read(size)
        if chunk:
            self.observed.set()
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class ReadObservedFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.read_observed = Event()
        self.reader: ReadObservedStream | None = None

    def open_source(self, path: Path):
        self.reader = ReadObservedStream(
            super().open_source(path), self.read_observed
        )
        return self.reader


@pytest.mark.parametrize("control", [Canceled, PauseRequested])
def test_copy_control_unwinds_within_one_chunk_and_cleans_temp(
    tmp_path: Path, control: type[Exception]
) -> None:
    source, target = _roots(tmp_path)
    (source / "large.bin").write_bytes(b"x" * 32)
    fs = ReadObservedFileSystem()
    source_stat = fs.stat(source, "large.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="large.bin",
        target_rel_path="large.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    events: list[object] = []

    def checkpoint() -> None:
        if fs.read_observed.is_set():
            raise control()

    with pytest.raises(control):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(max_chunk_size=4),
            fs,
        )

    assert not (target / "large.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert fs.reader is not None
    assert fs.reader.read_calls == 1
    assert not any(isinstance(event, Terminal) for event in events)
    if control is Canceled:
        assert xset.status[operation.op_id] is Outcome.CANCELED
    else:
        assert operation.op_id not in xset.status


def test_pause_retains_settled_copy_evidence_for_in_memory_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations = []
    for number, name in enumerate(("first.bin", "second.bin"), start=1):
        (source / name).write_bytes(name.encode("ascii"))
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    first, second = operations
    xset = _xset(_plan(source, target, tuple(operations)))
    first_settled = Event()
    events: list[object] = []

    def emit(event: object) -> None:
        events.append(event)
        if (
            isinstance(event, ItemOutcome)
            and event.item_id == str(first.op_id)
            and event.outcome is Outcome.SUCCEEDED
        ):
            first_settled.set()

    def checkpoint() -> None:
        if first_settled.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(emit, checkpoint),
            FakeRecorder(),
            _policies(),
            fs,
        )

    assert xset.status == {first.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {first.op_id}
    first_evidence = xset.published_evidence[first.op_id]
    assert first_evidence.copy_recorded

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert xset.status == {
        first.op_id: Outcome.SUCCEEDED,
        second.op_id: Outcome.SUCCEEDED,
    }
    assert set(xset.published_evidence) == {first.op_id, second.op_id}
    assert xset.published_evidence[first.op_id] is first_evidence
    assert xset.published_evidence[second.op_id].copy_recorded


def test_noncopy_recording_degradation_survives_pause_and_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    (source / "same.bin").write_bytes(b"same")
    (target / "same.bin").write_bytes(b"same")
    (source / "copy.bin").write_bytes(b"copy")
    source_same = fs.stat(source, "same.bin")
    target_same = fs.stat(target, "same.bin")
    copy_stat = fs.stat(source, "copy.bin")
    assert source_same is not None
    assert target_same is not None
    assert copy_stat is not None
    noop = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=source_same,
        target_expected=target_same,
        intended=source_same,
        reason=OperationReason.METADATA_MATCH,
    )
    copied = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="copy.bin",
        target_rel_path="copy.bin",
        source_expected=copy_stat,
        target_expected=None,
        intended=copy_stat,
    )
    xset = _xset(_plan(source, target, (noop, copied)))
    noop_settled = Event()

    def emit(event: object) -> None:
        if isinstance(event, ItemOutcome) and event.item_id == str(noop.op_id):
            noop_settled.set()

    def checkpoint() -> None:
        if noop_settled.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(emit, checkpoint),
            FakeRecorder(fail="noop"),
            _policies(),
            fs,
        )

    assert xset.status == {noop.op_id: Outcome.SKIPPED}
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence[copied.op_id].copy_recorded


def test_pause_flush_degradation_is_retained_for_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"content")
    fs = ReadObservedFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))

    def checkpoint() -> None:
        if fs.read_observed.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _event: None, checkpoint),
            FakeRecorder(fail="flush"),
            _policies(),
            fs,
        )

    assert xset.status == {}
    assert xset.published_evidence == {}
    assert xset.recording is RecordingStatus.DEGRADED

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence[operation.op_id].copy_recorded


class InterruptingBackend(NativeCopyBackend):
    def copy(self, _source, target, **_kwargs):
        target.write(b"partial")
        raise KeyboardInterrupt()


def test_unexpected_base_exception_cleans_owned_temp_before_propagating(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"complete")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()

    with pytest.raises(KeyboardInterrupt):
        execute(
            xset,
            RunContext(lambda _: None, lambda: None),
            recorder,
            _policies(
                copy_backend=InterruptingBackend(hasher_factory=xxh3_128)
            ),
            fs,
        )

    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert operation.op_id not in xset.status
    assert recorder.calls == []
    assert recorder.flushes == 1


class SharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise _sharing_violation("sharing violation")
        super().publish_new(temp, target)


class SharingViolationWriter:
    def __init__(self, stream) -> None:
        self.stream = stream
        self.writes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def write(self, data) -> int:
        self.writes += 1
        if self.writes == 2:
            raise _sharing_violation("sharing violation during streamed write")
        return self.stream.write(data)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MidCopySharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.create_attempts = 0
        self.cleaned: list[Path] = []

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.create_attempts += 1
        stream = super().create_temp(
            path, allocation_size=allocation_size
        )
        if self.create_attempts == 1:
            return SharingViolationWriter(stream)
        return stream

    def remove_owned_temp(self, path: Path) -> None:
        if path.exists():
            self.cleaned.append(path)
        super().remove_owned_temp(path)


class RetryCleanupFailureFileSystem(MidCopySharingOnceFileSystem):
    def __init__(self) -> None:
        super().__init__()
        self.cleanup_attempts = 0

    def remove_owned_temp(self, path: Path) -> None:
        if self.create_attempts > 0 and path.exists():
            self.cleanup_attempts += 1
            raise PermissionError("injected retry cleanup failure")
        super().remove_owned_temp(path)


class CleanupDiagnosticFileSystem(NativeFileSystem):
    def __init__(self, *, fail_finalize: bool) -> None:
        self.fail_finalize = fail_finalize
        self.temp_created = False
        self.fail_cleanup = False

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_created = True
        if not self.fail_finalize:
            self.fail_cleanup = True
        return stream

    def finalize_temp(
        self,
        path: Path,
        intended: FileStat,
        *,
        preserve_created: bool,
        acl_source: Path | None,
    ) -> FileStat:
        if self.fail_finalize:
            self.fail_cleanup = True
            raise OSError("injected finalization failure")
        return super().finalize_temp(
            path,
            intended,
            preserve_created=preserve_created,
            acl_source=acl_source,
        )

    def remove_owned_temp(self, path: Path) -> None:
        if self.fail_cleanup:
            native = to_extended_length_path(str(path))
            raise PermissionError(13, "cleanup denied", native)
        super().remove_owned_temp(path)


class PublishCancelCleanupDiagnosticFileSystem(CleanupDiagnosticFileSystem):
    def __init__(self) -> None:
        super().__init__(fail_finalize=False)

    def publish_new(self, temp: Path, target: Path) -> None:
        del temp, target
        raise Canceled()


class UnverifiedPublishCleanupFailureFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.publish_attempted = False
        self.settlement_probe_calls = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        del temp, target
        self.publish_attempted = True
        raise PermissionError("injected publish failure")

    def stat_path(self, path: Path) -> FileStat | None:
        if self.publish_attempted:
            self.settlement_probe_calls += 1
            if self.settlement_probe_calls == 1:
                raise PermissionError(
                    "injected one-shot publication probe failure"
                )
        return super().stat_path(path)

    def remove_owned_temp(self, path: Path) -> None:
        if self.publish_attempted:
            raise PermissionError("injected cleanup failure")
        super().remove_owned_temp(path)


def test_failed_cleanup_detail_sanitizes_native_temp_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = CleanupDiagnosticFileSystem(fail_finalize=True)
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    outcome = _item_outcome(events)
    assert result.items == (outcome,)
    assert outcome.reason == "cleanup-failed"
    assert r"file.bin.synctmp-" in outcome.detail["message"]
    assert "\\\\?\\" not in outcome.detail["message"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_canceled_cleanup_detail_sanitizes_native_temp_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = CleanupDiagnosticFileSystem(fail_finalize=False)
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    events: list[object] = []

    def checkpoint() -> None:
        if fs.temp_created:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            _xset(_plan(source, target, (operation,))),
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(),
            fs,
        )

    outcome = _item_outcome(events)
    assert outcome.outcome is Outcome.CANCELED
    assert r"file.bin.synctmp-" in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_canceled_durable_settlement_sanitizes_cleanup_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = PublishCancelCleanupDiagnosticFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            _xset(_plan(source, target, (operation,))),
            RunContext(events.append, lambda: None),
            FakeRecorder(),
            _policies(),
            fs,
        )

    outcome = _item_outcome(events)
    assert outcome.outcome is Outcome.CANCELED
    assert outcome.detail["publish_state"] == "not-published"
    assert r"file.bin.synctmp-" in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_failed_durable_settlement_observes_once_before_cleanup(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = UnverifiedPublishCleanupFailureFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(failure=BoundedFailurePolicy(retries=0)),
    )

    outcome = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert outcome.outcome is Outcome.FAILED
    assert outcome.reason == "io-error"
    assert outcome.detail == {
        "error_type": "PermissionError",
        "message": "injected publish failure",
        "publish_state": "unverified",
        "published_path": "file.bin",
        "durable_state": "publication-unverified",
        "state_error_type": "PermissionError",
        "state_error": "injected one-shot publication probe failure",
        "recording": RecordingStatus.DEGRADED.value,
        "recording_error": (
            "filesystem mutation may have published but durable state "
            "could not be verified"
        ),
        "cleanup_error": "injected cleanup failure",
    }
    assert fs.settlement_probe_calls == 1
    assert recorder.calls == []
    owned_temp = target / (
        f"file.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    assert owned_temp.exists()


def test_midcopy_sharing_retry_recreates_owned_temp_and_converges(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"abcdefghijkl"
    (source / "file.bin").write_bytes(payload)
    fs = MidCopySharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(max_chunk_size=4),
    )

    expected_temp = target / (
        f"file.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    assert result.status is SessionState.COMPLETED
    assert fs.create_attempts == 2
    assert fs.cleaned == [expected_temp]
    assert (target / "file.bin").read_bytes() == payload
    assert not expected_temp.exists()
    assert _recorder_names(recorder) == ["copied"]


def test_failed_pre_retry_cleanup_settles_before_control_checkpoint(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"abcdefghijkl")
    fs = RetryCleanupFailureFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    sleeps: list[float] = []
    decisions: list[tuple[OpId, int, type[Exception]]] = []

    class RetryPolicy:
        def on_item_failed(
            self,
            failed_operation: PlanOperation,
            error: Exception,
            attempt: int,
        ) -> Retry:
            decisions.append((failed_operation.op_id, attempt, type(error)))
            return Retry(0)

    def checkpoint() -> None:
        if fs.cleanup_attempts:
            raise Canceled()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            failure=RetryPolicy(),
            max_chunk_size=4,
            sleep=sleeps.append,
        ),
        checkpoint=checkpoint,
    )

    outcome = _item_outcome(events)
    owned_temp = target / (
        f"file.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert outcome.outcome is Outcome.FAILED
    assert outcome.reason == "cleanup-failed"
    assert outcome.detail["error_type"] == "OperationFailure"
    assert "injected retry cleanup failure" in outcome.detail["message"]
    assert fs.create_attempts == 1
    assert fs.cleanup_attempts == 1
    assert decisions == [(operation.op_id, 1, OSError)]
    assert sleeps == []
    assert owned_temp.exists()
    assert not (target / "file.bin").exists()
    assert recorder.calls == []
    assert recorder.flushes == 1


def test_transient_sharing_violation_retries_within_bound(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"retry")
    fs = SharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"retry"


class CopyMetadataSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.metadata_attempts = 0
        self.source_opens = 0

    def open_source(self, path: Path):
        self.source_opens += 1
        return super().open_source(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        self.metadata_attempts += 1
        if self.metadata_attempts == 1:
            raise _sharing_violation("sharing violation after copy publish")
        return super().ensure_published_metadata(path, *args, **kwargs)


class PublishedRetrySharingOnceFileSystem(NativeFileSystem):
    def __init__(self, published_target: Path, *, before_stat_cache: bool) -> None:
        self.published_target = published_target
        self.before_stat_cache = before_stat_cache
        self.published_metadata_observed = False
        self.metadata_attempts = 0
        self.flush_attempts = 0
        self.source_opens = 0

    def open_source(self, path: Path):
        self.source_opens += 1
        return super().open_source(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if path == self.published_target:
            self.metadata_attempts += 1
            if self.before_stat_cache and self.metadata_attempts == 1:
                native = path.stat(follow_symlinks=False)
                os.utime(
                    path,
                    ns=(native.st_atime_ns, native.st_mtime_ns + 2_000_000_000),
                )
                raise _sharing_violation("sharing violation before published stat")
        observed = super().ensure_published_metadata(path, *args, **kwargs)
        if path == self.published_target:
            self.published_metadata_observed = True
        return observed

    def flush_directory(self, path: Path) -> bool:
        if not self.before_stat_cache and self.published_metadata_observed:
            self.flush_attempts += 1
            if self.flush_attempts == 1:
                raise _sharing_violation("sharing violation after published stat")
        return super().flush_directory(path)


def _replace_published_target(path: Path, fs: NativeFileSystem) -> None:
    published = fs.stat_path(path)
    assert published is not None
    replacement = path.with_name(f".{path.name}.foreign")
    replacement.write_bytes(b"bad-version")
    os.utime(
        replacement,
        ns=(replacement.stat().st_atime_ns, published.mtime_ns),
    )
    replacement_stat = fs.stat_path(replacement)
    assert replacement_stat is not None
    assert replacement_stat.size == published.size
    assert replacement_stat.mtime_ns == published.mtime_ns
    assert replacement_stat.file_identity != published.file_identity
    os.replace(replacement, path)


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
@pytest.mark.parametrize(
    "before_stat_cache",
    (
        pytest.param(True, id="before-stat-cache"),
        pytest.param(False, id="after-stat-cache"),
    ),
)
def test_retry_rejects_replaced_published_target(
    tmp_path: Path,
    kind: OperationKind,
    before_stat_cache: bool,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=before_stat_cache,
    )
    operation, published_target = _reviewed_byte_operation(
        kind, source, target, fs
    )

    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    result, events, recorder = _run(
        xset,
        fs=fs,
        policies=_policies(
            sleep=lambda _delay: _replace_published_target(published_target, fs)
        ),
    )

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "target-drift"
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "changed-after-publish"
    assert item.detail["durable_state"] == "target-changed-after-publish"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert fs.metadata_attempts == 1
    assert fs.flush_attempts == (0 if before_stat_cache else 1)
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert published_target.read_bytes() == b"bad-version"


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
def test_cancel_after_published_target_changes_reports_changed_durable_state(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=True,
    )
    operation, published_target = _reviewed_byte_operation(
        kind, source, target, fs
    )
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    cancel_requested = False
    events: list[object] = []

    def sleep_for_retry(_delay: float) -> None:
        nonlocal cancel_requested
        _replace_published_target(published_target, fs)
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep_for_retry),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "changed-after-publish"
    assert item.detail["durable_state"] == "target-changed-after-publish"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


def test_metadata_retry_repairs_published_mtime_without_recopy(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / "file.bin"
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=True,
    )
    operation, _ = _reviewed_byte_operation(
        OperationKind.COPY, source, target, fs
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    published = fs.stat_path(published_target)
    assert published is not None
    assert operation.source_expected is not None
    assert result.status is SessionState.COMPLETED
    assert published.mtime_ns == operation.source_expected.mtime_ns
    assert fs.metadata_attempts == 2
    assert fs.source_opens == 1
    assert _recorder_names(recorder) == ["copied"]


class PermanentPublishedMetadataFailureFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.metadata_attempts = 0
        self.published_target: Path | None = None

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if path != self.published_target:
            return super().ensure_published_metadata(path, *args, **kwargs)
        self.metadata_attempts += 1
        raise _sharing_violation("persistent sharing violation after publish")


class TerminalPublishAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.published_target: Path | None = None

    def replace(self, temp: Path, target: Path) -> None:
        super().replace(temp, target)
        if target == self.published_target:
            raise _sharing_violation("sharing report after committed publish")

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        if target == self.published_target:
            raise _sharing_violation("sharing report after committed publish")


_TERMINAL_PUBLICATION_CASES = (
    pytest.param(
        OperationKind.COPY,
        "target-published",
        id="copy-target-published",
    ),
    pytest.param(
        OperationKind.UPDATE,
        "target-published-with-backup",
        id="update-target-published-with-backup",
    ),
    pytest.param(
        OperationKind.MOVE_UPDATE,
        "new-and-old",
        id="move_update-new-and-old",
    ),
)


def _assert_terminal_publication_failure(
    result,
    item: ItemOutcome,
    recorder: FakeRecorder,
    xset: ExecutionSet,
    published_target: Path,
    durable_state: str,
) -> None:
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "sharing-violation"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "published"
    assert item.detail["durable_state"] == durable_state
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert published_target.read_bytes() == b"new-version"
    assert recorder.calls == []
    assert xset.published_evidence == {}


@pytest.mark.parametrize(
    ("kind", "durable_state"),
    _TERMINAL_PUBLICATION_CASES,
)
def test_terminal_post_publish_failure_degrades_recording_and_reports_durable_state(
    tmp_path: Path,
    kind: OperationKind,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = PermanentPublishedMetadataFailureFileSystem()
    operation, published_target = _reviewed_byte_operation(
        kind,
        source,
        target,
        fs,
    )
    fs.published_target = published_target
    recorder = FakeRecorder()
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))

    result, events, _ = _run(xset, fs=fs, recorder=recorder)

    item = _item_outcome(events)
    _assert_terminal_publication_failure(
        result,
        item,
        recorder,
        xset,
        published_target,
        durable_state,
    )
    assert item.detail["published_path"] == operation.target_rel_path
    assert item.detail["recording_error"] == (
        "published filesystem mutation failed before ledger settlement"
    )
    assert fs.metadata_attempts == 3

    if kind is OperationKind.UPDATE:
        backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
        assert item.detail["backup_state"] == "retained"
        assert backup.read_bytes() == b"old-version"
    elif kind is OperationKind.MOVE_UPDATE:
        assert item.detail["prior_path"] == "old.bin"
        assert (target / "old.bin").read_bytes() == b"old-version"


@pytest.mark.parametrize(
    ("kind", "durable_state"),
    _TERMINAL_PUBLICATION_CASES,
)
def test_terminal_publish_that_commits_before_error_degrades_recording(
    tmp_path: Path,
    kind: OperationKind,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = TerminalPublishAfterCommitFileSystem()
    operation, published_target = _reviewed_byte_operation(
        kind,
        source,
        target,
        fs,
    )
    fs.published_target = published_target
    recorder = FakeRecorder()
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))

    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=recorder,
        policies=_policies(failure=BoundedFailurePolicy(retries=0)),
    )

    _assert_terminal_publication_failure(
        result,
        _item_outcome(events),
        recorder,
        xset,
        published_target,
        durable_state,
    )


def test_pause_during_published_copy_retry_settles_without_recopy(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = CopyMetadataSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(PauseRequested)

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    assert fs.metadata_attempts == 2
    assert fs.source_opens == 1
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "file.bin").read_bytes() == b"published-copy"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


def test_cancel_during_published_copy_retry_fails_without_false_evidence(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = CopyMetadataSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(Canceled)
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == "target-published"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}
    assert fs.source_opens == 1
    assert (target / "file.bin").read_bytes() == b"published-copy"


def test_cancel_after_failed_copy_publish_does_not_claim_foreign_target(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"prepared-copy")
    fs = SharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        (target / "file.bin").write_bytes(b"foreign-write")
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["publish_state"] == "not-published"
    assert item.detail["target_state"] == "unexpectedly-present-before-publish"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"foreign-write"
    assert not list(target.glob("*.synctmp-*"))


class VanishingTempSharingFileSystem(NativeFileSystem):
    def publish_new(self, temp: Path, target: Path) -> None:
        del target
        temp.unlink()
        raise _sharing_violation("sharing report with missing staged temp")


def test_unclassifiable_cancel_does_not_assume_publish_or_degrade_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"prepared-copy")
    fs = VanishingTempSharingFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(Canceled)
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.FAILED
    assert item.reason == "target-missing"
    assert item.detail["publish_state"] == "unverified"
    assert item.detail["durable_state"] == "unverified"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}


class PublishedMtimeThenFlushSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.flush_attempts = 0

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        super().ensure_published_metadata(path, *args, **kwargs)
        native = path.stat(follow_symlinks=False)
        os.utime(
            path,
            ns=(native.st_atime_ns, native.st_mtime_ns + 2_000_000_000),
        )
        observed = self.stat_path(path)
        assert observed is not None
        return observed

    def flush_directory(self, path: Path) -> bool:
        self.flush_attempts += 1
        if self.flush_attempts == 1:
            raise _sharing_violation("sharing violation after repaired metadata")
        return super().flush_directory(path)


def test_cancel_uses_cached_published_stat_after_metadata_changes(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = PublishedMtimeThenFlushSharingFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(Canceled)
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "published"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


class PrepareSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.failed = False
        self.attempts = 0

    def open_source(self, path: Path):
        self.attempts += 1
        self.failed = True
        raise _sharing_violation("sharing violation before durable ownership")


def test_pause_without_durable_continuation_unwinds_before_retry_sleep(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"not-staged")
    fs = PrepareSharingFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    slept = False

    def checkpoint() -> None:
        if fs.failed:
            raise PauseRequested()

    def sleep(_delay: float) -> None:
        nonlocal slept
        slept = True

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    assert fs.attempts == 1
    assert not slept
    assert operation.op_id not in xset.status
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))


def test_production_retry_sleep_budget_is_350_milliseconds() -> None:
    policy = BoundedFailurePolicy()
    error = _sharing_violation("sharing violation")
    operation = object()

    decisions = [
        policy.on_item_failed(operation, error, attempt)  # type: ignore[arg-type]
        for attempt in range(1, 5)
    ]
    delays = [decision.after for decision in decisions if isinstance(decision, Retry)]

    assert delays == pytest.approx([0.05, 0.1, 0.2])
    assert sum(delays) == pytest.approx(0.35)


class ReplaceSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise _sharing_violation("sharing violation during replace")
        super().replace(temp, target)


@pytest.mark.parametrize("hardlinks", [True, False])
def test_update_retries_replace_without_restarting_after_backup(
    tmp_path: Path, hardlinks: bool
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert _recorder_names(recorder) == ["updated"]


class ReplaceSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        super().replace(temp, target)
        raise _sharing_violation("sharing report after committed replace")


def test_update_retry_recognizes_replace_that_committed_before_error(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert _recorder_names(recorder) == ["updated"]


class BackupSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        self.attempts += 1
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        raise _sharing_violation("sharing report after committed backup")


def test_update_retry_recognizes_committed_copy_backup(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = BackupSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert _recorder_names(recorder) == ["updated"]


class CopyBackupMetadataSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_metadata_attempts = 0
        self.replace_metadata_attempts: list[int] = []

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if ".synctrash" in path.parts:
            self.backup_metadata_attempts += 1
            if self.backup_metadata_attempts == 1:
                observed = self.stat_path(path)
                assert observed is not None
                damaged_mtime = observed.mtime_ns + 10_000_000_000
                os.utime(path, ns=(damaged_mtime, damaged_mtime))
                raise _sharing_violation(
                    "sharing violation before backup metadata repair"
                )
        return super().ensure_published_metadata(path, *args, **kwargs)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_metadata_attempts.append(self.backup_metadata_attempts)
        super().replace(temp, target)


def test_copied_backup_metadata_repair_resumes_before_update_replace(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    repaired = fs.stat_path(trash)
    assert result.status is SessionState.COMPLETED
    assert fs.backup_metadata_attempts == 2
    assert fs.replace_metadata_attempts == [2]
    assert repaired is not None
    assert repaired.mtime_ns == target_stat.mtime_ns
    assert trash.read_bytes() == b"old-version"
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert _recorder_names(recorder) == ["updated"]


class CopyBackupMetadataSharingAlwaysFileSystem(
    CopyBackupMetadataSharingOnceFileSystem
):
    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if ".synctrash" in path.parts:
            self.backup_metadata_attempts += 1
            raise _sharing_violation(
                "persistent backup metadata sharing violation"
            )
        return NativeFileSystem.ensure_published_metadata(
            self,
            path,
            *args,
            **kwargs,
        )


def test_persistent_copied_backup_metadata_failure_prevents_update_replace(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    assert result.status is SessionState.FAILED
    assert fs.backup_metadata_attempts == 3
    assert fs.replace_metadata_attempts == []
    assert (target / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


def test_resumed_update_rejects_target_drift_before_backup_metadata_repair(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    published_target = target / "file.bin"

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
        policies=_policies(
            sleep=lambda _delay: _replace_published_target(
                published_target,
                fs,
            )
        ),
    )

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert fs.backup_metadata_attempts == 1
    assert recorder.calls == []
    assert published_target.read_bytes() == b"bad-version"


class CopyBackupStatSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_created = False
        self.backup_stat_failed = False
        self.backup_copy_attempts = 0

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        self.backup_copy_attempts += 1
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        self.backup_created = True

    def stat_path(self, path: Path) -> FileStat | None:
        if (
            self.backup_created
            and not self.backup_stat_failed
            and ".synctrash" in path.parts
        ):
            self.backup_stat_failed = True
            raise _sharing_violation(
                "sharing violation observing published backup"
            )
        return super().stat_path(path)


def test_update_retry_retains_continuation_when_backup_stat_temporarily_fails(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupStatSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.COMPLETED
    assert fs.backup_copy_attempts == 1
    assert fs.backup_stat_failed
    assert trash.read_bytes() == b"old-version"
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert _recorder_names(recorder) == ["updated"]


class ReplaceSharingAlwaysFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        raise _sharing_violation("persistent replace sharing violation")


def test_persistent_update_sharing_exhausts_policy_without_false_drift(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    outcome = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert outcome.reason == "sharing-violation"
    assert (target / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


def test_pause_during_update_retry_settles_then_resumes_without_trash_collision(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(PauseRequested)

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert fs.attempts == 2
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert trash.read_bytes() == b"old-version"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


@pytest.mark.parametrize(
    ("fs_factory", "expected_outcome", "expected_state"),
    [
        pytest.param(
            ReplaceSharingAlwaysFileSystem,
            Outcome.CANCELED,
            "backup-retained",
            id="before-publish",
        ),
        pytest.param(
            ReplaceSharingAfterCommitFileSystem,
            Outcome.FAILED,
            "target-published-with-backup",
            id="after-publish",
        ),
    ],
)
def test_cancel_during_update_retry_reports_owned_durable_state(
    tmp_path: Path,
    fs_factory: Callable[[], NativeFileSystem],
    expected_outcome: Outcome,
    expected_state: str,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = fs_factory()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(Canceled)
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    item = _item_outcome(events)
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert item.outcome is expected_outcome
    assert item.detail["durable_state"] == expected_state
    assert item.detail["backup_state"] == "retained"
    assert item.detail["backup_path"] == (
        f".synctrash\\{RUN_ID}\\file.bin"
    )
    assert trash.read_bytes() == b"old-version"
    assert not list(target.glob("*.synctmp-*"))
    assert xset.published_evidence == {}
    if expected_outcome is Outcome.CANCELED:
        assert item.reason == "canceled"
        assert xset.recording is RecordingStatus.OK
        assert (target / "file.bin").read_bytes() == b"old-version"
    else:
        assert item.reason == "canceled-after-publish"
        assert xset.recording is RecordingStatus.DEGRADED
        assert item.detail["recording"] == "degraded"
        assert (target / "file.bin").read_bytes() == b"new-version"


def test_cancel_during_update_retry_does_not_claim_replaced_backup(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        retained = fs.stat_path(trash)
        assert retained is not None
        replacement = trash.with_name("replacement.bin")
        replacement.write_bytes(b"bad-version")
        os.utime(
            replacement,
            ns=(retained.mtime_ns, retained.mtime_ns),
        )
        os.replace(replacement, trash)
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = _item_outcome(events)
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["backup_state"] == "changed"
    assert item.detail["backup_path"] == (
        f".synctrash\\{RUN_ID}\\file.bin"
    )
    assert item.detail["durable_state"] == "target-not-published"
    assert trash.read_bytes() == b"bad-version"
    assert (target / "file.bin").read_bytes() == b"old-version"


def test_cancel_after_failed_update_replace_does_not_claim_foreign_write(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        (target / "file.bin").write_bytes(b"foreign-write")
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = _item_outcome(events)
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["publish_state"] == "not-published"
    assert item.detail["target_state"] == "changed-before-publish"
    assert item.detail["durable_state"] == "backup-retained"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"foreign-write"
    assert trash.read_bytes() == b"old-version"
    assert not list(target.glob("*.synctmp-*"))


def test_cancel_update_settlement_rejects_matching_backup_decoy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = ReplaceSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    run_root = trash.parent
    detached = target / f".detached-trash-{RUN_ID}"
    real_stat_path = fs.stat_path
    decoy_stat: FileStat | None = None
    decoy_reads = 0
    swapped = False
    cancel_requested = False
    events: list[object] = []

    def matching_decoy_stat(path: Path) -> FileStat | None:
        nonlocal decoy_reads
        if swapped and path == trash:
            decoy_reads += 1
            assert decoy_stat is not None
            return decoy_stat
        return real_stat_path(path)

    monkeypatch.setattr(fs, "stat_path", matching_decoy_stat)

    def swap_before_cancel(_delay: float) -> None:
        nonlocal cancel_requested, decoy_stat, swapped
        decoy_stat = real_stat_path(trash)
        assert decoy_stat is not None
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        (redirected / "file.bin").write_bytes(b"old-version")
        swapped = True
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=swap_before_cancel),
            fs,
        )

    item = _item_outcome(events)
    assert swapped
    assert decoy_reads == 0
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["backup_state"] == "unverified"
    assert "reparse points" in item.detail["backup_state_error"]
    assert item.detail["durable_state"] == "target-not-published"
    assert live.read_bytes() == b"old-version"
    assert (detached / "file.bin").read_bytes() == b"old-version"
    assert (redirected / "file.bin").read_bytes() == b"old-version"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}


def test_cancel_preempts_an_already_latched_durable_pause(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    backoff_started = False
    pause_observed = False

    def sleep(_delay: float) -> None:
        nonlocal backoff_started
        backoff_started = True

    def checkpoint() -> None:
        nonlocal pause_observed
        if not backoff_started:
            return
        if not pause_observed:
            pause_observed = True
            raise PauseRequested()
        raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    assert pause_observed
    assert xset.status == {operation.op_id: Outcome.CANCELED}
    assert xset.published_evidence == {}
    assert (target / "file.bin").read_bytes() == b"old-version"


class RetryThenStopPolicy:
    def on_item_failed(self, operation, error, attempt):
        del operation, error
        return Retry(0) if attempt == 1 else Stop()


class ImmediateStopPolicy:
    def on_item_failed(self, operation, error, attempt):
        del operation, error, attempt
        return Stop()


def test_policy_stop_suppresses_latched_pause_and_settles_remaining_work(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "locked.bin").write_bytes(b"new")
    (target / "locked.bin").write_bytes(b"old")
    (source / "later.bin").write_bytes(b"later")
    fs = ReplaceSharingAlwaysFileSystem()
    locked_source = fs.stat(source, "locked.bin")
    locked_target = fs.stat(target, "locked.bin")
    later_source = fs.stat(source, "later.bin")
    assert locked_source is not None and locked_target is not None
    assert later_source is not None
    locked = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="locked.bin",
        target_rel_path="locked.bin",
        source_expected=locked_source,
        target_expected=locked_target,
        intended=locked_source,
    )
    later = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="later.bin",
        target_rel_path="later.bin",
        source_expected=later_source,
        target_expected=None,
        intended=later_source,
    )
    xset = _xset(_plan(source, target, (locked, later)))
    control = _ControlLatch(PauseRequested)

    result, events, _ = _run(
        xset,
        fs=fs,
        checkpoint=control.checkpoint,
        policies=_policies(failure=RetryThenStopPolicy(), sleep=control.arm),
    )

    items = [event for event in events if isinstance(event, ItemOutcome)]
    assert result.status is SessionState.FAILED
    assert [item.outcome for item in items] == [Outcome.FAILED, Outcome.CANCELED]
    assert items[1].reason == "policy-stop"
    assert not (target / "later.bin").exists()


def test_cancel_interrupts_policy_stop_settlement_sweep(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    operations: list[PlanOperation] = []
    fs = PrepareSharingFileSystem()
    for index, name in enumerate(
        ("locked.bin", "stopped.bin", "cancel-now.bin", "unreached.bin"),
        start=1,
    ):
        (source / name).write_bytes(name.encode())
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                index,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    xset = _xset(_plan(source, target, tuple(operations)))
    checkpoint_calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 3:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(failure=ImmediateStopPolicy()),
            fs,
        )

    items = [event for event in events if isinstance(event, ItemOutcome)]
    assert checkpoint_calls == 3
    assert [item.outcome for item in items] == [
        Outcome.FAILED,
        Outcome.CANCELED,
        Outcome.CANCELED,
        Outcome.CANCELED,
    ]
    assert [item.reason for item in items] == [
        "sharing-violation",
        "policy-stop",
        "canceled",
        "canceled",
    ]


class PersistentSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        if target.name == "locked.bin":
            self.attempts += 1
            raise _sharing_violation("persistent sharing violation")
        super().publish_new(temp, target)


def test_persistent_sharing_is_bounded_and_independent_work_continues(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "locked.bin").write_bytes(b"locked")
    (source / "free.bin").write_bytes(b"free")
    fs = PersistentSharingFileSystem()
    locked_stat = fs.stat(source, "locked.bin")
    free_stat = fs.stat(source, "free.bin")
    assert locked_stat is not None and free_stat is not None
    locked = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="locked.bin",
        target_rel_path="locked.bin",
        source_expected=locked_stat,
        target_expected=None,
        intended=locked_stat,
    )
    free = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="free.bin",
        target_rel_path="free.bin",
        source_expected=free_stat,
        target_expected=None,
        intended=free_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (locked, free))), fs=fs)

    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert not (target / "locked.bin").exists()
    assert (target / "free.bin").read_bytes() == b"free"
    outcome = _item_outcome(events, locked.op_id)
    assert outcome.reason == "sharing-violation"


def test_recorder_failure_preserves_filesystem_success_and_degrades_axis(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"copied")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    xset = _xset(_plan(source, target, (operation,)))
    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=FakeRecorder(fail="copied"),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"copied"
    item = _item_outcome(events)
    assert item.outcome is Outcome.SUCCEEDED
    assert item.detail["recording"] == "degraded"
    assert xset.recording is RecordingStatus.DEGRADED
    assert set(xset.published_evidence) == {operation.op_id}
    published = xset.published_evidence[operation.op_id]
    assert not published.copy_recorded
    assert published.recorded_identity is None


class MissingCopyIdentityRecorder(FakeRecorder):
    def record_copied(self, op, attestation) -> None:
        self._record("copied", op, attestation)


def test_copy_recorder_none_return_is_degraded_not_recorded(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"copied")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))

    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=MissingCopyIdentityRecorder(),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    published = xset.published_evidence[operation.op_id]
    assert not published.copy_recorded
    assert published.recorded_identity is None
    item = _item_outcome(events)
    assert "did not return a recorded copy identity" in item.detail["recording_error"]


class FailFirstCopyRecorder(FakeRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.copy_attempts = 0

    def record_copied(self, op, attestation) -> RecordedCopyIdentity:
        self.copy_attempts += 1
        if self.copy_attempts == 1:
            raise RuntimeError("injected first copy record failure")
        return super().record_copied(op, attestation)


def test_recording_truth_is_per_copy_while_aggregate_degradation_is_sticky(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations = []
    for number, name in enumerate(("first.bin", "second.bin"), start=1):
        (source / name).write_bytes(name.encode("ascii"))
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    xset = _xset(_plan(source, target, tuple(operations)))

    result, _, recorder = _run(
        xset,
        fs=fs,
        recorder=FailFirstCopyRecorder(),
    )

    first, second = operations
    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert set(xset.published_evidence) == {
        first.op_id,
        second.op_id,
    }
    assert not xset.published_evidence[first.op_id].copy_recorded
    assert xset.published_evidence[second.op_id].copy_recorded
    assert recorder.copy_attempts == 2


class MoveUpdateStageFaultStream:
    def __init__(
        self,
        stream,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        self.stream = stream
        self.stage = stage
        self.fault = fault
        self.reads = 0
        self.writes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.reads += 1
        if self.stage == "read" and self.reads == 2:
            self.fault("read")
        return self.stream.read(size)

    def write(self, data) -> int:
        self.writes += 1
        if self.stage == "write" and self.writes == 2:
            self.fault("write")
        return self.stream.write(data)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MoveUpdateStageFaultHasher:
    def __init__(self, fault: Callable[[str], None]) -> None:
        self.inner = xxh3_128()
        self.fault = fault
        self.updates = 0

    def update(self, data: bytes) -> None:
        self.updates += 1
        if self.updates == 2:
            self.fault("hash")
        self.inner.update(data)

    def digest(self) -> bytes:
        return self.inner.digest()


class MoveUpdateStageFaultFileSystem(NativeFileSystem):
    def __init__(
        self,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        self.stage = stage
        self.fault = fault
        self.temp_paths: list[Path] = []

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if self.stage == "read":
            return MoveUpdateStageFaultStream(stream, self.stage, self.fault)
        return stream

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_paths.append(path)
        if self.stage == "prepare":
            stream.close()
            self.fault("prepare")
        if self.stage == "write":
            return MoveUpdateStageFaultStream(stream, self.stage, self.fault)
        return stream

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().finalize_temp(path, *args, **kwargs)
        if self.stage == "finalize":
            self.fault("finalize")
        return result

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        if self.stage == "publish":
            self.fault("publish")

    def ensure_published_metadata(
        self, path: Path, *args, **kwargs
    ) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if self.stage == "post-metadata":
            self.fault("post-metadata")
        return result

    def rename_new(self, source: Path, target: Path) -> None:
        super().rename_new(source, target)
        if self.stage == "trash" and ".synctrash" in target.parts:
            self.fault("trash")

    def flush_directory(self, path: Path) -> bool:
        if self.stage == "directory-flush":
            self.fault("directory-flush")
        return super().flush_directory(path)


class MoveUpdateStageFaultRecorder(FakeRecorder):
    def __init__(
        self,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.stage = stage
        self.fault = fault
        self.move_update_attempts = 0

    def record_move_updated(self, op, attestation) -> RecordedCopyIdentity:
        self.move_update_attempts += 1
        if self.stage == "record":
            self.fault("record")
        return super().record_move_updated(op, attestation)


@pytest.mark.parametrize(
    ("stage", "expected_paths"),
    [
        pytest.param("prepare", "old-only", id="prepare"),
        pytest.param("read", "old-only", id="read"),
        pytest.param("hash", "old-only", id="hash"),
        pytest.param("write", "old-only", id="write"),
        pytest.param("finalize", "old-only", id="finalize"),
        pytest.param("publish", "both-live", id="publish"),
        pytest.param("post-metadata", "both-live", id="post-metadata"),
        pytest.param("attestation", "both-live", id="attestation"),
        pytest.param("trash", "new-and-trash", id="trash"),
        pytest.param("directory-flush", "new-and-trash", id="directory-flush"),
        pytest.param("record", "new-and-trash", id="record"),
    ],
)
def test_a15_move_update_stage_faults_never_lose_both_versions_or_false_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_paths: str,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"changed-content"
    old_payload = b"old-content"
    source_path = source / "new.bin"
    old_path = target / "old.bin"
    new_path = target / "new.bin"
    source_path.write_bytes(payload)
    old_path.write_bytes(old_payload)
    observed_faults: list[str] = []
    failure = RuntimeError(f"injected move-update {stage} failure")

    def fault(point: str) -> None:
        observed_faults.append(point)
        raise failure

    fs = MoveUpdateStageFaultFileSystem(stage, fault)
    source_stat = fs.stat(source, "new.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="new.bin",
        target_rel_path="new.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    if stage == "attestation":
        monkeypatch.setattr(
            executor_runtime,
            "_attestation",
            lambda *_args, **_kwargs: fault("attestation"),
        )
    hasher_factory = (
        (lambda: MoveUpdateStageFaultHasher(fault))
        if stage == "hash"
        else xxh3_128
    )
    recorder = MoveUpdateStageFaultRecorder(stage, fault)

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=recorder,
        policies=_policies(
            copy_backend=NativeCopyBackend(
                hasher_factory=hasher_factory,
            ),
            max_chunk_size=4,
        ),
    )

    trash_path = target / ".synctrash" / str(RUN_ID) / "old.bin"
    expected_temp = target / (
        f"new.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    item = _item_outcome(events)
    assert observed_faults == [stage]
    assert old_path.exists() or new_path.exists()
    assert not expected_temp.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []

    if expected_paths == "old-only":
        assert old_path.read_bytes() == old_payload
        assert not new_path.exists()
        assert not trash_path.exists()
        assert fs.temp_paths == [expected_temp]
    elif expected_paths == "both-live":
        assert old_path.read_bytes() == old_payload
        assert new_path.read_bytes() == payload
        assert not trash_path.exists()
        assert fs.temp_paths == [expected_temp]
    else:
        assert not old_path.exists()
        assert new_path.read_bytes() == payload
        assert trash_path.read_bytes() == old_payload
        assert fs.temp_paths == [expected_temp]

    if stage == "record":
        assert result.status is SessionState.COMPLETED
        assert result.recording is RecordingStatus.DEGRADED
        assert item.outcome is Outcome.SUCCEEDED
        assert item.reason is None
        assert item.detail["recording"] == RecordingStatus.DEGRADED.value
        assert recorder.move_update_attempts == 1
    else:
        assert result.status is SessionState.FAILED
        assert item.outcome is Outcome.FAILED
        assert item.reason == "io-error"
        assert recorder.move_update_attempts == 0
        if stage in {
            "publish",
            "post-metadata",
            "attestation",
            "trash",
            "directory-flush",
        }:
            assert result.recording is RecordingStatus.DEGRADED
            assert item.detail["publish_state"] == "published"
            assert item.detail["recording"] == RecordingStatus.DEGRADED.value
        else:
            assert result.recording is RecordingStatus.OK
            assert "recording" not in item.detail


class MoveUpdateTrashSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            if self.attempts == 1:
                raise _sharing_violation("sharing violation while trashing old path")
        super().rename_new(source, target)


def test_move_update_retries_old_to_trash_without_republishing(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingOnceFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert _recorder_names(recorder) == ["move_updated"]
    assert recorder.flushes == 3


class MoveUpdateTrashSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            super().rename_new(source, target)
            raise _sharing_violation(
                "sharing report after committed trash rename"
            )
        super().rename_new(source, target)


def test_move_update_retry_recognizes_committed_old_to_trash_rename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert _recorder_names(recorder) == ["move_updated"]
    assert recorder.flushes == 2


def test_move_update_retry_revalidates_committed_trash_parent(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "renamed.bin"
    old_path = target / "old.bin"
    new_path = target / "renamed.bin"
    source_path.write_bytes(b"changed")
    old_path.write_bytes(b"old")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    run_root = target / ".synctrash" / str(RUN_ID)
    detached = target / f".detached-trash-{RUN_ID}"
    swapped = False

    def swap_before_retry(_delay: float) -> None:
        nonlocal swapped
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        swapped = True

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(sleep=swap_before_retry),
    )

    item = _item_outcome(events)
    assert swapped
    assert fs.attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "unsafe-path"
    assert item.detail["publish_state"] == "published"
    assert not old_path.exists()
    assert new_path.read_bytes() == b"changed"
    assert (detached / "old.bin").read_bytes() == b"old"
    assert not list(redirected.iterdir())
    assert recorder.calls == []


def test_pause_during_move_update_retry_settles_then_resumes_without_collision(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingOnceFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(PauseRequested)

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    assert fs.attempts == 2
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert trash.read_bytes() == b"old"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


@pytest.mark.parametrize(
    ("fs_factory", "expected_state"),
    [
        pytest.param(
            MoveUpdateTrashSharingOnceFileSystem,
            "new-and-old",
            id="old-still-live",
        ),
        pytest.param(
            MoveUpdateTrashSharingAfterCommitFileSystem,
            "new-and-trash",
            id="old-already-trashed",
        ),
    ],
)
def test_cancel_during_move_update_retry_reports_partial_publish(
    tmp_path: Path,
    fs_factory: Callable[[], NativeFileSystem],
    expected_state: str,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = fs_factory()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    control = _ControlLatch(Canceled)
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, control.checkpoint),
            FakeRecorder(),
            _policies(sleep=control.arm),
            fs,
        )

    item = _item_outcome(events)
    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == expected_state
    assert item.detail["trash_path"] == (
        f".synctrash\\{RUN_ID}\\old.bin"
    )
    assert item.detail["recording"] == "degraded"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}
    assert (target / "renamed.bin").read_bytes() == b"changed"
    if expected_state == "new-and-old":
        assert (target / "old.bin").read_bytes() == b"old"
        assert not trash.exists()
    else:
        assert not (target / "old.bin").exists()
        assert trash.read_bytes() == b"old"


def test_cancel_move_update_settlement_rejects_matching_trash_decoy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "renamed.bin"
    old_path = target / "old.bin"
    new_path = target / "renamed.bin"
    source_path.write_bytes(b"changed")
    old_path.write_bytes(b"old")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    run_root = trash.parent
    detached = target / f".detached-trash-{RUN_ID}"
    real_stat_path = fs.stat_path
    decoy_stat: FileStat | None = None
    decoy_reads = 0
    swapped = False
    cancel_requested = False
    events: list[object] = []

    def matching_decoy_stat(path: Path) -> FileStat | None:
        nonlocal decoy_reads
        if swapped and path == trash:
            decoy_reads += 1
            assert decoy_stat is not None
            return decoy_stat
        return real_stat_path(path)

    monkeypatch.setattr(fs, "stat_path", matching_decoy_stat)

    def swap_before_cancel(_delay: float) -> None:
        nonlocal cancel_requested, decoy_stat, swapped
        decoy_stat = real_stat_path(trash)
        assert decoy_stat is not None
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        (redirected / "old.bin").write_bytes(b"old")
        swapped = True
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=swap_before_cancel),
            fs,
        )

    item = _item_outcome(events)
    assert swapped
    assert decoy_reads == 0
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == "new-and-old-unverified"
    assert "reparse points" in item.detail["trash_state_error"]
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert not old_path.exists()
    assert new_path.read_bytes() == b"changed"
    assert (detached / "old.bin").read_bytes() == b"old"
    assert (redirected / "old.bin").read_bytes() == b"old"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


class CompositeTrashFaultFileSystem(NativeFileSystem):
    def rename_new(self, source: Path, target: Path) -> None:
        raise OSError("injected old-path trash failure")


def test_composite_fault_after_publish_leaves_both_versions_and_no_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = CompositeTrashFaultFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert (target / "old.bin").read_bytes() == b"old"
    assert recorder.calls == []


class NonByteMutationFaultFileSystem(NativeFileSystem):
    def __init__(
        self,
        primitive: str,
        *,
        commit: bool,
        sharing: bool = False,
    ) -> None:
        self.primitive = primitive
        self.commit = commit
        self.sharing = sharing
        self.faults = 0

    def _fault(self) -> None:
        self.faults += 1
        error = OSError("injected mutation fault")
        if self.sharing:
            error.winerror = 32  # type: ignore[attr-defined]
        raise error

    def rename_new(self, source: Path, target: Path) -> None:
        if self.primitive != "rename":
            return super().rename_new(source, target)
        if self.commit:
            super().rename_new(source, target)
        self._fault()

    def remove_file(self, path: Path) -> None:
        if self.primitive != "remove-file":
            return super().remove_file(path)
        if self.commit:
            super().remove_file(path)
        self._fault()

    def remove_directory(self, path: Path) -> None:
        if self.primitive != "remove-directory":
            return super().remove_directory(path)
        if self.commit:
            super().remove_directory(path)
        self._fault()

    def mkdir_new(self, path: Path) -> None:
        if self.primitive != "mkdir":
            return super().mkdir_new(path)
        if self.commit:
            super().mkdir_new(path)
        self._fault()


@dataclass(frozen=True)
class _NonByteMutationCase:
    test_id: str
    kind: OperationKind
    primitive: str
    directory_delete: bool
    mutation_state: str
    durable_state: str
    precommit_id: str | None


_NONBYTE_MUTATION_CASES = (
    _NonByteMutationCase(
        "move", OperationKind.MOVE, "rename", False,
        "committed", "target-renamed", "move",
    ),
    _NonByteMutationCase(
        "recase", OperationKind.RECASE, "rename", False,
        "unverified", "recase-state-unverified", None,
    ),
    _NonByteMutationCase(
        "trash", OperationKind.TRASH, "rename", False,
        "committed", "target-trashed", None,
    ),
    _NonByteMutationCase(
        "delete-file", OperationKind.DELETE, "remove-file", False,
        "committed", "target-deleted", "delete",
    ),
    _NonByteMutationCase(
        "delete-directory", OperationKind.DELETE, "remove-directory", True,
        "committed", "target-deleted", None,
    ),
    _NonByteMutationCase(
        "mkdir", OperationKind.MKDIR, "mkdir", False,
        "unverified", "directory-present-after-create-attempt", "mkdir",
    ),
)


_COMMITTED_NONBYTE_CASES = tuple(
    pytest.param(
        case.kind,
        case.primitive,
        case.directory_delete,
        case.mutation_state,
        case.durable_state,
        id=case.test_id,
    )
    for case in _NONBYTE_MUTATION_CASES
)


_PRECOMMIT_NONBYTE_CASES = tuple(
    pytest.param(case.kind, case.primitive, id=case.precommit_id)
    for case in _NONBYTE_MUTATION_CASES
    if case.precommit_id is not None
)


@pytest.mark.parametrize(
    ("kind", "primitive", "directory_delete", "mutation_state", "durable_state"),
    _COMMITTED_NONBYTE_CASES,
)
def test_nonbyte_commit_then_raise_degrades_unrecorded_mutation(
    tmp_path: Path,
    kind: OperationKind,
    primitive: str,
    directory_delete: bool,
    mutation_state: str,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem(primitive, commit=True)
    operation = _nonbyte_mutation_operation(
        source,
        target,
        fs,
        kind,
        directory_delete=directory_delete,
    )
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.detail["mutation_state"] == mutation_state
    assert item.detail["durable_state"] == durable_state
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if kind is OperationKind.MOVE:
        assert not (target / "old.bin").exists()
        assert (target / "new.bin").read_bytes() == b"reviewed"
    elif kind is OperationKind.RECASE:
        assert [path.name for path in target.iterdir()] == ["KEEP.txt"]
    elif kind is OperationKind.TRASH:
        assert not (target / "old.bin").exists()
        assert (target / ".synctrash" / str(RUN_ID) / "old.bin").exists()
    elif kind is OperationKind.DELETE:
        assert not (target / operation.target_rel_path).exists()
    else:
        assert (target / "folder").is_dir()


@pytest.mark.parametrize(
    ("kind", "primitive"),
    _PRECOMMIT_NONBYTE_CASES,
)
def test_nonbyte_precommit_failure_keeps_recording_ok_when_state_is_unchanged(
    tmp_path: Path,
    kind: OperationKind,
    primitive: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem(primitive, commit=False)
    operation = _nonbyte_mutation_operation(source, target, fs, kind)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert "durable_state" not in item.detail
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if kind is OperationKind.MOVE:
        assert (target / "old.bin").exists()
        assert not (target / "new.bin").exists()
    elif kind is OperationKind.DELETE:
        assert (target / "old.bin").exists()
    else:
        assert not (target / "folder").exists()


class DestinationAppearedRenameFileSystem(NativeFileSystem):
    def rename_new(self, source: Path, target: Path) -> None:
        target.write_bytes(b"foreign")
        raise FileExistsError(target)


def test_move_failure_with_retained_source_and_occupied_destination_is_ambiguous(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = DestinationAppearedRenameFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "destination-occupied"
    assert item.detail["source_state"] == "reviewed"
    assert item.detail["destination_state"] == "changed"
    assert item.detail["durable_state"] == "move-state-ambiguous"
    assert recorder.calls == []
    assert (target / "old.bin").read_bytes() == b"reviewed"
    assert (target / "new.bin").read_bytes() == b"foreign"


class PostMoveDurabilityDriftFileSystem(NativeFileSystem):
    def __init__(self, moved: Path) -> None:
        self.moved = moved
        self.faulted = False

    def flush_directory(self, path: Path) -> bool:
        if not self.faulted and self.moved.exists():
            self.moved.unlink()
            self.moved.write_bytes(b"foreign")
            self.faulted = True
            raise PermissionError("injected post-move durability fault")
        return super().flush_directory(path)


def test_committed_move_failure_probes_current_durable_state(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = PostMoveDurabilityDriftFileSystem(target / "new.bin")
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert fs.faulted
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["source_state"] == "absent"
    assert item.detail["destination_state"] == "changed"
    assert item.detail["durable_state"] == "move-state-ambiguous"
    assert recorder.calls == []
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"foreign"


def test_nonbyte_sharing_retry_retains_committed_mutation_state(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(
        xset,
        fs=fs,
        policies=_policies(
            failure=BoundedFailurePolicy(retries=1),
            max_retries=1,
        ),
    )

    item = _item_outcome(events)
    assert fs.faults == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "target-renamed"
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


@pytest.mark.parametrize(
    ("escape_stage", "sharing", "expected_reason", "escaped_message"),
    (
        ("policy", False, "io-error", "injected failure-policy escape"),
        (
            "sleep",
            True,
            "sharing-violation",
            "injected retry-sleep escape",
        ),
    ),
)
def test_collaborator_escape_settles_committed_move_from_original_error(
    tmp_path: Path,
    escape_stage: str,
    sharing: bool,
    expected_reason: str,
    escaped_message: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=sharing)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []

    class RaisingFailurePolicy:
        def on_item_failed(self, _operation, _error, _attempt):
            raise RuntimeError(escaped_message)

    def failing_sleep(_delay: float) -> None:
        raise RuntimeError(escaped_message)

    policies = _policies(
        failure=(
            RaisingFailurePolicy()
            if escape_stage == "policy"
            else BoundedFailurePolicy(retries=1)
        ),
        max_retries=1,
        sleep=failing_sleep if escape_stage == "sleep" else lambda _delay: None,
    )

    with pytest.raises(RuntimeError, match=escaped_message):
        execute(
            xset,
            RunContext(events.append, lambda: None),
            recorder,
            policies,
            fs,
        )

    item = _item_outcome(events)
    assert xset.status == {operation.op_id: Outcome.FAILED}
    assert xset.recording is RecordingStatus.DEGRADED
    assert item.reason == expected_reason
    assert item.detail["error_type"] == "OSError"
    assert item.detail["message"] == "injected mutation fault"
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "target-renamed"
    assert recorder.calls == []
    assert recorder.flushes == 2
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


def test_checkpoint_exception_finalizes_pending_mkdir_before_propagating(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    mkdir = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    (source / "later.bin").write_bytes(b"later")
    (target / "later.bin").write_bytes(b"later")
    source_stat = fs.stat(source, "later.bin")
    target_stat = fs.stat(target, "later.bin")
    assert source_stat is not None and target_stat is not None
    later = _operation(
        2,
        OperationKind.NOOP,
        source_rel_path="later.bin",
        target_rel_path="later.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (mkdir, later)))
    recorder = FakeRecorder()
    events: list[object] = []
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 2:
            raise RuntimeError("injected checkpoint infrastructure escape")

    with pytest.raises(RuntimeError, match="checkpoint infrastructure"):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    item = _item_outcome(events)
    assert xset.status == {mkdir.op_id: Outcome.SUCCEEDED}
    assert item.item_id == str(mkdir.op_id)
    assert item.outcome is Outcome.SUCCEEDED
    assert _recorder_names(recorder) == ["mkdir"]
    assert recorder.flushes == 1
    assert (target / "folder").is_dir()
    assert (target / "later.bin").read_bytes() == b"later"


def test_item_event_exception_retires_effect_without_false_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    retired: list[tuple[executor_runtime._EffectJournal, OpId]] = []
    original_retire = executor_runtime._EffectJournal.retire

    def tracked_retire(
        journal: executor_runtime._EffectJournal,
        op_id: OpId,
    ) -> None:
        original_retire(journal, op_id)
        retired.append((journal, op_id))

    monkeypatch.setattr(executor_runtime._EffectJournal, "retire", tracked_retire)

    def emit(event: object) -> None:
        if isinstance(event, ItemOutcome):
            raise RuntimeError("injected item-event escape")

    with pytest.raises(RuntimeError, match="item-event escape"):
        execute(
            xset,
            RunContext(emit, lambda: None),
            recorder,
            _policies(),
            fs,
        )

    assert xset.status == {}
    assert _recorder_names(recorder) == ["moved"]
    assert recorder.flushes == 2
    assert len(retired) == 1
    journal, op_id = retired[0]
    assert op_id == operation.op_id
    assert not journal.has_active_entry(op_id)


def test_cancel_during_nonbyte_retry_settles_committed_mutation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 2:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    item = _item_outcome(events)
    assert fs.faults == 1
    assert item.outcome is Outcome.FAILED
    assert item.detail["durable_state"] == "target-renamed"
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


def test_pause_during_nonbyte_retry_settles_committed_mutation_before_pausing(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 2:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    item = _item_outcome(events)
    assert fs.faults == 1
    assert item.outcome is Outcome.FAILED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "target-renamed"
    assert xset.recording is RecordingStatus.DEGRADED
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


class NonByteMutationProbeFailureFileSystem(NonByteMutationFaultFileSystem):
    def stat_path(self, path: Path) -> FileStat | None:
        if self.faults:
            raise PermissionError("injected mutation-state probe failure")
        return super().stat_path(path)


def test_nonbyte_probe_failure_conservatively_degrades_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationProbeFailureFileSystem("rename", commit=False)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.detail["mutation_state"] == "unverified"
    assert item.detail["durable_state"] == "move-state-unverified"
    assert "PermissionError" in item.detail["mutation_state_error"]
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert (target / "old.bin").read_bytes() == b"reviewed"
    assert not (target / "new.bin").exists()


class CreatedDirectoryMetadataFailureFileSystem(NativeFileSystem):
    def __init__(self, target: Path) -> None:
        self.target = target

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target:
            raise PermissionError("injected created-directory metadata failure")
        super().apply_metadata(path, *args, **kwargs)


def test_mkdir_deferred_metadata_failure_degrades_created_directory(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = CreatedDirectoryMetadataFailureFileSystem(target / "folder")
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "directory-created"
    assert (target / "folder").is_dir()
    assert recorder.calls == []
    assert xset.published_evidence == {}


class ResumedDirectoryRestoreFileSystem(NativeFileSystem):
    def __init__(self, directory: Path, *, failure: str | None) -> None:
        self.directory = directory
        self.failure = failure
        self.restore_attempts = 0

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.directory:
            self.restore_attempts += 1
            if self.failure == "before":
                raise PermissionError("injected resumed-directory restore failure")
        super().apply_metadata(path, *args, **kwargs)
        if path == self.directory and self.failure == "after":
            raise PermissionError("injected post-restore failure")


def _resumed_directory_execution(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
) -> tuple[ExecutionSet, PlanOperation, PlanOperation, FileStat]:
    source_directory = source / "folder"
    source_directory.mkdir()
    (source_directory / "child.bin").write_bytes(b"child")
    os.utime(source_directory, ns=(1_000_000_000, 1_000_000_000))
    (target / "folder").mkdir()
    directory_stat = fs.stat(source, "folder")
    child_stat = fs.stat(source, "folder\\child.bin")
    assert directory_stat is not None and child_stat is not None
    mkdir = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path="folder",
        target_rel_path="folder",
        source_expected=directory_stat,
        target_expected=None,
        intended=directory_stat,
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    copy = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\child.bin",
        target_rel_path="folder\\child.bin",
        source_expected=child_stat,
        target_expected=None,
        intended=child_stat,
        dependencies=(mkdir.op_id,),
    )
    xset = _xset(_plan(source, target, (mkdir, copy)))
    xset.status[mkdir.op_id] = Outcome.SUCCEEDED
    return xset, mkdir, copy, directory_stat


def test_resumed_directory_restore_failure_degrades_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure="before")
    xset, mkdir, copy, _ = _resumed_directory_execution(source, target, fs)

    result, _, recorder = _run(xset, fs=fs)

    assert fs.restore_attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.status[mkdir.op_id] is Outcome.SUCCEEDED
    assert xset.status[copy.op_id] is Outcome.SUCCEEDED
    assert _recorder_names(recorder) == ["copied"]


def test_resumed_directory_restore_then_raise_keeps_recording_truth(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure="after")
    xset, _, _, _ = _resumed_directory_execution(source, target, fs)

    result, _, recorder = _run(xset, fs=fs)

    assert fs.restore_attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert _recorder_names(recorder) == ["copied"]


def test_cancel_restores_resumed_directory_metadata_before_unwind(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure=None)
    xset, mkdir, copy, intended = _resumed_directory_execution(source, target, fs)
    recorder = FakeRecorder()
    events: list[object] = []

    def checkpoint() -> None:
        raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    restored = fs.stat(target, "folder")
    assert restored is not None
    assert fs.restore_attempts == 1
    assert restored.mtime_ns == intended.mtime_ns
    assert xset.recording is RecordingStatus.OK
    assert xset.status[mkdir.op_id] is Outcome.SUCCEEDED
    assert xset.status[copy.op_id] is Outcome.CANCELED
    assert recorder.calls == []


class ReadonlyReplaceFailureFileSystem(NativeFileSystem):
    def __init__(
        self,
        target: Path,
        *,
        fail_restore: bool,
        fail_probe: bool = False,
        commit_replace: bool = False,
    ) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.fail_probe = fail_probe
        self.commit_replace = commit_replace
        self.probe_failure_armed = False
        self.restore_attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        if self.commit_replace:
            super().replace(temp, target)
        raise PermissionError("injected replace failure")

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                self.probe_failure_armed = self.fail_probe
                raise PermissionError("injected readonly restoration failure")
        super().apply_metadata(path, *args, **kwargs)

    def stat_path(self, path: Path) -> FileStat | None:
        if path == self.target and self.probe_failure_armed:
            self.probe_failure_armed = False
            raise PermissionError("ordinary publication-state probe unavailable")
        return super().stat_path(path)


class CanceledReadonlyProbeFileSystem(NativeFileSystem):
    def __init__(
        self,
        target: Path,
        *,
        fail_restore: bool,
        commit_replace: bool = False,
    ) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.commit_replace = commit_replace
        self.restore_attempts = 0
        self.probe_failures = 0

    def replace(self, temp: Path, target: Path) -> None:
        if self.commit_replace:
            super().replace(temp, target)
        raise _sharing_violation("injected replace sharing failure")

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                raise _sharing_violation(
                    "injected readonly restoration sharing failure"
                )
        super().apply_metadata(path, *args, **kwargs)

    def stat_path(self, path: Path) -> FileStat | None:
        if path == self.target and self.probe_failures:
            self.probe_failures -= 1
            raise PermissionError("cancel publication-state probe unavailable")
        return super().stat_path(path)


@pytest.mark.parametrize(
    ("fail_restore", "fail_probe", "commit_replace", "retain_backup"),
    (
        (False, False, False, False),
        (True, False, False, False),
        (True, True, False, False),
        (False, False, True, False),
        (True, False, False, True),
        (False, False, True, True),
    ),
    ids=(
        "restored",
        "restore-failed",
        "restore-and-probe-failed",
        "published",
        "restore-failed-with-backup",
        "published-with-backup",
    ),
)
def test_failed_readonly_update_reports_durable_truth(
    tmp_path: Path,
    fail_restore: bool,
    fail_probe: bool,
    commit_replace: bool,
    retain_backup: bool,
) -> None:
    target, live, setup_fs, fs, xset = _readonly_update_setup(
        tmp_path,
        lambda path: ReadonlyReplaceFailureFileSystem(
            path,
            fail_restore=fail_restore,
            fail_probe=fail_probe,
            commit_replace=commit_replace,
        ),
        retain_backup=retain_backup,
    )

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    restored = fs.stat(target, "readonly.bin")
    assert restored is not None
    assert fs.restore_attempts == (0 if commit_replace else 1)
    assert result.status is SessionState.FAILED
    assert live.read_bytes() == (
        b"new-version" if commit_replace else b"old-version"
    )
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not fs.probe_failure_armed
    if commit_replace:
        assert item.outcome is Outcome.FAILED
        assert item.reason == "io-error"
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail["publish_state"] == "published"
        assert item.detail["target_state"] == "published"
        assert item.detail["durable_state"] == (
            "target-published-with-backup"
            if retain_backup
            else "target-published"
        )
        assert "mutation_state" not in item.detail
        assert "mutation_durable_state" not in item.detail
        if retain_backup:
            assert item.detail["backup_state"] == "retained"
            assert item.detail["backup_path"] == (
                f".synctrash\\{RUN_ID}\\readonly.bin"
            )
    elif fail_probe:
        assert item.outcome is Outcome.FAILED
        assert item.reason == "io-error"
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail == {
            "error_type": "PermissionError",
            "message": "injected readonly restoration failure",
            "publish_state": "unverified",
            "published_path": "readonly.bin",
            "durable_state": "publication-unverified",
            "state_error_type": "PermissionError",
            "state_error": "ordinary publication-state probe unavailable",
            "recording": RecordingStatus.DEGRADED.value,
            "recording_error": (
                "filesystem mutation may have published but durable state "
                "could not be verified"
            ),
            "mutation_state": "unverified",
            "mutation_durable_state": "target-metadata-changed-before-publish",
        }
    elif fail_restore:
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail["publish_state"] == "not-published"
        assert item.detail["mutation_state"] == "unverified"
        if retain_backup:
            backup = target / ".synctrash" / str(RUN_ID) / "readonly.bin"
            assert backup.read_bytes() == b"old-version"
            assert item.detail["backup"] == "hardlink"
            assert item.detail["backup_state"] == "retained"
            assert item.detail["backup_metadata"] == "unrepaired"
            assert item.detail["backup_path"] == (
                f".synctrash\\{RUN_ID}\\readonly.bin"
            )
            assert item.detail["durable_state"] == "backup-retained"
            assert item.detail["mutation_durable_state"] == (
                "target-metadata-changed-before-publish"
            )
            assert item.detail["recording"] == RecordingStatus.DEGRADED.value
            assert item.detail["recording_error"] == (
                "filesystem mutation may have committed before ledger settlement"
            )
            assert "published_path" not in item.detail
            assert not list(target.glob("*.synctmp-*"))
        else:
            assert item.detail["durable_state"] == (
                "target-metadata-changed-before-publish"
            )
    else:
        assert result.recording is RecordingStatus.OK
        assert restored.metadata.attributes & 1
        assert "durable_state" not in item.detail


@pytest.mark.parametrize(
    ("fail_restore", "commit_replace", "retain_backup"),
    (
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, False, True),
        (False, True, True),
    ),
    ids=(
        "restored",
        "restore-failed",
        "published",
        "restore-failed-with-backup",
        "published-with-backup",
    ),
)
def test_cancel_composes_byte_and_readonly_mutation_state(
    tmp_path: Path,
    fail_restore: bool,
    commit_replace: bool,
    retain_backup: bool,
) -> None:
    target, live, setup_fs, fs, xset = _readonly_update_setup(
        tmp_path,
        lambda path: CanceledReadonlyProbeFileSystem(
            path,
            fail_restore=fail_restore,
            commit_replace=commit_replace,
        ),
        retain_backup=retain_backup,
    )
    recorder = FakeRecorder()
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        if not commit_replace and not retain_backup:
            fs.probe_failures = 1
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(sleep=sleep),
            fs,
        )

    item = _item_outcome(events)
    observed = setup_fs.stat(target, "readonly.bin")
    assert observed is not None
    assert fs.probe_failures == 0
    assert item.outcome is Outcome.FAILED
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not list(target.glob("*.synctmp-*"))
    if commit_replace:
        assert fs.restore_attempts == 0
        assert item.reason == "canceled-after-publish"
        assert item.detail["publish_state"] == "published"
        assert item.detail["durable_state"] == (
            "target-published-with-backup"
            if retain_backup
            else "target-published"
        )
        assert "mutation_state" not in item.detail
        assert "mutation_durable_state" not in item.detail
        assert xset.recording is RecordingStatus.DEGRADED
        assert live.read_bytes() == b"new-version"
        assert not observed.metadata.attributes & 1
        if retain_backup:
            assert item.detail["backup_state"] == "retained"
            assert item.detail["backup_path"] == (
                f".synctrash\\{RUN_ID}\\readonly.bin"
            )
    elif fail_restore:
        assert fs.restore_attempts == 1
        assert item.reason == "canceled-after-mutation"
        assert xset.recording is RecordingStatus.DEGRADED
        assert not observed.metadata.attributes & 1
        assert item.detail["mutation_state"] == "unverified"
        assert item.detail["mutation_durable_state"] == (
            "target-metadata-changed-before-publish"
        )
        assert item.detail["recording"] == RecordingStatus.DEGRADED.value
        if retain_backup:
            backup = target / ".synctrash" / str(RUN_ID) / "readonly.bin"
            assert backup.read_bytes() == b"old-version"
            assert item.detail["backup"] == "hardlink"
            assert item.detail["backup_state"] == "retained"
            assert item.detail["backup_metadata"] == "unrepaired"
            assert item.detail["backup_path"] == (
                f".synctrash\\{RUN_ID}\\readonly.bin"
            )
            assert item.detail["durable_state"] == "backup-retained"
    else:
        assert fs.restore_attempts == 1
        assert item.reason == "io-error"
        assert xset.recording is RecordingStatus.OK
        assert observed.metadata.attributes & 1
        assert "mutation_state" not in item.detail
        assert "mutation_durable_state" not in item.detail
        assert "recording" not in item.detail
    if not commit_replace:
        if retain_backup:
            assert item.detail["publish_state"] == "not-published"
            assert item.detail["durable_state"] == "backup-retained"
            assert "state_error_type" not in item.detail
            assert "state_error" not in item.detail
        else:
            assert item.detail["publish_state"] == "unverified"
            assert item.detail["durable_state"] == "unverified"
            assert item.detail["state_error_type"] == "PermissionError"
            assert item.detail["state_error"] == (
                "cancel publication-state probe unavailable"
            )
        assert live.read_bytes() == b"old-version"


class FailingReadonlyDeleteFileSystem(NativeFileSystem):
    def __init__(self, target: Path, *, fail_restore: bool) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.restore_attempts = 0

    def remove_file(self, path: Path) -> None:
        raise PermissionError("injected delete failure")

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                raise PermissionError("injected readonly restoration failure")
        super().apply_metadata(path, *args, **kwargs)


@pytest.mark.parametrize("fail_restore", [False, True], ids=("restored", "restore-failed"))
def test_failed_readonly_delete_reports_restoration_truth(
    tmp_path: Path,
    fail_restore: bool,
) -> None:
    source, target = _roots(tmp_path)
    live = target / "readonly.bin"
    live.write_bytes(b"keep")
    setup_fs = NativeFileSystem()
    expected = setup_fs.stat(target, "readonly.bin")
    assert expected is not None
    _make_readonly(setup_fs, live, expected)
    fs = FailingReadonlyDeleteFileSystem(live, fail_restore=fail_restore)
    expected = fs.stat(target, "readonly.bin")
    assert expected is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="readonly.bin",
        source_expected=None,
        target_expected=expected,
        intended=None,
    )
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = _item_outcome(events)
    restored = fs.stat(target, "readonly.bin")
    assert result.status is SessionState.FAILED
    assert live.read_bytes() == b"keep"
    assert restored is not None
    assert fs.restore_attempts == 1
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if fail_restore:
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail["mutation_state"] == "unverified"
        assert item.detail["durable_state"] == "target-changed-after-delete-attempt"
    else:
        assert result.recording is RecordingStatus.OK
        assert restored.metadata.attributes & 1
        assert "durable_state" not in item.detail


def test_effect_settlement_reducer_policy_matrix() -> None:
    PC = executor_runtime._PublicationClassification
    MC = executor_runtime._MutationClassification
    MS = executor_runtime._MutationState
    DS = executor_runtime._DurableState
    ordinary = executor_runtime._TerminalCause(
        executor_runtime._TerminalKind.ORDINARY_FAILURE,
        ExecutionReason.TARGET_DRIFT,
        "OperationFailure",
        "operation failed",
    )
    canceled = executor_runtime._TerminalCause(
        executor_runtime._TerminalKind.CANCELLATION,
        ExecutionReason.CANCELED,
        "Canceled",
        "execution canceled",
    )
    state_probe = executor_runtime._ProbeDiagnostic(
        ExecutionReason.TARGET_MISSING,
        "OperationFailure",
        "state unknown",
    )
    backup = executor_runtime._BackupVerdict(
        ".synctrash\\run\\file.bin",
        executor_runtime._BackupState.RETAINED,
        metadata="unrepaired",
    )

    def publication(
        classification: executor_runtime._PublicationClassification,
        *,
        kind: OperationKind = OperationKind.COPY,
        detail: dict[str, object] | None = None,
        target: executor_runtime._TargetState | None = None,
        retained_backup: bool = False,
        probe: executor_runtime._ProbeDiagnostic | None = None,
    ) -> executor_runtime._PublicationVerdict:
        return executor_runtime._PublicationVerdict(
            classification,
            kind,
            "file.bin",
            {} if detail is None else detail,
            target_state=target,
            backup=backup if retained_backup else None,
            probe_error=probe,
        )

    def mutation(
        classification: executor_runtime._MutationClassification,
        state: executor_runtime._MutationState,
        durable: executor_runtime._DurableState,
        *,
        kind: OperationKind = OperationKind.DELETE,
    ) -> executor_runtime._MutationVerdict:
        return executor_runtime._MutationVerdict(
            classification,
            kind,
            state,
            durable,
        )

    unchanged = mutation(MC.UNCHANGED, MS.NOT_COMMITTED, DS.TARGET_RETAINED)
    durable = mutation(MC.DURABLE, MS.COMMITTED, DS.TARGET_DELETED)
    ambiguous = mutation(
        MC.AMBIGUOUS, MS.UNVERIFIED, DS.TARGET_CHANGED_AFTER_DELETE_ATTEMPT
    )
    unreadable = mutation(MC.UNREADABLE, MS.UNVERIFIED, DS.DELETE_STATE_UNVERIFIED)
    degraded = RecordingStatus.DEGRADED.value
    mutation_error = "filesystem mutation may have committed before ledger settlement"
    unverified_error = (
        "filesystem mutation may have published but durable state could not be verified"
    )
    published_error = "published filesystem mutation failed before ledger settlement"
    canceled_publish = (
        "cancellation interrupted settlement of a published filesystem mutation"
    )
    canceled_mutation = (
        "cancellation interrupted settlement after a mutation attempt"
    )

    @dataclass(frozen=True, slots=True)
    class Expected:
        outcome: Outcome = Outcome.FAILED
        reason: ExecutionReason = ExecutionReason.TARGET_DRIFT
        degrade: bool = True
        publish: str | None = None
        durable: str | None = None
        sibling: str | None = None
        recording: str | None = degraded
        recording_error: str | None = mutation_error

    # Selected precedence axes only; operation tests retain probe and timing coverage.
    cases = [
        (
            "ordinary-retained-backup",
            ordinary,
            publication(
                PC.NOT_PUBLISHED,
                kind=OperationKind.UPDATE,
                detail={"durable_state": "misleading"},
                retained_backup=True,
            ),
            None,
            Expected(
                degrade=False,
                publish="not-published",
                durable="backup-retained",
                recording=None,
                recording_error=None,
            ),
        ),
        (
            "ordinary-unverified-plus-ambiguous",
            ordinary,
            publication(
                PC.UNVERIFIED,
                detail={"recording": "misleading", "recording_error": "misleading"},
                probe=state_probe,
            ),
            ambiguous,
            Expected(
                publish="unverified",
                durable="publication-unverified",
                sibling="target-changed-after-delete-attempt",
                recording_error=unverified_error,
            ),
        ),
        (
            "ordinary-confirmed-suppresses-sibling",
            ordinary,
            publication(
                PC.CONFIRMED,
                target=executor_runtime._TargetState.PUBLISHED,
            ),
            unreadable,
            Expected(
                publish="published",
                durable="target-published",
                recording_error=published_error,
            ),
        ),
        (
            "cancel-not-published",
            canceled,
            publication(PC.NOT_PUBLISHED),
            unchanged,
            Expected(
                outcome=Outcome.CANCELED,
                reason=ExecutionReason.CANCELED,
                degrade=False,
                publish="not-published",
                durable="target-not-published",
                recording=None,
                recording_error=None,
            ),
        ),
        (
            "cancel-confirmed-suppresses-sibling",
            canceled,
            publication(
                PC.CONFIRMED,
                target=executor_runtime._TargetState.PUBLISHED,
            ),
            unreadable,
            Expected(
                reason=ExecutionReason.CANCELED_AFTER_PUBLISH,
                publish="published",
                durable="target-published",
                recording_error=canceled_publish,
            ),
        ),
        (
            "cancel-unverified-retained-backup",
            canceled,
            publication(
                PC.UNVERIFIED,
                kind=OperationKind.UPDATE,
                detail={"durable_state": "misleading"},
                retained_backup=True,
                probe=state_probe,
            ),
            None,
            Expected(
                reason=ExecutionReason.TARGET_MISSING,
                degrade=False,
                publish="unverified",
                durable="backup-retained",
                recording=None,
                recording_error=None,
            ),
        ),
        (
            "cancel-unverified-plus-mutation",
            canceled,
            publication(
                PC.UNVERIFIED,
                probe=state_probe,
            ),
            ambiguous,
            Expected(
                reason=ExecutionReason.CANCELED_AFTER_MUTATION,
                publish="unverified",
                durable="unverified",
                sibling="target-changed-after-delete-attempt",
            ),
        ),
        ("ordinary-unchanged", ordinary, None, unchanged, None),
    ]
    for name, verdict in (
        ("durable", durable),
        ("ambiguous", ambiguous),
        ("unreadable", unreadable),
    ):
        wanted = Expected(durable=verdict.durable_state.value)
        cases.append((f"ordinary-{name}", ordinary, None, verdict, wanted))

    details: dict[str, dict[str, object]] = {}
    for name, cause, published, attempted, expected in cases:
        before = None if published is None else dict(published.base_detail)
        reduction = executor_runtime._reduce_effect_settlement(
            cause,
            published,
            attempted,
        )
        if reduction is None:
            actual = None
        else:
            detail = reduction.settled.detail
            details[name] = detail
            actual = Expected(
                outcome=reduction.settled.outcome,
                reason=reduction.settled.reason,
                degrade=reduction.degrade_recording,
                publish=detail.get("publish_state"),
                durable=detail.get("durable_state"),
                sibling=detail.get("mutation_durable_state"),
                recording=detail.get("recording"),
                recording_error=detail.get("recording_error"),
            )
            assert reduction.settled.published_evidence is None, name
        assert actual == expected, name
        assert published is None or published.base_detail == before, name

    assert details["ordinary-unverified-plus-ambiguous"]["state_error"] == (
        "state unknown"
    )
    assert details["cancel-unverified-retained-backup"]["backup_state"] == (
        "retained"
    )
    assert details["ordinary-retained-backup"]["message"] == "operation failed"
    assert details["cancel-unverified-plus-mutation"]["message"] == (
        canceled_mutation
    )
    for name in (
        "ordinary-confirmed-suppresses-sibling",
        "cancel-confirmed-suppresses-sibling",
    ):
        assert "mutation_state" not in details[name]


class SettlementObservationFileSystem(NativeFileSystem):
    def __init__(
        self,
        observations: dict[Path, FileStat | None | Exception],
    ) -> None:
        self.observations = {
            os.path.normcase(os.path.normpath(str(path))): observed
            for path, observed in observations.items()
        }

    def revalidate_root(self, root: Path, **_kwargs: object) -> None:
        return None

    def resolve(self, root: Path, relative_path: str, *, must_exist: bool) -> Path:
        del must_exist
        return root.joinpath(*PureWindowsPath(relative_path).parts)

    def revalidate_trash_destination(self, *_args: object) -> None:
        return None

    def stat_path(self, path: Path) -> FileStat | None:
        key = os.path.normcase(os.path.normpath(str(path)))
        if key not in self.observations:
            raise AssertionError(f"unexpected settlement observation: {path}")
        observed = self.observations[key]
        if isinstance(observed, Exception):
            raise observed
        return observed


def _ordinary_settlement_cause() -> executor_runtime._TerminalCause:
    return executor_runtime._TerminalCause(
        executor_runtime._TerminalKind.ORDINARY_FAILURE,
        ExecutionReason.TARGET_DRIFT,
        "OperationFailure",
        "operation failed",
    )


def test_mutation_observer_and_reducer_cover_restored_missing_and_unreadable_states(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    reviewed_path = target / "reviewed.bin"
    reviewed_path.write_bytes(b"reviewed")
    reviewed = NativeFileSystem().stat(target, "reviewed.bin")
    assert reviewed is not None
    xset = _xset(_plan(source, target, ()))
    state = executor_runtime._ExecutionState(xset, {})
    trash_destination = target / ".synctrash" / str(RUN_ID) / "trash.bin"

    cases = (
        (
            "move-restored",
            executor_runtime._MutationAttempt(
                OperationKind.MOVE,
                target / "move-old.bin",
                reviewed,
                secondary=target / "move-new.bin",
                destination_relative="move-new.bin",
                committed=True,
            ),
            {
                target / "move-old.bin": reviewed,
                target / "move-new.bin": None,
            },
            executor_runtime._MutationClassification.DURABLE,
            executor_runtime._DurableState.SOURCE_RESTORED_AFTER_MOVE,
        ),
        (
            "trash-restored",
            executor_runtime._MutationAttempt(
                OperationKind.TRASH,
                target / "trash.bin",
                reviewed,
                secondary=trash_destination,
                destination_relative=f".synctrash\\{RUN_ID}\\trash.bin",
                trash_source_relative="trash.bin",
                committed=True,
            ),
            {
                target / "trash.bin": reviewed,
                trash_destination: None,
            },
            executor_runtime._MutationClassification.DURABLE,
            executor_runtime._DurableState.SOURCE_RESTORED_AFTER_TRASH,
        ),
        (
            "delete-restored",
            executor_runtime._MutationAttempt(
                OperationKind.DELETE,
                target / "delete.bin",
                reviewed,
                committed=True,
            ),
            {target / "delete.bin": reviewed},
            executor_runtime._MutationClassification.DURABLE,
            executor_runtime._DurableState.TARGET_RESTORED_AFTER_DELETE,
        ),
        (
            "mkdir-disappeared",
            executor_runtime._MutationAttempt(
                OperationKind.MKDIR,
                target / "folder",
                None,
                committed=True,
            ),
            {target / "folder": None},
            executor_runtime._MutationClassification.DURABLE,
            executor_runtime._DurableState.DIRECTORY_MISSING_AFTER_CREATE,
        ),
        (
            "delete-unreadable",
            executor_runtime._MutationAttempt(
                OperationKind.DELETE,
                target / "delete-unreadable.bin",
                reviewed,
            ),
            {
                target / "delete-unreadable.bin": PermissionError(
                    "delete state probe unavailable"
                )
            },
            executor_runtime._MutationClassification.UNREADABLE,
            executor_runtime._DurableState.DELETE_STATE_UNVERIFIED,
        ),
        (
            "update-unreadable",
            executor_runtime._MutationAttempt(
                OperationKind.UPDATE,
                target / "update-unreadable.bin",
                reviewed,
            ),
            {
                target / "update-unreadable.bin": PermissionError(
                    "update state probe unavailable"
                )
            },
            executor_runtime._MutationClassification.UNREADABLE,
            executor_runtime._DurableState.UPDATE_STATE_UNVERIFIED,
        ),
    )

    for name, attempt, observations, classification, durable_state in cases:
        verdict = executor_runtime._observe_mutation(
            attempt,
            SettlementObservationFileSystem(observations),
            state,
        )
        assert verdict.classification is classification, name
        assert verdict.durable_state is durable_state, name

        reduction = executor_runtime._reduce_effect_settlement(
            _ordinary_settlement_cause(),
            None,
            verdict,
        )
        assert reduction is not None, name
        assert reduction.degrade_recording, name
        assert reduction.settled.outcome is Outcome.FAILED, name
        assert reduction.settled.reason is ExecutionReason.TARGET_DRIFT, name
        assert reduction.settled.detail["durable_state"] == durable_state.value, name
        assert reduction.settled.detail["recording"] == "degraded", name
        if classification is executor_runtime._MutationClassification.UNREADABLE:
            assert reduction.settled.detail["mutation_state"] == "unverified", name
            assert "mutation_state_error" in reduction.settled.detail, name


def test_published_target_observer_and_reducer_cover_changed_missing_and_unreadable(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    reviewed_path = target / "reviewed.bin"
    reviewed_path.write_bytes(b"reviewed")
    changed_path = target / "changed.bin"
    changed_path.write_bytes(b"changed-version")
    native = NativeFileSystem()
    reviewed = native.stat(target, "reviewed.bin")
    changed = native.stat(target, "changed.bin")
    assert reviewed is not None and changed is not None
    xset = _xset(_plan(source, target, ()))
    published_path = target / "published.bin"

    cases = (
        (
            "changed",
            changed,
            executor_runtime._TargetState.CHANGED_AFTER_PUBLISH,
            executor_runtime._DurableState.TARGET_CHANGED_AFTER_PUBLISH,
        ),
        (
            "missing",
            None,
            executor_runtime._TargetState.MISSING_AFTER_PUBLISH,
            executor_runtime._DurableState.TARGET_MISSING_AFTER_PUBLISH,
        ),
        (
            "unreadable",
            PermissionError("published target probe unavailable"),
            executor_runtime._TargetState.UNVERIFIED_AFTER_PUBLISH,
            executor_runtime._DurableState.TARGET_UNVERIFIED_AFTER_PUBLISH,
        ),
    )

    for name, observed, target_state, durable_state in cases:
        actual_state, diagnostic = executor_runtime._observe_published_target(
            published_path,
            reviewed,
            SettlementObservationFileSystem({published_path: observed}),
            xset,
            target,
        )
        assert actual_state is target_state, name
        assert (diagnostic is not None) is (name == "unreadable"), name

        publication = executor_runtime._PublicationVerdict(
            executor_runtime._PublicationClassification.CONFIRMED,
            OperationKind.COPY,
            "published.bin",
            {},
            target_state=actual_state,
            target_state_error=diagnostic,
        )
        reduction = executor_runtime._reduce_effect_settlement(
            _ordinary_settlement_cause(),
            publication,
            None,
        )
        assert reduction is not None, name
        assert reduction.degrade_recording, name
        assert reduction.settled.detail["publish_state"] == "published", name
        assert reduction.settled.detail["target_state"] == target_state.value, name
        assert reduction.settled.detail["durable_state"] == durable_state.value, name
        if name == "unreadable":
            assert reduction.settled.detail["target_state_error"] == (
                "PermissionError: published target probe unavailable"
            )


def _journal_copy_effect(tmp_path: Path) -> executor_runtime._CopyContinuation:
    root = tmp_path / "journal"
    root.mkdir()
    source = root / "source.bin"
    source.write_bytes(b"journal")
    stat = NativeFileSystem().stat(root, "source.bin")
    assert stat is not None
    prepared = executor_runtime._PreparedCopy(
        source=source,
        target=root / "target.bin",
        temp=root / "target.bin.synctmp-owned",
        digest=CopyDigest(b"\x00" * 16, len(b"journal")),
        intended=stat,
        finalized=stat,
    )
    return executor_runtime._CopyContinuation(prepared, stat)


def test_effect_journal_retains_independent_channels_until_settlement(
    tmp_path: Path,
) -> None:
    op_id = OpId("1" * 32)
    journal = executor_runtime._EffectJournal()
    byte = _journal_copy_effect(tmp_path)
    mutation = executor_runtime._MutationAttempt(
        OperationKind.UPDATE,
        byte.prepared.target,
        byte.prepared_stat,
    )
    retry_error = PermissionError("retry")

    journal.claim_temporary_path(op_id, byte.prepared.temp)
    journal.install_byte(op_id, byte)
    assert journal.retain_mutation(op_id, mutation) is mutation
    journal.remember_retry_error(op_id, retry_error)

    snapshot = journal.snapshot(op_id)
    assert snapshot == executor_runtime._EffectSnapshot(
        byte=byte,
        mutation=mutation,
        retry_error=retry_error,
        temporary_path=byte.prepared.temp,
    )
    assert journal.has_retained_effect(op_id)
    with pytest.raises(RuntimeError, match="still owns"):
        journal.settle(op_id)
    with pytest.raises(RuntimeError, match="not settled"):
        journal.retire(op_id)

    assert journal.release_temporary_path(
        op_id,
        expected=byte.prepared.temp,
    ) == byte.prepared.temp
    journal.settle(op_id)
    journal.retire(op_id)
    assert journal.snapshot(op_id) == executor_runtime._EffectSnapshot()


def test_effect_journal_retry_error_and_temp_are_not_retained_effects(
    tmp_path: Path,
) -> None:
    op_id = OpId("2" * 32)
    other_op_id = OpId("3" * 32)
    temp = tmp_path / "owned.temp"
    journal = executor_runtime._EffectJournal()
    retry_error = PermissionError("retry")

    journal.remember_retry_error(op_id, retry_error)
    journal.claim_temporary_path(op_id, temp)

    assert not journal.has_retained_effect(op_id)
    assert journal.snapshot(op_id).retry_error is retry_error
    with pytest.raises(RuntimeError, match="already owns"):
        journal.claim_temporary_path(other_op_id, tmp_path / "other.temp")
    with pytest.raises(RuntimeError, match="ownership changed"):
        journal.release_temporary_path(op_id, expected=tmp_path / "wrong.temp")
    assert journal.release_temporary_path(op_id, expected=temp) == temp
    journal.settle(op_id)
    journal.retire(op_id)


def test_effect_journal_reuses_only_the_same_mutation_attempt(tmp_path: Path) -> None:
    op_id = OpId("4" * 32)
    primary = tmp_path / "primary"
    journal = executor_runtime._EffectJournal()
    retained = executor_runtime._MutationAttempt(
        OperationKind.MOVE,
        primary,
        None,
        secondary=tmp_path / "secondary",
    )
    assert journal.retain_mutation(op_id, retained) is retained
    retained.committed = True

    equivalent = executor_runtime._MutationAttempt(
        OperationKind.MOVE,
        primary,
        None,
        secondary=tmp_path / "secondary",
    )
    assert journal.retain_mutation(op_id, equivalent) is retained
    with pytest.raises(RuntimeError, match="changed during retry"):
        journal.retain_mutation(
            op_id,
            executor_runtime._MutationAttempt(
                OperationKind.MOVE,
                primary,
                None,
                secondary=tmp_path / "different",
            ),
        )
    journal.settle(op_id)
    journal.retire(op_id)


def test_effect_journal_retires_after_terminal_item_and_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"journal-order")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    timeline: list[str] = []
    retired_journals: list[executor_runtime._EffectJournal] = []
    original_settle = executor_runtime._EffectJournal.settle
    original_retire = executor_runtime._EffectJournal.retire

    def tracked_settle(
        journal: executor_runtime._EffectJournal,
        op_id: OpId,
    ) -> None:
        entry = journal._entries[op_id]
        assert not entry.settled
        timeline.append("settle")
        original_settle(journal, op_id)

    def tracked_retire(
        journal: executor_runtime._EffectJournal,
        op_id: OpId,
    ) -> None:
        assert journal._entries[op_id].settled
        timeline.append("retire")
        retired_journals.append(journal)
        original_retire(journal, op_id)

    monkeypatch.setattr(executor_runtime._EffectJournal, "settle", tracked_settle)
    monkeypatch.setattr(executor_runtime._EffectJournal, "retire", tracked_retire)

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome):
            timeline.append("item")
        elif isinstance(body, Progress) and body.items_done == 1:
            timeline.append("progress")

    result = execute(
        xset,
        RunContext(emit, lambda: None),
        FakeRecorder(),
        _policies(),
        fs,
    )

    assert result.status is SessionState.COMPLETED
    assert timeline[:4] == ["item", "progress", "settle", "retire"]
    assert len(retired_journals) == 1
    assert operation.op_id not in retired_journals[0]._entries
