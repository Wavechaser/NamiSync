"""M2-A8 evidence driver: inventory pairs through the real service composition.

Usage (project venv, from a folder two levels below the repository):

    python a8_pair.py seed ROOT FILES MIN_BYTES MAX_BYTES SEED
    python a8_pair.py run OUTDIR HDD_A HDD_B NVME_A NVME_B

``seed`` writes a deterministic tree under ROOT (which must not exist) and
prints its file count, bytes and listing digest. ``run`` opens one
``NamiSyncService`` with a fresh database pair in OUTDIR, admits two inventory
sessions back to back for the HDD pair and then for the NVMe pair, and writes
``run.json`` with each session's dispatcher timestamps and every scheduling-key
read. The reader is the service's own ``read_disk_scheduling_keys``, wrapped
only to time and log each call. The HDD_A tree is digested before and after to
show the run left it unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DIRS = 16


def listing_digest(root: Path) -> tuple[int, int, str]:
    """Count, bytes and SHA-256 of sorted (relative path, size, mtime_ns)."""

    rows = []
    for dirpath, _, names in os.walk(root):
        for name in names:
            path = Path(dirpath, name)
            stat = path.stat()
            rows.append(
                f"{path.relative_to(root).as_posix()}\t{stat.st_size}\t{stat.st_mtime_ns}"
            )
    rows.sort()
    total = sum(int(row.split("\t")[1]) for row in rows)
    return len(rows), total, hashlib.sha256("\n".join(rows).encode()).hexdigest()


def seed(root: Path, files: int, low: int, high: int, seed_value: int) -> None:
    if root.exists():
        raise SystemExit(f"{root} exists; seed writes only a new folder")
    rng = random.Random(seed_value)
    content = hashlib.sha256()
    total = 0
    for index in range(files):
        size = rng.randint(low, high)
        data = rng.randbytes(size)
        path = root / f"d{index % DIRS:02d}" / f"f{index:05d}.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        content.update(f"{path.relative_to(root).as_posix()}\t{size}\n".encode())
        content.update(hashlib.sha256(data).digest())
        total += size
    print(json.dumps({
        "root": str(root), "files": files, "bytes": total, "seed": seed_value,
        "size_range": [low, high], "content_sha256": content.hexdigest(),
    }, indent=1))


def run(outdir: Path, roots: dict[str, list[str]]) -> None:
    import namisync.interfaces.service as service_module
    from namisync.core.session import is_terminal

    real_reader = service_module.read_disk_scheduling_keys
    reads: list[dict[str, object]] = []
    checkpoints: dict[str, object] = {}
    reads_lock = threading.Lock()

    def timed_reader(checkpoint: object) -> frozenset:
        start = time.perf_counter_ns()
        keys = real_reader(checkpoint)
        elapsed = time.perf_counter_ns() - start
        mount = getattr(getattr(checkpoint, "binding", None), "selected_mount", None)
        with reads_lock:
            reads.append({
                "mount": mount, "keys": sorted(map(list, keys)),
                "microseconds": elapsed // 1000,
            })
            if mount is not None:
                checkpoints.setdefault(mount, checkpoint)
        return keys

    service_module.read_disk_scheduling_keys = timed_reader
    outdir.mkdir(parents=True, exist_ok=False)
    hdd_first = Path(roots["hdd"][0])
    before = listing_digest(hdd_first)
    report: dict[str, object] = {"hdd_first_listing_before": before, "pairs": {}}

    service = service_module.NamiSyncService(outdir / "ledger.db", outdir / "history.db")
    try:
        service.initialize_database_contracts()
        dispatcher = service._dispatcher
        for pair, pair_roots in roots.items():
            started = [service.start_inventory(root_path=root) for root in pair_roots]
            records, times = {}, {}
            for root, session in zip(pair_roots, started):
                while (record := dispatcher.get(session.session_id)).result is None:
                    time.sleep(0.01)
                assert is_terminal(record.state)
                details = service.get_inventory_details(session.request_id)
                stored = times[root] = record.stored
                records[root] = {
                    "admission_order": stored.admission_order,
                    "resources": [str(resource) for resource in stored.resources],
                    "created_at": stored.created_at.isoformat(),
                    "started_at": stored.started_at.isoformat(),
                    "ended_at": stored.ended_at.isoformat(),
                    "state": stored.state.value,
                    "result_status": None if stored.result is None else stored.result.status.value,
                    "detail_state": details.state,
                    "detail": details.detail,
                    "observed_count": details.observed_count,
                    "missing_count": details.missing_count,
                    "complete": details.complete,
                    "warnings": len(details.warnings),
                }
                service.close_session(session.session_id)
            first, second = (times[root] for root in pair_roots)
            report["pairs"][pair] = {
                "sessions": records,
                "overlapped": second.started_at < first.ended_at
                and first.started_at < second.ended_at,
                "second_waited_for_first": second.started_at >= first.ended_at,
            }
    finally:
        service.close()
        service_module.read_disk_scheduling_keys = real_reader

    report["in_session_reads"] = reads
    repeat: dict[str, object] = {}
    for mount, checkpoint in checkpoints.items():
        samples = []
        for _ in range(20):
            start = time.perf_counter_ns()
            keys = real_reader(checkpoint)
            samples.append((time.perf_counter_ns() - start) // 1000)
        samples.sort()
        repeat[mount] = {
            "keys": sorted(map(list, keys)), "reads": len(samples),
            "median_us": samples[len(samples) // 2], "max_us": samples[-1],
        }
    report["repeat_reads"] = repeat
    report["hdd_first_listing_after"] = listing_digest(hdd_first)
    report["hdd_first_unchanged"] = report["hdd_first_listing_after"] == before
    (outdir / "run.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


def main(argv: list[str]) -> None:
    if argv[:1] == ["seed"] and len(argv) == 6:
        seed(Path(argv[1]), int(argv[2]), int(argv[3]), int(argv[4]), int(argv[5]))
    elif argv[:1] == ["run"] and len(argv) == 6:
        run(Path(argv[1]), {"hdd": argv[2:4], "nvme": argv[4:6]})
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
