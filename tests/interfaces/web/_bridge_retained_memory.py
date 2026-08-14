"""Separate deep-size instrument for retained bridge state fixtures."""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from namisync.core.events import Envelope, Terminal
from namisync.workflows.views import SessionEventView, SessionRecordView


@dataclass(frozen=True, slots=True)
class _QueueSnapshot:
    container: object
    identity: int
    shallow_bytes: int
    items: tuple[object, ...]


class _DeepSizer:
    def __init__(self) -> None:
        self._seen: set[int] = set()
        self.total = 0

    @property
    def identities(self) -> frozenset[int]:
        return frozenset(self._seen)

    def add_shallow(self, item: object) -> bool:
        identity = id(item)
        return self.add_known_shallow(identity, sys.getsizeof(item))

    def add_known_shallow(self, identity: int, size: int) -> bool:
        if identity in self._seen:
            return False
        self._seen.add(identity)
        self.total += size
        return True

    def add(self, item: object) -> None:
        if not self.add_shallow(item):
            return
        if type(item) in {dict, MappingProxyType}:
            for key, child in item.items():
                self.add(key)
                self.add(child)
            return
        if type(item) in {tuple, list, set, frozenset, deque}:
            for child in item:
                self.add(child)
            return
        if is_dataclass(item) and not isinstance(item, type):
            for field in fields(item):
                self.add(getattr(item, field.name))
            return
        if isinstance(item, Enum):
            return
        if type(item) in {
            type(None),
            bool,
            int,
            float,
            complex,
            str,
            bytes,
            datetime,
        }:
            return
        raise TypeError(
            "retained-state deep size does not support "
            f"{type(item).__module__}.{type(item).__qualname__}"
        )


def measure_retained_bridge_state(
    dispatcher: object,
    registry: object,
) -> dict[str, int]:
    """Measure terminal result artifacts separately from transport custody.

    Queue contents are copied while their owner lock is held, while the real
    queue's shallow storage is recorded before release. Two matching capture
    passes are required. Transport components are not additive; terminal and
    transport totals are independently rooted and are also not additive.
    """

    adapter_roots, retained_records = _adapter_snapshots(registry)
    replay_roots, subscriber_roots = _dispatcher_snapshots(dispatcher)
    adapter_after, records_after = _adapter_snapshots(registry)
    replay_after, subscriber_after = _dispatcher_snapshots(dispatcher)
    _require_quiescent("adapter queues", adapter_roots, adapter_after)
    _require_quiescent("replay queues", replay_roots, replay_after)
    _require_quiescent(
        "subscriber queues",
        subscriber_roots,
        subscriber_after,
    )
    if tuple(map(id, retained_records)) != tuple(map(id, records_after)):
        raise RuntimeError(
            "retained-state fixture is not quiescent: terminal records changed"
        )

    replay, _ = _size_transport(replay_roots)
    subscriber, _ = _size_transport(subscriber_roots)
    adapter, _ = _size_transport(adapter_roots)
    transport, terminal_results = _size_transport(
        (*replay_roots, *subscriber_roots, *adapter_roots),
    )

    terminal = _DeepSizer()
    for record in retained_records:
        terminal.add(record)
    for result in terminal_results:
        terminal.add(result)

    return {
        "adapter_queue_bytes": adapter.total,
        "adapter_queue_objects": len(adapter.identities),
        "replay_queue_bytes": replay.total,
        "replay_queue_objects": len(replay.identities),
        "subscriber_queue_bytes": subscriber.total,
        "subscriber_queue_objects": len(subscriber.identities),
        "terminal_artifact_bytes": terminal.total,
        "terminal_artifact_objects": len(terminal.identities),
        "transport_custody_bytes": transport.total,
        "transport_custody_objects": len(transport.identities),
    }


def _adapter_snapshots(
    registry: object,
) -> tuple[tuple[_QueueSnapshot, ...], tuple[SessionRecordView, ...]]:
    with registry._condition:
        tasks = tuple(registry._tasks.values())
    roots = []
    records = []
    for task in tasks:
        with task.condition:
            roots.append(_snapshot_queue(task.queue))
            if task.terminal_record is not None:
                records.append(task.terminal_record)
    return tuple(roots), tuple(records)


def _dispatcher_snapshots(
    dispatcher: object,
) -> tuple[tuple[_QueueSnapshot, ...], tuple[_QueueSnapshot, ...]]:
    with dispatcher._condition:
        hubs = tuple(dispatcher._hubs.values())
    replay_roots = []
    subscriber_roots = []
    for hub in hubs:
        with hub._lock:
            replay_roots.append(_snapshot_queue(hub._replay))
            streams = tuple(hub._subscribers)
        for stream in streams:
            with stream._condition:
                subscriber_roots.append(_snapshot_queue(stream._items))
    return tuple(replay_roots), tuple(subscriber_roots)


def _snapshot_queue(queue: object) -> _QueueSnapshot:
    return _QueueSnapshot(queue, id(queue), sys.getsizeof(queue), tuple(queue))


def _require_quiescent(
    label: str,
    before: tuple[_QueueSnapshot, ...],
    after: tuple[_QueueSnapshot, ...],
) -> None:
    signatures_before = tuple(
        (
            root.identity,
            root.shallow_bytes,
            tuple(map(id, root.items)),
        )
        for root in before
    )
    signatures_after = tuple(
        (
            root.identity,
            root.shallow_bytes,
            tuple(map(id, root.items)),
        )
        for root in after
    )
    if signatures_before != signatures_after:
        raise RuntimeError(
            f"retained-state fixture is not quiescent: {label} changed"
        )


def _size_transport(
    roots: tuple[_QueueSnapshot, ...],
) -> tuple[_DeepSizer, tuple[object, ...]]:
    sizer = _DeepSizer()
    terminal_results = []
    for root in roots:
        sizer.add_known_shallow(root.identity, root.shallow_bytes)
        for item in root.items:
            _add_transport_item(sizer, item, terminal_results)
    return sizer, tuple(terminal_results)


def _add_transport_item(
    sizer: _DeepSizer,
    item: object,
    terminal_results: list[object],
) -> None:
    if isinstance(item, Envelope) and isinstance(item.body, Terminal):
        if sizer.add_shallow(item):
            for name in item.__dataclass_fields__:
                if name != "body":
                    sizer.add(getattr(item, name))
        terminal = item.body
        sizer.add_shallow(terminal)
        terminal_results.append(terminal.result)
        return
    if isinstance(item, SessionEventView) and item.body_type == "Terminal":
        if sizer.add_shallow(item):
            for name in item.__dataclass_fields__:
                if name != "body":
                    sizer.add(getattr(item, name))
        if sizer.add_shallow(item.body):
            for key, value in item.body.items():
                sizer.add(key)
                if key == "result":
                    terminal_results.append(value)
                else:
                    sizer.add(value)
        return
    if isinstance(item, SessionRecordView):
        _add_record_metadata(sizer, item)
        if item.result is not None:
            terminal_results.append(item.result)
        return
    sizer.add(item)


def _add_record_metadata(sizer: _DeepSizer, record: SessionRecordView) -> None:
    if not sizer.add_shallow(record):
        return
    for name in record.__dataclass_fields__:
        if name != "result":
            sizer.add(getattr(record, name))


__all__ = ["measure_retained_bridge_state"]
