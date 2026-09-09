# Presentation contract

This document owns the bridge-facing representation of plan and inventory facts: tree identity, view state, windows, selection presentation, search, sorting, and scale-sensitive presentation work. `BRIDGE.md` owns wire and transport; `INTERFACES.md` owns implemented task lifecycle; workflows own the authoritative domain facts. The browser renders supplied facts and never computes a plan, path policy, selection closure, or filesystem action.

## Tree identity and meaning

Trees are pure workflow-derived projections. Node identity is deterministic, scope-qualified, and opaque. Existing plan-path identity is BLAKE2b-128 with the `NamiSyncNodeV1` personalization over length-prefixed tree kind, scope identity, and canonical path key; operation members use the corresponding `NamiSyncMemberV1` domain including operation id. A collision is a structural failure, never first-row-wins. Same relative paths in different scopes must not share an id.

A path may contain multiple direct plan operations. The path node remains the path index; it becomes a container and exposes each direct operation exactly once as an immediate member child. Member order is deterministic before any view sort, and view sorting does not alter canonical indexes, membership, or execution order. Move decomposition renders one paired annotation rather than a second selection or paging unit. Structural folders never impersonate an operation.

Nodes retain the structural data needed by presentation—preorder position, depth, parent index, subtree extent, and id-to-position lookup—so the adapter does not reconstruct ancestry from paths. Exact internal fields remain owned by the source codec. The emitted tree preserves valid Unicode; only the renderer projects fixed layout controls or marker delimiters into visible text. Search uses raw display text and never decodes that projection.

## Views, windows, and selection

**Future surface.** Views are server-side, opaque, immutable/revisioned projections. A response formed for a stale lifecycle, selection, result, view-state, or projection revision returns a typed conflict and does not combine old structure with new detail. The browser keeps at most its current window and treats DOM rows as disposable. Server selection remains authoritative across virtualized rows, collapse, filters, and windows: a folder choice applies to all descendants, not only visible or filtered rows.

Selection changes batch a short user gesture and settle as one revisioned server mutation. The UI may show pending intent but must not optimistically invent a final selection. Selection preview derives directly from the retained selection/domain facts; it does not rebuild an unrelated whole review to answer a checkbox change.

A plan or inventory window indexes the complete post-filter visible sequence, not lexical database order. Fixed-height virtual rows and leading/trailing spacers keep scrolling stable. Window requests carry the appropriate revision, offset, and limit; a renderer requests the index it needs, commits only under its request generation, and suppresses duplicate uncovered-range requests. Changing search, collapse, filters, sorting, task detail, publication state, or retirement advances the local generation. Stale responses and queued animation frames are inert. `dispose()` disconnects observers/listeners and invalidates pending work before a root is removed.

**Future surface.** Inventory projections remain service-owned and coherent for live readers. Retention must be bounded, with truthful refusal when capacity is unavailable; publication must not expose partially rebuilt state. Acknowledgment, restore, and terminal changes refresh affected facts without invalidating a live reader silently. Cache topology, pinning, and patch/rebuild mechanisms are reopened implementation choices. History belongs to `HISTORY.md` and pages in the database.

## Search, filters, sorting, and follow

**Future surface.** Search is backend literal case-folded display matching. It has no regex, trimming, normalization, marker decoding, or path authority. The helper admits at most the 65,536-byte ingress limit; actual bridge query capacity is smaller when JSON overhead is included. A fixed 150 ms trailing debounce and last-intent-wins generation rule provide responsiveness. Client-side search is incorrect because the client owns only a window.

Filtering/collapse determine visible rows; rollups and selection retain their canonical meaning. Empty ancestors disappear from the visible sequence rather than leaving a skeletal tree. Acknowledged inventory rows hide by default but remain available through their facet; counts make the hidden population visible. Acknowledgment changes the visible sequence and refetches its window, but does not rewrite inventory rollup truth.

**Future surface.** New views and explicit reset use ascending canonical path-key order. A user may choose filename, size, or mtime ascending or descending; descending path-key, omitted/toggle direction, unknown columns, and inferred direction refuse. Sort only immediate siblings and use casefolded raw basename for filename, raw signed-64 file size and nanosecond mtime for file rows, unavailable-last in both directions, and canonical path-key as the stable tie-breaker. Do not sort formatted labels, copied-work bytes, directory descendants, or invented folder timestamps. Sort is process-live view state, never durable preference; it preserves tree identity, selection, recursive action scope, execution order, rollups, ledger truth, and integrity candidate order. A rebuild derives the retained chosen sort from the new immutable projection and publishes its permutation, indexes, and revisions atomically; window reads perform no I/O to discover sort keys.

**Future surface.** Follow mode resolves an active item to the nearest visible ancestor-or-self under the same collapse, filter, search, and result revision. If nothing in its chain is visible it reports `not-visible`, without mutating filters or inventing a root target. The client requests the returned index's window. User scrolling away turns follow off; only explicit action resumes it. Progress carries an opaque item identity, never a display path.

## Bounded work and focused measurement

Windowing must bound repeated query, decode, allocation, and serialization work, not merely response size. The current plan adapter memoizes trees per request. Future inventory windows must bound detail loading and repeated visible-sequence work; exact query, flattening, and caching mechanisms are chosen at implementation against the focused criteria below. Scale-sensitive changes need a focused profile, scaling axis, predeclared criterion, artifact, and rerun trigger under `DEFENSE.md` §7. No numeric presentation budget is invented here.

The retained M1 support target for applicable plan, inventory, and standalone integrity populations is 120,000 rows. It defines the supported target, not a claim about behavior at 120,001 and not a complete-object-byte reservation. Independently enforced population/request limits remain owned by their runtime components and `DEFENSE.md`; a presentation view must surface a truthful refusal rather than publish partial authority when its own admitted population cannot be represented safely.

Focused checks must catch the failures that small fixtures conceal: scope-qualified node ids, stable duplicate operation/warning identities, no path arithmetic in presentation, literal hostile display search, server-side folder selection across filtered/windows, stale-view refusal, no quadratic expansion over sibling roots, bounded visible-range work, and causal projection rebuild after terminal changes. Historical benchmark rows and fixed completion gates are in `obsolete/M1_BRIDGE.md`; they are provenance, not a substitute for a newly predeclared measurement contract.

## Accepted future outcomes

The unrealized review surface must let users inspect a complete, stable view of their reviewed plan/inventory facts; make selection and destructive intent truthful; remain usable with hostile names and large supported populations; and avoid stale UI actions acquiring authority. Future DTO layout, command names, caching topology, and intermediate delivery sequence are open design choices. The implemented visible-sequence helper admits window limits of `1..256`, and the renderer uses 28 px rows; these existing contracts remain active. Each implementation checkpoint must make those choices once, with a named owner and verification.

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
