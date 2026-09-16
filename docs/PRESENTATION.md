# Presentation contract

This document owns the bridge-facing representation of plan and inventory facts: tree identity, view state, windows, selection presentation, search, sorting, and scale-sensitive presentation work. `BRIDGE.md` owns wire and transport; `INTERFACES.md` owns implemented task lifecycle; workflows own the authoritative domain facts. The browser renders supplied facts and never computes a plan, path policy, selection closure, or filesystem action.

## Tree identity and meaning

Trees are pure workflow-derived projections. Node identity is deterministic, scope-qualified, and opaque. Existing plan-path identity is BLAKE2b-128 with the `NamiSyncNodeV1` personalization over length-prefixed tree kind, scope identity, and canonical path key; operation members use the corresponding `NamiSyncMemberV1` domain including operation id. A collision is a structural failure, never first-row-wins. Same relative paths in different scopes must not share an id.

A path may contain multiple direct plan operations. The path node remains the path index; it becomes a container and exposes each direct operation exactly once as an immediate member child. Member order is deterministic before any view sort, and view sorting does not alter canonical indexes, membership, or execution order. Move decomposition renders one paired annotation rather than a second selection or paging unit. Structural folders never impersonate an operation.

Nodes retain the structural data needed by presentation—preorder position, depth, parent index, subtree extent, and id-to-position lookup—so the adapter does not reconstruct ancestry from paths. Exact internal fields remain owned by the source codec. The emitted tree preserves valid Unicode; only the renderer projects fixed layout controls or marker delimiters into visible text. Search uses raw display text and never decodes that projection.

## Views, windows, and selection

Plan views are server-side, opaque, immutable/revisioned projections. A response formed for a stale lifecycle, selection, result, view-state, or projection revision returns a typed conflict and does not combine old structure with new detail. The browser keeps at most its current 256-row window and treats DOM rows as disposable. Server selection remains authoritative across virtualized rows, collapse, filters, and windows: a folder choice applies to all descendants, not only visible or filtered rows. Inventory views retain this accepted contract but remain unrealized.

Selection changes batch a short user gesture and settle as one revisioned server mutation. The UI may show pending intent but must not optimistically invent a final selection. Selection preview derives directly from the retained selection/domain facts; it does not rebuild an unrelated whole review to answer a checkbox change.

A plan or inventory window indexes the complete post-filter visible sequence, not lexical database order. Fixed-height virtual rows and leading/trailing spacers keep scrolling stable. Window requests carry the appropriate revision, offset, and limit; a renderer requests the index it needs, commits only under its request generation, and suppresses duplicate uncovered-range requests. Changing search, collapse, filters, sorting, task detail, publication state, or retirement advances the local generation. Stale responses and queued animation frames are inert. `dispose()` disconnects observers/listeners and invalidates pending work before a root is removed.

Plan scrolling within the loaded viewport coverage performs no fetch. An uncovered
viewport coalesces to its latest intent with at most one window read in flight;
returning to covered rows invalidates an obsolete result. Window reads do not
disable the whole review or remount unchanged rows. View/selection/execute actions
retain their separate pending and revision guards, so a later window response
cannot restore older interactive facts. The retained browser window stays bounded
to 256 rows, including when the total population is larger.

**Future surface.** Inventory projections remain service-owned and coherent for live readers. Retention must be bounded, with truthful refusal when capacity is unavailable; publication must not expose partially rebuilt state. Acknowledgment, restore, and terminal changes refresh affected facts without invalidating a live reader silently. Cache topology, pinning, and patch/rebuild mechanisms are reopened implementation choices. History belongs to `HISTORY.md` and pages in the database.

## Search, filters, sorting, and follow

Plan search is backend literal case-folded display matching. It has no regex, trimming, normalization, marker decoding, or path authority. The helper admits at most the 65,536-byte ingress limit; actual bridge query capacity is smaller when JSON overhead is included. A fixed 150 ms trailing debounce and last-intent-wins generation rule provide responsiveness. Client-side search is incorrect because the client owns only a window. Inventory search retains this accepted contract but remains unrealized.

Filtering/collapse determine visible rows; rollups and selection retain their canonical meaning. Empty ancestors disappear from the visible sequence rather than leaving a skeletal tree. Acknowledged inventory rows hide by default but remain available through their facet; counts make the hidden population visible. Acknowledgment changes the visible sequence and refetches its window, but does not rewrite inventory rollup truth.

New Plan views and explicit reset use ascending canonical path-key order. A user may choose filename, size, or mtime ascending or descending; descending path-key, omitted/toggle direction, unknown columns, and inferred direction refuse. Sort only immediate siblings and use casefolded raw basename for filename, raw signed-64 file size and nanosecond mtime for operation-bearing file rows, unavailable-last in both directions, and canonical path-key as the stable tie-breaker. Do not sort formatted labels, copied-work bytes, directory descendants, or invented folder timestamps. An operation-bearing directory may use only its own reviewed mtime; structural/group/notice rows have no invented numeric key. Sort is process-live view state, never durable preference; it preserves tree identity, selection, recursive action scope, execution order, rollups, and domain truth. A rebuild derives the retained chosen sort from the new immutable projection and publishes its permutation, indexes, and revisions atomically; a failed rebuild preserves the previous complete view, and window reads perform no I/O to discover sort keys. Inventory sorting retains this accepted contract but remains unrealized.

**Future surface.** Follow mode resolves an active item to the nearest visible ancestor-or-self under the same collapse, filter, search, and result revision. If nothing in its chain is visible it reports `not-visible`, without mutating filters or inventing a root target. The client requests the returned index's window. User scrolling away turns follow off; only explicit action resumes it. Progress carries an opaque item identity, never a display path.

## Bounded work and focused measurement

Windowing must bound repeated query, decode, allocation, and serialization work, not merely response size. The Plan adapter retains one complete immutable projection and applies selection as a rollup overlay without rebuilding its tree, notices, raw sort facts, or unrelated view state. Future inventory windows must bound detail loading and repeated visible-sequence work; exact query, flattening, and caching mechanisms are chosen at implementation against the focused criteria below. Scale-sensitive changes need a focused profile, scaling axis, predeclared criterion, artifact, and rerun trigger under `DEFENSE.md` §7. No numeric presentation budget is invented here.

The retained M1 support target for applicable plan, inventory, and standalone integrity populations is 120,000 rows. It defines the supported target, not a claim about behavior at 120,001 and not a complete-object-byte reservation. Independently enforced population/request limits remain owned by their runtime components and `DEFENSE.md`; a presentation view must surface a truthful refusal rather than publish partial authority when its own admitted population cannot be represented safely.

Focused checks must catch the failures that small fixtures conceal: scope-qualified node ids, stable duplicate operation/warning identities, no path arithmetic in presentation, literal hostile display search, server-side folder selection across filtered/windows, stale-view refusal, no quadratic expansion over sibling roots, bounded visible-range work, and causal projection rebuild after terminal changes. Historical benchmark rows and fixed completion gates are in `obsolete/M1_BRIDGE.md`; they are provenance, not a substitute for a newly predeclared measurement contract.

## Implemented Plan and accepted future outcomes

The implemented Plan review surface lets users inspect a complete stable view of immutable review facts, inert notices, current server-owned selection and destructive intent without letting stale UI actions acquire authority. It preserves prior-path ancestry and paired move annotations, while operation groups remain non-folder membership containers. Its renderer retains only the current `1..256` row window and uses exact 24 px rows and matching virtual spacers. The generic `tree.js` inventory foundation retains its separate exact 28 px row contract. Inventory review, follow mode and later result-detail projection remain accepted future outcomes; their DTO layout, caching topology and intermediate delivery sequence remain open until implementation.

The Plan summary displays workflow-derived selected required bytes and destructive
operation count; each row exposes its server-provided risk alongside its reason
or notice. Filtering and windowing cannot redefine those selection facts.
DESKTOP_UI owns the blocking confirmation interaction and BRIDGE owns exact
request/revision admission and recovery.

## Focused scale acceptance

These remaining BR-G-42 criteria retain the shared reference profile and sampling
in [BRIDGE](BRIDGE.md#focused-measurement-profile). They remain open acceptance
work; the runtime population target alone does not close them.

| Behavior | Retained criterion |
| --- | --- |
| Local critical-click feedback | 50 ms maximum |
| Typed execute/control/one-row receipt, excluding admitted work | 100 ms p95; 250 ms maximum |
| Freeze/normalize a 100,000-subject scope | 500 ms p95; 1 s maximum |
| Cold 120,000-row base / 240,000-row information-heavy plan projection | 2 s / 4 s maximum |
| Cold base / information-heavy inventory projection | 3 s / 6 s maximum |
| Unchanged-parameter 256-row window | 250 ms p95; 500 ms maximum |
| Changed search/filter/collapse/sort/reset plus 256-row window at 240,000 rows | 1.5 s p95; 3 s maximum |
| Selection preview at depth 32 | 500 ms p95; 1 s maximum |
| Incremental plan projection process-memory measurement | 320 MiB maximum |
| Incremental inventory projection process-memory measurement | 384 MiB each; 2,304 MiB for a six-projection workload |

These process-memory measurements are scoped empirical criteria, not resurrected
128/192-MiB deterministic graph walls or a required six-entry cache topology.
Their fixture is 100,000 operation/subject rows plus up to 20,000 structural,
group, ghost or directory rows; information-heavy variants add 120,000 notices/
warnings. Every operation appears once, prior-path ancestors are included, and
path/dependency depth reaches 32. Informational fixtures retain seed 0x4E414D49,
stable typed-code cycling, indexed ASCII paths, null initial detail and duplicate
occurrences. The retired per-object byte-fill/maximum-task reservation companion
is archived, not acceptance authority.

Sorting covers balanced/widest siblings, tied/unavailable keys, Unicode names,
each allowed direction and reset; freeze raw keys and independently expected
orders before measurement. Record changed-sort-plus-window and unchanged windows
separately so fast variants cannot hide a failure. Measure attributable retained
state and construction overlap without imposing a complete-object census. Rerun
on key, projection, comparator, index, publication or retention changes. A seventh
view after six populated projections exercises truthful bounded retention/eviction;
it does not prescribe the implementation's cache mechanism. Timing claims use
DEFENSE's lowest sufficient evidence tier; no favorable observation promotes a
target into acceptance.

## M1-7 plan measurement procedure

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

The M1-7 plan projection, gesture and receipt budgets above are independently
predeclared, profile-scoped **Tier 2** SLOs under DEFENSE §7. Crossing workflow,
bridge and browser layers within the plan slice is not a cross-slice operation
gate. This evidence closes no setup/execution/inventory/integrity aggregate or
release-resource criterion; it derives no ceiling from calibration. Preserve
the budgets and fixed reference profile rather than tuning thresholds to runs.

The compact representation uses the successor
`tests/interfaces/web/m1_7_plan_compact_contract.json`, with separately frozen
compact authority and measurement files. The legacy contract/authority/results
remain preserved under their original names and meaning. The successor records
the actual source projection, cached canonical/current orders, compact buffer
widths and populations, and reference sharing. Its memory case retains a complete
120,000-row base review while constructing a 240,000-row heavy review; both
realize canonical and filename-descending orders and current 256-row windows.
Baseline follows artifact construction but precedes review construction; sampling
continues through both reviews, sort/window work and final retained-state checks.
This includes the original projection-construction overlap and added order/visible
storage, without changing the existing metric ID, 320 MiB maximum or five cold
children. It makes no six-view or whole-headed-process memory claim. The current
producer cannot label this representation as legacy evidence; validators reject
mixed contract/authority/artifact families. Legacy compatibility is confined to
reading and checking preserved evidence. There is no legacy fixture generator,
product-data admission path or second runtime representation; retire the legacy
reader when its evidence is archived and no longer needs active validation.

Ordinary synthetic authority, receipt and corruption tests take fresh deep
copies of the frozen compact fixture expectations. Their expected answers do
not invoke the live generator. Separate live tests construct both actual fixture
families and compare population, raw-order witnesses and retained descriptors
against those frozen expectations; actual sibling sorting is checked against
the frozen order. These test expectations never supply measurement observations.

Before measurement, freeze the finite source/instrument/validator file identities,
actual native runtime/dependencies/profile, installed wheel and measured installed
file hashes, exact fixture family counts and expected raw-key order witnesses.
For the completed P9 candidate, the historical file population is supplemented
by a before/after source/installed/wheel-member binding for `core/execution.py`;
M1_PLAN records its digest and raw evidence. This covers the shared execution
structure without changing the fixed contract or claiming that review memory
measures a paused execution index. Final integration checks the supplemental
physical bytes and Git-clean HEAD identity as well as the named population.
The separately reviewed authority manifest admits those exact values; syntactic
hash validity or a self-reported profile is insufficient. The candidate may be
frozen by immutable file/blob hashes before its final atomic commit; no unverified
product commit is required. That final commit must contain the measured bytes.
Bind measured product files across source, wheel archive and installed files,
not merely three independent self-reported hashes. After the atomic commit,
verify clean measured paths and matching HEAD Git-clean blob identities against
the authority; retain physical measured-file hashes separately from checkout
line-ending normalization.

Use five fresh children for each cold case and five fresh children with six timed
warm samples each for every warm case (30 total). Record child identities, case
membership and per-child sample ordinals; report process count and within/across-
child dispersion with each statistic. P95 is nearest rank, index
`ceil(0.95 * n) - 1` in ascending samples. Every changed-view sample restores its
prescribed initial state outside timing; every timed Execute uses a fresh eligible
plan. A repeated no-op cannot stand in for a changed search/filter/collapse/sort.

Installed headed cases publish one plan by default, or two cold/seven warm plans
for fresh execution/control samples. These are valid completed/released tasks
published before startup. Settle each fresh view sequentially with exactly one
public open followed by one public 256-row window read. Retain proof of the
initial `opened` disposition, current revision zero, exact task/request/session/
path identities, total row count and first-row identity; the independent validator
checks this fixture receipt. Ordinary selection still waits for every exact source
view outside timing. This prepares a current review for interaction measurements,
not concurrent cold-start latency; separate cold-construction cases remain timed.
Freeze their distinct task/request/plan-session/path identities
and prove each execution sample unused before admission. No private task/view
rewrite or synthetic startup event prepares a sample. Related idle views are
part of this finite fixture; the separate component memory case does not certify
their aggregate headed-process memory.

The fixed Plan case set contains 35 cases. Destructive Execute-to-modal,
Confirm-to-pending-frame and non-destructive Execute-to-pending-frame feedback
are separate 50 ms maximum cases. The non-destructive fixture deselects risk-bearing
operations through the authoritative service outside timing. The typed Execute
receipt starts at Confirm submission and ends at the actual TaskStartView,
including selection commitment and admission but excluding human decision time
and admitted execution work. It retains the 100 ms p95 / 250 ms maximum budget;
an outer asynchronous transport token is not that endpoint.
The passive headed receipt observer registers on the production document-message
channel before submission and removes its listener on settlement or timeout;
executable controls verify delivery alongside other listeners and reject missing
registration. Execution/control cases share this observer.

The contract identifies each fixture variant, untimed setup, timed transition,
endpoint and correctness assertion. Evaluate search, filter, collapse, all allowed
sort directions, reset and subsequent unchanged windows separately; do not pool
fast cases. Reset begins in a non-path sort and may cover explicit path-ascending
sorting only when deterministic tests prove the same measured mechanism. Include
balanced/widest siblings, ties/unavailable keys, raw numeric/Unicode cases, depth
32 and construction/staging overlap in the existing fixtures. The synthetic root
counts within the 20,000 structural allowance, not in addition to it.

Before the expensive sample set, run a separate untimed readiness pass against
the current frozen inputs. It covers all 35 contract IDs in 15 children: one
shared component child for the 21 non-memory cases, one isolated memory/staging
construction, and the 13 existing headed cases in fresh children. Selection runs
first and a failure stops the pass. Each case uses its existing setup and
correctness path with one transition; cold construction and memory have no
warmup. Full fixture populations remain intact. Readiness carries no timing or
retained-byte samples, does not replace quantitative acceptance, and cannot warm
or provide task state to the fresh measurement processes.
The parent process allows 600 seconds for the shared 21-case component readiness
group and 300 seconds for every other readiness child and each measurement child.
These are process liveness safeguards, separate from the fixed measurement
budgets; timeout leaves the collection incomplete and supplies no acceptance.

Selection setup identifies an enabled, checked operation row through the public
view and its connected checkbox. Warmup must publish pending and settle to an
advanced authoritative selection revision with that same row unchecked; the
measured action requeries that row. Public summary/window reads are untimed
witnesses, not asynchronous completion events for the synchronous mutation path.
The pending-frame criterion is unchanged; failure after verified eligibility is
a stop for review, not permission to delay product receipts or weaken the test.

Retain each checked child receipt atomically under a unique ignored run evidence
directory. A separate atomic index binds its frozen authority, case, planned
ordinal, launch/process identities, path and hash. Record attempts before launch;
failures and interruptions leave the collection incomplete and preserve receipts
already produced. This does not change measurement child or terminal schemas.
Partial evidence cannot satisfy the terminal validator and is not automatically
resumed, merged or reused. Any future reuse requires explicit validity review;
changing measured instrument bytes invalidates cross-revision reuse.

One verdict-free terminal artifact records genuine observations and provenance;
the independent validator checks exact case/count membership, source/profile and
fixture authority, P95 and maximum budgets. Validator corruption controls must
reach wrong-but-well-formed identities, wrong populations, missing/extra cases,
reused child identities and maximum-only failures. Local click feedback and typed
receipts use the installed headed production path; projection-only measurements
do not establish either. Deterministic structure/permutation and bounded-work
witnesses remain separate from elapsed time. Rerun after changes to any measured
source, key, comparator, index, publication, retention or admitted profile.

For the user-authorized R7 consolidation batch, affected checkpoint checks are
Tier 1 drift guards; run the full 35-case gate once at R7-G on the integrated
candidate. Freeze each checkpoint's dependency-based case selection before
editing. Selected noisy cases retain full fixture populations, five fresh
children, existing warm counts, independent receipt/correctness checking and
unchanged P95/maximum budgets. Test/parent/validator-only changes use affected
live-fixture, corruption and publication controls when no timed child changes.
Record the exclusion rationale rather than treating tests-only as an exemption.
Local evidence must bind source/instrument/validator/runtime and installed bytes;
it never satisfies the full terminal validator or renews P9 acceptance. Failed
local guards block the checkpoint. Do not pool slices or reuse their children in
the final full run. The [ablation register](M1_7_ABLATION_STUDY.md) owns checkpoint
commands and lineage; full acceptance remains pending until both terminal and
committed-source validation pass at closeout. Historical evidence is immutable.
