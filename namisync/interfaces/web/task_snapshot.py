"""Bounded, adapter-owned presentation reduction for one observed task session."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import exp, isfinite
from copy import deepcopy

from namisync.interfaces.task_port import TaskEventUpdateView, TaskRecordUpdateView, TaskUpdateView


_RATE_HORIZON_SECONDS = 5.0


class ProgressPresentationError(ValueError):
    """A structurally valid Progress event conflicts with prior display facts."""


def _percent(done: str | None, total: str | None) -> float | None:
    if done is None or total is None or int(total) <= 0:
        return None
    scaled = int(done) * 1_000_000 // int(total)
    return max(0.0, min(100.0, scaled / 10_000))


def _active_item(progress: dict[str, object]) -> dict[str, object] | None:
    if progress["item_id"] is None:
        return None
    return {key: progress[key] for key in (
        "item_id", "item_type", "item_attempt_id", "item_bytes_done", "item_bytes_total",
    )}


def _same_item(left: dict[str, object], right: dict[str, object]) -> bool:
    return left["item_id"] == right["item_id"] and left["item_type"] == right["item_type"]


def _aggregate_advances(previous: dict[str, object], current: dict[str, object]) -> bool:
    if current["items_done"] < previous["items_done"] or int(current["bytes_done"]) < int(previous["bytes_done"]):
        return False
    if previous["items_total"] is not None and current["items_total"] != previous["items_total"]:
        return False
    old_total = previous["bytes_total"]
    new_total = current["bytes_total"]
    if old_total is not None and new_total is None:
        return False
    if previous["phase"] == "execute" and old_total is not None and new_total != old_total:
        return False
    return not (previous["phase"] != "execute" and old_total is not None and int(new_total) < int(old_total))


def _attempt_advances(previous: dict[str, object], current: dict[str, object]) -> bool:
    old_done = previous["item_bytes_done"]
    new_done = current["item_bytes_done"]
    if old_done is None:
        return new_done is None
    if new_done is None:
        return True
    return int(new_done) >= int(old_done) and current["item_bytes_total"] == previous["item_bytes_total"]


@dataclass(frozen=True, slots=True)
class TaskPresentationState:
    """No outcome map, browser draft, or effect authority is retained here."""

    task_id: str
    session_id: str
    revision: int = 0
    last_reduced_sequence: int = 0
    session_state: str = "active"
    control_state: str = "running"
    phase: str | None = None
    phase_authority: str = "unknown"
    progress: dict[str, object] | None = None
    active_item: dict[str, object] | None = None
    aggregate_high_water: float | None = None
    item_high_water: float | None = None
    sample_at: float | None = None
    sample_bytes_done: str | None = None
    smoothed_rate: float | None = None
    throughput_bytes_per_second: float | None = None
    eta_seconds: float | None = None
    gap_first_missed_seq: int | None = None
    progress_inconsistent: bool = False
    terminal_result: dict[str, object] | None = None
    started_at: str | None = None
    ended_at: str | None = None

    def _clear_progress(self, *, phase: str | None = None, authority: str = "unknown") -> TaskPresentationState:
        return replace(
            self, phase=phase, phase_authority=authority, progress=None,
            active_item=None, aggregate_high_water=None, item_high_water=None,
            sample_at=None, sample_bytes_done=None, smoothed_rate=None,
            throughput_bytes_per_second=None, eta_seconds=None,
        )

    def advance(self, update: TaskUpdateView, now: float) -> TaskPresentationState:
        """Apply one byte-admitted update; old replay cannot regress newer facts."""

        if type(update) is TaskRecordUpdateView:
            record = update.record
            if self.terminal_result is not None or self.session_state != "active":
                if (
                    self.session_state != record.state
                    or self.terminal_result != (None if record.result is None else asdict(record.result))
                    or self.started_at != record.started_at
                    or self.ended_at != record.ended_at
                ):
                    raise ValueError("terminal replay changed task record")
                return self
            result = record.result
            axes = None if result is None else asdict(result)
            return replace(
                self._clear_progress(), revision=self.revision + 1,
                session_state=record.state, terminal_result=axes,
                started_at=record.started_at, ended_at=record.ended_at,
            )

        if type(update) is not TaskEventUpdateView:
            raise TypeError("task snapshot update has invalid type")
        event = update.event
        body = event.body
        if event.body_type == "Gap":
            missed = body["first_missed_seq"]
            minimum = missed if self.gap_first_missed_seq is None else min(missed, self.gap_first_missed_seq)
            if event.sequence <= self.last_reduced_sequence:
                if minimum == self.gap_first_missed_seq:
                    return self
                return replace(
                    self, revision=self.revision + 1, gap_first_missed_seq=minimum,
                    sample_at=None, sample_bytes_done=None, smoothed_rate=None,
                    throughput_bytes_per_second=None, eta_seconds=None,
                )
            return replace(
                self._clear_progress(), revision=self.revision + 1,
                gap_first_missed_seq=minimum,
            )
        if event.sequence <= self.last_reduced_sequence:
            return self
        if self.session_state != "active":
            return self
        state = replace(self, last_reduced_sequence=event.sequence)
        kind = event.body_type
        if kind == "PhaseChanged":
            phase = body["phase"]
            state = replace(state, phase_authority="phase_changed") if state.phase == phase else state._clear_progress(phase=phase, authority="phase_changed")
        elif kind == "Progress":
            try:
                state = state._advance_progress(body, now)
            except ProgressPresentationError:
                state = replace(state._clear_progress(), progress_inconsistent=True)
        elif kind in {"ItemOutcome", "IntegrityOutcome"}:
            if state.phase == body["phase"] and state.active_item is not None:
                active = state.active_item
                matches = active["item_id"] == body["item_id"] and (
                    active["item_type"] == body["item_type"] or (
                        state.phase == "verify" and kind == "IntegrityOutcome" and active["item_type"] == "operation"
                    )
                )
                if matches:
                    state = replace(state, active_item=None, item_high_water=None)
        elif kind == "StateChanged":
            value = body["state"]
            if value in {"running", "pausing", "paused", "canceling"}:
                state = replace(
                    state, control_state=value, sample_at=None,
                    sample_bytes_done=None, smoothed_rate=None,
                    throughput_bytes_per_second=None, eta_seconds=None,
                )
        elif kind == "Terminal":
            state = state._clear_progress()
        if state == self:
            return self
        return replace(state, revision=self.revision + 1)

    def _advance_progress(self, body: object, now: float) -> TaskPresentationState:
        progress = {key: body[key] for key in (
            "phase", "items_done", "items_total", "bytes_done", "bytes_total",
            "item_id", "item_type", "item_attempt_id", "item_bytes_done", "item_bytes_total",
        )}
        domain = self
        if self.phase is not None and progress["phase"] != self.phase:
            if self.phase_authority == "phase_changed":
                raise ProgressPresentationError("progress disagrees with reliable phase")
            domain = self._clear_progress()
        if domain.progress is not None and not _aggregate_advances(domain.progress, progress):
            raise ProgressPresentationError("progress aggregate regressed")
        active = _active_item(progress)
        previous = domain.active_item
        if active is not None:
            if previous is not None:
                old_attempt = previous["item_attempt_id"]
                new_attempt = active["item_attempt_id"]
                if _same_item(previous, active):
                    if old_attempt is not None and new_attempt is None:
                        raise ProgressPresentationError("progress attempt disappeared")
                    if old_attempt is not None and new_attempt == old_attempt and not _attempt_advances(previous, active):
                        raise ProgressPresentationError("progress attempt regressed")
                elif old_attempt is not None and new_attempt == old_attempt:
                    raise ProgressPresentationError("progress attempt changed item")
            elif domain.progress is not None and domain.progress["item_id"] is not None:
                settled = _active_item(domain.progress)
                assert settled is not None
                if _same_item(settled, active) or (
                    settled["item_attempt_id"] is not None and active["item_attempt_id"] == settled["item_attempt_id"]
                ):
                    raise ProgressPresentationError("settled progress item reactivated")
        aggregate_percent = _percent(progress["bytes_done"], progress["bytes_total"])
        item_percent = None if active is None else _percent(active["item_bytes_done"], active["item_bytes_total"])
        same_item = previous is not None and active is not None and _same_item(previous, active)
        attempt_changed = (
            same_item and previous["item_attempt_id"] is not None
            and previous["item_attempt_id"] != active["item_attempt_id"]
        )
        aggregate_high_water = (
            None if aggregate_percent is None else max(domain.aggregate_high_water or 0, aggregate_percent)
        )
        item_high_water = (
            domain.item_high_water if same_item and item_percent is None else
            None if item_percent is None else
            max(domain.item_high_water or 0, item_percent) if same_item else item_percent
        )
        reset_sample = (
            domain.sample_at is None or domain.sample_bytes_done is None
            or domain.progress is None or domain.progress["bytes_total"] != progress["bytes_total"]
            or attempt_changed
        )
        if reset_sample or now <= domain.sample_at:
            rate = None
        else:
            elapsed = now - domain.sample_at
            observed = (int(progress["bytes_done"]) - int(domain.sample_bytes_done)) / elapsed
            alpha = 1 - exp(-elapsed / _RATE_HORIZON_SECONDS)
            rate = observed if domain.smoothed_rate is None else alpha * observed + (1 - alpha) * domain.smoothed_rate
            if not isfinite(rate) or rate < 0:
                rate = None
        eta = None
        if rate is not None and rate > 0 and progress["bytes_total"] is not None:
            estimate = (int(progress["bytes_total"]) - int(progress["bytes_done"])) / rate
            eta = estimate if isfinite(estimate) and estimate >= 0 else None
        return replace(
            domain, phase=progress["phase"],
            phase_authority="phase_changed" if domain.phase_authority == "phase_changed" else "progress",
            progress=progress, active_item=active,
            aggregate_high_water=aggregate_high_water, item_high_water=item_high_water,
            sample_at=now, sample_bytes_done=progress["bytes_done"], smoothed_rate=rate,
            throughput_bytes_per_second=rate, eta_seconds=eta,
        )

    def snapshot(self) -> dict[str, object]:
        """Return detached, bounded display facts; no retained item-result map."""

        progress = self.progress
        active = self.active_item
        aggregate_percent = (
            self.aggregate_high_water
            if progress is not None and progress["bytes_total"] is not None
            and int(progress["bytes_total"]) > 0 else None
        )
        item_percent = (
            self.item_high_water
            if active is not None and active["item_bytes_total"] is not None
            and int(active["item_bytes_total"]) > 0 else None
        )
        display_percent = aggregate_percent
        if (
            display_percent is None and progress is not None
            and progress["bytes_total"] == "0" and progress["items_total"] is not None
            and progress["items_total"] > 0
        ):
            display_percent = max(0.0, min(100.0, progress["items_done"] / progress["items_total"] * 100))
        active_session = self.session_state == "active" and self.control_state != "paused"
        return {
            "wire_version": 2,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "revision": self.revision,
            "session_state": self.session_state,
            "control_state": self.control_state,
            "phase": self.phase,
            "active_item": None if active is None else {
                "item_id": active["item_id"], "item_type": active["item_type"],
            },
            "presentation": {
                "item_percent": item_percent,
                "items_done": None if progress is None else progress["items_done"],
                "items_total": None if progress is None else progress["items_total"],
                "value": 0.0 if display_percent is None else display_percent,
                "determinate": display_percent is not None,
                "indeterminate": display_percent is None and active_session,
                "throughput_bytes_per_second": self.throughput_bytes_per_second,
                "eta_seconds": self.eta_seconds,
            },
            "gap_first_missed_seq": self.gap_first_missed_seq,
            "progress_inconsistent": self.progress_inconsistent,
            "terminal_result": None if self.terminal_result is None else deepcopy(self.terminal_result),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


@dataclass(slots=True)
class TaskSnapshotStage:
    """Reduce captured drain updates without mutating the retained task."""

    state: TaskPresentationState
    progress_sample_at: float | None
    replay_from: int | None = None

    def consider(self, update: TaskUpdateView) -> TaskPresentationState:
        progress = type(update) is TaskEventUpdateView and update.event.body_type == "Progress"
        if progress and self.progress_sample_at is None:
            raise RuntimeError("queued Progress lacks its acceptance sample")
        now = self.progress_sample_at if progress else 0.0
        assert now is not None
        return self.state.advance(update, now)

    def accept(self, candidate: TaskPresentationState) -> None:
        self.state = candidate

    def snapshot(self) -> dict[str, object]:
        return self.state.snapshot()
