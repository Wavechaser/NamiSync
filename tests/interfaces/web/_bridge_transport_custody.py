"""Fresh-process SH-G-8 transport-custody measurement fixture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import struct
import sys
import sysconfig
import threading
import tracemalloc
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from types import ModuleType
from unittest.mock import patch


CORPUS_VERSION = "sh-g-8-transport-v1"
HEADROOM_POLICY = {
    "factor_numerator": 5,
    "factor_denominator": 4,
    "round_up_bytes": 65_536,
    "rule": (
        "round upward to 65536 bytes after applying 25 percent headroom "
        "to the largest calibration transport_custody_bytes measurement"
    ),
}
CORPUS_SPEC = {
    "version": CORPUS_VERSION,
    "task_count": 4,
    "path_depth": 32,
    "path_utf16_units": [240, 1_024, 4_096],
    "alphabet_counts_ratio": {"ascii": 2, "bmp": 1, "non_bmp": 1},
    "ordinary": {
        "logical_ticks": 60,
        "progress_count": 6_000,
        "progress_length_counts": {"240": 5_700, "1024": 240, "4096": 60},
        "outcome_count": 600,
        "outcome_length_counts": {"240": 570, "1024": 24, "4096": 6},
    },
    "maximum_no_gap": {
        "outcome_count": 516,
        "outcome_length_counts": {"240": 490, "1024": 21, "4096": 5},
        "per_task": {
            "adapter": 64,
            "in_flight": 1,
            "subscriber": 64,
            "replay": 128,
        },
    },
    "detail_families": {
        "publication": {
            "kind": "copy",
            "outcome": "failed",
            "reason": "io-error",
            "durability_warnings": 0,
        },
        "move_update": {
            "kind": "move_update",
            "outcome": "failed",
            "reason": "recorder-failed",
            "durability_warnings": 0,
        },
        "mutation": {
            "kind": "update",
            "outcome": "failed",
            "reason": "io-error",
            "durability_warnings": 0,
        },
    },
    "dataset_variants": {
        "calibration-a": "rank=(ordinal*37+17) mod population; alphabet=ordinal mod 4",
        "holdout-b": "rank=(ordinal*41+31) mod population; alphabet=(ordinal+1) mod 4",
    },
    "dynamic_nonaliased_values_distinct": True,
    "item_ids": {
        "format": "32 lowercase hexadecimal characters",
        "derivation": "first 128 bits of SHA-256 over corpus/variant/fixture/task/local",
        "disjoint_across_variants_and_fixtures": True,
    },
    "identity_aliases": {
        "copy_published_path": "ItemOutcome.path",
        "move_update_published_path": "ItemOutcome.path",
    },
    "path_length_scope": (
        "subject and prior paths use the frozen distribution; derived trash "
        "paths include their production prefix"
    ),
}

# Current-source representation overlay only. The frozen v1 corpus and its
# protected calibration/holdout hashes remain unchanged.
CURRENT_V5_TRANSPORT_REPRESENTATION = {
    "scope": (
        "all current transport custody; Progress is populated only in ordinary"
    ),
    "typed_envelope": {
        "retained_in": "EventHub replay and subscriber queues",
        "fields": {
            "session_id": "populated per task",
            "seq": "populated, increasing per session",
            "at": "populated UTC timestamp",
            "schema_version": "populated with live core event version 5",
            "body": (
                "Progress in ordinary or an inherited reliable body named below"
            ),
        },
    },
    "session_event_view": {
        "retained_in": "TaskRegistry adapter queue",
        "fields": {
            "session_id": "populated from the Envelope",
            "sequence": "populated from Envelope.seq",
            "at": "populated canonical timestamp string",
            "schema_version": "populated with nested live core event version 5",
            "body_type": "Progress or one inherited reliable body name",
            "body": (
                "exact progress_body dict or one inherited reliable body mapping"
            ),
        },
    },
    "progress_body": {
        "phase": "populated with execute",
        "items_done": (
            "populated with grouped-schedule emitted outcome counts from 0..148"
        ),
        "items_total": "populated with fixed selected admission 150",
        "bytes_done": "populated with attempted-work cadence 1..1500",
        "bytes_total": "populated with fixed reviewed work budget 1500",
        "current_path": "populated dynamic informational path; not identity",
        "item_id": (
            "populated 32-hex operation id; value-equals the first following "
            "ItemOutcome id but is independently allocated there"
        ),
        "item_type": "populated with operation",
        "item_attempt_id": "populated distinct 32-hex token per 25-byte attempt",
        "item_bytes_done": "populated with attempt-local cadence 1..25",
        "item_bytes_total": "populated with fixed attempt budget 25",
    },
    "mapping_families": {
        "SessionEventView.body": "ordinary Progress uses exactly progress_body",
        "other_body_types": "inherited unchanged from the frozen v1 representation",
    },
    "reliable_bodies": {
        "StateChanged": "populated at admission; fields and mapping inherited",
        "ItemOutcome": (
            "populated in ordinary and maximum with failed/degraded and "
            "unrecorded-mutation attribution; remaining fields inherited"
        ),
        "Terminal": (
            "populated at cleanup; result mapping inherited and its subject-scaled "
            "subtree is charged separately from transport custody"
        ),
        "Gap": "intentionally absent under both measured envelopes",
    },
    "maximum_no_gap": {
        "Progress": "intentionally absent",
        "Envelope.schema_version": "populated with live core event version 5",
        "SessionEventView.schema_version": (
            "populated with nested live core event version 5"
        ),
        "ItemOutcome": (
            "same current failed/degraded/unrecorded-mutation attribution as "
            "ordinary; remaining fields and body mapping inherited"
        ),
    },
    "aliasing": {
        "queue_envelope": (
            "one Envelope may be referenced by replay and subscriber custody; "
            "the recursive sizer deduplicates by identity"
        ),
        "view_body": (
            "SessionEventView owns a new dict whose keys are fixed serializer "
            "strings and whose scalar values forward the Progress field values"
        ),
        "item_identity": (
            "one item-id object is reused by 25 Progress snapshots; the first "
            "following ItemOutcome constructs an independent value-equal string"
        ),
        "attempt_identity": "one attempt-id value is reused by its 25 snapshots",
        "dynamic_paths": "each Progress owns one distinct informational path value",
    },
}

_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(_ROOT.resolve()))
_RETAINED = Path(__file__).with_name("_bridge_retained_memory.py")
_SOURCE_FILES = tuple(
    sorted(
        (
            *(path.relative_to(_ROOT) for path in (_ROOT / "namisync").rglob("*.py")),
            Path("tests/interfaces/web/_bridge_transport_custody.py"),
            Path("tests/bridge_transport_custody.py"),
        ),
        key=lambda path: path.as_posix(),
    )
)
_MODULE_PATHS = {
    "namisync": Path("namisync/__init__.py"),
    "namisync.core.events": Path("namisync/core/events.py"),
    "namisync.dispatcher.event_bus": Path("namisync/dispatcher/event_bus.py"),
    "namisync.interfaces.service": Path("namisync/interfaces/service.py"),
    "namisync.interfaces.web.drain": Path("namisync/interfaces/web/drain.py"),
    "namisync.workflows.views": Path("namisync/workflows/views.py"),
}
_FORBIDDEN_COMPONENT_CHARACTERS = frozenset('<>:"/\\|?*')
ALLOCATION_METHOD = (
    "recursive sys.getsizeof with identity deduplication, real queue "
    "shallow sizes, and path-local terminal-result exclusion"
)


@dataclass(slots=True)
class _RunState:
    task_index: int
    mode: str
    variant: str
    entered: threading.Event
    ordinary_releases: tuple[threading.Event, ...]
    ordinary_done: tuple[threading.Event, ...]
    ordinary_continue: tuple[threading.Event, ...]
    maximum_first_release: threading.Event
    maximum_first_done: threading.Event
    maximum_in_flight_release: threading.Event
    maximum_in_flight_done: threading.Event
    maximum_tail_release: threading.Event
    maximum_tail_done: threading.Event
    maximum_finish: threading.Event


class _CustodyInvocation:
    def __init__(self, state: _RunState) -> None:
        self._state = state

    def run(self, context):
        from namisync.core.evidence import RecordingStatus
        from namisync.core.session import OperationResult, SessionState

        self._state.entered.set()
        if self._state.mode == "ordinary":
            self._run_ordinary(context)
            bytes_done = 1_500
        else:
            self._run_maximum(context)
            bytes_done = 129
        return OperationResult(
            SessionState.FAILED,
            recording=RecordingStatus.DEGRADED,
            bytes_done=bytes_done,
            bytes_total=bytes_done,
        )

    def _run_ordinary(self, context) -> None:
        from namisync.core.events import ItemOutcome, Progress
        from namisync.core.evidence import RecordingStatus
        from namisync.core.execution import ItemRecordingReason

        reliable_pattern = (3, 3, 2, 2)
        outcome_offset = self._state.task_index * 150
        local_outcome = 0
        for tick in range(60):
            self._state.ordinary_releases[tick].wait()
            item_id = _item_id(
                self._state.variant,
                "ordinary",
                self._state.task_index,
                local_outcome,
            )
            attempt_id = _attempt_id(
                self._state.variant,
                self._state.task_index,
                tick,
            )
            for within_tick in range(25):
                local_progress = tick * 25 + within_tick
                ordinal = self._state.task_index * 1_500 + local_progress
                context.emit(
                    Progress(
                        "execute",
                        items_done=local_outcome,
                        items_total=150,
                        bytes_done=local_progress + 1,
                        bytes_total=1_500,
                        current_path=_payload_path(
                            "ordinary-progress",
                            ordinal,
                            _length_for(
                                ordinal,
                                6_000,
                                (5_700, 240, 60),
                                self._state.variant,
                            ),
                            self._state.variant,
                        ),
                        item_id=item_id,
                        item_type="operation",
                        item_attempt_id=attempt_id,
                        item_bytes_done=within_tick + 1,
                        item_bytes_total=25,
                    )
                )
            count = reliable_pattern[(self._state.task_index + tick) % 4]
            for _ in range(count):
                ordinal = outcome_offset + local_outcome
                length = _length_for(
                    ordinal, 600, (570, 24, 6), self._state.variant
                )
                kind, outcome, reason = _item_contract(ordinal)
                path = _payload_path(
                    "ordinary-item", ordinal, length, self._state.variant
                )
                context.emit(
                    ItemOutcome(
                        item_id=_item_id(
                            self._state.variant,
                            "ordinary",
                            self._state.task_index,
                            local_outcome,
                        ),
                        kind=kind,
                        path=path,
                        outcome=outcome,
                        reason=reason,
                        detail=_v5_detail(
                            _detail(
                                ordinal,
                                length,
                                "ordinary",
                                self._state.variant,
                                path,
                            )
                        ),
                        recording=RecordingStatus.DEGRADED,
                        recording_reason=ItemRecordingReason.UNRECORDED_MUTATION,
                        recording_detail=(
                            "published filesystem mutation failed before ledger settlement"
                            if ordinal % 3 == 1
                            else "filesystem mutation may have committed before ledger settlement"
                        ),
                    )
                )
                local_outcome += 1
            self._state.ordinary_done[tick].set()
            self._state.ordinary_continue[tick].wait()
        if local_outcome != 150:
            raise AssertionError("ordinary outcome schedule drifted")

    def _run_maximum(self, context) -> None:
        self._state.maximum_first_release.wait()
        for local in range(64):
            self._emit_maximum(context, local)
        self._state.maximum_first_done.set()
        self._state.maximum_in_flight_release.wait()
        self._emit_maximum(context, 64)
        self._state.maximum_in_flight_done.set()
        self._state.maximum_tail_release.wait()
        for local in range(65, 129):
            self._emit_maximum(context, local)
        self._state.maximum_tail_done.set()
        self._state.maximum_finish.wait()

    def _emit_maximum(self, context, local: int) -> None:
        from namisync.core.events import ItemOutcome
        from namisync.core.evidence import RecordingStatus
        from namisync.core.execution import ItemRecordingReason

        ordinal = self._state.task_index * 129 + local
        length = _length_for(
            ordinal, 516, (490, 21, 5), self._state.variant
        )
        kind, outcome, reason = _item_contract(ordinal)
        path = _payload_path(
            "maximum-item", ordinal, length, self._state.variant
        )
        context.emit(
            ItemOutcome(
                item_id=_item_id(
                    self._state.variant,
                    "maximum",
                    self._state.task_index,
                    local,
                ),
                kind=kind,
                path=path,
                outcome=outcome,
                reason=reason,
                detail=_v5_detail(
                    _detail(
                        ordinal,
                        length,
                        "maximum",
                        self._state.variant,
                        path,
                    )
                ),
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.UNRECORDED_MUTATION,
                recording_detail=(
                    "published filesystem mutation failed before ledger settlement"
                    if ordinal % 3 == 1
                    else "filesystem mutation may have committed before ledger settlement"
                ),
            )
        )

    def snapshot(self) -> object:
        return (self._state.mode, self._state.task_index)


class _QueueTracker:
    def __init__(self) -> None:
        self._high_water = {
            role: [0, 0, 0, 0]
            for role in ("replay", "subscriber", "adapter")
        }

    def observe(self, lengths: dict[str, list[int]]) -> None:
        for role, values in lengths.items():
            if len(values) != 4:
                raise AssertionError(f"{role} root count drifted")
            self._high_water[role] = [
                max(before, current)
                for before, current in zip(
                    self._high_water[role], values, strict=True
                )
            ]

    def summary(self) -> dict[str, object]:
        return {
            role: {
                "per_queue": list(values),
                "maximum": max(values),
            }
            for role, values in self._high_water.items()
        }


def _length_for(
    ordinal: int,
    population: int,
    counts: tuple[int, int, int],
    variant: str = "calibration-a",
) -> int:
    if sum(counts) != population or not 0 <= ordinal < population:
        raise ValueError("invalid frozen corpus position")
    multiplier, offset = _variant_permutation(variant)
    rank = (ordinal * multiplier + offset) % population
    if rank < counts[0]:
        return 240
    if rank < counts[0] + counts[1]:
        return 1_024
    return 4_096


def _payload_path(
    kind: str,
    ordinal: int,
    target_units: int,
    variant: str = "calibration-a",
) -> str:
    category_offset = 0 if variant == "calibration-a" else 1
    _variant_permutation(variant)
    category = ("ascii", "ascii", "bmp", "non_bmp")[
        (ordinal + category_offset) % 4
    ]
    token = f"x{variant.replace('-', 'x')}x{kind.replace('-', 'x')}x{ordinal:x}x"
    components = [token, *("x" for _ in range(31))]
    remaining = target_units - _utf16_units("\\".join(components))
    if remaining < 0:
        raise ValueError("path token exceeds the frozen path size")
    filler = {"ascii": "a", "bmp": "界", "non_bmp": "😀"}[category]
    if category == "non_bmp" and remaining % 2:
        components[0] += "a"
        remaining -= 1
    index = 0
    while remaining:
        components[index % 32] += filler
        remaining -= 2 if category == "non_bmp" else 1
        index += 1
    result = "\\".join(components)
    _validate_path(result, target_units)
    return result


def _validate_path(value: str, expected_units: int) -> None:
    components = value.split("\\")
    if len(components) != 32 or _utf16_units(value) != expected_units:
        raise AssertionError("frozen corpus path shape drifted")
    if any(
        not component
        or component[-1] in {".", " "}
        or any(character in _FORBIDDEN_COMPONENT_CHARACTERS for character in component)
        or _utf16_units(component) > 255
        for component in components
    ):
        raise AssertionError("frozen corpus path is not Windows legal")


def _utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _item_contract(ordinal: int) -> tuple[str, object, str]:
    from namisync.core.evidence import Outcome

    return (
        ("copy", Outcome.FAILED, "io-error"),
        ("move_update", Outcome.FAILED, "recorder-failed"),
        ("update", Outcome.FAILED, "io-error"),
    )[ordinal % 3]


def _item_id(variant: str, fixture: str, task: int, local: int) -> str:
    _variant_permutation(variant)
    if fixture not in {"ordinary", "maximum"} or not 0 <= task < 4 or local < 0:
        raise ValueError("invalid frozen item identity position")
    seed = f"{CORPUS_VERSION}\0{variant}\0{fixture}\0{task}\0{local}"
    return hashlib.sha256(seed.encode("ascii")).hexdigest()[:32]


def _attempt_id(variant: str, task: int, tick: int) -> str:
    _variant_permutation(variant)
    if not 0 <= task < 4 or not 0 <= tick < 60:
        raise ValueError("invalid current-v5 attempt identity position")
    seed = f"{CORPUS_VERSION}\0{variant}\0ordinary-attempt\0{task}\0{tick}"
    return hashlib.sha256(seed.encode("ascii")).hexdigest()[:32]


def _run_id(variant: str, fixture: str, task: int) -> str:
    _variant_permutation(variant)
    if fixture not in {"ordinary", "maximum"} or not 0 <= task < 4:
        raise ValueError("invalid frozen run identity position")
    seed = f"{CORPUS_VERSION}\0{variant}\0{fixture}\0run\0{task}"
    return hashlib.sha256(seed.encode("ascii")).hexdigest()[:32]


def _detail(
    ordinal: int,
    length: int,
    fixture: str,
    variant: str = "calibration-a",
    subject_path: str | None = None,
) -> dict[str, object]:
    family = ordinal % 3
    if subject_path is None:
        subject_path = _payload_path(
            f"{fixture}-item", ordinal, length, variant
        )
    _validate_path(subject_path, length)

    def value(label: str) -> str:
        return _payload_path(
            f"{fixture}-{label}", ordinal, length, variant
        )

    if family == 0:
        return {
            "error_type": "PermissionError",
            "message": (
                "copy publication failed for " + value("message-path")
            ),
            "cleanup_error": (
                "owned temporary cleanup failed for " + value("cleanup-path")
            ),
            "publish_state": "unverified",
            "published_path": subject_path,
            "durable_state": "publication-unverified",
            "state_error_type": "PermissionError",
            "state_error": (
                "publication-state probe failed for "
                + value("state-error-path")
            ),
            "recording": "degraded",
            "recording_error": (
                "filesystem mutation may have published but durable state "
                "could not be verified"
            ),
        }
    if family == 1:
        prior_path = value("prior-path")
        per_task = 150 if fixture == "ordinary" else 129
        run_id = _run_id(variant, fixture, ordinal // per_task)
        return {
            "error_type": "OperationFailure",
            "message": "recorder flush failed before destructive operation",
            "target_state": "published",
            "publish_state": "published",
            "published_path": subject_path,
            "prior_path": prior_path,
            "trash_path": f".synctrash\\{run_id}\\{prior_path}",
            "durable_state": "new-and-old",
            "recording": "degraded",
            "recording_error": (
                "published filesystem mutation failed before ledger settlement"
            ),
        }
    return {
        "error_type": "PermissionError",
        "message": "update mutation failed for " + value("message-path"),
        "publish_state": "not-published",
        "mutation_state": "unverified",
        "durable_state": "update-state-unverified",
        "mutation_state_error": (
            "PermissionError: mutation-state probe failed for "
            + value("mutation-state-path")
        ),
        "recording": "degraded",
        "recording_error": (
            "filesystem mutation may have committed before ledger settlement"
        ),
    }


def _v5_detail(value: dict[str, object]) -> dict[str, object]:
    """Adapt the frozen v1 corpus to the closed live-v5 detail projection."""

    return {
        key: member
        for key, member in value.items()
        if key not in {"recording", "recording_error"}
    }


def _variant_permutation(variant: str) -> tuple[int, int]:
    try:
        return {
            "calibration-a": (37, 17),
            "holdout-b": (41, 31),
        }[variant]
    except KeyError as error:
        raise ValueError("unknown transport-custody dataset variant") from error


def _structural_facts(variant: str) -> dict[str, object]:
    multiplier, offset = _variant_permutation(variant)
    return {
        **CORPUS_SPEC,
        "dataset_variant": variant,
        "active_length_permutation": {
            "multiplier": multiplier,
            "offset": offset,
        },
        "active_alphabet_offset": 0 if variant == "calibration-a" else 1,
    }


def _load_retained_instrument() -> ModuleType:
    name = "bridge_transport_retained_memory"
    specification = importlib.util.spec_from_file_location(name, _RETAINED)
    if specification is None or specification.loader is None:
        raise RuntimeError("retained-state instrument could not be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _states(mode: str, variant: str) -> tuple[_RunState, ...]:
    _variant_permutation(variant)
    ordinary_releases = tuple(threading.Event() for _ in range(60))
    ordinary_continue = tuple(threading.Event() for _ in range(60))
    maximum_first_release = threading.Event()
    maximum_in_flight_release = threading.Event()
    maximum_tail_release = threading.Event()
    maximum_finish = threading.Event()
    return tuple(
        _RunState(
            task_index=index,
            mode=mode,
            variant=variant,
            entered=threading.Event(),
            ordinary_releases=ordinary_releases,
            ordinary_done=tuple(threading.Event() for _ in range(60)),
            ordinary_continue=ordinary_continue,
            maximum_first_release=maximum_first_release,
            maximum_first_done=threading.Event(),
            maximum_in_flight_release=maximum_in_flight_release,
            maximum_in_flight_done=threading.Event(),
            maximum_tail_release=maximum_tail_release,
            maximum_tail_done=threading.Event(),
            maximum_finish=maximum_finish,
        )
        for index in range(4)
    )


def _wait_until(predicate, context: str, timeout: float = 10.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.002)
    raise TimeoutError(f"transport-custody fixture timed out: {context}")


def _queue_lengths(dispatcher, registry, starts) -> dict[str, list[int]]:
    result = {"replay": [], "subscriber": [], "adapter": []}
    for start in starts:
        with dispatcher._condition:
            hub = dispatcher._hubs[start.session_id]
        with hub._lock:
            if type(hub._replay) is not deque:
                raise AssertionError("replay custody root is not a built-in deque")
            result["replay"].append(len(hub._replay))
            streams = tuple(hub._subscribers)
        if len(streams) != 1:
            raise AssertionError("fixture requires one live subscriber per task")
        with streams[0]._condition:
            if type(streams[0]._items) is not deque:
                raise AssertionError("subscriber custody root is not a built-in deque")
            result["subscriber"].append(len(streams[0]._items))
        task = registry._tasks[start.task_id]
        with task.condition:
            if type(task.queue) is not deque:
                raise AssertionError("adapter custody root is not a built-in deque")
            result["adapter"].append(len(task.queue))
    return result


def _adapter_body_types(registry, starts) -> list[list[str]]:
    from namisync.workflows.views import SessionEventView

    bodies = []
    for start in starts:
        task = registry._tasks[start.task_id]
        with task.condition:
            updates = tuple(task.queue)
        if any(type(update) is not SessionEventView for update in updates):
            raise AssertionError("ordinary checkpoint retained a non-event update")
        if any(update.schema_version != 5 for update in updates):
            raise AssertionError("ordinary checkpoint retained a non-v5 event")
        bodies.append([update.body_type for update in updates])
    return bodies


def _subscribers_empty(dispatcher, starts, *, allow_absent: bool) -> bool:
    for start in starts:
        with dispatcher._condition:
            hub = dispatcher._hubs[start.session_id]
        with hub._lock:
            streams = tuple(hub._subscribers)
        if len(streams) > 1 or (not allow_absent and len(streams) != 1):
            return False
        for stream in streams:
            with stream._condition:
                if stream._items:
                    return False
    return True


def _has_gap(dispatcher, registry, starts) -> bool:
    from namisync.core.events import Gap
    from namisync.workflows.views import SessionEventView

    for start in starts:
        with dispatcher._condition:
            hub = dispatcher._hubs[start.session_id]
        with hub._lock:
            replay = tuple(hub._replay)
            streams = tuple(hub._subscribers)
        if any(isinstance(envelope.body, Gap) for envelope in replay):
            return True
        for stream in streams:
            with stream._condition:
                if any(isinstance(envelope.body, Gap) for envelope in stream._items):
                    return True
        task = registry._tasks[start.task_id]
        with task.condition:
            if any(
                type(update) is SessionEventView and update.body_type == "Gap"
                for update in task.queue
            ):
                return True
    return False


def _drain(registry, start, drain_ids) -> tuple[object, ...]:
    batch = registry.drain(
        start.task_id,
        start.session_id,
        next(drain_ids),
        replay_from=None,
    )
    return batch.updates


def _require_accounting_relations(
    measurement: dict[str, int],
    *,
    strict_shared: bool,
) -> None:
    _require_measurement_density(measurement)
    components = [
        measurement[f"{role}_queue_bytes"]
        for role in ("replay", "subscriber", "adapter")
    ]
    union = measurement["transport_custody_bytes"]
    if union < max(components) or union > sum(components):
        raise AssertionError("transport custody identity accounting drifted")
    if strict_shared and union >= sum(components):
        raise AssertionError("maximum custody did not exercise shared identities")
    if (
        measurement["terminal_artifact_bytes"] != 0
        or measurement["terminal_artifact_objects"] != 0
    ):
        raise AssertionError("preterminal transport snapshot retained terminal artifacts")


def _require_measurement_density(measurement: dict[str, int]) -> None:
    for prefix in (
        "adapter_queue",
        "replay_queue",
        "subscriber_queue",
        "terminal_artifact",
        "transport_custody",
    ):
        byte_count = measurement[f"{prefix}_bytes"]
        object_count = measurement[f"{prefix}_objects"]
        if object_count == 0:
            if byte_count != 0:
                raise AssertionError("empty custody root retained nonzero bytes")
        elif byte_count < object_count * 16:
            raise AssertionError("custody byte count is implausible for its objects")


def _require_terminal_path_cut(measurement: dict[str, int]) -> None:
    _require_measurement_density(measurement)
    if (
        measurement["terminal_artifact_bytes"] <= 0
        or measurement["terminal_artifact_objects"] <= 0
        or measurement["transport_custody_bytes"]
        >= measurement["terminal_artifact_bytes"]
    ):
        raise AssertionError("terminal-result path-cut witness was not exercised")


def _drain_initial(registry, starts, drain_ids) -> None:
    for start in starts:
        updates = _drain(registry, start, drain_ids)
        body_types = [
            update.event.body_type
            for update in updates
            if update.update_type == "event"
        ]
        if body_types != ["StateChanged", "StateChanged"]:
            raise AssertionError(f"unexpected admission events: {body_types}")
        if any(update.update_type == "record" for update in updates):
            raise AssertionError("fixture completed before its release")


def _ordinary_fixture(
    dispatcher,
    registry,
    starts,
    states,
    tracker,
    instrument,
    drain_ids,
) -> dict[str, object]:
    delivered_ids = {start.session_id: [] for start in starts}
    delivered_progress = {start.session_id: [] for start in starts}
    event_sequences = {start.session_id: [] for start in starts}
    quiescent_peak: dict[str, int] = {}
    for tick in range(60):
        states[0].ordinary_releases[tick].set()
        for state in states:
            if not state.ordinary_done[tick].wait(10):
                raise TimeoutError("ordinary producer did not finish its tick")

        def settled() -> bool:
            lengths = _queue_lengths(dispatcher, registry, starts)
            expected = [
                (3, 3, 2, 2)[(index + tick) % 4]
                for index in range(4)
            ]
            expected_bodies = [
                ["Progress", *("ItemOutcome" for _ in range(count))]
                for count in expected
            ]
            return (
                lengths["subscriber"] == [0, 0, 0, 0]
                and _adapter_body_types(registry, starts) == expected_bodies
            )

        _wait_until(settled, f"ordinary tick {tick} observation")
        tracker.observe(_queue_lengths(dispatcher, registry, starts))
        measurement = instrument.measure_retained_bridge_state(
            dispatcher, registry
        )
        for name, value in measurement.items():
            quiescent_peak[name] = max(quiescent_peak.get(name, 0), value)
        for start in starts:
            for update in _drain(registry, start, drain_ids):
                if update.update_type != "event":
                    raise AssertionError("ordinary fixture became terminal early")
                event = update.event
                event_sequences[start.session_id].append(event.sequence)
                if event.body_type == "Gap":
                    raise AssertionError("ordinary fixture produced Gap")
                if event.body_type == "ItemOutcome":
                    delivered_ids[start.session_id].append(event.body["item_id"])
                elif event.body_type == "Progress":
                    delivered_progress[start.session_id].append(
                        event.body["bytes_done"]
                    )
        states[0].ordinary_continue[tick].set()

    def terminals_quiescent() -> bool:
        for start in starts:
            task = registry._tasks[start.task_id]
            with task.condition:
                if task.terminal_record is None:
                    return False
        return _subscribers_empty(dispatcher, starts, allow_absent=True)

    _wait_until(terminals_quiescent, "ordinary terminal path-cut witness")
    if _has_gap(dispatcher, registry, starts):
        raise AssertionError("ordinary terminal path produced Gap")
    terminal_path_cut = instrument.measure_retained_bridge_state(
        dispatcher, registry
    )
    _require_terminal_path_cut(terminal_path_cut)
    for name, value in terminal_path_cut.items():
        if not name.startswith("terminal_artifact_"):
            quiescent_peak[name] = max(quiescent_peak.get(name, 0), value)

    terminal_records = {}
    terminal_events = {start.session_id: 0 for start in starts}
    terminal_orders = {start.session_id: [] for start in starts}
    for start in starts:
        def terminal_ready(start=start) -> bool:
            task = registry._tasks[start.task_id]
            with task.condition:
                return task.terminal_record is not None

        _wait_until(terminal_ready, "ordinary terminal record")
        for _ in range(4):
            updates = _drain(registry, start, drain_ids)
            for update in updates:
                if update.update_type == "record":
                    terminal_orders[start.session_id].append("record")
                    terminal_records[start.session_id] = update.record
                else:
                    event_sequences[start.session_id].append(
                        update.event.sequence
                    )
                    terminal_orders[start.session_id].append(
                        update.event.body_type
                    )
                    if update.event.body_type == "Terminal":
                        terminal_events[start.session_id] += 1
                    elif update.event.body_type == "Gap":
                        raise AssertionError(
                            "ordinary terminal delivery produced Gap"
                        )
            if start.session_id in terminal_records:
                break
        if start.session_id not in terminal_records:
            raise AssertionError("ordinary terminal record was not delivered")

    for index, start in enumerate(starts):
        expected = [
            _item_id(states[index].variant, "ordinary", index, item)
            for item in range(150)
        ]
        if delivered_ids[start.session_id] != expected:
            raise AssertionError("ordinary reliable ordering or delivery drifted")
        progress = [int(value) for value in delivered_progress[start.session_id]]
        if len(progress) != 60 or progress[-1] != 1_500 or any(
            earlier >= later
            for earlier, later in zip(progress, progress[1:], strict=False)
        ):
            raise AssertionError("ordinary progress cadence/final value drifted")
        record = terminal_records[start.session_id]
        retained = dispatcher.get(start.session_id)
        if (
            record.state != "failed"
            or record.result is None
            or record.result.headline != "failed"
            or record.result.bytes_done != "1500"
            or record.result.bytes_total != "1500"
            or retained.result is None
            or [item.item_id for item in retained.result.items] != expected
            or any(item.outcome.value != "failed" for item in retained.result.items)
            or terminal_events[start.session_id] != 1
            or terminal_orders[start.session_id]
            != ["StateChanged", "Terminal", "record"]
        ):
            raise AssertionError("ordinary terminal truth drifted")
        sequences = event_sequences[start.session_id]
        if sequences != sorted(set(sequences)):
            raise AssertionError("ordinary event sequence ordering drifted")

    checkpoint_peak = tracker.summary()
    _require_accounting_relations(quiescent_peak, strict_shared=False)
    for role in ("replay", "subscriber", "adapter"):
        if len(checkpoint_peak[role]["per_queue"]) != 4:
            raise AssertionError(f"ordinary {role} root count drifted")
    if checkpoint_peak["replay"]["maximum"] != 128:
        raise AssertionError("ordinary replay high-water did not reach 128")
    if checkpoint_peak["subscriber"]["per_queue"] != [0, 0, 0, 0]:
        raise AssertionError("ordinary checkpoint retained subscriber custody")
    if checkpoint_peak["adapter"]["per_queue"] != [4, 4, 4, 4]:
        raise AssertionError("ordinary exact-body checkpoint shape drifted")
    return {
        "emissions": {"progress": 6_000, "outcomes": 600},
        "root_container_type": "collections.deque",
        "delivered": {
            "progress": sum(map(len, delivered_progress.values())),
            "outcomes": sum(map(len, delivered_ids.values())),
            "terminal_events": sum(terminal_events.values()),
            "terminal_records": len(terminal_records),
        },
        "no_gap": True,
        "progress_per_task": [
            len(delivered_progress[start.session_id]) for start in starts
        ],
        "ordering": {
            "event_sequences_strict": True,
            "reliable_ids_exact": True,
            "terminal_order_exact": True,
        },
        "observed_checkpoint_peak": checkpoint_peak,
        "custody_sampling": (
            "60 exact-body producer-quiescent checkpoints plus terminal "
            "transport projection"
        ),
        "ordinary_quiescent_peak": quiescent_peak,
        "terminal_path_cut_witness": {
            "authority": "BR-G-45-nonnormative",
            "transport_result_exclusion_exercised": True,
            "measurement": terminal_path_cut,
        },
    }


def _maximum_fixture(
    dispatcher,
    registry,
    starts,
    states,
    tracker,
    instrument,
    drain_ids,
) -> dict[str, object]:
    states[0].maximum_first_release.set()
    for state in states:
        if not state.maximum_first_done.wait(10):
            raise TimeoutError("maximum first stage did not finish")
    _wait_until(
        lambda: _queue_lengths(dispatcher, registry, starts)["adapter"]
        == [64, 64, 64, 64],
        "maximum adapter fill",
    )
    tracker.observe(_queue_lengths(dispatcher, registry, starts))
    if _has_gap(dispatcher, registry, starts):
        raise AssertionError("maximum adapter fill produced Gap")

    states[0].maximum_in_flight_release.set()
    for state in states:
        if not state.maximum_in_flight_done.wait(10):
            raise TimeoutError("maximum in-flight stage did not finish")
    _wait_until(
        lambda: _queue_lengths(dispatcher, registry, starts)["subscriber"]
        == [0, 0, 0, 0],
        "maximum in-flight transfer",
    )
    tracker.observe(_queue_lengths(dispatcher, registry, starts))

    states[0].maximum_tail_release.set()
    for state in states:
        if not state.maximum_tail_done.wait(10):
            raise TimeoutError("maximum tail stage did not finish")
    expected_lengths = {
        "replay": [128, 128, 128, 128],
        "subscriber": [64, 64, 64, 64],
        "adapter": [64, 64, 64, 64],
    }
    _wait_until(
        lambda: _queue_lengths(dispatcher, registry, starts) == expected_lengths,
        "maximum no-Gap shape",
    )
    tracker.observe(_queue_lengths(dispatcher, registry, starts))
    if _has_gap(dispatcher, registry, starts):
        raise AssertionError("maximum reachable shape produced Gap")
    measurement = instrument.measure_retained_bridge_state(dispatcher, registry)
    _require_accounting_relations(measurement, strict_shared=True)
    if _queue_lengths(dispatcher, registry, starts) != expected_lengths:
        raise AssertionError("maximum shape changed during measurement")

    delivered = {start.session_id: [] for start in starts}
    delivery_deadline = monotonic() + 10
    while any(len(items) < 129 for items in delivered.values()):
        made_progress = False
        for start in starts:
            if len(delivered[start.session_id]) >= 129:
                continue
            task = registry._tasks[start.task_id]
            with task.condition:
                available = bool(task.queue)
            if not available:
                continue
            for update in _drain(registry, start, drain_ids):
                if update.update_type != "event":
                    raise AssertionError("maximum fixture became terminal early")
                if update.event.body_type == "Gap":
                    raise AssertionError("maximum fixture cleanup produced Gap")
                if update.event.body_type != "ItemOutcome":
                    raise AssertionError(
                        "maximum fixture cleanup delivered an unexpected event"
                    )
                delivered[start.session_id].append(update.event.body["item_id"])
                made_progress = True
        if monotonic() >= delivery_deadline:
            raise TimeoutError("maximum reliable cleanup did not complete")
        if not made_progress:
            sleep(0.002)

    for index, start in enumerate(starts):
        expected = [
            _item_id(states[index].variant, "maximum", index, item)
            for item in range(129)
        ]
        if delivered[start.session_id] != expected:
            raise AssertionError("maximum reliable cleanup lost or reordered items")
    _wait_until(
        lambda: all(
            values == [0, 0, 0, 0]
            for role, values in _queue_lengths(
                dispatcher, registry, starts
            ).items()
            if role in {"subscriber", "adapter"}
        ),
        "maximum reliable custody release",
    )

    states[0].maximum_finish.set()
    terminal_orders = {start.session_id: [] for start in starts}
    terminal_records = {}
    for start in starts:
        terminal_deadline = monotonic() + 10
        while start.session_id not in terminal_records:
            task = registry._tasks[start.task_id]
            with task.condition:
                available = bool(task.queue) or task.terminal_pending
            if not available:
                if monotonic() >= terminal_deadline:
                    raise TimeoutError("maximum terminal cleanup did not complete")
                sleep(0.002)
                continue
            for update in _drain(registry, start, drain_ids):
                if update.update_type == "record":
                    terminal_orders[start.session_id].append("record")
                    terminal_records[start.session_id] = update.record
                    continue
                body_type = update.event.body_type
                if body_type == "Gap":
                    raise AssertionError("maximum terminal cleanup produced Gap")
                if body_type == "ItemOutcome":
                    raise AssertionError("maximum terminal cleanup duplicated an item")
                terminal_orders[start.session_id].append(body_type)

    for index, start in enumerate(starts):
        expected = [
            _item_id(states[index].variant, "maximum", index, item)
            for item in range(129)
        ]
        record = terminal_records[start.session_id]
        retained = dispatcher.get(start.session_id)
        if terminal_orders[start.session_id] != [
            "StateChanged",
            "Terminal",
            "record",
        ]:
            raise AssertionError("maximum terminal ordering drifted")
        if (
            record.state != "failed"
            or record.result is None
            or record.result.headline != "failed"
            or retained.result is None
            or [item.item_id for item in retained.result.items] != expected
            or any(item.outcome.value != "failed" for item in retained.result.items)
        ):
            raise AssertionError("maximum terminal record drifted")

    return {
        "emissions": {"outcomes": 516},
        "root_container_type": "collections.deque",
        "no_gap": True,
        "queue_lengths": expected_lengths,
        "observed_queue_high_water": tracker.summary(),
        "custody_sampling": "exact producer-quiescent maximum no-Gap shape",
        "custody": measurement,
        "cleanup_delivery": {
            "outcomes": sum(map(len, delivered.values())),
            "outcomes_per_task": [
                len(delivered[start.session_id]) for start in starts
            ],
            "terminal_events": sum(
                order.count("Terminal") for order in terminal_orders.values()
            ),
            "terminal_records": len(terminal_records),
            "terminal_order_exact": True,
            "failed_state_headline_records": sum(
                record.state == "failed"
                and record.result is not None
                and record.result.headline == "failed"
                for record in terminal_records.values()
            ),
        },
    }


def _run_fixture(
    root: Path,
    mode: str,
    variant: str,
    instrument,
) -> dict[str, object]:
    from namisync.dispatcher import Dispatcher, PreparedSession, WorkflowRegistration
    from namisync.interfaces import service as service_module
    from namisync.interfaces.service import NamiSyncService
    from namisync.interfaces.web.drain import TaskRegistry
    from namisync.workflows import PLAN_KIND

    states = _states(mode, variant)
    state_by_checkpoint: dict[object, _RunState] = {}
    roots = []
    for state in states:
        source = root / "sources" / f"task-{state.task_index}"
        target = root / "targets" / f"task-{state.task_index}"
        source.mkdir(parents=True)
        target.mkdir(parents=True)
        roots.append((str(source), str(target)))
        state_by_checkpoint[str(source)] = state

    def prepare(request) -> PreparedSession:
        return PreparedSession(str(request.source_path))

    def open_invocation(checkpoint: object) -> _CustodyInvocation:
        return _CustodyInvocation(state_by_checkpoint[checkpoint])

    tracker = _QueueTracker()

    dispatcher = Dispatcher(
        {PLAN_KIND: WorkflowRegistration(prepare, open_invocation)}
    )
    with patch.object(
        service_module, "_dispatcher", lambda _runtime: dispatcher
    ):
        service = NamiSyncService(root / "ledger.db", root / "history.db")
    tokens = iter(f"{index:032x}" for index in range(1, 20_000))
    registry = TaskRegistry(
        service,
        token=lambda: next(tokens),
        drain_wait=0.1,
        progress_linger=0.001,
    )
    drain_ids = iter(f"{index:032x}" for index in range(20_000, 40_000))
    starts = []
    try:
        for index, (source, target) in enumerate(roots):
            starts.append(
                registry.start_plan(
                    source,
                    target,
                    deletion_policy=None,
                    command_id=f"{index + 1:032x}",
                )
            )
        for state in states:
            if not state.entered.wait(10):
                raise TimeoutError("fixture workflow did not enter")
        _wait_until(
            lambda: _queue_lengths(dispatcher, registry, starts)["adapter"]
            == [2, 2, 2, 2],
            "admission state delivery",
        )
        tracker.observe(_queue_lengths(dispatcher, registry, starts))
        _drain_initial(registry, starts, drain_ids)
        tracker.observe(_queue_lengths(dispatcher, registry, starts))
        if mode == "ordinary":
            result = _ordinary_fixture(
                dispatcher,
                registry,
                starts,
                states,
                tracker,
                instrument,
                drain_ids,
            )
        else:
            result = _maximum_fixture(
                dispatcher,
                registry,
                starts,
                states,
                tracker,
                instrument,
                drain_ids,
            )
        return result
    finally:
        for state in states:
            for release in state.ordinary_releases:
                release.set()
            for release in state.ordinary_continue:
                release.set()
            state.maximum_first_release.set()
            state.maximum_in_flight_release.set()
            state.maximum_tail_release.set()
            state.maximum_finish.set()
        registry.begin_close()
        registry.unsubscribe_all()
        service.close(timeout=5)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hashes(paths: tuple[Path, ...]) -> tuple[dict[str, str], str]:
    entries = {
        path.as_posix(): hashlib.sha256((_ROOT / path).read_bytes()).hexdigest()
        for path in paths
    }
    return entries, _canonical_hash(entries)


def _dependency_authority(root: Path) -> dict[str, object]:
    expected_root = (
        Path(sys.executable).resolve().parent.parent / "Lib" / "site-packages"
    ).resolve()
    root = root.resolve()
    if root != expected_root or not root.is_dir():
        raise RuntimeError("custody dependency root is not the active venv")
    package = root / "xxhash"
    extensions = tuple(package.glob("_xxhash*.pyd"))
    if len(extensions) != 1:
        raise RuntimeError("custody xxhash extension set is not exact")
    paths = (
        package / "__init__.py",
        package / "version.py",
        extensions[0],
    )
    if any(not path.is_file() for path in paths):
        raise RuntimeError("custody xxhash dependency is incomplete")
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in paths
    }
    return {
        "root": str(root),
        "files": files,
        "sha256": _canonical_hash(files),
    }


def _module_origins(dependency: dict[str, object]) -> dict[str, str]:
    origins = {}
    for name, relative in _MODULE_PATHS.items():
        module = importlib.import_module(name)
        raw_origin = getattr(module, "__file__", None)
        if not isinstance(raw_origin, str):
            raise RuntimeError(f"custody source module has no file origin: {name}")
        origin = Path(raw_origin).resolve()
        expected = (_ROOT / relative).resolve()
        if origin != expected:
            raise RuntimeError(
                f"custody source module resolved outside tested source: {name}"
            )
        origins[name] = str(origin)
    dependency_root = Path(dependency["root"])
    dependency_files = dependency["files"]
    extension = next(
        path for path in dependency_files if path.startswith("xxhash/_xxhash")
    )
    dependency_modules = {
        "xxhash": "xxhash/__init__.py",
        "xxhash.version": "xxhash/version.py",
        "xxhash._xxhash": extension,
    }
    for name, relative in dependency_modules.items():
        module = importlib.import_module(name)
        raw_origin = getattr(module, "__file__", None)
        if not isinstance(raw_origin, str):
            raise RuntimeError(f"custody dependency has no file origin: {name}")
        origin = Path(raw_origin).resolve()
        expected = (dependency_root / relative).resolve()
        if origin != expected:
            raise RuntimeError(
                f"custody dependency resolved outside authority: {name}"
            )
        origins[name] = str(origin)
    return origins


def _runtime(dependency_root: Path) -> dict[str, object]:
    qualifier_environment = {
        name: value
        for name, value in os.environ.items()
        if name.upper().startswith("PYTHON")
    }
    return {
        "python": sys.version,
        "version_info": [
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
            sys.version_info.releaselevel,
            sys.version_info.serial,
        ],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": str(Path(sys.executable).resolve()),
        "pointer_bits": struct.calcsize("P") * 8,
        "py_debug": int(sysconfig.get_config_var("Py_DEBUG") or 0),
        "with_pymalloc_config": sysconfig.get_config_var("WITH_PYMALLOC"),
        "allocator_predicate": "explicit-pymalloc-on-qualified-Windows-CPython",
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "python_malloc": os.environ.get("PYTHONMALLOC", "default"),
        "no_site": sys.flags.no_site,
        "safe_path": sys.flags.safe_path,
        "pycache_prefix": sys.pycache_prefix,
        "pycache_prefix_role": "fresh-empty-per-child-outside-source-tree",
        "dependency_root": str(dependency_root),
        "optimize": sys.flags.optimize,
        "dev_mode": sys.flags.dev_mode,
        "tracemalloc": tracemalloc.is_tracing(),
        "qualifier_environment": qualifier_environment,
        "allocation_method": ALLOCATION_METHOD,
    }


def _runtime_qualifier(runtime: dict[str, object]) -> dict[str, object]:
    normalized = dict(runtime)
    normalized["pycache_prefix"] = "<fresh-per-child>"
    environment = dict(runtime["qualifier_environment"])
    environment["PYTHONPYCACHEPREFIX"] = "<fresh-per-child>"
    normalized["qualifier_environment"] = environment
    return normalized


def run_once(
    root: Path,
    *,
    variant: str,
    tested_commit: str,
    dependency_root: Path,
) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", tested_commit) is None:
        raise ValueError("tested commit must be a full lowercase Git object id")
    pycache_prefix = os.environ.get("PYTHONPYCACHEPREFIX")
    if (
        sys.flags.no_site != 1
        or sys.flags.safe_path is not True
        or pycache_prefix is None
        or sys.pycache_prefix != pycache_prefix
    ):
        raise RuntimeError("custody child launch isolation is invalid")
    try:
        Path(pycache_prefix).resolve().relative_to(_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise RuntimeError("custody child pycache prefix enters source tree")
    dependency = _dependency_authority(dependency_root)
    structural_facts = _structural_facts(variant)
    module_origins = _module_origins(dependency)
    instrument = _load_retained_instrument()
    source_files, source_hash = _file_hashes(_SOURCE_FILES)
    runtime = _runtime(dependency_root.resolve())
    ordinary_root = root / "ordinary"
    maximum_root = root / "maximum"
    ordinary_root.mkdir(parents=True)
    maximum_root.mkdir(parents=True)
    ordinary = _run_fixture(
        ordinary_root, "ordinary", variant, instrument
    )
    maximum = _run_fixture(
        maximum_root, "maximum", variant, instrument
    )
    evidence = {
        "ordinary": ordinary,
        "maximum_no_gap": maximum,
    }
    return {
        "schema_version": 1,
        "gate": "SH-G-8 transport custody",
        "corpus_version": CORPUS_VERSION,
        "dataset_variant": variant,
        "tested_commit": tested_commit,
        "headroom_policy": HEADROOM_POLICY,
        "process_id": os.getpid(),
        "module_origins": module_origins,
        "dependency_authority": dependency,
        "runtime": runtime,
        "hashes": {
            "runtime_sha256": _canonical_hash(runtime),
            "runtime_qualifier_sha256": _canonical_hash(
                _runtime_qualifier(runtime)
            ),
            "source_sha256": source_hash,
            "source_files": source_files,
            "corpus_sha256": _canonical_hash(structural_facts),
            "instrument_sha256": hashlib.sha256(_RETAINED.read_bytes()).hexdigest(),
            "evidence_sha256": _canonical_hash(evidence),
        },
        "structural_facts": structural_facts,
        **evidence,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--variant", required=True, choices=("calibration-a", "holdout-b")
    )
    parser.add_argument("--tested-commit", required=True)
    parser.add_argument("--dependency-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    dependency_root = arguments.dependency_root.resolve()
    sys.path.append(str(dependency_root))
    arguments.root.mkdir(parents=True, exist_ok=False)
    result = run_once(
        arguments.root.resolve(),
        variant=arguments.variant,
        tested_commit=arguments.tested_commit,
        dependency_root=dependency_root,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "gate": result["gate"],
                "dataset_variant": result["dataset_variant"],
                "tested_commit": result["tested_commit"],
                "process_id": result["process_id"],
                "evidence_sha256": result["hashes"]["evidence_sha256"],
                "artifact_sha256": _canonical_hash(result),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CORPUS_SPEC",
    "CORPUS_VERSION",
    "HEADROOM_POLICY",
    "run_once",
]
