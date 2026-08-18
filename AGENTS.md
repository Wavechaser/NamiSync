# NamiSync Working Rules

## Project Goal

Build a Windows 11 x64 headed desktop app for safe one-way file mirroring.
Users review a dry-run plan before execution; location inventory, integrity
verification, history, and the desktop UI are part of the active product, not
future placeholders. Core sync behavior remains outside the GUI so it can be
reused by CLI, queue, or service entry points.

## Directory Conventions

- `namisync/core/`: contracts, session state, events, lexical path safety,
  ephemeral root-authority evidence, and protocol shapes. It imports only the
  Python standard library. Shared root-authority code probes and classifies;
  it does not cache freshness, persist bindings, or decide module policy.
- `namisync/modules/`: scanner, planner, preflight, executor, and verifier. A
  domain component may be one module or a package. Files inside one component
  package may import one another; component roots do not import sibling domain
  components and import project contracts only from `core`.
- `namisync/modules/executor/`: the executor component package. `__init__.py`
  is the stable public facade; `runtime.py` owns operation policy, dispatch,
  final-touch guards, retries, the typed effect journal, cancellation,
  recording, settlement, and outcomes; `native.py` owns Windows filesystem
  primitives, metadata, handles, publication, trash, and root-authority
  adaptation; `pipeline.py` owns the bounded one-file read/hash/write flow,
  teardown, metrics, and `CopyDigest` production. `native.py` and `pipeline.py`
  are independent leaves and never import `runtime.py` or one another.
- `namisync/modules/verifier/`: the verifier component package. `__init__.py`
  is the stable public facade; `engine.py` owns classification, progress,
  recording, and verifier policy; `native.py` owns the Windows cache-honest,
  handle-bound reader and native bindings and never imports `engine.py`.
- `namisync/db/`: recorder, repositories, schemas, and the history observer. It
  imports `core` and is the sole writer of the main ledger.
- `namisync/workflows/`: sync and integrity workflow coordination. It is the
  only layer where modules meet and may import `core`, `modules`, and `db`.
- `namisync/dispatcher/`: domain-blind session admission, custody, control, and
  event fan-out. It imports `core`, never modules or workflows.
- `namisync/interfaces/`: CLI, API, and desktop adapters. It imports workflows
  and the dispatcher through the composition root and owns no domain policy.
- `namisync/interfaces/web/assets/icons/`: fixed local monochrome icon assets
  selected from pinned `@fluentui/svg-icons@1.1.334`. Upstream filenames,
  exact package/file URLs, version, per-file SHA-256 hashes, and MIT license
  stay with the assets.
  Runtime registration, remote loading, generated SVG/path markup, and
  data-derived asset paths are forbidden; adding an icon is a source change to
  the fixed registry, CSS mask class, provenance, package manifest, and tests.
- `tests/`: pytest tests mirroring package boundaries where practical.
- Active focused documentation lives in `docs/`:
  - `DEFENSE.md` for supported assumptions, trusted boundaries, hard walls,
    tolerance policy, quantitative-evidence authority, and residual-risk
    dispositions.
  - `BUGS.md` for substantive defects, verified fixes, and current status.
  - `FEATURES.md` for all planned and existing features.
  - `ARCHITECTURE.md` for project architectural decisions and design principles. 
  - `HANDOFF.md` for the latest session only: changes made, verification, and
    immediate next-session operational context. Replace it each session rather
    than accumulating project-level reference material.
- Superseded planning material lives in `docs/obsolete/`; it remains readable
  for historical context but must not describe current behavior or guide new
  implementation.
- `README.md` at the repository root is the project-level README, package
  readme, active documentation index, roadmap/future directions, and concise
  milestone/phase changelog summary.
- `CHANGELOG.md` at the repository root is the detailed task history, grouped
  by milestone or released version and then by phase.
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
- Treat `RootAuthority` as reviewed evidence, never as a lasting authorization
  token. Consumers must re-probe at their existing point of use; scanner,
  preflight, executor, and verifier retain their distinct admission and outcome
  policies.
- Keep executor effects typed and operation-local. Publication, metadata, and
  non-byte mutation effects are orthogonal journal entries whose settlement is
  reduced centrally; do not reintroduce parallel ad-hoc state dictionaries or
  sibling-specific settlement branches.
- Treat executor settlement restructuring as gated work. Before splitting the
  executor or replacing its retained-state dictionaries with a journal or
  reducer, the corrected monolith must pass the committed settlement oracle
  three times with identical normalized traces, no skipped or unclassified
  scenarios, no snapshot drift, and no unresolved settlement finding. Land any
  discovered policy fix separately with a persistent regression, then reset
  and repeat the stability gate. Keep the oracle and its baseline under
  `tools/` through the full refactor; do not delete them in the split, journal,
  reducer, verifier, or test-consolidation commits.
- Use `sqlite3` directly. Do not add an ORM.
- Keep live SQLite databases local only. Do not place app DBs in cloud-synced
  folders.
- Bound every externally reachable request before constructing interface or
  presentation values. The desktop bridge limits the complete serialized
  command envelope to 65,536 UTF-8 bytes; any future non-bridge external
  adapter must impose an equal-or-stricter complete-request bound at its own
  ingress rather than relying on a field-level presentation limit.
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
- Follow `docs/TESTS.md` for focused, departmental, neighborhood, ordinary,
  and complete/headed verification. `tests/_departments.py` is the executable
  authority for exact primary module ownership; keep prose free of parallel
  module or case catalogs.
- Departments route primary ownership rather than proving complete blast
  radius. Add consumer departments explicitly for changed public contracts,
  and use the ordinary repository suite when impact is broad or uncertain.
- Import component public APIs through the component facade. Tests that inject
  or patch an internal collaborator patch the submodule that owns the symbol,
  not a facade re-export.
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

## Measurement Authority

- Follow `docs/DEFENSE.md` §7 for quantitative-claim classification,
  enforceability, evidence tiers, and protected-authority requirements. A
  target, diagnostic, or drift guard does not become acceptance evidence merely
  because it was measured rigorously.
- Classify the consequence and production-enforceability of a claim before
  selecting the lowest sufficient tier; keep observation separate from the
  predeclared contract and validator.
- Record exact fixtures, profiles, scaling axes, aggregation or retention,
  artifacts, and rerun triggers in the owning component document.
  `docs/TESTS.md` governs test scope and execution, not measurement authority.

## Commit Titles

- Start every commit title with a category using
  `<category>(<optional-scope>): <imperative summary>`.
- Use the narrowest primary category: `feat`, `fix`, `perf`, `test`, `docs`,
  `refactor`, `build`, or `chore`. The optional lowercase scope names the owning
  component, such as `web`, `executor`, or `dispatcher`; omit it when the change
  is genuinely cross-cutting.
- Keep one coherent checkpoint per commit. The title describes the commit's
  primary effect even when matching tests and documentation travel with it.

## Commit Readiness

- Before any future commit, review whether the relevant files under `docs/`,
  `docs/obsolete/`, `README.md`, or `AGENTS.md` need updates for the committed
  behavior.
- Do not commit behavior changes whose matching documentation is stale.
- Update `CHANGELOG.md` when a task-level delivery is complete. Before adding a
  new task, first decide whether the session advances an existing task; extend
  that task's date range and concise summary when it does. Create a new task
  only when no existing entry accurately fits the outcome. Update the README
  summary only when its milestone or phase synopsis changes.

## Documentation Maintenance

- Keep both changelogs newest-first. README contains only `##` milestone or
  released-version summaries and `###` phase summaries; it never lists task
  details. `CHANGELOG.md` repeats those two levels and adds dated `####` task
  entries with concise bullets describing what happened.
- Before named releases, use milestone headings such as `M1`. After versioning,
  use the version and codename, such as `v0.1.0 "Gertrud"`. Group related
  sessions under one task and put post-delivery work in the relevant hardening
  phase rather than appending it to the original feature task.
- Keep `docs/DEFENSE.md` as the normative owner of supported assumptions,
  trusted boundaries, hard walls, tolerance classes, quantitative-evidence
  authority, residual-risk dispositions, and model-reopen triggers. Other
  documents link to that policy and own their mechanisms or behavior; they do
  not restate its tables or accept a residual merely by describing it.
- Keep `docs/ARCHITECTURE.md` limited to durable decisions, contracts,
  layering, coordination, invariants, type/protocol meaning, and milestone-level
  direction. Dated build status, acceptance results, exact measurement evidence,
  and module implementation walkthroughs belong in the changelog, active
  delivery plan, or owning module document. Architecture defines a shared
  contract's meaning and invariants; the owning symbol under `namisync/core/`
  defines its exact standardized fields, enum values, inheritance, protocols,
  and signatures; module documents explain use and extension policy without
  redefining that shape. Keep the architecture contract-to-source locator
  current, and reproduce exact shapes only when the shape itself explains an
  architectural decision. `docs/FEATURES.md` owns product behavior and states
  whether behavior is active or unrealized without carrying milestone build
  recaps.
- Keep `docs/BUGS.md` as a concise module-first defect ledger. A category is a
  reusable causal class stated as a short noun phrase (for example, `TOCTOU
  parent redirection` or `shutdown ownership race`), not the incident's observed
  behavior, affected filename, milestone, review gate, test outcome, or broad
  consequence. Assign severity from the worst supported product consequence,
  not from the importance of the audit or gate that found it. Target 6–12
  rendered lines per entry, retaining only the consequence, cause, fix, and
  essential residual boundary or test context.

## Cleanup

- Remove only unused imports, variables, files, or generated artifacts created
  by the current change.
- Do not remove unrelated dead code or reformat adjacent files opportunistically.
- Keep generated build outputs, caches, virtual environments, databases, and
  sync trash out of Git.
