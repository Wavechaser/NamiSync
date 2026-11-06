"""SH-G-15 v1 validator statistics and verdict rules on synthetic observations."""

from __future__ import annotations

import pytest

from tools.performance import validate_resources as v

MIB = v.MIB


def sample(t: float, private_mib: float, *, handles: int = 1000, gui: int = 50, cpu: int = 0,
           complete: bool = True) -> dict:
    return {"t": t, "complete": complete, "private": int(private_mib * MIB), "procs": [
        {"pid": 1, "role": "host", "private": int(private_mib * MIB), "handles": handles, "gdi": gui, "user": 0,
         "cpu_100ns": cpu}]}


def windowed(names_and_values: list[tuple[str, float, float]], *, leak_handles: float = 0.0):
    """Consecutive windows; each value is the flat private MiB during its window."""

    events, samples, t = [], [], 0.0
    for index, (name, seconds, value) in enumerate(names_and_values):
        start = t
        while t <= start + seconds:
            samples.append(sample(t, value, handles=int(1000 + leak_handles * index)))
            t += 1.0
        events.append({"kind": "window", "name": name, "start": start, "end": t - 1.0})
    events.append({"kind": "phase", "phase": "close", "t": t})
    return events, samples


OK = {"complete": True, "close": {"exit_code": 0, "remaining_pids": []}}


def test_slope_is_least_squares():
    assert v.slope([1, 2, 3, 4], [10, 12, 14, 16]) == pytest.approx(2.0)


def test_window_rejects_gap_and_short_coverage():
    window = {"name": "final-idle", "start": 0.0, "end": 40.0}
    gap = [sample(t, 300) for t in range(0, 41) if not 20 <= t <= 24]
    assert "gap" in v.window_samples(gap, window)[1]
    sparse = [sample(t, 300, complete=t % 3 == 0) for t in range(0, 41)]
    assert "complete samples" in v.window_samples(sparse, window)[1]
    assert v.window_samples([sample(t, 300) for t in range(0, 41)], window)[1] is None


def test_startup_budgets_and_cdp_runs_are_diagnostic():
    events, samples = windowed([("startup-idle", 180, 451.0)])
    plain = v.evaluate_run("startup-01", "startup", OK, events, samples)
    assert plain["valid"] and not plain["checks"]["startup_settled_mib"]["pass"]
    driven = v.evaluate_run("startup-cdp-01", "startup", OK, events, samples)
    assert driven["valid"] and driven["checks"] == {}


def soak_windows(per_cycle: float):
    windows = [("initial-idle", 60, 400.0)]
    windows += [(f"cycle-{c:03}-closed", 15, 600.0 + per_cycle * c) for c in range(1, 101)]
    return windows + [("final-idle", 120, 600.0 + per_cycle * 100)]


def test_soak_flat_passes_and_leak_fails():
    flat = v.evaluate_run("soak-01", "soak", OK, *windowed(soak_windows(0.0)))
    assert flat["valid"] and all(c["pass"] for c in flat["checks"].values())
    leaking = v.evaluate_run("soak-01", "soak", OK, *windowed(soak_windows(0.5)))
    assert not leaking["checks"]["soak_slope_mib_per_cycle"]["pass"]
    assert not leaking["checks"]["soak_shift_mib"]["pass"]
    handles = v.evaluate_run("soak-01", "soak", OK, *windowed(soak_windows(0.0), leak_handles=2.0))
    assert not handles["checks"]["soak_handle_slope_per_cycle"]["pass"]


def test_incomplete_or_abnormal_runs_are_invalid():
    events, samples = windowed([("startup-idle", 180, 300.0)])
    failed = v.evaluate_run("startup-01", "startup", {"complete": False, "error": "x", "close": OK["close"]},
                            events, samples)
    assert not failed["valid"]
    killed = v.evaluate_run("startup-01", "startup", {"complete": True, "close": {"exit_code": 1}}, events, samples)
    assert not killed["valid"]


def test_missing_runs_fail_the_verdict(tmp_path):
    (tmp_path / "runs").mkdir()
    verdict = v.validate(tmp_path)
    assert verdict["verdict"] == "FAIL" and len(verdict["missing_runs"]) == len(v.EXPECTED_RUNS)
