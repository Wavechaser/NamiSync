# Workflows Module

Status (2026-08-22): M0 reviewed sync/history plus M1 Stages 1-5.5 are
implemented. The local
composition root now owns role-free inventory and standalone
baseline/verify/rebaseline, their production dispatcher registrations,
strict execute/verify continuation payloads, optional post-execution
verification, compound history/views, generic history reads, semantic-settings
snapshot/patch translation, and the shared facade used by the location CLI
commands. Stage 5.5's workflow-owned selection semantics are now implemented:
direct user deselection remains distinct from safety exclusion, execution
re-derives the authoritative set, and plan payload v5 plus execution payload v6
preserve that provenance and executor continuation truth.
Stage 5.5 facade integration is complete;
Stage 6 desktop behavior is finalized in `M1_BRIDGE.md`; queue durability,
maintenance/retention, replay, undo/repair, and ingest remain later work.

## Stage 6 Second-Half Workflow Contract (Checkpoint 2 Portion Active)

The checkpoint sequence is owned by
[M1_SHELL_H2.md](M1_SHELL_H2.md); exact event/result and task protocols live in
[M1_BRIDGE.md](M1_BRIDGE.md), and numeric/retention walls in
[DEFENSE.md](DEFENSE.md) §1.3. Workflows consume those contracts without
treating a continuation version as a global epoch or receiving an
interface-owned task claim.

Execution continuation is opaque process-local custody. Its exact v6 codec now
carries sparse operation recording reasons, ordered task issues, aggregate byte
high-water, and transient publication evidence needed for same-session
pause/resume or automatic linked verification; payload v5 is refused. The plan
codec remains exact v5. Transient evidence never becomes history, ledger,
desktop artifact, or JavaScript state, and dispatcher terminal settlement
clears the only retained opaque reference. Manual exact post-copy verification
remains a later checkpoint and instead classifies current durable evidence in
the original execution scope.

Workflow aggregation now preserves operation-local recording truth and the
first observation of each task issue in order: later failure cannot rewrite an
emitted item or revoke committed evidence. The live core event remains exact
v4; exact item detail, task-issue result fields, terminal summary, and omission
vocabularies activate together at checkpoint 3.

At the accepted scalar cutover, workflow accumulation follows the exact
checked-arithmetic contract in [M1_BRIDGE.md](M1_BRIDGE.md) and
[DEFENSE.md](DEFENSE.md) §1.3 without a workflow-local numeric variant.

## Purpose

Workflows are plain top-to-bottom functions and the only place operation modules
meet. They translate a typed request into sequential calls, pass immutable
outputs forward, aggregate filesystem/recording/history-aware results, and
declare required resources to dispatcher. They do not implement scan/diff/copy/
hash/SQL/UI behavior and never coordinate through signals or callbacks-for-
control.

Every runtime dependency arrives through one composition-root `deps` object:
clock, scanner/change source, repositories, planner/policies,
observer/preflight, executor, verifier, recorder, and later importer. Planning
adapters may snapshot semantic defaults when constructing a request; admitted
execution does not receive or reread a settings provider.

### Node tree substrate

`build_node_tree` is a pure workflow helper over path-keyed members. It emits
deterministic preorder structure, immutable id/path indexes, direct member ids,
subtree membership, and bottom-up member counts. The empty-key root is always
addressable and the canonical path index remains one-to-one and domain-only.

Plan projection preserves that single path authority when several immutable
operations share one target. It retains one path/group row and emits every
operation once as a direct member, with a separate operation-id index for item
anchors. Group presentation never changes executable membership or grants
filesystem-folder action semantics.

Informational warning/notice leaves are interleaved only after the domain tree
is built. They have typed stable identities and deterministic attachment, but
never enter the canonical path index, subtree membership, selection, rollups,
or actionable scope. Exact node codecs, ordering, projection frames, diagnostic
omission, and population walls are owned by [M1_BRIDGE.md](M1_BRIDGE.md).
Presentation filters, move grouping, overlays, and caches remain Stage 6
service/interface concerns rather than tree-builder policy.

### Review publication

Stage 6 injects an immutable workflow-owned `ReviewPublicationContext` and a
workflow-level `ReviewPublicationSink` implemented by the task service. The
incremental collector either stages one complete immutable plan/inventory
candidate—including indexes, rollups, charge, and omission identities—or
returns the typed no-partial population refusal. It never returns an unbounded
or partial raw graph.

The workflow invokes the sink only for the exact session/slot/tree intent it was
given and stages at most once. Once successful fresh preflight has staged its
complete notice generation, expected execution failures and cancellation are
contained into a normal terminal `OperationResult` so the stage survives for
reconciliation. Missing, duplicate, rejected, contradictory, or escaped
post-stage behavior is structural producer failure, not a recoverable workflow
result. The exact stage/result matrix, latch behavior, owner reconciliation,
fault disposition, and retry boundary are bridge authority.

An initial plan or inventory publication has no prior baseline. Inventory
refresh evaluates the complete candidate in place of the old inventory for
population admission but does not reclaim the still-owned generation before
atomic swap. Fresh execution preflight similarly replaces its complete notice
set—even when empty—without replacing the immutable plan. Workflow never
reprojects a staged candidate after publication.

## Reviewed Sync

### Plan session

1. Lexically normalize and validate distinct non-nested roots and request
   semantics without following filesystem links. The shared core chain-only
   admission obtains the current native anchor and uses extended spelling only
   for no-follow probes of every configured-root component below it,
   returns ordinary lexical `Path` values, compares separately resolved
   physical roots for overlap, refuses reparse, device, or ordinary-ambiguous
   root names, and never persists or displays a `\\?\` prefix.
2. Resolve volume/location/mapping evidence without persisting preview-only
   configuration.
3. Scan both roots with the same role-free observation contract.
4. Read immutable prior correspondence and one complete semantic-settings
   snapshot. If the request supplies a deletion-policy override, replace only
   that field in the snapshot.
5. Apply filters/policies and plan.
6. Derive the deterministic safe selection: retain additive/no-op work, mark
   direct blockers `BLOCKED`, quarantine overlapping/dependent work as
   `DEFERRED`, and withhold destructive/identity moves when either scan is
   incomplete.
7. Observe/preflight that exact selection for review information.
8. Return the immutable plan/verdict with reviewed authority and typed warning/
   refusal facts intact; terminate and release locks. Stage 6 projects those
   facts as inert notices rather than flattening or dropping them.

### Execution session

1. Re-derive the authoritative execution selection from the immutable plan,
   safety exclusions, and canonical `user_deselected` set. Validate the exact
   core `Commitment` defined by [M1_BRIDGE.md](M1_BRIDGE.md); execution cannot
   resupply a frozen Setup choice. Refuse a malformed or mismatched commitment
   before preflight. An all-skipped result refuses because there is nothing to
   execute; a selected `NOOP` remains executable work.
2. Reacquire required physical-volume custody.
3. Consume the immutable semantic snapshot bound into the reviewed plan; never
   reread global defaults to decide admitted filesystem behavior.
4. Freshly observe/preflight filesystem and volume state under execution
   custody; refusal mutates nothing.
5. After a successful verdict, remove exact prior-run temps once from the
   observed touched-target-parent scope; cleanup failure stops before executor
   admission, so capacity credited by preflight cannot become unsafe.
6. Execute selected dependency-closed work through the pipelined XXH3-aware
   backend, record each settled operation through the run recorder, and return
   ordered `operation`/`execute` items with independent filesystem, recording,
   and audit truth.

7. When explicitly requested, translate every successful byte-producing
   publish into a transient post-copy candidate, verify it under the same
   custody/run token and reviewed target-volume authority, and retain rowless
   candidates when copy recording failed.
8. Return one ordered operation+integrity item stream and independent execute/
   verify phase summaries. Finish the one logical ledger run exactly once; a
   pause leaves it unfinished for same-process resume. A malformed resumed
   continuation is refused before domain work and finishes the already-open
   run directly by its custody-bound token; it never attempts to re-begin that
   run from the malformed carried selection.

The default execution path still ends after step 6, preserving M0 behavior.

Human review occurs between sessions with nothing running. Commitment is the
durable preauthorization and has no time expiry, but binds exactly one plan,
dependency-closed selection, approval, and frozen linked-verification choice.
Scripts and queue releases may replay it; no API plans and executes in one
unreviewed breath or supplies a later linked-verification choice.

The implemented Stage 5.5 selection substrate keeps safety exclusions and
direct user deselection distinct. Effective exclusion closes downward over
dependencies; reselection removes the requested operation and its transitive
dependencies from `user_deselected`, but can never clear a safety exclusion.
Execution rejects an empty or mismatched re-derived set before observation and
preflight. The service integration owns review revisions, lower-level direct-
artifact replacement discard, and the reviewing/committing/committed
transition; the client submits revisions and opaque ids but never becomes
selection authority. The H2 desktop never replaces a published task plan in
place. A terminal unrun attempt returns the unchanged plan's selection to
reviewing at a new revision so a fresh commitment may authorize another subset;
the first ran result freezes it permanently. Explicit Plan again resolves the
retained reviewed location identities and creates a new task with default
selection rather than replacing the old artifact or carrying authorization.

### M0 implementation

`workflows/sync.py` contains the plain planning and execution functions.
`LocalWorkflowRuntime` is the local composition root: it injects every module,
resolves immutable prior correspondence through read-only repositories,
declares physical-volume resource keys, owns schema-versioned JSON continuation
payloads, starts ledger recording only after commitment and fresh preflight,
and supplies the dispatcher history observer. Planning and declined review do
not create either database. Invalid database locations are rejected before the
plan session, and an execution refusal may still create independent audit
history while leaving managed files and ledger configuration untouched.
Execution start custody is established only when the invocation actually enters
workflow work, or when a pre-run pause snapshots a resumable start. Terminal
refusal or failure before ledger recording releases that custody; a cooperative
pause retains it for exact resume/cancel settlement.
Execution recomputes the decoded plan fingerprint before comparing commitment,
so payload content cannot change behind a retained fingerprint. This makes
lossless payload encoding a correctness invariant, not a convenience: every plan
field that feeds the fingerprint must survive the JSON codec unchanged, or
execution refuses a faithfully committed plan. A round-trip/fingerprint-stability
test exercises the codec over every operation kind and optional field, so a
dropped or renormalized field fails the build instead of silently refusing every
execution.

Stage 1 advanced the opaque plan/execution codec to version 2 and removed
`worker_count` from `SyncOptions`, `Plan`, fingerprints, and both payloads
without adding a replacement execution setting. Stage 4 advances the global
codec to strict version 3 because execute decoding now has phase-specific
required fields. Stage 5.5 advances both plan and execution payloads to strict
version 4 and requires canonical `user_deselected` on every execution set;
version 1-3 payloads are refused instead of being guessed into the changed
contract. Progress-continuation hardening advances the shared plan/execution
codec to strict version 5, requires an exact bounded byte high-water on every
execution set, and refuses versions 1-4 rather than resetting a resumed task's
aggregate bar. Stage 6 checkpoint 2 then keeps plan payload v5 and advances only
the process-local execution payload to exact v6 for sparse recording reasons,
ordered task issues, and transient attestation consistency; execution payload
v5 is refused. Inventory request payloads advance to version 2 for recursive
subtree scope. The independent standalone-integrity continuation also advances
to strict version 2 to retain its physical-read total high-water and aggregate
recording status; the shared validator remains kind-aware rather than treating
either number as a global workflow-schema version.

The payload round-trips the fingerprinted
`SyncOptions.propagate_source_casing` seam as a required field. A payload that
omits a fingerprint input is rejected instead of decoding to false and
re-encoding into a different payload. Stage 5 exposes the complete semantic
snapshot through primitive service read/partial-commit views, but adds no
settings CLI command. Whatever interface commits the source-casing choice,
review and commitment bind it rather than letting execution reinterpret
filename spelling.
The interface-facing `PlanOperationView` retains `prior_target_path` separately
from source and planned target paths. Review adapters use it as the displayed
origin for recase, move, and move-update rows, so the target-side rename is not
lost while translating the immutable core plan into a presentation model.
Workflow JSON keeps valid-Unicode bytes stable and backslash-escapes an
unpaired surrogate defensively, matching plan, ledger-hash, and history
serialization without weakening path validation. Decoding rejects duplicate
object keys and the nonstandard numeric constants `NaN`, `Infinity`, and
`-Infinity`; no payload may acquire a non-finite value through Python's
otherwise-permissive JSON parser.

M0 automatically selects the maximal safe dependency-closed subset. Directly
blocked items remain in the reviewed plan as `BLOCKED`; operations touching
their source/target correspondence region or depending on an exclusion become
`DEFERRED`. If either scan is incomplete, `move`, `move_update`, `trash`, and
`delete` are withheld globally because absence and identity correspondence are
not proven, while `copy`, `update`, `mkdir`, and guarded `noop` remain eligible.
The commitment digest binds this derived selection and fresh preflight enforces
the same safety envelope if another caller supplies a different selection.

Workflow emits excluded items after execution settles and merges them into the
terminal result without rewriting successful filesystem status. Blocked intent
never writes the main ledger; selected no-ops still execute their live guard and
refresh source/target correspondence. Direct user deselections emit `SKIPPED`
with reason `user-deselected`; dependency fallout stays `DEFERRED`, so retained
history can reconstruct the same classification without guessing. Durable plan
files, queue release, linked verification, and integrity workflows were not
part of the implemented M0 slice. Stage 3 now implements the standalone
inventory/integrity half without changing that M0 execution boundary; Stage 5.5
now supplies the workflow semantics for process-local user selection editing,
with service exposure completed by the facade integration.

Stage 4 linked verification deliberately does not build its immediate candidate set
from inventory rows. The execution continuation retains each successfully
published operation's post-publish attestation plus its complete recorded
identity, or no identity only when the same operation carries
`record-write-failed`, then turns those values into transient verifier
candidates. This survives an in-process pause because evidence, recording
attribution, task issues, and aggregate byte high-water are encoded beside
execution status;
neither the continuation nor process-local plans survive closing/restarting
the M1 application. Later standalone integrity sessions use durable ledger
evidence.

The implemented compound transition rules are explicit:

```text
execute
  pause  -> snapshot status + item/task recording truth + evidence + byte high-water
  cancel -> typed terminal canceled; preserve recording truth; start no readback
  settle -> when requested, enter verify for candidates or missing-evidence failures

verify
  pause     -> snapshot candidates + completed ids/bytes
  cancel    -> retain filesystem truth; integrity is canceled/incomplete
  mismatch  -> retain filesystem truth; report integrity finding
  exception -> retain filesystem truth; incomplete verify PhaseResult
  complete  -> settle one compound terminal result
```

Running execute cancellation returns the same typed workflow result whether or
not post-copy verification was requested. It finishes the one ledger run with
the `ExecutionSet`'s current recording axis, so an executor-detected degraded
recording cannot be replaced by the generic runner's default `OK`. It captures
the executor's emitted outcomes, emits plan exclusions, and merges the complete
item result in reviewed plan order. The execute phase summary remains
compound-only; a plain execute cancellation does not invent a
verification-shaped phase.

An escaping ordinary execute exception follows the same authority rule. The
workflow constructs its failed result from the `ExecutionSet`'s settled-item
state, fixed reviewed byte budget, and aggregate byte high-water rather than
asking the generic runner to reinterpret the latest lossy Progress snapshot.
Fresh commitment or preflight failure/cancellation does the same before the
executor or run recording opens, retaining `UNRUN` disposition and the
phase-free result shape while still reporting the reviewed byte budget.
Plain execution retains its phase-free result shape; linked execution adds the
execute phase summary. Failure to enter the run-recording context likewise
returns continuation-derived counters with degraded recording, while a context
exit failure is secondary to an already-computed filesystem/result truth and
degrades recording without replacing that truth. Cooperative control and
`BaseException` causes still escape; a secondary context-exit failure is noted
without replacing them. If that happens while pausing, the active execute or
verify continuation is first degraded and recaptured, so paused cancellation
or resume cannot recover an `OK` aggregate from the failed recording owner.
During linked verification, the phase summary counts
successfully emitted reliable outcome identities as a floor, so a later
continuation-bookkeeping failure cannot erase an already-published settlement.
Executor advances operation status, recording reason, and transient evidence
only after reliable item emission returns; a sink failure therefore leaves no
continuation-only settlement. Candidate completion follows the same ordering.

Fresh preflight still runs on every resume. If an already-started execute
continuation is refused or faults there, workflow reopens the same run only to
finish it as `FAILED+RAN`, with settled execute counters preserved; it never
claims a fresh `REFUSED+UNRUN`. A verify-resume preflight refusal preserves the
settled execute filesystem status and adds a zero-work incomplete verify phase.
All terminal paths after recorder entry share one finish-once boundary.
`PauseRequested`, `KeyboardInterrupt`, `SystemExit`, and other
`BaseException` subclasses are not normalized into a workflow failure.
`PauseRequested` or `Canceled` raised by the recording factory or its entry
boundary likewise remains a control transition: pause escapes for custody
snapshotting, while cancellation projects authoritative continuation counters
without reopening the recording factory or consulting lossy Progress.
A resumed execution canceled at the dispatcher's entry checkpoint is settled
from its retained payload before `invocation.run()`, so the same finish-once
ledger boundary runs. Once that exact cancellation settlement is elected, its
validated process-local start claim is released in `finally` even if recorder
open throws or finalization degrades.

## Integrity Workflow

Inventory, baseline, verify, and rebaseline are location-centric,
not plan- or mapping-dependent. The workflow resolves or registers one selected
location, re-resolves its volume identity at start/resume, performs full or
selected refresh, commits inventory, constructs canonical selection, runs the
integrity module with the required XXH3-128 factory, flushes recorder, and
returns inventory plus nominal phase-tagged outcomes. Missing inventory is
created automatically; the user is not told to run a hidden prerequisite
manually.

Resolution carries the current sole selected mount even when a stable volume
has moved from its stored hint. The scan and every subsequent verifier open are
bound by an ephemeral `RootAuthority` built from the fresh resolution's logical
root, selected mount, and the location's full stable `VolumeId`, so a remount
between refresh and hashing cannot be recorded under the old location
authority. Post-copy verification instead derives the same contract from the
committed plan target root, its optional reviewed device anchor, and target
volume identity; neither workflow persists the authority in a continuation.
Before the scan, inventory uses that resolver-selected mount in core's
chain-only admission and then performs its existing accessibility probe; it
does not add a second volume observation or move ambiguity policy into core.

Scope has three semantic shapes: `FULL`, exact `PATHS`, and recursive
`SUBTREES`; mixed requests canonicalize overlapping roots and selecting the
location root becomes `FULL`. Exact refresh reconciles only named rows.
Completed subtree refresh reconciles every indexed descendant using a literal
canonical-path range, while full refresh reconciles the whole location. These
are separate recorder branches, not a two-valued full/selected shortcut.

Folder verification resolves an opaque location-scoped node id to a canonical
path and freezes all eligible indexed descendants independently of the current
filter/window. An unreadable frozen subject emits a visible `unsupported`
integrity result, makes verification incomplete, and does not suppress eligible
siblings. Non-subject-specific incompleteness still refuses before hashing. UI
receives refreshed inventory and typed scan warnings at the scan-to-hash
handoff so it never shows stale/empty or falsely complete state during work.

Baseline, verify, and rebaseline register pause support. Their continuation
retains the exact admitted candidate ids plus completed ids/bytes; resume
freshly inventories and guards those remaining rows without adding a newly
appeared row. Inventory and plan register pause unsupported and remain
cooperatively cancelable. The production interface registry contains all six
current workflow kinds, and the CLI reaches each through the shared service.

After integrity selection, running cancellation or ordinary failure derives
terminal item and byte counters from that live continuation rather than the
latest lossy Progress snapshot. Canceling a paused baseline, verify, or
rebaseline session decodes and settles the exact stored continuation without
reopening the workflow. Its strict v2 payload persists `processed_bytes`, the
nondecreasing physical-read `bytes_total_high_water`, and one-way aggregate
`recording`; a resumed invocation or paused cancellation cannot regress those
axes. The byte pair measures attempted physical work rather than durable
publication, while accumulated reliable outcomes and recorded evidence remain
the independent settlement and durability authority. The same request-level
`FAILED+RAN` projection applies if resumed volume resolution is offline or
ambiguous, its refresh is incomplete, or recorder setup fails before
`IntegritySelection` can be reconstructed. Fresh resolution refusal remains
`REFUSED+UNRUN`; a fresh incomplete refresh remains `FAILED+RAN` with zero work
counters.

Frozen resume selection does not materialize the location's complete inventory:
the workflow extracts canonical location-owned row IDs and asks the repository
for 400-ID chunks under one read snapshot, then restores the original admitted
order. Malformed, foreign-location, or missing saved IDs refuse resume instead
of broadening it. A stale-before run consumes the repository's stale query
directly and fetches only exact already-completed rows needed for settlement.
Explicit selected-path and intentional full Verify All behavior are unchanged.

Candidate filtering happens only while freezing a new integrity selection.
Baseline admits eligible non-directory rows with no attestation; rebaseline
admits eligible rows that already have an attestation; verify retains both,
including null-attestation rows that must establish evidence and report
verification-incomplete. When a continuation already carries
`selection_item_ids`, resume reconstructs that exact ordered set without
reapplying mode filters. Completed ids/bytes and the original admitted order
therefore survive even if evidence changes after admission. A repeat full
baseline still performs
its required fresh inventory recording, but hashes and writes no integrity
attestation when every eligible row already has evidence.

## Other Workflows

- History browsing is read-only and runs alongside mutating sessions.
- Replay reconstructs scope from retained detail and plans fresh.
- Undo/repair generates an ordinary plan and mandatory review.
- Database backup/check/export/import are typed maintenance sessions; app-owned
  mutation remains guarded/history-logged.
- Ingest follows [INGEST.md](INGEST.md) and the same two-session review boundary.
- Queue wakeup starts only an already reviewed/authorized execution set and
  freshly preflights; silent replan is forbidden. Contending commitments retain
  commit order, while disjoint-volume work may run concurrently.

## Error And Result Aggregation

Workflow catches typed module failures at the correct boundary, preserves
already-earned item/filesystem results, and lets the generic session runner
produce terminal. Filesystem, integrity, ledger `recording`, and history
`audit` statuses are independent. A verify-phase mismatch or exception never
rewrites successful execution; a ledger failure never suppresses byte
classification; a history failure/timeout degrades only `audit`. A contained
history receipt rejection also degrades audit while the observer continues to
record later events and terminal truth; an observer exception breaks the
prefix. The runner
drains and finalizes history first, settles the audit axis through the atomic
caller/pump ownership decision and actual pump outcome, and only then releases
the immutable Terminal.

Execution and integrity outcomes implement one nominal `ResultItem` contract
with explicit `item_type` and `phase` tags. Standalone Stage 3 sessions write
their ordered integrity items but no `history_phases` rows. Compound sessions add generic
`PhaseResult` summaries so a compound phase-wide failure before its first item
is not mistaken for empty success; transfer and readback byte counts remain
separate rather than being summed.

Result views keep the specific integrity axis visible. A hash mismatch receives
the higher `mismatch` headline; missing, modified/stale, unsupported, canceled,
or error items mean verification did not complete cleanly and cannot be
presented as success. A null-baseline item discovered during `phase=verify`
also receives `verification-incomplete` because it established a baseline
without performing a comparison; the same `baselined` result is successful in
an explicit baseline/rebaseline phase. One workflow-owned classifier applies
the exact precedence `failed > partial > refused > mismatch > canceled >
verification-incomplete > recording/audit degradation > all-noop > success`.
Live and reopened history views reuse it, while every lower-priority axis
remains independently renderable.

Live `all-noop` classification reconstructs effective selected kinds from item
kind plus the stable typed exclusion-reason set; excluded rows remain visible
but cannot make skipped non-noop work look like a selected no-op. The
current retained-history path reconstructs the same classification from
persisted item kind/outcome/reason, including `user-deselected`, after loading
the retained detail objects. Stage 6 replaces that summary path with grouped
SQL aggregation over those primitive columns and database-paged detail in
stable `item_order`; phase summaries remain whole.

Workflow result byte counters retain the central attempted-work meaning from
`ARCHITECTURE.md` §2.3. The execute projection uses its fixed reviewed budget
and aggregate high-water even when some streamed bytes were rolled back before
publication; standalone integrity uses physical-read work and its final
nondecreasing budget. A compound result exposes those domains in separate
phase summaries and projects execute at the top level rather than summing
copy and verification. Consumers must use reliable item outcomes, published
evidence, and ledger state—never the byte high-water—to infer durable content.

Paused compound execution continues from an explicit discriminated
continuation after fresh preflight. `phase=execute` carries execution status
and published evidence; `phase=verify` carries `PostCopySelection`'s transient
candidates plus completed ids/bytes, settled filesystem status, the execute
phase, compound-current recording, and ordered missing-evidence ids. Its phase
projection reconstructs the verifier's nondecreasing physical budget as
reviewed admission plus abandoned-attempt work and completed-stream overrun,
so terminal or resumed summaries cannot regress below emitted Progress. Frozen
`ExecutionSet.recording` remains execution truth; compound-current recording
may degrade later but cannot recover `DEGRADED` to `OK`. Resume never infers
phase from prior events or re-emits a completed reliable result. The compound
run's recorder may close at pause-drain and reopen the same token idempotently
on resume; it attempts finalization once after both entered phases settle, and
a finish failure degrades recording. Paused standalone
baseline/verify/rebaseline already use their exact candidate and item-status
continuation plus fresh remaining-selection guard. Unsupported pause requests
for inventory/plan/import are typed control rejections with no lifecycle
mutation.

The continuation is process-local custody state, not a durable recovery
format. `InMemorySessionStore.load_all()` deliberately returns no sessions;
closing the process offers no execute/verify resume. Exact active/accepted
payload versions are centralized in [M1_BRIDGE.md](M1_BRIDGE.md).
Splitting standalone-integrity continuation payloads is deferred: its exact v2
candidate/completed/authority payload remains until a named late-run pause
reserialization benchmark over large `completed_bytes` demonstrates that it
misses the bridge pause-latency budget.

Refusal is distinct from failure and has zero managed-data mutation. Partial
failure derives from item outcomes, not merely whether any bytes moved. An
all-noop explicit run is completed/no-op and still history-worthy. A safe-subset
run can be filesystem `COMPLETED` with itemized `BLOCKED`/`DEFERRED` exclusions;
interfaces present that as partial completion rather than clean full success.
An all-skipped review refuses before admission because it contains no executable
work; it is not an all-noop run.

## Orthogonality Rules

- Planning preview does not create mappings or persist deletion policy.
- Plan invalidation does not clear inventory evidence.
- Inventory refresh does not rewrite attested baselines.
- Verification does not mutate plans or mark unverified noops.
- History does not record ledger truth or control work.
- UI choice does not alter workflow semantics.
- UI filtering/windowing does not alter folder scope, selection, or integrity
  candidate membership.
- Ingest source temporariness does not create role-bearing location state.

## Expectations

- Modules are callable and never import each other.
- Repositories return immutable snapshots and recorder is sole ledger writer.
- Dispatcher treats request/result as opaque and owns custody/control.
- Interfaces submit typed requests and present events/results; no interface
  reaches around workflow to call executor/SQL.
- Settings shaping a plan are snapshotted, not read opportunistically later.
- Fresh preflight observes filesystem/volume safety only; it never compares
  admitted intent with newer global defaults.

Workflow is the sole preflight owner: it sequences fresh observe → preflight →
scoped prior-run temp recovery → execute under custody on every start/resume.
Executor imports no sibling and performs only operation-local live precondition
guards.

## PoC Hardening

This sequencing prevents the unwired ledger, preview side effects, no-inventory
baseline/verify failure, target-role fallback, full refresh for selected verify,
missing integrity audit on unexpected exceptions, stale plan/inventory display,
and view-wide false verification scope. A common guard envelope prevents hash
import from handling refusal differently than baseline/verify.

## Acceptance Criteria

- Workflow source reads visibly top-to-bottom and contains no signal loop,
  domain operation implementation, raw SQL, or UI import.
- Plan session persists no mapping/settings/user-data mutation and releases all
  custody before review.
- Planning reads semantic defaults exactly once; an explicit deletion override
  retains every other stored option, and later settings changes cannot alter
  the reviewed/committed execution.
- Execution always uses the exact reviewed plan/selection, fresh observation,
  and preflight; drift refuses without mutation.
- Payload round trips retain every fingerprint input and reject duplicate keys,
  invalid Unicode, and all nonstandard non-finite numeric constants before
  constructing a workflow request.
- A blocked item cannot refuse independent safe work merely by existing in the
  plan; its overlapping target correspondence and dependent operations remain
  excluded.
- Incomplete scans allow guarded copy/update/mkdir/noop/recase work but never
  admit move, move-update, trash, or delete operations.
- No workflow waits for human input; mandatory review is between terminated and
  newly submitted sessions.
- An uncommitted execution or one whose plan/selection no longer matches is
  refused before preflight; queue/script paths can replay but never mint a
  commitment without human review.
- Baseline/verify with no prior inventory automatically inventories then hashes;
  exact selected verify refreshes exact canonical paths, while a selected
  folder refreshes and freezes its complete indexed subtree regardless of the
  active UI filter/window.
- Fresh baseline selects only rows lacking evidence, fresh rebaseline selects
  only rows with evidence, and resume preserves the exact frozen selection
  without reapplying either mode filter.
- Location integrity requires only the selected location and never silently
  falls back to another root.
- Refusal, all-noop, partial failure, cancel, recorder failure, observer failure,
  and unexpected exception each preserve truthful typed results and history
  behavior.
- Execution re-derives selection from plan safety plus canonical
  `user_deselected`, rejects a mismatched carried selection, refuses
  all-skipped, and still admits selected guarded no-ops.
- Full, exact-path, and subtree scans take distinct reconciliation branches;
  subtree missing marking covers descendants with a wildcard-free indexed
  prefix range and never treats only the subtree root as selected.
- Pause/resume preserves completed execution and verifier-item outcomes and
  fresh-guards remaining work; scan/plan/import refuse pause without losing
  cancelability. The open mid-operation UPDATE/MOVE_UPDATE durable-sub-step
  limitation is documented in `EXECUTOR.md` and `BUGS.md`; this guarantee does
  not yet cover that boundary.
- Linked verify candidates equal successful byte-producing publishes and are
  derived from `PublishedCopyEvidence`, including copies whose ledger write
  degraded. The execution-to-verification boundary exposes refreshed phase
  state to the UI without releasing volume custody.
- Under uninterrupted event continuity, every emitted `Progress.phase` agrees
  with the latest reliable `PhaseChanged.phase`; execute, standalone integrity,
  and linked post-copy workflow integration tests own that producer assertion.
  After a `Gap`, the browser reducer—not workflow inference—owns acceptance of a
  later self-described Progress domain.
- Linked verification derives one items admission and physical-read budget from
  the complete `VerifyContinuation` before invoking the reporter. Operations
  with missing publication evidence remain in those Progress totals even though
  only evidence-backed candidates can enter the byte reader; pause/resume and
  the terminal verify phase reuse the same continuation authority.
- Pause during either compound phase resumes from the explicit phase
  discriminator without losing published evidence, repeating completed
  outcomes, or claiming survival across an application restart.
- Compound results preserve one ordered heterogeneous item list, separate
  phase byte counters, and independent filesystem, integrity, recording, and
  audit axes.
- Replay/undo/repair never execute retained historical operations directly and
  always create a new reviewed plan.
- A lower-level plan-only option change invalidates that direct caller's plan
  while preserving unrelated inventory. The H2 desktop never mutates or
  replaces a published task plan: changed options or locations create a new
  planning task, while the old task remains immutable until close.
- Import-linter proves workflows may import core/modules/db but not dispatcher
  or interfaces.
