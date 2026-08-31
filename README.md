# NamiSync

NamiSync is a safety-first, one-way file mirroring application for Windows. 
It is for people maintaining a backup, archive, media collection, or
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
Canonical hash inputs and boundary text require valid Unicode. Malformed
optional scan-warning detail is omitted without losing the warning or valid
observations; required text is refused rather than silently rewritten.

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
the Fluent/accessibility foundation, and dormant gallery-proven sync/integrity
file-list row renderers. User-facing workflow views and controls, final packaging, and beta
closure remain open, so the window is not yet the complete desktop product.

The Stage 6 second-half reslice covers Setup, bounded plan and execution review,
inventory/integrity, process-live multi-session tasks, and early lifecycle/
retention closure. Its exact core-event-v5, recording, signed-64 scalar, full-
width Windows file-identity, and coordinated persistence epoch are active;
the plan session now refuses independent raw-population excess and final
retained shallow-reference excess before publishing a partial plan. External
inputs are validated and bounded at ingress, populations remain independently
bounded at every applicable rung, reentrant collaborators receive only
immutable values after reliable local state is committed, and exact immutable
first-party module results are validated once at their named workflow adoption
transfer and then shared by identity with read-only consumers. Only the private
exact plan-limit signal carrying the active same-run admission token and an
exact PLAN fact becomes typed `REFUSED+UNRUN`; inventory uses a distinct private
signal and token. Ordinary lookalikes plus tokenless, different-run, or wrong-
scope exact signals retain failure truth without saving a plan. Reflective token
extraction or mutation remains outside the supported fault model.
Python bridge responses now stop at an exact 8 MiB canonical-JSON occurrence
wall before native construction; drains commit only the longest admitted update
prefix, and native positions remain charged through worker exit and exact
browser receipt. Construction, sorting, indexes, previews, representation-
specific native/browser bytes, and complete task graphs remain accepted but
unrealized M1 model work alongside the product surfaces and task lifecycle.
The repeated 120,000-item population walls serve one M1 performance-and-safety
support target in each applicable population. Existing independently owned
first-excess behavior remains active through M1; NamiSync makes no support
promise above that scale, but does not claim that item 120,001 is a failure
threshold.

Accepted but unrealized M1 behavior also includes server-owned filename/size/
mtime sibling sorting for plan and inventory views, with path-key order for new
views and reset; sorting changes neither selection nor execution authority.
Rebaseline will also create evidence for selected files that lack it, while
remaining explicit hash-and-replace rather than compare-and-accept. See the
[H2 plan](docs/M1_SHELL_H2.md) and
[integrity policy table](docs/VERIFIER.md#accepted-standalone-operation-policy).

M1 state remains process-local: queued sessions and unexecuted plans do not
survive an application restart, and committed nonterminal history returns only
as `incomplete`. Continuations stay in live session records; the session store
receives a separate metadata/result projection without a continuation field.
A durable metadata store alone cannot provide restart/resume. The active
database boundary is ledger v4 plus history v6 at
shared data epoch 6. This includes a reset from epoch 5 despite unchanged schema
numbers. Older, one-present, markerless, transitional, mismatched,
incomplete/poisoned, or orphan-sidecar pairs are refused. Admission checks
WAL-visible markers and schema without changing source artifacts; any journal
entry refuses. Both local database mains and their SQLite sidecars must be
archived or deleted together before creating a fresh pair. Startup never does
this automatically; resetting loses app evidence and history, not managed files.

## Compatibility

| Windows version / arch | NamiSync Core | Desktop shell (.NET FW) | Binary dependencies | Appearance | **Compatibility** |
|---|:--:|:--:|:--:|:--:|---|
| **Windows 11 x64** | ✅ | ✅ | ✅ | ✅ | ✅ **actively serviced** |
| **Windows 11 ARM64 (native)** | ✅ | ❌ | ❌ | — | ❌ shell & dependencies blocked |
| **Windows 11 ARM64 (emulation)** | ✅ | ⚠️ | ✅ | ⚠️ | ⚠️ runs (emulated) |
| **Windows 10 (x86, < 1709)** | ❌ | ✅ | ⚠️ | ⚠️ | ❌ backend floor |
| **Windows 10 (x86, ≥ 1709)** | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ runs with reduced appeareance |
| **Windows 10 (x64, < 1709)** | ❌ | ✅ | ✅ | ⚠️ | ❌ backend floor |
| **Windows 10 (x64, ≥ 1709)** | ✅ | ✅ | ✅ | ⚠️ | ⚠️ runs with reduced appeareance |

**Legend:** ✅ works · ⚠️ works reduced · ❌ blocked · — unreachable (blocked upstream in same row)

- **Backcompatibility:** NamiSync is designed on and for Windows 11 x64, but
  the engine is written to be version- and architecture-neutral and is therefore
  compatible with Windows 10 and is ARM64 ready. However, database pairing currently
  uses POSIX semantics with no fallback, therefore requiring Windows 10 to be newer
  than **version 1709/build 16299**. 
- **WebView2:** not natively included in Windows 10, and therefore requires one-time
  Evergreen runtime install (x86/x64/ARM64 all exist); it is included in-box on
  Windows 11. Runtime support on *very* old Win10 (< 1607) is unverified.
- **Appearance:** Mica needs build ≥ **22621** (Windows 11 22H2). Windows 11 21H2 and
  all Windows 10 fall back to an opaque window *by design* ([appearance.py:114](namisync/interfaces/web/appearance.py#L114)).
  The header's persisted System/Light/Dark choice drives both native material
  and page tokens; active high contrast still follows Windows without changing
  that stored choice. Proper downgrading is accounted for, NamiSync will run,
  just uglier.
- **Shell / ARM block:** the `netfx` pin + `require_supported_pythonnet_runtime()`
  refusal ([pywebview_runtime.py:44](namisync/interfaces/web/pywebview_runtime.py#L44))
  anchor the shell to .NET Framework, which has no native ARM64 build. Native
  ARM64 is therefore refused by dependencies.
- **x64 emulation on WoA:** works with potentially reduced performance. XXH3 could
  potentially see up to 50% performance loss, but actual loss should be negligible
  given its speed. Non-native I/O may see 10-20% throughput loss depending on
  exact situation. UI operations should be similar to native, but cold startups may
  take longer due to emulator translations.

## Setup and dependencies

NamiSync requires Windows 11 x64 and Python 3.13 or later. The package declares
no Python upper bound; exact runtime profiles in project evidence identify
measured configurations rather than launch admission. Runtime dependencies are
`xxhash` 3.x and the reality-tested `pywebview` 6.2.1 host stack.
Development dependencies are `pytest` and `import-linter`. The ordinary test
suite also requires a Node.js executable for the packaged Progress validator;
provide it through `NAMISYNC_TEST_NODE` or `PATH` as described in
[Tests](docs/TESTS.md).

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

## Commandline

Refer to the [CLI documentation](docs/COMMANDLINE.md) for full command, review,
and stopcodes. 

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

- [Architecture](docs/ARCHITECTURE.md) — system layers, contracts, and milestone order.
- [Features](docs/FEATURES.md), [Bugs](docs/BUGS.md), and [Threat Model](docs/DEFENSE.md) — 
  present and future scope, known issues, and supported assumptions, tolerance policy, 
  measurement authority.

- [Commandline](docs/COMMANDLINE.md) — commands, review, output, and exits.
- [Database](docs/DATABASE.md), [Recorder](docs/RECORDER.md), and
  [History](docs/HISTORY.md) — local persistence and audit behavior.
- [Desktop UI](docs/DESKTOP_UI.md) — current WebView2 desktop delivery contract.
- [Executor](docs/EXECUTOR.md) — guarded filesystem mutation, pipeline, and recovery.
- [Inventory](docs/INVENTORY.md), [Verifier](docs/VERIFIER.md), and
  [Workflows](docs/WORKFLOWS.md) — retained location evidence and orchestration.
- [Tests](docs/TESTS.md) — verification levels, department routing, markers,
  and diagnostic commands.
- [Detailed changelog](CHANGELOG.md) — dated task history grouped by milestone
  or version and phase.
- [Development tools](docs/TOOLS.md) — measurement tooling, the
  executor/verifier harness, deterministic corpora, and the settlement oracle.

- [Handoff](docs/HANDOFF.md) — immediate operational context.
- [M1 plan](docs/M1_PLAN.md) — M1 decisions, integration gates, and Stage 6 scope.
- [M1 Bridge](docs/M1_BRIDGE.md) — sole Stage 6 bridge protocol and BR-G acceptance authority.
- [M1 Shell](docs/M1_SHELL.md) — Stage 6 slice order, host/package placement, packaging, and SH-G map.
- [M1 Stage 6 second-half checklist](docs/M1_SHELL_H2.md) — current detailed acceptance, review, and verification plan.

Historical criteria are collected in the [retrospective M0 plan](docs/obsolete/M0_PLAN.md).
The [imported PoC documents](docs/obsolete/PoC_import/) are archived alongside it.
These are historical sources, not current acceptance authority; active component
contracts and the M1 plans govern current work.

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
foundation, bounded presentation core, dormant sync/integrity file-list row
renderers, and a persisted native/page theme override over the refrozen
cosmetic-state channel. The remaining second-half product/task contracts
are accepted but unrealized, and the exact event-v5/data-epoch-6 protocol cut
is active. Product surfaces and beta packaging remain open.

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
