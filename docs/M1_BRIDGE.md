# M1 Bridge and Presentation Contract

**Standing.** This document is the normative authority for the M1 bridge seam:
facade-to-frontend envelopes, command and revision contracts, event/terminal
semantics, presentation data ownership, and the BR-G acceptance gates.
`DEFENSE.md`, `FEATURES.md`, and `ARCHITECTURE.md` outrank it for defense,
product behavior, and cross-system architecture. `M1_PLAN.md` owns milestone
decisions; `M1_SHELL.md` owns host/package sequencing and SH-G gates; and
`DESKTOP_UI.md` owns the user-facing visual contract.

**Scope.** Sections 1–8 state bridge decisions and contracts. Section 9 records
only deferred, rejected, and resolved dispositions. Section 10 retains the
normative BR-G gate register and the remaining M1 delivery order; a lane or
slice closes only when all applicable gates and regressions pass. Dated build
status and evidence are recorded under [M1 GUI in the changelog](../CHANGELOG.md#m1-gui).

---

## 0. Goals

Stated first because everything below is a means to one of them, and because a
decision that serves none of them is a decision to cut.

### Product goals

1. **A reviewer can see what is about to happen, at any plan size.** A directory
   rename that decomposes into ten thousand moves must stay reviewable, not
   merely renderable. This is what the node tree, move annotation, and paging
   exist for.
2. **A reviewer can change what is about to happen, precisely.** Deselection is
   dependency-correct, folder-scoped where the user thinks in folders, and never
   silently readmits something the planner refused.
3. **The interface never claims more than the backend observed.** Four truth
   axes stay separable on screen; an incomplete refresh reads as incomplete
   rather than as a clean one; a count that cannot be computed honestly is not
   shown.
4. **Hostile filesystem content is inert and layout-honest on screen.** A
   filename remains raw display data through authority and search, becomes
   visible-marker text for defended layout controls only at its final sink,
   and is never markup, a command argument, or an executable string.
5. **Nothing irreversible happens by accident, and nothing reversible is made
   annoying.** Friction is placed where an action cannot be undone, and
   deliberately withheld everywhere else.

### Engineering goals

1. **Headless authority.** Every authoritative capability the desktop uses is
   reachable at or below `interfaces/service.py`, so a test or a second Python
   adapter can drive it without a browser, and nothing that *decides* anything
   runs in the browser. DR-BR-09 deliberately places the
   flatten/window/search/anchor mechanics in `interfaces/web`: they are
   presentation-only, are tested headlessly at that boundary, and need not be
   reachable through the CLI. What must never be true is a *domain decision*
   the backend cannot make on its own.
2. **The import law survives a second interface.** Nothing in this work
   introduces an upward or sideways import, reconstructs domain structure from
   display strings, or moves path arithmetic above `workflows/`.
3. **One implementation per concept.** Two trees share one builder, two window
   consumers share one flattener, two payload kinds share one validator, plan
   and inventory share one node-identity scheme.
4. **Retry identity and view guards are command-specific.** Every receipted
   bridge gesture is safe to retry under one `command_id`. A command formed
   against a revisioned server view also carries that view's revision and
   refuses stale intent; session creation does not invent a revision, and the
   native folder picker carries neither identity.
5. **Bounded repeated work, not just bounded payloads.** A window request bounds
   its detail query, decode, and per-row allocation. The deliberately
   whole-structure inventory projection and retained-history aggregate are
   separately measured, cached or indexed as specified by DR-BR-16, and paid at
   their stated lifecycle rather than once per viewport scroll. Every supported
   ceiling has recorded time and memory numbers.
6. **No new dormant seams.** A contract lands with its first consumer, matching
   `M1_PLAN.md`'s standing rule. The only inherited exception is a version/schema
   reservation that avoids a second incompatible bump; no Stage 6 cache,
   projection, or presentation helper lands early merely to make Stage 5.5 look
   complete.

### Non-goals

Durable plan/session persistence, cross-process task visibility, history
retention, observer thread multiplexing, and concurrent file execution all
remain deferred exactly as `M1_PLAN.md` §4 leaves them. This document adds
none of them and depends on none of them.

---

## Map of this document

This table is the navigation index. Each decision appears once under the module
or layer it binds; the linked section contains the normative rule.

| Decision | Binds | Ruling |
| --- | --- | --- |
| [DR-BR-01](#dr-br-01--user-selection-enters-the-facade-as-a-separate-set) | Selection workflow/service | Keep user deselection distinct from safety exclusions and retain its execution provenance. |
| [DR-BR-02](#dr-br-02--reselection-closes-upward-over-the-user-set-only) | Selection workflow | Reselection closes dependencies only within the user-deselected set. |
| [DR-BR-03](#dr-br-03--selection-is-revisioned-and-commitment-freezes-it) | Service selection state | Revision selection and freeze it through reviewing, committing, and committed states. |
| [DR-BR-04](#dr-br-04--deselection-does-not-survive-a-replan) | Selection workflow/service | Replan clears deselection, advances the revision epoch, and retains retry tombstones. |
| [DR-BR-05](#dr-br-05--four-runtime-methods-reach-the-facade) | Service facade | Lift the four inventory acknowledgment/staleness reads as typed passthroughs. |
| [DR-BR-06](#dr-br-06--location-commands-accept-opaque-ids) | Service, scanner, recorder | Resolve opaque row/folder ids server-side; folder refresh uses recursive subtree scope. |
| [DR-BR-07](#dr-br-07--scanner-ignore-contract-narrowed) | Scanner | Remove unused ignore snapshots while retaining the known filter-visibility gap. |
| [DR-BR-08](#dr-br-08--the-ui-never-computes-means-authority) | Cross-cutting UI | Keep decisions authoritative on the backend while permitting cosmetic client computation. |
| [DR-BR-09](#dr-br-09--node-trees-are-built-in-workflows-not-interfaces) | Workflow node tree | Build shared hierarchy in workflows, below presentation adapters. |
| [DR-BR-10](#dr-br-10--path-helpers-promote-to-corepathingpy) | Core pathing | Promote shared lexical path helpers unchanged into core. |
| [DR-BR-11](#dr-br-11--node-identity-is-deterministic-and-the-plan-tree-is-memoized) | Workflow node tree | Scope deterministic node ids and memoize immutable plan trees. |
| [DR-BR-12](#dr-br-12--folder-selection-is-path-scoped-and-the-tree-owns-the-scope) | Workflow node tree/selection | Derive folder selection and subtree membership from the same index. |
| [DR-BR-13](#dr-br-13--decomposed-moves-render-as-a-paired-annotation) | Plan presentation | Render decomposed moves as paired annotations, not new selection units. |
| [DR-BR-14](#dr-br-14--progress-carries-item-identity-never-a-display-path) | Core events/reporters | Carry item identity in progress; never join authority on display paths. |
| [DR-BR-15](#dr-br-15--flattened-windows-over-a-stateless-visible-sequence) | Presentation views/web | Derive one server-side visible sequence and return bounded windows. |
| [DR-BR-16](#dr-br-16--paging-bounds-payload-and-must-also-bound-work) | Views, service, database | Bound repeated work with plan memos, inventory projections, and database history pages. |
| [DR-BR-16.1](#dr-br-161--the-inventory-projections-lifecycle) | Service projection cache | Own immutable revisioned projections by opaque view id under a six-entry LRU. |
| [DR-BR-16.2](#dr-br-162--history-is-paged-at-the-database-not-after-it) | Database/history views | Keyset-page bounded history and capture committed traversal watermarks. |
| [DR-BR-17](#dr-br-17--selection-is-server-side-state-the-dom-is-disposable) | Service/web selection | Treat DOM rows as disposable views of server-owned selection. |
| [DR-BR-18](#dr-br-18--search-executes-on-the-backend) | Presentation views | Execute literal search with the server-side view parameters. |
| [DR-BR-19](#dr-br-19--autoscroll-anchors-on-the-nearest-visible-ancestor-or-self) | Presentation views | Resolve follow mode to the nearest visible ancestor-or-self. |
| [DR-BR-20](#dr-br-20--no-inventory-snapshot-token) | Inventory presentation | Re-read at causal boundaries; acknowledgment hides rows without changing counts. |
| [DR-BR-21](#dr-br-21--a-task-is-client-state-sessions-come-and-go-beneath-it) | Web task lifecycle | Let adapter task state outlive the sessions beneath it. |
| [DR-BR-22](#dr-br-22--closing-a-busy-task-cancels-waits-then-closes) | Web task lifecycle | Cancel, await durable terminal truth, then unsubscribe and release. |
| [DR-BR-23](#dr-br-23--single-instance-activates-the-existing-window) | Desktop host | Activate the existing window instead of starting a second instance. |
| [DR-BR-24](#dr-br-24--bridge-handlers-are-concurrent-and-must-be-synchronized) | Web concurrency | Synchronize shared bridge state without holding adapter locks across facade I/O. |
| [DR-BR-25](#dr-br-25--hostile-name-rendering-is-proven-in-a-real-browser) | Browser verification | Prove hostile-name sinks in installed WebView2 plus static scans. |
| [DR-BR-26](#dr-br-26--the-node-tree-is-a-pure-function) | Workflow node tree/tests | Keep hierarchy construction pure and headlessly testable. |
| [DR-BR-27](#dr-br-27--receipted-commands-are-idempotent-revisioned-view-mutations-are-guarded) | Service/web commands | Assign retry receipts and view-revision guards per command. |
| [DR-BR-28](#dr-br-28--cosmetic-persistence-crosses-one-typed-section-channel) | Interface UI state/web commands | Freeze one section-versioned cosmetic channel without admitting semantic or session state. |

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
- Every selection mutation supplies the **expected revision**. On match, the server
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

**`committing` always resolves.** The transition to `committed` or back to
`reviewing` sits in a `finally`, and *any* escaping exception takes the failure
branch. A state that can be left occupied by an unexpected error is a task that
can never be executed again and never says why — and `Dispatcher.submit` fails
by raising, so this is the ordinary path, not a defensive one.

A concurrent Execute observing `committing` must not create a second session —
it is a duplicate of work already in flight, not a new request. A double-click
therefore produces exactly one session. **The second caller is told so**: it
receives a named in-flight response, distinct from both a revision conflict and
an error, which the client renders as "already starting" rather than as a
failure. "Exactly one session exists" is only half a contract; the other half is
what the loser of the race sees.

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
([`runtime._update`](../namisync/modules/executor/runtime.py) guards the trash
step on that flag). **`MOVE_UPDATE` does not count**: `_move_update` publishes to the
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
forces re-review; any mutative refresh of a plan discards its selection while
advancing the request's revision monotonically. The service retains recognized
mutation command ids as retry tombstones across replacement: a lost-response
retry returns `NOOP` against the new empty selection rather than reapplying old
intent. A new command carrying the old revision conflicts, including an Execute
or destructive acknowledgement formed against the superseded artifact. The UI
states that the selection was reset because the plan changed. Required coverage
asserts the discard, monotonic revision, retry behavior, and mutation/replan
race rather than trusting presentation.

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

**Binding rule.** Desktop location commands send opaque row or folder-node ids,
never paths. The service resolves and validates every id against the named
location, refuses foreign or empty id sets, and unions duplicate subjects before
constructing one workflow request. The CLI path form remains exact-path scope;
recursive CLI scope is not inferred.

#### Command and scope contract

- A row id denotes exactly one inventory subject. A folder-node id denotes that
  folder and its complete indexed subtree, independent of the current view
  filter.
- Integrity commands freeze the folder's currently indexed eligible rows into
  exact subjects before admission. An unreadable frozen subject yields one
  visible `unsupported` result and makes verification incomplete while other
  readable subjects continue. Root/location failure, cancellation, or
  incompleteness not attributable to a frozen subject still refuses before
  hashing.
- Folder actions and row actions have distinct labels. No pre-admission
  descendant count is shown because baseline, verify, and rebaseline select
  different eligible subsets. These pausable, cancelable operations require no
  confirmation dialog; admitted progress reports the actual count.
- Folder refresh uses `ScanScopeKind.SUBTREES` so new descendants are
  discoverable. A mixed refresh carries both `selected_paths` and
  `subtree_roots` in one session.
- Scope normalization is segment-aware: overlapping roots reduce to minimal
  roots; exact paths beneath a root are redundant; exact paths outside roots
  remain exact; an exact directory-row id does not become recursive; and the
  location's empty root canonicalizes the whole request to `FULL`.
- The invariants are exact: `FULL` carries neither scoped field; `PATHS`
  carries nonempty exact paths and no roots; `SUBTREES` carries at least one
  root and may carry exact paths. Only an explicit full request or the location
  root may normalize to `FULL`.

#### Scan and reconciliation contract

Recursive scope is the full-walk algorithm bounded to roots, not a generalized
exact-path scan. It shares the full-walk helper and therefore inherits every
present and future full-walk incompleteness cause. The helper accepts an
`(absolute_path, relative_prefix)` start, probes the root kind, distinguishes
conclusive absence from `ROOT_UNAVAILABLE`, names the failing relative root,
and shares one visited-directory identity set across all requested roots.

A missing root and a former folder now observed as a file are conclusive; prior
descendants may become missing. A file placeholder or file reparse point is a
conclusive unsupported subject. A directory placeholder, directory reparse
point, repeated directory identity, denial, enumeration/stat/type failure,
case collision, or another inherited full-walk uncertainty makes the combined
scan incomplete and withholds all missing inference.

After a complete scan, the recorder handles all three scope kinds explicitly:

- `FULL` reconciles the full location.
- `PATHS` retains exact-key reconciliation.
- `SUBTREES` reconciles the union of remaining exact paths plus every root and
  descendant, considering prior `present` and `unsupported` rows.

Rows outside that union are untouched. Subtree descendants use the indexed,
wildcard-free binary range below, with equality to `:root` tested separately:

```sql
rel_path_key >= :root || '\'
AND rel_path_key < :root || ']'
```

`LIKE` is forbidden because `%` and `_` are legal filename characters.
`inventory_location_presence_idx(location_id, presence, rel_path_key)` must
serve the range; BR-G-27 pins the query plan.

#### Evidence and payload contract

`InventoryDetails` retains typed scan warnings and
`InventoryDetailsView` exposes primitives-only code/path/detail beside
`complete`. Stage 5.5 proves the evidence reaches the facade; Slice 6 must
render incomplete scope and its reason distinctly from a clean refresh.

Inventory workflow payload v2 carries subtree roots separately from exact
paths and rejects v1. Integrity payload remains v1 because its folder scope is
frozen into existing exact subjects. The shared decoder accepts explicit
`(expected_kind, expected_version)` and rejects wrong-kind or wrong-version
bodies.

Integrity continuation restructuring remains deferred until a late-run pause
benchmark over representative 10k, 100k, and large-folder subject sets proves a
problem. Any replacement must preserve paused/unpaused result and phase truth;
a nested payload alone is not accepted as bounded work.

> **Rationale (non-normative).**
>
> Opaque ids keep paths and subtree interpretation out of JavaScript. Folder
> integrity continues past subject-local unreadability because expansion turns a
> handful of explicit paths into tens of thousands of frozen subjects, while
> non-subject uncertainty still invalidates the whole scope. Refresh cannot
> expand only indexed rows because that would miss newly created descendants.
> The recursive walk shares full-scan completeness so ordinary ignored files do
> not make real subtrees permanently inconclusive, and the literal range avoids
> hostile-name wildcard bugs. Predicted folder counts and the withdrawn nested
> continuation draft were rejected because neither matched workflow-owned
> eligibility nor demonstrated bounded work.

Landed behavior is recorded under
[Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30).

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
| `workflows/node_tree.py` | ancestor synthesis, node ids, subtree op sets, rollups, id->path lookup; emits the ordered depth/parent-indexed array interfaces flatten |
| `workflows/views.py` | `PlanNodeView`, `InventoryNodeView`, preview projection |
| `workflows/runtime.py` | construct committed requests from authoritative `user_deselected`; no revision or client digest |
| `interfaces/service.py` | selection state/revision and commit transition, `view_id` minting and projection ownership, the four lifts, revision-guarded id-based location commands, tree passthroughs |
| `interfaces/web` | bridge, host, command allowlist, task state and locks, bounded event queue, JSON encoding, collapse/filter/search flattening, windowing, autoscroll lookup |

`interfaces/web` remains the largest new surface by volume, but after this
split it holds no domain-shaped computation — transport and presentation
mechanics only.

**Why flattening is legal above `workflows` when grouping is not.** The two
look similar and are not. Grouping needs `normalize_relative_path` and Windows
case semantics; flattening needs neither, *provided the tree hands up a
structure that has already done the path work*. `workflows/node_tree.py`
therefore emits an **ordered, depth-annotated, parent-indexed array** —
pre-order position, depth, parent index, and subtree extent per node — so
collapse is an index skip, filtering is a predicate over supplied fields, and
search is a casefolded substring test against a display string the workflow
already escaped. None of that re-derives hierarchy from text, which is the
actual prohibition. If a presentation task ever needs a parent, a depth, or a
descendant set that the array does not carry, that is the signal it belongs
below the boundary, not that the boundary should move.

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
Stage 6 slice 5. Same rule, two arrival times.

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
than inventing a parallel one. It also gains optional `item_bytes_done` and
`item_bytes_total` for the active byte-stream attempt. Both reporters already
hold the identity and stream counters: the executor knows its current
operation and copy stream, and the verifier knows its current subject and read
stream.

The fields are optional **as a pair**: legacy producers omit both; an
identified progress event supplies a nonempty `item_id` plus `item_type` equal
to `operation` or `integrity`. `Progress.__post_init__` rejects a one-sided
pair or an unknown type, so the bridge never guesses which node-id namespace
an opaque id belongs to.

The byte fields are likewise optional as a pair. They require item identity,
use exact nonnegative integers, and reject `done > total`. Identity may exist
without byte counters while an item is active but has not entered a meaningful
stream; non-byte operations remain indeterminate. Item counters describe the
current stream attempt and may restart from zero, while aggregate executor
bytes retain their monotonic high-water semantics. A settled item is named by
its reliable outcome, not by later lossy progress: later snapshots clear the
item identity and item-byte fields. `current_path` retains its prior
display-only behavior.

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
required Progress fields, the decoder reads all four optional item fields
with `raw.get(...)`, not strict subscripts. And
explicit compatibility tests assert both directions — a pre-change payload
deserializes, and a post-change envelope serializes with the fields present —
because an additive claim is only true if something proves it. A third test
rejects invalid identity/counter pairs and coercive item counters.

Absent those tests the change requires a version bump instead. What is not
acceptable is changing the body while asserting the version is unaffected
because nothing writes it to disk.

The remaining footprint is bounded: four dataclass fields, two reporters that
already own the relevant stream, and the exact serializer/browser consumers.

The bridge enriches `item_id` into an ancestor node-id chain. **Never join on
`current_path`**, which remains display-only telemetry.

### DR-BR-15 — Flattened windows over a stateless visible sequence

**Binding rule.** The server derives one ordered visible sequence from the
canonical tree projection plus collapsed ids, literal search, and domain-owned
filters. Clients request exact `[offset, limit]` windows; the DOM never owns or
reconstructs the hierarchy.

#### Sequence contract

- Plan and inventory use the same pure flatten/window shape. One canonical
  projection exists per open view; changing view parameters replaces the
  derived sequence rather than retaining a parameter-keyed cache family.
- A folder is visible only when it matches directly or retains a visible
  descendant. Synthetic-only ancestor chains disappear with the annotation they
  hosted. Folder rollups describe the unfiltered folder, while filter chips
  describe the current view.
- A visible container with a retained child reports `expanded=true|false`; a
  leaf, empty root, or direct match with all descendants filtered reports
  `expanded=null` and exposes no disclosure.
- Offset is an exact nonnegative integer and limit is an exact integer from
  1 through 256. Refuse oversize or invalid requests; never return silent
  truncation that looks complete.
- `interfaces/web/visible_sequence.py` remains tree-agnostic and pure. It may
  retain source/visible indexes and accessibility metadata for one derivation,
  but no path authority, domain filter vocabulary, projection lifecycle, or
  active-view cache.
- Search is literal, case-folded display matching. The first Slice 5/6 request
  owner applies a fixed 150 ms trailing debounce, advances generation on every
  search/collapse/filter intent, sends only the final burst value, and ignores
  stale success or failure while leaving the current valid window visible.

#### Renderer contract

The installed renderer uses fixed 28-pixel rows, two spacers, and one tab stop.
Its only data callback is `requestIndex(index, generation)`; the Slice 5/6
owner fetches a window containing that index and commits it under the supplied
generation. Parameter changes call `beginWindowRequest`; a callback does not
mint a second generation.

Passive scroll and one per-tree `ResizeObserver` coalesce into one animation-
frame reconciliation. Missing leading or trailing spacer indexes are requested
once; covered ranges request nothing. Scroll commits preserve `scrollTop` and
reject stale generations before reading payloads. A newer user scroll invalidates
older keyboard or different-index requests, while repeated requests for the same
missing index are suppressed. An unchanged viewport does not autonomously page
again after a valid narrow response.

Before removing a root, its owner calls idempotent `dispose()`, which disconnects
the observer, removes controller-owned listeners, invalidates pending work, and
makes queued frames and later commits inert. Pointer disclosure focuses the row
and requests expansion without triggering row activation; projected terminal
nodes remain inert.

#### Text contract

Workflow nodes, derived sequences, wire windows, and literal search preserve
exact valid Unicode. Only the renderer maps the fixed active layout controls
and marker delimiters from `DEFENSE.md` to visible `⟦U+XXXX⟧` text.
That spelling is not decoded by search and creates no second wire shape. The
bridge bounds the complete serialized request at 65,536 UTF-8 bytes; the pure
helper's search input may not exceed that bound.

> **Rationale (non-normative).**
>
> Per-node lazy expansion was rejected because review defaults expanded and
> would pay one round trip per folder. Row-level windows give scroll a stable
> index and keep payloads bounded. Filtering empty ancestors prevents a skeletal
> tree, unfiltered rollups keep selection meaning stable, and fixed height avoids
> measurement-dependent window geometry. Last-request-wins plus explicit
> disposal prevents stale responses or viewport feedback loops from creating
> authority in JavaScript.

The landed presentation-core realignment and its browser evidence are recorded
under [Complete and harden the accessible desktop foundation](../CHANGELOG.md#complete-and-harden-the-accessible-desktop-foundation-2026-08-12--2026-08-18).

### DR-BR-16 — Paging bounds payload, and must also bound work

**Binding rule.** Windowing must bound repeated query, decode, allocation, and
serialization work, not only response bytes.

- Immutable plan trees are memoized per request id.
- Inventory uses one slim all-row structure query per projection and fetches
  full snapshots only for the visible window's row ids.
- History summaries and details page in the database under DR-BR-16.2.
- Flattening remains per-request work. If BR-G-42 demonstrates a need, one
  latest visible-sequence value may be retained per open view and replaced on
  any parameter change; a parameter-keyed cache family is forbidden.
- `preview_selection` retains its
  O(operations × dependency depth) fixpoint and is measured at the declared
  depth under BR-G-42.
- BR-G-42 owns the fixed M1 scale fixtures, reference profile, budgets, and
  evidence tier. Measurements may pass or fail that contract but may not
  redefine it after observation.

Row-level SQL `LIMIT/OFFSET` is not inventory-tree paging: ancestor synthesis
and rollups require the structure, client offsets address the post-filter
visible sequence, and lexical key order is not depth-first pre-order.

#### DR-BR-16.1 — The inventory projection's lifecycle

**Binding rule.** Inventory projections are immutable, revisioned, service-owned
objects identified by opaque `view_id`.

- The service mints `view_id`; the adapter maps its own
  `(task_id, location_id)` to that id. Opening one location in two tasks creates
  independent projections without importing adapter task identity into the
  service.
- A view change, task-owned facade-artifact release, or service shutdown releases
  the projection. Background views remain cached under a six-live-projection
  least-recently-used cap. Plan-tree memos do not share this cap.
- Rebuilds happen outside the service guard and swap immutable references inside
  it. The LRU map and each per-view read-modify-write patch use that same
  service-side synchronization. The adapter `TaskState` lock guards adapter
  state only and is never held across facade I/O.
- Every projection has a monotonic process-local revision returned with its
  windows. A stale revision is refused so structure and detail from different
  generations cannot combine. This is an in-process projection revision, not
  the rejected database snapshot token of DR-BR-20.
- Acknowledge/restore uses pure
  `patch_row(projection, row_id, ...) -> projection` in
  `workflows/node_tree.py`. It shallow-copies the node array, shares unchanged
  nodes and indexes, replaces the one workflow-constructed node, bumps revision,
  and stores atomically. Concurrent patches cannot lose one another; a patch
  against an obsolete base is dropped.
- A session terminal that may affect many rows forces a full rebuild. Rollup
  changes, if later introduced, update only the ancestor chain.
- Eviction and causal invalidation share the stale-revision path. An in-flight
  request may finish against its immutable reference; the next request rebuilds
  or refuses stale state.

#### DR-BR-16.2 — History is paged at the database, not after it

**Binding rule.** History reads never materialize unbounded run detail before
windowing.

- `list_summaries(limit)` uses a run query plus fixed phase/aggregate queries
  and never decodes canonical event JSON. The database returns finite
  conditional facts; workflows own selection, integrity, and headline meaning.
- `get_item_page` keyset-pages dense immutable `item_order`;
  `get_event_page` keyset-pages reliable `event_seq`. Both accept limits
  1..256, fetch one raw lookahead row, and decode at most the requested limit.
- The first page captures a committed `through_*` watermark in the same read
  transaction. Later pages reuse it while new history commits. Event watermarks
  are inclusive sparse bounds and need not name a retained row.
- A fresh recovery traversal whose last accepted non-`Gap` cursor is already
  ahead of durability returns one empty terminal page. A later repair omits the
  old watermark and captures a new committed prefix; a reversed fixed interval
  is invalid.
- Terminal phase summaries have a 256-row recording ceiling and may load with a
  summary. Item and event detail may not.
- The service exposes summary, item-page, and event-page methods; CLI detail
  consumes those pages. `history_events_run_item_order_idx`, the composite
  primary key, and `history_events_run_item_aggregate_idx` serve the bounded
  seeks, pinned by query-plan regressions.
- Reset-only history v4 introduced this contract and receipt-aware v5 retains
  it. Durable reliable pages repair live gaps; lossy progress gaps remain valid,
  and finalized summaries supply terminal truth.

> **Rationale (non-normative).**
>
> The rejected row-page draft bounded SQL rows but could not construct correct
> tree ancestry, rollups, or visible ordering. Service-owned `view_id` avoids
> keying service state by adapter-owned task identity. Background retention makes
> the LRU meaningful; immutable swaps let active readers finish consistently;
> and shallow copy-on-write prevents a one-row acknowledgment from rebuilding
> hundreds of thousands of nodes. History keyset pages eliminate the former N+1
> full-run materialization without weakening durable gap recovery.

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

Four constraints: substring matching only (a user-supplied regex is a
denial-of-service surface for no benefit), matching against the **casefolded
raw display form** rather than the canonical key, no marker decoding or other
query syntax, no trimming or Unicode normalization, and an exact 65,536-UTF-8-byte
query ceiling. The pure presentation seam accepts 65,536 UTF-8 bytes
and refuses 65,537 before walking the node array. The existing 65,536-byte
complete inbound-envelope cap remains the external authority, so JSON overhead
makes an actual bridge query smaller; future non-bridge adapters impose their
own whole-request bound. Responsiveness comes from the 150 ms trailing debounce
and last-intent-wins generation rule in DR-BR-15, not a tiny field limit.

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
`item_id` (DR-BR-14), ordered deepest node first through the root, and an
anchor lookup resolves that chain against the same
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

`SessionRecordView.state` and `StateChanged` already carry the core `pausing`
value; Stage 6 must render it as **Pausing…**, not collapse it into `running` or
prematurely show `paused`. Durable executor retries can remain in that state
while one already-staged operation settles. Repeat pause/resume controls are
disabled during the drain, cancellation remains available, and either `paused`
or a legal terminal state may follow. This is presentation of an existing
bridge value, not a payload/schema addition.

**Terminal delivery releases session authority, not the reviewed task.** Until
the terminal record has been presented successfully, the task retains the
dispatcher record, replay, observation recovery source, and service command
receipt so a lost bridge response remains recoverable without another response
cache or acknowledgment. The browser then calls
`release_terminal_session`, which unsubscribes and closes that dispatcher
session while retaining the task id, request id, start receipt, presentation
state, capacity slot, and plan artifact. Only an explicit `close_task` drops the
plan and removes the adapter task.

The full terminal result is not ordinary transport custody. One completion can
simultaneously exist as a core `Terminal(OperationResult)`, its adapter event
view, the terminal `SessionRecordView`, the serialized response, and a browser
retry/presentation value. BR-G-45 owns that complete artifact set and the
aggregate policy for completed tasks. Until production enforces that policy and
its checked maxima prove an analytical bound for every enforceable term over the
complete admitted domain, with separate authority for any irreducible residual,
neither the 48-task count bound nor successful session release is evidence that
retained result bytes are bounded acceptably.

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
3. **On the terminal record — not the terminal event** — acknowledge browser
   presentation by releasing the observation and session. Keep the task and its
   reviewed artifact until explicit task close, which invokes the task-owned
   facade artifact release and drops the adapter's presentation projections.

Step 3's distinction is a real race, not pedantry. `SessionObserver` delivers
the `Terminal` event to the sink and only *afterward* calls
`dispatcher.get()` to build the terminal `SessionRecordView`. A client that
drains the event and immediately calls `close_session` removes the dispatcher
record out from under that lookup, and the observer thread takes
`SessionNotFound`. Cleanup therefore triggers on receiving a
`SessionRecordView` whose `result` is not `None`, which the observer emits
once the record is safely read.

Terminal cleanup remains caller-owned. A timeout before the hub gate changes no
stream state and releases the close claim, so an attachment can still succeed
before the adapter retries. Once subscriptions are detached, attach raises
typed `SessionCleanupPending` while `get`/`list` continue to expose the settled
record; the card remains closing until the caller or orderly shutdown retries
cleanup. There is no background reaper, and neither failure path rewrites the
terminal result or its settled history outcome.

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

Activation is not title-only: the process image owning the discovered HWND must
match `sys.executable` or the venv base interpreter before NamiSync restores or
foregrounds it. The fixed `Local\NamiSync.Desktop` mutex remains predictable.
A malicious same-principal process can squat that name or spoof an accepted
base interpreter, so this prevents accidental duplicate ownership but is not a
same-principal security boundary.

---

## 6. Concurrency

### DR-BR-24 — Bridge handlers are concurrent and must be synchronized

The pinned host creates one thread per exposed-function call before NamiSync
admission. The bridge admits at most 64 handlers past that gate and returns the
fixed `bridge_busy` refusal at saturation. This bounds admitted domain work and
teardown ownership, not raw WebMessage thread creation. The same admission
condition closes the race between admitted handler entry and teardown; no
bridge-global lock spans a command handler.

The ceiling is sized for one ordinary long poll on each of the 48 retained
tasks plus 16 shared transient-command positions. Those positions are not
partitioned or reserved: duplicate/superseding drains and other concurrent
calls can consume them, so saturation still produces the bounded, retryable
`bridge_busy` result rather than a per-command availability guarantee.

The product window is constructed with `js_api=None` and receives one
function-table entry named `dispatch`. Pywebview never walks the dispatcher
instance, so private dotted receiver names cannot become an alternate command
surface.

DR-M1-15 established that pywebview's exposed functions run on separate
threads—one newly spawned, unbounded thread per exposed-function call in the
pinned host. `BridgeDispatcher` correctly has no locking, because the spike's
handlers were pure. Every piece of state Stage 6 adds is not, and the runtime
is protected only for what it already owns (`_plans` is lock-guarded).

- **Selection** — owned by the service and revisioned (DR-BR-03). The
  revision is what makes ordering deterministic; a lock alone is not enough.
- **Event queue and drain tracker** — DR-M1-18's ordering guarantee rests on
  "at most one outstanding drain per task," stated as a *client* obligation.
  Two concurrent drains each pop a partial batch and events arrive out of
  order. **An ordering guarantee enforced only by client discipline is not a
  guarantee**; the server holds a per-task drain guard and a second concurrent
  drain waits or is refused explicitly. Each blocking drain has a bounded
  25–30 second wait, returns an empty batch on timeout, and is explicitly woken
  on close so pywebview threads cannot accumulate forever.
- **Progress-only drain linger** — once a drain first observes only queued
  `Progress`, it anchors one 150 ms server deadline capped by the drain's
  original 25-second deadline. Replacement progress never slides that anchor.
  With an active long poll on an otherwise idle task, the first detailed
  `Progress` may therefore wait the full 150 ms; command receipt and reliable
  running-state feedback bypass that linger.
  Reliable events, `Gap`, terminal events/records, close, supersession, or
  recovery wake immediately; a response may include the latest progress before
  the reliable value when sequence order permits. This enables the coalescing
  already promised by the queue without changing retry or cursor semantics.
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
- **Lost drain response** — adds no acknowledgment protocol, echoed delivery
  cursor, response cache, or server-side per-client receipt. The client knows
  the last non-`Gap` sequence it accepted. Transport/protocol uncertainty or an
  explicit `Gap` takes the existing resubscribe/terminal-record reconciliation
  path from its exact `first_missed_seq`; uncertainty without a `Gap` starts at
  the first sequence after the accepted value. A numeric sequence
  hole is legal because queued/replayed `Progress` may coalesce, and never by
  itself triggers recovery. A lost terminal batch is recovered from the
  retained terminal record; live replaceable progress may arrive late after
  resubscribe but never fabricates continuity.
- **Bridge reinjection** — pywebview reinjects after every
  `NavigationCompleted`, including canceled or failed navigation, and rebuilds
  the in-flight return-callback table. The renderer can trigger this
  repeatedly. `pywebviewready` is therefore repeatable: frontend
  initialization is idempotent and listener registration is not duplicated.
  A current-source contract test pins pywebview 6.2.1's
  `inject_pywebview`: it signals `before_load` before starting the API-injection
  worker that can fire `_pywebviewready`, so host generation renewal precedes
  every production frontend restart.
  Every firing invalidates operational readiness and pauses each nonterminal
  drain; only `shell_ready` and `readiness_echo` use bootstrap readiness.
  Normal calls, automatic retries, and exactly one re-arm per retained drain
  resume after the current host challenge is truthfully echoed. A lost mutation response retries
  with the original gesture `command_id`; a lost drain uses the sequence
  recovery above.
- **Subscription registry** — `SessionObserver.observe` raises when a session
  is already observed, so concurrent task opens must be guarded rather than
  treated as impossible.
- **Shutdown ordering** — stop accepting dispatches, close the task/drain
  registry and wake every outstanding drain **and every reliable producer
  waiting for bridge capacity**, wait for every handler already past that gate
  to return, close every observation, then close the service. Wrong order hangs
  exit, the same failure XV-18 catches one layer down. The quiesce barrier is
  the part an accept-flag alone misses: a dispatch
  that passed the gate a microsecond earlier can still be mid-`start_execution`
  when the service closes, admitting work nobody observes and then cancelling it
  half-applied. The dispatcher already has the pattern to copy — it waits on an
  in-flight admission count before closing — and the bridge needs the same
  counter over its handlers. The wait uses one finite monotonic deadline;
  failure leaves service, logging, app-path leases, and the instance mutex
  owned for retry. Only complete service shutdown permits native owner release.
- **Native document authority** — `CoreWebView2` remains owned by the WinForms
  UI thread. One idempotent synchronous `before_load` callback attaches the
  native handlers and writes a small committed-source snapshot; setup and
  dispatch workers only read that snapshot under its own lock. Pywebview's
  managed `Source`/`get_current_url()` are not authority because a canceled
  navigation can leave them naming the rejected target while native
  `CoreWebView2.Source` remains trusted. This lock is bridge-global and never
  nests inside a `TaskState` or service lock.

**Shape:** one `TaskState` per adapter-owned `task-<32-lowercase-hex>` holding a
64-update queue, observation generation, drain claim, and view state, with a
single lock/condition. Progress is the only replaceable member; reliable event
and record updates are ordered and backpressure at capacity. **Never hold a task
lock across a facade call, JSON encoding, or other I/O.** DR-BR-11's
deterministic ids remove what would otherwise have been a node-table lock site,
since a concurrent rebuild produces identical output.

Transport-memory accounting follows those custody roots rather than process
ownership: dispatcher replay deques, subscriber deques, and adapter task queues
form one identity-deduplicated graph. Terminal-result subgraphs reachable from
queue slots are reported separately under BR-G-45, never omitted and never
double-charged. Whole-process and renderer/runtime growth belongs only to
shell-owned SH-G-15.

---

## 7. Inherited Bridge Posture

`DEFENSE.md` owns the trust model: the packaged document is trusted code, all
values crossing or rendered by it are untrusted data, and arbitrary code in the
allowed origin is a trusted-base compromise rather than a contained principal.
This section owns the concrete bridge mechanisms beneath that policy.

Unchanged from `M1_PLAN.md` and restated only so this document is
self-contained: exactly one exposed `dispatch(command_json)`, versioned and
schema-validated and allowlisted (DR-M1-15/17); forced Edge Chromium with an
actionable failure and no MSHTML fallback; hardened pywebview settings with
`debug=False`; native `NavigationStarting`, `FrameNavigationStarting`, and
`NewWindowRequested` cancellation plus an independent per-call origin
recheck; no NamiSync-owned `evaluate_js`, `run_js`, `Window.state`, or
JavaScript construction as an application-data channel; opaque ids inbound
and validated raw display text outbound; final filesystem labels project the
fixed defended layout controls to visible injective markers through the sole
`textContent` writer; no `innerHTML`;
NamiSync uses the packaged asset server only for static assets and authorizes
no domain API through it. Pinned
pywebview 6.2.1 internally constructs JavaScript for exposed-function returns,
so its serializer/escaper is audited on every version change and covered by
the real-browser hostile-name round trip.

**The document security policy is normative and fixed.** The packaged
`index.html` carries exactly one Content-Security-Policy `<meta>` element, the
first element in `head`, whose raw ASCII content value is byte-for-byte:

```text
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
```

Both `default-src` and `connect-src` stay `'none'`: the bridge is the only
channel and needs no browser fetch, while the explicit
`script-src`/`style-src`/`img-src 'self'` directives authorize the same-origin
packaged assets. The authored `index.html`, this normative string, and the
static test's expected literal are the three witnesses — no generated HTML and
no production Python constant restate it. `M1_SHELL.md`'s SH-G-7 asserts the
wheel-shipped file equals this policy byte-for-byte.

The Stage 6 reality run refines how that posture is implemented. A pre-window
preparation step hardens pywebview and probes the WebView2 runtime through one
read-only compatibility module behavior-checked against the pinned pywebview
6.2.1 detector; a configured fixed runtime bypasses Edge-channel discovery but
not the shared .NET/netfx prerequisite read. The
start wrapper repeats preparation before pywebview initialization, then its
single zero-argument `initialized` callback refuses a non-Edge-Chromium
renderer before invoking host initialization. The host observes
`window.real_url` after the asset server has selected its random loopback port
and registers one idempotent synchronous `before_load` callback. Native
`CoreWebView2` access and event subscription occur only in `before_load` on the
WinForms UI thread, before pywebview injects application calls. The independent origin recheck
consumes a lock-protected native committed-source snapshot updated by
`SourceChanged`; it never calls pywebview `get_current_url()` from a handler. A
canceled target does not poison the snapshot, while a committed off-origin
native source does. Attachment success/failure is sticky and observable
because pywebview swallows callback exceptions; dispatch stays closed and the
host tears down actionably after failure. The exact origin is reconstructed
from the full `window.real_url` with `urlsplit`, never `rsplit`.

**Slice 2's wire contract is exact.** `assets/bridge.js` sends one JSON string
to `dispatch(command_json)`. Its UTF-8 representation is refused above 65,536
bytes before JSON decoding. Duplicate keys, non-finite numbers, malformed
Unicode, and missing or unknown fields at every defined object level are
invalid. A v1 request has exactly this shape:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "command": "pick_folder",
  "payload": {"purpose": "source"}
}
```

`schema_version` is the JSON integer `1`, not a Boolean. Transport
`request_id` and receipted-gesture `command_id` each match
`^[0-9a-f]{32}$`; a folder slot id matches `^slot-[0-9a-f]{32}$`. They are
opaque, noninterchangeable kinds. The wrapper mints a fresh request id for
every transport attempt. Success and failure return, respectively, exactly:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "ok": true,
  "result": null
}
```

```json
{
  "schema_version": 1,
  "request_id": null,
  "ok": false,
  "error": {
    "code": "invalid_request",
    "message": "The desktop request is invalid."
  }
}
```

The response echoes `request_id` only after that field independently passes
its grammar; otherwise it is `null`. The code/message vocabulary is exact:

| `code` | Fixed `message` |
| --- | --- |
| `invalid_request` | `The desktop request is invalid.` |
| `unsupported_version` | `Restart NamiSync to load a compatible desktop page.` |
| `unknown_command` | `This desktop action is not available.` |
| `invalid_payload` | `The desktop action contains invalid data.` |
| `request_too_large` | `The desktop request is too large.` |
| `slot_unavailable` | `That folder selection is no longer available. Choose both folders again.` |
| `picker_unavailable` | `The folder picker could not open. Try again.` |
| `command_conflict` | `This action no longer matches its first attempt. Start the action again.` |
| `planning_refused` | `NamiSync could not start a plan for those folders. Review both folders and try again.` |
| `task_unavailable` | `That desktop task is no longer available.` |
| `drain_busy` | `That desktop task already has an event request in progress.` |
| `observation_conflict` | `That desktop task is already observing different work.` |
| `bridge_busy` | `NamiSync is busy. Try this action again.` |
| `bridge_unavailable` | `NamiSync is closing or this desktop page is no longer trusted.` |
| `internal_error` | `NamiSync could not complete the desktop action.` |

Retry policy is
owned by the immutable command row and browser wrapper, not returned as handler
data. A structured refusal is definitive. An immutable row may declare one
identical-payload replay after uncertain transport delivery when a receipt or
revision rule makes that replay safe; only an admitted receipted command may
also declare replay after `internal_error`. Messages expose no request body, command payload, real
path, exception text, traceback, Python type, or implementation detail; a
handler exception never crosses pywebview as its native traceback-bearing error
value.

Command readiness is composition-owned. After reserving one of the bridge's 64
handler positions, rechecking exact document trust, bounding and decoding the
envelope, and resolving an allowlisted command name, the bridge calls mandatory
`admit(name)`. Host composition joins that row's declared `BOOTSTRAP` or `OPEN`
phase to the current exact `ReadinessContext`. Refusal, callback failure, or a
malformed verdict returns `bridge_unavailable` before payload validation. A
grant carries an opaque context that the bridge forwards unchanged;
`CommandSpec.invoke` exact-checks its context and phase before its payload
validator. The bridge names no readiness phase or appearance state. Handler
reservation and service/session admission remain separate mechanisms with
their existing lifetimes.

**The bilateral document-readiness rows are exact.** GUI Break 1 and its
hardening own two foundation-only rows outside Slice 2's two domain rows:

| Command | Exact payload | Exact success `result` | Identity / revision | Availability, deadline, and retry |
| --- | --- | --- | --- | --- |
| `shell_ready` | `{}` | `{"acknowledged":true}` | no `command_id`; no revision | `BOOTSTRAP` before `OPEN`; no post-open replay; 5,000 ms; no retry |
| `readiness_echo` | `{"challenge":"<32-lowercase-hex>"}` | `{"acknowledged":true}` for the current challenge after open, otherwise `{"acknowledged":false}` | no `command_id`; no revision | bootstrap plus exact post-open replay; 5,000 ms; after false or transport uncertainty, one retry with the identical payload |

The packaged module installs the fixed neutral readiness receiver before the
appearance receiver and shell DOM, then sends `shell_ready` through the existing
sole `dispatch` function. Native load and shell acknowledgement request
asynchronous initial surface-safety settlement. Only a confirmed safe surface
mints a cryptographic 32-lowercase-hex nonce and posts the exact host message
`{"challenge":"<nonce>","kind":"namisync.readiness.v1"}`. The current page
echoes that nonce with `readiness_echo`; only successful post completion and a
matching echo admit `OPEN` rows. The nonce proves current-generation bilateral
channel liveness only. It is not authorization, is never logged or persisted,
and cannot replace exact-origin trust, handler reservation, or task/session
admission.

Startup checks epoch ownership after every wait. The challenge receiver buffers
monotonic arrivals, including one arriving before the current waiter, and false
or uncertain echo delivery receives at most one identical-payload retry. A
same-origin reload begins a new closed generation before appearance or queued
posts can run; the UI-queued host post rechecks generation currency immediately
before WebView2 delivery. Once open, `shell_ready` is unavailable, while an
exact `readiness_echo` replay may obtain the truthful open result. Refusal or
close makes every row unavailable. The fixed five-second deadline starts at
each native `loaded`; it is product policy, not empirical acceptance evidence.
Appearance publication and enhancement quality are independent after a safe
base surface settles. Only an unconfirmed opaque rollback after native surface
mutation refuses startup.

**The Slice 2 production allowlist has exactly two rows.** Payload and result
schemas in this table are exact; Slice 2 adds no dormant or placeholder command
name.

| Command | Exact payload | Exact success `result` | Identity / revision | Deadline and retry |
| --- | --- | --- | --- | --- |
| `pick_folder` | `{"purpose":"source"}` or `{"purpose":"target"}` | cancel: `null`; selection: `{"id":"slot-<32-lowercase-hex>","display":"<valid Unicode string>"}` | no `command_id`; no revision | interactive native operation; no client deadline and no automatic retry; another gesture is a fresh attempt |
| `start_plan` | `{"command_id":"<32-lowercase-hex>","source_id":"slot-<32-lowercase-hex>","target_id":"slot-<32-lowercase-hex>","deletion_policy":null}` or the same key set with `"trash"` or `"additive"` | Slice 2: `{"request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}`; Slice 3: `{"task_id":"task-<32-lowercase-hex>","request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}` | required `command_id`; no revision because it creates a session rather than acting on a revisioned view; Slice 3's adapter task receipt returns the same task id on replay | 30,000 ms; after uncertain delivery, bridge reincarnation, or `internal_error`, at most one automatic replay has a fresh request id and the identical command, payload, and command id; an exposed manual Retry retains that command id |

`null` consumes the service's current semantic deletion setting; `mirror` is
not accepted here. Automatic replay uses the identical payload. The service
receipt ultimately keys the resolved source/target pair plus deletion policy:
the same resolved intent returns its retained receipt and different resolved
intent under that command id returns `command_conflict`. A JavaScript deadline
does not cancel an already admitted Python handler.

**The native folder picker is the only path ingress.** Only it may create a
server-side slot. A slot retains the real path, `source` or `target` purpose,
inert display text, fixed monotonic expiry 30 minutes after insertion, and LRU
recency. Lookup is nonconsuming and updates recency without extending expiry.
Expired entries are swept before insertion or lookup; at most 32 unexpired
entries exist, and an insertion at capacity evicts exactly the least-recently
used entry, with slot id breaking a timestamp tie. `start_plan` resolves and
snapshots both slots under one lock, requires one live purpose-matching source
and target in that same observation, and only then updates both recencies.
Fabricated, expired, evicted, and wrong-purpose ids have the same sanitized
`slot_unavailable` result. The browser receives only `{id, display}`, sends only
ids back, and can never promote `display` to filesystem authority.

An exact `start_plan` replay is checked against its retained wire intent before
these volatile slots are resolved, so an earned receipt survives slot expiry or
eviction. Its identity is the gesture `command_id`, the exact original
source-slot/target-slot/deletion-policy wire intent, and the resolved
source/target/deletion intent. A different wire or resolved intent under the
same command id remains a conflict.

The production command mapping is exactly `shell_ready`,
`readiness_echo`, `pick_folder`, `start_plan`, `next_events`,
`release_terminal_session`, `close_task`, `read_cosmetic_section`, and
`replace_cosmetic_section`.
`test_report` is a test-owned constructor-only harness row: the harness builds
a new immutable mapping from those production rows plus its own
validator, handler, payload, and result schema under `tests/`. No product argv,
environment, page value, or bridge request can enable it, and it has no product
retry class. Later plan, inventory, semantic-settings, and history commands
are not reserved or allowlisted until their owning slices
land each row with its schema, receipt/revision rule, deadline, retry policy,
and gate.

The existing Python/JavaScript command-policy mirror mechanically compares
each production row's availability phase as well as its timeout and retry
class. A browser/server phase drift therefore fails the owning static test
instead of silently changing admission.

`release_terminal_session` accepts exactly `{task_id, session_id}` and returns
those exact echoed ids. It is a mutating lifecycle acknowledgment with no
`command_id` or revision, a 30-second deadline, and finite delayed retries that
retain the identical payload. `close_task` remains the separate explicit
disposal operation.

`bridge.js` exports the neutral browser transport primitive
`dispatchInteractive(command, payload, validator)`. It accepts only a 1--64
ASCII lowercase-snake wire name matching
`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$` and a callable result validator, and performs
one attempt with no client deadline and no automatic retry; payload validation
belongs to the constructor-supplied Python command row. `pickFolder` and the
headed harness's constructor-only `test_report` client share this primitive.
The primitive only formats and submits a request: it neither registers nor
allows the name. The Python mapping remains the sole allowlist, while the
`test_report` literal, validator, payload/result schemas, and handler remain
tests-only and absent from the wheel.

**Slice 3's wire extension is exact.** It adds only `next_events`; the
production mapping then contains `pick_folder`, `start_plan`, and
`next_events`. Its payload is exactly
`{"task_id":"task-<32-lowercase-hex>","session_id":"<32-lowercase-hex>","drain_id":"<32-lowercase-hex>","replay_from":null}`,
or the same keys with a positive integer first-desired sequence. Its result is
exactly the echoed task/session/drain ids plus `updates`, an array of zero to 64
members. Each member is exactly
`{"update_type":"event","event":<SessionEventView>}` or
`{"update_type":"record","record":<SessionRecordView>}`. The server wait is
25 seconds and the browser deadline is 30 seconds. A terminal record returned
by `start_plan` carries the workflow's exact `kind` value, `"sync-plan"`; the
browser validates that production identity rather than an adapter-only alias.
Empty timeout success arms
the next ordinary drain. Transport/protocol uncertainty uses a fresh drain id
and `replay_from=last accepted non-Gap sequence + 1`; an ordinary explicit
`Gap` remains visible, stops later updates, and uses its exact positive
`first_missed_seq`;
numeric holes caused by legal progress coalescing do not. The response contains
no acknowledgment, cursor, receipt, `has_more`, or echoed replay value.

When the queued response is progress-only, the server waits at most one fixed
150 ms linger from first progress availability. Further progress replaces the
queued snapshot without extending that deadline. Any reliable event, `Gap`,
terminal event/record, close, supersession, or recovery ends the linger
immediately. This includes the first progress-only response: under an active
long poll it may consume the full 150 ms, while receipt and reliable state
bypass that linger. The 25-second long-poll deadline remains the outer bound.

The browser validates the whole response before applying it. On an ordinary or
uncertainty-recovery response, the first `Gap` remains visible, stops application
of later updates, and arms recovery from its `first_missed_seq`. A recovery
response may begin with the matching `Gap` whose `first_missed_seq` equals that
attempt's `replay_from`; this proves the prefix is no longer retained, so the
browser preserves the gap, applies the available tail, and does not loop. A
later or different `Gap` becomes a new recovery point. Accepting a terminal
record stops the task's drain loop even when it follows that matching leading
gap; terminal truth never erases the visible loss.

The adapter queue is exactly 64 updates. A new `Progress` replaces an older
queued progress or is discarded when reliable data owns every slot. Reliable
events and terminal records may evict progress but never another reliable
update; an all-reliable full queue blocks its observation sink until drain or
shutdown. Exactly one drain per task removes up to 64 FIFO entries. A second
marks the incumbent superseded, wakes it, waits
under the same 25-second bound for its claim to release, then returns
`drain_busy`; reinjection therefore has a bounded one-rearm convergence rule.
Unknown/closed or mismatched task/session authority is
`task_unavailable`; a competing observation attach/recovery generation is
`observation_conflict`. Their fixed messages are defined by the table above.

The adapter retains at most 48 tasks. After a terminal record has been returned
by a drain, `release_terminal_session` stepwise unsubscribes and closes the
session, then refuses further drain/recovery while retaining the plan, task,
start receipt, and capacity slot. `close_task` completes either unfinished step,
drops the plan, and alone removes the task and start receipt. A 48-entry
close-receipt LRU also proves success to a delayed release retry. Browser drain,
session-release, and explicit-close recovery use finite delayed schedules and
become visibly retryable when their budget is exhausted; no uncertainty path
implicitly disposes of the task.

BR-G-45 remains open on which terminal-result representation, if any, survives
successful presentation and session release. The eventual aggregate policy
must preserve callback/release retry truth, reviewed-plan authority, and a
truthful fallback when durable history is degraded; it may not treat the
48-task count ceiling as a byte ceiling or clear the only exact result early.

Task start is single-flight per `(command_id, resolved source, resolved target,
deletion policy)`. One provisional adapter task exists while the facade call is
outside the task lock; same-intent callers wait and different intent conflicts.
Success binds and returns one task/request/session triple. Facade, admission, or
attach failure wakes same-intent waiters with the same sanitized refusal and
removes every provisional task/command entry after they release it; no failed
task id is exposed or retained. Failure after facade success compensates by
unsubscribing, closing the session, and dropping its plan outside the task lock.

Normal attachment precedes schedulability. The service plan start accepts an
optional sink excluded from its command-receipt signature. The domain-blind
dispatcher constructs an unpublished record/hub/store row and preopened stream,
passes `(session_id, stream)` to an optional attach callback, and receives an
idempotent rollback. Only after adoption succeeds does it emit `PENDING` while
the session remains unschedulable, then atomically publish the maps, append
pending, and notify the scheduler under its gates. Every exception through
`PENDING` emission and atomic publication takes the same path. Attach is atomic
from dispatcher ownership: it returns rollback only after complete adoption,
or raises after self-reverting every partial observer entry/thread. Once
ownership transferred, dispatcher invokes rollback first so it signals, closes, joins,
and identity-removes that adopted observation, then closes remaining
stream/hub ownership and drops the store row. Cleanup failure never replaces
the initiating error; it remains dispatcher cleanup-pending ownership, makes
shutdown incomplete, and can never become schedulable. Recovery uses
the service observer's explicit positive `from_sequence` resubscribe seam and
replaces one adapter observation generation without holding a task lock over
the facade call. Reobserve returns `SessionRecordView`: nonterminal means the
replacement sink is installed; terminal means no stream was installed and the
registry enqueues that record. Per-task serialization ensures close can clean a
replacement that returned after its generation became stale.

At Slice 2 closure the exact packaged frontend set is `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`. The last owns the strict production
`renderText(element, text)` sink and remains the only `textContent` writer.
Slice 4 adds `renderFilesystemText(element, text)`: it rejects non-strings,
maps the exact `DEFENSE.md` set to injective uppercase `⟦U+XXXX⟧` markers, and
delegates the final write to `renderText`. It is used only for
filesystem-derived `row.display`; generic interface copy is not rewritten.
Browserless transport/render probes and the headed transport page live under
`tests/assets/`, not package data.

The headed gate composes its single `test_report` row only through the same
dispatcher constructor used by production, under a unique test identity and an
absolute physical local page/data root. It automates the real native folder
picker without a foreground-forcing API, localized-label lookup, or synthetic
mouse/keystroke input: UI Automation classifies the exact edit and confirmation
controls, then a visible, enabled, same-dialog/process/thread native `Button`
with control id `1` receives one queued `BM_CLICK` per validated attempt, with
at most one reclassification-bound retry. Exact dialog closure and the later
selected-path assertions prove processing rather than treating `PostMessageW`
admission as selection. The gate proves selected paths stay
behind purpose-bound ids, commits an independent second loopback origin and
verifies zero handler calls, and round-trips the hostile corpus through the real
pinned return transport and production sink. Renderer/log evidence is read from
native `BrowserVersionString`; logs contain neither request bodies,
real paths, hostile sentinels, tracebacks, exception text, nor `NICKNAME`.
The installed-wheel browser scenario also drives the production `bridge.js`
drain manager through stale readiness and generation settlements, identical
`start_plan` replay, numeric holes without recovery, explicit-`Gap` recovery,
busy and malformed refusal budgets, nested hostile-Unicode public views,
the real `sync-plan` terminal-record identity, terminal release without
automatic task close, and task/listener/timer cleanup.

**`ui-state.json` carries cosmetics only.** `M1_PLAN.md` DR-M1-03 established it
as the GUI-owned counterpart to `db/settings.json`. The ratified strict v1 schema
contains only the appearance override; later recents, window geometry, column
and sort state, active filter chips, and file-list treegrid state require
explicit typed section additions whose durable keys are ratified by their
owning slice. It may **not** hold a plan
request id, a session id, a task identity, a selection, a `view_id`, or a
projection revision. The distinction is not stylistic — anything in the
second list would be a durable session store arriving through the back door,
unreconciled with the process-local truth it would contradict on the next
launch.

### DR-BR-28 — Cosmetic persistence crosses one typed section channel

The bridge thaw adds two generic-shaped commands and one accepted section,
then refreezes the protocol. Future cosmetic sections extend a source-owned
registry with their own bounded value schema; they do not add one bridge
command per widget and do not pass through semantic settings or the service
facade. The v1 appearance value is exactly `{"theme":"system"}`,
`{"theme":"light"}`, or `{"theme":"dark"}`.

| Command | Exact payload | Exact success `result` | Identity / revision | Availability, deadline, and retry |
| --- | --- | --- | --- | --- |
| `read_cosmetic_section` | `{"section":"appearance","value_version":1}` | `{"section":"appearance","value_version":1,"revision":N,"dirty":false-or-true,"value":{"theme":"system-or-light-or-dark"}}` | `READ_ONLY`; `command_id` and request revision metadata forbidden; returns a nonnegative JavaScript-safe process-local section revision | `OPEN`; local 5,000 ms; after transport uncertainty or timeout, at most one retry with the identical payload and a fresh request id |
| `replace_cosmetic_section` | `{"section":"appearance","value_version":1,"expected_revision":N,"value":{"theme":"system-or-light-or-dark"}}` | the read result plus `"disposition":"applied-or-noop-or-conflict"` | `MUTATING`; `command_id` forbidden and request revision metadata required; `expected_revision` is a non-Boolean JavaScript-safe integer | `OPEN`; local 5,000 ms; no automatic replay; after transport uncertainty or timeout, reconcile through `read_cosmetic_section` before another replacement |

Every object is exact: missing or unknown members, another section, a
`value_version` other than the non-Boolean integer `1`, an invalid theme, or a negative, fractional, Boolean, or
greater-than-`9007199254740991` expected revision is `invalid_payload`. No new
bridge error code is added. Each loaded section starts at revision zero;
accepted value changes advance its process-local revision by one and also
advance one private process-local document generation. The document generation
is not persisted or exposed; it orders whole-file snapshots across all current
and future sections. `dirty` is
document-wide because all sections share one atomic file; it covers a pending
or failed save and the session-only fallback used for unsupported forward state.

Replacement is serialized and follows this complete decision table:

- current revision plus a different value updates memory, advances the
  revision, notifies isolated subscribers, and returns `applied` with
  `dirty:true`. When persistence is permitted it schedules the new current
  document generation for the shared writer; forward-version protection instead keeps the
  value session-only without touching the file;
- current revision plus the same clean value returns `noop` without writing;
- current revision plus the same dirty value returns `noop` and explicitly
  schedules the current document generation when persistence is permitted; forward-
  version protection performs no attempt;
- stale revision plus the already-current value returns `noop` without another
  write, making duplicate delivery harmless;
- stale revision plus a different value returns `conflict` without mutation or
  persistence.

A subscriber failure is logged without its exception text, cannot change an
accepted disposition, and cannot prevent other subscribers from observing the
revision. Registration and current-snapshot capture are atomic; callbacks run
outside the state lock, carry the revision, and consumers discard non-newer
delivery so appearance composition has neither a read/subscribe gap nor a
reversed-notification regression. Cosmetic reads and writes never invoke
the service, registry, planner, task state, semantic settings, or plan hashing.
They remain independently degradable and do not participate in readiness.

The on-disk v1 shape is exactly:

```json
{"schema_version":1,"sections":{"appearance":{"value_version":1,"value":{"theme":"system"}}}}
```

The owner reads at most 1 MiB plus one sentinel byte before UTF-8 decoding or
JSON construction and rejects duplicate keys, non-finite values, excessive
nesting, and every unknown or malformed member. Missing state yields clean
defaults and creates no file. The unversioned prototype is recognized only by
its exact top-level key set — `recent_sources`, `recent_targets`, `window`,
`columns`, and `sort`; it and a malformed current document yield dirty defaults
and a sanitized diagnostic, but load itself does not mutate the artifact. A
newer document schema or appearance value
version yields dirty session defaults with persistence blocked for the life of
that owner. An existing artifact that cannot be read likewise yields dirty
session defaults with persistence blocked; the owner never overwrites content
it could not inspect. An older binary never overwrites state it cannot
understand.
Adding a registered section advances the global document schema and starts the
new section at value version one. Changing an existing persisted value shape
advances both the global schema and that section's value version. The canonical
encoded document is checked against the same 1 MiB ceiling before any write.

The single process-local writer waits 250 ms after an explicit schedule. Each
schedule captures the private document generation and the complete typed
document. A newer accepted document generation cancels and replaces a pending attempt before it
starts, so intermediate revisions coalesce; an attempt already in progress is
serialized ahead of the newer snapshot. A completed write may mark the
document clean only when the written document generation is still current.
Every explicit
schedule receives at most one atomic attempt, and a superseded pending schedule
receives none. A failed document generation may be scheduled again only by a later
same-value request carrying that current revision; close never invents that
retry. Failure preserves the accepted session value,
leaves `dirty` true, and logs only a stable event plus exception type. Access
or path failure, full disk, and unclassified I/O end that attempt immediately;
there is no timer retry loop.

Close first stops new cosmetic commands, then cancels a pending timer and waits
for any in-flight atomic replacement. It flushes the current snapshot exactly
once only when its document generation is dirty, persistence-permitted, and
has never been attempted; it does not retry a failed document generation and never writes
unsupported forward state. Missing state is not created merely by launch.
There is no cross-process mutex. Save failure remains a sanitized log event in
this checkpoint; `dirty` is retained for a later settings surface and does not
replace the operational shell status. After uncertain replacement delivery or
timeout, the page performs a guarded section read and
reconciles before enabling another theme change. An unchanged expected
revision remains delivery-ambiguous and disabled. A same-realm bridge
generation waits the prior replacement settlement before its initial read. If
a full document replacement destroys that realm, a later validated native
appearance publication triggers another authoritative section read on the
healthy publication path; this converges a late prior-document mutation but
does not claim a zero-stale interval while publication is pending or degraded.

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

- **Staged WebView2 integration tests** drive real page JavaScript through
  `window.pywebview.api.dispatch`, the Python handler, and pinned pywebview's
  internal `evaluate_js` return transport. Slice 2 renders the scanner's
  hostile-name corpus through the production inert-text path in the
  constructor-only harness and reads `.textContent` back byte-for-byte; this
  proves the real return transport and shared sink without pretending the later
  product surfaces exist. Slice 4 separately drives every defended layout
  character plus marker delimiters through the installed production tree and
  proves the exact visible markers in both DOM and Chromium accessibility
  names, no surviving active layout control, unchanged ordinary Unicode/markup-
  like and long labels, and raw opaque ids at callbacks. Slice 5 repeats both
  corpora against the actual plan DOM and slice 6 repeats them against the
  actual inventory DOM. BR-G-32 remains open until those product surfaces prove
  text, not markup, attributes, or script.
- **A broadened static scan** over packaged assets, because scanning only for
  `innerHTML`, `eval`, and `Function(` misses most markup sinks. It also
  rejects `outerHTML`, `insertAdjacentHTML`, `document.write`, `srcdoc`,
  `DOMParser`, `Range.createContextualFragment`, dynamic `setAttribute` names,
  assignment of returned data into `href`, `src`, `style`/`cssText`, or any
  `on*` attribute, plus `eval`, `new Function`, and string-form timers. This
  source scan proves only that NamiSync-owned code constructs no JavaScript;
  it cannot prove or inspect the third-party return transport.

The split evidence has concrete homes:

- `tests/interfaces/web/test_commands.py`, `test_transport.py`, and
  `test_slots.py` own separately discoverable ordinary `test_br_g_32_*` nodes
  for the immutable table, public-view codec manifest, exact envelope/refusal
  boundary, receipt identity, and slot lifecycle. `test_frontend_static.py`
  owns the prefixed packaged-asset sink scan.
- `tests/interfaces/web/test_transport_headed.py::test_br_g_32_hostile_text_crosses_real_return_transport_and_production_text_sink`
  owns the real pinned-pywebview hostile-text return path through the
  constructor-only harness.
- Separate `test_br_g_32_*` nodes in `test_transport_headed.py` own real
  native-picker confinement and independent off-origin dispatch refusal.
- `tests/interfaces/web/test_sync_surface.py::test_br_g_32_plan_dom_hostile_text`
  and
  `tests/interfaces/web/test_inventory_surface.py::test_br_g_32_inventory_dom_hostile_text`
  own the production plan and inventory DOM stages in slices 5 and 6.

Thus Slice 2 closes BR-G-32's transport, picker, origin-refusal, and static-sink
portion of XV-19 without claiming that transport alone proves a later DOM sink.
It also closes SH-G-3. Slice 4 closes the generic filesystem-label sink and
installed-tree portion of XV-19 through SH-G-7/BR-G-34. The production plan and
inventory DOM clauses remain open for Slices 5 and 6, so BR-G-32 as a whole
remains open.

### DR-BR-26 — The node tree is a pure function

Plan review plus collapsed set plus deselected set to an ordered node list,
tested directly in pytest with no bridge involved. It is the largest new
component and must not be entangled with transport, or it becomes untestable
exactly where risk concentrates. Coverage includes a hostile-named directory
move, since grouping does segment arithmetic on canonical keys while
retaining raw display paths for the final presentation sink and the two must
stay consistent.

Because node identity now arrives in Stage 5.5 (DR-BR-11), that stage carries
its own hostile-name case: **inventory** node ids minted from hostile paths,
round-tripped through exact-row and recursive-subtree command resolution plus
foreign-location refusal. The directory-move case above belongs to slice 5 and
does not cover it.

### DR-BR-27 — Receipted commands are idempotent; revisioned-view mutations are guarded

Selection needs both properties in DR-BR-03, but they are not one universal
mutation schema. The gap is still not cosmetic:
`acknowledge_inventory` and `restore_inventory` already take a caller-supplied
`command_id` that the recorder uses as its receipt key, and DR-BR-05 lifted them
as "plain passthroughs" without saying who mints it. A bridge that generates a
fresh command id per attempt defeats the receipt the recorder was built around.

**Each command row declares the two concerns independently.** A receipted user
gesture carries an idempotency key that survives uncertain delivery. A command
formed against a revisioned server view also carries that exact revision. Thus
Slice 2's session-creating `start_plan` requires `command_id` but no revision,
while `pick_folder` requires neither; later selection and inventory mutations
carry the revision required by their owning view contract. The bridge never
invents a blanket revision field for a mutation that was not formed against a
revisioned view.

- **Idempotency key.** For every receipted command, `command_id` is minted
  **once per user gesture** by the adapter and reused verbatim across every
  retry of that gesture. It is not regenerated on resend, and it is not minted
  per dispatch, so a double-click or resend collapses to one applied change.

  **One mechanism cannot supply this property.** Three separate obstacles exist
  in the current tree:

  1. **The receipt reaches one command family.** `command_id` appears only on
     `InventoryVisibilityCommand`, and only `change_inventory_visibility` keys on
     it. Every session-creating command — refresh, baseline, verify, rebaseline,
     plan, execute — mints `request_id = uuid4().hex` inside the facade per
     dispatch, and `run_inventory` derives its scope token from that. A retried
     gesture therefore mints a fresh identity and submits a **second session**.
     Nothing dedupes, and no receipt is consulted.
  2. **The receipt cannot express a retry across two real executions.**
     `_payload_hash` is recursive over every dataclass field, and both
     `InventoryVisibilityCommand` and `InventoryCommand` carry a timestamp the
     caller does not supply (`changed_at`, `observed_at`); `InventoryCommand` also
     carries the whole `ScanResult`. A genuine retry therefore hashes differently
     under the same key, which raises `TokenConflictError` rather than returning
     `NOOP`. The receipt is a crash-and-transaction guard, not a retry mechanism.
  3. **One gesture is many calls.** `acknowledge_inventory` and
     `restore_inventory` take one row per call while the key is minted per
     gesture, and the receipt key is `command_id` alone. Ten rows under one
     `command_id` collide on the second row.

  **Resolution: split by mechanism.** Acknowledge/restore remain
  recorder-keyed, using a per-(gesture, row) derived key and one
  caller-supplied timestamp reused byte-identically on retry. Every receipted
  facade call that mints an identity and submits a session instead uses a
  service-held
  `command_id → (request_id, session_id)` receipt and returns the existing pair
  on a repeat. That receipt lives exactly as long as the retained session:
  `close_session` removes its reverse mapping and service shutdown clears the
  remainder, so retry safety does not become an unbounded process-lifetime map.
- **The typed disposition reaches the view.** The recorder already answers
  `APPLIED` / `NOOP` / `STALE` / `CONFLICT`, and DR-BR-05's "view types" phrase
  never named one for it. A primitives-only disposition view carries that value
  through, because the four mean different things to a user: applied and noop
  are both success and only one should reflow the list (DR-BR-20), while stale
  and conflict mean the row moved underneath them and the view must re-read.
  Collapsing them into a boolean would reintroduce exactly the string-parsing
  the four truth axes exist to prevent.

  **A replay reports `NOOP`, not `APPLIED`** — `_command_receipt` maps a prior
  `APPLIED` to `NOOP` deliberately, so the caller can tell "I just changed this"
  from "this was already changed." Idempotency here means *applied once*, never
  *same answer twice*, and any test asserting the latter is asserting something
  false.
- **Revision guard.** An id-based location command (DR-BR-06) resolves node and
  row ids against a projection the user was looking at. Between that render and
  admission the projection can be invalidated by an observed session terminal or
  a completed acknowledge. The command therefore carries the `view_id` and
  projection revision it was formed against and is **refused as stale** if the
  projection has moved, down the same path DR-BR-16.1 already refuses a stale
  page request. Without it, a user acts on what they see and the server freezes
  something else — the identical failure DR-BR-03's modal interval closes for
  selection, left open on the inventory side.
- **The freeze is taken under the guard, not before it.** Folder integrity
  expansion reads the descendant set inside the same validation that checks the
  revision, so the admitted subject list and the revision the client saw cannot
  disagree.
- **The receipt is consulted before the guard.** These two mechanisms otherwise
  cancel each other on the one command family where both apply: an acknowledge
  both consumes a revision and bumps it, and the client only learns the new value
  from the response — so a retry after a lost response necessarily carries `R`
  while the projection sits at `R+1`, and a guard evaluated first refuses it as
  stale without ever reaching the receipt that would have recognized it. A
  recognized `command_id` therefore short-circuits to the recorded disposition
  plus the current revision, and only an *unrecognized* command is revision-
  guarded. For the same reason the guard is evaluated **once per command over the
  whole subject set**, with a single revision bump per gesture: a per-row guard
  refuses rows 2..n of a gesture against a revision that gesture's own first row
  advanced.

**Origin authorization is entry-only.** `dispatch` admits a handler against
the current native committed document, then releases that lock before the
handler runs. It does not recheck after completion or roll back a mutation
whose response becomes undeliverable after navigation or bridge reinjection.
That is uncertain delivery, not uncertain commit: the client retries a
receipted gesture with the same `command_id`. Recorder-backed mutations replay
as `NOOP` after an earlier `APPLIED`; session-creating commands return the
retained original request/session identity. Receipt lookup still precedes
mutable-state reread and revision validation.

**Refusal is not an error dialog.** A stale command re-reads and re-renders; the
user sees current truth and repeats the gesture if they still want it. This is
the DR-BR-03 conflict posture, not the DR-BR-22 confirmation posture, because
nothing was destroyed — the view was simply out of date.

The recorder's receipt must also cover the scope it applied. `record_inventory`
keys on `inventory:{location_id}:{scope_token}` plus a payload hash, so
**DR-BR-06's subtree roots participate in that hash**: otherwise a replay under
an equal scope token could accept a materially different scope. The generic
hasher makes this likely automatic and "likely automatic" is precisely what
`M1_PLAN.md` DR-M1-10 warned about when the history hasher silently skipped an
unrecognized body — so it is asserted, not assumed.

---

## 9. Deferred, Rejected, and Resolved

This section records dispositions only. Live rules remain in their DR-BR section
or BR-G gate; dated delivery and evidence remain in the changelog and owning
artifact documents.

### Rejected

| Proposal | Disposition |
| --- | --- |
| Inventory snapshot token | Rejected — causal rereads plus projection revision cover the owned consistency boundary without a database generation. |
| Per-node lazy expansion | Rejected — expanded review would cost one round trip per folder; bounded visible windows serve the same hierarchy. |
| Move-group thresholds or sub-windows | Rejected — a move is one paired annotation, not a second paging or selection unit. |
| Synthetic operation ids for structural folders | Rejected — scope-qualified node ids represent structure without impersonating operations. |
| Client-side search or filtering | Rejected — the client sees only a window and cannot filter/search the authoritative unmaterialized set. |
| Merge safety exclusions with user deselection | Rejected — reselection could silently readmit planner-refused work. |
| Discard late selection by request id | Rejected — revision conflict is the authoritative concurrency decision. |
| Path-only node ids | Rejected — identical relative paths across scopes would collide. |
| Inventory row-level SQL paging | Rejected — row order cannot express synthesized ancestry, rollups, or the post-filter visible sequence. |
| Freeze selection directly to committed | Rejected — failed dispatcher admission would strand an uneditable task. |
| Typed desktop confirmation phrase | Rejected — ordinary explicit confirmation supplies the intended irreversible-action friction. |
| Stage 5.5 CLI acknowledgment commands | Rejected — ids were undiscoverable and a coherent CLI contract exceeded the facade-lift scope. |
| Release every background projection | Rejected — it makes the LRU cap unreachable and defeats fast task switching. |
| Deep-copy a projection for one-row patch | Rejected — it restores O(n) allocation for a local change. |
| `cli → web` launch import | Rejected — a sibling import violates the interface boundary; the launcher owns selection. |
| Reconstruct deselection reasons from selected ids | Rejected — final membership cannot recover user-choice provenance. |
| Exact-path semantics for folder commands | Rejected — it silently omits descendants and cannot discover new files during refresh. |
| Generalize the exact-path scanner for recursion | Rejected — exact-path ignore semantics make ordinary recursive scopes inconclusive. |
| Restate subtree incompleteness causes | Rejected — a closed copy would drift from the shared full-walk contract. |
| Predict folder-integrity descendant counts | Rejected — each mode owns a different eligibility set. |
| Confirm folder integrity actions | Rejected — the operation is non-destructive, pausable, and cancelable. |
| Client-only autoscroll anchor | Rejected — the target may not be materialized in the DOM. |
| Second bridge reliable-loss protocol | Rejected — dispatcher `Gap` plus durable reconciliation already owns visible loss. |

### Deferred

| Work | Reopen condition |
| --- | --- |
| Integrity continuation restructuring | A late-run 10k/100k/large-folder pause benchmark demonstrates unacceptable cost. |
| Filter-exclusion visibility in plan review | A product slice owns the missing review explanation. |
| Eliminate `get_plan_review` full-view rebuilding | A measured caller still pays it after memoized tree and direct preview paths. |
| Persist selected-kind/integrity history summaries | A later schema-version decision owns the columns; M1 does not add a fallback. |

### Resolved

| Disposition | Landed record |
| --- | --- |
| User selection, subtree scope, partial subject-local integrity, and page size use the contracts in DR-BR-01–06 and DR-BR-15. | [Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30) |
| Recorder mutations use reproducible row receipts; session-creating commands use service-held lifecycle receipts. | [Close the M1 safety and post-refactor audit](../CHANGELOG.md#close-the-m1-safety-and-post-refactor-audit-2026-08-08--2026-08-11) |
| Drain recovery triggers only on explicit `Gap` or uncertain drain failure; legal progress sequence holes do not trigger it. | [Close transport custody and realign the bridge boundary](../CHANGELOG.md#close-transport-custody-and-realign-the-bridge-boundary-2026-08-13--2026-08-14) |
| The 100,000-subject scale envelope and transport-custody authority are governed by BR-G-42; terminal artifacts remain separate under BR-G-45. | [Ratify measurement and documentation authority](../CHANGELOG.md#ratify-measurement-and-documentation-authority-2026-08-14--2026-08-18) |
| Move-ghost filtering removes synthetic-only ancestors with the ghost. | [Complete and harden the accessible desktop foundation](../CHANGELOG.md#complete-and-harden-the-accessible-desktop-foundation-2026-08-12--2026-08-18) |

---

## 10. Delivery

### Packaging

`pywebview` is a required runtime dependency. `nami-sync` and
`python -m namisync` remain CLI-only and point no-subcommand users to
`nami-sync-gui`, which launches without a retained console. Missing or
incompatible WebView2 is refused with an actionable error; MSHTML is not a
fallback.

`interfaces/launcher.py` sits above the sibling CLI and web adapters and
imports only the selected adapter lazily:
`launcher → {cli, web} → service`, while `cli ↮ web`. Explicit CLI work
does not import or initialize `pywebview`; GUI code remains under
`interfaces/web`. BR-G-19 enforces this boundary.

### Stage 5.5 lanes

Stage 5.5 used three disjoint implementation lanes converging on the facade.
The table remains as ownership context for its gates; delivery status is in
[Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30).

| Lane | Owns | Delivery | Depends on |
| --- | --- | --- | --- |
| **A — Tree substrate** | `core/pathing.py`, `workflows/node_tree.py`, `modules/planner.py` | Shared path helpers, hierarchy/index, scoped ids, pure tree tests | — |
| **B — Scan scope** | `core/models.py`, scanner, recorder, inventory workflow | `SUBTREES`, shared walk, literal reconciliation range, inventory v2/warnings | — |
| **C — Selection semantics** | Selection, execution/payload/view/sync workflows | Deselection provenance, payload v4, re-derivation, closure, `all-noop` truth | — |
| **D — Facade** | Service and workflow runtime | Revisions/commitment, inventory lifts, opaque-id commands, receipts, preview | A, B, C |

A, B, and C could land independently; D was the integration point. The table
owns production boundaries, not every later consumer: projection ownership,
`patch_row`, `view_id`, and projection revision belong to Slice 6, while
DR-BR-14 belongs to Stage 6. Stage 5.5 was verified headlessly at the facade and
each owning scanner/recorder/codec/tree boundary; it did not add CLI surface or
desktop presentation.

### Acceptance gates

A BR-G gate is closed only by its stated production entry point and
counterexample. Every gate has a collected `test_br_g_<number>_*` pytest at
each named level; fault injection may replace a dependency, never the unit under
test. A skipped, xfailed, uncollected, or comment-only counterexample leaves the
gate open.

Only a gate-required installed-WebView2 check, source/import scan, or recorded
measurement may supplement pytest. Those artifacts link from the implementation
change. BR-G-42 owns its exact reference profile and budgets below. Gate
headings are organizational, not lane ownership.

| Owner | Gate-test module | Independent Stage 5.5 scope |
| --- | --- | --- |
| A | `tests/test_bridge_tree.py` | BR-G-1 builder, BR-G-2 structure, BR-G-3 |
| B | `tests/test_bridge_scan_scope.py` | BR-G-4–9, BR-G-25–28 |
| C | `tests/test_bridge_selection.py` | BR-G-11–12 |
| D/integration | `tests/test_bridge_service.py`, `tests/test_bridge_resume.py` | BR-G-1 service refusal, BR-G-10, BR-G-13–18, BR-G-20–21, BR-G-24, BR-G-29 |

**Lane A — tree substrate**

**Lane A — tree substrate**

- **BR-G-1 — Node ids are scope-qualified and stable.** Two locations each
  containing `docs\a.txt` produce different node ids; rebuilding either tree
  twice produces byte-identical ids. At integration, a foreign-location id is
  refused by `NamiSyncService`, not filtered. *Not satisfied by* asserting ids
  are unique within one tree, which a path-only id also satisfies; and *not
  satisfied by* testing the service refusal with a syntactically invalid id,
  which never proves ownership is checked.
- **BR-G-2 — The emitted array carries the structure interfaces need.** Assert
  every node exposes pre-order position, depth, parent index, subtree extent,
  and stable id→position lookup. Stage 6's BR-G-34 then asserts a
  collapse/filter/search pass over it references no path string except for
  display matching. *Not satisfied by* deriving a missing parent or subtree
  boundary inside the presentation layer; the point is that the array makes
  path arithmetic there unnecessary.
- **BR-G-3 — The promotion changed nothing.** The planner's pre-existing test
  file passes unmodified, and a diff of the three helpers shows relocation
  only. *Not satisfied by* new tests written against the promoted helpers,
  which cannot detect a behavior change the planner depended on.

**Lane B — scan scope** (the data-corruption lane)

- **BR-G-4 — Nested roots record their own keys.** A subtree scan rooted at
  `Photos\2024` records `PHOTOS\2024\IMG.JPG`, not `IMG.JPG`. Assert the exact
  stored `rel_path_key` values, not the row count. *Not satisfied by* asserting
  the right number of rows was observed — the prefix bug preserves counts and
  corrupts keys.
- **BR-G-5 — Missing inference is bounded by the completed roots.** In a
  location holding `A\`, `B\`, and `C\`, a completed refresh of `A` alone marks
  the disappeared row under `A` missing and leaves every row under `B` and `C`
  untouched, including rows already `missing`. *Not satisfied by* a
  single-folder fixture, where a whole-location sweep is indistinguishable from
  a bounded one.
- **BR-G-6 — Hostile roots stay literal.** Roots named `100%`, `a_b`, and one
  containing `]` reconcile exactly their own subtrees. *Not satisfied by*
  asserting the query returns rows; assert that a sibling the wildcard would
  have matched is untouched.
- **BR-G-7 — Completeness is inherited, not restated.** A subtree containing
  `THUMBS.DB`, `DESKTOP.INI`, or an owned temp reconciles normally; a file
  placeholder or file reparse remains complete; each of the directory
  placeholder, directory reparse, and repeated-directory-identity conditions
  withholds all missing inference. A junction crossing from one requested root
  into another trips the shared identity guard. A structural test asserts the
  recursive path routes through the shared full-walk helper so a newly added
  incompleteness cause propagates without a doc edit. *Not satisfied by*
  enumerating today's causes only in a subtree-specific implementation or test,
  which reproduces the closed-list bug one layer down.
- **BR-G-8 — Absence and unavailability are distinguished at the root.** A
  deleted root is conclusive and marks its former subtree missing; a
  permission-denied root is `ROOT_UNAVAILABLE`, incomplete, and marks nothing;
  the warning names the failing root. A root that is now a file is recorded as
  a file. *Not satisfied by* testing only the deleted-root case, which passes
  even when both are caught together and treated as absent.
- **BR-G-9 — The receipt covers the scope.** Two `InventoryCommand`s sharing
  `location_id` and `scope_token` but carrying different `subtree_roots` are not
  deduped against each other — concretely, the second raises `TokenConflictError`
  rather than returning a silent `NOOP`. **This gate is checkable only at the
  recorder**, not through `NamiSyncService`: the facade mints
  `request_id = uuid4().hex` per dispatch and `run_inventory` sets
  `scope_token = request.request_id`, so two facade-level refreshes can never
  collide on a receipt key regardless of whether the roots participate in the
  hash. *Not satisfied by* a facade-level test, which passes with the
  payload-hash work not done at all; and *not satisfied by* asserting a replay
  of the identical command is a `NOOP`, which is the naive assertion this gate
  exists to rule out.
- **BR-G-25 — Scope normalization preserves the union's meaning.** A mixed
  request containing exact rows and recursive folders canonicalizes overlapping
  subtree roots by segment ancestry, preserves an exact file outside those
  roots, and does **not** recursively expand an exact directory row. Selecting
  the location root produces `FULL`, not a degenerate `SUBTREES`; duplicate ids
  do not duplicate subjects. Canonicalization work over many sibling roots and
  exact paths remains proportional to the declared path depth rather than
  comparing every path with every root. *Not satisfied by* testing each scope
  form in isolation, where a lossy "convert everything to roots"
  implementation passes; and *not satisfied by* five-item fixtures that hide a
  quadratic admission-time walk.
- **BR-G-26 — Every reconciled presence state takes the intended branch.** A
  completed subtree refresh marks disappeared `present` and `unsupported` rows
  inside its exact-path/root union missing, preserves already-`missing` rows,
  and leaves all rows outside the union byte-for-byte unchanged. An incomplete
  refresh marks none of them missing. If one root in a multi-root request is
  incomplete, missing inference is withheld for the whole combined receipt,
  including a different root that looked conclusively empty. *Not satisfied
  by* counting missing rows without asserting the before/after state of every
  in-scope and out-of-scope fixture row.
- **BR-G-27 — Reconciliation seeks literal ranges through the declared index.**
  The representative subtree predicate is
  `rel_path_key >= root || '\' AND rel_path_key < root || ']'`; an
  `EXPLAIN QUERY PLAN` assertion proves SQLite searches through
  `inventory_location_presence_idx` with the location, presence, and key range
  constrained. The hostile-root fixtures from BR-G-6 execute through this exact
  path. *Not satisfied by* a `LIKE` query with escaping, an index merely present
  in the schema, or a plan that reports a scan.
- **BR-G-28 — Inventory and integrity codecs version independently.** Inventory
  v2 round-trips and rejects v1; integrity v1 still round-trips; a wrong-kind
  body is rejected at either version; and the shared validator's version guard
  is proven kind-aware and exact-type (`2.0`, `"2"`, and `true` do not denote
  inventory v2, with the equivalent malformed integrity-v1 cases rejected).
  *Not satisfied by* separate test-only decoders or by testing only the two
  accepted payloads, which misses cross-kind and coercible-version acceptance.

**Lane C — selection semantics**

- **BR-G-10 — Provenance survives the payload.** Payload v4 round-trips
  `user_deselected` through a real pause and resume; direct choices settle
  `SKIPPED` and dependency fallout settles `DEFERRED` **after** the round trip,
  not only before it; v3 is rejected. *Not satisfied by* asserting the field
  encodes and decodes, which a payload that is never consulted also satisfies.
  Additionally: a continuation whose `selection` differs by one operation from
  `derive_execution_selection(plan, user_deselected=…)` is refused before
  execution preflight with no filesystem mutation — and that refusal is injected
  on **an execute resume and a verify resume**, not only on a fresh submission,
  so the resumed run still finishes `FAILED+RAN` rather than a fresh
  `REFUSED+UNRUN` (XV-7's contract). *Not satisfied by* the commitment digest
  check, which compares the carried selection against a digest computed from
  that same carried selection and is therefore circular.
  The pause/resume proof drives the real dispatcher snapshot/reopen path. A
  real-ledger tampered verify continuation must also settle the already-open
  run terminally; it may not re-begin recording from the tampered selection and
  strand the run on a start-token conflict.
- **BR-G-11 — `all-noop` reads kinds, not outcomes.** Run as a **classifier-level
  unit test** over a constructed `OperationResult`/selection pair, not as an
  end-to-end session: the live path may make a divergence unreachable, and a
  gate that cannot express its own counterexample proves nothing. Assert that a
  result whose items are one `NOOP` settling `SKIPPED` plus one user-deselected
  `COPY` settling `SKIPPED` classifies `all-noop`, while one whose items are a
  single user-deselected `COPY` settling `SKIPPED` does **not** — the outcome-based
  predicate cannot tell those apart and the kind-based one must. Separately, a
  selection emptied by user deselection is refused before admission. *Not
  satisfied by* any case in which the current outcome-based predicate returns the
  same answer as the corrected one — the gate must contain at least one input on
  which the two disagree. The corrected predicate's other consumer is
  DR-BR-16.2's retained-history aggregate, which must reach the same verdict from
  persisted `kind`/`reason` columns. In addition to the classifier
  counterexample, a service-level test admits a nonempty all-`NOOP` plan,
  executes it, records its items, and returns `all-noop`; an all-skipped plan is
  refused before admission. *Not satisfied by* treating both as empty work or
  by proving only the pure classifier.
- **BR-G-12 — Safety exclusions are unreachable, and reselection closes upward.**
  On a graph containing both dependency directions, directly deselecting an
  operation adds only that id to `user_deselected`, cascades the effective
  exclusion through every dependent, and labels the fallout
  `BLOCKED_DEPENDENCY`; reselecting a child of a safety-blocked parent leaves
  the child excluded. A mutation naming a safety-excluded or unknown id is
  refused rather than absorbed. Separately — DR-BR-02's half — reselecting a
  deselected file *under a user-deselected folder* also clears that folder's
  `MKDIR` from the user set, so the child is selected in the very next
  derivation rather than immediately re-excluded as `blocked-dependency`.
  *Not satisfied by* storing dependency fallout in `user_deselected`, asserting
  the final selection only after a deselect-only sequence, or exercising the
  blocked-parent case without the upward closure.
- **BR-G-13 — A replan discards.** A replan of an unchanged tree — reproducing
  identical operation ids — after at least one operation has first been
  user-deselected resets the selection, **advances** the revision, and produces
  the default `selection_digest`. A replay of the recognized old gesture is a
  `NOOP`; a new mutation, Execute, or confirmation carrying the old revision
  conflicts. A mutation racing replacement may not return an old-artifact
  `applied` response. *Not satisfied by* replanning an untouched default
  selection, whose digest is allowed to be identical; and *not satisfied by*
  asserting the UI shows a message.
- **BR-G-24 — A folder gesture covers the subtree, not the viewport.** A folder
  deselect over a subtree whose descendants are split by a collapsed ancestor
  removes every operation at or under that path, and the folder's rollup counts
  are identical whether or not descendants are collapsed. *Not satisfied by* a
  fully-expanded fixture, where subtree scope and rendered scope are
  indistinguishable. A safety-disabled descendant is skipped during folder
  expansion rather than refusing the selectable siblings; naming that disabled
  operation directly still refuses. The filter half of this invariant cannot
  be gated until filters exist and is carried by slice 4's gate; this is the
  inventory-side clause's missing twin on the selection side.

**Lane D — facade**

- **BR-G-14 — The revision protocol cannot diverge.** A mutation at a stale
  revision applies nothing and returns conflict with the current revision; a
  no-op batch still advances the revision; a deselect-then-reselect cycle
  advances it while reproducing the prior digest. *Not satisfied by* comparing
  digests, which cannot observe an applied no-op.
- **BR-G-15 — Admission failure is recoverable.** Fault-inject
  `Dispatcher.submit` to fail; assert the selection returns to `reviewing`,
  Execute is available, and no session exists. Then assert a concurrent Execute
  during `committing` yields exactly one session. *Not satisfied by* the happy
  path, where the three states are indistinguishable from two.
- **BR-G-16 — Mutating commands are retry-safe.** A replayed gesture applies
  exactly once. Assert the actual disposition sequence rather than an equality:
  the first call reports `APPLIED` and the replay reports `NOOP`, because
  `_command_receipt` maps a prior `APPLIED` to `NOOP`; both are success and only
  the first reflows the list (DR-BR-20). A replayed multi-row gesture applies
  each row exactly once without raising. A replayed session-creating command
  yields **one** session, not two, including two concurrent first deliveries of
  the same command id. An id-based retry checks its canonical raw gesture
  receipt before rereading mutable inventory, so a disappeared row or changed
  subtree cannot defeat replay. The folder-integrity freeze is taken inside the
  same single-flight validation that resolves the ids. The service-held receipt
  survives while that session is retained, is removed by `close_session`, and
  is cleared at shutdown without a late admission repopulating it. *Not
  satisfied by* asserting
  acknowledge works, which a non-idempotent implementation also passes on first
  call; and *not satisfied by* asserting the two calls return the same value,
  which is false by construction.
  **The projection-revision clause is deliberately not here** — the cached
  projection is Stage 6 slice 6, and a Stage 5.5 gate over an object Stage 5.5
  does not build is satisfiable by a counter nothing advances. It is BR-G-23.
- **BR-G-17 — CLI compatibility remains explicit.** The original lane merge
  kept `tests/test_cli.py` byte-identical, proving that facade integration did
  not silently rewrite existing expectations. The integrated adversarial pass
  then adds one permanent real-CLI regression for the newly exposed
  `confirmation-required` admission: a typed `execute` on an effective
  irreversible update renders the risk, supplies an exact boolean
  acknowledgement, completes without an admission-view crash, and updates the
  target. Existing M0 sync/history and Stage 5 location-command tests remain
  behaviorally unchanged. An omitted revision is accepted only for an
  untouched default selection. *Not satisfied by* adapting broad expected
  output to hide a signature break; and *not satisfied by* running only the M0
  subset, which never touches location commands or the destructive-risk path.
- **BR-G-20 — Destructive risk is computed from the effective selection.** A plan
  containing one `UPDATE` with `trash_on_update` disabled reports
  `requires_destructive_confirmation` true and `irreversible_update_count` 1;
  deselecting exactly that operation flips the flag false and the count to 0
  with the plan unchanged; a `MOVE_UPDATE` never contributes to either. *Not
  satisfied by* an all-selected fixture, where a flag computed over the plan's
  operations and one computed over the effective selection are
  indistinguishable — which is the specific wrong answer DR-BR-03 names.
  Admission accepts an exact boolean acknowledgement only; a truthy string such
  as `"false"` is rejected rather than bypassing the confirmation.
- **BR-G-21 — The commitment's terminal states are observable.** A mutation
  against a `committing` or `committed` selection returns a response distinct
  from a revision conflict, and the client can tell the two apart without string
  parsing. A concurrent Execute observing `committing` receives a named
  in-flight response rather than an error or a silent drop. `committing` always
  resolves: assert that an exception escaping the submit leaves the state
  `reviewing`, not occupied. *Not satisfied by* asserting only that exactly one
  session exists, which says nothing about what the second caller was told.
- **BR-G-18 — Incompleteness reaches the facade.** An incomplete refresh
  delivers typed warnings with code, path, and detail through
  `InventoryDetailsView`. *Not satisfied by* asserting `complete is False`,
  which is precisely the reduction this work exists to undo.
- **BR-G-29 — Every promised location command crosses the real facade.**
  `acknowledge_inventory`, `restore_inventory`,
  `list_unacknowledged_missing`, and `list_stale_inventory` are each driven
  through `NamiSyncService` and return primitives-only views. Refresh,
  baseline, verify, and rebaseline each accept owned row ids and folder ids,
  union and deduplicate mixed ids, refuse empty and foreign-location
  collections, freeze integrity folders to exact subjects before admission,
  and continue a folder operation past one unreadable frozen subject while
  emitting that subject once as `unsupported` and keeping the run explicitly
  verification-incomplete. Cancellation or non-subject-specific incompleteness
  still refuses before hashing. *Not satisfied by* testing
  `LocalWorkflowRuntime` directly,
  by covering only one of the four lifts or four location commands, or by
  resolving ids in a test helper before calling the service.

**Stage 6 — deferred here because their object does not exist until then**

- **BR-G-22 — The projection patch is a single critical section.** Two concurrent
  acknowledges against one `view_id` both survive in the resulting projection; a
  patch racing a full rebuild never resurrects pre-rebuild structure; a patch
  whose base revision no longer matches is dropped rather than applied over newer
  structure. *Not satisfied by* asserting the swap is atomic, which is true of a
  read-modify-write that has already lost the other writer's patch.
- **BR-G-23 — The revision guard refuses a superseded view.** A command formed
  against a projection revision the server has since advanced is refused as
  stale and the client re-reads; the refusal is distinguishable from a receipt
  replay. *Not satisfied by* a monotonic counter nothing advances, which passes
  every assertion in a test that never invalidates.
- **BR-G-30 — The host assumptions are measured before they become
  architecture.** On supported Python 3.13 and the pinned pywebview range, the
  spike records real `CoreWebView2` reachability, pythonnet event-handler syntax,
  the asset-server origin actually observed at runtime, and off-thread
  `current_url` behavior. It proves that native access/attachment occurs on the
  synchronous WinForms `before_load` callback rather than a setup or bridge
  worker, and that dispatch authority follows cached native committed
  `CoreWebView2.Source` across a canceled off-origin navigation rather than the
  poisoned managed `Source`/`get_current_url()` value. It also records the
  pinned host's internal result-return transport and proves a canceled
  navigation can trigger reinjection/callback loss. Its rerun also invokes
  `window.open('https://example.invalid/')` from the packaged page through
  pywebview's real first popup handler and NamiSync's later guards, proving no
  system browser launch, no document replacement, and a working subsequent
  bridge call. *Not satisfied by*
  documentation lookup, a mock `Window`, a different Python/runtime
  combination, a native property read from a worker, an origin test that never
  attempts and cancels navigation, or a source scan confined to NamiSync code.
- **BR-G-31 — The packaged host keeps its security and process boundaries.**
  A built installation prepares pywebview before `create_window`, using only
  read-only registry access through the upstream-parity compatibility detector
  to reject missing WebView2 before pywebview can import MSHTML, and pins
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False`,
  `ALLOW_FILE_URLS=False`, `ALLOW_DOWNLOADS=False`,
  `REMOTE_DEBUGGING_PORT=None`, and `debug=False` before native startup; opens
  only on Edge Chromium; and attaches top-level navigation, all-frame,
  new-window, and source guards on the UI thread before app data is accepted.
  It makes swallowed attachment failure observable and tears the window down
  actionably; rejects a missing or incompatible WebView2 with an actionable
  message; rejects an off-origin committed native source independently of
  navigation hardening; routes both console/package-module entry points through
  `interfaces/launcher.py` without importing the web adapter; and exposes
  `nami-sync-gui` through that same launcher as a GUI-subsystem entry point.
  No-subcommand console use prints usage and points to the GUI launcher.
  Explicit CLI subcommands do not import or initialize pywebview. A second
  desktop launch activates the existing window
  and exits successfully; activation failure is visible and still non-error.
  The real packaged-page popup composition leaves the page and bridge usable
  without opening a system browser. *Not satisfied by* running from a source
  checkout, guarding only navigation, testing popup handlers separately, or
  importing `web` lazily from `cli`.
- **BR-G-32 — The transport is one allowlisted, inert-data channel.** Slice 2
  proves every public view type round-trips through the production JSON codec
  and the one exposed `dispatch(command_json)`; the two Slice 2 rows are exactly
  `pick_folder` and `start_plan`, and the thaw/refreeze allowlist adds the
  foundation-only readiness rows `shell_ready` and `readiness_echo`, Slice 3's
  `next_events`, plus
  lifecycle-only `release_terminal_session` and `close_task`, and the
  pre-Slice-5 cosmetic rows `read_cosmetic_section` and
  `replace_cosmetic_section`, while
  `test_report` is possible only through test-owned
  constructor composition. Host composition, rather than transport, joins the
  final command mapping to current-document readiness through an exact opaque
  admission verdict; the bridge retains only document trust, request bounds,
  handler reservation, and serialization. Unknown versions, commands,
  fields, malformed opaque ids, and input above 65,536 UTF-8 bytes are refused
  before handler invocation. Errors expose no filesystem path or internals even
  though pywebview otherwise returns Python tracebacks. The native picker keeps
  its path in the bounded server slot table, returns only `{id, display}`,
  accepts only purpose-matching live ids through dispatch, and refuses a
  fabricated id without making display text authoritative. The scanner's
  complete hostile-name corpus crosses page JavaScript, the real pinned
  pywebview return transport, and the production inert-text path in the headed
  harness byte-for-byte, while the broadened DR-BR-25 packaged-asset sink scan
  is empty. Slice 4 adds the final filesystem-label layout projection and exact
  installed DOM/accessibility marker corpus without changing raw transport or
  opaque callback ids. Those clauses close Slice 2's transport, picker,
  origin-refusal, and static-sink portion plus Slice 4's generic tree sink.
  Slice 5 must repeat the corpora in the production plan DOM
  and Slice 6 in the production inventory DOM; BR-G-32 is not wholly closed
  until the latter lands. *Not satisfied by* a direct Python call that bypasses
  dispatch, a benign-name subset, a test-only reimplementation of the sink,
  returning a real picker path, an `innerHTML`-only source scan, or treating the
  Slice 2 harness as proof of a later production surface.
- **BR-G-33 — Event delivery remains ordered, bounded, recoverable, and
  stoppable.** Admission-time observation is adopted before `PENDING` emission;
  `PENDING` reaches that stream while work remains unschedulable, and only then
  are maps/pending publication and scheduler notification atomic. An
  attach/shutdown race rolls back the unpublished session and starts no work. Concurrent drains
  cannot reorder or split one task's sequence;
  progress coalesces behind one fixed 150 ms progress-only deadline without
  displacing or delaying reliable data; a reliable flood reaches
  the existing visible `Gap`/resubscribe path and terminal truth is recovered;
  shutdown refuses new handlers, waits for admitted handlers, and wakes drains
  and capacity-blocked producers before closing observations. A failed drain
  without a `Gap` resubscribes after the last client-accepted non-`Gap`
  sequence. Repeated progress cannot extend the deadline; reliable and terminal
  values wake it immediately. An ordinary explicit `Gap` remains visible, stops later updates,
  and resubscribes from its exact `first_missed_seq`; a recovery response's
  matching leading `Gap` proves the prefix unavailable and permits its retained
  tail without another loop
  and recovers terminal truth without a client acknowledgment, echoed cursor,
  or new server receipt. Numeric sequence holes are legal progress coalescing
  and do not themselves recover. Fault-inject a lost response containing reliable data
  and a separate lost response containing the terminal delivery; both reconcile
  through the production resubscribe/terminal-record path, while replaceable
  progress may coalesce to the latest truthful snapshot. Concurrent
  observe attempts create one subscription or a named refusal, and a
  fault-injected slow facade call proves no `TaskState` lock is held across it.
  Repeated `pywebviewready` firings while a drain is outstanding install one
  listener set, retain at most one drain per task, pause it while the new
  document is presentation-pending, and re-arm delivery exactly once after
  that bridge generation becomes operational. The transport fault gate's
  synthetic return-table loss stays explicitly renderer-only: it resets the
  JavaScript bridge while the already-open native document generation remains
  unchanged, and does not stand in for the separate production startup and
  native reinjection evidence.
  *Not satisfied by* a single drain, a naturally finishing session, one task,
  or a queue that stays below capacity.
- **BR-G-34 — One visible-sequence implementation defines both trees.** The
  same pure flattener produces plan and inventory windows from the ordered array
  under expanded/collapsed, filter, and casefolded-display-substring search
  combinations. Changing parameters replaces one active sequence rather than
  retaining a parameter-keyed family. A container appears only for a directly
  matching node or matching descendant, and collapse hides descendants only
  after matching. Search treats regex metacharacters literally, matches the
  casefolded display form only, accepts 65,536 UTF-8 bytes, and refuses 65,537
  before traversal. The bridge's separate 65,536-byte complete-envelope bound
  and every future external adapter's ingress bound remain authoritative.
  Sparse caller-owned match counts are validated but their domain
  vocabulary is not interpreted here. The default is expanded, fixed row
  height is enforced, 256 rows are accepted, and 257 are refused rather than
  truncated. The workflow-owned node array is consumed directly without a
  second complete DTO copy. Anchor lookup uses the same derived sequence and
  exact deepest-to-root id chain and performs work proportional to chain depth,
  not tree size. Plan and inventory cases must start from real
  `build_node_tree` output and retain object identity; hand-built generic arrays
  alone do not close the gate. The positive renderer witness uses the same
  canonical temporary JSON bytes generated through `build_node_tree` ->
  `derive_visible_sequence` -> `window_visible_sequence` ->
  `to_visible_window_view` in both the direct Node probe and installed WebView2
  child. Python, child, and page SHA-256 values must agree. Its cases cover the
  `head`, `next`, `tail`, `empty`, `maximum`, and `layout_control` windows,
  expansion tri-state across the pointer and projected-empty windows, and
  ordinary-Unicode and long-label values in `next`;
  independently authored positive row dictionaries are insufficient evidence.
  The separate renderer-local control corpus tests the fixed sink set without
  pretending invalid Windows filename characters traversed `NodeTree`. The
  bounded window carries server-derived parent/child/sibling accessibility
  metadata. Boolean expansion exists only
  for a projected parent with a retained immediate child; leaves and filtered-
  empty containers carry `null`. A static assertion proves the
  implementation calls no path helper and reconstructs no parent or descendant
  relationship from display text. *Not
  satisfied by* filtering an already-windowed page, searching the canonical
  key, accepting an arbitrary callable as filter policy, or separate plan and
  inventory flatteners fed the same fixtures. The realignment regressions, full
  20,000-container/100,000-leaf retained-representation witness, and
  deterministic linear field-access guard now pass. These are structural
  evidence, not latency acceptance; broader BR-G-42 product-view measurements
  remain with Slices 5-7. Display strings remain byte-exact in the Python
  sequence/wire/search seam; visible `⟦U+XXXX⟧` layout markers are a final
  renderer projection and marker spelling has no query syntax. The production
  renderer regressions additionally
  cover coalesced leading/trailing spacer paging, exact row-boundary math,
  external-projection priority, keyboard-versus-newer-scroll ordering,
  covered-window cancellation, callback failure, stale-payload refusal before
  access, preserved scroll position, a one-row valid response that cannot
  self-retry for an unchanged viewport, changed-viewport convergence, and a
  fully visible presentation-only active descendant. The installed-wheel SH-G-7 witness sends a native CDP
  mouse-wheel gesture through a four-row viewport, accepts a five-row page
  spanning both viewport edges, and proves the viewport remains nonblank
  while the activation recorder remains empty. Those are functional regressions, not latency
  measurements. The shared manifest binds current Python projection output to
  the installed generic renderer; it neither exercises a Slice 5/6 plan or
  inventory bridge command nor closes their product-DOM or BR-G-42 latency
  gates.
- **BR-G-35 — Plan presentation preserves operation truth while compressing
  moves.** This is also the first consumer that proves a filtered move ghost
  removes its synthetic-only ancestor chain, an ordinary real operation keeps
  its folder visible on its own merits, folder rollups remain the original
  unfiltered values, and each filter chip count describes filtered domain items
  rather than structural ancestors. The plan tree memo is byte-stable per request and is dropped with the
  plan; selection overlays do not rebuild its structure. Move annotation uses
  the union of target and prior-target ancestors, keeps the ordinary folder
  selection scope and original operation kinds, emits a noninteractive old-path
  ghost only when no real node exists there, annotates the real old node when it
  does, and suppresses nested ghosts. Synthetic node ids never enter execution,
  persistence, or a selection digest. The production plan DOM passes DR-BR-25.
  *Not satisfied by* a move-only happy path, a synthetic operation standing in
  for a folder, or a renderer that relabels inferred groups as renames.
- **BR-G-36 — Progress compatibility and follow mode use identity, never
  display paths.** A pre-change Progress body lacking the four optional item
  fields decodes through `.get(...)`; a new body serializes all four;
  one-sided identity/counter pairs, coercive counters, and unknown types are
  rejected; and both production reporters emit the correct nominal pair plus
  determinate stream counters without changing the current envelope version. An
  off-window item resolves through its server-supplied
  ancestor chain to the deepest visible ancestor-or-self and exact visible
  index under collapse, filter, and search; the window and anchor-only paths
  call the same resolver. User scrolling disables follow until explicit resume.
  A static/counterexample test proves `current_path` is never used for identity
  or lookup. *Not satisfied by* testing only a currently materialized operation
  or by joining an id to a matching display path.
- **BR-G-37 — Virtualization cannot own or narrow selection.** Rows destroyed
  and recreated by scrolling recover the server's current selection; a folder
  gesture covers filtered, collapsed, and off-window descendants; tri-state
  values and rollups come from the server; and `preview_selection` calls
  `derive_execution_selection` directly rather than `get_plan_review`. A burst
  of toggles enters visible pending state, batches within the configured
  120–150 ms interval as one mutation and one revision advance, and resolves
  conflict by re-read rather than optimistic local repair. Execute is
  unconfirmed unless the effective selection carries the irreversible risk from
  BR-G-20. *Not satisfied by* a fully materialized, unfiltered tree or one click
  per debounce interval.
- **BR-G-38 — The inventory projection pays whole-location work once per
  lifecycle.** A slim explicit-column query builds one immutable projection per
  `view_id` without constructing full `InventorySnapshot`s; detail queries
  fetch only the visible row ids. Rebuild occurs outside the service lock and
  swaps inside it. Concurrent patches and patch-vs-rebuild races satisfy
  BR-G-22; unchanged node objects and position indexes retain identity after a
  one-row patch; session terminal causes a rebuild. Two views of one location
  remain independent, six projections are retained LRU, the seventh evicts the
  least-recently-used one, and location change, task close, and service shutdown
  release their views. Eviction and invalidation take the same stale-revision
  client path. *Not satisfied by* rebuilding on every page, deep-copying every
  node, guarding only the immutable value rather than the cache map, or testing
  fewer than seven views.
- **BR-G-39 — Inventory interaction exposes all observed truth and exact
  scope.** The five XV-14 resolution states render distinctly; incomplete
  refresh shows each typed warning's code, path, and detail; row actions remain
  exact while folder refresh is recursive and folder integrity freezes all
  indexed descendants regardless of filter. Each integrity action reports the
  count it actually selected after mode eligibility. One unreadable frozen
  descendant produces one visible `unsupported` item and an incomplete
  verification axis while every other eligible subject proceeds.
  Acknowledge hides the row by default, changes no ancestor rollup, refetches
  the shifted window only on `APPLIED`, and updates missing/acknowledged chip
  counts; restore is reachable through the acknowledged filter. No view-open or
  timer path auto-scans. The production inventory DOM passes DR-BR-25. *Not
  satisfied by* a generic warning chip, a descendant count predicted before
  mode selection, or a default view that still contains acknowledged rows.
- **BR-G-40 — History work is paged before object decoding and preserves
  classification.** The summary query count is fixed and its indexed primitive
  aggregate produces one fixed-size fact object per run without selecting or
  decoding canonical event JSON; free-form kind/reason values cannot expand
  summary retention, and workflow code, not `db`, interprets those facts. Item
  and reliable-event detail use immutable keyset
  order and one captured committed watermark, terminal phases have an explicit
  256-row ceiling, adjacent headline precedence remains XV-10 exact, and
  retained `all-noop` matches the live kind/reason classifier including
  `USER_DESELECTED`. `EXPLAIN QUERY PLAN`, query-count, and decode-spy
  assertions pin the bounded path. Limits 1 and 256 succeed; 0 and 257 are
  refused rather than truncated.
  *Not satisfied by* a compatibility getter that materializes a whole run, or
  by matching only the final headline of an uncomplicated run.
- **BR-G-41 — Task and process lifecycle lose neither work nor authority.** A
  reviewed task exists without live work; a terminal plan session is absent
  from the active rail. Its record/replay authority survives until successful
  terminal presentation, then session release removes that live authority while
  the plan artifact, task/start identity, and presentation state survive until
  explicit task close; compound phases remain one session with independent
  counters. Closing a live task asks once, enters
  visible closing, cancels, waits for a terminal **record**, then unsubscribes,
  closes, and releases the exact task-owned plan, selection, execution/inventory
  detail, view/projection, session, and receipt artifacts; refusal leaves it
  open. Plan-only and already-terminal tasks release immediately. A delayed
  terminal leaves the card visibly closing without prematurely closing the
  session or dropping artifacts. Repeated create/close cycles keep facade,
  runtime, bridge, and adapter registries bounded while retained history remains
  readable. The rail renders `pausing` distinctly until `paused` or terminal,
  with repeat pause/resume disabled and cancel still available. Closing a
  terminal task asks nothing. `ui-state.json` round-trips only registered typed
  cosmetic sections — beginning with appearance and later adding file-list
  expansion state only after its durable key is ratified — but never serializes a plan request id, session id,
  task identity, selection, `view_id`, or projection revision; corruption
  recovers with defaults while unsupported newer state is preserved. Settings
  round-trip through the service;
  invalid values do not poison the file, and changed semantics affect the next
  plan but never an already committed one. Shutdown under concurrent dispatch
  satisfies DR-BR-24 and XV-18. *Not satisfied by* cleanup triggered by the
  terminal event, by releasing only the plan, by a task rail reconstructed only
  from `list_sessions()`, or by a clean idle shutdown.
- **BR-G-42 — The named scale envelope passes fixed budgets.** The
  implementation records every row below against the predeclared fixtures and
  profile. Ordinary pytest proves deterministic shape/query/decode/allocation
  bounds; the owning benchmark records raw samples, source, machine/runtime,
  fixture seed, statistic, run count, p95, and maximum. Sizes and ceilings may
  not be selected after observation.

  **Reference profile and sampling.** Windows 11 Pro build 26200; Intel
  i7-13700K (16 cores/24 logical processors); 63.7 GiB RAM; repository,
  fixtures, and SQLite on a WD_BLACK SN850X 4 TB NVMe; CPython 3.13.14 and
  SQLite 3.50.4; AC power with no unrelated sustained workload. P95 rows use at
  least 30 warm samples; cold maxima use at least five fresh-process or
  cold-projection samples.

  | Fixture | Required shape |
  | --- | --- |
  | Plan | 100,000 operations plus up to 20,000 folder nodes; dependency/path depth reaches 32 |
  | Inventory | 100,000 file rows plus up to 20,000 directory rows in one location |
  | History | 50 run summaries covering 1,000,000 retained items, including one 100,000-item run |
  | Projection retention | Six populated 120,000-node inventory projections, then a seventh view to force LRU eviction |
  | Events | Four active tasks for 60 seconds at 100 aggregate `Progress` events/s plus 10 aggregate reliable events/s |

  | Measurement | Ceiling and authority |
  | --- | --- |
  | Local critical-click feedback | 50 ms maximum; Tier 0 target, Tier 2 Slice 5/6 acceptance |
  | Typed execute/control/one-row receipt, excluding admitted work | 100 ms p95, 250 ms maximum; Tier 0 target, Tier 2 owning-slice acceptance |
  | Freeze/normalize a 100,000-subject scope | 500 ms p95, 1 s maximum; Tier 0 target, Tier 2 owning-slice acceptance |
  | Reliable/terminal delivery under event fixture | 100 ms p95, 250 ms maximum, no `Gap`; current-source Tier 2 timing remains open |
  | Replaceable progress delivery | 1 s p95, 2 s maximum, monotonic after coalescing; current-source Tier 2 timing remains open |
  | Cold 120,000-node plan projection | 2 s maximum; Tier 2 Slice 5 acceptance |
  | Cold 120,000-node inventory projection | 3 s maximum; Tier 2 Slice 6 acceptance |
  | Unchanged-parameter 256-row window | 250 ms p95, 500 ms maximum; Tier 2 Slice 5/6 acceptance |
  | Changed search/filter/collapse plus 256-row window | 750 ms p95, 1.5 s maximum; Tier 2 Slice 5/6 acceptance |
  | `preview_selection` at depth 32 | 500 ms p95, 1 s maximum; Tier 2 Slice 5 acceptance |
  | Fifty-run/1,000,000-item history summary | 3 s maximum; Tier 2 Slice 7 acceptance |
  | 256-row history detail window | 500 ms p95, 1 s maximum; Tier 2 Slice 7 acceptance |
  | Incremental plan projection memory | 128 MiB maximum; Tier 2 Slice 5 acceptance |
  | Incremental inventory projection memory | 192 MiB each, 1,152 MiB for six; Tier 2 Slice 6 acceptance |
  | Identity-deduplicated transport custody | 1,966,080 bytes; frozen protected authority plus Tier 1 live guard |
  | Terminal artifacts plus completed-task retention | No derived bound yet; BR-G-45 remains open |

  **Transport-custody clause.** Custody is the identity-deduplicated live graph
  rooted at dispatcher replay deques, subscriber deques, and adapter task
  queues. It includes containers and nonterminal event values. A terminal value
  occupies its queue slot, but the subject-scaled result graph is cut and
  charged to BR-G-45. The instrument reports every root class and their
  deduplicated union; payload bytes and whole-process memory are invalid
  substitutes.

  The frozen `sh-g-8-transport-v1` corpus drives four tasks through the
  production dispatcher/service/task-registry path, covers the ordinary
  60-second rate and exact per-task 128/64/64 maximum no-`Gap` custody shape,
  and requires ordered cleanup plus exact terminal truth. The authoritative
  corpus, calibration, ceiling, holdout, validator, and live-guard files are
  `tests/bridge_transport_custody.py` and
  `tests/interfaces/web/sh_g_8_transport_*`; `TOOLS.md` explains their use.
  The frozen ceiling is 1,966,080 bytes. Calibration never validates its own
  limit, and later representations must select authority anew under
  `DEFENSE.md` §7.

  **Status.** Event correctness and transport custody are closed by the frozen
  calibration/ceiling and independent holdout recorded in
  [Close transport custody and realign the bridge boundary](../CHANGELOG.md#close-transport-custody-and-realign-the-bridge-boundary-2026-08-13--2026-08-14).
  Current-source event timing and the Slice 5–7 product-view rows remain open on
  their owning slices. BR-G-45 terminal retention and shell-owned SH-G-15
  whole-runtime containment are separate gates. *Not satisfied by* changing
  fixtures after measurement, reporting averages in place of the declared
  statistic, using empty history runs or shared short strings, omitting a
  custody root/high-water mark, including terminal artifacts in custody, or
  treating payload/whole-process bytes as the retained transport graph.
- **BR-G-45 — Terminal artifacts and completed-task retention are bounded
  separately.** First define a bounded production representation and enforce
  per-completion plus aggregate completed-task budgets over the exact
  100,000-subject admitted domain. The complete per-completion artifact set is:
  the core `Terminal(OperationResult.items)` retained by dispatcher custody,
  its adapter `SessionEventView`, the terminal `SessionRecordView` and
  `OperationResultView.items`, serialization/native return values, browser
  retry/presentation copies, and the post-callback representation. Checked
  production maxima for every retained representation, subject-scaled field,
  node/depth family, and aggregate budget must derive the analytical containment
  bound without either omission or double-charging. A separately identified
  native or renderer copy that production cannot bound analytically is an
  empirical residual and must receive its own tier and evidence. Construction,
  delivery, presentation, release, and settlement latency remain separately
  classified so a memory pass cannot hide a frozen window.

  A separate aggregate policy fixes the maximum completed-task bytes and exact
  representations retained before presentation, during callback or release
  retry, after successful `release_terminal_session`, and after explicit
  `close_task`. It preserves the reviewed plan, exact retry authority, and a
  truthful result when durable history is degraded. Repeated complete/release/
  close cycles and the maximum permitted completed-task set must remain within
  the enforced budget and release retained state at the declared boundaries; a
  task-count cap alone is not a byte policy. **Current
  status: OPEN.** No bounded production representation, enforced aggregate
  policy, complete-domain analytical proof, or separately justified empirical
  residual acceptance has landed. *Not satisfied by*
  measuring only `SessionRecordView`, excluding the full terminal event,
  reusing one interned path/detail value, measuring an empty/summary result,
  clearing truth before its presentation/retry boundary, assuming degraded
  history can reconstruct it, or treating SH-G-8/SH-G-15 as substitutes.
- **BR-G-46 — Cosmetic state is typed, bounded, non-authoritative, and visually
  coherent.** The exact nine-row native mapping and browser policy mirror
  agree on both cosmetic rows, their `OPEN` phase, five-second deadline,
  field requirements, read-only uncertainty replay, and replacement read-
  reconciliation policy.
  Focused tests prove the complete revision decision table, concurrent
  serialization, 250 ms coalescing, single-attempt failure behavior, guarded
  close flush, subscriber isolation/order, the 1 MiB read/write bounds, strict
  and duplicate-key decoding, forward-version preservation, and atomic
  replacement. Fault injection proves an accepted in-memory value survives a
  failed save without leaking path, payload, exception text, or traceback.

  Cosmetic reads and replacements leave semantic `settings.json`, service,
  registry, planner, plan fingerprints, tasks, and sessions untouched;
  pre-`OPEN`, off-origin, oversized, and malformed requests produce no state or
  file mutation. The product loads the initial override before window creation,
  then headed installed-WebView2 evidence proves the selector reconciles only
  accepted state and light/reduced versus dark/forced gallery modes agree across
  native material and page tokens. Raw Windows appearance remains distinct,
  high contrast temporarily wins, and accent/reduced-motion values stay
  system-owned. No bridge oracle or compositor sentinel is required: exact
  native policy/static tests, fault-directed material tests, and the installed
  transport/gallery witnesses jointly own this gate. The typed owner, exact
  two-row bridge channel, appearance consumer, and named headed selector
  witness are active; **gate status: complete.** *Not
  satisfied by* changing page CSS alone, seeding gallery DOM state after window
  creation, persisting a
  permissive dictionary, retrying failed I/O on a timer, or proving only the
  happy-path file round trip.
- **BR-G-43 — Documentation describes the shipped contract, not the plan.**
  `DESKTOP_UI.md`, the focused component documents, README overview/index/
  limitations/changelog, and `ui_mockup/` status agree with the implemented
  behavior and supported scale envelope. A release trace maps every active
  `DESKTOP_UI.md` acceptance item to a BR-G/test or to an explicit, already
  approved deferral; zero items are merely omitted. *Not satisfied by* marking
  this bridge implemented while active documentation still describes the
  pre-bridge CLI or mockup behavior, or by copying an unmapped requirement into
  a new prose checklist.

**Import law, gating every lane**

- **BR-G-19 — The boundary holds.** `lint-imports` passes with the launcher
  contract extension and no new `allow_indirect_imports` exemption; a static
  assertion shows no symbol under `interfaces/` calls
  `normalize_relative_path`, `validate_relative_path`, or any `core` path
  helper. *Not satisfied by* the linter alone, which permits indirect use
  through a re-export.
- **BR-G-44 — The repository closes as one system.** The complete pytest suite,
  including tests excluded by ordinary-development marker defaults, and
  `lint-imports` pass from a clean checkout with the supported interpreter;
  every `test_br_g_*` test is collected, none is skipped/xfail on Windows, and
  `git diff --check` is clean. The narrow gate and watchlist commands are
  diagnostics, not substitutes. *Not satisfied by* running only changed test
  files, deselecting slow/platform tests, or weakening an existing assertion to
  preserve green.

Stage 6 follows the same collision rule as Stage 5.5. Host/transport tests live
under `tests/interfaces/web/` in `test_host.py`, `test_native_host_gates.py`,
`test_slice1_headed.py`, `test_commands.py`, `test_transport.py`,
`test_slots.py`, `test_transport_headed.py`, `test_drain.py`, and
`test_frontend_static.py`; detector
parity lives in `tests/test_pywebview_runtime.py`; pure presentation tests live
in `test_visible_sequence.py`;
sync, inventory, and lifecycle vertical tests live in `test_sync_surface.py`,
`test_inventory_surface.py`, and `test_lifecycle.py`; scale tests live in
`tests/test_bridge_scale.py`, the event artifact validator lives in
`tests/interfaces/web/test_bridge_event_benchmark.py`, the custody-runner
contract lives in `tests/interfaces/web/test_bridge_transport_custody.py`, and
BR-G-45's focused artifact/retention cases will live in
`tests/interfaces/web/test_terminal_artifact_scale.py`; BR-G-46's typed state
and bridge/appearance cases live in `tests/interfaces/test_ui_state.py` and
`tests/interfaces/web/test_cosmetic_channel.py`. Their gate tests retain the
`test_br_g_<number>_` prefix. A slice may add narrower unit files, but moving a
gate test elsewhere requires updating this table in the same change so no
acceptance test becomes undiscoverable.

**Decision-to-gate traceability.** This is the completeness check. A DR is not
implemented because its code exists; it is implemented only when every gate in
its row and the applicable regression rows are green.

| Decision | Required gate(s) |
| --- | --- |
| DR-BR-01 | BR-G-10–13, BR-G-20, BR-G-24, BR-G-37, BR-G-40 |
| DR-BR-02 | BR-G-12, BR-G-24, BR-G-37 |
| DR-BR-03 | BR-G-13–15, BR-G-17, BR-G-20, BR-G-21, BR-G-37 |
| DR-BR-04 | BR-G-13 |
| DR-BR-05 | BR-G-16, BR-G-18, BR-G-29 |
| DR-BR-06 | BR-G-1, BR-G-4–9, BR-G-18, BR-G-25–29, BR-G-39 |
| DR-BR-07 | BR-G-7 and scanner hostile/completeness regression rows |
| DR-BR-08 | BR-G-19, BR-G-34, BR-G-36, BR-G-37 |
| DR-BR-09 | BR-G-2, BR-G-19, BR-G-34, BR-G-35, BR-G-38 |
| DR-BR-10 | BR-G-2, BR-G-3, BR-G-19 |
| DR-BR-11 | BR-G-1, BR-G-2, BR-G-23, BR-G-35, BR-G-38 |
| DR-BR-12 | BR-G-12, BR-G-24, BR-G-29, BR-G-37, BR-G-39 |
| DR-BR-13 | BR-G-34, BR-G-35 |
| DR-BR-14 | BR-G-32, BR-G-36 |
| DR-BR-15 | BR-G-2, BR-G-34, BR-G-36 |
| DR-BR-16 | BR-G-27, BR-G-34, BR-G-38, BR-G-40, BR-G-42 |
| DR-BR-16.1 | BR-G-22, BR-G-23, BR-G-38, BR-G-42 |
| DR-BR-16.2 | BR-G-11, BR-G-40, BR-G-42 |
| DR-BR-17 | BR-G-14, BR-G-24, BR-G-37 |
| DR-BR-18 | BR-G-34, BR-G-36 |
| DR-BR-19 | BR-G-34, BR-G-36 |
| DR-BR-20 | BR-G-16, BR-G-23, BR-G-38, BR-G-39 |
| DR-BR-21 | BR-G-35, BR-G-41, BR-G-45 |
| DR-BR-22 | BR-G-21, BR-G-33, BR-G-41, BR-G-45 |
| DR-BR-23 | BR-G-31 |
| DR-BR-24 | BR-G-14, BR-G-15, BR-G-21–23, BR-G-33, BR-G-38, BR-G-41, BR-G-42 |
| DR-BR-25 | BR-G-32, BR-G-35, BR-G-39 |
| DR-BR-26 | BR-G-1–3, BR-G-35 |
| DR-BR-27 | BR-G-9, BR-G-14–16, BR-G-23, BR-G-29, BR-G-33 |
| DR-BR-28 | BR-G-46 |

BR-G-19, BR-G-43, and BR-G-44 are cross-cutting release gates and therefore
apply to every row even where not repeated. Product goals 1–5 are witnessed,
respectively, by `{34,35,42}`, `{12,20,24,37,39}`,
`{18,36,39,40,41}`, `{6,32,35,39}`, and `{15,20,21,37,39,41}`.

### Regression watchlist (existing M1)

These preservation commands supplement rather than replace BR-G gates. A
changed pre-existing assertion is a regression unless its governing DR changes
the contract.

| Watch | Required command | Why it is at risk / owner |

| Watch | Required command | Why it is at risk / owner |
| --- | --- | --- |
| `XV-1`–`XV-8` compound execution, continuation, and phase truth | `.\.venv\Scripts\python.exe -m pytest -q tests/test_executor_runtime.py tests/test_executor_native.py tests/test_executor_pipeline.py tests/test_executor_settlement.py tests/test_post_execution_workflow.py tests/test_payload_roundtrip.py tests/dispatcher/test_dispatcher.py` | `ExecutionSet` and payload v4 change the handoff that must retain evidence, phase, one run, refusal settlement, and independent truth axes / C, D |
| `XV-9`–`XV-10` history vocabulary and headline precedence | `.\.venv\Scripts\python.exe -m pytest -q tests/test_db_history.py tests/test_workflow_views.py tests/test_cli.py` | The retained classifier and `all-noop` input change; every adjacent precedence edge and secondary axis must remain visible / C, Stage 6 slice 7 |
| `XV-11`–`XV-12` frozen settings and codec shape | `.\.venv\Scripts\python.exe -m pytest -q tests/test_settings_facade.py tests/test_payload_roundtrip.py tests/test_planner.py` | Commitment construction and execution payloads change; no live-settings read or removed field may return / C, D |
| `XV-13` scope completeness and recorder branch | `.\.venv\Scripts\python.exe -m pytest -q tests/test_scanner.py tests/test_recorder_inventory_integrity.py` | `SUBTREES` must not alter exact `PATHS` or fall through to `FULL`; incomplete scans infer no missing rows / B |
| `XV-14` five volume states and `XV-15` wakeup re-resolution | `.\.venv\Scripts\python.exe -m pytest -q tests/test_inventory_workflow.py tests/test_inventory_runtime.py` | Folder expansion and reshaped details must preserve five distinct states and re-resolve on resumed/woken integrity work / B, D |
| `XV-16` shared hash factory and production composition | `.\.venv\Scripts\python.exe -m pytest -q tests/test_executor_runtime.py tests/test_executor_native.py tests/test_executor_pipeline.py tests/test_executor_settlement.py tests/test_inventory_runtime.py tests/test_db_repositories.py tests/test_package.py tests/modules/test_verifier_engine.py` | Payload/runtime edits must not fork verifier construction, diverge copy from verify encoding, or import a second hash implementation / B, C |
| `XV-17` history-v4 window contract | `.\.venv\Scripts\python.exe -m pytest -q tests/test_db_schema.py tests/test_db_history.py` | Reset-only v4, append-only reliable events, atomic window/terminal visibility, incomplete restart views, and 1..256-row summary/detail bounds remain exact / B, C, Stage 6 slice 7 |
| `XV-18` observer and dispatcher teardown | `.\.venv\Scripts\python.exe -m pytest -q tests/test_service.py tests/dispatcher/test_event_bus.py tests/dispatcher/test_dispatcher.py` | New handler, projection, drain, and task lifecycles must still close streams before joins, recover terminal-before-subscribe, and terminate within bounds / D, slices 3, 6, 7 |
| `XV-19` ids-in, inert layout-honest text out, independent origin check | `.\.venv\Scripts\python.exe -m pytest -q tests/interfaces/web/test_commands.py tests/interfaces/web/test_transport.py tests/interfaces/web/test_slots.py tests/interfaces/web/test_transport_headed.py tests/interfaces/web/test_frontend_static.py tests/interfaces/web/test_visible_sequence.py tests/interfaces/web/test_shell_headed.py tests/interfaces/web/test_sync_surface.py tests/interfaces/web/test_inventory_surface.py` | The real page-JS → pinned pywebview return → sole `textContent` writer, raw Python/wire/search preservation, final filesystem layout-control markers, installed DOM/accessibility evidence, and NamiSync-owned sink scan become executable across slices 2, 4, 5, and 6; the split transport/static/visible/shell files plus both later surface files are required because one layer alone cannot prove the full chain / slices 2, 4, 5, 6 |
| `XV-20` stateless checkpoint | `.\.venv\Scripts\python.exe -m pytest -q tests/test_executor_pipeline.py` | Selection re-derivation and bridge progress must not motivate count-coupled checkpoint behavior in execution / C, slice 5 |
| M0/Stage 5 CLI behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_cli.py` | The initial Stage 5.5 lanes left this file byte-for-byte unchanged; the integrated adversarial closure adds only the permanent irreversible-update admission regression described by BR-G-17. Every prior explicit sync, history, inventory, and integrity command remains behaviorally unchanged. Slice 1 may later replace only the no-subcommand/entry-point expectations required by the launcher decision / B, C, D, slice 1 |
| Planner helper behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_planner.py` | `_depth`, `_parent`, and `_is_descendant` are pure relocations; no cleanup or semantic drift is allowed / A |
| Scanner hostile names, cancellation, and walk completeness | `.\.venv\Scripts\python.exe -m pytest -q tests/test_scanner.py` | Parameterizing the walk must preserve literal names, escaped/unrepresentable reporting, identity-cycle handling, cancellation checks, and every existing incompleteness cause / B |
| Recorder receipt, range, and transaction behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_recorder_inventory_integrity.py tests/test_recorder_concurrency.py` | Scope enters the payload hash and missing marking gains a third branch; idempotent transaction and concurrency behavior must not weaken / B, D |
| Inventory/integrity payload and pause behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_inventory_workflow.py tests/test_inventory_runtime.py tests/test_payload_roundtrip.py` | A kind-aware shared validator and expanded frozen subject set must preserve integrity v1, pause order, and incomplete-scope settlement / B, C, D |
| Service facade and import boundary | `.\.venv\Scripts\python.exe -m pytest -q tests/test_service.py tests/test_package.py` then `.\.venv\Scripts\lint-imports.exe` | New lifts, state, launcher, and web adapter must preserve primitives-only views, lazy CLI imports, shutdown order, and every layer edge / D, slices 1–3 |

A lane runs every row naming it; integration lane D runs all Stage 5.5 rows.
Each Stage 6 slice runs its named watch rows and `test_br_g_*` module. BR-G-44
requires the complete suite before each vertical slice and release:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
git diff --check
```

No bridge gate may be skipped, xfailed, xpassed, or uncollected on the supported
Windows profile. The implementation record includes collected
`test_br_g_*` ids.

### Stage 6

The table is the remaining owner/dependency sequence; the BR-G entries above,
not the slice prose, define completion. Presentation core is separated from
plan and inventory so Slices 5 and 6 can proceed in parallel.

| # | Department | Slice | Depends on | Acceptance gate |

| # | Department | Slice | Depends on | Acceptance gate |
| --- | --- | --- | --- | --- |
| 0 | Host | pywebview reality spike | nothing | BR-G-30 |
| 1 | Host | Promote the spike into `bridge.py` / `host.py`; hard dependency; packaged assets; launcher entry point; forced Edge Chromium; single instance | 0 | BR-G-19, BR-G-31 |
| 2 | Transport | Command allowlist, JSON encoding, opaque-id and folder-picker slots | 1 | BR-G-32 transport/picker/static-sink portion; the gate remains open for the production DOM |
| 3 | Transport | Event drain with coalescing, bounded wait, reliable backpressure, gap visibility, server-side drain guard | 2 | BR-G-33, BR-G-41 transport/lifecycle foundations, the closed BR-G-42 event/transport-custody portion, plus XV-18 |
| GUI 1 (completed/realigned) | Presentation foundation | Native material behavior; Fluent neutral/Windows accent roles; exact authored status palette and semantic aliases in `tokens.css`; alias-only controls; fixed local Fluent icon registry; headed component gallery | 3 | SH-G-11, SH-G-12, SH-G-13 foundations and SH-G-14 closed; visual contract in `DESKTOP_UI.md` |
| 4 (completed/realigned) | Presentation core | Tree-agnostic flatten/window/search/filter and indexed anchor resolver over Lane A's ordered array; bounded installed operable tree renderer and honest shell frame | Lane A, GUI Break 1 | BR-G-2's Stage 6 clause, BR-G-32 generic-tree-sink portion, BR-G-34, SH-G-7 closed |
| Cosmetic thaw/refreeze | Interface/web | Typed UI-state lifecycle, two-row cosmetic channel, persistent theme override, native/page agreement, and headed gallery repair | 4 | BR-G-46 |
| 5 | Sync surface | Plan-tree presentation and memo, DR-BR-14 Progress identity, selection controls, indexed autoscroll; vertical sync slice end to end | 3, 4, Lane D | BR-G-32 plan-DOM portion, BR-G-35–37, and the plan portion of BR-G-42 |
| 6 | Integrity surface | Cached inventory projection, `patch_row`, `view_id` lifecycle, five resolution states, recursive folder context actions, scope-warning display, per-window detail query | 3, 4, Lane D | BR-G-32 inventory-DOM closure, BR-G-22, BR-G-23, BR-G-38, BR-G-39, and the inventory portion of BR-G-42 |
| 7 | Lifecycle | Database-paged history, settings, remaining typed `ui-state.json` consumers, task close sequence, clean shutdown, terminal-artifact retention policy | 5, 6 | BR-G-40, BR-G-41, BR-G-45, and the history portion of BR-G-42 |
| GUI 2 | Visual cohesion | Holistic spacing, motion, empty/error-state, accessibility, and responsive review across the completed product surfaces | 7 | `DESKTOP_UI.md` holistic review before release |
| 8 | Docs/release | PyInstaller and frozen smoke, dependency lock and CI, license/source release material, as-built docs and README, `ui_mockup/` status, clean-checkout release proof | GUI Break 2 | BR-G-43, BR-G-44, and shell-owned SH-G-15 |

**Ordering.** Host/transport Slices 0→1→2→3 precede GUI Break 1
and Slice 4. The cosmetic thaw/refreeze closes before Slices 5–7 add traffic to
the bridge. Once Slice 4 and Lane D are complete, Slices 5 and 6 may run in
parallel; Slice 7 joins them, then GUI Break 2 and Slice 8 close the milestone.
`DESKTOP_UI.md` owns visual-cohesion criteria and `M1_SHELL.md` owns host and
package closure. This ordering makes no duration or critical-path claim.
