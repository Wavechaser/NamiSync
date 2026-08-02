# NamiSync

NamiSync is a safety-first, one-way file mirroring application for Windows 11
x64. It scans a source and target, presents a deterministic dry-run plan, and
only changes files after explicit human review and exact confirmation. It keeps
inventory and XXH3-128 integrity evidence, records completed work in a local
ledger, and retains independent activity history.

The product is designed to be cautious rather than clever: it never silently
guesses a destructive action, rechecks reviewed intent before touching files,
publishes copied files atomically on the target volume where supported, and
keeps filesystem, integrity, ledger-recording, and history-audit outcomes as
separate facts.

## Current state

M1 Stages 1–5.5 are implemented. The headless sync, inventory, integrity,
history, dispatcher, and service/CLI surfaces are usable; M1 Stage 6, the
headed local WebView2 desktop, is next. The desktop's service facade and bridge
security foundation already exist, but no GUI host has shipped.

M1 state is process-local: queued sessions and unexecuted plans do not survive
an application restart. The active database boundary is ledger v2 plus history
v3. Older, missing, transitional, or mismatched databases are refused; close
NamiSync and reset both local database files together before creating a fresh
matching pair.

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

M1's future desktop additionally requires Microsoft Edge WebView2 Runtime.
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

- No headed desktop host, durable plan/session queue, or restart-resume.
- No cross-process desktop task visibility, background integrity, concurrent
  file execution, general database migration, backup, or history retention.
- No automatic execution or bypass of reviewed-plan confirmation.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system layers, contracts, and milestone order.
- [M1 plan](docs/M1_PLAN.md) — M1 decisions, integration gates, and Stage 6 scope.
- [Desktop UI](docs/DESKTOP_UI.md) — current WebView2 desktop delivery contract.
- [Command line](docs/COMMANDLINE.md) — commands, review, output, and exits.
- [Executor](docs/EXECUTOR.md) — guarded filesystem mutation, pipeline, and recovery.
- [Inventory](docs/INVENTORY.md), [Verifier](docs/VERIFIER.md), and
  [Workflows](docs/WORKFLOWS.md) — retained location evidence and orchestration.
- [Database](docs/DATABASE.md), [Recorder](docs/RECORDER.md), and
  [History](docs/HISTORY.md) — local persistence and audit behavior.
- [Features](docs/FEATURES.md), [Bugs](docs/BUGS.md), and
  [Handoff](docs/HANDOFF.md) — present and future scope, known issues, and session context.

## Changelog

### M1

- Completed the Stage 6 pywebview reality spike on CPython 3.13.14 and
  pywebview 6.2.1: native guards now attach only on the WinForms UI thread,
  dispatch authorization follows native WebView2 document state across
  canceled navigation, attachment failures are observable, frame navigation
  and popup/browser escape paths are closed, hardened settings and the actual
  Edge Chromium renderer are verified, WebView2 absence is refused through a
  read-only pre-window probe before pywebview can import its mutating MSHTML
  fallback, full asset URLs derive exact origins, and the security-relevant
  host dependency is pinned. The headed desktop itself remains unshipped.
- Completed the integrated M1 adversarial review across execution,
  inventory/integrity, persistence, dispatcher/history, facade concurrency,
  and strict persisted/bridge protocols. Straightforward invariant violations
  are closed with permanent regressions; an atomic history-finalization
  ownership decision now keeps timeout audit truth identical live and after
  reopen. Operation-safe pause after a durable retry sub-step remains the
  explicit design decision in `BUGS.md`. The Stage 6 desktop shell remains next.
- Landed the Stage 5.5 facade bridge: deterministic workflow trees and opaque
  ids, recursive inventory scope with bounded missing inference, revisioned
  user selection with payload-safe provenance, concurrent retry-safe facade
  commands, typed scan warnings, and folder-scoped integrity that continues
  visibly past unreadable subjects. The integrated bridge also closes stale
  replan intent, resumed-ledger settlement, and irreversible-update
  confirmation failures. Stage 6 presentation paging and the desktop host
  remain next.
- Delivered Stages 1–5 of the integrity product and executor refactor; the
  WebView2 desktop shell remains M1 Stage 6.
  - **Executor:** switched content evidence to XXH3-128 and added the bounded
    reader/hasher/writer pipeline, adaptive chunks, conditional preallocation,
    and leaner Windows publish/finalization paths.
  - **Workflows:** added role-free inventory, standalone baseline/verify/
    rebaseline, and optional in-session execute-to-verify readback.
  - **Interfaces:** added the shared service facade, explicit location CLI
    commands, semantic-settings views, typed result classification, and the
    WebView2 bridge-security foundation.
  - **Persistence:** established the reset-only ledger v2/history v3 boundary
    under the `m1-ledger-xxh3-128` ledger contract and separated semantic
    settings from cosmetic UI state.

### M0 Hardening

- Hardened the reviewed-sync baseline against filesystem drift and unsafe edge
  cases without weakening its explicit-plan safety model.
  - **Planning and scanning:** hardened fingerprints, database placement,
    built-in artifact ignores, hostile filenames, incomplete scans, and
    case/Unicode filename handling.
  - **Execution:** added exact prior-run temp recovery and hardened Windows
    updates, directory cleanup, metadata preservation, and retry behavior.
  - **Reporting:** made blocked/deferred safe subsets and partial outcomes
    explicit in review, history, and CLI exit classification.

### M0

- Shipped the headless reviewed-sync product and its reusable layered runtime.
  - **Core sync:** added scanning, deterministic planning, fresh preflight, and
    guarded Windows copy/update/delete execution with atomic publication.
  - **Runtime:** added dispatcher volume custody, cooperative controls, typed
    events/results, local ledger recording, and independent activity history.
  - **Access:** added workflow composition and the `nami-sync` CLI for reviewed
    sync and history browsing.
