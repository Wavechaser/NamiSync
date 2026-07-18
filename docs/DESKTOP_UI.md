# Desktop UI

Status: draft interaction contract. Current architecture schedules the desktop
for M3+, while the repository goal treats it as active product scope. Toolkit is
not selected; Qt-specific PoC regressions below apply if Qt is chosen again.

## Purpose

The Windows desktop presents tasks, mandatory plan review, live session state,
inventory/integrity evidence, and history. It is a thin adapter over dispatcher
and workflows. It never computes plans, decides sync safety, writes SQLite,
directly mutates files, or invents a second domain session lifecycle.

## Task Model And Rail

The newest-first scrollable rail contains stable-height task cards with activity
state, source/subject and target where applicable, completion date, close action,
and mini progress. The session table is live-state authority; durable task
grouping later links to history without making CLI/service activities require a
task parent.

Closing a terminal task explicitly drops its live `SessionStore` record; durable
history remains. Closing a queued-unrun task first waits for its discarded audit
event to be delivered or visibly reports audit degradation. Closing a busy task
offers pause only for a kind whose registration supports it and otherwise asks
for phase-specific cancellation; it waits for actual session/thread completion.
It never destroys a live worker because a UI `busy` flag changed early.

## Single-Page Task Shell

One page contains editable recent-folder controls, options, status, progress,
Plan/Inventory toggle, tree, filters, and log/detail access. Up to five source
and target recents are maintained separately. Invalid/unusable input is shown
inline with an actionable fix, not represented only by disabled buttons.

Changing plan-only options invalidates plan but preserves inventory and current
view. Changing a location invalidates only state tied to that location and does
not force the Plan view unconditionally.

## Plan Review And Execution

Plan session completes before review. The Plan tree is directory-nested and
shows operation kind, dependencies, reason, source/destination, bytes, hashes or
evidence, conflict/block state, and status. Rolled-up counts/sizes reflect the
active All/Changes/Moves/Conflicts filter.

A folder rename is presentation grouping over its per-file moves, full mkdir
chain, and cleanup dependencies. Expanding it reveals real executable operation
ids/outcomes; grouping never becomes a hidden directory-level mutation.

Blocked operations do not disable unrelated dependency-closed work globally.
Any future partial selection recomputes dependencies/capacity and shows deferred
outcomes. Verify-after-execution is disclosed in scope/operation presentation.
Commit binds the reviewed plan fingerprint and exact dependency-closed selection
digest, then starts a new execution session and fresh preflight. Editing the
selection invalidates the commitment. Refusal is visibly different from
success.

No automatic/unattended UI execution bypasses commitment. Cancel/pause text
explains the current phase, in-flight temp behavior, retained completed work,
and lock release/resume consequences. Resume returns to the back of the volume
queue and never interrupts currently running work.

## Inventory And Integrity

Inventory tree is distinct retained state with All/Verified/Baseline/
Unbaselined/Missing/Reappeared/Acknowledged filters and live counts. Mismatch is
visually prominent and persistent, distinct from ordinary modification.

Inventory actions share one action definition across menus/buttons/context:
inventory refresh, selected verify, baseline, rebaseline, import hashes,
acknowledge/restore missing, and copy path. Scope labels include active-filter
and visible present-row count. Right-click first selects the valid index under
the pointer; blank space acts on nothing.

Baseline/verify automatically inventory when needed. Selected verify uses scoped
refresh. Refreshed inventory is shown at the scan-to-hash handoff; per-file typed
outcomes update rows live. Linked verify marks only successfully executed
eligible files and affected bytes, never the whole directory or manual-plan
noops.

## Live State And Feedback

Progress snapshots are throttled and update overall/per-file bars, path, counts,
phase, and immediate placeholder throughput/ETA text. Later rolling metrics,
graph, follow mode, and live integrity follow consume events without changing
domain behavior. A user scroll cancels auto-follow until explicitly restored.

Partial failure groups by cause/path and suggests action. Completion while
unfocused may notify with accurate outcome and mismatch callout. Empty states
explain the next domain action. Search/filter never mutates underlying plan or
inventory.

## History

History dialog lists activity-aware envelopes/details and retention controls.
Subject-only activities never show source→target placeholders. Restoring setup
requires fresh planning. Pruned replay/detail is disclosed. History retention
applies on a writable store through workflow, not direct UI SQL.

## Threading And Worker Lifecycle

Dispatcher remains domain lifecycle owner. Toolkit adapters marshal event/result
callbacks to the GUI thread through declared receiver objects. A finishing old
worker cannot release a newer one; object deletion waits for actual thread
finish. Shutdown connects completion observation before testing running state and
uses event-aware waiting rather than blocking the UI thread needed for terminal
delivery.

Thread-affinity guards raise `RuntimeError` under all optimization modes. Tests
exercise selection/action/model logic without entering modal menus. If Qt is
used, proxy-style ownership, stylesheet subcontrols, and deferred deletion are
tested against Windows to prevent the PoC crashes.

## GUI Instance And CLI Coexistence

One desktop instance owns the desktop task shell and explains what the existing
instance is doing. This lock does not block read-only CLI or safe disjoint-volume
mutating CLI sessions; all mutations arbitrate through dispatcher volume locks.

## Theme And Layout

The shell is dark-only with accessible status/operation colors, alternating
rows, and styled progress. Color is never the sole outcome signal. Card/header
geometry remains stable as text appears; long paths elide with accessible full
text. Native controls retain visible affordances—styling a combo border must not
erase its arrow.

## Expectations Of Other Modules

- Dispatcher is the live session/task/control source and owns custody.
- Workflow adapters expose reviewed sync, inventory, integrity, import, history,
  and maintenance requests; UI never calls operation modules.
- Planner/preflight results provide immutable review/refusal models.
- Inventory/history readers provide typed view models with explicit scope and
  retention state.
- Core event/reason schemas remain presentation-neutral; UI maps them to text,
  color, accessibility, and suggested actions without changing semantics.
- Toolkit worker adapters marshal only interface work and cannot become a second
  recorder, scheduler, or session state machine.

## Latent Features

Drag/drop, rolling metrics, graphing, follow mode, notifications, guided empty
states, search, failure grouping, and mapping management consume existing typed
state/events/actions. They add presentation state only. Task grouping and
annotations use history/annotation contracts; they never make GUI task ids a
requirement for CLI or service sessions.

## PoC Regression Requirements

The acceptance suite must retain coverage for: plan-wide blocked gating; stale
worker release/GC; close-before-thread-finish; overwritten status hints; missing
combo arrows; stacked-page excess height; progress floods; uncancelable import;
verify without inventory; stale plan rows; wrong paired-root gating; partial
failure rendering; proxy-style double-free; rotated/overlapping tabs and zero
height New button; manual-noop false verification; stale size/headline;
right-click wrong row/blank space; missed execution→verify handoff; card-height
jitter; bogus Exit shortcut; delayed throughput line; GUI-thread violations;
shutdown races/deadlock/crash; `assert` guard loss; subject-history rendering;
refusal shown as success; wrong-location fallback; modal menu test hang;
duplicated actions; ambiguous selected scope; plan/inventory invalidation;
forced view switch; baseline/verify without inventory; stale verification list;
missing summary count; full refresh for selected verify; whole-directory false
verification; silent invalid paths; and hidden verify-after-execution scope.

## Acceptance Criteria

- End-to-end plan review ends session/releases locks, displays complete intent,
  and execution starts only as a separately committed freshly guarded session.
- Task cards remain stable height and retain real status beneath temporary
  contention hints; stale worker completion cannot affect current task.
- Closing/shutdown during every phase cancels/drains without thread destruction,
  deadlock, timeout race, leaked custody, or event loss.
- All model/widget mutation callbacks run on GUI thread; injected off-thread call
  raises under normal and `python -O` runs.
- Progress stress stays responsive under fast-disk chunk rates and shows
  immediate phase/placeholder metrics before rate stabilizes.
- Plan filter counts/sizes and blocked/dependency enablement match planner
  selection; unrelated work is not globally disabled.
- Plan and Inventory state/view survive only the invalidations that semantically
  affect them.
- Every inventory action targets the pointer/explicit selection, discloses exact
  filtered scope, and no blank-space context action can target stale selection.
- Baseline/verify with empty inventory chains refresh automatically; selected
  verify avoids full scan; handoff displays current rows before hashing.
- Manual and linked verification update only actual scoped rows; mismatch,
  modified, missing, unsupported, canceled, and error are distinct.
- Refusal, all-noop, partial failure, canceled, recording-behind, and history
  degradation have truthful distinct headlines and accessibility text.
- A discarded queue item renders from `CANCELED+UNRUN`; a cancellation after
  work renders from `CANCELED+RAN`, regardless of operation count.
- Closing a terminal task drops only live session state; queued discard is
  audit-delivered first and neither action deletes durable history.
- Menu/button/context actions share label, shortcut, enablement, scope, and
  dispatch behavior from one source.
- History renders each activity kind and retained detail; retention actually
  persists through workflow.
- Offscreen tests never invoke a modal menu loop; presentation logic is isolated.
- Toolkit-specific style tests preserve combo arrows, tab/card geometry, New
  control visibility, and object ownership without crashes.
- Second desktop launch is refused with useful status while read-only/disjoint
  CLI behavior remains available under dispatcher policy.
- Dark theme meets contrast/non-color signaling requirements and long/empty text
  causes no layout jitter.
