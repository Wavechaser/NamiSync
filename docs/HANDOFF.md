# Latest session — GUI follow-up

2026-10-05 on `milestone1`, base `583f14d`. The user ratified GUI-B1–B6 in
M1_PLAN, then explicitly deferred all of B2 for separate review. B1 is committed
as `53e1abb`; B3 is committed as `2828b8b`. B4 timestamp formatting passed its
final gates and is ready for atomic commit; B5–B6 remain authorized. No B2 work is included.

## Delivered B1

Plan windows carry compact display/notice/destination labels and Rename-only
prior filenames. One revisioned exact-node detail read preserves original-case
paths, their source/target origin and complete notices without filesystem or
ledger I/O. Raw projection search, node-id reveal, selection and execution are
unchanged. Bridge admission checks closed presentation kinds and their exact
row/operation relationships. Command catalogs and direct fixtures migrated.

Evidence: `build/gui-followup-20261005/`. The user's sole pre-existing dirty
HANDOFF was preserved verbatim in `user-handoff.md`; its findings are addressed
by B1 and the corresponding BUGS entry. Focused backend checks passed 601 tests
and 12 import contracts before the final casing adjustment; its seven direct
checks passed. Frontend/gallery checks passed 82 tests, followed by 56 after
independent review corrected row-kind/identity validation. Reviewer evidence is
`b1-review-*`; the independent correction witness rejects four invalid shapes
while retaining legitimate prior-location operations.

`b1-ordinary-01` passed 5,910 tests with four privilege skips, but three sandbox
setup failures prevented acceptance. Two ACL fixtures targeted a different
principal than the sandbox process and failed before reaching the executor;
PowerShell policy blocked the third test before its version guard. All twelve
`b1-native-01` cases stopped at window enumeration before input. No product or
driver changes were made for these conditions. `b1-environment-disposition.md`
records the evidence. Final `b1-ordinary-02` passed 5,913 tests with four privilege
skips and 35 headed exclusions, followed by all 12 import contracts.
`b1-native-02` passed all 12 affected installed gallery/shell/transport checks.
Both ran outside the sandbox on frozen product/test inputs. Independent approval
and exact input binding are in `b1-review-final.md` and its binding JSON. Local
document links and diff checks pass; `integration.md` records the atomic commit.

## B3 delivery

Verify Setup shares Plan's path-area minimum height. Status uses the current
outcome, one rollup summary and one persistent detailed paragraph for publication
scope/counts and loading/action/recovery guidance. Shared progress animates for
unknown active totals and retains a static terminal track without inventing 100%.
Table, payload, details and action scope remain unchanged. Direct composition and
frontend checks passed 15 tests; the final focused set passed 41. Final gates
passed 1,943 interfaces tests and seven installed gallery/shell/Inventory checks
(`b3-*-01`). Independent review found no actionable defect; final source and
closing-document binding is retained with its receipt. Source/tests/measurement/
checker inputs matched the independent receipt. Local document links and diff
checks pass. `b3-review-receipt.json` binds actual equal Setup heights at both
widths, installed progress observations and the final inputs.

## B4 delivery

B4's final focused set passed 13 direct/composition/checker tests. The shared
local formatter preserves unavailable values, nanosecond precision and original
elapsed-time calculations. Representative installed gallery dates and direct
UTC/non-UTC/boundary cases migrated together. `b4-interfaces-01` passed 1,944 tests;
`b4-native-01` passed all seven gallery/Inventory/execution cases. Independent
review found no actionable defect and bound frozen inputs. Preliminary failed receipts retain the sandbox
temporary-root denial and corrected test-only window-identity ordering; no
production cache behavior changed.

## Deferred B2 and next work

Read-only Inventory review reproduced the same full-path replication mechanism:
supported domain/notices windows exceeded the bridge's existing 8 MiB wall.
AGENTS recurrence review produced the consolidated mechanism table and proposed
an existing-detail-response extension for warning/synthetic snapshot paths.
The user chose **Defer B2 and review separately**. No Inventory table, checkbox,
payload or detail-contract changes were made. The open defect, complete field
population and raw reproducer are in BUGS, M1_PLAN and `b2-design-inventory-envelope.*`.
The earlier disabled-checkbox proposal is deferred with B2; functionality remains
M1-10. Execution-to-Verify navigation/A6 remains deferred too.

Current B4: shared local date/time display, preserving machine values and elapsed
calculations. Next B5: 20rem details pane, 3:2 item/global height and
root-correct full paths; B6 row context menus. Menus use existing actions only:
Show details, Plan Select/Deselect where allowed, folder Expand/Collapse, and
Verify Refresh selected/Acknowledge missing. Inventory keeps its existing single
highlighted-node scope; no clipboard, new filesystem effects or selection policy.

## Operational context

No task worktree/branch, push or PR. Evidence/temp roots are owned and recorded by
each run; retain failed receipts. Shared source/tests/validators are frozen for
acceptance; future work must wait for the current coherent commit. No external
Claude review was requested for this follow-up; each unit uses a fresh independent
reviewer through execute-task. README phase synopsis and AGENTS need no changes.
