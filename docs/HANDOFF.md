# Latest session — inventory scan scope and M2 capacity

2026-10-02 on `milestone1`, starting from `c129fe5`.
The user requested scan-scope labeling and an M2 capacity design note. Later
M1 checkpoints remain unactivated.

## Changes

- `0d4d7d1` records command-result retention independent of task lifetime in
  M2_PROPOSAL. M1's shared 48-slot capacity and task-close retirement remain.
- The scan-label change retains producing subtree scope alongside exact paths,
  sends a bounded kind/optional-path descriptor, and labels Entire location,
  Item, Folder including subfolders, or Selected items. Scoped scans disclose
  that other inventory items were not rescanned. Notices belong to this scan.
- Retained prior publications keep their original scope after newer scans or
  refusals. Ledger contents and notice lifecycle are unchanged.

## Verification and immediate context

Evidence is retained under `build/m1-9-20261001/scope-label-*`; independent
reviews are `review-m2-capacity-note.md` and `review-scan-scope-label.md`.
Focused workflow/adapter/frontend checks pass 406 cases. The initial focused
run's sandbox default-temp setup failures are retained; the external-temp run
passes without changing product expectations.
The workflows/interfaces neighborhood passes 2,797 cases; all twelve import
contracts and 260 local document targets pass. The headed gate has 33 passes
plus a passing isolated execution-review rerun. Its first larger-window run
timed out waiting for capture readiness after observing execution and release;
the cause is not established, and the unchanged rerun passes in 18.65 seconds.
That failed receipt remains retained. The manually focused inventory witness
passes in 17.67 seconds, including the displayed whole-location scope and
scan-specific notice label. All 35 headed cases pass across these runs.
Existing cold-projection evidence validates against unchanged dependencies;
no new timing measurement is required.

The native-input interval has ended and all test windows have closed. No
further measurements are needed. Stop for the user's GUI review after these
changes; the M2 note grants no capacity-redesign implementation authority.
