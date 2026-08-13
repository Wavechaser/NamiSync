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
orderly-close/retry controller. The transport chain through Slice 3 is
complete: production exposes exactly `pick_folder`, `start_plan`,
`next_events`, and lifecycle-only `close_task`, with real paths retained behind opaque server slots, task
observation attached before work can start, a bounded event drain, and a strict
inert-text return sink. GUI Break 1's design foundation is also complete:
`tokens.css` owns the exact authored palette and semantic mappings,
`components.css` supplies the shared control states, a fixed local Fluent icon
registry owns four pinned foundation glyphs, and native appearance follows
Windows theme/material capability with an opaque fallback. User-facing workflow
controls/product views are not yet available in the window. Slice 4's shared
presentation foundation is complete: one pure visible-sequence implementation
owns strict structure, literal display search, caller-decided filtering,
collapse, bounded windows, and visible anchoring; the installed renderer owns
only accessible fixed-height rows, two virtual spacers, inert labels, and stale
generation refusal. The shipped frame now shows truthful focusable empty task
navigation and work regions without fabricating a task or widening the
workflow-command surface. Clean-wheel Windows gates exercise the real WebView2
host, packaged page and design assets,
navigation/popup and per-dispatch origin guards, runtime refusal,
single-instance activation, isolated data root, visible database refusal,
native picker confinement, hostile-text transport, log privacy, the four-mode
component gallery, real native material apply/fallback paths, and Slice 4
keyboard, 200%-zoom reflow, forced-colors focus, hostile/long tree text,
28-pixel row bounds, and stale-generation behavior. The plan, inventory,
history, lifecycle, packaging, and beta closures remain open.

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
- [M1 Shell](docs/M1_SHELL.md) — ordered Stage 6 host, frontend, and beta-package delivery plan.
- [Command line](docs/COMMANDLINE.md) — commands, review, output, and exits.
- [Executor](docs/EXECUTOR.md) — guarded filesystem mutation, pipeline, and recovery.
- [Inventory](docs/INVENTORY.md), [Verifier](docs/VERIFIER.md), and
  [Workflows](docs/WORKFLOWS.md) — retained location evidence and orchestration.
- [Database](docs/DATABASE.md), [Recorder](docs/RECORDER.md), and
  [History](docs/HISTORY.md) — local persistence and audit behavior.
- [Features](docs/FEATURES.md), [Bugs](docs/BUGS.md), and
  [Handoff](docs/HANDOFF.md) — present and future scope, known issues, and session context.
- [Development tools](docs/TOOLS.md) — the `tools` executor/verifier measurement
  harness and deterministic corpus generator.

## Changelog

### M1 Stage 6 - Post-Delivery Hardening

- Hardened the early desktop shell without expanding its product workflow UI.
  - **Host and transport:** changed pywebview to one function-only dispatch
    entry, bounded handler/task admission and shutdown, added terminal-gated
    `close_task`, receipt-safe pre-slot replay, finite recovery, sanitized
    command logging, and retained the hidden-`mirror` refusal.
  - **Native ownership:** pinned app directories and ready database mains with
    process-lifetime handles, authenticated activation by executable/base-image,
    and made fresh-pair rollback exact-object and interrupt-safe;
    same-principal mutex or base-interpreter spoofing remains outside the
    single-instance security boundary.
  - **Evidence:** regressions cover saturation, cleanup compensation and retry,
    service receipt shutdown races, replacement attacks, private raw bridge
    receiver names, and a real headed 25-second drain concurrent with another
    RPC and settling on close.

### M1 Stage 6 — Presentation Checkpoint

- Completed Slice 4 without claiming the later product surfaces or beta
  package.
  - **Shared presentation core:** added the frozen tree-agnostic visible
    sequence, strict structural/search/filter contracts, exact 256-row windows,
    and visible-ancestor anchoring.
  - **Installed shell:** added the accessible fixed-28-pixel tree renderer with
    two spacers and stale-generation refusal, plus labelled focusable task/work
    regions with honest empty states and no synthetic domain data or new bridge
    command.
  - **Evidence:** installed-wheel SH-G-7 covers renderer-level shell Tab traversal,
    native 200% zoom reflow, forced-colors focus, hostile and long labels,
    row/DOM bounds, and an older response unable to replace a newer window.

### M1 Stage 6 — GUI Foundation

- Completed GUI Break 1 without claiming the later product surfaces or beta
  package.
  - **Design system:** added the exact authored palette, contrast-tested semantic
    status/operation aliases, shared Fluent controls and motion guardrails, plus
    a fixed four-glyph local Fluent icon registry with pinned provenance.
  - **Native appearance:** added system theme/accent observation, progressive
    Mica and immersive-dark handling, and a system-color opaque fallback while
    preserving the secured host lifecycle.
  - **Evidence:** clean-wheel headed gates cover light, dark, forced-colors, and
    reduced-motion gallery modes; real DWM readbacks and renderer transparency
    prove the capable path and two injected opaque fallback sequences.

### M1 Stage 6 — Transport Checkpoint

- Completed the desktop shell foundation through Slice 3 without claiming the
  later product UI or beta package.
  - **Host:** retained the secured installed-wheel WebView2 composition and
    hardened repeated-load close status so late workers do not query a destroyed
    document or let presentation failure change shutdown truth.
  - **Transport:** added exact strict v1 envelopes, the three-row
    `pick_folder`/`start_plan`/`next_events` allowlist, bounded purpose-bound
    path slots, receipt-safe plan replay, transactional task observation, and a
    64-update progress-coalescing/reliable-backpressure drain.
  - **Frontend and evidence:** added the sole strict `render.js` text sink, the
    generation-counted browser drain manager, and constructor-only headed
    harness; gates cover native picker confinement, independent off-origin
    refusal, hostile text/log privacy, gap recovery, terminal settlement, and
    repeated bridge readiness without duplicate drains.

### Development Tooling

- Flattened the executor/verifier measurement harness into `tools/` and made
  unsafe or semantically mixed benchmark samples fail instead of reporting
  plausible throughput.
  - **Safety and evidence:** bound owned workspaces to directory identity under
    an exclusive lease, made corpus regeneration deterministic, isolated report
    artifacts, and made sidecar schemas, bound identity, and writes strict.
  - **Measurements and tests:** retained diagnostics-on tool defaults with a
    complete opt-out, disclosed empty correspondence, validated execution and
    readback coverage, and added focused corpus, verifier, sidecar, and CLI tests.

### M1 Hardening

- Closed post-refactor effect-settlement and verifier authority seams without
  weakening the stabilized package boundaries.
  - **Executor:** generic collaborator failures now settle active effects and
    pending directories from the original operation error before propagating;
    source/target guards also bind the operational root to reviewed authority.
  - **Verifier:** native subclasses and timing decorators use an explicit
    authority-bound reader protocol, while engine retains selected-root and
    opened-volume policy and sidecar shares the pure stat predicate.
  - **Oracle and tests:** expanded the retained oracle to 30 scenarios and 70
    exact rows for collaborator escapes and restored, missing, and unreadable
    settlement states, then replaced its baseline and semantic pin separately.
- Consolidated the recent safety hardening behind stable authority, execution,
  verification, and settlement boundaries without changing persisted contracts.
  - **Root authority:** centralized fresh ephemeral anchor, volume, and no-follow
    facts in core while preserving each consumer's timing and refusal policy.
  - **Executor and verifier:** introduced stable package facades with coarse
    runtime/native/pipeline and engine/native ownership respectively.
  - **Settlement:** replaced parallel retained-state maps with a typed effect
    journal and pure reducer, guarded by the retained 30-scenario oracle.
  - **Tests:** consolidated shared fixtures and matrices, then organized executor
    and verifier coverage by the production boundary each case protects.
- Closed the remaining actionable LOW audit findings and tightened adjacent
  malformed-input boundaries without changing deferred feature scope.
  - **Planner and executor:** share one managed Windows-attribute mask so
    unmanaged ARCHIVE/TEMPORARY drift converges, while copied UPDATE backups
    bind reviewed target evidence to one stable open handle before publication.
  - **Defensive boundaries:** classify SQLite contention by result code, reject
    the remaining documented DOS-device aliases and non-finite workflow JSON,
    and surface malformed recorder context through typed rollback-safe errors.
  - **Tests:** cover managed/unmanaged attribute behavior and native rerun,
    grow/truncate/rewrite backup drift, extended BUSY/LOCKED codes, reserved
    names, strict payload constants, and malformed recorder transactions.
- Restored FULL scan availability when a managed root is exactly a trusted
  folder-mounted volume anchor, without relaxing junction refusal.
  - **Scanner:** requires the resolved root, reviewed/current anchor, and volume
    evidence mount to agree, then uses followed metadata only for that exact
    mount root while retaining the surrounding anchor and `VolumeId` checks.
  - **Tests:** cover inventory-reviewed and native-derived anchors, accurate
    mounted-root identity, forged/placeholder/invalid states, scoped scans, and
    continued descendant and configured-root reparse refusal.
- Closed a cancellation-settlement composition gap that could hide an earlier
  readonly mutation.
  - **Executor:** now evaluates retained byte-publication and mutation-marker
    state independently; confirmed publication stays authoritative, while
    changed or unverified marker truth degrades recording even when publication
    probing fails.
  - **Tests:** cover restored readonly pre-state, failed restoration with an
    unavailable publication probe, and committed-publication precedence without
    false success evidence.
- Closed managed-root redirection, owned-trash parent substitution, sticky
  mismatch projection, and native-path diagnostic gaps without expanding the
  external-writer threat contract.
  - **Filesystem safety:** kept managed roots lexical while no-follow admitting
    configured root-chain components below trusted or reviewed volume anchors,
    bound scans, execution, and verifier opens to full reviewed volume identity,
    and revalidated target and owned-trash parents after blocking barriers.
  - **Evidence and diagnostics:** made sticky hash mismatch dominate later stat
    drift and normalized enumeration/temp-cleanup filenames before public or
    durable rendering.
  - **Tests:** added real junction and deterministic remount substitutions across
    scan, execution, trash/update, and verification, plus inventory-preservation,
    projection, and serialized-detail regressions.
- Closed executor attestation and durable-settlement gaps without changing the
  full-intent/safe-selection contract or adding normal-path filesystem probes.
  - **Executor:** moved UPDATE's recorder wait ahead of all final prepared/live
    validation, bound published identity to the prepared temp, and made failed
    non-byte and readonly mutations report ledger-behind truth.
  - **Controls and tests:** covered commit-then-raise, exact pre-state,
    probe failure, deferred mkdir, temp substitution, and retry pause/cancel.
- Closed the remaining selected medium audit findings without broadening
  deferred feature scope.
  - **Windows paths:** made service-to-verifier native I/O explicitly long-path
    safe while keeping logical paths unprefixed and refusing ambiguous/device
    roots instead of risking wrong-tree normalization.
  - **History:** introduced reset-only history v5 receipts so exact duplicate
    items are non-counting and one oversized valid event degrades audit without
    discarding the later run or terminal truth; receipt/order and summary
    projections are authenticated and indexed classification is append-only.
  - **Inventory:** replaced full-location materialization for frozen resume and
    stale integrity selection with location-scoped, snapshot-bounded row reads.
  - **Tests:** added deep-root end-to-end mutation/verification, path-boundary
    refusal/diagnostic, receipt state-machine/tamper, bounded selection, and
    million-item history benchmark coverage.
- Closed the planned M1 safety-audit findings while preserving full reviewed
  intent and executing only the derived safe selection.
  - **Planner and selection:** pinned blocked parent/type and unsupported-source
  cases as visible raw intent whose corresponding removals stay deferred.
  - **Executor:** moved destructive flush waits before every final mutation
    guard and made confirmed or unverified post-publish failures
    recording-degraded.
  - **Inventory and verifier:** introduced ledger v3 sticky verification
    invalidation with explicit four-state inventory projections.
  - **Dispatcher:** keyed workers, reservations, and leases by process-local
    generation so cancel/resume handoffs cannot overlap or clean up successors.
  - **Tests:** added adversarial planning, path-swap, published-failure,
    invalidation, and dispatcher acquisition/shutdown race regressions.
- Resolved M1 integration and adversarial-review findings without weakening the
  reviewed-plan safety model or making history/audit failures alter sync truth.
  - **Executor:** shared ordered publication settlement across COPY, UPDATE, and
    MOVE_UPDATE; retries preserve owned state, pause safely, and disclose only
    validated backups, partial publishes, and target drift.
  - **Dispatcher and history:** bounded writer, audit, and close budgets; made
    terminal cleanup retryable; and kept live and retained audit results,
    sparse-page traversal, subscriptions, and lifecycle order consistent.
  - **Workflows and CLI:** closed custody, replan-generation, idempotent-command,
    cancellation-projection, confirmation, and shutdown-reporting races across
    the service facade and command-line surface.
  - **Database, inventory, and protocols:** bounded SQLite contention, preserved
    read snapshots and incomplete-scan authority, and rejected coercive persisted
    event, workflow, settings, and bridge JSON.
  - **Interface host:** constrained native WebView2 access to the UI thread,
    failed closed on guard attachment, and closed navigation, frame, popup, and
    fallback-renderer escape paths.
  - **Tests:** pinned temporal, concurrency, recovery, and bounded-work
    regressions, including retry/delay stress cases and independent pipeline
    queue-capacity checks.

### M1

- Delivered M1 Stages 1–5.5 as a headless integrity and reviewed-sync product;
  Stage 6's headed WebView2 desktop remains unshipped.
  - **Executor:** moved content evidence to XXH3-128 and added a bounded
    reader/hasher/writer pipeline, adaptive chunks, preallocation, and leaner
    Windows publication and finalization paths.
  - **Scanner and preflight:** added recursive multi-root inventory scope,
    bounded missing inference, typed scan warnings, and folder-scoped integrity
    that continues visibly past unreadable subjects.
  - **Workflows and CLI:** added role-free inventory, baseline/verify/rebaseline,
    optional execute-to-verify readback, deterministic workflow trees, opaque
    identifiers, revisioned selection, and typed result views.
  - **Dispatcher and history:** added retry-safe facade commands and the
    reset-only history v4 journal with committed nonterminal recovery, fixed-cost
    summaries, bounded keyset detail, and live reliable-event repair.
  - **Database:** established the `m1-ledger-xxh3-128` ledger v2 boundary,
    separated semantic settings from cosmetic UI state, and preserved local
    history as an independent audit axis.
  - **Interfaces and security:** added the shared service facade and location
    CLI commands, plus a WebView2 bridge/host foundation with a read-only runtime
    probe, hardened renderer settings, and exact packaged-asset origins.
  - **Development tools:** added executor/verifier measurement harness and corpus
    generator, with owned-workspace safety and strict benchmark-result validation.
  - **Tests:** added focused integration coverage for scoped inventory,
    selection/replan provenance, retry-safe commands, durable history pages, and
    the WebView2 host foundation.

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
