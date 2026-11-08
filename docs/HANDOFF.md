# Latest session — rebuilt-package resource schedule, 2026-11-07/08

## Delivered changes

Documentation only. CHANGELOG nits fixed in `733f0cb1`: renderer memory and copy
path work got its own task, and the measurement task's heading and date range
were restored. A package rebuilt from clean `733f0cb1` then ran the full
17-run resource schedule overnight. PERFORMANCE ("Full resource schedule on
`733f0cb1`"), M1_PLAN and CHANGELOG record the results. No product, test or tool
source changed.

## Results

- All 17 runs completed with exact mirrors and exit 0 (`full.log` ends `exit 0`).
- Settled memory after close: 10k 527–540 MiB (was 826–842); 100k 689–793 MiB
  (was 1,999–2,126); soak 510–536 MiB per cycle; open-task idle 560 MiB (was 837).
- Execution peaks rose: 10k 1,101–1,224 MiB, 100k 3,298–3,674 MiB (was
  2,365–2,557), renderer-driven, during `task-execute`.
- Soak whole-app slopes +0.28/+0.27/+0.17 MiB/cycle; renderer consistently
  +0.19–0.20.
- Five task runs (soak-03, scale-10k ×3, payload) left the WebView2 browser and
  crashpad running past the 10-second close grace. The Job terminated them. Task
  runs took 10–14 s to close, against 1–3 s before.

## Open findings (not fixed, owners decide)

1. **Slow exit after work.** Two old-package 10k runs on the same Edge
   157.0.4341.42 runtime closed in 1.1/1.5 s with no leftover processes, so the
   runtime update is excluded; the likeliest suspect is the collection path
   (`host.py` `collect_garbage` via `CallDevToolsProtocolMethodAsync`).
   Unestablished: the cause, and how long the browser lingers without Job
   termination. Owner: INTERFACES.
2. **Execution peak.** The 10k old-package control (894/1,131 MiB) overlaps the
   new range, so runtime and product are not separated. 100k was not rerun on
   the old package.

## Evidence and operational context

Evidence: `build/resource-study-20261108/` — `build_package.ps1`, `build.log`,
`package/` (SHA-256 `c14d1691…a7c082`), `full/` (runs, `fixtures.jsonl`,
`collection.json`), `full.log`, `validation.json` (FAIL: abnormal closes, soak
slope, 100k peak), and `oldpkg-runtime157/` plus its log. Analysis helpers are
the 20261106c `summarize.py` and `soak_trend.py`.

Study fixtures (sources under `F:\`, targets under `H:\test_dir\`) are
registered in `full/fixtures.jsonl` and `oldpkg-runtime157/fixtures.jsonl` and
were retained. The supplied corpus was not modified. No push.
