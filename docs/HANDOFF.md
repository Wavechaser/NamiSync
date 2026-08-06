# NamiSync Session Handoff

Date: 2026-08-06
Branch: `milestone1`

## Session Outcome

Closed the four follow-up questions from the bounded-history and dispatcher
review.

- Reliable-event pages now treat caller-supplied `through_seq` as a sparse
  inclusive bound. Every request verifies the run's official durable maximum
  through the indexed event tail, reads `limit + 1` raw rows, and decodes at
  most the requested limit.
- A fresh event traversal whose live cursor is ahead of durability returns the
  agreed empty terminal page: durable `through_seq`, unchanged
  `next_after_seq`, and `has_more=False`. That traversal ends; a later repair
  omits `through_seq` and captures a new committed prefix. An explicit reversed
  fixed interval remains invalid.
- Terminal cleanup now distinguishes a reversible timeout before the hub gate
  from irreversible stream detachment. Subscribers wait while an accepting
  explicit close is tentative, attach after a reversible timeout, and receive
  typed `SessionCleanupPending` after detachment or a store-drop failure.
  Shutdown claims remain immediate, all session ownership survives retryable
  failures, and there is no background reaper.
- CLI terminal cleanup no longer swallows errors, and all command paths inspect
  final service shutdown. Warnings state that the terminal result and history
  outcome are already settled; cleanup does not rewrite the command result or
  exit classification.
- The executor plateau regression now freezes the accepted three-sample
  evidence before signaling, waits for two later coordinator checkpoints so one
  complete blocked retry has elapsed, and compares the live reader count with
  that immutable evidence. It tolerates waiter delay but detects a hidden read
  during the first later retry.
- Replay headroom remains unchanged by decision, not omission. No finite slot
  reserve guarantees burst survival when a producer can outrun an ordinary
  sink for an arbitrary reliable run. With the current 128/64 replay/subscriber
  capacities, another ejection is visible and replay-recoverable churn rather
  than silent loss. A future continuity guarantee needs a readiness handshake
  or subscription before workflow start; `docs/DISPATCHER.md` owns the policy.

The event-bus truncation fix in `3cba6fb` remains clean. The initial plateau
changes in `4ca9e13` and `870dc94` removed the observed false failure but did
not freeze post-signal evidence; the regression above completes that gate.

## Verification

- Focused schema/history/event-bus/dispatcher/service/CLI/executor suite:
  `293 passed`.
- Complete pytest suite: `995 passed in 55.73s`.
- Import linter: `8 kept, 0 broken`.
- Package and test compile gate: clean.
- Plateau probes: 0/50/200/500 ms waiter delays, 200 repetitions, and an
  injected post-signal hidden read all behaved as required.
- Independent adversarial reviews found and then closed the plateau
  single-retry observation gap and the close/subscribe tentative-stage and
  blocking-store-drop races. Final page and close reviews found no remaining
  actionable defects.
- The documented 50-run/1,000,000-item history benchmark passed every gate:
  0.409-second fresh summary; 7.486/6.163 ms item/event p95 pages;
  14.382 ms p95 and 204.203 ms maximum window commits; retained peak remained
  256 events and 79,360 bytes.

## Immediate Next Context

- History v1-v3 and mismatched contract markers still require the documented
  coordinated manual ledger/history reset; startup never migrates or deletes
  automatically.
- A crash can lose only the final uncommitted history window. Committed
  nonterminal history remains queryable as `incomplete`; durable process/session
  custody and automatic interruption classification remain M2 work.
- The backend recovery contract and service APIs are ready for the future
  WebView consumer. No frontend was added here.
- Session-wide `OperationResult.items` and dispatcher item accumulation remain
  intentionally out of scope; history writer and readback memory are bounded.
- Do not change the 256-event/1-MiB/one-second history policy or invent replay
  headroom from a convenient constant. Re-run the documented scale fixture or
  collect UI/load evidence before changing either decision.
