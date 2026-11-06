# Small-file investigation handoff — 2026-11-06

The independent investigation below informed the follow-up on `b2e872e6`.
Its proposed savings are hypotheses. In the matched current rig the native
byte-copy call took 0.11 ms/file. Inclusive path timers overlap, thread CPU
does not isolate GIL contention, and the SQLite microprobe timed a full
single-row transaction. The 33 visible window reads cover the click-to-terminal
interval; 25–26 began inside executor execution. See the
[matched measurements](PERFORMANCE.md#copy-phase-only--matched-revision-and-gui-comparisons-2026-11-06)
and the [current decisions](M1_PLAN.md#small-file-copy-cost--2026-11-06).
Grouped directory flushes and ledger commits belong to the M2 small-file batch.

The follow-up service probe measured 0.662 and 0.700 ms/file in the recorder
with outer timing alone. Commit accounted for 0.404–0.416 ms/file in two
instrumented runs. Suppressing identical timeout assignments gave overlapping
results, so retain the writer as implemented. All six runs checked their
mirrors and durable identities. Raw samples and limitations are indexed by
`build/copy-record-opt/summary.json`. The native path and headed delivery
comparisons use separate frozen snapshots and require independent review.

## Independent investigator's initial interpretation

The 6–7 ms per file is spread over three layers. In the executor, about 1.9 ms is spent re-checking paths that were just checked. Recording costs about 0.6 ms, half of it one disk flush per file. In the GUI, the page fetches events once per file, and that churn slows down the copy thread itself. I haven't changed any product code.

## Where the time goes (1,000 × 4 KiB)

| Layer | ms/file | Main cost |
|---|---:|---|
| Executor alone | ~3.2 | Path guards ~1.9 · two flushes ~0.7 · actual copy work ~0.45 |
| + durable ledger | +0.9 | Recording 0.64 (database flush ~0.29, the rest Python/SQL) · settlement +0.07 |
| + GUI, Plan hidden | +2.0 | ~1,010 event fetches, about one per file |
| + Plan visible | +0.5 | ~33 Plan window reads at ~18 ms CPU each |

New measurements, saved in `build/perf-probe-20261106/`:

| Probe | Result |
|---|---:|
| `os.lstat` (the full check used for every component) | 22–25 µs |
| `GetFileAttributesW` (reads only the attribute flags) | 2.6–2.8 µs |
| Database commit, one per file (current setting) | 0.28–0.30 ms |
| Same, 64 rows per commit | 0.006 ms/row |
| Flushing a 4 KiB file to disk | 0.36 ms |
| Flushing its parent folder | 0.31 ms |

## Changes that fit the current contracts

1. **Cheaper folder checks (about −0.4 ms/file).** Each copied file gets 26 `lstat` calls, about 1 ms in total. About 20 of them only check whether a parent folder is a reparse point, which needs only the attribute flag. Switching those to `GetFileAttributesW` keeps the same checks at the same moments and is about 9× cheaper. Full `lstat` stays wherever the result is actually used.
   - Where: [native.py](../namisync/modules/executor/native.py#L1573)
2. **Drop back-to-back duplicate checks (about −0.3 to −0.5 ms/file).** Each copy resolves paths 10 times and re-checks the roots 7 times, and some of these repeat each other within microseconds:
   - Each explicit root re-check is followed by a call to `resolve()`, which checks the root again.
   - `_guard_present(source)` is immediately followed by `fs.resolve(source)`.
   - `_guard_expected_target` is immediately followed by `fs.resolve(target)`.

   Merging these keeps a fresh check before every action. PERFORMANCE.md already lists this as an open question.
   - Where: [runtime.py](../namisync/modules/executor/runtime.py#L1652)
3. **Plan refreshes while it's visible (about −0.5 ms/file).** Every finished file marks the visible Plan as stale, and `refreshExecutionWindow` re-reads it back to back. Refreshing only when a finished file is in the visible rows, or capping refreshes at about 4 per second, removes most of the ~33 reads.
   - Where: [app.js](../namisync/interfaces/web/assets/app.js#L2483)
4. **Profile the recorder's Python side before changing it.** About 0.35 ms per file is spent outside the flush. Likely candidates are listed below, but I haven't measured how much each one costs:
   - The payload hash over the full operation projection.
   - The `PRAGMA busy_timeout` statement before every transaction.
   - The extra lookup query before each insert.
   - Re-reading the row's identity after writing it.

## Changes that need further discussion

5. **Batch the per-file events (largest GUI gain, about −1.4 to −1.7 ms/file).**
   - **Current behavior:** progress updates already wait 150 ms to collect a batch, but each file's result is sent immediately ([drain.py](../namisync/interfaces/web/drain.py#L2755)). The page then asks again right away, so there is about one request per file.
   - **Cost per file:** each request passes through four threads: the observer thread, the long-poll thread, a brand-new thread that pywebview 6.2.1 creates for every call, and a blocking `Invoke` on the UI thread.
   - **Effect on the copy thread:** the handler threads use only 0.06–0.09 s of CPU in total, yet the copy thread's CPU rose from 3.4 s to about 4.2 s. That points to contention for the Python interpreter lock (GIL).
   - **Evidence it works:** your 25 ms delay test already showed a large gain.
   - **Proposed change:** batch file results for 25–50 ms, but still send state changes, phase changes, gaps, the final result and close immediately.
   - **Contract impact:** this changes BRIDGE.md's frozen SH-G-8 delivery contract and needs new latency, replay, cancel and final-result checks.
6. **Record and flush in groups (about −0.6 ms/file through the service).**
   - **Proposed change:** publish K files, flush each parent folder once, write the K records in one transaction, then send their results. A pre-flush hook already exists: `_flush_before_destructive`.
   - **Contract impact:** item results would arrive after their group is committed. A crash could leave published files that aren't yet recorded, so reruns would have to settle those cleanly. This crosses the executor, database and session layers, so it needs a formal scope from you.
7. **Two path-based checks on the temp file before publishing (about −0.1 to −0.15 ms/file).** Publishing renames the file through its open handle, so these checks don't protect the file that actually gets published. Removing them changes the safety reasoning, so it would need review against EXECUTOR.md.

**Not recommended:** lowering the database's `synchronous` setting to NORMAL, which gives up durable recording on power loss. Also not recommended: skipping the per-file flush before publishing, which would break atomic publishing.

## Rough outlook

Items 1–3 alone should bring the visible-Plan GUI from about 6.7 ms to roughly 5.5 ms per file. Adding items 5 and 6 should reach roughly 3.5–4 ms. These are estimates: contention effects don't add up linearly, so each step needs a rerun on the matched rig.
