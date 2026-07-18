# NamiSync
A safety-first, one-way file mirroring app for Windows. NamiSync performs source to target syncs, database-based maintenance, and integrity tracking features. 

## Development status

The integrity operation module is implemented and directly testable: it
supports baseline, verify, explicit rebaseline, pause/cancel continuation, and
cache-honest Windows unbuffered reads. The end-user integrity workflow remains
an M1 integration task because inventory refresh, persisted integrity history,
dispatcher registration, and interface composition are separate layers.

The M0 dispatcher is also implemented: generic sessions run concurrently when
their resource sets are disjoint, serialize when they overlap, use real
cross-process Windows mutex custody, support cooperative pause/resume/cancel,
and expose bounded replay plus timeout-guarded audit delivery. Its session table
is intentionally process-local until the M2 SQLite queue/reconciliation phase.

The M0 scanner, planner, and preflight modules are implemented as a headless
pipeline surface. Scans retain deterministic typed filesystem evidence and
explicit completeness; planning is pure, correspondence-aware, dependency
ordered, and byte-stable; preflight separates scoped read-only observation
from exhaustive typed judgment. Workflow and interface composition remain
separate M0 integration work.

The M0 persistence foundation is implemented: a serialized run-bound recorder
is the only main-ledger writer; versioned WAL schemas retain role-free inventory,
mapping correspondence, runs, and distinct observed/attested evidence; typed
repositories are read-only; and an independent history observer stores sync
envelopes, summaries, and ordered operations. Migrations, backup/retention,
hash import, richer history detail, and workflow/interface composition remain
later phases.

## Development setup

NamiSync requires Python 3.13 or later. Create and activate a virtual
environment, then install the development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Check the architectural import boundaries with:

```powershell
.\.venv\Scripts\lint-imports.exe
```

## Documentation

- [`FEATURES.md`](docs/FEATURES.md): settled and latent product behavior.
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): system structure, contracts, and
  milestone order.
- [`DESIGN_REVIEW.md`](docs/DESIGN_REVIEW.md): resolved decision ledger from
  hardening the architecture and module contracts.
- [`CORE.md`](docs/CORE.md): shared types, session/event contracts, path safety,
  identity, time, and evidence.
- [`SCANNER.md`](docs/SCANNER.md): filesystem observation and completeness.
- [`PLANNER.md`](docs/PLANNER.md): deterministic intent and dependency planning.
- [`PREFLIGHT.md`](docs/PREFLIGHT.md): scoped observation and pure execution
  judgment.
- [`EXECUTOR.md`](docs/EXECUTOR.md): guarded filesystem mutation and recovery.
- [`INVENTORY.md`](docs/INVENTORY.md): role-free retained location evidence.
- [`VERIFIER.md`](docs/VERIFIER.md): baseline, verification, and rebaseline.
- [`HASH_IMPORT.md`](docs/HASH_IMPORT.md): safe TeraCopy SHA-256 import.
- [`INGEST.md`](docs/INGEST.md): latent metadata-sorted media ingest workflow.
- [`RECORDER.md`](docs/RECORDER.md): sole main-ledger write path.
- [`DATABASE.md`](docs/DATABASE.md): schemas, repositories, migrations, and data
  protection.
- [`HISTORY.md`](docs/HISTORY.md): independent activity history observer/store.
- [`DISPATCHER.md`](docs/DISPATCHER.md): generic sessions, custody, control, and
  event delivery.
- [`WORKFLOWS.md`](docs/WORKFLOWS.md): cross-module sequencing.
- [`INTERFACES.md`](docs/INTERFACES.md): shared adapter rules.
- [`COMMANDLINE.md`](docs/COMMANDLINE.md): CLI commands, review, output, and exit
  behavior.
- [`DESKTOP_UI.md`](docs/DESKTOP_UI.md): headed Windows interaction contract.
- [`HANDOFF.md`](docs/HANDOFF.md): latest session state and verification only.

## Changelog

### Unreleased

- Implemented the guarded M0 Windows executor for every planned operation kind,
  including atomic copy/update publication, trash-on-update recovery, exact temp
  ownership, typed continuation, bounded retries, progress, and copy evidence.
- Implemented the integrity verifier operation with baseline, verification,
  explicit rebaseline, conditional evidence commands, lossless pause/cancel
  continuation, and cache-honest Windows unbuffered reads.
- Implemented the M0 domain-blind dispatcher, shared session runner/event
  contracts, bounded audit-aware subscriptions, and abandoned-holder-safe
  Windows resource custody.
- Implemented M0 scanner, deterministic planner, and scoped preflight modules
  with shared Windows path/evidence contracts, exact artifact handling,
  correspondence-qualified moves, explicit directory dependencies, shared
  capacity accounting, and typed stale-plan refusal coverage.
- Implemented the M0 recorder/database foundation with frozen ledger/history
  schemas, a run-bound serialized sole writer, idempotent sync evidence,
  scalable inventory and conditional integrity transactions, read-only typed
  repositories, bounded cross-process retry, and minimal independent sync
  history.
