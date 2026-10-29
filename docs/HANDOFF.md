# Latest session — Consolidation A1/A2 and requested pause, 2026-10-29

The user adopted the amended study reconciliation and authorized the finite
pre-closeout register in M1_PLAN, then requested a pause after license and
documentation corrections. A1/A2 are complete. The batch is paused; do not
resume remaining rows until the user resumes. M1-12, release and DOC-2 remain
inactive. Baseline was clean `2285b426` on milestone1.

A1 (`0bbe841d`) pins LICENSE to LF, updates only the NamiSync embedded text/hash,
and fixes the wheel/checkout comparison to use raw decoded bytes. JavaScript
EOLs are not pinned and third-party notices are unchanged. A2 corrects README
and FEATURES active desktop/Inventory status and support wording, explicitly
retains scoped planning as future, and describes actual workflow publication
owners instead of nonexistent context/sink APIs. Matching owner docs, BUGS
and CHANGELOG are updated. No new generator or support expansion.

Verification: four real wheel/About/package checks in each fresh autocrlf
false/true checkout; 2,132 interfaces passes in the sandbox and all 67 cases
in the affected recheck population passing outside it with external temp.
The initial five failures/28 setup errors were sandbox native restrictions and
the custody driver's refusal of a source-tree cache path. Earlier pip-temp and
Git/MSYS sandbox failures are retained too; no failed receipt was relabeled.
Independent byte/source review, documentation consistency/diff checks and
77 A2 local link targets passed. No headed test was required for unchanged
modal/host behavior; this is not M1 release acceptance.

Evidence root: `build/m1-closeout-study-20261029/`. See `results/a1-fresh-checkouts.*`,
`a1-c1-interfaces.log`, `a1-c1-native-recheck.log`, and the study/reconciliation.
Temporary checkout fixtures live under the root; native recheck temp is under
Local/Temp with prefix `a1-c1-native-recheck-temp-`. No user files were copied.

C1 candidate-ingress tests were already written when the pause was requested.
They passed 280 command cases, the interfaces gate and independent review, but
remain undelivered. Their only changed file is preserved on disposable recovery
branch `codex/recovery-closeout-c1-20261029`, commit `419aad11`, based on `2285b426`.
`results/c1-preservation.json` and `c1-unfinished.patch` hold exact provenance.
Rebuild that delta on resumption; do not merge/cherry-pick the recovery commit
as-is. It covers the real parser with valid purpose and SafeInt ID bounds;
the upper accepted remembered-location ID is 2^53-1, not signed-64 maximum.
C1 must land before B1 legacy-slot removal. The remaining B/C/D/R/E/CLOSE rows
have not started implementation. Existing user recovery refs and stashes are
unchanged. This session created only the named C1 recovery ref; no push or PR.
