# NamiSync Session Handoff

Date: 2026-08-03
Branch: `milestone1`

## Session Outcome

Closed the durable-retry pause defect and its cancellation siblings without
changing persisted continuation, payload, or database contracts.

- **Pause now drains an owned durable retry operation.** COPY, UPDATE, and
  MOVE_UPDATE install process-local continuations once staged or published
  filesystem state must survive a retry. A pause observed at the two retry
  backoff checkpoints is latched until that operation settles, then unwinds at
  the ordinary boundary. Resume therefore never collides with the executor's
  own backup, trash entry, or published target.
- **The latency statement is bounded where the product owns it.** Production
  retry sleeps total at most 350 ms (50 + 100 + 200 ms). Remaining time is
  uncapped filesystem and recorder latency over already-staged data; guarded
  attempts do not copy the main payload again. A pause rides all remaining
  retries so requesting pause cannot make a transient failure permanent.
- **Cancel and policy Stop have explicit precedence.** Cancellation always
  preempts a latched pause and settles immediately from the continuation's
  durable state. A failure-policy `Stop` suppresses the latch, settles later
  operations `policy-stop`, and terminates rather than losing the policy
  decision across a resume.
- **Cancellation reports published truth rather than blanket `CANCELED`.** A
  prepared-but-unpublished operation remains canceled. Published-but-unfinished
  COPY/UPDATE/MOVE_UPDATE settles `FAILED/canceled-after-publish`, records the
  observed durable shape, degrades recording, and carries no success-only
  `PublishedCopyEvidence`. MOVE_UPDATE distinguishes new+old from new+trash.
- **UPDATE backups remain recoverable and visible.** Cancellation deletes only
  the owned staged temp and reports the retained backup path/method/state in the
  item detail. It never deletes the old version. Purging retained trash remains
  part of the deferred maintenance-session retention work.
- **The bridge contract exposes the drain.** The existing `PAUSING` lifecycle
  value must render as **Pausing…** until unwind and custody release; it is
  distinct from `PAUSED`, remains cancelable, and can transition directly to a
  terminal state when policy Stop wins.
- Updated `BUGS.md`, executor/core/dispatcher/architecture contracts, Stage 6
  bridge and desktop UI requirements, features, plan wording, and README.

## Verification

- Focused executor suite: `152 passed`.
- Executor/dispatcher/resume/payload integration selection: `298 passed`.
- Full repository: `881 passed in 30.65s`.
- Import boundaries: all eight contracts kept, zero broken (50 files and 183
  dependencies analyzed).
- Package health: `pip check` reported no broken requirements.
- New regressions cover pause with and without a continuation, post-publish
  COPY, UPDATE backup/replace, MOVE_UPDATE old-to-trash, the 350 ms production
  retry budget, cancellation before and after publish, new+old/new+trash state,
  cancellation over a latched pause, and policy Stop over a latched pause.

## Immediate Next Context

`BUGS.md` has no remaining open executor durable-retry entry. Stage 6 remains
the next product delivery: implement the pywebview/WebView2 desktop shell in the
slice order and against the host/security gates in `M1_BRIDGE.md` and
`DESKTOP_UI.md`.

The executor behavior delivered here relies on process-local continuations and
is deliberately an M1 safe-boundary solution, not restart-resume persistence.
Preserve these invariants in later work:

1. `PAUSING` may last through all remaining guarded attempts; do not replace
   this with a one-attempt cap or claim a hard elapsed-time bound.
2. Once a continuation exists, retries operate on already-staged data and must
   not call `_prepare_copy` again.
3. Cancellation is immediate. It never waits out retries and never deletes an
   UPDATE backup that may be the only recoverable old version.
4. A published but unfinished canceled operation is failed with explicit state
   and degraded recording, never succeeded without XV-1 evidence and never
   mislabeled canceled.
5. Policy Stop suppresses a pending pause so later selected operations retain
   their `policy-stop` settlement.
6. Persisted operation-local continuation remains an M2 concern if restart
   resume is introduced; do not put it into the M1 `ExecutionSet` payload.
