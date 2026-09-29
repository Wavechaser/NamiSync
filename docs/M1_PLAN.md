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

## Executor simplification and throughput — 2026-09-29

Activated by the user on 2026-09-29 on `milestone1-adelbert`, before M1-9, from
the commit that registers this section. It applies the proportional-defense
policy in [DEFENSE §2.5](DEFENSE.md) to the executor and verifier, then makes
large copies run closer to device speed.

**Results, in order.**

1. **Consolidated admission per effect.** Each mutating effect reuses one
   plan-fidelity observation across the reads and checks that feed that effect.
   Remove duplicate root admissions within that effect where the approved hold
   contract permits reuse; retain held-attribute checks before each access that
   reuses admission and per-access admission for fallback roots. An item may
   contain several effects; the fidelity observation does not carry across
   later effects.
   Work kept only to preserve which accurate refusal reason wins is removed.
2. **One handle per copied file.** The temp handle carries a copied file through
   writing, metadata, flush, publication and the post-publication observation,
   removing the reopen and path lookups around finishing. It covers COPY and the
   UPDATE/MOVE_UPDATE publication paths; how far it reaches into backup and
   replacement mechanics is the implementer's call.
3. **Planner-used drift facts; verifier classifier cleanup.** Drift checks
   compare only facts the planner used to choose the action (§2.5.1). The
   user-approved verifier outcome below preserves the pre-open walk and
   post-open final-path check while removing its duplicate placeholder classifier.
4. **Direct writes for large files.** Above a measured threshold, target data is
   written unbuffered, with buffered fallback where that is unavailable. The
   file flush remains.

**Goal, not gate.** 1,000 × 4 KiB F:→G: at or above the pre-pathing
1.6 MiB/s, and the 4 GiB band well above today's 2.0 GiB/s toward the device
ceilings in [PERFORMANCE](PERFORMANCE.md#device-ceilings--2026-09-29). Missing
either means reporting the breakdown, not holding back correct work.

**Must hold.** DEFENSE's §1.2 hard walls and §2.5.2 backstops; atomic publication;
a file flush before publication and a directory flush before recording, per
file; recording only after the durable effect; the approved hold contract, its
per-access fallback and a held-attribute check before each admission reuse;
persisted identity and wire values.

**Implementer authority.** Within these results the implementer chooses
mechanisms, thresholds, helper shapes, test structure and commit boundaries,
and may merge or reorder results when code structure or measurement argues
for it, recording the choice in the commit and HANDOFF. Commits stay atomic.
Acting on a §2.5.3 consolidate, freeze or relax disposition needs no further
approval when its differences fall in the declared list below; removing a
backstop or a family marked keep does.

The 2026-09-29 execution scope covers results 1–3. Direct writes (result 4)
remain deferred and are not authorized by this execution. Start with admission
consolidation and refusal-reason relaxation together, then handle continuity;
use small atomic commits with their own verification and independent review.
Refusal selection may change; publication, recovery-artifact and recording
facts and their settlement meaning may not.

**First outcome delivered — `a6e2306`.** Fresh COPY/MOVE_UPDATE publication
reuses preparation's source fidelity; retries still recheck it. Final source
admissions with no later source access and retained-target refusal-precedence
scaffolding are removed. Target checks, UPDATE, fallback admission, effects and
settlement remain unchanged. Ordinary tests, imports, 67-group differential,
guard scan, independently classified 70-row oracle re-pin and committed 30×3
oracle passed. All 25 five-band executions/readbacks passed; the small-file
median is 1.163 MiB/s, below the non-gating goal. PERFORMANCE and
`build/executor-simplification-20260929/` retain measurements and exact evidence.
Automatic approval review rejected target-fidelity consolidation even after the
user explicitly approved the bounded proposal. That portion remains unapplied;
the first outcome uses the smaller source-only consolidation instead.

**Reopened target consolidation — user-authorized 2026-09-29.** After cleaning
the ACL-witness leftovers, retry the bounded remainder on `d444a6a`. Fresh COPY
and MOVE_UPDATE reuse `_prepare_copy`'s final target-fidelity check for that same
publication effect. Only their immediately repeated target check is conditional
on retained continuation state; retries still recheck. Final target-root admission,
held-attribute/fallback checks, prepared-temp proof, MOVE_UPDATE old-target and
trash proofs, conditional publication, durability, recording and UPDATE stay
unchanged. No check is reused across pause, retry or another mutating effect.
Runtime owns the change; executor runtime/native/ACL/settlement tests and the
existing oracle producer/baseline, EXECUTOR and delivery/evidence documents are
the finite population. Run existing native/retained-retry seams first, then
executor/workflow and ordinary/import gates, classified oracle trace changes
and its three-run check, guard scan, fixed baseline differential, five-band
measurement and fresh independent review. One small atomic commit closes this
remainder; direct writes and the recorded native own-effect defect remain out
of scope. The earlier refusal is retained as history, not a new approval request.

**Second outcome delivered — `0d7dd6b`.** One
invocation-owned descriptor now covers writing, metadata, flush, conditional
publication and successful observation, with release before recording and on
operation/invocation exit. Public APIs, retry namespace proofs and UPDATE
recovery remain unchanged. Native continuity, ACL, timestamp, lifecycle and
exFAT rename witnesses pass; the latter does not exercise the excluded FileIdInfo
defect. The unchanged 30×3 oracle, 67-group differential, guard scan, all 12
imports, 1,479 executor/workflow tests and 5,633 ordinary tests pass.
All 25 five-band executions/readbacks pass, but medians are slower than result 1:
small-file throughput is 0.737 MiB/s. PERFORMANCE retains the measured breakdown
and bounded handle/fallback diagnostic; no throughput lift is claimed.
Real external-mutation controls remain on narrowly scoped path-finishing
fallbacks where native retained handles prevent their setup. All original
identity/refusal assertions remain; native witnesses separately prove blocked
pathname access and truthful settlement. Source-open and post-close controls
retain native behavior. No new namespace/race guard was introduced.

**Third outcome delivered — `84ce0fb`, planner-used drift facts.** Core planning now owns
the narrow metadata/link-count predicate shared by preflight, executor plan
admission and recorder NOOP/MOVE/RECASE/TRASH acceptance. Creation time,
unmanaged attributes and non-move link counts no longer veto plan admission.
Existence, kind, size, mtime tolerances, identity semantics, managed attributes
and MOVE/MOVE_UPDATE link eligibility remain. Complete observations are retained;
pure rename and MOVE_UPDATE recovery bind the full admitted, profile-normalized
old version. UPDATE backup repair/restoration and failed DELETE restoration use
the admitted target metadata. Prepared/publication/backup/recovery checks, DB
concurrency, integrity and replay remain strict. The introduced weak-profile
witness mismatch was corrected and covered by a valid native RECASE case.
Direct-consumer tests passed 904 with one existing skip; ordinary tests passed
5,702 with four symlink-privilege skips. Imports, unchanged 30×3 oracle,
67-group differential and the admission scan pass. All 25 five-band executions
and readbacks pass; small-file throughput is 0.602 MiB/s and no lift is
established. PERFORMANCE retains the breakdown and comparison. Independent
final review accompanies this atomic outcome.

The finite native migration witnesses also reproduce a pre-existing own-effect
NORMAL→ARCHIVE mismatch in starting `b1b58476` and the candidate. It is deferred,
not repaired by weakening retained-version checks; BUGS owns the open defect.
The common mechanism is a strict full-version comparison spanning native
rename/hardlink attribute changes. No data loss or false success was observed.

| Executor seam | Verified consequence and owner |
| --- | --- |
| MOVE / RECASE | Runtime post-rename version proof refuses; renamed bytes remain, no success is recorded. |
| Hardlink UPDATE | Runtime live/backup proof refuses before replacement; old live and backup remain. |
| MOVE_UPDATE | Normal completion succeeds; committed-trash retry cannot recognize its intact new/trash state. |

Raw baseline/candidate vectors are under the evidence root's `differential/`
`result3a-archive-*.json`. Planner-fidelity success witnesses use stable unmanaged
attributes; they do not claim to fix the separate native own-effect limitation.

**Final outcome delivered — equivalent verifier classifier cleanup.**
The user approved the smaller verifier outcome on 2026-09-29: remove the
duplicate placeholder classifier from the pre-open reparse condition, preserving
the walk and result classes. Core placeholder classification already requires
reparse state. Moving ordinary-leaf refusal after open saves no filesystem
query while placeholder inspection remains; the finite native junction probe
changed Unsupported to Error. No result-class change is authorized. Keep root
admission/holds, opened-volume corroboration, share/cache behavior and
read-stability checks. Native verifier, its existing reparse/placeholder tests,
VERIFIER and the delivery/evidence documents are the finite population; no new
test family is required for the equivalent condition. The probe receipt is
`build/executor-simplification-20260929/verifier-leaf-design-probe.json`;
unavailable file-symlink cases are explicitly retained. Each outcome uses the verification below
and independent review; no source-freshness API, persisted-shape change,
continuation merger, target-check consolidation or direct-write work is included.

The implementation removes only the unused import and redundant classifier call.
Existing focused tests pass 239; verifier/database/workflow tests pass 1,465.
The unchanged oracle, 67-group differential, admission scan, imports and
ordinary suite (5,702 passed, four skips) pass. A README review correction is
bounded to plan admission; all 85 checks in its five ordinary package-consumer
modules pass against the final text. All 25 five-band executions/readbacks pass;
small-file throughput is 0.628 MiB/s and the 4 GiB band is 1,765.673 MiB/s.
Both goals remain unmet; overlapping ranges establish no throughput lift.
Independent closeout review passed; no tests are added or retired. Results 1–3
are closed with the recorded target-consolidation block and approved narrower
verifier disposition. Direct writes remain deferred.

**Equivalence against the starting commit.**
- *Must match:* effects, final managed trees, owned artifacts, recorder commands
  and their evidence, and every refusal on an unchanged filesystem, except the
  declared changes below.
- *May differ:* number, order and API of read-only probes; timing; message text;
  unmanaged metadata such as access time.
- *Declared expected changes:*
  - **Refusal reason when several apply.** The item still refuses with no
    effect; its reason code may become another accurate one.
  - **Drift outside planner facts.** A change only to attribute bits outside
    the managed mask, creation time, or link count outside move detection no
    longer refuses; the reviewed effect proceeds. Size, mtime, kind, existence,
    available identity and managed attributes still refuse.
  - **Finishing failure classification.** Handle-based publication may report a
    sharing or access failure under a different accurate reason. Effects, owned
    artifacts and recoverability do not change.
  - **Retained-handle permissions (user-approved 2026-09-29).** An already-granted
    owned-temp handle may finish the reviewed copy when a later reopen or
    path-based publication would be denied by copied or inherited ACLs. This
    may turn the former finishing refusal into successful publication or
    metadata completion. Containment, atomicity, durability and truthful
    settlement remain required. The finite native witnesses and restored-ACL
    receipts are preserved under `build/executor-simplification-20260929/differential/`
    as `handle-acl-<original-id>-receipt.json`; `acl-fixture-cleanup.json` records
    their original paths and hashes after user-requested fixture removal.
  - **Oracle traces and counts.** Filesystem traces, per-method counts and
    guard-scan admission counts shrink. The guard scan still requires an
    admission and a fidelity check before every mutating effect.
  - **Direct writes.** Trace changes only; a padded or partial tail is never
    visible at a live name.
  - **Mid-invocation external mutation.** A change made by another process
    between checks that this run consolidates may be detected later, or only
    at the next effect's check. The last check before each mutating effect
    remains, and the hold still blocks root and ancestor renames. Differences
    here fall under DEFENSE's quiescence precondition and need classification,
    not a decision.
- *Needs a decision:* anything else, usually a one-line question. The candidate
  never performs an effect the starting commit refused on a filesystem left
  unchanged during the invocation, except under the drift and retained-handle
  permissions changes above.

**Oracle.** Each result may re-pin the settlement baseline once, in the same
atomic commit as its cause, with a receipt classifying every changed row and
trace line into the declared list. EXECUTOR's dedicated replacement-commit rule
is waived for this run; the three-run gate restarts after each re-pin.

**Verification.** Proportionate to reach: focused, department and ordinary
tests; `lint-imports`; settlement oracle and guard scan; a differential against
the starting commit using the existing harness; native witnesses for new
Windows behavior (handle rename, unbuffered tail handling on the available
sector geometries, exFAT fallback); five-band measurements after each result;
independent review per commit. Evidence goes under
`build/executor-simplification-20260929/`.

**Needs a decision first.** Removing a backstop; changing durability or
recording order; persisted or wire changes; supported-filesystem changes.

**Stop** on an undeclared equivalence difference without a decision. AGENTS
mandatory stops apply.

**Out of scope.** Directory-flush batching (proposed for M2), the internal
re-certification and interface audits named in §2.5.3, M1-9/M1-10 work, the
exFAT FileIdInfo defect, and the pre-invocation replacement findings recorded
under the root admission round below.

## Delivered hardening rounds

### Root admission optimization — 2026-09-28

Delivered 2026-09-28 to 2026-09-29.

Executor, preflight and verifier invocations now hold each local root after
full admission instead of re-proving it on every access; remote, unholdable
and uncorroborated roots keep per-access admission with fewer native calls.
1,000 × 4 KiB F:→G: went from 28.2 s (0.14 MiB/s) to a 3.63 s median
(1.08 MiB/s) in the post-round five-band run, meeting the non-gating
1 MiB/s goal. [CORE](CORE.md), [EXECUTOR](EXECUTOR.md), [PREFLIGHT](PREFLIGHT.md)
and [VERIFIER](VERIFIER.md) own behavior, [DEFENSE](DEFENSE.md) §2.1 the hold
policy, and [PERFORMANCE](PERFORMANCE.md) the measurements. Every commit had
independent review and its named focused/direct/ordinary/import/oracle/
differential gates. Evidence paths are relative to
`build/root-admission-optimization-20260928/`.

| Commit | Shipped outcome | Review/evidence |
| --- | --- | --- |
| `6536c04` | Shared admission with one anchor lookup, reused bindings and strict held final-path confirmation; NTFS/exFAT hold witnesses. | `core/` |
| `90b57646` | Invocation-scoped executor holds with visible fallback diagnostics. | `executor/` |
| `8cdd669` | Current held attributes before every executor admission reuse. | `rootguard/` |
| `4263b12` | Preflight observation holds with lazy admission. | `preflight/` |
| `0b85d88` | Verifier invocation holds, per-file checks retained. | `verifier/` |
| `e189b48` | Verifier sector geometry from the opened handle. | `verifier/` |
| `7e60a47` | One no-follow leaf snapshot for executor metadata. | `executor/` |
| `5fe5126` | Bounded invocation-scoped pure path conversions. | `executor/` |
| `db05e31` | Single-lstat executor descendant walks. | `executor/` |
| `d88219d` | Anchor self-comparison documented as an echo, not fresh evidence. | `executor/` |
| `acdaefa` | String-only conversion-cache eligibility. | `executor/`, `resume/` |
| `0c8d304` | Leaf volume from a matching stat serial on held roots. | `executor/`, `resume/` |
| `30b0c2c` | No physical resolution for confirmed held roots. | `executor/`, `resume/` |
| `db03926` | Fix: unreadable descendants refuse instead of reading as absent ([BUGS](BUGS.md)). | `executor/` |
| `eaf62d7` | Production held-root fast paths pinned by test. | `executor/` |
| `23589bd` | Adjacent duplicate target-root admission delegated to resolve. | `executor/`, `resume/` |
| `8159905` | Full five-band corpus comparison. | PERFORMANCE |

Still binding from this round:
- **Hold contract.** Directory access without delete sharing, write sharing
  retained; one exact final-path confirmation except drive-letter case; a
  failed confirmation selects per-access admission. Held-root rename and
  delete fail with 32, ancestor renames (including POSIX-semantics) with 5; an
  attribute-only handle would not block renames. An empty held root can still
  become a junction in place, hence the held-attribute check.
- **Decisions.** Rename, move and Safely Remove failing with "in use" during an
  invocation is acceptable; the per-access fallback stays; commits are atomic.
- **Findings outside the round.** A same-volume root replacement before an
  invocation starts accepts creation effects, and identity-less DELETE/TRASH
  acts on a metadata-matching replacement. Holds cannot close either; both
  remain logged, not scheduled. The exFAT FileIdInfo defect is open in BUGS.
- **Preservation.** Baseline worktree
  `C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
  `b8baf42d` and the 67-group differential (producer `e7ba9b8d`) remain.
  Recovery drafts `cfcc6ef`, `0a04921` and `7eb8c19d` were rebuilt, never merged;
  `c833bb99`'s partial oracle-v2 migration was retired by `3c8b4b41`.
  All four WIP branches were accounted for and pruned on 2026-09-29. Exact tips,
  path dispositions and a verified recovery bundle remain under the evidence
  root's `resume/wip_cleanup_20260929*` receipts.
  The superseded nine-row RO register is in Git at `c05eea25`.

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

Pending rows record accepted future outcomes. The executor simplification run
above has its own authorized scope; other pending rows still need user authorization,
active scope and finite verification. A finding does not enlarge a row;
[AGENTS](../AGENTS.md) governs
scope changes, stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| Executor simplification and throughput | Consolidated admission per effect, one handle per copied file, planner-used drift facts and the approved equivalent verifier classifier cleanup, and deferred direct large writes, per the section above. Goal (not gate): 4 KiB at or above 1.6 MiB/s; 4 GiB toward device ceilings. | Equivalence against the starting commit with the declared changes, per-result oracle re-pin receipts, guard scan, differential, native witnesses, five-band measurements and independent review per commit. | Results 1–3 active; result 4 deferred. |
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
