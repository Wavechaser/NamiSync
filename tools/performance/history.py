"""Selected bounded history diagnostics and the unchanged release profile."""

from __future__ import annotations

import os
import platform
import sqlite3
import statistics
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


from namisync.core.events import (
    Envelope,
    ItemOutcome,
    PhaseChanged,
    CORE_EVENT_SCHEMA_VERSION,
    StateChanged,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.history import (
    DEFAULT_HISTORY_WINDOW_POLICY,
    HistoryContext,
    HistoryObserver,
    HistoryRepository,
    HistoryStore,
)


RUN_COUNT = 50
TOTAL_ITEMS = 1_000_000
LARGE_RUN_ITEMS = 100_000
PAGE_SIZE = 256
PAGE_SAMPLE_COUNT = 40
CASES = ("smoke", "release")


@dataclass(frozen=True)
class _Fixture:
    name: str
    runs: int
    items: int
    largest_run_items: int
    page_size: int
    page_samples: int


_RELEASE = _Fixture("release", RUN_COUNT, TOTAL_ITEMS, LARGE_RUN_ITEMS, PAGE_SIZE, PAGE_SAMPLE_COUNT)
_SMOKE = _Fixture("smoke", 2, 96, 64, 16, 4)

SUMMARY_MAX_SECONDS = 3.0
PAGE_P95_MAX_SECONDS = 0.5
PAGE_MAX_SECONDS = 1.0
WINDOW_COMMIT_MAX_SECONDS = 5.0

NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _run_sizes(fixture: _Fixture) -> tuple[int, ...]:
    remaining = fixture.items - fixture.largest_run_items
    base, extra = divmod(remaining, fixture.runs - 1)
    sizes = (fixture.largest_run_items,) + tuple(
        base + (1 if index < extra else 0)
        for index in range(fixture.runs - 1)
    )
    assert len(sizes) == fixture.runs
    assert sum(sizes) == fixture.items
    return sizes


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[percentile - 1]


def _timed(call):
    started = perf_counter()
    result = call()
    return result, perf_counter() - started


def _record_fixture(path: Path, fixture: _Fixture) -> dict[str, object]:
    policy = DEFAULT_HISTORY_WINDOW_POLICY
    transaction_seconds: list[float] = []
    peak_pending_count = 0
    peak_pending_bytes = 0
    active_observer: HistoryObserver | None = None
    started = perf_counter()
    with HistoryStore(path, clock=_Clock(), window_policy=policy) as store:
        original_transact = store._writer.transact

        def timed_transact(operation):
            nonlocal peak_pending_count, peak_pending_bytes
            if active_observer is not None:
                peak_pending_count = max(
                    peak_pending_count,
                    active_observer.pending_event_count,
                )
                peak_pending_bytes = max(
                    peak_pending_bytes,
                    active_observer.pending_bytes,
                )
            transaction_started = perf_counter()
            try:
                return original_transact(operation)
            finally:
                transaction_seconds.append(perf_counter() - transaction_started)

        store._writer.transact = timed_transact
        expected_transactions = 0
        for run_index, item_count in enumerate(_run_sizes(fixture)):
            record = SessionRecord(
                session_id=SessionId(f"{run_index + 1:032x}"),
                kind="sync",
                state=SessionState.PENDING,
                resources=(),
                checkpoint=b"benchmark",
                supports_pause=True,
                admission_order=run_index,
                created_at=NOW,
            )
            observer = store.observer(
                record,
                HistoryContext(f"benchmark-run-{run_index:02d}", "benchmark-host"),
            )
            active_observer = observer
            observer.on_event(
                Envelope(
                    record.session_id,
                    1,
                    NOW,
                    CORE_EVENT_SCHEMA_VERSION,
                    StateChanged(SessionState.RUNNING),
                )
            )
            observer.on_event(
                Envelope(
                    record.session_id,
                    2,
                    NOW,
                    CORE_EVENT_SCHEMA_VERSION,
                    PhaseChanged("execute"),
                )
            )
            for item_index in range(item_count):
                sequence = item_index + 3
                observer.on_event(
                    Envelope(
                        record.session_id,
                        sequence,
                        NOW,
                        CORE_EVENT_SCHEMA_VERSION,
                        ItemOutcome(
                            item_id=f"{item_index + 1:032x}",
                            kind="copy",
                            path=f"directory/file-{item_index:06d}.bin",
                            outcome=Outcome.SUCCEEDED,
                        ),
                    )
                )
                peak_pending_count = max(
                    peak_pending_count, observer.pending_event_count
                )
                peak_pending_bytes = max(
                    peak_pending_bytes, observer.pending_bytes
                )
            observer.finalize(OperationResult(SessionState.COMPLETED))
            observer.close()
            expected_transactions += (item_count + 2) // policy.max_events + 1
        active_observer = None
    recording_seconds = perf_counter() - started
    assert len(transaction_seconds) == expected_transactions
    return {
        "recording_seconds": recording_seconds,
        "transaction_count": len(transaction_seconds),
        "transaction_samples_ms": [value * 1_000 for value in transaction_seconds],
        "transaction_p50_ms": statistics.median(transaction_seconds) * 1_000,
        "transaction_p95_ms": _percentile(transaction_seconds, 95) * 1_000,
        "transaction_max_ms": max(transaction_seconds) * 1_000,
        "peak_pending_events": peak_pending_count,
        "peak_pending_bytes": peak_pending_bytes,
        "transaction_max_seconds": max(transaction_seconds),
    }


def _measure_readback(path: Path, fixture: _Fixture) -> dict[str, object]:
    with HistoryRepository(path) as repository:
        summaries, cold_summary_seconds = _timed(
            lambda: repository.list_summaries(fixture.runs)
        )
        _, warm_summary_seconds = _timed(
            lambda: repository.list_summaries(fixture.runs)
        )
        assert len(summaries) == fixture.runs
        assert sum(summary.item_count for summary in summaries) == fixture.items
        assert all(summary.finalized for summary in summaries)
        assert all(summary.audit is RecordingStatus.OK for summary in summaries)

    large_run = "benchmark-run-00"
    with HistoryRepository(path) as repository:
        _, item_cold_seconds = _timed(
            lambda: repository.get_item_page(
                large_run,
                through_order=fixture.largest_run_items,
                limit=fixture.page_size,
            )
        )
    with HistoryRepository(path) as repository:
        _, event_cold_seconds = _timed(
            lambda: repository.get_event_page(
                large_run,
                through_seq=fixture.largest_run_items + 2,
                limit=fixture.page_size,
            )
        )

    with HistoryRepository(path) as repository:
        repository.get_item_page(
            large_run,
            through_order=fixture.largest_run_items,
            limit=fixture.page_size,
        )
        repository.get_event_page(
            large_run,
            through_seq=fixture.largest_run_items + 2,
            limit=fixture.page_size,
        )
        item_page_seconds: list[float] = []
        event_page_seconds: list[float] = []
        for sample in range(fixture.page_samples):
            item_after = sample * fixture.largest_run_items // fixture.page_samples
            item_page, elapsed = _timed(
                lambda item_after=item_after: repository.get_item_page(
                    large_run,
                    after_order=item_after,
                    through_order=fixture.largest_run_items,
                    limit=fixture.page_size,
                )
            )
            assert 1 <= len(item_page.items) <= fixture.page_size
            item_page_seconds.append(elapsed)

            event_after = sample * (fixture.largest_run_items + 2) // fixture.page_samples
            event_page, elapsed = _timed(
                lambda event_after=event_after: repository.get_event_page(
                    large_run,
                    after_seq=event_after,
                    through_seq=fixture.largest_run_items + 2,
                    limit=fixture.page_size,
                )
            )
            assert 1 <= len(event_page.events) <= fixture.page_size
            event_page_seconds.append(elapsed)

    return {
        "summary_cold_reader_seconds": cold_summary_seconds,
        "summary_warm_reader_seconds": warm_summary_seconds,
        "item_page_cold_reader_ms": item_cold_seconds * 1_000,
        "item_page_p50_ms": statistics.median(item_page_seconds) * 1_000,
        "item_page_samples_ms": [value * 1_000 for value in item_page_seconds],
        "item_page_p95_ms": _percentile(item_page_seconds, 95) * 1_000,
        "item_page_max_ms": max(item_page_seconds) * 1_000,
        "item_page_p95_seconds": _percentile(item_page_seconds, 95),
        "item_page_max_seconds": max(item_page_seconds),
        "event_page_cold_reader_ms": event_cold_seconds * 1_000,
        "event_page_p50_ms": statistics.median(event_page_seconds) * 1_000,
        "event_page_samples_ms": [value * 1_000 for value in event_page_seconds],
        "event_page_p95_ms": _percentile(event_page_seconds, 95) * 1_000,
        "event_page_max_ms": max(event_page_seconds) * 1_000,
        "event_page_p95_seconds": _percentile(event_page_seconds, 95),
        "event_page_max_seconds": max(event_page_seconds),
    }


def run_case(
    case: str, *, output: Path, installed_root: Path | None = None
) -> dict[str, object]:
    if case not in CASES:
        raise ValueError(f"unknown history case: {case}")
    fixture = _SMOKE if case == "smoke" else _RELEASE
    with tempfile.TemporaryDirectory(prefix="namisync-history-benchmark-") as temp:
        path = Path(temp) / "history.db"
        recording = _record_fixture(path, fixture)
        readback = _measure_readback(path, fixture)
        report = {
            "case": case,
            "status": "complete",
            "release_gates_applied": case == "release",
            "fixture": {
                "profile": fixture.name,
                "runs": fixture.runs,
                "items": fixture.items,
                "largest_run_items": fixture.largest_run_items,
                "window_policy": {
                    "max_events": DEFAULT_HISTORY_WINDOW_POLICY.max_events,
                    "max_bytes": DEFAULT_HISTORY_WINDOW_POLICY.max_bytes,
                    "max_event_bytes": DEFAULT_HISTORY_WINDOW_POLICY.max_event_bytes,
                    "max_age_seconds": DEFAULT_HISTORY_WINDOW_POLICY.max_age_seconds,
                },
                "page_size": fixture.page_size,
                "page_samples": fixture.page_samples,
                "database_bytes": path.stat().st_size,
            },
            "environment": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "logical_cpu_count": os.cpu_count(),
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
            },
            "recording": {
                key: value
                for key, value in recording.items()
                if not key.endswith("_seconds") or key == "recording_seconds"
            },
            "readback": {
                key: value
                for key, value in readback.items()
                if not key.endswith("_seconds")
                or key.startswith("summary_")
            },
            "thresholds": None if case == "smoke" else {
                "summary_max_seconds": SUMMARY_MAX_SECONDS,
                "page_p95_max_seconds": PAGE_P95_MAX_SECONDS,
                "page_max_seconds": PAGE_MAX_SECONDS,
                "window_commit_max_seconds": WINDOW_COMMIT_MAX_SECONDS,
            },
        }
        assert recording["peak_pending_events"] <= 256
        assert recording["peak_pending_bytes"] <= 1_048_576
        if case == "release":
            assert recording["transaction_max_seconds"] < WINDOW_COMMIT_MAX_SECONDS
            assert readback["summary_cold_reader_seconds"] < SUMMARY_MAX_SECONDS
            assert readback["summary_warm_reader_seconds"] < SUMMARY_MAX_SECONDS
            assert readback["item_page_p95_seconds"] < PAGE_P95_MAX_SECONDS
            assert readback["item_page_max_seconds"] < PAGE_MAX_SECONDS
            assert readback["event_page_p95_seconds"] < PAGE_P95_MAX_SECONDS
            assert readback["event_page_max_seconds"] < PAGE_MAX_SECONDS
        return report
