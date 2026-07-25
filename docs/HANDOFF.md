# NamiSync Session Handoff

Date: 2026-07-25

## Session Outcome

M1 Stage 4 is implemented on `milestone1`, following the Stage 5 Track A
facade commits `4db4a4741197c96ce686d0ef40c7f1a6f785cc35` and
`89c6351778864389e3abc2b2b67539f8e2331b33`. Execution now has an opt-in
in-session readback path:

```python
NamiSyncService.start_execution(
    request_id,
    *,
    verify_after_execute=False,
) -> ExecutionSession
```

The default remains the M0 execute-only workflow. Setting
`verify_after_execute=True` keeps one session, volume-custody interval, logical
ledger run, ordered result stream, history envelope, and terminal settlement
across execute and verify.

There is no database schema/version/marker change in this stage. Ledger v2 and
history v3 remain frozen, compound phases use the already-reserved
`history_phases` table, and standalone producers continue to write zero phase
rows. Workflow payloads advance globally to strict v3; v1/v2 are rejected
rather than guessed. The process-local in-memory session store still offers no
application-restart resume.

## Stage 4 Contracts

- Every successfully settled COPY, UPDATE, and MOVE_UPDATE, and only those
  operations, stores exactly one `PublishedCopyEvidence` before its reliable
  operation outcome is emitted. Missing evidence is a named
  verification-incomplete invariant failure.
- `RecordedCopyIdentity` is the complete real target-row identity returned
  atomically by the copy transaction. Recording failure leaves identity absent
  and degrades recording without suppressing byte verification or inventing an
  id.
- The workflow converts evidence into ledger-neutral `PostCopyCandidate`
  values. The verifier reuses the private classifier; ledger identity only
  gates conditional advancement. Target stat drift is `modified`, stable-stat
  byte corruption is `mismatch`, and a stale conditional write leaves
  integrity verified while degrading recording.
- Execute and verify continuations are explicitly discriminated. They freeze
  candidates, completion ids, cumulative bytes, evidence, timestamps, and
  phase truth. Pause may close and idempotently reopen the same run token;
  completed items are not re-emitted.
- Successful published candidates still verify after a later execution
  failure. Execute cancellation starts no verification. Verify cancellation
  preserves settled filesystem truth and reports a canceled/incomplete verify
  phase.
- `PhaseResult` is compound-only and records one independent summary per
  entered phase. Transfer and readback bytes are never summed.
- `OperationResult.status` remains filesystem truth; `canceled` is independent.
  `result_terminal_state()` is the sole dispatcher lifecycle projection, so a
  verify-canceled result can retain filesystem `COMPLETED` or `FAILED` while
  the session lifecycle settles `CANCELED`.
- The execution registration alone opts into the generic, domain-blind
  `settle_canceled` callback. Started paused or resumed-pending cancellation
  finishes the same logical run without scanning, preflighting, hashing, or
  opening a competing writer. Pending unrun cancellation creates no run.
- Resumed execute preflight refusal after mutation finishes the existing run as
  `FAILED+RAN` with a failed execute phase and preserved partial counters,
  never as a fresh terminal `REFUSED`.
- Resumed verify preflight refusal preserves the settled execution filesystem
  status, adds a zero-work incomplete verify phase, and finishes that same run.
- One finish-once boundary covers normal completion, mismatch/modified,
  cancellation, resumed refusal, and unexpected `Exception`. Finish failure
  degrades recording only. `KeyboardInterrupt`, `SystemExit`, and other
  `BaseException` subclasses are not normalized into workflow results.

## Views And Retained History

Live and retained results share the same classification path.
`HistoryRunView` now exposes primitive `canceled`, `integrity_status`, and
`headline` fields alongside filesystem, recording, audit, disposition, mixed
items, and ordered phases. `runtime._history_view()` unwraps
`HistoryPhaseSnapshot.phase`, reconstructs the typed result from persisted
axes/items/phases, and routes it through `operation_result_view`; it does not
infer terminal truth from phase shapes.

Retained regressions cover verify-canceled results, mismatch, partial plus
degraded precedence, a real mixed execute/verify run reopened from history,
and standalone zero-phase history.

## Adversarial Review

Separate builder and reviewer passes found and fixed:

- post-recorder exceptions that could leave a run unfinished;
- resumed execute preflight refusal mislabeled as fresh `REFUSED+UNRUN`;
- identityless evidence accepted while execution recording claimed `OK`;
- contradictory canceled/filesystem/phase/disposition combinations;
- a PAUSING snapshot-drain cancellation race and malformed callback failure
  being masked as clean cancellation; and
- retained compound history passing a wrapper to the phase view and dropping
  cancellation/integrity/headline truth.

Six deliberate release mutations were tried. Removing evidence publication,
conditional verification recording, exact native hasher-object injection,
history phase persistence, compound canceled settlement, or ledger-run
finishing caused the corresponding targeted test to fail. Every mutation was
restored, the restored targets passed together, and no mutation survived.

## Verification

- Full suite: `628 passed in 17.23s`; no skips reported.
- Import Linter: 48 files, 173 dependencies, 8 contracts kept, 0 broken.
- `python -m compileall -q namisync`: clean.
- `git diff --check`: no whitespace errors; only the repository's expected
  LF-to-CRLF notices.
- Literal XV-1 through XV-8 and XV-17 test names and scenario companions are
  mapped in `docs/M1_PLAN.md`.
- Static checks confirm the sole production concrete `xxhash` import remains
  `namisync/workflows/runtime.py`; the exact factory object reaches executor
  and verifier; executor and verifier retain `O_SEQUENTIAL` versus
  `WINDOWS_UNBUFFERED`; workflows contain no SQL; and no `worker_count`,
  live-settings, Stage 6, or restart-resume implementation leaked into Stage 4.

## Immediate Next Context

1. Stage 5 Track B owns the final four-axis result-category/CLI exit
   classification, the `inventory`/`baseline`/`verify`/`rebaseline` commands,
   runtime/service semantic-settings seam, plan-default snapshot consumption,
   and standalone baseline/rebaseline selection filtering. Do not reassign
   those concerns to Stage 4.
2. The temporary Track A CLI compatibility adapter intentionally remains
   status-first until Track B replaces it with the final precedence matrix.
   Stage 4 did not edit `interfaces/cli.py`, `tests/test_cli.py`, or
   `dispatcher/event_bus.py`.
3. Preserve the distinction between frozen execution truth
   (`ExecutionSet.recording`) and compound-current recording state carried by
   verify continuation/result. Compound recording may degrade later but cannot
   improve a degraded execution.
4. `PublishedCopyEvidence` is executor continuation state, not a durable-resume
   protocol. `PostCopyCandidate` is verifier input, not an inventory selection
   and not an embedded evidence object.
5. Keep the single outer `LedgerRecorder`/`SyncRunRecorder` window unfinished
   through compound settlement. Conditional integrity recording reuses that
   recorder; do not open a competing ledger writer.
6. Pre-switch development databases still require the coordinated Stage 2
   ledger/history reset. Do not add a migration, marker backfill, schema bump,
   or second reset for Stage 4.
