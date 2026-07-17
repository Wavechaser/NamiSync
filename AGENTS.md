# NamiSync Working Rules

## Project Goal

Build a Windows 11 x64 headed desktop app for safe one-way file mirroring.
Users review a dry-run plan before execution; location inventory, integrity
verification, history, and the desktop UI are part of the active product, not
future placeholders. Core sync behavior remains outside the GUI so it can be
reused by CLI, queue, or service entry points.

## Directory Conventions

- `namisync/core/`: contracts, session state, events, path safety, and protocol
  shapes. It imports only the Python standard library.
- `namisync/modules/`: scanner, planner, preflight, executor, and verifier. It
  imports `core`; modules do not import one another.
- `namisync/db/`: recorder, repositories, schemas, and the history observer. It
  imports `core` and is the sole writer of the main ledger.
- `namisync/workflows/`: sync and integrity workflow coordination. It is the
  only layer where modules meet and may import `core`, `modules`, and `db`.
- `namisync/dispatcher/`: domain-blind session admission, custody, control, and
  event fan-out. It imports `core`, never modules or workflows.
- `namisync/interfaces/`: CLI, API, and desktop adapters. It imports workflows
  and the dispatcher through the composition root and owns no domain policy.
- `tests/`: pytest tests mirroring package boundaries where practical.
- Active focused documentation lives in `docs/`:
  - `FEATURES.md` for all planned and existing features.
  - `ARCHITECTURE.md` for project architectural decisions and design principles. 
  - `HANDOFF.md` for the latest session only: changes made, verification, and
    immediate next-session operational context. Replace it each session rather
    than accumulating project-level reference material.
- Superseded planning material lives in `docs/obsolete/`; it remains readable
  for historical context but must not describe current behavior or guide new
  implementation.
- `README.md` at the repository root is the project-level README, package
  readme, active documentation index, roadmap/future directions, and changelog.
- `AGENTS.md` stays at the repository root as the repository instruction file.

## System Integrity Principles

These are product invariants. Preserve them unless the task explicitly changes
their contract, and update the matching tests and documentation when it does.

- **Operational safety:** filesystem changes follow an explicit reviewed plan;
  destructive behavior stays guarded, scoped, and visible to the user.
- **Atomicity:** publish copied files atomically on the target volume, and only
  record durable state after the corresponding filesystem operation succeeds.
- **Idempotency:** repeated scans and immediate reruns must converge on an
  accurate no-op or near-no-op plan. Preserve stable metadata and timestamps
  where they support that result.
- **Feature orthogonality:** planning/execution, inventory/integrity, history,
  and UI presentation have distinct responsibilities. Do not make one feature
  silently reinterpret, duplicate, or invalidate another feature's state.
- **Discrete layering:** `core` defines contracts; `modules` implement isolated
  domain operations; `db` owns persistence; `workflows` are the only place
  modules meet; `dispatcher` is domain-blind; and `interfaces` adapt workflows
  and sessions. Dependencies follow the import law in `ARCHITECTURE.md`; UI code
  does not decide sync behavior or reach around workflows.

## Naming Conventions

- Python modules use lowercase snake_case.
- Dataclasses, enums, and public types use clear domain names:
  `RootMapping`, `FileRecord`, `ScanResult`, `SyncOptions`, `SyncPlan`,
  `PlanOperation`, `ProgressEvent`, and `RunResult`.
- Relative paths stored by the app are root-relative strings. Filesystem APIs
  may use `pathlib.Path`, but persisted paths must not depend on a drive letter.
- Deletion policies are named `trash`, `additive`, and `mirror`; `trash` is the
  default user-facing policy.
- Use `NamiSync` as the product name, `namisync` as the Python package and
  module name, and `nami-sync` as the command-line executable. Never use
  `nami_sync`.

## Implementation Rules

- Keep the minimum code that solves the current phase. Do not add speculative
  features, extension points, or broad refactors.
- Make surgical changes. Every changed line should trace to the current task.
- Prefer explicit dataclasses and typed functions over implicit dictionaries for
  core contracts.
- Use `sqlite3` directly. Do not add an ORM.
- Keep live SQLite databases local only. Do not place app DBs in cloud-synced
  folders.
- Use WAL mode for the main database.
- Commit database state only after successful filesystem operations.
- Preserve timestamps on copied files so reruns can stay stable.
- Hide or guard `mirror` deletion until the rest of the safety model is proven.

## Windows Rules

- The target platform is native Windows 11 x64.
- Use PowerShell syntax for project commands.
- Prefer Python 3.13 from the project virtual environment.
- Do not introduce WSL, Bash, Git Bash, or CMD workflows unless explicitly
  requested or technically necessary.
- Use long-path-safe handling where code touches filesystem paths.

## Testing And Verification

- Use pytest.
- For bug fixes, write or identify a reproducing test first when practical.
- For new core behavior, add focused tests in the matching test area.
- Document behavioral changes in the module-specific document in `docs/` in
  the same change: GUI, database, scanner, planner, executor, history, or
  another focused document as appropriate. Update or create that focused
  document when a component has no adequate coverage.
- Also update `README.md` whenever a change affects the product overview,
  features, safety model, limitations, documentation index, roadmap, or other
  cross-cutting/user-visible behavior. Keep superseded material in
  `docs/obsolete/` rather than leaving it as active guidance.
- Run the narrowest relevant verification after each change, then broader tests
  before considering a phase complete.
- Before declaring work complete, review the result for requirement drift,
  brittle assumptions, security risks, hidden edge cases, and unnecessary
  complexity.

## Commit Readiness

- Before any future commit, review whether the relevant files under `docs/`,
  `docs/obsolete/`, `README.md`, or `AGENTS.md` need updates for the committed
  behavior.
- Do not commit behavior changes whose matching documentation is stale.
- When committing or pushing a versioned update, add a concise entry to the
  README changelog describing the user-meaningful change.

## Cleanup

- Remove only unused imports, variables, files, or generated artifacts created
  by the current change.
- Do not remove unrelated dead code or reformat adjacent files opportunistically.
- Keep generated build outputs, caches, virtual environments, databases, and
  sync trash out of Git.
