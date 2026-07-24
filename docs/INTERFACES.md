# Interfaces Layer

Status: M0 CLI is implemented. M1 Stage 1 adds isolated cosmetic UI-state
storage and a tested WebView2 security spike. Stage 3 registers inventory,
baseline, verify, and rebaseline with the interface-owned production dispatcher
registry but deliberately adds no parser commands. The shared facade/CLI
expansion remains Stage 5, the desktop host remains Stage 6, and the API remains
latent.

## Purpose

Interfaces translate user/client intent into typed workflow submissions and
render dispatcher session state, events, plans, inventory, history, and results.
They own interaction behavior, validation feedback, and presentation state—not
sync policy, filesystem mutation, SQL, plan dependencies, integrity
classification, or session lifecycle.

CLI and desktop must produce the same workflow request for the same intent and
interpret the same typed result consistently. API, when added, follows the same
rule.

## M0 CLI Adapter

`interfaces/cli.py` is a thin dispatcher-backed adapter. It exposes reviewed
`sync` and read-only `history`, renders typed plan/refusal/result axes, requests
cooperative cancellation on Ctrl+C, and never imports core, modules, or the
database layer. Human confirmation occurs only after the plan session is
terminal and closed. Both real entry points consume `sys.argv[1:]`; before the
desktop exists, no subcommand prints usage and exits nonzero.

Plan review identifies the exact runnable selection plus blocked and deferred
items. A filesystem-completed safe subset is rendered as `completed with
exceptions` and returns the documented partial exit category; it is not
collapsed into either clean success or execution failure. Detailed history uses
the same outcome/reason fields. Rename-shaped review rows prefer the workflow
view's prior target path as their displayed origin, so recase, move, and
move-update approvals show the actual old-to-new target spelling.

The implemented options and numeric exits are recorded in
[COMMANDLINE.md](COMMANDLINE.md). The production composition root registers
plan, execution, inventory, baseline, verify, and rebaseline with their exact
pause capabilities; parser choices remain only `sync` and `history`. Queue
control, machine output, integrity commands, and the desktop action layer remain
deferred.

## M1 Stage 1 Desktop Foundations

`interfaces/ui_state.py` owns strict-shape `ui-state.json` independently
from database-owned semantic defaults. It retains at most five source and five
target recents separately, deduplicates Windows spellings, and stores only
cosmetic window/column/sort mappings. Atomic replacement prevents torn JSON;
cross-process semantic write coordination deliberately remains in the database
settings store.

`interfaces/web/security_spike.py` proves the security-sensitive host shape
without shipping a desktop or adding a pywebview dependency. Startup explicitly
requests `gui="edgechromium"` and turns only pywebview's renderer-unavailable
failure into an actionable WebView2 message. Once the native control exists,
the spike attaches `NavigationStarting` and `NewWindowRequested` handlers on
`CoreWebView2`, cancels every popup, and cancels navigation away from the exact
packaged scheme/host/effective port.

The only public bridge method is versioned, size-bounded, allowlisted
`dispatch`. It rechecks the current exact origin on every call, accepts one
strict JSON request object, and returns a JSON-safe structured result. There is
no `evaluate_js`, `run_js`, or `Window.state` data path. The actual Stage 6 host
must preserve this shape and add the bounded/coalesced event drain plus escaped
DOM rendering.

## Common Adapter Contract

- Validate syntax/presence early and report actionable path/input errors; domain
  validation remains in workflow/preflight.
- Submit through dispatcher/registry rather than starting ad hoc workers that
  call modules directly.
- Read current session records and subscribe from a sequence number.
- Treat progress as a replaceable snapshot. Handle bounded state/item/terminal
  delivery, including `Gap` plus resubscription for an ejected/late ordinary
  subscriber; history has timeout-bounded admission delivery and exposes failure
  through the audit axis rather than pretending the stream was complete.
- Present refusal, cancellation, partial failure, recording-behind, history
  failure, and integrity mismatch as distinct states.
- Keep plan, inventory, and history presentation models orthogonal.
- Commit only after the plan session terminates, binding plan fingerprint and
  exact selection digest. Never expose an “execute anyway” path around
  commitment or fresh preflight.
- Runtime thread/ownership guards raise real exceptions, not `assert`.

## Shared Actions

An interface action has one source of truth for label, enablement, shortcut,
scope, confirmation, and dispatch. Menus, buttons, context menus, and commands
adapt that action rather than duplicating rules. Enablement is derived from
typed state and selected scope; hidden/filtered selection is disclosed.

Presentation logic that selects a row, computes scope, or builds a result model
is testable without entering a modal event loop.

## Session And Worker Boundary

Dispatcher is the lifecycle source of truth. A desktop may need toolkit threads
to keep its event loop responsive, but those adapters do not invent another
domain session state machine or own volume locks. Worker release is identity-
checked, result delivery is marshaled to the UI thread, and close waits for
actual thread/session completion without blocking the event delivery needed to
complete it.

## Security And Data Isolation

Explicit database overrides reach both ledger and history. Tests never default
to real `%LOCALAPPDATA%` databases. Paths and annotations are treated as data;
no shell interpolation, HTML injection, or spreadsheet formula execution is
introduced by rendering/export.

Read-only commands/views may coexist with active writers under WAL. Mutating
interfaces use the same dispatcher and physical-volume custody; GUI single
instance is a presentation-instance rule, not a global ban on safe CLI work.

## Latent API

The future API exposes versioned request/result/event schemas, authentication,
local binding by default, explicit replay gaps, and no direct module endpoints.
It is not scaffolded until a concrete client exists; core event schema version
is the provisioning seam.

## Expectations

- Dispatcher supplies generic state/control/events.
- Workflow registry/composition root supplies typed activity adapters.
- Core reason/outcome schemas are stable and presentation-neutral.
- Repositories expose read models only through workflows/application services;
  interfaces do not issue SQL.
- UI and CLI do not infer domain success from zero bytes or green styling.

`OperationResult.recording` and `.audit` expose independent ledger/history
durability, while `Disposition.RAN|UNRUN` distinguishes discarded/refused work
from a zero-byte activity that actually ran. Interfaces render these typed axes
without parsing diagnostics or overloading filesystem status.

## PoC Hardening

The layer contract prevents dead real CLI argv, real-user test database writes,
plan-wide blocked gating, stale worker GC/release, premature thread destruction,
per-chunk UI floods, uncancelable import close, wrong-location fallback,
plan/inventory state conflation, misleading partial/refused completion, modal
test hangs, duplicated action wiring, and `assert`-only thread guards.

## Acceptance Criteria

- Import-linter proves interfaces import workflows/dispatcher but not
  core/modules/db directly under the agreed composition-root arrangement.
- Equivalent CLI/desktop requests produce equivalent workflow payloads and
  result classification.
- No interface mutation path bypasses dispatcher, mandatory review, preflight,
  executor, or recorder.
- Invalid/unusable paths show a specific next action rather than silently
  disabling everything.
- Refused zero-op, all-noop, partial failure, cancellation, mismatch, and
  ledger-behind states render distinctly.
- Audit-behind is independent of ledger-behind; queued discard renders from
  `CANCELED+UNRUN`, not byte count or free-form reason.
- Event reconnect handles current state/tail/gap without duplicate row outcomes.
- Changing plan selection after review invalidates commitment; neither UI nor
  CLI can submit the stale commitment.
- Action source-of-truth tests cover menu/button/context presentation equality.
- Presentation-selection tests run without modal loops or live filesystem/DB.
- Thread/result callbacks execute on the required presentation thread and raise
  explicit runtime errors on violation even under `python -O`.
- Database override tests write neither ledger nor history to real user paths.
- Read-only history/status remains usable during an active mutating session.
- The security spike forces Edge Chromium, attaches both native navigation
  guards, rejects a dispatch after hostile navigation, and exposes only the
  versioned allowlisted structured endpoint.
