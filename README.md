# NamiSync
A safety-first, one-way file mirroring app for Windows. NamiSync performs source to target syncs, database-based maintenance, and integrity tracking features. 

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
- [`DESIGN_REVIEW.md`](docs/DESIGN_REVIEW.md): unresolved inconsistencies and
  safety decisions found while hardening module contracts.
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
