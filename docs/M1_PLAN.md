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

## Incident repairs and closeout — 2026-09-27

The user authorized four separate reviewed outcomes from `a0205c08`.
Implementation boundaries and the original finite populations are retained in
Git history; component documents own the resulting behavior. Evidence is under
`build/admission-bridge-closeout-20260927/`.

| ID | Delivered outcome | Verification | Commit / status |
| --- | --- | --- | --- |
| IR-DB | Separate strict cold file admission from runtime-owned live SQLite validation. Preserve exact schema/pair/journal/placement refusal, independent role reads, fresh noncreating Plan and truthful effects. DATABASE/DEFENSE own the contract. | Deterministic reader/WAL activity and refusal/lifetime controls; 5,379 ordinary passes, 4 privilege skips, 34 headed deselections; installed Setup passed; 12 import contracts; 87 documentation links; independent review. | Complete: `639b2ea`; `db-review.md`, `db-implementation.md`, `db-ordinary-final.xml`, `db-installed-setup.xml`. |
| IR-BRIDGE | Migrate the optional diagnostic to current scalar/terminal shapes, retain exact reliable-item witnesses, preserve the first report failure and raw incomplete streams, and settle synthetic cancellation through normal host cleanup. BRIDGE/PERFORMANCE own behavior and observations. | 35 focused passes and CRLF page probe; 5,380 ordinary passes, 4 privilege skips, 34 headed deselections; complete installed observation on `639b2ea`; injected rejection retains raw evidence and exits normally. | Complete; independent review approved. The commit carrying this row delivers IR-BRIDGE. `bridge-review.md`, `bridge-ordinary-final.xml`, `bridge-full-final.json`, `bridge-injected-report-failure.json`. |
| IR-CLOSE | Remove AB-7 focus loss from BUGS and retain environmental troubleshooting in TESTS. Retain the enabled-button wait for independent asynchronous-filter sequencing. Retire the unrealized DWM sentinel obligation; no new focus/compositor detector. | Source/evidence review, 86 documentation links and diff checks; independent approval. Product/helper unchanged. | Complete: `e8d3613`; `closeout-review.md`, `closeout-docs-check.json`. |
| IR-DEFER | Shelve AB-8 stack/wrap; retain the unconfirmed renderer/check race, historical limitations and recurrence inspection points in TESTS. | Documentation consistency, 84 links, evidence references and diff checks; independent approval. No CSS/helper/assertion change. | Complete: `8f75f75`; `defer-review.md`, `defer-docs-check.json`. |

The database runtime retains two lazy role connections. Later pair checks and
consumer opens validate current SQL, main identity and journal absence; public
standalone constructors retain cold byte-preserving preflight. Reader retirement,
writer placement and retryable runtime shutdown remain intact.

The bridge driver decodes only its finite 1–1,500 byte coordinates, consumes
item-free terminal facts and independently checks 150 ordered reliable outcomes
per task. Reporting stops on the first rejection, queued counters unwind, and
failure metadata is captured before cleanup. Failure/final milestones and
unfinished timing streams survive clean incomplete exits. The current source
population is the bridge diagnostic package, its focused test module and page
probe; production host/transport and frozen custody JSON are unchanged.

Historical advisory `passed`/`event_passed` remain false in the final native
observation; `status=complete` and `measurement_valid=true` establish the
diagnostic endpoint only. No new timing/custody acceptance is claimed.
Original AB-7 Setup and AB-2/AB-10 causal attribution remains qualified.
All original and intermediate failure receipts are retained.

AB-8 implementation, environment monitoring, GUI changes, automatic mutation
replay, broad schema migration and unrelated M1 work remain excluded. A
pre-existing performance-CLI error suggests an unsupported replacement flag;
BUGS records that separate guidance defect, and reruns use fresh report paths.
No CLI change was included.

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
acknowledge/restore desktop capability is accepted and still needs an explicit
delivery allocation when M1-9/10 activates. M1-10's rebaseline confirmation
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

Pending rows record accepted future outcomes; implementation still needs user
authorization, active scope and finite verification. A finding does not enlarge a
row; [AGENTS](../AGENTS.md) governs scope changes, stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| M1-9 | Bounded inventory projections, current evidence and the full inventory consumer for sibling sorting. | Complete or prior-complete publication; warnings outside action scope; raw evidence provenance; search/filter/collapse/window/detail, replacement/race and production sort/reset paths; headed witnesses. | Pending. Missing-row acknowledge/restore UI must be explicitly allocated at activation; this row does not silently claim it. |
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
unprofiled. No completed row authorizes M1-9 inventory projection, M1-10
integrity controls, M1-12 lifecycle closure or release.

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
