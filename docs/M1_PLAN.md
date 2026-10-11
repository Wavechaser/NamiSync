# M1 Delivery Register

This is the sole active M1 delivery register. Exact contracts and release criteria
remain with [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md),
[BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md),
[FEATURES](FEATURES.md), [TESTS](TESTS.md) and their component owners.
[M1-8's archived register](obsolete/M1_8_DELIVERY.md) retains its finite
R0–R3 and A1–A6/B1–B6 gates. The [archived post-M1-8 study](obsolete/POST_M1_8_ABLATION.md)
retains investigation, rejected proposals and superseded execution recipes;
the decisions still governing delivery are below. Historical observations
certify their recorded build and dependencies only.

## Scroll continuity and interruptible navigation — 2026-10-11

The user formalized three atomic units below. Base is `0580b1b`; preserve the
delivered compatible-response ownership and one-read/256-row bounds. Root owns
shared register/handoff/evidence; serialize overlapping frontend writers. Read
the current owners and direct consumers before each unit, including retained
SW instrumentation anchors and installed helpers. No row-schema migration,
bridge byte-counter change, renderer rewrite or filesystem/domain change.

| ID | Outcome, owners and finite consumers | Gate and commit boundary |
| --- | --- | --- |
| SN1 | Confirm Plan focus-induced scrolling and dropped-read settlement; correct demonstrated failures in `app.js`/`plan_review.js`, their task-shell/Plan probes and installed shell fixture. Keep explicit keyboard reveal and owner fences. | Reproduce each claimed failure or record a negative result; affected frontend and interfaces checks, installed Plan/task-shell witness, fresh review, one fix commit with PRESENTATION/DESKTOP_UI/BUGS/CHANGELOG. Never automatically loop failed reads. |
| SN2 | Directional placement and travel-side edge prefetch in Plan and Inventory: `app.js`, `plan_review.js`, `tree.js`, `inventory_review.js`, direct probes/native consumers and existing loading collector anchors. Covered viewport must not retire useful early reads; direction reversal, endpoints, hidden/resize and navigation retire stale intent correctly. | After SN1, focused no-ping-pong/one-read/256-row/ownership checks, interfaces and affected tools checks, installed tree/Inventory/shell, repeated matched 240/1,000-row/s measurements and fresh review. One performance commit; PERFORMANCE owns diagnostic results, no latency acceptance promise. |
| SN3 | Replace navigation backlog with at most one in-flight navigation read and one latest pending target. Other later input supersedes pending intent immediately; late responses cannot reclaim focus or highlighting/selection. Trace Plan highlight mutation and Inventory tree owners plus bridge/projection consumers before implementation. | After SN2, finalize finite action/target contract and affected consumers. Held repeats, release tail, reversal, pointer/scroll/view/task interruption, Shift-range and selection truth require delayed-response tests, affected departments and installed keyboard/pointer witnesses; fresh independent review and separate fix commit. No silent browser-owned selection policy. |

Evidence goes in ignored `build/scroll-navigation-20261011/`; unique receipts,
source manifests and failed controls remain retained. Existing SW native fixture
publication and fractional-geometry corrections stay active. The accepted
navigation outcome does not authorize bypassing server selection or mutation
custody; unresolved contract/effect changes need a coherent proposal before edits.
AGENTS recurrence and mandatory stops remain binding. No new defect expands scope.

SN1 is complete: focused negative/positive controls, 37 loading-method checks,
the final interfaces/tools neighborhood and installed `sn1-native-03` pass;
fresh review confirms source identity and ownership. Ordinary focus restoration
preserves scroll; explicit keyboard intent is attached before adoption's
synchronous detail render. Exact request settlement handles Settings and
zero-height restoration without failed-read loops. Earlier failed native and
geometry receipts remain evidence. SN1 is integrated as `940c7ef`.

SN2 proceeds from integrated SN1 `940c7ef`. Direction comes from viewport travel;
place the window with 32 rows behind and trigger only within 64 rows of the travel
edge. Clamp endpoints, retain useful early requests, and keep short/failing-window
settlement suppression. Product owners are Plan, tree and Inventory panel assets;
the app read lanes retain their ownership contracts. Direct consumers are their
Plan/tree/Inventory/task-shell probes, the existing shell-tree, Inventory and
task-shell native witnesses, and `table_loading.py`/its browser probe/method tests.
PRESENTATION and DESKTOP_UI own behavior; PERFORMANCE owns the matched SN1 versus
candidate study (three children per page, both 240 and 1,000 rows/s, retained
12-second forward/reverse trajectory). Keyboard setup must correlate the actual
adopted setup read and exact offset-minus-one target, without relying on old
placement or triggering an extra scroll-to-edge prefetch. Root owns these
measurement consumers and shared docs; the builder owns product/probes/subject
docs. No new latency threshold or native wheel/compositor claim is introduced.

SN2 is complete: focused Plan/tree/Inventory controls, 2,385 interfaces/tools
checks (3 skipped), the revised method's 406 tools checks (3 skipped), installed
tree `sn2-native-final-01` and Inventory/shell `sn2-native-retry-01` pass. Review
corrected the full-page endpoint assumption and verified the actual short-tail
case. Twelve matched installed children and independently reconstructed frame
gaps support delivery; PERFORMANCE owns results and limitations. Failed native
admission and initial keyboard-setup receipts remain retained. SN3 follows and
revalidates its read-admission and interruption seams against integrated SN2.

SN2 is integrated as `fac8ed0`. SN3 starts there: `app.js` owns Plan navigation
admission/custody/publication, while `tree.js` and `inventory_review.js` own the
Inventory desired index and request generation. `plan_review.js` supplies input
interruption at the panel boundary. Coalesce repeat navigation to an absolute
desired visible index and ordinary pointer replacement to its latest target,
sharing Plan read admission with scrolling.
Existing revisioned windows resolve off-window node IDs; existing highlight
commands retain server range/anchor policy. Retiring local intent cannot undo an
admitted mutation or authorize its replay. Scope-dependent pointer and checkbox
effects keep the revisions the user saw; a conflict must have no selection effect.
Noncoalescible toggle/add-range/selection commands retain individual custody.

The finite consumer population is the existing task-shell, Plan, tree and
Inventory browser probes/runners, existing installed shell/Inventory/tree
witnesses, and existing Python Plan highlight/bridge selection tests. Inspect
`plan_review.py`, `drain.py`, `commands.py` for preserved contract meaning; no
Python behavior or command/schema addition is currently needed. Migrate existing
loading instrumentation anchors/method fixtures only if changed signatures or
read ordering requires it. PRESENTATION/DESKTOP_UI own behavior and BRIDGE needs
an update only if its description of existing gesture use changes. Verify held
repeat endpoint/release tail/reversal/Shift anchor, pointer/scroll/search/view/task
interruption, stale success/error, admitted mutation custody and no replay in
delayed-response probes, then interfaces plus any changed tools consumers and
installed keyboard/pointer witnesses. Fresh review and one fix commit close SN3.

SN3 is complete: `sn3-neighborhood-final-01` passes 2,385 interfaces/tools
tests (3 existing privilege skips); `sn3-native-final-01` passes installed tree,
and `sn3-native-retry-02` passes Inventory/shell (2 in 46.33s) with user
foreground coordination and unchanged product/test inputs. Independent source
and evidence review closes the gate. Earlier incomplete native attempts and
the baseline negative control remain retained; no product correction was needed
for the successful retry. Rebuild the reviewed outcome from recovery `eba28a6`
on integrated SN2 `fac8ed0`, without merging the WIP. No production timing claim
is added for SN3; SN2's measured revision remains explicit in PERFORMANCE.

## Continuous-scroll adoption and follow-up measurements — 2026-10-09–10

The user reviewed the BC2–5 shared-mechanism finding and authorizes its coherent
Plan/Inventory correction, followed by measurement and narrower experiments.
This supersedes the investigation-only restriction for the outcomes below.
Row-schema migration is deferred; no renderer rewrite is authorized.

| ID | Outcome and population | Verification and commit boundary |
| --- | --- | --- |
| SW1 | Correct compatible scroll-window adoption together in `app.js`, `tree.js` and `plan_review.js`, with their direct browser/installed consumers and DESKTOP_UI/PRESENTATION documentation. Coalesce newer scroll demand without retiring compatible in-flight reads; reconcile coverage and active row against the current viewport. | Existing composition first, focused delayed-response/navigation/owner regressions, interfaces department and affected installed headed checks, independent review; one fix commit. Preserve task/session/publication/view/action/highlight fences, exact keyboard/external intent, one read and one 256-row window. |
| SW2 | Extend the existing loading collector and controls to report burst time from last input as well as first, observed frame cadence, and browser-event steady trajectories at 240 and 1,000 rows/s. Reuse bounded installed fixture/identity/restoration infrastructure. PERFORMANCE owns results. | Method controls and tools department, independent review; separate measurement commit. Three fresh children per page, 12-second forward/reverse trajectories, uncovered intervals and final settlement; freeze sources and serialize timing. No timing acceptance threshold or native wheel/compositor claim. |
| SW3 | Assess one-window edge-margin/directional prefetch after SW1/SW2 measurements. Approximately 64 rows is an experiment parameter, not an accepted latency guarantee. | Read-only design/measurement decision first; any justified implementation gets its own finite population, navigation/ownership/bound checks, repeated steady measurements and independent review before commit. No second retained window or concurrent read. |
| SW4 | Experiment with successfully encoded key byte counts and combined punctuation/key charges without changing the row schema. Bridge response and drain-prefix capture remain the owners. | Disposable bounded prototype, old/new differential tests for invalid text, overflow precedence and exact partial charges, real-window timing and bounded-cache analysis. Report findings before product delivery; do not weaken admission/custody or add unbounded/global key retention. |

Evidence belongs in `build/scroll-window-study-20261009/`, with directory
conventions and unique run receipts; preserve earlier evidence and failures.
Expand each implementation row before editing its product seam. AGENTS stops
remain binding. The user's review resolves the prior two-owner recurrence
decision; it does not authorize unrelated instance fixes. HANDOFF owns current
resumption context, and each delivered outcome gets tests/docs/review and a
separate coherent commit. SW3 and SW4 do not justify the deferred DTO migration.

SW1 is delivered in `93a13b8`. The approved recurrence
correction separates pending demand from read settlement: Inventory finishes
only the matching failed request without an automatic loop; old Plan navigation
cannot clear newer demand. Exact keyboard/external and task/session/publication/
view/action/highlight ownership remain intact. `inventory_review.js` and existing
failure/navigation probes are included in the finite consumer population.

Evidence: 59 frontend and 1,979 interfaces checks; installed Inventory
`sw-native-01`, tree `sw-native-retry-01`, and full task-shell
`sw-task-shell-20261010-02` pass. Eight ordinary shell-helper checks pass after
its fixture correction. The tree consumer observes current-viewport row 4 and
fractional border edges with unchanged tolerance. The native shell fixture now
waits for pointer-highlight publication before opening its menu: the old
already-highlighted/pending-empty predicate passed before the async response,
whose valid window replacement dismissed the menu. A foreground-owned trace
proves the race; no product menu change or weakened input guard was needed.
Independent review confirms the correction and atomic split. Failed receipts
and recovery ancestry remain evidence, not acceptance or mergeable commits.

SW2 method/results are complete and independently reviewed:
37 focused and 402 tools checks pass (three skips), twelve installed children
retain coverage/cadence and source/restoration identity. SW3 assessment is complete:
directional placement and a roughly 64-row margin are justified for a separate
implementation outcome. SW4's bounded disposable cache experiment and balanced
capture comparison are complete; production delivery still needs ordinary
response and actual drain-prefix/custody checks. PERFORMANCE owns the values and
limitations. No prefetch or bridge cache shipped. Row schemas and renderer
rewrites remain deferred. Recovery changes were rebuilt into coherent commits;
the disposable ref can be removed after exact source and documentation accounting.

## Bridge counter optimization and loading investigation — 2026-10-07–08

The user authorizes #1 implementation and #2–5 investigation only, from
`706be4b`. Preserve the response admission contract exactly: canonical UTF-8
byte count, inclusive ceiling, Unicode refusal and first-failure ordering,
bounded work on oversized strings, occurrence counting, detached ownership and
one-time hostile-source enumeration. No wire, GUI, filesystem or domain change.

| ID | Outcome and finite population | Verification and commit boundary |
| --- | --- | --- |
| BC1a | Remove per-character observer overhead from `tools/performance/table_loading.py`; retain actual budget accounting. Update its method controls and PERFORMANCE. | Focused controls, tools department, independent review; separate measurement-method commit. Recollect the unchanged-product Plan/Inventory baseline with this method before counter edits. |
| BC1b | Replace scalar string counting in `interfaces/web/bridge.py` with bounded bulk JSON/UTF-8 encoding; scalar handling of a failing chunk preserves original precedence and budget. Direct consumers are ordinary response capture and drain-prefix capture; tests are transport, commands, shared public views and installed bridge consumers. Update BRIDGE, PERFORMANCE and delivery docs. | Differential old/new mixed-text and boundary tests, actual composition first, ordinary suite/import contracts, same corrected six-child loading matrix and independent adversarial review; one product performance commit. No latency threshold. |
| BC2–5 | Profile remaining capture; attribute row bytes and consumers; distinguish DOM construction/insertion/layout; measure a predefined steady-scroll profile before discussing prefetch. Owners are bridge/window producers and existing installed measurement assets. | Read-only product investigation with bounded disposable instrumentation and retained raw receipts. Report measurements, limitations and proposals; no capture, DTO, DOM, scheduler or prefetch optimization delivery. |

Evidence lives in `build/bridge-counter-study-20261007/`: unique run-prefixed
receipts/logs/manifests, disposable installations and temporary analysis helpers;
retain originals and failures, restore instrumented assets in parent-owned
cleanup, and remove no earlier evidence. PERFORMANCE owns procedure/results;
HANDOFF owns resumption. Existing C5 figures retain their original observer
provenance and cannot serve as the corrected counter baseline. Serialize writers
and timing; keep profiling separate from headline timings. AGENTS mandatory and
recurrence stops apply. No changed safety boundary or further optimization is
authorized; investigation may identify recommendations without delivering them.

BC1a is delivered as `806df04`: 33 focused and 398 tools checks, independent
review, unchanged product. BC1b passes 587 focused composition checks, the
migrated observer control plus transport population (191), 5,982 ordinary
checks, 12 import contracts and six installed transport checks. The observer
control migration permits product string encoding while rejecting whole-response
or extra observer serialization; its first failed ordinary receipt is retained.
Corrected six-child matrices complete with restored assets and unchanged jump
bytes. PERFORMANCE records faster capture, overlapping Inventory coverage ranges
and unchanged Plan burst median; no timing threshold is claimed. Final BC1b
commit/review accounting is retained with the evidence. BC2–5 remains
investigation only under the predeclared PERFORMANCE method.

BC1b is committed as `9d09f70`; final independent review recomputed raw statistics
and verified all 144 matrix asset hashes. BC2–5 investigation is complete on
that unchanged product. Capture/field profiles, six DOM/steady children and two
browser-event-only control children pass their declared checks. PERFORMANCE
owns findings and recommendations; BUGS records moving-intent starvation OPEN.

The shared recurrence review for the two observed viewport cases is:

| Owner | Consequence | Common mechanism and follow-up boundary |
| --- | --- | --- |
| Plan `app.js` / grid viewport | Returned rows repeatedly discarded during continuous movement; recovery at rest. | Exact request revision/offset is conflated with current viewport compatibility. |
| Inventory `app.js` / generic tree | Same exposed viewport; both intent and tree generation reject older demand. | Same viewport-demand mechanism, with an additional tree adoption fence. |

No instance fix was attempted. A coherent follow-up must review both adoption
paths and navigation/stale-owner consumers together, preserving the unchanged
view/action/identity fences and bounded window/concurrency. Row-schema reductions,
cheaper encoding calls, shared layout work and prefetch are proposals only.
User review, not this investigation's closure, authorizes any implementation.

## GUI Inventory refinement — 2026-10-05

The user approved the finalized follow-up proposals and their order from
`614cd19`: contract correction, Refresh selected target, menu corrections,
Verify table alignment, then loading measurements and evidence-led optimization.
This renews GUI-B2 authority and supersedes its earlier deferral below. The
original review is preserved byte-for-byte in
`build/gui-inventory-refinement-20261005/user-handoff.md`; run evidence uses
that directory. Each outcome is independently reviewed and committed before
dependent implementation. No additional approval is needed for these outcomes.

| ID | Accepted outcome | Dependencies and verification |
| --- | --- | --- |
| GUI-C1 | Bound every Plan/Inventory window field by construction; compact Inventory basenames and warning path tails, preserve full-path search, and provide revision-guarded complete snapshot details for rowless nodes through the existing detail command. Preserve structured Plan notice side/code while shortening path/explanation. Migrate serializers, browser validators, consumers and fixtures together. | First. Complete 256-row envelope tests include execution overlays and encoding overhead with a clear margin below the unchanged 8 MiB wall. Real bridge/detail composition, direct consumer tests, ordinary suite/import contracts and affected installed checks. |
| GUI-C2 | Refresh selected targets the tree's current visible active eligible row, including arrow-key changes while Details is hidden. Detail-card actions retain their displayed item. | C1. Existing action route, tree owner and page consumers; regression activates A, arrows to B, then proves exactly one refresh of B. Interfaces and installed Inventory check. |
| GUI-C3 | Suppress native fallback for owned row-context gestures even when the custom menu is stale/empty. Verify actual installed Menu/Shift+F10 event behavior before adding any duplicate-event correction. Document acknowledgement as own missing presence, not descendant rollup. | C2. Shared menu and Plan/tree consumers, direct probes, gallery and installed keyboard/pointer checks. No Restore context action. |
| GUI-C4 | Deliver deferred B2 table appearance: shared 24px row geometry, zebra, disabled unchecked checkboxes, Notes, concise Presence, hierarchical basenames, typography and tones. Only Filename grows passively; Notes participates in deliberate resizing. | C1–C3. Preserve generic tree geometry default and Inventory navigation; direct renderer/tree/bridge probes, interfaces, gallery and installed Inventory checks against official Fluent references. |
| GUI-C5 | Measure Plan and Inventory loading separately: queue wait, server build, serialization/bytes, browser validation, DOM and visible paint without double-counting round-trip intervals. Then coalesce Inventory to one in-flight/latest-intent read and remeasure. | C4. Record finite profiles and measurement authority before execution. Plan already coalesces. Placement/directional prefetch follows only measured need, retaining one 256-row window; fixed-height noninteractive placeholders only if gaps remain. Each justified optimization is its own reviewed commit with navigation/stale-owner tests and repeated measurements. |

Preserve safe filesystem text, task/session/view ownership, authoritative action
scope, fresh-ledger versus published-snapshot evidence, revision conflict behavior,
selection counts and geometry. Never truncate identities or enum values; establish
their finite producer domains. No response-wall or row-limit increase, new command,
filesystem probe/effect, backend selection, hashing or persistence change. Functional
checkboxes and execution-to-Verify navigation remain M1-10; irreversible-count
presentation and fixed Filename under Details remain deferred. AGENTS mandatory
and recurrence stops apply. Expand each pending row's finite source/test/doc
population and acceptance/commit boundary before editing its product.

**C1 delivered boundary.** Bounded Inventory window labels retain full-path
search; exact revision-guarded snapshot paths and warning text are separate
from fresh ledger details. Structured Plan scan notices retain side/code.
Producer, validator, page and fixture migrations passed 370 focused and 5,921
ordinary tests (four Windows privilege skips), all 12 import contracts and
all seven installed obligations. Inventory passed on the 2026-10-06 retry
`c1-native-inventory-03`; the two earlier foreground failures remain evidence.
Conservative complete envelopes are 1,193,678 bytes Inventory and 2,395,485
bytes Plan with execution metadata against the unchanged 8 MiB wall.
Independent review found no actionable issues and verified dependency-bound
reuse of prior passes. C1 is reconstructed from exact reviewed files on
`milestone1`; recovery `a638040` was not merged or cherry-picked. Final commit
identity and accounting belong to `integration.md` in the evidence directory.
Retain its disposable recovery ref until final batch accounting. BRIDGE,
PRESENTATION, INVENTORY and DESKTOP_UI own shipped behavior.

**C2 delivered boundary (from `9868f5c`).** Refresh selected resolves the tree's
active eligible file/folder in its current window; arrows do not read details,
cleared/notice targets disable Refresh, and item-card actions retain their own
item. Optional tree notification plus post-window-adoption eligibility preserve
revision/session/pending ownership and the existing original-command route.
The real-page reproducer failed A versus B before correction. Final gates:
64 focused, 1,951 interfaces, 12 import contracts and both installed Inventory
and shared-tree journeys. The installed witness preserves hidden card A while
trusted arrows activate B and exactly one scoped Refresh targets B; earlier
whole-refresh and visibility assertions remain. Independent review and frozen
input checks found no actionable issues. Evidence `c2-*`; commit identity in
`integration.md`. No bridge, backend, selection or geometry contract changed.

**C3 delivered boundary (from `dfd9291`).** Owned row gestures cancel before
stale/empty or missing-window returns; the custom menu cancels the Menu key's
observed native follow-up context event. No Plan/tree product change or debounce
was needed. Direct probes distinguish own-missing domain folders from present
folders with missing descendants; Restore remains absent. Native Menu/Shift+F10
checks preserve stable popup placement/focus and compare Escape with the live
canonical row, not a replaced element. All original action and foreground guards
remain. Gates: 67 focused, 1,951 interfaces, 12 import contracts and seven installed
checks across `c3-native-01` (six) and unchanged Inventory retry
`c3-native-inventory-02` (one). Retain failed/invalidated characterization and
filter-target-readiness receipts; they are not product regression evidence.
Independent review found no actionable issue and verified frozen dependencies.
DESKTOP_UI and BUGS own behavior; raw evidence and commit accounting use `c3-*`
and `integration.md`. Integrated as `95ff419`.

**C4 delivered boundary (from `95ff419`).** Inventory now reuses shared file-row
cells and integrity labels in a seven-column, 24px zebra table with disabled
unchecked selection visuals, Notes, concise Presence and aligned typography.
Tree identities/disclosure/navigation and the generic 28px default remain.
Only Filename grows passively; Notes supplies deliberate resizing. Full evidence
remains in Details; no wire, action, icon or backend change. Gallery producers,
closed schemas, checkers and native consumers migrated together, retaining C2/C3
witnesses. Adversarial review reproduced an active forced-color regression and
confirmed the scoped all-text-cell HighlightText correction, including filled
Presence. Retain `c4-active-colors-repro-01` and the later stale-reference failure.
Final gates: 114 focused, 12 imports, 1,951 interfaces with the changed gallery
checker reverified by `c4-focused-final-03`, and eight installed obligations via
`c4-native-final-02` non-gallery passes plus `c4-gallery-final-03` (four passes).
Independent review and exact input binding close the atomic commit; commit
accounting is in `integration.md`. DESKTOP_UI, PRESENTATION and FEATURES own
current behavior. Functional checkboxes remain deferred.

**C5 delivered — 2026-10-07.** Loading diagnostics, Inventory viewport
coalescing and the measured Plan keyboard placement correction are separate
reviewed units. The optional collector (`61ee878`) reuses existing installed-host,
fixture and containment helpers, retains exact source/runtime/asset provenance
and restores disposable installed instrumentation. PERFORMANCE owns the frozen
six-child method, phase/byte populations and all three matrices. It distinguishes
visible coverage from obsolete-read settlement, keeps nested spans unsummed and
makes no SLO, tail-latency or compositor-presentation claim.

Inventory coalescing (`4122b10`) retains one running viewport read plus one latest
queued intent at task scope. Each caller keeps its own promise/generation;
superseded queued callbacks resolve null. Covered returns, loaded gestures,
keyboard replacement, navigation/view/session/reload/disposal retire obsolete
work. Direct action-owned initial/view reads retain their independent ordering.
Current dispatch eligibility and stale result/error ownership remain guarded.
The optional tree cancellation callback leaves generic geometry at 28px and
Inventory at 24px; selection, C2 Refresh targeting, C3 menus and the 256-row
window are preserved. Evidence: 88 focused, 2,348 interfaces/tools passes with
three privilege skips, 12 imports, two installed checks and the repeated matrix.

The separate C5c placement correction changes only off-window moving Plan
highlights to use the existing 32-row leading margin, clamped at zero. Pointer
and in-window placement, highlight/selection/revision/navigation/foreground/error
semantics and the 256 limit remain unchanged. Direct task-shell controls cover
both directions, extend gestures and zero clamp. Its gate passes 88 focused,
2,348 interfaces/tools with three privilege skips, 12 imports, both installed
task-shell sizes and the identical six-child matrix. All nine sampled keyboard
gestures use one read with covered target rows rather than two reads with exposed
preceding rows. This is the finite profile's observation, not a universal timing
guarantee. Final source, consumer and raw-evidence review closes C5c; commit
identities and gate receipts are recorded in `integration.md` under the evidence
root. PRESENTATION owns current loading/placement behavior.

The method gate passed 29 focused, 5,953 ordinary/four privilege skips, 12 imports,
both representatives and six baseline children. Earlier fixture consumers were
repaired separately: bounded destination-label expectation (`6c6e10f`) and genuine
RECASE prior evidence (`455fd49`), preserving populations and historical timing
authorities. The latter user-approved recurrence correction passed 68 focused,
5,924 ordinary/four privilege skips, 12 imports and installed compatibility.
Failed receipts, exact recovery bytes and independent reviews remain in the
evidence root; no recovery WIP was merged or cherry-picked.

Conditional disposition: abrupt jumps provide no gradual-scroll lead time for
directional prefetch. After the keyboard correction, remaining exposed-spacer
intervals do not establish beneficial placeholder behavior. Neither is added;
no backend, bridge, filesystem effect, general scheduler or new measurement
matrix was introduced. Original accepted exclusions remain. Both task recovery
contents are accounted for in reviewed integration; `integration.md` records
reference cleanup. This closes the GUI-C1–C5 batch.

## GUI follow-up batch — 2026-10-05

User-ratified six-unit follow-up from `583f14d` on `milestone1`. B1 and B3–B6
are delivered as separate verified, independently reviewed atomic units; B2 was
deferred and is now resumed under GUI-C1/C4 above. Overlapping renderer, gallery and bridge consumers were
migrated together. Evidence and the user's
original uncommitted HANDOFF findings are preserved in
`build/gui-followup-20261005/`. Component docs own shipped behavior; the prior
proposal and recurrence review below explain the renewed GUI-C1/C4 boundary.

| ID | Accepted outcome | Dependencies and verification |
| --- | --- | --- |
| GUI-B1 | Restore bounded plan-window labels, validate presentation enums/relationships, and migrate detail disclosure and all direct consumers. Full paths belong to individual details; Rename keeps its prior basename, Move uses a generic origin note, and previous-location destinations use compact labels. Preserve projection classification, node-id reveal, selection, revisions and the existing response wall. | Complete in `53e1abb`: 5,913 ordinary passes/four privilege skips, 12 import contracts and 12 installed gallery/shell/transport passes (`b1-*-02`). Independent review includes the corrected row-kind validator and final input binding. |
| GUI-B2 | Align Verify table with Plan/gallery row geometry, zebra, disabled checkbox affordances, Notes, concise Presence labels, hierarchical basenames, typography and semantic tones. Preserve inventory evidence, scope, sorting, windowing and recovery. | Earlier deferral is superseded by GUI-C1/C4. Functional checkboxes remain M1-10; disabled visuals are authorized in C4. |
| GUI-B3 | Match Verify Setup height and reorganize status into summary plus one stable detailed line, with shared progress presentation and existing Refresh/recovery actions. Retain published/current scan distinctions without duplicate routine prose. | Complete in `2828b8b`: 41 focused, 1,943 interfaces and seven installed gallery/shell/Inventory checks (`b3-*-01`); independent review and source binding. |
| GUI-B4 | Use local `yyyy-MM-DD HH:mm` display for UI timestamps, including Verify mtime, terminal completion and both detail panes; retain raw machine values where explicitly diagnostic. | Complete in `0f87f6a`: 13 focused, 1,944 interfaces and seven installed gallery/Inventory/execution checks (`b4-*-01`); independent review and input binding. |
| GUI-B5 | Cap details at 20rem, allocate more height to item details, and show full paths joined to the correct known root without filesystem probes. | Complete in `61a5cf5`: six focused, 1,944 interfaces and all nine installed obligations across `b5-native-01` (eight passes) and unchanged-input larger-shell rerun `b5-native-larger-02`. Initial readiness timeout retained; independent review/input binding. |
| GUI-B6 | Row context menus reuse existing menu styling and existing Show details, Select/Deselect where allowed, and folder Expand/Collapse actions. Verify additionally offers Refresh selected and Acknowledge missing for missing rows, through existing node-scoped commands. | Complete in this atomic commit from `61a5cf5`: 5,914 ordinary passes/four privilege skips, 12 import contracts and 86 final focused checks. Seven installed obligations passed across shell `b6-native-01`, Inventory `-03` and gallery `-04`; final independent review/input binding in `b6-review*`. Inventory has no Select/Deselect action. No clipboard or new filesystem actions. |

All units retain safe filesystem-text rendering, server-owned action scope,
bounded windows, truthful publication/recovery, operation semantics and M1-10/A6
deferrals. No hashing, persistence, new execution authority, push or PR. Apply
AGENTS mandatory and recurrence stops. Trace producer/validator/fixture migrations
together and retain failed evidence; test color alone does not classify defects.
Use official Microsoft Fluent references and existing components. HANDOFF is
updated at delivery, preserving the original user-authored finding in evidence.

**Prior B2 inspected boundary (`583f14d`; renewed by C1/C4).** Inventory's generic tree
uses 28px rows, while the file-row specimen uses 24px. B2 migrates the Inventory
controller's geometry with its renderer; preserve the generic tree default and
generation/keyboard rules. Reuse file-row/Integrity markup and tokens while
retaining disclosure listeners/tree semantics. Checkbox visuals are explicitly
disabled and unchecked, with selection functionality deferred by the user.
Add Notes from existing warning/acknowledgement/partial-total facts; keep complete
facts in details. Display basenames only, preserve search/identity, and let Notes
donate manual resize width while only Filename grows passively. Presence uses one
semantic label with mismatch precedence; Reappeared suppresses redundant Present
and Unverified text without claiming fresh verification.

Deferred B2 population: the Inventory adapter/detail route and bridge consumer
if the proposed contract correction is ratified; assets `inventory_review.js`,
`app.css`, `tree.js` geometry, existing file-row/Integrity rendering; direct
projection/adapter/bridge/inventory/tree probes; gallery producer/checker and
installed Inventory helper/parent; DESKTOP_UI/PRESENTATION/BRIDGE and delivery
docs. Revalidate this proposal against the then-current commit before work.
Named gates remain real refresh/release/scope composition, direct consumers,
interfaces and affected installed gallery/Inventory checks. The public-contract
extension needs its direct consumer departments or the ordinary suite. No
backend selection, hashing, fabricated progress or new scan policy is approved.

**B2 recurrence review and user deferral.** Read-only examination found the same
repeated-full-text mechanism in Inventory. The common bridge response wall
correctly refuses these responses; each adapter's serializer owns compact windows
and its exact detail route owns complete text. There is no common path-population
limit enforced before those serializers, and widening the response wall is not a
remedy. The finite inventory field review found full `display` and `warning.path`;
remaining warning text is already bounded to 1,024 UTF-8 bytes.

| Instance | Supported consequence | Owner / disposition |
| --- | --- | --- |
| Plan move/origin/notice labels | 8.56–50.25 MB windows refused by the 8 MiB wall | B1 adapter and exact detail migration delivered in `53e1abb`. |
| Inventory domain display | 19,426,765-byte window; basename diagnostic 175,565 bytes admitted | Inventory adapter; no fix implemented. |
| Inventory warning display/path | 38,691,017-byte window; basename alone still 19,439,817; removing repeated path gives 186,057 admitted | Inventory adapter plus rowless detail routing; no fix implemented. |

The fixture uses 256 typed entries beneath supported 25,120-unit rooted CJK
paths. Raw method/results: `b2-design-inventory-envelope.py` and `.json` under the
batch evidence root. Proposed coherent reorganization: compact adapter display,
remove repeated warning paths, and extend the existing Inventory detail response
with explicitly snapshot-owned path/warning context for selected rowless nodes,
separate from existing fresh ledger evidence. No new command, scan, filesystem
probe or action authority. Following AGENTS recurrence review, the user initially
chose **Defer B2 and review separately**. That review is now complete; GUI-C1/C4
own renewed implementation authority and verification. B3–B6 shipped independently
on the earlier table and contract.

**B6 delivered boundary.** One shared frontend menu retains existing styling,
server-scoped callbacks and exact row/window/task ownership. Opening it performs
no read or selection action. Pointer and keyboard navigation, dismissal, pending/
retired guards and informational-row restrictions are tested together. Inventory
Refresh accepts the exact current-window domain row; acknowledgement requires
that row's own missing presence. Existing toolbar folder actions remain unchanged.
No new bridge command, backend selection, Restore context item or filesystem effect.

The installed Inventory witness distinguishes clicked missing-file scope from
the other selected folder's details and proves one effect per original command.
The finite consumer migration corrected clipped-row pointer scrolling, driver
Details reopening, geometry measurement precision and a gallery combobox capture
that mixed open and later closed states. Production remained unchanged after the
ordinary gate; changed producers/checkers/drivers were rerun. Failed receipts,
exact rejected-report diagnosis and dependency-based evidence reuse are retained
in `b6-native-disposition.md` and `b6-gallery-rejection.md` under the evidence root.
`integration.md` records the resulting commit identity. B2 was excluded from B6;
the renewed scope is owned by GUI-C1/C4 above.

## GUI alignment batch — 2026-10-05

User-ratified seven-point register from `999a568` on `milestone1`. Units
GUI-A1–A5 and A7 are complete; A6 remains deferred. Each delivered
unit includes its direct consumers and fixtures, matching documentation,
verification and fresh independent review in its own atomic commit.
Shared-file writers and native acceptance runs are serialized. An ordinary
suite may read the same frozen inputs independently with isolated temporary
roots and receipts; it cannot overlap source or checker edits. A1–A5 evidence belongs
under `build/gui-alignment-20261005/`; A7 uses `build/rename-move-20261005/`.
HANDOFF owns immediate resumption context.

| ID | Accepted outcome / finite owners and consumers | Dependency, gate and status |
| --- | --- | --- |
| GUI-A1 | Narrow move-reveal recovery: report a still-current rejected/mismatched follow-up window as refreshable; preserve the last coherent summary/window; align conflict viewport with the loaded offset. `assets/app.js`, task-shell and Plan-review probes, their frontend/native consumers, DESKTOP_UI and BUGS. No retries, new bridge fields or lifecycle changes. | `4f314b2`: seven focused, 1,921 interfaces and both installed task-shell cases passed; independent review approved in `a1-review.md`. Evidence `a1-*`. |
| GUI-A2 | Table enlargement gives extra width only to Filename, preserving header/body alignment, horizontal scrolling and deliberate column resizing. First-visible snapshot in `assets/plan_review.js`; direct Plan probe, installed task-shell child/parent and DESKTOP_UI. No CSS/token/helper redesign. Keep Notes-limited resizing: a narrow snapshot at Notes minimum needs deliberate space transfer before positive fixed-column resizing. Apply the same sizing behavior when A5 migrates Inventory. | `498eb24`: focused 36, interfaces 1,921 and six installed task-shell/gallery checks passed; independent review approved in `a2-review.md`. Evidence `a2-*`. |
| GUI-A3 | One shared counted Fluent Filter menu for Plan/Inventory with independent canonical categories, All reset, retained search/selection/default visibility, stable pending focus and existing request guards. Pinned Regular icons; neutral/accent trigger; known work-panel popup bounds; outside interaction, resize, Escape, focus/foreground and retirement dismissal. No Python/bridge/query-policy changes. | `49801f7`; 84 focused, 2,286 interfaces/tools (three skips), pinned icon archive and seven installed gallery/task-shell/Inventory checks passed. Fresh review in `a3-review.md`; frozen and raw evidence `a3-*-final*`. A5 reuses it. |
| GUI-A4 | Full-height optional right details column, toggled by Details; central Setup/status/table regain width when hidden. Separate independently scrollable global and item cards, category/status and supplied item facts. Details capped at 24rem and task rail at 18rem, both shrinking with the window while preserving tab alignment. UI-only renderer/CSS and direct consumer migration. | `4a39789`; 89 focused, 1,921 interfaces and all six installed gallery/task-shell cases pass across retained runs. Fresh review `a4-review.md`; final source `a4-frozen-final-03.json`. A5 adopts this layout. |
| GUI-A5 | Align standalone Verify/Inventory Setup, status and table with Plan/Execution; put whole/selected Refresh on status; reuse semantic row labels and shared sizing/filter/details components. Add a nullable bounded recorded-baseline checksum to window rows, matching bridge validation and fixtures; show shortened checksum with full stored evidence accessible. Standalone Verify stays on Integrity with Sync disabled. Remove only code made obsolete by this migration. `inventory_review.py`, browser inventory/bridge/panel/status owners, direct Python/JS probes, installed Inventory/gallery helpers, DESKTOP_UI/PRESENTATION/BRIDGE/FEATURES. | Closing A5 commit: 23 early service, 84 focused, 12 token and all seven installed checks pass; 5,887 ordinary tests (four privilege skips) cover interfaces and batch integration; all 12 import contracts pass. Fresh review `a5-review.md`; frozen source `a5-frozen-03.json`, native `a5-native-final-03.xml`, ordinary/import `a5-integration-final.*` / `a5-imports-final.*`. Commit identity is retained in `integration.md`. |
| GUI-A6 | Execution-to-Verify navigation. Current inventory reads/actions require an inventory task and captured inventory publication; Refresh requires inventory settlement and no retained plan token. Same-task execution navigation needs new association, retention and lifecycle policy. | Deferred to M1-10 under the user's permitted fallback. No enabling switch or new lifecycle behavior in this batch. |
| GUI-A7 | Projection-owned Rename classification and matching filters; pure same-parent moves/recases have prior-name annotations without origin groups. Genuine move groups begin collapsed; action-shaped purple destination badges contain their paths, while bounded canonical origin annotations preserve filename space. Raw operation kinds and backend behavior stay unchanged. | Closing A7 commit from `37d89ef`: 304 server, 94 frontend and 60 consumer-focused checks; 5,903 ordinary passes/four privilege skips, six installed gallery/shell checks and 12 import contracts. Independent review in `build/rename-move-20261005/rename-review.md`; commit identity in `integration.md`. Claude could not authenticate; the user approved internal-review completion. |

Preserve revision/task/session ownership, coherent bounded 256-row windows,
authoritative selection and its counts/bytes, literal search, existing sort and
collapse behavior except where expressly changed above, safe text rendering,
original-command recovery and current integrity/visibility action scopes.
Checksum means stored baseline evidence, not current bytes or fresh verification.
No hashing, baseline/rebaseline controls, manual post-copy verification, domain
operation changes, new persistence, M1-10 activation, push or PR is authorized.
Use Microsoft's Fluent guidance and existing repository components; no framework
dependency or general UI rewrite. Apply AGENTS mandatory and recurrence stops;
new effects or ownership changes outside these rows require adjudication.

Before each pending row's implementation, settle its exact source/test/helper
population against the integrated predecessor. Tests follow TESTS: broaden to
the ordinary suite/import checks if a shared contract crosses departments or
blast radius is uncertain. Retain failed evidence and reuse passes only when
their product, producer, checker and driver dependencies remain unchanged.

**A4 delivered boundary.** `4a39789` moves Plan diagnostics to a root sibling
spanning Setup/status/table, with default-hidden global/item card scrollers.
It preserves disclosure focus, highlighted-item ownership, bounded virtual
windows, selection and central recovery/Gap guidance. Only supplied item facts
were restored; there are no new DTOs or inferred paths. DESKTOP_UI owns the
shipped behavior. The four-mode gallery and both task-shell sizes cover card
scroll, pane/rail caps, central width, alignment and row reachability; frozen
source, independent review and retained-run identities are in `a4-*` evidence.
Historical horizontal-card recipes are superseded. The bounded table height
chain and folded-status feedback-wrap witnesses remain required for A5 reuse.

**A5 delivered boundary.** Inventory reuses the settled Setup/status/table/details surfaces
and keeps its 28px tree controller, bounded windows, action scope, publication
and original-command recovery. The five columns are Filename, State, Checksum,
Size and Modified. Header sorting preserves server meanings; row states retain
all presence/evidence facts. The nullable stored digest is 32 lowercase hex
characters, displayed as eight with the full value accessible. No hashing or
detail fanout is introduced. The shared `table_columns.js` preserves Filename's
12rem floor and sole passive growth, Plan's Notes donor/14rem floor, and
Inventory's Modified donor/7rem floor.

Direct projection, bridge, renderer, asset-loader, gallery and installed
consumers were migrated together with DESKTOP_UI/PRESENTATION/BRIDGE/FEATURES.
After two inherited-style findings, the user ratified one combined Inventory
adapter correction: remove generic tree gaps/borders and competing horizontal
scrolling, and align the single Refresh group beside the title. Plan styling
and domain effects remain unchanged. The actual Inventory gallery checks all
five column edges, scroll ownership, status placement, semantic labels, checksum,
disclosure, sizing and virtual paging. `a5-frozen-03.json`, `a5-review.md` and
the retained native receipts bind the final candidate and reviewed corrections;
they do not authorize a general CSS redesign or A6 implementation.

**A7 delivered boundary.** The user explicitly extended presentation classification
into the Python server and plan projection. RECASE and pure MOVE with the same
Windows parent display/filter as Rename; cross-parent MOVE remains Move and
MOVE_UPDATE stays distinct even in place. Details and execution retain real
operation kinds. Rename rows have no prior groups; genuine groups preserve
surviving-ancestor/target-parent grouping, initial collapse with retained reopen
state, and revisioned reveal/recovery. Canonical origin annotations are bounded
to preserve filenames. No browser row hiding, domain behavior, persistence,
execution authority, A6 activation or new performance acceptance was introduced.

Projection/server, bridge/renderers, direct tests, gallery and installed shell
consumers were migrated together. The shell now uses actual cross-parent MOVE
fixtures. Current measurement adapters use the actual collapsed fixture's full
first-row facts, including correction of their previously stale target-parent
id/label; legacy drivers and historical measurement JSON remain unchanged.
PRESENTATION/BRIDGE/DESKTOP_UI own the shipped contracts; Git retains the finite
population and implementation register. Final source manifests and raw gates are
`ordinary-02-*` and `native-02-*` under `build/rename-move-20261005/`.

The requested `claude-opus-5-5` / `xhigh` review did not run: OAuth had expired.
The user authorized completion with independent internal review. The narrowed
review package produced zero model usage/cost; original hashes/status matched
afterward and the exact copy was removed. Raw failure and cleanup receipts remain.
No external approval is claimed. A6 remains deferred to M1-10.

## Plan GUI refinements — 2026-10-04

Completed user-authorized three-unit batch from `99e65c8` on `milestone1`.
Each unit includes direct production/test/tool contract migrations, matching
component documentation and independent adversarial review.

| ID | Shipped outcome and preserved guarantees | Commit / verification |
| --- | --- | --- |
| GUI-RF1 | Bounded preflight refusal codes and origin reach Plan review; distinguish commitment/admission failures while preserving effect authority and original-command recovery. | `1865d66`; focused 628, ordinary 5,854/four skips plus corrected fixture module 40, 12 import contracts, all 35 installed cases across retained runs. |
| GUI-RF2 | Informational prior-move groups attach beneath the deepest surviving scanned ancestor, with root fallback and one capped relative purple pill per move target parent. Reveal canonical destinations and clear only obstructing query settings; preserve expansion and selection/count/byte exclusion. Root destinations reveal the first canonical moved item. | `53fb959`; projection/scale 311, frontend 367, ordinary 5,866/four skips plus corrected host/catalog modules 84/96, 12 import contracts, all 35 installed cases across retained runs. |
| GUI-RF3 | Delete/Recase labels; regular Pause/play toggle with accented Resume; neutral regular Stop/Cancel arms for five seconds with accented filled Stop before a second click cancels. Preserve authoritative state, pending/recovery and task/session ownership; ordinary renders retain the deadline and retirement disarms. | Atomic RF3 delivery commit containing this record; ordinary 5,875/four skips, focused consumers, pinned archive, 12 import contracts, all 35 installed cases across retained runs. Independent final review approved. |

Evidence and reviews: `build/gui-refinements-20261004/`. RF3's final inventory
case passed unchanged on resumption; failed foreground-prerequisite receipts
remain alongside the successful receipt. Its recovery candidate was rebuilt on
`milestone1`, without merging or cherry-picking the WIP. Git retains the finite
implementation populations and recovery chronology.

No execution-policy, commitment-authority, persisted-state or unrelated feature
changes. The optional benchmark's seven pre-existing inventory-command catalog
omissions remain deferred in BUGS and `rf2-command-catalog-audit.json`; this batch
claims no new quantitative benchmark result. No later milestone, push or PR is
authorized by this batch.

## Open-bug resolutions — 2026-10-01

Authorized from `1d17883` on `milestone1`; evidence and disposable native probes
live under `build/open-bugs-20261001/`. Each row is one independently reviewed
commit. Shared ledger/changelog/handoff edits are serialized by the coordinator.

| Outcome | Finite population and preserved guarantees | Verification / status |
| --- | --- | --- |
| Optional replacement advice | `tools/__main__.py`, its CLI tests and TOOLS; an absent replacement flag advises a new `--json` path. Existing reports remain untouched and existing replacement-capable callers retain their flag. | Delivered: CLI 77 passed/two skips; tools department 336 passed/three skips; independent review approved. |
| Handle identity on identity-weak filesystems | Core native identity adapter, scanner predicate, executor/verifier consumers, database-pair native lease consumer, their focused tests and owning docs. Only a failed identity query probes the handle filesystem; only a confirmed non-NTFS/ReFS filesystem permits no identity. Database leases still refuse absent identity. NTFS/ReFS and filesystem observation failures remain failures; successful queries add no lookup. | Delivered: eight native COPY/UPDATE/readback/NOOP cases, settlement 30×3, 5,733 ordinary tests/four skips, 12 import contracts and independent correction review pass. The nullable database consumer is migrated; workflow verification's reviewed-volume identity requirement is unchanged. |
| Bounded exception-retention disposition | Host consumers and document callbacks in `interfaces/web/host.py` and `document_channel.py`, their direct readiness/logging consumers and tests, BUGS and INTERFACES. No repository-wide raw-exception elimination criterion. | Bounded closure without product changes: no measured excess lifetime established. INTERFACES names endpoints and the measured production-owner condition for reopening. Four existing lifetime/retry cases pass; independent review approved. |

BUGS, CHANGELOG and HANDOFF carry the corresponding dispositions and final
verification. The response-copy entry is explicitly excluded. New effects,
identity weakening on NTFS/ReFS, or an unbounded retention migration are outside
this authorization; repository mandatory stops remain in force.

## Delivered backend optimizations

### Executor simplification and throughput — 2026-09-29

Closed 2026-09-30 on `milestone1-adelbert`, from equivalence baseline `b1b58476`
through `7f36a2a4`. The full execution register remains in Git at `7f36a2a4`;
this compact record preserves shipped outcomes and decisions. [DEFENSE](DEFENSE.md)
owns proportional defense, [EXECUTOR](EXECUTOR.md) and [VERIFIER](VERIFIER.md)
own current behavior, and [PERFORMANCE](PERFORMANCE.md) owns measurements.

| Delivered outcome | Commit / evidence |
| --- | --- |
| Reuse fresh source/target fidelity before COPY/MOVE_UPDATE publication; remove duplicate admissions and refusal-precedence probes. Retry checks remain. | `a6e2306`, `eb18611`; classified per-row oracle re-pins. |
| Carry one invocation-owned copied-file handle through writing, metadata, flush, publication and observation. Already-granted access may finish where copied/inherited ACLs would deny a reopen. | `0d7dd6b`; native handle/ACL witnesses and restored-fixture receipts. |
| Use planner facts for plan drift; remove duplicate verifier placeholder classification. Publication, backup, recovery, DB concurrency and integrity retain their separate criteria. | `84ce0fb`, `d444a6a`; core/executor/recorder and verifier coverage. |
| Recognize the same file version after own effects and recovery using kind, size, mtime and available identity. Native ARCHIVE/link-count reactions no longer cause false refusals; record actual resulting metadata. | `d43f832`; five native cases, changed-version controls and ordinary coverage. |
| Compose native paths from admitted root prefixes and select one held-root production path without method-identity gates. Concrete NativeFileSystem alone delegates admission to resolve; subclasses keep runtime admission. | `6157226`, `878f15e`, `b9c4ad3`; native guard/fallback/override witnesses. |
| Write targets directly at a blanket 8 MiB across device types, using aligned buffers within the 32 MiB pool, exact tail EOF and retained-handle publication. Keep buffered capability fallback/source reads, create-new-first temp recovery and synchronous eligible small-file copies. | `6b116a58`; native failure/ownership controls, real ledger/verifier integration, classified oracle re-pin. `7f36a2a4` pins the aligned bulk path and documents private-view ownership. |

**Accepted policy.** Planner fidelity and post-effect version recognition answer
different questions. Consolidation may change read-only probe counts/order and
choose another accurate refusal when several apply; effects, final trees,
owned artifacts and recorder evidence must match except the explicitly accepted
own-effect and retained-handle ACL outcomes above. Root holds, fresh held
attributes, descendant guards, per-access fallback, atomic publication, per-file
file/directory flushes before recording, stable wire values and persistence
contracts remain. The completed run's oracle re-pin exception is closed.

**Verification.** Each outcome received independent review and its affected
focused/department/ordinary, import, oracle, guard, differential and five-band
checks. Final direct-write ordinary evidence has 5,720 passes/four capability
skips and one stale cleanup-count assertion; its corrected audit module passes
95 tests, with unaffected passes reused by dependency. The official committed
oracle passes 30 scenarios × 3; the guard scan covers 70 rows/344 effects with
no missing admission; all 12 imports pass. The 67-group fixed differential's
four changed groups contain only seven obsolete cleanup-count diagnostics;
all effect/tree/settlement facts match. Follow-up coverage passes 640 executor
tests. Failed receipts remain; no aggregate all-green invocation is invented.

Evidence root: `build/executor-simplification-20260929/`, especially
`differential/result8-*` and measurement prefix
`measurements/result8-b9c4ad3e-20260930-201114-989e90d9`. All 25 final production
copies/readbacks pass with stable inputs, expected write modes and owned cleanup.
Latest diagnostic medians: 1,000 × 4 KiB **2.789 s / 1.40 MiB/s**; 1 × 4 GiB
**0.909 s / 4,505 MiB/s**. The small-file 1.6 MiB/s goal remains unmet and is not
a gate. Comparisons are sequential repeated-source observations, not cold-cache
or universal-device claims. The 336-copy/16-tail threshold study remains
historical evidence; the user's blanket 8 MiB decision supersedes its per-device
candidates. No volume/model classifier ships.

**Closeout and exclusions.** No in-scope optimization or bug remains open.
Directory-flush batching and unbuffered source reads belong to
[M2_PROPOSAL](M2_PROPOSAL.md); the latter requires evidence of integrated benefit.
The exFAT FileIdInfo defect, pre-invocation replacement findings below, internal
re-certification/interface audits and future M1 product rows were not part of
this run. Earlier recovery changes were rebuilt into reviewed commits rather
than merged as WIP; Git and retained evidence preserve that accounting.

### Root admission optimization — 2026-09-28

Delivered 2026-09-28–29, `6536c04` through `8159905`. Executor, preflight and
verifier now admit and hold confirmed local roots per invocation; remote,
unholdable or uncorroborated roots keep per-access admission. Native observation
and path-probe consolidation accompanied the holds; later simplification above
supersedes intermediate conversion caches. [CORE](CORE.md),
[EXECUTOR](EXECUTOR.md), [PREFLIGHT](PREFLIGHT.md), [VERIFIER](VERIFIER.md) and
[DEFENSE](DEFENSE.md) own the retained contract.

| Delivered outcome | Commit / evidence |
| --- | --- |
| Shared full admission and exact held final-path confirmation; directory access without delete sharing, with fresh attributes before reuse and release on pause/exit. | `6536c04`, `8cdd669`; native NTFS/exFAT root/ancestor rename and in-place junction witnesses. |
| Invocation ownership in executor, preflight and verifier; geometry from opened verifier handles. | `90b57646`, `4263b12`, `0b85d88`, `e189b48`; consumer gates and fallback cases. |
| Reuse native leaf observations, simplify descendant checks and delegate adjacent concrete-native admission. Unreadable descendants refuse instead of appearing absent. | `7e60a47` through `23589bd`; `db03926` defect fix and `eaf62d7` fast-path controls. |

Each outcome passed its independent review and named gates. The post-round
five-band corpus reduced 1,000 × 4 KiB from 28.2 s to 3.63 s (1.08 MiB/s);
PERFORMANCE owns the diagnostic limits and later results. Evidence remains in
`build/root-admission-optimization-20260928/`; the immutable 67-group differential
producer is `e7ba9b8d`. The prior nine-row register is in Git at `c05eea25`.

Still binding: rename/move/Safely Remove may report “in use” during a hold; failed
confirmation cannot authorize reuse. Holds do not fix pre-invocation same-volume
root replacement or metadata-matching identity-less DELETE/TRASH replacement.
Those findings remain logged in the retained differential evidence and prior
register; the exFAT FileIdInfo defect remains open in [BUGS](BUGS.md), outside
this completed work. Recovery tips were accounted and
pruned with a verified bundle (`resume/wip_cleanup_20260929*`). The detached
`b8baf42d` baseline worktree was removed at closeout after confirming integrated
ancestry, no tracked/untracked changes and only 59 regenerable Python caches;
inventory and removal receipts live in
`build/executor-simplification-20260929/closeout/worktree-*.json`.

### Incident repairs and closeout — 2026-09-27

| ID | Delivered outcome | Commit / evidence |
| --- | --- | --- |
| CLI-DRIFT | Cold-file drift distinguished from stable incompatibility and unavailable artifacts; bounded validation-only retries and non-destructive guidance. [DATABASE](DATABASE.md). | `5e4bf87`; `build/cold-admission-followup-20260927/` |
| DOC-PRECISION | TESTS notice rationale and DATABASE snapshot scope corrected. | `6de6d1c` |
| IR-DB | Strict cold file admission separated from runtime-owned SQLite validation. [DATABASE](DATABASE.md), [DEFENSE](DEFENSE.md). | `639b2ea`; `build/admission-bridge-closeout-20260927/` |
| IR-BRIDGE | Bridge diagnostic migrated to current scalar/terminal shapes with first-failure and raw-stream retention. [BRIDGE](BRIDGE.md), [PERFORMANCE](PERFORMANCE.md). | `0e4595e`; same evidence root |
| IR-CLOSE | AB-7 focus loss moved from BUGS to TESTS troubleshooting; DWM sentinel obligation retired. | `e8d3613` |
| IR-DEFER | AB-8 stack/wrap shelved with its inspection points in TESTS. | `8f75f75` |

Admission retries never retry task submission or effects, and inconclusive
observations never gain reset advice by exhausting retries. AB-8
implementation, environment monitoring, GUI changes, automatic replay and broad
schema migration stayed excluded. The unsupported CLI replacement-flag guidance
defect is in BUGS. Implementation detail and failed receipts remain in Git and
the evidence roots.

## Post-M1-8 reduction plan

AB-1–AB-10 are delivered. The batch reduced duplicate presentation and bridge
work while retaining reviewed effects, truthful results, installed desktop
journeys and the current subject contracts. It made Plan/execution UI latency
and empirical representation-memory measurements optional developer tooling;
enforced bounds, counted-work regressions, release resource checks, transport
custody, and executor settlement retain their separate authority. No speed or
memory improvement is claimed. The table is the completed register; Git,
CHANGELOG and the named ignored evidence hold its chronology and failed receipts.

| Closed outcome | Result and current owner | Commit and evidence |
| --- | --- | --- |
| AB-1 | AGENTS small-change default, concise delivery records and PERFORMANCE methods/results ownership; subject contracts and DEFENSE evidence authority stay separate. | `29d9b8f`; `build/post-m1-8-ablation-20260925/ab1-checks.json` and review. |
| AB-2 | Optional selected performance drivers moved to `tools/performance/` with independent fixture/action checks and truthful incomplete reports; required correctness/release gates retained. [PERFORMANCE](PERFORMANCE.md), [TESTS](TESTS.md), [TOOLS](TOOLS.md), [DEFENSE](DEFENSE.md). | `8ba38ced`; `build/post-m1-8-ablation-20260925/ab2-migration.md`. Historical JSON/contract/authority bytes remain unchanged. |
| AB-3 | Unused historical mapping reader removed; current scan correspondence, unique-pair/hardlink refusal and ledger behavior retained. [DATABASE](DATABASE.md), [PLANNER](PLANNER.md). | Reviewed `c5f1de8`, integrated as `dd23c270`; `build/post-m1-8-ablation-20260925/ab3-integration.md`. |
| AB-4 | Desktop Plan open captures one revision-bound summary and workflow-owned membership without building a full public preview; folder derivation is lazy. Public CLI/API preview and selection authority remain. [INTERFACES](INTERFACES.md), [PRESENTATION](PRESENTATION.md). | `9cfd2a0`; AB-4 verification in `build/post-m1-8-ablation-20260925/`. |
| AB-5 | Bridge response adoption combines repeated traversal over one detached value; complete request, byte, type, identity, prefix and custody checks remain. [BRIDGE](BRIDGE.md). | `1cb75fb`; AB-5 verification in the same evidence root. |
| AB-6 | Genuine document replacement retires page authority and presents a contained restart path while admitted work and worker custody continue. Canceled navigation and same-document history retain their distinct behavior. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Harness prerequisite `f55a7dd`, product `2b4a2214`; AB-6 gesture and verification receipts in the same evidence root. |
| AB-7, AB-7R, AB-7S and corrections | Existing asynchronous admission/completion retains original results for effect/lifecycle commands without elapsed-time mutation abandonment or replay. Bounded observation, late adoption, explicit unavailable/invalid-result feedback, duplicate protection, exact intent fences and pending Close survive. Five revisioned/current-state commands use refresh or fresh choice. One browser attempt/settlement owner replaces duplicate recovery paths. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md). | `6287db0c`, `d4351acd`, `514d71d1`, corrections through `4f1537c2`; `build/post-m1-8-ablation-20260925/ab7-verification.md`, `ab7r-verification.md`, `ab7s-verification.md` and later review receipts. The earlier unexplained Setup/Plan-again observations are not claimed fixed. |
| AB-8 and follow-up | One Python task/session snapshot owns semantic progress and terminal presentation; the page atomically adopts bounded facts. Gap uncertainty, exact scalar identity, item windows/detail, transport replay, local interaction, D4, command recovery and Close remain. A task-list summary can briefly precede snapshot delivery without becoming a second terminal authority; record adoption reconciles them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [INTERFACES](INTERFACES.md). | `7445f70a`, `4ff11a8`; `build/ab8-resume-20260926/` and `build/ab8-followup-20260926/`. Full event-body removal remains a separate protocol decision. The earlier stack/wrap rerun's cause was not established. |
| AB-9 | Duplicate CSS/source/gallery spelling pins retired with behavioral, computed-style, native, accessibility and security witnesses retained; no production asset changed. [TESTS](TESTS.md), [DESKTOP_UI](DESKTOP_UI.md). | `7af07724`; `build/ab9-20260926/verification.md` and `detector-map.md`. |
| AB-10 | Integrated workflow, boundary and evidence sweep; one stale optional execution-UI feedback driver/checker corrected while frozen historical JSON and product semantics stayed unchanged. Required retained gates and final endpoint/installed journeys were accounted by dependency. | `cb57c41a` (first AB-10 commit); `build/ab10-20260926/verification.md`, `reuse-and-raw-evidence.json`, review and link receipts. The bridge-event diagnostic remains incomplete with an unassigned event-v5 fixture migration; it claims no product cause, release gate or performance result. |

Post-closeout consolidation archived the study and pruned the accounted AB-3,
AB-6 gesture, GUI-J and GUI-M2 recovery refs plus the AB-3 worktree. Exact tips
and complete history remain in `build/ab10-20260926/side-recoveries.bundle`;
`preservation.json` and `cleanup.json` record verification and 78 copied evidence
files. All five stashes and the pending DOC-2 branch remain; no remote changed.

The retained user decisions are: unsupported reload with stale-document
containment (D1); no timed mutation-result abandonment or automatic replay, but
recovery of the original result after delivery failure (D2); optional useful
performance measurements without new hard speed targets (D3/E1/D7); unchanged
highlight/focus and range/navigation behavior separate from execution checkboxes
(D4); native Advanced Color mitigation (D5); and the user-owned small-change
classification in [AGENTS](../AGENTS.md) (D7). D6's missing-row
acknowledge/restore desktop capability was delivered in M1-9 below.
M1-10's rebaseline confirmation
accepts replacement of content evidence and is a different action. Existing
[FEATURES](FEATURES.md), [INVENTORY](INVENTORY.md),
[PRESENTATION](PRESENTATION.md) and [DESKTOP_UI](DESKTOP_UI.md) own the D6 behavior;
this completed batch neither deletes it nor marks it delivered.

| Rejected or deferred study lead | Current disposition |
| --- | --- |
| L5 producer/retained admission merger | Rejected: independent counter-free populations and cumulative retained charges differ. [DEFENSE](DEFENSE.md) owns bounds. |
| L7 copy diagnostic removal | Rejected: tools consume default-off copy metrics. [TOOLS](TOOLS.md), [EXECUTOR](EXECUTOR.md). |
| L8 continuation/settlement class merger | Rejected: distinct recovery facts and legal states; no safety-equivalent simplification. [EXECUTOR](EXECUTOR.md). |
| L9 CSS replacement for native Advanced Color | Rejected: CSS misses SDR WCG; retain native mitigation. [DESKTOP_UI](DESKTOP_UI.md). |
| L6 Plan-volume/verdict check consolidation; S5 full application-owner merger | Unqualified/deferred. Construction, shape and semantic checks protect different boundaries; lifecycle, service, observer, dispatcher and adapter cleanup have distinct owners. No generic validator, lock or settlement framework is authorized. [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md), [INTERFACES](INTERFACES.md). |
| Full event-body removal; Plan-again tracer retirement; broad projection topology and shared selection-admission/safety cache ideas | Separate deferred decisions, without implementation authority from AB-8 snapshot trimming or the older R7 study. Retain diagnostic/replay consumers, tracer and copy metrics until an activated boundary accounts for them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [TESTS](TESTS.md). |
| Older recording-tail, pause/cancel and mutation-verdict compression ideas | Unscheduled alternatives from the completed narrow-reduction study, not latent checkpoints. Exact mutation/publication/recording order and settlement oracle remain [EXECUTOR](EXECUTOR.md) obligations. |
| Older R7-5–R7-8/R7-G and the blanket AB-7 domain-resend proposal | Old execution denominator retired, not passed. AB-2/4/7 absorb selected outcomes; AB-7R validation rejected blanket receipt equivalence and resend. No old checkpoint or frozen test recipe resumes. Historical detail is in the archived study §13–14. |

Five earlier studies remain historical under `obsolete/`: completed TA/ST/PR/NR
work is accounted in the [archived study §13](obsolete/POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting).
Their still-supported boundary, selection, lifetime, native, history, database,
workflow and executor guarantees are owned by CORE/TESTS/DESKTOP_UI/INTERFACES,
DATABASE/HISTORY, ARCHITECTURE/WORKFLOWS and EXECUTOR respectively; archived
method prescriptions cannot silently reopen them. The old M1-7 R7-1–R7-4
were delivered, RI-1–RI-4 investigated, and later R7 rows suspended/superseded.
The unproven foreign-task Execute-result concern did not establish a supported
misroute; current [BRIDGE](BRIDGE.md) identity adoption remains binding.
In particular, history write admission precedes pending mutation, persisted
readback checks normalization/hash/columns/receipts, old or mixed database pairs
refuse without automatic migration, and executor publication/settlement ordering
remains guarded. CORE/TESTS retain the FailureDetail lifetime guard;
VERIFIER/ARCHITECTURE retain duplicate/unknown integrity-selection refusal and
detached facts; DESKTOP_UI/INTERFACES/BRIDGE retain real native input,
accessibility, privacy and media checks. Representation-specific frozen lists,
query-count pins and superseded private-index prescriptions are historical.

## Completed preparation and MOVE-1

PA-1–PA-3 reconciled five earlier studies and moved them to `obsolete/` in
`0c74ee7`; the current decisions above and the archived study preserve their
dispositions. MOVE-1 (`549f3b4`) restored repeated source moves through current
unique correspondence while current hardlinks, duplicate identities, ambiguous
pairs and incomplete scans remain ineligible. [DATABASE](DATABASE.md),
[PLANNER](PLANNER.md) and [BUGS](BUGS.md) own its behavior; the native/ordinary
receipts remain in `build/move-history-20260925/`. No schema, recorder or
retained-history rewrite was part of MOVE-1.

## M1-8 execution review closure

M1-8 delivered shared Plan/live/terminal status, bounded rows and Details,
current-ledger distinctions, follow/Go, truthful progress/capacity, action
feedback and same-task Retry observation including pending Close. Retry never
restarts execution. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md) and [EXECUTOR](EXECUTOR.md) own the behavior.
P2/R0–R2/post-R2/RC-1 passed A1–A5 and B1–B6: 5,405 ordinary passes/five
skips, 33 installed GUI obligations and 12 imports. Reviewed commits
`4bbf943`, `8f7555b`, `0fc2f5d`, `9e5b080`, `b1f5a07`, `c974447`,
`96a0212`, `9be2930`, `3ea4e6b`; raw and failed receipts are in
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/`.
[PERFORMANCE](PERFORMANCE.md#source-linked-historical-observations) owns the
fixed U-v2 78-attempt observations.

The A6 integration receipt at `build/m1-8-archive-20260924/integration.json`
records non-squash merge `6c00ec731dd176d201e2a2c3a2a53b47652c544e`,
tree `f7691c518a31a160f888db299faa9342bd9a4349`, candidate
`cd2d44a802c665a4f76331b0a15856ef8102f1ac` and
`postmerge_validation: PASS`. It, not later test color, closes A6. The archived
register owns its finite gate; prior failed R2 attempts remain failed. A page
capture alone does not prove native compositor health. Historical recovery
commits were not merge units.

## Remaining checkpoints

### Completed M1-9 — 2026-10-01 – 2026-10-02

Delivered on `milestone1` from `937af54`. The user allocated missing-row
acknowledge/restore here and directed the shared start-admission correction and
narrow native witness on resumption. Stop here for recap and GUI tweaks;
M1-10, M1-12, release and DOC-2 are not activated.

| Delivered outcome | Reviewed commit | Acceptance evidence |
| --- | --- | --- |
| Immutable inventory facts and shared sibling ordering | `ec3865c` | Hierarchy, domain/warning separation, raw evidence, checked/partial totals, both sort directions/reset and 120,000/240,000-row fixtures; 160 focused and 894 workflow checks. |
| Reproducible cold projection acceptance | `12cae9b` | Independent collector/checker; five fresh samples each, maxima 1.9712401 s base and 2.8123806 s heavy below 3/6 s; source dependencies revalidated at closeout. |
| Bounded task inventory reads and fresh exact-row details | `a84e816` | Real scan/release/read composition, revision/window/detail/Close races, 529 focused and 3,109 combined department checks. |
| Desktop inventory read pane and controls | `687549a` | Search/facets/collapse/paging/sibling sort/reset, evidence provenance and stale responses; production frontend and installed shared-tree checks. |
| Same-task whole/item/folder Refresh | `9266845` | Fresh location admission, old-complete publication, exact original success/failure recovery and bounded task-owned receipts; 2,769 workflow/interface checks. |
| Conditional missing-row acknowledge/restore | `978ddf1` | Complete hidden/off-window scope, reappeared/stale cases, retained actual partial counts, dirty-view fence and exact Close; 795 focused and 2,785 workflow/interface checks. |
| Shared admitted-start identity adoption | `910255f` | Initial Plan/Inventory, Plan again and serial pair batches; failed/stale-list red/green probes, replacement drain and preserved execution semantics; 1,890 interfaces checks. |
| Installed host command catalogs and native completion waits | `02d7595` | Six exact catalogs include seven inventory commands; three local waits fit observed native completion without changing the sixty-second parent bound or semantic assertions; actual host gates, replacement/Close and 1,890 interfaces checks. |
| Desktop Refresh and missing visibility actions | `5cf18f8` | Original-command recovery, immediate Refresh identity, truthful partial feedback, dirty/current publication rules; production probes and real folder-command clicks, replaced results, row hide/return, screenshot and task/host Close. |

Inventory remains a complete or prior-complete ledger publication, not a claim
that its preceding scan was complete. Warnings stay outside domain action scope.
The server owns full folder membership; view filters/windows do not narrow
effects. Refresh re-admits location authority and can recover retained scope;
visibility additionally needs a current complete publication. Conditional writes
retain frozen original facts and actual bounded dispositions, including uncertain
suffixes after failure. Receipts share the existing 48-entry admission capacity
and live until task Close. No batch-atomicity or automatic-replay promise is added.
[INVENTORY](INVENTORY.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md) and [BRIDGE](BRIDGE.md) own shipped behavior.

Final ordinary gate: 5,829 passed, four skipped, 35 headed excluded. The subsequent
test-only maintenance passes all 1,890 interfaces checks. All 35 headed cases
are covered across dependency-scoped runs: 30 unchanged existing passes, refreshed
replacement/Close (one), transport (one), live host gates (two), and the new
inventory journey (one). This is not a single aggregate headed invocation.
Twelve import contracts, local document-target checks and diff checks pass.
The 64 focused frontend/trace checks and retained negative controls cover the
shared and Refresh lifecycle corrections. Screenshot capture preserves browser
surface evidence; it does not claim native-material or GUI-polish acceptance.

Raw successes, failures, diagnostic-only runs and independent reviews remain in
`build/m1-9-20261001/`. Final receipts include
`complete-ordinary-20261002.log`, `native-wait-ordinary.log`,
`complete-headed-20261002.log`, `headed-recheck-20261002.log`,
`native-wait-headed.log`, `native-replacement-20261002.log`,
`inventory-headed-focus-ready.log` and `cold-evidence-final-20261002.log`.
The nine outcome reviews and final documentary review are retained there.
Thirty-four inventory receipt/identity copies are hash-verified under
`inventory-native-preserved/`; external fixture roots are retained for provenance.
Recovery `4b936db` was reconstructed into reviewed commits, never merged or
cherry-picked as-is; its disposable ref was removed after independently reviewed
accounting of all twenty saved paths. The original patch remains preserved.

New hashing and integrity controls, overlays, manual post-copy verification,
schema/history work, broad lifecycle redesign, new performance targets and
release acceptance remain excluded. Earlier stop/recovery chronology is retained
in Git and evidence rather than a second active register.

Pending rows record accepted future outcomes. Backend optimization is closed;
pending rows still need user authorization, active scope and finite verification.
A finding does not enlarge a row; [AGENTS](../AGENTS.md) governs scope changes,
stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| M1-9 | Bounded inventory projections, current evidence and the full inventory consumer for sibling sorting, including missing-row acknowledge/restore. | Complete or prior-complete publication; warnings outside action scope; raw evidence provenance; search/filter/collapse/window/detail, replacement/race and production sort/reset paths; headed witnesses. | Complete; reviewed commits and final evidence above. |
| M1-10 | Baseline, verify and rebaseline controls plus first same-task manual post-copy verification, without persistent operation-time hashes. Eligible null-evidence files enter rebaseline; every admitted rebaseline hashes and replaces/creates evidence, and a match is not verified. | Confirm acknowledgement admission before claim/native work; all-null/mixed workflow, service/CLI and desktop paths; conditional recording and supersession races; atomic handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; overlay/result identity. Independently review operation matrix and conditional recording. Terminal Verify-remaining/subset retry remains deferred. | Pending. Rebaseline confirmation is distinct from missing-row acknowledgement. |
| M1-12 | Close integrated lifecycle/retention across activated task surfaces, then complete adversarial, documentation, ordinary and headed verification. This absorbs former M1-11. | Plan-only, execution-only, linked/manual verification, inventory, refused/canceled/degraded/failed tasks across same-document navigation, contained unsupported reload, explicit close and shutdown; admission bounds, stale-response suppression, exact resource release and retained truth. Applicable settlement oracle, ordinary/headed, installed-wheel/product, imports, diff/active-link checks and independent cross-component review. No aggregate-artifact or whole-owner-graph criterion. | Pending. |
| M1-Release | Beta packaging and release closure after delivery rows above. | Installed artifact from clean checkout; frozen specification/dependency/CI, notices and corresponding source; standard-integrity host proof and every applicable BR-G/SH-G gate. [INTERFACES](INTERFACES.md) owns host/package/SH-G; [BRIDGE](BRIDGE.md) owns BR-G. | Pending. |

DOC-2 remains **pending, outside the AB batch**. Its historical branch proposal
removes exactly four superseded compact-plan commits from `milestone1`, preserves
the old tip and opens a draft PR from `milestone1-anthony`. Before any action,
freshly check divergence, remote tip and preservation of all work; unexpected
commits or unaccounted work require adjudication. AB-10 and the documentation
consolidation do not execute, close or authorize DOC-2 history rewriting.

## Delivered product checkpoints

| Closed row | Result and current owner | History/evidence |
| --- | --- | --- |
| M1-4, M1-async | Process-live task creation/navigation/close and bounded asynchronous admission/completion with original effect owners. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `ab453e1`, `675181a`; `build/m1-async/`. No durable task survival claimed. |
| M1-5, M1-6 | Typed location admission, bounded recents, frozen Setup, serial pair and standalone inventory starts, fresh Plan again. [INTERFACES](INTERFACES.md), [WORKFLOWS](WORKFLOWS.md), [BRIDGE](BRIDGE.md). | `e19ed9d`, `76ba7d0`; `build/m1-5/evidence/`, `build/m1-6/`. Hints grant no authorization; no global default mutation or partial-pair start. |
| M1-7 | Bounded Plan review, sibling sorting, committed selection and same-task execution. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Through `5986c57`; `build/m1-7/evidence/p9-full-20260916/`; R7-1–R7-4 later through `95f31e1`, with R7-G retired rather than passed. |
| M1-8-capacity, E, P1, P2, R0–R3 | Stop later operations after recognized capacity failure and current settlement; bounded current-ledger/retained execution review and installed recovery. [EXECUTOR](EXECUTOR.md), [DATABASE](DATABASE.md), [PRESENTATION](PRESENTATION.md), [DESKTOP_UI](DESKTOP_UI.md). | `04947ba`, `7905a1b`, `055325b`, `4bbf943`, exact A6 receipt above and [archived register](obsolete/M1_8_DELIVERY.md). Recorder-only failure remains independent degradation; P2 timing was superseded for final UI by U-v2. |
| GUI-1/S/R/I/D, Plan GUI-P/S/F/H/J/K/L/M/N/O/P, AI-1/2, DOC-1/3 | Task shell, Setup/Settings, bounded batch receipts, Fluent controls/icons, rootless Plan table, server selection/highlighting, search/sort/status and installed polish. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md), [TOOLS](TOOLS.md), [BRIDGE](BRIDGE.md); AGENTS and subject docs own the reconciled rules. | Matching CHANGELOG tasks and commits `27f1a6b` through `2cc0083`. GUI-M2 WIP `af02913` and stash `93414b7` were historical preservation; useful folder-total work was rebuilt in `7cf4448`. |
| GUI-W1/WR1 | Native Advanced Color v3 mitigation for specified dark flyout shadows on WCG/HDR displays. [DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md), [BUGS](BUGS.md). | `c637025`, `build/wcg-review-20260924/`. No Windows compositor fix or WCG-only selector proof claimed; Mica remains required. |

The existing 48-pair bound, serial best effort, per-row options, exact uncertain
retry, keyboard/forced-color and admission guarantees remain active. Clearing
a batch receipt does not close a task. The reported Optics refresh delay remains
unprofiled. No completed row authorizes M1-10 integrity controls, M1-12
lifecycle closure or release.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps normal review with visible issues. Canceled/abnormal sessions
retain terminal truth without resume, domain retry or session cleanup. Live
pause/resume remains separate. Busy Close requests best-effort cancellation and
keeps the card until settlement/resource release; it never implies trash purge.
Forced process exit has no durable task/resume guarantee.

Capacity refusal before execution, including queued wakeup, retains the task
without execution, automatic retry or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again and requires fresh review. It
never carries old selection/authorization or changes the old artifact. Removing
source/target entries affects capacity only through that fresh scan.

Recognized operation, cleanup and destructive-prerequisite capacity failure
stops later admission after current settlement. Recorder-only write failure
remains recording degradation with continuation. Generic I/O retains its typed
reason. Yellow capacity presentation cannot hide independent known failures.
Trash-location text is accepted for M1; exact count needs complete outcome
evidence. Location-only Details never promises a count, existence or purge.

Location admission is workflow-owned for typed, picker and recent Setup/inventory
inputs. A remembered location is not authorization; consumers re-probe at use.
Setup freezes semantic plan options in a backend-derived snapshot without
writing global defaults or granting browser text/filter normalization authority.

Plan review preserves operation, selection, scope and fresh-preflight truth
across view gestures. Canonical path-key order and complete-sibling filename,
raw size and raw mtime sorting in both directions with reset are accepted M1
behavior. Sort is process-live view state and cannot change selection,
commitment, dependency/execution order, risk/counts or action scope; hierarchy
and node identity survive. [BRIDGE](BRIDGE.md) and [PRESENTATION](PRESENTATION.md)
own exact validation and scale criteria.

Execution, inventory and post-copy overlays remain distinct from each other
and ledger-derived state; zero-byte work that ran never looks unrun. Inventory
warnings stay outside path/action scope; publication is complete or keeps the
prior complete generation. Baseline, verify and rebaseline remain distinct.
Rebaseline requires acknowledgement, includes eligible selected null-evidence
files, creates/replaces evidence after fresh hash and clears verification
freshness without becoming compare-and-accept. Manual exact post-copy
verification uses atomic handoff classification on a ready subset, preserves
execution truth and reports ineligible outcomes honestly.

Release remains accepted. [INTERFACES](INTERFACES.md#sh-g-release-criteria)
owns open SH-G-15 cold-start/repeated/long-workload resource policy, still without
a numeric budget or acceptance artifact. Enforced request/population limits and
separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status describe shipped behavior;
every active DESKTOP_UI acceptance item maps to its subject check or an
explicitly approved deferral. Omission or copied, unmapped checklists do not
close release. BR-G-44: from a clean checkout, run the complete suite including
ordinary-default exclusions, lint-imports and diff checks; collect/pass every
`test_br_g` case without skip/xfail on Windows. Narrow selections do not
substitute for release evidence. [TESTS](TESTS.md) owns commands and routing.
These obligations remain open, with no product release claimed by AB-10.
