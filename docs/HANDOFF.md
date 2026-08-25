# Session Handoff

Status (2026-08-26): independent review remediation checkpoint 3R.0 is complete
in `M1_SHELL_H2.md`. The checkpoint 3.2 runtime is unchanged, checkpoint 3.3
has not started, and its legacy-removal commit is blocked until the ordered
3R.1–3R.15 sequence closes and S5 receives a user-approved disposition.

## Delivered

- Added the interstitial 3R sequence as 16 serviceable commits: one ratification
  row, fourteen independently reviewable remediation boundaries, and one
  integrated documentation/evidence closure. Every row requires a distinct
  builder/reviewer handoff, exact staged-snapshot review, focused gates, and a
  clean commit before later-row work enters the snapshot.
- Mapped every Reviewer O/S finding at the aspect level. Executor settlement,
  workflow projection, exact-v5 semantics, live bridge custody, database-pair
  admission, and file-identity codecs remain inside the existing architecture
  and checkpoints 1–3.2.
- Left Reviewer S5 outside the authorized sequence. The current
  `SessionStore.put/load_all/drop` contract cannot guarantee terminal scrub
  after its own mutator fails. Dispatcher-owned process memory with redacted
  persisted records, a stronger atomic store contract, and separately revocable
  protected continuation storage remain explicit alternatives for user choice.
- Retained the appended independent review reports below as the active detailed
  finding source until remediation closure.

## Safe Stop

This checkpoint changes documentation only. All authorized production and test
defects remain open until their named 3R row lands, while S5 remains on design
hold; no prior green evidence is treated as rebutting the reproduced
counterexamples. The unreachable private v3/v4 decoder seam remains in source
for checkpoint 3.3 and must not be removed or widened during remediation.

The working tree is expected to be clean after the named 3R.0 commit. No
generated artifact, settlement baseline, normalized trace, or protected hash
change belongs to this checkpoint.

## Verification

- Two independent reviewers iterated on the exact plan/handoff snapshot. Their
  findings corrected ordering, cause precedence, persistent-sink truth,
  checkpoint isolation, database WAL/journal handling, timestamp grammar,
  public-contract consumer gates, S5 closure, and handoff lifecycle.
- Both final stable-snapshot read-only passes reported `CLEAN`. The retained raw
  reviewer-report tail is byte-identical to HEAD.
- `git diff --check -- docs/M1_SHELL_H2.md docs/HANDOFF.md` passes. No runtime
  test is credited to this documentation-only checkpoint.

## Immediate Next Context

Start only checkpoint 3R.1, `test(executor): restore settlement gate authority`.
First inventory the clean tree and reread 3R's execution protocol, ownership
map, and 3R.1 acceptance. Keep the frozen normalized trace, baseline JSON,
scenario/row manifest, and semantic hash unchanged; add the typed oracle-only
side channel and fail-closed seven-case catalog, repair the reducer assertion,
and leave execution-v6 codec coverage to 3R.2. Run the named focused/departments
and three-run oracle gates, obtain an independent exact-diff review, refresh
this handoff, and commit before starting 3R.2.

## Reviewer O.

Independent adversarial review of checkpoints 1-2 (`4c3b5ea`, `df86150`,
`0e14b32`), conducted read-only against extracted trees at `4c3b5ea`,
`0e14b32`, and `HEAD`. Findings are ordered by severity; every claim below was
reproduced by execution rather than inference. Checkpoint 3 and later event-v5
work were out of scope.

### F1. Recorder-flush refusal is erased from the recording axis (HIGH, open)

When `_flush_before_destructive` refuses a destructive operation *and* the
owned-temp cleanup also fails, the run reports `recording=ok`.
`_settle_ordinary_failure` in `modules/executor/runtime.py` replaces the caught
exception with a fresh `OperationFailure(CLEANUP_FAILED, ...)`, and the
recording reason rides on a dynamic attribute (`failure._recording_reason`, set
in `_flush_before_destructive`, read by `getattr` in `_settle_failure`), so the
substitution drops it. Before checkpoint 2 this was impossible because
`_flush_before_destructive` set `state.recording = DEGRADED` before raising.

Reproduction: one UPDATE, recorder fails the first flush only, filesystem fails
`remove_owned_temp` on the staged temp.

| revision | `result.recording` | `recording_reasons` | `recording_issues` |
| --- | --- | --- | --- |
| `4c3b5ea` | `degraded` | n/a | n/a |
| `0e14b32` | `ok` | `{}` | `()` |
| `HEAD` | `ok` | `{}` | `()` |

The item settles with reason `cleanup-failed`. The consequence is inverted for
the safety model: the executor refused the destructive step precisely because
the ledger was known to be behind, and the run then reports the ledger clean
through `OperationResult.recording`, CLI `ledger=ok`, and persisted
`recording_status`.

Same root cause, second instance: `_backstop_operation` settles from
`snapshot.retry_error or escaped`, a different exception object. Latent third:
`_settle` returns early when `op_id in xset.status` and discards
`settled.recording_reason`; no reachable path was found, but the pre-checkpoint
`_record()` global degradation made that drop impossible.

The fix is structural rather than a patch: carry the reason as a typed field on
`OperationFailure` preserved across substitution, or attach it to the operation
at refusal time instead of to an exception object the executor freely swaps.

### F2. A moved assertion disabled the reducer policy matrix (MODERATE, open)

In `tests/test_executor_settlement.py`,
`test_effect_settlement_reducer_policy_matrix` re-indented
`assert actual == expected, name` from the outer loop body into the `else:`
branch. When `_reduce_effect_settlement` returns `None`, `actual` is `None`,
the `else` is skipped, and nothing is asserted. The lost direction is "this
case must produce a reduction," across roughly twenty matrix cases.

Proven by mutation: making the reducer return `None` whenever there is no
publication verdict passes under the current indentation and fails with
`AssertionError: ordinary-durable` once the assertion is returned to its
pre-checkpoint position. Seventeen sibling end-to-end tests caught that
particular gross mutation, so present blast radius is contained; the unit
matrix is nonetheless the artifact that pins exact per-case policy. A one-line
dedent restores it.

### F3. The oracle projection cannot see production typed attribution (MODERATE, open)

`tools/executor_settlement_audit.py` defines private `_ItemRecordingReason` and
`_TaskRecordingIssueReason` enums, never imports the `core.execution` ones, and
never reads `xset.recording_reasons` or `xset.recording_issues`. It projects
from event-v4 report fields and derives the item reason from the filesystem
outcome (`RECORD_WRITE_FAILED` when the filesystem succeeded, otherwise
`UNRECORDED_MUTATION`); `_ItemRecordingProjection.__post_init__` then validates
the same implication the derivation just applied. The item-reason axis
therefore carries no independent information.

Proven: attaching `UNRECORDED_MUTATION` instead of
`RECORDING_PREREQUISITE_FAILED` in `_flush_before_destructive` (legal in core,
since both require `FAILED`) leaves `oracle` at "passed: 30 scenarios" and
`diff --repeat 3` at "settlement baseline matches"; only pytest
(`test_recorder_flush_failure_blocks_destructive_delete`) catches it.

This is correct for checkpoint 1, where no production field existed to read.
The residual is that checkpoint 2's Tests bullet treats the oracle as the
regression gate for attribution work it structurally cannot observe, and
`TOOLS.md` claims the projection rejects cross-axis combinations that could
relabel a filesystem outcome or assign task degradation to an item. Either
rewire the projection to consume `recording_reasons` at checkpoint 3, or reduce
the `TOOLS.md` claim to what it enforces: aggregate consistency and
presence-of-degradation. The aggregate teeth are real and were confirmed
separately: dropping attribution entirely fails the oracle loudly on
`record.copy-failure` and `recording.sticky-aggregate-degradation`.

### F4-F7. Smaller findings (open)

- **F4, dead guard.** `RuntimeError("settlement reducers disagree on recording
  cause")` in `_reduce_effect_settlement` is unreachable: both reducers' only
  non-`None` reason is `unrecorded-mutation`, so the set holds at most one
  element.
- **F5, self-confirming guard.** `RuntimeError("executor returned unattributed
  recording degradation")` in `workflows/sync.py` compares `result.recording`
  against `xset.recording`, but `RunResult.recording` is built as
  `recording=state.recording`, which is `xset.recording`. It compares two views
  of one derived property, cannot detect attribution loss, and does not fire on
  F1. Only a `deps.executor` double could trip it and no test does, while it
  would crash a path whose filesystem work is already committed.
- **F6, untested decoder guard.** The `execution aggregate recording
  contradicts its item/task attribution` rejection in `workflows/payloads.py`
  has no test; it is the only validation of the redundant on-wire `recording`
  field.
- **F7, documentation drift from F1.** `EXECUTOR.md` states that a
  pre-destructive flush refusal attaches `recording-prerequisite-failed` only
  to the refused operation. In the F1 case it attaches nothing.

### Behavior changes worth an explicit decision (not defects)

- `_finish_existing_recording` now swallows `open_recording` exceptions that
  previously propagated. Both callers are already terminal-failure projections,
  so this is an improvement: a recorder-open failure no longer replaces a
  well-formed failure result with a crash. It is undocumented.
- `run_execution` dropped the verify-phase condition before noting the close
  issue, so the execution set now carries a task issue in the verify-present
  case where it previously stayed OK.
- `preserve_exit_failure` now captures unconditionally. This is required once
  the execution set mutates, so it corrects prior behavior rather than changing
  it arbitrarily.
- Dead store: `recording_status = xset.recording` immediately overwritten in
  `settle_canceled_execution`.

### Confirmed sound

- Checkpoint 1's oracle change is purely additive with zero deletions, so the
  protected scenario/row manifest, normalized trace, baseline JSON, and
  semantic hash pin are provably untouched.
- The identityless-evidence invariant moved from task-global to
  operation-local, which was the point of checkpoint 2 and landed correctly.
- The sink-ordering invariant is real and correctly documented: `_settle` emits
  before touching status, evidence, and recording, and the strengthened
  `FakeRecorder(fail="noop")` case proves a failing recorder plus a rejecting
  sink leaves `recording_reasons` empty.
- Terminal payload scrubbing is fail-closed by construction:
  `SessionRecord.__post_init__` raises rather than leaking, and
  `_transition_locked` scrubs inside the lock before persist and emit, so no
  observer can see a terminal record carrying a payload. Four terminal states
  are parametrized and both record and store are asserted.
- `bounded_recording_detail` correctly guards lone surrogates through
  `UnicodeEncodeError`, and the 513-character accented detail case is a true
  1,026-byte boundary test.
- The plan-v5 / execution-v6 split is correct, `_payload` takes an expected
  version, and the inventory/integrity codecs carry their own constant, so
  nothing was collaterally bumped. `lint-imports`: `11 kept, 0 broken`.

### Disposition

F1 is a policy defect surfaced by adversarial review, so under the checkpoint
execution protocol it lands as a separate commit with a persistent regression,
affected evidence is invalidated, and checkpoint 2's gate reruns from its
declared entry state. F2 travels with it as a one-line dedent. F3 is a
checkpoint 3 decision: rewire the projection or correct the `TOOLS.md` claim,
rather than leave the oracle credited with coverage it does not have.

## Reviewer S.

Independent adversarial review of checkpoints 1-2 (`4c3b5ea`, `df86150`,
`0e14b32`), performed commit-by-commit against the exact historical tree.
Checkpoint 3 and later event-v5 work were excluded except to confirm whether a
checkpoint-2 defect remains reachable. Findings are ordered by severity.

### S1. Reliable emission can revoke a committed recorder receipt (HIGH, open)

`_record()` can commit and return a valid `RecordedCopyIdentity`, but `_settle`
keeps that receipt only in the transient `_Settled` value while it emits the
reliable item outcome. It writes published evidence, status, recording reason,
and journal retirement only after `ctx.emit(event)` returns. If the sink rejects
that outcome, the unexpected-exception backstop re-observes the published file
without the lost receipt and reduces it to `FAILED + UNRECORDED_MUTATION`.

Exact `df86150` reproduction: a seven-byte COPY publishes normally and
`record_copied` commits exactly once, returning a durable identity. The sink
rejects only the first `ItemOutcome` and accepts the backstop item. The target
and recorder row are durable, the original sink `OSError` escapes, but the
accepted item and `ExecutionSet` say `FAILED`, `unrecorded-mutation`, and carry
no published evidence. This violates the locked rule in `RECORDER.md` and
`M1_SHELL_H2.md` that a committed receipt is final and cannot be rewritten by
later task/audit failure.

The existing event-sink regression avoids the counterexample by using NOOP
with `FakeRecorder(fail="noop")`, so no receipt exists to preserve. COPY,
UPDATE, MOVE_UPDATE, and the non-byte recording paths share the vulnerable
settlement order. The receipt must become operation-local retained settlement
state before reliable emission, without marking continuation status settled
until emission succeeds.

### S2. A retained UPDATE retry erases its terminal recording prerequisite
failure (HIGH, open)

`_flush_before_destructive` stores
`recording-prerequisite-failed` on a dynamic exception attribute. Only the
direct failure settler reads it. When a durable-effect reducer supplies the
filesystem settlement, the NOT_PUBLISHED/retained-backup branch creates a new
`_SettlementReduction` with `recording_reason=None` and discards the terminal
cause.

Exact `df86150` reproduction: UPDATE attempt 1 creates a hardlink backup, then
replace raises a sharing violation and policy retries. Attempt 2's
pre-destructive flush fails and policy continues; the final task flush succeeds.
The old target and exact retained backup both remain, and the item is correctly
`FAILED/recorder-failed`, but `ExecutionSet.recording` and the returned result
are `ok`, with empty item reasons and task issues. The recorder trace proves the
failed prerequisite flush.

This is a second reachable form of Reviewer O.'s F1: exception substitution
during owned-temp cleanup loses the same dynamic attribute. The recording
cause must be a typed operation-local input to reduction and survive retries,
cleanup substitution, and durable-effect settlement; it cannot safely ride on
an exception object.

### S3. The checkpoint-1 oracle is not an independent authority for the typed
checkpoint-2 axes (HIGH gate defect, open)

The raw oracle remains deterministic and protected: checkpoint 1 did not alter
the scenario/row manifest, normalized trace contract, baseline JSON, or
semantic hash, and its filesystem, recorder-order, policy, and repeat checks
retain real value. The typed attribution layer does not observe the production
truth added by checkpoint 2, however.

`_execution_set_projection` exports only aggregate `xset.recording`, status,
and evidence. `_recording_projection` reconstructs an item reason from legacy
item outcome/detail and reconstructs final-flush failure from the recorder
trace; it never reads `xset.recording_reasons` or `xset.recording_issues`.
In-memory mutations that changed the production prerequisite reason to
`unrecorded-mutation` and the production final-flush issue to `finish-failed`
still reported `settlement check passed: 30 scenarios x 3 runs`.

The seven-case projection catalog also fails open. `ExpectedSettlement.errors`
uses `_RECORDING_PROJECTION_CASES.get(row)` and silently skips the check if a
case is absent, while `manifest_errors()` does not require the seven labels.
Deleting `recording.final-flush-degradation` in memory left `capture.ok=True`,
`manifest_errors=[]`, and no oracle errors. Only a focused test containing a
second editable literal catches removal, so projection and test can drift
together without the protected baseline or official `check` noticing.

The gate must either compare the declared typed expectations directly with the
authoritative `ExecutionSet` fields and protect the seven-case catalog, or stop
claiming independent attribution coverage. The green oracle does not rebut S1,
S2, or the following fault-path findings.

### S4. Sink failure plus recording-close failure produces terminal
`recording=ok` (HIGH, open)

On the workflow exception path, `finish_once` runs before `_emit_items` emits
excluded outcomes. If that reliable emission raises, the recording context can
also fail on close. `preserve_exit_failure` records
`recording-close-failed` only in the live `ExecutionSet`, then rethrows the sink
exception. `core.session.run_session` constructs a fresh generic failed result
from accepted items; when the sink accepted no degraded item, it derives
`recording=ok`. Dispatcher then correctly scrubs the terminal continuation,
which removes the only exact close witness.

An exact combined probe produced a degraded `ExecutionSet` with the close task
issue, but a published/stored `FAILED + recording=ok` terminal result. The
normal close-failure and normal event-rejection tests exercise the axes
separately. Exceptional exit must project the continuation's task recording
truth into the terminal result before the continuation is discarded.

### S5. A failed terminal store write leaves the old execution-v6 payload
retained (MODERATE security/contract defect, open)

`_transition_locked` correctly builds and publishes an in-memory terminal
record with `payload=None`, but `_persist_locked` swallows every store failure.
If the store accepted admission and rejects every later `put`, its current row
remains the original PENDING record with the opaque execution-v6 continuation
and transient attestations after the session is terminal and shutdown
completes.

The existing `test_later_store_failure_does_not_leak_custody_or_duplicate_terminal`
already constructs exactly that store, but passes it inline and never inspects
the retained row. A direct probe observed the safe terminal dispatcher record
and event alongside the stale payload-bearing store snapshot. This contradicts
`DISPATCHER.md`'s claim that every terminal store view is payload-free and that
attestations cannot survive terminal storage. M0 has no restart durability, so
the present exposure is process-local, but `SessionStore` is also the M2
abstraction and the categorical retention claim is false on its supported
fault path.

### S6. Diagnostic rendering can replace a recorder failure and leave the
recording axis clean (MODERATE, open)

`_recording_error_detail` and the equivalent workflow helper call
`logical_error_text(error)` before storing the typed reason. That helper begins
with unguarded `str(error)`. A recorder exception whose `__str__` raises
therefore escapes the catch path before `FINAL_FLUSH_FAILED`, open, finish, or
close attribution is recorded.

Exact final-flush reproduction: COPY publishes and commits its receipt; final
flush raises a custom exception whose `__str__` raises `ValueError`. The target,
receipt, success status, and evidence remain, but execution raises the renderer
`ValueError` and `ExecutionSet.recording` remains `ok` with no issue. Bounded
diagnostic text is optional; failure to render it must yield `detail=None`, not
erase the typed cause or replace primary filesystem/recorder truth.

### S7. Focused tests contain fail-open and self-round-trip gaps (MODERATE,
open)

- In `test_effect_settlement_reducer_policy_matrix`, `assert actual == expected`
  moved inside the `else` branch. Any case expected to reduce but unexpectedly
  returning `None` is not asserted. The pre-checkpoint placement covered both
  directions; a one-line dedent restores the matrix's stated authority.
- Execution-v6 serialization and decoding use the same production enums, and
  payload tests derive almost every expected reason from those enums. Only the
  literal `final-flush-failed` is pinned; there is no exact closed-set assertion
  or unknown-value counterexample for all three item and five task reasons.
  Encoder, decoder, and tests can therefore accept the same typo or widening
  against `M1_BRIDGE.md`.
- The decoder's redundant aggregate-attribution contradiction guard has no
  direct counterexample test. This combines with the self-round-trip gap to
  leave an important v6 consistency check unpinned.

### S8. The checkpoint boundary was not documentation-coherent (MODERATE,
open)

`df86150` activated execution-v6 and scoped recording state while `CORE.md`
still described execution-v5 and task-global identityless evidence. `0e14b32`
repairs CORE in a second post-closure commit, contrary to the named checkpoint
boundary and repository commit-readiness rule. Even at `0e14b32`, active docs
still disagreed: `M1_SHELL.md` said checkpoint 2 was next while its table marked
it complete; `ARCHITECTURE.md` said workflow continuation remained v5; and
`HANDOFF.md` told the next implementer checkpoint 1 was uncommitted and not to
start checkpoint 2. Later checkpoint-3 commits repaired part of this, but
`M1_SHELL.md` remains stale at current HEAD.

### Confirmed sound

- Normal `ExecutionSet` invariants are operation-local: aggregate recording is
  derived, identityless evidence requires the same operation's
  `record-write-failed`, task issues are ordered/unique/bounded, and ordinary
  first-item-fails/second-item-commits behavior does not leak task-global state.
- Normal partial success, pause/resume, cancellation, final flush, recording
  open/finish/close, and resumed-directory restoration preserve their intended
  axes when the hidden failure combinations above are absent.
- Execution payload v6 normally round-trips the new fields, refuses execution
  v5, leaves plan v5 unchanged, and normal terminal transitions publish and
  store payload-free records.
- No import-law, sibling-component, new dependency, external-ingress,
  path-authority, SQL, or filesystem-security drift was found in the reviewed
  commits. The store-retention fault in S5 is the material security exception.

### Verification and disposition

Five adversarial tests against an exact extracted `df86150` tree passed while
asserting the faulty observations: committed receipt plus one-shot sink
rejection; retained UPDATE retry plus prerequisite refusal; hostile final-flush
exception rendering; sink/close compound failure; and later store-write
failure. Result: `5 passed, 358 deselected in 0.77s`. The extracted tree and
pytest cache were removed afterward; no review fixture remains.

Checkpoints 1-2 are not independently cleared. S1-S4 are policy/gate failures
requiring separate fixes with persistent counterexamples. S5-S8 also need
resolution before closure. Per `M1_SHELL_H2.md`, invalidate the affected gate
evidence, make the oracle directly observe and protect typed attribution, then
repeat the focused/departments/ordinary and three-run oracle gates from the
declared checkpoint entry state.

## Reviewer O. Checkpoints 3.1-3.2

Independent adversarial review of `c93835a` (dormant v5 consumers) and
`7c93380` (exact v5 activation) against `0e14b32`. Findings continue the F
numbering above. Evidence came from extracted `c93835a`/HEAD trees, a Node
v22.17.1 probe of `bridge.js`, and injected production mutations; every fixture
was removed afterward and the working tree is unchanged apart from this file.

### F8. The retained legacy browser validator drifted into accepting v5 (MODERATE, open)

`7c93380` flipped `LIVE_CORE_EVENT_SCHEMA_VERSION` from 4 to 5 and renamed the
old v4 body to `validateLegacySessionEvent`, but that body still gates on
`event.schema_version !== LIVE_CORE_EVENT_SCHEMA_VERSION`. The retained seam
therefore no longer accepts genuine v4 and instead accepts v5-stamped v4
shapes.

Node probe against HEAD `bridge.js`:

- `validateLegacySessionEvent` accepts `schema_version: 5` - true
- `validateLegacySessionEvent` accepts `schema_version: 4` - false
- `validateLegacySessionEvent` accepts a v5-stamped v4 `Progress` body with
  numeric `bytes_done: 10` and `bytes_total: 20` - true
- `validateDormantSessionEventV5` rejects that same body - false

The seam has no caller, so this is not an active vulnerability; it is a
weakening of the v5 boundary inside the retained seam and makes the seam unfit
for its stated checkpoint-3.3 purpose. The Python seam pins
`_LEGACY_CORE_EVENT_SCHEMA_VERSIONS = frozenset({3, 4})` literally and does not
drift, so the two sides of the same retention decision disagree.
`test_frontend_static.py` additionally asserts
`source.count("LIVE_CORE_EVENT_SCHEMA_VERSION") == 2`, which is satisfied only
because the legacy body references the live constant; repinning the legacy gate
to a literal `4` breaks that assertion. Fix by giving the legacy branch its own
frozen constant and updating that count.

### F9. The live-routing static test is satisfied by legacy text (MODERATE, open)

`test_second_protocol_stop_routes_the_live_browser_through_exact_v5` slices
`bridge.js` from `function validateLiveSessionEvent` to
`function validateSessionRecord`. At HEAD that 1459-character region spans all
of `validateLegacySessionEvent`, so
`assert "event.schema_version !== LIVE_CORE_EVENT_SCHEMA_VERSION" in live`
passes on legacy text. The real live body is one delegating line and contains
no `schema_version` reference at all.

The companion check in `test_frontend_static.py` slices to
`function validateLegacySessionEvent` and is correct. The repository therefore
holds one correct and one fail-open copy of the same routing invariant; the
fail-open copy would not notice the live validator being rewired.

### F10. The settlement oracle's normalized trace is now synthetic and undocumented (MODERATE, open)

`7c93380` kept the frozen 2 MB baseline green by back-projecting v5 truth into
the retired v4 trace shape rather than by reseeding. `_oracle_item_detail`
re-injects `detail["recording"]` and `detail["recording_error"]` from the typed
`recording`, `recording_reason`, and `recording_detail` fields and deliberately
suppresses them when the reason is `recording-prerequisite-failed`;
`_oracle_item_reason` synthesizes the retired `previously-settled` label. The
protected trace consequently records a computed reconstruction, not what the
executor emits. `docs/TOOLS.md` was changed only by rewording `current-v4` to
`historical v4` and discloses none of this. Under the `AGENTS.md` settlement
gate, reshaping the normalized projection so an old baseline still matches is
functionally a gate retune to preserve green.

Interaction with F3 and S3, measured at HEAD:

- Swapping the item reason `recording-prerequisite-failed` to
  `unrecorded-mutation` is now caught by both `oracle` and `diff`. The
  back-projection made that one reason observable through the absence of
  `detail["recording"]`, so F3's item-axis severity drops at HEAD.
- Swapping the task issue `final-flush-failed` to `finish-failed` still yields
  `oracle passed: 30 scenarios x 1 runs` and `settlement baseline matches`.
  Only `test_pause_flush_degradation_is_retained_for_resume` catches it. The
  typed-attribution blind spot therefore persists on the task axis, and the
  oracle still never reads `xset.recording_reasons` or `xset.recording_issues`.

### F11. `M1_SHELL.md` staleness reconfirmed and not repaired (MODERATE, open)

`7c93380` edited `M1_SHELL.md` but only to swap `current-v4` for `v4` and
`historical v4` in two measurement paragraphs. Line 42-43 still reads
"checkpoint 1 settlement-oracle work is complete, and checkpoint 2 recording
attribution is next," and the status table still marks checkpoint 3 `pending`
although two of its three commits landed at a documented safe stop, for which
`M1_SHELL_H2.md` provides `in progress`. This confirms S8 as still open with
the owning file touched in the same commit. `README.md`, `TESTS.md`, `CORE.md`,
`DATABASE.md`, `HISTORY.md`, and `INTERFACES.md` were correctly marked v5
active.

### F12. Nothing binds the Python view producer to the JavaScript validator (MINOR, open)

`validate_session_event_view_v5` is called only from
`tests/core/test_event_v5_consumers.py`. Production builds the browser payload
as a `SessionEventView` dataclass with no v5 view validation. The JavaScript
validator is exercised only against hand-authored `_event_v5_fixtures`, and the
Python view is pinned only against hand-authored `_public_view_witnesses`
expectations; the two fixture sets are independent and nothing compares them.

Measured, no live disagreement exists: the production `SESSION_EVENT_JSON`
witness, all seven body fixtures, and a real `operation_result_view` carrying
`ReviewFactLimitExceeded.plan_logical_bytes()` all pass
`validateDormantSessionEventV5` and `validateOperationResultView` under Node.
The `logical-bytes` axis is absent from the Node corpus even though the
checkpoint requires plan logical-byte refusal, so that agreement is currently
unprotected. This is a brittleness and coverage finding, not a defect.

### F13. Volume-serial narrowing survives the identity-width cutover (MINOR, open)

`file_identity_from_windows_parts` masks `FILE_ID_INFO.VolumeSerialNumber`, a
`ULONGLONG`, with `& 0xFFFFFFFF`. The checkpoint's premise was removing
narrowing from the file-index axis, and identity is the volume/index pair. The
mask is plausibly deliberate so handle-derived identities compare against the
32-bit serial used elsewhere, but no active document states that the volume
axis remains intentionally 32-bit while the index axis became full-width.

### F14. Scalar boundary raises two exception families (MINOR, open)

`scalar_64_from_text` and `file_index_128_from_text` raise `TypeError` for
non-canonical text but `ScalarDomainError`, a `ValueError`, for out-of-domain
values. No current caller catches `ValueError` around either function, so no
reachable escape was found; the split is a consistency and future-robustness
concern rather than a defect. `file_index_128_from_bytes` also guards a
mathematically guaranteed range with a bare `assert`, which `-O` removes.

### Confirmed sound

- `c93835a` is genuinely dormant: 1801 insertions with no deletions, no
  existing file rewritten, `namisync/core/event_v5.py` imported by nothing
  under `namisync/`, and `validateDormantSessionEventV5` reachable only from
  its test.
- No production Python or JavaScript route accepts a pre-v5 version. The
  private Python legacy seam has zero callers, including tests.
- The scalar grammar is tight. `int()`-acceptable Unicode digit strings
  (Devanagari, Arabic-Indic, fullwidth), leading zeros, signs, underscores,
  surrogates, surrounding whitespace, and trailing newlines are all rejected;
  the signed-64 boundary is exact. JavaScript `isScalar64` uses the same
  grammar, and `isV5Path` uses the same UTF-16 unit bound as
  `require_utf16_path`.
- `ItemOutcome` enforces operation-local recording truth: `ok` requires null
  reason and detail, `degraded` requires a typed `ItemRecordingReason`.
  `TerminalSummary` derives its aggregate and rejects contradiction, bounds
  phases and issues, and fully constrains review-limit facts. The JavaScript
  mirror rejects duplicate issue reasons, four phases, degraded items with
  `recording: "ok"`, and a non-canonical `byte_limit`.
- Terminal emission is single-sourced through
  `emit(Terminal(TerminalSummary.from_result(...)))`, and `run_session`
  forbids workflow-emitted Terminal.
- Whole-batch drain validation precedes reduction, with record-last, no events
  after terminal, strictly increasing sequences, and gap bounds;
  `preflightProgressUpdates` runs only after every update validates, so the new
  `BigInt` monotonicity comparisons cannot receive unvalidated input.
- The historical `IntegrityOutcome.kind` decode gap is closed:
  `_validate_integrity_item` applies `_exact_object` and rejects a `kind` other
  than `"integrity"`, and `validate_event_v5_envelope` runs before
  `result_item_from_dict`, so that decoder's internal permissiveness is
  unreachable.
- File identity is stored as canonical `TEXT` under a SQL `CHECK` enforcing
  canonical decimal and exactly `340282366920938463463374607431768211455`. No
  `<< 32` narrowing or numeric index column remains, and the shared adapter is
  used by scanner, preflight, executor, verifier, and the database pair, each
  binding kernel32 with `use_last_error=True`.
- Core and presentation omission counters are separated:
  `omitted_detail_count` passes through from the core summary while
  `presentation_omitted_detail_count` is derived only from the bridge-local
  concatenated error bound.
- Persistence is coherent: ledger v4, history v6, `data_epoch` 5, contract ids
  checked on both reader and writer paths, an all-null-or-exact SQL group
  constraint on the terminal-summary columns, canonical round-trip validation
  of `recording_issues_json`, and complete action-guiding reset text naming the
  `-wal`, `-shm`, and `-journal` sidecars.
- `type(value) is int` is used consistently, so Boolean-as-integer values are
  rejected at every scalar entry point.
- `lint-imports` reports 11 kept and 0 broken; `tests/core`,
  `tests/dispatcher`, `test_db_history.py`, `test_db_schema.py`, and
  `test_database_contracts.py` pass at 665 tests.

### Disposition

Checkpoint 3.1 is clean. Checkpoint 3.2 is materially correct on the protocol
itself: the activation is atomic, the exact-v5 boundary holds on every reachable
route, and Python and JavaScript agree everywhere measured. F8 and F9 are
seam-and-gate defects to resolve before checkpoint 3.3 relies on that seam, and
F10 must be resolved together with F3 and S3 rather than separately, because
checkpoint 3 changed what the frozen baseline means without declaring it.

## Reviewer S. Checkpoints 3.1-3.2

Independent adversarial review of `c93835a` and `7c93380`, with `0e14b32` as
the baseline. I reviewed the two diffs separately, then traced the active v5
contract through core construction/encoding, EventHub mutation order, workflow
views, the production command/transport path, the packaged JavaScript consumer,
history, database-pair admission, repositories, native identity adapters, CLI,
tests, and active documentation. Temporary Python/Node/SQLite probes were
removed; this section is the only retained Reviewer-S change.

### S9. The public drain/bridge route emits unchecked views (HIGH, open)

`SessionEventView` is an unchecked dataclass (`workflows/views.py:148-154`).
`TaskEventUpdateView` checks only the nominal dataclass type, `TaskDrainView`
checks only ids and tuple length (`interfaces/web/drain.py:105-140`), and
`commands.next_events` checks only the outer echoed ids
(`interfaces/web/commands.py:469-485`). `to_primitive_view` then serializes the
approved dataclasses generically. The exact Python v5 view validator has no
production caller.

This is a live outward compatibility route, not the permitted private decoder
seam. A registry collaborator can return a schema-4 event or a structurally
invalid v5 event and receive an `ok:true` production bridge response. The
packaged browser then rejects v4, so the default path fails closed rather than
silently consuming it, but producer and consumer no longer form an atomic
protocol boundary.

Two green committed tests positively freeze the defect:

- `test_br_g_33_codec_approves_only_exact_adapter_task_views` constructs and
  expects a schema-4 `SessionEventView`.
- `test_br_g_33_next_events_crosses_production_dispatch_as_exact_tagged_views`
  takes schema 4 plus a nonterminal `SessionRecordView(state="pending",
  result=None)` through `production_command_specs` and `BridgeDispatcher` and
  expects success.

Those exact tests passed (`2 passed in 0.11s`). The concrete `TaskRegistry` and
ordinary service producer currently emit valid v5; that does not make the
published collaborator/adapter boundary exact or remove the public route.
This contradicts the preceding Reviewer-O disposition that every reachable
route is exact v5.

### S10. Item recording can contradict filesystem outcome (HIGH, open)

The Python v5 validator (`core/event_v5.py:376-391,573-589`), `ItemOutcome`
constructor (`core/events.py:250-308`), and JavaScript validator
(`bridge.js:2085-2117,2308-2318`) validate the filesystem and recording axes
separately but never validate their required relationship. They accept, for
example, filesystem `succeeded` plus recording `degraded` and
`recording-prerequisite-failed` or `unrecorded-mutation`.

The authoritative execution contract rejects those values:
`ExecutionSet` requires `record-write-failed` on `succeeded`/`skipped`, while
`unrecorded-mutation` and `recording-prerequisite-failed` require `failed`
(`core/execution.py:213-225,324-342`). H2 checkpoint 1 pins the same matrix.
Direct probes decoded `succeeded + unrecorded-mutation` in Python and returned
`true` from the packaged JavaScript validator. EventHub cannot catch the error:
its pre-mutation canonicalization calls this same incomplete validator.

The tests are self-confirming. Both the Python and Node corpora iterate every
`ItemRecordingReason` while leaving the fixture outcome `succeeded`; the
Python suite also attaches every ordinary outcome reason to the same succeeded
fixture. This is downstream of, and compounds, checkpoint-1/2 findings F3/S3
about the oracle not independently observing typed attribution. It is not the
same executor settlement defect as S1/S2: even after those are repaired, v5
would still admit impossible operation-local truth.

### S11. `TerminalSummary` drops cancellation invariants (HIGH, open)

`OperationResult` requires compound cancellation to have `Disposition.RAN`, a
matching completed/failed execute phase, and a canceled verify phase; an
execute-canceled result cannot claim a completed execute phase
(`core/session.py:239-279`, documented in `CORE.md:453-458`).
`TerminalSummary.__post_init__`, the Python v5 validator, and the JavaScript
terminal/result validators omit those invariants.

Independent probes were accepted for both of these impossible terminal truths:

- `status="completed", canceled=true, disposition="unrun", phases=[]`;
- `status="canceled"` with a completed execute phase.

The equivalent full `OperationResult` counterexamples are correctly rejected
by existing core tests, which makes the loss at the terminal projection
especially clear. The v5 tests cover valid copies and review-limit facts but no
malformed cancellation variants. A directly constructed terminal summary,
decoded envelope, or malformed public view can therefore become accepted
terminal/browser truth even though the canonical result cannot exist.

### S12. Live view validators omit the reliable-event ceiling (HIGH, open)

`validate_event_v5_envelope` enforces the 1,048,576-byte canonical reliable
ceiling, but `validate_session_event_view_v5` ends after structural body
validation and the active JavaScript validator has no equivalent size check.
The committed maximum-plus-one test exercises only the persistence-envelope
validator.

A per-field-valid `ItemOutcome` with maximum declared path leaves measured
1,180,158 canonical Python envelope bytes. The envelope validator rejected it,
while the Python session-view validator accepted it. The corresponding
1,180,136-byte browser view also returned `true` from the packaged validator.
Ordinary EventHub emission is protected, but S9 lets this view bypass EventHub,
cross the production bridge, pass whole-batch validation, and then participate
in cursor/reducer/callback mutation. Thus the requirement to reject a
structurally over-limit reliable event before sequence/queue/consumer mutation
is not closed across the claimed exact producer-consumer graph.

This finding is limited to the one-event v5 ceiling. Checkpoint 4 owns the
separate maximum-head/complete-drain response-byte policy; I did not treat that
later count/packing work as a checkpoint-3 defect.

### S13. A result-free terminal record releases custody (HIGH, open)

The terminal record is the cleanup boundary only when its result is non-null
(`M1_BRIDGE.md:2752-2759`). Instead, `validateSessionRecord` requires a terminal
state but explicitly permits `record.result === null`
(`bridge.js:1571-1594`). `presentTerminalUpdate` then marks the task terminal and
starts release (`bridge.js:948-975`). On the server, draining any
`SessionRecordView` sets `terminal_delivered`, and release checks only that flag
(`interfaces/web/drain.py:548-549,710-711`). The Python update/view types impose
no stronger invariant.

A live drain-manager probe delivered the null-result terminal, reported no
refusal, and issued `release_terminal_session`. The normal observer currently
waits for a result-bearing record; this is nevertheless an exact live-consumer
and custody-boundary defect. A malformed collaborator response can discard the
only full `OperationResult` presentation and still retire the native session.
Committed drain-manager fixtures also positively exercise null terminal
records.

### S14. Metadata self-certifies incomplete databases (HIGH, open)

The pair gate checks only schema version, contract id, and data epoch. Neither
`validate_*_reader_contract` nor `_require_contract_id` verifies required
tables, columns, indexes, triggers, constraints, or their definitions
(`db/schema.py:1081-1173`). `validate_database_pair` therefore returns `READY`
for two files that merely carry the three exact metadata rows. Individual
initializers then execute `CREATE ... IF NOT EXISTS`, which can silently repair
missing objects while preserving hostile same-name objects
(`db/schema.py:1036-1075`).

Independent SQLite probes demonstrated both consequences:

- marker-only ledger and history files were classified `READY`;
- an exact-marker ledger with a poisoned `inventory(id, poison)` table was
  classified `READY`, after which `LedgerRepository.get_inventory` failed with
  `no such column: location_id`;
- direct initialization of a marker-only ledger silently added production
  tables instead of refusing the incomplete current-version file.

This violates the published reset boundary for incomplete current databases
(`FEATURES.md:258-260`, `DATABASE.md:19-26,354-360`) and leaves malformed local
persistence inside a claimed current contract. Tests cover missing/wrong
markers and a complete reopen, but not exact markers with incomplete or
malicious topology.

### S15. The WAL-blind pair gate mutates on refusal (HIGH, open)

`db/contracts.py:30-49` validates with `immutable=1`, based on the assumption
that published metadata can never change. There is no trigger preventing
updates/deletes of `schema_metadata`, and persisted database structure is an
untrusted boundary. SQLite immutable mode ignores WAL state, while normal
readers use `mode=ro` and do observe it.

In an independent fixture, the durable main files carried exact current
markers, while the history WAL changed `contract_id`. With the main plus WAL
copied and no SHM, pair validation returned `READY`. `HistoryRepository` then
observed the WAL value, raised `SchemaResetRequired`, and created the previously
absent `history.db-shm`. This is both false admission and a mutation during the
documented byte-for-byte-unchanged refusal path (`DATABASE.md:87-106`). The
existing WAL test changes only `PRAGMA user_version`; the repository
no-mutation test has no WAL.

### S16. Active JSON hashes encode `FileIndex128` numerically (MODERATE, open)

The SQL columns, workflow payloads, repository binds/decoders, and native
adapters correctly use canonical decimal text. However, the generic JSON
primitive functions in `core/planning.py:318-345` and
`db/recorder.py:112-143` leave dataclass integers untouched. Active plan
fingerprints serialize the whole plan, and recorder idempotency hashes serialize
plans/inventory/evidence through that path. The public `serialize_plan` helper
does the same.

For `FileIdentity("serial", 2**100)`, `canonical_json_bytes` emits
`"file_index":1267650600228229401496703205376` rather than a quoted canonical
`FileIndex128`. Current hashes remain Python-local, so this does not presently
create a JavaScript rounding collision; it does violate the checkpoint hard
wall that no file identity crosses JSON numerically (`M1_BRIDGE.md:237-250`) and
makes the active fingerprint/persistence codec depend on an unsafe
representation. The full-width storage cutover tests do not cover these JSON
hash/serialization paths.

### S17. Python and JavaScript disagree on timestamps (MODERATE, open)

Python delegates to `datetime.fromisoformat` (`core/event_v5.py:743-755`), while
JavaScript checks a UTC suffix and `Date.parse` (`bridge.js:2432-2438`). Direct
differential probes found both directions of disagreement:

- JavaScript accepted the impossible calendar date
  `2024-02-30T00:00:00Z`, which Python rejected.
- Python accepted `2026-08-25T00:00:00+00:00:00`, which JavaScript rejected.
- Python also accepts basic/week-date ISO forms that JavaScript rejects, while
  JavaScript accepts date-only/24:00 forms Python rejects.

Service-produced `datetime.isoformat()` values lie in the shared subset, so the
ordinary producer path is sound. The two advertised exact validators and their
malformed-input behavior are not equivalent, and S9 makes JavaScript-only
values reachable through the public view route. No shared negative timestamp
corpus pins one grammar or calendar validation.

### S18. Gates and docs preserve legacy or circular truth (MODERATE, open)

In addition to the positive v4 and contradictory recording fixtures above:

- `test_br_g_36_browser_progress_validator_owns_the_expanded_exact_shape`
  extracts `validateProgress`, which now belongs only to the unreachable legacy
  branch; it does not inspect the active v5 progress validator.
- The browser vocabulary comparison omits active v5 operation kinds/reasons,
  item/task recording reasons, and detail keys. The Node corpus omits the
  reliable ceiling, timestamp grammar, cancellation counterexamples, and
  logical-byte review facts.
- `test_second_protocol_stop_switches_every_live_python_route_to_v5` checks two
  constants and `envelope_from_dict`, not the production view/command route.
- `docs/M1_BRIDGE.md:3182-3185` still calls the live nested event version 4, and
  `:4362-4368` still describes current-source fixtures as version 4.
- `docs/M1_SHELL.md:42-43` says checkpoint 2 is next and its status table still
  marks all of checkpoint 3 pending. `docs/DATABASE.md:126` still calls the
  active history schema version 5 rather than 6.

This continues checkpoint-1/2 finding S8 and reconfirms Reviewer-O F9/F11. It
also contradicts the checkpoint-3 handoff claims that active-v4 source was
cleared, database pairs refuse incomplete files, and no file identity crosses
JSON numerically.

### Confirmed sound in this review

- `c93835a` is behaviorally dormant: it is additive, no production Python
  module imports `event_v5`, and the new JavaScript validator is reached only by
  its direct tests. No v5 event, persistence, dispatcher, or browser behavior
  became active at that stop.
- The retained Python and JavaScript legacy decoders have no production caller.
  Under the review premise, I do not count their mere presence or private
  behavior as a finding; no public version selector or live v3/v4 decoder was
  found there.
- On the ordinary concrete path, core/live constants are 5, the public current
  decoder rejects versions 3/4/6 and Boolean versions, service views originate
  from validated envelopes, history admits exact v5 reliable envelopes, and
  the browser selects the v5 validator.
- EventHub validates before sequence, replay, audit, or subscriber mutation.
  Gap recovery, whole-batch preflight, cursor immutability on rejected batches,
  progress identity/attempt monotonicity, FIFO terminal ordering, terminal
  precedence, and late subscription/replay were coherent; I found no separate
  cancellation, replay, or partial-application defect beyond S11-S13.
- Terminal events are item-free and the full result remains in the terminal
  record on the normal path. History's event receipts, dense item projections,
  finalization hashes, all-null-or-exact terminal columns, reconstruction, and
  presentation-omission separation were coherent apart from S14-S15.
- Full-width file indexes use checked canonical text in SQLite and public
  workflow payloads; scanner, preflight, executor, and verifier use the shared
  complete native adapter, and no high/low file-index projection or numeric SQL
  identity column remains. S16 is confined to generic JSON fingerprint/hash
  codecs.
- Closed scalar grammar, Boolean rejection, UTF-16 path limits, safe integers,
  `Scalar64`, `FileIndex128`, review-limit variants, and import layering agreed
  across the ordinary tested paths apart from the timestamp and size findings.

### Reviewer-S verification and disposition

- `git diff --check 0e14b32 c93835a` and
  `git diff --check c93835a 7c93380`: clean.
- Focused production v4-route tests: `2 passed in 0.11s`.
- Independent Python/Node semantic, ceiling, timestamp, terminal-record, and
  numeric-identity probes produced the counterexamples recorded above.
- Independent SQLite incomplete-schema and WAL probes reproduced false `READY`,
  repository failure/refusal, partial repair, and SHM creation. Their focused
  harnesses passed and all temporary artifacts were removed.
- Final worktree check before this handoff addition showed only the expected
  pre-existing `docs/HANDOFF.md` modification.

Checkpoint 3.1 met the behavioral-dormancy safe stop, but its direct validators
did not accept/reject the exact target because S10-S12 and S17 were already
latent. Checkpoint 3.2 is not an atomic, exact-v5 acceptance stop: S9 and S13
leave production adapter/custody boundaries outside the exact validator, S10-
S12 admit contradictory or over-limit event truth, and S14-S16 leave the reset
and identity codec contract incomplete. These should be repaired with
independent counterexample fixtures before checkpoint 3.3 removes the private
legacy seam.
