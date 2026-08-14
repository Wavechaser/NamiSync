# M1 Bridge and Presentation Contract

Status (2026-07-30, contract realigned 2026-08-14): design, decision, and
acceptance log for implemented M1 Stage 5.5 (facade completion) and active
Stage 6 (web desktop shell). Stage 6's installed, secured product-host and
existing transport chain through Slice 3 and the post-Slice-3 hardening have
landed. The fixed 150 ms progress-only linger has landed with focused
fixed-anchor, non-sliding replacement, immediate-wake, and lifecycle-race
evidence. Benchmark/accounting support now provides bounded manifested streams,
post-exit assembly, direct-Job admission, event/diagnostic result separation,
and a path-local retained-state sizer. The frozen `sh-g-8-transport-v1`
calibration-a/holdout-b corpora and production-path transport-custody runner
have also landed. The committed calibration-a artifact now supplies the
normative transport measurement; no byte ceiling, acceptance result, or
holdout result has landed.
GUI Break 1 and Slice 4 have completed the audited realignment recorded here;
Slices 5-8 and GUI Break 2 remain. The installed real-WebView2 browser-gate
migration is complete. SH-G-8 remains open pending a byte ceiling fixed before
independent holdout-b and that holdout.
BR-G-45 separately keeps the 100,000-subject terminal
artifact set and aggregate completed-task retention policy open. Shell-owned
SH-G-15 separately keeps version-bound whole-runtime containment open. The
explicit-`Gap`-only recovery and command-specific `start_plan` revision
decisions are ratified and their named regressions have landed.
Stage 5.5 landed its tree substrate,
recursive scan scope, selection semantics, and facade integration without
taking Stage 6 presentation work. It
governs the seam between `NamiSyncService` and the packaged frontend: what
computes where, how large plans and inventories reach the client, how
selection binds, and what the bridge may carry. Closing that seam necessarily
reaches below the facade where information would otherwise be lost: the
execution continuation retains user-selection provenance, and selected
inventory refresh gains an explicit recursive-subtree scan-and-record scope.
The implemented seam remains authoritative, while §9 and BR-G-45 now identify
the terminal-retention policy and evidence limits that must be fixed before
their independent holdouts; those open gates are not silently resolved by the
existing implementation.

**Standing.** `FEATURES.md` owns behavior and `ARCHITECTURE.md` owns
contracts; both outrank this file. `M1_PLAN.md` owns the milestone's decision
log, and DR-M1-14 through DR-M1-19 remain the governing bridge decisions —
this document refines them with implementation detail settled afterward and
does not overrule them. Where it adds a decision M1_PLAN did not make, it is
numbered `DR-BR-##` to avoid colliding with either existing series.
`DESKTOP_UI.md` remains the user-facing delivery contract; this file is the
mechanism behind it. Within Stage 6, this is the sole normative authority for
bridge envelopes and limits, command schemas and exact errors, retry identity
and deadlines, command-specific revisions, sequence/`Gap`/terminal semantics,
terminal-session release versus task close, and every BR-G acceptance gate.
`M1_SHELL.md` owns only the remaining Stage 6 implementation sequence, host and
package placement, launcher/packaging decisions, SH-G definitions, and their
mapping to these BR-G dependencies. Its later console/GUI entry-point decision
supersedes this file's older no-subcommand desktop-launch wording; it may link
to this contract but does not restate or refine it.

Section 10 is normative for implementation: a lane or slice is complete only
when its numbered acceptance gates, decision prerequisites, regression rows,
and integration/release gates are all satisfied. The delivery table is an
ordering aid, not an alternative definition of done.

**Propagation is implementation-gated.** Stage 5.5 behavior and Stage 6's
secured host and production transport are promoted into the active focused
documents and README. GUI Break 1 and Slice 4 completion claims are restored
after their ordinary, scale, security, and clean-wheel headed gates passed. The
complete Stage 6 UI remains unshipped; `M1_SHELL.md` and `DESKTOP_UI.md` record
the remaining product-surface, second GUI-break, and packaging work, while
slice 8 still performs the
final as-built pass over every active document and `ui_mockup/`.

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
4. **Hostile filesystem content is inert on screen.** A filename is display
   text, never markup, never a command argument, never an executable string.
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

Twenty-seven primary decisions plus two numbered DR-BR-16 subdecisions have
accumulated across eleven sections. The two lists below are navigation only. The
first follows the document's own top-level sections; the second re-sorts every
`DR-BR-##` by the module or layer it actually binds, which frequently cuts
across those sections (DR-BR-17 is filed under §4 but is a selection decision;
DR-BR-26 is filed under §8 but is a node-tree decision). Each entry is one
sentence: what the decision does, and what it connects to.

### Contents

0. [Goals](#0-goals) — product and engineering objectives everything below serves
1. [Stage 5.5 — Facade Completion](#1-stage-55--facade-completion)
2. [Compute Ownership](#2-compute-ownership)
3. [The Node Tree](#3-the-node-tree)
4. [Paging and Live State](#4-paging-and-live-state)
5. [Task and Process Lifecycle](#5-task-and-process-lifecycle)
6. [Concurrency](#6-concurrency)
7. [Inherited Bridge Posture](#7-inherited-bridge-posture)
8. [Verification](#8-verification)
9. [Deferred, Rejected, and Resolved](#9-deferred-rejected-and-resolved)
10. [Delivery](#10-delivery) — work lanes, decision prerequisites, acceptance
    traceability, executable regression watchlist, and Stage 6 slices

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
  — a replan discards the prior selection but advances the request's revision
  epoch and retains retry tombstones, because deterministic operation ids and
  a reset-to-zero ABA would otherwise let stale intent silently re-apply to a
  plan no one reviewed.
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
  ranges. The recursive scan shares the full-walk helper and inherits every one
  of its incompleteness causes rather than the exact-path scan's ignore rule;
  folder actions are named separately from row actions instead of predicting a
  count they cannot honestly compute; and kind-aware decoding advances only the
  inventory payload to v2, with integrity continuation restructuring deferred
  behind a named pause-latency benchmark.

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
  guard and sequence-gap recovery, the subscription registry, and shutdown
  order.

- **[DR-BR-27](#dr-br-27--receipted-commands-are-idempotent-revisioned-view-mutations-are-guarded)**
  — assigns retry identity and revision guards per command rather than as one
  blanket mutation schema: a gesture-scoped idempotency key, the typed
  `APPLIED`/`NOOP`/`STALE`/`CONFLICT` disposition reaching the view, and a
  `view_id` + projection-revision guard so an id-based command cannot freeze a
  subject set the user never saw, with the receipt consulted before the guard so
  the two do not cancel. Slice 2's `start_plan` is receipted without a revision;
  `pick_folder` has neither. The former single-mechanism assumption is resolved
  by the recorder/service receipt split in DR-BR-27 and §9.1.

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
their existing exact-subject workflow semantics remain unchanged.

**One consequence of that reuse is not neutral.** `run_integrity` currently
refuses the whole session when its scoped pre-scan is
not authoritative — `InventoryScopeIncomplete`, taken before any subject is
examined — and that pre-scan is the exact-path scan, which marks itself
incomplete on a single per-path access error. Today `selected_paths` holds a
handful of paths a user named. After folder expansion it holds an entire indexed
subtree, so one permission-denied descendant among fifty thousand aborts the
whole folder verify. The input cardinality changes by orders of magnitude while
the all-or-nothing guard stays fixed, which is the same shape of mismatch this
decision rejects for refresh two paragraphs below.

**Resolution:** a folder-expanded integrity request continues over every
readable frozen subject. A frozen subject whose exact pre-scan access fails is
emitted once as `unsupported`, with its warning retained, and receives no
attestation; the session reports verification incomplete while the remaining
eligible subjects run normally. This relaxation is narrow: cancellation,
location/root resolution failure, or any incompleteness not attributable to a
named frozen subject still refuses the scope before hashing. A folder verify
with one unreadable descendant is a required test so partial truth cannot become
a silently clean attestation.

**The action names its scope; it does not predict its count.** A folder
integrity action can admit far more work than a row action, and integrity
workflows carry no plan, no review, and no commitment to make that legible the
way DR-BR-03's plan review does for sync. The temptation is a count in the menu
item, and it is **rejected as unimplementable honestly**: the descendant rollup
is not the subject set that will run. `baseline` selects eligible unbaselined
subjects, `rebaseline` selects eligible baselined ones, `verify` has its own
candidate set, and directories are normally excluded from all three. A rollup
number would therefore be wrong for every mode, and wrong in the direction that
overstates — the worst kind of reassurance. Computing three mode-specific counts
before admission would duplicate each mode's eligibility rules outside the
workflow that owns them, which is the browser-authority failure DR-BR-08 forbids
one layer down.

**What is rejected is a *predicted* count, not a reported one.** Once a mode has
selected its subjects, the count is a fact the workflow owns, and progress and
results report it per action as they do for any other session. The rejection is
narrow and specific: no number is asserted *before* admission, from a rollup
that does not model eligibility. Slice 6 renders what each action actually
selected; the menu promises nothing.

**Menu wording carries the distinction instead.** Row actions and folder actions
are separate, plainly named commands — "Verify selected items" versus "Verify
folders" — so the scope of the gesture is legible from the label without
asserting a quantity the facade cannot yet know. Verification is pausable and
cancelable and writes nothing irreversible, so under DR-BR-03's own rule it
takes no dialog either: a user who asks for too much stops it, which is the
ordinary control rather than a failure.

**Refresh is different:** expanding only current inventory rows would miss files
newly created beneath the folder. The scanner therefore gains an explicit recursive
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
conservatively withholds all missing inference.

**The subtree walk is the full scan bounded to a root, not the exact-path scan
generalized.** That framing decides completeness, and the two existing scan
paths do not agree on what breaks it. `_scan_selected` marks the whole scan
incomplete when a requested path is ignored, because an explicitly named path
the scanner refuses to report on leaves the requested key set unresolved.
`_scan_full` skips an ignored entry and preserves completeness, because there
the ignore contract is an ordinary part of the sweep. A recursive walk meets
that contract constantly — `THUMBS.DB` and `DESKTOP.INI` appear in ordinary
picture and settings folders, and the owned-temp grammar appears wherever a
prior run wrote. Inheriting the exact-path rule would make nearly every real
subtree refresh incomplete and withhold all missing inference, leaving the
feature green on a synthetic fixture tree while doing nothing on an actual
volume.

**Resolution: the recursive implementation shares the full-walk helper and
inherits every one of its incompleteness causes**, rather than restating a list
that would drift the first time the scanner grows a case. Only the exact paths
named alongside the roots keep exact-path semantics. The recursive scope is
incomplete wherever `_scan_full` is already incomplete — which today includes
root unavailability, enumeration failure, unrepresentable paths, type-probe and
stat failures, unknown entry types, case-colliding keys, an unhydrated
**directory** placeholder, a **directory** reparse point, and a repeated
directory identity. Those last three are worth naming as examples because they
are the ones a scoped implementation is most likely to get wrong, **not because
the list is exhaustive**: sharing the helper is the contract, and any cause the
full walk later adds applies to subtree scope automatically.

**Sharing the helper means parameterizing it**, because its root handling is
written for the location root and silently assumes three things an arbitrary
subtree root does not satisfy. Each assumption is correct today only because
`root` is always the resolved location root, which is exactly why the sharing
contract must state them:

- It takes a starting **`(absolute path, relative prefix)` pair** rather than an
  absolute path alone. The helper currently hardcodes the root record and its
  traversal prefix to `""`, so a walk rooted at `Photos` would emit a root
  record claiming to be the location root and record descendants under keys like
  `IMG.JPG` instead of `PHOTOS\IMG.JPG` — wrong canonical keys written into
  inventory, reconciled against the wrong rows.
- It **probes the root's entry kind** instead of asserting
  `EntryKind.DIRECTORY`, so the former-folder-now-a-file case above is recorded
  as the file it is rather than as a directory record that contradicts the disk.
- It **distinguishes `FileNotFoundError` from other root-lstat failures**, the
  way `_scan_selected` already does for exact paths. Absence is the conclusive
  empty observation described above; denial or IO error is `ROOT_UNAVAILABLE`
  and incomplete. Catching them together — the current behavior — would make the
  absent-root case unreachable and quietly contradict this decision.

`ROOT_UNAVAILABLE` also carries the failing root's relative path rather than
`None`, since a multi-root scan must say *which* root it could not open; that
value is what the scope-warning surfacing below has to render. One `visited`
identity set spans every root in a scan: the roots are canonicalized
non-overlapping, so a repeated identity across two of them is a genuine junction
cycle rather than legitimate reuse.

The directory qualifier on placeholder and reparse is load-bearing rather than
descriptive: a *file* placeholder or file reparse point is a conclusive
unsupported observation and leaves completeness intact, because nothing was
being enumerated through it. For those two conditions this is a deliberate
divergence from `_scan_selected`, which records them as conclusive even for a
directory. Recorded explicitly because an implementer reading the exact-path
branch as the model will otherwise carry the wrong behavior across.

Completeness distinguishes absence from uncertainty. If a subtree root no
longer exists, that root is a successful empty observation and its previously
indexed root/descendant rows may become missing. **A former folder root that is
now an ordinary file is equally conclusive:** the scanner observed the path,
records it as the file it now is, and its former descendants may become missing,
because nothing about that observation is uncertain. Any inherited
incompleteness cause, by contrast, means the scanner could not observe the
claimed recursive scope; it makes the whole multi-root `ScanResult` incomplete
and therefore marks nothing missing under any requested root. Per-root
completeness would require a richer result contract and is not introduced
implicitly here.

**An incomplete refresh must say so.** "Refreshed, nothing disappeared" and
"refreshed, but I could not see enough to tell you" are different facts that
currently render identically — the missing chip simply does not move.
Withholding the inference is correct; reporting an unqualified clean refresh
afterwards is not, and it is the same invisible-exclusion gap DR-BR-07 records
for filters, asked the other way round: "why wasn't this deleted file marked
missing?"

**This needs plumbing, and an earlier draft wrongly said it did not.** The
scanner produces the evidence as typed `ScanWarning`s, but nothing carries it
upward: `run_inventory` reads `scan.complete` and discards `scan.warnings`
entirely, `InventoryDetails` has no warning field, and `InventoryDetailsView`
consequently cannot have one either. A user is told *that* a refresh was
incomplete only through a chip that failed to move, and never *why*. The chain
is four small steps: the workflow retains the warnings already in scope at the
`InventoryDetails` construction site, `InventoryDetails` carries them, a
primitives-only warning view converts code/path/detail under DR-M1-07's rule,
and the facade delivers them beside `complete`. Small, but new — and therefore
owed to a stage rather than assumed.

**Delivery splits along the interface boundary.** Stage 5.5 proves the warning
details reach the facade, which is a workflow/service obligation provable
without a second interface. Stage 6 slice 6 proves the inventory UI visibly
distinguishes an incomplete refresh from a clean one and renders its reason.

The existing
`inventory_location_presence_idx(location_id, presence, rel_path_key)` serves
the location/presence equalities plus each root range directly. A focused
`EXPLAIN QUERY PLAN` assertion verifies indexed range search for a
representative subtree rather than leaving the bounded-cost claim as an
assumption.

`InventoryRequest`/`InventoryWorkflowRequest` carry subtree roots separately
from exact selected paths, including both fields for a mixed id selection. The
inventory workflow payload advances from v1 to v2 for that new field and
rejects v1.

The integrity payload **remains v1**, because folder integrity actions are
expanded into its existing exact subjects before admission and no field changes
shape. The two decoders currently share `_payload`, whose hardcoded v1 guard
expresses no per-kind version at all, so that divergence is impossible as
written. Its signature becomes
`_payload(payload, expected_kind, expected_version)`;
`decode_inventory_request` passes 2 and `decode_integrity_request` passes 1.
Tests prove inventory v2 round-trips while inventory v1 is rejected, integrity
v1 remains accepted, and a body of the wrong kind is rejected at either version.

**Restructuring the integrity continuation is noted and deferred, not adopted.**
Folder expansion makes `selected_paths`/`selection_item_ids` large, and
`_IntegrityInvocation.snapshot` re-encodes the whole request on every pause
alongside `completed_bytes`, which grows toward the subject count as items
settle — so the largest jobs plausibly pay the most to pause, which is where a
user most wants to. A drafted fix split the body into an immutable `subjects`
half and a mutable `progress` half so pause rebuilt only progress. It is
withdrawn for M1 on four grounds:

- **The proposed immutable half was not immutable.** `refresh_generation` is
  incremented by `snapshot()` on every pause, and `selection_item_ids` is
  recomputed there from the live selection. Both would have to sit in the
  mutable half, which removes much of what the split was meant to freeze.
- **Nesting does not bound the work.** `completed_bytes` still grows toward
  O(subject count), and reassembling the single `bytes` payload the dispatcher
  requires still copies the immutable section on every pause.
- **The cache has no specified owner or framing.** Each resumed invocation would
  have to recreate or recover the retained fragment, and the document named
  neither the owner nor the serialization boundary.
- **The cost is reasoned, not measured**, and a strict payload version change is
  the wrong thing to spend on a hypothesis.

M1 therefore retains inventory v2 / integrity v1 and the kind-aware validator
until a benchmark demonstrates a pause-latency problem. **The measurement is
named:** representative 10k, 100k, and large-folder continuations, each sampled
at late-run `completed_bytes` rather than at admission, since that is when the
mutable half is largest. If it fails the gate, the continuation is designed
around the measured cost rather than around this draft — which may well not be a
nesting change at all.

Should the split be kept anyway for structural clarity, three corrections are
binding: `refresh_generation` moves into `progress`, fragment ownership is
`_IntegrityInvocation`'s, and full-payload copying is acknowledged as remaining.
Its acceptance test is **semantic and result equivalence** between a paused and
an unpaused run over the same subjects — identical items, outcomes, phase
truth, and terminal classification. "Resumes byte-identically" is not a
well-defined criterion, since a resumed run legitimately differs in
`refresh_generation`, timestamps, and scope token.

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
and inventory projections are keyed by the service-minted `view_id` of
DR-BR-16.1. Every paging request applies the view's current parameters to its
one canonical projection
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
collapsing is a deliberate act on a handful of folders. The pure helper accepts
at most 65,536 UTF-8 bytes of search text; the bridge separately caps the
complete serialized request at 65,536 bytes, including JSON overhead. A future
non-bridge external adapter imposes an equal-or-stricter complete-request bound
at ingress.
**Responses have a common server-enforced `limit` ceiling of 256 rows** for
plan, inventory, and history windows. The current transport cap is inbound
only, and a truncation must be an explicit refusal rather than a short list
that reads as a complete tree. M1 starts at 256 because it covers multiple
fixed-height viewports of prefetch while keeping query, decode, allocation, and
serialization firmly bounded by one shared number.

Fixed row height is a design constraint, not an aesthetic preference:
variable heights require measurement passes that make window math fragile.

Search responsiveness is interaction-owned, not an excuse for a tiny semantic
query limit. The first Slice 5/6 request owner uses a fixed 150 ms trailing
debounce and advances its window generation on every search, collapse, or
filter intent before dispatch. Only the final search in a burst is sent; stale
successes and failures are ignored, the current valid window remains visible
while pending, and teardown cancels the timer. Slice 4 supplies the generation
primitive but adds no dormant command or timer.

This document freezes the pure request boundary: a typed structural
view over the workflow-owned node object, collapsed known-container ids, a literal display-search string,
and an optional sparse mapping of caller-decided direct-match counts. That
mapping deliberately carries no filter vocabulary into the generic layer.
Offset is an exact nonnegative integer, limit is an exact 1..256 integer, and
the pure derived sequence is replaced rather than cached as a parameter-keyed
family. Domain command rows and projection revisions remain with their first
Slice 5/6 consumers.

**Realignment completed after audit (2026-08-13).**
`interfaces/web/visible_sequence.py` remains the single tree-agnostic pure
implementation. The corrected seam uses
the workflow-owned array directly, retains source/visible indexes once, and
derives compact active-tree accessibility metadata before windowing. It keeps strict pre-order structure
validation, collapse after match retention, literal case-folded display search,
caller-supplied sparse direct-match counts, exact 1..256 windows, and
deepest-visible ancestor anchoring proportional to chain depth. It retains no projection, path, domain
filter vocabulary, or active-view cache. The installed frontend consumes only
the generic `{offset,total,rows}` window through a fixed-height renderer with
two spacers, stale-generation refusal, and a single-tab-stop operable tree.
The focused scale/security regressions and real clean-wheel shell evidence pass,
closing BR-G-34 and SH-G-7. Plan and inventory command rows and projection
ownership remain unimplemented until Slices 5 and 6.

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
  Section 9.4 fixes the M1 fixtures, reference machine, sample rules, and
  ceilings; an implementation result may fail or pass them but may not redefine
  them after measurement.

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

- **Identity, and who owns it.** An earlier draft keyed projections by
  `(task id, location id)` while also placing the cache in the service. Those
  contradict: DR-BR-21 makes task identity the **adapter's**, so the service
  would hold a cache keyed by a word it cannot mint, validate, or enumerate.
  **Resolution:** the service mints an opaque **`view_id`** when a location view
  is opened and keys the projection by that alone; the adapter maps its own
  `(task id, location id)` to a `view_id` and sends the `view_id` thereafter.
  Opening the same location in two tasks yields two `view_id`s and therefore two
  projections, because their invalidation timing is independent — the property
  the original key was reaching for, obtained without importing task vocabulary
  below the bridge. Cache state stays under the same ownership as selection
  state (DR-BR-03), which is what lets both be validated atomically.
- **Cleanup.** Released definitively when the view changes location, through the
  task-owned facade artifact release when the task closes, and at service
  shutdown. The adapter separately drops its task/projection references.
- **Swap, never mutate.** Rebuilds construct a new immutable projection and swap
  the reference under a lock. A window request already holding a reference
  finishes against consistent structure instead of watching rows move beneath it.

  **The lock is the service's, per `view_id` — not the adapter's `TaskState`
  lock.** An earlier draft said "under the task lock", which inverts ownership:
  DR-BR-24 puts that lock on `TaskState` in `interfaces/web`, DR-BR-21 makes task
  identity the adapter's, and the projection is service-owned. Reaching an
  adapter lock from the service is the inversion; holding it *across* the facade
  call collides with DR-BR-24's own "never hold a task lock across I/O", since a
  rebuild runs a query. The `TaskState` lock guards adapter state only and is
  never held across a facade call. The LRU map is guarded by the same
  service-side lock — an unguarded cache map is not made safe by immutable
  values, because insert and evict mutate the map itself.

  **The rebuild happens outside the guard; only the swap is inside it.** But a
  *patch* is not a swap: read, shallow-copy, replace the node, bump, and store is
  one read-modify-write and must be one critical section per `view_id`, or two
  concurrent acknowledges silently discard one another's change while both
  clients see an advanced revision and trust it. A full rebuild and a patch are
  mutually exclusive under that same guard, and a patch whose base revision no
  longer matches is dropped rather than applied over newer structure.
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
  heuristics — and is **six live projections** for M1. The WebView2 process tree
  dwarfs a few slim projections, so being stingy here optimizes the wrong thing.
  Projection
  size does scale with location size, so the scale gate records per-projection
  memory and the number is revised against that rather than re-guessed.

  Plan-tree memos (DR-BR-11) do **not** share this cap. They are keyed per
  request id, hold structure over a frozen artifact, are typically far smaller,
  and die with the task — a large location must not be able to evict one.
- **Invalidation is causal, and patches in place by copy-on-write.** A
  completed acknowledge or restore changes exactly one known row, and
  acknowledgment participates in no rollup (DR-BR-20), so no ancestor is
  affected. A pure `patch_row(projection, row_id, …) -> projection` in
  `workflows/node_tree.py` **shallow-copies** the node array — a copy of
  references, sharing every unchanged node object and the position indexes
  untouched, since nothing reorders — and returns a new projection with that one
  node replaced. The service calls it, bumps the revision, and stores the result
  under its per-`view_id` lock.

  **Constructing the replacement node is `workflows/`' job, not the service's.**
  Deciding what an acknowledged row now looks like is domain semantics, and
  DR-BR-09's table already assigns node structure to `node_tree.py` while giving
  the service only projection ownership. The current tree has no precedent for
  the alternative: `interfaces/service.py` calls `inventory_row_view(row)` rather
  than assembling row views itself. Keeping the patch pure also makes it
  unit-testable without a cache.

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
  ordering machinery of its own — but "no ordering machinery" is not "no lock":
  insert and evict mutate the cache map, so they take the same service-side lock
  as the swap. Immutable *values* do not make a mutable *map* safe, and an
  earlier draft's "needs no defensive locking" elided the two.

#### DR-BR-16.2 — History is paged at the database, not after it

The old path loaded and decoded every item for one run, and the list path called
that full getter once per listed run. A 50-run list therefore performed N+1
query sets and materialized every selected item before the bridge could discard
all but one window.

**Resolution (introduced in history v4 and retained by receipt-aware v5):**

- `list_summaries(limit)` uses one run query plus fixed phase and aggregate
  queries. It never selects or decodes canonical event JSON. The repository
  returns one fixed-size conditional fact object per run; free-form item kinds
  and reasons cannot expand Python object retention. Workflow code supplies the
  finite selection/no-op predicates and owns selection, integrity, and headline
  interpretation, preserving the `db → workflows` import prohibition.
- `get_item_page(...)` keyset-pages dense immutable `item_order`, and
  `get_event_page(...)` keyset-pages reliable `event_seq`. Both reject limits
  outside 1..256. The first page captures a committed `through_*` watermark in
  the same read transaction; subsequent pages reuse it while new history
  windows continue committing. Caller-supplied event watermarks are inclusive
  sparse bounds and need not name a retained row. Every request verifies the
  official durable maximum through the composite primary-key index, fetches one
  raw lookahead row, and decodes no more than the requested limit.
- A fresh event traversal whose last successfully applied non-`Gap` cursor is
  ahead of durability returns one empty terminal page. That traversal ends;
  the next repair attempt omits `through_seq` and captures a new committed
  prefix. Echoing the older watermark with the preserved cursor is an invalid
  reversed fixed interval.
- Terminal phase summaries have an explicit 256-row recording ceiling and may
  therefore load with the summary. Item/event detail never does.
- The service exposes summary, item-page, and event-page methods and removes the
  unbounded full-run getter. CLI detail rendering consumes item pages directly.
- `history_events_run_item_order_idx` serves item windows, the composite primary
  key serves event catch-up, and `history_events_run_item_aggregate_idx` serves
  typed summary facts. Query-plan regressions pin those seeks.

This change deliberately advances the reset-only history contract to v4 rather
than pretending the v3 terminal-only rows could recover discarded state and
phase events. It also makes committed reliable pages the backend recovery path
for a live subscriber gap. Missing lossy `Progress` sequence numbers remain
valid; a finalized summary supplies terminal truth if the live `Terminal` was
lost.

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
display form** rather than the canonical key (the user types what is on
screen), no trimming or Unicode normalization, and an exact 65,536-UTF-8-byte
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
aggregate policy for completed tasks. Until its policy and ceilings pass an
independent holdout, neither the 48-task count bound nor successful session
release is evidence that retained result bytes are bounded acceptably.

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

The pinned host creates one thread per exposed-function call, so the bridge
admits at most 64 handlers and returns the fixed `bridge_busy` refusal at
saturation. The same admission condition closes the race between handler entry
and teardown; no bridge-global lock spans a command handler.

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
  initialization is idempotent, listener registration is not duplicated, and
  every firing ensures exactly one drain is re-armed per nonterminal task. A lost mutation
  response retries with the original gesture `command_id`; a lost drain uses
  the sequence recovery above.
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

Unchanged from `M1_PLAN.md` and restated only so this document is
self-contained: exactly one exposed `dispatch(command_json)`, versioned and
schema-validated and allowlisted (DR-M1-15/17); forced Edge Chromium with an
actionable failure and no MSHTML fallback; hardened pywebview settings with
`debug=False`; native `NavigationStarting`, `FrameNavigationStarting`, and
`NewWindowRequested` cancellation plus an independent per-call origin
recheck; no NamiSync-owned `evaluate_js`, `run_js`, `Window.state`, or
JavaScript construction as an application-data channel; opaque ids inbound
and escaped display text outbound; `textContent` only and no `innerHTML`; the
packaged asset server serves static assets and is not an API channel. Pinned
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
data. A structured refusal is definitive; only uncertain transport delivery or
`internal_error` from an admitted receipted command may trigger that row's one
same-command replay. Messages expose no request body, command payload, real
path, exception text, traceback, Python type, or implementation detail; a
handler exception never crosses pywebview as its native traceback-bearing error
value.

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

The immutable production command mapping is exactly `pick_folder`,
`start_plan`, `next_events`, `release_terminal_session`, and `close_task`.
`test_report` is a test-owned constructor-only
harness row: the harness builds a new immutable mapping from those production rows plus its own
validator, handler, payload, and result schema under `tests/`. No product argv,
environment, page value, or bridge request can enable it, and it has no product
retry class. Later plan, inventory, settings, and history commands
are not reserved or allowlisted until their owning slices
land each row with its schema, receipt/revision rule, deadline, retry policy,
and gate.

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
immediately. The 25-second long-poll deadline remains the outer bound.

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
`renderText(element, text)` sink and writes only validated string data through
`textContent`. Browserless transport/render probes and the headed transport
page live under `tests/assets/`, not package data.

The headed gate composes its single `test_report` row only through the same
dispatcher constructor used by production, under a unique test identity and an
absolute physical local page/data root. It automates the real native folder
picker without a foreground-forcing API, localized-label lookup, or keystroke
input, proves selected paths stay behind purpose-bound ids, commits an
independent second loopback origin and verifies zero handler calls, and
round-trips the hostile corpus through the real pinned return transport and
production sink. Renderer/log evidence is read from native
`BrowserVersionString`; logs contain neither request bodies,
real paths, hostile sentinels, tracebacks, exception text, nor `NICKNAME`.
The installed-wheel browser scenario also drives the production `bridge.js`
drain manager through stale readiness and generation settlements, identical
`start_plan` replay, numeric holes without recovery, explicit-`Gap` recovery,
busy and malformed refusal budgets, nested hostile-Unicode public views,
the real `sync-plan` terminal-record identity, terminal release without
automatic task close, and task/listener/timer cleanup.

**`ui-state.json` carries cosmetics only.** `M1_PLAN.md` DR-M1-03 established it
as the GUI-owned counterpart to `db/settings.json` — recents, window geometry,
column and sort state — and this document's slice 7 is where it is finally
written. It is bounded here because it is the one new persistent artifact Stage 6
adds and §0's non-goals defer durable plan/session persistence: it may hold
window geometry, column widths and order, sort state, collapsed sets, the active
filter chips, and the recents lists. It may **not** hold a plan request id, a
session id, a task identity, a selection, a `view_id`, or a projection revision.
The distinction is not stylistic — anything in the second list would be a durable
session store arriving through the back door, unversioned and unreconciled with
the process-local truth it would contradict on the next launch. A corrupt or
absent file is a recoverable cosmetic reset, never a lost task; the GUI starts
with defaults and says nothing.

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
  product surfaces exist. Slice 5 repeats the corpus against the actual plan
  DOM and slice 6 repeats it against the actual inventory DOM. BR-G-32 remains
  open until all three stages prove text, not markup, attributes, or script.
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
It also closes SH-G-3. The production plan and inventory DOM clauses remain
open for Slices 5 and 6, so BR-G-32 as a whole remains open.

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
(DR-BR-06); generalizing the exact-path scan for recursive scope, whose
ignore rule would make almost every real subtree refresh incomplete
(DR-BR-06); restating the full scan's incompleteness causes as a closed list
rather than sharing its helper (DR-BR-06); a descendant count on folder
integrity menu items, which no rollup can honestly supply because each mode
selects its own eligible subjects (DR-BR-06); a confirmation dialog for
folder-scoped integrity actions, which are pausable and cancelable
(DR-BR-06); a client-only autoscroll anchor that cannot locate an
unmaterialized row (DR-BR-19); and a second bridge-specific reliable-loss
policy instead of the dispatcher's existing visible `Gap` path (DR-BR-24).

**Deferred:** integrity continuation restructuring, held behind a named
pause-latency benchmark over late-run `completed_bytes` rather than adopted on a
reasoned cost (DR-BR-06); filter-exclusion visibility in plan review (DR-BR-07);
`get_plan_review` rebuilding every view object per call, which the memoized
tree and direct `preview_selection` path route around rather than fix; and
persisted selected-kind/integrity summary columns on `history_runs`, which
require a later schema-version decision rather than an M1 fallback
(DR-BR-16.2).

**Resolved implementation prerequisites:**

1. **Idempotency uses two mechanisms, not one fictional universal receipt.**
   Recorder mutations use a reproducible per-(gesture, row) key and
   caller-supplied timestamp; session-creating facade commands use the
   service-held command receipt and lifecycle specified in DR-BR-27.
2. **Folder integrity continues past unreadable frozen subjects.** Each such
   subject becomes one visible `unsupported` result, the run stays explicitly
   verification-incomplete, and every other eligible frozen subject proceeds.
   Non-subject-specific incompleteness still refuses before hashing.
3. **Drain recovery is explicit-gap/uncertainty recovery.** No client
   acknowledgment, echoed cursor, response cache, or second server receipt is
   added. A failed/malformed drain takes the existing
   resubscribe/terminal-record path from the sequence after the last accepted
   non-`Gap` event; an explicit `Gap` uses its exact `first_missed_seq`, with a
   matching leading recovery gap proving the missing prefix unavailable rather
   than causing another loop. Numeric sequence holes are legal when
   replaceable progress coalesces and do not themselves trigger recovery.
4. **M1's scale envelope is 100,000 file-backed subjects, with concrete
   reference budgets.** This matches the current user's upper bound; ordinary
   directories are expected to be in the thousands to tens of thousands. The
   first reference profile is intentionally this development machine, not a
   claim about minimum supported hardware:

   - Windows 11 Pro build 26200;
   - Intel Core i7-13700K, 16 cores / 24 logical processors;
   - 63.7 GiB RAM;
   - repository, fixtures, and SQLite databases on a WD_BLACK SN850X 4 TB NVMe;
   - CPython 3.13.14 and SQLite 3.50.4.

   Measure on AC power with no unrelated sustained workload. Each p95 uses at
   least 30 warm samples; each cold maximum uses at least five fresh-process or
   cold-projection samples. The benchmark artifact records exact commit,
   machine/runtime profile, fixture seed, raw samples, p95, and maximum.

   | Fixture | Required shape |
   | --- | --- |
   | Plan | 100,000 operations plus up to 20,000 synthesized/real folder nodes; dependency and path depth reach 32 |
   | Inventory | 100,000 file rows plus up to 20,000 directory rows in one location; the slim projection therefore reaches 120,000 nodes |
   | History | 50 recent-run summaries covering 1,000,000 retained items total, with at least one 100,000-item run; detail paging targets that large run |
   | Projection retention | Six populated 120,000-node inventory projections, then a seventh view to exercise LRU eviction |
   | Events | Four active tasks for 60 seconds at 100 aggregate `Progress` events/s plus 10 aggregate reliable events/s |

   | Measurement on the reference profile | Ceiling |
   | --- | --- |
   | Local pending/disabled feedback after a critical click | 50 ms maximum |
   | Typed facade receipt for execute, pause/resume/cancel, or one-row acknowledge/restore, excluding admitted work | 100 ms p95; 250 ms maximum |
   | Admission that freezes/normalizes the full 100,000-subject scope (folder refresh/integrity or multi-row visibility) | 500 ms p95; 1 s maximum |
   | Reliable/terminal bridge delivery under the event fixture | 100 ms p95; 250 ms maximum; no `Gap` |
   | Replaceable progress delivery under the event fixture | 1 s p95; 2 s maximum; monotonic and ordered after coalescing |
   | Cold 120,000-node plan projection build | 2 s maximum |
   | Cold 120,000-node inventory slim-projection build | 3 s maximum |
   | Unchanged-parameter 256-row plan/inventory window | 250 ms p95; 500 ms maximum |
   | Changed collapse/filter/search visible sequence plus 256-row window | 750 ms p95; 1.5 s maximum |
   | `preview_selection` over the plan fixture at depth 32 | 500 ms p95; 1 s maximum |
   | Fifty-run / 1,000,000-item history summary | 3 s maximum |
   | 256-row history detail window | 500 ms p95; 1 s maximum |
   | Incremental plan projection memory | 128 MiB maximum |
   | Incremental inventory projection memory | 192 MiB maximum each; 1,152 MiB for six |
   | Identity-deduplicated bridge transport custody under the event fixture | OPEN: runner and normative calibration-a artifact landed; later byte ceiling and independent holdout-b pending |
   | One 100,000-subject terminal artifact set plus the declared aggregate completed-task policy | OPEN under BR-G-45; per-completion and aggregate ceilings are separate |

   **BR-G-42 event-custody definition (required by SH-G-8; REALIGNED, OPEN).**
   Transport custody
   includes only the live dispatcher replay deques, subscriber deques, and
   adapter task queues, measured as one identity-deduplicated deep Python graph.
   Queue containers and nonterminal event values count. A terminal event or
   `SessionRecordView` occupies its queue slot, but its result graph does not:
   terminal artifacts scale with subject count and are measured only by
   BR-G-45. The instrument reports each root class separately as well as their
   deduplicated union so one scaling axis cannot be charged to another.

   The named corpus is `sh-g-8-transport-v1`: four tasks use distinct,
   Windows-legal subject/prior paths at depth 32 and exactly 240, 1,024, or
   4,096 UTF-16 code units, with a 2:1:1 ASCII/BMP/non-BMP alphabet ratio;
   derived MOVE_UPDATE trash paths add their real `.synctrash` prefix. The
   ordinary 6,000 progress values distribute those lengths 5,700/240/60; its
   600 reliable outcomes distribute them 570/24/6. The maximum no-`Gap` fixture
   emits 516 reliable outcomes with a 490/21/5 distribution. Reachable failure
   details rotate among the committed failed-COPY cleanup/unverified branch
   (`io-error`, primary and publication-state `PermissionError`, and
   `cleanup_error`), failed `move_update` / `recorder-failed`, and failed update
   mutation / `io-error`; none fabricates a `durability_warnings` entry. This is
   not the distinct post-flush warning branch. Subject paths, ids, and
   path-bearing detail values are each unique while fixed categorical strings
   retain their production values. The COPY and MOVE_UPDATE `published_path`
   fields deliberately reuse the exact `ItemOutcome.path` object, matching
   production identity instead of inflating the graph; MOVE_UPDATE's trash path
   embeds an equal but separately allocated prior path. Item ids are 32
   lowercase hexadecimal characters from the first 128 SHA-256 bits over
   corpus/variant/fixture/task/local identity and are disjoint across variants
   and fixtures. Calibration-a uses rank
   `(ordinal*37+17) mod population` and
   alphabet `ordinal mod 4`; holdout-b uses `(ordinal*41+31) mod population`
   and alphabet `(ordinal+1) mod 4`, so their generated values are disjoint.

   The landed corpus and runner preserve the existing capacities, event rates,
   ordering, coalescing, no-`Gap`, and latency predicates while using a declared
   named realistic path/detail corpus with distinct values rather than
   shared test strings. It records both the ordinary four-task run and the
   maximum reachable no-`Gap` custody shape: per task, the 128-entry replay,
   64-entry subscriber, and 64-entry adapter bounds are driven through the
   production offer/observation path and sampled from a quiescent snapshot. The
   construction emits 64 outcomes per task to fill adapter custody, admits one
   further production transfer, then emits the 64-outcome tail; no queue value
   is inserted synthetically. The committed calibration artifact, generated
   from clean source, records the frozen corpus version/hash,
   raw root measurements, interpreter, allocation method, and every achieved
   high-water mark. The already-declared derivation rule applies 25 percent
   headroom to the largest calibration
   `transport_custody_bytes` measurement and rounds upward to 65,536 bytes. A
   later commit fixes the resulting byte ceiling before an independent holdout
   run; the calibration run cannot validate its own limit. The former 16 MiB
   whole-Job ceiling is retired rather than inherited or raised.
   Payload-byte totals and complete-process memory are invalid substitutes for
   retained transport custody.

   **BR-G-42 / SH-G-8 evidence status (REALIGNED, OPEN, 2026-08-14).** The deterministic ordinary
   fixture now drives four simultaneous tasks through 60 logical seconds with
   exactly 6,000 `Progress` emissions, 600 reliable item emissions, and terminal
   truth for every task. It proves every observer is attached before tick zero,
   no normal-envelope `Gap` occurs, all reliable ids arrive exactly once and in
   per-session order, delivered progress is strictly monotonic after coalescing
   and reaches 1,500 per task, every terminal record is exact, and neither the
   dispatcher subscriber queue nor adapter task queue exceeds 64. The existing
   260-reliable fault-injected overflow case remains a
   separate, explicitly beyond-envelope witness for visible `Gap`, retained-tail
   recovery, and terminal reconciliation. Those correctness predicates pass,
   and the production drain now anchors one fixed 150 ms deadline at first
   progress-only availability without restarting it for replacement,
   supersession, or retry. Reliable, `Gap`, terminal, recovery, close, and
   supersession wake immediately; 174 focused drain/command/host checks pass.
   The former short-path 289,147-byte diagnostic does not close
   realistic-payload custody because it included terminal records and ran
   beside the whole-Job sampler. A separate retained-state sizer now snapshots
   the real replay, subscriber, and adapter deques under their owner locks,
   requires two identical structural captures, refuses unknown graph types,
   reports those three non-additive graphs plus one identity-deduplicated union,
   and stops at terminal-result subtrees only along terminal paths. It is
   accounting support, not acceptance evidence. The frozen
   `sh-g-8-transport-v1` corpus and its disjoint calibration-a/holdout-b variants
   now drive the real built-in deques through
   `Dispatcher` -> `NamiSyncService`/`SessionObserver` -> `TaskRegistry`. The
   runner samples 60 exact-body producer-quiescent ordinary checkpoints, then
   constructs the quiescent per-task replay/subscriber/adapter 128/64/64
   maximum without a synthetic `Gap`; cleanup proves all 129 reliable items per
   task arrive exactly once and ordered before exact terminal records. Its
   ordinary report retains independent observed high-water values across those
   checkpoints plus the terminal transport projection; in particular,
   `transport_custody_bytes` is an observed union high water, never a sum of
   component maxima. The 128/64/64 measurement is one unchanged exact
   quiescent snapshot. Its terminal witness includes the queue slot while
   cutting and separately reporting result artifacts, so it is not BR-G-45
   calibration. Each dataset
   requires an isolated/safe-path parent launched with `-I -S`
   (`isolated=1`, `ignore_environment=1`, `no_site=1`, `safe_path=true`). After
   proving clean committed source authority, the parent manually compiles the
   exact verified child bytes; it does not import that contract through an
   executable site-package startup path. It then launches three fresh Windows
   CPython 3.13 children with `-P -S`, `no_site=1`, safe-path mode, and a fresh empty
   per-child bytecode-cache prefix outside the source tree. Source and dependency
   authority are rechecked around every child. Stable source, dependency,
   corpus, instrument, and normalized runtime-qualifier hashes plus each
   child's external exact-schema digest receipt bind the dataset; each child's
   exact runtime and cache path are also recorded and hashed.

   The runtime qualifier is final non-debug 64-bit CPython 3.13 on Windows with
   explicit `pymalloc` and optimization/dev/tracemalloc disabled. All inherited
   `PYTHON*` variables are removed before setting only `PYTHONHASHSEED=0`,
   `PYTHONMALLOC=pymalloc`, `PYTHONNOUSERSITE=1`, `PYTHONUTF8=1`, and the fresh
   `PYTHONPYCACHEPREFIX`. The exact active-venv `xxhash/__init__.py`,
   `xxhash/version.py`, and sole `_xxhash*.pyd` file, their origins, and their
   combined digest are recorded. The durable normative calibration-a artifact
   is `tests/interfaces/web/sh_g_8_transport_calibration.json`. It was generated
   from clean tested commit
   `56c50b43dc19090ad33af031891503bfec80599b`; its file SHA-256 is
   `13589307538eb90f05da2322c7e0ba627234e060c8455d9b7e3013aa575cece8`, and
   its three measured child PIDs are 47288, 47520, and 26968. It records an
   ordinary union high water of 1,376,690 bytes / 4,890 objects and an exact
   maximum no-`Gap` union of 1,534,946 bytes / 5,499 objects. Its stable
   evidence, corpus, normalized runtime-qualifier, and dependency-authority
   SHA-256 values are respectively
   `62930023783624e742aebaba6a148351a7103a213e93e08a1972b2c90ce4c3ea`,
   `a80d908babaff50872cb15bf4f9fa23eb2a054b982a25ac607223208a80787ec`,
   `a520cababa83f3c878ca13e2a7f43053b68ed6ee40ccee04aed3834bab05e88e`, and
   `8c0cab9dfa7aeed198ecbd0e66844cd834cf36ca8b32fd6647a53924a200de30`.
   The artifact contains no byte ceiling or pass/fail field and makes no
   acceptance decision. The next commit mechanically freezes the ceiling as
   `ceil((1,534,946 * 5 / 4) / 65,536) * 65,536`; only a later independent
   holdout-b may decide acceptance.
   Calibration can be reproduced from a clean commit with
   `.\.venv\Scripts\python.exe -I -S tests\bridge_transport_custody.py calibration --output "$env:TEMP\namisync-bridge-transport-custody-calibration.json"`.
   Do not run or interpret holdout-b before the later ceiling commit.

   The standalone `tests/bridge_event_benchmark.py` harness builds and installs
   the archived-HEAD wheel, loads a test-owned benchmark page with the installed
   production bridge/render assets in real WebView2, waits on a
   test-only start handshake, runs the same aggregate rates for a real 60
   seconds, and records latency, `Gap`, fixture, runtime, dirty-state, and
   whole-Job diagnostics that may inform, but cannot close, shell-owned SH-G-15.
   The browser streams bounded sample batches and the producers stream bounded
   timing batches to SHA-256-manifested sidecars; the measured child retains no
   growing sample dictionary and performs no repeated full producer-document
   serialization during the fixture. Final evidence attachment and artifact
   assembly happen only after the child exits. The actual Python child is
   assigned directly to the Job before product composition rather than hiding
   an unmeasured launcher outside it. Whole-Job diagnostics preserve per-PID
   role/private bytes, sampled thread/handle counts, and membership/topology
   transitions. They have no acceptance line here: artifact `passed` and
   `event_passed` describe only the event envelope,
   `sh_g_8_acceptance` is `incomplete-without-custody`, diagnostic completeness
   is reported separately, and `whole_runtime_acceptance` is `not-defined`.
   The former 16 MiB whole-Job ceiling has no pass/fail effect.
   The artifact also
   identifies and enforces the declared Windows build, CPU/core shape, RAM,
   repository NVMe, AC-power state, and declared Python/SQLite plus pinned
   pywebview/pythonnet profile; it records the resolved Bottle, evergreen
   WebView2, and loaded CLR identities without pretending they are all
   package-pinned. Reproduce it from the repository root with:

   ```powershell
   .\.venv\Scripts\python.exe tests\bridge_event_benchmark.py --output "$env:TEMP\namisync-bridge-event-benchmark.json"
   ```

   The 2026-08-13 reference run of archived commit
   `288969426d6e005bac7a7e540e0cfdbacf28f9eb` completed the exact 60-second
   fixture with 6,000 `Progress` and 620 reliable/terminal deliveries (600
   `ItemOutcome`, 12 `StateChanged`, four `Terminal`, and four terminal
   records), four valid sessions, every item id exactly once and ordered,
   monotonic progress, no `Gap`, and clean shutdown. Measured producer rates
   were 100.043 `Progress`/s and 10.004 reliable items/s. Progress latency was
   4 ms p95 / 17 ms maximum; reliable/terminal
   latency was 5 ms p95 / 28 ms maximum. Its declared archive, machine/runtime
   identity-profile, event, latency, cadence, and terminal predicates passed;
   those were not SH-G-15 containment predicates. The complete headed Job
   sampled 287,506,432 idle-baseline bytes and a 354,881,536-byte peak, a
   67,375,104-byte delta against the 16,777,216-byte ceiling, over 3,006
   fixture samples with a 21.042 ms maximum interval. That conservative
   overage is intentionally non-normative. It does not measure transport
   custody and therefore neither passes nor fails realigned SH-G-8. Queue
   capacities and event latency budgets are unchanged; no replacement custody
   ceiling is set by this checkpoint. The
   archived source scope was clean; its recorded worktree status contained only
   the two approved temporary root references, removed during final cleanup.

   Critical feedback and command admission are strict because they determine
   whether the interface feels alive. Page, projection, progress, and history
   work may be late up to the larger ceilings, but lateness never permits a
   torn page, stale mutation, fabricated sequence, wrong count, or clean result
   from incomplete evidence.
5. **The common maximum page size is 256 rows.** Plan, inventory, and history
   use the same ceiling and refuse 257 rather than truncating it.

**Closed earlier:** DR-BR-15 settles the former move-ghost filter question —
when a filter hides the ghost, its synthetic-only ancestor chain disappears
with it.

---

## 10. Delivery

### Packaging

`pywebview` is a normal runtime dependency, not an optional extra. The console
script `nami-sync` and `python -m namisync` remain CLI-only; no-subcommand use
prints usage and points to the GUI launcher. The `nami-sync-gui` GUI script
starts the same web adapter without retaining a console window. Explicit CLI
work does not import or initialize `pywebview`, and GUI imports stay
quarantined under `interfaces/web`.

This packaging decision does not accept a renderer fallback. Slice 0 pins the
supported pywebview version range after proving Python 3.13 compatibility and
the required bridge behavior. Slice 1 refuses a missing or incompatible
WebView2 runtime with an actionable error rather than falling back to MSHTML.
Moving the host to an optional extra remains possible later, but is not an M1
distribution mode.

**Both entry-point families use a launcher module.** The current console script
is `namisync.interfaces.cli:main`; Slice 1 retargets it and the package module
entry point to `interfaces.launcher:main`, while the GUI script targets
`interfaces.launcher:gui_main`. The launcher is **neither adapter**: its two
functions import the selected sibling lazily, and the layers contract permits
`launcher → {cli, web}` while `cli ↮ web` stands. It lives at
**`namisync/interfaces/launcher.py`** so the existing `interfaces` forbidden
imports and BR-G-19 static scan cover it. The new top layer sits above
`cli | web`, which remain above `service`. Importing the web adapter lazily from
`cli.main` would still violate that contract.

### Stage 5.5 — four work lanes

Stage 5.5 grew well past what one sequential list describes usefully. It
decomposes by owning module into **three lanes that share no files and may run
concurrently, converging on a fourth**. Lane assignment is by module, so two
people can take two lanes without coordinating on anything but the lane
boundary.

| Lane | Owns | Delivers | Depends on |
| --- | --- | --- | --- |
| **A — Tree substrate** | `core/pathing.py`, `workflows/node_tree.py`, `modules/planner.py` | DR-BR-10 helper promotion (which *removes* the three private helpers from `planner.py`, so that file is owned here); DR-BR-09's hierarchy core (ancestor synthesis, ordering, subtree membership, rollups); DR-BR-11 location-scoped ids and id→path lookup; the ordered depth/parent-indexed array; DR-BR-26 pure-function tests | nothing |
| **B — Scan scope** | `core/models.py`, `modules/scanner.py`, `db/recorder.py`, `workflows/inventory.py` | DR-BR-06's `SUBTREES` scope and invariants; the parameterized full-walk helper; the three-way recorder branch and indexed literal range; inventory payload v2 and the kind-aware validator; scan-warning retention into `InventoryDetails` | nothing |
| **C — Selection semantics** | `workflows/selection.py`, `core/execution.py`, `workflows/payloads.py`, `workflows/views.py`, `workflows/sync.py` | DR-BR-01 user deselection, `USER_DESELECTED`, `ExecutionSet` provenance, payload v4, and `run_execution`'s re-derivation and mismatch refusal; DR-BR-02 upward closure; DR-BR-04 replan discard; the corrected `all-noop` predicate | nothing |
| **D — Facade** | `interfaces/service.py`, `workflows/runtime.py` | DR-BR-03 revision and three-state commitment; DR-BR-05 four lifts with the disposition view; DR-BR-06 id-based commands; the Stage 5.5 portions of DR-BR-27; `preview_selection`; the scan-warning view field | **A, B, C** |

A, B, and C touch disjoint files and can land in any order. **D is the
integration point** and is where a disagreement between them surfaces — which
is the same posture `M1_PLAN.md` takes toward its Stage 4 slice, for the same
reason.

The lane table owns production files, not every gate that mentions their
output. `patch_row`, projection ownership, `view_id`, and the projection
revision guard land together in Stage 6 slice 6, where their cache consumer
exists. Lane A supplies the immutable array and row indexes that slice consumes;
Lane D does not pre-mint an otherwise unusable `view_id`. This is engineering
goal 6 applied to the delivery plan.

Two lane notes worth stating so they are not rediscovered:

- **Lane A's promotion is a pure relocation.** DR-BR-10's caution is the
  acceptance criterion: the planner's existing tests pass unchanged, with no
  tidying of `_depth`, `_parent`, or `_is_descendant` during the move.
- **Lane B is the only lane that can corrupt stored data.** Its wrong outcomes
  are wrong `rel_path_key`s and wrongly-missing rows, neither of which raises.
  It carries the heaviest gate below for that reason.
- **`workflows/sync.py` is Lane C's, not Lane D's.** DR-BR-01's provenance is
  inert until `run_execution` re-derives from `(plan, user_deselected)`, and
  `_exclusion_items` is the only site that turns an `OperationExclusion` into a
  `result.items` entry. Both live there. Lane D consumes the result but must not
  edit that file, or the two lanes conflict at the one place their contracts
  meet.
- **`modules/planner.py` is Lane A's for one reason only:** DR-BR-10's promotion
  deletes three helpers from it. No other planner behavior is in scope, and
  BR-G-3 is what holds that line.
- **DR-BR-14 belongs to no Stage 5.5 lane.** It edits `core/events.py`,
  both reporters in `modules/`, and `envelope_from_dict`. It is Stage 6 work,
  listed in that table rather than here, and is called out because a
  presentation slice otherwise reaches into `core/` and `modules/` unannounced.

The builder's plan-presentation layers stay in Stage 6: move grouping, ghost
annotation, and nested-move suppression (DR-BR-13) are plan tree concerns, and
Stage 5.5 needs none of them to resolve an inventory node id.

Stage 5.5 is **verified through headless Python tests rather than new CLI
surface**. Cross-lane behavior is driven through `NamiSyncService`; pure
builder, scanner, codec, query-plan, and recorder-receipt invariants are tested
at their owning boundary because a facade test can make those specific defects
unobservable. Contract tests prove:

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
  directory row; folder-scoped baseline/verify/rebaseline resolve over the
  folder's complete indexed subtree regardless of which descendants a view
  filter hides, with each mode's existing eligibility rules then selecting its
  own subjects; the representative subtree reconciliation query proves an
  indexed range search; and empty-id and foreign-location requests are refused;
- a subtree containing ignored entries — `THUMBS.DB`, `DESKTOP.INI`, an owned
  temp — stays complete and still reconciles; a former folder root that is now a
  file is recorded as that file and its former descendants become missing; a
  *file* placeholder or file reparse point leaves completeness intact; a
  **directory** placeholder, directory reparse point, and repeated directory
  identity each make the scan incomplete and mark nothing missing; the recursive
  path is asserted to share the full-walk helper so a newly added full-scan
  incompleteness cause propagates without a doc edit; and an incomplete subtree
  refresh delivers its typed scope warnings through `InventoryDetails` to
  `InventoryDetailsView` — code, path, and detail — rather than reducing to a
  bare `complete=False`, with rendering left to Stage 6 slice 6;
- the parameterized walk records a nested root's descendants under the root's
  own canonical key rather than the location root's, records a root that is now
  a file as a file, treats an absent root as conclusive while denial or IO error
  is `ROOT_UNAVAILABLE` and incomplete, names the failing root in that warning
  instead of `None`, and trips the identity cycle guard for a junction crossing
  from one requested root into another;
- inventory v2 round-trips and rejects v1 while integrity v1 remains accepted
  through the shared kind-aware validator, and a wrong-kind body is rejected at
  either version.

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

### Acceptance gates

The bullet lists above say what to build. These say **when it is done**, and
they are written adversarially on purpose: each names the cheap implementation
that would pass a naive test, so satisfying the gate cannot be faked by
someone — including a future one of us, in a hurry — who only wants the suite
green. The `*Not satisfied by*` idiom is `M1_PLAN.md` §5.1's and is used here
for the same reason. Numbered `BR-G-##` to avoid colliding with the `XV`
series.

**Gate closure protocol.** A checked box is not evidence. Every numbered gate
has at least one collected pytest whose name begins `test_br_g_<number>_`; a
gate split across levels has one such test at each level it names. Tests call
the production entry point named by the gate. A test double may fault-inject
the named dependency, but may not replace the unit whose behavior is under
test. The counterexample in *Not satisfied by* must be present in the fixture
or assertion, not merely quoted in a comment.

The only non-pytest evidence is a real-WebView2 platform check, a recorded
scale result, or a source/import scan explicitly required below. Those produce
an artifact linked from the implementation change. BR-G-42's pytest proves
deterministic query/decode/allocation bounds and the benchmark harness; its
wall-clock and memory budgets run separately on §9.4's reference profile. On
the supported Windows environment, no ordinary gate test may be skipped or
xfailed; an uncollected, conditionally skipped, or expected-failing test leaves
the gate open.

To keep the production lanes disjoint without moving their collisions into
tests, new Stage 5.5 gate tests have fixed owners:

| Owner | New gate-test module | May close independently |
| --- | --- | --- |
| A | `tests/test_bridge_tree.py` | BR-G-1's builder clauses, BR-G-2's structure clauses, BR-G-3 |
| B | `tests/test_bridge_scan_scope.py` | BR-G-4–9 and BR-G-25–28 |
| C | `tests/test_bridge_selection.py` | BR-G-11 and BR-G-12 |
| D/integration | `tests/test_bridge_service.py` and `tests/test_bridge_resume.py` | BR-G-1's service refusal, BR-G-10, BR-G-13–18, BR-G-20, BR-G-21, BR-G-24, BR-G-29 |

The headings below group related contracts; they do **not** imply that every
gate under a heading is lane-local. A, B, and C are independently mergeable
only on the clauses in the table's last column plus their regression rows. D
closes the cross-lane Stage 5.5 gates. Section 9's five former prerequisites are
resolved and are part of the gates below; implementation may not substitute a
different retry, partial-integrity, drain, scale, or page-size contract merely
because its local tests are easier.

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
  `pick_folder` and `start_plan`, and the current allowlist adds Slice 3's
  `next_events` plus lifecycle-only `release_terminal_session` and
  `close_task`, while `test_report` is possible only through test-owned
  constructor composition. Unknown versions, commands,
  fields, malformed opaque ids, and input above 65,536 UTF-8 bytes are refused
  before handler invocation. Errors expose no filesystem path or internals even
  though pywebview otherwise returns Python tracebacks. The native picker keeps
  its path in the bounded server slot table, returns only `{id, display}`,
  accepts only purpose-matching live ids through dispatch, and refuses a
  fabricated id without making display text authoritative. The scanner's
  complete hostile-name corpus crosses page JavaScript, the real pinned
  pywebview return transport, and the production inert-text path in the headed
  harness byte-for-byte, while the broadened DR-BR-25 packaged-asset sink scan
  is empty. Those clauses close Slice 2's transport, picker, origin-refusal, and
  static-sink portion. Slice 5 must repeat the corpus in the production plan DOM
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
  listener set, retain at most one drain per task, and re-arm delivery after
  each bridge reincarnation.
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
  alone do not close the gate. The bounded window carries server-derived
  parent/child/sibling accessibility metadata. A static assertion proves the
  implementation calls no path helper and reconstructs no parent or descendant
  relationship from display text. *Not
  satisfied by* filtering an already-windowed page, searching the canonical
  key, accepting an arbitrary callable as filter policy, or separate plan and
  inventory flatteners fed the same fixtures. The realignment regressions and
  Slice 4's 120,000-node scale evidence now pass; broader BR-G-42 product-view
  measurements remain with Slices 5-7.
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
  display paths.** A pre-change Progress body lacking the two identity fields
  decodes through `.get(...)`; a new body serializes both; one-sided and
  unknown-type pairs are rejected; and both production reporters emit the
  correct nominal pair without changing the current envelope version. An
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
  terminal task asks nothing. `ui-state.json` round-trips
  only the permitted cosmetic fields, including collapsed opaque node-id sets,
  but never serializes a plan request id, session id, task identity, selection,
  `view_id`, or projection revision; corruption recovers with defaults. Settings
  round-trip through the service;
  invalid values do not poison the file, and changed semantics affect the next
  plan but never an already committed one. Shutdown under concurrent dispatch
  satisfies DR-BR-24 and XV-18. *Not satisfied by* cleanup triggered by the
  terminal event, by releasing only the plan, by a task rail reconstructed only
  from `list_sessions()`, or by a clean idle shutdown.
- **BR-G-42 — The named scale envelope passes fixed budgets.** Using §9.4's
  exact fixtures, reference profile, sample rules, and ceilings, record critical
  click feedback, command/frozen-scope receipt latency, plan projection build
  and memory, inventory slim-projection build and per-projection memory,
  unchanged-parameter and changed-parameter window latency, bounded detail-query
  row and decode counts, `preview_selection` at depth 32, and history
  summary/detail latency over the exact retained-item fixture. It also records
  event-drain latency and peak identity-deduplicated transport custody under
  the stated normal burst/rate and maximum reachable no-`Gap` shape using the
  SH-G-8 definition above. It proves no `Gap` occurs below the ordinary
  envelope. The ordinary pytest
  deterministically asserts query count, decoded row count,
  allocation-sensitive object count, queue bound/coalescing, and fixture shape;
  the named benchmark command runs cold and warm cases separately and records
  machine/runtime identity. *Not satisfied by* choosing sizes after seeing
  results, reporting averages without the declared percentile/maximum,
  measuring payload bytes, whole-process memory, or a short/shared-string
  fixture instead of the declared live custody roots, folding terminal result
  graphs into transport, omitting one root class or achieved high-water mark,
  allowing normal-load gaps, or using many empty history runs instead of a
  large retained run.

  **Current status:** the exact logical-time fixture and standalone
  installed-wheel benchmark harness have landed, while the separate
  beyond-envelope overflow regression remains passing. The fixed 150 ms
  progress-only linger and focused regressions have landed. Benchmark evidence
  is now bounded/streamed and manifest-checked, final assembly is outside the
  measured child lifetime, event acceptance is independent of diagnostic
  whole-runtime completeness, and the old 16 MiB line is retired. The
  path-local retained-state sizer, frozen/disjoint realistic corpus, and
  production-path three-fresh-process runner have also landed. The runner
  verifies real built-in deque roots, the exact quiescent per-task 128/64/64
  no-`Gap` shape and ordered cleanup, terminal path-cut reporting, and clean
  source/dependency/runtime/digest authority. The committed calibration-a
  artifact now records the normative 1,376,690-byte ordinary and
  1,534,946-byte exact-maximum union measurements. A byte ceiling, acceptance
  result, and independent holdout-b have not landed. The 2026-08-13 run of
  archived commit `288969426d6e005bac7a7e540e0cfdbacf28f9eb` passed exact
  event truth, ordering, no-`Gap`, latency, cadence, identity, and clean-exit
  predicates. Its 67,375,104-byte whole-Job delta is not transport-custody
  evidence and neither passes nor fails this realigned clause. BR-G-42's event
  portion and SH-G-8 remain open without claiming a byte limit or acceptance
  result.
- **BR-G-45 — Terminal artifacts and completed-task retention are bounded
  separately.** For one exact 100,000-subject completion, calibration and a
  later independent holdout measure the complete per-completion artifact set:
  the core `Terminal(OperationResult.items)` retained by dispatcher custody,
  its adapter `SessionEventView`, the terminal `SessionRecordView` and
  `OperationResultView.items`, serialization/native return values, browser
  retry/presentation copies, and the post-callback representation. The
  identity ledger reports shared and distinct objects without either omitting
  or double-charging them. Calibration fixes separate native, serialized, and
  renderer-retained ceilings before holdout; it also records construction,
  delivery, presentation, release, and settlement latency so a memory pass
  cannot hide a frozen window.

  A separate aggregate policy fixes the maximum completed-task bytes and exact
  representations retained before presentation, during callback or release
  retry, after successful `release_terminal_session`, and after explicit
  `close_task`. It preserves the reviewed plan, exact retry authority, and a
  truthful result when durable history is degraded. Repeated complete/release/
  close cycles and the maximum permitted completed-task set must reach the
  declared plateau; a task-count cap alone is not a byte policy. **Current
  status: OPEN.** No realistic 100,000-subject calibration, frozen ceilings,
  aggregate policy, or independent holdout has landed. *Not satisfied by*
  measuring only `SessionRecordView`, excluding the full terminal event,
  reusing one interned path/detail value, measuring an empty/summary result,
  clearing truth before its presentation/retry boundary, assuming degraded
  history can reconstruct it, or treating SH-G-8/SH-G-15 as substitutes.
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
`tests/interfaces/web/test_terminal_artifact_scale.py`. Their gate tests retain the
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

BR-G-19, BR-G-43, and BR-G-44 are cross-cutting release gates and therefore
apply to every row even where not repeated. Product goals 1–5 are witnessed,
respectively, by `{34,35,42}`, `{12,20,24,37,39}`,
`{18,36,39,40,41}`, `{6,32,35,39}`, and `{15,20,21,37,39,41}`.

### Regression watchlist (existing M1)

These are preservation guards, not restatements of the new gates. Every
currently existing target passes before bridge work; changing an old assertion or fixture to
accommodate the bridge is a regression unless the governing DR explicitly
changes that behavior. Commands are repository-root PowerShell commands and use
stable files/symbols rather than line numbers. A row may run more tests than its
named XV because that is safer than maintaining a brittle node-id list. XV-19's
split transport/static files and two later surface files are created by slices
2, 5, and 6 and become mandatory as each lands.

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
| `XV-19` ids-in, inert text out, independent origin check | `.\.venv\Scripts\python.exe -m pytest -q tests/interfaces/web/test_commands.py tests/interfaces/web/test_transport.py tests/interfaces/web/test_slots.py tests/interfaces/web/test_transport_headed.py tests/interfaces/web/test_frontend_static.py tests/interfaces/web/test_sync_surface.py tests/interfaces/web/test_inventory_surface.py` | The real page-JS → pinned pywebview return → production `textContent` round trip and NamiSync-owned sink scan become executable across slices 2, 5, and 6; the split transport/static files plus both later surface files are required because one layer alone cannot prove the full chain / slices 2, 5, 6 |
| `XV-20` stateless checkpoint | `.\.venv\Scripts\python.exe -m pytest -q tests/test_executor_pipeline.py` | Selection re-derivation and bridge progress must not motivate count-coupled checkpoint behavior in execution / C, slice 5 |
| M0/Stage 5 CLI behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_cli.py` | The initial Stage 5.5 lanes left this file byte-for-byte unchanged; the integrated adversarial closure adds only the permanent irreversible-update admission regression described by BR-G-17. Every prior explicit sync, history, inventory, and integrity command remains behaviorally unchanged. Slice 1 may later replace only the no-subcommand/entry-point expectations required by the launcher decision / B, C, D, slice 1 |
| Planner helper behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_planner.py` | `_depth`, `_parent`, and `_is_descendant` are pure relocations; no cleanup or semantic drift is allowed / A |
| Scanner hostile names, cancellation, and walk completeness | `.\.venv\Scripts\python.exe -m pytest -q tests/test_scanner.py` | Parameterizing the walk must preserve literal names, escaped/unrepresentable reporting, identity-cycle handling, cancellation checks, and every existing incompleteness cause / B |
| Recorder receipt, range, and transaction behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_recorder_inventory_integrity.py tests/test_recorder_concurrency.py` | Scope enters the payload hash and missing marking gains a third branch; idempotent transaction and concurrency behavior must not weaken / B, D |
| Inventory/integrity payload and pause behavior | `.\.venv\Scripts\python.exe -m pytest -q tests/test_inventory_workflow.py tests/test_inventory_runtime.py tests/test_payload_roundtrip.py` | A kind-aware shared validator and expanded frozen subject set must preserve integrity v1, pause order, and incomplete-scope settlement / B, C, D |
| Service facade and import boundary | `.\.venv\Scripts\python.exe -m pytest -q tests/test_service.py tests/test_package.py` then `.\.venv\Scripts\lint-imports.exe` | New lifts, state, launcher, and web adapter must preserve primitives-only views, lazy CLI imports, shutdown order, and every layer edge / D, slices 1–3 |

A lane runs every row naming it before merge. D runs all Stage 5.5 rows because
it integrates A/B/C. Every Stage 6 slice runs its named rows plus its
`test_br_g_*` module. Before Stage 5.5 integration, before each vertical slice
(5–7), and before release, BR-G-44's full-suite command is mandatory; this
watchlist never authorizes a partial-suite sign-off.

The BR-G-44 release evidence is the unedited output of:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
git diff --check
```

The pytest summary must contain no skipped, xfailed, or xpassed bridge gate on
the supported Windows profile. The implementation change also records the
collected `test_br_g_*` node ids, so a misspelled or undiscovered gate test
cannot disappear behind a green full-suite total.

### Stage 6

Regrouped by department. The change from the original ordering is **slice 4**:
flatten, window, search, filter, and anchor resolution were previously built
inside the plan tree and reused implicitly by inventory, which made the
inventory work depend on plan work it does not need. Extracting the
tree-agnostic presentation core lets the plan and inventory surfaces proceed as
a parallel pair.

| # | Department | Slice | Depends on | Acceptance gate |
| --- | --- | --- | --- | --- |
| 0 | Host | pywebview reality spike | nothing | BR-G-30 |
| 1 | Host | Promote the spike into `bridge.py` / `host.py`; hard dependency; packaged assets; launcher entry point; forced Edge Chromium; single instance | 0 | BR-G-19, BR-G-31 |
| 2 | Transport | Command allowlist, JSON encoding, opaque-id and folder-picker slots | 1 | BR-G-32 transport/picker/static-sink portion; the gate remains open for the production DOM |
| 3 | Transport | Event drain with coalescing, bounded wait, reliable backpressure, gap visibility, server-side drain guard | 2 | BR-G-33 plus XV-18 |
| GUI 1 (completed/realigned) | Presentation foundation | Native material behavior; Fluent neutral/Windows accent roles; exact authored status palette and semantic aliases in `tokens.css`; alias-only controls; fixed local Fluent icon registry; headed component gallery | 3 | SH-G-11, SH-G-12, SH-G-13 foundations and SH-G-14 closed; visual contract in `DESKTOP_UI.md` |
| 4 (completed/realigned) | Presentation core | Tree-agnostic flatten/window/search/filter and indexed anchor resolver over Lane A's ordered array; bounded installed operable tree renderer and honest shell frame | Lane A, GUI Break 1 | BR-G-2's Stage 6 clause, BR-G-34, SH-G-7 closed |
| 5 | Sync surface | Plan-tree presentation and memo, DR-BR-14 Progress identity, selection controls, indexed autoscroll; vertical sync slice end to end | 3, 4, Lane D | BR-G-32 plan-DOM portion, BR-G-35–37, and the plan portion of BR-G-42 |
| 6 | Integrity surface | Cached inventory projection, `patch_row`, `view_id` lifecycle, five resolution states, recursive folder context actions, scope-warning display, per-window detail query | 3, 4, Lane D | BR-G-32 inventory-DOM closure, BR-G-22, BR-G-23, BR-G-38, BR-G-39, and the inventory portion of BR-G-42 |
| 7 | Lifecycle | Database-paged history, settings, `ui-state.json`, task close sequence, clean shutdown, terminal-artifact retention policy | 5, 6 | BR-G-40, BR-G-41, BR-G-45, and the history portion of BR-G-42 |
| 8 | Docs/release | PyInstaller and frozen smoke, dependency lock and CI, license/source release material, as-built docs and README, `ui_mockup/` status, clean-checkout release proof | 7 | BR-G-43, BR-G-44, and shell-owned SH-G-15 |

**Ordering and parallelism.** Slice 0 shares nothing with Stage 5.5 and runs
beside it. It is the falsification gate for the chosen host and must complete
before later host/transport or vertical slices rely on assumptions no code has
verified against a real runtime. Slices 1→2→3 are serial within the
host/transport departments. GUI Break 1 closes after Slice 3 and before Slice 4;
its exact 13-swatch palette, semantic mappings, contrast/forced-colors evidence,
no-raw-surface-color rule, and closed local Fluent icon foundation are
normative in `DESKTOP_UI.md`.
Slice 4 additionally needs GUI Break 1, while its Lane A logic may be prepared
earlier. **Slices 5 and 6 are a parallel pair**
only once the host/transport chain through slice 3, slice 4, and Lane D are all
in. Slice 7 needs 5 and 6; slice 8 needs 7.

There is no fixed critical path without duration estimates. The dependency
shape is
`max(max(0→1→2→3→GUI1, A)→4, max(A,B,C)→D) → (5 ∥ 6) → 7 → 8`. Lanes B and C and slices
0–3 are therefore parallelizable prerequisites, not work "off" the path.
