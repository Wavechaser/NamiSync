# Latest session — bridge counter and loading investigation complete

2026-10-07–08, milestone1. User scope was #1 implementation and #2–5
investigation only. Delivered BC1a 806df04 (remove hot byte-counter observer)
and BC1b 9d09f70 (bounded 4K bulk string encoding). No further product changes.
M1_PLAN owns scope, PERFORMANCE owns methods/results, and BUGS records the
open continuous-scroll finding. Final accounting is in the evidence directory.

Evidence: build/bridge-counter-study-20261007/. BC1a passes 33 focused and
398 tools checks. BC1b passes 587 composition, 191 post-migration focused,
5,982 ordinary (four privilege skips), 12 import contracts and six installed
transport checks. Retain earlier failures, including the stale observer test
that prohibited legitimate product string encoding. No persistent execution
policy changed. Independent review verified admission/custody, raw statistics,
source/wheel/pin identities and all 144 matrix asset hashes.

Corrected baseline/candidate matrices each contain six fresh children and
96 gestures. Jump capture falls from 18.505 to 12.477 ms Plan and 17.070 to
13.568 ms Inventory. Coverage and ranges are in PERFORMANCE: Plan bursts do
not improve, and Inventory jump ranges overlap. Both retain one concurrent
read. Original C5 hot-observer timings are not this counter's reference.

Investigation uses four real component windows, separate unwrapped/cProfile
blocks, six installed DOM/steady children, and two browser-event-only controls.
There is no typed-view reconstruction in these windows. Roughly 11,000 string
encodings, mostly keys, and 45,000–48,000 budget charges remain per window.
Profile overhead is substantial; counts do not predict saved latency. Sample-only
schema proposals save 35.6% Inventory and 21.0% Plan; no migration was implemented.
Container rollups, full checksums and Inventory geometry have real consumers;
row-consumers.md traces those uses. Inventory basenames already shipped in C1.

DOM endpoint differences explain the apparent gap. Detached construction costs
3.9/3.8 ms and replacement 2.1/1.9 ms (Plan/Inventory); Inventory pays 15.9 ms
post-insertion while Plan's residual geometry flush costs 16.3 ms afterward.
No evidence supports rewriting Inventory decoration on that comparison alone.

New OPEN finding: continuous movement invalidates exact viewport-request
freshness and discards still-compatible responses. At 240 rows/second, both
pages remain uncovered about 11.1 of 12 seconds and recover at rest. Browser-
event-only controls reproduce this (Plan 453 reads/452 discarded, Inventory
430/429). Native wheel/compositor cadence is unmeasured. Same-index requests
are deduplicated. app.js revision/offset gates and Inventory tree generation
share the mechanism; it predates the Python-only BC1 change.

Recommended user decision: review compatible viewport response adoption across
both pages, preserving task/session/publication/view/action/navigation/highlight
fences and one-window/one-read bounds. Then consider bounded row DTO migration
and remeasure. Prefetch is a later experiment. No instance fix was attempted;
this investigation does not authorize further implementation.

All disposable installations, raw frames/profiles, manifests and failed receipts
are retained. Assets are restored and identities rechecked. No active test or
benchmark process. Native/broad checks use the actual Windows user through
require_escalated, preserving foreground guards. No push, PR, worktree or
unrelated changes. Prior GUI-C1–C5 evidence remains in its original directory.
