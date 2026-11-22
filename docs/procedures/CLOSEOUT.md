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
- Update the active delivery register ([M1_PLAN](../M1_PLAN.md) for M1) when
  scope, decisions or checkpoint status changes, and at session/stop
  boundaries; it is not a per-commit transcript.
- At session/stop boundaries, clean or promote the session's `build/` output
  under the [retention policy](../PERFORMANCE.md#evidence-retention), then
  replace HANDOFF with latest-session changes, verification and immediate
  operational context. Keep command chronology in evidence.
