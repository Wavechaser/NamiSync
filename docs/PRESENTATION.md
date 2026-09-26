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
terminal truth exists; an unrun refusal retains a null start and a real end.

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

Nodes retain the structural data needed by presentation—preorder position, depth, parent index, subtree extent, and id-to-position lookup—so the adapter does not reconstruct ancestry from paths. Exact internal fields remain owned by the source codec. The emitted tree preserves valid Unicode; only the renderer projects fixed layout controls or marker delimiters into visible text. Search uses raw display text and never decodes that projection.

## Views, windows, and selection

Plan views are server-side, opaque, immutable/revisioned projections. A response formed for a stale lifecycle, selection, result, view-state, or projection revision returns a typed conflict and does not combine old structure with new detail. The browser keeps at most its current 256-row window and treats DOM rows as disposable. Server selection remains authoritative across virtualized rows, collapse, filters, and windows. A Plan header bulk gesture applies to all selectable operations whose own rows match the current search and operation filters; a folder gesture applies to matching descendants only. Both include matches outside the loaded window and under collapsed folders. Sorting, collapse and scroll do not change gesture membership. View changes alone never alter selection, and Execute always uses the complete current selection, including hidden operations. Workflow dependency closure can reselect an operation outside the view when a chosen operation requires it; safety exclusions remain in force. Inventory views retain their separate accepted complete-folder contract but remain unrealized.

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

Row highlighting is separate from execution selection. Plain clicks replace the
highlighted set; Ctrl-click toggles; Shift-click extends from the retained
anchor; Ctrl+Shift-click adds a range. Arrow keys move focus, Shift+arrows
extend, and Escape clears. Arrow navigation sends `node_id: null`, which the
server resolves relative to its retained focus; it is not a deselection gesture.
The browser sends only a compact gesture endpoint with expected view/highlight revisions. Python
resolves ranges against the full ordered view, including off-window rows and
collapsed descendants; when a target is outside the retained window, the
browser requests that window before painting the returned focus/highlight flags.
Window rows carry highlight flags; scrolling, sorting and collapse preserve them,
while search/filter changes clear them. Pointer highlighting does not request a
keyboard focus ring; `:focus-visible` remains the keyboard-only ring. Checkboxes
change execution selection without changing highlighting, and a checkbox inside
a highlighted range applies to that range. Highlight-driven selection also
carries the execution-selection revision and is rejected as stale before one
atomic workflow mutation.

Scoped highlighted selection retains a finite under-10-second cost gate on the
supported Windows host, with exact matched count and post-mutation scope and
selection assertions. [PERFORMANCE](PERFORMANCE.md#selected-plan-and-execution-ui-observations)
owns the fixture, measured interval, rerun triggers and historical observation.

A plan or inventory window indexes the complete post-filter visible sequence, not lexical database order. Fixed-height virtual rows and leading/trailing spacers keep scrolling stable. Window requests carry the appropriate revision, offset, and limit; a renderer requests the index it needs, commits only under its request generation, and suppresses duplicate uncovered-range requests. Changing search, collapse, filters, sorting, task detail, publication state, or retirement advances the local generation. Stale responses and queued animation frames are inert. `dispose()` disconnects observers/listeners and invalidates pending work before a root is removed.

Plan scrolling within the loaded viewport coverage performs no fetch. An uncovered
viewport coalesces to its latest intent with at most one window read in flight;
returning to covered rows invalidates an obsolete result. Window reads do not
disable the whole review or remount unchanged rows. View/selection/execute actions
retain their separate pending and revision guards, so a later window response
cannot restore older interactive facts. The retained browser window stays bounded
at 256 rows. Background execution refresh waits for complete foreground view,
highlight, selection, and scroll reads. It adopts only while the same review and
foreground epoch, view, task/session, and displayed offset
remain current. Invalidated or rejected reads preserve one dirty replay at the
accepted offset and cannot publish result facts or retire exact detail, including
when the total population is larger.

**Future surface.** Inventory projections remain service-owned and coherent for live readers. Retention must be bounded, with truthful refusal when capacity is unavailable; publication must not expose partially rebuilt state. Acknowledgment, restore, and terminal changes refresh affected facts without invalidating a live reader silently. Cache topology, pinning, and patch/rebuild mechanisms are reopened implementation choices. History belongs to `HISTORY.md` and pages in the database.

## Search, filters, sorting, and follow

Plan search is backend literal case-folded display matching. It has no regex, trimming, normalization, marker decoding, or path authority. The helper admits at most the 65,536-byte ingress limit; actual bridge query capacity is smaller when JSON overhead is included. A fixed 150 ms trailing debounce keeps the field editable during an in-flight view refresh; only the latest newer query is retained for sequential dispatch after the current receipt. Client-side search is incorrect because the client owns only a window. Inventory search retains its accepted literal matching contract but remains unrealized.

Filtering/collapse determine visible rows; the Plan Status rollups and effective execution selection retain their complete-plan meaning. The Plan header and filtered folder checkbox states report the active search/filter scope so their visible state agrees with their gesture; collapse does not narrow it. Empty ancestors disappear from the visible sequence rather than leaving a skeletal tree. Acknowledged inventory rows hide by default but remain available through their facet; counts make the hidden population visible. Acknowledgment changes the visible sequence and refetches its window, but does not rewrite inventory rollup truth.

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

Sort is process-live view state, never durable preference; it preserves tree identity, selection, recursive action scope, execution order, rollups, and domain truth. A rebuild derives the retained chosen sort from the new immutable projection and publishes its permutation, indexes, and revisions atomically; a failed rebuild preserves the previous complete view, and window reads perform no I/O to discover sort keys. Inventory sorting retains its accepted contract but remains unrealized.

**M1-8-R0 surface.** Follow resolves the active operation to the nearest
visible ancestor-or-self under the current collapse, filter, search, sort and
revision. Nothing visible means no target; never mutate filters or invent a
root. Automatic follow is restricted to unfiltered, search-free canonical order.
User scroll-away or changing sort/search/filter disables it until explicit enable;
returning to canonical alone does not resume it. One-shot Go to current operation
remains available in other views without enabling follow. DESKTOP_UI owns the
floating controls and override behavior.

Reuse `PlanProjection.operation_node_id_by_id` and existing visible-anchor
resolution for off-window operations; the browser must not derive node IDs or
retain a full mapping. The read-only active-operation variant of `get_plan_anchor`
is bound to the current task/session and view revision for execution and post-copy
verification. Existing node-anchor callers retain their unchanged request shape. BRIDGE owns its exact wire extension;
standalone integrity/inventory following remains outside this batch.

## Bounded work and focused measurement

Windowing must bound repeated query, decode, allocation, and serialization work, not merely response size. The Plan adapter retains one complete immutable projection and applies selection as a rollup overlay without rebuilding its tree, notices, raw sort facts, or unrelated view state. Future inventory windows must bound detail loading and repeated visible-sequence work; exact query, flattening, and caching mechanisms are chosen at implementation against the focused criteria below. Scale-sensitive changes need a focused profile, scaling axis, predeclared criterion, artifact, and rerun trigger under `DEFENSE.md` §7. No numeric presentation budget is invented here.

The retained M1 support target for applicable plan, inventory, and standalone integrity populations is 120,000 rows. It defines the supported target, not a claim about behavior at 120,001 and not a complete-object-byte reservation. Independently enforced population/request limits remain owned by their runtime components and `DEFENSE.md`; a presentation view must surface a truthful refusal rather than publish partial authority when its own admitted population cannot be represented safely.

Focused checks must catch the failures that small fixtures conceal: scope-qualified node ids, stable duplicate operation/warning identities, no path arithmetic in presentation, literal hostile display search, server-side scoped folder/header selection across filtered/windows and collapsed folders, stale-view/selection refusal, no quadratic expansion over sibling roots, bounded visible-range work, and causal projection rebuild after terminal changes. Historical benchmark rows and fixed completion gates are in `obsolete/M1_BRIDGE.md`; they are provenance, not a substitute for a newly predeclared measurement contract.

## Implemented Plan and accepted future outcomes

The implemented Plan review surface lets users inspect a complete stable view of immutable review facts, inert notices, current server-owned selection and destructive intent without letting stale UI actions acquire authority. It preserves prior-path ancestry and paired move annotations, while operation groups remain non-folder membership containers. Its renderer retains only the current `1..256` row window and uses exact 24 px rows and matching virtual spacers. The generic `tree.js` inventory foundation retains its separate exact 28 px row contract. Inventory review and follow mode remain accepted future outcomes; their DTO layout, caching topology and intermediate delivery sequence remain open until implementation.

The Plan summary displays workflow-derived selected/eligible counts, selected
required bytes, and planning issues (preflight refusals plus scan notices).
The short task-tab digest uses selected operations, not scanned items; zero
selected items does not make a nonempty plan empty. Each row exposes its
server-provided risk alongside its reason or notice. `filter_counts` is a complete-plan facet mapping `all` plus every
canonical Plan filter (`copy`, `mkdir`, `move`, `recase`, `update`,
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
All, Copy, Move, Update and Remove controls remain visible even at zero; other
categories appear only when their count is positive. Group toggles combine
Copy/Mkdir, Move/Recase, Update/Move update, Trash/Delete (Remove), and
Error/Unsupported/Blocked (Error). Their main buttons toggle the whole group;
only the arrow opens a counted detail menu. A detail choice replaces that group's
facets, leaving other groups alone; the menu's All choice restores the whole
group. All, Noop and Notice remain ordinary toggles. Inactive Remove text turns
red only when its count exceeds one. Search keeps its 150 ms trailing debounce;
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
nonempty executable selection. A strictly empty plan says **Plan is empty**;
a nonempty plan with no search/filter matches says **No items match these filters**.
Neither navigation nor these labels change execution eligibility or selection.

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
