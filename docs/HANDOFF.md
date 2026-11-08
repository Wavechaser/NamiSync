# Latest session — Inventory row reuse, 2026-11-08

## Outcome and scope

Base is `e80cec1a`. The user requested Inventory allocation optimization and a
trace of remaining Follow costs. Delivery is narrowed by explicit user approval
to row reuse; the automatic loaded-target shortcut is deferred.

`tree.js` permits its Inventory consumer to retain compatible rows at the same
visible index. `inventory_review.js` requires the same review, publication,
active ordinary integrity session, view/highlight revision and total, then
compares complete row facts. Unchanged rows retain DOM/handlers; changed facts
rebuild the row, and changed integrity presentation updates the presence cell.
Only the current window's checkbox controls remain after a successful commit.
Rejected viewport commits restore the accepted overlay. Generic tree behavior,
Follow scheduling, row limit, focus/selection and GC policy are preserved.

## Findings and disposition

The combined candidate removed foreground Follow lookups. That exposed the
independent overlay refresh on nearly every drain reply: Baseline window reads
rose from 542 to 3,788, elapsed time from 47.62 to 150.78 seconds, and renderer
private peak reached about 6,709 MiB despite much lower DOM construction. Verify
was canceled and the owned host closed normally. The user chose row reuse only;
`app.js` and its app probe were restored to base. The combined patch, source
copies, failed/partial receipts and source trace remain in ignored evidence.

Review also caught stale-view admission in the withdrawn shortcut and an API
floor violation in the retained comparator. The latter is corrected to the
existing own-property-call idiom. `mechanism-review.md` records independent
recurrence review and the approved narrow correction; no broader fix was added.

## Verification and evidence

Functional evidence: `build/inventory-follow-20261108/`. Final focused pane/app,
generic tree and packaged API-floor checks pass (four cases). The final clean
interface department passes all 2,261 cases. Both installed Inventory/default
tree gates pass; raw receipts, screenshots and wheel identities are retained in
`headed-receipts/`.
Final independent approval is recorded in `independent-review.md`; documentation
links and diff checks pass.
The first department attempt put custody temporary files inside the source tree
and ran under restricted filesystem permissions; its errors are retained. The
exact failed-node retry exposed the API-floor issue above, now corrected.

Measurement evidence: `build/inventory-costs-20261108/`. Same-window 8/64/256-row
paints create 112/896/3,584 elements before versus zero after; a one-row shift and
changed presence cell create 16 elements and seven listeners at all widths and
all three modes. Native baseline and candidate runs use an isolated 10k x 32 B
corpus, normal terminal GC, fixed pauses, frozen source/runtime/driver identity,
exact per-mode path/outcome audits and empty-Job shutdown. Final `final-01`
evidence matches the API-compatible source. Created elements fall 81–91%, but
renderer private peaks rise in this sample (1,759→1,811 / 1,295→1,585 /
1,082→1,629 MiB). Window reads rise 1,181→1,510. No footprint, throughput or
read-reduction claim is made. PERFORMANCE owns final tables and limits; the
earlier row-only run remains separate pre-correction evidence.

An external table-loading instrumentation check has a pre-existing bridge
anchor mismatch, independently reproduced from the base revision. The changed
tree transformation parses successfully in an isolated contained Node witness
(`check_table_consumer.json`). The unrelated profiler repair is deferred.

## Immediate operational context

No measuring-session process, profile or fixture was changed. Task-owned native
fixtures/profiles remain registered under the measurement root; retain them with
the evidence. No task branch or worktree was created.

Remaining costs include full window payloads/overlay reads, bounded comparisons,
new entering rows, changed cells and open-detail rebuilding. Plan additionally
builds a temporary complete row to update three execution cells. The user's
40 MiB/eight-second observation is not attributed to a specific path by this
study. Revisit Inventory refresh ownership/cadence before its local shortcut.
No execution GC, heap cap, further post-Close GC or phase-transition GC is added.
Verification pipelining, grouped recording and small-file batching remain M2.
Prior resource studies, the Plan optimization and early-close observations stay
in PERFORMANCE and their existing evidence roots; their fixtures are untouched.
