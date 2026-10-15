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

Completed registers below are condensed from `fc8a79b`; Git retains their
full finite populations and chronology, while named local evidence roots
retain raw and failed receipts. Current subject
contracts and retained exclusions remain binding; historical measurements
do not establish acceptance for changed dependencies.

## Remaining checkpoints

M1-10 is complete as of 2026-10-14, including the requested integrated A–C
review before D and final cross-component review. The user has activated the
GUI-hardening follow-up below. M1-12, release and DOC-2 remain inactive. Backend
optimization is closed.
Other pending rows still need user authorization, active scope and verification.
A finding does not enlarge a row; [AGENTS](../AGENTS.md) governs scope changes,
stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| M1-9 | Bounded inventory projections, current evidence and the full inventory consumer for sibling sorting, including missing-row acknowledge/restore. | Complete or prior-complete publication; warnings outside action scope; raw evidence provenance; search/filter/collapse/window/detail, replacement/race and production sort/reset paths; headed witnesses. | Complete; reviewed commits and evidence in the completed M1-9 section below. |
| M1-10 | Baseline, verify and rebaseline controls plus first same-task manual post-copy verification, without persistent operation-time hashes. Eligible null-evidence files enter rebaseline; every admitted rebaseline hashes and replaces/creates evidence, and a match is not verified. | Confirm acknowledgement admission before claim/native work; all-null/mixed workflow, service/CLI and desktop paths; conditional recording and supersession races; atomic handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; overlay/result identity. Independently review operation matrix and conditional recording. Terminal Verify-remaining/subset retry remains deferred. | Complete; A–E reviewed and integrated through D2 `d88f863` plus documentation closure. Stopped for recap and GUI tweaks. Rebaseline confirmation remains distinct from missing-row acknowledgement. |
| M1-12 | Close integrated lifecycle/retention across activated task surfaces, then complete adversarial, documentation, ordinary and headed verification. This absorbs former M1-11. | Plan-only, execution-only, linked/manual verification, inventory, refused/canceled/degraded/failed tasks across same-document navigation, contained unsupported reload, explicit close and shutdown; admission bounds, stale-response suppression, exact resource release and retained truth. Applicable settlement oracle, ordinary/headed, installed-wheel/product, imports, diff/active-link checks and independent cross-component review. No aggregate-artifact or whole-owner-graph criterion. | Pending. |
| M1-Release | Beta packaging and release closure after delivery rows above. | Installed artifact from clean checkout; frozen specification/dependency/CI, notices and corresponding source; standard-integrity host proof and every applicable BR-G/SH-G gate. [INTERFACES](INTERFACES.md) owns host/package/SH-G; [BRIDGE](BRIDGE.md) owns BR-G. | Pending. |

DOC-2 remains **pending, outside the AB batch**. Its historical branch proposal
removes exactly four superseded compact-plan commits from `milestone1`, preserves
the old tip and opens a draft PR from `milestone1-anthony`. Before any action,
freshly check divergence, remote tip and preservation of all work; unexpected
commits or unaccounted work require adjudication. AB-10 and the documentation
consolidation do not execute, close or authorize DOC-2 history rewriting.

### Verify table hardening — 2026-10-15–16

Approved after the M1-10 GUI recap, starting at `d6770c7`. This is a separate
hardening batch, not activation of M1-12. Root owns delivery documents; evidence
and the final ablation report live under `build/verify-ux-20261015/`.

| Outcome / atomic boundary | Owners and finite consumers | Verification |
| --- | --- | --- |
| Kind catalog coverage | `tests/interfaces/web/test_browser_event_v5_consumers.py`; use the Python task-port catalog to generate browser mirror cases. | Owning module and interfaces department; preserve invalid/coercive cases. |
| Verify table alignment | Inventory/Plan web presentation state, shared highlight/visible-sequence helpers, task presentation/port/lifecycle bridge adapters, `app.js`, `bridge.js`, Inventory/Plan/tree/row assets as directly needed; their existing Python, browser probes, installed Inventory/execution/shell/gallery consumers. PRESENTATION, DESKTOP_UI, BRIDGE and FEATURES own changed contracts. | Shared server range gestures, Ctrl/Shift and keyboard behavior, highlighted checkbox scope, query-matched folder/header membership including off-window/collapsed matches, authoritative stale/conflict rejection, live viewport/focus continuity, separate result identities. Existing interfaces tests plus affected installed Inventory/execution, shell and gallery gates; imports and broader ordinary coverage for shared contract changes. |
| Bounded overlay cost | `inventory_review.js` and its existing probe: avoid repeated self-membership validation for a window's own manual result. | Preserve mismatch/detail rejection and row result labels; demonstrate removal of repeated quadratic membership work without a new timing threshold. May accompany the renderer alignment where dependencies overlap. |
| Refresh consequence UX | `inventory_review.js`, `app.js`, existing confirmation component and their browser/installed execution consumers; DESKTOP_UI/PRESENTATION/FEATURES. Make exact Verify primary; warn before a scan can forfeit it; truthful supersession message. | Cancel has no scan effect; explicit confirmation retains normal revision/scope/admission checks; whole, selected and context Refresh routes; no unnecessary prompt after the exact option is consumed/unavailable; installed command journey. |
| Evidence correction and ablation | M1_PLAN/HANDOFF/CHANGELOG and retained D1/D2 receipts; study the D delivery diff and final table changes. | Correct the shell failures to foreground refusals and trace self-failure, retaining raw receipts. Assess removals/reuse by lost behavior, logic, test/environment complexity and maintenance costs, with source/evidence pointers. Report only; no study-driven simplification. |

Preserve workflow safety and execution-evidence token ownership, complete
operation selection for starts (including hidden selections), separate row
highlight and checkbox selection, bounded 256-row browser windows, revision
and lifecycle fences, exact/manual/automatic versus ordinary result truth, and
existing native ownership guards. Only checkbox bulk membership changes to
current search/facet matches; Refresh and missing-row visibility retain their
complete explicit scope. Reuse shared mechanics where they fit without a new
general UI framework. No backend eligibility preservation across scans, automatic
fallback/replay, terminal subset retry, or unrelated shell repair is authorized.
Each outcome requires fresh independent review before commit. Repository
recurrence and always-stop rules apply; the named findings are declared inputs,
not newly discovered defects. Finish with the requested study and recap.

The scope/evidence correction is committed as `aca87d4`; catalog coverage is
delivered in independently reviewed `47a4bcae`. Its host interfaces gate passed
2,024 cases (`catalog-interfaces-02.log/xml` in the evidence root). The earlier
sandbox run encountered native/path and package-build access failures and is
retained without an acceptance claim. The user stopped work on 2026-10-15
for separate shell review and approved resumption on 2026-10-16. The table candidate is preserved on disposable
recovery branch `codex/wip-20261015-1621-verify-table`, based on `47a4bcae`;
it is not a mergeable delivery. Refresh implementation and the final ablation
study remain pending. Rebuild reviewed work into coherent verified commits;
never merge or cherry-pick the recovery commit as-is.

Saved table-candidate evidence: Inventory native08 and four gallery cases native09 pass;
ordinary01 has 6,062 passes/four skips and three test-consumer failures corrected
by the 74-pass owning-module migration28 run. The later execution-helper
correction passes its 22 ordinary cases (execution30), but native12 does not
close execution acceptance: default stopped at a foreground guard; larger
timed out at initial readiness with no recorder failure and no Refresh admission.
The subsequent review identifies a D2 readiness-reconciliation defect; native
timeouts do not establish its exact response ordering. Twelve import contracts
pass. All failed receipts remain under the evidence root. Fresh table review
withholds approval. The earlier shell-gate adjudication was based on a mistaken
failure-state interpretation and is retracted below; no gate waiver is needed
for a product Plan-again defect that these receipts do not show. Those incomplete
attempts still do not satisfy the current shell gate. The approved recurrence
scope and resumption order are recorded below; current gates remain open.

The saved table candidate uses the existing `VisibleSequence` through one shared
server highlight owner, keeping Plan operation/dependency policy and Inventory
file membership separate. Inventory gains compact revisioned highlight and
highlighted-selection commands; direct command-catalog consumers in host,
transport, gallery and `tools/performance/bridge_event` migrate together.
Existing data-URL probes and table-loading instrumentation are direct consumers
of extracted browser imports/functions and must remain usable. Shared browser
gesture/navigation code should reuse existing behavior without a general table
framework. Selection replies preserve highlights; search/facet changes clear
them; sort/collapse preserve membership; a new scan/publication clears highlights
while retaining surviving checkbox selections. Extend the existing Inventory
native witness to inspect the actual outer viewport at nonzero scroll, including
an off-window range, rather than the non-scrolling rows element.

**Corrected shell evidence (2026-10-15):** all eight untraced cases in D2
shared01/shared02 and table native09/native10 stopped at the foreground guard
before the first Shift+F10 input. Their `plan_again` checkpoint is reached only
after Task 53 selection and changed-row rendering. The reported Task 52/pending
snapshot is taken earlier on every run, not at failure. These are incomplete
native-input attempts under TESTS, not evidence of intermittent Plan-again failure.
Native11 failed its own trace: normal pending eligibility entries overflow the
bounded trace, which the handler saves permissively then rejects strictly.
Retain all receipts; gallery acceptance remains separate. The corrected audit
and scripts are in `shell-review-01/` and `recurrence-evidence-audit-01.md` under
the evidence root. This correction does not resolve unrelated older D1/AB observations.

**Async-read recurrence — implementation approved 2026-10-16.**
The finite corpus is the three read families below, their Plan execution-window
adopters, and direct viewport/detail/navigation/start consumers in `app.js`,
their bridge/renderer contracts and existing browser/native probes. The common
mechanism is incomplete coordination of read ownership, invalidation and renewed
demand, not a shared backend or transport failure.

| Instance / consequence | Owner and present disposition | Common boundary |
| --- | --- | --- |
| Plan reload crosses newer foreground interaction; applied highlight/detail can disappear. | `loadPlanReview`; corrected in `b52f8ddf`. | Capture foreground ownership, preserve the incumbent review and retain dirty reconciliation at its offset. |
| Inventory live overlay crosses newer scroll/highlight; an old window can replace current rows or discard the final needed update. | `refreshInventoryOverlay`; saved candidate correction must be revalidated during rebuild. | Same foreground read boundary, current revision/offset checks and deferred dirty replay. |
| Copied-file readiness crosses an execution revision or returns conflict; the action can remain unavailable until another load. | `loadManualReadiness`, `originalExecution` and execution-window adoption; pre-existing D2 defect corrected in the rebuild. | Named execution observation owner plus coalesced demand and bounded conflict reconciliation, separate from Plan painting. |

The scratch A/B/C orderings and no-crossing control reproduce consumer behavior
on `47a4bcae` and `d1c3b325`; their direct window assignment is not proof that a
full Plan reload adopts while Verify is visible. Production fences that reload;
retained view completions can still adopt. Selection has similar retained-owner
code but reviewing-state admission limits its post-execution relevance. Thus
retrying the unchanged old revision alone is insufficient. Full census and source limits are in
`recurrence-census-01.md`.

Approved reorganization: give original-execution identity/revision
one named observation/adoption owner, separate from permission to repaint Plan;
feed it from matching authoritative reads. Apply one read-reconciliation rule
to the three families: preserve latest demand while a read runs, reject obsolete
paint, and reconcile still-owned demand after an authoritative revision or
foreground owner advances. A conflict is a revision hint, never verification
eligibility. Keep one in-flight readiness read and coalesced demand; bound conflict
reconciliation to one round per admitted demand, with actionable Reload if it
cannot settle. Execution facts must not roll back within the same execution and
must reset when the original execution changes. No retry loop against an unchanged
conflicting revision, transport-error polling or mutation replay.
Reuse existing foreground helpers and explicit domain adopters; no generic
request framework or merged result authority is proposed.

During implementation, revalidate the finite adoption sites against this mechanism
table. The separate bounded frontend fix covers production release/pane
ordering plus A/B/C/control, coalescing, repeated unchanged conflict, terminal
update and task/session/pane/Close retirement. Preserve existing Plan/overlay
witnesses and backend exact-start checks. The harness correction is a separate
test-only outcome: shared deadline-bounded foreground waiting for shell/execution,
truthful refusal facts and trace-overflow handling, preserving every input guard.
The user approved both bounded outcomes on 2026-10-16 and resumed the hardening
batch. Rebuild on `codex/verify-ux-rebuild` from `47a4bcae`, retaining recovery
`d1c3b325`/`fb2253e2`; never integrate their WIP ancestry. Root owns delivery
documents and integration. Atomic order: harness correction, readiness fix,
revalidated table alignment, Refresh consequence UX, then read-only ablation.
Readiness must land before or with Refresh confirmation. Re-check the saved
overlay fix against the common rule during rebuild, including obsolete rejection
and retained final demand; do not merely restore its earlier approval.

Readiness production scope is `app.js` execution-fact adoption and its existing
read/start consumers; existing Inventory app/Plan shell probes own realistic
release/pane ordering, currentness, bounded coalescing, conflict/error termination
and retained Plan state. Harness scope is `_headed_native.py`, shell/execution
drivers, trace handling and their existing ordinary/native tests; enumerate shared
helper consumers before editing. Preserve foreground/focus/hit checks and bounded
waits, with no input after refusal. Existing installed execution and shell cases
run early after focused tests; owning interfaces, ordinary/import and affected
Inventory/gallery gates remain required by dependency. Subject docs accompany
each behavioral commit, and each outcome gets fresh adversarial review. The
already declared defects are approved inputs, not new recurrence instances.
Other scope exclusions and mandatory stops remain unchanged. HANDOFF returns to
latest-session operational context; the exact prior user text remains in ignored
`recurrence-input-handoff-01.md`.

Rebuild prerequisites (2026-10-16): harness `8a780ac` and the readiness fix pass
fresh independent review. The real release/Verify producer witness fails on the
baseline and passes on the candidate; the no-crossing control passes both.
Focused gates pass 70 harness and 59 frontend cases. On the frozen combined
candidate, installed shell/execution pass all four sizes/cases, trace-enabled
shell passes both sizes with no overflow, interfaces pass 2,029 cases and all
12 import contracts hold. Evidence: `rebuild-{native,trace,interfaces}-20261016-01`,
`readiness-replay-identities-20261016-01.json` and the two outcome review reports.
This is prerequisite acceptance, not table/Refresh or final batch acceptance.

### M1-10 delivered register — 2026-10-13–14

Delivered from clean `milestone1` at `fc8a79b` through separately reviewed
atomic commits. The temporary hold after C and later resumption are recorded
in Git and evidence. Root owns this register, HANDOFF and CHANGELOG. Evidence remains under
`build/m1-10-20261013/`, with its local naming/retention conventions.

| Unit | Finite owners and consumers | Acceptance gate / commit boundary |
| --- | --- | --- |
| D — desktop integrity and GUI-A6 | Assets app/bridge/inventory review/plan review/integrity plus directly required markup/styles and task status; existing production JS probes and installed inventory/task-shell/execution/gallery helpers. DESKTOP_UI, BRIDGE, PRESENTATION, FEATURES. | Functional selection, Baseline/Verify/Rebaseline confirmation, truthful live/terminal overlays and pause/resume/cancel, execution-to-Verify navigation, first eligible exact manual action and explicitly ordinary fallback. Delayed/stale/recovery tests and real installed command journeys; preserve scroll/keyboard/selection custody and existing failed-read retries. Independently reviewed UI commits may divide ordinary controls from exact manual navigation after their backend gates pass. |
| E — checkpoint closure | Integrated A–D and their direct test/doc/helper consumers. | Ordinary suite, affected installed headed gates, import contracts, active-link/diff checks and fresh adversarial cross-component review; account for tests/receipts and all commits. Stop for recap and GUI tweaks. No M1-12 or release claim. |

Delivered A–C and resumed review corrections are condensed below. Their finite
implementation populations, earlier decisions and failed receipts remain in Git through `1648d2d5` and the
named evidence root; subject documents own current behavior. Scope preparation
and the earlier delivered-register condensation are committed as `a730165`.

| Delivered unit | Shipped result and preserved boundaries | Reviewed commit and evidence |
| --- | --- | --- |
| A — operation policy | Explicit confirmation and selected scope precede rebaseline admission. Eligible null-evidence and matching files are freshly hashed and conditionally baselined without claiming verification; engine/recorder behavior remains. | `6ba35753`; 3,504 affected department checks, twelve imports and `policy-review-01.md`. |
| B — exact manual workflow | Complete selected byte-producing population is classified in one coherent transaction, target authority is freshly admitted, then a second classification freezes current evidence. Separate session/history preserves original execution truth; no scan or persisted operation-time hashes. | `959f1bc9`; 239 focused and 3,520 affected department checks, twelve imports, `manual-departments-10.log`, `manual-imports-11.log` and `manual-review-01.md`. |
| C1 — server-owned selection | Initially empty exact file/folder/location selection; complete membership and counts include hidden/collapsed/off-window files. Warnings are inert. Existing view revision fences gestures, reads and later confirmation; selection grants no hashing authority. | `26e72ad`; 2,399 interfaces/tools checks, three skips, unaffected workflow evidence, 12 imports and seven installed checks. `selection-neighborhood-08.log`, `selection-installed-11.log`, `selection-review-01.md`. |
| C2 — ordinary integrity association | Current request/session binds exact selected scope, confirmation and controls. One latest ordinary result remains separate from ledger state and is wholly replaced even for zero outcomes. Real scan provenance, normalized partial-pause results, original-command recovery, rollback, stale-response fences and exact Close remain intact. | `eecf31c`; 3,348 neighborhood checks, three skips, 12 imports and eight affected installed obligations including traced Setup; independent partial-pause resume/cancel probes. `ordinary-installed-12.log`, `ordinary-installed-13.log`, `ordinary-review-01.md`. |
| C3a — execution target ledger reads | Released executions expose the existing target location through original Plan/execution binding. Opening creates no location, scan, native admission or hash. Missing scan provenance is explicitly null; complete ledger projection does not imply complete scan. Plan reads/selection/Close remain available. C3b owns auxiliary mutations. | `07947213`; 2,946 workflows/interfaces checks, 12 imports, installed Inventory and both execution-window cases. `execution-inventory-departments-01.log`, `execution-inventory-headed-01.log`, `execution-inventory-review-01.md`. |

The separate `bf9d649` Setup driver repair replaces retired hidden-Setup DOM
predicates with visible review and authoritative frozen context. The timeout
reproduced on accepted `26e72ad`; actual Plan again/new task/revisit and native
ownership guards remain. Its two-file change passed 37 ordinary checks and a
traced installed journey (`setup-driver-ordinary-03.log`,
`setup-driver-installed-03.log`, `setup-driver-review-01.md`). Retained captures
carry an undiagnosed label-legibility observation for the later GUI review;
behavioral DOM evidence does not prove pixel legibility.

Earlier foreground refusals remain failed receipts; unchanged checks passed
after user availability confirmations. C1 recovery `c3bb191` was rebuilt into
the reviewed commit without merging recovery ancestry. HANDOFF retains the
task-owned recovery/worktree cleanup pointers until final accounting.

C3b shipped as `41afd262`: original Plan/execution identity, results, times,
selection, detail/follow and Plan again remain separate from current auxiliary
activity. First exact manual verification, ordinary integrity, Refresh and missing
visibility share the retained task with distinct result generations, actual scan
provenance, original-command recovery, live controls and exact Close. Readiness
is not authority; the first valid manual claim consumes the opportunity through
failure/cancellation, while preclaim refusal does not. Linked verification stays
ineligible; no terminal subset retry, schema or verifier/recorder rewrite shipped.
Direct identity/catalog/fixture consumers migrated without retiring their checks;
review corrected original-execution retirement and no-scan visibility admission.

C3b acceptance: 6,049 ordinary passes/four expected skips (`c3b-ordinary-12.log`),
twelve imports (`c3b-imports-13.log`), and nineteen installed obligations by
dependency: fourteen in `c3b-headed-02.log`, four in `c3b-gallery-04.log`, and
Inventory in `c3b-inventory-17.log`. The latter passed with unchanged guards after
foreground/focus refusals. `auxiliary-review-luna-01.md` owns independent review;
`c3b-close-repro-01.log`, `c3b-review-corrections-01.log` and
`c3b-visibility-11.log` retain the Close, Gap/zero/partial and visibility witnesses.
The two `c3b-native-evidence*` manifests preserve 141 hash-verified evidence files.
Earlier broad/gallery/foreground failures remain failures, not acceptance.

The requested resumed A–C review is complete. Three fresh reports
(`resume-review-{ab,c,consumers}-01.md`) cover policy/recording, lifecycle/results
and all direct browser/validator/fixture consumers against `41afd262`.
A/B passed 43 fresh native cases with no product finding; stale delivery prose
was reconciled. Two finite omissions in C's original/current identity and closed
kind migrations were corrected in separate reviewed commits:

| Correction | Verified result and evidence |
| --- | --- |
| `bccd88f` — retain existing execution Inventory reads during live/paused auxiliary work | Original execution release proof authorizes existing reads; current release still gates selection/mutations. 234 drain, 2,015 interfaces and twelve imports; `resume-read-{drain-04,interfaces-05,imports-05}.log`. |
| `1648d2d5` — accept manual terminal records with exact pause capability | Complete-batch validation retains all kind/capability refusals. 164 focused and two installed host/transport checks; `resume-kind-{focused-03,installed-05}.log`. Interfaces: 1,782 unaffected passes in `resume-kind-interfaces-04.log` plus 234 drain passes in `resume-read-revision-07.log`. |

The latter gate exposed only an asynchronous test assumption: `dc80d06` permits
result revision advancement between independent live reads while retaining all
other fact equality. The failed receipt and independent red/green drain witness
remain; the consumer reviewer approved dependency reuse. Fifteen installed
receipts/identities are hash-verified in `resume-kind-native-evidence/`.
D must close the reports' remaining renderer/wrapper/current-status obligations;
no new effect authority or outcome was added by this review.

D1 shipped as `541a90f`, reviewed and fast-forward integrated on `milestone1`.
It delivers standalone Inventory checkboxes and complete selected/hidden counts,
Baseline/Verify/Rebaseline with revision-bound explicit confirmation, current
pause/resume/cancel, original-command observation and separate ordinary results.
Empty selection and canceled confirmation start nothing; actual scan provenance
remains separate. Current subject documents own the behavior; D2/E delivery is
recorded below.

D1's final gate passes 2,018 interface checks, 69 focused consumer checks, two
final browser probes and all nine affected installed obligations: Inventory,
four gallery modes, both task-shell sizes and both execution-review sizes.
The unchanged external Inventory table-loading probe passes one child with
before/after installed identity and asset-restoration checks; this establishes
consumer correctness, not a performance claim. Evidence in the existing root:
`d1-interfaces-20261014.log`, `d1-consumer-ordinary-final-20261014.log`,
`d1-probe-final-20261014.log`, `d1-native-final-20261014.log`,
`d1-native-final-temp-20261014/`, and `d1-table-inventory-20261014-01.*`.
`d1-final-review-20261014.md` closes independent review; 51 final native evidence
files are hash-verified in `d1-native-evidence-final-20261014/manifest.json`.
No recovery commit is an integration unit. HANDOFF retains cleanup pointers.

The user's 2026-10-14 review replaced the rejected selector-consumer migration
with removal of the checkbox's unused duplicate `data-node-id`. Selection uses
its row closure; row identity remains unique. Only D1-owned checkbox tests were
adjusted; gallery row selectors and the external tool remain unchanged. The
unnecessary facts wrapper was also removed to preserve original facts/Details
alignment. Three status witnesses now count the reusable feedback line rather
than conflating it with the new selection-count paragraph; geometry, input
guards and other verdicts remain unchanged.

The retained failure history is evidence, not extra product defects: Inv01's
pause-race hypothesis was unproved and almost certainly masked the missing-stat
failure. Its attempted fix introduced Inv02's blocking UI-thread wait. Inv04's
raw visible counts were 0/0/0/0, not the earlier 1/1/0/1 interpretation; expanding
the helper's collapsed folder resolved that witness. Shell Shift+F10 guards remain
unchanged with five-Boolean diagnostics; later passes establish no earlier cause.
Pytest removed raw retry-173 before copying; its failed parent log remains,
without a raw-evidence claim. The final nine-check run uses a unique retained
base directory and supplies current acceptance. Earlier preserved failures remain
in `d1-native-evidence*`; reports retain their corrections and superseded claims.

Two separately reviewed prerequisites/corrections accompany D1:

- `107dfa2` fixes shared workflow conversion of missing rows' historical stat
  into current expected stat. Real Baseline/Verify/Rebaseline red/green cases,
  177 owning tests and 2,960 workflow/interfaces checks pass. The defect failed
  entire affected selections, including CLI use; BUGS records its core-workflow
  consequence. Core, repository, verifier policy and historical evidence remain.
- `f26cb57` restores C3b's distinct execution publication branch and missing-
  reviewed-plan backstop, preserving optional auxiliary association. The
  reproducer is red/green; 45 lifecycle and 215 direct-consumer tests pass with
  independent approval in `c3b-backstop-review-20261014.md`. No supported path to
  the lost check was found. It is fast-forward integrated in `milestone1`.

### D2 — verified implementation and prerequisites

The D1-based design was revalidated through `d2-design-refresh-01.md`,
`d2-kinds-design-20261014.md` and `d2-ui-refresh-20261014.md`. The delivered
prerequisites are independently reviewable commits:

| Outcome | Commit and verification |
| --- | --- |
| Consolidate task/effect/session catalogs in lifecycle, task port and browser owners, preserving distinct admission and pause capabilities. | `d52a7b2`; 837 direct-consumer tests, 2,020 interfaces tests, 12 imports; `d2-kinds-review-20261014.md`. |
| Preserve foreground Plan ownership across execution-triggered full reloads; reconcile authoritative summary/window facts after the interaction. | `b52f8dd`; baseline-failing probe, 2,020 interfaces tests and both installed execution sizes; `plan-custody-review-20261014.md`. |
| Correct the standalone Inventory confirmation witness to the existing conditional focus contract, with strong enabled-invoker Cancel proof and bounded diagnostics. | `cb48274`; complete owning-module ordinary/native checks, including `d2-inventory-native-20261014-04`; `m1-10-final-cross-review-20261014.md`. |

D2 UI shipped as `d88f863`, delivering mounted Plan/Verify
panes, exact first **Verify copied files**, explicit selected **Verify current
state** fallback, current auxiliary controls, and separate original/manual/ordinary
results. Inapplicable Baseline/Rebaseline controls are hidden on sync tasks.
Readiness grants no authority and never starts or substitutes an operation.
Accepted activity adoption updates current request/session together while keeping
original Plan identity and fencing older task lists.

Owners are app, panels, Plan/Inventory review, task status and the narrow hidden
pane style. Direct consumers are the existing execution, task-shell, Plan and
Inventory probes, installed execution child/parent and the gallery's shared pane
callback fixture. No wire command, schema, generic pane framework, external
performance-tool change or backend-policy weakening was added.

Final evidence under `build/m1-10-20261013/`:

- Combined frontend gate: 59 passes (`d2-combined-frontend-01`). Owning interfaces
  gate: 2,024 passes (`d2-final-interfaces-20261014-02`). Later helper-only edits
  have exhaustive owning-module ordinary reruns: execution 21, Inventory 1.
- Installed gates: both execution sizes pass in `d2-execution-native-20261014-17`,
  Inventory passes in `d2-inventory-native-20261014-04`, both shell cases pass in
  `d2-foreground-native-20261014-03`, and four gallery cases pass in
  `d2-shared-native-20261014-02`. The unchanged guards, geometry/scroll/focus,
  trusted selection, actual effects, control routing, independent result owners
  and exact Close remain asserted. Failed attempts are retained, not acceptance.
- The ordinary repository gate and complete external-basetemp tools/custody
  correction are `d2-ordinary-20261014-01/02`; their populations overlap and are
  not summed. The 12 import contracts remain valid. E confirms dependency reuse,
  final documentation and recovery accounting at checkpoint closure.

`d2-final-review-20261014.md` owns independent D2 review. Two product findings
were corrected: the separately committed Plan reload owner race, and D2's
accepted-current-request omission. Native Refresh/release/superseded readiness
and the explicit selected fallback now complete. Helper corrections retain the
original guarantees: order selection before its enabled fallback; choose a
fully visible, hit-owned Plan row rather than one covered by the sticky header;
read capture completion from its exact-phase owner; and test modal focus only
when the invoker was available at close. Native14 disproved the proposed passive
row-replacement scroll diagnosis. No third substantive product defect was found.
Raw receipts and reviews retain the diagnostic chronology and withdrawn claims.

### E — checkpoint closure

`m1-10-final-cross-review-20261014.md` closes the integrated A–D review and
verification accounting. Nine affected installed checks pass across the named
final receipts; the ordinary/department/helper/import populations are accounted
by dependency without summing overlapping runs. Final local-link and diff checks
pass. Product/package bytes remain identical to the accepted installed source.

All four recovery snapshots were rebuilt into reviewed commits without WIP
ancestry and fully accounted in `recovery-accounting-20261014.md`. Their complete
history remains recoverable in the verified `m1-10-recovery-snapshots-20261014.bundle`.
The four local recovery refs, four integrated task branches and two clean
temporary worktrees were removed; only regenerable caches accompanied worktree
removal. Raw evidence, manifests and five pre-existing stashes remain.
`recovery-cleanup-20261014.log` records the checks and exact removals.

Stop here for recap and GUI tweaks. Existing Inventory legibility and physical
wheel/tilt observations remain for that review, without a claimed fix or visual
acceptance. M1-12, release, terminal subset retry and unrelated optimization
remain outside this delivery.

Preserve atomic publication, conditional recording including prior absence,
root admission, fixed continuation identity and original execution truth.
Manual exact readiness excludes already-verified members only after proving
the entire applicable set coherent; an empty set starts nothing. A selected
byte operation without a successful terminal outcome, current committed
evidence, or stable settlement blocks the handoff. Unrelated non-byte failure
or close/flush degradation alone does not revoke committed item evidence.
The new session uses current ledger evidence and its own history identity;
ordinary integrity and manual post-copy results remain separate.

Existing 120,000-candidate admission, 256-row presentation windows and bounded
command custody remain. No schema redesign, persisted operation-time hashes,
browser-owned domain policy, new performance targets, automatic manual-start
replay or terminal Verify-remaining/subset retry. Archived D6 missing visibility
acknowledgement remains distinct; AB-7R's rejected blanket resend and the
deferred generic owner merger remain rejected/deferred. GUI-A6 and functional
inventory checkboxes are activated here; prior GUI batches did not deliver them.
AGENTS scope, recurrence and mandatory preservation stops apply throughout.

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

## Loading sequence and axis scrolling — 2026-10-12

LS1 (`81731de`) immediately shows the existing blank Plan/Inventory review shell
with truthful Checking/Planning/Scanning and indeterminate progress; frozen
inputs, command custody, refusal/recovery and complete publication remain.
Interfaces/tools passed 2,385 checks (three privilege skips), installed
task-shell/Inventory and independent review passed. Six 8k/32k startup samples
are diagnostic, with warm filesystem caches and no backend or latency promise.
Evidence: `build/loading-sequence-20261012/`; PERFORMANCE owns observations.

AX1 (`ca31654`) did not reproduce the axis lock in 80 valid CDP trials.
The first Windows injection stopped before input on job-ownership evidence;
neither receipt establishes physical-device behavior. The user then explicitly
authorized AX2 despite the unconfirmed cause. AX2 (`fc8a79b`) gives Plan/Inventory
one two-axis scroller and sticky header while generic/Setup tables retain their
existing scrollers. Row/window bounds, direction/prefetch, widths, exact
selection/request ownership and keyboard reveal remain. Interfaces/tools,
installed task-shell/Inventory/execution/tree/gallery and fresh review passed;
foregrounded `axis-candidate-03` passed all 20 actual-table sequences. Evidence:
`build/single-scroller-20261012/`, including failed receipts and manifests.
Recovery `dbcc686` was rebuilt from `ca31654`, never merged as-is. The reported
physical wheel/tilt symptom remains unverified; no backend optimization shipped.

## Review follow-ups — 2026-10-11

| Closed row | Shipped outcome | Commit / evidence |
| --- | --- | --- |
| RF1 | Later wheel/pointer/touch input retires navigation intent while compatible scroll reads survive. Exact external intent and existing placement/read bounds remain. | `23e5810`; real-event red/green probes, 2,385 interfaces/tools checks (three skips), installed tree/Inventory/shell and independent review. |
| RF2 | Move badge text alignment, opacity hover/press, inline-annotation gap and Inventory disclosure rotation corrected. | `7136764`; 84 focused, 2,385 interfaces/tools checks (three skips), gallery light/dark/forced-color/reduced-motion and independent review. |
| RF3 | Only execution `skipped` with reason `noop` displays green Completed; other skips remain neutral Skipped. Raw notes and independent verification truth remain. | `42aa079`; red/green matrix, 2,385 interfaces/tools checks (three skips), six installed cases and independent review. |

Evidence: `build/review-followups-20261011/`, including unchanged-input native
retries and earlier failures without invented causes. RI1/RI2 were read-only
startup/axis investigations from `350af26`; LS1/AX2 above subsequently delivered
the user-approved frontend outcomes. Initial cost attribution does not authorize
backend changes; RF1 cancellation and browser axis movement are separate causes.

## Scroll continuity and interruptible navigation — 2026-10-11

| Closed row | Shipped outcome | Commit / evidence |
| --- | --- | --- |
| SN1 | Ordinary focus restoration preserves scroll; explicit keyboard intent precedes adoption. Exact dropped-read settlement handles Settings/zero-height restoration without failed-read loops. | `940c7ef`; focused controls, loading method, interfaces/tools and installed `sn1-native-03`. |
| SN2 | Viewport direction places windows with 32 rows behind and prefetches within 64 rows of the travel edge; endpoints and useful early/short/failing reads retain correct settlement. | `fac8ed0`; 2,385 interfaces/tools checks (three skips), 406 tools checks, installed tree/Inventory/shell and twelve matched 240/1,000-row/s children. |
| SN3 | At most one navigation read and latest pending target; later input retires intent without reclaiming focus or undoing/replaying admitted mutations. Noncoalescible selection commands retain individual custody. | `350af26`; delayed ownership/interruption probes, 2,385 interfaces/tools checks (three skips), installed tree/Inventory/shell. |

All received independent review. Evidence: `build/scroll-navigation-20261011/`;
failed and successful native receipts remain. SN3 recovery `eba28a6` was rebuilt
on SN2, never merged as-is. PRESENTATION/DESKTOP_UI own behavior; PERFORMANCE
owns SN2's measured revision, not a universal timing claim. One read/256 rows,
server range/anchor policy, exact visible revisions and task/view fences remain.

## Continuous-scroll adoption and follow-up measurements — 2026-10-09–10

SW1 (`93a13b8`) corrected Plan/Inventory's shared viewport-demand starvation
after user recurrence review: compatible responses settle independently of
newer demand, with exact navigation/task/session/publication/view fences and
one read/256-row bounds. Focused/interfaces and installed Inventory/tree/shell
passed independent review. The native menu fixture now waits for actual pointer
highlight publication; no menu product change or weakened input guard followed.

SW2–4 (`0580b1b`) delivered loading diagnostics and experiments, not production
prefetch or key caches. Twelve installed children measure first/last-input
delay, cadence and 12-second forward/reverse trajectories; 37 focused and 402
tools checks (three skips) passed independent review. SW3 justified subsequent
SN2. SW4's bounded encoding/cache prototype still requires ordinary-response
and actual drain-prefix/custody proof before any product delivery. Row-schema
migration and renderer rewrites remain deferred. Evidence:
`build/scroll-window-study-20261009/`; PERFORMANCE owns methods and limitations.

## Bridge counter optimization and loading investigation — 2026-10-07–08

BC1a (`806df04`) removed observer hot-loop overhead; BC1b (`9d09f70`) uses bounded
bulk JSON/UTF-8 string encoding with scalar failing-chunk fallback. Canonical
bytes, inclusive ceiling, Unicode/first-failure precedence, bounded oversized
work, occurrence counting, detached ownership and one-time hostile enumeration
remain. Gates included 5,982 ordinary checks, 12 imports, six installed transport
checks and independently reviewed six-child measurements with restored assets.
No wire, domain or timing threshold changed. Evidence:
`build/bridge-counter-study-20261007/`; PERFORMANCE owns corrected-baseline values.

BC2–5 (`59e92ae`) investigated capture/fields/DOM/steady scrolling on unchanged
product. The shared Plan/Inventory mechanism conflated current viewport demand
with exact response ownership; user review authorized the later SW1 correction.
No isolated instance fix or DTO/layout/cache/prefetch delivery followed from the
investigation itself. Raw failed receipts and controls remain historical.

## GUI Inventory refinement — 2026-10-05

GUI-C1–C5 closed the user-approved follow-up and renewed B2 scope. Evidence,
original user handoff, exact gate receipts and reviewed recovery accounting:
`build/gui-inventory-refinement-20261005/`, especially `integration.md`.

| Closed row | Shipped outcome | Commit / evidence |
| --- | --- | --- |
| C1 | Compact bounded Plan/Inventory window fields retain full-path search and revision-guarded complete snapshot details, distinct from fresh ledger evidence. Identities/enums are never truncated. | `9868f5c`; 5,921 ordinary/four skips, 12 imports and seven installed obligations. Complete envelopes 1,193,678/2,395,485 bytes remain below 8 MiB. |
| C2 | Refresh selected targets the current visible active eligible row even with Details hidden; item-card actions retain their displayed item. | `dfd9291`; red/green target witness, 64 focused, 1,951 interfaces, 12 imports and installed Inventory/tree. |
| C3 | Owned context gestures suppress native fallback, including Menu-key follow-up; acknowledgement requires own missing presence, not missing descendants. No Restore context action. | `95ff419`; 67 focused, 1,951 interfaces, 12 imports and seven installed obligations. |
| C4 | Shared 24px zebra rows, disabled unchecked selection visuals, Notes, concise Presence and shared typography; generic tree remains 28px. Filename alone grows passively; Notes donates deliberate resize width. | `3c984b6`; focused/interfaces/import and eight installed obligations, including forced-color active-cell correction. |
| C5 | Optional loading collector, task-scoped one-running/latest-queued Inventory reads, then separate Plan off-window keyboard leading-margin correction. Navigation, action custody and 256-row bounds remain. | `61ee878`, `4122b10`, `706be4b`; ordinary/import/method, installed and repeated six-child matrices. |

Every unit received fresh review. C5 fixture prerequisites `6c6e10f`/`455fd49`
retain bounded labels and genuine RECASE evidence; failed receipts remain.
PERFORMANCE owns measurements, not latency/compositor guarantees. Recovery
contents were rebuilt and accounted without merging WIPs. No placeholders,
row-limit/wall increase, new filesystem effect, backend selection or hashing
shipped. Functional checkboxes and execution-to-Verify remain M1-10;
irreversible-count presentation and fixed Filename under Details remain deferred.

## GUI follow-up batch — 2026-10-05

| Closed row | Shipped outcome | Commit |
| --- | --- | --- |
| B1 | Bounded Plan labels/enums and exact individual detail disclosure preserve identities, revisions and response wall. | `53e1abb` |
| B3 | Verify Setup/status alignment with stable summary/detail and truthful progress/recovery. | `2828b8b` |
| B4 | Local `yyyy-MM-DD HH:mm` UI times; diagnostic raw values remain. | `0f87f6a` |
| B5 | Details capped at 20rem, more item height and full paths from known roots without filesystem probes. | `61a5cf5` |
| B6 | Shared scoped row menus with existing actions, exact row/task/window ownership and no opening-time read/selection effect. Inventory has no Select/Deselect or Restore menu action. | `614cd19` |

Independent review, ordinary/interface/import and installed obligations passed
per unit; evidence and original findings: `build/gui-followup-20261005/`, including
`integration.md` and retained native/gallery disposition receipts. B2's repeated
full-text envelope finding paused implementation after recurrence review; the
user first deferred it, then approved the coherent compact-window/exact-detail
correction and table alignment as C1/C4. Widening the wall was rejected.
Functional checkboxes and same-task execution-to-Verify remain M1-10.

## GUI alignment batch — 2026-10-05

| Closed row | Shipped outcome | Commit |
| --- | --- | --- |
| A1 | Refreshable move-reveal refusal preserves coherent summary/window and aligns conflicts to loaded offset. | `4f314b2` |
| A2 | Only Filename passively grows; headers align and deliberate Notes-limited resizing remains. | `498eb24` |
| A3 | Shared counted Fluent filter menu with canonical categories, All reset and exact pending/retirement guards. | `49801f7` |
| A4 | Optional full-height right Details with separate global/item scrollers and bounded pane/rail widths. B5 later narrows the cap. | `4a39789` |
| A5 | Inventory adopts Setup/status/table/filter/details surfaces and bounded stored-baseline digest; no fresh hash or detail fanout. C4 later replaces its initial five-column/28px table. | `37d89ef` |
| A7 | Projection-owned same-parent MOVE/RECASE Rename classification; genuine move groups start collapsed with bounded destination/origin annotations. Raw operations and effects remain. | `583f14d` |

Each unit passed its focused, department/ordinary, installed and independent
review gate. Evidence: `build/gui-alignment-20261005/` and
`build/rename-move-20261005/`, with exact manifests and `integration.md`.
The requested external Claude review could not authenticate; the user approved
independent internal review, with no external approval claimed. A6 execution-to-
Verify was deferred to M1-10 because it needs association/retention/lifecycle
policy beyond an enabling switch. Server selection, counts, raw evidence and
bounded windows remain; no new hashing, persistence or execution authority shipped.

## Plan GUI refinements — 2026-10-04

GUI-RF1 (`1865d66`) exposes bounded preflight refusal origin/codes; GUI-RF2
(`53fb959`) restores grouped move destinations with revisioned canonical reveal;
GUI-RF3 (`3c0378a`) adds Pause/Resume and five-second two-click Stop arming with
exact pending/task/session retirement. Effects and selection authority remain.
Each passed ordinary/import, all 35 installed obligations across retained runs
and independent review. Evidence: `build/gui-refinements-20261004/`.
Recovery was rebuilt, never merged as-is; failed native receipts remain.
The seven optional benchmark inventory-command catalog omissions were excluded
from this batch and later fixed on 2026-10-04; [BUGS](BUGS.md) records closure.
`rf2-command-catalog-audit.json` retains the original finding; no new benchmark
result is claimed here.

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
register; the exFAT FileIdInfo defect was outside this completed work and was
later fixed on 2026-10-01 as recorded in [BUGS](BUGS.md). Recovery tips were accounted and
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
defect was later fixed on 2026-10-01; [BUGS](BUGS.md) records closure.
Git retains implementation detail; the evidence roots retain failed receipts.

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

## Completed M1-9 — 2026-10-01 – 2026-10-02

Delivered from `937af54` on `milestone1`, closed in `0160f87`.

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

Inventory publishes a complete or prior-complete ledger view; this does not
claim a complete preceding scan. Warnings remain outside action scope, and
server-owned folder scope is independent of filters/windows. Refresh re-admits
location authority; visibility needs a current complete publication. Conditional
writes retain original facts and actual partial/uncertain dispositions. Receipts
share the 48-entry admission capacity until Close; no automatic replay or batch
atomicity is promised. INVENTORY/PRESENTATION/INTERFACES/BRIDGE own behavior.

Final gates: 5,829 ordinary/four skips, 12 imports, all 35 installed obligations
across dependency-scoped runs, later 1,890 interfaces checks, document/diff and
independent reviews. Screenshots prove browser surface, not compositor health.
Raw successes/failures/reviews: `build/m1-9-20261001/`, including final
`complete-*`, `native-wait-*`, `headed-recheck-*`, `native-replacement-*`,
`inventory-headed-focus-ready.log` and `cold-evidence-final-20261002.log`.
Thirty-four receipt/identity copies are verified in `inventory-native-preserved/`.
Recovery `4b936db` was rebuilt, accounted and pruned; original patch retained.
New integrity controls/overlays/manual post-copy verification, schema/history,
broad lifecycle redesign, performance targets and release were not delivered.

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
