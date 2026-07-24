# Workflows Module

Status: M0 reviewed sync and history are implemented, with M1 Stage 1's
immutable admitted-policy and payload-v2 contract. M1 inventory/integrity,
linked post-execution verification, facade/CLI expansion, and desktop shell are
specified but not implemented. Queue durability, maintenance/retention, replay,
undo/repair, and ingest remain later work.

## Purpose

Workflows are plain top-to-bottom functions and the only place operation modules
meet. They translate a typed request into sequential calls, pass immutable
outputs forward, aggregate filesystem/recording/history-aware results, and
declare required resources to dispatcher. They do not implement scan/diff/copy/
hash/SQL/UI behavior and never coordinate through signals or callbacks-for-
control.

Every runtime dependency arrives through one composition-root `deps` object:
clock, scanner/change source, repositories, planner/policies,
observer/preflight, executor, recorder, and later verifier/importer. Planning
adapters may snapshot semantic defaults when constructing a request; admitted
execution does not receive or reread a settings provider.

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
3. Consume the immutable semantic snapshot bound into the reviewed plan; never
   reread global defaults to decide admitted filesystem behavior.
4. Freshly observe/preflight filesystem and volume state under execution
   custody; refusal mutates nothing.
5. After a successful verdict, remove exact prior-run temps once from the
   observed touched-target-parent scope; cleanup failure stops before executor
   admission, so capacity credited by preflight cannot become unsafe.
6. Execute selected dependency-closed work and record through recorder. Settle
   each successful `COPY`, `UPDATE`, or `MOVE_UPDATE` status together with its
   `PublishedCopyEvidence`; a byte-producing success without evidence is an
   internal incomplete-verification error.
7. If requested and at least one eligible publish succeeded, continue inside
   the same session and volume custody into post-execution verification.
   Construct transient candidates from published evidence, not from a ledger
   query, so readback still runs when copy-ledger recording degraded.
8. Finish the one logical recorder invocation and return one compound result:
   ordered phase-tagged execution/integrity items, phase-local progress, and
   independent filesystem, integrity, ledger-recording, and audit axes.

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

Stage 1 advances the opaque plan/execution codec to version 2 and removes
`worker_count` from `SyncOptions`, `Plan`, fingerprints, and both payloads
without adding a replacement execution setting. Version-1 workflow payloads
are refused instead of being guessed into the changed contract.

The payload round-trips the fingerprinted
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
part of the implemented M0 slice.

M1 linked verification deliberately does not build its immediate candidate set
from inventory rows. The execution continuation retains each successfully
published operation's post-publish attestation and copy-recording disposition,
then turns those values into transient verifier candidates. This survives an
in-process pause because the evidence is encoded beside execution status;
neither the continuation nor process-local plans survive closing/restarting the
M1 application. Later standalone integrity sessions use durable ledger evidence.

Compound transition rules are explicit:

```text
execute
  pause  -> snapshot operation status + published evidence
  cancel -> terminal canceled; do not start new readback work
  settle -> enter verify only when requested and candidates exist

verify
  pause     -> snapshot candidates + completed ids/bytes
  cancel    -> retain filesystem truth; integrity is canceled/incomplete
  mismatch  -> retain filesystem truth; report integrity finding
  exception -> retain filesystem truth; incomplete verify PhaseResult
  complete  -> settle one compound terminal result
```

## Integrity Workflow

Inventory, baseline, verify, and rebaseline are location-centric,
not plan- or mapping-dependent. The workflow resolves or registers one selected
location, re-resolves its volume identity at start/resume, performs full or
selected refresh, commits inventory, constructs canonical selection, runs the
integrity module with the required XXH3-128 factory, flushes recorder, and
returns inventory plus nominal phase-tagged outcomes. Missing inventory is
created automatically; the user is not told to run a hidden prerequisite
manually.

Selected verification uses scoped refresh. Full verify uses a complete location
scan before missing marking. UI receives refreshed inventory at the scan-to-hash
handoff so it never shows stale/empty rows during work.

Verify and baseline register pause support and retain per-item status so resume
freshly guards only the remaining selection. Scan and plan register pause
unsupported and remain cooperatively cancelable.

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
classification; a history failure/timeout degrades only `audit`. The runner
drains and finalizes history first, settles the audit axis from its bounded
acknowledgement, and only then releases the immutable Terminal.

Execution and integrity outcomes implement one nominal `ResultItem` contract
with explicit `item_type` and `phase` tags. Entered phases also produce generic
`PhaseResult` summaries so a phase-wide failure before its first item is not
mistaken for empty success. Transfer and readback byte counts remain separate;
they are never summed into a misleading doubled total.

Paused execution continues from an explicit discriminated continuation after
fresh preflight. `phase=execute` carries execution status and published
evidence; `phase=verify` also carries transient candidates plus completed
verification ids/bytes. Resume never infers phase from prior events or re-emits
a completed reliable result. The compound run's recorder may close at
pause-drain and reopen the same token idempotently on resume; it finalizes the
logical sync only once after both entered phases settle. Paused standalone
baseline/verify use their item-status continuation and fresh
remaining-selection guard. Unsupported pause requests for scan/plan/import are
typed control rejections with no lifecycle mutation.

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
- Linked verify candidates equal successful byte-producing publishes and are
  derived from `PublishedCopyEvidence`, including copies whose ledger write
  degraded. The execution-to-verification boundary exposes refreshed phase
  state to the UI without releasing volume custody.
- Pause during either compound phase resumes from the explicit phase
  discriminator without losing published evidence, repeating completed
  outcomes, or claiming survival across an application restart.
- Compound results preserve one ordered heterogeneous item list, separate
  phase byte counters, and independent filesystem, integrity, recording, and
  audit axes.
- Replay/undo/repair never execute retained historical operations directly and
  always create a new reviewed plan.
- Plan-only option changes invalidate plan but preserve inventory; location
  changes invalidate only state whose identity depends on that location.
- Import-linter proves workflows may import core/modules/db but not dispatcher
  or interfaces.
