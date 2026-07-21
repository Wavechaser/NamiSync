# Workflows Module

Status: M0 reviewed sync and history implemented. M1 inventory/integrity/import
and later queue, maintenance, replay, undo/repair, and ingest remain deferred.

## Purpose

Workflows are plain top-to-bottom functions and the only place operation modules
meet. They translate a typed request into sequential calls, pass immutable
outputs forward, aggregate filesystem/recording/history-aware results, and
declare required resources to dispatcher. They do not implement scan/diff/copy/
hash/SQL/UI behavior and never coordinate through signals or callbacks-for-
control.

Every dependency arrives through one composition-root `deps` object: clock,
scanner/change source, repositories, planner/policies, observer/preflight,
executor, recorder, verifier/importer, and settings snapshots.

## Reviewed Sync

### Plan session

1. Validate distinct non-nested roots and request semantics.
2. Resolve volume/location/mapping evidence without persisting preview-only
   configuration.
3. Scan both roots with the same role-free observation contract.
4. Read immutable prior correspondence and semantic settings snapshot.
5. Apply filters/policies and plan.
6. Derive the deterministic safe selection: retain additive/no-op work, mark
   direct blockers `BLOCKED`, quarantine overlapping/dependent work as
   `DEFERRED`, and withhold destructive/identity moves when either scan is
   incomplete.
7. Observe/preflight that exact selection for review information.
8. Return immutable serializable plan/verdict; terminate and release locks.

### Execution session

1. Accept only an explicit `Commitment` whose plan fingerprint and selection
   digest match the reviewed `ExecutionSet`; refuse before preflight otherwise.
2. Reacquire required physical-volume custody.
3. Load current semantic environment without altering the reviewed snapshot.
4. Freshly observe/preflight under execution custody; refusal mutates nothing.
5. After a successful verdict, remove exact prior-run temps once from the
   observed touched-target-parent scope; cleanup failure stops before executor
   admission, so capacity credited by preflight cannot become unsafe.
6. Execute selected dependency-closed work and record through recorder.
7. Optionally start a separately scoped linked verification phase/session as
   specified by the request.
8. Return truthful filesystem, ledger-recording, audit, and verification
   aggregates with independent axes.

Human review occurs between sessions with nothing running. Commitment is the
durable preauthorization and has no time expiry, but it binds exactly one plan
fingerprint and dependency-closed selection. Scripts and queue releases may
replay an existing commitment; no API plans and executes in one unreviewed
breath.

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
Execution recomputes the decoded plan fingerprint before comparing commitment,
so payload content cannot change behind a retained fingerprint. This makes
lossless payload encoding a correctness invariant, not a convenience: every plan
field that feeds the fingerprint must survive the JSON codec unchanged, or
execution refuses a faithfully committed plan. A round-trip/fingerprint-stability
test exercises the codec over every operation kind and optional field, so a
dropped or renormalized field fails the build instead of silently refusing every
execution.

The payload also round-trips the fingerprinted
`SyncOptions.propagate_source_casing` seam as a required field. A payload that
omits a fingerprint input is rejected instead of decoding to false and
re-encoding into a different payload. M0 exposes no config, CLI, or GUI control
for it; when a future interface does, review and commitment will already bind
the choice rather than letting execution reinterpret filename spelling.
The interface-facing `PlanOperationView` retains `prior_target_path` separately
from source and planned target paths. Review adapters use it as the displayed
origin for recase, move, and move-update rows, so the target-side rename is not
lost while translating the immutable core plan into a presentation model.
Workflow JSON keeps valid-Unicode bytes stable and backslash-escapes an
unpaired surrogate defensively, matching plan, ledger-hash, and history
serialization without weakening path validation.

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
refresh source/target correspondence. Durable plan files, user selection
editing, queue release, linked verification, and integrity workflows are not
part of this implementation slice. When linked verification lands, its
selection is built ledger-first from the inventory rows execution just
recorded, not handed over from the executor, which surfaces only op-level
outcomes.

## Integrity Workflow

Inventory, baseline, verify, rebaseline, and hash import are location-centric,
not plan- or mapping-dependent. The workflow resolves one selected location,
performs full or selected refresh, commits inventory, constructs canonical
selection, runs the integrity module, flushes recorder, and returns inventory
plus typed outcomes. Missing inventory is created automatically; the user is
not told to run a hidden prerequisite manually.

Selected verification uses scoped refresh. Full verify uses a complete location
scan before missing marking. UI receives refreshed inventory at the scan-to-hash
handoff so it never shows stale/empty rows during work.

Verify and baseline register pause support and retain per-item status so resume
freshly guards only the remaining selection. Scan, plan, and hash import register
pause unsupported and remain cooperatively cancelable.

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
produce terminal. Filesystem-derived `SessionState`, ledger `recording`, and
history `audit` statuses are independent. A history failure/timeout degrades
only `audit`. The runner drains and finalizes history first, settles the audit
axis from its bounded acknowledgement, and only then releases the immutable
Terminal.

Paused execution continues from `ExecutionSet.status` after fresh preflight.
Paused baseline/verify use their item-status continuation and fresh remaining
selection guard. Unsupported pause requests for scan/plan/import are typed
control rejections with no lifecycle mutation.

Refusal is distinct from failure and has zero managed-data mutation. Partial
failure derives from item outcomes, not merely whether any bytes moved. An
all-noop explicit run is completed/no-op and still history-worthy. A safe-subset
run can be filesystem `COMPLETED` with itemized `BLOCKED`/`DEFERRED` exclusions;
interfaces present that as partial completion rather than clean full success.

## Orthogonality Rules

- Planning preview does not create mappings or persist deletion policy.
- Plan invalidation does not clear inventory evidence.
- Inventory refresh does not rewrite attested baselines.
- Verification does not mutate plans or mark unverified noops.
- History does not record ledger truth or control work.
- UI choice does not alter workflow semantics.
- Ingest source temporariness does not create role-bearing location state.

## Expectations

- Modules are callable and never import each other.
- Repositories return immutable snapshots and recorder is sole ledger writer.
- Dispatcher treats request/result as opaque and owns custody/control.
- Interfaces submit typed requests and present events/results; no interface
  reaches around workflow to call executor/SQL.
- Settings shaping a plan are snapshotted, not read opportunistically later.

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
- Execution always uses the exact reviewed plan/selection, fresh observation,
  and preflight; drift refuses without mutation.
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
  selected verify refreshes only selected canonical paths.
- Location integrity requires only the selected location and never silently
  falls back to another root.
- Refusal, all-noop, partial failure, cancel, recorder failure, observer failure,
  and unexpected exception each preserve truthful typed results and history
  behavior.
- Pause/resume preserves completed execution and verifier-item outcomes and
  fresh-guards remaining work; scan/plan/import refuse pause without losing
  cancelability.
- Linked verify selection equals successful eligible executed operations and is
  handed to UI at the execution-to-verification phase boundary.
- Replay/undo/repair never execute retained historical operations directly and
  always create a new reviewed plan.
- Plan-only option changes invalidate plan but preserve inventory; location
  changes invalidate only state whose identity depends on that location.
- Import-linter proves workflows may import core/modules/db but not dispatcher
  or interfaces.
