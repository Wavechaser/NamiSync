Notes for "Cold admission follow-up (2026-09-27)": text files chosen from `build/cold-admission-followup-20260927/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/cold-admission-followup-20260927/cli-review.md`

# CLI-DRIFT independent review

Reviewed the frozen working-tree candidate against `0e4595e4` on `milestone1`.
Reviewer was read-only for product, tests and documentation; this receipt is
the sole reviewer edit. No native desktop or package-build run was performed.

## Disposition

Approved for the separate CLI-DRIFT commit. No blocking source or documentation
findings. Final ordinary evidence and HANDOFF/register updates were inspected
after source/test freeze; focused evidence is not substituted for that gate.

## Inspection and evidence

- Inspected contracts/schema, complete pair retry ownership, initialization
  separation, live-owner classification, service/workflow facade propagation,
  CLI history and pair rendering, host startup guidance, and direct test diffs.
- Three attempts belong to either the complete pair validation or standalone
  role admission. Pair role probes are single-attempt; initialization,
  reservations, task submission and filesystem effects are outside retries.
- Drift rechecks retain typed causes through the final peer check. Schema/SQL
  failures are rechecked against original source evidence before reset-worthy
  classification. Inaccessible, journal-bearing and incomplete artifacts carry
  preservation guidance. The original live-owner availability-to-reset finding
  was corrected without changing live admission decisions or ownership.
- Cleanup annotations prevent retries of incomplete cleanup; existing control
  exception precedence and cold source/copy containment remain. Tests retain
  source-byte assertions and exact complete-pair attempt populations.
- Inspected deterministic transient/persistent SHM drift, provisional schema
  failure, final-peer drift, cleanup failure, live unavailable errors, and real
  SQLite WAL commit controls through both pair and history entry points.
- Checked README, DATABASE, INTERFACES, BUGS, CHANGELOG and M1_PLAN against the
  implemented behavior. The separately authorized TESTS/own-snapshot precision
  changes are not included in this outcome.
- `cli-focused-progress.xml`: 571 tests, zero failures/errors/skips (29.798 s).
- `cli-drift-counts.xml`: 27 tests, zero failures/errors/skips (2.036 s).
- `git diff --check` passed; only repository line-ending notices were emitted.
- Final `cli-ordinary.xml/log`: 5,410 passed, 4 privilege-related skips and 34
  headed deselections, 287.10 seconds. Final HANDOFF, M1_PLAN and CHANGELOG
  accurately record this gate and leave DOC-PRECISION pending separately.
- `cli-docs-check.json`: 151 local links, no errors. Twelve import contracts
  passed. No product/test correction was made after the reviewed freeze.

Remaining boundaries are explicit: retries bound attempt count, not snapshot
I/O duration; no cross-process mutex or task replay is introduced; source drift
does not establish the exact cause of a historical AB-7 exception. Desktop
Setup failure normalization is outside this fix.

# `build/cold-admission-followup-20260927/docs-review.md`

# DOC-PRECISION independent review

Reviewed the working-tree documentation diff against `5e4bf87` on `milestone1`.
The diff is limited to `docs/TESTS.md`, `docs/DATABASE.md`, `CHANGELOG.md`,
`docs/M1_PLAN.md`, and `docs/HANDOFF.md`. No product, helper, or test source
changed in this documentation commit.

The `TESTS.md` readiness description matches
`tests/interfaces/web/_task_shell_headed_child.py`: after clicking the notice
filter, the helper waits for the expected notice text, an empty pending-action
marker, and an enabled Plan-again button before its single click. It no longer
attributes the historical focus-loss failure to an already-visible notice or
claims a specific request settled. The exclusion of a product button/icon
change is consistent with this documentation-only correction.

The `DATABASE.md` statement is scoped accurately. Connections opened through
`DatabaseConnectionOwner` receive validation on their own SQLite snapshot in
`namisync/db/contracts.py`. `HistoryStore._load_existing` and
`HistoryStore._load_event_receipt` in `namisync/db/history.py` connect directly
and do not repeat schema admission. The remaining placement and standalone
constructor wording is consistent with the existing source and does not claim
new behavior.

The changelog, M1 plan, and handoff describe the separate documentation commit
and do not expand the CLI fix. `docs-check.json` reports 85 local links and zero
errors; `git diff --check` passed. The full product suite's earlier 5,410-pass
result belongs to the CLI commit and was not rerun for this docs-only diff.

Decision: **approved; no blocking findings** for the second documentation commit.
