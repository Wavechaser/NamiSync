# NamiSync Session Handoff

Date: 2026-08-02
Branch: `milestone1`

## Session Outcome

Closed the M1 audit-timeout live/retained parity defect without changing the
history schema, payload version, or write topology.

- Added one atomic first-claim decision latch to each audit finalization
  command. A caller that reaches the five-second cutoff first decides degraded;
  the late pump conforms the result before history builds its payload hash. A
  pump that claims first owns finalization and the caller waits for its actual
  success or failure.
- Made `HistoryObserver.finalize` persist the decided `result.audit` value
  instead of hard-coding OK.
- Preserved the prior failure contract found during adversarial review: if an
  earlier observer event has already failed, a queued finalization does not
  create a row. A caller-owned timeout is the only degraded state that permits
  the late, parity-preserving final write.
- Kept the cutoff at five seconds. The default history writer can retry for ten
  seconds, so pump-owned finalization can intentionally outlive that cutoff.
- Added deterministic caller-win, pump-win, late-success, late-failure,
  prior-event-failure, dispatcher parity, and retained degraded-axis
  regressions. Strengthened XV-8 so a degraded live audit axis must reopen as
  degraded rather than passing through an all-OK fixture.
- Marked the audit timeout entry fixed in `BUGS.md` and updated history,
  architecture, interface, and README descriptions of the contract.

## Verification

- Focused dispatcher/history regression suite: `55 passed in 3.63s`.
- XV-1 through XV-8 gate: `235 passed in 16.26s`.
- Full repository: `844 passed in 67.51s`.
- Import boundaries: 49 files / 181 dependencies; all eight contracts kept,
  zero broken.
- Package health: `pip check` reported no broken requirements.
- `git diff --check` was clean apart from expected LF-to-CRLF notices.

## Immediate Next Context

The only open substantive bug in `BUGS.md` is executor pause after a durable
retry sub-step. It still needs a product decision among persisted continuation,
rollback before pause, or deferring pause to an operation-safe boundary.

For audit finalization, preserve these invariants:

1. The latch is claimed before `HistoryObserver.finalize` builds the payload
   hash.
2. Caller ownership means both the immutable Terminal and any late retained row
   use `audit=degraded`.
3. Pump ownership means the caller waits for the real commit outcome; a failed
   commit yields a degraded Terminal and no contradictory row.
4. Pre-finalization observer failure remains degraded with no row, and no
   corrective Terminal or secondary history write is introduced.
