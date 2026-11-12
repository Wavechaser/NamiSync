# NamiSync

NamiSync is an open-source Windows application for reviewed one-way file
mirroring, persistent file inventory and content integrity checking. It is
intended for maintaining collections such as photographs, media libraries,
project archives and files on backup drives.

Choose what to copy, inspect the changes, and confirm the plan. Afterward,
NamiSync keeps a database-backed record of your files and their integrity
evidence for later checks.

## Features

### Persistent inventory

Inventory works independently of sync pairs. Catalog a location
on its own, without assigning it a source or target partner. Revisit what was
observed, search and filter the inventory, and see missing or reappearing files
alongside their integrity evidence. The records live in a local SQLite database
and survive application restarts.

A scan updates observations without silently replacing an established integrity
baseline. An incomplete scan or an offline drive does not turn unseen files into
confirmed deletions, including when a removable drive is disconnected or a scan
cannot finish.

### Reviewed copying

Every sync starts with a dry run. Review the proposed operations, search and
filter the tree, and choose the files you want to include before confirming.
NamiSync checks the selected work again before execution and reports files that
have changed since review.

Copies are published atomically on the destination volume. Replaced target
versions are preserved in local trash by default, and removal uses trash by
default too. Pause, resume and cancel controls keep long operations manageable;
per-file results make partial completion visible.

### Integrity checking

NamiSync hashes content as it copies and offers a separate readback verification
step. New desktop tasks enable automatic verification by default. You can also
establish a baseline for an existing collection, verify selected files later,
or explicitly accept changed content as a new baseline.

XXH3-128 provides fast content fingerprints for detecting accidental changes.
The inventory keeps current observations separate from recorded hash evidence,
so a fresh scan does not replace a baseline with changed content.
These fingerprints are integrity evidence, not cryptographic authentication.

### How the features fit together

Folder synchronization, collection catalogs and checksum tools each solve useful
parts of this problem. For example, [FreeFileSync](https://freefilesync.org/manual.php?topic=synchronization-settings)
offers folder synchronization with database-assisted change detection, while
[digiKam](https://www.digikam.org/about/features/) offers database-backed photo
collections across local, removable and network media.

NamiSync combines reviewed mirroring, an independent persistent inventory and
repeatable integrity verification for general files. These share workflows and
stored evidence, so copying a collection and checking it later are related
operations within the same application.

### Desktop and command line

The desktop presents searchable Plan and Inventory views, file-level details,
progress, throughput and estimated time remaining. Filesystem completion,
verification, database recording and audit results remain distinct: a successful
copy does not conceal an unsuccessful verification or a failure to save evidence.
Retained run history is available through the CLI; a desktop History view is
planned. The desktop and CLI use the same underlying workflows.

## Current state

The first milestone is complete. **v0.1.0 “Gertrud”** is prepared as an unsigned
Windows x64 portable tester build, with reviewed copy, inventory and verification
workflows tested in the packaged application. Public distribution is still
pending. See the [tester guide](tools/packaging/START-HERE.txt) for prerequisites,
extraction and first use, and the [delivery register](docs/M1_PLAN.md) for release
evidence and known qualifications.

Inventory, integrity evidence and recorded history persist. Open tasks and
unexecuted plans do not survive restart; pause/resume applies within the current
application session.

## Compatibility

**Windows 11 x64 is the supported and actively serviced platform.** The desktop
uses Microsoft Edge WebView2 Runtime and .NET Framework 4.8 or a compatible later
4.x runtime. Run it with standard user permissions; elevated launches are refused.

### Recommended minimum system

| Component | Recommendation |
| --- | --- |
| Operating system | Windows 11 x64 |
| Memory | **8 GB RAM or more**; allow additional headroom for large collections and other applications |
| Processor | An x64 CPU that runs Windows 11 comfortably; no high-end CPU requirement |
| Graphics | Windows 11-compatible graphics; integrated graphics are sufficient as the recommended starting point |
| Storage | Space for copied files, temporary copies and retained replaced versions, plus the local inventory/history databases |

The 8 GB recommendation leaves room for Windows and the desktop host as well as
NamiSync. Our measured 100,000-entry collections reached approximately **2.4 GB
of whole-application peak memory**. This is workload-based guidance, not a tested
8 GB hardware floor or a universal memory ceiling; see the
[resource measurements](docs/PERFORMANCE.md#release-repair-resource-attempt-on-cfeac2d9--2026-11-10).
CPU, graphics and storage performance affect responsiveness and throughput;
we have not established a separate minimum CPU/GPU model list.

Windows 10 and Windows on ARM are not actively serviced targets. The engine's
database-pairing operations require Windows 10 version 1709 or later; native
ARM64 desktop use is blocked by the current .NET Framework/pythonnet stack.
x64 emulation is a possible route on ARM, outside the supported configuration.
Windows 11 22H2 or later provides Mica; older systems use an opaque window.

## Working safely with your files

Keep managed folders free of concurrent changes by other applications while
NamiSync is writing to them. It checks for drift and unsafe path changes, but
cannot guarantee protection against every external writer racing a final
filesystem operation. Local trash is useful recovery protection; it is not a
separate backup if the destination drive fails.

For cloud-synchronized folders, reading a source can download content and target
changes can propagate through the provider. NamiSync reports local completion,
not completed cloud uploads or verified remote copies. Alternate data streams
are not yet preserved. Review the [supported assumptions and limitations](docs/DEFENSE.md)
and [feature scope](docs/FEATURES.md) before using a collection with special
filesystem requirements.

## Architecture

NamiSync has a Python engine shared by its Windows desktop and command line.
The desktop combines a WebView2 interface with native Windows integration;
SQLite stores inventory, integrity evidence and independent activity history.
The interface presents decisions and results while the engine owns sync policy.

| Layer | Responsibility |
| --- | --- |
| Core | Shared contracts, path safety, identities and operation lifecycle |
| Domain modules | Scanning, planning, preflight checks, copying and verification |
| Workflows | Coordinate those operations into reviewed sync and inventory/integrity tasks |
| Persistence | Record file evidence and history after the corresponding effects succeed |
| Dispatcher | Admit tasks, coordinate control and distribute events |
| Interfaces | Desktop and CLI access to the same workflows |

Domain modules depend on shared contracts rather than calling each other;
workflows are where they meet. This separation lets presentation evolve while
keeping file operations and integrity decisions consistent across entry points.
Copies use a bounded read/hash/write pipeline, and database-backed views load
bounded windows for review. Automated tests and enforced import boundaries
support these design rules. See [Architecture](docs/ARCHITECTURE.md) for the
full design and [Performance](docs/PERFORMANCE.md) for measured behavior.

## Setup and dependencies

For the portable tester package, follow the bundled
[START-HERE guide](tools/packaging/START-HERE.txt). Python installation and the
development tools below are for running from source, not for using that package.

### Development from source

NamiSync's supported and actively serviced target is Windows 11 x64; the
compatibility section above describes other configurations without extending
that support target. Python 3.13 or later is required. The package declares
no Python upper bound; exact runtime profiles in project evidence identify
measured configurations rather than launch admission. Runtime dependencies are
`xxhash` 4.1 or later within 4.x and the `pywebview` 6.2.1 host stack.
Development dependencies are `pytest` and `import-linter`. The ordinary test
suite also requires a Node.js executable for its unmarked packaged live-event,
bridge deadline/interactive, and drain probes; probes marked `supplemental_node`
may skip. Provide
Node through `NAMISYNC_TEST_NODE` or `PATH` as described in
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

The supported M1 desktop environment includes Microsoft Edge WebView2 Runtime
and .NET Framework 4.8 or a compatible later .NET Framework 4.x runtime.
Declaring pywebview does not make explicit CLI commands initialize a GUI; the
Stage 6 host contract performs a read-only runtime preflight before window
creation, then refuses pywebview's silent older-engine fallback with an install
action and no fallback-time registry writes.

## Commandline

Refer to the [CLI documentation](docs/COMMANDLINE.md) for full command, review,
and stopcodes. 

Review and, only after typing the exact confirmation, execute a one-way sync:

```powershell
namisync sync C:\Source D:\Target
namisync sync C:\Source D:\Target --verify-after-copy
```

Refresh or check one explicit location:

```powershell
namisync inventory E:\Archive
namisync baseline --location-id 12
namisync verify E:\Archive --path Photos\keeper.jpg
namisync rebaseline E:\Archive --path Photos\keeper.jpg --accept-current-evidence
```

Browse retained history or one run in detail:

```powershell
namisync history
namisync history RUN_TOKEN
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

- No durable plan/session queue or restart-resume.
- No cross-process desktop task visibility, background integrity, concurrent
  file execution, general database migration, backup, or history retention controls.
- No automatic execution or bypass of reviewed-plan confirmation.
- The desktop host requires standard Windows permissions and refuses elevated
  launches before exposing commands. [Defense model](docs/DEFENSE.md#21-supported-environment-and-trusted-computing-base)

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
- [Performance](docs/PERFORMANCE.md) — measurement methods, profiles, source-linked
  historical results and raw-evidence limitations; [Threat Model](docs/DEFENSE.md)
  owns evidence authority.
- [Detailed changelog](CHANGELOG.md) — dated task history grouped by milestone
  or version and phase.
- [Development tools](docs/TOOLS.md) — measurement tooling, the
  executor/verifier harness, deterministic corpora, and the settlement oracle.

- [Bridge](docs/BRIDGE.md) — external protocol, transport, retry/recovery and evidence.
- [Presentation](docs/PRESENTATION.md) — tree/view, search/sort and scale contracts.
- [Interfaces](docs/INTERFACES.md) — adapters, host/package and lifecycle contracts.
- [M1 delivery register](docs/M1_PLAN.md) — completed outcomes, decisions,
  release verification and unresolved dispositions.
- [M2 proposal](docs/M2_PROPOSAL.md) — proposed later features, without an
  implementation plan or delivery commitment.
- [Handoff](docs/HANDOFF.md) — immediate operational context.

Historical plans and investigations are indexed in the [M1 delivery register](docs/M1_PLAN.md).

## Changelog

Detailed task history and dates live in [CHANGELOG.md](CHANGELOG.md). This
README intentionally stops at milestone and phase summaries.

## M1

M1 expands the reviewed-sync runtime into a complete headless integrity,
history, and workflow product while building its secured headed WebView2 shell.

### M1 Release

The unsigned Windows x64 v0.1.0 Gertrud tester set completes M1 with exact
source/build identities, serviced runtime inputs, notices, recipient terms and
guides. Final release and packaged workflow checks pass; measured resources
retain the user's scoped acceptance and recorded qualifications. Preparation
does not include signing, publishing or external delivery.

### M1 Performance

Executor and verifier root holds, admitted path reuse and reduced duplicate
observations lower measured overhead while retaining per-access fallback and
effect checks. Local copies at or above 8 MiB use bounded aligned direct target
writes with exact EOF and atomic publication; capability failures select buffered
writes before streaming. All five final measurement bands passed readback. The
4 KiB band reached 1.40 MiB/s but its stated goal remains unmet; the 4 GiB
band reached 4,505 MiB/s. Plan review passed its 35 fixed scale criteria.
[PERFORMANCE.md](docs/PERFORMANCE.md) owns samples, provenance and comparison
limits. Unbuffered source reads remain deferred to M2.

### M1 Consolidation

Repeated executor checks, native dispatch variants, bridge recovery state,
desktop snapshot reduction, visual test recipes and unused mapping readers were
removed while preserving reviewed effects, settlement, source/target admission,
command identity and behavioral witnesses. Earlier product, test and document
consolidation aligned core contracts, stable component facades, the typed
settlement reducer and layered test routes. M1_PLAN remains the sole active
delivery register; historical plans and studies are archived.

### M1 Hardening

Proportional defenses, current held-root attributes and fail-closed descendant
observation protect mutation boundaries. Cold/live database admission separates
normal WAL activity from reset-worthy incompatibility. Bounded task custody,
original command-outcome recovery, durable settlement and exact event/scalar
contracts keep failures and retries truthful. Named residual rendering and
native compatibility issues remain in BUGS/TESTS and their component owners.

### M1 GUI

Stage 6 delivered the secured WebView2 host, exact bridge, process-live tasks,
frozen Setup and shared location admission, bounded Plan review/selection and
execution, and live/retained result review with independent verification and
recording facts. Advanced Color flyouts suppress the reproduced dark shadow
halo; the compositor behavior remains deferred. A fixed local Fluent icon
vocabulary, accessible presentation and persisted cosmetic theme support the
headed shell. Inventory review adds bounded browsing, current evidence,
same-task Refresh, conditional missing-row visibility, shared row highlighting
and filter-scoped file selection
and standalone integrity controls/results. Plan/Verify navigation keeps original
execution review separate from ordinary current-state verification, including
repeatable verification of successful copy targets. Integrated lifecycle
verification is complete.

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
