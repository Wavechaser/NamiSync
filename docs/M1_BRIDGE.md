# M1 Bridge and Presentation Contract

Status: design and decision log for M1 Stage 5.5 (facade completion) and
Stage 6 (web desktop shell). No code in this document is implemented. It
governs the seam between `NamiSyncService` and the packaged frontend: what
computes where, how large plans and inventories reach the client, how
selection binds, and what the bridge may carry.

**Standing.** `FEATURES.md` owns behavior and `ARCHITECTURE.md` owns
contracts; both outrank this file. `M1_PLAN.md` owns the milestone's decision
log, and DR-M1-14 through DR-M1-19 remain the governing bridge decisions —
this document refines them with implementation detail settled afterward and
does not overrule them. Where it adds a decision M1_PLAN did not make, it is
numbered `DR-BR-##` to avoid colliding with either existing series.
`DESKTOP_UI.md` remains the user-facing delivery contract; this file is the
mechanism behind it.

---

## 1. Stage 5.5 — Facade Completion

Stage 6 was blocked on four gaps in the service surface. They are grouped
here as one stage rather than folded into Stage 6 because every one of them
is provable from the CLI before a second interface exists — the same
"prove it on the existing interface first" posture DR-M1-02 used for the
facade extraction itself.

### DR-BR-01 — User selection enters the facade

`commit_plan` derives its selection from safety alone
(`derive_execution_selection(artifact.plan)`), and no user-chosen subset
exists anywhere. `DESKTOP_UI.md` nonetheless promises a "dependency-closed
selection," and the commitment model already anticipated one: DR-M1-05's
third binding is the selection digest, distinct from the plan and policy
fingerprints.

**Resolution: add user deselection to the existing derivation.**
`derive_execution_selection` already runs a transitive exclusion fixpoint
seeded from blocked, quarantined, and incomplete-scan operations. User
deselection seeds the same dictionary and reuses the same cascade. One
function serves both preview and commitment authority, so a client-side
prediction cannot diverge from what actually binds.

**Outcome semantics.** A user-deselected operation reports `SKIPPED`.
Operations force-excluded *because* a dependency was deselected keep
`DEFERRED` and drive the `partial` headline — the user chose the parent, not
the children, and collapsing that distinction would misreport the run.

### DR-BR-02 — Reselection closes upward

The existing fixpoint propagates exclusion **downward only**. Deselecting
folder `a\b` removes `MKDIR(a\b)` and every copy beneath it; reselecting
`a\b\important.txt` alone leaves that copy depending on a still-deselected
`MKDIR`, so the fixpoint immediately re-excludes it as `blocked-dependency`.
The user would watch a checkbox go grey the instant they clicked it.

**Resolution:** reselecting an operation also removes its transitive
`dependencies` from the deselected set. This lives beside the downward
cascade in `workflows/selection.py`, never in the client.

### DR-BR-03 — Deselection does not survive a replan

Operation ids are deterministic over intent
(`deterministic_operation_id(kind, source, target, prior_target, reason)`),
so a replan of an unchanged tree reproduces identical ids and a stale
deselected set would silently still apply. That is a trap, not a feature: the
new plan may contain operations no human reviewed, and carrying the old set
forward would let a checkbox state that was never applied to *this* plan
participate in `selection_digest`.

**Resolution:** any preflight rescan discrepancy invalidates the plan and
forces re-review; any mutative refresh of a plan discards its selection. The
UI states that the selection was reset because the plan changed. Required
coverage asserts the discard rather than trusting it.

### DR-BR-04 — Four runtime methods reach the facade

`acknowledge_inventory`, `restore_inventory`, `list_unacknowledged_missing`,
and `list_stale_inventory` stop at `LocalWorkflowRuntime`. The inventory
context menu and the staleness affordance both need them, and their absence
was an oversight rather than a decision. They lift as passthroughs with view
types, matching every other facade read.

Everything else on the runtime is already lifted or is dispatcher wiring
(`prepare_*`, `open_*`, `audit_observer`) that correctly stays below the
facade.

### DR-BR-05 — Scanner ignore contract narrowed

`IgnoreSet.for_owned_paths()`, `IgnoreSet.exact_path_keys`, and
`ScanResult.ignore_snapshot` are removed (landed in `84a7c53`). Once nothing
constructs a non-default `IgnoreSet`, the type is a compile-time constant and
a snapshot of a constant distinguishes nothing. The remaining contract —
`DESKTOP.INI`, `THUMBS.DB`, the owned-temp grammar, and `.SYNCTRASH` — covers
files whose invisibility is intended, so no UI owes the user an explanation
for them.

This narrows a known gap rather than closing it: **filter** exclusions remain
invisible in plan review, because a filtered file never becomes an operation
and therefore has no row. "Why isn't this file being copied?" is currently
unanswerable for filters. Recorded here; resolution belongs with the filter
discussion, not with Stage 6.

---

## 2. Compute Ownership

### DR-BR-06 — "The UI never computes" means authority

The original rule was driven by two goals: the backend must run full
functionality headlessly, and the browser must never hold decision power.
Neither goal forbids the client from computing things that affect only its
own presentation.

**Resolution — cosmetic versus authoritative describes what a computation
affects, not where it runs.** The client never computes selection semantics,
dependency closure, result classification, or headline precedence. It may
compute purely cosmetic state for itself. Conversely, cosmetic work may
legitimately execute on the backend when that is where the data lives — being
cosmetic is not an argument for running in the browser.

Three client-side computations are sanctioned under this rule, named
explicitly so the rule is not later cited to block them: rendering tri-state
checkboxes from server-supplied outcomes, resolving the autoscroll anchor
from a server-supplied ancestor chain (DR-BR-13), and applying view filters
to already-materialized rows.

### DR-BR-07 — The node tree is built in `workflows`, not `interfaces`

The import law forbids `interfaces → core`, so the web layer cannot call
`normalize_relative_path` and cannot safely group paths — grouping on display
strings gets Windows case semantics wrong. Anything requiring path arithmetic
must sit at workflows-or-below.

There is also a precedent. DR-M1-07 built the view vocabulary precisely so
interfaces would not reconstruct domain structure by inspecting shape.
Reconstructing a *hierarchy* from path strings in the adapter is that same
anti-pattern one level up.

**Resolution:** a new `workflows/plan_tree.py` produces an ordered,
primitives-only node list. `interfaces/web` consumes it and never parses a
path.

| Layer | Compute |
| --- | --- |
| `core/pathing.py` | relative-key `parent` / `depth` / `is_descendant`, common-suffix stripping |
| `modules/planner.py` | unchanged behavior; loses its three private path helpers |
| `workflows/selection.py` | deselection seeding, downward cascade, upward closure |
| `workflows/plan_tree.py` | ancestor synthesis, node ids, move grouping, ghosts, subtree op sets, rollups |
| `workflows/views.py` | `PlanNodeView`, preview projection |
| `workflows/runtime.py` | `preview_selection`, `commit_plan(deselected)` |
| `interfaces/service.py` | the four lifts, selection and tree passthroughs |
| `interfaces/web` | bridge, host, command allowlist, task state and locks, event queue, JSON encoding, collapse flattening, search matching, windowing, autoscroll anchor |

`interfaces/web` remains the largest new surface by volume, but after this
split it holds no domain-shaped computation — transport and presentation
mechanics only.

### DR-BR-08 — Path helpers promote to `core/pathing.py`

`_parent`, `_depth`, and `_is_descendant` are private to `planner.py` and are
needed identically by the tree builder. Duplicating them is exactly the drift
this project avoids.

**Resolution:** promote them unchanged, plus one addition for common-suffix
stripping. Two cautions. `core/pathing.py` already exposes `is_path_below`,
which operates on **absolute** paths for root containment — a different
domain from the relative-key descendant test, and the two must not be merged.
And the promotion is a pure relocation: `_depth` counts
`PureWindowsPath(path).parts`, `_parent` returns `None` for `"."`, and any
tidying during the move silently changes planner behavior. The planner's
existing tests are the proof, unchanged.

---

## 3. The Node Tree

### DR-BR-09 — Node identity is deterministic, not tabled

Structural folder nodes have no operation and still need addressing for
collapse state and folder-scoped selection. An earlier design minted ids into
a per-request table; that table would have been built concurrently by
separate bridge threads, with the loser's already-issued ids becoming
unresolvable.

**Resolution:** node ids are deterministic over the canonical path key,
mirroring `deterministic_operation_id`. The tree regenerates identically from
the frozen plan artifact on every call, so there is nothing to memoize and
nothing to race. This removes one of three lock sites outright.

They remain opaque in the sense DR-M1-16 requires: the client cannot
construct one from a path, and the server resolves it through a tree it
rebuilt itself.

**Synthetic ids never become operation ids.** Folder nodes come in three
flavors — a real `MKDIR`, a real directory-cleanup `DELETE`, or pure
structure. Only the third is synthetic, and giving it an `operation_id` to
make the tree uniform would reach the recorder, history item identity, and
the selection digest simultaneously. Nothing below `interfaces` ever sees a
node id; selection resolves to real operation ids before binding.

### DR-BR-10 — Folder selection is path-scoped, and the tree owns the scope

A folder node frequently has no operation at all: the planner skips `MKDIR`
when the target directory already exists, so copying into an established tree
produces operations with no directory dependency. "Deselect this folder"
therefore cannot mean "deselect this folder's operation."

**Resolution:** it means every operation whose target sits at or under that
path. The tree already computes subtree membership to produce rollups, so
`deselect_node` is a lookup returning an operation-id set, then the ordinary
derivation. One path walk, not two, and no chance of the two disagreeing.

Dependencies exist for exactly two structural reasons, running in opposite
directions: a child depends on the `MKDIR` that creates its parent
(one `MKDIR`, many dependents), and a directory-cleanup `DELETE` depends on
every removal beneath it (one `DELETE`, many dependencies). File `TRASH` and
`DELETE` carry none. A single folder checkbox meaning "everything at or under
this path" is coherent across both, but the resulting tri-state must be
**rendered from what the server returned**, never predicted from sibling
checkbox states — the cascade runs opposite ways in the two subtrees.

### DR-BR-11 — Decomposed moves render as a paired annotation

A folder rename decomposes into one move per file. Left flat, the rows sprawl
across the destination tree indistinguishable from unrelated new content,
and a reviewer must read every source path to notice they share a prefix. At
realistic scale it is unreviewable, and it buries genuinely new content
sitting alongside it.

**Resolution: annotate, do not reclassify.** The destination folder node
carries the move annotation and its rollup; a dimmed, non-interactive row at
the old location points to it, and the two highlight together.

- **The group is the folder node, not a new selection unit.** A destination
  folder may receive both moved files and genuinely new copies in the same
  run; making the group its own unit would let the collapsed row report only
  the moves and silently omit the rest. Its checkbox is the ordinary
  path-scope deselection from DR-BR-10 — no second selection currency.
- **The ghost is an annotation on the old location.** When the old location
  still holds real operations (a partial move where some files stayed and were
  trashed), the existing node is annotated and no ghost is emitted. The
  dimmed row is simply what renders when the old location would otherwise have
  no node. One mechanism, two renderings.
- **Ancestor synthesis takes the union** of operation target paths and prior
  target paths, since a ghost position may have no other reason to exist.
- **Nested moves suppress the inner ghost.** If a move's old path falls under
  another move's old path, the outer annotation already explains it and the
  inner would be orphaned at a position that no longer exists.
- **No "renamed" label.** The planner never asserts a rename; the grouping is
  inferred from path arithmetic over move operations, and enough unrelated
  files moving between two directories would be labeled falsely. The kind
  column keeps `MOVE` / `MOVE_UPDATE`, and the annotation reads literally —
  "moved from `<old path>`" — which is true whatever the cause.
- **No minimum-size threshold and no sub-window.** A two-file move gets the
  same treatment as a two-thousand-file move; consistency costs nothing here,
  since collapsed it occupies the same rows sprawl would. Group children need
  no separate paging because expanding simply inserts rows into the flattened
  sequence (DR-BR-12), which the existing window already serves.

---

## 4. Paging and Live State

### DR-BR-12 — Flattened windows over a stateless visible sequence

DR-M1-18 fixed that bridge data is paged pull/RPC but not the shape. Per-node
lazy expansion was considered and rejected: a review UI wants everything
expanded by default — "show me what you are about to do" is the point of a
dry run — and lazy expansion makes the default state cost one round trip per
folder.

**Resolution:** the server flattens the tree into an ordered visible sequence
given a set of collapsed nodes and a search query, and the client requests
`[offset, limit]` windows of it. One command shape serves the plan tree, the
inventory tree, and history items, and scroll position maps directly to an
index.

Expansion and search ride on the request rather than living server-side, so
there is no per-view lifecycle to leak. The default is expanded, so collapsing
is a deliberate act on a handful of folders, and the existing 64 KB inbound
cap is the backstop. **Responses need a server-enforced `limit` ceiling** —
the current cap is inbound only, and a truncation must be an explicit refusal
rather than a short list that reads as a complete tree.

The plan artifact is immutable and `save_plan` keys by a freshly minted
request id, so plan windows are consistent by construction and need no
versioning. Inventory is not immutable; see DR-BR-16.

Fixed row height is a design constraint, not an aesthetic preference:
variable heights require measurement passes that make window math fragile.

### DR-BR-13 — Autoscroll anchors on the nearest visible ancestor-or-self

One rule removes every special case. If the current operation is visible, it
is the target; if it sits inside a collapsed folder, that folder is the target
and shows an active indicator; expanding moves the target inward; execution
moving on moves it forward. Filtering is absorbed identically, since "visible"
means after collapse and after filtering.

The server cannot compute the visible index without knowing the collapsed
set, which under DR-BR-12 it only sees during a paging call. **Resolution:**
progress carries the current operation's ancestor node-id chain, and the
client picks the deepest entry it currently renders. That is presentation,
not authority, and it preserves stateless paging.

Follow mode is on by default and any user scroll that moves the target out of
view turns it off. It re-enables only on explicit action — a persistent pill
showing the distance to the current operation, one click to resume. Silently
re-grabbing the viewport when a row drifts back into view is the standard
log-viewer annoyance and is deliberately not done.

### DR-BR-14 — Selection is server-side state; the DOM is disposable

Virtualization destroys and recycles rows, so selection must not live in them.
The deselected set is keyed by operation id and every window response carries
each row's current outcome, so scrolling away and back re-reads authority.

This is the same problem as view filtering, and the same rule covers both:
**a folder deselect applies to every operation under that path regardless of
which rows are currently rendered or currently passing a filter.** Otherwise
"deselect this folder" would quietly mean different things depending on which
chip is lit, with no way for the user to tell.

Interaction is debounced: a click puts the row into an honest *pending* state
rather than an optimistic result, toggles accumulate for roughly 120–150 ms,
and the batch resolves as one derivation. Batching matters more than the
delay, since range selection and folder toggles generate many toggles per
gesture. At most one preview is outstanding; later batches queue, and a
response arriving after a newer request is discarded by request id.

`preview_selection` calls `derive_execution_selection` directly and **never**
`get_plan_review` — rebuilding every operation view, both scans' warnings, and
all refusals to answer "which checkboxes changed" is the wrong shape
regardless of how fast it runs.

### DR-BR-15 — Search executes on the backend

With virtualized paging the client holds a viewport, not the plan. Client-side
search would match only materialized rows and get worse as plans grow — broken
before hostile filenames enter the discussion.

Sending a query is not a DR-M1-16 violation. That rule bans JS supplying
**paths** because a path can become filesystem authority; a query never
becomes authority, it selects rows the backend already holds. Structurally it
is a view parameter exactly like the collapsed set, so it composes with
DR-BR-12 rather than needing a parallel code path — and as a backend
parameter it stays available to a headless consumer, which a frontend
implementation would not be.

Three constraints: substring matching only (a user-supplied regex is a
denial-of-service surface for no benefit), matching against the **casefolded
display form** rather than the canonical key (the user types what is on
screen), and the existing inbound size cap.

### DR-BR-16 — No inventory snapshot token

A generation token was designed to stop a paging client from stitching two
inventory generations together, then rejected. Recorded with its reasons so it
is not reinvented:

- `PRAGMA data_version` is database-wide, so any unrelated write causes
  spurious restarts, and it does not change for same-connection commits.
- A `COUNT` plus `MAX()` aggregate over mutation timestamps **collides**:
  acknowledging one row while another already carries a later timestamp leaves
  every aggregate identical. A token that can miss a change is worse than none.
- A recorder-maintained counter is exact but needs a schema addition and a
  bump on every write path, where a missed bump is a silent staleness bug.

The deciding argument is that it solves a problem the event stream already
solves better. The client observes the session and re-reads on terminal — a
precise causal signal that says what changed and when. The only case a token
adds is a concurrent write from **another process**, and M1 deliberately has
no cross-process visibility (DR-M1-08). A token would invent partial
cross-process awareness the milestone declined to build.

**Resolution:** re-read on view open, on observed session terminal for that
location, and after an acknowledge or restore. Rendered rows key on `row_id`,
so an externally torn page degrades to a missing or duplicated row that the
next re-read corrects. Severity is low regardless: nothing in this view acts
on display position — acknowledge and restore are row-id keyed, and
verify-selected is path-keyed and resolved server-side. The cross-process
limit is documented alongside the task rail's existing one.

**Never auto-scan.** A refresh is a real filesystem session, and periodic
rescanning would be the scheduled maintenance DR-M1-20 defers. Staleness is
reported through `list_stale_inventory`, not silently repaired.

---

## 5. Concurrency

### DR-BR-17 — Bridge handlers are concurrent and must be synchronized

DR-M1-15 established that pywebview's exposed functions run on separate
threads. `BridgeDispatcher` correctly has no locking, because the spike's
handlers were pure. Every piece of state Stage 6 adds is not, and the runtime
is protected only for what it already owns (`_plans` is lock-guarded).

- **Deselected set** — read-modify-write, so concurrent toggles lose updates.
- **Event queue and drain tracker** — DR-M1-18's ordering guarantee rests on
  "at most one outstanding drain per task," which is stated as a *client*
  obligation. Two concurrent drains each pop a partial batch and events arrive
  out of order. **An ordering guarantee enforced only by client discipline is
  not a guarantee**; the server holds a per-task drain guard and the second
  concurrent drain waits or is refused explicitly.
- **Subscription registry** — `SessionObserver.observe` raises when a session
  is already observed, so concurrent task opens must be guarded rather than
  treated as impossible.
- **Shutdown ordering** — stop accepting dispatches, wake every outstanding
  drain, close observations, then close the service. Wrong order hangs exit,
  the same failure XV-18 catches one layer down.

**Shape:** one `TaskState` per task holding queue, deselection, and
subscription, with a single lock. **Never hold a task lock across I/O.**
`preview_selection` is safe to hold — pure CPU over a frozen plan — but
anything starting a session releases first. DR-BR-09 removes the node table
that would otherwise have been a third lock site.

---

## 6. Inherited Bridge Posture

Unchanged from `M1_PLAN.md` and restated here only so this document is
self-contained: exactly one exposed `dispatch(command_json)`, versioned and
schema-validated and allowlisted (DR-M1-15/17); forced Edge Chromium with an
actionable failure and no MSHTML fallback; native `NavigationStarting` and
`NewWindowRequested` cancellation plus an independent per-call origin recheck;
no `evaluate_js`, `run_js`, or `Window.state` as application-data channels;
opaque ids inbound and escaped display text outbound; `textContent` only and
no `innerHTML`; the packaged asset server serves static assets and is not an
API channel.

The folder picker is the single flow where a real path legitimately enters.
The host runs the native dialog, retains the path in a server-side slot, and
returns `{id, display}`; the client only ever sends the id back.

---

## 7. Deferred, Rejected, and Open

**Rejected with reasons recorded:** the inventory snapshot token (DR-BR-16);
per-node lazy expansion in favor of flattened windows (DR-BR-12); a
minimum-size threshold and per-group sub-windows for move groups (DR-BR-11);
synthetic operation ids for structural folders (DR-BR-09); a client-side
search implementation (DR-BR-15).

**Deferred:** filter-exclusion visibility in plan review (DR-BR-05); repository
`LIMIT`/`OFFSET` for inventory, which currently loads a whole location per
call; the `derive_execution_selection` fixpoint cost, which scales with plan
size times dependency depth; `get_plan_review` rebuilding every view object per
call. These are noted cost points, not measurement gates — the
recorded-numbers standard in `M1_PLAN.md` §5 governs the executor refactor,
not this surface.

**Open, to settle during implementation:**

1. Where the deselected set lives — recommended `interfaces/web` keyed by
   request id, passed to `commit_plan` only at the end, keeping the workflow
   API stateless.
2. Whether changing selection invalidates an already-typed confirmation
   phrase — recommended yes.
3. The task-close protocol on a live session. `close_session` calls
   `Dispatcher.close`, which raises `SessionNotTerminal`; cancel → observe
   terminal → close needs a defined owner.
4. Plan-session lifecycle. A task opens a plan session and later an execution
   session, and nothing closes the first; the derived rail will show both.
5. Whether ghost rows survive view filters.
6. Single-instance behavior on second launch — focus the existing window, or
   exit with a message.
7. Whether pywebview is a hard dependency or an extra, and what a
   no-subcommand `nami-sync` does without it.

---

## 8. Delivery

Stage 5.5 is DR-BR-01 through DR-BR-05 plus the DR-BR-08 promotion, all
provable through the CLI. Stage 6 follows in eight slices:

| # | Slice | Gate |
| --- | --- | --- |
| 0 | pywebview reality spike | `CoreWebView2` reachability, pythonnet handler syntax, asset-server origin at runtime, off-thread `current_url` |
| 1 | Promote the spike into `bridge.py` / `host.py`; packaged assets; entry point; forced Edge Chromium | Window opens on real WebView2, guards attached, off-origin dispatch rejected |
| 2 | Command allowlist, JSON encoding, opaque-id and folder-picker slots | Every view type round-trips; hostile-name corpus survives a real dispatch |
| 3 | Event drain with coalescing, bounded wait, gap visibility, server-side drain guard | XV-18 plus concurrent-drain ordering |
| 4 | Node tree, paging, selection, autoscroll; vertical sync slice end to end | A desktop sync produces the same facade calls and classification as the CLI |
| 5 | Inventory and integrity views, five resolution states, context actions | XV-14 states render distinctly and actionably |
| 6 | History, settings, `ui-state.json`, single-instance mutex, clean shutdown | Four truth axes visible without string parsing |
| 7 | Documentation: rewrite `DESKTOP_UI.md` acceptance to as-built, README, re-status `ui_mockup/` | — |

Slice 0 shares nothing with Stage 5.5 and may run in parallel. It should run
**before** the Stage 6 sections here are treated as settled — four decisions
now rest on assumptions no code has verified against a real runtime.

**Testing posture.** Frontend verification is Python-side: bridge round-trips
over the scanner's hostile-name corpus, plus a static scan of packaged assets
asserting no `innerHTML`, `eval`, `Function(`, or `evaluate_js`. This covers
XV-19's ids-in / escaped-text-out and origin-recheck clauses. **It does not
prove a text node was created** — that limitation is recorded rather than
glossed, and closing it would require a DOM test runner this project does not
otherwise need.

The node tree is a **pure function** — plan review plus collapsed set plus
deselected set to an ordered node list — and is tested directly in pytest with
no bridge involved, including a hostile-named directory move, since grouping
does segment arithmetic on canonical keys while rendering escaped display
paths and the two must stay consistent.
