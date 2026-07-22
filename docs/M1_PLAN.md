# M1 Plan

Status: planning decisions resolved and reconciled 2026-07-22. Nothing below is implemented
yet. This is both the milestone plan and the decision log for the choices made
while shaping it — later docs (`ARCHITECTURE.md`, `FEATURES.md`,
`DESKTOP_UI.md`, `INTERFACES.md`) get updated as each track lands, and this
file is the record of *why*, the same role `DESIGN_REVIEW.md` plays for M0.

**Documentation precedence**, stated once here because it resolved a real
conflict during this planning pass (DR-M1-20, retention): `FEATURES.md` owns
behavior, `ARCHITECTURE.md` owns contracts, module docs are subordinate to
both. Where a module doc reads stricter or looser than FEATURES/ARCHITECTURE,
the module doc is what's stale.

**Standing of this document.** This plan governs unimplemented M1 decisions
until each is promoted into the active documents. It does not silently
override `FEATURES.md` or `ARCHITECTURE.md` for anything already implemented;
where it changes a settled bullet (DR-M1-03's settings-file split, DR-M1-05's
worker-count removal), the active document is edited **as that track
lands**, not deferred indefinitely. Once a decision is promoted, the active
document wins and this file becomes history — the same lifecycle
`DESIGN_REVIEW.md` has.

---

## 1. What M1 Actually Is

`ARCHITECTURE.md` §6 compresses M1 to one line — "integrate the verifier
through baseline + inventory + history integrity detail + retention." That
undersells it. The verifier operation module is done; M1 builds the **second
workflow family** it plugs into: a one-location, no-plan, no-commitment shape
that M0 never needed, plus the interface substrate that M0's CLI never had to
build properly because it only ever had one workflow to drive.

Three tracks, run in parallel, kept **functionally integrated but modularly
implemented** — each has its own module boundary, but Track B and Track C are
both clients of Track A from day one rather than parallel forks that get
reconciled later:

- **Track A — Interface substrate.** The composition root, session
  observation, result classification, and view-model vocabulary that both the
  CLI and the new web UI need, extracted from where M0 left them (mostly
  inside `interfaces/cli.py`).
- **Track B — Integrity spine.** `run_integrity`, inventory reads
  (acknowledge/restore/staleness), history v3 detail, retention, and the CLI
  commands that expose them.
- **Track C — Web desktop shell.** pywebview host, versioned bridge, task
  rail / plan tree / inventory tree / history dialog, built only against
  Track A's facade.

Track B's CLI commands land after Track A retargets `cli.py` onto the
facade, or get ported once it does — not written twice.

---

## 2. Decision Log

Grouped by theme; each item states the tension, the resolution, and why.
Numbered `DR-M1-##` to avoid colliding with `DESIGN_REVIEW.md`'s M0 numbering.

### Layering

**DR-M1-01 — Where does cross-cutting orchestration live?**
M0's registry construction, session observation, and result classification
all ended up inside `interfaces/cli.py` because nothing else could import
both `dispatcher` and `workflows`. A second interface would either duplicate
that ~90 lines or import the CLI module.
**Resolution:** `interfaces/service.py`, a sibling of `cli.py` and the new
`web` adapter — not a new top-level layer. New import-linter contracts: `cli`
and `web` do not import each other; both import `service`; `service` imports
neither.

**DR-M1-02 — Is the layering fix separate from the GUI facade?**
They looked like two different pieces of work (restore intended separation;
prepare for a second interface) but touch the same 90 lines for the same
reason.
**Resolution:** one change. Extract to `service.py`, retarget `cli.py` onto
it, prove behavior is unchanged via the existing 13 end-to-end CLI tests,
*then* build the web adapter against the proven facade.
**Caveat (S1):** those tests exercise `main()` end to end, which is a strong
behavior net, but the facade moves runtime/dispatcher lifetime from
per-command to process-scope while the CLI process stays per-command. The
exact `finally`-nested shutdown ordering in `_run_sync` (dispatcher shutdown
before runtime close) must be reproduced in the facade's lifecycle, not
assumed — expect to touch fixtures that construct runtimes directly.

### Settings

**DR-M1-03 — One settings file or two?**
The single `StaticSettingsReader` is fed the plan's own filter snapshot
(`runtime.py:125`), so the filter-drift check preflight already implements
compares a value against itself — there is no live settings source at all.
Building one raised where it lives: `db/`, `workflows/`, or the new
`interfaces/service`. A single file also forces GUI-cosmetic keys (recent
folders, window geometry) through the same accessor as plan-shaping keys
(filters, deletion policy), which either makes `workflows/` grow UI
vocabulary or makes the settings module import-illegal for the GUI to touch
directly.
**Resolution: split into two files, two owners.**
- `settings.json`, owned by `db/` (schema-versioned, atomic temp+replace
  write): semantic keys that shape a plan (filters, default deletion policy,
  trash-on-update default) and operational keys (history retention). Written
  through the facade on explicit settings commits.
- `ui-state.json`, owned by `interfaces/`: recents (5 source + 5 target,
  maintained separately, per the settled FEATURES bullet), window geometry,
  column/sort state. Plain file the GUI owns outright; `interfaces/` may
  write files, it just can't import `db/`.
This amends the FEATURES.md *Local Settings File* bullet from one file to
two — the smaller edit, given what it buys.
**Also removes obsolete preflight plumbing:** the `SettingsReader` protocol
and `StaticSettingsReader` currently exist only to feed live filter/policy
values into execution preflight. The runtime supplies the plan's own values,
so those checks compare a snapshot with itself today; under the frozen-session
model they are conceptually wrong as well. M1 removes the settings collaborator
from observe/preflight, the `ObservedWorld` live-settings fields, and the
`FILTER_DRIFT`/`OPTIONS_DRIFT` refusal paths. `db/settings.py` supplies defaults
to planning through the injected runtime/facade, never to admitted execution.

**DR-M1-04 — Concurrency policy for the settings files.**
GUI and CLI can write settings concurrently by design (read-only/disjoint CLI
work coexists with a GUI session per `INTERFACES.md`).
**Resolution:** serialize semantic-settings commits with a named cross-process
mutex. The mutex is held only for the brief read-modify-atomic-replace
transaction; opening the GUI or running a CLI command does not reserve the
settings file, and ordinary reads remain available. A second writer waits,
then re-reads the current file under the mutex, changes only its owned keys,
writes a temporary file, atomically replaces `settings.json`, and releases
the mutex. This prevents two interfaces from silently overwriting changes
based on the same stale read. `ui-state.json` remains GUI-owned and does not
need this cross-interface writer mutex.

**DR-M1-05 — What does a committed plan's fingerprint bind, and does a
settings change invalidate an outstanding commitment?**
Two settled statements looked contradictory: filter-drift refusal is listed
as implemented preflight flesh, but "changed defaults affect new plans and do
not affect existing commitments" reads like commitments are immune to
settings changes.
**Resolution — immutable session snapshot.** Planning captures all semantic
settings used to construct the plan. Commitment binds that snapshot; later
changes to global defaults neither mutate nor invalidate the admitted session.
The executor consumes the reviewed plan snapshot and never rereads global
semantic settings to decide filesystem behavior.

Commitment has three explicit bindings:

1. `policy_fingerprint` binds the captured reviewed intents that shape
   filesystem effect: deletion policy, trash-on-update, filters, preservation
   policy, and casing propagation.
2. `plan_fingerprint` binds the complete reviewed plan, including roots,
   volume identity, before-state metadata, operations, and the captured policy
   values embedded in that plan.
3. The existing selection digest separately binds the selected operation ids.

**Rechecked live at execution, never fingerprinted:** volume still exists,
file drift, capacity.
**Excluded entirely:** UI presentation (sorting, columns, notifications).

`worker_count` is not semantic intent, but it is currently embedded in both
`SyncOptions` and `Plan`, so the full plan fingerprint binds it accidentally.
M1 removes it rather than relocating it to another public setting: concurrent
file execution is deferred by `HASH_REFACTOR.md`, and a dormant tuning knob
would serve no current behavior.

**Precision:** one canonical fingerprint function in `core/`, used identically
by plan construction and commitment validation. It fingerprints the captured
snapshot, not a second serialization of current defaults.

**DR-M1-06 — What does editing a bound setting do at each lifecycle stage?**
**Resolution:** global defaults remain editable at all times and affect only
future planning snapshots. Task-local bound controls follow the session:

- While planning or reviewing, editing a bound value invalidates the current
  plan and returns the task to planning/pre-commitment. A new plan receives a
  new snapshot and requires review.
- During execution, task-local bound controls are disabled. To change roots,
  deletion/trash policy, filters, preservation, or another bound value, the
  user cancels, edits, and replans from the filesystem's new current state.
- Completed operations are not rolled back. The next scan observes them and
  converges normally.
- A global settings commit never runs advisory preflight over outstanding
  sessions and never terminates or rewrites their snapshots.

The UI states this directly: the active run is using its reviewed settings;
new defaults apply to future plans.

**DR-M1-07 — Build the view-model vocabulary, or relax the import-linter
boundary?**
Interfaces may hold core objects but not name their types
(`allow_indirect_imports = true` on the forbidden-imports contract), which is
why the CLI duck-types `Progress` by `hasattr`. A GUI mapping ~35
discriminated values (6 event bodies, 10 `SessionState`, 6 `Outcome`, 8
`IntegrityResult`, 2 axes, 2 `Disposition`) onto labels/colors/text by shape
is a bug farm.
**Resolution:** build the vocabulary — `SessionEventView`,
`SessionRecordView`, `OperationResultView`, `IntegrityOutcomeView`,
`InventoryRowView`, `ResultCategory` — primitives-only dataclasses in
`workflows/views.py`, following the existing `PlanOperationView`/
`RefusalView`/`HistoryRunView` pattern. Being primitives-only means the same
structure serializes straight to JSON for the web bridge (DR-M1-15..18) — no
second serialization layer. Retarget the CLI's four `hasattr` sites onto it
as the proof before the GUI depends on it. `OperationResultView` preserves the
ordered heterogeneous item list, each item's `item_type` and `phase`, and the
generic phase summaries; interfaces never reconstruct domain lists by testing
which fields happen to exist.

**DR-M1-08 — Does plan review survive app closure, as `ARCHITECTURE.md` §4.9
promises ("the app may even close")?**
Plans currently live in a process-local dict (`self._plans` on
`LocalWorkflowRuntime`). True durability is `SqliteSessionStore`, which is
scheduled M2.
**Resolution:** ship M1 without plan persistence.

**Amended per review finding 9.** The original entry proposed a `PlanStore`
protocol with a single in-memory implementation. The reviewer is right that
this is a speculative seam for a future single implementation — the
`SessionStore` precedent is weaker than it looks, since that protocol exists
because the *dispatcher* genuinely needs injection, whereas a plan store has
one in-process consumer and no second present-tense implementer.
**Middle ground adopted:** keep the existing private dictionary, but route
all access through named methods on the runtime/facade
(`save_plan`/`get_plan`/`drop_plan`) rather than touching the dict directly.
That is the "opening" B7 asked for — M2 swaps the internals without changing
a caller — with no protocol declared before a second implementation exists.

Known M1 limitations to document, not silently carry: a task card's plan does
not survive a process restart, and until M2's durable session store the task
rail only shows its own process's sessions — a concurrent CLI run is invisible
to it except through volume-lock contention. Also (review finding 10's
corollary): the plan dictionary now grows for the life of a long-running GUI
process where the CLI's process-per-command previously hid that; closing a
task card must call `drop_plan`, matching the dispatcher's existing
close-drops-record behavior.

### History and event schema

**DR-M1-09 — History schema v2 → v3 for integrity detail: migrate, or
reset?**
Tagged `ResultItem` values and generic phase summaries need a home in history
detail; the schema is currently v2 with one narrow v1→v2 migration and a
stated "reset-and-refuse posture" otherwise. A second narrow migration was floated, then a chain-runner
(ordered `(from, to, fn)` steps) to guarantee v1→v2→v3 ran in order rather
than skipped.
**Resolution — reset, not migrate.** NamiSync is unreleased and tested only
in closed environments; a lean migrator now that gets upgraded into a real
one later costs more than accepting a schema-version-mismatch reset on a
database holding nothing of value. **No migration path ships in M1.** The
existing reset-and-refuse posture (refuse to open a stale-version database;
user deletes and lets it recreate) covers the v2→v3 bump. The general,
versioned migration module stays deferred past M3, unchanged from
`ARCHITECTURE.md`'s build order — this decision does not pull it forward,
it explicitly declines to.

**DR-M1-10 — Ordering: view vocabulary vs. verifier wiring vs. post-exec
verify (DR-M1-13)?**
`IntegrityOutcome` exists in `core/integrity.py` but is absent from
`core/events.py`'s `EventBody` union; today it silently vanishes from history
(`HistoryObserver.on_event` only collects `ItemOutcome`, and the generic
`_primitive` hasher doesn't error on the unrecognized type — it just isn't
appended). Wiring the verifier to a session before adding the nominal
`ResultItem` contract, phase/item tags, and `PhaseResult` serialization would
produce integrity history that comes back empty or structurally ambiguous
with no failure anywhere.
**Resolution:** vocabulary before wiring, confirmed as the single critical
path for Track B — the event union, serializer, and view models block
*both* standalone verify sessions and DR-M1-13's in-session integrity phase.
Do this first in Track B, not first-out-of-enthusiasm on the more visible
work.

### Inventory and volume resolution

**DR-M1-11 — Does inventory scanning need a new scanner module?**
No. The scanner contract is already single-root
(`deps.scanner(root, ignores, ctx)`); paired sync just calls it twice. A new
module would also violate "Domain modules are mutually independent."
**Resolution:** inventory scanning is a **workflow**, not a module: resolve
volume → resolve root → call the existing `WalkingScanner` once →
`record_inventory`. No new scanner code.

Volume resolution ladder (workflow-level, using the already-supported
`VolumeId(serial, fs_type)` + volume-relative path). **Five states, not three**
(review finding 2) — a mounted volume whose configured root is gone is not the
same condition as an absent volume or an access failure, and collapsing them
would produce wrong missing-marking or a misleading "offline" label:
- volume found, unique, root present → **resolved**; scan
- volume not mounted → **offline**, not missing (per *Offline Volumes*)
- two+ volumes report the same identity → **ambiguous**, explicit user choice
  required (per *Cloned-Volume Ambiguity*), never resolved silently
- volume found, configured relative root absent → **root_missing**; a real
  condition needing user action (moved/deleted folder), never a location full
  of missing rows
- volume found, root present but unreadable → **root_unavailable**
  (permissions, IO error); an access failure, distinct from absence

**Blocking contract gap (review finding 2).** The scoped-refresh behavior
`INVENTORY.md` describes is currently **unreachable in code**. A selected scan
always reports `complete=False` (`scanner.py:252`:
`complete = requested_scope.kind is ScanScopeKind.FULL`), while the recorder's
selected-path missing branch requires `complete=True` (`recorder.py:573`).
No selected scan can ever reach it. M1 changes `ScanResult.complete` to mean
**complete for the declared `ScanScope`**. `ScanResult.is_full_scan` already
distinguishes full-tree from selected-path scope, so the recorder can retain
its separate full and selected reconciliation branches. A selected scan sets
`complete=True` only after every requested key was conclusively observed as
present, unsupported, or absent; an interrupted or access-failed selected
scan remains incomplete and marks nothing missing. Still **no new scanner
module** — but this is producer/contract work, not pure integration, and it
was missing from this plan's original scope.

**First-location sequence (review finding 2).** Resolving an
already-recorded location is not enough — nothing produces the *first*
non-paired scan today. The explicit sequence: selected path →
host/volume/location registration (`ensure_host`, `observe_volume`,
`ensure_location`) → scan → role-free inventory recording — **and never
`ensure_mapping`**, per *Untracked Ingest Sources* and INVENTORY.md's rule
that location scans never create or infer mapping roles.

Resolution runs **pre-submission, in the facade** — not inside a session —
because there is deliberately no `WAITING_INPUT` state; sessions never block
on a human. Ambiguous → user picks → resubmit with the choice bound in.
Genuinely new code here: the inverse resolver (`VolumeId` → current mount
point); `_resolve_volume` today only goes path → identity.

**Integrity preflight (session-level, for verify/baseline/inventory
sessions):** re-check root → recorded `VolumeId`, online, exactly one match —
at session start, every resume, and queue wakeup, matching the "same
preflight-on-resume posture" §4.6 already promises but nothing implements.
Catches a clone attached *after* commitment (queued verify, disk swapped
mid-wait). Per-item TOCTOU is already covered by the conditional-recording
primitive; no new per-item machinery needed. The narrow inventory-scan case
(disk pulled mid-scan) needs no abort-and-escalate logic of its own — it's
already absorbed by the existing rule that an incomplete scan marks nothing
missing.

### Post-execution verification

**DR-M1-12 — Auto-chained second session, or a phase inside `run_execution`?**
Chaining keeps result shapes clean (no hybrid `OperationResult`) but drops the
volume lock between copy and verify — a foreign sync can interleave before
the medium is attested, wrong for a verified-offload use. An in-session phase
holds custody through both, matches the desired one-tab/one-session UX
exactly, and — since DR-M1-10 already makes the event/history plumbing
mandatory for standalone verify anyway — costs little extra to add.
**Resolution: in-session phase (shape (a))**, with four amendments so it
doesn't corrupt existing invariants:
1. **One nominally typed heterogeneous item list, with an explicit phase on
   every payload.** Add a nominal `ResultItem` marker in `core`; both
   `ItemOutcome` and `IntegrityOutcome` implement it. Each result item carries
   a `phase` value such as `execute` or `verify`, and serialized items carry an
   explicit `item_type` tag as well. `OperationResult` exposes one
   `items: tuple[ResultItem, ...]` in emission order — not separate operation
   and integrity lists, and not a bare union inferred by shape.

   `run_session` accumulates only `isinstance(body, ResultItem)`. Delete the
   current `hasattr(item_id/path)` duck typing; the runner and dispatcher stay
   domain-blind because they know only the marker, phase, and generic item
   identity. History/serialization identifies an item by at least
   `(item_type, item_id)` so ids from different domains cannot collide. Views
   may group or filter the heterogeneous list by phase without changing the
   stored result shape.
2. **Phase-scoped progress.** The verify phase emits its own `PhaseChanged` +
   `Progress` with its own totals; transfer-byte progress and verify
   read-byte progress are never summed (per *Content-Byte Accounting*).
3. **A verify-phase failure degrades the integrity axis; it never rewrites
   filesystem truth — but it must be *reported*, not swallowed.** The copies
   already succeeded; "never wrong, only behind" forbids the terminal lying
   about that. A generic **`PhaseResult`** list sits beside `items`, with one
   entry per entered phase: `phase`, status, byte counts, and optional error.
   This represents a failure before any item exists without creating a
   domain-specific integrity field. Filesystem status may remain `COMPLETED`,
   but the verify `PhaseResult` must then say verification is incomplete.
   Do **not** blanket-convert unexpected exceptions into per-item errors, and
   do **not** catch `BaseException`; narrow expected failures to result items
   and let the phase result carry phase-wide failure.
4. **Pause during the verify phase needs a real continuation.**
   `_ExecutionInvocation.snapshot()` returns `encode_execution_request(...)`
   (`runtime.py:427`) — the original request only, with no phase marker and no
   verifier state. Resuming a session paused mid-verification would repeat
   outcomes or lose phase progress entirely. The continuation payload must
   carry an explicit **phase flag** plus both the execution set and the
   integrity selection/completion state, including enough identity to avoid
   re-emitting already completed `ResultItem` values. The phase flag is
   mandatory even when only one phase has emitted items: resume never infers
   phase from list contents. This is the amendment that makes shape (a)
   honest about pause; without it, in-session verification is only safe for
   sessions that are never paused.

**DR-M1-13 — Scheduling.**
**Resolution:** early in Track B — it's the one M1 item that isn't purely
additive (it touches `run_execution` and `OperationResult`), so it should
settle before Track C builds UI against that result shape, and before it
collides with other work on the same surface.

### GUI toolkit and bridge

**DR-M1-14 — Toolkit.**
The `ui_mockup/` was grounded in real PySide6 files as a pre-Qt-rewrite
staging artifact; that's now stale.
**Resolution: WebView2, hosted via pywebview.** `mockup.html` stops being
throwaway and becomes an actual starting point (rewrite its stated premise
away from "before touching the real PySide6 UI"). `DESKTOP_UI.md` needs a
deliberate rewrite, not a find-and-replace: *Threading And Worker Lifecycle*
dissolves into the single-outbound-pump rule (DR-M1-18 below); roughly a
third of the PoC-regression list is Qt-specific (proxy-style double-free,
stylesheet subcontrols, `QMenu.exec()` hangs, combo arrows, thread-affinity
guards) and should be translated where the underlying concern survives
(thread-affinity marshaling → bridge message ordering) or retired where it
doesn't. Tracked as a Track C deliverable, not a side effect of this doc.
Naming: `interfaces/desktop` → `interfaces/web`, reflected in import-linter
contracts (DR-M1-01).

**DR-M1-15 — Bridge posture.**
Explicit goal: block security loopholes, not build a custom WebView2
embedding. Raw `WebMessageReceived` isn't pywebview's public surface; its
bridge (`js_api`/`expose()`) is.
**Resolution: keep the posture, adapt the mechanism.** Expose exactly **one**
function, `dispatch(command_json)`; schema validation and an explicit
command allowlist sit behind it; nothing else is reachable.

**Amended per review finding 4 — the inbound half alone is not
security-equivalent.** Four gaps this decision originally left open:

1. **Outbound transport is unspecified, and the naive form breaks the
   hostile-filename defense.** Interpolating serialized event data into an
   `evaluate_js` string reintroduces exactly the injection DR-M1-16 exists to
   prevent, one layer down — a filename becomes JS source. Outbound must be
   **data-safe**: pass values as structured arguments to a fixed, pre-loaded
   JS receiver function, never string-built script. No event payload is ever
   concatenated into executable text.
2. **No sender-origin value.** pywebview's exposed functions run on separate
   threads and do not surface WebView2's sender origin, so the adapter cannot
   authenticate a caller the way raw `WebMessageReceived` would. Compensate
   with explicit **trusted-origin and navigation enforcement**: navigation
   locked to the packaged asset origin, external navigation and new-window
   requests refused outright.
3. **The renderer must be forced.** pywebview documents an MSHTML fallback;
   silently accepting it means the product is not reliably WebView2 and the
   CSP/isolation assumptions above do not hold. Force Edge Chromium and
   **fail actionably** if the WebView2 runtime is unavailable — a clear
   install prompt, never a degraded silent fallback.
4. **Separate asset serving from the API surface.** pywebview's built-in local
   server is for packaged UI assets only; it is not an event/API channel and
   must not become one. Restricted to static packaged assets.

Implementation follows the vendor security guidance:
[pywebview bridge](https://pywebview.flowrl.com/guide/interdomain),
[renderer selection](https://pywebview.flowrl.com/guide/web_engine),
[WebView2 security](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security).

**DR-M1-16 — Structural XSS defense, not sanitization.**
NamiSync deliberately retains hostile filenames as escaped scan evidence
(there's already a test corpus for this). A web UI means those filenames
reach a DOM; `innerHTML`-based rendering turns a filename on the user's own
disk into script execution in the shell. Sanitizing paths upstream is the
wrong fix — it corrupts the truth layer, and an escaped-then-echoed path can
target a filesystem operation that doesn't match what's on disk.
**Resolution — commands reference opaque ids; paths are display-only.**
The plan tree already has `operation_id`; inventory rows have canonical keys.
JS never sends a path back over the bridge — only ids; the adapter resolves
server-side. View models carry paths in the **escaped display form** the
scanner's own hostile-name handling already produces (never raw
`rel_path`) — malformed surrogate code units are unrepresentable in UTF-8 and
would mangle or fail on the message channel raw regardless. Sink side: strict
CSP (`default-src 'self'`, no inline script), `textContent`-only rendering,
no `innerHTML` anywhere, and the scanner's existing hostile-name corpus reused
as UI rendering fixtures — the web equivalent of the CLI's `_safe()`.

**DR-M1-17 — Bridge protocol versioning.**
Commands and view models are a new Python↔JS contract shipping in two halves,
same shape of risk the event `Envelope.schema_version` already exists to
prevent.
**Resolution:** version every bridge message, checked on both sides, from
first commit — same law as the event envelope, applied one layer up.

**DR-M1-18 — Large trees over the bridge.**
A directory-rename decomposition can be thousands of rows; pushing a whole
plan through one `evaluate_js` call is a latency/memory cliff, and naive
per-event pushing rebuilds the PoC's per-chunk UI flood one language over.
**Resolution:** small state-change events push through the bridge; the plan
tree, inventory tree, and history detail are paged **pull** commands. One
serialized outbound queue coalesces `Progress` to its latest snapshot before
marshaling — the `LOSSY` delivery class, applied at the bridge boundary.

**DR-M1-19 — Session observation: one thread per live session now, kept
swappable for later.**
Each `EventStream` owns a private `Condition`, so nothing except the observer
itself forces per-stream threads; `EventHub.emit` fans out synchronously and
non-blocking under the hub lock, so subscriber count never backpressures the
producer. Live sessions are bounded by volume-disjointness — realistically
single digits — so one thread per live session is not a scaling problem at M1
or M2. Building a multiplexer now would be speculative.
**Resolution:** don't scale it; keep it swappable. The facade's public
surface is a **sink** (`observe(session_id, sink)`), never a raw
`EventStream` — `EventStream` never escapes `interfaces/service`. The sink is
keyed by session id, not subscription identity, so a future multiplexer
changes internals only. Resubscribe/gap handling lives in the observer
(already required by DR-M1-01/07). All producers converge on the single
outbound pump (DR-M1-18) regardless of thread count.
**Two fixes to get right the first time, not the tenth:** (1) block on
`stream.next()` with no timeout and exit on `Terminal`/`StopIteration`
instead of the CLI's current `timeout=0.1` poll that also re-checks
`record.result` every pass; (2) read `dispatcher.get()` **before**
subscribing and return an already-terminal result directly — a short session
can finish between submit and subscribe, and `subscribe()` raises
`SessionNotFound` once the hub is gone.

**Mandatory shutdown contract (review finding 10).** Removing the poll is
only safe with an explicit teardown path: an indefinite `next()` on a stream
nobody closes hangs its thread forever, and with it window close or app exit.
`SessionObserver` therefore **retains every stream it opens and closes them
all before joining observer threads** — `EventStream.close()` sets `_closed`
and calls `notify_all()`, which is what makes a blocked `next()` raise
`StopIteration` and let the thread exit. Required coverage, none of which
exists today: explicit unsubscribe of a live session, window close during an
active session, and application shutdown with sessions still running.

### Maintenance and retention

**DR-M1-20 — Where does history retention run?**
`FEATURES.md`'s *Scheduled Integrity Maintenance* argues against a **separate
daemon**, not against a plain function call — and describes *scheduled*
maintenance, which M1 doesn't have. `DESKTOP_UI.md` says retention runs
"through workflow, not direct UI SQL." Read together (FEATURES owns behavior,
per the precedence rule) these agree.
**Resolution:** M1 retention is **user-invoked**, a facade-invoked workflow
function against a writable history connection — not a daemon, not UI SQL,
an app-owned artifact exempt from the pipeline-mutation law. Uses the same
bounded busy timeout as every other writer. When scheduled maintenance
arrives later, it becomes a session kind wrapping this same function, not a
rewrite.

**Corrected per review finding 6.** The original entry claimed retention was
"history-logged" with session-like semantics while explicitly *not* being a
session, and asserted it would never degrade audit without any mechanism
enforcing that. Both claims are withdrawn:
- A plain function is **not** a session and does not get session or history
  semantics. It produces no history envelope of its own in M1. If a durable
  record of retention runs is wanted, that is the argument for making it a
  maintenance session — deferred, not smuggled in.
- "Never runs inside the audit path" is not self-enforcing. A retention
  write holding the history SQLite write lock can overlap a live session's
  audit timeout and degrade its `audit` axis. M1 **gates retention until
  active audit writers drain** — the facade refuses to start a sweep while
  any live session holds an audit subscription; the UI disables the action
  with an explanation until the gate clears, and CLI reports the same
  actionable condition. The sweep is expected to be short on M1-sized local
  databases. That is the honest M1 bound; coordinated history-writer custody
  is a maintenance session's job, and it is deferred with it.

---

## 3. Track Deliverables

### Track A — Interface Substrate

- `interfaces/service.py`: composition root (registry + per-kind pause
  capability table, moved out of `cli.py`), runtime/dispatcher lifecycle
  management, plan/execute sequencing (`plan_and_review`,
  `commit_and_execute`)
- `SessionObserver`: sink-based (DR-M1-19), resubscribe + `Gap` recovery,
  get-before-subscribe race fix, no polling
- `ResultCategory` classification, shared by CLI exit-code mapping and GUI
  headline/color mapping. **Four axes, not one (review finding 8):**
  `filesystem`, `integrity`, `recording`, and `audit` stay independent —
  a single generic `degraded` must never hide whether the cause was a hash
  mismatch, a lagging ledger, or a failed history write. Categories:
  refused, canceled, failed, partial, all-noop, success, plus the integrity
  axis's **mismatch** and **verification-incomplete**. Headline precedence is:
  **failed > partial > refused > mismatch > canceled >
  verification-incomplete > recording/audit degradation > all-noop >
  success**. Cancellation sits below mismatch because it is deliberate user
  input, but remains adjacent to incomplete verification. The non-headline
  axes are always rendered rather than dropped
- Remove `worker_count` from `SyncOptions`, `Plan`, payloads, and fingerprints;
  do not replace it with an execution setting while concurrent file execution
  is deferred (DR-M1-05; `HASH_REFACTOR.md`)
- Add the nominal `ResultItem` marker, phase-tagged heterogeneous
  `OperationResult.items`, generic `PhaseResult` summaries, and the explicit
  continuation phase flag before either integrity producer is wired
  (DR-M1-12)
- `workflows/views.py`: `SessionEventView`, `SessionRecordView`,
  `OperationResultView`, `IntegrityOutcomeView`, `InventoryRowView`
  (DR-M1-07)
- `db/settings.py` (semantic + operational, named-mutex-serialized
  read-modify-replace) and
  `interfaces/ui_state.py` (cosmetic) (DR-M1-03/04); remove the execution
  preflight settings reader and drift refusals; canonical snapshot fingerprint
  function remains in `core/` (DR-M1-05)
- Runtime/facade `save_plan`/`get_plan`/`drop_plan` seams over the existing
  private in-memory dictionary; no `PlanStore` abstraction (DR-M1-08)
- Remove the duplicated path validator in `cli.py` (`_validated_paths`
  duplicates `workflows/sync.py`'s `_validated_roots`); facade exposes the
  workflow's own check as a pre-submit call
- Retarget `cli.py` onto the facade; 13 existing end-to-end tests as the
  regression net (DR-M1-02)
- Import-linter contracts: `cli`/`web` mutually forbidden, both import
  `service`, `service` imports neither

### Track B — Integrity Spine

- Land `HASH_REFACTOR.md`'s fixed XXH3-128 content-evidence contract and
  parameterless hasher-factory inversion seam before wiring `run_integrity`:
  `ExecutorPolicies` requires an explicitly constructed `NativeCopyBackend`,
  workflow composition supplies the sole XXH3 implementation, and the new
  production `VerifierContext` construction receives the same seam
- Land the bounded single-file read/write/hash copy pipeline as the independent
  executor track defined by `HASH_REFACTOR.md`; it does not introduce
  concurrent file execution
- `run_integrity` workflow (inventory / baseline / verify), gated
  by the integrity preflight (DR-M1-11)
- Inventory workflow: five-state volume resolution ladder + first-location
  registration sequence + scoped scan-and-record reusing the existing scanner
  (DR-M1-11); acknowledge/restore, staleness queries against
  `LedgerRepository`
- Scoped-completeness contract fix so selected refreshes can actually reconcile
  (DR-M1-11 — currently unreachable; `scanner.py:252` vs `recorder.py:573`)
- **Mapping-filter/exclusion persistence** — `INVENTORY.md` assigns it to M1
  ("mapping-filter state ... remain M1 work") and this plan originally omitted
  it (review finding 7). Filtered rows are marked excluded, never missing or
  deleted, and an exclusion can never become a target deletion candidate
- **`rebaseline` entry points** — the verifier already implements explicit
  rebaseline (*Accept and Re-Baseline*); M1 must expose it via CLI and UI, not
  leave it callable-but-unreachable (review finding 7)
- Dispatcher registration for verify/baseline/inventory session kinds with
  correct per-kind pause capability
- `IntegrityOutcome` added to `core/events.py`'s `EventBody` (schema
  version bump); both outcome types implement nominal `ResultItem`, and
  serializer/history/view support preserves `item_type`, `phase`, item order,
  and `PhaseResult` summaries (blocks on Track A's DR-M1-07 — the critical
  path, DR-M1-10/12)
- Post-execution verification as an in-session phase of `run_execution`
  (DR-M1-12/13), scheduled early
- History schema v3: integrity summaries and retained issue detail — via
  reset, not migration (DR-M1-09)
- Retention sweep function on a writable history connection, facade-invoked
  (DR-M1-20)
- CLI commands: `inventory`, `baseline`, `verify` — built
  against Track A's facade once it exists

### Track C — Web Desktop Shell

- pywebview host; `nami-sync-gui` entry point + no-subcommand launch
- Bridge: single `dispatch(command_json)`, schema-validated, allowlisted,
  versioned (DR-M1-15/17); ids-not-paths + escaped-display rule (DR-M1-16);
  push for small events, pull for plan/inventory/history trees (DR-M1-18);
  result messages carry explicit `item_type` and `phase` fields rather than
  asking JavaScript to infer either from payload shape
- CSP (`default-src 'self'`, no inline script), `textContent`-only
  rendering, no `innerHTML`, remote navigation disabled
- Task rail, single-page task shell, plan tree, inventory tree, history
  dialog — built only against Track A's views/facade
- GUI single-instance lock via a named mutex (the dispatcher's existing
  cross-process volume-mutex pattern, applied to instance ownership)
- `DESKTOP_UI.md` rewrite for the web target (DR-M1-14); `ui_mockup/`'s
  stated premise updated to reflect it's now a real starting point

---

## 4. Explicitly Deferred (not M1)

- General, versioned migration module — stays past M3 (DR-M1-09); M1 uses
  reset-and-refuse for the v2→v3 history bump
- Durable plan/session persistence (`SqliteSessionStore`) — M2; M1 ships the
  named runtime/facade access seams only, with no storage abstraction
  (DR-M1-08)
- Cross-process task visibility in the GUI — depends on the same M2 durable
  session store
- Scheduled/daemon-driven maintenance — M1 retention is user-invoked only
  (DR-M1-20)
- Observer thread multiplexing — not needed at M1/M2 scale; sink API keeps it
  swappable (DR-M1-19)
- Concurrent file execution, multithreaded verification, background
  integrity, and repair guidance — deferred; `HASH_REFACTOR.md` requires new
  post-XXH3 utilization evidence before file-level workers are introduced

---

## 5. Acceptance Notes

Each track's work should land with the same standard the M0 module docs use:
a named failure-injection or regression test per behavior, not just "tested."
Specific ones worth calling out because they don't exist yet and are easy to
skip:

- The XXH3-128 replacement and copy pipeline satisfy every collaborator,
  vector, acknowledgement, failure, and cancellation test listed in
  `HASH_REFACTOR.md`; M1 does not weaken that document's gates.
- A global semantic-settings change leaves an admitted plan's captured
  snapshot and execution behavior unchanged, while a task-local edit during
  review invalidates that plan and requires replanning (DR-M1-05/06).
- Two concurrent semantic-settings commits serialize through the named mutex;
  the second writer re-reads after acquiring it and preserves the first
  writer's unrelated keys (DR-M1-04).
- A cloned volume attached after a verify session is **queued** (integrity
  workflows carry no commitment) is caught by the integrity preflight at
  resume/wakeup, not silently resolved (DR-M1-11).
- A selected inventory refresh actually reconciles the requested keys — the
  regression that proves the `scanner.py:252` / `recorder.py:573`
  completeness gap is closed rather than still unreachable (DR-M1-11).
- A session paused mid-verification resumes without repeating or losing
  result items, proving the continuation carries the explicit phase flag plus
  integrity selection/completion state, not just the execution request
  (DR-M1-12).
- A canceled or failed mixed-phase session returns one ordered heterogeneous
  `items` list whose entries retain nominal `item_type` and `phase` tags; no
  integrity item is lost or swept into an operation-only accumulator
  (DR-M1-12).
- An outbound bridge message carrying a hostile filename reaches JS as
  structured data and never as interpolated script text (DR-M1-15).
- Observer teardown: unsubscribe, window close, and app shutdown with a live
  session each terminate every observer thread rather than blocking forever
  (DR-M1-19).
- A verify-phase exception during post-execution verification leaves the
  execution's filesystem status `COMPLETED` and reports the exception as an
  incomplete verify `PhaseResult`, never as execution `FAILED`
  (DR-M1-12).
- A hostile filename never reaches JS as anything but its escaped display
  form, and no bridge command can be constructed from a raw path (DR-M1-16) —
  reuse the scanner's existing hostile-name corpus as the fixture set.
- The CLI's 13 end-to-end tests pass unchanged after the Track A retarget,
  proving equivalent-request/equivalent-result-classification across
  interfaces before a second interface exists to test it against
  (DR-M1-02/07).

---

## 6. Sanity Review Notes — 2026-07-22

This section records the adversarial review of the plan. It is appended rather
than folded into the decision log so the original planning rationale remains
visible. Findings are implementation gates unless explicitly marked
non-blocking.

**Disposition (2026-07-22).** All ten findings were verified against the code
and resolved into §2 and §3 above. Four load-bearing claims were confirmed at
source and are the reason this review mattered:

| Finding | Verified at | Status |
| --- | --- | --- |
| 1 — worker count is fingerprinted despite the doc's claim | `planning.py:301`, `:404`, `:411` (`asdict(plan)`) | Confirmed; DR-M1-05 now removes it without replacement |
| 2 — scoped missing-marking is unreachable | `scanner.py:252` vs `recorder.py:573` | Confirmed; contract fix added to Track B |
| 3 — runner sweeps integrity outcomes into `operations` | `session.py:255-258` duck-types on `item_id`+`path`; `integrity.py:180-182` has both | Confirmed; nominal `ResultItem` plus one phase-tagged heterogeneous list replaces duck typing |
| 3 — pause loses verifier state | `runtime.py:427` snapshots the request only | Confirmed; explicit continuation phase flag and completion state added |

Later decisions refined three original dispositions, with the binding result
recorded in the decision log above:

- **Finding 1's remedy.** Frozen per-session settings snapshots are now the
  settled model. DR-M1-06 describes lifecycle UX rather than advisory drift
  refusal, and `worker_count` is removed rather than relocated.
- **Finding 3's remedy.** The result does not grow parallel domain lists. A
  nominal `ResultItem` marker, one heterogeneous phase-tagged item list,
  generic phase summaries, and an explicit continuation phase flag guide the
  runner, history, views, and resume payload.
- **Finding 9 (`PlanStore` speculative).** No protocol or storage abstraction
  is introduced. Named runtime/facade methods preserve only the present-tense
  access seam around the existing dictionary.

Finding 5 is resolved with a named cross-process mutex held only around the
semantic settings read-modify-atomic-replace transaction. It does not reserve
settings for an interface's lifetime. `interfaces/service.py` still reaches
`db/settings.py` through the injected runtime rather than importing it, since
the import law forbids `interfaces → db` outright.

Finding 6's plain-function resolution is explicitly accepted for M1. The
facade gates the short retention sweep until active audit writers drain; it
does not gain dispatcher-session or history semantics.

Finding 8's headline precedence is now explicit, with deliberate cancellation
below integrity mismatch and adjacent to incomplete verification. All four
axes remain visible regardless of headline.

The editorial corrections (stale `DR-M1-12` cross-references, the precedence
note's wrong attribution, "committed verify session", and this document's
standing relative to the active docs) are all applied above.

### Blocking findings

#### 1. Commitment semantics contradict themselves

The reviewed draft said that defaults changed after commitment affected only
new plans, but then said that the same change refused an outstanding
commitment. Those are different policies. The settled correction is the
frozen-session model: the commitment executes its reviewed policy snapshot,
and current defaults do not invalidate it. DR-M1-06 is retained only as the
lifecycle/interaction rule for editing task-local bound controls; its former
advisory drift-refusal behavior is removed.

Excluding `worker_count` from `policy_fingerprint` is also insufficient while
`worker_count` remains a field on `Plan`: the full plan fingerprint hashes the
whole plan. Because concurrent file execution is now deferred, M1 removes the
field without replacing it with another setting.

#### 2. The inventory producer and state vocabulary are incomplete

DR-M1-11 distinguishes online, offline, and ambiguous volumes, but omits
`ROOT_MISSING` and `ROOT_UNAVAILABLE`. A mounted volume whose configured
relative root is absent is not the same as an unmounted volume or an access
failure.

The existing selected scanner reports `complete=False`, while the recorder's
selected-path missing reconciliation requires `scan.complete=True`. Therefore
the proposed scoped missing behavior is currently unreachable. The settled
contract makes completeness relative to the declared scope and keeps
`is_full_scan` as the full-tree discriminator; it does not need a new scanner
module, but it does need producer/contract work.

The plan also needs the first-location sequence explicitly: selected path →
host/volume/location registration → scan → role-free inventory recording,
without creating a mapping. Resolving an already-recorded location is not
enough to produce the first non-paired scan.

#### 3. In-session verification lacks a safe result and continuation shape

Adding a separate `OperationResult.integrity` field would not stop the generic
session runner from collecting objects with `item_id` and `path` into its
existing `operations` tuple. The settled correction is one nominal
`ResultItem` list: both outcome types implement the marker and carry explicit
`phase` and serialized `item_type` tags. The runner accumulates by nominal
marker only, never by domain type or attribute shape.

Pausing during the verification phase also serializes the execution request but
not verifier selection/completion state. Resume would repeat outcomes or lose
phase progress. The continuation carries an explicit phase flag plus both the
execution set and integrity selection/completion state; phase is never inferred
from accumulated items.

The heterogeneous item tuple is still insufficient for a phase-wide failure
before an item exists. Generic `PhaseResult` entries carry phase status, byte
counts, and an optional error alongside the item list. Unexpected exceptions
are not converted blindly into item errors or caught as `BaseException`. Copy
success may remain `COMPLETED`, but the verify phase must say that verification
is incomplete.

#### 4. The pywebview bridge is not yet security-equivalent to raw WebView2
messages

DR-M1-15 defines an inbound `dispatch` function but not a safe outbound
mechanism. pywebview exposed functions run on separate threads and do not
provide WebView2's sender-origin value. The plan therefore needs an explicit
trusted-origin/navigation enforcement mechanism and a data-safe host-to-JS
transport. Interpolating serialized event data into `evaluate_js` would
undermine the hostile-filename defense.

The plan must also force the Edge Chromium renderer and fail actionably when it
is unavailable. pywebview documents an MSHTML fallback; accepting that fallback
means the product is not reliably WebView2. Static asset serving through
pywebview's built-in local server must be distinguished from an event/API
server and restricted to packaged UI assets.

The bridge implementation must follow the relevant security guidance:

- [pywebview JavaScript/Python bridge](https://pywebview.flowrl.com/guide/interdomain)
- [pywebview renderer selection](https://pywebview.flowrl.com/guide/web_engine)
- [Microsoft WebView2 security guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security)

### Significant corrections

#### 5. Settings concurrency is still lossy

Rereading immediately before replacement narrows the race but does not prevent
two processes from reading the same version and overwriting each other's
changes. Semantic settings deserve a named mutex/file lock or revision-based
compare-and-swap. The plan should also state that `interfaces/service.py`
reaches `db/settings.py` through an injected workflow/runtime service so the
import law remains intact.

#### 6. Retention lifecycle and audit isolation are unresolved

DR-M1-20 calls retention facade-invoked, workflow-owned, and history-logged,
but does not make it a dispatcher session. It also cannot guarantee that
retention never degrades audit if its SQLite write lock overlaps the audit
timeout. Either make retention a maintenance session with coordinated
history-writer custody, or explicitly gate it until active audit writers drain.
If it remains a plain function, remove the claim that it has the same session
and history semantics as long-running activities.

#### 7. M1 scope omits already-defined behavior

The plan should explicitly include:

- the implemented verifier's explicit `rebaseline` operation and its CLI/UI
  entry point;
- mapping-filter/exclusion persistence, which the inventory contract assigns
  to M1; and
- role-free location creation for the first inventory scan.

#### 8. Result classification needs an integrity axis

Track A's `ResultCategory` list includes refused, canceled, failed, degraded,
partial, all-noop, and success, but not mismatch or incomplete verification.
Define headline precedence while preserving `filesystem`, `integrity`,
`recording`, and `audit` as independent axes. A single generic `degraded`
category must not hide whether the problem was a hash finding, ledger lag, or
history failure. Settled precedence:
`failed > partial > refused > mismatch > canceled > verification-incomplete >
recording/audit degradation > all-noop > success`.

#### 9. `PlanStore` is speculative in the current milestone

DR-M1-08 proposes a protocol with only an in-memory implementation for an M2
durability change. That is an abstraction for a future single implementation
and conflicts with the repository rule to avoid speculative seams. Keep the
existing private in-memory plan dictionary until durable plan/session storage
is actually implemented, unless M1 has a present-tense second consumer for the
protocol.

#### 10. Blocking observers need an explicit shutdown contract

Replacing the CLI's polling with an indefinite `stream.next()` is sound only
if `SessionObserver.close()` retains and closes every stream before joining
observer threads. Add unsubscribe, window-close, and application-shutdown
tests; otherwise a live session can leave the GUI waiting forever.

### Non-blocking editorial and terminology corrections

- The opening documentation-precedence note attributes the conflict to
  `DR-M1-14`, although that decision is the toolkit decision rather than the
  precedence decision.
- The DR-M1-07 paragraph points bridge serialization to `DR-M1-12`; the bridge
  decisions are DR-M1-15 through DR-M1-18.
- DR-M1-14 says the single-outbound-pump rule is “DR-M1-12 below”; the pump is
  specified under DR-M1-18.
- “Committed verify session” in the acceptance notes is inconsistent with the
  plan's non-commitment integrity workflow. Use “queued verify session” or
  “verify session admitted with a stale volume snapshot.”
- The precedence rule says `FEATURES.md` owns behavior while this plan
  intentionally postpones the corresponding active-document edits. Either
  state that this plan governs unimplemented M1 decisions until promotion, or
  update the affected active documents before implementation starts.
