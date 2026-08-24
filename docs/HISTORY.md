# History Module

Status: history schema v5 records receipt-aware reliable session events in
bounded, incrementally durable windows and exposes bounded summary, item-page,
and event-page reads. Retention, export, durable task custody, and execution
resume remain later work.

## Accepted Schema-V6 Persistence Target (Not Active)

Status: accepted on 2026-08-24. History v5 remains active until the coordinated
checkpoint-3 reset to history v6 beside ledger v4. `DATABASE.md` owns the
pair metadata, refusal boundary, and reset instructions; there is no in-place
migration or anticipatory schema creation.

History v6 accepts only the coordinated exact core-event receipts, including
duplicate and bounded rejection receipts; it has no mixed-version page or
compatibility decoder. The observer stores the canonical envelope and matching
typed projection from the same admitted snapshot. `M1_BRIDGE.md` owns the exact
event/result shapes, bounds, and codec rules.

Reliable item rows retain their accepted recording and omission facts as part
of receipt identity. Once committed, an item receipt is immutable: later task,
finalization, or audit failure cannot rewrite it or suppress independent ledger
evidence.

Finalization continues to consume the dispatcher's full operation result, not
the bounded live terminal event. It persists the accepted task recording and
producer-omission facts for authentication and bounded reconstruction; the live
summary remains a bridge-owned transport contract.

The typed review-limit fact is persisted as one all-null-or-complete terminal
group. Writer and SQL validation reject partial or mismatched groups before
publication; the group remains independent of audit and participates in
authentication, repeat equality, reconstruction, bounded summary readback, and
CLI rendering. Presentation-only omission state never enters history.

Numeric persistence follows `DEFENSE.md` §1.3 and the mapped bridge decision.
This document owns only the durable consequence: relational values are checked
before transaction, and envelope readback must agree with its typed projection.

## Purpose And Boundary

History is an independent audit of what NamiSync attempted and reported. It is
not the filesystem ledger and never participates in a filesystem or ledger
transaction. An unavailable, conflicting, or unwritable history stream
degrades the result's `audit` axis; it must not change filesystem, integrity,
or ledger-recording truth. One otherwise valid oversized event is instead
retained as a bounded hash-only rejection receipt: audit degrades, but later
reliable events and terminal truth remain recordable.

The dispatcher attaches one distinguished reliable observer at admission.
Lossy `Progress` events are intentionally absent from durable history. Reliable
sequence numbers can therefore contain gaps without implying lost audit data.
The live `Terminal` is also absent: terminal truth is the finalized
`history_runs` row, written before that live terminal is released.

The finalized row copies the workflow result's byte pair without changing its
meaning. `bytes_done` is attempted-work high-water, not durable successful
content, and `bytes_total` is the matching final work budget. It can therefore
include a prefix written to an owned temporary file and removed before a failed
copy publishes anything. Compound sync keeps each phase's work separate and
uses execute as the top-level byte domain. History records what NamiSync
attempted and reported; reliable item receipts and the independent filesystem
ledger, not this aggregate byte pair, own settlement and publication truth.

## Schema V5 And Reset Boundary

The current exact marker is
`contract_id=m1-history-windowed-receipts-v1` with
`HISTORY_SCHEMA_VERSION = 5`. NamiSync refuses history v1-v4 and a v5 database
with a missing or mismatched marker through a read-only connection. Refusal
must not alter the database or its WAL, SHM, or journal sidecars. This remains
a pre-release reset-only boundary: close every NamiSync process and reset the
ledger and history databases together. Startup never deletes either file and
there is no v4-to-v5 migration because v4 has no receipt dispositions,
semantic duplicate links, or hash-only rejection rows from which to
reconstruct the v5 chain.

`history_runs` is created provisionally by the first committed window. It holds
immutable context, lifecycle and phase, the committed sequence and item
watermarks, rolling outcome counts, a context hash, the rolling event-chain
hash, an authenticated prefix-projection hash, and nullable terminal axes.
The prefix hash binds lifecycle timestamps/state/phase, both watermarks, and
all item/outcome/duplicate/rejection counts to the context and receipt chain.
`terminal_payload_hash IS NOT NULL` is the authoritative finalized marker.
Terminal-only columns become populated as one checked group, so a committed
prefix cannot impersonate a finalized run. A finalized run is immutable, and
committed run rows cannot be deleted or replaced.
`started_at` records an actual start only: a finalized queued cancellation with
`disposition=unrun` keeps it null and validates its end against `created_at`.

`history_events` is the append-only reliable-event receipt journal. Its primary
key is `(run_id, event_seq)`. Every row retains timestamp, schema/body type,
the original payload hash, a disposition-bound receipt hash, and exactly one of
three checked shapes:

- `recorded` retains the canonical envelope and, for a result item, its typed
  projection plus identity and semantic item hashes;
- `duplicate` retains the repeated full envelope and links to an earlier
  recorded or rejected identity receipt with the same identity and semantic
  hash, but receives no item order and changes no outcome count;
- `rejected` retains bounded metadata, payload hash, and reason but no
  oversized envelope body; an oversized result item also retains only its
  fixed-size identity and semantic hashes so changed reuse is still fatal.
  Later exact oversized copies remain individually counted rejections and link
  to the first recorded/rejected identity representative.

Canonical result items receive a dense, immutable, one-based `item_order`; a
partial unique index preserves one canonical `(run_id, item_type, item_id)`.
The receipt hash binds sequence, timestamp, schema/body type, disposition,
payload and item hashes, duplicate link/rejection reason, and canonical item
order. Typed summary columns are writer-derived immutable projections of the
retained canonical JSON and are rechecked when an envelope is decoded. The
strict receipt table uses the composite primary key without
a hidden SQLite `rowid`; guarded recursive-trigger writers and schema triggers
make event rows append-only, so indexed classification cannot diverge from the
authenticated envelope. Run rows separately count
duplicate and rejected receipts. Separate indexes serve event catch-up, item
paging, identity-conflict checks, and typed summary aggregates.
A partial unique index admits exactly one recorded or unlinked-rejected
representative per item identity; one bulk lookup per window therefore remains
bounded even if that identity has many linked rejected receipts.

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
individual supported event over the per-event ceiling becomes a bounded
hash-only `event-too-large` receipt, commits immediately, and returns
`audit=DEGRADED`; later events still enter the same run. Before accepting an
event that would cross the window byte or count bound, the existing window is
committed. Reaching either bound commits immediately. `StateChanged(PAUSED)`
forces a commit after that event is admitted. The audit pump commits by the
original one-second deadline from the first event even under continuous
traffic, and performs a final clean flush at shutdown. Finalization commits its
tail and terminal row together.

Pending objects and their serialized-byte count are cleared only after the
transaction commits. A failed transaction leaves the complete pending window
and the previous durable watermark unchanged, then breaks that observer's
prefix. Earlier windows stay readable. A contained rejection does not enter
that fail-stop state. A process crash can lose the final uncommitted window but
cannot expose part of a window.

The generic dispatcher contract is
`on_event(envelope) -> RecordingStatus`, idempotent `flush()`,
`finalize(result) -> RecordingStatus`, and exactly-once `close()`. The
dispatcher owns timing and backpressure; the database observer owns window
contents and atomicity. `DEGRADED` is a contained status and does not stop the
pump. An observer exception or flush/write failure breaks the prefix and stops
further admission/finalization so no unauthenticated tail is recorded.
Successful durable finalization is settled before cleanup, so a later close
error cannot rewrite persisted or live terminal truth.

## Admission, Idempotency, And Hashes

Only hashes for the current window are retained in memory. The observer keeps
one scalar highest accepted sequence. A sequence within the pending window is
verified from that bounded map; an older sequence is resolved with an indexed
`history_events` lookup:

- the same sequence and hash is an idempotent no-op;
- the same sequence with another hash is an integrity error;
- an unseen lower sequence is an out-of-order integrity error.

For a new sequence carrying a `ResultItem`, identity and content are separate
contracts. The canonical hash covers the complete typed item payload while
excluding envelope sequence, time, and session metadata. Re-emitting the same
`(item_type, item_id)` with that same semantic hash produces a non-counting
`duplicate` receipt. Reusing the identity with any changed item field is
producer corruption and breaks the prefix. These rules apply both within one
pending window and against an earlier durable window, including when the first
occurrence was retained only as an oversized rejection receipt.

Each window transaction creates or validates the provisional context, verifies
any concurrent replay, appends new receipts and projections, advances dense
canonical item order and rolling counts, and atomically publishes the new
receipt chain and watermark. The chain advances over each disposition-bound
receipt hash, including duplicates and rejected events. Exact concurrent replay
is harmless. A changed context, event, or terminal payload under the same run
token raises a token conflict.
`last_committed_at` is sampled only after the serialized writer owns its
transaction and is clamped to the prior durable value if wall time moves
backward. Every commit is also clamped to the latest envelope timestamp newly
made durable, as well as admission and any observed start, so a higher
watermark never carries an older or impossible commit timestamp.

Every window recomputes the prefix-projection hash from immutable context, the
committed event-chain hash, lifecycle projections, watermarks, timestamps, and
all rolling counts. Finalization binds that authenticated prefix, `ended_at`,
and the terminal result without `result.items`. Item detail is already
authenticated by the receipt chain; hashing the session-wide terminal tuple
again would require retaining the whole run and defeat the window bound. A run
with any rejected receipt finalizes with `audit=DEGRADED`. Identical repeated
finalization is a no-op. A changed repeat is rejected. Incomplete and finalized
summary reads validate the context and prefix hashes; finalized reads and
repeated finalization additionally reconstruct bounded terminal truth from the
stored axes and ordered phase rows and validate the terminal hash.
Summary, item-page, event-page, observer-reopen, and writer-admission reads also
compare the indexed physical event/item tails with the official watermarks in
the same snapshot. A tail row outside the committed projection is therefore
rejected rather than influencing classification or later admission.

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
  receipt-aware reliable events by sequence. Recorded and duplicate receipts
  expose their validated envelope; rejected receipts expose bounded
  metadata/hash/reason with `envelope=None`.

Read limits are explicit and bounded at 256; invalid limits are rejected rather
than truncated. When a page omits `through_order` or `through_seq`, the
repository starts a fresh traversal by capturing the corresponding durable
watermark in the same SQLite read transaction as the page. Callers reuse that
watermark for later pages, so one traversal sees a stable committed prefix even
while a writer commits newer windows. A caller-supplied event watermark is an
inclusive sequence bound and may fall on an omitted lossy `Progress` sequence.
Event reads fetch one indexed lookahead row to determine `has_more`, but return
and decode no more than the requested limit. The service projects these rows as
`HistoryEventView`; it does not synthesize a live `SessionEventView` for a
hash-only rejection receipt.

Under current history v5, each `HistoryEventView.schema_version` is the
persisted core event version of that row, not the current live-drain version.
Recorded and duplicate rows may therefore legitimately mix supported v3 and v4
envelopes in one page. Readback authenticates the receipt and original payload,
dispatches the Python core decoder by the row version, and exposes a canonical
typed body; a rejected receipt instead has `body=None`. Because the current
reliable-body decoder is additive and uses selected local defaults, that
canonical view is not a byte-preserving copy of the authenticated JSON. The
payload hash, not the projected body, remains the identity of the retained
envelope.

That compatibility posture ends at the accepted checkpoint-3 coordinated
event/database reset. The target history projection consumes only the exact
accepted event schema and needs no legacy or mixed-version browser validator;
an old, mixed, or incomplete database pair refuses before commands. Exact
epochs, reset rules, and projection shapes are owned by `M1_BRIDGE.md`.
Until checkpoint 3 lands, current history validators remain boundary-specific:
compatibility-decode success does not prove live or JavaScript-safe
representation, a retained row does not pass through the live validator, and
v3 compatibility is not tightened without reviewing authenticated fixtures.
These current allowances are not accepted future shapes.

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
and applies the available recorded/duplicate envelopes in order while
deduplicating by sequence. A rejected receipt advances authenticated history
but has no body to replay; the consumer reports the receipt and uses the
degraded terminal/summary truth rather than inventing an event. Missing
lossy-progress sequence numbers are expected and are not reported as history
loss. A live cursor ahead of the committed window produces the empty fresh page
described above; the next repair attempt starts a new traversal. The subscriber
then reads the summary to recover finalized terminal truth if the live terminal
was missed, resubscribes after the committed watermark, and repeats if live
replay advanced again during repair.

Only the committed prefix can be repaired. If audit degraded before an event
became durable, history correctly makes no claim that it can recover that tail.

## Failure Semantics

Observer construction, canonical serialization failure, wrong-session or
illegal event bodies, ordering/token/item conflicts, SQLite contention
exhaustion, window writes, and terminal writes are fatal to that audit prefix.
They remain audit failures only: they never roll back or reinterpret filesystem
changes or ledger evidence. Replay reads retry only
SQLite `BUSY`/`LOCKED` within the existing bounded writer budget; exhaustion
and every non-retryable storage error remain fail-stop.

Observer cleanup occurs after durable finalization. A cleanup-only failure
therefore cannot rewrite persisted or live terminal truth. The pump retains an
internal degraded cleanup state, but that post-finalization state is not yet a
public session-health axis; any future persistent dispatcher/store delivery
must define and test that projection before it ships.

A supported, canonically serializable event exceeding `max_event_bytes` is the
single contained per-event failure. Its bounded durable receipt degrades audit,
later events and finalization continue, and reopening/replay derives the same
degraded result from durable rejection count. Exact replay of its sequence and
payload hash is idempotent; a changed hash is fatal.

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

The final 2026-08-08 history-v5 receipt rerun used the same million-item
fixture and 256-event/1-MiB policy after receipt/projection hardening. Recording
took 136.700 seconds over 3,919 transactions; commit latency was 20.899 ms p50,
44.491 ms p95, and 121.026 ms maximum, with retained state peaking at 256
events/79,360 bytes. Fresh and immediate-repeat 50-run summaries took
1.670/1.605 seconds. Warm item pages were 12.386 ms p50, 15.156 ms p95, and
16.256 ms maximum; event pages were 12.375 ms p50, 14.087 ms p95, and 14.818 ms
maximum. Audit remained OK for the ordinary fixture and every locked gate
passed; no window-policy default changed.

Increasing a threshold trades crash exposure, memory, and write latency for
fewer transactions. Decreasing one does the reverse. The one-second maximum
age is a durability bound, not a debounce interval; continuous events must not
postpone it.

## Regression Contract

Automated coverage pins count, byte, age, pause, close, and finalization
flushes; durable oversized-event receipts and continued finalization; same- and
cross-window duplicate/conflict semantics; atomic visibility and rollback;
committed-prefix recovery; incomplete-versus-finalized visibility;
order/token conflicts; dense canonical item order across pause/resume; bounded
page limits and stable watermarks; receipt/link/hash/counter tamper detection;
fixed summary query count without event decoding; WAL reader visibility;
streamed CLI output; subscriber repair; finalization parity; and the relevant
query plans.

Checkpoint-3 coverage proves exact event-v5-only persistence, canonical-envelope/
typed-projection agreement, immutable item recording facts, once-only full-
result finalization, the all-null-or-complete review-limit group, and bounded
rejection recovery. Shared event-shape and scalar boundary cases remain with
the owning core/bridge checkpoint rather than being cataloged here.

The structural sequence-admission test must continue to prove that adding an
event cannot iterate all prior hashes. Wall-clock timing is not an acceptable
CI assertion for that O(1) property.
