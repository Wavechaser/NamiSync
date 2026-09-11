# M1 Delivery Register

This is the sole active M1 delivery register. It records remaining accepted outcomes, their order, and the verification that closes each one. Implemented contracts are owned by their active subject documents; completed delivery history and superseded mechanisms are in [obsolete](obsolete/). The archived plan files retain historical staging and review but are not instructions for new work.

[BRIDGE.md](BRIDGE.md) owns external command, transport, retry/recovery, and bridge-gate contracts. [PRESENTATION.md](PRESENTATION.md) owns trees, views, search, selection, sorting, and scale evidence. [INTERFACES.md](INTERFACES.md) owns implemented task lifecycle and desktop host/package rules. [FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [DEFENSE.md](DEFENSE.md) remain the owners of product behavior, cross-layer meaning, and safety/evidence policy.

[PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) is the closed maintenance
subregister for the completed production-ablation pass under M1-12. Its PR-0
through PR-9 rows remove redundant implementation and test prescriptions; they
do not add, defer, or reinterpret an M1 product outcome.

## Main objectives and current boundary

[REDUCTION_FOLLOWUP.md](REDUCTION_FOLLOWUP.md) owns the accepted narrow
immutable-value, scan-validation, history encoding/projection, and executor
simplification follow-up under M1-12. Its NR-0–NR-9 register and migrated RF-E/RF-X
dispositions preserve existing product outcomes; implementation and integrated
verification are complete. Further product simplification is outside the
remaining frontend delivery scope.

The secured desktop host and transport, presentation foundation, current service/CLI surface, and implemented ledger/history boundary are active. The frozen v1 event-and-transport custody claim remains closed at its bridge evidence owner. That closure does not establish whole-runtime containment.

The process-live desktop task shell, shared location admission and frozen Setup
are active, including plan/inventory starts and Plan again. Finish reviewed
execution, execution/inventory projections, integrity controls and first manual
post-copy verification, then release closure. These remain unrealized frontend outcomes. The history page, global-settings mutation
page, drag-and-drop, file-scoped planning, durable task survival across a process
restart, durable sort preferences, status/progress or global-flat sorting, and
compare-and-accept rebaseline semantics remain deferred. User-facing terminal
execution/verification retries (including Verify remaining), user-invoked session
cleanup/trash purge, and richer I/O error categories are deferred to M2; see the
feature-only [M2 proposal](M2_PROPOSAL.md). Existing automatic retries, owned-temp
recovery, transport replay, close/shutdown recovery, and live pause/resume are
not removed by those deferrals.

The prior aggregate complete-owner-graph model and BR-G-45 are retired. No future work inherits its reservation, DTO, lease, byte-budget, command-count, or representation recipe. Completed M1-4 replaced the former task lifecycle/retention preservation checkpoint. Existing externally enforced ingress and population bounds remain active independently.

## Remaining checkpoints

### Icon removal and upgrade verification (2026-09-11)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-I3 | Verify catalog removal and package-version migration, document their boundaries, and correct any demonstrated gap. | 29 maintenance tests; tools department 334 passed, 3 skipped; unchanged real-archive check and fresh adversarial review passed. No tool correction needed. | Complete |

Observed base: `fe3c11c`. Finite corpus: tools/icons.py and its catalog,
tests/test_icon_maintenance.py, fixed registry/CSS consumers, TOOLS and existing
icon guidance. Implementation population: focused maintenance tests, TOOLS,
this register, HANDOFF and the existing CHANGELOG task; tool correction only
if a demonstrated transition failure requires it. One verification/documentation
commit; no actual package upgrade, glyph removal, runtime change or shadow work.
Regression study preserves selected bytes/provenance, explicit fallbacks,
read-only check and refusal before mutation for invalid inputs or modified stale
files. Existing tests cover pruning but do not yet prove a successful version
transition end to end. Current fixed asset/caller interfaces remain unchanged.
Existing repository stop rules apply.

### Startup GUI icon foundation and shadow audit (2026-09-11)

GUI-I2 continues the uncommitted GUI-I1 outcome at the user's request: simplify
icon maintenance while preserving the exact 47-glyph runtime vocabulary and
appearance. The accepted outcome is one authored catalog plus an offline
generator/check command, with no parallel hand-maintained per-icon test catalog.
Status: complete. Gate: meaningful tool corruption/refusal/drift
tests, icon consistency/provenance/safety/wheel checks, tools/interfaces tests,
ordinary suite (new test module registration), installed headed gate and fresh
adversarial review. No new icons, placements, shadow fix or runtime loading.

Finite population: `tools/icons.py`, `tools/icons.json`, `.gitattributes` LF rules for generated owners, marked generated regions
in icons.js/components.css, SOURCE/native assets (must retain current bytes),
existing icon/gallery/test-support consumers, new `tests/test_icon_maintenance.py`
and its tools-department registration, plus AGENTS, DESKTOP_UI, this register,
HANDOFF, CHANGELOG and README as needed. Existing GUI-I1 changes are the
preservation baseline; the user authorized deleting the superseded ICONS.md
after its 47 names were checked against the catalog. One coherent maintenance-tool outcome
owns all required migrations. No shipped tool/catalog or new dependency.

Regression study: unknown glyph/size refusal before DOM creation, fixed local
URLs, currentColor and native-size selection, immutable upstream integrity,
exact package coverage, semantic restraint and UTF-8/LF preservation remain.
The generator validates inputs and archive before writes; check is read-only,
rejects drift, and authenticates against the pinned archive. It must not extract
arbitrary archive paths, silently invent fallbacks, or remove unrelated files.
Removing duplicate test constants does not remove independent tests of the
generator's rules. Existing repository stop rules apply.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-I2 | Simplify the uncommitted icon foundation with one authored catalog and maintenance sync/check command. | 61 focused checks; 4,972 ordinary tests passed (4 skipped); all 30 installed headed tests passed; authentic pinned-archive check and zero-change sync passed; fresh adversarial review approved. | Complete |
| GUI-I1 | Import and register the user's ICONS.md glyph vocabulary with deliberate 16/20/24 px artwork selection; establish selective icon semantics. | Pinned package/hash, SVG safety, exact mappings and wheel coverage verified; 1,520 interface tests and all 30 installed headed tests passed. Final independent adversarial review approved. | Complete |

Observed base is M1-6 commit `76ba7d0`; only the user's untracked `ICONS.md`
pre-exists. GUI-I1 owns fixed local SVGs/SOURCE, icons.js, icon CSS, icon and
gallery evidence consumers, and documentation in DESKTOP_UI, this register,
HANDOFF, CHANGELOG and README's phase synopsis. Existing package-data glob must
cover the exact expanded set; no runtime dependency or dynamic registration is introduced. Keep upstream
version/license and existing glyph names/API stable. Audit requested size
availability before selecting fallbacks. One coherent icon-foundation outcome
includes its tests and docs. GUI-I2 replaces the root list with its JSON catalog
under the user's explicit cleanup authorization.

Regression study: fixed names and own-property admission must continue rejecting
unknown/prototype/path input before DOM creation; status/badge meaning, forced
colors, accessible control names, M1-6 task effects and existing icon consumers
remain unchanged. Gallery evidence must cover the expanded registry rather than
silently accepting only its former four glyphs. No blanket surface decoration,
startup layout rewrite, badge redesign, shadow fix or Mica removal is included.


Pinned inventory study confirms all 47 requested Regular names exist in
`@fluentui/svg-icons@1.1.334`. Use 136 distinct native SVGs for the 141 glyph/size
combinations; explicit 20 px fallback covers Arrow Sync Checkmark at 16,
Database Arrow Up at 24, Folder Holder at 16/24, and Timeline at 16. The existing
four 20 px assets and metadata remain unchanged. Shared size classes select
fixed per-glyph mask variables; no URL is constructed from runtime input.
Final GUI-I1 evidence is `build/gui-icons/interfaces-01.txt` and `headed-03.txt`.
The gallery verifies all 141 mappings and sequentially decodes each of the 136
unique assets once, without retry. Its earlier concurrent probe recorded one
unexplained light-mode load failure; the old Boolean evidence cannot establish
the cause. An earlier shell focus failure passed in isolation and in the final
full gate without a code change. See HANDOFF for environment/diagnostic limits.

### Shadow composition audit (2026-09-11)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-D4 | Re-audit our shadow layers, color and alpha composition for an application defect exposed by WCG. | Source audit found matching Fluent black shadow tokens and no inherited popup opacity/duplicate elevation. Paired Mica diagnostics confirmed native alpha-zero white/black; user observes halos on single/nested translucent receivers with key/combined shadows, not ambient/none or opaque receivers, with no noticeable white/black difference. Native probe confirms 10-bpc WCG SDR. Exact blend fault remains unproven. | Complete: diagnostic only |

GUI-D4 does not authorize production/test changes. Existing stop rules apply.
Its temporary comparison wrappers/scenario and evidence use the existing ignored
`build/gui-tuning/halo-10bit/` conventions. The scenario derives from observed
`76ba7d0`, independent of simultaneous icon-gallery edits. Native Mica remains;
only each diagnostic process's controller hidden RGB and receiving samples vary.

### GUI integration tuning (2026-09-11)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-1 | Restore gallery-equivalent persistent selection fill and accent indicator on the live task rail; retain the Close button. | Pre-fix headed reproducer; 56 focused, 1,503 interface and all 29 installed-wheel headed tests passed; all 12 import contracts, diff checks and fresh adversarial review passed. | Complete |
| GUI-D1 | Investigate SDR dark flyout haloing and discuss findings without implementing a shadow change. | Current shadow/material CSS, appearance owners, gallery isolation and tests, DESKTOP_UI guidance and originating HDR-fallback commit inspected; separate read-only review confirms source findings, with visual cause unconfirmed. | Complete: discussion only |
| GUI-D2 | Investigate the reported dark-only halo on 10-bpc-or-higher SDR output, distinguishing display depth from automatic color management. | Inspected Windows/NVIDIA settings, production/gallery owners, Microsoft/Chromium primary sources and diagnostic host media state. User's repeated comparison confirms automatic color management off removes the halo; native probes confirm WCG to ordinary SDR transition at unchanged 10 bpc. Findings and limitations recorded in HANDOFF; exact renderer cause remains unconfirmed. | Complete: discussion only |
| GUI-D3 | Compare transparent Mica and fully opaque diagnostic hosts with identical gallery cards/shadows, at 10-bit SDR with automatic color management enabled. | Native controller alpha confirmed 0/255; opaque fallback and Mica landed. Paired card reports and popup shadow/surface/border/filter match; native probe confirms WCG at 10 bpc, HDR off. User reports opaque window does not appear to produce halo. Screenshots inspected without claiming a pixel-equivalent comparison or proven renderer fault. | Complete: diagnostic only |

GUI-D2 authorizes diagnostic-only files in ignored `build/gui-tuning/halo-10bit/`
under its local conventions, plus findings in this register and HANDOFF.
No production/test change, driver installation, global browser flag, or shipped
shadow workaround is included. Any temporary diagnostic setting is restored;
unrelated user windows/data remain untouched. Existing stop rules apply.

GUI-D3 extends the same diagnostic directory and findings documents only. Its
finite population is a process-local gallery launcher, separate data/evidence
for each host, and native display-state evidence. Production/test sources stay
unchanged. Opacity removes both native Mica and controller transparency through
the existing fallback; cards and shadow CSS remain identical. Final review must
distinguish a host-opacity dependency from proof of a particular renderer fault.

The unresolved dark flyout halo is tracked in
[BUGS.md](BUGS.md#desktop-material-composition) at the user's request. GUI-D2/D3
established reported Advanced Color/transparent-host dependencies, not a
specific renderer cause or correction. Mica remains required; the issue is
unfixed and adds no M1-6 implementation or release gate. GUI-D4 reopens the
bounded investigation only; it does not authorize a workaround.

GUI-1 is one atomic presentation fix based on clean `e19ed9d` on `milestone1`,
delivered as `fix(web): restore live task rail selection cues` in that checkout.
Its finite production population is `namisync/interfaces/web/assets/components.css`;
test population is `tests/interfaces/web/test_design_tokens.py`,
`tests/interfaces/web/_task_shell_headed_child.py`, and
`tests/interfaces/web/test_task_shell_headed.py`. Documentation population is
this register, `DESKTOP_UI.md`, `CHANGELOG.md`, and the replaced `HANDOFF.md`.
The live rail owns navigation state through `aria-current="page"`; shared
component CSS owns paint. Preimplementation inspection found that CSS recognized
only `aria-current="true"` and `aria-selected="true"`, explaining the missing
fill and marker despite existing passing navigation checks. The fix adds exact page
selectors throughout ordinary and forced-color current-state rules, preserving
the existing gallery variants, pressed/hover behavior and focus indication.
The headed computed-style assertion failed before the CSS correction and passed after it.
The acceptance gate above includes selection transfer and persistent marker/fill
on actual live rail buttons with the separate Close action intact.

Non-goals: close icons or layout redesign, lifecycle/admission changes, shadow or
material changes, M1-6 onward, and revival of archived presentation recipes.
The established gallery selection contract is the reference. Lost navigation,
Close semantics, accessibility state or existing theme behavior is a regression
to correct within GUI-1. Repository stop classes remain unchanged. GUI-D1 is a
read-only discovery outcome over the named corpus, not shadow-fix authority.
Generated diagnostics use ignored `build/gui-tuning/`: `evidence/` holds command
logs and review receipts; remove only task-created disposable inputs at closure.
Final headed acceptance is `evidence/headed-03.txt`, run on the interactive
desktop with pip cache disabled. Earlier attempts hit a shared pip-cache access
failure, then sandbox desktop enumeration failure; both precede GUI assertions
and are retained as environment evidence. No production/test workaround or
whole-runtime/compositor-health claim was added. No test module was added or
retired, and no task branch or worktree required cleanup.

GUI-D1 source findings: `1fe32b3` introduced the HDR-only shadow suppression;
the current selectors still win over later base rules by specificity. SDR
retains black elevation shadows, not a light shadow token. Mica makes the
WebView controller/page background transparent even though the dropdown surface
is opaque. The gallery's old normal/opaque isolation surfaces now both resolve
to the same opaque dark background, so those labels no longer distinguish
surface alpha; its shadowless comparison remains useful, but its elevation-8
differs from the production dropdown's elevation-16. No runtime or test
change is authorized by these observations. The user reports dropdown halos on
natively SDR displays but no halo when moving this computer's window from HDR
to SDR; the trigger and compositor cause remain unconfirmed. A controlled
fresh-launch HDR-off comparison should record Chromium's dynamic-range result,
native material, and shadow-on/off appearance before choosing a mitigation.
After the rail gate finished, the user disabled HDR globally and reported a
reliable distinction: dropdown shadows halo over cards, but not over bare Mica.
Dark cards use white at 5% alpha; their preceding solid-background declaration
is a fallback replaced by that translucent value, not an opaque underlay. This
narrows the next diagnostic to the card/shadow overlap: compare the production
shadow over bare Mica, the current card and a temporarily opaque card, plus a
shadowless control. It does not yet establish which renderer/compositor stage
causes the artifact, and no shadow or card fix was implemented.

### Documentation reconciliation pass (2026-09-09)

This closed maintenance register covers the accepted frontend decisions and
branch reconciliation only. It does not authorize product or test changes,
executor restructuring, new retry/cleanup mechanisms, or revival of compact-plan
memory prescriptions. Existing safety and measurement policy in `AGENTS.md` and
`DEFENSE.md` remains unchanged.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DOC-1 | Reconcile M1 lifecycle, fresh replanning, terminal actions, capacity/I/O presentation, trash information, and M2 deferrals across active subject docs; consolidate maintenance history and inspect defect sections. | Reviewed against service/executor behavior and accepted decisions; active-doc contradiction search, all 148 local links/anchors in 34 active Markdown files, history-preservation checks, docs-only scope, diff whitespace, and fresh adversarial review passed. BUGS module sections remain appropriate; no entry changes. | Verified for documentation commit |
| DOC-2 | Remove only the four superseded compact-plan commits from `milestone1` after DOC-1 is committed and verified, then open a draft PR from `milestone1-anthony`. | Verify exact divergence and remote tips, preserve the old tip in a recovery ref, reset only the named base branch, verify the resulting PR base/head/draft state and clean current worktree. Unexpected additional base-branch commits or unaccounted work stop this row for adjudication. | Pending |

Discovery is limited to active Markdown documentation and the service, workflow,
executor, projection, and test evidence needed to distinguish current behavior
from accepted targets. Findings outside these decisions are reported, not fixed.
No product suite rerun is claimed by a documentation-only check. DOC-2 depends
on DOC-1; no merge or implementation of remaining M1 rows is authorized here.

### Documentation and procedure pass (2026-09-10)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DOC-3 | Condense completed M1-4; expose product checkpoint status; register and expand M1-async; reconcile repository policy with the installed execute-task procedure and ratify lightweight checkpoint expansion. | Docs-only scope, all existing pending outcomes and alternate ordering preserved, 60 local links, exact skill installation, diff checks and adversarial scenario/design review passed; applied drafts cleaned. | Verified for documentation commit |

This user-authorized pass changes only `AGENTS.md`, this register, README,
CHANGELOG, HANDOFF and the installed
`C:\Users\Spectrum\.codex\skills\execute-task\SKILL.md`. The referenced
plan-work skill is read-only. No product, test, measurement authority, branch
reconciliation or pending checkpoint implementation is included. Diagnostic
artifacts use ignored `build/m1-procedures/`: `inputs/` holds original skill
content, `drafts/` holds reviewed replacements, and `evidence/` holds checks;
remove applied drafts at closure and retain the original and verification
receipt. The skill is outside repository Git history; verify its separate
installation and record that distinction. Existing hard-wall stops still apply.

### Product delivery register

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification | Status |
| --- | --- | --- | --- |
| M1-4 | Process-live blank task creation, navigation and explicit closure through existing lifecycle owners, with generation-aware callback containment. | Delivered in `ab453e1`; ordinary/headed checks and adversarial review passed. Active contracts are in BRIDGE and INTERFACES; concise delivery record below. | Complete |
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Complete |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Pending |
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Before M1-8, use the existing failure-policy/Stop and settlement paths; verify direct and wrapped capacity failures, ordinary I/O distinction, current-effect/recording truth, later work left unrun, terminal projection, and unchanged sharing-violation retries. Run executor plus core/workflow/interface consumers and the retained settlement oracle. No general I/O taxonomy or settlement restructuring. | Pending |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | Pending |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


## Checkpoint expansion and scope decisions

Use this lightweight expansion before each pending checkpoint, drawing on
`plan-work` without duplicating its full template. AGENTS owns the boundaries;
`execute-task` supplies the decision, waiting and recovery procedure. These
requirements remain usable without either personal skill installed.

1. Start from the accepted outcome and current repository revision. Trace the
   owners, state/effect transitions, direct consumers and harness dependencies;
   include helpers outside the initially selected directory. Record the finite
   corpus, relevant observations and remaining uncertainty.
2. Name the finite production, test and documentation population, current
   owners/seams, one acceptance gate and atomic commit boundary. State preserved
   guarantees, excluded/archived clauses and dependencies. Add only the detail
   needed to implement and review that outcome; findings do not silently become
   scope.
3. Probe likely regressions during design: lost guarantees, false states,
   unauthorized/duplicate effects and newly unbounded work. Tie each concrete
   risk to a reached seam and named verification. Record baseline evidence;
   red tests indicate a question, green tests do not prove absence of defects.
   Implementation validates this map rather than starting a broad discovery pass.
4. Require final adversarial review of source, tests, documentation and evidence
   at the checkpoint gate. Completion requires the gate and preserved baseline,
   not a favorable test count. After delivery, replace detailed working/recovery
   notes with what happened, what did not, and commit/contract/evidence pointers.

One next-checkpoint design lane may begin during the current checkpoint's final
product implementation and continue through testing, verification and review.
It is read-only toward product and test sources; serialize shared plan edits.
Record the inspected revision, then compare affected seams against the final
integrated predecessor before implementation. Refresh only changed assumptions,
consumers and probes. A current finding that changes those seams reopens that
part of the next design. Design readiness cannot waive predecessor completion,
implementation authorization or the user's pause.

Elaborating an accepted pending outcome within these boundaries is planning;
enlarging an active implementation population or its mechanism is a scope
decision. For the latter, suspend dependent edits and first complete the finite
dependency probe and one consolidated proposal. A narrow, understood extension
may obtain explicit adjudication in-turn using the available permitted input
mechanism; unanswered requests within the bounded procedure become a full stop.
Architectural or unresolved changes require a full stop with the design study.
Hard-wall stops take precedence immediately. Record approved scope before edits;
silence never expands it, and unchanged approvals are not requested again.

## M1-4 delivered

Delivered in `ab453e1` on `milestone1`: process-live blank task creation,
newest-first navigation, reinjection/recovery and explicit closure using the
existing lifecycle, observer and service owners. Terminal release retains the
task; busy close requests cancellation and removes the card only after
settlement and successful close. Failed close remains retryable. Existing
48-task admission and command/receipt/worker bounds remain enforced.

Generation-aware native callback containment prevents obsolete pywebview return
errors after reload while preserving command effects, recovery, current error
visibility and actual worker-exit accounting. This is not an atomic JavaScript
delivery fence; [BRIDGE](BRIDGE.md) and [INTERFACES](INTERFACES.md) own the active
contracts and limitation. Exact test consumers were migrated without filtering
stderr or relaxing their independent assertions.

No Setup/workflow content, durable task survival, domain retry/purge controls,
asynchronous command boundary or new timing/whole-runtime memory acceptance was
delivered in M1-4. Acceptance passed 4,862 ordinary
tests (four existing capability skips), 29 installed headed tests, all 12 import
contracts, documentation checks and independent adversarial review. Detailed
task history is in CHANGELOG; recovery chronology remains in Git history.

## M1-async delivered

Native create/start/release/close now separate admission from bounded completion
through the existing document channel. Ordinary/custom dispatch stays
synchronous. Task/session owners still execute and recover effects; reload
retires delivery without canceling admitted work. One shared 64-exchange budget
retains both actual worker exits and both delivery phases before reuse.
Completions are capped at 65,536 UTF-8 bytes, with a bounded FIFO, readiness
priority and appearance fairness. Browser correlation distinguishes host and
page generations, bounds early delivery, and uses existing recovery after
uncertainty. The atomic native final-epoch/send guard remains intact.

No generic scheduler, cancellation framework, durable command history,
whole-runtime resource certification, retired reservation/lease recipe or
M1-5 location behavior was delivered. Direct-response limits and all M1-4
effect, recovery and lifecycle guarantees remain active. The user-approved
README status update and logging startup-fixture migration are included.

M1-async-G covers the declared transition matrix, four command projections,
replay/timeout/reload, two-worker custody, first-excess population/size refusal,
post-effect delivery failure, saturation cleanup and shutdown recovery. Its
focused, neighborhood, ordinary, installed headed, import and documentation
checks accompany fresh adversarial source/evidence review. BRIDGE and
INTERFACES own the implemented contracts. The checkpoint is delivered by
`feat(web): add bounded asynchronous command completion` on `milestone1`
from `74aa6b7`; Git history identifies the atomic commit.

The preimplementation twelve-selector baseline and pinned runtime/source
receipt remain in `build/m1-async-design/evidence/`. The finite accepted plan,
replay inputs, transition matrix, per-run candidate hashes and raw closure
results remain in ignored `build/m1-async/inputs/` and `evidence/`.
HANDOFF records the final counts and immediate next work. These functional
checks do not change protected measurement authority or close release gates.

## M1-5 delivered

Delivered in `e19ed9d` on `milestone1` after M1-async. Fresh picker-backed
plan starts and inventory/integrity share typed location admission. Inputs
are literal and bounded; current volume identity, remount/clone resolution,
no-follow admission and existing point-of-use re-probes remain effective.
Remembered sources, targets and active pairs derive from durable sync activity,
each limited to five identity-deduplicated results. Remembered hints grant no
authority, and merely selecting or admitting a location writes no recent record.

Task refusal creates no delivery/session effect; equal replay performs no new
native admission. Two introduced service regressions were corrected before
delivery: exception-context retention and oversized input entering task custody.
Preimplementation probes were refreshed on integrated `675181a` before coding.
Closure passed 680 focused, 2,697 neighborhood and 4,912 ordinary tests (four
existing privilege skips), all 29 installed WebView2 tests, twelve import
contracts, documentation checks and independent adversarial review.

No Setup widgets, frozen options, Plan-again UI, schema/index changes, domain
policy changes or new resource certification were delivered. Retired DTO,
reservation and command-count recipes were not revived. Raw evidence remains
under `build/m1-5/evidence/`; later checkpoints implement the remaining user
outcomes through their own accepted gates.

## M1-6 delivery

M1-6 delivers backend-canonical frozen Setup with typed, picker and run-derived
recent folders/pairs; task-local options; standalone inventory; serial
best-effort pair creation; and fresh-identity Plan again in a new task.
Existing task/session owners attach the first session to a blank task and
preserve stable replay, recovery, close and admission bounds. Picker ambiguity
uses the user-approved purpose-bound continuation within the existing slot
population; an explicit current mount is required before Start.

Whole-gesture revisions prevent stale edits from restoring folder authority.
Form and batch starts exclude one another; uncertainty retains the same command
for retry. Per-task readback restores frozen inputs, and plan readiness requires
an actual artifact. Global defaults remain unchanged.

The same checkpoint condenses M1-5's delivered history and records the substantive
transparent-host rendering issue in BUGS without changing its header/policy.
Its cause remains unconfirmed and investigation is deferred indefinitely.
Changes to native Mica/material or global settings, durable tasks, M1-7
review/execution, inventory projections and new resource certification remain
excluded. Retired
command-count, reservation and aggregate-owner-graph recipes remain retired.

M1-6-G verification: 1027 passed, 2 deselected in 28.13s; neighborhood
2731 passed, 2249 deselected in 113.29s (0:01:53); ordinary 4946 passed, 4 skipped, 30 deselected in 212.33s (0:03:32);
installed headed 30 passed, 4950 deselected in 150.10s (0:02:30); all 12 import contracts.
The four ordinary skips are unchanged core/tool symlink cases lacking Windows
privilege (WinError 1314); no M1-6 or bridge gate was skipped. This checkpoint is
not release-wide or compositor-health acceptance. Final independent adversarial
review and documentation/hash checks passed before its atomic commit.

Delivery is one `feat(web): deliver frozen task setup and location flows` commit
on `milestone1`, based on `b98dce4`. The accepted study is retained in
[the archive](obsolete/M1_6_SETUP.md). Exact commands, candidate hashes, raw
results, review dispositions and screenshots are in ignored `build/m1-6/`;
successful gate directories are `focused-final05`, `neighborhood-final04`, `ordinary-final04`, `headed-final03`, `imports-final02`.
No test was retired and no recovery branch or worktree was created.

## Investigation and regression map

The current service rolls `committing` back only when admission fails;
post-admission preflight refusal remains committed. `run_plan` saves a plan
with its review-preflight verdict even when that verdict is negative; a typed
plan-admission limit instead saves no artifact. Existing preflight tests pin
the exact capacity boundary, fresh-world drift, and refusal without plan or
selection mutation. Existing core/planner tests pin operation identities,
selection digests, and dependency closure. Preserve these behavioral witnesses
when implementing fresh Plan again; a digest is not a filesystem snapshot.

The executor already projects generic I/O reasons and accepts `Stop` after
ordinary failure settlement, but its default policy continues non-sharing
failures. M1-8-capacity is a separate reviewable behavior commit before its
frontend consumer. Verify classification through the real error wrapping path,
post-effect and recording outcomes, and the later-operation stop sweep in the
executor runtime/settlement tests, then core/workflow/interface consumers.
Run the ordinary suite and unchanged retained oracle; final review must reject
any new settlement mechanism or capacity label that masks an unrelated failure.
Update EXECUTOR, FEATURES, DESKTOP_UI, and the register with the implemented
boundary and evidence before `feat(executor): stop on recognized capacity failure`.

For test cleanup, retire only unimplemented UI retry/reopening/cleanup promises
from future acceptance lists. Keep direct-service artifact replacement,
admission rollback, protocol replay, close recovery, automatic operation/read
retry, and pause/resume tests. They protect different behavior. Add terminal
action-availability witnesses when each surface activates, including degraded
completion, abnormal termination, and first manual verification. Add trash
location-only and evidence-backed count cases without requiring a full trash
inventory. Green existing tests cannot prove these new frontend outcomes; red
tests justify removal only when their exact retired product promise is named.

All remaining rows are pending product work. The baseline is the implemented
public/CLI, schema/event, authority, and settlement behavior recorded by the
closed reduction registers; those guarantees remain protected. The future
capacity checkpoint changes only the explicitly accepted failure classification
and later-operation admission policy. No implementation recipe from the discarded
compact-plan branch is an additional prerequisite. Product changes follow the
finite rows above, owning subject docs, and AGENTS/DEFENSE stop rules.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses, and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps the normal review experience with visible issues. Canceled or
abnormally terminated sessions retain terminal truth without resume, domain
retry, or session cleanup. Live pause/resume remains separate. Busy task close
requests immediate best-effort cancellation and keeps the card until settlement
and resource release permit closure; close never implies trash purge. Forced
process exit provides no durable task/resume guarantee.

Capacity refusal before execution (including queued wakeup) retains the task
without execution, automatic retry, or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again, and requires fresh review. It
never copies selection/authorization or changes the old artifact. Disk space
freed by removing source/target entries is accounted for by that fresh scan,
not by assuming that a prior selection digest binds the changed filesystem.

Recognized execution-time disk-capacity failure is the narrow planned addition
above; the current default failure policy continues past non-sharing failures.
Generic I/O already has a typed reason and needs ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence and display placement is
open. No filesystem inventory or purge is added to populate that information.

Location admission is workflow-owned and reused by typed, picker, and recent Setup/inventory inputs. A remembered location is not authorization; every consumer retains its point-of-use re-probe. Setup freezes its semantic plan options in a backend-derived snapshot and never writes global defaults or makes browser text/filter normalization authority.

Plan review must preserve operation, selection, scope, and fresh-preflight truth across view gestures. New views use canonical path-key order; filename, raw size, and raw mtime sorting in either direction and reset to canonical order are accepted M1 behavior. Sorting is process-live view state only and cannot alter selection, commitment, operation/dependency order, risk/counts, or action scope. It orders complete siblings before windowing and preserves node identity/hierarchy. Its exact protocol, validation, and scale evidence belong to BRIDGE and PRESENTATION.

Execution, inventory, and post-copy overlays stay distinct from each other and from ledger-derived state. A zero-byte activity that ran is never presented as unrun. Inventory warnings stay outside path/action scope and publication is complete or retains the prior complete generation. Baseline, verify, and rebaseline remain distinct operations. Rebaseline requires acknowledgement, includes eligible selected null-evidence files, replaces/creates evidence after a fresh hash, clears verification freshness, and does not become compare-and-accept. Manual exact post-copy verification uses an atomic handoff classification, works only on a ready subset, preserves original execution truth, and reports ineligible outcomes truthfully.

Release remains an accepted outcome. [INTERFACES.md](INTERFACES.md#sh-g-release-criteria) owns the open SH-G-15 scoped cold-start and repeated/long-workload resource policy. It has no numeric budget or acceptance artifact yet; runtime request/population bounds and the separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status must describe shipped behavior.
Map every active DESKTOP_UI acceptance item to its subject check or an explicitly
approved deferral; an omitted item or copied unmapped checklist is not closure.
BR-G-44: from a clean checkout, run the complete suite including ordinary-default
exclusions, lint-imports and diff checks. All test_br_g cases must be collected
and pass without skip/xfail on Windows; narrow selections do not substitute for
release evidence. TESTS owns collection commands and routing. These requirements
remain open release obligations, not an assertion that this checkpoint delivery
performed a product release run.

## Resumption

M1-4, M1-async (`675181a`), M1-5 (`e19ed9d`), GUI-1 (`b98dce4`) and M1-6
are delivered on `milestone1`. Pause before M1-7. Its expansion and implementation require a new
user instruction. No halo workaround, push or PR is part of this delivery.
HANDOFF owns current operational context; AGENTS owns containment boundaries.
