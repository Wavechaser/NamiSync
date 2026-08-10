# NamiSync Session Handoff

Date: 2026-08-10
Branch: `milestone1`

## Session Outcome

Closed the four actionable LOW findings selected from `M1_AUDIT_DSV4.md` and
made the agreed opportunistic defensive cleanups. No schema or workflow-payload
version changed.

- Planner and executor now consume one core-owned Windows managed-attribute
  mask: readonly, hidden, system, and not-content-indexed. Full raw attribute
  evidence remains intact, while ARCHIVE/TEMPORARY-only drift converges to
  `NOOP` instead of scheduling an update the executor cannot reproduce.
- A copied UPDATE backup now binds the reviewed live-target snapshot to pre/post
  stats from one open read handle and to the exact copied byte count. Detectable
  growth, truncation, or same-size metadata drift publishes neither the backup
  nor the update; prepublication cleanup retains the existing owned-path guards.
- Serialized SQLite retry classifies only primary `BUSY`/`LOCKED` result codes,
  including extended-code masking. Message text can no longer delay or
  misclassify another operational error.
- Core path validation now rejects `CONIN$`, `CONOUT$`, and the documented
  superscript-one/two/three COM/LPT aliases with the same case/extension rules as
  other DOS devices.
- Workflow payload JSON rejects `NaN` and positive/negative `Infinity`; recorder
  corruption/malformed-noop paths raise typed rollback-safe errors; one dead
  private dispatcher timeout override was removed without changing hub policy.
- Active documentation now distinguishes these fixes from intentional LOW
  behavior and deferred work, including physical verifier progress, fail-closed
  orphan cleanup, retained recovery backups, schema-v3 defensive constraints,
  startup/reset boundaries, preflight observation cost, and Stage 6 task-owned
  process-artifact release.

## Verification

- Combined changed-area regression gate: `520 passed, 1 skipped`.
- Complete pytest gate: `1354 passed, 2 skipped`.
- Import linter: `8 kept, 0 broken` across 50 files and 189 dependencies.
- Python package compilation and `git diff --check` passed.
- Two independent code/test reviews and one documentation review found no
  remaining implementation blocker after the reviewed target-snapshot repair,
  extended `LOCKED` coverage, rollback assertions, and active-document fixes.

## Immediate Next Context

- The LOW audit review is closed for M1. `docs/M1_AUDIT_DSV4.md` remains
  unchanged as point-in-time evidence; deferred notes do not require immediate
  implementation.
- Stage 6 task close still needs one facade-owned release of linked plan,
  selection, execution/inventory detail, view/session, and receipt artifacts,
  plus repeated create/close bounded-registry tests. `close_session()` alone
  intentionally does not claim that broader ownership today.
- A future ledger schema revision may tighten raw-SQL attestation/identity
  constraints and defensive reads. A persistent multi-process service should
  add a database-pair initialization gate. Neither warrants a v3 schema change
  during this delivery.
- Trash retention/purge, invocation-scoped preflight observation optimization,
  and a reusable verifier chunk-buffer contract remain profile- or
  maintenance-driven work. Failed UPDATE recovery backups must not be deleted
  opportunistically by executor failure handling.
- Copied-backup drift proof remains metadata/stat based. A deliberate mutation
  that restores all reviewed evidence remains inside the documented external-
  writer inference boundary and would require stronger handle/share semantics
  or byte revalidation to close.
