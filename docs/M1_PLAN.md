# M1 Plan

Status: planning decisions resolved 2026-07-21. Nothing below is implemented
yet. This is both the milestone plan and the decision log for the choices made
while shaping it — later docs (`ARCHITECTURE.md`, `FEATURES.md`,
`DESKTOP_UI.md`, `INTERFACES.md`) get updated as each track lands, and this
file is the record of *why*, the same role `DESIGN_REVIEW.md` plays for M0.

**Documentation precedence**, stated once here because it resolved a real
conflict during this planning pass (§3, DR-M1-14): `FEATURES.md` owns
behavior, `ARCHITECTURE.md` owns contracts, module docs are subordinate to
both. Where a module doc reads stricter or looser than FEATURES/ARCHITECTURE,
the module doc is what's stale.

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
  (acknowledge/restore/staleness), the hash-import module (currently
  unwritten), history v3 detail, retention, and the CLI commands that expose
  them.
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
**Also relocates:** the `SettingsReader` protocol currently lives in
`modules/preflight.py`; it belongs in `core/` with the other protocol shapes
(§2.7), since `db/settings.py` can't import `modules/`.

**DR-M1-04 — Concurrency policy for the settings files.**
GUI and CLI can write settings concurrently by design (read-only/disjoint CLI
work coexists with a GUI session per `INTERFACES.md`).
**Resolution:** last-writer-wins, no merge machinery — accepted risk, matches
how rarely both write at once. **Patched:** `settings.json`'s writer
re-reads the file immediately before every write and modifies only its own
keys, shrinking the lossy window from "GUI session length" to milliseconds.
Splitting the file (DR-M1-03) already removes most of the risk on its own:
`ui-state.json`'s only realistic writer is the GUI, so the dangerous
cross-writer case barely exists anymore.

**DR-M1-05 — What does a committed plan's fingerprint bind, and does a
settings change invalidate an outstanding commitment?**
Two settled statements looked contradictory: filter-drift refusal is listed
as implemented preflight flesh, but "changed defaults affect new plans and do
not affect existing commitments" reads like commitments are immune to
settings changes.
**Resolution — the fingerprint binds:**
- reviewed intents that shape filesystem effect: deletion policy,
  trash-on-update, filters, preservation policy, casing propagation
- before-state evidence: roots, volume identity, metadata
Binds **separately**, via the existing selection digest: selected op ids.
**Rechecked live at execution, never fingerprinted:** volume still exists,
file drift, capacity.
**Excluded entirely:** execution tuning (worker count), UI presentation
(sorting, columns, notifications). Defaults changed *after* commitment affect
only plans created afterward.
**This resolves the apparent contradiction as drift-refusal, not
snapshot-immunity:** a semantic setting change *does* affect an outstanding
commitment — it refuses it back to review at execution time, it never
silently re-plans and never retroactively changes what already-committed work
means. DR-M1-06 makes that refusal visible before execution time, not just
at it.
**Precision:** one canonical fingerprint function in `core/`, used identically
by plan construction and by the settings-side comparison — two independent
serializations of "current semantic settings" would drift in key order alone
and produce false refusals of every outstanding commitment.

**DR-M1-06 — Refuse immediately on settings commit, or wait for the queued
session's own preflight?**
A user who changes a filter, then walks away from a queued committed plan,
would otherwise only discover the refusal when the session finally wakes.
But refusal is terminal — an eager, independent judgment risks killing a
commitment for a setting the user reverts five minutes later, and it would be
a second judge of plan validity where preflight is supposed to be the only
one ("Preflight as a Callable, Not a Gate").
**Resolution:** on settings commit, the facade re-runs the real
`observe()`/`preflight()` over outstanding committed, unexecuted sets as an
**advisory** — rendered immediately, does not touch the commitment. The
binding refusal still happens at execution entry, unchanged. Self-heals if
the setting reverts; costs little (observe is scoped stats, outstanding
commitments are few); doubles as the M2 queued-sessions-on-launch
confirmation view later.

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
structure serializes straight to JSON for the web bridge (DR-M1-12) — no
second serialization layer. Retarget the CLI's four `hasattr` sites onto it
as the proof before the GUI depends on it.

**DR-M1-08 — Does plan review survive app closure, as `ARCHITECTURE.md` §4.9
promises ("the app may even close")?**
Plans currently live in a process-local dict (`self._plans` on
`LocalWorkflowRuntime`). True durability is `SqliteSessionStore`, which is
scheduled M2.
**Resolution:** ship M1 without plan persistence; leave the seam. Mirror the
existing `SessionStore` protocol with a `PlanStore` protocol and an in-memory
implementation, so durability later is a new implementation behind the same
shape, not a facade rewrite. Known M1 limitation to document, not silently
carry: a GUI task card's plan does not survive a process restart, and until
M2's durable session store, the task rail only shows its own process's
sessions — a concurrent CLI run is invisible to it except through volume-lock
contention.

### History and event schema

**DR-M1-09 — History schema v2 → v3 for integrity detail: migrate, or
reset?**
`IntegrityOutcome` needs a home in history detail; the schema is currently
v2 with one narrow v1→v2 migration and a stated "reset-and-refuse posture"
otherwise. A second narrow migration was floated, then a chain-runner
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
appended). Wiring the verifier to a session before fixing this produces
integrity history that comes back empty with no failure anywhere.
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
`VolumeId(serial, fs_type)` + volume-relative path):
- volume found, unique → resolve location-relative root, scan
- volume not mounted → **offline**, not missing (per *Offline Volumes*)
- two+ volumes report the same identity → **ambiguous**, explicit user choice
  required (per *Cloned-Volume Ambiguity*), never resolved silently

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
**Resolution: in-session phase (shape (a))**, with three amendments so it
doesn't corrupt existing invariants:
1. **Don't union item vocabularies.** Add a separate `integrity:
   tuple[IntegrityOutcome, ...]` field on `OperationResult`, empty for every
   existing producer. `_result_to_dict` and the history observer both assume
   `operations` is `ItemOutcome`-only today; this keeps axis separation
   instead of fighting that assumption.
2. **Phase-scoped progress.** The verify phase emits its own `PhaseChanged` +
   `Progress` with its own totals; transfer-byte progress and verify
   read-byte progress are never summed (per *Content-Byte Accounting*).
3. **A verify-phase exception is an itemized error outcome, not a session
   failure.** The copies already succeeded; "never wrong, only behind"
   forbids the terminal lying about that. Unexpected exceptions during the
   integrity phase become `error` integrity outcomes plus a warning — they
   never unwind a successful execution into `FAILED`. Mismatches were never
   failures to begin with; they're the finding, reported on the integrity
   axis.

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
dissolves into the single-outbound-pump rule (DR-M1-12 below); roughly a
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
command allowlist sit behind it; nothing else is reachable; remote navigation
disabled. Security-equivalent to raw messages, achievable in pywebview.

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

### Maintenance and retention

**DR-M1-20 — Where does history retention run?**
`FEATURES.md`'s *Scheduled Integrity Maintenance* argues against a **separate
daemon**, not against a plain function call — and describes *scheduled*
maintenance, which M1 doesn't have. `DESKTOP_UI.md` says retention runs
"through workflow, not direct UI SQL." Read together (FEATURES owns behavior,
per the precedence rule) these agree.
**Resolution:** M1 retention is **user-invoked**, a facade-invoked workflow
function against a writable history connection — not a daemon, not UI SQL,
an app-owned artifact exempt from the pipeline-mutation law but still
guarded and history-logged. Uses the same bounded busy timeout as every other
writer, and must never run inside the audit path — a retention sweep
blocking the audit pump would degrade a live session's `audit` axis for an
unrelated maintenance call. When scheduled maintenance arrives later, it
becomes a session kind wrapping this same function, not a rewrite.

---

## 3. Track Deliverables

### Track A — Interface Substrate

- `interfaces/service.py`: composition root (registry + per-kind pause
  capability table, moved out of `cli.py`), runtime/dispatcher lifecycle
  management, plan/execute sequencing (`plan_and_review`,
  `commit_and_execute`)
- `SessionObserver`: sink-based (DR-M1-19), resubscribe + `Gap` recovery,
  get-before-subscribe race fix, no polling
- `ResultCategory` classification (refused/canceled/failed/degraded/
  partial/all-noop/success), shared by CLI exit-code mapping and future GUI
  headline/color mapping
- `workflows/views.py`: `SessionEventView`, `SessionRecordView`,
  `OperationResultView`, `IntegrityOutcomeView`, `InventoryRowView`
  (DR-M1-07)
- `db/settings.py` (semantic + operational, reread-before-write) and
  `interfaces/ui_state.py` (cosmetic) (DR-M1-03/04); `SettingsReader`
  protocol relocated to `core/`; canonical fingerprint function in `core/`
  (DR-M1-05)
- `PlanStore` protocol + in-memory implementation (DR-M1-08)
- Remove the duplicated path validator in `cli.py` (`_validated_paths`
  duplicates `workflows/sync.py`'s `_validated_roots`); facade exposes the
  workflow's own check as a pre-submit call
- Retarget `cli.py` onto the facade; 13 existing end-to-end tests as the
  regression net (DR-M1-02)
- Import-linter contracts: `cli`/`web` mutually forbidden, both import
  `service`, `service` imports neither

### Track B — Integrity Spine

- `run_integrity` workflow (inventory / baseline / verify / import), gated
  by the integrity preflight (DR-M1-11)
- Inventory workflow: volume resolution ladder + scoped scan-and-record
  reusing the existing scanner (DR-M1-11); acknowledge/restore, staleness
  queries against `LedgerRepository`
- Dispatcher registration for verify/baseline/inventory session kinds with
  correct per-kind pause capability
- `IntegrityOutcome` added to `core/events.py`'s `EventBody` (schema
  version bump), serializer support, view models (blocks on Track A's
  DR-M1-07 — the critical path, DR-M1-10)
- Post-execution verification as an in-session phase of `run_execution`
  (DR-M1-12/13), scheduled early
- Hash-import module (`modules/hash_import.py` does not exist yet — this is
  new module work, not integration) + recorder support for sidecar recording
- History schema v3: integrity/import summaries, retained issue detail — via
  reset, not migration (DR-M1-09)
- Retention sweep function on a writable history connection, facade-invoked
  (DR-M1-20)
- CLI commands: `inventory`, `baseline`, `verify`, `import-hashes` — built
  against Track A's facade once it exists

### Track C — Web Desktop Shell

- pywebview host; `nami-sync-gui` entry point + no-subcommand launch
- Bridge: single `dispatch(command_json)`, schema-validated, allowlisted,
  versioned (DR-M1-15/17); ids-not-paths + escaped-display rule (DR-M1-16);
  push for small events, pull for plan/inventory/history trees (DR-M1-18)
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
  `PlanStore` seam only (DR-M1-08)
- Cross-process task visibility in the GUI — depends on the same M2 durable
  session store
- Scheduled/daemon-driven maintenance — M1 retention is user-invoked only
  (DR-M1-20)
- Observer thread multiplexing — not needed at M1/M2 scale; sink API keeps it
  swappable (DR-M1-19)
- Multithreaded verification, background integrity, repair guidance — already
  deferred in `FEATURES.md`, unchanged by this plan

---

## 5. Acceptance Notes

Each track's work should land with the same standard the M0 module docs use:
a named failure-injection or regression test per behavior, not just "tested."
Specific ones worth calling out because they don't exist yet and are easy to
skip:

- A settings change refusing an outstanding commitment's live preflight while
  leaving the commitment itself intact (DR-M1-05/06) — this test could not
  exist before the settings store does; it's the actual deliverable, not the
  store.
- A cloned volume attached after a verify session is committed/queued gets
  caught by the integrity preflight at resume, not silently resolved
  (DR-M1-11).
- A verify-phase exception during post-execution verification leaves the
  execution's filesystem status `COMPLETED` and reports the exception as an
  integrity-axis error, never as execution `FAILED` (DR-M1-12).
- A hostile filename never reaches JS as anything but its escaped display
  form, and no bridge command can be constructed from a raw path (DR-M1-16) —
  reuse the scanner's existing hostile-name corpus as the fixture set.
- The CLI's 13 end-to-end tests pass unchanged after the Track A retarget,
  proving equivalent-request/equivalent-result-classification across
  interfaces before a second interface exists to test it against
  (DR-M1-02/07).
