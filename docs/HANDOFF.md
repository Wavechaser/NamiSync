# Latest session — C5 baseline complete, coalescing next

2026-10-07, `milestone1`. The approved fixture correction is integrated as
`455fd49`, following helper correction `6c6e10f` and C1–C4. It preserves fixture
populations and historical authorities while supplying genuine RECASE evidence.
Its checks passed: 68 focused, 5,924 ordinary/four privilege skips, 12 imports
and the installed Plan04 compatibility probe. That probe is not timing evidence.

C5a's frozen diagnostic method and baseline are complete. Evidence root:
`build/gui-inventory-refinement-20261005/`. `c5-method-focused-06` passes 29;
`c5-method-ordinary-01` passes 5,953/four privilege skips plus 12 imports.
Installed representatives Plan05 and Inventory01 pass all 16 observations each.
`c5-baseline-plan-01.json` and `c5-baseline-inventory-01.json` contain three fresh
children each, 96 observations total, with raw receipts, before/after source
hashes and verified restoration/installation identity. Independent review
recomputed all summaries and found no remaining issue. PERFORMANCE and
`c5-baseline-summary.md` own figures/limits; `integration.md` records commits.

Inventory's nine bursts dispatched 72 reads, concurrency eight, discarding 63;
Plan dispatched 27, concurrency one, discarding 18. Median target coverage was
413.8/192.9 ms respectively. Covered-return visibility is separated from later
obsolete-read settlement. These are instrumented diagnostics, not latency SLOs;
observer overhead, compositor presentation and host queues remain unmeasured.
No broad suite ran during timing. Product assets remain unchanged by C5a.

Next implement C5b under the accepted M1_PLAN boundary: task-owned one running
viewport read plus one latest queued intent; independently retire callbacks to
null. Preserve direct action-owned initial/view replacement reads and existing
action ordering. Tree cancellation must cover loaded/covered returns without
requiring another request. The read-only design inspected `455fd49`; revalidate
the unchanged product seams after the C5a commit. Owners: app, Inventory panel,
optional tree callback and their existing real-page/lifecycle/tree probes.
Run focused/interface/import and installed Inventory/shared-tree checks, then
the identical six-child matrix from a separate pinned-runtime installation.
Placement/prefetch and placeholders remain conditional, separate outcomes.

Native/broad runners must use the actual Windows user (`require_escalated`),
not the sandbox identity whose environment misleadingly reports Spectrum.
The first fixture ordinary run's identity/policy precondition failures and
unchanged actual-user pass are retained in `c5-fixture-environment-disposition.md`.
No user policy or assertion was changed. Announce native runs; preserve all
foreground guards. The user will try to foreground the window. No native run
is active at this checkpoint.

Keep `c5-install-baseline-01` unchanged. `run-c5.ps1` validates the wheel/install
before and after, records input hashes and uses unique output names. The host
profile was refreshed on Oct7; the Oct6 profile remains separately retained.
Keep failed probes and original `user-handoff.md`. Both task recovery refs
remain until full batch accounting: C1 `a638040` and C5 `5031f22`. All nine C5
recovery paths have been reconstructed or superseded individually; never merge
or cherry-pick the WIP. No unrelated changes, worktrees, push or PR.

Functional Verify checkbox selection and execution-to-Verify remain deferred.
No new filesystem effects, backend changes or general request scheduler are
authorized by C5.
