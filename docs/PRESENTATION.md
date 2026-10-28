# Presentation contract

This document owns the bridge-facing representation of plan and inventory facts: tree identity, view state, windows, selection presentation, search, sorting, and scale-sensitive presentation work. `BRIDGE.md` owns wire and transport; `INTERFACES.md` owns implemented task lifecycle; workflows own the authoritative domain facts. The browser renders supplied facts and never computes a plan, path policy, selection closure, or filesystem action.

## Retained execution review and evidence classification

Task presentation is reduced once in the Python desktop adapter. Its bounded,
task/session-bound snapshots supply progress, control and terminal facts to the
existing shell; the browser owns formatting and local interaction state.
BRIDGE owns snapshot admission and delivery. A snapshot is not an execution
authorization, a complete outcome index or proof that an upstream Gap was
reconciled. Item windows and exact detail keep the independent bounds below.

The workflow retains the exact immutable core terminal result for a task-bound
execution. Its summary preserves the filesystem, recording, audit,
disposition, cancellation, phase, byte, error, recording-issue and omission
axes without carrying item details. Operation and automatic linked-verification
items have separate Plan-bounded indexes. Exact internal reads admit at most 256
operation identities before lookup and may return the immutable item references;
missing selected items remain unknown and emitted exclusion outcomes retain
their actual result.

The web adapter projects that truth onto the existing Plan summary and rows.
One execution revision guards the summary, window overlays and exact detail.
Before execution the summary has no session or terminal facts. During execution
it identifies the current session, retains compact operation and automatic-
verification facts separately, and exposes no ledger evidence. A terminal
session release replaces only facts proved by the captured workflow review: its
item-free result axes, typed failure counts, location-only trash context and
bounded retained item/evidence reads. Missing retained items remain unknown.
The adapter adds the matching delivered terminal record's UTC start and end
times to that Plan summary after capture. Both remain null before retained
terminal truth exists; a refusal retains the exact dispatcher timestamps.
An unrun filesystem result may have a worker start time; a worker that never
started retains a null start.

Every Plan row with an operation identity receives that operation's compact
overlay, including an operation-bearing container. Structural rows remain null.
Compact operation facts are result, reason, recording state/reason and omission
count; compact automatic verification has its own result, reason, recording,
record disposition and omission count. Details and paths remain absent from a
256-row window because one reliable item can approach the event-envelope limit.
The separate exact one-operation detail read is available only after retained
review exists and keeps the operation item, automatic verification and current
ledger evidence distinct.

Complete committed selection owns target uniqueness. Every selected operation
touches its canonical target; MOVE and MOVE_UPDATE also touch their prior target,
with same-operation same-key touches deduplicated. A copy-like target is unique
only when that operation is the sole selected toucher. Failed or missing selected
operations still compete, while unselected exclusions do not.
The summary also derives the informational trash location from the exact target
root and run identity. It claims no directory existence, item count, complete
trash scan or purge availability.

The workflow classifies a bounded retained-operation window against one atomic
current-ledger snapshot. Only successful `copy`, `update`, and `move_update`
items are eligible, including empty files. Eligible items are `unrecorded` when
no matching committed successful receipt exists, and `superseded` when the
receipt cannot be joined to unique, coherent, current same-run target evidence.
Coherence requires exact agreement between the current observed `FileStat` and
the attested subject, including identity and managed metadata; partial stat
agreement cannot lend the attestation to a changed target.
Coherent copy provenance without a verification time is `recorded-copy`;
coherent readback or verify provenance with a verification time is
`already-verified`. Every other item is `not-applicable`.

Only `recorded-copy` and `already-verified` expose their stored `xxh3_128`
content evidence. The workflow receives complete-run target-ownership facts
as a trusted internal boolean derived by retained task review. E has
no browser surface, and later adapters never supply or reinterpret the bit.
The classifier never derives uniqueness from one window. Item and task recording degradation remain separate
axes, so the committed ledger snapshot decides whether an item has evidence.

Adapter result maps are independently bounded by the immutable Plan operation
membership already retained by the projection; they do not copy another complete
membership set. Live replay equality compares compact facts, not an unbounded
event body, and changes no revision for an equal replay. A `Gap` records only the
minimum and maximum observed `first_missed_seq`;
it is visible uncertainty, not a
lost-item count or a claim about the entire intervening sequence range. Terminal
reconciliation never erases that history.

A result window admits at most the existing 256 Plan rows before any workflow or
ledger read. Retained operation and automatic-verification lookups use only the
distinct requested operation identities; current evidence uses one bounded
workflow query over those identities. Adapter task/session/generation, Plan view
and execution revisions are snapshotted before those external reads and exactly
revalidated afterward. Pre-execution and live windows perform no ledger query,
and no window or detail scans the complete run.

## Tree identity and meaning

Trees are pure workflow-derived projections. Node identity is deterministic, scope-qualified, and opaque. Existing plan-path identity is BLAKE2b-128 with the `NamiSyncNodeV1` personalization over length-prefixed tree kind, scope identity, and canonical path key; operation members use the corresponding `NamiSyncMemberV1` domain including operation id. A collision is a structural failure, never first-row-wins. Same relative paths in different scopes must not share an id.

A path may contain multiple direct plan operations. The path node remains the path index; it becomes a container and exposes each direct operation exactly once as an immediate member child. Member order is deterministic before any view sort, and view sorting does not alter canonical indexes, membership, or execution order. Move decomposition renders one paired annotation rather than a second selection or paging unit. Structural folders never impersonate an operation.

The Plan projection classifies display actions independently of immutable
operations. RECASE and pure MOVE operations whose old and new parent paths
have the same Windows path key display and filter as `rename`; root-level
renames follow the same rule. Cross-parent MOVE remains `move`, and MOVE_UPDATE
remains `move_update` even in place because it changes content. Canonical rows
retain the actual operation kind and root-relative prior path internally. The
table uses the derived kind and shows `renamed from` the bounded old filename
or a generic previous-location note for moves. Full paths and complete notice
text are available through a revisioned exact one-node Plan detail read during
planning; execution results and diagnostics retain operation truth.
This changes no operation, dependency, selection or execution behavior.

Prior-location groups attach to the deepest proper old-path ancestor observed
as a target directory that survives at the same Windows path key in immutable
reviewed intent; root is the fallback. Unblocked directory removal, move or
recase excludes its old prefix and descendants, independently of selection.
Newly created replacements and inferred destination ancestors are not evidence
of old-directory survival. Missing surviving context is added structurally.
Each attachment groups by the move's target parent; a directory move counts as
one item. Presentation renames have no prior-location group; MOVE_UPDATE keeps
its group, including an in-place update. Groups start collapsed when a fresh
Plan view opens, and reopening an existing view retains its expansion state.
Groups and their expandable prior contents are informational and
contribute no execution selection, facet counts or folder bytes. Their label
uses a bounded destination hint (empty for root, an ellipsis for omitted
ancestors), and the group peer resolves its canonical target
parent, or the first canonical moved item for a root destination.

Explicit move-group reveal is revisioned presentation navigation. It expands
the destination's ancestors, clears only search/category filters that obstruct
that exact row, preserves sort and execution selection, and returns its rootless
index with the updated summary. Ordinary anchors and execution follow keep their
existing read-only nearest-visible-ancestor semantics.

Nodes retain the structural data needed by presentation—preorder position, depth, parent index, subtree extent, and id-to-position lookup—so the adapter does not reconstruct ancestry from paths. Exact internal fields remain owned by the source codec. The emitted tree preserves valid Unicode; only the renderer projects fixed layout controls or marker delimiters into visible text. Search uses raw display text and never decodes that projection.

Row serialization bounds display and notice labels to 300 UTF-16 units and rename
names and destination hints to 255 without splitting Unicode characters. Search,
sort and reveal retain the immutable complete server facts. Plan scan notices
retain the scanned side and warning code while bounding the path and explanation
separately. Inventory window labels use basenames; flat scan notices use a warning
code plus bounded path tail, and omit the repeated full warning path. Exact Plan details
preserve original path spelling and a source/target discriminator for the path.
Canonical operation details additionally carry an exact source-relative path
only when their reviewed source observation exists. Unsupported placeholders,
target-only operations and structural/prior nodes do not infer source paths.
They do not infer a warning's root from operation metadata. The read is one
node-id lookup under the current task/view revision, without filesystem or ledger
I/O. Execution detail remains separately guarded by its execution revision.
The browser joins these relative facts to established summary roots only for
detail display, preserving machine values and original spelling. Plan path
origin selects its source or target root; previous, destination and execution
path facts use target. Inventory detail and global scan-scope paths use its
nullable published root, retaining relative text when unavailable. Joining adds
no filesystem access, disclosure context or action authority.

## Views, windows, and selection

Plan and Inventory use one server view-transition and cache implementation.
Their owners supply sorting, matching and direct selection contributions;
shared mechanics check revision capacity, stage replacement values and publish
together. Expected revisions remain guarded by each domain entry point.
Sort or collapse alone reuses matching-scope counts. Selection replacement
preserves ordering and visibility when the domain owner guarantees unchanged
topology; a new Inventory publication rebuilds against its new projection.
Domain selection, workflow effects and row serialization remain separate.

Plan views are server-side, opaque, immutable/revisioned projections. A response formed for a stale lifecycle, selection, result, view-state, or projection revision returns a typed conflict and does not combine old structure with new detail. The browser keeps at most its current 256-row window and treats DOM rows as disposable. Server selection remains authoritative across virtualized rows, collapse, filters, and windows. A Plan header bulk gesture applies to all selectable operations whose own rows match the current search and operation filters; a folder gesture applies to matching descendants only. Both include matches outside the loaded window and under collapsed folders. Sorting, collapse and scroll do not change gesture membership. View changes alone never alter selection, and Execute always uses the complete current selection, including hidden operations. Workflow dependency closure can reselect an operation outside the view when a chosen operation requires it; safety exclusions remain in force. Inventory read views and their separate complete-folder Refresh and visibility actions have desktop controls.

The synthetic Plan root remains internal to the projection and its complete-plan
rollups, but is not a table row or a second whole-plan checkbox. Plan window
offsets, totals, row indexes, depths, parent/child indexes and anchors are
rootless public coordinates: the root's direct children start at index/depth
zero with no public parent; an anchor that resolves only to the root returns
null. The header checkbox is the sole whole-view bulk control.

Selection changes batch a short user gesture and settle as one revisioned server mutation. Scoped Plan gestures carry expected view and selection revisions, resolve the full query and guard both revisions under the task owner before applying one workflow mutation. A stale gesture has no effect. The UI may show pending intent but must not optimistically invent a final selection. Selection preview derives directly from the retained selection/domain facts; it does not rebuild an unrelated whole review to answer a checkbox change.

Opening a Plan view receives the immutable selected membership in its projection
and a matching revision/state/aggregate summary from one service capture. The
task owner rechecks its generation before publishing the view. Public preview
continues to include operation-level detail for CLI/API consumers. Direct leaf
gestures need no folder-wide selectable-membership derivation; folder gestures
still expand the full tree through workflow safety selection.

An operation-bearing directory's eligibility rollup includes descendants. The
selection refresh validates its own operation using the direct contribution
(rollup minus immediate-child rollups), never the subtree total. Descendant
eligibility cannot authorize an unavailable parent operation.

Plan and Inventory share row highlighting, separate from checkbox selection. Plain clicks replace the
highlighted set; Ctrl-click toggles; Shift-click extends from the retained
anchor; Ctrl+Shift-click adds a range. Arrow keys move focus, Shift+arrows
extend, and Escape clears. An initial arrow sends `node_id: null`, which the
server resolves relative to its retained focus. Repeated arrows retain one
latest desired visible index, clamped on every input; their final endpoint uses
the existing `replace` or `extend` gesture with a server-supplied node identity.
An off-window endpoint is resolved through a revisioned window read. This is
not a deselection gesture, and Python continues to own range membership.
The browser sends only a compact gesture endpoint with expected view/highlight revisions. Python
resolves ranges against the full ordered visible view, including off-window rows;
multiple highlighted rows contribute only their directly associated file or
operation. A single highlighted folder retains matching descendant scope.
When a target is outside the retained window, the
browser requests that window before painting the returned focus/highlight flags.
An off-window moving highlight requests up to 32 leading rows before the
authoritative focus index, clamped at zero, within the unchanged 256-row limit.
This provides leading coverage when browser focus reveals preceding rows;
in-window and pointer highlight reads retain the displayed window offset.
Window rows carry highlight flags; scrolling, sorting and collapse preserve them,
while search/filter changes clear them. Pointer highlighting does not request a
keyboard focus ring; `:focus-visible` remains the keyboard-only ring. Checkboxes
change membership without changing highlighting, and a checkbox inside
a highlighted range applies to that range. Highlight-driven selection also
carries Plan's execution-selection revision before one atomic workflow mutation.
Inventory instead fences its file membership with the publication/view and
highlight revisions; it creates no workflow operation. Inventory Home/End resolve
the first/last visible row through the same bounded read and highlight queue.

A first Inventory view opened from a scan checks every indexed file,
including files outside the current filter or window; folder checkboxes reflect
their matching descendants. Warnings and empty folders remain nonselectable.
Every later publication, including explicit Refresh, integrity-owned scoped scans
and acknowledgements, retains surviving checkbox choices. New rows start unchecked;
rows absent from the replacement leave selection. Missing ledger rows retain their
checkbox state. Failed scans retaining an earlier publication do not reset selection.
Execution-associated ledger browsing without a scan keeps its empty
initial selection. Checking a row changes no workflow eligibility or action authority.

Plan and Inventory navigation retain at most one read in flight and one latest
pending target. Each surface's scrolling, endpoint lookup and highlight refresh share
read admission. Pointer replacement likewise supersedes unsubmitted navigation;
toggle, add-range and other scope-dependent gestures retain individual mutation
admission with captured revisions. Later pointer, wheel, touch, non-navigation
keyboard, search, view, task or lifecycle input retires pending navigation and
its authority to paint, focus or report feedback. Already submitted highlight
mutations still settle and are never replayed. A subsequent fresh window may
reconcile their matching authoritative receipt without moving keyboard focus.
Highlighted selection preserves the revisions displayed at the gesture; a
conflict asks the user to review the current highlight and select again instead
of silently applying selection to a changed range. Passive row replacement
restores the actually focused row; only an accepted keyboard navigation result
uses the server highlight as a new focus target.
Input interruption retires keyboard/highlight intent separately from compatible
scroll reads. Repeated wheel, pointer or touch events preserve a useful in-flight
scroll read; viewport coverage and travel direction still decide its adoption.
Loaded-row gestures and explicit navigation retain their replacement authority,
and view, task and lifecycle changes retain their existing ownership fences.

Plan scoped highlighted selection retains a finite under-10-second cost gate on the
supported Windows host, with exact matched count and post-mutation scope and
selection assertions. [PERFORMANCE](PERFORMANCE.md#selected-plan-and-execution-ui-observations)
owns the fixture, measured interval, rerun triggers and historical observation.

A plan or inventory window indexes the complete post-filter visible sequence, not lexical database order. Fixed-height virtual rows and leading/trailing spacers keep scrolling stable. Window requests carry the appropriate revision, offset, and limit; a renderer requests the index it needs, commits only under its request generation, and suppresses duplicate uncovered-range requests. Changing search, collapse, filters, sorting, task detail, publication state, or retirement advances the local generation. Stale responses and queued animation frames are inert. `dispose()` disconnects observers/listeners and invalidates pending work before a root is removed.

Plan and Inventory use one outer viewport for horizontal and vertical scrolling,
with a sticky 24 px header. The row area's height is the viewport's client height
minus that header; client height already excludes a horizontal scrollbar. Row
index zero maps to scrollTop zero because the row origin and sticky occlusion
both occupy the same header height. Coverage, overlap, follow and keyboard reveal
use this row area. Scroll observations, resize observations and retained offsets
belong to the outer viewport. Inventory keeps its semantic tree and active
descendant on the rows element: the generic tree accepts an optional viewport
and top inset while its default remains the root with no inset. Focus restoration
preserves scrolling; explicit keyboard movement reveals the complete target row
below the header. The outer viewport alone owns the stable vertical gutter and
header/body column alignment.

Inventory publication reloads preserve a visible non-notice row and its pixel
offset within the viewport. The existing bounded window anchor lookup resolves
that identity in the new view before loading its 256-row window; the lookup is
never rendered. If the row has disappeared or no longer matches the view, the
old scroll offset is clamped to the new row extent and retained viewport height.
Viewport restoration is passive: its anchor does not become the active row or
take focus. The active row retains its separate anchor, and enabled integrity
Follow remains responsible for revealing current work after load. Task, pane,
session and reload generations retire late restoration reads.

`table_controller.js` owns the common viewport geometry, coverage, request
generations, settlement and programmatic reveal. The Plan panel and Inventory's
tree adapter keep row rendering and focus policy: Plan uses roving grid rows;
Inventory uses an active descendant and its own Refresh target. Neither panel
keeps a second copy of the controller's pending-window or travel state.
Tree hands its requests to the app and reports their retirement. Plan's app owns
reads across panel reuse; the panel supplies demand, so review replacement,
empty external publication and teardown retire that demand silently. Other
viewport cancellations retain their existing callback to the owning app.

Plan and Inventory scrolling prefetch within 64 rows of the loaded edge in the
direction of travel. Placement retains 32 rows behind travel within one requested
256-row window, clamped at the sequence endpoints. Only the travel-side edge
triggers prefetch; the trailing margin cannot cause stationary ping-pong.
Actual returned rows determine coverage, including short pages; the requested
start is not clamped to `total - 256`, which could pin a short tail page away
from the viewport.
Repeating the same start is unnecessary only when its loaded window already
contains 256 rows or reaches the sequence end; a short nonterminal window may
still need another read after resize. A settled scroll commit schedules no extra
reconciliation frame. Passive replacement restores scroll before tree active-row
reconciliation. Programmatic scroll suppression matches the assigned offset;
a different browser-adjusted offset may update travel but cannot disable Follow
without a manual-input signal.
Keyboard and programmatic reveals rebase travel direction. Hidden viewports
retire scroll intent; resize does not invent a travel direction.
Both surfaces use one app-owned navigation reader per retained task and surface,
with one running job and only the latest pending job across review replacement.
Each job owns its settlement; renderer cancellation retires the exact viewport
job, not another highlight or Follow read belonging to the same review. An old
viewport's internal retry cannot overtake a newer navigation request. Geometry and
request generations remain with the shared table controller. Mutation custody
and initial/view-action reads retain their independent ordering.
An uncovered viewport coalesces to its latest intent with at most one navigation
read in flight.
Same-direction scroll positions retain useful early reads: a response with current task,
session, publication, action/view and highlight ownership may publish when it
overlaps the current viewport. The renderer then reconciles coverage and requests
another window for changed demand. Covered rows retain useful early requests;
reversal retires obsolete intent before replacing it behind the running read.
A later navigation demand has its own request
revision; settlement of the old read cannot clear that newer queued demand. Window reads do not
disable the whole review or remount unchanged rows. View/selection/execute actions
retain their separate pending and revision guards, so a later window response
cannot restore older interactive facts. The retained browser window stays bounded
at 256 rows. Background execution refresh waits for complete foreground view,
highlight, selection, and scroll reads. It adopts only while the same review and
foreground epoch, view, task/session, and displayed offset
remain current. Independently invalidated reads preserve one dirty replay at the
accepted offset and cannot publish result facts or retire exact detail, including
when the total population is larger.

Full Plan reloads obey the same foreground ownership rule: a reload admitted
before or during a user interaction cannot replace the review owning that
interaction. Compatible authoritative summary facts reconcile in place without
rolling back newer foreground revisions. Execution window reconciliation remains
pending until a read can be adopted at the retained offset after the interaction.
Both background pumps and full Plan reload use the same freshness decision:
retired ownership is silent; newer foreground work, demand or incompatible
retained context keeps one reread. This decision precedes transport-success
handling, so a failed old read cannot erase independently newer demand. A current
failure alone stops without polling. Paired window/detail observations settle together
before their ownership decision.

Inventory read views retain one immutable workflow projection, its complete sort
permutation and its derived `VisibleSequence` at task scope. A released execution
may publish its original target's current ledger with an initially empty file
selection, while retaining Plan review. Actual scan provenance is independent
of this publication identity and is coherently absent when no scan exists;
view/selection gestures preserve it. Its browser tree
uses an explicit 24 px geometry; the generic tree default remains
28 px. Spacer, viewport and keyboard calculations share the invocation's height,
while the same generation and active-node ownership rules remain authoritative.
Every Inventory callback owns its own promise and tree generation; retiring a
queued intent resolves it with null, never a newer result. Same-direction scroll positions share an in-flight scroll
generation instead of creating replacement callbacks. The tree passes the desired
window offset separately from its navigation target index. A scroll commit must
overlap the current viewport and chooses its active row from that viewport,
not its original requested index. Changed demand is reconciled after settlement;
a short response for unchanged demand does not initiate an automatic retry loop.
Keyboard and external requests retain exact intent-generation checks. A failed
or blocked read explicitly settles only its matching tree generation. An unchanged
viewport does not retry; movement since that request retains one reconciliation
for the changed demand, and later viewport movement can retry. A stale null result cannot
settle a newer keyboard or external request. Covered returns, loaded-row gestures, replacement
requests and disposal retire obsolete intent through the tree's optional
`requestCancelled(generation)` callback, after invalidation. A successful commit
does not emit cancellation. Navigation, view/action, session and publication
replacement also retire queued work. Dispatch rechecks ownership and current
action/loading/close eligibility; obsolete results and errors are silent.
Scrolling introduces no action-pending state. Initial and view-action follow-up
windows keep their independent action ordering and may overlap a retired
viewport read while it drains; that read cannot adopt or dispatch obsolete
queued work. Keyboard targets retain precedence until a newer user scroll or
loaded-row gesture replaces them. The browser retains one 256-row window.
Inventory checkboxes start empty and retain exact file row IDs independently of
row highlights and the active/detail row. Folder and header gestures apply to
files matching the current search/facets in their complete server-owned scope,
including collapsed and off-window matches. A checkbox in a highlighted range
applies only to directly highlighted matching files when multiple rows are
highlighted; highlighted folders do not add unhighlighted descendants. A singly
highlighted folder, or a folder checkbox outside the highlighted set, retains
recursive matching scope. Folder checkboxes still aggregate descendant membership.
Changing the view alone does
not change membership; selected totals still include hidden files. Warnings are
informational and directories provide membership only. Labels disclose matching
scope; selected/hidden-by-filter counts disclose retained hidden membership.
Refresh and missing-row visibility continue to use complete explicit scope.
Passive selection/result replacement retains the live outer viewport and the
focused checkbox without scrolling it into view. Only accepted keyboard
navigation reveals its new focus. Live result reads defer to newer foreground
reads/highlights and replay a dirty refresh at the retained offset after they settle.

Ordinary integrity starts freeze this complete nonempty selection against the
current released publication. Inventory task/session generations fence live
outcomes and reject stale delivery; result facts have an independent revision
and exact request/session/mode/location/row binding. The server retains only the
latest ordinary generation, replacing it on admission and repairing a live Gap
from the terminal result at release. Window/detail overlays expose only their
bounded subjects and stay distinct from current ledger evidence and scan scope.
Refresh preserves these activity facts. Failed admission restores prior state;
Close retires it. The standalone desktop exposes selection and mode controls,
current-session pause/resume/cancel, and separate window/detail result overlays.
Selection replies replace authoritative summary/window state; uncertain or stale
gestures reload that state rather than replaying membership changes. Rebaseline
confirmation binds the selected count and scope to the exact publication revision.

Execution tasks can attach ordinary current-location work. Their current activity
request/session/kind is independent of original Plan request, execution session,
terminal timestamps, operation results and automatic verification. Plan detail,
anchors/follow and Plan again retain original identity; task status follows
current activity. Reconstruction gets original execution identity from the Plan
summary, never from a current auxiliary session. Auxiliary progress cannot drive
Plan follow or replace its terminal result.

**Verify copied** supplies successful execution copy-target paths to
ordinary Verify without changing Inventory checkbox selection. It is repeatable,
includes successful work in partial or linked executions, and refuses an empty
copied population. The server freezes copied paths under current-task admission;
the browser supplies no paths. Scanning may create a new row for a formerly
unrecorded copy, so copied-scope outcome admission binds normalized path,
location and mode and establishes a one-to-one path/row identity. Selected-scope
ordinary operations retain their exact selected-row membership. Neither scope
can accept foreign or conflicting subjects.
An identity/revision-admitted original execution summary with an explicitly
empty copied population disables the copied action with guidance to select files
for current-state Verify. Unknown facts preserve server admission; they do not
mean empty and trigger no readiness read or polling. Later inventory work does
not rewrite this original-execution fact.

One latest ordinary result generation covers both start scopes. Each bounded
window is indexed once; detail retains generation and row identity checks.
Terminal normalization repairs a live Gap and retains outcomes completed before
pause, including a truthful empty result. Ledger state stays separate from
ordinary outcomes; baselined is not verified. A scan supplies its own provenance
and may supersede execution-relative evidence. An ordinary outcome supplies the
primary row state only for the current session or its displayed scan request.
A newer successful publication shows current ledger state while retaining prior
activity results separately in Details; a pending or failed Refresh preserves
the prior publication. View and selection revisions do not change that provenance.
There is no separate manual
result slot, readiness read or first-attempt claim.

Plan/Verify navigation retains pane state while retiring pending reads from the
pane being left. Current ordinary controls address only their current session;
returning to Plan preserves its focused item, selection, follow and viewport.
An auxiliary scan or ordinary-integrity release marks current execution evidence
dirty and retires its cached or pending detail. Returning to Plan consumes the
existing bounded refresh at the retained offset, even when the original
execution revision is unchanged. Original execution outcomes remain retained.
Refresh retains its complete explicit scan scope and current activity request,
including recovery from a displayed prior publication. It needs no exact-
verification-forfeiture confirmation because that one-shot feature is retired.
Rebaseline consent and ordinary revision/admission fences remain unchanged.

One existing view revision fences selection, windows and details. A stale request
or revision changes nothing; selection changes advance the revision. Selection
requires a current released, clean publication and cannot race admission or a
pending visibility effect. Replacements retain only surviving exact file row IDs and leave new rows
unselected. Replacements retain surviving exact highlighted node identities,
anchor and focus within the same location, and invalidate prior gestures through
advancing revisions. Removed identities are pruned. A retained focus suppressed
by the current filter/collapse has no visible index and shows no stale details.
Compact prefixes of complete selected membership and matching selectable/selected
files provide constant-time per-row tri-state; hidden counts are computed at selection/view changes, not on
each window read. Mode eligibility remains workflow-owned and no integrity
operation starts through this selection API.
Repeated windows
reuse these values and serialize only the requested slice; current detail uses
one exact ledger row read for domain subjects. Its separate revisioned snapshot
supplies complete scan-time paths and warning diagnostics for rowless folders
and notices without ledger or filesystem access. The browser never derives their
full paths from compact labels. Window checksum presentation uses only the immutable
row's recorded attestation: nullable lowercase full digest, rendered as an eight
character prefix with the full value in a tooltip. Presence/freshness changes
do not erase that evidence or trigger per-row reads or hashing. View updates
stage replacement sequence values before
advancing their revision. Open, update, window, detail and same-task Refresh are
available through the production bridge. The desktop read renderer is
implemented, including whole/selected Refresh and missing-item visibility
controls. A new released scan stages a complete replacement, preserving
search, facets, sort and surviving collapsed nodes while advancing the existing
view revision. Failed construction preserves the prior publication, which stays
readable during a new scan. Its request identity remains distinct from the
task's current scan request. Incomplete scan evidence does not veto a complete
ledger projection. History belongs to `HISTORY.md` and pages in the database.

Visibility gestures act on complete missing-row domain membership, regardless of
search, facets, collapse or the loaded window. A current released publication
and exact revision are required. The response retains bounded actual conditional
outcomes before rebuilding; failure leaves prior reads available but marks their
publication dirty, excluding another visibility effect until whole replacement
succeeds. Rebuilds preserve concurrent view gestures and advance the view revision.
Visibility changes introduce no ordinary-integrity overlay; selection remains
the separate revisioned presentation state described above.

## Search, filters, sorting, and follow

Plan and inventory search use backend literal case-folded projection display matching. Inventory retains full relative-path matching even though its wire labels are basenames. They have no regex, trimming, normalization, marker decoding, or path authority. The helper admits at most the 65,536-byte ingress limit; actual bridge query capacity is smaller when JSON overhead is included. The Plan renderer's fixed 150 ms trailing debounce keeps the field editable during an in-flight view refresh; only the latest newer query is retained for sequential dispatch after the current receipt. Client-side search is incorrect because the client owns only a window.

Filtering/collapse determine visible rows; the Plan Status rollups and effective execution selection retain their complete-plan meaning. The Plan header and filtered folder checkbox states report the active search/filter scope so their visible state agrees with their gesture; collapse does not narrow it. Empty ancestors disappear from the visible sequence rather than leaving a skeletal tree. Acknowledged inventory rows are excluded as direct matches by default but remain available through their facet; an acknowledged folder can remain as structural context for matching descendants. Counts make the hidden population visible. Acknowledgment changes the visible sequence and refetches its window, but does not rewrite inventory rollup truth.

New Plan views and explicit reset use ascending canonical path-key order. A user may choose filename, size, or mtime ascending or descending; descending path-key, omitted/toggle direction, unknown columns, and inferred direction refuse. Sort immediate siblings by casefolded raw basename, raw byte size or nanosecond mtime, never formatted labels. Size sorting keeps file-path rows before folders in both directions; values reverse within each group, with unavailable values last within that group. Prior-location and notice structures follow those groups. Filename/mtime sorting retains its existing unavailable-last semantics. Canonical path-key/node-id order breaks ties. Directories use only their own reviewed mtime, never a descendant timestamp.

Folder sizes are static sums of the plan's retained displayed file facts in its destination-oriented hierarchy. Count each canonical file path once, not each operation member; identical duplicate facts contribute once, conflicting sizes contribute no claimed bytes and mark the total partial. Removals use their displayed target-file size. Moves contribute at their destination, never again through prior-location annotations. Reuse child totals without counting a nested folder and its descendants twice. Unknown or blocked facts and incomplete/scoped plan scans mark the total partial; known blocked-file sizes still contribute. Directory facts themselves contribute no file bytes; empty directories have size zero. Selection, filters, collapse and the 256-row window never narrow these totals. Selected required bytes remain the separate execution estimate.

Accumulate exact Python integers in one reverse parent pass; before publishing a row, a total above MAX_SIGNED_64 becomes null with an explicit overflow note. Overflow remains visible in every containing folder; unaffected siblings retain their own totals. This approved display policy leaves the signed-64 bridge contract and execution admission unchanged. Null totals sort as unavailable inside the folder group, not as zero.

The aggregation cost is linear in retained operation memberships plus path-tree
nodes: visit each direct fact once, then add each child total to its parent
once. The finite regression witness
`test_plan_review_fixture_folder_sizes_match_independent_path_facts_and_survive_selection`
uses the existing 100,000-operation/120,000-projection-row fixture, including its
32-layer hierarchy. An independent destination-path-prefix oracle checks all
folder totals and a selection overlay checks unchanged values. Its elapsed
console output includes fixture construction and is diagnostic only, not a
latency gate. Rerun on changes to fact precedence, grouping, aggregation or
selection overlays; prior benchmark receipts do not certify the new totals.

Sort is process-live view state, never durable preference; it preserves tree identity, selection, recursive action scope, execution order, rollups, and domain truth. A rebuild derives the retained chosen sort from the new immutable projection and publishes its permutation, indexes, and revisions atomically; a failed rebuild preserves the previous complete view, and window reads perform no I/O to discover sort keys. Inventory projection sorting and its desktop read consumer are implemented. Inventory raw own-object sort keys remain distinct from complete folder byte rollups. Synthetic ancestors have no own size or mtime; real directories use only their observed values. Warnings retain an attachment-order tail and never affect domain rollups or scope.

Follow resolves the active Plan operation or ordinary Inventory integrity item to the nearest
visible ancestor-or-self under the current collapse, filter, search, sort and
revision. Nothing visible means no target; never mutate filters or invent a
root. Automatic follow is restricted to unfiltered, search-free canonical order.
User scroll-away or changing sort/search/filter disables it until explicit enable;
returning to canonical alone does not resume it. One-shot Go to the current item
remains available in other views without enabling follow. DESKTOP_UI owns the
floating controls and override behavior.
Manual scroll-away still disables Follow while a pending view/selection change,
inventory action, loading or Close blocks row interaction. That notification does
not authorize active-row changes or other blocked gestures.

Reuse `PlanProjection.operation_node_id_by_id` and existing visible-anchor
resolution for off-window operations; the browser must not derive node IDs or
retain a full mapping. The read-only active-operation variant of `get_plan_anchor`
is bound to the current task/session and view revision for execution and post-copy
verification. Inventory uses its projection's row index and the same ancestor
walk, bound to the current ordinary baseline/verify/rebaseline session, location,
frozen scope and view revision. Copied scope uses workflow-owned pure admission;
lookup never changes scope associations or reads the ledger. A scan-created row
absent from the displayed projection has no target. Scan, terminal and no-active
states do not invent one. Existing Plan node-anchor callers are unchanged;
BRIDGE owns the exact read-only requests.

One app-local Follow transaction uses the shared table reader for anchor and
bounded window lookup. Each domain supplies identity and adoption rules. Pane,
session, view and user-intent changes retire the exact request. Passive Inventory
publication/reveal uses the existing tree painter and controller. It retains the
active node identity and keyboard position while that row is outside the loaded
window, removing only `aria-activedescendant` until the row renders again. It
never chooses a replacement. Refresh selected retains the node target. Focusing
the tree while the active row is off-window does not reveal it, move the viewport
or override Follow. Explicit arrow/Home/End navigation starts from the retained
row; a click or manual scroll re-engages ordinary active-row navigation. Clear
identity only when authoritative current-view evidence establishes disappearance,
including filter/search/collapse/deletion, not because a bounded window omits it.
Collapsing an active row's parent therefore clears that row and its Refresh
selected target; expanding the parent does not restore the former active identity.
Follow and Go never retarget highlighting, checkbox selection, detail or keyboard
focus.

## Bounded work and focused measurement

Plan scroll-read settlement is separate from response adoption: rejected or
retired responses release only their matching renderer request. An unchanged
failed viewport does not retry automatically; a changed viewport or navigation
re-entry can request its rows again without replacing the accepted window first.
Restoring the same focused row preserves scroll, while explicit movement to a
different keyboard target retains reveal behavior.

Windowing must bound repeated query, decode, allocation, and serialization work, not merely response size. The Plan adapter retains one complete immutable projection and applies selection as a rollup overlay without rebuilding its tree, notices, raw sort facts, or unrelated view state. Inventory windows reuse a cached visible sequence; exact current-detail reads do not reread the location. Scale-sensitive changes need a focused profile, scaling axis, predeclared criterion, artifact, and rerun trigger under `DEFENSE.md` §7. No numeric presentation budget is invented here.

The retained M1 support target for applicable plan, inventory, and standalone integrity populations is 120,000 rows. It defines the supported target, not a claim about behavior at 120,001 and not a complete-object-byte reservation. Independently enforced population/request limits remain owned by their runtime components and `DEFENSE.md`; a presentation view must surface a truthful refusal rather than publish partial authority when its own admitted population cannot be represented safely.

Focused checks must catch the failures that small fixtures conceal: scope-qualified node ids, stable duplicate operation/warning identities, no path arithmetic in presentation, literal hostile display search, server-side scoped folder/header selection across filtered/windows and collapsed folders, stale-view/selection refusal, no quadratic expansion over sibling roots, bounded visible-range work, and causal projection rebuild after terminal changes. Historical benchmark rows and fixed completion gates are in `obsolete/M1_BRIDGE.md`; they are provenance, not a substitute for a newly predeclared measurement contract.

## Implemented Plan and accepted future outcomes

The implemented Plan review surface lets users inspect a complete stable view of immutable review facts, inert notices, current server-owned selection and destructive intent without letting stale UI actions acquire authority. It preserves prior-path ancestry and paired move annotations, while operation groups remain non-folder membership containers. Its renderer retains only the current `1..256` row window and uses exact 24 px rows and matching virtual spacers. The inventory renderer retains the same bounded window with an explicit 24 px invocation of the generic `tree.js` foundation, whose default remains 28 px. Its Refresh and visibility controls pass server-owned node identities, never visible-row or browser-derived path scope. Refresh selected retains the active file or folder's node target across passive off-window publication; accepted arrow navigation updates highlighting and reads current item details, including a bounded off-window row lookup when needed. Actual removal from the current view clears the target and disables the action. Item-card visibility actions retain the card's displayed row independently.

The Plan summary displays workflow-derived selected/eligible counts, selected
required bytes, and planning issues (preflight refusals plus scan notices).
The short task-tab digest uses selected operations, not scanned items; zero
selected items does not make a nonempty plan empty. Each row exposes its
server-provided risk alongside its reason or notice. `filter_counts` is a complete-plan facet mapping `all` plus every
canonical Plan filter (`copy`, `mkdir`, `move`, `rename`, `update`,
`move_update`, `trash`, `delete`, `noop`, `blocked`, `unsupported`, `error`, and `notice`) to direct-row
counts. It is independent of search, active filters, collapse, sorting, and
the loaded window. Container rollups, prior-path context, and other structural
rows are excluded; unsupported blocked operations count as `unsupported`, other
blocked operations as `blocked`. Immutable plans contain no execution errors,
so `error` is zero. `all` is
the sum of the mutually exclusive operation and notice categories. Filtering
and windowing cannot redefine these summary facts. All is active when no
category filter is active; clicking it clears category filters without changing
search, sort, or selection. Activating any other filter deactivates All. The
shared Filter menu exposes every canonical category independently, including
zero counts. Selecting a category adds/removes only its canonical key; there are
no aggregate group toggles. The trigger always shows the number of selected
canonical categories, including zero, excluding All and search. It is accented
only with active categories. Plan's All item retains the complete-plan counter.
Beside the trigger, both pages show matching/total synthetic items. Matching
counts the complete search/filter-retained tree, including structural ancestors,
folded descendants and offscreen rows; total counts the full projection. Both
exclude the internal root. Collapse and viewport changes do not change these
counts. The existing view derivation caches its retained population once;
summary reads do not traverse the tree again.
Inventory reuses the menu with its existing ten facets and authoritative
rollup/notice counts; those categories overlap and are never summed into an All
counter. Inventory's All clears its category settings and retains the default
acknowledged-row visibility policy. Menu interaction changes no selection,
effect scope or server query semantics. Search keeps its 150 ms trailing debounce;
Enter or the inset search button submits immediately with a shared 150 ms guard
against repeated manual gestures. Pending refreshes retain the newest query.
The browser formats those exact decimal byte facts into binary display units
with two fixed decimal places, retaining trailing zeros; values below 1 KiB use
exact integer bytes. Integer rounding may promote a
label to the next unit, without feeding labels back into size sorting. Plan header gestures cycle a
chosen sibling sort from ascending to descending to canonical path order;
switching headers begins ascending, and the backend remains the sole sort owner.
DESKTOP_UI owns the blocking confirmation interaction and BRIDGE owns exact
request/revision admission and recovery.

Every successfully built, unexecuted plan reports neutral **Plan ready**, not
executable readiness. Execute independently requires preflight readiness and a
nonempty executable selection. Review preflight refreshes change-operation facts;
NOOP file facts remain as of the scans. Execution freshly checks all selected
operations, so later-detected NOOP drift can refuse execution before target
effects. A strictly empty plan says **Plan is empty**;
a nonempty plan with no search/filter matches says **No items match these filters**.
Neither navigation nor these labels change execution eligibility or selection.

Recall availability is a separate scan-time fact, independent of action reason,
blocked status and selection. Workflow projections retain positive visible
`RECALL_ON_DATA_ACCESS` evidence for ordinary and unsupported rows, including
actual observed directories. Synthetic ancestors do not inherit the fact, and
missing inventory rows never present old availability as current. The server's
overlapping `recall` filter keeps parent context without changing operation
eligibility. Its item count differs from the bridge's file-only scan aggregate;
the latter is fixed across view gestures and is not an execution download estimate.
Plan and Inventory expose this fact through plain cloud row indicators and
the **Remote files** filter. Aggregate status-panel placement remains deferred.

The planning page distinguishes execution preflight refusal, an invalid
execution commitment and another unrun refusal. It explains each closed
preflight code using fixed actionable wording and guides the user to resolve
the issue and use **Plan again**. The existing retained execution summary
preserves that diagnosis after terminal release and navigation. A refusal
after admission keeps selection committed; the page never implies that
the old plan can be edited or executed again. A refused reviewed plan rejected
before admission keeps its existing reviewing state. BRIDGE owns the bounded
origin/code disclosure and exact lifecycle relationships.

## Focused scale acceptance

The inventory projection criterion retains the reference profile and sampling
in [PERFORMANCE](PERFORMANCE.md#reference-profile-and-collection). It remains
open acceptance work; the runtime population target alone does not close it.

| Behavior | Retained criterion |
| --- | --- |
| Cold base / information-heavy inventory projection | 3 s / 6 s maximum |

The former Plan/UI click, receipt, projection, view, selection and scoped
process-memory numbers, including inventory representation memory, are
advisory historical comparison points under [DEFENSE §7](DEFENSE.md#7-quantitative-evidence-and-measurement-authority).
Selected Plan/UI cases are available as optional observations in
[PERFORMANCE](PERFORMANCE.md#selected-plan-and-execution-ui-observations);
the inventory memory number remains historical without a current selected
driver.
Fixture/action correctness, actual 120,000/240,000-row populations, bounded
work and counted scaling remain required where owned by tests and runtime
contracts. No deterministic object-graph wall or six-entry cache topology is
introduced by the old memory figures.

## Measurement methods

[PERFORMANCE](PERFORMANCE.md) owns the selected Plan, receipt and execution UI
methods, provenance and historical results. Their timing and empirical
representation-memory observations are optional; the inventory projection
criterion above and separate release, custody and settlement gates remain.

### Current Plan projection implementation

Projection construction uses private slotted row drafts, streams warning rows,
and releases completed tree/index intermediates before materialization. Move
peers are assigned before final nodes are built; consumed drafts are released
before publication. Source nodes remain stable across display sorts. Real sorts produce
compact source-position permutations and inverse ranks, preserving exact sibling
comparison and subtree contiguity without cloning projection nodes or identity
maps. PlanReviewState validates structure on acquisition and
retains only canonical and current orders. Search, filters and collapse reuse the
current order; reset can reuse canonical order.
Real sorts derive siblings from canonical order, stable-sort available raw
primary values and append unavailable siblings in their canonical tie order.
Internally generated orders use trusted publication; public construction still
validates malformed topology and permutations. No extra per-sort cache is kept.
Selection-only updates rebind orders to the new projection under the owner's
structural/key guarantee, so old
projection nodes are not kept alive by cached order references. Fresh acquisition
owns new orders even for an equal request ID; no in-place full replacement route
is exposed. Public malformed structure/order
rejection remains intact; trusted derivation reuses already validated inputs.

Changed-view matching retains each direct match and its parent chain, stopping
at an already retained ancestor. Visibility and accessibility metadata are then
derived from retained positions rather than repeated complete-array passes.
Empty, unfiltered search retains all rows without reading display text. Nonempty
search still uses literal Unicode casefolded
substring semantics: only a query that remains non-ASCII after casefolding can
skip ASCII displays; lowercase ASCII displays need no folded copy. Plan filters
use a private immutable positional 0/1 byte mask aligned with the source
projection. Public node-ID filters retain validation and weighted counts,
including matches hidden by collapse. These changes introduce no persistent
folded-text search cache.

Visible state retains compact source positions, inverse visible indexes and
sibling ordinals, plus retained direct-child counts. Counts are computed after
matching/ancestor retention and before collapse, preserving collapsed-parent
expandability. Each requested row derives its parent through the source-parent
inverse, its first child through the next global visible entry, its sibling size
through its parent's count, and expanded state through its retained-child count
and collapse state. Lookahead may read one entry beyond the 256-row window;
it never scans an entire sibling set. Ordinals and inverse indexes remain global
to keep arbitrary windows and deepest-visible-ancestor lookup bounded. Compact
values own immutable bytes, not read-only aliases of mutable buffers.

For a validated N-row structure retaining R rows and exposing V rows, filtered
or nonempty search examines at most N candidates, visits each retained ancestor
once, orders R positions, and derives metadata over V rows: O(N + R log R + V)
work excluding text lengths. Compact inverse/count populations and the Plan mask
add linear source-index storage; public filter-map validation retains its own
costs. Empty search skips display reads; all-retained derivation walks the cached
order, suppressing collapsed descendants. Creating fresh dense inverse/count
buffers also has a source-population cost.
Public structure validation and real sorting remain separate costs. Window reads
use O(limit) work and anchor resolution O(depth), independent of sibling width.
Named access/reference tests witness these distinctions; timing does not prove
complexity or waive the M1-7 budgets below.

The execution receipt path may reuse a workflow-derived selection only for the
exact checked plan and user-intent snapshot. Its construction-owned structural
cache retains references to the immutable plan, selected and deselected sets,
one operation-id-to-existing-operation index, and a scalar selected-byte bound;
it introduces no copied operation graph. The 100,000-operation receipt fixture
populates that index and selected set; its pristine deselection set is empty.
The separate projection memory case does not construct this execution cache.
These corrections invalidate prior source authority for a new acceptance run;
they do not change the budgets, old raw artifact or the fixture worker workload.
