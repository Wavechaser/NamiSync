# History Module

Status: history schema v4 records reliable session events in bounded,
incrementally durable windows and exposes bounded summary, item-page, and
event-page reads. Retention, export, durable task custody, and execution resume
remain later work.

## Purpose And Boundary

History is an independent audit of what NamiSync attempted and reported. It is
not the filesystem ledger and never participates in a filesystem or ledger
transaction. An unavailable, oversized, conflicting, or unwritable history
stream degrades the result's `audit` axis; it must not change filesystem,
integrity, or ledger-recording truth.

The dispatcher attaches one distinguished reliable observer at admission.
Lossy `Progress` events are intentionally absent from durable history. Reliable
sequence numbers can therefore contain gaps without implying lost audit data.
The live `Terminal` is also absent: terminal truth is the finalized
`history_runs` row, written before that live terminal is released.

## Schema V4 And Reset Boundary

The current exact marker is
`contract_id=m1-history-windowed-events-v1` with
`HISTORY_SCHEMA_VERSION = 4`. NamiSync refuses history v1-v3 and a v4 database
with a missing or mismatched marker through a read-only connection. Refusal
must not alter the database or its WAL, SHM, or journal sidecars. This remains
a pre-release reset-only boundary: close every NamiSync process and reset the
ledger and history databases together. Startup never deletes either file and
there is no v3-to-v4 migration because v3 did not retain the reliable state and
phase events needed to reconstruct the journal.

`history_runs` is created provisionally by the first committed window. It holds
immutable context, lifecycle and phase, the committed sequence and item
watermarks, rolling outcome counts, a context hash, the rolling event-chain
hash, and nullable terminal axes. `terminal_payload_hash IS NOT NULL` is the
authoritative finalized marker. Terminal-only columns become populated as one
checked group, so a committed prefix cannot impersonate a finalized run.
`started_at` records an actual start only: a finalized queued cancellation with
`disposition=unrun` keeps it null and validates its end against `created_at`.

`history_events` is the append-only reliable-event journal. Its primary key is
`(run_id, event_seq)`. Each row holds the canonical envelope JSON, timestamp,
schema and body type, payload hash, and optional typed `ResultItem` projection.
Result items receive a dense, immutable, one-based `item_order` and retain the
unique `(run_id, item_type, item_id)` contract. Separate indexes serve event
catch-up, item paging, and typed aggregates used by summary classification.

`history_phases` remains a small terminal summary, not an event-detail store.
Its explicit phase-count ceiling protects summary reads from hostile or broken
producers. Phase names and terminal failure type names are limited to 256
UTF-8 bytes; phase errors and terminal failure messages are limited to 4,096
UTF-8 bytes. Oversize text rejects history finalization before its transaction,
degrading audit while leaving any earlier committed prefix incomplete and
readable. Matching SQLite byte-length checks defend the stored contract. Phase
detail and terminal axes are written only in the finalization transaction.

## Window Policy

`HistoryWindowPolicy` is the single history-side policy value. Production uses
these defaults:

- `max_events = 256`
- `max_bytes = 1_048_576` serialized bytes
- `max_event_bytes = 1_048_576` serialized bytes
- `max_age_seconds = 1.0`

An observer serializes and hashes a reliable envelope before retaining it. An
individual event over the per-event ceiling is rejected and audit degrades;
the domain operation continues. Before accepting an event that would cross the
window byte or count bound, the existing window is committed. Reaching either
bound commits immediately. `StateChanged(PAUSED)` forces a commit after that
event is admitted. The audit pump commits by the original one-second deadline
from the first event even under continuous traffic, and performs a final clean
flush at shutdown. Finalization commits its tail and terminal row together.

Pending objects and their serialized-byte count are cleared only after the
transaction commits. A failed transaction leaves the complete pending window
and the previous durable watermark unchanged, then permanently degrades that
observer. Earlier windows stay readable. A process crash can lose the final
uncommitted window but cannot expose part of a window.

The generic dispatcher contract is `on_event(envelope)`, idempotent `flush()`,
`finalize(result)`, and exactly-once `close()`. The dispatcher owns timing and
backpressure; the database observer owns window contents and atomicity. A
flush/write failure stops further audit admission and finalization so no tail
after a broken prefix is recorded. Successful durable finalization is settled
before cleanup, so a later close error cannot rewrite persisted or live
terminal truth.

## Admission, Idempotency, And Hashes

Only hashes for the current window are retained in memory. The observer keeps
one scalar highest accepted sequence. A sequence within the pending window is
verified from that bounded map; an older sequence is resolved with an indexed
`history_events` lookup:

- the same sequence and hash is an idempotent no-op;
- the same sequence with another hash is an integrity error;
- an unseen lower sequence is an out-of-order integrity error.

Each window transaction creates or validates the provisional context, verifies
any concurrent replay, appends new receipts and projections, advances dense
item order and rolling counts, and atomically publishes the new event chain and
watermark. Exact concurrent replay is harmless. A changed context, event, or
terminal payload under the same run token raises a token conflict.
`last_committed_at` is sampled only after the serialized writer owns its
transaction and is clamped to the prior durable value if wall time moves
backward. Every commit is also clamped to the latest envelope timestamp newly
made durable, as well as admission and any observed start, so a higher
watermark never carries an older or impossible commit timestamp.

Finalization hashes immutable context, the committed event-chain hash, and the
terminal result without `result.items`. Item detail is already authenticated by
the event chain; hashing the session-wide terminal tuple again would require
retaining the whole run and defeat the window bound. Identical repeated
finalization is a no-op. A changed repeat is rejected. Summary reads and
identical repeated finalization reconstruct the bounded terminal result from
the stored terminal columns and ordered phase rows, then recompute this hash.
Before that check, the fixed set of loaded immutable run-context columns is
rehash-checked against `context_hash`, for incomplete and finalized summaries
alike. A mismatch is an integrity error; stored hash blobs cannot make modified
context or terminal columns authoritative.

## Incomplete Runs

A committed row without a terminal payload hash is returned as `incomplete`,
including after restart. Its committed state, phase, watermarks, counts, and
pages remain useful, but its terminal axes are absent and its headline is
`incomplete` even if the last reliable lifecycle event says `COMPLETED`.

NamiSync does not infer that such a run was interrupted, abandoned, or safe to
resume. Another process may still own it, and M1 has no durable process/session
lease. Durable custody and automatic interruption classification belong to M2.

## Bounded Readback

`HistoryRepository` provides only these read shapes:

- `list_summaries(limit)` uses a fixed number of queries for run rows, bounded
  phase rows, and one fixed-size indexed classification aggregate per run. It
  never selects or decodes event JSON and never calls a full-detail getter per
  run. Free-form item kinds and reasons cannot create additional summary
  objects, and phase/error text has the fixed UTF-8 byte ceilings above.
- `get_summary(run_token)` returns one terminal or incomplete snapshot with
  context, lifecycle, phase, watermarks, counts, axes, and phase summaries.
- `get_item_page(run_token, after_order, through_order, limit)` keyset-pages
  typed items by dense item order.
- `get_event_page(run_token, after_seq, through_seq, limit)` keyset-pages
  canonical reliable envelopes by sequence.

Read limits are explicit and bounded at 256; invalid limits are rejected rather
than truncated. When a page omits `through_order` or `through_seq`, the
repository starts a fresh traversal by capturing the corresponding durable
watermark in the same SQLite read transaction as the page. Callers reuse that
watermark for later pages, so one traversal sees a stable committed prefix even
while a writer commits newer windows. A caller-supplied event watermark is an
inclusive sequence bound and may fall on an omitted lossy `Progress` sequence.
Event reads fetch one indexed lookahead row to determine `has_more`, but return
and decode no more than the requested limit.

Every event-page request verifies that `history_runs.last_committed_seq` is the
actual maximum durable event sequence in the same read snapshot, including
requests traversing an older caller-supplied watermark. A missing, trailing, or
otherwise mismatched official row is history corruption, not an ordinary
sequence gap. If a fresh traversal's `after_seq` is ahead of current durability,
the repository returns an empty terminal page with the captured durable
`through_seq`, the unchanged `after_seq` as `next_after_seq`, and
`has_more=False`. That page ends the traversal; a later attempt omits
`through_seq` again to capture newly committed history. An explicit fixed
watermark below `after_seq` remains an invalid interval. Each request ends its
read transaction, allowing the same WAL reader to observe the next committed
window on its next request.

Workflow code supplies the finite selection-exclusion/no-op predicates and,
not SQL, interprets the resulting primitive counts into integrity and headline
values. The service exposes `list_history()`,
`get_history_summary()`, `get_history_items()`, and `get_history_events()`.
There is no unbounded `get_history()` compatibility path. CLI detail rendering
prints the summary and streams item pages without assembling a complete run.

## Subscriber Repair

A subscriber that receives `Gap` keeps the sequence of its last successfully
applied non-`Gap` envelope, not the sequence carried by the synthetic `Gap`
itself, requests durable event pages through one captured committed watermark,
and applies the available reliable envelopes in order while deduplicating by
sequence. Missing
lossy-progress sequence numbers are expected and are not reported as history
loss. A live cursor ahead of the committed window produces the empty fresh page
described above; the next repair attempt starts a new traversal. The subscriber
then reads the summary to recover finalized terminal truth if the live terminal
was missed, resubscribes after the committed watermark, and repeats if live
replay advanced again during repair.

Only the committed prefix can be repaired. If audit degraded before an event
became durable, history correctly makes no claim that it can recover that tail.

## Failure Semantics

Observer construction, canonical serialization, oversized events, ordering or
token conflicts, SQLite contention exhaustion, window writes, terminal writes,
and cleanup failures are audit failures only. They remain visible through
system health and the terminal audit axis when a terminal can still be
settled. They never roll back or reinterpret filesystem changes or ledger
evidence.

Finalization remains a two-party ownership decision. If the caller reaches its
cutoff before the pump owns finalization, both live and any late retained
terminal truth use `audit=degraded`. If the pump owns first, the caller waits
for the actual write result. There is no corrective second terminal or mutable
terminal history row.

## Policy Tuning And Scale Gate

The four `HistoryWindowPolicy` fields are the only tuning point. Do not change
them from anecdotal timing. Use a fixture with 50 runs and 1,000,000 items,
including one 100,000-item run, and record:

- Windows build, CPU, storage, Python and SQLite versions;
- cold versus warm cache state;
- transaction count and window count;
- p50, p95, and maximum window-commit latency;
- peak pending event count and serialized bytes;
- 50-run summary latency and 256-row item/event page latency.

The release gates are at most three seconds for the 50-run summary; 500 ms p95
and one second maximum for either 256-row page; and no normal window commit at
or above the five-second audit-offer cutoff during a 100,000-event recording.
That recording must remain `audit=OK` and never exceed either pending bound.

The 2026-08-05 baseline ran
`.\.venv\Scripts\python.exe tests\history_benchmark.py` on Windows 11
10.0.26200, Intel64 Family 6 Model 189 with 8 logical CPUs, Python 3.14.6, and
SQLite 3.50.4. The 650,465,280-byte fixture contained exactly 50 runs and
1,000,000 items, with one 100,000-item run. The full-range recording took
87.969 seconds over 3,919 transactions; commit latency was 7.969 ms p50,
25.237 ms p95, and 104.301 ms maximum. Peak retained state
was 256 events and 79,360 serialized bytes. A fresh-reader 50-run summary took
0.984 seconds and the immediate repeat took 0.652 seconds. Fresh-reader
item/event pages took 9.556/8.012 ms; full-range warm item pages were 10.686 ms
p50, 17.746 ms p95, and 37.898 ms maximum, while event pages were 9.800 ms p50,
13.995 ms p95, and 22.100 ms maximum. “Fresh reader”
means a new SQLite connection after fixture creation, not a forced cold OS
filesystem cache. All locked gates passed.

The 2026-08-06 rerun after sparse event-bound and official-watermark validation
used the same environment, fixture, and policy. Recording took 48.826 seconds
over 3,919 transactions; commit latency was 3.676 ms p50, 14.382 ms p95, and
204.203 ms maximum, with the same 256-event/79,360-byte retained peak. Summary
readback took 0.409 seconds on a fresh reader and 0.516 seconds immediately
afterward. Fresh-reader item/event pages took 3.650/5.092 ms; warm item pages
were 3.927 ms p50, 7.486 ms p95, and 8.861 ms maximum, while event pages were
3.614 ms p50, 6.163 ms p95, and 6.752 ms maximum. All locked gates passed; no
window-policy default changed.

Increasing a threshold trades crash exposure, memory, and write latency for
fewer transactions. Decreasing one does the reverse. The one-second maximum
age is a durability bound, not a debounce interval; continuous events must not
postpone it.

## Regression Contract

Automated coverage pins count, byte, age, pause, close, and finalization
flushes; oversized-event isolation; atomic visibility and rollback; committed
prefix recovery; incomplete-versus-finalized visibility; duplicate/order/token
conflicts; dense item order across pause/resume; bounded page limits and stable
watermarks; fixed summary query count without event decoding; WAL reader
visibility; streamed CLI output; subscriber repair; finalization parity; and
the relevant query plans.

The structural sequence-admission test must continue to prove that adding an
event cannot iterate all prior hashes. Wall-clock timing is not an acceptable
CI assertion for that O(1) property.
