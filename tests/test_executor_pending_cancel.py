"""Cancellation cannot replace an outcome awaiting reliable delivery."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PureWindowsPath

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome, Progress
from namisync.core.execution import ExecutionReason, ExecutionSet, ItemRecordingReason
from namisync.core.planning import OpId, OperationKind, OperationReason, PlanOperation
from namisync.core.session import Canceled, RunContext, SessionState, run_session
from namisync.modules.executor import NativeFileSystem, execute
import namisync.modules.executor.runtime as executor_runtime

from _executor_fixtures import (
    FakeRecorder,
    _nonbyte_mutation_operation,
    _operation,
    _plan,
    _policies,
    _reviewed_byte_operation,
    _roots,
    _xset,
)


class _CountingRecorder(FakeRecorder):
    def __init__(self, *, fail: str | None = None) -> None:
        super().__init__(fail=fail)
        self.attempts: list[str] = []

    def _record(self, name: str, first: object, second: object | None = None) -> None:
        self.attempts.append(name)
        super()._record(name, first, second)


class _CanceledDelivery:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        xset: ExecutionSet,
        rejected_id: OpId,
        *,
        original: Exception | None = None,
        secondary: Exception | None = None,
    ) -> None:
        self.xset = xset
        self.rejected_id = rejected_id
        self.original = Canceled() if original is None else original
        self.secondary = secondary
        self.offered: list[ItemOutcome] = []
        self.events: list[object] = []
        self.retained: list[
            tuple[OpId, executor_runtime._EffectJournal, executor_runtime._Settled]
        ] = []
        self.retired: list[OpId] = []
        self.canceled_reductions: list[OpId] = []
        original_retain = executor_runtime._EffectJournal.retain_pending_settlement
        original_retire = executor_runtime._EffectJournal.retire
        original_reduce = executor_runtime._canceled_durable_settlement

        def retain(journal, op_id, settled):
            value = original_retain(journal, op_id, settled)
            self.retained.append((op_id, journal, value))
            return value

        def retire(journal, op_id):
            assert op_id in {OpId(item.item_id) for item in self.accepted}
            assert self.progress[-1].items_done == len(self.accepted)
            original_retire(journal, op_id)
            self.retired.append(op_id)

        def reduce(operation, *args):
            self.canceled_reductions.append(operation.op_id)
            return original_reduce(operation, *args)

        monkeypatch.setattr(
            executor_runtime._EffectJournal, "retain_pending_settlement", retain
        )
        monkeypatch.setattr(executor_runtime._EffectJournal, "retire", retire)
        monkeypatch.setattr(executor_runtime, "_canceled_durable_settlement", reduce)

    @property
    def accepted(self) -> list[ItemOutcome]:
        return [event for event in self.events if isinstance(event, ItemOutcome)]

    @property
    def progress(self) -> list[Progress]:
        return [event for event in self.events if isinstance(event, Progress)]

    def emit(self, body: object) -> None:
        if isinstance(body, ItemOutcome):
            op_id = OpId(body.item_id)
            assert op_id not in self.xset.status
            assert op_id not in self.xset.published_evidence
            self.offered.append(body)
            if op_id == self.rejected_id:
                attempts = sum(
                    item.item_id == body.item_id for item in self.offered
                )
                if attempts == 1:
                    raise self.original
                if self.secondary is not None:
                    raise self.secondary
        self.events.append(body)

    def assert_replayed(self, op_id: OpId) -> executor_runtime._Settled:
        retained = [entry for entry in self.retained if entry[0] == op_id]
        assert len(retained) == 2
        _, journal, pending = retained[0]
        assert retained[1][1] is journal
        assert retained[1][2] is pending
        offered = [item for item in self.offered if item.item_id == str(op_id)]
        assert len(offered) == 2
        assert offered[1] == offered[0]
        assert [item for item in self.accepted if item.item_id == str(op_id)] == [
            offered[1]
        ]
        assert self.retired.count(op_id) == 1
        assert not journal.has_active_entry(op_id)
        assert journal.pending_settlement(op_id) is None
        assert op_id not in self.canceled_reductions
        return pending


def _following_copy(source: Path, fs: NativeFileSystem) -> PlanOperation:
    (source / "later.bin").write_bytes(b"later-payload")
    source_stat = fs.stat(source, "later.bin")
    assert source_stat is not None
    return _operation(
        2,
        OperationKind.COPY,
        source_rel_path="later.bin",
        target_rel_path="later.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )


@pytest.mark.parametrize(
    ("kind", "record_method"),
    [
        (OperationKind.COPY, "copied"),
        (OperationKind.UPDATE, "updated"),
        (OperationKind.MOVE_UPDATE, "move_updated"),
    ],
)
@pytest.mark.parametrize("recording_fails", [False, True])
def test_cancel_replays_pending_byte_outcome_without_reclassifying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: OperationKind,
    record_method: str,
    recording_fails: bool,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation, published_path = _reviewed_byte_operation(kind, source, target, fs)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = _CountingRecorder(fail=record_method if recording_fails else None)
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id)

    with pytest.raises(Canceled) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is delivery.original
    pending = delivery.assert_replayed(operation.op_id)
    assert pending.outcome is Outcome.SUCCEEDED
    assert pending.reason is None
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    evidence = xset.published_evidence[operation.op_id]
    assert evidence is pending.published_evidence
    assert evidence.copy_recorded is not recording_fails
    assert evidence.recorded_identity == (
        None if recording_fails else recorder._copy_identity(operation.op_id)
    )
    assert xset.recording_reasons == (
        {operation.op_id: ItemRecordingReason.RECORD_WRITE_FAILED}
        if recording_fails else {}
    )
    assert recorder.attempts == [record_method]
    assert published_path.read_bytes() == b"new-version"
    assert not list(target.glob("*.synctmp-*"))
    assert delivery.progress[-1].items_done == 1
    assert delivery.progress[-1].bytes_done == operation.content_bytes
    assert delivery.progress[-1].item_id is None
    assert delivery.progress[-1].current_path is None


def test_cancel_preserves_pending_prerequisite_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.DELETE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = _CountingRecorder(fail="flush")
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id)

    with pytest.raises(Canceled) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is delivery.original
    pending = delivery.assert_replayed(operation.op_id)
    assert pending.outcome is Outcome.FAILED
    assert pending.reason is ExecutionReason.RECORDER_FAILED
    assert pending.recording_reason is ItemRecordingReason.RECORDING_PREREQUISITE_FAILED
    assert xset.status == {operation.op_id: Outcome.FAILED}
    assert xset.published_evidence == {}
    assert xset.recording_reasons == {
        operation.op_id: ItemRecordingReason.RECORDING_PREREQUISITE_FAILED
    }
    assert recorder.attempts == []
    assert (target / "old.bin").read_bytes() == b"reviewed"


@pytest.mark.parametrize("later_copy", [False, True])
@pytest.mark.parametrize("recording_fails", [False, True])
def test_cancel_replays_pending_mkdir_even_when_current_is_already_settled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    later_copy: bool,
    recording_fails: bool,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    operations = (
        (operation, _following_copy(source, fs)) if later_copy else (operation,)
    )
    xset = _xset(_plan(source, target, operations))
    recorder = _CountingRecorder(fail="mkdir" if recording_fails else None)
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id)

    with pytest.raises(Canceled) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is delivery.original
    pending = delivery.assert_replayed(operation.op_id)
    assert pending.outcome is Outcome.SUCCEEDED
    assert pending.published_evidence is None
    assert xset.status == {item.op_id: Outcome.SUCCEEDED for item in operations}
    assert xset.recording_reasons == (
        {operation.op_id: ItemRecordingReason.RECORD_WRITE_FAILED}
        if recording_fails else {}
    )
    assert recorder.attempts == (["copied", "mkdir"] if later_copy else ["mkdir"])
    assert (target / "folder").is_dir()
    assert delivery.progress[-1].items_done == len(operations)
    assert delivery.progress[-1].item_id is None
    assert delivery.progress[-1].current_path is None


def test_cancel_preserves_pending_deferred_mkdir_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    later = _following_copy(source, fs)
    xset = _xset(_plan(source, target, (operation, later)))
    original_apply = fs.apply_metadata
    metadata_attempts = 0

    def apply_metadata(path, *args, **kwargs):
        nonlocal metadata_attempts
        if path == target / "folder":
            metadata_attempts += 1
            raise OSError("injected directory metadata failure")
        return original_apply(path, *args, **kwargs)

    monkeypatch.setattr(fs, "apply_metadata", apply_metadata)
    recorder = _CountingRecorder()
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id)

    with pytest.raises(Canceled) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is delivery.original
    pending = delivery.assert_replayed(operation.op_id)
    assert pending.outcome is Outcome.FAILED
    assert pending.reason is ExecutionReason.IO_ERROR
    assert pending.recording_reason is ItemRecordingReason.UNRECORDED_MUTATION
    assert pending.detail["message"] == "injected directory metadata failure"
    assert xset.status == {later.op_id: Outcome.SUCCEEDED, operation.op_id: Outcome.FAILED}
    assert recorder.attempts == ["copied"]
    assert metadata_attempts == 1
    assert (target / "folder").is_dir()


@pytest.mark.parametrize("later_copy", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_cancel_finishes_remaining_deferred_directories_after_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    later_copy: bool,
    nested: bool,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    first = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    second_path = r"folder\nested" if nested else "other"
    source.joinpath(*PureWindowsPath(second_path).parts).mkdir()
    other_stat = fs.stat(source, second_path)
    assert other_stat is not None
    if nested:
        parent_stat = fs.stat(source, "folder")
        assert parent_stat is not None
        first = replace(
            first,
            source_expected=parent_stat,
            intended=parent_stat,
            metadata=parent_stat.metadata,
        )
    second = _operation(
        2,
        OperationKind.MKDIR,
        source_rel_path=second_path,
        target_rel_path=second_path,
        source_expected=other_stat,
        target_expected=None,
        intended=other_stat,
        dependencies=(first.op_id,) if nested else (),
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    later = (
        replace(_following_copy(source, fs), op_id=OpId(f"{3:032x}"))
        if later_copy else None
    )
    operations = (first, second) if later is None else (first, second, later)
    xset = _xset(_plan(source, target, operations))
    recorder = _CountingRecorder()
    directory_order = (second, first) if nested else (first, second)
    directory_paths = [
        target.joinpath(*PureWindowsPath(operation.target_rel_path).parts)
        for operation in directory_order
    ]
    metadata_paths: list[Path] = []
    original_apply = fs.apply_metadata

    def apply_metadata(path, *args, **kwargs):
        if path in directory_paths:
            metadata_paths.append(path)
        return original_apply(path, *args, **kwargs)

    monkeypatch.setattr(fs, "apply_metadata", apply_metadata)
    delivery = _CanceledDelivery(monkeypatch, xset, directory_order[0].op_id)

    with pytest.raises(Canceled) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is delivery.original
    delivery.assert_replayed(directory_order[0].op_id)
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED for operation in operations}
    assert xset.recording_reasons == {}
    assert xset.recording is RecordingStatus.OK
    expected_calls = ([] if later is None else [("copied", later.op_id)]) + [
        ("mkdir", operation.op_id) for operation in directory_order
    ]
    assert [(name, op_id) for name, op_id, _ in recorder.calls] == expected_calls
    assert recorder.attempts == [name for name, _ in expected_calls]
    assert [item.item_id for item in delivery.accepted] == [
        str(op_id) for _, op_id in expected_calls
    ]
    assert delivery.retired == [op_id for _, op_id in expected_calls]
    assert delivery.progress[-1].items_done == len(operations)
    assert delivery.progress[-1].item_id is None
    assert delivery.progress[-1].current_path is None
    assert metadata_paths == directory_paths
    assert delivery.canceled_reductions == []
    for operation in (first, second):
        actual = fs.stat(target, operation.target_rel_path)
        assert actual is not None and operation.intended is not None
        assert actual.mtime_ns == operation.intended.mtime_ns
    if later_copy:
        assert (target / "later.bin").read_bytes() == b"later-payload"


def test_ordinary_directory_sink_failure_does_not_requeue_metadata_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    first = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    (source / "other").mkdir()
    other_stat = fs.stat(source, "other")
    assert other_stat is not None
    second = _operation(
        2,
        OperationKind.MKDIR,
        source_rel_path="other",
        target_rel_path="other",
        source_expected=other_stat,
        target_expected=None,
        intended=other_stat,
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    later = replace(_following_copy(source, fs), op_id=OpId(f"{3:032x}"))
    xset = _xset(_plan(source, target, (first, second, later)))
    metadata_paths: list[Path] = []
    original_apply = fs.apply_metadata

    def apply_metadata(path, *args, **kwargs):
        if path in (target / "folder", target / "other"):
            metadata_paths.append(path)
        return original_apply(path, *args, **kwargs)

    monkeypatch.setattr(fs, "apply_metadata", apply_metadata)
    recorder = _CountingRecorder()
    original = OSError("injected directory outcome refusal")
    delivery = _CanceledDelivery(monkeypatch, xset, first.op_id, original=original)

    with pytest.raises(OSError) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is original
    delivery.assert_replayed(first.op_id)
    assert xset.status == {
        later.op_id: Outcome.SUCCEEDED,
        first.op_id: Outcome.SUCCEEDED,
        second.op_id: Outcome.FAILED,
    }
    assert xset.recording_reasons == {
        second.op_id: ItemRecordingReason.UNRECORDED_MUTATION
    }
    assert [(name, op_id) for name, op_id, _ in recorder.calls] == [
        ("copied", later.op_id), ("mkdir", first.op_id)
    ]
    assert recorder.attempts == ["copied", "mkdir"]
    assert metadata_paths == [target / "folder"]
    assert (target / "other").is_dir()


def test_cancel_replay_finishes_session_with_unstarted_items_canceled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation, published_path = _reviewed_byte_operation(OperationKind.COPY, source, target, fs)
    later = _following_copy(source, fs)
    xset = _xset(_plan(source, target, (operation, later)))
    recorder = _CountingRecorder()
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id)

    outcome = run_session(
        lambda ctx: execute(xset, ctx, recorder, _policies(), fs),
        emit=delivery.emit,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    delivery.assert_replayed(operation.op_id)
    assert not outcome.paused
    result = outcome.result
    assert result is not None
    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert result.error is None
    assert result.items == tuple(delivery.accepted)
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED, later.op_id: Outcome.CANCELED}
    assert delivery.accepted[-1].reason == "canceled"
    assert recorder.attempts == ["copied"]
    assert published_path.read_bytes() == b"new-version"
    assert not (target / "later.bin").exists()
    assert (result.bytes_done, result.bytes_total) == (
        operation.content_bytes, operation.content_bytes + later.content_bytes
    )
    assert (delivery.progress[-1].items_done, delivery.progress[-1].items_total) == (2, 2)
    assert delivery.progress[-1].item_id is None
    assert delivery.progress[-1].current_path is None
    assert delivery.retired == [operation.op_id, later.op_id]


@pytest.mark.parametrize("secondary_type", [Canceled, OSError])
def test_cancel_replay_persistent_refusal_retains_unaccepted_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    secondary_type: type[Exception],
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation, published_path = _reviewed_byte_operation(OperationKind.COPY, source, target, fs)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = _CountingRecorder()
    secondary = secondary_type("injected persistent outcome refusal")
    delivery = _CanceledDelivery(monkeypatch, xset, operation.op_id, secondary=secondary)

    with pytest.raises(secondary_type) as raised:
        execute(xset, RunContext(delivery.emit, lambda: None), recorder, _policies(), fs)

    assert raised.value is secondary
    assert len(delivery.offered) == 3
    assert all(item == delivery.offered[0] for item in delivery.offered)
    assert delivery.accepted == []
    assert delivery.retired == []
    assert xset.status == {}
    assert xset.published_evidence == {}
    assert xset.recording_reasons == {}
    assert len(delivery.retained) == 3
    _, journal, pending = delivery.retained[0]
    assert all(entry[1] is journal and entry[2] is pending for entry in delivery.retained)
    assert journal.has_active_entry(operation.op_id)
    assert journal.pending_settlement(operation.op_id) is pending
    assert pending.published_evidence is not None
    assert pending.published_evidence.recorded_identity == recorder._copy_identity(operation.op_id)
    assert operation.op_id not in delivery.canceled_reductions
    assert recorder.attempts == ["copied"]
    assert published_path.read_bytes() == b"new-version"
    assert delivery.progress[-1].items_done == 0
    assert delivery.progress[-1].item_id is None
    assert any("executor exception backstop also failed" in note for note in raised.value.__notes__)
