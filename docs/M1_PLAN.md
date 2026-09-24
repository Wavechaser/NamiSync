# M1 Delivery Register

This is the sole active M1 delivery register. Subject contracts remain in
[ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md), [BRIDGE](BRIDGE.md),
[PRESENTATION](PRESENTATION.md), [INTERFACES](INTERFACES.md),
[DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md) and [TESTS](TESTS.md).
The [archived delivery register](obsolete/M1_8_DELIVERY.md) preserves the finite
R0–R3 criteria, original B1–B6 dispositions and recovery chronology.

## MOVE-1 retained-history move detection (2026-09-25)

User-authorized backend investigation and correction, independent of pending
GUI work. Base: `3514bb8`; current checkout `milestone1`. One atomic fix commit
after independent review; no push, PR or live development-ledger mutation.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| MOVE-1 | Repeated source renames/moves remain eligible for correspondence-backed target moves despite retained historical inventory aliases; real simultaneous hardlinks and ambiguous correspondence remain ineligible. | Native failure reproduced before correction; 148 focused checks; 5,417 ordinary passes/five environment skips; 12 imports; diff/link checks; fresh adversarial review. | Complete in the commit recording this row |

Finite population: planning correspondence in `db/repositories.py`, its direct
consumer `workflows/runtime.py`, planner move eligibility in `modules/planner.py`,
and existing `test_db_repositories.py`, `test_planner.py`, `test_workflows.py`.
Recorder retention/reconciliation, scanner links, workflow completeness and
service Plan projection were inspected without changes. Documentation owners:
DATABASE, PLANNER, BUGS, this register, CHANGELOG and HANDOFF; README only if its
phase synopsis changes (none needed). Preserved the prior investigation in
`build/move-history-20260925/handoff-before.md` before replacing it at delivery.
That ignored evidence directory holds flat, descriptively named logs and review
notes, plus named pytest temporary-root subdirectories when the system temp
directory is unavailable; retain evidence at closeout, with no artifacts in Git.

Preserved guarantees: reviewed effects, current source/target identity and link
checks, unique correspondence, incomplete-scan refusal, query admission/batching,
one SQLite read snapshot, ordering, retained inventory/history and ledger schema.
Verified repeated native move/no-op cycles with retained aliases; current
source/target links, including outside-root/excluded links; stale multi-link
observations; duplicate scan identities/pair ambiguity; and consistent batched
reads. Archived M0 hardlink refusal remains binding. No performance claim added.
Non-goals: ledger cleanup/migration, identity-reuse redesign, GUI behavior,
inventory reconciliation changes, broader planner refactoring or unrelated bugs.
AGENTS mandatory safety/recurrence stops apply; changed effect or ownership
boundaries require adjudication before implementation.

Shipped: remove historical disqualification only from `find_current_mapping`;
current `FileRecord.nlink` and planner identity counts own current alias
eligibility. General inspection remains conservative. No path/presence filter
can make a retained observation fresh. Production edits are confined to
`db/repositories.py`; the three test files above cover the affected seams.
Obsolete identity-query assertions became pair-query batching/index and
concurrent correspondence snapshot controls without retiring their guarantees.
Archived DESIGN_REVIEW DR-04's correspondence and hardlink evidence obligation
remains satisfied by retained pairs plus current scans. No recorder, schema,
workflow, scanner, preflight, executor or interface production change is needed.
The completed TEST_REFINEMENT ST-2 register described historical alias-query
assertions at its frozen source revision. MOVE-1 supersedes only that obsolete
alias-query mechanism; its current pair index, batching, ordering, identity
filtering and snapshot guarantees remain binding. FEATURES already describes
hardlink refusal in terms of scanned paths and needs no contract change.

Evidence: `build/move-history-20260925/` contains the native pre-fix failure,
`focused-final2.log`, `ordinary-final.log`, imports, links, and independent
`reviewer-readonly.md`. The first ordinary attempt used repository-local temp
roots and hit protective test refusals; its failed receipt is retained. The
final run uses normal external temp roots and the final frozen source/tests.
Five skips: unavailable symlink privileges (four) and unconfigured M1-7 readiness
artifact (one); 33 headed tests are outside this backend-only change. No extra
branch/worktree, live user-data mutation or unrelated change was introduced.

## M1-8 execution review closure

Delivered: shared Plan/live/terminal status, bounded virtual rows and reachable
Details at native minimum, exact execution/current-evidence distinctions,
follow/Go navigation, truthful progress and capacity feedback, retained action
feedback, and task/session-owned Retry updates including pending Close.
Operational admission, terminal truth, close fences and effect authority are
unchanged. Retry restores observation; it never restarts execution.

| Outcome | Reviewed commit / disposition |
| --- | --- |
| P2 foundation | `4bbf943`; bounded live/retained overlays and one-detail custody. |
| R0 usable execution review | `8f7555b`; A1–A4 and B1–B6 closed. |
| R1 functional consolidation | `0fc2f5d`, corrections `9e5b080`; retained semantic/native detectors. |
| R2 quantitative consolidation | `b1f5a07`, `c974447`; U-v2 observers and fixed 78-attempt acceptance. |
| Post-R2 containment/control fixes | `96a0212`, `9be2930`; automatic probe bounds and task-owned control feedback. |
| RC-1 observation recovery | `3ea4e6b`; separate reviewed correction, fresh affected gates and U evidence. |
| R3 integration | A6 below defines the terminal observation; no WIP or unrelated GUI recovery enters the merge. |

### Final acceptance ledger

Evidence root **E** is `build/recovery-close-20260924/` inside the candidate.
After cleanup the entire directory is preserved at
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/` in the main
checkout. E's `delivery-01.json` binds RC-1 `3ea4e6b1b59d700428440c45cc845f68d852eeae`, its Git tree,
artifact hashes, raw logs and independent review. All package inputs, wheel
members and installed files are compared physically; the U authority records
the fixed runtime/native profile and measured source population.

| ID / accepted outcome | Owning detector and evidence | Result / review disposition |
| --- | --- | --- |
| A1 usable layout; B1/B2 | Existing gallery's eight disclosure/size/row states, native keyboard/scroll and bounded-window adoption; E `builder/consumer-headed-pytest.txt`, `captures/`, `review/visual-review.md`. | Pass on final installed product; native minimum 1024×640 retained. Raw browser alpha captures are not native-material contrast evidence. |
| A2 identity/interaction; B6 | Task-shell/drain/row probes, deferred-response controls, follow/Go sequences and native task-shell recovery/Close witness; E `ordinary-01.log`, `builder/rc1-builder-report.md`, `headed-01.log`. | Pass; exact task/session/revision, bounded 256-row window/one detail, stale rejection, control feedback and retirement remain distinct. |
| A3 truthful facts; B6 | Producer, reducer and execution-review tests plus rendered row/status witnesses in the ordinary and installed suites. | Pass for success/zero/unrun/canceled/degraded, capacity plus independent failure, Gap/terminal and exact large-byte progress. No changed ingress, mutation or safety authority. |
| A4 installed composition; B3/B4/B5 | E `headed-01.log`: 24 unaffected passes; nine gallery/transport passes after two direct test-consumer migrations, E `builder/consumer-headed-pytest.txt`. Both short copies/details/PNGs and both legacy native journeys pass. Full source/wheel/install identity in `run-01/head-validation.log`. | All 33 obligations pass; failed original headed attempt preserved. E `review/RC-review.md` and visual review name actual evidence and limitations. |
| A5 fixed performance | Three `tests/interfaces/web/m1_8_execution_ui_*.json` artifacts; E `run-01/` raw/freeze/derive/staged/HEAD validations and `artifact-controls-01.log`. | All 78 attempts: 13 readiness + 65 measurement children, 40 cold/150 warm samples. Unchanged cold max ≤50ms, warm nearest-rank p95 ≤100ms/max ≤250ms; independent raw derivation passes. Historical failed R2 runs remain failed. |
| A6 coherent integration | E `review/R3-review.md`, `accounting/`; main `build/m1-8-archive-20260924/integration.json` records non-squash merge, exact candidate/merge tree and passing postmerge source/package/artifact identity. `evidence-move.json` and `cleanup.json` record preservation and cleanup. | Functional gates: 5,405 ordinary passes/five skips, 33 installed GUI obligations and 12 imports. Complete only when the integration receipt records the matching merge/tree and PASS; receipt absent means integration remains open. |

The integration receipt is the terminal observation; this register does not
claim completion before it exists. Independent reviews cover the complete
P2-to-final delta, not only RC-1. Seven recovery refs are preserved in a verified
bundle; four dirty detached-worktree files and every unique build-evidence tree
are accounted before removal. Unrelated GUI refs and all stashes stay untouched.

Stop after M1-8. Filter/Search, speculative theme changes, M1-7 reduction-study
resumption, general test-framework changes, M1-9, push and PR are excluded.
The [retained reduction study](M1_7_ABLATION_STUDY.md) requires explicit user
resumption. Future product and release obligations below remain binding.

## Remaining checkpoints

### Completed GUI and documentation work

Completed records are condensed here; CHANGELOG and Git history through
`2cc0083` retain individual deliveries, studies, verification and exact diffs.
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
| Plan-surface GUI-P1–P3 (2026-09-17) | Plan/Status cards, resizable rootless virtual table, sibling-sort gestures and exact byte display. `27f1a6b`, `4053a53`, `6425fa7`, `db46269`; component and installed Plan/gallery checks. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md). |
| Scoped Plan GUI-S1–S3 (2026-09-17) | Revision-guarded header/folder selection over complete filtered membership, hidden selections preserved, synthetic root omitted. `f3bd84f`, helper correction `87dbd49`; ordinary/installed checks and 120,000-operation scoped-cost witness. These IDs are distinct from the earlier Setup GUI-S rows. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md). |
| GUI-F1–F2, GUI-H1–H4 | Editable queued search, counted filters, stable panel/row refresh, server-owned highlights and atomic highlighted selection. `ae99f54`, `218866b`; ordinary, browser, installed and 120,000-row checks. The empty-rootless Setup witness noted in GUI-F was corrected during GUI-J. [PRESENTATION](PRESENTATION.md). |
| GUI-J1–J3, GUI-K1–K3 | Grouped filters, compact viewport/task digest, neutral Plan-ready meaning, layout and status polish; directory own-operation eligibility corrected independently of descendant rollups. `44a5d49`, `4ef526e`, `f8bc1aa`, `0584707`; focused, department and installed default/larger Plan checks. Shared byte formatting was superseded by GUI-O below. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md). |
| GUI-L1–L2 | Fluent control/gallery alignment and server-owned arrow navigation across windows, preserving pointer focus modality. `dd926b8`, `e6ee448`; component, interface and installed gallery/Plan checks. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-M1–M2 | Status actions/feedback and static destination-tree folder totals from retained file facts; partial/overflow facts remain explicit, numeric sorting stays server-owned. `70a9270`, `7cf4448`; workflow/interface, independent scale-fixture sums, scalar boundaries and installed Plan checks. Historical scale receipts were not rewritten. [PRESENTATION](PRESENTATION.md), [DEFENSE](DEFENSE.md). |
| GUI-N, GUI-O, GUI-P (2026-09-19–20) | Friendly labels and selective low-risk notes, fixed semantic icon slots, immediate planning feedback, exact bytes below 1 KiB/two decimals above, tertiary text and final spacing/alignment. `c552537`, `8fd8cd0`, `2cc0083`; focused/department and installed gallery/default/larger Plan checks. [DESKTOP_UI](DESKTOP_UI.md). |


GUI delivery evidence remains in the matching CHANGELOG tasks and those commits'
HANDOFF snapshots. Intermittent installed dialog/confirmation failures were
retained as failed attempts; unchanged isolated reruns passed without weakened
assertions. GUI-P's last evidence root is
`C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/`.
GUI-M2 recovery `af02913` and stash `93414b7` remain historical preservation,
not merge units; useful changes were rebuilt in `7cf4448`. The reported Optics
refresh delay remains unprofiled; no cloud/path diagnosis was established.

No rendering fix was established for the WCG shadow halo or intermittent
disabled-label blur. Mica remains required and no compositor-health release gate
was added. GUI-D8–D10 attributed the halo to Windows Advanced Color composition;
GUI-W1 below adds a mitigation, not a fix. BUGS and DESKTOP_UI retain
investigation boundaries and reopen evidence. Recent availability remains observation, never admission.
The existing 48-pair bound, serial best effort, per-row options and exact
uncertain retry remain active; clearing receipts does not close tasks.

### GUI-W1 Advanced Color shadow mitigation (2026-09-24)

User-activated after M1-8; it does not resume other excluded work. Evidence
and diagnostics: [BUGS](BUGS.md#desktop-material-composition).

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-W1 | While the window's current display has Windows Advanced Color active (SDR WCG or HDR), dark flyouts (dialogs other than keyboard-focused, menus, combobox popups) suppress CSS elevation shadows exactly as the existing dark HDR rule does. Native appearance reads the state for the window's monitor, refreshes it on display-setting changes, monitor changes and activation without reapplying material, and publishes it in the exact appearance envelope (v2 → v3). Read or observation failure keeps the prior value and degrades like other appearance observation. | Controller/fake-native publication, refresh, failure and close tests; page receiver probe for the v3 schema; token rule assertions; installed gallery report on this WCG display recording `advanced_color` and suppressed popup shadow; ordinary interface departments; import contracts; `git diff --check`. | Complete in the commit recording this row |

Population: `appearance.py`, `appearance.js`, `components.css`; their tests,
the appearance probe and the gallery evidence path; BUGS, DESKTOP_UI,
FEATURES, CHANGELOG and HANDOFF. Non-goals: fixing the Windows defect, scRGB
or other renderer flags, light-theme or card-level changes, pre-distorted
tokens, removing the HDR media rule. Stops: any change to Mica/opaque material
selection, surface-safety settlement or command/readiness authority.

### GUI-WR1 mitigation review (2026-09-24)

User-authorized review of `c637025` against `6c00ec7`, limited to its native
Advanced Color observation, appearance-v3 producer/receiver, shadow selectors,
direct test/helper consumers and GUI-W1 documentation. Preserve material and
surface-safety decisions, readiness authority, light-theme shadows and keyboard
focus. No new GUI features, compositor fixes or unrelated harness cleanup.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-WR1 | Review the GUI-W1 mechanism and consumer migration; correct concrete in-bound defects if found, with a reproducer and finite correction population recorded before implementation. | Independent native/API review; source/consumer inspection; 165 focused checks; three installed gallery passes and the fourth passing unchanged in isolation; final diff review. | Complete; no production/test correction identified |

One atomic reviewed commit per necessary correction; a review-only result changes
only this register, CHANGELOG and HANDOFF. GUI-W1's stops remain binding; a
changed ownership, safety or verification boundary requires adjudication. The
regression study compares the old HDR selectors with the new WCG selectors,
traces envelope readers and native subscription cleanup, and checks retained
failure behavior. Historical GUI-D8–D10 diagnostics remain evidence, not a new
acceptance gate or authority to rerun compositor experiments.

Evidence: `build/wcg-review-20260924/` retains both installed attempts and
source/wheel/install identity records. The first gallery matrix attempt failed
the unchanged dark minimum-window clipping detector; the isolated rerun passed
without changed assertions. Both Advanced Color and HDR were active, so this
run does not isolate the WCG-only selector. GUI-W1's prior WCG-only and live
monitor-move evidence remains separate. No new compositor-health claim is made.

DOC-2 remains **pending, outside this M1-8 batch**: the historical branch
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
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Gate C passed with A8-02's explicit recorder-only/finalization boundary; existing failure-policy/Stop and settlement paths, unchanged oracle. | Complete |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | A1–A5 verified; A6 receipt governs integrated closure. |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


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

## M1-7 delivered

Delivered and integrated through `5986c57`: bounded Plan review and sibling
sorting, selection/commitment freshness, snapshot-bound destructive confirmation,
same-task execution, pause/resume/cancel, truthful committed-but-unrun review,
fresh Plan again and task-close/replay ordering. The browser keeps only its
bounded window; workflows/service remain authority for operations and effects.
BRIDGE, PRESENTATION, INTERFACES and DESKTOP_UI own current contracts. No
inventory/result-overlay or terminal retry/reopening was delivered by M1-7.

P9 accepted the unchanged `3c3bbbc` measured candidate: 35 metrics, 175 fresh
measurement children/775 samples after declared readiness, with independent
source/runtime/installed and terminal validation. Final ordinary verification
was 5,158 passed/four platform skips; imports, installed Plan checks, docs and
reconstructed integration accounting passed. Raw evidence and integration
receipt: `build/m1-7/evidence/p9-full-20260916/`; protected compact artifacts
remain at their existing paths in `tests/interfaces/web/`. This is the declared
Plan profile, not whole-app memory or current-source acceptance for later edits.

Post-delivery ablation R7-1–R7-4 landed through `95f31e1`; R7-5–R7-8/R7-G remain
suspended, not completed. RI-1–RI-4 discovery is complete; larger test/evidence
retirement remains a proposal in [M1_7_ABLATION_STUDY](M1_7_ABLATION_STUDY.md).
Revisiting it is deferred until after M1-8 closes and requires user resumption;
it is not a closure dependency and cannot expand R2. Later delivered Plan GUI refinements
through `2cc0083` are recorded in the compact GUI results table above.

## M1-8 foundation delivered

| Closed row | Result and owner | Commit / accepted evidence |
| --- | --- | --- |
| M1-8-D | Condensed prior GUI records and established the original delivery register. | `42ff8f2`; documentation/link/diff review. |
| M1-8-capacity | Recognized disk-capacity operation/cleanup/prerequisite failures stop later admission after current settlement. Recorder-only failure remains independent degradation; finalization remains settlement. EXECUTOR owns classification. | `04947ba`; Gate C, unchanged 30-scenario/three-run settlement oracle, 5,216 ordinary passes/five skips, twelve import contracts. `build/m1-8-capacity-*-final01.log`, `build/m1-8-capacity-oracle-final.log`. |
| M1-8-E | Bounded atomic current-ledger classification, coherent content only, no schema/write path or full-run scan. DATABASE/PRESENTATION own evidence semantics. | `7905a1b`; Gate E, 5,226 ordinary passes/five unchanged skips and consumer/independent checks. `build/m1-8-e-ordinary-final01.log`, `build/m1-8-e-neighborhood-02.log`. |
| M1-8-P1 | Exact task/Plan/session/run-bound retained execution summary and separate operation/linked-verification indexes; capture before release; idempotent close/shutdown retirement. INTERFACES/PRESENTATION own lifetime. | `055325b`; Gate P1, 5,232 ordinary passes/five unchanged skips, neighborhood/independent/import checks. `build/m1-8-p1-ordinary-final02.log`, `build/m1-8-p1-neighborhood-01.log`. |
| M1-8-P2 | Bounded live/retained Plan summary/window overlays and one-operation detail, revision binding, visible Gap history and bounded current evidence. BRIDGE/PRESENTATION own protocol and measurement. | `4bbf943`; independent functional/installed/source review and full unmocked terminal/clean-HEAD validation. A8-03/A8-05 scoped Tier-2 window/start receipts accepted: p95/max 6.8/7.3ms and 58.8/65.1ms against unchanged 100/250ms. |

The immutable P2 artifacts remain reproducible at their recorded revision. The final U artifact supersedes corresponding performance results for the delivered UI bytes; historical failures and reconstruction dispositions remain in the evidence archive and [historical register](obsolete/M1_8_DELIVERY.md).

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

Recognized operation, cleanup and destructive-prerequisite disk-capacity failure
stops later admission after current settlement under M1-8-capacity. Recorder-only
write failure remains recording degradation with continuation. Generic I/O keeps
its typed reason and has ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence. Location-only text is
displayed in execution Details. No filesystem inventory or purge is added to populate that information.

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
