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
are active, including plan/inventory starts and Plan again. M1-7 delivers bounded
Plan review, selection, sorting and reviewed execution admission. Finish execution/
inventory projections, integrity controls and first manual post-copy verification,
then release closure; those remain unrealized frontend outcomes. The history page, global-settings mutation
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

### Completed GUI and documentation work

Completed records are condensed here; CHANGELOG and Git history through
`7e94598` retain individual deliveries, studies, verification and exact diffs.
Active behavior belongs to the linked subject owners, not old implementation
populations or repeated test counts.

| Closed IDs | Delivered result / owner |
| --- | --- |
| GUI-1, GUI-S1–S3 | Task navigation, frozen Setup controls and Settings/About shell; independent rail/work scrolling and preserved task drafts. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-S4–S12, GUI-R1–R2 | Origin-owned batch receipts, queued removal and settled-result clearing; compact tables with stable header/body gutters; native CSS scrollbar approximation; explicit smoke-only Ready witness; Fluent control and Setup refinements. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-S13–S21 | Translucent Fluent control fills and authored 1.2px boundaries; keyboard/pointer textbox focus; pinned checkbox glyph; per-pair frozen options; sync-only batch projection. Keyboard, forced-color, exact retry and admission guarantees remain. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-I1–I3 | Pinned local Fluent icon catalog, provenance, offline generation/checking and maintenance workflow. [TOOLS](TOOLS.md). |
| GUI-D1–D7 | Shadow/disabled-label diagnostics and batch-housing study; M2 records for native overlay scrollbars, verify-only batching and persistent presets. [BUGS](BUGS.md#desktop-material-composition), [DESKTOP_UI](DESKTOP_UI.md), [M2_PROPOSAL](M2_PROPOSAL.md). |
| AI-1–AI-2 | Execution/containment guidance and instruction condensation; component rules routed to their owners. AGENTS remains execution authority; personal-skill edits are separately recorded in CHANGELOG. |
| DOC-1, DOC-3 | Accepted frontend/M2 decisions reconciled across subject docs; completed history condensed and checkpoint expansion procedure established. Documentation verification did not claim product acceptance. |

No rendering fix was established for the WCG shadow halo or intermittent
disabled-label blur. Mica remains required; no workaround or compositor-health
release gate was added. BUGS and DESKTOP_UI retain investigation boundaries and
reopen evidence. Recent availability remains observation, never admission.
The existing 48-pair bound, serial best effort, per-row options and exact
uncertain retry remain active; clearing receipts does not close tasks.

DOC-2 remains **pending, outside this M1-7 task**: the historical branch
reconciliation proposal was to remove exactly four superseded compact-plan
commits from `milestone1`, preserve the old tip and open a draft PR from
`milestone1-anthony`. It requires fresh divergence/remote-tip and work-preservation
verification before action; unexpected commits or unaccounted work require
adjudication. This condensation neither executes nor marks that proposal done.

### Product delivery register

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification | Status |
| --- | --- | --- | --- |
| M1-4 | Process-live blank task creation, navigation and explicit closure through existing lifecycle owners, with generation-aware callback containment. | Delivered in `ab453e1`; ordinary/headed checks and adversarial review passed. Active contracts are in BRIDGE and INTERFACES; concise delivery record below. | Complete |
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Complete |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Complete |
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

## M1-7 implementation and closure

### Post-delivery ablation study (2026-09-16)

This discovery-only pass studies `ae3daf6^..5986c57`, starting from a clean
`5986c57` checkout. It authorizes no production/test changes, new acceptance
criteria, M1-8 work, push or PR. Work proceeds from diff/structure inventories
to selected behavioral seams and direct consumers, not exhaustive line review.
The original report, committed in `dbeb7a5`, distinguishes observed redundancy,
bounded experimental support and design proposals. Its successor
[implementation plan](M1_7_ABLATION_STUDY.md) retains that evidence and candidate
register; neither discovery nor plan preparation authorizes implementation.

| ID | Accepted study outcome | Named verification | Status |
| --- | --- | --- | --- |
| AB7-1 | Attribute checkpoint growth and map product/test/evidence owners. | Inclusive Git/AST census: 77 files, 22,273 additions; 72.3% of added lines in tests/helpers/evidence. | Complete |
| AB7-2 | Identify bounded architecture, logic and test ablations while preserving behavioral guarantees. | Twelve source/consumer-backed candidates with retained obligations and falsifying gates; E1 33/33 focused control/ablation passes, E2 5/5, and both deliberately seeded faults detected. | Complete |
| AB7-3 | Independently review with one Claude Opus 5 xhigh session and synthesize useful findings. | Two invocations of the same session, zero Claude subagents; targeted challenge accepted, corrected claims and useful recommendations synthesized. | Complete |
| AB7-4 | Deliver a ranked report and preserve exact review provenance. | Adversarial synthesis, documentation/link/diff checks, preserved review-start state, unchanged product/test tree; disposable copies removed. | Complete |

Finite corpus: the 77 changed files, their immediate symbol consumers and
owning active documents; earlier reduction dispositions are contextual evidence.
Stop discovery and report if supported hard-wall/data-loss/false-success
evidence is established; do not fix findings during this study. Other findings
are recommendations only. No benchmark rerun or performance claim is authorized
by static inspection. Evidence lives in ignored `build/m1-7-ablation/`: named
UTF-8 prompts/scripts, structural inventories, original-state receipt and raw
review responses. Preserve these for report provenance; disposable fixtures,
if needed, must be separately identified and removed after verification.

Both E1/E2 experiments used disposable copies and retained their exact plans,
patches and control/ablation/fault logs. E2's cohort-only patch is not suitable
for direct integration: any implementation must separate synthetic controls
from live-generator coverage. No full benchmark rerun, product/test edit or
commit was performed during discovery. The subsequent user-requested snapshot
commit is `dbeb7a5`; it preserves the original review reconciliation and usage.

### Post-delivery ablation implementation (2026-09-16 – 2026-09-17)

The user first requested a reviewed subtractive plan, then authorized execution
on 2026-09-17 after baseline and working-set preparation.
[M1_7_ABLATION_STUDY.md](M1_7_ABLATION_STUDY.md#checkpoint-register) is this
register's detailed maintenance subregister: R7-1–R7-8 and R7-G are the finite
accepted completion denominator; implementation rows remain pending at startup.
Its candidate register preserves A1–A12 and explicitly separates selected
portions from deferred work. This does not reopen M1-7 product acceptance or
authorize M1-8, deferred redesigns, push or PR.

The selected scope is synthetic/live fixture separation, canonical-comparator
and unused replacement-route removal, independent-validator receipt checks,
producer publication bookkeeping, browser admission replay, lazy ID resolver
work and the tracer's mirrored test oracle. A5/A6/A7/A8/A10 remain deferred;
A4 read retries, broader A12 safety reuse and A11 tracer retirement are excluded.
A7 may be ratified later in ARCHITECTURE/PRESENTATION and this register.

Every row names its bounded behavioral population, protected guarantees,
product seams, detector-quality controls and atomic commit gate. Existing
product behavior is the baseline; green rewritten tests alone cannot prove
detector quality. Log/report latent product defects without fixing them in this
refactor. Introduced regressions remain checkpoint obligations; AGENTS stops
and DEFENSE consequence/evidence policy apply. The user-approved measurement
policy uses affected local Tier 1 checks before checkpoint commits and one full
current-source measurement suite at R7-G. Local checks do not renew full scale
acceptance; frozen budgets and historical artifacts remain unchanged.
PRESENTATION owns this scoped rerun policy; the subregister records exact gates.

### Delivered product scope and P9 closure

The user authorized M1-7, the closing-race correction, snapshot-bound destructive
confirmation, aggregate/breakdown facts, an inert gallery preview, and confirmed
Plan-again/control consumer corrections. Stop after this checkpoint for recap and
GUI tweaks. No M1-8, DOC-2, push or PR is included. Original study revision:
`7e94598`; documentation cleanup is integrated in `a1d78ca` and `40ca76f`.

### Implemented behavior and ownership

- Workflows derive immutable Plan projections, raw sibling-sort facts and selected
  operation/risk/space totals. Selection preserves dependency closure, operation
  ordering and immutable artifact identity. Filters and windows do not redefine
  scope. The browser retains only its bounded 1–256-row window.
- TaskRegistry owns task delivery and the current session; the existing service
  and lifecycle own reviewed identity, selection commitment and admission.
  Same-task Execute requires the released planning session. Failed admission
  restores editable review; admitted execution remains committed even when fresh
  preflight refuses before effects. Original Plan replay cannot become current.
- Execute captures task/request/selection revision. Every selected destructive
  scope opens the production Fluent smoke modal. Cancel submits nothing; Confirm
  submits the same snapshot for backend validation, commitment and admission in
  one command. Exact uncertain retries retain their intent and fence selection
  and Close. Modal/background focus, pointer, wheel, Escape, animation exit and
  reduced-motion behavior are verified. The gallery starts closed and previews
  the same dialog without execution effects.
- Terminal-session release retains a task; explicit Close retires it. Close and
  follow-up admission have atomic ordering and claim revalidation after waits,
  without holding owner locks over domain I/O. Exact replay survives source-task
  retirement. Terminal records retain the exact plan/inventory/execution kind and
  capability contract.
- Current-session StateChanged events drive execution controls. A later event or
  terminal record prevents an older command reply from regressing presentation;
  Plan refresh preserves live state. Hidden Plan controls stay hidden. Plan again
  creates a fresh task under the existing 48-task limit; release does not free a
  task slot. Selecting a task after a Plan-load error performs the advertised
  guarded retry, preserving cached and in-flight views.

Behavior owners: [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md).
[BUGS](BUGS.md) records substantive corrected mechanisms. Core source remains the
authority for exact contract shapes; no dispatcher/module/db effect-policy change
was needed.

### Finite implementation and regression boundary

Production owners are core execution contracts; workflow tree/projection/selection helpers; existing
interface service/lifecycle/task-port owners; web commands, task delivery and
Plan review; and packaged app/bridge/Plan/modal assets. Tests cover those owners
and their current setup/task-shell/gallery, event, wheel, replay/uncertainty,
close-ordering and quantitative consumers. The user-approved investigation
compared Setup, Task 47→48 and post-release Task 48→49 across button, eligibility,
attempt, bridge, host validation, registry, response and refresh boundaries.
Its bounded opt-in test trace preserves installed asset bytes and is diagnostic
only; clean installed runs establish acceptance. Raw findings are retained in
`build/m1-7/evidence/plan-again-findings.md` and its referenced records.

Regression guarantees include exact review/session identity, current-request
binding, monotonic selection revision, stale callback rejection, single admission,
Close/replay ordering, truthful committed-but-unrun status, inert hostile display
text, bounded ingress/windows and authoritative state ordering. There is no
selection reopening, terminal subset retry, execution-result overlay, inventory
projection, capacity-policy change or global-settings expansion. Archived bridge
recipes remain provenance, not renewed representation or reservation requirements.

### Acceptance evidence and integration

The authorized P9 full run on the unchanged `3c3bbbc` candidate passed all
**35 fixed metrics**, after **15 readiness children / 35 untimed cases**, with
**175 fresh measurement children / 775 samples**. No retries, budget changes or
product changes were made during the run. Independent terminal, collection,
identity and physical-byte verification passed. This closes the quantitative
part of **M1-7-G**, alongside functional/consumer, ordinary, import, installed
headed, documentation and final integration checks.

| Evidence | Result |
| --- | --- |
| Six changed sorts | P95 0.756–1.109 s; largest maximum 1.192 s, within 1.5/3 s. |
| Review construction/staging memory | 280,768,512 bytes (267.762 MiB), within 320 MiB. This is not whole-app or paused-execution memory. |
| Confirmed execution admission receipt | P95 54.6 ms / maximum 55.4 ms, within 100/250 ms; receipt remains after admission. |
| Prior unchanged candidate verification | 5,157 ordinary tests, 259 checkpoint/resume/post-execution tests, 12 import contracts and installed Plan GUI passed at P8. |
| Final closure verification | 55 artifact/scale checks and 5,158 ordinary tests pass (four platform skips; 30 headed tests deselected). Documentation and reconstructed endpoint reviews pass. Clean committed-source, supplemental core and exact product/test accounting pass. |

Raw children, incremental indexes, readiness, authority, terminal measurements,
independent audit and before/after identities are retained under
`build/m1-7/evidence/p9-full-20260916/`. The current compact authority and
measurement artifacts are published at their contract-owned paths under
`tests/interfaces/web/`; previous bytes remain in Git and the evidence directory.
Authority SHA-256: `dcea9df79599739e07c8652b9a16eca6b7e88e81de31594c30bd74ec309797b7`.
Terminal artifact SHA-256: `e5718367c4f386e5845b93b7de484176228504b8382d0f6d5c0a1317d862665d`.
The fixed compact contract, historical legacy evidence and all budgets remain
unchanged. Legacy compatibility remains confined to the historical evidence reader.

The historical contract names 42 source, 38 installed and 14 runtime files.
P8's additional `namisync/core/execution.py` is bound separately by equal source,
installed and wheel-member SHA-256
`76350ca8aebb23959c47a502cb0767cfb569adf7cb45fdc1f80399b7df8ffbb9`,
checked before and after the full run and again at integration. The independent
audit verifies both this supplemental binding and the contract-owned population.
Collection receipt hashes are verified; per-child invocation/log hashes are not
fields of the full-run collection contract and are not claimed.

The reviewed closure series reconstructs six dependency-ordered outcomes from the
recovery history: reviewed Plan delivery and measurement readiness; covered
windows and compact Plan scale; reduced review/selection retention; prepared
selection digests; shared validated execution structure; and accepted evidence
with closure documentation. Intermediate trees preserve the historical failed
measurements honestly; only the complete verified series is merge-ready.
The original commits, including `cf5a00b` and `30d35f3`, are not amended or
integrated as WIP objects. Final product/test accounting against `3c3bbbc`
permits only the two newly accepted artifact files. Recovery history is preserved
by the `codex/m1-7-recovery-20260916` archive tag and the verified
`build/m1-7/evidence/p9-full-20260916/m1-7-recovery.bundle`. The integration receipt
in that directory records exact reconstructed and recovery commit identities,
tree equality, merge and branch cleanup. No original commit was amended.

The earlier confirmed hidden-control, state-ordering and Plan-retry defects are
closed at their existing owners; BUGS retains their mechanisms and witnesses.
Historical working records, failed runs and the bounded admission breakdown
remain in Git/evidence rather than this active register. Shared execution
structure extends one immutable index's paused lifetime; ARCHITECTURE owns its
complete retention account. No dispatcher policy or receipt guarantee changed.

Stop on `milestone1` after verified integration for the requested recap and GUI
review. M1-8, DOC-2, push, PR and release gates remain outside this task.

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

M1-4, M1-async (`675181a`), M1-5 (`e19ed9d`), GUI-1 (`b98dce4`), M1-6
and M1-7 are delivered on `milestone1`. Stop for the requested recap and GUI
review. HANDOFF owns current operational context; AGENTS
owns containment. No later checkpoint, halo workaround, push or PR is authorized.
