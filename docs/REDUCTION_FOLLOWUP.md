# Narrow Reduction Follow-up

## Main objectives

- Preserve reviewed sync, inventory, progress, history, and settlement behavior
  while removing repeated work on already-admitted values.
- Reuse history's validated encoding and local item projections without changing
  event transport, canonical bytes, hashes, or persisted schemas.
- Condense only MOVE/RECASE rename mechanics, new-file/update publication
  observation, and the named unused executor arguments/no-op wrapper.
- Change tests with their owning simplification: retire only obsolete assertions,
  preserve independent behavioral witnesses, and add only demonstrated gaps.

## Scope and decisions

Status: implementation authorized 2026-09-08. NR-0 qualification is complete;
later implementation gates remain pending. The user authorized GPT-5.6 agent
implementation, fresh adversarial reviewers, independent atomic commits, and
isolated parallel work where dependencies permit. This is the maintenance subregister linked by
[M1_PLAN.md](M1_PLAN.md), not another M1 product roadmap. The closed PR-0–PR-9
register in [PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) remains unchanged.

### Closed simplification populations

| Family | Removed mechanism | Protected guarantees and production seams |
| --- | --- | --- |
| File-stat graph: `FileIdentity`, `MetadataSnapshot`, `FileStat` inside `FileStat.__post_init__`, `snapshot_file_stat`, `file_stat_fact` | Throwaway nested constructors and rebuilding an exact admitted immutable stat merely to read or return its facts | Initial scalar/type validation; exact-base adoption; unchanged fact tuple and identity/metadata meaning. Consumers are attestation adoption, integrity selection facts, and inventory row snapshots. |
| Runner Progress branch in `run_session` | Second identical Progress reconstruction after the first normalized snapshot | First producer-to-runner normalization, every progress field, accepted-emission ordering, terminal fallback and pause/cancel behavior. `emit` remains a reentrant seam. |
| Scan graph from `ScanResult` construction through workflow adoption and inventory recording | Repeated element-type/warning/scope certification of the same exact immutable graph | Constructor validation, exact transfer shape, independent raw domain/information admission, requested root/scope matching, completeness and recorder reconciliation. Scanner callback and DB transaction remain real seams. |
| Reliable-envelope admission inside `HistoryObserver._admit` | Validator encoding discarded before storage encoding and recursive primitive rebuilding | Semantic refusal and canonical-byte check before history queue/flush mutation; dispatcher admission, public validator behavior, wire and schema unchanged. |
| Item projection in history admission and readback | A second local item projection for hashing/column comparison | Distinct envelope/item/identity/receipt hashes, decoded canonical item semantics, SQL-column consistency, replay/conflict handling. No cross-call retained cache. |
| MOVE/RECASE bodies | Duplicated reviewed-target rename sequence | Different prologues, MOVE-only absence guard, exact errors, operation kind, recorder method, mutation marker and native call order. |
| `_observe_new_publication` / `_observe_update_publication` | Duplicated published-target/temp/target observation and common final branches | Explicit new-file/update prepublication distinctions, diagnostics, probe order, update-backup and MOVE_UPDATE composition. |
| Three unused executor parameters and one no-op wrapper | `_record.detail`, `_noop.state`, `_complete_published_byte_operation.state`; outer `_prepare_copy` try/except that only re-raises | Identical call/effect/control behavior; existing collaborator seams and local exception translations. |

The immutable family is deliberately the demonstrated stat graph plus duplicate
Progress snapshot, not all frozen dataclasses. Settings, IgnoreSet, ContentEvidence
datetime normalization, result/phase snapshots, volume/request reconstruction,
and broader selection/continuation validation are outside this register.
`file_identity_projection` and other hash projection validators are not included
merely because they reference the same leaf type. Keep their public contracts.
NR-2 intentionally replaces CORE's explicit separate runner/emitter Progress
snapshot prescription; that representation change was accepted with the duplicate
Progress cleanup. It does not retire accepted-emission fallback or allow ordinary
mutation of Progress. Record this precise documentation change with NR-2.

The narrow scan change may remove repeated graph walks in `core/review.py`
adoption, `InventoryCommand` scan validation, and `db/recorder.py` scan projection.
Keep `ScanResult.__post_init__` / public `validate_scan_result` as the full shape
validator. Keep unrelated `InventoryCommand` scalar checks and recorder-side
command reconstruction; eliminating the scan rewalk does not authorize deleting
those checks. Keep individual record hash projectors and their current guards.

Explicitly shelved: recording-tail builders, pause/cancel block merging,
mutation-verdict constructor compression, and the previously suggested legacy
recording-key pops. Also excluded: settlement/journal/reducer redesign, root-probe
removal, native/pipeline changes, runtime test-seam removal, schema/version changes,
feature retirement, planner re-sort removal, new generic engines, and unrelated
cleanup. No new production injection knob is needed for this plan.

### Governing policy, baseline, and uncertainty

[AGENTS.md](../AGENTS.md) governs containment, commits, and recovery.
[DEFENSE.md §2.1](DEFENSE.md#21-supported-environment-and-trusted-computing-base)
governs validation/custody; §7 governs measurement. Capacity, freshness, and
exception lifetime are independent of trusting an immutable value. This plan
does not change those policies, hard walls, or residual dispositions.

Source investigated: `50bc05ebab57da724faa11ccf4f8882cdcb6a291` on
`milestone1-anthony`; final preceding product commit is `08572b7`.
At plan creation only documentation was dirty; the two user-owned root ablation
reports were untracked and were absent when execution began. Do not restore them
or treat their absence as task cleanup. Establish a
qualified current-source baseline in NR-0; do not inherit green from a date or
from the external report's older `40fd8a5` worktree.

Prior evidence: the preceding reduction's complete run reported 4,741 passes,
four WinError 1314 capability skips, all 28 headed cases, 12 import contracts and
30 oracle scenarios across three identical runs. The discovery follow-up ran
25 selected event/history/executor cases successfully in 1.58 seconds. Its first
sandbox attempt passed three but failed 22 fixture setups; a one-case diagnosis
confirmed denial of pytest's Windows temporary directory. The same selection
passed with access and cache disabled. These are historical observations, not
this plan's baseline or proof of any candidate refactor.

No functional decision is delegated to a failing test. NR-0 binds the test-node
inventory to these already-closed families; it may not expand them. Unresolved
equivalence, a needed policy change, or a finding outside the bounded family
returns to the user for adjudication. Exact helper names and extraction layout
are implementation choices when they preserve the declared behavior and seams.

## Investigation and regression map

### Migrated RF-E/RF-X dispositions

These discovery findings were previously in M1_PLAN and are now owned here.
RF-E and RF-X discovery are complete; their implementation successors below are
pending. The original reports remain evidence, not governing instructions.

- EventHub's `canonical_event_bytes` runs before sequence/replay/audit mutation.
  History separately projects, validates (including encoding), and encodes again.
  Prefer returning checked bytes from a core validate-and-encode operation while
  preserving the existing public validator API. Keep dispatcher admission.
- History admission can hash its existing projected body. History readback can
  share one projection of the decoded item between column and hash checks. Do
  not substitute raw stored JSON: decoding/normalization remains significant.
- Do not cache bytes or projections across dispatcher, subscribers, audit, or
  pending windows. `_PendingEvent` keeps an envelope and text today; adding a
  third full graph to avoid commit-time projection is not accepted. Browser
  conversion, persisted validators, Unicode/Scalar64, and rejection receipts
  remain. An envelope hash cannot detect item reuse across sequences by itself.
- MOVE and RECASE share the guarded rename mechanism, but have different initial
  evidence-check precedence, occupancy semantics, diagnostics and recorder calls.
  Method selection stays at recording time, not before filesystem work.
- Publication observers share confirmed-publication and final ambiguity paths.
  Both intact-temp and changed-temp classification differ for update versus new
  files. Update backup is probed earlier by `_observe_publication`; retain that.
- The small argument/no-op-wrapper removals remain accepted. Prior optional
  recording tails and legacy recording-key pops are now shelved by user scope.
- Preserve typed recording causes before diagnostic rendering, especially both
  prerequisite journal writes. Preserve accepted-settlement reconciliation,
  journal ownership/type guards, restoration probes, root revalidation and the
  unchanged settlement oracle. Report labels such as "throwaway" do not override
  the causal ordering documented by EXECUTOR.
- Source-derived encoding counts establish repeated work, not a measured speedup
  or universal resource bound. No benchmark or candidate equivalence was proved
  during discovery.

### Retained guarantees and failure detection

| Risk | Mechanism and retained witness | Owner |
| --- | --- | --- |
| Invalid stat admitted | Removing nested rechecks must not remove leaf constructors' exact scalar/type rules or stat adoption's base-type refusal; preserve scalar identity and scan-model tests. | NR-1 |
| Progress fallback advances on refused emit | `latest_progress` must update only after successful emission; preserve `test_runner_uses_only_emitter_accepted_progress_as_fallback`, including Terminal bytes. | NR-2 |
| Wrong or excessive scan reaches DB | Exact type, root/scope relation and domain/information limits are different checks; preserve first-excess and inventory-before-ledger tests. | NR-3 |
| Receipt/hash drift | Identical canonical payload bytes and separate item identity/payload receipts must survive; event-v5 literal fixtures, replay and tampered-read tests detect it. | NR-4/5 |
| Invalid event flushes prior pending data | New encoding must validate before `_admit` can flush, append, or update hashes; preserve invalid-projection prefix test. | NR-4 |
| New retained mutable projection | Local reuse must end with the call; preserve pending owner shape and queue bounds by inspection and existing custody tests. | NR-5/9 |
| Rename overwrites, misclassifies, or records early | Preserve conditional rename, final guard sequence, committed marker, exact recorder dispatch and operation-specific refusals. | NR-7 |
| Update treated as new publication | Retained live target means something different from absent new-file target; independent state fixtures plus oracle cover both branches. | NR-8 |
| Exception precedence or cleanup changes | Removing a no-op wrapper cannot alter inner ACL translation, unwind cleanup, retries or progress; runtime/settlement/control witnesses and unchanged oracle remain. | NR-6/9 |
| Tests stop detecting retained behavior | Every assertion retirement needs a disposition and an independent successor or explicit unsupported-only classification; fault/harmless controls below exercise this. | NR-0–9 |

### Regression definition and test-change rules

A regression is a violation of a retained guarantee, including loss of its only
effective witness. This includes changed supported input acceptance/refusal,
wrong error/control precedence, byte/schema/hash drift, lost alias isolation for
mutable inputs, changed native call order, premature recording, changed progress
or terminal truth, and new retained transport state. It is not defined by diff
size, test count, or whether the old helper still exists.

Intentional differences are limited to: no second reconstruction/element sweep
in the named families; reuse allowed for exact admitted immutable stat values;
one normalized Progress may serve internal/public roles; removal/relocation of
named private arguments/helpers; and local history encoding/projection reuse.
Fresh identity is not required for those immutable outputs, but new alias
identity is not itself a new public guarantee. Initial validation, supported
subclass normalization at existing seams, and mutable-state checks remain.

Classify every changed/red assertion as: **retained**, **relocated**,
**retired unsupported-only**, **retired representation-only**, or **regression**.
Record old node/parameter/assertion, protected fact, replacement node if needed,
and reason. No blanket deletion of tests containing `object.__setattr__`: mutation
of ordinary mutable continuations is still supported, and forged fixtures can
also exercise a genuine retained boundary. Remove only the relevant assertion
or parameter when other assertions protect valid behavior. An unexplained red
test or missing successor cannot close a checkpoint.

Green alone is insufficient. Use independently specified fixtures, source
inspection, unchanged oracle comparisons, and finite fault/harmless controls.
A control counts only when its intended interception was reached and a named
retained assertion failed; setup/import/syntax errors do not count. Test-only
variations run in disposable task-owned copies and do not enter product commits.

### Test cleanup and additions assessment

| Family | Cleanup permitted | Needed characterization or additional witness |
| --- | --- | --- |
| Stat graph | Within the three named functions, retire only forged-frozen re-certification/fresh-copy expectations; retain source hash projection tests outside this population. | Exact leaf/stat refusal and independent fact tuples with/without identity and creation time; prove valid repeated adoption without reconstructing nested values. |
| Progress | Rewrite `test_runner_uses_a_detached_progress_snapshot_for_terminal_fallback` and `test_runner_keeps_private_progress_truth_from_the_emitter` only to retire reflective-frozen protection or duplicate assertions. | Ordinary producer rebinding, same fields at emit, canceled/failed fallback, and accepted-versus-rejected emitter behavior. Retain the existing accepted-emission test; add only missing cases. |
| Scan | Replace assertions requiring redundant validation location/count with constructor and transfer witnesses. `test_scan_adoption_preserves_identity_without_constructor_validation` is retained evidence, not cleanup bait. | Constructor invalid leaves, valid but excessive source/warning tuples, wrong transfer type/root/scope, complete/incomplete/offline and scoped recorder behavior. No new population cartesian product. |
| History | Share local test setup if duplicated solely by the moved helper; do not delete corruption, replay, omission, Unicode, or boundary cases. | Encoder/validator agreement for all existing canonical body fixtures; malformed shapes/Scalar64/version, Unicode and exact size edges; local projection reuse with independent bytes/SQL expectations. |
| Rename | Retarget private patches to the new symbol owner; share identical setup only. Keep MOVE/RECASE as separately identified scenario rows. | Existing success/occupancy/final-guard and nonbyte fault cases are strong; add evidence-check precedence and recorder-dispatch cases if NR-0 finds no exact witness. |
| Publication | Consolidate helper-specific setup, not different new-file/update expectations. Keep public settlement outcomes and oracle unchanged. | Add a bounded direct observation table for the branch distinctions below; current changed/missing/unreadable test covers the lower published-target helper, not the complete dispatch distinction. |
| Unused arguments/wrapper | Update callers and private tests, remove only support made orphaned by those edits. | Existing success/control/ACL-failure tests plus oracle; no new test that merely asserts a private parameter is absent. |

No target number of deleted tests or net source lines is an acceptance criterion.
New tests protect missing behavior or structural-work obligations, not the
spelling of the replacement implementation. No broad test-ablation pass is in scope.

## Checkpoint register

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| NR-0 | Qualify baseline and freeze assertion/evidence dispositions for this register. | — | Current-source complete baseline, imports, protected identities, oracle repeat 3, finite witness map | complete |
| NR-1 | Reuse exact immutable file-stat graphs without redundant construction. | NR-0 | Initial refusals, independent fact tuples, stat consumer tests, construction witness | pending |
| NR-2 | Use one normalized Progress snapshot at runner emission. | NR-0 | Accepted-emission fallback and control/field equivalence | complete |
| NR-3 | Remove repeated scan element certification after full initial validation. | NR-0 | Constructor/transfer/limit/recorder witnesses and unchanged scan payloads | pending |
| NR-4 | Persist history's already-validated canonical envelope bytes. | NR-0 | Byte equivalence, invalid-before-mutation, canonical byte limits | pending |
| NR-5 | Reuse local history item projections for hashes and readback columns. | NR-4 | Replay/corrupt-read/column/hash equality; no retained cache | pending |
| NR-6 | Remove the three unused executor arguments and no-op exception wrapper. | NR-0 | Caller inspection, runtime/settlement/control tests and oracle repeat 3 | complete |
| NR-7 | Share the MOVE/RECASE guarded rename sequence. | NR-6 | Separate operation traces/refusals, late recorder dispatch, oracle repeat 3 | pending |
| NR-8 | Share publication observation with explicit new-file/update distinctions. | NR-7 | Independent observation matrix, settlement outcomes, oracle repeat 3 | pending |
| NR-9 | Close combined reduction and evidence/documentation consistency. | NR-1–8 | Complete/headed suite, imports, unchanged oracle, control replay, final review | pending |

These are semantic outcomes, not a list of every permitted edit. Exact caller
updates, focused tests and matching documentation belong to their outcome.
No helper, test population or behavior outside these families enters implicitly.
Execute serially in register order unless the user separately requests delegation.

The execution authorization permits parallel independent checkpoints. Root owns
integration commits and this register; builders own assigned source/test/module
documentation in isolated checkouts, and fresh reviewers have read-only scope.
Disposable checkouts live at `build/reduction-followup/worktrees/<checkpoint>`
on `codex/nr-<checkpoint>` branches. Only one owner edits a checkout at a time.
Each outcome is reviewed before its own commit and integration; shared docs are
reconciled without absorbing another checkpoint's source. At NR-9, account for
every branch/checkout, integrate all verified outcomes to the starting branch,
then remove only fully accounted task-owned temporary checkouts and refs.
A stopping blocker halts its dependent lane only; finish independent work before
preserving the isolated blocked lane under AGENTS.md's recovery procedure.

## Detailed checkpoints

### Shared gate and evidence conventions

Every checkpoint uses the eight fields below. A mergeable checkpoint requires all
its criteria, named tests, controls, documentation and adversarial review; it may
not defer its own regression. Gates preserve the qualified baseline modulo the
explicit assertion dispositions. A failed comparison is investigated, not
silenced by updating its expected value.

Evidence lives under ignored `build/reduction-followup/<base>/<checkpoint>/<run>/`.
Use stable checkpoint IDs and unique timestamp run names; put raw command output
in `logs/`, disposable variations in `controls/`, and one manifest at run root.
The manifest records actual cwd/interpreter/import origins, source/dirty state,
commands, outcomes, node dispositions, control hits, protected hashes and review.
Do not overwrite prior runs. Clean only task-owned disposable control copies
after evidence capture and reviewed closure; preserve logs/manifests and failed
attempts. This convention applies before creating those directories.

No new noisy performance SLO is proposed. Constructor/traversal/encoding
elimination is an analytical implementation claim over named functions and
immutable exact-base inputs. Use counted witnesses to corroborate the source
derivation, not timing to prove complexity. Timing and line deltas, if recorded,
are diagnostics only under DEFENSE §7. No new memory-containment certificate,
benchmark framework, permanent certification token, or production test hook.

Establish these PowerShell variables from the actual qualified environment:

```powershell
$reductionPython = 'F:\GitHubRepositories\NamiSync\build\test-refinement\1026541\baseline\checkout\.venv\Scripts\python.exe'
$reductionImports = 'F:\GitHubRepositories\NamiSync\build\test-refinement\1026541\baseline\checkout\.venv\Scripts\lint-imports.exe'
$env:NAMISYNC_TEST_NODE = 'C:\Users\Spectrum\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
```

Run from this integration checkout. Do not silently fall back if these paths are
stale; qualify a replacement and record it. Native tests need usable Windows
temporary storage. Use existing TESTS.md conventions, preserve capability skip
reasons, and never count environment/setup failure as a product fault detection.

### NR-0 — Baseline and dispositions

**Objective.** Establish the finite comparison and test-retirement denominator
before changing production or deleting assertions.

**Scope and approach.** Freeze actual source, dirty exclusions, exact collected
nodes/parameters for the families above, and each guarantee's existing/missing
witness. Search the named producers and all their repository callers plus their
owning tests; terminal observation is one classified inventory with no unassigned
affected assertion. Do not turn this into a repository-wide test audit.

**Acceptance criteria.** Qualify the complete current-source suite, all imports,
and unchanged oracle three-run stability. Reconcile existing skips by exact node
and capability; required headed gates cannot be skipped. Record any initial
failure and resolve only under containment rules. Hash all 11 protected paths
listed by the preceding register's authority manifest and compare with committed
source; record that list in this run so ignored prior evidence is not required
to resume. Also preserve committed identity-vector fixtures and wire literals.

**Regression watchlist.** Wrong checkout imports, hidden baseline failures,
missing headed/Node cases, stale protected inputs, or lost assertion ownership.

**Tests and evidence.** Run `& $reductionPython -m pytest -q -o 'addopts='`,
`& $reductionImports`, and
`& $reductionPython -m tools.executor_settlement_audit check --repeat 3`.
The two protected executor files are `tools/executor_settlement_audit.py` and
`tools/executor_settlement_baseline.json`. The other nine unchanged paths are:

- `tests/bridge_transport_custody.py`
- `tests/interfaces/web/_bridge_retained_memory.py`
- `tests/interfaces/web/_bridge_transport_custody.py`
- `tests/interfaces/web/sh_g_8_transport_calibration.json`
- `tests/interfaces/web/sh_g_8_transport_ceiling.json`
- `tests/interfaces/web/sh_g_8_transport_holdout.json`
- `tests/interfaces/web/test_bridge_transport_custody.py`
- `tests/interfaces/web/test_bridge_transport_custody_holdout.py`
- `tests/interfaces/web/test_bridge_transport_custody_live.py`

Capture collection,
logs and actual imports. Predeclare the fault/harmless controls in NR-1–8 before
candidate edits. Exact test-node binding refines evidence, not accepted scope.

**Documentation and handoff.** Fill baseline and assertion manifest references
here and in HANDOFF; retain the closed discovery evidence separately.

Qualified execution evidence is under
`build/reduction-followup/50bc05e/NR-0/20260908-144229/manifest.json`.
Both complete runs passed 4,741 tests with the same four WinError 1314
capability skips; explicit headed verification passed all 28 cases. Import
contracts: 12 kept, none broken. The unchanged oracle passed 30 scenarios in
three identical runs. The manifest records exact skipped nodes, command logs,
actual interpreter/import origins, source exclusions, and all 11 protected
authority comparisons plus committed identity/event-v5 fixtures. Git-filtered
content equality and raw-byte provenance are recorded separately.

The preimplementation assertion authority is
`build/reduction-followup/50bc05e/NR-0/dispositions-20260908-145100/disposition-map.json`
(SHA-256 `ef37014c66943f8a00f303f911056225aff1b149034be841e69ad2625ff03378`).
Its companion `publication-expectations.json` has SHA-256
`911c678e8513e8abb1514a98f3c35b9f9c628cb0ddfd54c0bb3aa66d39b5bafc`.
The finite map binds 66 assertion rows, 18 missing witness groups, and 25
controls (17 fault, eight harmless) to the eight accepted families. Coverage
gaps are checkpoint-owned additions, not product defects or new scope.
Publication expectations are 30 literal rows authored before implementation.
Fresh GPT-5.6 Terra review passed after correcting missing disposition reasons
and fixture/hash indexing; no product finding or scope expansion was identified.

**Adversarial review.** Recheck the inventory against source and existing tests;
reject any retirement that removes a retained boundary or relies on candidate-
derived expected output. Confirm source/schema/wire/oracle exclusions.

**Commit gate.** Baseline qualified and dispositions closed; commit only planning
and evidence indexing as `docs: qualify narrow reduction baseline and witnesses`.

### NR-1 — Immutable stat graph

**Objective.** Remove construction used only to re-certify exact stat leaves.

**Scope and approach.** Only the three model functions in the population table
and necessary callers/tests/docs. Keep first validation of `FileIdentity`,
`MetadataSnapshot`, and FileStat scalar fields. `snapshot_file_stat` may adopt
an exact immutable base graph; `file_stat_fact` reads the same eight scalar facts
without rebuilding it. Preserve wrong-type/subclass refusal at this exact seam.
No attestation/content/selection redesign or hash-projector cleanup.

**Acceptance criteria.** All supported leaf and stat constructor refusals remain;
fact tuples and consumers' observed metadata/identity stay identical. No nested
FileIdentity/MetadataSnapshot or FileStat reconstruction on exact stat adoption
or fact extraction. No native probing is removed or cached.

**Regression watchlist.** Boolean-as-integer, signed-width and 128-bit identity
limits, missing identity/creation time, replacing semantic facts with object
identity, or weakening adoption for mutable/lookalike inputs.

**Tests and evidence.** Characterize independent tuples for identity present/
absent and creation time present/absent, file/directory kind, boundary scalar
values, invalid nested types and subclasses. Keep tests/core scalar identity and
tests/test_core_scanplan coverage; add only missing cases. Corroborate absence of
reconstruction by instrumenting constructors after fixture construction in a
task-local witness, not by pinning helper names. Fault controls: omit a stat fact;
accept a wrong nested type. Harmless control: return an equal fresh validated stat
at a consumer seam. Run `& $reductionPython -m pytest -q --dept core --dept scanner
--dept preflight --dept executor --dept verifier --dept database --dept workflows`
as one PowerShell line. All selected witnesses must pass; both faults must be
detected at retained assertions and the harmless variation must pass.

**Documentation and handoff.** CORE owns adoption/fact behavior; WORKFLOWS and
VERIFIER explain unchanged evidence consumers if their existing copy claims
need narrowing. Record exact assertion dispositions and structural evidence here.

**Adversarial review.** Inspect transitive fields to establish immutability;
check every `snapshot_file_stat`/`file_stat_fact` consumer and distinguish a
reflectively changed frozen value from a legitimately mutable continuation.

**Commit gate.** Shared gate complete; `refactor(core): reuse admitted immutable stat graphs`.

### NR-2 — One normalized Progress

**Objective.** Remove only the runner's second identical Progress object.

**Scope and approach.** Keep the first producer snapshot and subclass-to-base
normalization. Share it with the emitter and fallback state; assign fallback
only after the emitter returns successfully. Do not change result accumulation,
Progress validation/throttling, pause/cancel handlers or terminal projection.

**Acceptance criteria.** Every field reaches the emitter unchanged; rejected
progress never replaces accepted fallback. Existing terminal bytes/status,
pause behavior and exception precedence remain. No promise to withstand
reflective mutation of that shared frozen object is added or retained here.

**Regression watchlist.** Advancing fallback before callback acceptance, losing
item-attempt fields, weakening producer normalization, or using last attempted
rather than last accepted bytes after cancellation/error.

**Tests and evidence.** Retain the accepted-emission regression named above.
Rewrite only the reflective assertions in the two identified snapshot tests;
use normal rebinding and supported callback refusal for retained semantics.
Characterize all progress fields and cancel/failure after accepted/rejected
emission before implementation. Fault: assign latest progress before emit.
Harmless: reconstruct an equal Progress at the producer seam. Run
`& $reductionPython -m pytest -q --dept core --dept dispatcher --dept workflows --dept interfaces`.
Pass requires matching public fields/fallback, detected fault and accepted control.

**Documentation and handoff.** CORE records one normalized immutable snapshot
and accepted-emission authority; do not broaden the DEFENSE fault model.

**Adversarial review.** Follow exception paths after emit, including terminal
fallback; show that fewer objects do not move the state-commit point.

**Commit gate.** Shared gate complete; `refactor(core): reuse normalized runner progress`.

**Execution evidence (2026-09-08).** Removed the second Progress construction;
the first normalizes all fields and fallback advances only after accepted emit.
The two named reflective tests were revised according to the frozen map, with
ordinary rebinding, exact-base fields, cancel/failure fallback and returned-result
truth retained. Prechange and candidate focused selections each passed six cases;
the neighborhood passed 3,266 with one existing WinError 1314 capability skip.
All 12 import contracts and 11 protected comparisons passed. Evidence:
`build/reduction-followup/7fe09b8/NR-2/20260908-161500/manifest.json`.
The fault reached the retained `17 == 5` failure; harmless producer reconstruction
passed. Fresh GPT-5.6 Terra review passed after the task-local fault replacement
gained an exact count-one guard and both controls were replayed. Initial sandbox
failures are separately retained and excluded from candidate qualification.

### NR-3 — Narrow scan graph validation

**Objective.** Trust exact constructed ScanResult elements downstream while
retaining independent admission and requested-scan semantics.

**Scope and approach.** Full initial ScanResult validation remains. Remove only
the repeated leaf/warning/scope sweeps in adopt_scan_result, InventoryCommand's
scan check and recorder `_scan_projection`. Exact type/tuple transfer checks,
domain/information counts and token correlation stay; workflow root/scope checks
stay. Keep recorder command scalar revalidation, per-record projection guards,
SQL hashing/reconciliation and planner sorting. No adoption-token replacement.

**Acceptance criteria.** Constructors still reject malformed child types/scopes;
valid oversized tuples still produce the same typed first-excess refusal before
retention/publication/ledger setup. Empty, complete, incomplete, offline and
selected-scope scans retain exact rows, missing inference and command receipts.
Identical scan payload hashes and projection ordering remain. Removed downstream
checks do not migrate into another whole-population pass.

**Regression watchlist.** Confusing shape proof with capacity proof, counting
after filtering/deduplication, accepting wrong root/scope, or inferring missing
files from incomplete/offline evidence.

**Tests and evidence.** Retain plan-review limit and inventory-before-ledger
tests, scan adoption identity witness and recorder scope/rollback tests.
Characterize constructor failure for each files/directories/unsupported/warnings
population, valid-but-excess domain/information independently, and semantic
scope mismatch. Use existing small limit-injection seams plus an unmodified
120,000/120,001 boundary witness per independent population if no existing one
covers it. Structural-work witness at 0, 1 and 1,024 admitted rows observes only
adoption/command validation (exclude required serialization/reconciliation).
Source inspection establishes no repeated leaf sweep over the admitted domain;
counts corroborate that conclusion without requiring a particular helper name.
Faults: omit domain admission; accept wrong inventory scope; remove initial child
type refusal. Harmless: equivalent helper relocation with identical counts and
output. Run `& $reductionPython -m pytest -q --dept core --dept scanner --dept planner
--dept preflight --dept workflows --dept database` as one line. All retained
checks, three fault detections and harmless control must pass their disposition.

**Documentation and handoff.** CORE, WORKFLOWS, INVENTORY and RECORDER identify
initial shape ownership versus continuing population/semantic admission. No
DEFENSE limit, schema reset requirement or planner input-order change.

**Adversarial review.** Trace a valid excessive producer result and wrong-scope
result, not only a malformed frozen-object forge. Verify recorder entry still
has validated scalar command facts and retains atomic missing inference.

**Commit gate.** Shared gate complete; `refactor(core): remove repeated admitted scan validation`.

### NR-4 — Reuse validated history encoding

**Objective.** Encode a history envelope once at its local validation/storage boundary.

**Scope and approach.** Add the smallest core validate-and-encode operation and
use its returned bytes in HistoryObserver admission. Preserve existing
`validate_event_v5_envelope` successful return and refusal behavior; share
mechanics without a validation-skip flag. Dispatcher `canonical_event_bytes`
and event transport are unchanged. No broad JSON utility or schema change.

**Acceptance criteria.** Same canonical bytes and digest for every existing v5
fixture, including review-limit Terminal; validator behavior on Progress is
unchanged even though history rejects Progress/Terminal. Invalid events cannot
flush or mutate pending history. Exact maximum and first excess stay at current
owners. The history local path uses the checked bytes for storage/hash rather
than serializing/rebuilding the graph again.

**Regression watchlist.** Dropped semantic validator, changed Unicode/key order,
Scalar64 coercion, new Progress byte refusal, catching different exceptions,
moving invalid-event rejection after window flush, changing rejected receipts.

**Tests and evidence.** Extend existing event-v5 literals/negative fixtures to
the new encoder; do not generate expectations from it. Keep invalid-projection
prefix test, adjusting its internal interception only with a proven hit. Retain
EventHub size wall, history lower-policy rejection, and browser consumers.
Faults: bypass semantic validation; change one canonical encoding option; advance
pending state before validation. Harmless: equivalent JSON field insertion order.
Use one task-local counted encoding witness for each reliable body fixture,
with construction excluded; no timing claim. Run
`& $reductionPython -m pytest -q --dept core --dept database --dept dispatcher --dept interfaces`.
Pass requires exact bytes, public validator compatibility, three detections and
passing harmless control, with no new queue/cache fields.

**Documentation and handoff.** CORE and HISTORY record checked-byte ownership
and unchanged boundary validation; update exact core contract locator only if
the new public symbol needs a locator. Wire/schema descriptions stay current.

**Adversarial review.** Compare both encoders on admitted primitives, then prove
semantic rejection still precedes any history mutation. Inspect direct validator
callers, including Progress and persisted decode, for compatibility.

**Commit gate.** Shared gate complete; `refactor(history): reuse validated envelope bytes`.

### NR-5 — Local item projection reuse

**Objective.** Remove repeated projection within history admission/readback calls.

**Scope and approach.** Hash `_admit`'s existing projected body. During readback,
project the decoded item once and reuse it for item hash and SQL-column checks.
Keep necessary conversion helpers explicit. Do not share raw JSON as domain
authority, remove hashes, alter `_PendingEvent`, or cache commit-time projections.

**Acceptance criteria.** Same stored payload/receipt/item/identity hashes,
canonical/noncounting duplicate behavior, conflict refusal, readback columns
and recording detail/omission semantics. Projection lifetime stays call-local;
no extra retained whole-body representation or cache invalidation mechanism.

**Regression watchlist.** Hashing the complete envelope as an item, omitting
detail from semantic hash, reusing raw JSON instead of decoded canonical values,
or allowing columns inconsistent with the envelope.

**Tests and evidence.** Existing history replay, rejected-first duplicate,
semantic conflict and tampered column/identity tests stay. Add missing parameter
rows for both operation/integrity bodies, optional reason/recording fields and
nonempty detail. Faults: omit detail from item hash; bypass column comparison.
Harmless: reconstruct an equal decoded item before projection. Run
`& $reductionPython -m pytest -q --dept database --dept workflows --dept interfaces`.
Finite local-call witness confirms no duplicate projection inside the two named
paths; inspect lifetime rather than claiming memory bounds from timing. Pass
requires equivalent durable rows and both intended detections.

**Documentation and handoff.** HISTORY records local reuse and distinct hash
purposes; preserve DATABASE schema and retry/idempotency contracts.

**Adversarial review.** Follow different sequence/same item and same identity/
changed payload, including rejected receipts. Inspect readback normalization and
the unchanged pending object fields.

**Commit gate.** Shared gate complete; `refactor(history): reuse local item projections`.

### NR-6 — Unused executor arguments and wrapper

**Objective.** Remove the finite obsolete plumbing family without changing policy.

**Scope and approach.** Remove only `_record.detail`, `_noop.state`,
`_complete_published_byte_operation.state`, their call arguments, and the outer
no-op exception wrapper in `_prepare_copy`. Keep inner handlers, typed recording
construction/diagnostic order, recording tails and legacy key pops.

**Acceptance criteria.** No stale callers; return values and supported exception,
cleanup, recorder, progress and filesystem traces are unchanged. No new wrapper
or compatibility alias is added solely for private tests.

**Regression watchlist.** Deleting the wrong try block, disturbing ACL exception
translation, shifting argument evaluation, or including an apparently redundant
recording-cause write in this cleanup.

**Tests and evidence.** Search the full repository for each edited symbol before
and after. Existing executor runtime/settlement/pending-cancel/ACL tests and
`& $reductionPython -m pytest -q --dept executor --dept workflows` must pass,
followed by unchanged oracle `check --repeat 3`. No implementation-mirroring
new test is required. Harmless control: the pre-change private signatures/no-op
wrapper with matching calls must still pass retained behavioral tests.

**Documentation and handoff.** EXECUTOR states unchanged collaborator and
recording-order semantics; record mechanical scope and caller verification here.

**Adversarial review.** Read the whitespace-insensitive diff and each old/new
call site; verify removed arguments were side-effect-free values and only the
outer re-raise was removed. Inspect oracle output, not merely its exit code.

**Commit gate.** Shared gate complete; `refactor(executor): remove unused runtime plumbing`.

**Execution evidence (2026-09-08).** Only `runtime.py` changed: the three named
parameters/call arguments and outer no-op rethrow. Executor/workflows passed
1,145 cases; the prechange harmless control passed the same 1,145; the unchanged
oracle passed 30 scenarios across three runs. Evidence and exact import/source
provenance are in
`build/reduction-followup/7fe09b8/NR-6/20260908-151000/manifest.json`.
Fresh GPT-5.6 Sol review passed after explicit runtime metadata was added.
All protected/fixture paths remain unchanged. EXECUTOR already describes the
retained semantics, so no textual module-doc edit was needed. No test assertions
were removed. Initial temporary-directory denial is retained as environment-only
evidence. NR-9's harmless replay reverses only this plumbing; remap overlapping
rename call-site hunks narrowly if NR-7 prevents direct reverse-patch application.

### NR-7 — Guarded MOVE/RECASE rename

**Objective.** One explicit rename mechanism for these two reviewed operation kinds.

**Scope and approach.** Share `_move`/`_recase` common work inside runtime, using
their closed operation distinction. Retain prologue order (including source
evidence versus prior-target checks), RECASE path rules, MOVE absence check,
flush/final guards, conditional rename, committed marker, durability/stat checks
and late recorder method selection. Do not include TRASH or MOVE_UPDATE and do
not extract recording tails as a second simplification.

**Acceptance criteria.** Identical operation-specific success/refusal/error text,
filesystem and recorder call order, committed-marker point and settlement truth.
Same occupancy/drift handling with no copied bytes or trash for RECASE. No new
callback strategy object, arbitrary mode/configuration, or mutation authority.

**Regression watchlist.** A destination-absence check breaks case-only rename;
omitting it changes MOVE refusal. Eager recorder attribute lookup changes a
collaborator call point; moving the committed marker changes exception settlement.

**Tests and evidence.** Preserve separate MOVE/RECASE success, source drift,
occupancy, final-guard, precommit/commit-then-raise and pause/cancel witnesses.
Characterize both-invalid prologue precedence and recorder method/access timing
if missing, using existing filesystem/recorder seams. Faults: omit MOVE absence
guard; use MOVE recording for RECASE; set committed after durability callback.
Harmless: separate equivalent operation-specific wrappers over the common body.
Run `& $reductionPython -m pytest -q --dept executor --dept workflows --dept database`
and unchanged oracle `check --repeat 3`. Pass requires all three fault detections
and trace/behavioral parity; oracle does not substitute for uncovered prologues.

**Documentation and handoff.** EXECUTOR records shared mechanics with distinct
operation semantics; recorder contracts stay unchanged. Map migrated test patches
to the actual owner without changing their independent expected behavior.

**Adversarial review.** Compare aligned operation traces, including failures at
flush, each guard, rename, durability, post-stat and recording. Reject abstraction
that hides the operation distinction or adds policy parameters.

**Commit gate.** Shared gate complete; `refactor(executor): share reviewed rename mechanics`.

### NR-8 — Common publication observation

**Objective.** Share observation mechanics while keeping publication classifications explicit.

**Scope and approach.** Combine the two named observers behind their existing
runtime owner. Common published-target and temp/target probes surround explicit
new-file/update prepublication branches. Preserve update-backup probing before
publication observation, outer probe-error handling, diagnostic text and
MOVE_UPDATE's later observation. Reducers and mutation verdicts are untouched.

**Acceptance criteria.** Every finite observation row below yields the same
classification, target/temp state and diagnostic presence/text, and the same
probe order. Settlement outcomes and recording degradation stay unchanged.
No new repeated filesystem probes or broadened claim of confirmed publication.

**Regression watchlist.** Treating retained update live bytes like a new-file
occupied target; losing changed-temp distinctions; confirming from an ambiguous
target; moving backup probing or swallowing a probe error at a different layer.

**Tests and evidence.** Bind existing tests to this finite matrix and add only
uncovered rows through `_observe_publication` and existing fake FS seams:
for COPY/new-file and UPDATE, (a) published latch with expected/missing/changed/
unreadable target; (b) unpublished intact temp with absent/reviewed-old/foreign
target; (c) unpublished changed temp with those same three target states;
(d) unpublished missing temp with absent/prepared-matching/foreign target;
(e) temp-probe error and target-probe error. Rows use explicitly distinct old,
prepared and foreign file identities; expected classifications are authored from
the retained operation rules before implementation, not captured from candidate.
Keep existing MOVE_UPDATE composition and backup-error tests; add a dispatch/order
witness only if absent. The lower published-target helper test is insufficient
alone. Faults: use new-file retained-temp rule for UPDATE; move backup probe after
publication probe; collapse changed target into matching publication. Harmless:
equivalent private wrapper/function relocation. Run
`& $reductionPython -m pytest -q --dept executor --dept workflows`
and unchanged oracle `check --repeat 3`. Every matrix row must be classified and
pass, all faults detected, harmless control accepted; no skipped/unclassified row.

**Documentation and handoff.** EXECUTOR records common observation ownership and
retained new/update distinctions; retain exact oracle files and baseline.

**Adversarial review.** Independently derive matrix expectations from publication
evidence and retained live-target meaning, then inspect source, traces and fault
hits. A disagreement with baseline is a finding, never permission to change it.

**Commit gate.** Shared gate complete; `refactor(executor): share publication observation mechanics`.

### NR-9 — Integrated closure

**Objective.** Verify the combined product and its test/disposition accounting.

**Scope and approach.** Integrate only NR-1–8, reconcile shared consumers and
replay every declared fault/harmless control on the combined candidate. This is
closure, not a new cleanup population. Follow the overall sweep below.

**Acceptance criteria.** Every row closes with retained guarantees and qualified
baseline intact; all protected files match; no unresolved scope/regression or
unclassified assertion remains. Implementation benefit is evidenced by removed
named mechanisms, not net LOC/test counts or a promised speedup.

**Regression watchlist.** Stat/scan reuse affecting recorder hashes; progress
reuse affecting serialized terminal truth; combined history changes altering
replay; helper extraction changing settlement on exceptional paths.

**Tests and evidence.** Complete/current-source headed suite, imports, unchanged
oracle repeat 3, integrated control replay and exact assertion reconciliation.
Use the commands below; retain logs/manifests and evidence for all skipped nodes.

**Documentation and handoff.** Close this register; update HANDOFF and the existing
CHANGELOG task. Update README only if synopsis/index changes. Audit CORE,
WORKFLOWS, INVENTORY, RECORDER, HISTORY and EXECUTOR against final behavior;
ARCHITECTURE locators, DEFENSE and database schema descriptions must not drift.

**Adversarial review.** Review the whole diff from the retained guarantees and
independent expectations, including test deletions. Check that all shelved items
and protected authorities are untouched; verify evidence provenance directly.

**Commit gate.** All final evidence complete; `docs: close narrow reduction verification`.

## Overall final sweep

1. Trace scan -> plan/inventory -> recorder and executor -> Progress/result ->
   dispatcher/history -> readback/UI. Require existing end-to-end tests plus
   checkpoint controls to preserve exact row/hash/terminal behavior.
2. Run from the qualified current checkout:

   ```powershell
   & $reductionPython -m pytest -q -o 'addopts='
   & $reductionImports
   & $reductionPython -m tools.executor_settlement_audit check --repeat 3
   git diff --check
   ```

   This includes installed headed and required Node witnesses under TESTS.md;
   an ordinary-only run cannot close NR-9. No required headed gate may skip.
3. Replay the finite fault and harmless controls, recording intended hits and
   independent failure/pass observations. Reconcile every retired assertion
   with the frozen manifest and preserve all remaining tests/authority inputs.
4. Confirm no schema/version/reset change, weaker parser/type/Unicode/Scalar64
   refusal, population-check relocation, new retained graph, replayed mutation,
   changed recording cause, or lost cleanup. Check actual import origins and
   protected file hashes against NR-0 rather than assuming the command cwd.
5. Validate plan/doc links and current source-owner statements; inspect exact
   staged paths for accidental cleanup or included reports/build artifacts.
   A clean tree is not achieved by deleting unrelated files.
6. Record a final adversarial review with concrete source/test/evidence findings
   and dispositions. Completion requires all register rows and this integrated
   review; individually green checkpoints alone are insufficient.

## Resumption block

- Current state: execution authorized; NR-0 baseline and disposition qualification
  complete with separate GPT-5.6 agents and a fresh reviewer. Product edits
  have not begun. Discovery's 25-pass result is historical evidence only.
- Source base: `50bc05ebab57da724faa11ccf4f8882cdcb6a291`. Existing branch at
  creation: `milestone1-anthony`. Recheck HEAD/dirty files and qualify actual
  product imports before running NR-0. Use a task branch with `codex/` prefix
  when implementation is separately requested; do not commit unrelated changes.
- Next action: launch isolated NR-1, NR-2, and NR-6 checkpoint builders from the
  committed NR-0 baseline under root coordination.
- Evidence already present: prior PR-9 integrated evidence under
  `build/production-reduction/pr9/`; protected-input list under
  `build/production-reduction/40fd8a5/protected/authority-inputs.json`; this plan's
  run layout and verified command forms are above. Missing ignored evidence is
  not grounds to invent a pass; reconstruct from committed authorities and rerun.
- Preserve prior ignored worktrees/evidence,
  protected oracle/SH-G-8 files, and pre-existing documentation changes. The
  user-owned root reports were already absent at execution; do not restore them. Plan
  creation migrates only its own dispositions and updates the index/handoff.
- Deferred: all shelved mechanisms listed in Scope, including recording tails,
  pause/cancel and mutation-verdict constructors. No evidence requires another
  feature decision now. Any needed expansion goes to the user.
- Stop and preserve state under AGENTS.md for supported-path data loss/corruption,
  unauthorized/out-of-root mutation, supported security/hard-wall escape, false
  durable/terminal success, duplicate/replayed mutation, or unrecoverable work.
  Its second same-mechanism / third substantive unplanned-defect limits also
  apply. Finish only the allowed safety-preserving atomic outcome, produce the
  mechanism table, and obtain adjudication. No extra stop class is introduced.
- A checkpoint regression must be corrected before its mergeable commit except
  where a mandatory stop above preempts further work. For interruption before
  readiness, use the exact task-owned WIP branch/commit recovery procedure in
  AGENTS.md; never merge the recovery commit as-is. An unresolved named gate
  cannot be bypassed by retiring a retained test or rewriting the oracle.
