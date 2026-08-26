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
- The observation-stream prerequisite removes closed-stream history. Stop and
  replacement adoption share one lock; cleanup snapshots the current stream,
  while closes and joins run outside that lock. Independent review cleared
  the weak-reference churn and both stop/adopt race directions.
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

## Verification

- Checkpoint 3.3 ordinary required-Node suite: **4,524 passed, 4 privilege
  skips, 28 headed deselected**. All 11 import rules held. The protected
  settlement oracle passed **30 scenarios × 3**, identical traces and baseline
  parity. Full details remain in `092b628:docs/HANDOFF.md`.
- Dispatcher prerequisite: both new retention regressions failed before the
  fix; core/dispatcher/workflows then passed **1,905 tests, 1 privilege skip**.
- Observation prerequisite: **3 expected failures, 2 passes** before the fix;
  **55 service tests** and the required-Node interfaces department's **1,299
  tests** pass afterward. Independent review found no remaining issue.
- Native prerequisite: six new lifetime/callback witnesses failed before the
  fix. After correction, focused bridge/host tests passed **121 tests**; shared
  host-fixture repair passed **161 tests**.
- Transport migration: two failing-first fixture cases, then **148 focused
  tests passed, 6 headed deselected**. Installed-wheel transport/native-host
  run: **8 passed, 32 deselected** (55.17 s).
- Final ordinary required-Node suite after all fixture corrections:
  **4,541 passed, 4 privilege skips, 28 headed deselected** (191.24 s).
  No required Node gate skipped. Whitespace validation passed.

## Next work and preserved boundaries

Follow checkpoint 4's three ordered stops in
[M1_SHELL_H2.md](M1_SHELL_H2.md#4-install-task-centric-lifecycle-and-compact-artifacts):
model/validator first, dormant machinery second, coherent 12-row activation
third. No size constant may be selected or retuned from measurement.

The remaining source-derived prerequisites include full-result header
normalization under the existing omission rules,
canonical typed-detail admission, and a sound worker-retirement witness.
Dispatcher close currently does not prove its exact worker has exited; do not
use successful close as that proof until the ownership fix lands.

The model must separately account for full serialization occurrences (including
shared dependency expansion), old/new generations, full result/audit owners,
instance dictionaries, mapping-proxy stores, container high-water capacities,
Path caches, and native/browser copies. The frozen transport sizer is not a
complete task-graph validator. Standalone integrity's row reload also needs its
own admission bound; an inventory-tree limit does not constrain it today.

The native prerequisite is committed; the observation prerequisite is delivered
at this safe stop. Remaining dirty core/session/event/scalar files and their
tests/docs belong to full-result diagnostic normalization; dirty dispatcher
files and their tests/docs belong to exact worker retirement. Neither is yet a
committed model or activation. No unrelated dirty work was present. Next:
finish independent review and verification of those fixes, then canonical
typed-detail admission, before freezing the model.

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
