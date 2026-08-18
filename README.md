# NamiSync

NamiSync is a safety-first, one-way file mirroring application for Windows 11
x64. It is for people maintaining a backup, archive, media collection, or
working-tree replica who want to see exactly what will happen before granting
filesystem mutations. It is deliberately not a bidirectional conflict resolver
or an unattended deletion engine.

Every sync scans both sides, builds a deterministic dry-run plan, and requires
explicit human review and exact confirmation. The plan captures deletion,
filter, preservation, and casing policy; execution then rechecks roots, volume
identity, capacity, file types, metadata, and dependencies immediately before
touching files. Copies use a bounded pipeline and atomic target-volume
publication, and completed mutations reach the local WAL-backed ledger only
after the corresponding filesystem operation succeeds.

NamiSync also keeps an inventory of known locations and XXH3-128 integrity
evidence for baseline, verification, and explicit rebaseline workflows. Its
independent activity history and separate filesystem, integrity, ledger, and
audit result axes prevent one failure from being hidden behind another result.

The implemented core has been adversarially hardened and regression-tested
against root, junction, and remount redirection; source/target substitution and
review-to-execution drift; incomplete or hostile scans; case, Unicode,
reserved-name, device-path, and long-path ambiguity; partial publication and
retry/pause/cancel failures; recorder and SQLite contention; malformed stored
or interface data; and dispatcher custody/lifecycle races. When safety evidence
is missing or contradictory, NamiSync refuses or defers the affected work and
reports the residual truth instead of guessing.

The full data-preservation guarantee assumes managed roots are not being
changed by other software while NamiSync is mutating them. Observable drift is
refused or reported, but a writer that wins after a final path-based guard is a
documented external-writer boundary. The supported assumptions, tolerance
classes, and exact residual dispositions live in the defense model.

## Current state

M1's headless product is implemented and usable through the service and CLI:
reviewed sync, inventory, integrity baseline/verify/rebaseline, optional
post-copy verification, and retained history. The Windows desktop shell now has
a secured WebView2 host, bounded command/event transport, native folder picking,
and the Fluent/accessibility foundation. User-facing workflow views and
controls, final packaging, and beta closure remain open, so the window is not
yet the complete desktop product.

M1 state remains process-local: queued sessions and unexecuted plans do not
survive an application restart, and committed nonterminal history returns only
as `incomplete`. The active database boundary is ledger v3 plus history v5;
older, missing, transitional, or mismatched databases are refused and the two
local database files must be reset together before creating a fresh pair.

## Setup and dependencies

NamiSync requires Windows 11 x64 and Python 3.13 or later. Runtime dependencies
are `xxhash` 3.x and the reality-tested `pywebview` 6.2.1 host stack.
Development dependencies are `pytest` and `import-linter`.

Create a virtual environment, then install the editable development package:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the tests and check the import boundaries:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\lint-imports.exe
```

Focused, departmental, cross-department neighborhood, ordinary, and complete/
headed verification commands are defined in [Tests](docs/TESTS.md).

M1's desktop host additionally requires Microsoft Edge WebView2 Runtime.
Declaring pywebview does not make explicit CLI commands initialize a GUI; the
Stage 6 host contract performs a read-only runtime preflight before window
creation, then refuses pywebview's silent older-engine fallback with an install
action and no fallback-time registry writes.

## Command line

Review and, only after typing the exact confirmation, execute a one-way sync:

```powershell
nami-sync sync C:\Source D:\Target
nami-sync sync C:\Source D:\Target --verify-after-copy
```

Refresh or check one explicit location:

```powershell
nami-sync inventory E:\Archive
nami-sync baseline --location-id 12
nami-sync verify E:\Archive --path Photos\keeper.jpg
nami-sync rebaseline E:\Archive --path Photos\keeper.jpg --accept-current-evidence
```

Browse retained history or one run in detail:

```powershell
nami-sync history
nami-sync history RUN_TOKEN
```

`trash` is the default deletion policy; `additive` is public, while `mirror`
remains guarded and hidden. There is no `--yes` bypass. Location commands
require exactly one root or `--location-id`; repeatable `--path` values are
exact root-relative selections and clone ambiguity requires `--mount`.

Ledger and history default to separate files under `%LOCALAPPDATA%\NamiSync`.
Sync and location commands accept isolated `--database` and
`--history-database` paths. The sibling `settings.json` supplies semantic
defaults; an explicit deletion-policy option overrides that plan only.

Clean full/no-op runs return `0`; input/refusal/failure/cancel/partial/degraded/
mismatch/verification-incomplete use codes `2` through `9`. The selected code
never hides the other result axes in rendered output.

## What is deliberately not promised yet

- No user-facing desktop workflow-control surface, durable plan/session queue,
  or restart-resume; the current headed page remains a secured transport
  bootstrap boundary with its production event drain available to later views.
- No cross-process desktop task visibility, background integrity, concurrent
  file execution, general database migration, backup, or history retention.
- No automatic execution or bypass of reviewed-plan confirmation.
- No supported elevated desktop host; standard-integrity startup is the
  defense baseline, and enforced elevated-launch refusal remains beta work.

## Documentation

- [Tests](docs/TESTS.md) — verification levels, department routing, markers,
  and diagnostic commands.
- [Defense model](docs/DEFENSE.md) — supported assumptions, threat ceiling,
  hard walls, tolerance policy, measurement authority, and residual-risk
  decisions.
- [Architecture](docs/ARCHITECTURE.md) — system layers, contracts, and milestone order.
- [M1 plan](docs/M1_PLAN.md) — M1 decisions, integration gates, and Stage 6 scope.
- [Desktop UI](docs/DESKTOP_UI.md) — current WebView2 desktop delivery contract.
- [M1 Bridge](docs/M1_BRIDGE.md) — sole Stage 6 bridge protocol and BR-G acceptance authority.
- [M1 Shell](docs/M1_SHELL.md) — Stage 6 slice order, host/package placement, packaging, and SH-G map.
- [Command line](docs/COMMANDLINE.md) — commands, review, output, and exits.
- [Executor](docs/EXECUTOR.md) — guarded filesystem mutation, pipeline, and recovery.
- [Inventory](docs/INVENTORY.md), [Verifier](docs/VERIFIER.md), and
  [Workflows](docs/WORKFLOWS.md) — retained location evidence and orchestration.
- [Database](docs/DATABASE.md), [Recorder](docs/RECORDER.md), and
  [History](docs/HISTORY.md) — local persistence and audit behavior.
- [Features](docs/FEATURES.md), [Bugs](docs/BUGS.md), and
  [Handoff](docs/HANDOFF.md) — present and future scope, known issues, and session context.
- [Detailed changelog](CHANGELOG.md) — dated task history grouped by milestone
  or version and phase.
- [Development tools](docs/TOOLS.md) — measurement tooling, the
  executor/verifier harness, deterministic corpora, and the settlement oracle.

## Changelog

Detailed task history and dates live in [CHANGELOG.md](CHANGELOG.md). This
README intentionally stops at milestone and phase summaries.

## M1

M1 expands the reviewed-sync runtime into a complete headless integrity,
history, and workflow product while building its secured headed WebView2 shell.

### M1 Hardening

Safety, settlement, authority, and measurement work made high-risk release
claims explicit, independently reviewable, and regression-backed.

### M1 Maintenance Refactor

Shared root authority, stable executor/verifier package boundaries, an oracle-
guarded typed settlement reducer, and layered test operations made internal
ownership explicit without changing public or persisted contracts.

### M1 GUI

Stage 6 delivered the secured desktop host, command/event transport, design
foundation, and bounded presentation core; later workflow surfaces and beta
packaging remain future phases.

### M1 Features

Stages 1–5.5 delivered the headless reviewed-sync, inventory/integrity, history,
CLI, and reusable workflow product plus its development measurement tooling.

## M0

M0 established the reusable headless reviewed-sync baseline and its explicit-
plan safety model.

### M0 Hardening

Filesystem and reporting edge cases were hardened without weakening explicit
review or guarded execution.

### M0 Features

The first milestone shipped reviewed one-way sync through reusable core,
runtime, persistence, workflow, and CLI layers.
