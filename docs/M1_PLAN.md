# M1 Plan

Status: planning decisions revised and reconciled 2026-07-24. Stages 1–3
(contracts/semantics, executor/hash refactor, and inventory/standalone
integrity) landed on 2026-07-24; Stages 4–6 remain unimplemented. This is both
the milestone plan and the decision log for the choices made
while shaping it. Cross-cutting decisions are summarized in `ARCHITECTURE.md`,
`FEATURES.md`, and `WORKFLOWS.md`; individual component documents update as
their code stages land. This file remains the detailed record of *why* and of
the integration gates, the same role `DESIGN_REVIEW.md` plays for M0.

**Documentation precedence**, stated once here because it resolved a real
conflict during this planning pass (DR-M1-20, retention): `FEATURES.md` owns
behavior, `ARCHITECTURE.md` owns contracts, module docs are subordinate to
both. Where a module doc reads stricter or looser than FEATURES/ARCHITECTURE,
the module doc is what's stale.

**Standing of this document.** This plan governs unimplemented M1 decisions
until each is promoted into the active documents. It does not silently
override `FEATURES.md` or `ARCHITECTURE.md` for anything already implemented;
where it changes a settled bullet (DR-M1-03's settings-file split, DR-M1-05's
worker-count removal), the active document is edited **as that stage
lands**, not deferred indefinitely. Once a decision is promoted, the active
document wins and this file becomes history — the same lifecycle
`DESIGN_REVIEW.md` has.

---

## 1. What M1 Actually Is

`ARCHITECTURE.md` §6 compresses M1 to one line — "integrate the verifier
through baseline + inventory + history integrity detail + retention." That
both undersells it and retains one stale scope item: retention is deferred by
DR-M1-20 until cross-process history-writer custody exists. The verifier
operation module is done; M1 builds the **second
workflow family** it plugs into: a one-location, no-plan, no-commitment shape
that M0 never needed, plus the interface substrate that M0's CLI never had to
build properly because it only ever had one workflow to drive.

M1 is a dependency graph, not three nominally parallel tracks. Its binding
sequence is:

1. **Contracts and semantics.** Settle the fixed content-evidence contract,
   both-database reset boundary, generic standalone-integrity event/result
   vocabulary, settings semantics, and the post-execution state machine. This
   stage decides compound-session semantics but does not merge unused
   compound-only abstractions.
2. **Executor refactor according to `HASH_REFACTOR.md`.** Land Track 1's full
   adaptive pipeline and IO/finalization reductions first. Land Track 2's
   wholesale XXH3-128 replacement second, including both executor and verifier
   consumers; production integrity-workflow wiring remains in the next stage.
3. **Inventory and integrity.** Build inventory production and standalone
   baseline/verify/rebaseline sessions against the now-fixed contracts.
4. **Integration.** Add post-execution verification as one vertical slice:
   published-evidence continuation, transient verification candidates,
   compound phase results, pause/resume encoding, history, and views become
   live together rather than appearing as dormant seams in separate modules.
5. **Facade and CLI.** Retarget the existing CLI and expose the new workflows
   through one interface service.
6. **GUI shell.** Build the pywebview/WebView2 shell only against the settled
   facade, views, and compound result contract.

The graph still permits bounded parallel development. These are work lanes,
not permission to merge a consumer before its prerequisite:

- HASH Track 1 may run beside a Stage 3 branch containing the
  standalone-integrity event/result implementation and inventory producer
  because their semantics and main diff surfaces are independent. That branch
  merges its vocabulary with its first producer and does not finish
  baseline/verify wiring until HASH Track 2 is available.
- The inventory producer work — volume/root resolution, first-location
  registration, scoped completeness, and exclusion persistence — may run
  beside the HASH executor work after its core contracts are fixed. Standalone
  verification wiring still waits for HASH Track 2.
- Facade extraction that preserves existing M0 behavior may run beside late
  inventory/integrity work after result and view contracts stabilize. New CLI
  commands wait for their workflows.
- A static GUI layout and hostile-navigation bridge spike may run early, but
  no GUI binding to session/result data lands before the facade and integration
  contracts are settled.

Post-execution integration itself is deliberately serial after standalone
integrity. It is the proof that the executor, verifier, recorder, continuation,
history, and result contracts compose; splitting that proof among parallel
module changes would hide the very semantic failures the stage exists to find.

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
Before Stage 1, the single `StaticSettingsReader` was fed the plan's own filter snapshot
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
  trash-on-update default). Written through the facade on explicit settings
  commits. No unused retention key ships while retention is deferred.
- `ui-state.json`, owned by `interfaces/`: recents (5 source + 5 target,
  maintained separately, per the settled FEATURES bullet), window geometry,
  column/sort state. Plain file the GUI owns outright; `interfaces/` may
  write files, it just can't import `db/`.
This amends the FEATURES.md *Local Settings File* bullet from one file to
two — the smaller edit, given what it buys.
**Also removes obsolete preflight plumbing:** the `SettingsReader` protocol
and `StaticSettingsReader` existed only to feed live filter/policy
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

`worker_count` is not semantic intent, but before Stage 1 it was embedded in
both `SyncOptions` and `Plan`, so the full plan fingerprint bound it
accidentally. Stage 1 removed it rather than relocating it to another public setting: concurrent
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

**DR-M1-09 — Ledger/history schema reset, or migration?**
Tagged `ResultItem` values and generic phase summaries need a home in history
detail, while `HASH_REFACTOR.md` makes existing main-ledger content evidence
incompatible by replacing SHA-256 with the single `xxh3_128` contract. History
was v2 with one narrow v1→v2 migration before Stage 1; the main ledger was v1.

**Resolution — reset both databases, migrate neither.** NamiSync is unreleased
and tested only in closed environments. M1 bumps both schema versions, refuses
every older ledger or history version with one actionable reset message, and
deletes/recreates both databases as one development boundary. No ledger rows,
content evidence, history rows, or run detail cross the boundary. Settings
files are not databases and survive it.

The final integrated contract is frozen by decision
`M1-SCHEMA-CONTRACT-20260724-02`: metadata key `contract_id`, ledger value
`m1-ledger-xxh3-128-mapping-filters-v1`, and history value
`m1-history-generic-items-phases-v1`. For a nonempty database, startup checks
the supported numeric version and then this exact opaque marker through a
read-only connection before opening any writer or running the schema script.
Missing/mismatched markers—including transitional Stage 1 v2/v3 files—take the
same reset-both refusal. Fresh initialization writes both exact markers; normal
reopen is a no-op. There is no backfill, migration, or second numeric version
bump.

The former `_migrate_history()` shortcut had to be removed before the history
constant was raised: it wrote the current
`HISTORY_SCHEMA_VERSION`, so merely changing that constant to 3 would falsely
promote a v1 database to v3 after applying only the v2 column change. Required
coverage refuses ledger v1, history v1, and history v2 rather than silently
upgrading any of them.

The general versioned migration module stays deferred past M3, unchanged from
`ARCHITECTURE.md`'s build order. This decision does not pull it forward; it
explicitly declines to.

**DR-M1-10 — Ordering: view vocabulary vs. verifier wiring vs. post-exec
verify (DR-M1-13)?**
`IntegrityOutcome` exists in `core/integrity.py` but is absent from
`core/events.py`'s `EventBody` union; today it silently vanishes from history
(`HistoryObserver.on_event` only collects `ItemOutcome`, and the generic
`_primitive` hasher doesn't error on the unrecognized type — it just isn't
appended). Wiring the verifier to a session before adding the nominal
`ResultItem` contract and phase/item tags would produce integrity history that
comes back empty or structurally ambiguous with no failure anywhere.
**Resolution:** vocabulary before its first producer, but no dormant
compound-session scaffolding. The nominal `ResultItem`, integrity event union,
explicit `item_type`/`phase`, serializer, history support, and views land with
standalone `run_integrity`, which consumes them immediately. Compound-only
contracts — published-evidence continuation, transient post-copy candidates,
generic `PhaseResult`, and an execute/verify continuation discriminator — land
together in the later post-execution integration slice. "Settle semantics
early" means freeze their behavior and tests now, not spread unused optional
fields through every layer before integration. The one deliberate exception is
the final history-v3 storage shape: it reserves phase-summary storage before
HASH Track 2 performs the single coordinated database reset, so Stage 4 does
not force a second schema bump. No producer/serializer uses that storage until
the integration slice.

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
**Resolution: one in-session execute → verify state machine**, with these
binding contracts:

1. **The immediate evidence handoff does not query the ledger.**
   `ExecutionSet`, which already owns mutable pause continuation, gains
   `published_evidence: op_id → PublishedCopyEvidence`. Every successfully
   settled `COPY`, `UPDATE`, or `MOVE_UPDATE` has exactly one entry containing
   its post-publish `Attestation` and whether the copy-ledger transaction
   succeeded. `_settle()` stores successful status and evidence together
   before emitting the reliable item outcome. A successful byte-producing
   status without evidence is an internal invariant failure and makes
   verification incomplete.

   This must live in continuation rather than only an executor return value:
   the executor does not return when it pauses. The execution payload encodes
   `published_evidence` alongside status, so a same-process pause during
   execution preserves evidence for already published operations. M1's
   process-local session store still means no pause or evidence continuation
   survives closing/restarting the application; durable resume remains M2.

2. **The recorder is a guard and durable store, not an independent digest
   oracle.** It validates reviewed operation identity, kind, provenance,
   size/stat binding, intended metadata, and idempotent payload identity, but
   it cannot recompute whether digest bytes came from the source. A rejected
   or failed record degrades recording and execution continues. Immediate
   readback therefore consumes the transient copy attestation; the ledger is
   the durable source for later standalone integrity runs.

   A malicious in-process executor is outside this trust model: it could lie
   consistently to any in-process handoff or interfere with result reporting.
   Independent readback protects against ordinary copy bugs, IO corruption,
   and recorder failure, not hostile executable code.

3. **Post-copy candidates are not inventory-row selections.** The verifier
   gains a transient candidate contract rooted in successful byte-producing
   publishes, carrying expected post-publish stat and copy attestation whether
   or not a ledger row exists. It shares the existing guarded
   open/stat/hash/classification body with ledger-bound verification rather
   than duplicating a byte loop. When copy evidence was durably recorded, a
   matching readback may conditionally advance ledger verification state.
   When it was not, byte classification still completes while the recording
   axis remains degraded; M1 does not invent fake row ids or silently
   reconstruct a missing sync transaction.

   **Type ownership and import direction:** `PublishedCopyEvidence` lives in
   `core/execution.py` because `ExecutionSet` stores it.
   `PostCopyCandidate` lives in `core/integrity.py` because it is a
   verifier-input contract shared across the workflow/module boundary. The
   discriminated `ExecuteContinuation | VerifyContinuation` payload is owned
   by `workflows/` and may reference those core types; core never imports a
   workflow continuation type. The sync workflow alone translates published
   evidence into verification candidates. `PostCopyCandidate` contains the
   verifier-facing values rather than embedding or importing
   `PublishedCopyEvidence`, so executor and verifier remain sibling modules
   with no direct dependency. The dispatcher continues to hold only opaque,
   schema-versioned payload bytes.

4. **Filesystem, integrity, recording, and audit remain separate truths.**
   A publish may be `succeeded`, its readback `verified`, and its ledger
   recording `degraded` at the same time. A readback mismatch does not rewrite
   the already successful filesystem operation, and a successful ledger write
   does not prove readback. Conditional verification recording that becomes
   stale after a match reports `verified + recording degraded/stale`, not a
   false hash failure.

5. **One nominally typed heterogeneous item list.** `ItemOutcome` and
   `IntegrityOutcome` implement `ResultItem`; each carries an explicit
   `phase`, and serialization carries `item_type`. `OperationResult.items`
   preserves emission order. `run_session` accumulates only nominal
   `ResultItem` values, never the current `hasattr(item_id/path)` duck type.
   History identity includes at least `(item_type, item_id)`.

6. **Phase-scoped progress and phase-wide truth.** Transfer and readback byte
   counts are never summed. A generic `PhaseResult` for each entered phase
   carries status, phase-local counts, and optional error, so a failure before
   any verification item exists remains visible. Unexpected exceptions are
   not blanket-converted into item errors and `BaseException` is not caught.

7. **Explicit continuation state.** The payload is a discriminated
   continuation, not an execution request plus optional fields:
   `phase=execute` carries the execution set/status/published evidence;
   `phase=verify` additionally carries transient candidates and completed
   verification ids/bytes. Resume never infers phase from emitted items and
   never re-emits a completed reliable result.

The state transitions are fixed before implementation:

```text
execute
  pause  -> snapshot execute status + published evidence
  cancel -> terminal canceled; do not start new readback work
  settle -> verify when at least one successful byte-producing candidate exists

verify
  pause    -> snapshot candidates + completion state
  cancel   -> filesystem truth retained; verification canceled/incomplete
  mismatch -> filesystem truth retained; integrity mismatch
  record failure -> byte result retained; recording degraded
  complete -> one compound terminal result
```

Successful publishes remain eligible for verification even when a later
independent operation makes execution partial/failed. `NOOP`, metadata-only
move, directory, trash, and delete operations are not post-copy candidates.
Target stat drift before/during readback is `modified`, not `hash mismatch`.
The logical sync recording remains unfinished through both phases and is
finished once at compound terminal settlement. A pause may close and
idempotently reopen its process-local recorder on resume; one invocation
exposes narrow execution and integrity recorder views rather than opening
competing writers.

**DR-M1-13 — Scheduling.**
**Resolution:** decide the state machine early, implement it later as one
vertical integration slice after standalone integrity works. The slice may be
reviewed as ordered commits, but it does not merge dormant compound-only seams:

1. executor evidence and its payload round-trip;
2. transient verifier candidates sharing the existing classifier;
3. compound phase/result and continuation encoding;
4. `run_execution` wiring plus recorder lifetime;
5. history/view/facade consumption and end-to-end pause/failure tests.

All five are one integration gate. Stage 6 does not bind to compound results
until it passes.

### GUI toolkit and bridge

**DR-M1-14 — Toolkit.**
The `ui_mockup/` was grounded in real PySide6 files as a pre-Qt-rewrite
staging artifact; that's now stale.
**Resolution: WebView2, hosted via pywebview.** `mockup.html` stops being
throwaway and becomes an actual starting point (rewrite its stated premise
away from "before touching the real PySide6 UI"). `DESKTOP_UI.md` needs a
deliberate rewrite, not a find-and-replace: *Threading And Worker Lifecycle*
dissolves into the single bounded event-drain rule (DR-M1-18 below); roughly a
third of the PoC-regression list is Qt-specific (proxy-style double-free,
stylesheet subcontrols, `QMenu.exec()` hangs, combo arrows, thread-affinity
guards) and should be translated where the underlying concern survives
(thread-affinity marshaling → bridge message ordering) or retired where it
doesn't. Tracked as a Stage 6 deliverable, not a side effect of this doc.
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

1. **Host-initiated JavaScript is unnecessary and forbidden for application
   data.** Interpolating serialized event data into `evaluate_js` would make a
   filename JavaScript source; pywebview's `evaluate_js` also has no structured
   argument channel. JavaScript initiates every exchange through
   `dispatch(command_json)` and receives ordinary structured return values.
   Live delivery uses one outstanding `next_events`/event-drain request against
   a bounded Python queue. Neither `evaluate_js`, `run_js`, nor
   `Window.state` is an application-data channel. No event payload is ever
   executable text.
2. **No sender-origin value.** pywebview's exposed functions run on separate
   threads and do not surface WebView2's sender origin, so the adapter cannot
   authenticate a caller the way raw `WebMessageReceived` would. Public
   `before_load` is not a documented cancellation hook, and pywebview's
   Windows backend otherwise redirects a new-window request into the existing
   view when external opening is disabled. The WebView host therefore installs
   narrow native WebView2 `NavigationStarting` and `NewWindowRequested`
   handlers that cancel every URL outside the exact packaged asset origin.
   Every `dispatch()` call also rejects unless the current top-level URL is
   that exact origin. This is backend hardening, not a second message API.
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
would mangle or fail on the message channel raw regardless. Sink side:
`textContent`-only rendering, no `innerHTML` anywhere, and the scanner's
existing hostile-name corpus reused as UI rendering fixtures — the web
equivalent of the CLI's `_safe()`. The CSP is explicit: `default-src 'none';
script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none';
frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`.

**DR-M1-17 — Bridge protocol versioning.**
Commands and view models are a new Python↔JS contract shipping in two halves,
same shape of risk the event `Envelope.schema_version` already exists to
prevent.
**Resolution:** version every bridge message, checked on both sides, from
first commit — same law as the event envelope, applied one layer up.

**DR-M1-18 — Large trees over the bridge.**
A directory-rename decomposition can be thousands of rows, and naive per-event
delivery rebuilds the PoC's per-chunk UI flood one language over.
**Resolution:** all bridge data is pull/RPC. The plan tree, inventory tree, and
history detail use paged commands. For live state, JavaScript holds at most one
`next_events` request; Python returns a bounded batch as structured data and
the client immediately asks again. The Python event queue preserves reliable
order, coalesces `Progress` to its latest snapshot before return, and wakes the
outstanding request during window shutdown. This retains the `LOSSY` delivery
class at the bridge boundary without creating a host-to-JS execution channel.

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
(already required by DR-M1-01/07). All producers converge on the bounded
event-drain queue (DR-M1-18) regardless of thread count.
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
**Resolution: defer retention from M1.** A facade-local "active audit writers"
gate cannot see a concurrent CLI/GUI process, while `SerializedWriter`
serializes only one process-local connection. A retention write could
therefore outlast another process's audit timeout and degrade the audit axis
despite the apparent gate.

Retention returns with maintenance-session work, where every audit writer and
the sweep can participate in explicit cross-process history-writer custody.
M1 adds no retention command, facade function, GUI action, partial local gate,
or direct UI SQL.

---

## 3. Dependency-Ordered Deliverables

### Stage 1 — Contracts and Semantics

**Implemented 2026-07-24.** The code-bearing Stage 1 prerequisites are live:
`worker_count` and the false live-settings drift path are removed; opaque
workflow payloads are v2; ledger v2/history v3 refuse old schemas and reserve
generic item/phase storage; the explicit development reset recreates both
databases; semantic settings and cosmetic UI state have their split owners;
the compatible `xxhash>=3.8.1,<4` runtime dependency is declared; and the
WebView2 security spike proves forced Edge Chromium, native navigation guards,
exact-origin dispatch, and structured pull/RPC.

The standard-library-only `StreamingHasher`/`HasherFactory` contract landed in
core in this stage. At the Stage 1 checkpoint, the actual
`ContentEvidence`/`CopyDigest`, executor, verifier, repository, and fixture
switch to 16-byte `xxh3_128` remained the atomic Stage 2 Track 2 change required
by DR-HASH-01/02. Nominal integrity result/event code similarly waited for its
Stage 3 producer; compound continuation/result code still waits for Stage 4.

- Freeze the execute → verify state machine, candidate set, four independent
  truth axes, pause/cancel/failure behavior, process-close limitation, and
  recorder lifetime from DR-M1-12. These decisions are acceptance inputs, not
  dormant implementation seams.
- Define the single XXH3-128 content-evidence contract and parameterless
  standard-library-only hasher protocol consumed by executor and verifier.
- Define the ledger v2/history v3 schemas and one destructive reset procedure.
  History v3 includes the final generic item and phase-summary storage needed
  by Stages 3/4; this storage reservation is the sole compound-only seam that
  lands before its producer. Remove/disable the v1→v2 history migrator before
  changing the current constant (DR-M1-09).
- Remove `worker_count` from `SyncOptions`, `Plan`, payloads, and fingerprints;
  do not replace it while file-level concurrency is deferred (DR-M1-05).
- Settle nominal standalone-integrity result/event vocabulary:
  `ResultItem`, explicit `item_type`/`phase`, generic serialization, item
  identity, history detail, and view shapes. These land with the standalone
  integrity producer in Stage 3, not as unused fields in Stage 1.
- Settle settings ownership and snapshot semantics; implement
  `db/settings.py` with named-mutex-serialized read-modify-replace and
  `interfaces/ui_state.py` for cosmetic state (DR-M1-03/04/05).
- Complete a hostile-navigation bridge spike proving forced Edge Chromium,
  native cancellation of untrusted navigation/new windows, exact-origin
  rejection in `dispatch`, and structured pull/RPC without `evaluate_js`.

### Stage 2 — Executor and Hash Refactor

**Implemented 2026-07-24.** Track 1 uses the fixed adaptive chunk bands, one
bounded three-stage pipeline for every normal copy, conditional preallocation,
Windows sequential-source hints, and the specified finalization reductions.
Track 2 atomically switched copy and verification evidence to raw 16-byte
XXH3-128, injected the same exact composition-owned factory into both
consumers, retained different executor/verifier opener strategies, reconstructed
stored algorithms without relabeling, and joined the final marked
ledger-v2/history-v3 reset boundary. No file-level concurrency or alternate
content algorithm was added. Final measured tables and acceptance status remain
recorded in `HASH_REFACTOR.md`.

0. **Precondition — validate the fixed chunk bands and measure allocation.**
   `HASH_REFACTOR.md` DR-HASH-07 fixes the M1 copy policy at 256 KiB below
   8 MiB, 1 MiB from 8 MiB through less than 32 MiB, and 4 MiB from 32 MiB
   upward. Before landing step 1, run the standard synthetic distribution
   (1,000×4 KiB, 512×128 KiB, 64×4 MiB, 4×128 MiB, 1×4 GiB) cross-volume,
   validate those bands against the production-shaped workload, and record
   per-size operations/second, fixed finalization time, and the measured
   preallocation crossover. Revising a fixed band requires evidence; choosing
   bands ad hoc during implementation does not satisfy this stage.
1. Land all of `HASH_REFACTOR.md` Track 1, not merely "the pipeline":
   the fixed 256 KiB / 1 MiB / 4 MiB adaptive chunk policy, the combined
   32 MiB byte budget and 32-entry FIFO caps, immutable linear
   reader/hasher/writer handoff, conditional preallocation, sequential source
   hint, hoisted Win32 bindings, one temp flush, combined
   metadata/finalization handle, conditional post-publish repair, backup-loop
   boundaries, and attestation size invariants.
2. Land `HASH_REFACTOR.md` Track 2 after Track 1: replace content SHA-256 with
   XXH3-128 in both copy and verifier implementations, add the one concrete
   factory at composition, update repositories/fixtures, and apply the
   coordinated ledger/history reset. The verifier implementation and
   `VerifierContext` seam belong to this HASH track; construction of production
   integrity sessions waits for Stage 3.

No file-level concurrency, serial/pipelined engine split, batching, publish
pipeline, or direct IO is introduced.

### Stage 3 — Inventory and Standalone Integrity

**Implemented 2026-07-24.** The delivered slice includes the five distinct
resolution states; first-location host→volume→role-free-location registration;
full and selected reconciliation with producer-correct completeness;
mapping-scoped authoritative filter snapshots plus hash-tagged exclusion
projections; typed immutable repository snapshots; acknowledge/restore and
staleness reads; nominal ordered result/history items; and standalone inventory,
baseline, verify, and rebaseline composition. Integrity re-resolves on initial
start, every resume, and queued wakeup; pause/resume retains the exact admitted
row ids while refreshes may inventory newly appeared rows. The production
dispatcher registers all six current workflow kinds with their correct pause
capabilities, but parser choices remain exactly `sync` and `history`. Stage 3
writes no `history_phases` rows and introduces none of Stage 4's transient or
compound types.

- Inventory workflow: five-state volume resolution, first-location
  registration, scoped scan-and-record using the existing scanner,
  acknowledge/restore, and staleness queries (DR-M1-11).
- Fix scoped completeness so selected refreshes can reconcile
  (`scanner.py:252` vs `recorder.py:573`).
- Persist mapping-filter/exclusion state: excluded rows are never marked
  missing/deleted and cannot become target deletion candidates.
- Land the nominal result/event/history/view vocabulary from Stage 1 together
  with its first producer. `IntegrityOutcome` enters `EventBody`; history and
  views preserve `item_type`, `phase`, item order, and integrity detail.
- Implement `run_integrity` for inventory, baseline, verify, and rebaseline,
  with integrity preflight and dispatcher registration for each supported
  session kind/pause capability.
- Expose no CLI/UI entry points yet; exercise the workflow and serialization
  contracts directly.

The inventory producer sub-lane may run beside Stage 2 after Stage 1 contracts
are fixed. Standalone baseline/verify/rebaseline waits for HASH Track 2 and
the inventory selection producer.

### Stage 4 — Post-Execution Integration

Land DR-M1-12/13 as one vertical integration gate:

- core-owned `PublishedCopyEvidence` in `core/execution.py`, stored by
  `ExecutionSet`, plus its workflow payload round-trip;
- core-owned `PostCopyCandidate` in `core/integrity.py`, constructed by the
  workflow from published evidence and sharing the standalone verifier's
  guarded classifier;
- workflow-owned discriminated continuation payloads that depend only on core
  contracts and remain opaque to the dispatcher;
- conditional verification recording without making ledger-row existence a
  prerequisite for byte classification;
- one heterogeneous item list plus compound-only `PhaseResult`;
- explicit execute/verify continuation and phase-scoped progress;
- one logical recording spanning both phases, with idempotent pause/reopen and
  one compound terminal settlement;
- history, views, failure classification, and pause/resume consumption; and
- end-to-end tests for partial execution, degraded recording, mismatch,
  target drift, pause in both phases, cancellation, and unexpected
  verify-phase failure.

No compound-only abstraction merges earlier without its consumer except the
final history-v3 storage reservation required to keep one destructive schema
boundary.

### Stage 5 — Facade and CLI

- `interfaces/service.py`: composition root, registry and per-kind pause
  table, runtime/dispatcher lifecycle, plan/execute sequencing, workflow
  commands, and result classification.
- `SessionObserver`: sink-based observation, resubscribe/`Gap` recovery,
  get-before-subscribe race fix, blocking reads, and explicit stream-close/join
  shutdown (DR-M1-19).
- `ResultCategory` preserves filesystem, integrity, recording, and audit axes.
  Headline precedence is **failed > partial > refused > mismatch > canceled >
  verification-incomplete > recording/audit degradation > all-noop >
  success**; non-headline axes remain visible.
- `workflows/views.py`: `SessionEventView`, `SessionRecordView`,
  `OperationResultView`, `IntegrityOutcomeView`, and `InventoryRowView`.
- Runtime/facade `save_plan`/`get_plan`/`drop_plan` methods over the existing
  process-local dictionary; no speculative `PlanStore`.
- Remove the duplicated CLI path validator, retarget the existing CLI onto the
  facade, then add `inventory`, `baseline`, `verify`, and `rebaseline`.
- Import-linter: `cli`/`web` mutually forbidden, both import `service`,
  `service` imports neither. Preserve the existing 13 CLI end-to-end tests.

Pure facade extraction that preserves M0 behavior may begin after Stage 1's
result/view contracts settle, in parallel with late Stage 3 work. New commands
and final classification wait for Stages 3 and 4.

### Stage 6 — Web Desktop Shell

- pywebview host; `nami-sync-gui` entry point plus no-subcommand launch.
- Exactly one versioned, schema-validated, allowlisted
  `dispatch(command_json)` method. All data uses structured pull/RPC; live
  events use one bounded/coalescing `next_events` drain.
- Force Edge Chromium; fail actionably without WebView2. Install native
  cancellation hooks for untrusted navigation/new windows and reject every
  dispatch outside the exact packaged origin.
- Opaque ids rather than command paths, explicit `item_type`/`phase`,
  hardened CSP, `textContent` only, no `innerHTML`, and hostile-name fixtures.
- Task rail, task shell, plan tree, inventory tree, and history dialog built
  only against Stage 5's facade/views.
- GUI single-instance named mutex.
- Rewrite `DESKTOP_UI.md` for the web target and update `ui_mockup/` from
  staging artifact to implementation starting point.

---

## 4. Explicitly Deferred (not M1)

- General, versioned migration module — stays past M3 (DR-M1-09); M1 refuses
  every stale ledger/history version and resets both databases
- Durable plan/session persistence (`SqliteSessionStore`) — M2; M1 ships the
  named runtime/facade access seams only, with no storage abstraction
  (DR-M1-08)
- Cross-process task visibility in the GUI — depends on the same M2 durable
  session store
- History retention and scheduled/daemon-driven maintenance — deferred until a
  maintenance session coordinates cross-process custody with every audit
  writer (DR-M1-20)
- Observer thread multiplexing — not needed at M1/M2 scale; sink API keeps it
  swappable (DR-M1-19)
- Concurrent file execution, multithreaded verification, background
  integrity, and repair guidance — deferred; `HASH_REFACTOR.md` requires new
  post-XXH3 utilization evidence before file-level workers are introduced

---

## 5. Acceptance Notes

Each stage's work should land with the same standard the M0 module docs use:
a named failure-injection or regression test per behavior, not just "tested."
The following are milestone gates because they are easy to skip:

**Implementation checkpoint (2026-07-24).** Stage 2 satisfies the Track 2
composition gates through C1–C11 in `HASH_REFACTOR.md`, including a single
production-composition proof of exact factory identity plus distinct
`O_SEQUENTIAL` executor and Windows-unbuffered verifier openers, and a direct
plus optimized-`python -O` attestation-size invariant. Stage 3 has executable
coverage for XV-8 through XV-17 to the extent those gates apply before Stage 4:
nominal item validation/order, integrity history, view precedence, scanner and
five-state inventory behavior, resume/wakeup clone refusal, shared factory
composition, final-schema markers/reservations, and zero standalone phase rows.
The compound-only halves of XV-8/XV-17 and all execute→verify gates remain
Stage 4 work.

- The XXH3-128 replacement and copy pipeline satisfy every collaborator,
  vector, acknowledgement, failure, and cancellation test listed in
  `HASH_REFACTOR.md`; M1 does not weaken that document's gates.
- "Pipeline every size" is validated end to end, not only by microbench. The
  standard synthetic distribution (1,000×4 KiB, 512×128 KiB, 64×4 MiB,
  4×128 MiB, 1×4 GiB) runs cross-volume, and the small-file band's end-to-end
  results are 412.182 ops/s to `G:` NAND, 337.106 ops/s to `E:` Optane, and
  50.177 ops/s to `J:` HDD. In the controlled three-engine comparison those
  are respectively 83.1%, 92.1%, and 37.6% faster than the retired serial
  SHA-256 executor, so the accepted isolated worker-startup cost does not
  become an end-to-end small-file regression. All 15 current-tip corpus rows,
  fixed finalization time, stage starvation, payload high-water, serial
  comparisons, and the allocation sweep are recorded in
  `HASH_REFACTOR.md` §2.8. A green correctness-only pipeline test does not
  satisfy this bullet: the measurement is a named gate with recorded numbers,
  and a regression past the accepted margin blocks the stage
  (`HASH_REFACTOR.md` §2.7(7), DR-HASH-07).
- Ledger v1, history v1, and history v2 are all refused with the same
  actionable reset posture; the old history migrator cannot label a partially
  migrated database as v3, and reset setup recreates both databases together
  (DR-M1-09).
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
- A session paused after one or more successful publishes but before/during
  verification round-trips the exact `PublishedCopyEvidence` for every settled
  byte-producing operation. Closing/restarting the M1 process does not claim
  to resume that state (DR-M1-12).
- A copy-ledger failure followed by matching target readback reports
  filesystem succeeded + integrity verified + recording degraded. A mismatch
  or target-stat drift remains an integrity result and never rewrites the copy
  outcome (DR-M1-12).
- A canceled or failed mixed-phase session returns one ordered heterogeneous
  `items` list whose entries retain nominal `item_type` and `phase` tags; no
  integrity item is lost or swept into an operation-only accumulator
  (DR-M1-12).
- A hostile filename returned by `dispatch` reaches JS as structured data and
  never as interpolated script text; application-data delivery invokes neither
  `evaluate_js`, `run_js`, nor `Window.state` (DR-M1-15/18).
- Native WebView2 hooks cancel external navigation and new-window requests,
  and a dispatch attempted from any non-packaged top-level origin is rejected
  even if navigation hardening is deliberately bypassed in the test
  (DR-M1-15).
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
- The CLI's 13 end-to-end tests pass unchanged after the Stage 5 retarget,
  proving equivalent-request/equivalent-result-classification across
  interfaces before a second interface exists to test it against
  (DR-M1-02/07).

### 5.1 Cross-Module Contract Gates (prove before integration)

The §5 notes above check per-decision behavior. This section exists because the
failure mode the plan most fears is two modules that each pass their own tests
while disagreeing about a shared contract — a disagreement that only surfaces
at Stage 4 integration. Each gate below names both sides of a seam and the test
that makes a disagreement fail *before* they are wired together. The anti-slack
rules from `HASH_REFACTOR.md` §4.5 apply verbatim: inject the named divergence,
assert the typed result, and reject any test that would still pass if the two
sides were mis-wired.

**Resolved doc reconciliation.** `WORKFLOWS.md` previously specified
linked-verify selection as ledger-first, contradicting DR-M1-12 §1 and §3.
The active workflow and architecture documents now use the execution-owned
published-evidence handoff whether or not a ledger row exists. Keep XV-2 below
as the executable proof: otherwise a later implementation can regress to a
ledger query and silently drop every candidate whose copy-ledger write was
`DEGRADED`.

#### Execute → verify handoff (the highest-fear seam)

- **XV-1 — Published-evidence cardinality.** Every settled COPY/UPDATE/
  MOVE_UPDATE yields exactly one `ExecutionSet.published_evidence` entry;
  `set(published_evidence) == {settled byte-producing op_ids}`. Fault-inject one
  `_settle()` to mark status succeeded but omit evidence and assert the session
  reports a named verification-incomplete invariant error, not a clean
  all-verified terminal. *Not satisfied by* asserting `published_evidence` is
  non-empty after a single copy.
- **XV-2 — Candidates come from the handoff, not the ledger.** Run a copy whose
  copy-ledger transaction is fault-injected to fail (recording `DEGRADED`) but
  whose bytes published; assert the verify phase *still* produces a candidate
  and reports `verified` + `recording degraded`. A ledger-first implementation
  yields zero candidates here — this is the executable form of the doc
  reconciliation above. *Not satisfied by* the happy path where the ledger row
  exists (both sources agree).
- **XV-3 — One recorder lifetime across both phases.** Run
  execute → pause → resume → verify → settle; assert exactly one run window and
  one compound terminal in the ledger, the reopened recorder reuses the same run
  token idempotently (no token-conflict, no duplicate row), and a repeated close
  during the pause is a no-op. *Not satisfied by* an execute→verify run with no
  pause between, where close/reopen idempotency is never exercised.
- **XV-4 — Continuation carries phase, not just the request.** Pause mid-verify
  after k of n items; resume and assert exactly the remaining n−k items are
  produced (none repeated, none lost) and the terminal phase came from the
  explicit `phase=verify` discriminator, not inferred from accumulated items;
  the serialized continuation contains phase + candidates + completed-
  verification ids/bytes. *Not satisfied by* pausing only in the execute phase.
- **XV-5 — Published evidence survives an in-process pause (only).** Pause
  execution after some COPYs published but before settle; resume same-process
  and assert every already-published op still has its exact
  `PublishedCopyEvidence` and is verified. Separately restart the process and
  assert resume is not offered (no false durable-resume claim). *Not satisfied
  by* pausing only at a boundary where the executor already returned.
- **XV-6 — Four axes stay independent under compound results.** A copy succeeds;
  force *stat-stable* target-byte corruption (bytes changed, size and mtime
  preserved) so readback mismatches; assert filesystem=`COMPLETED` AND
  integrity=`mismatch` AND the copy outcome unchanged. Target *stat* drift is
  `modified`, not `mismatch` (DR-M1-12) — assert that boundary separately. A
  conditional verification write that goes stale after a byte match reports
  `verified` + `recording degraded/stale`, never `HASH_MISMATCH`. *Not
  satisfied by* asserting only that "the session reports a problem."
- **XV-7 — Phase byte counters are never summed.** Copy+verify of a known-size
  file exposes two independent phase counters (each reaching the size once), not
  one reaching 2×; a verify-phase failure before any item produces a
  `PhaseResult` with the error, not an empty success. *Not satisfied by*
  asserting a single total "reaches the size," which a double-counting single
  counter also satisfies.

#### Result vocabulary, history, classification

- **XV-8 — Nominal `ResultItem`, not duck-typing.** A mixed session emits one
  `ItemOutcome` (phase=execute) and one `IntegrityOutcome` (phase=verify) where
  *both objects expose `item_id` and `path`* (the real `integrity.py` type
  does); assert `OperationResult.items` is one ordered length-2 list, each entry
  keeps its own `item_type`/`phase`, and neither was routed into a separate
  operations tuple; history round-trips both `item_type` tags distinctly. *Not
  satisfied by* using the real (with-`path`) `IntegrityOutcome` and asserting
  only that it lands in `items` — the current `hasattr` duck-typing collects it
  too; the discriminator is that each entry keeps its own `item_type`/`phase`
  and is not swept into a separate operations tuple.
- **XV-9 — `IntegrityOutcome` reaches history.** Run a standalone verify, read
  the persisted history detail back, and assert each `IntegrityOutcome` is
  present with its integrity fields; feed `HistoryObserver` an unknown
  `EventBody` subtype and assert it raises rather than silently no-ops. *Not
  satisfied by* asserting the in-memory terminal result rather than reading the
  history database.
- **XV-10 — Headline precedence keeps all four axes visible.** Construct a
  result that is simultaneously partial + mismatch + recording-degraded +
  audit-degraded; assert headline == `partial` and all three secondary axes
  remain individually renderable; drive the *adjacent* precedence pairs
  (mismatch vs canceled, canceled vs verification-incomplete) and assert the
  headline flips at each boundary. *Not satisfied by* testing only far-apart
  pairs and never asserting the secondary axes survive the view model.

#### Settings snapshot and fingerprint

- **XV-11 — Executor never re-reads global settings.** Commit a plan, mutate
  *every* global semantic setting (filters, deletion, trash-on-update,
  preservation, casing), then execute; assert filesystem effects match the
  original snapshot and the session neither refuses nor changes behavior; a
  static scan asserts no executor/preflight symbol reads `db/settings` at
  execution time and no `SettingsReader`/`ObservedWorld` live-settings field or
  `FILTER_DRIFT`/`OPTIONS_DRIFT` path remains. *Not satisfied by* editing one
  setting, where a lingering self-comparison passes trivially.
- **XV-12 — `worker_count` fully removed, codec still lossless.** Assert
  `worker_count` is absent from `Plan`, `SyncOptions`, and the encoded payload;
  two plans differing only in a would-be `worker_count` produce identical
  `plan_fingerprint` and `policy_fingerprint`; a full plan round-trips through
  the JSON codec across every op kind byte-identically with a stable
  fingerprint. *Not satisfied by* removing it from `SyncOptions` only while it
  stays defaulted on `Plan` (the `asdict(plan)` fingerprint still hashes it) and
  both test plans default it identically.

#### Inventory, volume resolution, scanner ↔ recorder

- **XV-13 — `ScanResult.complete` means complete-for-scope, recorder branches on
  `is_full_scan`.** A selected refresh over {A,B} in a location also holding
  {C,D}, with A present and B absent, marks B missing and leaves C,D untouched
  (no location-wide sweep); an interrupted selected scan sets `complete=False`
  and marks nothing missing; confirm the recorder chose the selected branch via
  `is_full_scan`, not via `complete`. *Not satisfied by* asserting only that A/B
  reconcile while never asserting C,D are preserved.
- **XV-14 — Five volume states → distinct recorder behavior, none marks
  missing wrongly.** For each state assert the outcome:
  resolved→scan+reconcile; offline→zero missing + offline label;
  ambiguous→refusal requiring user choice; root_missing→distinct actionable
  state, zero missing; root_unavailable→access-failure state, zero missing.
  Specifically inject a mounted volume with a deleted configured root and assert
  no rows flip to missing. *Not satisfied by* aliasing root_missing/
  root_unavailable back onto offline (the "no missing marked" assertion still
  passes while the user-actionable distinction is lost).
- **XV-15 — Integrity preflight re-resolves the volume on resume/wakeup.** Queue
  a verify session, swap in a duplicate-identity (ambiguous) volume before
  wakeup, and assert the resume/wakeup path detects ambiguous-at-resume and
  refuses/escalates rather than hashing, through the reopened invocation — not
  only at original submit. *Not satisfied by* checking the ambiguous case only
  at submit time, where every implementation checks.

#### XXH3 / attestation / factory seam (cross-module composition)

- **XV-16 — Both consumers wired in one track, same factory, right openers.**
  This seam is proven by `HASH_REFACTOR.md` §4.5 gates C4 (copy→verify
  round-trip = `verified`), C5 (same hasher object, different openers at
  composition), C6 (global size invariant on the readback path), C7
  (self-describing reconstruction), and C8 (import law + required backend). The
  M1-specific obligation on top: assert `VerifierContext` gains the required
  factory *field* in Track 2 while its first *production construction* is
  Stage 3, and that copy and verify evidence written across the single
  destructive reset use the identical encoding. *Not satisfied by* landing the
  executor and verifier hasher wiring in different stages, which lets copy write
  `xxh3_128` while verify still computes `sha256` during the reset window.

#### Bridge, observer, schema reservation, checkpoint

- **XV-17 — History-v3 shape reserved at the single reset.** Introspect the v3
  schema created at reset and assert it already contains the generic-item and
  phase-summary storage Stage 4's `PhaseResult` persistence needs; assert
  Stage 4's compound write succeeds against the un-bumped v3 schema (no ALTER,
  no second version bump) and no Stage 1/3 producer writes phase-summary rows.
  *Not satisfied by* defining v3 to cover only standalone integrity items and
  discovering the gap at Stage 4 (a silent second reset).
- **XV-18 — Observer closes every stream before joining threads.** Start a live
  session, then trigger (a) explicit unsubscribe, (b) window close mid-session,
  (c) app shutdown with the session running; assert every observer thread
  terminates within a bounded deadline and `close()` was called on every opened
  stream before join; separately submit a session that completes before
  subscribe and assert an already-terminal result is returned, not
  `SessionNotFound`. *Not satisfied by* only covering a session that ends
  naturally before teardown, where blocked-`next()`-needs-close never runs.
- **XV-19 — Bridge: ids in, escaped text out, origin re-checked
  independently.** Feed the scanner's hostile-name corpus through a real
  `dispatch` round-trip; assert every filename reaches JS only as escaped
  display text via `textContent` (grep proves zero `innerHTML`/`evaluate_js`
  for app data), no command can be built from a raw path (ids only), and — with
  navigation hardening deliberately bypassed in-test — a dispatch from a
  non-packaged origin is rejected on the origin recheck alone. *Not satisfied
  by* one benign filename and a single-file `innerHTML` grep.
- **XV-20 — Checkpoint is stateless; tests don't count it.** Cancel at each
  pipeline stage and assert clean teardown via stage-state synchronization; then
  double the checkpoint poll frequency and assert identical cancellation
  outcomes and identical digest/progress on non-canceled runs. *Not satisfied
  by* a checkpoint that raises on its Nth call — it passes while coupling to a
  count the contract explicitly disclaims.

**Historical code anchors these gates came from** (line numbers record the
reviewed pre-Stage-1 tree and are not current navigation): `planning.py:301`/
`:403`/`:411` (`worker_count` in `policy_fingerprint` at :403; `asdict(plan)`
at :411), `scanner.py:252` (selected scan forces
`complete=False`), `recorder.py:573` (selected-missing requires
`complete=True`), `session.py:255-258` (`hasattr` duck-typing),
`integrity.py:179-182` (`IntegrityOutcome` has `item_id`+`path`),
`runtime.py:427` (pause snapshots the request only).

---

## 6. Sanity Review Notes — 2026-07-22, revised 2026-07-24

This section records the adversarial review of the plan. It is appended rather
than folded into the decision log so the original planning rationale remains
visible. Findings are implementation gates unless explicitly marked
non-blocking.

**Disposition (revised 2026-07-24).** All ten findings were verified against
the code and resolved into §2 and §3 above. Later executor/integration review
replaced the original retention gate, bridge transport, and post-execution
handoff dispositions. Four load-bearing claims were confirmed at
source and are the reason this review mattered:

| Finding | Verified at | Status |
| --- | --- | --- |
| 1 — worker count is fingerprinted despite the doc's claim | `planning.py:301`, `:403` (`policy_fingerprint`), `:411` (`asdict(plan)`) | Confirmed; DR-M1-05 now removes it without replacement |
| 2 — scoped missing-marking is unreachable | `scanner.py:252` vs `recorder.py:573` | Confirmed; contract fix added to Stage 3 |
| 3 — runner sweeps integrity outcomes into `operations` | `session.py:255-258` duck-types on `item_id`+`path`; `integrity.py:179-182` has both | Confirmed; nominal `ResultItem` plus one phase-tagged heterogeneous list replaces duck typing |
| 3 — pause loses verifier state | `runtime.py:427` snapshots the request only | Confirmed; explicit continuation phase flag and completion state added |

Later decisions refined three original dispositions, with the binding result
recorded in the decision log above:

- **Finding 1's remedy.** Frozen per-session settings snapshots are now the
  settled model. DR-M1-06 describes lifecycle UX rather than advisory drift
  refusal, and `worker_count` is removed rather than relocated.
- **Finding 3's remedy.** The result does not grow parallel domain lists.
  Standalone-integrity vocabulary lands with its producer; compound-only
  phase summaries, published evidence, transient candidates, and continuation
  state land later as one post-execution vertical slice. Successful copy
  attestations live in `ExecutionSet` continuation rather than being
  rediscovered through a ledger query.
- **Finding 9 (`PlanStore` speculative).** No protocol or storage abstraction
  is introduced. Named runtime/facade methods preserve only the present-tense
  access seam around the existing dictionary.

Finding 5 is resolved with a named cross-process mutex held only around the
semantic settings read-modify-atomic-replace transaction. It does not reserve
settings for an interface's lifetime. `interfaces/service.py` still reaches
`db/settings.py` through the injected runtime rather than importing it, since
the import law forbids `interfaces → db` outright.

Finding 4 now uses JS-initiated structured pull/RPC only and requires native
WebView2 navigation cancellation plus exact-origin dispatch rejection.

Finding 6 is deferred rather than locally gated. A facade cannot observe audit
writers in another process; retention waits for maintenance-session work with
cross-process history-writer custody.

Finding 8's headline precedence is now explicit, with deliberate cancellation
below integrity mismatch and adjacent to incomplete verification. All four
axes remain visible regardless of headline.

The editorial corrections (stale `DR-M1-12` cross-references, the precedence
note's wrong attribution, "committed verify session", and this document's
standing relative to the active docs) are all applied above.

### Original blocking findings (resolved above)

#### 1. Commitment semantics contradict themselves

The reviewed draft said that defaults changed after commitment affected only
new plans, but then said that the same change refused an outstanding
commitment. Those are different policies. The settled correction is the
frozen-session model: the commitment executes its reviewed policy snapshot,
and current defaults do not invalidate it. DR-M1-06 is retained only as the
lifecycle/interaction rule for editing task-local bound controls; its former
advisory drift-refusal behavior is removed.

Excluding `worker_count` from `policy_fingerprint` would also have been
insufficient while `worker_count` remained a field on `Plan`: the full plan
fingerprint hashes the whole plan. Because concurrent file execution is
deferred, Stage 1 removed the field without replacing it with another setting.

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

Later review closed the earlier execute→verify evidence gap as well:
successful copy attestations are stored with operation status in
`ExecutionSet.published_evidence`, and post-copy verification consumes
transient candidates rather than requiring a successful ledger query.

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

The revised resolution removes host-to-JS application-data transport entirely:
JavaScript drains structured results through `dispatch`, while native WebView2
handlers enforce navigation and each dispatch rechecks the top-level origin.

The plan must also force the Edge Chromium renderer and fail actionably when it
is unavailable. pywebview documents an MSHTML fallback; accepting that fallback
means the product is not reliably WebView2. Static asset serving through
pywebview's built-in local server must be distinguished from an event/API
server and restricted to packaged UI assets.

The bridge implementation must follow the relevant security guidance:

- [pywebview JavaScript/Python bridge](https://pywebview.flowrl.com/guide/interdomain)
- [pywebview renderer selection](https://pywebview.flowrl.com/guide/web_engine)
- [Microsoft WebView2 security guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security)

### Original significant corrections (resolved above)

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
timeout. The first review allowed a facade-local active-writer gate; the later
cross-process review rejected it because another CLI/GUI process is invisible
to that facade. The binding resolution is §4 deferral until a maintenance
session provides coordinated history-writer custody.

#### 7. M1 scope omits already-defined behavior

The plan should explicitly include:

- the implemented verifier's explicit `rebaseline` operation and its CLI/UI
  entry point;
- mapping-filter/exclusion persistence, which the inventory contract assigns
  to M1; and
- role-free location creation for the first inventory scan.

#### 8. Result classification needs an integrity axis

The original interface-track `ResultCategory` list included refused, canceled,
failed, degraded,
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
- DR-M1-14 formerly pointed the outbound rule to DR-M1-12; the bounded
  event-drain rule is specified under DR-M1-18.
- “Committed verify session” in the acceptance notes is inconsistent with the
  plan's non-commitment integrity workflow. Use “queued verify session” or
  “verify session admitted with a stale volume snapshot.”
- The precedence rule says `FEATURES.md` owns behavior while this plan
  intentionally postpones the corresponding active-document edits. Either
  state that this plan governs unimplemented M1 decisions until promotion, or
  update the affected active documents before implementation starts.
