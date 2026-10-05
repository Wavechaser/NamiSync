# Latest session — GUI follow-up

2026-10-05 on `milestone1`, base `583f14d`. The user ratified GUI-B1–B6,
then explicitly deferred all of B2 for separate review. B1 and B3–B6 are
delivered as separate reviewed atomic units. No B2 correction is included.

| Unit | Delivered change | Commit |
| --- | --- | --- |
| B1 | Bounded Plan window labels, strict presentation validators, exact-node full details and migrated consumers | `53e1abb` |
| B3 | Shared Verify Setup height, stable consolidated status detail and truthful progress | `2828b8b` |
| B4 | Local `yyyy-MM-DD HH:mm` timestamps with unchanged raw values and elapsed calculations | `0f87f6a` |
| B5 | 20rem Details cap, 2:3 global/item height and full paths joined to the correct known root | `61a5cf5` |
| B6 | Existing row actions through pointer/keyboard context menus; exact clicked-row scope | This commit; identity in `integration.md` |

## Verification and evidence

Evidence root: `build/gui-followup-20261005/`. The user's original uncommitted
HANDOFF is preserved verbatim in `user-handoff.md`; `integration.md` records
atomic commit identities. Each delivered unit has a fresh independent review
and exact input binding in `b1-review-final*`, `b3-review-receipt.json`,
`b4-review-receipt.json`, `b5-review*` and `b6-review*`.

B1 passed 5,913 ordinary tests, 12 import contracts and 12 installed UI/transport
checks. B3/B4 passed their interfaces gates and seven installed checks each;
B5 passed 1,944 interfaces tests and nine installed obligations. The retained
B5 larger-shell initial-readiness failure passed on unchanged-input retry.
B1's earlier sandbox principal/policy/window-enumeration failures and B4/B5
fixture corrections remain in evidence; they were not discarded or accepted
as passes. B6's ordinary integration passed 5,914 tests (four privilege skips,
35 headed exclusions) and all 12 import contracts. Final focused verification
passed 86 cases. Its seven installed obligations passed across `b6-native-01`
(two shell sizes), `b6-native-03` (Inventory) and `b6-native-04` (four gallery
checks). Failed receipts and the corrected script/visibility/measurement causes
remain in `b6-native-disposition.md` and `b6-gallery-rejection.md`. Product bytes
remained unchanged after the ordinary gate; every changed test consumer was
rerun. Native Inventory proves the clicked missing-file scope independently of
the other selected folder's details, with one effect per original command.

## Deferred B2

The entire Verify table alignment is deferred, including row spacing, zebra,
disabled checkbox visuals, Notes, Presence labels and basename rendering.
Functional selection remains M1-10. Execution-to-Verify navigation/A6 also
remains deferred.

Read-only recurrence review reproduced Inventory full-path replication exceeding
the correctly enforced 8 MiB response wall. BUGS and M1_PLAN retain the open
defect and one consolidated proposal: compact window basenames/warning paths
and extend existing single-item details with separate snapshot path context.
No B2 product, test or contract correction was implemented. Reproduction is in
`b2-design-inventory-envelope.py` and `.json`; renewed user authority is needed
before implementing the deferred proposal.

## Operational context

No task worktree/recovery branch, push or PR. Retain owned evidence and failed
receipts. No external Claude review was requested for this follow-up; execute-task
uses fresh independent reviewers for every unit. README's phase synopsis and
AGENTS need no changes. M1_PLAN owns scope and DESKTOP_UI owns shipped behavior.
