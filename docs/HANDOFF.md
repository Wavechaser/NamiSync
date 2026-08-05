# NamiSync Session Handoff

Date: 2026-08-05
Branch: `milestone1`

## Session Outcome

Adversarial review of the bounded durable history delivery (`93e7b94`) plus the
older dispatcher code it exercises. The history windowing, admission,
finalization, and bounded-readback contracts held under review; two defects
outside history itself were corrected.

- FIXED: `EventHub.subscribe()` handed a new stream `subscriber_capacity + 1`
  envelopes whenever the retained replay was longer than one subscriber's
  bound. The truncation branch reserved a slot for the leading `Gap` only when
  a gap was already required before truncating, never when truncation itself
  created it. Production sizing (128-event replay, 64-event subscriber bound)
  reaches this on any session that has emitted more events than the subscriber
  bound, and the over-full stream was then ejected by the next reliable event
  before its consumer could drain. The allowance is now recomputed once
  truncation forces the gap, and a regression pins the initial buffer at the
  bound.
- CLEANUP: `HistoryObserver._event_chain_hash` was write-only state; the
  authoritative chain is always re-read inside the owning transaction. Removed
  it along with the `_ExistingRun` field and the reader column that fed only
  it, so no reader can mistake the in-memory copy for durable truth.

Verified by inspection and by direct probes, not only by the suite: query plans
for the summary/item/event reads use the intended indexes; a real end-to-end
CLI sync records and renders finalized history; and hand-built incomplete sync
and verify runs render correctly through `history` list and detail.

`docs/BUGS.md` and `docs/DISPATCHER.md` carry the matching updates.

## Verification

- Complete pytest suite: `980 passed in 29.54s` (979 prior plus one regression).
- Focused dispatcher set: `72 passed in 3.54s`.
- Import linter: `8 kept, 0 broken`.
- Package and test compile gate: clean.
- Dispatcher/history/service set run six times consecutively with no flake.
- See the interpreter-crash item below: the suite is green, but roughly one
  full-suite run in six aborts before finishing. Treat a single green run as
  weaker evidence than it looks.

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

### Open questions raised by this review (no code change made)

- SEVERE, PRE-EXISTING, UNDIAGNOSED: the full pytest run intermittently aborts
  with `Windows fatal exception: access violation`, roughly one run in six.
  Reproduced on unmodified `93e7b94` as well, so it is not introduced by this
  session. Under `PYTHONMALLOC=debug` the faulting stack is
  `Garbage-collecting` reached from an ordinary allocation, which points at a
  refcount or use-after-free bug in native code rather than at the test that
  happens to be running. Other runs surface it as an impossible Python-level
  error (a `TypeError` on `len(str)` in
  `namisync/core/pathing.py::_uppercase_one_codepoint`) with a `<invalid frame>`
  in the traceback — the same corruption presenting differently. It has landed
  in at least `tests/test_recorder_inventory_integrity.py` and
  `tests/test_bridge_scan_scope.py`, both of which allocate tens of thousands of
  paths and so trigger GC often; they are the victims, not the cause. pywebview
  and pythonnet are ruled out (`clr` is never imported by the suite). The
  remaining native surface is `xxhash`, `_sqlite3`, and the `ctypes` Windows
  bindings in `scanner`, `executor`, `verifier`, `preflight`, and `custody`.
  Running `tests/test_scanner.py` and `tests/test_bridge_scan_scope.py` alone
  six times did not reproduce it, so it needs a longer prefix of the suite.
  This deserves its own session: it currently makes every green suite run a
  probabilistic claim. Separately and once only,
  `tests/test_executor_pipeline.py::test_b2_hash_fifo_independently_plateaus_at_32_items`
  failed inside a full run and then passed in isolation and in six consecutive
  full runs; its traceback was not captured, so whether that is the same
  corruption or an unrelated load-sensitive assertion is unknown.
- A late subscriber whose replay was truncated still starts at exactly its
  bound, so the next reliable event ejects it unless the consumer drains first.
  That is now the documented bound rather than a violation of it, but whether
  `subscribe()` should hand out headroom instead of a full buffer is a policy
  decision, not a defect.
- `get_event_page()` rejects `after_seq` greater than the durable watermark with
  `ValueError`. `docs/HISTORY.md` § Subscriber Repair describes a repairing
  subscriber that "keeps its last applied sequence", and a live sequence can
  legitimately exceed the last committed window. Either the repair contract
  should say the cursor is clamped to the captured watermark, or the page should
  return an empty result for a cursor past durability. `tests/test_service.py`
  currently exercises repair from sequence zero, so nothing in the tree hits it.
- `get_event_page()` also raises `HistoryIntegrityError` when a caller supplies
  a `through_seq` that falls inside a reliable-sequence gap. That is correct as
  tamper detection for a watermark the repository itself captured, but it makes
  arbitrary caller-chosen watermarks an integrity failure rather than an
  argument error. Worth deciding before the WebView history frontend chooses
  its paging cursors.
- `Dispatcher.close()` leaves a session in `_closing` when hub cleanup times
  out, so `subscribe()` reports `SessionNotFound` for that settled session until
  a `close()` retry succeeds. This matches "retain timed-out cleanup for retry",
  but nothing forces the retry.
