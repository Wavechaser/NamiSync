# NamiSync Session Handoff

Date: 2026-08-05
Branch: `milestone1`

## Session Outcome

Delivered bounded, incrementally durable history recording and bounded
readback under reset-only history schema v4.

- Reliable preterminal events now commit in append-only windows at 256 events,
  1 MiB, one second, pause, clean close, or finalization. A failed window leaves
  the prior committed prefix and watermark intact; restarted nonterminal rows
  are reported as `incomplete`, not guessed to be interrupted or resumable.
- Admission remains constant-time without retaining all prior event hashes.
  Durable duplicate lookup, event-chain hashing, dense item order, rolling
  counts, context validation, terminal validation, and finalization replay are
  transactional and detect conflicting or tampered state.
- Summary listing uses a fixed query count and fixed-size workflow aggregates
  without decoding event JSON. Item and reliable-event detail use stable
  keyset pages with a hard 256-row maximum. Service views expose summary,
  item-page, and event-page methods; CLI detail rendering streams pages.
- The audit pump flushes on the first event's age deadline even under
  continuous traffic, makes `PAUSED` durability a barrier, drains a broken
  prefix without retaining queued payloads, and closes its observer exactly
  once. History failure still cannot rewrite filesystem or ledger truth.
- Shutdown and explicit close retain retryable ownership until cleanup
  succeeds. Cancellation reserves lifecycle and hub publication consistently,
  spends one shared deadline without cross-session head-of-line blocking,
  gates subscriptions, and clears subscriber plus replay state before audit
  cleanup.
- Final adversarial corrections bound terminal phase/error text in Python and
  SQLite, verify stored context and terminal payload hashes on read and replay,
  include every committed event timestamp in the durability watermark, keep
  queued `UNRUN` start time null, and prevent free-form summary classifications
  from expanding with item cardinality.

The matching database, history, dispatcher, interface, architecture, feature,
bug, bridge, command-line, README, and benchmark documentation is current.

## Verification

- Complete pytest suite: `979 passed in 53.91s`.
- Final focused history/schema/dispatcher set: `141 passed in 6.79s`.
- Integrated history/schema/service/workflow set: `151 passed in 8.50s`.
- Import linter: `8 kept, 0 broken`.
- Package and test compile gate: clean.
- Independent final adversarial review: no actionable findings remain.
- `git diff --check`: clean apart from Git's existing LF-to-CRLF notices.
- Opt-in 50-run/1,000,000-item benchmark passed every release threshold:
  0.984 s cold summary, 0.652 s warm summary, 17.746 ms item-page p95,
  13.995 ms event-page p95, 104.301 ms maximum window commit, and a measured
  peak of 256 pending events / 79,360 serialized bytes.

## Immediate Next Context

- History v1-v3 and mismatched contract markers require the documented
  coordinated manual ledger/history reset. No migration or automatic deletion
  exists.
- A crash can lose only the final uncommitted history window. Committed
  nonterminal history is queryable as `incomplete`; durable process/session
  custody and automatic interruption classification remain M2 work.
- This delivery provides the backend recovery contract and service APIs, not
  the future WebView history frontend.
- Session-wide `OperationResult.items` and dispatcher item accumulation remain
  intentionally out of scope; history writer and readback memory are bounded.
- The window policy has one tuning point in `docs/HISTORY.md`; do not change its
  defaults without rerunning the documented million-item benchmark.
