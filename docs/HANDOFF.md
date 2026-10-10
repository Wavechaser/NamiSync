# Latest session — directional loading verified; navigation coalescing next

2026-10-11. M1_PLAN SN1–SN3 owns the approved batch, starting milestone1 at
0580b1b. SN1 is integrated as 940c7ef; SN2 is verified for its separate commit.
SN3 remains authorized and pending. No row schema, bridge counter, renderer
rewrite or domain change is included.

SN1 preserves passive row focus without scrolling, retains explicit keyboard
reveal and settles discarded Plan reads without losing newer demand or looping
failed reads. Its native and interfaces/tools gates passed. SN2 places one
256-row window ahead of travel, keeps 32 rows behind and prefetches within 64 rows
of only the travel-side edge. Early reads survive covered reconciliation;
reversal retires obsolete intent through the existing serialized read lane.
Programmatic/view replacement rebases direction. Actual short-window endpoints
remain authoritative; do not restore a total-minus-256 start clamp.

Evidence: build/scroll-navigation-20261011/. SN2 focused receipt is
build/sn2-focused-10.log (4 passed). sn2-neighborhood-final-01 passes 2,385
interfaces/tools tests, 3 skipped. A later fixture-only keyboard setup correction
passes sn2-tools-method-final-01 (406 passed, 3 skipped). Current installed
tree passes in sn2-native-final-01; Inventory and shell pass in
sn2-native-retry-01 (2 in 42.96s) after user foreground coordination. Retain
the earlier input-admission failures; they did not prove product failures.

Matched matrices: sn2-baseline-plan-02, sn2-candidate-plan-01,
sn2-baseline-inventory-01, sn2-candidate-inventory-01; aggregate
sn2-summary-01.json. Twelve fresh installed children use one frozen method and
matching profile/runtime. SN1 installation is sw-install-baseline-sn1-01;
final candidate is sw-install-candidate-sn2-02. Installation01 is superseded.
Initial Plan measurement01 failed before steady collection because offscreen
row activation focused/scrolled normally. The revised setup restores the
viewport synchronously, checks original geometry and active identity, and keeps
the exact offset-minus-one ArrowUp target. Both variants use that same method.
Source/install/restored hashes and failed receipts remain retained.

In each 12-second trajectory, median uncovered seconds fall from Plan
2.107/5.176 and Inventory 1.237/4.442 to zero at 240/1,000 rows/s. One Plan
1,000-row/s run has 97.1 ms total sampled gaps; other candidate runs have none.
Reads fall to 20/81 in both pages, with one outstanding read and 256 retained
rows. PERFORMANCE owns direction splits, ranges, burst intervals and limits.
These are frame-sampled DOM observations, not compositor/native-wheel guarantees.

SN3 design: replace Plan's promise FIFO with one running navigation operation and
one latest absolute desired target; Inventory needs desired-index accumulation.
Plan scroll and highlight-related reads must share admission. Resolve off-window
node IDs through existing revisioned reads; Python retains range/anchor truth.
Later input retires pending navigation and its visual authority immediately.
Already admitted highlight mutations retain custody until settlement; never
replay them or let a late reply reclaim focus, details or current messages.
Do not coalesce toggle/add-range/checkbox effects. Scope-dependent actions retain
the displayed revisions and conflict/no effect if superseded server truth differs.
Revalidate current SN2 callbacks before implementation; no new server schema is
currently needed. Existing frontend probes, server selection guarantees and
installed keyboard/pointer witnesses own verification.

No unrelated work, push, PR or worktree. No active native/measurement process.
Use unique run names and preserve prior studies. Sandbox launch fails before
execution; justified host pwsh works (no approval rejection). User authorization
for headed attempts and recovery if foreground ownership blocks them persists.
