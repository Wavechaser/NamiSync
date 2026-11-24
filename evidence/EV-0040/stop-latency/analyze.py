"""Summarize raw sample JSON files: python analyze.py samples.json [...]"""
import json
import math
import sys
from collections import defaultdict

FIELDS = ["scanner_raise_ms", "custody_release_ms", "terminal_event_ms",
          "final_record_ms", "cancel_call_ms", "max_checkpoint_gap_ms"]


def pct(xs, p):  # nearest-rank
    xs = sorted(xs)
    return xs[max(0, math.ceil(p / 100 * len(xs)) - 1)]


for path in sys.argv[1:]:
    d = json.load(open(path))
    groups = defaultdict(list)
    for s in d["samples"]:
        groups[(s["case"], s.get("tag"))].append(s)
    print(f"## {path}")
    for (case, tag), ss in groups.items():
        ok = [s for s in ss if s.get("final_state") == "canceled" and s.get("held_when_armed")
              and not s.get("prober_error") and s.get("scanner_raise_ms") is not None and s["scanner_raise_ms"] >= 0]
        print(f"{case} [{tag}] n={len(ss)} valid_canceled={len(ok)} "
              f"states={sorted({str(s.get('final_state')) for s in ss})} "
              f"held_ok={sum(1 for s in ss if s.get('held_when_armed'))}")
        for f in FIELDS:
            xs = [s[f] for s in ok if s.get(f) is not None]
            if xs:
                print(f"   {f:24s} p50={pct(xs,50):9.2f} p95={pct(xs,95):9.2f} max={max(xs):9.2f} min={min(xs):9.2f}")
        cps = [s["checkpoints_at_cancel"] for s in ok]
        if cps:
            print(f"   checkpoints_at_cancel   min={min(cps)} max={max(cps)}")
