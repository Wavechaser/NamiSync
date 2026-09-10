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
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
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

## M1-5 bounded checkpoint detail

**Outcome and acceptance gate.** M1-5-G is one checkpoint gate: Setup's
current picker-backed plan start and inventory use one workflow-owned location
candidate admission route, expose typed results, and can read bounded,
identity-based remembered locations. The gate closes only when the finite
transition checks below, affected-department and ordinary verification, source
tracing of preserved guarantees, matching documentation, and a fresh adversarial
review all pass. A green test run alone does not close it. M1-4 must be reviewed
and committed before M1-5 implementation begins; M1-async normally precedes
M1-5, with the permitted alternate order recorded above. The user authorized
this delivery on 2026-09-10; M1-5 starts after M1-async closes and its affected
design seams are refreshed.

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

Native picker paths already flow through slots into service plan start. Pure
input bounds precede task custody. On a fresh start, perform native candidate
admission after the command replay/claim boundary
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

**Delivered (2026-09-10).** One workflow-owned candidate route now serves
fresh picker-backed plan starts and inventory/integrity binding. Literal inputs
are bounded before task custody and native work; typed refusal preserves
identity context, and accepted candidates carry the final current mount.
Read-only remembered sources, targets and active pairs each stop at five
identity-deduplicated durable-run results in one database snapshot. No schema,
frontend, domain-policy or task/session ownership change was made.

The finite preimplementation corpus covered the named owner/consumer seams,
including probe-only recorder setup/move and sync tests. Its integrated baseline
receipt is below. Source tracing and final review confirmed fresh point-of-use
probes, replay before native admission, purpose-bound atomic slot resolution,
literal/native path separation, local capability behavior, and run provenance.
Candidate admission promises an observed directory, never later write capacity
or authorization. Archived recipes and the non-goals above remain deferred.

M1-5-G passed: 680 focused tests; 2,697 database/workflows/interfaces tests;
4,912 ordinary tests with four existing privilege skips; all 29 installed
WebView2 tests and twelve import contracts. Final documentation/diff and
independent adversarial review close the same atomic outcome. Two introduced service
regressions were corrected with retained witnesses: exception-context cleanup
and raw input bounds before task custody. No test module was added or retired.
Raw commands/results, candidate identities and review are retained under
`build/m1-5/evidence/`; inputs remain under `build/m1-5/inputs/`.

## Investigation and regression map

**M1-5 integrated refresh (2026-09-10).** M1-async is committed as `675181a`
on `milestone1`. Before M1-5 source edits, the unchanged twenty-selector and
five-picker corpora passed **44** and **17** tests on that clean commit.
Commands, raw output and before/after source identities are retained in
`build/m1-5-design/runs/integrated-675181a-02/`. The first disposable-runner
invocation omitted its temporary parent directory; the runner was corrected
and rerun with a fresh identity, without changing product or tests. Candidate
implementation must preserve the replay/claim and slot seams traced above.

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

M1-4 and M1-async (`675181a`) are committed on `milestone1`; M1-5-G is closed
for the atomic delivery described above.
This delivery stops for the requested recap and GUI adjustments. M1-6 awaits
the user's fuller specification and authorization; no M1-6 implementation,
historical DOC-2 branch/PR work, push or PR is part of this delivery.
HANDOFF owns the latest operational evidence; AGENTS owns stop/adjudication
boundaries. Future checkpoints use the expansion rule above against this
integrated state before starting dependent work.
