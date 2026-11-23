# NamiSync Working Rules

These rules always apply. Start each session with [HANDOFF](docs/HANDOFF.md),
then the focused document for the task. Situational procedures live in
[docs/procedures/](docs/procedures/); read one when its trigger below applies.

| Procedure | Read when |
| --- | --- |
| [SCOPE](docs/procedures/SCOPE.md) | A formal batch or register row, a finding outside active scope, a scope or ownership question, or any stop or recovery |
| [CLOSEOUT](docs/procedures/CLOSEOUT.md) | Before each commit, and at every session or stop boundary |
| [DOCUMENTS](docs/procedures/DOCUMENTS.md) | Before creating or editing a document in `docs/`, README or CHANGELOG |

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
- **Root authority:** `RootAuthority` is reviewed evidence, never lasting
  authorization; consumers admit under their own policies. Held-root reuse of
  admission follows [ARCHITECTURE §3.3](docs/ARCHITECTURE.md#33-root-authority)
  and [DEFENSE §2.1](docs/DEFENSE.md#21-supported-environment-and-trusted-computing-base).
- **Ingress:** bound complete external requests before constructing
  interface/presentation values. All external adapters follow
  [BRIDGE.md](docs/BRIDGE.md)'s ingress contract, including its equal-or-stricter
  bound for future adapters.

## Structure

| Path | Responsibility and permitted project imports |
| --- | --- |
| `namisync/core/` | Contracts, session state/events, path safety, root evidence and protocols; standard library only. |
| `namisync/modules/` | Isolated domain components; import contracts from core, never sibling components. Files within one component package may collaborate behind its facade. |
| `namisync/db/` | Persistence, repositories and history observer; imports core; sole main-ledger writer. |
| `namisync/workflows/` | Only place domain modules meet; imports core, modules and db. |
| `namisync/dispatcher/` | Domain-blind admission, custody, control and event fan-out; imports core only. |
| `namisync/interfaces/` | CLI/API/desktop adapters; access workflows and dispatcher through composition; no domain policy. `branding/` holds the app icon's SVG masters as package data. |
| `tests/` | Pytest coverage following package boundaries. |
| `tools/` | Development utilities in purpose folders listed in [TOOLS](docs/TOOLS.md); their fixtures, archives and run output go in `build/`. |
| `build/` | Ignored working output and work in progress, kept free of lasting dependencies under the [retention policy](docs/procedures/CLOSEOUT.md#evidence-retention). Authored studies, proposals and plans go in `docs/`; work files go nowhere else. |
| `evidence/` | Tracked, validated records promoted at session closeout under the [retention policy](docs/procedures/CLOSEOUT.md#evidence-retention). |

`lint-imports` enforces the import law through the contracts in `pyproject.toml`.

## Routing

Use the relevant route, not a mandatory full-document reading sequence:

- Component work: its focused document in `docs/`. [EXECUTOR.md](docs/EXECUTOR.md)
  owns package/effect boundaries and the settlement stability gate;
  [VERIFIER.md](docs/VERIFIER.md) owns engine/native boundaries;
  [DATABASE.md](docs/DATABASE.md) owns persistence and placement requirements.
- Cross-layer/contracts work: [ARCHITECTURE.md](docs/ARCHITECTURE.md) owns the
  import law and contract-to-source locator. Exact shared shapes are source-owned
  under core; prefer explicit dataclasses and typed functions.
- Safety, bugfix boundaries or quantitative claims: [DEFENSE.md](docs/DEFENSE.md).
  Under §2.5 a new defense needs a demonstrably plausible trigger. Under §7,
  classify consequence and enforceability before choosing the lowest sufficient
  evidence tier; a measured diagnostic, target or drift guard is not acceptance,
  and observations stay separate from contracts/validators.
- Measurement methods, fixtures, profiles, samples and results:
  [PERFORMANCE.md](docs/PERFORMANCE.md); component documents own their criteria.
- Adapter/host/lifecycle work: [INTERFACES.md](docs/INTERFACES.md); command/event
  transport and ingress: [BRIDGE.md](docs/BRIDGE.md); tree/search/sort/selection
  and scale: [PRESENTATION.md](docs/PRESENTATION.md).
- UI and icons: [DESKTOP_UI.md](docs/DESKTOP_UI.md); icon assets or catalog
  servicing use the tooling and maintenance guidelines in [TOOLS.md](docs/TOOLS.md).
- Product scope: [FEATURES.md](docs/FEATURES.md); M1 checkpoints and decisions:
  [M1_PLAN.md](docs/M1_PLAN.md). Accepted future outcomes remain binding, but
  unrealized representation, reservation, DTO and command-count recipes are
  reconsidered at first use; retain only narrow admission and measured scale
  obligations with named owners.

## Implementation And Verification

- Default to a small change unless the user asks for a formal plan. Apply the
  relevant checks, tests, documentation, adversarial review and concise
  changelog entry without a permanent worksheet or register for each fix. The
  user owns classification; agents impose no size threshold or eligibility
  rubric. When work crosses architectural ownership, public contracts, safety
  guarantees or multiple independently deliverable outcomes, explain the
  concrete boundary and ask the user to formalize it. Existing authorization persists.
- Make only task-relevant changes; avoid speculative features and adjacent
  refactors. Remove only orphans/artifacts created by this task, preserving
  unrelated work. Keep build outputs, caches, virtual environments, databases
  and sync trash out of Git.
- Commit as you go: each commit is a small, self-contained unit that reverts
  independently, staged by path with only this task's files. Recovery or `wip`
  commits at a stop are exempt. Push and merge need an explicit request.
- Use `NamiSync`, Python package and console executable `namisync`, and GUI
  executable `namisync-gui`; never `nami_sync`. Use lowercase snake_case modules
  and clear domain type names. Persist root-relative paths independent of drive
  letters; filesystem APIs may use `pathlib.Path` with long-path-safe handling.
- Use native PowerShell and prefer the project venv created with the selected
  release interpreter in [TOOLS.md](docs/TOOLS.md#portable-build-preparation).
  Do not introduce CMD, Bash, Git Bash or WSL unless requested or technically
  necessary.
- Follow [TESTS.md](docs/TESTS.md) for test scope, execution, probe containment
  and bounded failure diagnostics. `tests/_departments.py` owns exact primary
  module assignment; do not duplicate its catalogs in prose. Departments do not
  prove blast radius: add direct consumer departments for public contracts and
  use the ordinary suite when impact is broad or uncertain. Routine tests need
  no one watching memory; inspect resource evidence for failures or a named
  resource gate.
- Import component public APIs through their facades; patch internal collaborators
  in the owning submodule. For fixes, identify a reproducer first when practical;
  add focused tests for new core behavior.
- Documentation-only work needs consistency, link and diff checks; product
  tests are needed when it changes an executable contract or test authority.

### Execution priorities

1. **Work by mechanism.** Trace owners and direct consumers, including fixtures
   and external helpers. Classify the failure before fixing its family; scope
   follows the accepted outcome, not a file list.
2. **Check the real seam early.** Run existing affected composition/native cases
   before broad gates. Add no separate preflight suite or protocol.
3. **Settle inputs before acceptance.** Finish writers and reconcile review
   corrections before freezing. Serialize shared source, tests and validators.
4. **Reuse evidence by dependency.** Changed product, producer, checker or driver
   dependencies invalidate their evidence. Retain unaffected passes and failed
   receipts; unchanged product bytes alone are insufficient.
5. **Keep one current decision record.** The delivery register owns
   scope/decisions, HANDOFF owns resumption context, and evidence owns
   chronology. Update those owners; do not add parallel checklists or
   stop/resume transcripts.

## Stops

- New findings do not add scope; only the user may change active scope.
  [SCOPE](docs/procedures/SCOPE.md) owns findings, scope decisions and recovery.
- Always stop, preserve exact state and report evidence of supported-path data
  loss/corruption, unauthorized or out-of-root mutation, supported security or
  hard-wall escape, false durable/terminal success, duplicate/replayed mutation,
  or inability to preserve/recover current work.
- On the **second unplanned instance of one causal mechanism**, or **third
  unplanned substantive defect** in a pass/checkpoint, finish only the current
  safety-preserving atomic outcome, begin no further instance fix, and follow
  SCOPE's [recurrence pause](docs/procedures/SCOPE.md#recurrence-pause).
