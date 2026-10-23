# Latest session — Inventory refresh viewport, 2026-10-24

User-authorized browser improvement on `milestone1`, starting at `b24c66f0`.
M1-12, release, DOC-2, push and PR remain inactive.

Full/selected refresh and publication reloads retain a visible non-notice row,
its viewport-relative pixel offset, and viewport height. The existing bounded
Inventory window anchor resolves that row in the replacement view before the
256-row publication window loads at its restored position. Missing/filtered-out
anchors fall back to a clamped offset. Active-row identity uses its own final
window anchor; restoration is passive and does not take focus. Integrity Follow
remains the final reveal owner. Existing task/session/pane/reload fences reject
late lookup and publication results. No bridge/backend/core contract changed.

Verification: 2 focused browser-composition tests, 2,092 interface tests, all 12
import contracts, the installed gallery and installed Inventory journey passed.
The final harness's 3 ordinary tests also passed. The native journey preserves a
partially visible row through real Refresh and samples painted frames for a jump
to the top. Fresh independent review approved product and the final harness delta.
Root owns the final atomic commit and clean-tree check.

Two earlier native attempts failed the new test's exact requested-offset oracle:
Windows scaling represented requested 7 pixels as 6.857142925262451. Setup, both
arrow gestures, native focus preparation, and pre/post/minimum refresh positions
were identical. This was a measurement assumption, not a product defect. Final
acceptance requires a positive partial-row offset and exact observed preservation.
All failed and passing receipts/captures and their dependency accounting are in
`build/inventory-refresh-anchor-20261024/verification.md` and neighboring evidence.
No recovery refs, stashes or unrelated files changed.
