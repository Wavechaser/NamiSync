# Latest session — current-source BR-G-42 timing, 2026-11-09

## Delivered change

Base `ddf1afe9`, branch `milestone1`. No product change. `8d599511` realigns
the optional `tools performance execution-ui` driver: start settlement now uses
`plan_request_id` (changed by `41afd262`), control successors match the leading
status message (changed by `2dcdc05f`), and the parent accepts the page's exact
typed control reply. Tests feed the real shapes and fail on the old driver.

## Verification

- `tests/interfaces/web/test_m1_8_execution_ui_scale.py`: 46 pass; 3 fail with
  the driver change removed.
- Ordinary suite: 6,489 pass, 4 skipped. Two pre-existing failures are
  unrelated: `tests/test_table_loading_performance.py` reports
  "table-loading instrumentation anchor drifted" with and without this change.
  The optional table-loading driver's anchor no longer matches current
  `bridge.js`; it was not investigated or fixed.

## Measurements

[PERFORMANCE](PERFORMANCE.md#current-source-br-g-42-diagnostics--2026-11-09)
owns the table and limits. In summary, bridge-event latencies, Plan, 13
execution-UI cases and History release are all within the historical budgets.
Bridge-event stays `incomplete`: its memory-sampler limb (0.1 s blind interval)
fails because a once-a-second thread snapshot walks all system threads (about
43 ms at 7,700 threads, 88 ms at 15,000). The harness reference still names
CPython 3.13.14. Plan retained memory has 11.8 MiB headroom on a single sample.

## Next decisions

- R3 acceptance needs: a bridge-event harness whose memory limb is independent
  of system thread count (or a bounding quiescence profile), a runtime-profile
  decision for 3.13.17 and predeclared five-child cold collections.
- The table-loading driver anchor drift is a separate optional-tool repair.
- Cleanup of F:, H:\test_dir and `build\` was inventoried earlier this session
  and awaits the user's decision; this session adds
  `build/bridge-timing-20261109/` (wheel, `site/` install, reports, raw logs).

## Operational context

No task-owned native process remains. Evidence, including failed attempts
(`*.attempt1`, `*.attempt2`), is retained under `build/bridge-timing-20261109/`.
The timing runs created no new roots on F: or H:. Six
`%TEMP%\NamiSync-cadence-*` directories (2026-11-08 23:34 – 2026-11-09 00:33,
about 12,800 files) predate this session's runs and belong to another session;
they are cleanup candidates.
