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
history, dispatcher, and service/CLI surfaces are usable. Stage 6 now has its
classified launcher, coordinated database gate, packaged bootstrap page, fixed
single-instance identity, secured local WebView2 product host, and nonblocking
orderly-close/retry controller. The existing transport chain through Slice 3
has landed under the production mapping defined exclusively in
`docs/M1_BRIDGE.md`, with real paths retained behind opaque server slots, task
observation attached before work can start, a bounded event drain, and a strict
inert-text return sink. Explicit-`Gap`-only recovery and command-specific
`start_plan` revision are ratified with landed named regressions. GUI Break 1
and Slice 4 have completed their audited
realignment: pinned Fluent neutral and live Windows accent roles, structured
appearance fallback and retry lifetime, direct workflow-owned visible arrays,
a 65,536-byte literal-search field ceiling behind the separately bounded bridge
envelope, indexed anchors, an operable platform-accessible virtual tree, and
Mica-visible rail/task-card rest surfaces. User-facing workflow controls and
product views are not yet available in the window. Clean-wheel Windows gates
now exercise the real WebView2 host, packaged page and design assets,
navigation/popup and per-dispatch origin guards, runtime refusal,
single-instance activation, isolated data root, visible database refusal,
native picker confinement, hostile-text transport, log privacy, the component
gallery, real native material apply/fallback paths, and Slice 4 platform
keyboard/accessibility, 200%-zoom reflow, forced-colors focus, hostile/long tree
text, 28-pixel row bounds, scale, and stale-generation behavior. The plan, inventory,
history, lifecycle, packaging, and beta closures remain open. The named
browser-behavior witnesses now run through the installed production bridge and
renderer in real WebView2; Node probes remain supplemental. SH-G-8's exact
four-task logical-time fixture and standalone installed-wheel benchmark harness
have landed. The fixed, non-sliding 150 ms progress-only linger has also landed
with focused immediate-wake, lifecycle-race, ordering, and cursor regressions.
An active long poll may hold the first detailed `Progress` snapshot for the
full 150 ms; command receipt and reliable running-state feedback still bypass
that wait.
The installed-wheel benchmark now streams bounded browser and producer evidence
to SHA-256-manifested sidecars, assembles the final artifact only after the
measured child exits, and reports whole-runtime memory only as a non-acceptance
diagnostic. Its `passed` field covers the event envelope alone and explicitly
does not stand in for custody evidence. The separate accepted custody evidence
below closes SH-G-8. The actual child is
assigned directly to the Job before product composition, with per-PID
role/private-byte plus thread/handle/topology diagnostics. A separate
retained-state sizer reports replay, subscriber, adapter, and
identity-deduplicated union graphs while cutting terminal-result subtrees only
along terminal paths. The frozen `sh-g-8-transport-v1` calibration-a and
holdout-b corpora and production-path custody runner have now landed. They
drive the real built-in dispatcher, subscriber, and adapter deques, prove the
quiescent per-task 128/64/64 maximum no-`Gap` shape and terminal path cut, and
bind three fresh-process artifacts to clean committed source, an isolated
`-I -S` parent and safe-path `-P -S` children, a hashed dependency root, and an
external digest receipt. Realigned BR-G-42
event-custody and SH-G-8 now have a committed calibration-a artifact and
normative transport measurement plus a mechanically frozen 1,966,080-byte
(1.875 MiB) ceiling. The independent holdout-b dataset passed, closing SH-G-8
and BR-G-42's event/transport-custody predicate. Other BR-G-42 feature rows
remain on their owning slices.
BR-G-45 separately leaves the complete 100,000-subject terminal artifact set
and aggregate completed-task retention policy open. Shell-owned SH-G-15
separately leaves version-bound absolute cold/settled and repeated/long warm
whole-runtime containment open. A valid prior real-60-second run passed event
truth, ordering, latency, and shutdown and measured a 67,375,104-byte whole-Job
delta; that diagnostic neither passes nor fails any of the realigned memory
predicates. The durable
`tests/interfaces/web/sh_g_8_transport_calibration.json` artifact records a
1,376,690-byte ordinary union high water and a 1,534,946-byte exact maximum
no-`Gap` union from clean commit
`56c50b43dc19090ad33af031891503bfec80599b`. The separate
`tests/interfaces/web/sh_g_8_transport_ceiling.json` contract freezes the
1,966,080-byte ceiling by integer 5/4 headroom and 65,536-byte round-up. The
accepted `tests/interfaces/web/sh_g_8_transport_holdout.json` artifact records
1,351,794 ordinary and 1,513,014 exact-maximum no-`Gap` bytes, leaving 614,286
and 453,066 bytes of margin respectively. A separate one-child current-source
regression now applies that frozen ceiling to both live custody shapes on every
ordinary suite run; it detects drift but does not replace acceptance evidence.

M1 state is process-local: queued sessions and unexecuted plans do not survive
an application restart. Committed nonterminal history survives restart as
`incomplete`, but is not classified as interrupted or executable. The active
database boundary is ledger v3 plus history v5. Older, missing, transitional,
or mismatched databases are refused; close
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

## Documentation

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

Shared root authority, stable executor/verifier package boundaries, and an
oracle-guarded typed settlement reducer separated internal ownership without
changing public or persisted contracts.

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
