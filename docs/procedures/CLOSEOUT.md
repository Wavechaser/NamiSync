# Commit And Session Closeout

Read this before each commit and at every session or stop boundary.
[DOCUMENTS](DOCUMENTS.md) owns which document records what.

## Commits

- One coherent checkpoint per mergeable commit, including its tests and matching
  documentation. Review relevant docs, obsolete material, and AGENTS for updates
  before committing; stale behavior documentation blocks readiness.
- Update/create the owning component doc with behavior changes. Update README
  for product, safety, limitations, roadmap or documentation-index changes.
- Use `<category>(<optional-scope>): <imperative summary>` with the narrowest of
  `feat`, `fix`, `perf`, `test`, `docs`, `refactor`, `build`, `chore`; scope is a
  lowercase owning component, omitted for cross-cutting work. `wip` is recovery-
  only, never on integration branches; its temporary readiness exemption does
  not make it mergeable.

## Review

Review each atomic outcome independently. After corrections, review the changed
delta and affected dependencies against the prior review; do not repeat
unchanged reviews or gates without a dependency reason.

## Task delivery and session boundaries

- Atomic commits carry matching subject docs; CHANGELOG records task delivery.
  At task delivery, extend the matching CHANGELOG task/date range or add a new
  task when none fits; update README's summary only if its phase/milestone
  synopsis changes.
- Update the active delivery register ([M2_PLAN](../M2_PLAN.md) for M2) when
  scope, decisions or checkpoint status changes, and at session/stop
  boundaries; it is not a per-commit transcript.
- Move work deferred in the session or checkpoint into the row that will own it,
  under [SCOPE](SCOPE.md#deferred-work), instead of leaving it in the source row.
- At session/stop boundaries, clean or promote the session's `build/` output
  under [evidence retention](#evidence-retention), then replace HANDOFF with
  latest-session changes, verification and immediate operational context. Keep
  command chronology in evidence.

## Evidence retention

Ignored `build/` holds generated and unfinished work, for example:

- measurement, test and probe runs with their receipts, logs and captures;
- study workspaces, scratch scripts, fixtures, and candidate or baseline copies;
- packages, installs and downloaded inputs;
- work in progress that continues in a later session.

Authored material someone decides from — studies, proposals, plans — lives in
`docs/` and moves to `docs/obsolete/` when superseded; promoted results live in
`evidence/`. Work files go nowhere else, inside or outside the repository,
except named deliverables and fixtures such as `dist/` or a benchmark source a
document names.

`build/` must be clearable at any time without lasting consequence. That is a
test that no lasting document depends on it, not a schedule: nobody clears it
routinely, and unfinished work stays there across sessions. Documents may name
it as a working location or leave temporary pointers (for example
work-in-progress context in HANDOFF). No lasting document rests a claim on
anything in `build/`.

Retention is decided by kind, not age. Promote to tracked `evidence/` only
results that were validated and whose work unit finished — a checkpoint,
consolidation run or longer effort, not necessarily one commit:

| Kind | Disposition |
| --- | --- |
| Measurement record | Promote the summary or report, exact source/producer/checker/runtime/profile/fixture identities, review decisions, validator output, and raw samples a Tier 2/3 claim needs. |
| Large raw dumps | Not promoted once the owning document holds the numbers; the record's identities let the method be rerun. |
| Per-run records, differentials, ledgers and copies | Not promoted, however small each file is: promote the aggregate (statistic, counts, verdict) instead of each run's record, a per-item diff or disposition ledger, or a copy of source or documents that Git can reproduce. Many files in one record usually means it was not compacted. |
| Study workspaces | Ablation, consolidation, refinement and optimization trees, candidate/baseline copies, installs and packages are deleted after the outcome is recorded. |
| Failed or superseded runs | Not retained wholesale. A failure a lasting document cites gets its own failure record, kept apart from any acceptance: identities, each failed predicate with its observed value and limit, the cause if known, and the disposition (fixed, rerun, waived or open). A superseded run keeps only what a lasting claim still needs. |
| Release evidence | Promote gate counts, identities and reconciliation; delivered files belong in `dist/`. |
| Bug reproducers | Promote only when small and hard to recreate; otherwise the bug entry carries a recipe. |

At each session closeout, clean or promote the output of work units that
finished, in compacted or recipe form where that suffices; unfinished work
stays in `build/` with a HANDOFF pointer. Confirm the session left no work files
outside the places above. Output too large to promote is decided with the user
during that closeout. [TOOLS](../TOOLS.md#evidence-records)
documents record IDs and manifest checks. Citations from transient documents
(HANDOFF, delivery registers, archived material) confer no retention. Promoted
files keep their original bytes; a compaction is a new summary that names what
it condenses. Historical observations remain bound to their measured
dependencies. Measurement methods and current result summaries belong in
[PERFORMANCE](../PERFORMANCE.md); detailed investigation chronology belongs in
the evidence record.
