"""Frozen behavior oracle for the initial subtractive simplification run.

The audit deliberately observes two stable public seams only:

* dispatcher-driven workflow pause/resume/cancel settlement; and
* the canonical event-v5 body bytes delivered to persistence boundaries.

It does not model workflow policy, validate event bodies independently, or
encode workflow continuation payloads.  Those mechanisms are the subject of
the simplification and must remain removable without changing this oracle.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from typing import Sequence
from uuid import UUID


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TEST_ROOT = _REPOSITORY_ROOT / "tests"
for _path in (_REPOSITORY_ROOT, _TEST_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from _event_v5_fixtures import (  # noqa: E402
    bodies as event_v5_bodies,
    envelope as event_v5_envelope,
    maximum_reliable_envelope,
    review_limit_terminal_summary,
)
from _inventory_fixtures import (  # noqa: E402
    _Resolver,
    _Scanner,
    _file,
    _runtime as inventory_runtime,
)
from namisync.core.events import (  # noqa: E402
    PhaseChanged,
    Progress,
    envelope_from_dict,
    envelope_to_dict,
    result_item_to_dict,
)
from namisync.core.evidence import (  # noqa: E402
    Attestation,
    ContentEvidence,
    Provenance,
    RecordingStatus,
)
from namisync.core.integrity import (  # noqa: E402
    IntegrityMode,
    IntegrityOutcome,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegrityRunResult,
    InventoryState,
    RecordDisposition,
)
from namisync.core.session import (  # noqa: E402
    OperationResult,
    SessionState,
)
from namisync.dispatcher import (  # noqa: E402
    Dispatcher,
    InProcessResourceLockProvider,
)
import namisync.dispatcher.dispatcher as dispatcher_module  # noqa: E402
from namisync.db.recorder import LedgerRecorder  # noqa: E402
from namisync.db.history import HistoryRepository  # noqa: E402
from namisync.interfaces.service import _workflow_registry  # noqa: E402
from namisync.workflows.inventory import (  # noqa: E402
    IntegrityRequest,
    InventoryRequest,
)
from namisync.workflows.models import PlanRequest  # noqa: E402
from namisync.workflows.runtime import (  # noqa: E402
    BASELINE_KIND,
    EXECUTION_KIND,
    INVENTORY_KIND,
    PLAN_KIND,
    REBASELINE_KIND,
    VERIFY_KIND,
    LocalWorkflowRuntime,
)


FORMAT_VERSION = 1
DEFAULT_BASELINE = Path(__file__).with_name(
    "simplification_regression_baseline.json"
)
FROZEN_CORPUS_PATHS = (
    "tests/_event_v5_fixtures.py",
    "tests/test_tools_simplification_regression_audit.py",
    "tools/simplification_regression_audit.py",
    "tools/simplification_regression_baseline.json",
)
NOW = datetime(2026, 8, 25, tzinfo=UTC)


class AuditError(RuntimeError):
    """The audit could not produce trustworthy, deterministic evidence."""


class _FixedClock:
    def now(self) -> datetime:
        return NOW


def _canonical_json(value: object) -> str:
    """Render the exact canonical JSON spelling used by event-v5 storage."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="strict")).hexdigest()


def build_event_corpus() -> dict[str, object]:
    """Project the existing positive v5 fixture through production contracts."""

    rows: dict[str, object] = {}
    for body_type in event_v5_bodies():
        envelope = envelope_from_dict(event_v5_envelope(body_type))
        encoded = _canonical_json(envelope_to_dict(envelope))
        rows[body_type] = {
            "bytes": len(encoded.encode("utf-8")),
            "sha256": _digest_text(encoded),
            "json": encoded,
        }

    review_envelope = envelope_from_dict(
        event_v5_envelope(
            "Terminal",
            body={"result": review_limit_terminal_summary()},
        )
    )
    review_encoded = _canonical_json(envelope_to_dict(review_envelope))
    rows["Terminal.review-limit"] = {
        "bytes": len(review_encoded.encode("utf-8")),
        "sha256": _digest_text(review_encoded),
        "json": review_encoded,
    }

    maximum = envelope_from_dict(maximum_reliable_envelope())
    maximum_encoded = _canonical_json(envelope_to_dict(maximum))
    maximum_bytes = len(maximum_encoded.encode("utf-8"))
    if maximum_bytes != 1_048_576:
        raise AuditError(
            "event-v5 maximum fixture no longer reaches the exact byte wall"
        )
    rows["ItemOutcome.maximum-reliable"] = {
        "bytes": maximum_bytes,
        "sha256": _digest_text(maximum_encoded),
    }
    return rows


def _wait_for(
    dispatcher: Dispatcher,
    session_id: str,
    state: SessionState,
    timeout: float = 5.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            }
            or record.result is not None
        ):
            return record
        sleep(0.005)
    raise AuditError(
        f"session did not reach {state.value}: {dispatcher.get(session_id)}"
    )


def _submit(
    dispatcher: Dispatcher,
    kind: str,
    request: object,
    *,
    session_ordinal: int,
):
    """Make fixture identity deterministic without changing admission policy."""

    original = dispatcher_module.uuid4
    dispatcher_module.uuid4 = lambda: UUID(int=session_ordinal)
    try:
        return dispatcher.submit(kind, request)
    finally:
        dispatcher_module.uuid4 = original


def _normalized_events(stream) -> dict[str, object]:
    reliable: list[dict[str, object]] = []
    progress: dict[str, dict[str, object]] = {}
    deadline = monotonic() + 5.0
    while monotonic() < deadline:
        envelope = stream.next(max(0.01, deadline - monotonic()))
        projected = envelope_to_dict(envelope)
        body_type = str(projected["body_type"])
        body = projected["body"]
        if body_type == "Progress":
            if not isinstance(body, dict):
                raise AuditError("production progress projection is not an object")
            phase = str(body["phase"])
            progress[phase] = {
                "items_done": body["items_done"],
                "items_total": body["items_total"],
                "bytes_done": body["bytes_done"],
                "bytes_total": body["bytes_total"],
                "current_path": body["current_path"],
            }
            continue
        reliable.append({"body_type": body_type, "body": body})
        if body_type == "Terminal":
            return {
                "reliable": reliable,
                "progress_high_water": {
                    phase: progress[phase] for phase in sorted(progress)
                },
            }
    raise AuditError("event stream did not publish a terminal body")


def _normalized_result(result: OperationResult) -> dict[str, object]:
    return {
        "status": result.status.value,
        "recording": result.recording.value,
        "audit": result.audit.value,
        "disposition": result.disposition.value,
        "canceled": result.canceled,
        "bytes_done": str(result.bytes_done),
        "bytes_total": str(result.bytes_total),
        "phases": [
            {
                "phase": phase.phase,
                "status": phase.status.value,
                "items_done": phase.items_done,
                "items_total": phase.items_total,
                "bytes_done": str(phase.bytes_done),
                "bytes_total": (
                    None if phase.bytes_total is None else str(phase.bytes_total)
                ),
                "error": phase.error,
            }
            for phase in result.phases
        ],
        "items": [result_item_to_dict(item) for item in result.items],
        "error": (
            None
            if result.error is None
            else {
                "type_name": result.error.type_name,
                "message": result.error.message,
            }
        ),
    }


def _durable_run(ledger_path: Path, run_id: str) -> dict[str, object]:
    connection = sqlite3.connect(ledger_path)
    try:
        row = connection.execute(
            "SELECT ended_at, filesystem_status FROM runs WHERE run_token = ?",
            (run_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise AuditError(f"durable run {run_id} was not recorded")
    return {
        "ended": row[0] is not None,
        "filesystem_status": row[1],
    }


def _persisted_body_witness(history_path: Path, run_id: str) -> list[dict[str, object]]:
    connection = sqlite3.connect(history_path)
    try:
        rows = connection.execute(
            """SELECT event.event_seq, event.body_type, event.envelope_json
                 FROM history_events AS event
                 JOIN history_runs AS run ON run.id = event.run_id
                WHERE run.run_token = ? AND event.envelope_json IS NOT NULL
                ORDER BY event.event_seq LIMIT 1""",
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    with HistoryRepository(history_path) as repository:
        readback = repository.get_event_page(run_id).events
    by_sequence = {
        event.event_seq: event.envelope
        for event in readback
        if event.envelope is not None
    }
    witness: list[dict[str, object]] = []
    for sequence, body_type, envelope_text in rows:
        envelope = by_sequence.get(sequence)
        if envelope is None:
            raise AuditError("persisted event did not survive public history readback")
        canonical = _canonical_json(envelope_to_dict(envelope))
        if envelope_text != canonical:
            raise AuditError(
                "persisted event bytes differ from public history readback"
            )
        witness.append(
            {
                "event_seq": sequence,
                "body_type": body_type,
                "bytes": len(envelope_text.encode("utf-8")),
                "sha256": _digest_text(envelope_text),
            }
        )
    if not witness:
        raise AuditError("production history stored no canonical event bodies")
    return witness


def _seed_baseline(
    runtime: LocalWorkflowRuntime,
    location_id: int,
    path: str,
) -> None:
    row = next(
        value
        for value in runtime.list_inventory(location_id)
        if value.rel_path == path
    )
    if row.observed is None:
        raise AuditError("baseline seed row has no observed stat")
    evidence = Attestation(
        ContentEvidence(
            "xxh3_128",
            b"\x01" * 16,
            row.observed.size,
            Provenance.READBACK_ATTESTED,
            NOW,
        ),
        row.observed,
    )
    with LedgerRecorder(runtime.ledger_path, clock=_FixedClock()) as recorder:
        disposition = recorder.record_integrity(
            IntegrityRecordCommand(
                IntegrityMode.BASELINE,
                f"seed-baseline:{row.row_id}",
                row.row_id,
                str(row.location_id),
                row.rel_path_key,
                row.scope_token,
                InventoryState(row.presence.value),
                row.observed,
                None,
                evidence,
                False,
                False,
            )
        )
    if disposition is not RecordDisposition.APPLIED:
        raise AuditError("baseline seed was not recorded")


def _prepare_execution(
    runtime: LocalWorkflowRuntime,
    dispatcher: Dispatcher,
    source: Path,
    target: Path,
    *,
    request_id: str,
    run_id: str,
    verify_after_execute: bool,
):
    plan_id = _submit(
        dispatcher,
        PLAN_KIND,
        PlanRequest(request_id, str(source), str(target)),
        session_ordinal=1,
    )
    plan = _wait_for(dispatcher, plan_id, SessionState.COMPLETED)
    if plan.result is None or plan.result.status is not SessionState.COMPLETED:
        raise AuditError("production plan did not complete")
    return runtime.commit_plan(
        request_id,
        run_id=run_id,
        committed_at=NOW,
        verify_after_execute=verify_after_execute,
    )


def _execution_trace(root: Path, *, pause_phase: str, action: str) -> dict[str, object]:
    source = root / "source"
    target = root / "target"
    source.mkdir(parents=True)
    target.mkdir()
    (source / "a.bin").write_bytes(b"first")
    (source / "b.bin").write_bytes(b"second")
    runtime = LocalWorkflowRuntime(
        root / "ledger.db",
        root / "history.db",
        clock=_FixedClock(),
        host_key="audit-host",
        host_name="Audit Host",
    )
    entered, calls = Event(), 0
    if pause_phase == "execute":
        original = runtime._deps.executor

        def pause_once(execution_set, context, recorder, policies, filesystem):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)
            return original(execution_set, context, recorder, policies, filesystem)

        runtime._deps = replace(runtime._deps, executor=pause_once)
    elif pause_phase == "verify":
        original = runtime._deps.verifier

        def pause_once(selection, context, recorder):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                while True:
                    context.run.checkpoint()
                    sleep(0.005)
            return original(selection, context, recorder)

        runtime._deps = replace(runtime._deps, verifier=pause_once)
    else:
        raise AuditError(f"unsupported execution pause phase: {pause_phase}")
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    stream = None
    identifier = {
        ("execute", "resume"): "1",
        ("execute", "cancel"): "3",
        ("verify", "resume"): "5",
        ("verify", "cancel"): "7",
    }[(pause_phase, action)]
    run_id = str(int(identifier) + 1) * 32
    try:
        execution = _prepare_execution(
            runtime,
            dispatcher,
            source,
            target,
            request_id=identifier * 32,
            run_id=run_id,
            verify_after_execute=True,
        )
        session_id = _submit(
            dispatcher,
            EXECUTION_KIND,
            execution,
            session_ordinal=2,
        )
        stream = dispatcher.subscribe(session_id)
        if not entered.wait(5.0):
            raise AuditError(f"{pause_phase} did not reach its pause checkpoint")
        if not dispatcher.pause(session_id).accepted:
            raise AuditError(f"{pause_phase} pause was rejected")
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        if paused.result is not None:
            raise AuditError(f"paused {pause_phase} unexpectedly became terminal")
        decision = (
            dispatcher.resume(session_id)
            if action == "resume"
            else dispatcher.cancel(session_id)
        )
        if not decision.accepted:
            raise AuditError(f"paused {pause_phase} {action} was rejected")
        terminal_state = (
            SessionState.COMPLETED
            if action == "resume"
            else SessionState.CANCELED
        )
        terminal = _wait_for(dispatcher, session_id, terminal_state)
        if terminal.result is None:
            raise AuditError(f"{pause_phase} {action} completed without a result")
        events = _normalized_events(stream)
        return {
            "controls": ["pause:accepted", f"{action}:accepted"],
            "collaborator_calls": calls,
            "result": _normalized_result(terminal.result),
            "events": events,
            "target": [
                path.relative_to(target).as_posix()
                for path in sorted(target.rglob("*"))
            ],
            "durable": _durable_run(runtime.ledger_path, run_id),
            "persisted_body_witness": (
                _persisted_body_witness(runtime.history_path, run_id)
                if pause_phase == "verify" and action == "resume"
                else None
            ),
        }
    finally:
        if stream is not None:
            stream.close()
        shutdown = dispatcher.shutdown()
        runtime.close()
        if not shutdown.complete:
            raise AuditError(f"{pause_phase} dispatcher did not shut down cleanly")


_INTEGRITY_KINDS = {
    IntegrityMode.BASELINE: BASELINE_KIND,
    IntegrityMode.VERIFY: VERIFY_KIND,
    IntegrityMode.REBASELINE: REBASELINE_KIND,
}


def _integrity_trace(
    root: Path,
    *,
    mode: IntegrityMode,
    action: str,
) -> dict[str, object]:
    mount = root / "mount"
    (mount / "managed").mkdir(parents=True)
    scanner = _Scanner(mount, (_file("a.txt", 1), _file("b.txt", 2)))
    entered, calls = Event(), 0

    def runner(selection, context, recorder):
        nonlocal calls
        del recorder
        calls += 1
        outcomes: list[IntegrityOutcome] = []
        total = sum(
            0 if item.expected_stat is None else item.expected_stat.size
            for item in selection.items
        )
        selection.advance_bytes_total_high_water(total)
        for item in tuple(selection.pending):
            size = 0 if item.expected_stat is None else item.expected_stat.size
            selection.note_bytes_processed(size)
            result = (
                IntegrityResult.VERIFIED
                if mode is IntegrityMode.VERIFY and item.baseline is not None
                else IntegrityResult.BASELINED
            )
            outcome = IntegrityOutcome(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                path=item.display_path,
                phase=mode.value,
                result=result,
            )
            context.run.emit(outcome)
            selection.mark_completed(item.item_id, size)
            outcomes.append(outcome)
            if calls == 1:
                entered.set()
                while True:
                    context.run.checkpoint()
                    sleep(0.005)
        return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)

    runtime, location_id = inventory_runtime(
        root,
        _Resolver(mount),
        scanner,
        {mode: runner},
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    stream = None
    request_id = f"audit-{mode.value}-{action}"
    try:
        inventory_id = _submit(
            dispatcher,
            INVENTORY_KIND,
            InventoryRequest(f"{request_id}-inventory", location_id=location_id),
            session_ordinal=1,
        )
        inventory = _wait_for(dispatcher, inventory_id, SessionState.COMPLETED)
        if inventory.result is None:
            raise AuditError("inventory seed completed without a result")
        _seed_baseline(runtime, location_id, "a.txt")
        session_id = _submit(
            dispatcher,
            _INTEGRITY_KINDS[mode],
            IntegrityRequest(request_id, mode, location_id=location_id),
            session_ordinal=2,
        )
        stream = dispatcher.subscribe(session_id)
        if not entered.wait(5.0):
            raise AuditError(f"{mode.value} did not reach its pause checkpoint")
        if not dispatcher.pause(session_id).accepted:
            raise AuditError(f"{mode.value} pause was rejected")
        paused = _wait_for(dispatcher, session_id, SessionState.PAUSED)
        if paused.result is not None:
            raise AuditError(f"paused {mode.value} unexpectedly became terminal")
        decision = (
            dispatcher.resume(session_id)
            if action == "resume"
            else dispatcher.cancel(session_id)
        )
        if not decision.accepted:
            raise AuditError(f"{mode.value} {action} was rejected")
        terminal_state = (
            SessionState.COMPLETED
            if action == "resume"
            else SessionState.CANCELED
        )
        terminal = _wait_for(dispatcher, session_id, terminal_state)
        if terminal.result is None:
            raise AuditError(f"{mode.value} {action} completed without a result")
        return {
            "controls": ["pause:accepted", f"{action}:accepted"],
            "runner_calls": calls,
            "result": _normalized_result(terminal.result),
            "events": _normalized_events(stream),
        }
    finally:
        if stream is not None:
            stream.close()
        shutdown = dispatcher.shutdown()
        runtime.close()
        if not shutdown.complete:
            raise AuditError(f"{mode.value} dispatcher did not shut down cleanly")


def build_workflow_corpus(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    rows = {
        f"{label}.pause-{action}-settle": _execution_trace(
            root / f"{phase}-{action}",
            pause_phase=phase,
            action=action,
        )
        for label, phase in (
            ("execution", "execute"),
            ("linked-verify", "verify"),
        )
        for action in ("resume", "cancel")
    }
    rows.update(
        {
            f"{mode.value}.pause-{action}-settle": _integrity_trace(
                root / f"{mode.value}-{action}",
                mode=mode,
                action=action,
            )
            for mode in IntegrityMode
            for action in ("resume", "cancel")
        }
    )
    return dict(sorted(rows.items()))


def collect_once() -> dict[str, object]:
    with TemporaryDirectory(prefix="namisync-simplification-audit-") as temp:
        workflows = build_workflow_corpus(Path(temp))
    return {
        "format_version": FORMAT_VERSION,
        "event_v5": build_event_corpus(),
        "workflows": workflows,
    }


def collect_stable(repeat: int) -> dict[str, object]:
    if repeat < 1:
        raise AuditError("repeat must be positive")
    first = collect_once()
    for attempt in range(2, repeat + 1):
        candidate = collect_once()
        if candidate != first:
            raise AuditError(
                f"normalized corpus changed between attempts 1 and {attempt}"
            )
    return first


def snapshot(path: Path, *, repeat: int, replace_existing: bool = False) -> None:
    if path.exists() and not replace_existing:
        raise AuditError(f"baseline already exists: {path}")
    observed = collect_stable(repeat)
    path.write_text(
        json.dumps(observed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check(path: Path, *, repeat: int) -> None:
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot read baseline {path}: {error}") from error
    observed = collect_stable(repeat)
    if observed != expected:
        raise AuditError("observed corpus differs from the frozen baseline")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "check"))
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing baseline (snapshot only)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            snapshot(
                args.baseline,
                repeat=args.repeat,
                replace_existing=args.replace,
            )
        else:
            if args.replace:
                raise AuditError("--replace is valid only for snapshot")
            check(args.baseline, repeat=args.repeat)
    except AuditError as error:
        print(f"simplification regression audit failed: {error}", file=sys.stderr)
        return 1
    print(
        f"simplification regression audit {args.command} passed "
        f"({args.repeat} identical run{'s' if args.repeat != 1 else ''})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
