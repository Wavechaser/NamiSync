# Session Handoff

Status (2026-08-28): the checkpoint-4 prerequisite stabilization is complete
in the commit containing this handoff. Checkpoint 4 itself has not started. No
reservation constant, formula, model fixture, validator, lifecycle surface, or
BR-G-45 acceptance from the rejected draft is production authority.

The work stopped at the requested boundary: every already-open P1 gap that
could produce false success, false refusal, replay, lost reliable truth,
mutation misreporting, or partial persistence is closed and regression-backed.
Consolidation, abstraction, optimization, and new checkpoint-4 design work are
deferred.

## Safe repository state

- The active branch is `milestone1`. The commit immediately before this
  stabilization was `c2b1150` (`fix(web): bound bridge response custody`).
- The checkpoint-4 draft is quarantined under the stash named
  `checkpoint 4 model draft before prerequisite consolidation` (currently
  `stash@{0}`). It contains only:
  `namisync/interfaces/web/task_retention_model.py`,
  `tests/_departments.py`,
  `tests/interfaces/web/fixtures/task_retention_model_v1.json`,
  `tests/interfaces/web/test_task_retention_model.py`,
  `tools/task_retention_model_oracle.py`, and
  `tools/task_retention_model_v1.json`.
- Do not pop that stash wholesale. After the consolidation pass, inspect it by
  name and rederive any useful model work from current source and frozen
  requirements. Its numbers and hashes are not accepted evidence.
- Older recovery stashes remain under their descriptive names: `safety:
  pre-simplicity exception audit 2026-08-27`, `recovery: paused exception
  retirement for source-wall simplicity audit 2026-08-27`, and `recovery:
  interrupted checkpoint-4 audit 2026-08-27`.
- The complete interrupted tree also remains at object
  `33f699448b5940b2aa4b0464b3a238297c68ab86` on branch
  `codex/recovery-power-loss-20260827`. Preserve the recovery evidence until a
  later, explicitly reviewed cleanup.

## Stabilized prerequisite behavior

- Planning and inventory now admit each independent source population at its
  first excess, before normalization, omission, sorting, indexing, or retained
  artifact construction. Initial plan/inventory excess is typed
  `REFUSED+UNRUN` with no partial save; standalone-integrity excess remains
  honest `FAILED+RAN` with no partial selection or verifier start.
- Declared scans, correspondence, policy inputs and results, observed world,
  verdicts, inventory resolver output, mounted-set evidence, and retained
  selections/results are captured as exact typed snapshots and revalidated at
  their distinct hostile seams. Reliable private truth never shares the public
  callback graph.
- Only unavoidable simultaneously retained reference slots are charged by the
  prerequisite ledger. Disposable previews, selections, callback inputs, and
  construction graphs are not treated as retained owners.
- Session item, progress, continuation, settlement, audit, publication, and
  returned-result custody are distinct. Accepted reliable truth is retained
  before later hostile work, and malformed collaborator aggregates cannot
  replace it.
- Execution continuation is exact v7. Its required plan-ordered exclusion
  cursor advances locally after reliable acceptance and before hostile cursor
  capture, so pause/resume and cancellation cannot replay an accepted
  exclusion. The v6 compatibility branch is removed and v6 payloads are
  rejected.
- Fresh preflight-refusal control failures stay phase-free
  `REFUSED+UNRUN`, retain only the accepted exclusion prefix, and open neither
  recording nor executor work.
- Recording finish, fallback finish, and context exit receive exact execution
  and candidate authorities. Hostile mutation returns failed execution or
  incomplete verification from saved pre-finish items, counters, phases, and
  mutation provenance, including paused-cancellation and fallback paths. Later
  reconciliation cannot turn that finding into success or replace it with a
  generic mismatch.
- Ordinary scanner, planner, preflight, CLI/service, dispatcher, and verifier
  behavior remains unchanged outside these exact safety boundaries. No new
  public compatibility contract was added.

## Bounded correctness review

The independent final reviewer challenged false refusal, replay, mutation
misreporting, lost truth, and unnecessary ownership. It found three P1 gaps:

1. recording finish/context-exit mutation could rebuild counters or provenance
   from corrupted aliases, including cancellation and fallback paths;
2. cancellation from hostile continuation custody could replay an already
   accepted exclusion; and
3. pause/cancel during fresh-refusal exclusion delivery could escape the typed
   `REFUSED+UNRUN` boundary.

All three were fixed. The reviewer's bounded closure matrix passed all eleven
regressions and found no remaining blocker within the frozen prerequisite
scope. Earlier review concerns about repeated full-graph scans, disposable fact
construction, duplicate maps, and aggregate confirmation are recorded below;
they did not justify another redesign during stabilization.

## Verification

- Expanded changed-file suite: `1,103 passed`.
- Affected `core`, `scanner`, `planner`, `preflight`, `executor`, `verifier`,
  `database`, `workflows`, `dispatcher`, and `interfaces` department union:
  `4,765 passed, 1 skipped, 336 deselected`.
- Ordinary repository suite with the bundled Node runtime:
  `5,070 passed, 4 skipped, 28 deselected`.
- Independent final closure matrix: `11 passed, 153 deselected`.
- The final static closeout included `git diff --check`, a current-versus-
  historical execution-version terminology review, and a worktree/stash
  inventory proving checkpoint-4
  model artifacts are absent from the stabilization commit.

## Deferred consolidation and checkpoint-4 owners

The active ledger is `docs/BUGS.md`; `docs/M1_SHELL_H2.md` owns the delivery
boundary. The next consolidation/model pass must review or price these owners
without widening the stabilized workflow contracts:

- repeated full-graph revalidation at callback/checkpoint seams and its
  disposable fact graphs;
- duplicate operation/candidate maps and settlement snapshots;
- the unused `ExecutionOperationFact.content_bytes` field;
- verifier aggregate-versus-reliable-stream confirmation and standardized
  four-string record identities;
- unslotted or custom nested Python values, result projection containers,
  EventHub envelope/body subscriber aliases, and SessionStore live-record
  aliases;
- process-restart durability for the item accumulator and exclusion receipt;
- remaining host/document exception owners, history construction/read-open
  failures, path-message construction, and complete path/codec copies;
- complete tree projection, codec/text estimates, construction transients,
  sorting/index storage, callback overlap, native/browser copies, mutable
  container capacity, and every speculative future owner.

These are logged design/model inputs, not accepted constants or permission to
add compatibility branches. Only a newly proved correctness consequence in the
user's bounded classes should reopen prerequisite behavior.

## Next safe action

Perform the requested consolidation/abstraction pass against this committed
baseline. Reconcile the deferred ledger and inspect the quarantined draft
without applying it. Only after that review should checkpoint 4 derive and
freeze a fresh ownership model from active source, `docs/M1_BRIDGE.md`,
`docs/DEFENSE.md`, and the current plan.
