# Latest session — GUI-C1–C5 complete

2026-10-07, `milestone1`. The resumed fixture correction is integrated as
`455fd49`, followed by diagnostic baseline `61ee878`, Inventory coalescing
`4122b10`, and the final Plan keyboard placement unit. `integration.md` under
`build/gui-inventory-refinement-20261005/` records final commit identities and
recovery-reference cleanup. No accepted C1–C5 work remains pending.

Inventory now keeps one running viewport read and only the latest queued intent.
Each caller retains its promise; cancellation covers loaded/covered returns and
lifecycle replacement. Direct action-owned reads keep independent ordering.
Off-window Plan keyboard moves use the existing 32-row leading buffer; pointer
and in-window placement remain unchanged. No backend, bridge, filesystem effect
or general scheduler change was made.

The three complete six-child matrices (96 observations each) are
`c5-baseline-*`, `c5b-measured-*` and `c5c-measured-*`, with raw browser/host
receipts, source manifests and restored-asset evidence. PERFORMANCE owns method,
figures and limits; `c5-baseline-summary.md`, `c5b-comparison-summary.md` and
`c5c-comparison-summary.md` retain compact evidence summaries. Inventory burst
reads fell from 72/max concurrency eight to 27/max one; median coverage
413.8→175.4 ms in that comparison. Plan keyboard reads fell from two to one per
gesture, with zero uncovered interval and median 155.7→83.0 ms. Other latency
variance receives no causal claim. Instrumented diagnostics are not SLOs;
observer overhead, unrelated workload/power, host queues and compositor timing
remain unmeasured. No broad suite ran alongside timing.

Verification: fixture 68 focused/5,924 ordinary/four privilege skips/12 imports;
method 29 focused/5,953 ordinary/four privilege skips/12 imports; coalescing and
placement each 88 focused/2,348 interfaces+tools/three privilege skips/12 imports.
Installed Inventory/shared-tree pass two; final task-shell default/larger pass two.
Final gate `c5c-neighborhood-01` passes in 196.34 s. Independent fresh reviews
check source, controls, raw receipts, exact dependency binding and restoration.
All failed attempts remain retained with their dispositions. The new Close
test's obsolete-review setup was corrected without a product change.

All three disposable measurement installations are retained intact with exact
runtime pins and wheel/installed identities. `run-c5.ps1` revalidates identities
and source before/after; all instrumented assets were restored. Reuse evidence
only after dependency checks. Native/broad runs need the actual Windows user
(`require_escalated`), not the sandbox identity whose environment reports
Spectrum. Its earlier identity/policy precondition failures and unchanged actual
user pass are documented in `c5-fixture-environment-disposition.md`; no settings
or assertions were weakened. Foreground guards remain required for native input.
No test or benchmark process is active at closure.

Original `user-handoff.md` and all recovery bytes are preserved. C1 recovery
`a638040` product/test/component docs were integrated exactly in `9868f5c`;
only delivery prose was superseded. C5 recovery `5031f22` was reconstructed into
the reviewed fixture/method commits, with every saved path accounted for.
Never merge/cherry-pick those WIPs. No unrelated changes, worktrees, push or PR.

No prefetch or placeholders were added: this fixed abrupt-jump corpus establishes
neither gradual lead time nor beneficial placeholder presentation after the
keyboard placement fix. Remaining observed gaps are retained as limitations.
Functional Verify checkbox selection and execution-to-Verify remain M1-10;
the other explicit product exclusions remain in M1_PLAN.
