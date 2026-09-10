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

The process-live desktop task shell is active. Finish shared location admission
and frozen Setup, reviewed execution, execution/inventory projections, integrity
controls and first manual post-copy verification, then release closure. These
remain unrealized frontend outcomes. The history page, global-settings mutation
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
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G below covers delivery races, worker custody, saturation cleanup, direct commands, shutdown/recovery and installed headed evidence. | Pending |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Pending |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Pending |
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
delivered. M1-5 and M1-async remain pending. Acceptance passed 4,862 ordinary
tests (four existing capability skips), 29 installed headed tests, all 12 import
contracts, documentation checks and independent adversarial review. Detailed
task history is in CHANGELOG; recovery chronology remains in Git history.

## M1-async bounded checkpoint detail

**Outcome and placement.** Separate bounded command admission from completion
for concrete small M1 actions, while reusing task/session effect owners.
This distinct checkpoint is registered after completed M1-4, by default before
M1-5. The user's permitted alternative remains after M1-5 but before M1-6.
Its status is Pending: this documentation pass registers and expands the plan,
not its implementation authority. M1-5 requires no new browser command; its
workflow admission remains behind existing start-plan semantics. M1-6 and M1-7
can later use this boundary only for explicitly admitted small-result actions.

**Finite implementation population.** Production: `interfaces/web/bridge.py`,
`commands.py`, `host.py`, `document_channel.py`, and `assets/bridge.js` under
`namisync/`. Keep exported browser wrapper APIs stable. No workflow, core,
dispatcher, service, lifecycle, observer, persistence, drain, task-view or app
content changes are planned. The boundary implementation stays in the existing
bridge component; it introduces no new directory or general scheduler.

Tests: `tests/interfaces/web/test_bridge.py`, `test_commands.py`,
`test_document_channel.py`, `test_host.py`, `test_frontend_static.py`,
`test_transport.py`, `test_task_shell_headed.py`, `_task_shell_headed_child.py`,
`test_transport_headed.py`, `_transport_gate_child.py`,
`test_browser_event_v5_consumers.py`, `test_cosmetic_channel.py`,
`_startup_test_support.py`, `_frontend_test_support.py`; existing JavaScript
consumers `tests/assets/bootstrap_test_bridge.js`,
`bootstrap_test_bridge_probe.mjs`, `app_startup_probe.mjs`,
`task_shell_probe.mjs`, `drain_manager_probe.mjs`, `cosmetic_bridge_probe.mjs`,
`bridge_timeout_probe.mjs`, `bridge_interactive_probe.mjs`,
and `tests/assets/transport_gate/transport.js`, `off_origin.js`,
`off_origin_start.js`. These are mechanism and
exact consumer migrations only; no test module retirement is planned.
Documentation: this register, BRIDGE, INTERFACES, ARCHITECTURE, DEFENSE,
CHANGELOG and HANDOFF. Existing service/lifecycle, slots and dispatcher tests
are regression consumers. Production `appearance.py`, `assets/app.js` and
`assets/theme.js` are unchanged consumers, not additional edit scope.
Unchanged harness consumers also include `test_native_host_gates.py`,
`_native_gate_child.py`, `test_materials.py`, `test_bridge_event_benchmark.py`,
`_bridge_event_benchmark_child.py`, `test_component_gallery_headed.py` and
`_component_gallery_child.py` (under `tests/interfaces/web/`),
`tests/assets/component_gallery/gallery.js`,
`tests/assets/native_host_gate/probe.js`, `tests/bridge_event_benchmark.py` and
`tests/assets/bridge_event_benchmark/benchmark.js`. Run their ordinary or headed
contract checks as appropriate. Ordinary verification retains
`test_bridge_transport_custody_live.py::test_current_source_transport_custody_stays_within_frozen_ceiling`;
do not rerun/retarget calibration, holdout or the timing diagnostic, or reopen
its deferred v5 migration. Any additional edit dependency must be adjudicated
before implementation rather than silently enlarging this population.

**Owners and work classes.** BridgeDispatcher still validates the complete
65,536-byte envelope, exact payload, trust and readiness before admission. An
adapter-local exchange invokes the existing CommandSpec handler once; it owns
delivery bookkeeping, never task/session association, mutation receipts,
filesystem authority, compensation or domain cancellation. TaskLifecycle,
TaskRegistry and SessionObserver retain their existing distinct responsibilities.
Literal validated request data can be held by a running worker, within the
ingress bound; no resolved authority or live domain result is cached for replay.

`CommandSpec` owns the direct/async-small classification; the dispatcher must
not infer work classes from command-name switches. Existing/custom rows remain
direct unless explicitly classified. Perform validation and capture the admitted
readiness/document context before creating the command worker; invoke the
existing handler once with that context. That context supplies no new domain
authority and does not replace downstream point-of-use checks. `host.py` binds
the dispatcher to the existing DocumentChannel after channel construction and
retires that delivery lane at the existing before-load/close seams. Preserve
readiness setup order and retire/wake delivery before waiting for workers;
appearance-channel teardown must not strand their completions.

Async admission is confined to `_dispatch_native` for explicitly classified
rows. `BridgeDispatcher.dispatch()` and `CommandSpec.invoke()` keep synchronous
full-envelope semantics for their existing direct/ordinary consumers. Custom
headed and diagnostic rows remain direct. The four packaged command wrappers
retain their exported Promise results while adopting admission/completion
delivery internally; unknown/custom `dispatchInteractive` calls stay direct.

Initially migrate only `create_task`, `start_plan`, `release_terminal_session`
and `close_task`: their current result fields are bounded opaque identities,
fixed dispositions and fixed errors. Keep bootstrap, `next_events`, list reads,
picker and cosmetic rows direct. In particular, a supported long picker display
path cannot be assumed to fit a 65,536-byte document message. Drain keeps its
existing 25-second server wait, 30-second browser deadline and 8 MiB response
bound. M1-6 Setup/inventory/Plan-again and M1-7 selection/execution admission
choose a class at activation from their full result shape and recovery needs;
plan windows, large projections and event traffic do not migrate by default.

**Admission and custody.** Extend the existing 64-slot bridge custody rather
than adding a second admission budget. An async exchange retains its original
native worker/receipt charge and additionally owns at most one command worker
and one completion. Start that worker during the admitted transfer; there is
no pending work queue. Worker-start refusal invokes no handler. Once accepted,
the worker settles through the existing handler despite reload or window close.
An exchange is reaped only after the original native worker has exited and its
admission return is acknowledged/retired, the command worker has actually
exited, and completion delivery is acknowledged/retired. Result production or
browser timeout is not worker death. There may be two worker owners during
transfer; the claim is 64 admitted exchanges and at most 64 new command workers,
not a new whole-runtime thread or memory certification.

Saturation refuses before creating a command worker. Cleanup acknowledgment
must bypass ordinary admission, origin/readiness and saturation like current
native response cleanup: it is an exact exchange/token/phase match and grants
no command authority. Never introduce an OPEN command whose acknowledgment
itself requires one of the 64 occupied slots. Native admission receipt and
completion receipt are distinct phases, not new effect-replay authorities.

**Completion and document generations.** The browser registers an entry using
its already minted request id before dispatch. Its pending table is capped at
64 attempts, with at most one early completion per entry while the small native
admission return is pending. No unsolicited completion creates an entry. Validate
both phases and resolve only their exact matching generation/id. Preserve the
existing native response acknowledgment even after a caller's deadline; valid
late completion is cleanup-only. Validate admission/completion identities and
perform bounded cleanup acknowledgment before resolving a live result; uncertain
cleanup remains transport uncertainty. A deadline removes result authority and
frees that pending slot, without retaining a tombstone/history table. A valid
same-generation late completion may send only its host-issued exact token/phase
cleanup acknowledgment; it never creates an entry or adopts/resolves a result.
Host custody validates the match and malformed/unknown cleanup is inert. Timeouts
mean uncertain delivery, never that an admitted effect did not happen.
Replacement retires old browser pending work and host completion delivery
without canceling admitted handlers.

Use DocumentChannel for bounded current-document completion messages. Add a
command-delivery lane bounded by the same admitted exchanges, sharing its one
native post owner. Required readiness takes priority; command completions are
FIFO, with a pending replaceable appearance update serviced between command
posts so a stream of completions cannot starve appearance. Replacement/close
retires all old queued/in-flight completion posts before a new readiness
challenge can post. Do not hold a bridge/channel lock across native evaluation,
handler work or another component's callback. This is a finite delivery queue,
not another job queue or task-result store.

Snapshot each completion to bridge-safe primitive values before posting, with
the full document envelope bounded to 65,536 canonical UTF-8 bytes. A post-effect
encoding/size failure must report bounded delivery uncertainty and use the
existing command recovery route; it cannot assert a pre-effect refusal, undo
work or invoke the handler again. Encode that failure as a fixed bounded
completion before posting. Actual post failure retires only completion-delivery
custody; worker-death and native-admission custody still apply, while the browser
reaches its bounded timeout and existing recovery route. The small class requires exact
largest success/error envelope tests. Larger future result shapes stay direct.
The small admission return still uses pywebview, so M1-4 containment remains
necessary and no latency claim says that callback must beat a reload.

**Recovery and shutdown.** Create/start uncertainty uses existing same-command
receipts and list reconstruction; release/close uses retained task/session truth
and existing idempotent recovery. M1-5 fresh candidate probing must remain after
receipt lookup. The boundary adds no generic cancel API. Close rejects admission,
wakes existing drain waiters, retires completion publication, waits for both
worker owners within the existing bounded quiescence path, then performs service
shutdown. An unfinished worker leaves close retryable; do not close the service
under live command work or silently discard an accepted action.

**Design probes and regression surfaces.** The named source corpus is the five
production files above, current TaskLifecycle/TaskRegistry/SessionObserver,
service task admission, FolderSlotTable and the listed tests. Inspection found
the exact native-worker-plus-browser-receipt charge; DocumentChannel's one
required slot and readiness precedence; host before-load retirement; the
browser's pre-dispatch request-id minting; picker display retaining full path;
and the installed-wheel harness's direct native-response assumptions. These
findings drive the proposed shared charge, command lane, early registration,
picker exclusion and exact consumer migrations. They are design observations,
not proof of future implementation.

The preimplementation baseline retained eight existing finite selectors for
native receipt/death, saturation cleanup, preempted generation entry, document
replacement/readiness precedence, start replay before slot re-resolution, and
close with an admitted call. `build/m1-async-design/run-baseline.ps1` ran all
eight: **8 passed** (`baseline.txt`); pytest also reported that its existing
repository cache directory was not writable. This is functional baseline
evidence, not a measurement claim. No async production work preceded the probe.
Design artifacts stay under ignored
`build/m1-async-design/`, grouped by command; retain scripts and raw results,
replace only the same command's rerun output. Implementation must add the finite
new-mechanism transition matrix: immediate completion before admission return;
reload before worker start, during handler work, after result/before post,
after post/before acknowledgment and after acknowledgment; every migrated
command's lost delivery; shared-capacity first excess; acknowledgment under
saturation/trust loss; both worker exits; readiness and appearance under queued
completions; post-effect encoding/size/post failure; and close timeout/retry.

Regressions mean lost active guarantees, false states, unauthorized/duplicate
effects or newly unbounded work. Probe these surfaces in design before edits;
do not discover the baseline during implementation. A red test is an indicator,
not proof of regression, and green tests do not prove absence. New findings
follow AGENTS containment/stop rules and do not enlarge the denominator.

**Gate, atomic commit and archived dispositions.** M1-async-G is one gate:
all finite transition witnesses, unchanged M1-4 behavior, affected department
and ordinary checks, installed-wheel reload/shutdown evidence, import contracts,
matching docs and a fresh adversarial review must pass before
`feat(web): add bounded asynchronous command completion`. Required headed proof
cannot be deferred to a later test commit. A separately authorized independent
fix may use its own reviewed commit. Review must trace both delivery phases,
each work class, all retirement paths and actual worker death; reject duplicate
receipt owners, false refusal after effects, hidden queue growth or weakened
direct-response limits. No BR-G-45, whole-retained-graph target, phase reservation,
lease, durable command history, generic cancellation or archived 18-command
recipe is restored. All active task, response, safety and recovery guarantees
remain binding.

**Registration refresh (2026-09-10).** The design study at integrated revision
`22a0da1` followed native versus direct dispatch, CommandSpec invocation, host
channel construction/shutdown, appearance consumers, wrapper probes and their
parent tests across the whole test tree. It added the actual transport,
appearance, timeout and generic-interactive consumers above; diagnostic parent
and native probes remain unchanged checks. This avoids treating an imported
test-root validator as invisible scope. These are read-only design observations;
the retained eight-selector baseline is historical evidence, not a new test run.

Before implementation, refresh changed seams against the current revision and
run the eight named baseline selectors plus these `test_transport.py` nodes:
`test_required_node_start_plan_identity_and_timeout_contract`,
`test_task_close_crosses_production_dispatch_as_exact_echo`,
`test_terminal_session_release_crosses_dispatch_as_exact_echo`, and
`test_bridge_admission_ceiling_fails_fast_and_releases_capacity`. Record the
implementation base and installed Python/Node/pywebview/pythonnet versions;
refresh the pinned native return source-shape witness. These are local
compatibility receipts, not new measurement authority. Required new witnesses cover every listed
transition for the four migrated commands; direct ordinary/custom invocation
must still return its original full envelope. Verify the shared 64-entry first
excess before worker creation, both worker exits before slot reuse, the complete
65,536-byte completion boundary and its first excess, and every post-effect
encoding/post refusal as delivery uncertainty without repeated effects.
Use the focused modules above, then the TESTS commands for the
interfaces/dispatcher neighborhood, ordinary repository and full interface-
headed gate, plus import and documentation/diff checks. No skipped or
unclassified required async transition closes M1-async-G. Implement only after
the current pause is lifted; retain one feature commit with its tests/docs and
final adversarial review, not a feature followed by deferred acceptance work.

## M1-5 bounded checkpoint detail

**Outcome and acceptance gate.** M1-5-G is one checkpoint gate: Setup's
current picker-backed plan start and inventory use one workflow-owned location
candidate admission route, expose typed results, and can read bounded,
identity-based remembered locations. The gate closes only when the finite
transition checks below, affected-department and ordinary verification, source
tracing of preserved guarantees, matching documentation, and a fresh adversarial
review all pass. A green test run alone does not close it. M1-4 must be reviewed
and committed before M1-5 implementation begins; M1-async normally precedes
M1-5, with the permitted alternate order recorded above. The current delivery pauses
before M1-5 for the user's recap and GUI adjustments; this section is design
only and does not authorize starting its implementation during this delivery.

**Finite implementation population.** Production changes are confined to
`namisync/workflows/inventory.py`, `runtime.py`, and `__init__.py`,
`namisync/db/repositories.py`, and `namisync/interfaces/service.py`.
Workflow-owned candidate/result types stay with their actual owner; no core
contract, domain module, schema, settings store, dispatcher, task lifecycle,
or frontend content change is planned. The existing picker/slot/bridge path is
a consumer through service plan start, not a new owner of path policy.

The test population is `tests/test_inventory_workflow.py`,
`test_inventory_runtime.py`, `test_db_repositories.py`, `test_service.py`,
`test_bridge_service.py`, and their existing `tests/_inventory_fixtures.py`
and `tests/_service_fixtures.py` support. Existing
`tests/interfaces/web/test_slots.py` and `test_commands.py` are named consumer
regression checks. `tests/interfaces/web/test_transport.py` is also admitted for
its direct-service plan-start runtime fixture: the preimplementation consumer
trace found that it must model the new admission seam without weakening the
production service. No collected module is added or retired. Documentation is
limited to this register, `INVENTORY.md`, `WORKFLOWS.md`, `DATABASE.md`,
`INTERFACES.md`, `FEATURES.md`, `DESKTOP_UI.md`, `BRIDGE.md`, the README
current-state/phase summaries, and task-level `CHANGELOG.md`/`HANDOFF.md`.
Files in this population change only when necessary for the accepted outcome;
the population is not a cleanup checklist.

**Owners and seams.** `inventory.py` owns candidate parsing/admission,
`LocationBinding`, current mounted-volume resolution, and inventory/integrity
binding. Reuse its existing bounded resolver and no-follow root-chain authority;
typed parser/native refusal must not depend on parsing diagnostic strings.
`runtime.py` composes the native collaborators and read-only ledger access;
`service.py` exposes typed application results and integrates fresh plan starts.
`db/repositories.py` owns bounded SQL readback. Service task claims, command
receipts, observer ownership, and dispatcher admission remain with their M1-4
owners. Source/target overlap and canonical path checks remain effective.

Raw text is bounded before parsing/native work, treated literally, and never
expanded as shell, environment, URI, home, or current-directory syntax. Keep
long logical paths and the existing extended-length native boundary. Refuse
files without selecting their parents, redirected/placeholder chains, malformed
or unsupported namespaces, and remote locations with typed guidance. Preserve
existing local filesystem capability behavior; this checkpoint does not create
new optical/unknown-filesystem support or writable-media promises.

Native picker paths already flow through slots into service plan start. On a
fresh start, perform candidate admission after the command replay/claim boundary
and before workflow/session work. An equal replay must not probe again or create
another effect. Slot ids remain purpose-bound, nonconsuming and expiry-bounded;
pair lookup stays atomic and no slot lock spans native I/O. Typed and remembered
Setup widgets, picker-time feedback, and standalone-inventory picker controls
remain M1-6. Inventory/integrity and all scanner, preflight, executor, and verifier
point-of-use re-probes remain active; neither a candidate nor a remembered
identity authorizes later filesystem work.

**Remembered locations.** Implement the existing FEATURES outcome of at most
five recent sources, five targets, and five active pairings, derived only from
durable ledger run activity. Deduplicate by stable location/pair identity and
order by latest recorded run time with a deterministic identity tie-break.
Exclude soft-deleted mappings from the run-derived suggestions; do not discard historical
failed, canceled, degraded, unfinished, offline, or remounted locations.
Bound SQL result materialization before constructing presentation collections.
Typing, picking, probing, and mere candidate admission write no recent record.
Activation resolves the remembered identity afresh; a stored drive hint is
never presented as an authoritative current path. Missing/offline/ambiguous
results keep identity context and cannot become a successful admission.

**Design probes and regression definition.** Before production edits, inspect
the owners and consumer seams above, and exercise the exact selector corpus
recorded in the preimplementation receipt below for parser and native-path
boundaries; file, reparse, placeholder, and long-root behavior; offline, missing,
remounted and cloned volumes; queued re-resolution; service admission/replay;
slot purpose/expiry/eviction/concurrent pair resolution; and ledger run/mapping
provenance. These probes sample the declared regression surfaces; they do not
claim full-module runs of every file in the implementation population. Record
the commands and direct owner traces below before freezing implementation.
Diagnostic outputs, if needed, use ignored
`build/m1-5-design/` for disposable baseline output and `build/m1-5/` for
per-command implementation evidence; neither is measurement authority.

A regression is a lost existing guarantee, a false state/evidence claim, an
unauthorized effect, or newly unbounded work. A red test is a lead that requires
tracing the reached production seam and consequence; a green test does not
prove absence. Implementation validates the predeclared surfaces and diagnoses
failures; it does not initiate a new broad discovery pass. Required new witnesses
cover every refusal class, long-path acceptance, current remount and clone
selection, fresh activation/queue probes, all three five-entry boundaries and
ordering/provenance, and replay before candidate work. Run the database,
workflows, and interfaces neighborhood, ordinary repository suite, import
contracts, and `git diff --check`; retain M1-4 headed evidence unless a changed
production desktop path requires its witness to run again.

**Archived-clause dispositions and non-goals.** Archived candidate DTO shapes,
assessment/activation command counts, reservation/lease recipes, and aggregate
retained-graph byte targets are not implementation prerequisites. The active
literal-input, typed-refusal, fresh-identity, bounded-recent and purpose-bound
slot outcomes remain binding. Frozen Setup/options, browser normalization,
multi-pair task creation, inventory panes, fresh Plan-again UI, domain retries,
cleanup/purge controls, durable tasks, and new resource certification remain
outside M1-5. No archived clause is used to remove an active guarantee.

**Review, commit and stop rules.** Plan one coherent commit,
`feat(workflows): unify location admission and remembered locations`, after
M1-5-G passes. No separate database-only or unused-interface prerequisite commit
is needed. Any separately authorized bounded pre-existing fix uses its own
reviewed commit under AGENTS; it does not enlarge this gate. A fresh reviewer
must inspect the actual final diff, raw verification, parsing/TOCTOU, receipt
ordering, persisted identity provenance, bounds, and documentation, then confirm
any correction before commit. Apply AGENTS/DEFENSE hard-wall and numerical
unplanned-defect stops unchanged. Preserve blocked task-owned work under the
repository recovery procedure rather than committing an incomplete checkpoint.

**Preimplementation probe receipt (2026-09-10).** The finite baseline additionally
reads `tests/test_recorder_setup_and_move.py` and `test_recorder_sync.py` for
durable-run provenance; those modules are probe-only, not implementation scope.
`pwsh -NoProfile -File build/m1-5-design/run-baseline.ps1` records the exact
20-selector baseline and five-selector picker corpus: **44 passed** and
**17 passed**. Raw outputs are `build/m1-5-design/baseline.txt` and `picker.txt`.
The orchestrator repeated these once to retain reproducible evidence after the
initial design probe's temporary output was removed; no M1-5 production edit
preceded either run. This is functional baseline evidence, not performance or
resource acceptance.

Direct traces confirm that `LedgerRecorder.begin_sync_run` inserts the run in
the writer transaction and rejects a missing/deleted mapping; repository reads
already use `mapping.deleted_at IS NULL`. `LocationSnapshot` preserves volume
identity, root-relative location and a non-authoritative mount hint.
`resolve_binding` checks the root chain before accessibility and compares the
mounted-volume set again afterward; queued inventory/integrity reopens that
evidence before scan/hash. Bridge start replay precedes atomic pair-slot
resolution. Service direct-plan replay already precedes pair validation;
task-plan pair validation currently precedes its claim/replay branch. Move that
validation with candidate work into the guarded fresh-claim path and keep
admission rollback on refusal. This is a declared seam adaptation, not discovery
scope during implementation.

The current parser/no-follow/volume-resolution, ledger provenance, and slot
tests plus these owner traces establish the guarantees to retain. They do not
claim an exhaustive absence of defects. Existing local capability behavior is
preserved, including read-only observations: candidate admission promises an
observed directory, never permission or capacity for a later write. Remote
roots receive the active model's typed refusal; unknown/no-root observations
remain unavailable rather than acquiring invented optical support semantics.
`NativeScannerBackend.volume_snapshot` exposes volume identity, evidence and
capabilities, not drive kind. Any drive-kind observation needed for mapped-remote
refusal belongs in the workflow candidate's native admission seam; it does not
justify a scanner contract or module change.

**Status.** Design boundary frozen after these probes; implementation remains
paused for the user's recap after M1-4. M1-5-G and its final implementation
adversarial review remain pending.
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
remain open release obligations, not an assertion that this docs-only migration
performed a product release run.

## Resumption

M1-4 is complete. The default next checkpoint is M1-async, followed by M1-5;
the already-permitted alternate order puts M1-async after M1-5 but before M1-6.
All remaining product rows are Pending. This pass changes documentation and
the local execution procedure only. Implementation remains paused for the
user's recap and GUI adjustments; registration is not permission to start code.

On resumption, confirm implementation authority, refresh M1-async's named
consumer/seam probes against the current integrated revision, and use its one
gate below the expansion rules. M1-5 design may overlap M1-async's final work
under those rules; revalidate its service/start replay seam before coding.
M1-6 still requires the user's fuller specification. HANDOFF owns latest
operational evidence; AGENTS owns stop/adjudication boundaries. Historical DOC-2
branch/PR work and unrelated files remain untouched.
