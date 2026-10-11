# Latest session — SN3 verified; scroll/navigation batch complete

2026-10-11. M1_PLAN's approved SN1–SN3 batch is complete. On milestone1,
SN1 is 940c7ef and SN2 is fac8ed0. SN3 is rebuilt as one reviewed fix commit
from the task-only recovery eba28a6, without merging or cherry-picking its WIP.
Exact integration identity is recorded in build/scroll-navigation-20261011/integration.md.

SN3 keeps one navigation read in flight and one latest target in Plan and
Inventory. Repeated arrows accumulate the desired endpoint; ordinary pointer
replacements coalesce, while discrete toggle/range gestures preserve order and
captured revisions. Python still owns range/anchor truth. Highlighted selection
uses the revisions displayed at input, so conflicts cannot silently select a
different range. Already admitted mutations settle without replay; retired
responses cannot restore focus or overwrite newer feedback. A later current
read can reconcile their matching receipt without keyboard reveal.

Other input inside or outside the review panel retires pending navigation,
including modified keys and immediate table reentry before an old read settles.
Passive row rebuilding retains actual focus. Four frontend modules and three
existing browser probes changed; no Python, bridge schema, byte counter, row
schema, renderer rewrite or native-helper change was needed.

Verification (build/scroll-navigation-20261011):
- sn3-neighborhood-final-01: 2,385 interfaces/tools tests passed, 3 existing
  symlink-privilege skips, 194.67s. Before/after source manifests match.
- sn3-native-final-01: installed tree passed. Inventory foreground and shell
  pre-context-input readiness were incomplete; retain both failed receipts.
- sn3-native-retry-02: Inventory and shell both passed in 46.33s after the user
  offered foreground assistance, without product/test changes. Earlier shell
  receipts did not identify the failed readiness predicate, so do not claim
  foreground alone was proven to cause that failure.
- Baseline fac8ed0 fails the new coalescing witness; current delayed probes cover
  repeat/reversal, discrete ordering, lookup/shared-read interruption, stale
  success/error, outside input, selection conflicts and passive focus.
  Negative control: build/sn3-negative-control.log and its retained driver.
- Independent source review found no remaining blocker; final evidence review
  checks current executable/probe identities and actual installed input receipts.

Raw successful native receipts:
%LOCALAPPDATA%/Temp/namisync-sn-sn3-native-retry-02/pytest/
The runner retains logs, XML, source manifests and exit codes in the evidence root.
SN1/SN2 verification and matched timing are retained there too; PERFORMANCE owns
SN2's results and limits. No SN3 timing claim is inferred from SN2 measurements.

No tests, native windows or measurement processes remain active. No unrelated
work, push or PR. After integration, verify all recovery paths are accounted for
before removing the task-owned recovery branch. No task worktree was created.
User foreground retry authority was exercised; no further gate is pending.
Default sandbox shell launch fails before execution; justified host pwsh works.
No approval rejection occurred. Use unique evidence names and freeze tracked
writers during whole-manifest verification.
