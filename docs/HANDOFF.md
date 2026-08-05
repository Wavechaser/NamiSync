# NamiSync Session Handoff

Date: 2026-08-05
Branch: `milestone1`

## Session Outcome

Adversarial review of the bounded durable history delivery (`93e7b94`) plus the
older dispatcher code it exercises. The history windowing, admission,
finalization, and bounded-readback contracts held under review. One older
dispatcher defect and one racy executor test were corrected, and one piece of
dead history state removed.

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
- FIXED: `test_b2_hash_fifo_independently_plateaus_at_32_items` was racy and
  failed roughly one full run in three under core pinning. Its checkpoint
  sampled `source.reads` whenever both FIFOs read as full, but the two queues
  are sampled separately while workers run, so both can read as full during
  fill-up with a worker between its get and its put. Captured locals showed
  `plateau_reads = [65, 67, 67]`: the first sample was taken two reads before
  the pipeline settled, and the test then demanded all three samples agree. The
  sampler now requires three consecutive samples at the same read count and
  restarts the run whenever the reader moves, which is what "plateaus" was
  meant to assert. No product behavior was involved: the item-cap assertions on
  both queues passed every time. Eight pinned full runs are clean.
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
- Roughly one full-suite run in six aborted on this machine with a hardware
  fault, not a test or product failure. See "Development machine instability"
  below before reading anything into an aborted run.

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

### Development machine instability — not a product defect

The development CPU produces intermittent hardware faults once it has been
powered on for a long stretch; the maintainer has identified this and it is not
a NamiSync bug. Do not spend a session hunting it in the code. Recorded here
only so the next session recognizes the signature instead of re-investigating:

- Roughly one full pytest run in six aborts with
  `Windows fatal exception: access violation`. It reproduces identically on
  unmodified `93e7b94`, so it tracks the machine rather than any commit.
- The signature moves between unrelated tests and presents in two ways: a
  faulthandler stack whose top frame is `Garbage-collecting` reached from an
  ordinary allocation, and an impossible Python-level error such as a
  `TypeError` on `len(str)` in
  `namisync/core/pathing.py::_uppercase_one_codepoint` accompanied by
  `<invalid frame>` in the traceback. Observed victims so far are
  `tests/test_recorder_inventory_integrity.py` and
  `tests/test_bridge_scan_scope.py`; both pass in isolation and on a re-run.
- Any test that allocates heavily surfaces it more often simply because it
  spends more time in the allocator and GC. That is exposure, not cause.
- Not everything intermittent is this. The pipeline plateau flake fixed in this
  session initially looked like the same signature and was not: it reproduced
  under core pinning with a normal `AssertionError` and a coherent traceback.
  A real Python-level assertion with an intact stack is a real defect; the
  machine fault shows up as an abort or an impossible error.
- Mitigation while the machine cannot be underclocked: pin the interpreter to
  one core so threads do not migrate between them. This exact form is verified
  to run the suite from PowerShell and to return its exit status:

  ```
  cmd /c "start /affinity 1 /wait /b .\.venv\Scripts\python.exe -m pytest -q"
  ```

  `/affinity` takes a hex CPU mask, so `1` is core 0 and `2` is core 1; `/wait`
  and `/b` keep it synchronous and in the same console. Measured at 28.7 s
  against roughly 28 s unpinned, so the whole suite costs nothing meaningful to
  run this way. Pinning reduces the fault rate; it does not eliminate it.
- Practical rule: an aborted or impossible-looking failure is a machine event.
  Re-run it. A reproducible failure that survives a re-run and an isolated run
  is a real defect and should be treated normally.

### Open questions raised by this review (no code change made)

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
