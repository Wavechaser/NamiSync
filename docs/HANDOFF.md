# Latest session — GUI alignment

2026-10-05 on `milestone1`, base `999a568`. The user ratified seven
GUI units in [M1_PLAN](M1_PLAN.md): A1–A5 active; execution-to-Verify
navigation (A6) deferred to M1-10; all previous-location/rename redesign
(A7) deferred to a focused session. Standalone Verify remains on Integrity
with Sync disabled. No A7 presentation-boundary exception was approved.

## Integrated work

- A1 `4f314b2`: visible recovery after an incoherent move-reveal window and
  conflict scrolling. Seven focused, 1,921 interfaces and both installed
  task-shell cases pass.
- A2 `498eb24`: first-visible column snapshot lets only Filename absorb
  enlargement, preserving bounded manual resizing. Thirty-six focused,
  1,921 interfaces and six installed task-shell/gallery cases pass.
- A3 `49801f7`: shared counted Filter menu and pinned Regular icons.
  Eighty-four focused, 2,286 interfaces/tools (three skips), pinned icon
  provenance and seven installed task-shell/gallery/Inventory cases pass.
- A4, the atomic delivery containing this handoff: optional full-height right
  details column with two independent card scrollers; category/status and
  supplied item facts; capped shrinking details and task rail. Eighty-nine
  focused, 1,921 interfaces and all six installed cases pass across the final
  gallery run and unchanged retained default/larger shell evidence.

Evidence lives in `build/gui-alignment-20261005/`; `a1-review.md` through
`a4-review.md` own independent review decisions. A4's final source is bound by
`a4-frozen-final-03.json`; native gallery is `a4-gallery-final-03.xml`,
shell passes are in `a4-native-final.xml`, and department results are
`a4-interfaces-final.xml`. All 277 installed files match between the retained
shell and final gallery builds. Failed/superseded receipts remain: A4's natural
row-height overlap was corrected; its obsolete endpoint-only table-header
detector and queued-scroll gallery ordering were migrated without weakening
visibility, hit, dismissal or ingress guarantees. Evidence owns that chronology.

## Immediate next work

A5 is designed read-only and awaits A4 integration before implementation.
M1_PLAN contains its finite population and gate. Align standalone Inventory/
Verify with the settled setup/status/table/details surfaces, move Refresh
actions to status, reuse semantic labels and five-column sizing, and expose the
already-recorded checksum through the bounded window/bridge contract. Preserve
scan versus verification truth, current/prior publication and acknowledgement
scope. Refresh A4's integrated layout and report seams before writing.

Finish A5's focused/composition/department/native gates and fresh review, then
the ordinary suite/import checks for batch integration. Source/test writers
and native acceptance remain serialized. Cleanup only exact task-owned external
roots after retained evidence accounting; `integration.md`, frozen manifests
and `a3-temp-ownership.json` record ownership. No task worktrees or branches have
been created. No push, PR or new domain/integrity feature is authorized.
