# Latest session — current-source BR-G-42 timing, 2026-11-09

## Delivered change

Base `ddf1afe9`, branch `milestone1`. No product change.

- `8d599511` realigns the optional `tools performance execution-ui` driver with
  current task identity (`plan_request_id`), status lines that append control
  guidance, and the page's typed control reply.
- `387a9749` ratifies CPython 3.13.17 as the BR-G-42 reference runtime (user
  decision, DEFENSE §7, budgets unchanged).
- `ec194871` makes the bridge-event harness count threads from one
  `SystemProcessInformation` snapshot instead of a Toolhelp walk of every
  system thread. Counts are identical, and cost drops from 44–88 ms to
  about 7.6 ms.

## Verification

- Driver and harness tests pass: 46 execution-UI tests and 42 bridge-event
  tests. The execution-UI tests fail with the old driver.
- The ordinary suite earlier passed 6,489 with 2 pre-existing failures in
  `tests/test_table_loading_performance.py`. That optional driver's
  instrumentation anchor no longer matches `bridge.js`; it is not fixed.
- Bridge-event `installed` passes three times on clean `ec194871`, with a
  longest memory-sample gap of 0.021–0.022 s. It remains a diagnostic case.

## Measurements

[PERFORMANCE](PERFORMANCE.md#current-source-br-g-42-diagnostics--2026-11-09)
owns the results. Every family is within its historical budget. The tight
items are stable:
- Plan cold base: 1,819–1,833 ms against 2,000 ms.
- Retained construction memory: 323.3–324.3 MB against 335.5 MB.

The causes are attributed; no product change has been made or approved.

## Open decisions

- **Retained memory:** derive or share folder `path` strings instead of
  retaining node-tree strings (about 18 MiB), and possibly move rarely set node
  fields into an optional record (about 19 MiB; broader contract change).
- **Cold base:** fill frozen node slots through member descriptors during
  materialization (about 100 ms). The node-tree build (about 660 ms) and draft
  append (about 500 ms) remain the largest phases.
- **Acceptance:** R3 still needs predeclared collections.
- **Table-loading driver:** the anchor repair is a separate optional-tool fix.

## Operational context

Cleanup (`build/cleanup-20261109/delete-list.txt` and `delete-log.txt`) removed
1,947 items:
- all `F:\NamiSync-resource-*` corpora;
- everything in `H:\test_dir` except `source` and `target`;
- `build\` package environments, evidence-free profiles, WebView2 browser data,
  measurement-run databases and evidence-free fixture trees.

Logs, receipts and results were kept. 19 old pytest venv/profile folders under
`ab10-20260926`, `m1-7*` and `m1-9-20261001` failed with access denied, a
probable sandbox ACL issue. Six `%TEMP%\NamiSync-cadence-*` folders from
another session remain. No task-owned native process remains.
