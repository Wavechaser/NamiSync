# NamiSync Working Rules

## Product And Integrity

Build a Windows 11 x64 headed app for safe one-way file mirroring. Users review
an explicit dry-run plan before execution. Inventory, integrity verification,
history and desktop presentation are product responsibilities; sync behavior
stays outside the GUI for reuse by other entry points.

Preserve these invariants unless the user explicitly changes their contract,
with matching tests and documentation:

- **Operational safety:** filesystem changes follow an explicit reviewed plan;
  destructive behavior stays guarded, scoped, and visible to the user.
- **Atomicity:** publish copied files atomically on the target volume, and only
  record durable state after the corresponding filesystem operation succeeds.
- **Idempotency:** repeated scans and immediate reruns must converge on an
  accurate no-op or fire the same pending action. Preserve stable metadata and
  timestamps where they support that result.
- **Feature orthogonality:** planning/execution, inventory/integrity, history,
  and UI presentation have distinct responsibilities. Do not make one feature
  silently reinterpret, duplicate, or invalidate another feature's state.
- **Discrete layering:** `core` defines contracts; `modules` implement isolated
  domain operations; `db` owns persistence; `workflows` are the only place
  modules meet; `dispatcher` is domain-blind; and `interfaces` adapt workflows
  and sessions. Dependencies follow the import law in `ARCHITECTURE.md`; UI code
  does not decide sync behavior or reach around workflows.
- `RootAuthority` is point-of-use evidence, never lasting authorization. Consumers
  re-probe under their own admission/outcome policies. Shared core code probes
  and classifies; it does not cache freshness, persist bindings or decide policy.
- Bound complete external requests before constructing interface/presentation
  values. All external adapters follow [BRIDGE.md](docs/BRIDGE.md)'s ingress
  contract, including its equal-or-stricter bound for future adapters.

## Structure And Task Routing

| Path | Responsibility and permitted project imports |
| --- | --- |
| `namisync/core/` | Contracts, session state/events, path safety, root evidence and protocols; standard library only. |
| `namisync/modules/` | Isolated domain components; import contracts from core, never sibling components. Files within one component package may collaborate behind its facade. |
| `namisync/db/` | Persistence, repositories and history observer; imports core; sole main-ledger writer. |
| `namisync/workflows/` | Only place domain modules meet; imports core, modules and db. |
| `namisync/dispatcher/` | Domain-blind admission, custody, control and event fan-out; imports core only. |
| `namisync/interfaces/` | CLI/API/desktop adapters; access workflows and dispatcher through composition; no domain policy. |
| `tests/` | Pytest coverage following package boundaries. |
| `tools/` | Development utilities; temporary fixtures, archives and evidence go in ignored `build/`. |

Use the relevant routes below, not a mandatory full-document reading sequence:

- Component work: read its focused document in `docs/`. In particular,
  [EXECUTOR.md](docs/EXECUTOR.md) owns package/effect boundaries and the settlement
  stability gate; [VERIFIER.md](docs/VERIFIER.md) owns engine/native boundaries;
  [DATABASE.md](docs/DATABASE.md) owns persistence and placement requirements.
- Cross-layer/contracts work: [ARCHITECTURE.md](docs/ARCHITECTURE.md) owns the
  import law and contract-to-source locator. Exact shared shapes are source-owned
  under core; prefer explicit dataclasses and typed functions.
- Safety, bugfix boundaries, or quantitative claims: [DEFENSE.md](docs/DEFENSE.md), 
  including §7 for evidence authority. Diagnostics, targets and drift guards are not
  acceptance merely because they were measured. Classify consequence and enforceability
  before choosing the lowest sufficient tier; keep observations separate from
  contracts/validators. Record fixtures, profiles, scaling, aggregation/retention,
  artifacts and rerun triggers in the owning component doc, not TESTS.md.
- Adapter/host/lifecycle work: [INTERFACES.md](docs/INTERFACES.md); command/event
  transport and ingress: [BRIDGE.md](docs/BRIDGE.md); tree/search/sort/selection
  and scale: [PRESENTATION.md](docs/PRESENTATION.md).
- UI and icons: [DESKTOP_UI.md](docs/DESKTOP_UI.md); icon assets or catalog servicing
  should use the tooling and maintenance guidelines documented in [TOOLS.md](docs/TOOLS.md).
- Product scope: [FEATURES.md](docs/FEATURES.md); checkpoints:
  [M1_PLAN.md](docs/M1_PLAN.md), the sole active M1 delivery register. Accepted
  future outcomes remain binding, but unrealized representation, reservation,
  DTO and command-count recipes are reconsidered at first use; retain only
  narrow admission and measured scale obligations with named owners.

## Implementation And Verification

- Make only task-relevant changes; avoid speculative features and adjacent
  refactors. Remove only orphans/artifacts created by this task, preserving
  unrelated work. Keep build outputs, caches, virtual environments, databases
  and sync trash out of Git.
- Use `NamiSync`, Python package `namisync`, and executable `nami-sync`; never
  `nami_sync`. Use lowercase snake_case modules and clear domain type names.
  Persist root-relative paths independent of drive letters; filesystem APIs
  may use `pathlib.Path` with long-path-safe handling.
- Use native PowerShell and preferably Python 3.13 from the project venv. Do not
  introduce CMD, Bash, Git Bash or WSL unless requested or technically necessary.
- Follow [TESTS.md](docs/TESTS.md) for test scope and execution.
  `tests/_departments.py` owns exact primary module assignment; do not duplicate
  its catalogs in prose. Departments do not prove blast radius: add direct
  consumer departments for public contracts and use the ordinary suite when
  impact is broad or uncertain.
- Import component public APIs through their facades; patch internal collaborators
  in the owning submodule. For fixes, identify a reproducer first when practical;
  add focused tests for new core behavior.
- Run focused checks and required broader gates. Repeat passed checks only when
  edits, failures or changed seams invalidate evidence. Documentation-only work
  needs consistency, link and diff checks; product tests are needed when it
  changes an executable contract or test authority.

## Task Containment And Recovery

These boundaries apply with or without a skill. Execution skills define the
investigation, interaction, delegation and recovery procedure; they cannot
expand authority or relax repository gates.

### Scope And Completion

- Before audit-driven implementation, hardening/stabilization, cross-component
  work or multiple independently committable outcomes, record a closed register
  in the owning delivery doc: stable ids, accepted outcomes, status, named
  verification, non-goals and task-specific stops. Quantified criteria require
  a finite domain, procedure and terminal observation; discovery may instead
  close over a named corpus/method without authorizing fixes.
- Before implementing a pending row, declare its finite production/test/doc
  population, owners/seams, acceptance gate, atomic commit boundary, relevant
  archived dispositions and a regression study. Scope is the accepted outcome
  and mechanism/verification boundary, not file/line count. Record newly found
  direct consumers before editing; routine in-bound choices need no new approval.
  Explicit exclusions remain binding.
- Continue through implementation, correction of introduced regressions, required
  tests/docs and final adversarial review of every checkpoint. Completion means
  every accepted row passes its named gate without regressing the declared
  baseline. Resolve routine ambiguity from contracts and state material
  assumptions; ask when an outcome or boundary changes.
- Next-checkpoint design may overlap the predecessor's final implementation and
  verification, but stays read-only toward product/tests and cannot weaken or
  delay its gate. Record the inspected revision and revalidate changed seams
  against the integrated predecessor. Dependent implementation waits for its
  completion and active user scope; a future outcome or ready plan is not authority.

### Findings And Scope Decisions

- New findings do not add scope. Regressions are lost guarantees, false states,
  unauthorized/duplicate effects or newly unbounded work; test color alone proves
  neither their presence nor absence. Correct introduced regressions before a
  mergeable commit. A bounded pre-existing substantive defect may receive a
  separate fix commit only while no stop rule applies; log and defer other
  verified findings. A blocked gate with no authorized remedy needs adjudication.
- Only the user may change active scope. Suspend dependent work when an outcome,
  architectural ownership, safety/effect model or mechanism/verification boundary
  changes; do not split off a non-atomic commit to evade that boundary. Before a
  scope-only full stop, investigate a finite corpus covering cause, owners,
  dependencies and consumers (including external test helpers), preserved
  guarantees and verification. Present one coherent proposal, not successive
  first-failure additions. Investigation does not authorize implementation.
- A narrow understood extension preserving outcome and ownership/safety may seek
  an explicit in-turn decision. Larger architectural changes, unresolved
  boundaries or changed safety/effects require a full stop and reviewable redesign.
  Existing approval persists. While a decision is pending, only independent
  authorized work may continue. No answer within a bounded response window means
  stop and recover, never consent. Always-stop rules override investigation/waiting.
- On the **second unplanned instance of one causal mechanism**, or **third
  unplanned substantive defect** in a pass/checkpoint, finish only the current
  safety-preserving atomic outcome and begin no further instance fix. Produce a
  mechanism table of consequences, owners and common choke point (or why none
  exists); reorganize and obtain review before resuming. Narrow reorganization
  may use in-turn adjudication, never waive the pause/review. Count mechanisms
  semantically, not by BUGS category spelling. Predeclared finite migrations
  are exempt from this recurrence rule.

### Mandatory Stops And Preservation

- Always stop, preserve exact state and report evidence of supported-path data
  loss/corruption, unauthorized or out-of-root mutation, supported security or
  hard-wall escape, false durable/terminal success, duplicate/replayed mutation,
  or inability to preserve/recover current work. Broad checkpoints may add
  narrower stops with precise consequences/transitions before work starts;
  only the user may expand them during a checkpoint.
- If stopping before a merge-ready commit, preserve only task-owned changes on
  an isolated disposable recovery branch with provenance, scope, verification
  and excluded-work details sufficient for exact resumption. Never absorb or
  destroy unrelated work. Recovery commits are not review units: never merge or
  cherry-pick them as-is. Rebuild useful changes into coherent verified commits;
  remove recovery refs only after review, integration and full accounting.

## Commits And Documentation

- One coherent checkpoint per mergeable commit, including its tests and matching
  documentation. Review relevant docs, obsolete material, and AGENTS for updates
  before committing; stale behavior documentation blocks readiness.
- Use `<category>(<optional-scope>): <imperative summary>` with the narrowest of
  `feat`, `fix`, `perf`, `test`, `docs`, `refactor`, `build`, `chore`; scope is a
  lowercase owning component, omitted for cross-cutting work. `wip` is recovery-
  only, never on integration branches; its temporary readiness exemption does
  not make it mergeable.
- Update/create the owning component doc with behavior changes. Update README
  for product, safety, limitations, roadmap or documentation-index changes.
  At task delivery, extend the matching CHANGELOG task/date range or add a new
  task when none fits; update README's summary only if its phase/milestone
  synopsis changes. Replace HANDOFF with latest-session changes, verification
  and immediate operational context. 

## Documentation Maintenance

Active subject documents live in `docs/`; superseded plans belong in
`obsolete/` and must not guide current implementation. Root `AGENTS.md` owns
repository execution boundaries. Root `README.md` remains the product/package
readme, documentation index, roadmap and concise milestone/phase changelog;
this file owns editing conventions, not a second product index.

Read the section relevant to the document being edited. Update a subject's
existing owner rather than creating parallel authority or copying its rules
into every consumer document.

### Subject Ownership

- [ARCHITECTURE.md](ARCHITECTURE.md) owns durable decisions, contracts, layering,
  coordination, invariants, type/protocol meaning and milestone direction.
  Exact fields, enums, inheritance, protocols and signatures belong to the
  owning core symbol. Keep the contract-to-source locator current; reproduce
  exact shapes only when needed to explain an architectural decision. Module
  docs explain use/extension policy without redefining shapes. Put dated
  status, acceptance results, measurements and implementation walkthroughs in
  the changelog, delivery plan or owning component document.
- [DEFENSE.md](DEFENSE.md) is normative for supported assumptions, trusted
  boundaries, hard walls, tolerances, quantitative evidence, residual-risk
  dispositions and model-reopen triggers. Other documents link to its policy
  and describe their own mechanisms; they do not restate its tables or accept
  a residual merely by describing it.
- [FEATURES.md](FEATURES.md) owns product behavior and distinguishes active
  from unrealized outcomes, without milestone build recaps.
- [BUGS.md](BUGS.md) owns substantive defects and its entry conventions. Keep
  entries module-first, roughly 6–12 rendered lines, retaining consequence,
  cause, fix and essential residual/test context. Categories name reusable
  causal mechanisms; severity follows the worst supported product consequence,
  not the audit or gate that found it.
- [M1_PLAN.md](M1_PLAN.md) is the sole active M1 delivery register. Archive
  superseded plan ancestry rather than maintaining parallel current authorities.
- [HANDOFF.md](HANDOFF.md) covers only the latest session: changes, verification
  and immediate operational context. Replace it rather than accumulating a
  project reference or transcript; retain necessary resumption/evidence pointers.
- Superseded material are placed in `docs/obsolete/`. They are historical references, 
  not current implementation guidance.

### Changelogs

Both root changelogs are newest-first. README has only `##` milestone/release
and `###` phase summaries, never task entries. CHANGELOG repeats those levels
and adds dated `####` tasks with concise delivery bullets. Before named releases,
use milestone headings such as `M1`; afterward use version and nickname, such as
`v0.1.0 "Gertrud"`.

Before adding a task, decide whether the session advances an existing one;
extend its date range and summary when it does. Put post-delivery work in the
relevant hardening phase rather than appending it to the original feature task.
Update README's changelog synopsis only when the milestone/phase summary changes.
