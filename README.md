# NamiSync
A safety-first, one-way file mirroring app for Windows. NamiSync performs source to target syncs, database-based maintenance, and integrity tracking features. 

## Development status

The integrity operation module is implemented and directly testable: it
supports baseline, verify, explicit rebaseline, pause/cancel continuation, and
cache-honest Windows unbuffered reads. The end-user integrity workflow remains
an M1 integration task because inventory refresh, persisted integrity history,
dispatcher registration, and interface composition are separate layers.
M1 also replaces bulk content evidence with fixed XXH3-128 and pipelines each
normal copy's read/write/hash stages under one combined 32 MiB byte budget.
Copy chunks are fixed at 256 KiB below 8 MiB, 1 MiB below 32 MiB, and 4 MiB
thereafter. The same refactor adds conditional temp preallocation, sequential
cache hints, hoisted Windows bindings, one pre-publish temp flush, and
conditional metadata repair. File-level execution/verification workers,
batching, direct copy IO, and cross-file publish overlap remain deferred until
new measurements justify them. Internal plan, custody, history, and database
identity hashes remain SHA-256.

M1's optional post-execution verification is one execute→verify state machine
inside the same session and volume custody. Successful copy/update/move-update
publishes hand transient attestations directly to readback even if ledger
recording degraded; filesystem, integrity, recording, and audit remain
independent result axes. Same-process pause preserves explicit phase and
published-evidence continuation, while application-restart recovery remains M2.

The M0 dispatcher is also implemented: generic sessions run concurrently when
their resource sets are disjoint, serialize when they overlap, use real
cross-process Windows mutex custody, support cooperative pause/resume/cancel,
and expose bounded replay plus timeout-guarded audit delivery. Its session table
is intentionally process-local until the M2 SQLite queue/reconciliation phase.

The M0 scanner, planner, and preflight modules are implemented as a headless
pipeline surface. Scans retain deterministic typed filesystem evidence and
explicit completeness; planning is pure, correspondence-aware, dependency
ordered, and byte-stable; hostile filesystem names become escaped incomplete-
scan evidence instead of aborting review. Exact-case and NFC/NFD filename-form
mismatches remain visible as non-blocking advisories while their ordinary
update/no-op work continues; the unexposed opt-in casing policy uses a zero-byte
rename when content already matches. Preflight separates scoped read-only
observation from exhaustive typed judgment.

The M1 contract foundation is now implemented. `worker_count` and execution's
false live-settings drift check are gone, so admitted runs consume only their
reviewed immutable policy snapshot. Schema-versioned semantic defaults live in
database-owned `settings.json` with named-mutex-serialized partial commits;
cosmetic recents/window/column/sort state lives separately in interface-owned
`ui-state.json`. The measured `xxhash` 3.x runtime is now a declared project
dependency, while the content producers remain unchanged until their atomic
Stage 2 switch. A security spike proves the future pywebview host can force
Edge Chromium, install native WebView2 navigation/new-window guards, recheck
the packaged origin on its single versioned `dispatch`, and return application
data structurally without executing JavaScript text. The desktop host itself
still waits for M1 Stage 6.

The M0 persistence implementation remains the operational base: a serialized run-bound recorder
is the only main-ledger writer; versioned WAL schemas retain role-free inventory,
mapping correspondence, runs, and distinct observed/attested evidence; typed
repositories are read-only; and an independent history observer stores sync
envelopes, summaries, and ordered operations, including blocked/deferred safe-
subset exclusions. The active schema boundary is now ledger v2/history v3:
history reserves generic phase-tagged item and phase-summary storage, while the
existing sync observer writes operation/execute tags and no phase rows yet.
Ledger v1 and history v1/v2 are refused without mutation and require manual
deletion/reset of the local database files. The actual XXH3-128 producer switch
still lands atomically for executor and verifier in Stage 2, after which local
development databases must be recreated. General migrations, backup, and
cross-process-coordinated retention remain later phases.

The M0 reviewed-sync slice is runnable end to end. The workflow layer joins
scanner, planner, repeated preflight, executor, ledger recorder, dispatcher,
and independent history without crossing package boundaries. The CLI exposes
the two-session `sync` review/commit/execute flow and read-only `history`
browsing through both `nami-sync` and `python -m namisync`. Blocked items no
longer refuse independent work: review commits a quarantined safe subset,
incomplete scans allow guarded additive/no-op work while withholding moves and
deletions, and history itemizes every blocked/deferred exception.

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

## Command line

Review and, only after typing the exact confirmation, execute a one-way sync:

```powershell
nami-sync sync C:\Source D:\Target
```

Browse retained history or one run in detail:

```powershell
nami-sync history
nami-sync history RUN_TOKEN
```

`trash` is the default deletion policy; `additive` is also public, while
`mirror` remains hidden. Ledger and history default to separate files under
`%LOCALAPPDATA%\NamiSync`; `sync` accepts `--database` and
`--history-database` overrides for isolated runs. There is no `--yes` bypass.
Completed safe-subset runs with blocked or deferred items return exit code `6`
and print `completed with exceptions`; clean full/no-op runs return `0`.

## Documentation

- [`BUGS.md`](docs/BUGS.md): current substantive defect log and fix status.
- [`FEATURES.md`](docs/FEATURES.md): settled and latent product behavior.
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): system structure, contracts, and
  milestone order.
- [`DESIGN_REVIEW.md`](docs/DESIGN_REVIEW.md): resolved decision ledger from
  hardening the architecture and module contracts.
- [`M1_PLAN.md`](docs/M1_PLAN.md): detailed M1 decision record, dependency
  sequence, integration gates, and adversarial acceptance tests.
- [`HASH_REFACTOR.md`](docs/HASH_REFACTOR.md): measured single-file pipeline,
  fixed adaptive chunk policy, Windows finalization refactor, and canonical
  XXH3-128 content-evidence plan for M1.
- [`CORE.md`](docs/CORE.md): shared types, session/event contracts, path safety,
  identity, time, and evidence.
- [`SCANNER.md`](docs/SCANNER.md): filesystem observation and completeness.
- [`PLANNER.md`](docs/PLANNER.md): deterministic intent and dependency planning.
- [`PREFLIGHT.md`](docs/PREFLIGHT.md): scoped observation and pure execution
  judgment.
- [`EXECUTOR.md`](docs/EXECUTOR.md): guarded filesystem mutation and recovery.
- [`INVENTORY.md`](docs/INVENTORY.md): role-free retained location evidence.
- [`VERIFIER.md`](docs/VERIFIER.md): baseline, verification, and rebaseline.
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

- Landed M1 Stage 1 contracts and semantics: removed `worker_count` and
  execution-time settings drift refusal, added the shared streaming-hasher
  protocol and compatible `xxhash` dependency, activated ledger v2/history v3
  with explicit reset-only stale schema handling and reserved generic history
  storage, split semantic/UI state persistence, and proved the hostile-
  navigation structured WebView2 bridge boundary.
- Made rename review truthful: recase, move, and move-update rows now show the
  observed prior target path changing to the planned target path, including
  visible case-only changes such as `keep.txt -> KEEP.txt`.
- Fixed crashed-copy temp recovery: successful executions now sweep exact
  prior-run temps once from preflight's touched target parents before copying,
  while preserving current-run temps, lookalikes, untouched paths, and trash.
- Hardened filename handling without suppressing sync work: invalid names become
  typed incomplete-scan evidence, surrogates cannot reach canonical encoding,
  and unique case-only or NFC/NFD filename-form differences are explicit
  non-blocking advisories. Target spelling is preserved by default; a
  fingerprinted, currently unexposed option can propagate source basename
  casing with a zero-byte, no-trash rename when content already matches.
- Made every fingerprinted plan-request option mandatory on decode and extended
  malformed-surrogate-safe JSON encoding to ledger idempotency hashes, history
  hashes/detail, and opaque workflow payloads while preserving valid Unicode.
- Added safe partial sync: blocked work is itemized and quarantined, incomplete
  scans are additive-only, independent work and no-op correspondence refreshes
  continue, and CLI/history report blocked or deferred items with a distinct
  partial exit.
- Hardened Windows execution: same-run empty-directory cleanup accepts only
  child-induced metadata churn, parent-directory flushing requests the required
  write access, and retried multi-step operations resume from durable sub-steps.
- Fixed planner no-ops for standard-attribute changes, so readonly, hidden, and
  system drift now produces an update.
- Hardened plan admission and Windows scan identity: plan fingerprints are
  recomputed before commitment validation, unsafe database locations are refused
  before confirmation, preflight results render reliably, and NTFS identity has
  an exact-path fallback.
- Implemented the M0 workflow/composition and CLI slice: versioned dispatcher
  payloads, two-session plan/commit/execute, fresh execution preflight, volume
  custody, ledger recording, independent history browsing, real process entry
  points, and isolated database overrides.
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
