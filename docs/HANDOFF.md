# Latest session — rebuilt-package resource schedule, 2026-11-07/08

## Delivered changes

Documentation only. CHANGELOG nits fixed in `733f0cb1`: renderer memory and copy
path work got its own task, and the measurement task's heading and date range
were restored. A package rebuilt from clean `733f0cb1` then ran the full
17-run resource schedule overnight; the slow close and the execution-peak rise
were then investigated with source controls. PERFORMANCE ("Full resource
schedule on `733f0cb1`"), M1_PLAN and CHANGELOG record the results. No product, test or tool
source changed.

## Results

- All 17 runs completed with exact mirrors and exit 0 (`full.log` ends `exit 0`).
- Settled memory after close: 10k 527–540 MiB (was 826–842); 100k 689–793 MiB
  (was 1,999–2,126); soak 510–536 MiB per cycle; open-task idle 560 MiB (was 837).
- Execution peaks rose: 10k 1,101–1,224 MiB, 100k 3,298–3,674 MiB (was
  2,365–2,557), renderer-driven, during `task-execute`.
- Soak whole-app slopes +0.28/+0.27/+0.17 MiB/cycle; renderer consistently
  +0.19–0.20.
- Five overnight task runs (soak-03, scale-10k ×3, payload) left the WebView2
  browser and crashpad running past the 10-second close grace. The Job
  terminated them. From 03:35 local, task runs took 10–14 s to close.

## Findings

1. **Slow exit: environmental, product cleared.** The 10–14 s tail began at
   soak-03's close (03:35 local), after an Office Click-to-Run update that left
   a pending restart, and persisted overnight. In `build/close-probe-20261108/`
   (scripts and results retained) the following all closed normally:
   - a bare pywebview window, with or without `collectGarbage` or the debug port;
   - the source app with collection on or replaced by a no-op;
   - interleaved old/new packages (2.1–3.8 s, no leftovers).
   The first old-package control was confounded by time of day and is
   superseded. The machine still reports a required restart; not rebooted.
2. **Execution peak: isolated to `323b5377` (remedy open, unscheduled).**
   Interleaved 10k runs on runtime 157: new package 1,203–1,258 MiB, old
   951–1,082 MiB. Source bisection (`build/peak-bisect-20261108/`) puts every
   tree through `2ca0b291` at 741–959 MiB and `323b5377` onward at
   1,323–1,454 MiB; response-copy removal and idle collection are cleared. The
   Plan follow now tracks settled verification items, and every follow step to
   a new item reads and fully rebuilds a 256-row window (`plan_review.js` `renderRows` reuses
   rows only for an identical offset and node list). Renderer DOM nodes peak
   117–142k instead of 37–43k. Disabling the commit's new follow chaining did
   not help. Candidate remedies: skip the window read and rebuild when the new
   target is already inside the rendered rows (narrow, `app.js`
   `queueReviewFollow`), or reuse rows by node id across overlapping windows
   (broader, `plan_review.js`). 100k not measured.
3. **Unexplained close-click stall.** Two of 19 source runs carrying
   `323b5377` timed out waiting for the task card to leave after Close was
   clicked 30–35 ms after completion; none of 19 earlier-tree runs did. Not
   investigated; `failure.txt` capture exists in the probe for a recurrence.

## Evidence and operational context

Evidence: `build/resource-study-20261108/` — `build_package.ps1`, `build.log`,
`package/` (SHA-256 `c14d1691…a7c082`), `full/` (runs, `fixtures.jsonl`,
`collection.json`), `full.log`, `validation.json` (FAIL: abnormal closes, soak
slope, 100k peak), and `oldpkg-runtime157/` plus its log. Analysis helpers are
the 20261106c `summarize.py` and `soak_trend.py`.

Peak isolation: `build/peak-bisect-20261108/` — `peak_probe.py`, `wrapper.py`
(collection on/off and bridge-command counting), `nochain.diff`, and
`runs/`–`runs4/` with `results.jsonl` and per-run `heap.jsonl`. Its scratch
worktrees were removed.

Study fixtures (sources under `F:\`, targets under `H:\test_dir\`) are
registered in each output's `fixtures.jsonl` (`full/`, `oldpkg-runtime157/`,
`newpkg-recheck/`, `close-probe-20261108/app/` and `pkg/*/`, and
`peak-bisect-20261108/smoke/` and `runs*/`) and were retained. The supplied corpus was not modified. No push.
