Notes for "Response/snapshot copy allocation (2026-11-07)": text files chosen from `build/allocation-20261107/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/allocation-20261107/README.md`

# Execution allocation evidence, 2026-11-07

This ignored directory holds the baseline bridge source, focused test receipts,
and diagnostic microbenchmark script/results. Names use baseline/candidate plus
run number. Preserve through review. These artifacts are not product inputs or
release acceptance thresholds.

# `build/allocation-20261107/builder-results.md`

# Builder results

Base product: ade6ba75 (same bridge bytes as b6a4fefe).

## Focused verification

- Before edits: `python -m pytest -q -p no:cacheprovider tests/interfaces/web/test_transport.py -k 'node_drain or node_interactive or node_timeout'`: 3 passed, 157 deselected in 1.34 s. The timeout pattern selected no timeout case; the later targeted run includes the start-plan identity test explicitly.
- After edits: `python -m pytest -q -p no:cacheprovider tests/interfaces/web/test_transport.py -k 'node_drain or node_interactive or start_plan_identity'`: 6 passed, 154 deselected in 1.42 s.
- Full focused: `python -m pytest -q -p no:cacheprovider tests/interfaces/web/test_transport.py tests/interfaces/web/test_browser_event_v5_consumers.py`: 166 passed in 1.94 s.
- One intermediate fixture failure: strengthening native display mutation initially altered a reused expected fixture object. Limited the witness to the first display-bearing response, and retained an explicit assertion that the mutation happened. This was test-fixture aliasing, not a product failure.

## Diagnostic microbenchmark

`run_microbench.py` runs the real public getPlanWindow wrapper under the existing
512 MiB Node Job containment, with the current wire fixture expanded to 64 rows.
Every response is freshly parsed from serialized JSON, validates normally, and
checks row count/content. After 200 warmup reads, V8 samples allocations including
collected objects over 2,000 reads at a 16 KiB sampling interval. Six fresh Node
24.22.1 processes ran baseline, candidate, candidate, baseline, baseline, candidate.

- Baseline sampled bytes: 1,028,048,192; 1,029,834,376; 1,028,869,184.
- Candidate sampled bytes: 266,960,888; 267,199,496; 268,973,664.
- Clone-inclusive baseline sampled bytes: 724,006,032; 722,876,520; 726,294,816. Candidate: zero.
- Baseline elapsed milliseconds: 708.10; 708.31; 718.06.
- Candidate elapsed milliseconds: 278.39; 271.94; 276.46.

These are observations for a response-heavy JS seam, not whole-app memory or
throughput claims. Native script compilation, DOM rendering and filesystem IO
are absent. The owning real-package A/B study must establish their significance.
Raw child receipts are microbench-01 through microbench-06 JSON files.

## Ownership

pywebview 6.2.1 `js/api.js::_checkValue` deletes its return callback and resolves
JSON.parse(value). Direct and original-observation responses thus have no Python
backing aliases in the renderer. The interactive test executes that installed
function and mutates the retained test-native backing result during ack, asserting
the delivered display stays original. Shared completion-event data retains its
capture. Terminal retry retains initial update/snapshot capture and clones the
mutable update for each callback. Frozen snapshots can be shared across retries.
