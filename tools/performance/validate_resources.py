"""SH-G-15 v1 validator: frozen budgets and statistics over collected runs.

Usage: python -m tools.performance.validate_resources OUT_DIR [--json VERDICT]

Budgets are whole-Job private bytes (host plus every WebView2 descendant).
Changing a budget, statistic or schedule is a declaration change: PERFORMANCE
and INTERFACES must change first, and earlier evidence does not carry over.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

MIB = 1024 * 1024

BUDGETS = {
    "startup_settled_mib": 450.0,
    "startup_peak_mib": 600.0,
    "startup_idle_cpu_percent": 1.0,
    "work_peak_mib": 2048.0,
    "closed_settled_mib": 1024.0,
    "soak_slope_mib_per_cycle": 0.2,
    "soak_shift_mib": 20.0,
    "soak_handle_slope_per_cycle": 1.0,
    "soak_gui_object_growth": 10.0,
    "idle_slope_mib_per_10min": 2.0,
}

# Statistic span (seconds at the end of each named window) by window-name suffix.
SPANS = {"startup-idle": 60, "initial-idle": 30, "final-idle": 30, "-closed": 10, "plan-open": 15,
         "task-executed-open": 15, "long-idle-open": 3000}
MAX_GAP_SECONDS = 3.0
MIN_COVERAGE = 0.8
SOAK_FIRST, SOAK_LAST = 21, 100

EXPECTED_RUNS = {
    **{f"startup-{i:02}": "startup" for i in (1, 2, 3)},
    **{f"startup-cdp-{i:02}": "startup" for i in (1, 2, 3)},
    **{f"soak-{i:02}": "soak" for i in (1, 2, 3)},
    **{f"scale-{k}-{i:02}": "scale" for i in (1, 2, 3) for k in ("10k", "100k")},
    "payload-01": "payload",
    "idle-open-01": "idle_open",
}


def slope(xs: list[float], ys: list[float]) -> float:
    """Ordinary least-squares slope."""

    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def span_for(name: str) -> float:
    for suffix, seconds in SPANS.items():
        if name.endswith(suffix):
            return seconds
    raise ValueError(f"no statistic span for window {name}")


def window_samples(samples: list[dict], window: dict) -> tuple[list[dict], str | None]:
    """Complete samples in the statistic span, or a fidelity failure reason."""

    span = span_for(window["name"])
    if window["end"] - window["start"] < span - 0.5:
        return [], f"window {window['name']} shorter than its {span} s span"
    low = window["end"] - span
    chosen = [s for s in samples if s["complete"] and low <= s["t"] <= window["end"]]
    if len(chosen) < MIN_COVERAGE * span:
        return chosen, f"window {window['name']} has {len(chosen)} complete samples for {span} s"
    edges = [low] + [s["t"] for s in chosen] + [window["end"]]
    gap = max(b - a for a, b in zip(edges, edges[1:]))
    if gap > MAX_GAP_SECONDS:
        return chosen, f"window {window['name']} has a {gap:.2f} s sample gap"
    return chosen, None


def median_of(chosen: list[dict], key) -> float:
    return statistics.median(key(sample) for sample in chosen)


def private_mib(sample: dict) -> float:
    return sample["private"] / MIB


def handles(sample: dict) -> float:
    return sum(p["handles"] for p in sample["procs"])


def gui_objects(sample: dict) -> float:
    return sum(p["gdi"] + p["user"] for p in sample["procs"])


def role_mib(sample: dict, role: str) -> float:
    def group(name: str) -> str:
        if name == "host":
            return "host"
        if name == "webview2-renderer":
            return "renderer"
        if name == "webview2-gpu-process":
            return "gpu"
        return "other"
    return sum(p["private"] for p in sample["procs"] if group(p["role"]) == role) / MIB


def idle_cpu_percent(chosen: list[dict]) -> float:
    first, last = chosen[0], chosen[-1]
    before = {(p["pid"], p["role"]): p["cpu_100ns"] for p in first["procs"]}
    used = sum(p["cpu_100ns"] - before[(p["pid"], p["role"])] for p in last["procs"] if (p["pid"], p["role"]) in before)
    return 100.0 * (used / 1e7) / (last["t"] - first["t"])


def load(run_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    samples = [json.loads(line) for line in (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()]
    return result, events, samples


def evaluate_run(name: str, profile: str, result: dict, events: list[dict], samples: list[dict]) -> dict:
    checks: dict[str, dict] = {}
    invalid: list[str] = []
    metrics: dict[str, object] = {}

    def check(key: str, value: float, budget_key: str) -> None:
        checks[key] = {"value": round(value, 3), "budget": BUDGETS[budget_key], "pass": value <= BUDGETS[budget_key]}

    close = result.get("close") or {}
    if not result.get("complete"):
        invalid.append(f"collection incomplete: {result.get('error')}")
    if close.get("exit_code") != 0 or close.get("remaining_pids"):
        invalid.append(f"abnormal close: {close}")
    windows = {e["name"]: e for e in events if e["kind"] == "window"}
    stats: dict[str, list[dict]] = {}
    for window in windows.values():
        chosen, problem = window_samples(samples, window)
        if problem:
            invalid.append(problem)
        stats[window["name"]] = chosen
    close_start = next((e["t"] for e in events if e["kind"] == "phase" and e["phase"] == "close"), float("inf"))
    complete = [s for s in samples if s["complete"] and s["t"] < close_start]
    if not complete:
        invalid.append("no complete samples")
        return {"name": name, "profile": profile, "valid": False, "invalid": invalid, "checks": checks, "metrics": metrics}
    peak = max(private_mib(s) for s in complete)
    metrics["sampled_peak_mib"] = round(peak, 3)
    metrics["windows"] = {
        key: {"private_mib": round(median_of(chosen, private_mib), 3),
              **{role: round(median_of(chosen, lambda s, r=role: role_mib(s, r)), 3) for role in ("host", "renderer", "gpu", "other")},
              "handles": median_of(chosen, handles), "gui_objects": median_of(chosen, gui_objects)}
        for key, chosen in stats.items() if chosen}

    def settled(window_name: str) -> float | None:
        chosen = stats.get(window_name)
        return median_of(chosen, private_mib) if chosen else None

    if profile == "startup":
        if "startup-idle" not in stats:
            invalid.append("missing startup-idle window")
        else:
            metrics["idle_cpu_percent"] = round(idle_cpu_percent(stats["startup-idle"]), 4)
            if not name.startswith("startup-cdp"):
                check("startup_settled_mib", settled("startup-idle"), "startup_settled_mib")
                check("startup_peak_mib", peak, "startup_peak_mib")
                check("startup_idle_cpu_percent", metrics["idle_cpu_percent"], "startup_idle_cpu_percent")
        return {"name": name, "profile": profile, "valid": not invalid, "invalid": invalid, "checks": checks, "metrics": metrics}

    check("work_peak_mib", peak, "work_peak_mib")
    closed = [key for key in stats if key.endswith("-closed") or key == "final-idle"]
    if "final-idle" not in stats:
        invalid.append("missing final-idle window")
    if closed:
        check("closed_settled_max_mib", max(settled(key) for key in closed), "closed_settled_mib")

    if profile == "soak":
        cycles = list(range(SOAK_FIRST, SOAK_LAST + 1))
        keys = [f"cycle-{c:03}-closed" for c in cycles]
        missing = [k for k in keys if not stats.get(k)]
        if missing:
            invalid.append(f"missing soak windows: {missing[:5]}")
        else:
            series = [settled(k) for k in keys]
            handle_series = [median_of(stats[k], handles) for k in keys]
            gui_series = [median_of(stats[k], gui_objects) for k in keys]
            metrics["post_close_series_mib"] = [round(v, 3) for v in series]
            check("soak_slope_mib_per_cycle", slope(cycles, series), "soak_slope_mib_per_cycle")
            check("soak_shift_mib", statistics.median(series[-20:]) - statistics.median(series[:20]), "soak_shift_mib")
            check("soak_handle_slope_per_cycle", slope(cycles, handle_series), "soak_handle_slope_per_cycle")
            check("soak_gui_object_growth", statistics.median(gui_series[-20:]) - statistics.median(gui_series[:20]),
                  "soak_gui_object_growth")
    if profile == "idle_open":
        chosen = stats.get("long-idle-open")
        if chosen:
            xs = [s["t"] / 600.0 for s in chosen]
            check("idle_slope_mib_per_10min", slope(xs, [private_mib(s) for s in chosen]), "idle_slope_mib_per_10min")
        else:
            invalid.append("missing long-idle-open window")
    return {"name": name, "profile": profile, "valid": not invalid, "invalid": invalid, "checks": checks, "metrics": metrics}


def validate(out: Path) -> dict:
    runs = []
    missing = []
    for name, profile in EXPECTED_RUNS.items():
        run_dir = out / "runs" / name
        if not (run_dir / "result.json").exists():
            missing.append(name)
            continue
        runs.append(evaluate_run(name, profile, *load(run_dir)))
    startup = {r["name"]: r["metrics"]["windows"].get("startup-idle", {}).get("private_mib")
               for r in runs if r["profile"] == "startup" and r["valid"]}
    plain = [v for k, v in startup.items() if not k.startswith("startup-cdp") and v is not None]
    driven = [v for k, v in startup.items() if k.startswith("startup-cdp") and v is not None]
    overhead = round(statistics.median(driven) - statistics.median(plain), 3) if plain and driven else None
    passed = not missing and all(r["valid"] and all(c["pass"] for c in r["checks"].values()) for r in runs)
    return {"declaration": "SH-G-15 v1", "budgets": BUDGETS, "missing_runs": missing,
            "devtools_overhead_settled_mib": overhead, "verdict": "PASS" if passed else "FAIL", "runs": runs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    verdict = validate(args.out)
    text = json.dumps(verdict, indent=1)
    if args.json:
        if args.json.exists():
            raise SystemExit(f"{args.json} exists; choose a new path")
        args.json.write_text(text, encoding="utf-8")
    for run in verdict["runs"]:
        failed = [k for k, c in run["checks"].items() if not c["pass"]]
        print(f"{run['name']:<16} valid={run['valid']} failed={failed} invalid={run['invalid'][:2]}")
    print("missing:", verdict["missing_runs"], "devtools overhead MiB:", verdict["devtools_overhead_settled_mib"])
    print("VERDICT:", verdict["verdict"])
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
