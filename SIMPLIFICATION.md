# NamiSync Initial Simplification Run

**Standing (2026-09-01): ratified delivery authority.** This document owns the
closed register, evidence, stop rules, and resumption state for the initial
simplification run. It instantiates `AGENTS.md` **Task Containment And
Recovery**; it does not replace or restate that protocol. Only an explicit user
decision may change the accepted register after implementation starts.

This is a removal plan. A green suite is necessary but not sufficient because
the same work removes tests and enforcers. Completion therefore requires both
unchanged public behavior and proof that no guarantee lost its last enforcer.
The run fails if complexity is moved into new wrappers, authorities, generic
freezing machinery, duplicate DTOs, compatibility shims, or a replacement
oracle instead of being removed.

---

## 1. Objective and fixed boundary

The run removes two high-fanout mechanisms before any new feature work:

1. Replace process-local workflow JSON payloads with detached immutable domain
   checkpoints.
2. Remove redundant event certification downstream of the domain owner while
   preserving the exact current v5 persisted body.

The behavioral exit is that adding one named domain field no longer requires
editing internal codecs or validators. Source, test, and collected-test counts
are reported trends, never acceptance gates. Atomic outcome, not diff size,
continues to determine commit scope.

### Non-goals

The following are outside every register row even when a removal exposes an
apparently convenient edit:

- the history chain;
- executor fact algebra or settlement restructuring;
- ledger receipt consolidation;
- `MOVE_UPDATE`;
- task-ownership or task-lifecycle restructuring;
- View types beyond the event-certification path in SIM-2;
- a broad `adopt_*`, `snapshot_*_authority`, `revalidate_*_authority`, or
  provenance-token sweep;
- H2 checkpoints 5–8 or any other new feature, including pause/resume
  expansion, volume concurrency changes, `visible_sequence`,
  `mutate_selection`, and annotations.

Existing pause/resume/cancel behavior is a protected regression subject, not a
feature delivered by this run. H2 checkpoint 4 under its former complete owner-
graph and retained-byte rules is retired, not implemented. Later feature work
requires a fresh finite delivery register; this run does not activate a task
surface or any checkpoint-5–8 command or control.

Only five existing BR-G records change in this run: BR-G-10, BR-G-28,
BR-G-33, BR-G-36, and retired BR-G-45. All other gate prose and executable
evidence remain outside the register.

### Architectural decisions

- The four validation rungs in `DEFENSE.md` remain authoritative. External
  validation belongs at filesystem/persistence edges and interface-adapter
  ingress, currently the bridge and CLI and equally any future API.
- Internal contracts are typed domain values. Serialization is allowed only at
  a real process, browser, persistence, or filesystem boundary.
- A concept has at most its domain value and one boundary representation. One
  canonical event body may be wrapped by a separate durable history envelope.
- Dispatcher custody is domain-blind. It holds an opaque checkpoint and does
  not inspect, certify, or reinterpret it.
- Detachment is a construction property. There is no
  `WorkflowCheckpointAuthority`, `adopt_checkpoint()`, generic checkpoint
  protocol, recursive deep-freeze utility, `deepcopy` framework, pickle, or
  replacement wire format.
- Existing frozen requests are checkpoints where they are already safe.
  Execution may add one narrowly scoped frozen checkpoint that reuses existing
  detached execution and selection snapshots; it must not duplicate their
  fields in another DTO.
- Same-run tokens may retain a freshness or correlation role. They are not
  internal forgery defenses, and removing that role does not authorize losing
  staleness detection.
- Event v5 remains the persistence contract. SIM-2 may remove certification
  but may not change persisted bytes or trigger a data epoch.

---

## 2. Closed checkpoint register

The accepted rows below are the completion denominator. Findings never add a
row.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| `SIM-0` | Ratify this removal contract; close the removal/enforcement ledger; capture stable behavior and v5-body corpora before implementation. | Three identical snapshots with no skipped or unclassified scenario; ordinary suite and import-law baseline; corpus self-test; clean declared diff. | Complete |
| `SIM-1` | Remove process-local workflow payload serialization and replace it with structurally detached semantic checkpoints without changing pause/resume/cancel/settlement behavior or losing real ingress enforcement. | Frozen corpora three times; ownership/aliasing tests; affected departments; ordinary suite; import law; enforcement ledger; test-deletion and relocation audits. | Active |
| `SIM-2` | Remove redundant event certification while preserving exact v5 persisted bodies, history envelopes, browser delivery/recovery, and reducer behavior. | Frozen corpora three times; byte-for-byte persisted-body check; affected departments and Node probes; ordinary suite; import law; enforcement ledger; test-deletion and relocation audits. | Pending on SIM-1 |

SIM-0 closes only when the corpus artifacts and baseline commit are recorded in
the resumption block. No implementation or removable test may be changed before
that point.

---

## 3. Frozen regression corpora

Before implementation, capture:

- `tests/_event_v5_fixtures.py`;
- `tools/simplification_regression_audit.py`;
- `tools/simplification_regression_baseline.json`; and
- `tests/test_tools_simplification_regression_audit.py`.

The audit follows the evidence pattern of `tools/executor_settlement_audit.py`
but remains small. It may contain fixtures and normalization; it may not
reimplement a codec, validator, workflow reducer, settlement policy, or other
production decision. Existing positive event-v5 fixtures are moved or shared,
not copied into a second independently maintained vocabulary.

### Workflow checkpoint corpus

Drive production runtime/dispatcher paths through these exact scenarios:

1. execution pause -> resume -> settle;
2. execution pause -> cancel -> settle;
3. linked verification pause -> resume;
4. linked verification pause -> cancel and compound settlement;
5. standalone baseline, verify, and rebaseline pause -> resume; and
6. standalone baseline, verify, and rebaseline pause -> cancel.

Normalize only nondeterministic ids, timestamps, temporary roots, and explicitly
unordered facts. Preserve state/event order, terminal axes and items, recording
disposition, byte high-water values, omission facts, and durable terminal
state. No scenario may skip or remain unclassified.

### Canonical v5 body corpus

Freeze all seven event-body kinds, the review-limit terminal case, and the
maximum-size envelope case. Record exact canonical JSON bytes and hashes and
the exact `history_events.envelope_json` write/read value. Parsed-object
equality is not a substitute for byte equality.

Snapshot and check each corpus three times. SIM-0 is accepted only when all
three normalized observations are identical. After the SIM-0 corpus commit,
the audit, corpus definitions, baseline, and audit test are immutable for this
run and must pass `git diff --exit-code` against that commit at every checkpoint.

The corpora are exempt from every test-cut disposition: the suite may shrink;
the corpora may not.

Official capture and check commands are:

```powershell
.\.venv\Scripts\python.exe -m tools.simplification_regression_audit snapshot --baseline tools\simplification_regression_baseline.json --repeat 3
.\.venv\Scripts\python.exe -m tools.simplification_regression_audit check --repeat 3
```

`--replace` is permitted only while finalizing the pre-freeze SIM-0 snapshot;
it is forbidden after the corpus commit.

---

## 4. Regression, defect, and stop routing

A regression has two independent limbs:

1. **Behavioral:** a frozen corpus produces different output.
2. **Enforcement:** a supported guarantee loses its last enforcer, even with a
   green suite.

For each removed check, the ledger in §5 must name what still enforces the
property or record that the claimed property was not part of the supported
contract.

Route findings through `AGENTS.md`:

- A corpus failure introduced by the active checkpoint is corrected before its
  mergeable commit.
- If the corpus passes but removal exposes a bounded pre-existing defect, that
  defect may land in a separate fix commit only when no stop rule fires.
- Every other finding is logged and deferred.
- A finding never expands the register.

Classify each unplanned mechanism as `aliasing`, `lost enforcement`,
`representation drift`, or `coverage hole`. Counters are cumulative across this
run. Two findings of one class, or three findings total, stop new work after the
current safety-preserving atomic outcome and require the mechanism table from
`AGENTS.md` before reorganization and review.

In addition to the repository-wide stop classes, stop immediately when:

- resumed execution mutates a checkpoint still in dispatcher custody; this is
  a design failure and must not be patched in place;
- persisted-body inequality is first discovered after an encoder was removed;
  restore the safe state and do not invent an epoch migration; or
- a removed check was the sole enforcer of a `DEFENSE.md` hard wall.

---

## 5. Closed removal and enforcement ledger

Only the exact mechanisms below may be removed. A newly discovered candidate
is deferred. Private helpers wholly owned by a file listed for deletion travel
with that file; no similarly named helper elsewhere is implied.

| Checkpoint and exact mechanism | Property previously claimed | Disposition | Remaining authority and proof |
| --- | --- | --- | --- |
| SIM-1: complete modules `namisync/workflows/payloads.py` and `namisync/workflows/_json_envelope.py`, including public `encode_plan_request`, `decode_plan_request`, `encode_execution_request`, and `decode_execution_request` | Process-local transport compatibility, byte bounds, and detached continuation state | Remove the internal transport contract. Compatibility and byte bounds are not supported properties inside one process; detachment is real. | Frozen/request constructors enforce domain shape; checkpoint construction snapshots mutable state; ownership tests and the workflow corpus prove detachment and behavior. |
| SIM-1: codec-embedded calls to `core.execution.validate_execution_set` and `workflows.models._exact_verify_continuation` | Mutable execution-overlay validity and exact verify-continuation phase/handoff semantics | **Keep the enforcers.** Move their named invocation to semantic checkpoint construction/open as appropriate; deleting the codec does not delete these checks or their public behavior. | The existing functions remain authoritative; focused construction/open tests plus frozen execute/verify traces prove they still run before unsafe state is used. |
| SIM-1 / BR-G-28: inventory codec entry points `encode_inventory_request`, `decode_inventory_request`, `encode_integrity_request`, `decode_integrity_request`; their codec-only `_charge_inventory_*`, `_charge_integrity_*`, `_payload`, `_json_bytes`, `_mapping`, `_list`, `_unique_object`, `_reject_json_constant`, `_expect_keys`, `_string`, `_integer`, and `_boolean` helpers | Internal inventory/integrity JSON shape, version, wrong-wire-kind separation, and encoded-size admission | Remove. These requests never cross a process or persistence boundary. | Existing frozen workflow-request constructors preserve mode and domain shape; detached checkpoint construction plus real source-population/path and adapter-ingress admission remain. The corpus and public workflow tests prove behavior. |
| SIM-1: `PreparedSession.payload: bytes`, `WorkflowInvocation.snapshot() -> bytes`, `WorkflowRegistration.open(bytes)`, `SessionRecord.payload`, dispatcher `_replace_payload`, and the byte-type branches attached to them | Opaque dispatcher custody and pause detachment | Replace only the representation and names needed to carry an opaque semantic checkpoint. | Frozen checkpoint construction is the enforcer; dispatcher must not inspect it. Mutation-after-snapshot and repeated-open tests prove non-aliasing. |
| SIM-1: `LocalWorkflowRuntime` calls to the eight codec entry points and `_PlanInvocation.snapshot`, `_ExecutionInvocation.snapshot`, `_InventoryInvocation.snapshot`, `_IntegrityInvocation.snapshot` byte returns | Workflow reopen receives a complete request/continuation | Retain snapshot/open behavior while removing encoding. | One checkpoint-construction and one materialization/open path per workflow; frozen traces prove exact observable behavior. |
| SIM-1: internal payload-version, duplicate-key, malformed-JSON, charge-ceiling, and round-trip checks rooted in `tests/test_payload_roundtrip.py` and the codec-only blocks in inventory/resume tests | Compatibility with arbitrary process-local bytes | Not a supported property after the wire form is deleted. | Any test that also covers selection, provenance, freshness, path/population bounds, cancellation, recording, or settlement must be replaced at a public surface or retained. Zero uncovered behavior is permitted. |
| SIM-1: any forgery interpretation attached to plan/inventory same-run signal tokens | Resistance to forged first-party private values | Remove only the unsupported forgery role; do not sweep the token mechanism. | Same-run freshness/correlation remains until separately adjudicated. Exact first-excess behavior and real boundary admission remain tested. |
| SIM-2: the `validate_event_v5_envelope(...)` self-check inside `core.events.envelope_to_dict` | A typed domain producer certifies its own projected output; today the same call is also the sole enforcer of `MAX_RELIABLE_EVENT_CANONICAL_BYTES` | Remove semantic encode-time recertification, not the canonical projector, persistence validator, or byte wall. Before that call is removed, `canonical_event_bytes` must explicitly enforce the maximum before `EventHub` sequence/replay/subscriber mutation. | Typed event constructors own domain semantics; `validate_event_v5_envelope` remains at persistence decode; `canonical_event_bytes` becomes the named byte-wall enforcer; exact bytes and first-excess behavior are frozen. |
| SIM-2: `core.event_v5.validate_session_event_view_v5` and `workflows.views.validate_session_event_view` | Downstream Python layers independently certify event-body semantics | Remove. Trusted internal projections do not independently reinterpret domain truth. | Canonical projector plus persistence decode validation; browser transport-envelope checks; frozen body and delivery corpora. |
| SIM-2: the duplicate event-body projection/revalidation in `workflows.views.session_event_view` | Presentation reconstructs and certifies the body | Collapse to the one canonical body projection; retain the view and its boundary representation. | Exact corpus bytes and public view tests. |
| SIM-2: event-body calls in `interfaces.web.drain._validate_task_observation`, `validate_task_update_view`, and `validate_task_drain_view` | Drain/task layers certify body fields again | Remove only body-semantic certification. Keep task/session matching, wrapper shape, sequence, batch, ordering, and lifecycle checks. | Reduced transport-wrapper checks and existing drain/recovery/reducer tests. |
| SIM-2: event-related `_VIEW_VALIDATORS` entries and traversal in `interfaces.web.bridge`; do not remove validators for unrelated command/result types | Native response traversal certifies trusted event bodies | Remove event semantic recertification while preserving response ownership, JSON bounds, and projection. | Bridge response budget/ownership checks and browser transport checks remain. |
| SIM-2: JavaScript `validateSessionEventV5`, `validateProgressV5`, `validateOperationItemV5`, `validateTerminalSummaryV5`, and their body-semantic-only private helper closure | Browser independently implements Python's event schema | Replace with one minimal transport-envelope check: plain object, v5 marker, matching session, positive safe sequence, recognized body tag, object body, and atomic batch staging. | Canonical Python producer owns body semantics; browser delivery/reducer probes prove transport and behavior. |
| SIM-2: Python-to-JavaScript vocabulary mirrors and v5 body mutation gates | Two independent semantic implementations stay synchronized | Remove only tests of deleted certification. | Valid reducer/lifecycle cases, persistence corruption negatives, receipt/hash checks, and boundary-envelope rejection remain. Zero uncovered behavior is permitted. |

`validate_event_v5_envelope` at persistence ingress, history receipt/hash/
watermark checks, all JavaScript-to-Python command validation, filesystem
freshness, bridge origin/security rules, complete external-request bounds, and
active scalar/population/handler/queue walls are explicitly kept.
`MAX_RELIABLE_EVENT_CANONICAL_BYTES` is likewise kept and must never have a
window in which size is checked only after sequence or queue mutation.

---

## 6. Test deletion rule

Tests travel with their removed mechanism in the same commit. The frozen
corpora remove the need for an artificial intermediate green-suite commit, but
they do not authorize deleting unique coverage.

For every deleted test, record one disposition:

- `mechanism-removed`, when it asserts only the deleted internal contract; or
- `public-replacement`, naming the public-surface test that preserves the real
  guarantee.

A test that is the only node for a surviving gate or `DEFENSE.md` hard wall may
be deleted only through `public-replacement`. The knowingly-uncovered allowance
for this run is **zero**. A test that is eligible for deletion but cannot meet
that rule remains in place and is listed in the checkpoint recap for a later
test-specific removal run.

---

## 7. Complexity-relocation failure audit

Record the pre-change mechanism graph and repeat it after SIM-1 and SIM-2.
Completion requires every statement below:

- No internal workflow JSON schema, payload version, byte ceiling, charge
  calculator, or encode/decode path remains.
- Dispatcher/session custody contains checkpoint objects, not serialized
  continuation bytes.
- There is no new generic freeze, authority, adoption, recertification,
  serialization, compatibility, or checkpoint framework.
- There is no checkpoint DTO duplicating an existing immutable domain value or
  detached snapshot field-for-field.
- Each workflow has one checkpoint construction path and one open/materialize
  path.
- Event flow has one domain-to-v5 projector and one persistence decoder
  validator, with no downstream Python event-body certifier or JavaScript
  semantic twin.
- The browser retains only its real transport-envelope checks.
- The frozen audit does not encode production policy or become a substitute
  implementation of what was removed.
- Dependency paths and standing mechanisms are fewer, not renamed or displaced
  into tests, docs, adapters, or generic helpers.

Any failed statement fails the task. Do not compensate with line-count gains.

---

## 8. Finite terminal exit test

After SIM-2, create disposable branch
`codex/simplification-field-probe` from the completed simplification HEAD and
add this scratch-only field:

```python
PlanOperation.simplification_probe: str | None = None
```

A non-null value must participate in domain equality and the existing plan
fingerprint/projection, survive semantic dispatcher checkpoint pause/resume,
and appear in the single `PlanOperationView` boundary projection. It has no
executor-policy effect. Construct probes with `dataclasses.replace` so
mechanical constructor churn cannot dominate the observation.

Count every tracked source and test file required to make the focused public
workflow/dispatcher/view check pass. Test fixtures count; generated artifacts
and caches do not. Record the exact file list and command, then revert the
scratch changes, return to the source branch, and delete the disposable branch.
Nothing from the probe is committed or merged.

- Historical baseline: 20–27 files.
- Declared target: **at most 8 files**.
- More than 8 means the run is incomplete. Record the residual fanout and stop;
  do not expand the register with opportunistic cleanup.

---

## 9. Verification and resumption

After each implementation checkpoint, run the frozen audit three times, the
affected producer and consumer departments, the ordinary suite, and
`lint-imports`. SIM-2 also runs the direct Node drain/reducer probes. No headed
witness is required because this run activates and changes no user workflow;
that does not waive ordinary packaged-JavaScript and transport verification.

The final sweep reconciles every ledger row, proves the zero-uncovered rule,
runs repository-wide searches for forbidden replacement mechanisms, compares
before/after representation and dependency counts, records line/test trends,
and performs the field probe in §8. `CHANGELOG.md` and `HANDOFF.md` close only
after those checks pass.

### Resumption block

- Planning branch: `milestone1-anthony`.
- Planning base: `42fae4d3b498175a4884e64b6995287188f616e3`.
- Committed SIM-0 collection: 5,208 of 5,236 tests collected, 28 deselected.
- Ordinary baseline: 5,204 passed, 4 skipped, 28 deselected, with the bundled
  Node runtime supplied through `NAMISYNC_TEST_NODE`.
- Import baseline: 11 contracts kept, 0 broken across 77 files and 346
  dependencies.
- Active row: `SIM-1`.
- Next action: land the CLI complete-request bound, then replace internal
  payload bytes with detached semantic checkpoints and run the frozen corpus
  before removing any codec.
- SIM-0 corpus commit:
  `144cbbceb7841d31cc5c85fa04ea1a34d89a74ec`.
- Frozen SHA-256 values:
  - `tests/_event_v5_fixtures.py`:
    `52d36cdab200d047225a604de50e0b5118268074c21d243c896ea94e9c9b94e6`;
  - `tests/test_tools_simplification_regression_audit.py`:
    `7e8e2f106c4ed638d5f9026970bf95bffe0a0ef92556951a8e4e79d85bf0b897`;
  - `tools/simplification_regression_audit.py`:
    `a56f1df879e05d268d5228b0522518751289ca1fb40820c0d39c93bbd21d29b3`;
  - `tools/simplification_regression_baseline.json`:
    `97d11b6f69cc0ba8d1cd9e56096e3ccc539f79020f7c2322fe3b0adc805e6dab`.
- Mechanism counters: aliasing 0; lost enforcement 0; representation drift 0;
  coverage hole 0.
- Do not begin SIM-2, modify a frozen corpus artifact, or resume H2 feature
  work until SIM-1 is complete.
