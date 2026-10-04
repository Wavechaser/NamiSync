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
