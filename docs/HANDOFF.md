# Latest session — Rebuilt-package resource study, paused at the 100k refusal, 2026-11-06

On `milestone1`, the renderer allocation fix (`ea0daac2`), the dead-page
shutdown fix (`5f60abbb`) and the later GUI fixes through `48b1f708` were
reviewed and found to have no blockers. A clean package was built from
`48b1f708` (SHA-256 `30e83c33…eb91`, `build/resource-study-20261106b/package/`)
and driven through the resource collector. The previous session's GUI receipts
remain in `build/gui-live-20261106/`. Its larger-window Pause/Resume timeout
still has no confirmed cause.

Results are in [PERFORMANCE](PERFORMANCE.md), section "Rebuilt package resource
study". In brief:

- **Startup:** 352–378 MiB settled with idle CPU ≈ 0.25 %.
- **Workloads:** 10k peaks at 1.2–1.4 GiB and 50k at 1.9 GiB, with exact
  mirrors and normal exits. No crash occurred.
- **Retained memory:** ~0.7–1.2 GiB of renderer memory stays after a task
  closes. A forced GC shows it is collectable garbage (renderer back to
  ~90–120 MiB).
- **Throughput:** execution is now host-bound, at ~21 ms host CPU per item.

New BUGS entries, both OPEN, are under Interfaces › Planning refusal
presentation:

- **SEVERE: plan refused below the supported item target.** Preflight charges
  both the source and target subject of each operation against the
  120,000-row domain wall, so copy plans are refused at about 60,000
  operations. This contradicts the user's stated policy of guaranteed
  performance to 120,000 items with larger plans allowed. DEFENSE's
  population-wall list still states the old refuse-at-first-excess policy.
- **MODERATE: the refusal is shown as a retryable failure.** The page shows
  "Plan unavailable. Select the task to retry." through `open_plan_view`
  `internal_error`.

The user paused collection after `scale-50k-01` to look into the refusal
personally. Not yet run: scale-10k-02/03, scale-50k-02/03, payload,
soak ×3 and idle-open. To resume, use `build/resource-study-20261106b/resume.py`
with the same `--out .../full` and the remaining run names; it reuses the
recorded manifest and bundle check. `scale-10k-02-interrupted` is a
launch-only stub left by stopping the collector.

Diagnostics kept in the evidence directory:

- `debug_gui.py`/`debug_100k.py`: source GUI with bridge-exception and
  review-limit logging.
- `retention.py`: forced-GC retention runs.
- `summarize.py` and `cpu_split.py`.
- `wall_trace.py`: a CLI attempt that stalled before planning and was stopped.
  It produced no data; one empty walltrace target is registered in
  `debug100k/fixtures.jsonl`.

Study fixtures remain on `F:\` and `H:\test_dir\` and are registered in the
`fixtures.jsonl` files of `full/`, `smoke/`, `retention/` and `debug100k/`.
They include the 100k source `F:\NamiSync-resource-scale-100k-7f8dda2c`.
Earlier pilot fixtures stay as recorded in
`build/resource-baseline-20261106/`. R2 provenance, R3 judgment, R4 and R5
remain open.
