"""BR-G-42 History and bridge-event acceptance collection and validation.

``collect`` runs the predeclared collection from a clean checkout: five fresh
children each of the History release case and the installed bridge-event case.
It never retries; a failed child stays in the collection. ``validate`` is the
separate checker: it recomputes the statistics from the child reports and
compares them with the HISTORY and BRIDGE limits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

_REPOSITORY = Path(__file__).resolve().parents[2]
CHILDREN = 5
RUNTIME_PREFIX = "3.13.17 "
UNITS = (("history", "release"), ("bridge-event", "installed"))
# HISTORY.md: 50-run summary at most 3 s; 256-row pages 500 ms p95 / 1 s maximum.
HISTORY_LIMITS = {"summary_s": 3.0, "page_p95_ms": 500.0, "page_max_ms": 1000.0}
# BRIDGE.md: reliable/terminal 100 ms p95 / 250 ms max; progress 1 s / 2 s.
EVENT_LIMITS = {"reliable_and_terminal": (100.0, 250.0), "progress": (1000.0, 2000.0)}
_EVENT_FLAGS = ("passed", "measurement_valid", "runtime_profile_match", "archive_scope_clean")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPOSITORY, capture_output=True, text=True,
        check=True, timeout=30,
    ).stdout.strip()


def collect(output: Path, children: int = CHILDREN) -> int:
    if _git("status", "--porcelain"):
        raise SystemExit("refusing collection: the working tree is not clean")
    output.mkdir(parents=True, exist_ok=False)
    index = {
        "schema": "namisync-br-g-42-collection-v1",
        "revision": _git("rev-parse", "HEAD"),
        "children": children,
        "python": sys.version,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "runs": [],
    }
    index_path = output / "index.json"
    for family, case in UNITS:
        for child in range(1, children + 1):
            report = output / family / f"{case}-{child:02d}.json"
            report.parent.mkdir(exist_ok=True)
            command = [
                sys.executable, "-m", "tools", "performance", family, case,
                "--json", str(report),
            ]
            started = time.monotonic()
            with report.with_suffix(".log").open("wb") as log:
                exit_code = subprocess.run(
                    command, cwd=_REPOSITORY, stdout=log, stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
            index["runs"].append({
                "family": family, "case": case, "child": child,
                "exit_code": exit_code, "report": f"{family}/{report.name}",
                "seconds": round(time.monotonic() - started, 1),
            })
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
            print(f"{family} {case} {child} exit={exit_code}", flush=True)
    index["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return 0


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _reports(output: Path, index: dict, family: str, case: str, problems: list[str]) -> list[dict]:
    reports = []
    runs = [run for run in index["runs"] if run["family"] == family and run["case"] == case]
    if len(runs) != CHILDREN:
        problems.append(f"{len(runs)} of {CHILDREN} children recorded")
    for run in runs:
        path = output / run["report"]
        if run["exit_code"] != 0 or not path.is_file():
            problems.append(f"child {run['child']} exit {run['exit_code']}")
            continue
        raw = path.read_bytes()
        report = json.loads(raw)
        if report.get("status") != "complete" or report.get("family") != family or report.get("case") != case:
            problems.append(f"child {run['child']} report incomplete or mismatched")
            continue
        environment = report["environment"]
        if environment["driver_source"] != {"dirty": False, "revision": index["revision"]}:
            problems.append(f"child {run['child']} source {environment['driver_source']}")
        if not environment["python"].startswith(RUNTIME_PREFIX):
            problems.append(f"child {run['child']} runtime {environment['python']}")
        report["_sha256"] = hashlib.sha256(raw).hexdigest()
        reports.append(report)
    return reports


def _history(reports: list[dict], problems: list[str]) -> dict:
    summary, items, events = [], [], []
    for report in reports:
        observation = report["observation"]
        if observation.get("release_gates_applied") is not True:
            problems.append("release gates not applied")
        readback = observation["readback"]
        summary += [readback["summary_cold_reader_seconds"], readback["summary_warm_reader_seconds"]]
        items += readback["item_page_samples_ms"]
        events += readback["event_page_samples_ms"]
    if not reports:
        return {}
    result = {
        "summary_max_s": max(summary),
        "item_page_samples": len(items), "event_page_samples": len(events),
        "item_page_p95_ms": _p95(items), "item_page_max_ms": max(items),
        "event_page_p95_ms": _p95(events), "event_page_max_ms": max(events),
    }
    if result["summary_max_s"] > HISTORY_LIMITS["summary_s"]:
        problems.append("summary exceeds limit")
    for page in ("item", "event"):
        if result[f"{page}_page_p95_ms"] > HISTORY_LIMITS["page_p95_ms"]:
            problems.append(f"{page} page p95 exceeds limit")
        if result[f"{page}_page_max_ms"] > HISTORY_LIMITS["page_max_ms"]:
            problems.append(f"{page} page maximum exceeds limit")
    return result


def _event(reports: list[dict], revision: str, problems: list[str]) -> dict:
    result: dict[str, object] = {}
    for report in reports:
        observation = report["observation"]
        for flag in _EVENT_FLAGS:
            if observation.get(flag) is not True:
                problems.append(f"{flag} is not true")
        if observation.get("tested_commit") != revision:
            problems.append(f"tested commit {observation.get('tested_commit')}")
    for stream, (p95_limit, maximum_limit) in EVENT_LIMITS.items():
        rows = [report["observation"][stream] for report in reports]
        if not rows:
            continue
        result[stream] = {
            "events": sum(row["count"] for row in rows),
            "worst_child_p95_ms": max(row["p95_ms"] for row in rows),
            "maximum_ms": max(row["maximum_ms"] for row in rows),
        }
        if result[stream]["worst_child_p95_ms"] > p95_limit or result[stream]["maximum_ms"] > maximum_limit:
            problems.append(f"{stream} exceeds limit")
    return result


def validate(output: Path) -> dict:
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    rows = {}
    for family, case in UNITS:
        problems: list[str] = []
        reports = _reports(output, index, family, case, problems)
        if family == "history":
            result = _history(reports, problems)
        else:
            result = _event(reports, index["revision"], problems)
        rows[f"{family}/{case}"] = {
            **result,
            "children": len(reports),
            "report_sha256": [report["_sha256"] for report in reports],
            "passed": not problems,
            "problems": problems,
        }
    complete = "finished" in index
    return {
        "schema": "namisync-br-g-42-validation-v1",
        "revision": index["revision"],
        "python": index.get("python"),
        "complete": complete,
        "passed": complete and all(row["passed"] for row in rows.values()),
        "metrics": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.performance.br_g_42")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("collect").add_argument("output", type=Path)
    commands.add_parser("validate").add_argument("output", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == "collect":
        return collect(arguments.output)
    verdict = validate(arguments.output)
    (arguments.output / "validation.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    for name, row in verdict["metrics"].items():
        print(f"{'PASS' if row['passed'] else 'FAIL'} {name} {'; '.join(row['problems'])}")
    print(f"passed={verdict['passed']} complete={verdict['complete']}")
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
