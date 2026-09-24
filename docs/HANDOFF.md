# Latest session — repeated-move detection correction

2026-09-25: MOVE-1 corrects the backend planning reader on `milestone1`, based
on `3514bb8`. The user authorized investigation, implementation and the
execute-task review/commit workflow. The original uncommitted investigation
handoff is preserved at `build/move-history-20260925/handoff-before.md`.

The cause was historical inventory alias aggregation, not merely multiple
correspondence entries. Inventory retains path-keyed observations; the scoped
reader counted every old path and retained link count for a current identity
and disqualified it. A native workflow test starting with an executed paired
no-op reproduced the second rename planning `copy` plus `trash` after the first
rename correctly moved.

`find_current_mapping` now supplies scan-relevant correspondence without
historical identity disqualifiers. The planner already checks fresh source and
target link counts, identity multiplicity and pair ambiguity. Query input bounds,
target-key batching, filtering, canonical order and one SQLite snapshot remain.
The general inspection reader, recorder, inventory retention, schema and all
execution safety/effect logic are unchanged. DATABASE, PLANNER, BUGS and the
M1 Hardening changelog describe the correction; M1_PLAN owns scope/dispositions.

Verification complete: the before-fix native failure is retained in
`reproducer-before-detail.log`; 148 focused checks cover repeated moves with
zero copied bytes, preserved target identity, no trash and immediate no-op
reruns. Native hardlink cases cover source/target links outside the root or
excluded from planning. Planner controls retain current duplicates and ambiguous
correspondence. Repository tests cover historical link observations, current
pair filtering and mutation of a later-batch pair under one snapshot.
`focused-final2.log` records that final run. `ordinary-final.log` records
5,417 passes, five skips (four unavailable symlink privileges, one unconfigured
M1-7 readiness artifact), and 33 headed deselections. `imports.log` records all
12 contracts kept; diff and 45 local documentation-link checks passed.
`reviewer-readonly.md` independently approves the final source/test diff.
The first ordinary attempt's repository-local temp roots triggered protective
test refusals; its failed `ordinary.log` is retained. The passing rerun used
normal external temp roots and Windows subprocess access, with no code change.

No live development ledger or `H:\test_dir` content was changed. The existing
ledger needs no reset or repair: after restarting the development app to load
the corrected code, create a fresh plan. Previously reviewed plans keep their
original operations. The live nine-file case was not rerun in this session;
native temporary-root regressions are the direct behavioral evidence.

No extra branch/worktree was created; the atomic commit containing this handoff
delivers MOVE-1 directly on the original branch. Build evidence is retained.
The prior GUI-W1 mitigation and all pending M1 GUI work remain outside this task.
