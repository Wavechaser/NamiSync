# M1 Bridge and Presentation Contract

Status: design and decision log for M1 Stage 5.5 (facade completion) and
Stage 6 (web desktop shell). Every decision here is unimplemented except
DR-BR-07, which records already-landed scanner work and is retained because
the reasoning behind that removal governs the presentation gap it leaves. It
governs the seam between `NamiSyncService` and the packaged frontend: what
computes where, how large plans and inventories reach the client, how
selection binds, and what the bridge may carry. Closing that seam necessarily
reaches below the facade where information would otherwise be lost: the
execution continuation retains user-selection provenance, and selected
inventory refresh gains an explicit recursive-subtree scan-and-record scope.

**Standing.** `FEATURES.md` owns behavior and `ARCHITECTURE.md` owns
contracts; both outrank this file. `M1_PLAN.md` owns the milestone's decision
log, and DR-M1-14 through DR-M1-19 remain the governing bridge decisions —
this document refines them with implementation detail settled afterward and
does not overrule them. Where it adds a decision M1_PLAN did not make, it is
numbered `DR-BR-##` to avoid colliding with either existing series.
`DESKTOP_UI.md` remains the user-facing delivery contract; this file is the
mechanism behind it.

**Propagation is deliberately deferred.** This document is still under active
revision, and scattering half-settled decisions across the active documents
would mean re-editing them on every pass. Nothing here propagates until it is
ready. `DESKTOP_UI.md` in particular **requires revision once it does** — its
interaction contract and acceptance criteria both still specify a typed
confirmation phrase, which DR-BR-03 removes for the desktop. Other active
documents are reviewed for drift at the same time, in one pass rather than
incrementally.

---

## Map of this document

Twenty-six primary decisions plus two numbered DR-BR-16 subdecisions have
accumulated across ten sections. The two lists below are navigation only. The
first follows the document's own top-level sections; the second re-sorts every
`DR-BR-##` by the module or layer it actually binds, which frequently cuts
across those sections (DR-BR-17 is filed under §4 but is a selection decision;
DR-BR-26 is filed under §8 but is a node-tree decision). Each entry is one
sentence: what the decision does, and what it connects to.

### Contents

1. [Stage 5.5 — Facade Completion](#1-stage-55--facade-completion)
2. [Compute Ownership](#2-compute-ownership)
3. [The Node Tree](#3-the-node-tree)
4. [Paging and Live State](#4-paging-and-live-state)
5. [Task and Process Lifecycle](#5-task-and-process-lifecycle)
6. [Concurrency](#6-concurrency)
7. [Inherited Bridge Posture](#7-inherited-bridge-posture)
8. [Verification](#8-verification)
9. [Deferred, Rejected, and Open](#9-deferred-rejected-and-open)
10. [Delivery](#10-delivery)

### Decisions by area

**`workflows/selection.py` + `interfaces/service.py` — selection and
commitment.** Who owns the checked/unchecked state of a plan, and what
"Execute" is allowed to freeze.

- **[DR-BR-01](#dr-br-01--user-selection-enters-the-facade-as-a-separate-set)**
  — user deselection is a second exclusion set alongside the planner's safety
  exclusions, never merged into one dictionary, so a reselect can't silently
  readmit a blocked operation. Its canonical provenance crosses the execution
  payload under the named `user-deselected` reason so `SKIPPED` user choices
  cannot be reconstructed as `DEFERRED` or mistaken for genuine `NOOP`; this
  advances the strict workflow payload to v4 and feeds DR-BR-02 and DR-BR-03
  directly.
- **[DR-BR-02](#dr-br-02--reselection-closes-upward-over-the-user-set-only)**
  — reselecting an operation removes its dependencies from the *user*-deselected
  set only, never from DR-BR-01's safety exclusions, so a checkbox can't
  immediately grey itself back out.
- **[DR-BR-03](#dr-br-03--selection-is-revisioned-and-commitment-freezes-it)**
  — selection gets an optimistic-concurrency revision number and a three-state
  commit (`reviewing → committing → committed`) so concurrent bridge handlers
  (DR-BR-24) can't race an execution start; the service owns that state while
  the runtime constructs a request from its immutable snapshot. Also where the
  typed-confirmation question and destructive-action confirmation get settled.
- **[DR-BR-04](#dr-br-04--deselection-does-not-survive-a-replan)**
  — a replan discards the prior selection and revision outright, because
  deterministic operation ids would otherwise let a stale checkbox silently
  re-apply to a plan no one reviewed.
- **[DR-BR-17](#dr-br-17--selection-is-server-side-state-the-dom-is-disposable)**
  — restates DR-BR-03's ownership for virtualized rows: a recycled DOM node
  must re-read authority from the server rather than remember it, and toggles
  batch into one revisioned mutation.

**`interfaces/service.py` — facade surface.** What the GUI can actually call.

- **[DR-BR-05](#dr-br-05--four-runtime-methods-reach-the-facade)**
  — lifts `acknowledge_inventory`/`restore_inventory`/`list_unacknowledged_missing`/
  `list_stale_inventory` from the runtime to the facade as plain passthroughs,
  closing an oversight the inventory view needs.
- **[DR-BR-06](#dr-br-06--location-commands-accept-opaque-ids)**
  — adds an id-based form of the location commands so the inventory view can
  drive scoped refresh/baseline/verify/rebaseline without ever sending a path;
  row ids mean one exact row while folder-node ids mean the complete recursive
  subtree, DR-BR-11's location scope validates ownership, and completed subtree
  refreshes use a genuine third reconciliation branch with indexed literal
  ranges; kind-aware decoding advances only the inventory workflow payload to
  v2.

**`modules/scanner.py` — scanner contract.** Already-landed, kept for context.

- **[DR-BR-07](#dr-br-07--scanner-ignore-contract-narrowed)**
  — records the landed removal of unused `IgnoreSet` snapshot machinery and the
  gap it leaves open: filtered files still have no visible "why" in plan review.

**Cross-cutting — the compute-ownership principle.** The rule everything else
in this document argues from.

- **[DR-BR-08](#dr-br-08--the-ui-never-computes-means-authority)**
  — reframes "the UI never computes" as *authority*, not *location*, sanctioning
  purely cosmetic client-side work (tri-state checkboxes, autoscroll anchor,
  filter chips) without contradicting the rule; sets up DR-BR-09's module split.

**`workflows/node_tree.py` + `core/pathing.py` — the node tree.** One shared
hierarchy builder behind both the plan tree and the inventory tree.

- **[DR-BR-09](#dr-br-09--node-trees-are-built-in-workflows-not-interfaces)**
  — puts the shared tree builder in `workflows/node_tree.py` because
  `interfaces` can't import `core`'s path arithmetic; contains the layer table
  this whole map is organized around.
- **[DR-BR-10](#dr-br-10--path-helpers-promote-to-corepathingpy)**
  — promotes the planner's three private path helpers to `core/pathing.py`
  unchanged, so DR-BR-09's tree builder can reuse instead of duplicate them.
- **[DR-BR-11](#dr-br-11--node-identity-is-deterministic-and-the-plan-tree-is-memoized)**
  — node ids are deterministic over `(tree kind, scope identity, path key)`,
  which is what lets DR-BR-06 validate that an id belongs to its location and
  lets a plan tree be memoized safely.
- **[DR-BR-12](#dr-br-12--folder-selection-is-path-scoped-and-the-tree-owns-the-scope)**
  — "deselect this folder" means every operation at or under that path,
  computed once by the same tree that produces rollups so the two can't
  disagree; the inventory side reuses that subtree index for DR-BR-06's
  recursive folder actions.
- **[DR-BR-13](#dr-br-13--decomposed-moves-render-as-a-paired-annotation)**
  — a folder rename's per-file moves group under the destination folder node
  with a dimmed ghost at the old location, annotated rather than reclassified
  into a second selection unit.
- **[DR-BR-26](#dr-br-26--the-node-tree-is-a-pure-function)**
  — keeps the tree builder testable in plain pytest with no bridge involved,
  including the hostile-name case DR-BR-11's location-scoped ids introduced.

**`interfaces/web` + `workflows/views.py` — paging, search, and live state.**
The bridge-facing layer that turns a tree plus view parameters into what the
client actually renders.

- **[DR-BR-14](#dr-br-14--progress-carries-item-identity-never-a-display-path)**
  — adds optional `item_id`/`item_type` to `Progress` as an additive wire
  change, giving DR-BR-19's autoscroll something to anchor on besides a
  display path.
- **[DR-BR-15](#dr-br-15--flattened-windows-over-a-stateless-visible-sequence)**
  — the server flattens tree + collapsed set + search + filters into one
  visible sequence and the client pages `[offset, limit]` windows of it — the
  shared shape behind the plan tree, inventory tree, and history. One canonical
  projection remains; at most the latest derived sequence is cached per view.
- **[DR-BR-16](#dr-br-16--paging-bounds-payload-and-must-also-bound-work)**
  (with
  **[DR-BR-16.1](#dr-br-161--the-inventory-projections-lifecycle)** and
  **[DR-BR-16.2](#dr-br-162--history-is-paged-at-the-database-not-after-it)**)
  — extends DR-BR-15 so paging bounds *work*, not just payload: a memoized
  plan tree, a cached per-view inventory projection with its own eviction and
  shallow copy-on-write rules, and a paged/aggregated history query. A persisted
  history summary is explicitly post-M1, not a fallback schema change.
- **[DR-BR-18](#dr-br-18--search-executes-on-the-backend)**
  — a search query is just another server-side view parameter alongside
  DR-BR-15's collapsed set, not a client-side filter, so plan scale and hostile
  filenames never become a JS matching problem.
- **[DR-BR-19](#dr-br-19--autoscroll-anchors-on-the-nearest-visible-ancestor-or-self)**
  — one rule collapses every follow-mode special case: the server resolves
  DR-BR-14's ancestor chain to the nearest visible node and visible-sequence
  index under the active view parameters.
- **[DR-BR-20](#dr-br-20--no-inventory-snapshot-token)**
  — rejects a generation-token mechanism for torn inventory reads in favor of
  re-reading on view-open/session-terminal/acknowledge, and defines
  acknowledgment as a hide-not-count filter touching only DR-BR-16.1's cache.

**`interfaces/web` — task and process lifecycle.** The client-visible unit
above any one session.

- **[DR-BR-21](#dr-br-21--a-task-is-client-state-sessions-come-and-go-beneath-it)**
  — a task card is durable UI state that outlives any one session beneath it,
  and is where a compound execute-then-verify run's two phases surface as one
  rail entry.
- **[DR-BR-22](#dr-br-22--closing-a-busy-task-cancels-waits-then-closes)**
  — specifies the confirm → cancel → wait-for-terminal-record → unsubscribe
  sequence for closing a running task, and the terminal-event-vs-terminal-record
  race that makes the ordering matter.
- **[DR-BR-23](#dr-br-23--single-instance-activates-the-existing-window)**
  — a named mutex plus Win32 window activation stops a second launch from
  opening a second window.

**`interfaces/web` — concurrency.** What the bridge's threading model forces
everything above to account for.

- **[DR-BR-24](#dr-br-24--bridge-handlers-are-concurrent-and-must-be-synchronized)**
  — catalogs every piece of state Stage 6 adds that needs explicit
  synchronization because pywebview handlers run on separate threads:
  selection revision (DR-BR-03), reliable-event backpressure, the event-drain
  guard, the subscription registry, and shutdown order.

**Verification.** Proof obligations that don't live at a single module.

- **[DR-BR-25](#dr-br-25--hostile-name-rendering-is-proven-in-a-real-browser)**
  — requires both a real WebView2 DOM test and a broadened static sink scan,
  with bridge transport proved in slice 2 and the actual plan/inventory DOM
  sinks proved only once those production renderers exist.

---

## 1. Stage 5.5 — Facade Completion

Stage 6 was blocked on gaps in the service surface. They are grouped as one
stage rather than folded into Stage 6 because each is verifiable before a
second interface exists.

### DR-BR-01 — User selection enters the facade as a separate set

`commit_plan` derives its selection from safety alone
(`derive_execution_selection(artifact.plan)`), and no user-chosen subset
exists anywhere. `DESKTOP_UI.md` nonetheless promises a "dependency-closed
selection," and the commitment model already anticipated one: DR-M1-05's
third binding is the selection digest, distinct from the plan and policy
fingerprints.

**Resolution: user deselection is a second, independent input to the same
derivation — not a seed into the same dictionary.**

`derive_execution_selection` computes **safety exclusions** (blocked,
quarantined correspondence, incomplete scan, and their transitive dependents)
from the plan alone. The signature becomes
`derive_execution_selection(plan, *, user_deselected=frozenset())`, and the
two exclusion sources stay separately identifiable throughout. Merging them
into one dictionary would let DR-BR-02's upward reselection clear a
*blocked* or *quarantined* exclusion, silently readmitting an operation the
planner refused. **Safety exclusions are immutable and unreachable by any
user action.**

The final selection is the plan's operations minus the union of both sets,
with the dependency fixpoint run over the union so a dependent of either kind
is excluded correctly.

The service accepts user mutations only for operations that are toggleable
after safety derivation. `user_deselected` is therefore canonical and disjoint
from all safety-derived exclusions; sending a disabled operation id is refused
rather than retained as fake user provenance.

**Outcome semantics.** A user-deselected operation reports `SKIPPED`.
Operations force-excluded *because* a dependency was deselected keep
`DEFERRED` and drive the `partial` headline — the user chose the parent, not
the children, and collapsing that distinction would misreport the run.
`ExclusionReason` gains the stable member
`USER_DESELECTED = "user-deselected"` for the direct choice; reusing
`BLOCKED_DEPENDENCY` would erase exactly the provenance this decision exists
to preserve. Dependency fallout retains `BLOCKED_DEPENDENCY`. Exclusion reason
values remain disjoint from executor reason values so persisted history can
identify excluded rows without parsing detail text.

**That distinction must survive the second-session boundary.** The final
selected-id set cannot reconstruct whether an omitted operation was a direct
user choice or dependency fallout: different user actions can produce the same
runnable set while requiring different `SKIPPED`/`DEFERRED` explanations.
`ExecutionSet` therefore carries the canonical immutable `user_deselected`
operation-id set alongside `selection`; the execution payload and every
execute/verify continuation serialize it. `run_execution` re-derives the
selection and typed exclusions from `(plan, user_deselected)` and refuses a
derived-selection mismatch before preflight. Pause/resume and history then see
the same explanations that were reviewed.

This is a **strict workflow-payload version change**, not an unversioned field
addition. Payload v3's exact-key execution-set shape cannot represent the
provenance, so Stage 5.5 advances the shared opaque workflow payload to v4 and
continues to reject older versions. The plan-request half changes version with
the shared envelope even though its body shape is unchanged. M1 has no durable
cross-process queued payloads to migrate.

This provenance is **not a fourth commitment binding**. The selection digest
continues to authorize the exact runnable operation set; `user_deselected`
explains why reviewed operations sit outside it and cannot grant additional
filesystem authority.

**An empty effective selection is refused, not executed.** If user deselection
removes every otherwise selectable operation, `commit_plan` returns the
distinct actionable error "Nothing is selected to synchronize" before
admission. The UI disables Execute with the same reason. This refusal is about
an empty selected set, not about the executor's `SKIPPED` outcome vocabulary.

**`NOOP` remains real selected work.** It confirms observed state and performs
its required recording even though the executor settles it with
`Outcome.SKIPPED`. A nonempty selection containing only `OperationKind.NOOP`
therefore executes and retains the `all-noop` headline. The classifier must not
infer that headline from "every operation outcome is `SKIPPED`": user-deselected
COPY/UPDATE/etc. exclusions also carry that outcome. `all-noop` means the
**effective selection is nonempty and every selected operation kind is
`NOOP`**; user-deselected exclusions do not participate in that predicate.

**Safety-excluded rows render disabled, not merely unchecked.** Because
reselection cannot reach a safety exclusion, a checkbox on a blocked or
quarantined row would be inert — the user clicks and nothing happens, which is
the same failure DR-BR-02 exists to prevent. Those rows present a disabled
control alongside the reason, so the distinction between "you turned this off"
and "the planner refused this" is visible before the click, not after.

### DR-BR-02 — Reselection closes upward, over the user set only

The exclusion fixpoint propagates **downward only**. Deselecting folder `a\b`
removes `MKDIR(a\b)` and every copy beneath it; reselecting
`a\b\important.txt` alone leaves that copy depending on a still-deselected
`MKDIR`, so the fixpoint immediately re-excludes it as `blocked-dependency`.
The user would watch a checkbox go grey the instant they clicked it.

**Resolution:** reselecting an operation also removes its transitive
`dependencies` **from the user-deselected set**. It can never remove a safety
exclusion (DR-BR-01), so reselecting a child whose parent is genuinely
blocked leaves the child excluded, correctly and visibly.

### DR-BR-03 — Selection is revisioned, and commitment freezes it

Selection is server-side state mutated by concurrent bridge handlers
(DR-BR-17). A lock alone is insufficient: two toggle batches can acquire it in
an order different from the user's clicks, and an execution request can race a
queued preview, committing a selection other than the one on screen.

**Resolution: optimistic concurrency with an explicit revision.**

- Selection state is owned by the **service**, keyed by plan request id, not
  by the web adapter. Ownership below the bridge is what lets execution
  validate atomically.
- Every mutation supplies the **expected revision**. On match, the server
  applies it and returns the new revision plus the current selection digest.
  On mismatch it applies nothing and returns an explicit **conflict** with the
  current revision, and the client re-reads. Responses are never silently
  discarded — a late response either applied or reported conflict, so the
  client and server cannot diverge.
- This replaces an earlier "at most one outstanding, discard stale by request
  id" rule, which contradicted itself: discarding a response whose mutation
  already applied would desynchronize the client. At most one mutation is
  outstanding, queued batches merge, and every response is processed.
- The revision increments on every **applied** mutation whether or not the
  effective set moved, because a no-op batch or a deselect-then-reselect cycle
  reproduces an identical digest and digest comparison cannot detect that
  anything was applied. Revision answers "has an accepted mutation advanced
  this view"; digest binds the actual selected set and is what `commit_plan`
  validates.

**Commitment has three states, because admission can fail.** Freezing straight
to `committed` strands the selection: `start_execution` calls `commit_plan`
and *then* `Dispatcher.submit`, so a submit failure leaves no session while the
selection stays frozen and Execute stays dead. The task becomes unusable with
nothing to retry.

The transition is `reviewing → committing → committed`:

1. Under the selection lock, validate the expected revision and snapshot the
   effective selection.
2. Mark `committing`, release the lock, and submit.
3. On success, mark `committed`.
4. **On failure, return to `reviewing`** and leave Execute available. Nothing
   ran, so nothing is bound.

A concurrent Execute observing `committing` must not create a second session —
it is a duplicate of work already in flight, not a new request. A double-click
therefore produces exactly one session.

Mutations against a `committing` or `committed` selection are refused with a
**distinct** response, not a revision conflict. A conflict tells the client to
re-read and retry; committed means retrying is wrong. The client settles
silently into the frozen selection with its controls disabled — a late click
made before the freeze changed nothing and warrants no error.

A `committed` selection returns to `reviewing` only through a new plan, which
under DR-BR-04 discards it entirely.

**The client supplies a revision, never a digest.** JavaScript needs the
revision for stale-view detection and nothing more. The service derives the
selected set and its digest authoritatively when constructing the commitment,
so the binding cannot be shaped by anything the client sends.

**The service/runtime boundary follows that ownership.** Under its selection
lock the service validates the expected revision, snapshots the immutable
`user_deselected` set, and enters `committing`. The runtime receives that
snapshot only; it has no selection revision or client-supplied digest to
validate. It derives the effective set, constructs the commitment and
`ExecutionRequest`, and returns them for dispatcher submission. This keeps the
concurrency state in one owner while the runtime remains the sole constructor
of workflow requests.

The CLI retains its automatic-selection path without acquiring GUI revision
semantics. Omitting `expected_revision` is accepted only while the service
selection is untouched (`revision == 0`, empty `user_deselected`, and
`reviewing`); the web command schema always requires a revision. An adapter
cannot omit the revision after editing a selection and silently commit whatever
state happens to be current.

**No typed confirmation phrase in the GUI.** The CLI's typed `execute` is a
terminal convention and stays there. The safety invariant is the mandatory
two-step — plan and review, then separately commit — not the ritual by which
an interface elicits the second step. A GUI's speedbump is the plan review
itself, and adding a modal after it trains users to dismiss modals, which is
worse than none. Removing the phrase also collapses this decision: the Execute
click *is* the moment of intent, so the revision anchors to it directly and
there is no interval to protect between typing and committing.

The plan's scale is already legible from the status box and the filter counter
chips; restating it on the button would be a third redundant readout, not a
safeguard.

**Confirmation is reserved for the genuinely irreversible.** In M1 the public
request path almost cannot reach one: the `workflows/views.py`
`_require_deletion_policy` validator admits only `trash` and `additive`,
`db/settings.py` refuses persisted semantic defaults that enable `mirror`, and
even a directly constructed `SyncOptions` requires
`internal_mirror_authorized` in `core/planning.py`. Consequently `mirror` is
unreachable through the M1 facade surface, removals go to `.SYNCTRASH` with no
retention sweep to purge them, and execution can be paused or canceled.

The single exception is `UPDATE` while `trash_on_update` is disabled, where
the prior target content is overwritten with no recoverable copy
([executor.py:2095](../namisync/modules/executor.py) guards the trash step on
that flag). **`MOVE_UPDATE` does not count**: `_move_update` publishes to the
new path and trashes the old one unconditionally, with no `trash_on_update`
guard, so its prior content is always recoverable.

**Risk is computed from the effective selection, server-side.** A modal for a
"plan carrying" such an update would be wrong — if the user deselected every
irreversible update, nothing irreversible remains and no confirmation is
warranted. `preview_selection` therefore returns authoritative primitive
fields alongside the outcome changes:

- `requires_destructive_confirmation`
- `irreversible_update_count`

The frontend renders those facts. It must never inspect operation kinds and
policy flags to reach its own conclusion — that would be authority in the
browser, and it would drift the moment a new irreversible case is added.

**The modal reintroduces a revision interval, so it must validate one.** For
an ordinary selection Execute calls `start_execution(request_id,
expected_revision)` directly and no interval exists. When confirmation is
required:

1. Execute opens the modal for revision `R`.
2. Confirm calls `start_execution` with `R` plus the destructive
   acknowledgement.
3. The service recomputes the effective selection and its risk under the
   selection lock.
4. If the selection moved while the modal was open, execution is refused as
   stale and the modal closes back to review.

The debounce and single-outstanding-mutation rules make that race unlikely
rather than impossible, and an unlikely hole that silently executes an
unconfirmed irreversible write is still worth closing.

Later, a destructive purge or `mirror` joins the same mechanism rather than
adding a second one. Friction scales with irreversibility rather than being a
flat toll, so the dialog carries weight on the rare occasion it appears.

### DR-BR-04 — Deselection does not survive a replan

Operation ids are deterministic over intent
(`deterministic_operation_id(kind, source, target, prior_target, reason)`),
so a replan of an unchanged tree reproduces identical ids and a stale
deselected set would silently still apply. That is a trap: the new plan may
contain operations no human reviewed, and carrying the old set forward would
let a checkbox state never applied to *this* plan participate in
`selection_digest`.

**Resolution:** any preflight rescan discrepancy invalidates the plan and
forces re-review; any mutative refresh of a plan discards its selection and
resets the revision. The UI states that the selection was reset because the
plan changed. Required coverage asserts the discard rather than trusting it.

### DR-BR-05 — Four runtime methods reach the facade

`acknowledge_inventory`, `restore_inventory`, `list_unacknowledged_missing`,
and `list_stale_inventory` stop at `LocalWorkflowRuntime`. The inventory
context menu and the staleness affordance both need them, and their absence
was an oversight rather than a decision. They lift as passthroughs with view
types, matching every other facade read.

Everything else on the runtime is already lifted or is dispatcher wiring
(`prepare_*`, `open_*`, `audit_observer`) that correctly stays below the
facade.

### DR-BR-06 — Location commands accept opaque ids

The facade's location commands accept `selected_paths`, but DR-M1-16 forbids
JavaScript from sending paths. As specified, the inventory view could not
drive a scoped refresh, baseline, verify, or rebaseline at all.

**Resolution:** each location command gains an id-based form accepting opaque
node or row ids. The service validates that every id belongs to the named
location. An id belonging to another location is a refusal, not a silent
filter. Multiple ids are unioned and deduplicated before a workflow request is
constructed. The id-based form refuses an empty id collection before scope
construction; it must not reinterpret "nothing selected" as the path form's
deliberate full-location request.

**Row and folder ids deliberately have different scope.** A row id resolves to
that one exact inventory subject. A folder-node id resolves to the folder and
its complete recursive subtree through the same descendant index the tree uses
for rollups, regardless of which descendants currently pass a view filter.
Treating a folder as one exact path — or as only its visible descendants —
would make a hierarchical context action appear to cover its children while
silently omitting part of the subtree.

Integrity actions (`baseline`, `verify`, `rebaseline`) freeze the folder's
currently indexed descendant rows into exact row ids/paths before admission;
their existing exact-subject workflow semantics remain unchanged. **Refresh is
different:** expanding only current inventory rows would miss files newly
created beneath the folder. The scanner therefore gains an explicit recursive
subtree scan scope, distinct from today's exact selected-path scope. A folder
refresh passes that subtree root and discovers the folder's current and new
descendants in one ordinary inventory session.

The scope contract is explicit rather than inferred from a directory path:
`ScanScopeKind` gains `SUBTREES` alongside `FULL` and exact `PATHS`. Overlapping
subtree roots canonicalize by path-segment ancestry to the minimal
non-overlapping roots, never by raw string prefix. Exact paths at or below one
of those roots are redundant and are removed; exact paths outside them remain
exact, including an exact directory-row id that must not become recursive.
Selecting the location's empty relative root canonicalizes the entire mixed
scope to `FULL`: it covers the whole location, and treating `""` as an ordinary
delimiter range would miss every top-level entry. A successful subtree scan is
complete for its remaining roots and exact paths, not for the whole location.

`SUBTREES` is also the mixed scoped form. If an id-based refresh contains both
row ids and folder-node ids, `ScanScope` carries `selected_paths` and
`subtree_roots` together under `SUBTREES`; it does not discard either half,
promote exact directory rows to recursive roots, create a fourth scope kind,
or split one user action into multiple sessions. Its constructor invariants
are exact: `FULL` carries neither field; `PATHS` carries nonempty
`selected_paths` and no roots; `SUBTREES` carries at least one
`subtree_root` and may also carry exact paths. Canonicalization chooses `FULL`
when both scoped fields are empty. Only the existing explicit full-request form
or selection of the location's root node may reach that state.

This is a third reconciliation shape, not a new value that may fall through
the existing two-way discriminator. `ScanResult.is_full_scan` remains true
only for `FULL`; after checking `scan.complete`, `db/recorder.py` branches
explicitly on all three scope kinds:

- `FULL` uses the current all-location observed-key anti-join;
- exact `PATHS` retains its exact-key missing inference; and
- `SUBTREES` uses the same observed-key anti-join, bounded independently to
  the union of any remaining exact paths plus each completed root and its
  descendants.

The subtree branch reconciles rows whose prior presence is either `present` or
`unsupported`, matching full-scan reconciliation. It marks one missing only
when the row was absent from the completed scan and its canonical key is
either the root itself or in this wildcard-free descendant range:

```sql
rel_path_key >= :root || '\'
AND rel_path_key < :root || ']'
```

The equality case `rel_path_key = :root` is tested separately. `]` (0x5D) is
the immediate binary successor of the canonical separator `\` (0x5C), so this
range selects exactly keys beginning with `root || '\'` under SQLite's default
binary collation. `LIKE` is forbidden here: `%` and `_` are legal hostile-name
characters and would turn a literal subtree root into a wildcard pattern.
Rows outside the roots are untouched. Any incomplete subtree scan
conservatively withholds all missing inference, matching the existing
selected-scan rule.

Completeness distinguishes absence from uncertainty. If a subtree root no
longer exists, that root is a successful empty observation and its previously
indexed root/descendant rows may become missing. Access denial, enumeration
failure, an unhydrated directory placeholder, or a directory reparse point
means the scanner could not observe the claimed recursive scope; it makes the
whole multi-root `ScanResult` incomplete and therefore marks nothing missing
under any requested root. Per-root completeness would require a richer result
contract and is not introduced implicitly here.

The existing
`inventory_location_presence_idx(location_id, presence, rel_path_key)` serves
the location/presence equalities plus each root range directly. A focused
`EXPLAIN QUERY PLAN` assertion verifies indexed range search for a
representative subtree rather than leaving the bounded-cost claim as an
assumption.

`InventoryRequest`/`InventoryWorkflowRequest` carry subtree roots separately
from exact selected paths, including both fields for a mixed id selection. The
inventory workflow payload advances from v1 to v2 for that new field and
rejects v1; the integrity payload remains v1 because folder integrity actions
are expanded into its existing exact subjects before admission. The two
decoders currently share `_payload`, whose hardcoded v1 guard would make that
divergence impossible. Its signature becomes
`_payload(payload, expected_kind, expected_version)`;
`decode_inventory_request` passes v2 and `decode_integrity_request` passes v1.
Tests prove inventory v2 round-trips while inventory v1 is rejected, and that
integrity v1 remains accepted.

The path form remains for the CLI, which legitimately has paths and retains its
current exact-path meaning. Recursive CLI scope is not inferred or added as a
side effect of the desktop contract.

### DR-BR-07 — Scanner ignore contract narrowed

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

### DR-BR-08 — "The UI never computes" means authority

The original rule was driven by two goals: the backend must run full
functionality headlessly, and the browser must never hold decision power.
Neither forbids the client from computing things that affect only its own
presentation.

**Resolution — cosmetic versus authoritative describes what a computation
affects, not where it runs.** The client never computes selection semantics,
dependency closure, result classification, or headline precedence. It may
compute purely cosmetic state for itself. Conversely, cosmetic work may
legitimately execute on the backend when that is where the data lives — being
cosmetic is not an argument for running in the browser.

Three client-side computations are sanctioned under this rule, named
explicitly so the rule is not later cited to block them: rendering tri-state
checkboxes from server-supplied outcomes, scrolling to the server-resolved
anchor/index from DR-BR-19, and rendering filter chips from server-supplied
counts.

An earlier draft sanctioned a fourth — applying view filters to
already-materialized rows — which was wrong for the reason DR-BR-18 gives
about search, and for a sharper one. **Filtering a window and windowing a
filter are different operations.** The client holds a slice of the *unfiltered*
sequence, so filtering it yields an arbitrary subset of an arbitrary slice:
"deletions only" would show the deletions in the current viewport rather than
the plan's deletions, and scrolling would reveal more of them. Filters are
server-side view parameters (DR-BR-15). What the client renders is the chips,
never the decision about what passes.

### DR-BR-09 — Node trees are built in `workflows`, not `interfaces`

The import law forbids `interfaces → core`, so the web layer cannot call
`normalize_relative_path` and cannot safely group paths — grouping on display
strings gets Windows case semantics wrong. Anything requiring path arithmetic
must sit at workflows-or-below.

There is also a precedent. DR-M1-07 built the view vocabulary precisely so
interfaces would not reconstruct domain structure by inspecting shape.
Reconstructing a *hierarchy* from path strings in the adapter is that same
anti-pattern one level up.

**Resolution:** one new `workflows/node_tree.py` holds the shared hierarchy
builder — ancestor synthesis, deterministic node ids, ordering, and subtree
rollups — over any collection of path-keyed rows. Plan-specific move grouping
(DR-BR-12) and the inventory projection are thin layers on it. Two trees, one
implementation; a second near-duplicate module is exactly the drift this
project avoids.

| Layer | Compute |
| --- | --- |
| `core/pathing.py` | relative-key `parent` / `depth` / `is_descendant`, common-suffix stripping |
| `core/execution.py` | immutable selected ids plus canonical user-deselection provenance in `ExecutionSet` |
| `core/models.py` | FULL/PATHS/SUBTREES scan scopes; SUBTREES may retain exact paths outside its recursive roots |
| `modules/planner.py` | unchanged behavior; loses its three private path helpers |
| `modules/scanner.py` | unchanged exact selected-path scan plus explicit recursive/mixed subtree scan scope |
| `db/recorder.py` | explicit FULL/PATHS/SUBTREES reconciliation; completed subtree refresh uses indexed literal ranges and marks missing only within its exact-path/root union |
| `workflows/selection.py` | safety exclusions, user deselection, downward cascade, upward closure |
| `workflows/node_tree.py` | ancestor synthesis, node ids, subtree op sets, rollups; plan move grouping and inventory projection |
| `workflows/views.py` | `PlanNodeView`, `InventoryNodeView`, preview projection |
| `workflows/runtime.py` | construct committed requests from authoritative `user_deselected`; no revision or client digest |
| `interfaces/service.py` | selection state/revision and commit transition, the four lifts, id-based location commands, tree passthroughs |
| `interfaces/web` | bridge, host, command allowlist, task state and locks, bounded event queue, JSON encoding, collapse/filter/search flattening, windowing, autoscroll lookup |

`interfaces/web` remains the largest new surface by volume, but after this
split it holds no domain-shaped computation — transport and presentation
mechanics only.

### DR-BR-10 — Path helpers promote to `core/pathing.py`

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

### DR-BR-11 — Node identity is deterministic, and the plan tree is memoized

Structural folder nodes have no operation and still need addressing for
collapse state and folder-scoped selection.

*Staged across both stages.* Location-scoped identity lands in Stage 5.5,
because DR-BR-06's id-based location commands cannot validate ownership
without it. Plan-scoped identity and the plan memo land with the plan tree in
Stage 6 slice 4. Same rule, two arrival times.

**Resolution:** node ids are deterministic over
**`(tree kind, scope identity, canonical path key)`** — not over the path
alone. Scope identity is the plan request id for plan nodes and the location
id for inventory nodes.

The scope component is not decoration. DR-BR-06 promises that a location
command refuses an id belonging to another location, and a path-only id makes
that check impossible: two locations both containing a `docs` folder would
produce the same id, so the service could neither reject the foreign id nor
detect that it had resolved into the wrong tree. Scoping the id is what makes
ownership validation mean anything.

Determinism still buys two things: a concurrent rebuild produces
byte-identical ids so there is no race to lose, and the built tree may be
**memoized per scope** without an invalidation protocol. For plans that memo
is exact — the artifact is immutable and `save_plan` keys by a freshly minted
request id — and it is dropped by `drop_plan`. The memo holds *structure
only*; selection outcomes overlay per request, since those change with every
preview. Inventory scope is not immutable and is handled by DR-BR-16.

They remain opaque in the sense DR-M1-16 requires: the client cannot
construct one from a path, and the server resolves it through a tree it owns.

**Synthetic ids never become operation ids.** Folder nodes come in three
flavors — a real `MKDIR`, a real directory-cleanup `DELETE`, or pure
structure. Only the third is synthetic, and giving it an `operation_id` to
make the tree uniform would reach the recorder, history item identity, and
the selection digest simultaneously. Node ids are minted by
`workflows/node_tree.py` and travel no further down: they never enter `core`,
the domain modules, persistence, or execution. Selection resolves them to real
operation ids before anything binds.

### DR-BR-12 — Folder selection is path-scoped, and the tree owns the scope

A folder node frequently has no operation at all: the planner skips `MKDIR`
when the target directory already exists, so copying into an established tree
produces operations with no directory dependency. "Deselect this folder"
therefore cannot mean "deselect this folder's operation."

**Resolution:** it means every operation whose target sits at or under that
path. The tree already computes subtree membership to produce rollups, so
`deselect_node` is a lookup returning an operation-id set, then the ordinary
derivation. One path walk, not two, and no chance of the two disagreeing.

The inventory tree reuses the same structural rule for commands rather than
selection: its folder-node lookup returns every descendant inventory row for
integrity work, while refresh sends the folder path as the recursive subtree
root defined by DR-BR-06. Plan and inventory therefore agree on what a folder
gesture covers without pretending their downstream workflows have the same
input type.

Dependencies exist for exactly two structural reasons, running in opposite
directions: a child depends on the `MKDIR` that creates its parent
(one `MKDIR`, many dependents), and a directory-cleanup `DELETE` depends on
every removal beneath it (one `DELETE`, many dependencies). File `TRASH` and
`DELETE` carry none. A single folder checkbox meaning "everything at or under
this path" is coherent across both, but the resulting tri-state must be
**rendered from what the server returned**, never predicted from sibling
checkbox states — the cascade runs opposite ways in the two subtrees.

### DR-BR-13 — Decomposed moves render as a paired annotation

A folder rename decomposes into one move per file. Left flat, the rows sprawl
across the destination tree indistinguishable from unrelated new content, and
a reviewer must read every source path to notice they share a prefix. At
realistic scale it is unreviewable, and it buries genuinely new content
sitting alongside it.

**Resolution: annotate, do not reclassify.** The destination folder node
carries the move annotation and its rollup; a dimmed, non-interactive row at
the old location points to it, and the two highlight together.

- **The group is the folder node, not a new selection unit.** A destination
  folder may receive both moved files and genuinely new copies in the same
  run; making the group its own unit would let the collapsed row report only
  the moves and silently omit the rest. Its checkbox is the ordinary
  path-scope deselection from DR-BR-12 — no second selection currency.
- **The ghost is an annotation on the old location.** When the old location
  still holds real operations (a partial move where some files stayed and
  were trashed), the existing node is annotated and no ghost is emitted. The
  dimmed row is what renders when the old location would otherwise have no
  node. One mechanism, two renderings.
- **Ancestor synthesis takes the union** of operation target paths and prior
  target paths, since a ghost position may have no other reason to exist.
- **Nested moves suppress the inner ghost.** If a move's old path falls under
  another move's old path, the outer annotation already explains it and the
  inner would be orphaned at a position that no longer exists.
- **No "renamed" label.** The planner never asserts a rename; the grouping is
  inferred from path arithmetic over move operations, and enough unrelated
  files moving between two directories would be labeled falsely. The kind
  column keeps `MOVE` / `MOVE_UPDATE`, and the annotation reads literally —
  "moved from `<old path>`" — true whatever the cause.
- **No minimum-size threshold and no sub-window.** A two-file move gets the
  same treatment as a two-thousand-file move; collapsed it occupies the same
  rows sprawl would. Group children need no separate paging because expanding
  inserts rows into the flattened sequence (DR-BR-15), which the existing
  window already serves.

---

## 4. Paging and Live State

### DR-BR-14 — Progress carries item identity, never a display path

Follow mode anchors on the current operation, but `Progress` carries only
`items_done`, `items_total`, `bytes_done`, `bytes_total`, and `current_path`.
Mapping a running operation to a node would require joining on a display
path — forbidden, ambiguous under escaping, and wrong.

**Resolution:** `Progress` gains optional `item_id` and `item_type`,
mirroring the nominal `ResultItem` vocabulary DR-M1-10 established rather
than inventing a parallel one. Both emission sites already hold the value:
the executor's reporter knows its current operation, and the verifier's knows
its current subject row.

The fields are optional **as a pair**: legacy producers omit both; an
identified progress event supplies a nonempty `item_id` plus `item_type` equal
to `operation` or `integrity`. `Progress.__post_init__` rejects a one-sided
pair or an unknown type, so the bridge never guesses which node-id namespace
an opaque id belongs to.

**This is a versioned wire change and must be treated as one.** An earlier
draft argued that because `HistoryObserver.on_event` refuses `Progress` and
nothing persists it, no schema concern arose. That reasoning was wrong:
persistence is not the criterion. `Envelope` carries an explicit
`schema_version` that `__post_init__` and `envelope_from_dict` both reject on
mismatch, and both serialization directions are tested. Adding fields changes
the serialized body regardless of where it travels.

**Resolution:** land it as an **additive change within the current version**,
which requires three things rather than none. The new fields carry defaults so
existing producers remain valid without modification. `envelope_from_dict`
tolerates a body lacking them and yields the defaults: unlike the existing
required Progress fields, the two new fields are decoded with
`raw.get("item_id")` and `raw.get("item_type")`, not strict subscripts. And
explicit compatibility tests assert both directions — a pre-change payload
deserializes, and a post-change envelope serializes with the fields present —
because an additive claim is only true if something proves it. A third test
rejects a one-sided identity pair.

Absent those tests the change requires a version bump instead. What is not
acceptable is changing the body while asserting the version is unaffected
because nothing writes it to disk.

The remaining footprint is genuinely small: a dataclass field pair, two
emission sites that already hold the value, and the serializer pair.

The bridge enriches `item_id` into an ancestor node-id chain. **Never join on
`current_path`**, which remains display-only telemetry.

### DR-BR-15 — Flattened windows over a stateless visible sequence

DR-M1-18 fixed that bridge data is paged pull/RPC but not the shape. Per-node
lazy expansion was considered and rejected: a review UI wants everything
expanded by default — "show me what you are about to do" is the point of a
dry run — and lazy expansion makes the default state cost one round trip per
folder.

**Resolution:** the server flattens the tree into an ordered visible sequence
given the active **view parameters** — collapsed nodes, search query, and
filters — and the client requests `[offset, limit]` windows of it. One command
shape serves the plan tree, the inventory tree, and history items, and scroll
position maps directly to an index.

**One canonical projection per open view, one active parameter set.**
Filtering, searching, and collapsing never produce additional trees. "Session"
is intentionally not the identity here: a reviewed plan has no live session,
and inventory projections are keyed by `(task id, location id)`. Every paging
request applies the view's current parameters to its one canonical projection
and slices the resulting visible sequence. Changing a parameter **replaces the
current visible sequence**; it does not fork a second structure to cache,
invalidate, or drift against the first. This keeps the plan memo in DR-BR-11
and each projection in DR-BR-16.1 single objects rather than families keyed by
parameter combinations.

**Filters apply symmetrically to both trees.** Sync and Integrity use the same
flatten signature, so the Integrity side gets identical behavior rather than a
parallel implementation with its own semantics.

**A folder renders only if it has a visible descendant, or is itself a
match.** Without this, every filter leaves a skeleton of empty directories —
"deletions only" would render the whole directory structure with almost nothing
in it. The second clause carries real weight on the plan side, where a folder
can be an operation in its own right (`MKDIR`, cleanup `DELETE`), and it also
disposes of the move-ghost case correctly: a ghost hidden by a filter takes its
synthesized ancestor chain with it, since those nodes exist only to host it
(DR-BR-13). Where a ghost was *not* emitted because the old location still held
real operations, that folder is visible on its own merits and is unaffected.

**Rollups on a folder row describe the folder, not the filtered view.** A
number whose meaning changes with filter state is a bug factory, and selection
already commits to unfiltered semantics (DR-BR-17): a folder checkbox covers
every operation beneath it regardless of what is rendered. Rollups follow that
same rule, and the filter chips carry the counts that describe the current
view. A move annotation is provenance rather than a count and reads the same
under any filter.

Collapse, filter, and search ride on the request rather than being retained as
independent server-side objects, so **the view parameters** leak no lifecycle.
That is a narrower claim than an earlier draft made: DR-BR-16's cached
inventory projection is genuine server-side per-view state, and its lifecycle
is specified there rather than denied here. The default is expanded, so
collapsing is a deliberate act on a handful of folders, and the existing 64 KB
inbound cap is the backstop.
**Responses need a server-enforced `limit` ceiling** — the current cap is
inbound only, and a truncation must be an explicit refusal rather than a short
list that reads as a complete tree.

Fixed row height is a design constraint, not an aesthetic preference:
variable heights require measurement passes that make window math fragile.

### DR-BR-16 — Paging bounds payload, and must also bound work

Windowing solves response size. It does not, by itself, solve
responsiveness: a naive implementation rebuilds the tree from the whole plan,
flattens it entirely, and then slices — doing whole-collection work for every
viewport scroll. Inventory is worse, since `get_inventory` loads an entire
location per call with no `LIMIT`/`OFFSET`.

**Row-level SQL paging is rejected.** An earlier draft moved `LIMIT`/`OFFSET`
into the repository query. It does not compose with this tree design, for
three independent reasons:

1. Ancestor synthesis needs the whole collection to know which folders exist,
   and subtree rollups need every descendant. A page of rows cannot produce
   either.
2. Paging happens *after* collapse and search produce a visible hierarchical
   sequence, so the offset a client asks for is an index into the visible
   tree, not into a row ordering.
3. The visible tree order is not `(rel_path_key, id)` order. Lexicographic
   path-key sorting is not depth-first pre-order, because the separator `\`
   (0x5C) sorts *after* characters that are legal in filenames — `a-x` sorts
   before `a\b`, while the tree places `a\b` inside `a` and `a-x` after it.
   The two orders genuinely differ.

A folder node id also cannot be resolved to its subtree without the location
index rebuilt anyway.

**Resolution: one coherent model — a cached per-view projection, built from a
slim query.**

- **Plan tree:** memoized per request id (DR-BR-11), exact because the
  artifact is immutable.
- **Inventory tree:** the repository gains a **slim structure query** —
  explicit columns, not `SELECT *`, and no full `InventorySnapshot`
  construction — returning every row in the location. The tree builder holds
  that projection per open view. A **detail query** then fetches full
  snapshots for the visible window's row ids only, so the expensive per-row
  work is bounded by the viewport while the structure work is bounded by the
  view's lifetime. Its lifecycle is DR-BR-16.1.
- **History:** see DR-BR-16.2. Its data path currently loads everything, and
  slicing afterward would bound only the bridge payload.
- **Named scale gate.** Synthetic plans, inventories, and history at defined
  sizes, with recorded window-response times, recorded projection build and
  memory cost, and recorded `preview_selection` times at realistic dependency
  depth. History is measured on a run with a large item count, not only a
  large run count. This is not the executor's measured-throughput standard; it
  is a stated ceiling with numbers behind it. If a size cannot be served
  responsively, **the supported M1 ceiling is documented rather than left as
  an unknown cliff.** The in-memory projection makes location size a memory
  question as well as a time question, and the gate must record both.

Flattening under the active collapsed set, filter, and search remains the
per-request cost for both trees. If the gate shows it matters, the named
fallback is one **latest visible-sequence cache per open view**, tagged with
the exact parameter tuple that produced it. Scroll-only paging with unchanged
parameters hits that cache; changing any parameter replaces it. No
parameter-keyed family is retained. The cache is not built before the numbers
justify it.

The `derive_execution_selection` fixpoint remains O(operations × dependency
depth) per preview and is measured by the same gate.

#### DR-BR-16.1 — The inventory projection's lifecycle

A cached projection is server-side per-view state and needs its rules stated,
or it leaks memory and serves torn reads.

- **Identity.** A projection is keyed by `(task id, location id)`. Opening a
  location in a task creates one; the same location open in two tasks is two
  projections, because their invalidation timing is independent.
- **Cleanup.** Released definitively when the view changes location, when the
  task closes (alongside `drop_plan`), and at service shutdown.
- **Swap, never mutate.** Rebuilds construct a new immutable projection and
  swap the reference under the task lock. A window request already holding a
  reference finishes against consistent structure instead of watching rows
  move beneath it.
- **Projection revision.** Each projection carries a monotonic process-local
  revision returned with every window response. A page request carrying a
  stale revision is refused and the client restarts, so old structure can
  never be combined with newly fetched details. **This is not the database
  generation token rejected in DR-BR-20** — it identifies an in-process cached
  object, requires no schema change, and cannot silently miss a change because
  the process performing the invalidation is the one bumping it.
- **Background views retain, up to an LRU cap.** An earlier draft said
  background views release and rebuild on return, *and* that an LRU cap bounds
  the total. Those cannot both hold: if every background view releases, the
  live count never exceeds the visible views and the cap is unreachable —
  documented as a memory safeguard while protecting nothing. Background views
  therefore retain, and the cap evicts beyond it, least-recently-used first.
  Switching among the two or three views someone is actually alternating
  between stays instant; a view untouched long enough rebuilds.

  The cap is a **count**, not a size-aware budget — predictable, no eviction
  heuristics. Size it generously (4–6): the WebView2 process tree dwarfs a few
  slim projections, so being stingy here optimizes the wrong thing. Projection
  size does scale with location size, so the scale gate records per-projection
  memory and the number is revised against that rather than re-guessed.

  Plan-tree memos (DR-BR-11) do **not** share this cap. They are keyed per
  request id, hold structure over a frozen artifact, are typically far smaller,
  and die with the task — a large location must not be able to evict one.
- **Invalidation is causal, and patches in place by copy-on-write.** A
  completed acknowledge or restore changes exactly one known row, and
  acknowledgment participates in no rollup (DR-BR-20), so no ancestor is
  affected. The service **shallow-copies** the node array — a copy of
  references, sharing every unchanged node object and the position indexes
  untouched, since nothing reorders — replaces that node, increments the
  projection revision, and swaps the reference under the task lock.

  Shallow is the operative word. Reconstructing every node object would be
  hundreds of thousands of allocations for a one-field edit; it would skip the
  query and the tree build while giving back most of the saving, and it would
  present as an unexplained stall during exactly the triage workflow the
  inventory view exists for. Rollups, where a future change does touch them,
  are adjusted by delta along the ancestor chain — never recomputed over a
  subtree, which is O(n) again regardless of copy depth.

  A projection is never mutated while a window request may still hold it. Only
  an observed session terminal, which may have changed many rows, forces a full
  rebuild.
- **Eviction is indistinguishable from invalidation, client-side.** A returning
  view rebuilds and mints a new projection revision, so a stale client revision
  is refused down the path invalidation already uses — no second mechanism.
  Eviction also cannot race an in-flight window request: projections are
  immutable and swapped by reference, so a request already holding one
  completes correctly even after the cache entry is dropped, and the client's
  *next* request takes the stale-revision refusal. The cap therefore needs no
  defensive locking of its own.

#### DR-BR-16.2 — History is paged at the database, not after it

The common window shape promises paged history, but the data path defeats it.
`HistoryRepository.get()` loads and decodes **every** retained item for a run,
and `list_recent()` calls that full method once per listed run — so rendering
a 50-run list decodes every item of all 50. Slicing afterward bounds the
bridge payload and nothing else: not the query, not memory, not decoding.

**Resolution:**

- A **summary query** first selects the requested `history_runs` rows and uses
  their persisted operation counts, which are operation-only —
  `Counter(item.outcome … if isinstance(item, ItemOutcome))` where it is
  written. Those counts still supply failed/partial/skipped outcome facts, but
  DR-BR-01's corrected `all-noop` predicate needs more: both a genuine `NOOP`
  and a user-deselected COPY settle as `SKIPPED`, so counts alone cannot tell
  them apart.

  One grouped aggregate over the typed `history_items` columns therefore
  supplies two narrow additions. First, grouped operation
  `(kind, result, reason, count)` facts let the workflow classifier reconstruct
  the effective selection by excluding rows carrying one of the stable
  `ExclusionReason` values:
  `blocked-correspondence`, `blocked-dependency`, `incomplete-scan`, or
  DR-BR-01's named `user-deselected`. The resulting selected set must be
  nonempty and every selected `kind` must be `noop`; the aggregate never
  equates `result = 'skipped'` with selection. That predicate is consumed at
  the existing headline precedence point, after failure and partial facts, so
  a failed selected `NOOP` cannot acquire an `all-noop` headline merely because
  its kind matches. Second, integrity phase/result facts supply
  `_integrity_axis` and the verify-phase-baseline check. The query never
  selects or decodes `detail_json`, constructs per-item Python objects, or
  loops over `get()`.

  The repository returns those grouped primitive facts; it does not import
  `workflows.selection.ExclusionReason` or assign a headline. `db → workflows`
  would violate the import law. Interpretation remains in `workflows`, which
  already owns selection and presentation classification, so the stable reason
  vocabulary has one semantic owner rather than being reimplemented in SQL.

  The existing `UNIQUE(run_id, item_type, item_id)` constraint gives an index
  led by `(run_id, item_type)`, so each item-type range is a seek rather than a
  full table scan. The operation range must nevertheless visit the retained
  operation items for those runs; the schema has no persisted selected-kind
  count, and inventing one inside M1 is rejected below.
- A **paged detail query** for one run's items, ordered by the immutable
  `item_order` column the schema already stores — so windows are stable and
  offsets mean something.
- **Phases load whole.** Phase count is bounded by the phases a session can
  enter, so paging them would add machinery for no benefit.
- The list's Python work and payload are bounded by the run limit. Its indexed
  aggregate database work remains proportional to the operation plus integrity
  items in those runs, so history timing joins the scale gate on runs with
  genuinely large item counts rather than only a large run count.

Persisting terminal selected-kind or integrity summary facts on `history_runs`
is **not an M1 fallback**. It would make list work proportional only to the run
limit, but it costs three things: a change to a history schema already frozen
under a contract marker, a matching change to the recording contract, and a
second source of truth that can disagree with the items it summarizes —
structurally the same defect as the mapping-filter projection this project
already removed. If the indexed query misses the gate, M1 documents the
measured supported ceiling; persisted summaries can be reconsidered only in a
later schema version with their own migration/reset decision.

### DR-BR-17 — Selection is server-side state; the DOM is disposable

Virtualization destroys and recycles rows, so selection must not live in them.
Selection is owned by the service (DR-BR-03) and every window response carries
each row's current outcome, so scrolling away and back re-reads authority.

This is the same problem as view filtering, and the same rule covers both:
**a folder deselect applies to every operation under that path regardless of
which rows are currently rendered or currently passing a filter.** Otherwise
"deselect this folder" would quietly mean different things depending on which
chip is lit, with no way for the user to tell.

Interaction is debounced: a click puts the row into an honest *pending* state
rather than an optimistic result, toggles accumulate for roughly 120–150 ms,
and the batch resolves as one revisioned mutation (DR-BR-03). Batching matters
more than the delay, since range selection and folder toggles generate many
toggles per gesture.

`preview_selection` calls `derive_execution_selection` directly and **never**
`get_plan_review` — rebuilding every operation view, both scans' warnings, and
all refusals to answer "which checkboxes changed" is the wrong shape
regardless of how fast it runs.

### DR-BR-18 — Search executes on the backend

With virtualized paging the client holds a viewport, not the plan. Client-side
search would match only materialized rows and get worse as plans grow — broken
before hostile filenames enter the discussion.

Sending a query is not a DR-M1-16 violation. That rule bans JS supplying
**paths** because a path can become filesystem authority; a query never
becomes authority, it selects rows the backend already holds. Structurally it
is a view parameter exactly like the collapsed set, so it composes with
DR-BR-15 rather than needing a parallel code path — and as a backend parameter
it stays available to a headless consumer, which a frontend implementation
would not be.

Three constraints: substring matching only (a user-supplied regex is a
denial-of-service surface for no benefit), matching against the **casefolded
display form** rather than the canonical key (the user types what is on
screen), and the existing inbound size cap.

### DR-BR-19 — Autoscroll anchors on the nearest visible ancestor-or-self

One rule removes every special case. If the current operation is visible, it
is the target; if it sits inside a collapsed folder, that folder is the target
and shows an active indicator; expanding moves the target inward; execution
moving on moves it forward. Filtering is absorbed identically, since "visible"
means after collapse and after filtering.

An ancestor chain alone is insufficient under virtualization. If the current
operation is outside the materialized window, none of its ancestors need be in
the DOM; the client could neither scroll to it nor compute the distance shown
by the follow pill.

**Resolution:** progress carries the ancestor node-id chain derived from
`item_id` (DR-BR-14), and an anchor lookup resolves that chain against the same
canonical projection and active collapse/filter/search parameters as
DR-BR-15. It returns the deepest visible ancestor-or-self, its visible-sequence
index, and the projection revision where applicable. The client can then
request the window containing that index. The lookup is presentation-only and
creates no second tree or persistent filtered projection.

The ordinary window response may carry this anchor metadata when it is already
doing the traversal; an anchor-only request serves progress that moves outside
the current window. Both paths call the same pure visible-sequence resolver so
their indices cannot disagree.

Follow mode is on by default and any user scroll that moves the target out of
view turns it off. It re-enables only on explicit action — a persistent pill
showing the distance to the current operation, one click to resume. Silently
re-grabbing the viewport when a row drifts back into view is the standard
log-viewer annoyance and is deliberately not done.

### DR-BR-20 — No inventory snapshot token

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
verify-selected resolves ids to paths server-side (DR-BR-06). The
cross-process limit is documented alongside the task rail's existing one.

**Never auto-scan.** A refresh is a real filesystem session, and periodic
rescanning would be the scheduled maintenance DR-M1-20 defers. Staleness is
reported through `list_stale_inventory`, not silently repaired.

**Acknowledgment hides, and is not counted.** The purpose of acknowledging a
missing row is to make "missing" go away, so an acknowledged row leaves the
default view rather than sitting in it wearing a badge. Acknowledgment
participates in **no folder rollup** — which is what reduces the projection
patch in DR-BR-16.1 to a single node with no ancestor walk.

Four consequences follow:

- **Hidden by default is still a filter.** "Hide acknowledged" is simply the
  inventory tree's default view parameter, applied server-side through
  DR-BR-15 like any other. It is the one filter that starts on.
- **Counts stay honest.** Because the default view is a filtered view, the
  acknowledged chip carries its own count. The hidden population is always
  visible even when its rows are not, and the missing chip reports only what
  remains missing and unacknowledged.
- **Acknowledging reflows the list.** The row leaves the visible sequence and
  everything below shifts, so acknowledge refetches its window rather than
  repainting a row in place — a different path from every other row update.
- **Restore is reached through the filter.** The workflow is filter to
  acknowledged, then restore there. This contradicts `ui_mockup/mockup.html`,
  whose context menu enables "Restore acknowledged" on an acknowledged row in
  the default listing; under this rule such a row is never in the default
  listing, and the mockup's menu logic needs revising with the rest of it.

The resulting loop is the intended one: 300 missing, acknowledge ten, they
vanish, the missing chip falls to 290 and the acknowledged chip rises to ten —
missing goes away without pretending the file came back.

---

## 5. Task and Process Lifecycle

### DR-BR-21 — A task is client state; sessions come and go beneath it

A task card outlives its sessions. It holds a plan request id, zero or one
current session id, and retained results per pane. **A task with a reviewed
but unexecuted plan has no live session at all**, so the rail cannot be
derived purely from `list_sessions()` — session-derived fields refresh from
it, but task identity is the adapter's.

**Plan sessions close as soon as their terminal result is delivered.** The
plan *artifact* lives in the runtime keyed by request id and is what
`get_plan_review` reads; the session record is only the delivery vehicle, and
leaving it open would show a permanent dead entry per task. `drop_plan`
happens at task close, not at plan-session close.

For a compound execute-then-verify run, the two phases are one session
producing one result with ordered `PhaseResultView`s. The rail summarizes the
latest phase; the Sync pane reads `phase="execute"` and the Integrity pane
reads `phase="verify"`. Phase counters are never summed (XV-7).

### DR-BR-22 — Closing a busy task cancels, waits, then closes

`Dispatcher.close` raises `SessionNotTerminal` for a live session, and
`NamiSyncService.close_session` calls it unguarded. Closing a running task is
therefore a sequence, not a call.

**Resolution:** the adapter owns the sequence, and the facade keeps its
precondition documented rather than growing a control policy.

0. **Ask first.** Closing a queued or running task requires explicit
   confirmation naming what is being stopped. A misclick — or a cat — must
   not destroy a long-running transfer, and cancellation is not free:
   the executor stops mid-plan and the user replans from the filesystem's new
   state. Closing an already-terminal card is unconfirmed, since nothing is
   lost. The confirmation is GUI-owned; the CLI does not need it, being
   already resistant to accidental input, but nothing prevents it adopting the
   same prompt.

   This is not in tension with DR-BR-03 removing the execute confirmation.
   Starting execution begins recoverable work the user can pause or cancel;
   closing a running task destroys work already in progress, and no later
   control undoes it. The prompt appears where the action is irreversible,
   which is the same rule in both places.
1. Request the service-supported control (cancel).
2. The card enters a visible **closing** state and remains on the rail.
3. **On the terminal record — not the terminal event** — unsubscribe, close
   the session, and drop the plan.

Step 3's distinction is a real race, not pedantry. `SessionObserver` delivers
the `Terminal` event to the sink and only *afterward* calls
`dispatcher.get()` to build the terminal `SessionRecordView`. A client that
drains the event and immediately calls `close_session` removes the dispatcher
record out from under that lookup, and the observer thread takes
`SessionNotFound`. Cleanup therefore triggers on receiving a
`SessionRecordView` whose `result` is not `None`, which the observer emits
once the record is safely read.

If the control is refused or unsupported, the card stays open and says why.
A transient progress flag is never treated as completion. Application
shutdown with a closing card still tears down through DR-BR-24's ordering.

### DR-BR-23 — Single instance activates the existing window

**Resolution:** a named mutex guards the process. A second launch does not
open a window; it attempts to activate the running instance's window through
Win32 and exits successfully. The codebase already uses `ctypes` Win32
bindings in the executor and verifier, so this needs no new dependency and no
IPC channel. If activation fails, the second instance prints a clear message
and exits successfully. Exiting silently, or reporting an error for what is
ordinary user behavior, are both rejected.

---

## 6. Concurrency

### DR-BR-24 — Bridge handlers are concurrent and must be synchronized

DR-M1-15 established that pywebview's exposed functions run on separate
threads. `BridgeDispatcher` correctly has no locking, because the spike's
handlers were pure. Every piece of state Stage 6 adds is not, and the runtime
is protected only for what it already owns (`_plans` is lock-guarded).

- **Selection** — owned by the service and revisioned (DR-BR-03). The
  revision is what makes ordering deterministic; a lock alone is not enough.
- **Event queue and drain tracker** — DR-M1-18's ordering guarantee rests on
  "at most one outstanding drain per task," stated as a *client* obligation.
  Two concurrent drains each pop a partial batch and events arrive out of
  order. **An ordering guarantee enforced only by client discipline is not a
  guarantee**; the server holds a per-task drain guard and a second concurrent
  drain waits or is refused explicitly.
- **Reliable queue overflow** — the bridge queue is a second bounded handoff
  after the dispatcher's already-bounded `EventStream`, so it must not invent a
  second silent-loss policy. `Progress` is replaceable: a newer snapshot
  replaces an older queued one and may be dropped when reliable data owns the
  capacity. Reliable events and terminal `SessionRecordView`s instead wait for
  bridge capacity on the observer thread. This never blocks the workflow
  producer; if the observer falls far enough behind, the existing upstream
  `EventStream` ejects it with a visible `Gap`, and the observer's established
  resubscribe/terminal-record path reconciles. The bridge does not synthesize a
  competing gap vocabulary.
- **Subscription registry** — `SessionObserver.observe` raises when a session
  is already observed, so concurrent task opens must be guarded rather than
  treated as impossible.
- **Shutdown ordering** — stop accepting dispatches, wake every outstanding
  drain **and every reliable producer waiting for bridge capacity**, close
  observations, then close the service. Wrong order hangs exit, the same
  failure XV-18 catches one layer down.

**Shape:** one `TaskState` per task holding queue, subscription, and view
state, with a single lock. **Never hold a task lock across I/O.** DR-BR-11's
deterministic ids remove what would otherwise have been a node-table lock
site, since a concurrent rebuild produces identical output.

---

## 7. Inherited Bridge Posture

Unchanged from `M1_PLAN.md` and restated only so this document is
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

## 8. Verification

### DR-BR-25 — Hostile-name rendering is proven in a real browser

An earlier draft substituted a source scan for a DOM test and conceded it did
not prove filesystem text becomes a text node. That does not satisfy
`DESKTOP_UI.md`'s acceptance requirement that hostile filenames render as
text, and it is weakest exactly where the risk is highest: the starting
mockup renders through `innerHTML` throughout, so the property being asserted
is the one most likely to regress.

**Resolution: both layers, and the DOM test is required.**

- **A WebView2 integration test** drives the real host with the scanner's
  hostile-name corpus and asserts the rendered nodes are text nodes carrying
  the exact escaped display form — not markup, not attributes, not script.
  Slice 2 cannot honestly satisfy this by inventing a test-only renderer: the
  production plan and inventory sinks do not exist yet. Slice 2 proves bridge
  round-trip and static sink restrictions; the DOM assertion lands against the
  actual plan renderer in slice 4 and is extended to the inventory renderer in
  slice 5. It stays in the suite thereafter.
- **A broadened static scan** over packaged assets, because scanning only for
  `innerHTML`, `eval`, and `Function(` misses most markup sinks. It also
  rejects `outerHTML`, `insertAdjacentHTML`, `document.write`, `srcdoc`,
  `DOMParser`, `Range.createContextualFragment`, dynamic `setAttribute` names,
  and assignment of returned data into `href`, `src`, or any `on*` attribute.

Bridge round-trip tests over the same corpus land in slice 2, covering the
ids-in / escaped-text-out and origin-recheck clauses of XV-19 without claiming
that transport alone proves a later DOM sink.

### DR-BR-26 — The node tree is a pure function

Plan review plus collapsed set plus deselected set to an ordered node list,
tested directly in pytest with no bridge involved. It is the largest new
component and must not be entangled with transport, or it becomes untestable
exactly where risk concentrates. Coverage includes a hostile-named directory
move, since grouping does segment arithmetic on canonical keys while
rendering escaped display paths and the two must stay consistent.

Because node identity now arrives in Stage 5.5 (DR-BR-11), that stage carries
its own hostile-name case: **inventory** node ids minted from hostile paths,
round-tripped through exact-row and recursive-subtree command resolution plus
foreign-location refusal. The directory-move case above belongs to slice 4 and
does not cover it.

---

## 9. Deferred, Rejected, and Open

**Rejected with reasons recorded:** the inventory snapshot token (DR-BR-20);
per-node lazy expansion in favor of flattened windows (DR-BR-15); a
minimum-size threshold and per-group sub-windows for move groups (DR-BR-13);
synthetic operation ids for structural folders (DR-BR-11); a client-side
search implementation (DR-BR-18); merging safety exclusions with user
deselection (DR-BR-01); discarding late selection responses by request id in
favor of revision conflict (DR-BR-03); path-only node ids in favor of
scope-qualified ids (DR-BR-11); row-level SQL `LIMIT`/`OFFSET` for the
inventory tree, which cannot express visible-tree semantics (DR-BR-16);
freezing selection straight to `committed`, which strands a task when
dispatcher admission fails (DR-BR-03); a typed confirmation phrase in the
desktop (DR-BR-03); and CLI acknowledge/restore/staleness commands as the
Stage 5.5 verification route, which needed a larger interface design than the
lift they were meant to prove (§10); client-side view filtering, which filters
a window rather than windowing a filter (DR-BR-08); releasing every background
inventory projection, which made the LRU cap unreachable (DR-BR-16.1);
deep-copying a projection to patch one row (DR-BR-16.1); and a `cli → web`
import for no-subcommand launch, replaced by a launcher module (§10);
reconstructing user-selection reasons from the final selected-id set
(DR-BR-01); exact-path semantics for a folder-node location command
(DR-BR-06); a client-only autoscroll anchor that cannot locate an
unmaterialized row (DR-BR-19); and a second bridge-specific reliable-loss
policy instead of the dispatcher's existing visible `Gap` path (DR-BR-24).

**Deferred:** filter-exclusion visibility in plan review (DR-BR-07);
`get_plan_review` rebuilding every view object per call, which the memoized
tree and direct `preview_selection` path route around rather than fix; and
persisted selected-kind/integrity summary columns on `history_runs`, which
require a later schema-version decision rather than an M1 fallback
(DR-BR-16.2).

**Open:** none. DR-BR-15 settles the former move-ghost filter question: when a
filter hides the ghost, its synthetic-only ancestor chain disappears with it.

---

## 10. Delivery

### Packaging

`pywebview` is a normal runtime dependency, not an optional extra. NamiSync is
a headed Windows product, so a standard installation includes the desktop host
and no-subcommand `nami-sync` launches it. Explicit CLI subcommands remain
headless at runtime: they do not import or initialize `pywebview`, and GUI
imports stay quarantined under `interfaces/web`.

This packaging decision does not accept a renderer fallback. Slice 0 pins the
supported pywebview version range after proving Python 3.13 compatibility and
the required bridge behavior. Slice 1 refuses a missing or incompatible
WebView2 runtime with an actionable error rather than falling back to MSHTML.
Moving the host to an optional extra remains possible later, but is not an M1
distribution mode.

**No-subcommand launch needs a launcher module.** The console script is
`namisync.interfaces.cli:main`, and DR-M1-01 forbids the edge this would
create: "`cli` and `web` do not import each other; both import `service`;
`service` imports neither," encoded as an import-linter layers contract with
`cli` and `web` as independent siblings. Dispatching to the desktop from
`cli.main` is exactly that forbidden import, and it would surface as a linter
failure during slice 1 rather than as a design choice.

`nami-sync` therefore points at a small launcher that is **neither adapter**:
it inspects argv and dispatches to the CLI or the web host, with the contract
extended to permit `launcher → {cli, web}` while `cli ↮ web` stands. That
also makes the headless claim true by construction: the launcher decides
before either side is imported, so an explicit CLI subcommand never pays
pywebview's import cost. Lazy imports inside `cli.main` would achieve the
same runtime effect while still violating the contract.

### Stage 5.5

DR-BR-01 through DR-BR-07 plus the minimum node-identity substrate required by
DR-BR-06 move here: **the hierarchy core** of DR-BR-09's shared tree builder —
ancestor synthesis, deterministic ids, ordering, subtree membership, rollups —
DR-BR-10's path helper promotion, DR-BR-11's location-scoped deterministic ids,
the slim inventory structure lookup needed to resolve them, the recursive
selected-subtree scan/recorder scope, and the `ExecutionSet`/payload extension
that retains canonical user-deselection provenance.

The builder's plan-presentation layers stay in Stage 6 slice 4: move grouping,
ghost annotation, and nested-move suppression (DR-BR-13) are plan tree
concerns, and Stage 5.5 needs none of them to resolve an inventory node id.
This is **verified through facade-level tests rather than new CLI surface**:
user selection, the revision protocol and three-state commitment, the
service/runtime ownership boundary, destructive-risk computation, replan
discard, deterministic node rebuilding, foreign-location id refusal, and
node/row id location commands, all proven against `NamiSyncService` directly.
Contract tests additionally prove:

- strict workflow payload v4 round-trips user deselection through pause/resume
  and rejects v3; direct choices settle `SKIPPED`, and dependency fallout
  settles `DEFERRED`;
- an empty user selection is refused while a genuine nonempty `NOOP`-only
  selection executes, records, and classifies `all-noop` from selected kinds
  rather than from `Outcome.SKIPPED` alone;
- the CLI's omitted revision is accepted only for untouched default selection;
- a nested folder refresh discovers a descendant absent from the prior
  inventory, marks disappeared `present` and `unsupported` descendants
  missing, and leaves absent rows outside the subtree untouched; incomplete
  subtree scans infer no missing rows, a genuinely absent root is complete and
  marks its indexed subtree missing, `%`/`_`/`]` hostile roots remain literal,
  overlapping roots canonicalize by segment ancestry, and selecting the
  location root takes the full-scan branch; a mixed row/folder refresh retains
  the exact row outside the subtree without recursively expanding an exact
  directory row; folder-scoped
  baseline/verify/rebaseline freeze every indexed descendant even when a view
  filter hides some of them, inventory workflow payload v2 round-trips the
  subtree roots and rejects v1 through the shared kind-aware validator while
  integrity v1 remains accepted, the representative subtree reconciliation
  query proves an indexed range search, and empty-id and foreign-location
  requests are refused.

Stage 5.5 establishes identity and server-side resolution, not desktop
presentation or per-view caching. Stage 6 consumes the same tree/index
structure for flattening, paging, selection controls, and DR-BR-16's cached
inventory projection rather than introducing a second node-id implementation.

Two earlier claims were wrong and are corrected here. All of Stage 5.5 is not
"provable through the CLI" — the CLI commits the automatic selection directly
and has no selection surface at all. And the proposed CLI acknowledge, restore,
and stale-inventory commands were named without a command contract: both
mutations need a location and a row id, but the CLI's inventory listing prints
only presence and path, so the required identifier is undiscoverable from its
own output. Specifying them properly means command names, arguments, an
identifier the listing actually exposes, idempotency ids, and cutoff semantics
for staleness — a larger change than the lift it was meant to verify.

Dropping the CLI additions is therefore the smaller Stage 5.5. A CLI surface
for acknowledge, restore, and staleness can be designed on its own merits
later, driven by headless demand rather than by a need to test a facade
passthrough.

### Stage 6

| # | Slice | Gate |
| --- | --- | --- |
| 0 | pywebview reality spike | Supported version range on Python 3.13; `CoreWebView2` reachability, pythonnet handler syntax, asset-server origin at runtime, off-thread `current_url` |
| 1 | Promote the spike into `bridge.py` / `host.py`; hard dependency; packaged assets; entry point; forced Edge Chromium; single instance | Window opens on real WebView2, guards attached, missing/incompatible WebView2 is refused, off-origin dispatch rejected, second launch activates the first |
| 2 | Command allowlist, JSON encoding, opaque-id and folder-picker slots | Every view type round-trips; DR-BR-25's hostile corpus crosses the real bridge as escaped data, origin is rechecked, and the broadened static sink scan passes |
| 3 | Event drain with coalescing, bounded wait, reliable backpressure, gap visibility, server-side drain guard | XV-18 plus concurrent-drain ordering; a reliable flood beyond bridge capacity reaches the existing visible `Gap`/resubscribe path, terminal truth is recovered, and shutdown wakes blocked drains and producers |
| 4 | Plan-tree presentation, paging, selection, indexed autoscroll; vertical sync slice end to end | A desktop sync consumes the Stage 5.5 node ids and produces the same facade calls and classification as the CLI; additive Progress compatibility and identity-pair validation pass; an off-window progress item resolves to the correct visible index under collapse/filter/search; the production plan DOM passes DR-BR-25; plan portions of DR-BR-16's scale gate recorded |
| 5 | Cached inventory projection and integrity views, five resolution states, recursive folder context actions, per-window detail query | XV-14 states render distinctly; row-id exact scope and folder-id recursive scope work end to end; the inventory DOM extension passes DR-BR-25; inventory portions of DR-BR-16's scale gate recorded |
| 6 | History, settings, `ui-state.json`, task close sequence, clean shutdown | Four truth axes and the corrected retained `all-noop` classification are visible without string parsing; closing a busy task cancels and waits; history portions of DR-BR-16's large-operation-count scale gate are recorded |
| 7 | Documentation: rewrite `DESKTOP_UI.md` acceptance to as-built, README, re-status `ui_mockup/` | — |

Slice 0 shares nothing with Stage 5.5 and may run in parallel. It should run
**before** the Stage 6 sections here are treated as settled — four decisions
rest on assumptions no code has verified against a real runtime.
