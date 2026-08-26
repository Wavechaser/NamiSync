# Session Handoff

Status (2026-08-27): checkpoint **3.3 is committed** at `092b628`.
Checkpoint 4 is in its pre-model ownership audit, before the first required
model commit. The production command map still has exactly nine rows; no new
task command or control is active. The analytical model has not been frozen,
calibrated, or accepted.

## Delivered in this session

- `092b628` removes private Python v3/v4 and browser v4 compatibility, with
  failing-first source guards, all-family live refusal, isolated reintroduction
  witnesses, and whole-batch drain rejection before cursor/delivery mutation.
- `ff23af9` replaces unbounded dispatcher store/custody exception collections
  with sticky failure flags. Weak-reference regressions prove contained error
  graphs retire across repeated session completion/close cycles.
- `fec8825` keeps exact dispatcher worker ownership through real thread exit,
  makes close join under one bounded deadline outside dispatcher locks, and
  releases scheduler/audit-factory exception graphs without weakening custody.
- The observation-stream prerequisite removes closed-stream history. Stop and
  replacement adoption share one lock; cleanup snapshots the current stream,
  while closes and joins run outside that lock. Independent review cleared
  the weak-reference churn and both stop/adopt race directions.
- Full-result header diagnostics now use the terminal summary's existing
  whole-value omission rules before settlement, audit, or publication. Header
  counts are not double-counted with item omissions; bounded objects retain
  identity. Ordinary exception-formatting failure becomes one omission rather
  than losing the terminal, while `BaseException` still escapes.
- `32d7dac` retains each admitted pywebview call's
  position until its exact worker exits, including serialization and native
  delivery. Shutdown joins outside the bridge lock; a timeout keeps ownership
  for retry. Direct Python calls still release on return.
- A per-window compatibility registry drops only pinned pywebview's unused
  synchronous None callback cells; real asynchronous callbacks retain their
  lookup/deletion behavior. This does not add an application-data channel.
- Installed transport verification exposed stale v4 fixture values. The
  current producer/page/parent now carry exact v5 byte strings, recording
  fields, item events, and compact terminal summaries. The original hostile
  data, fault stages, sequence prefix, replay cursors, retry/cleanup counts,
  and DOM checks remain intact. Frozen transport authority was not changed.
- Independent reviews cleared the dispatcher fix, native lifetime mechanism,
  shared host fixture, and v5 transport migration. The first installed run's
  five failures were traced to the stale fixture and reproduced separately
  before correction; all eight installed witnesses then passed.
- Dispatcher close now waits for its exact worker thread to exit before any
  session cleanup, under one bounded deadline and outside dispatcher locks.
  Current-generation fencing survives retirement handoff through actual thread
  death, including a running exception hook; timeout and self-close keep all
  ownership intact for retry. The scheduler also drops its temporary selected
  record and the degraded-audit sentinel discards factory exception graphs.
- Canonical operation detail now validates exact tuple/key/value variants at
  construction, snapshots every admitted source into a fresh exact base value,
  rejects duplicates before omission, and revalidates direct wire projection.
  Invalid key/path size refuses before encoding. Raw mapping diagnostics retain
  the existing whole-value omission count; projection subclasses and caller
  aliases cannot rewrite or hide state in a retained result.
- `2818686` ratifies a standalone-integrity candidate wall independent of an
  inventory tree: 120,000 unique rows plus a 192-MiB complete candidate graph,
  row-first/no-partial collection, honest post-refresh `FAILED+RAN` truth, and
  predecessor-overlay preservation. Enforcement is not complete yet.
- Linked verify continuation now normalizes executor phase/failure diagnostics,
  bounds their combined phase string, and advances the execution-set omission
  authority exactly once per dropped input. It snapshots a fresh exact
  `PhaseResult`, revalidates v6 encoding and direct workflow/cancellation entry,
  and drops the raw normalized executor result before invoking the continuation
  sink. Subclasses, forged counters, caller aliases, reflective mutation, and
  alternating field access cannot bypass the retained phase boundary.

## Verification

- Checkpoint 3.3 ordinary required-Node suite: **4,524 passed, 4 privilege
  skips, 28 headed deselected**. All 11 import rules held. The protected
  settlement oracle passed **30 scenarios × 3**, identical traces and baseline
  parity. Full details remain in `092b628:docs/HANDOFF.md`.
- Dispatcher prerequisite: both new retention regressions failed before the
  fix; core/dispatcher/workflows then passed **1,905 tests, 1 privilege skip**.
- Exact worker-retirement prerequisite: **6 expected failures, 3 passes**
  before the fix; the focused matrix now passes **10 tests** and the complete
  dispatcher file passes **81 tests**. Independent adversarial review found no
  remaining worker, close, shutdown, lock-order, or sentinel-lifetime defect.
- Observation prerequisite: **3 expected failures, 2 passes** before the fix;
  **55 service tests** and the required-Node interfaces department's **1,299
  tests** pass afterward. Independent review found no remaining issue.
- Full-result normalization: **9 expected failures, 2 passes** before the fix;
  the focused matrix now passes **15 tests**, and expanded core/scalar/v5/history
  coverage passes **1,146 tests**. Independent mutation review's identity,
  input-immutability, overflow, and wording findings are resolved.
- Canonical detail admission: **28 expected failures, 1 pass** initially;
  independent review then exposed **3 additional alias/serialization failures**.
  The final focused matrix passes **33 tests**, expanded core event/scalar
  coverage passes **1,058 tests**, and the settlement oracle remains clean at
  **30 scenarios × 3** with baseline parity.
- Verify-continuation diagnostics: **6 expected failures, 4 passes** initially;
  the omission-authority mismatch added one more red witness. Three independent
  review rounds then exposed **4 canonical snapshot/encoder failures**, **3
  direct workflow/cancellation failures**, and **1 alternating-access failure**.
  The final focused files pass **208 tests**; the workflows department passes
  **657 tests with 3,994 deselected**. The protected settlement oracle passes
  **30 scenarios × 3** with identical traces and baseline parity.
- Native prerequisite: six new lifetime/callback witnesses failed before the
  fix. After correction, focused bridge/host tests passed **121 tests**; shared
  host-fixture repair passed **161 tests**.
- Transport migration: two failing-first fixture cases, then **148 focused
  tests passed, 6 headed deselected**. Installed-wheel transport/native-host
  run: **8 passed, 32 deselected** (55.17 s).
- Final ordinary required-Node suite after all current prerequisite corrections:
  **4,619 passed, 4 privilege skips, 28 headed deselected** (195.91 s),
  including exact worker retirement, canonical detail admission, and the
  verify-continuation boundary.
  No required Node gate skipped. Whitespace validation passed.

## Next work and preserved boundaries

Follow checkpoint 4's three ordered stops in
[M1_SHELL_H2.md](M1_SHELL_H2.md#4-install-task-centric-lifecycle-and-compact-artifacts):
model/validator first, dormant machinery second, coherent 12-row activation
third. No size constant may be selected or retuned from measurement.

Canonical typed-detail admission and dispatcher worker retirement now provide
their required ownership witnesses; do not weaken the fresh detail snapshot,
validated wire projection, registered-thread fence, or bounded join.

The model must separately account for full serialization occurrences (including
shared dependency expansion), old/new generations, full result/audit owners,
instance dictionaries, mapping-proxy stores, container high-water capacities,
Path caches, and native/browser copies. The frozen transport sizer is not a
complete task-graph validator. Standalone integrity's row reload also needs its
newly ratified independent bound enforced; an inventory-tree limit does not
constrain it today.

The next source-derived blockers are enforcement of the independently bounded
standalone-integrity population, pre-projection and pre-parse continuation
ceilings, source-backed primitive/mount admission, and exact
`_inventory_details` retirement. None is supplied by the inventory-tree wall or
the bridge's 65,536-byte external command ceiling. The continuation diagnostic
value itself is closed; do not conflate that with the still-unbounded complete
codec occurrence graph. Keep the production command map at nine until all
model and dormant-machinery gates pass.

Protected settlement scenarios/baseline/hash/assertions, frozen transport
authority, and the epoch-5 witness remain unchanged. The witness SHA-256 is
`52f80f8539b863da0a357ba4a47c20a32cb77a5a14db9194d5adf98e31c538d9`.
The active pair remains ledger v4/history v6 at shared data epoch 6. No user
database was reset. BR-G-45 and SH-G-15 remain open.

## Separately deferred context

- The installed-wheel **event diagnostic** producer/page/parent migration is
  distinct from the repaired transport gate and remains unassigned under
  BR-G-42. Earlier v4 timings are not current-v5 acceptance.
- `_settle_execute_resume_failure` pre-entry/resume sink behavior remains an
  inspection-only concern, not a reproduced or repaired defect in this session.
- Checkpoint 3R closure and capture provenance remain at
  `e4a1ae0:docs/HANDOFF.md` and its historical references. Sorting and rebaseline
  additions remain assigned to H2 checkpoints 7/9 and 10.
