from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from namisync.core.planning import OperationKind, selection_digest
from namisync.core.recording import HostCommand
from namisync.core.recording import SyncRunCommand
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import LedgerRecorder
from namisync.db.writer import RecordingBusyError

from _db_fixtures import (
    FakeClock,
    NOW,
    attestation,
    file_stat,
    operation,
    plan,
    setup_recorder,
)


_HOLDER = r"""
import sqlite3
import sys
import time
from pathlib import Path

database, ready, release = map(Path, sys.argv[1:])
connection = sqlite3.connect(database, isolation_level=None)
connection.execute("PRAGMA busy_timeout = 50")
connection.execute("BEGIN IMMEDIATE")
ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 5
while not release.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
connection.rollback()
connection.close()
"""


def _wait_for(path: Path) -> None:
    deadline = time.monotonic() + 5
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"subprocess did not create {path}")
        time.sleep(0.01)


def test_two_parallel_runs_record_completely_through_one_writer(tmp_path: Path) -> None:
    def run_plan(prefix: str, identity_offset: int):
        pairs = []
        for index in range(40):
            source = file_stat(identity_index=identity_offset + index)
            target = file_stat(
                identity_index=identity_offset + 1_000 + index,
                volume_serial="target-serial",
            )
            item = operation(
                OperationKind.COPY,
                source_path=f"{prefix}\\file-{index}.bin",
                target_path=f"{prefix}\\file-{index}.bin",
                source=source,
                intended=target,
            )
            pairs.append((item, target))
        return plan(tuple(item for item, _ in pairs)), tuple(pairs)

    first_plan, first_pairs = run_plan("first", 1)
    second_plan, second_pairs = run_plan("second", 100)
    setup = setup_recorder(tmp_path / "ledger.db", first_plan)
    second_selection = frozenset(item.op_id for item, _ in second_pairs)
    second = setup.recorder.begin_sync_run(
        SyncRunCommand(
            "b" * 32,
            setup.host_id,
            setup.mapping_id,
            setup.source_location_id,
            setup.target_location_id,
            second_plan,
            second_selection,
            selection_digest(second_selection),
            NOW,
        )
    )
    errors: list[BaseException] = []

    def record(bound, pairs) -> None:
        try:
            for item, target in pairs:
                bound.record_copied(item.op_id, attestation(target))
        except BaseException as error:
            errors.append(error)

    threads = [
        threading.Thread(target=record, args=(setup.run, first_pairs)),
        threading.Thread(target=record, args=(second, second_pairs)),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
        assert errors == []

        connection = connect_ledger_reader(setup.recorder.path)
        try:
            assert connection.execute("SELECT count(*) FROM operations").fetchone()[0] == 80
            assert connection.execute(
                "SELECT count(*) FROM inventory WHERE location_id = ?",
                (setup.target_location_id,),
            ).fetchone()[0] == 80
        finally:
            connection.close()
    finally:
        setup.recorder.close()


def test_cross_process_contention_retries_then_records(tmp_path: Path) -> None:
    database = tmp_path / "ledger.db"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    recorder = LedgerRecorder(
        database,
        clock=FakeClock(),
        busy_timeout_ms=5,
        retry_timeout_seconds=1,
        retry_interval_seconds=0.01,
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(database), str(ready), str(release)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for(ready)
        result: list[int] = []
        error: list[BaseException] = []

        def record() -> None:
            try:
                result.append(
                    recorder.ensure_host(HostCommand("host", "Host", NOW))
                )
            except BaseException as caught:
                error.append(caught)

        worker = threading.Thread(target=record)
        worker.start()
        time.sleep(0.05)
        release.write_text("release", encoding="utf-8")
        worker.join(timeout=5)
        stdout, stderr = holder.communicate(timeout=5)

        assert holder.returncode == 0, (stdout, stderr)
        assert not worker.is_alive()
        assert error == []
        assert result == [1]
    finally:
        release.touch(exist_ok=True)
        if holder.poll() is None:
            holder.terminate()
            holder.wait(timeout=5)
        recorder.close()


def test_cross_process_contention_surfaces_final_failure(tmp_path: Path) -> None:
    database = tmp_path / "ledger.db"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    recorder = LedgerRecorder(
        database,
        clock=FakeClock(),
        busy_timeout_ms=5,
        retry_timeout_seconds=0.05,
        retry_interval_seconds=0.005,
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(database), str(ready), str(release)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for(ready)
        with pytest.raises(RecordingBusyError):
            recorder.ensure_host(HostCommand("host", "Host", NOW))
    finally:
        release.touch(exist_ok=True)
        holder.communicate(timeout=5)
        recorder.close()
