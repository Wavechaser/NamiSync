r"""Opt-in release benchmark for bounded history recording and readback.

Run from the repository root with::

    .\.venv\Scripts\python.exe tests\history_benchmark.py

The script intentionally is not named ``test_*.py`` so the million-item
fixture is excluded from the normal pytest suite.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from namisync.core.events import (  # noqa: E402
    Envelope,
    ItemOutcome,
    PhaseChanged,
    CORE_EVENT_SCHEMA_VERSION,
    StateChanged,
)
from namisync.core.evidence import Outcome, RecordingStatus  # noqa: E402
from namisync.core.session import (  # noqa: E402
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.history import (  # noqa: E402
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

SUMMARY_MAX_SECONDS = 3.0
PAGE_P95_MAX_SECONDS = 0.5
PAGE_MAX_SECONDS = 1.0
WINDOW_COMMIT_MAX_SECONDS = 5.0

NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _run_sizes() -> tuple[int, ...]:
    remaining = TOTAL_ITEMS - LARGE_RUN_ITEMS
    base, extra = divmod(remaining, RUN_COUNT - 1)
    sizes = (LARGE_RUN_ITEMS,) + tuple(
        base + (1 if index < extra else 0)
        for index in range(RUN_COUNT - 1)
    )
    assert len(sizes) == RUN_COUNT
    assert sum(sizes) == TOTAL_ITEMS
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


def _record_fixture(path: Path) -> dict[str, object]:
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
        for run_index, item_count in enumerate(_run_sizes()):
            record = SessionRecord(
                session_id=SessionId(f"benchmark-session-{run_index:02d}"),
                kind="sync",
                state=SessionState.PENDING,
                resources=(),
                payload=b"benchmark",
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
                            item_id=f"operation-{item_index:06d}",
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
        "transaction_p50_ms": statistics.median(transaction_seconds) * 1_000,
        "transaction_p95_ms": _percentile(transaction_seconds, 95) * 1_000,
        "transaction_max_ms": max(transaction_seconds) * 1_000,
        "peak_pending_events": peak_pending_count,
        "peak_pending_bytes": peak_pending_bytes,
        "transaction_max_seconds": max(transaction_seconds),
    }


def _measure_readback(path: Path) -> dict[str, object]:
    with HistoryRepository(path) as repository:
        summaries, cold_summary_seconds = _timed(
            lambda: repository.list_summaries(RUN_COUNT)
        )
        _, warm_summary_seconds = _timed(
            lambda: repository.list_summaries(RUN_COUNT)
        )
        assert len(summaries) == RUN_COUNT
        assert sum(summary.item_count for summary in summaries) == TOTAL_ITEMS
        assert all(summary.finalized for summary in summaries)
        assert all(summary.audit is RecordingStatus.OK for summary in summaries)

    large_run = "benchmark-run-00"
    with HistoryRepository(path) as repository:
        _, item_cold_seconds = _timed(
            lambda: repository.get_item_page(
                large_run,
                through_order=LARGE_RUN_ITEMS,
                limit=PAGE_SIZE,
            )
        )
    with HistoryRepository(path) as repository:
        _, event_cold_seconds = _timed(
            lambda: repository.get_event_page(
                large_run,
                through_seq=LARGE_RUN_ITEMS + 2,
                limit=PAGE_SIZE,
            )
        )

    with HistoryRepository(path) as repository:
        repository.get_item_page(
            large_run,
            through_order=LARGE_RUN_ITEMS,
            limit=PAGE_SIZE,
        )
        repository.get_event_page(
            large_run,
            through_seq=LARGE_RUN_ITEMS + 2,
            limit=PAGE_SIZE,
        )
        item_page_seconds: list[float] = []
        event_page_seconds: list[float] = []
        for sample in range(PAGE_SAMPLE_COUNT):
            item_after = sample * LARGE_RUN_ITEMS // PAGE_SAMPLE_COUNT
            item_page, elapsed = _timed(
                lambda item_after=item_after: repository.get_item_page(
                    large_run,
                    after_order=item_after,
                    through_order=LARGE_RUN_ITEMS,
                    limit=PAGE_SIZE,
                )
            )
            assert 1 <= len(item_page.items) <= PAGE_SIZE
            item_page_seconds.append(elapsed)

            event_after = sample * (LARGE_RUN_ITEMS + 2) // PAGE_SAMPLE_COUNT
            event_page, elapsed = _timed(
                lambda event_after=event_after: repository.get_event_page(
                    large_run,
                    after_seq=event_after,
                    through_seq=LARGE_RUN_ITEMS + 2,
                    limit=PAGE_SIZE,
                )
            )
            assert 1 <= len(event_page.events) <= PAGE_SIZE
            event_page_seconds.append(elapsed)

    return {
        "summary_cold_reader_seconds": cold_summary_seconds,
        "summary_warm_reader_seconds": warm_summary_seconds,
        "item_page_cold_reader_ms": item_cold_seconds * 1_000,
        "item_page_p50_ms": statistics.median(item_page_seconds) * 1_000,
        "item_page_p95_ms": _percentile(item_page_seconds, 95) * 1_000,
        "item_page_max_ms": max(item_page_seconds) * 1_000,
        "item_page_p95_seconds": _percentile(item_page_seconds, 95),
        "item_page_max_seconds": max(item_page_seconds),
        "event_page_cold_reader_ms": event_cold_seconds * 1_000,
        "event_page_p50_ms": statistics.median(event_page_seconds) * 1_000,
        "event_page_p95_ms": _percentile(event_page_seconds, 95) * 1_000,
        "event_page_max_ms": max(event_page_seconds) * 1_000,
        "event_page_p95_seconds": _percentile(event_page_seconds, 95),
        "event_page_max_seconds": max(event_page_seconds),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namisync-history-benchmark-") as temp:
        path = Path(temp) / "history.db"
        recording = _record_fixture(path)
        readback = _measure_readback(path)
        report = {
            "fixture": {
                "runs": RUN_COUNT,
                "items": TOTAL_ITEMS,
                "largest_run_items": LARGE_RUN_ITEMS,
                "window_policy": {
                    "max_events": DEFAULT_HISTORY_WINDOW_POLICY.max_events,
                    "max_bytes": DEFAULT_HISTORY_WINDOW_POLICY.max_bytes,
                    "max_event_bytes": DEFAULT_HISTORY_WINDOW_POLICY.max_event_bytes,
                    "max_age_seconds": DEFAULT_HISTORY_WINDOW_POLICY.max_age_seconds,
                },
                "page_samples": PAGE_SAMPLE_COUNT,
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
            "thresholds": {
                "summary_max_seconds": SUMMARY_MAX_SECONDS,
                "page_p95_max_seconds": PAGE_P95_MAX_SECONDS,
                "page_max_seconds": PAGE_MAX_SECONDS,
                "window_commit_max_seconds": WINDOW_COMMIT_MAX_SECONDS,
            },
        }
        print(json.dumps(report, indent=2, sort_keys=True))

        assert recording["peak_pending_events"] <= 256
        assert recording["peak_pending_bytes"] <= 1_048_576
        assert recording["transaction_max_seconds"] < WINDOW_COMMIT_MAX_SECONDS
        assert readback["summary_cold_reader_seconds"] < SUMMARY_MAX_SECONDS
        assert readback["summary_warm_reader_seconds"] < SUMMARY_MAX_SECONDS
        assert readback["item_page_p95_seconds"] < PAGE_P95_MAX_SECONDS
        assert readback["item_page_max_seconds"] < PAGE_MAX_SECONDS
        assert readback["event_page_p95_seconds"] < PAGE_P95_MAX_SECONDS
        assert readback["event_page_max_seconds"] < PAGE_MAX_SECONDS
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
