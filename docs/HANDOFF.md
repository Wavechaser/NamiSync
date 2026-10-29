# Latest session — Shell gutter compensation, 2026-10-29

One requested CSS outcome on milestone1 from 253e78af. Removed the document's
stable scrollbar gutter while retaining the work-panel stable gutter on every
page, including Plan and Inventory. Global inline-end padding is 24px minus the
shared 10px scrollbar-size token, giving 14px plus the normal 10px gutter. Other
outer padding stays 24px. Forced colors intentionally retain browser-owned
scrollbar width and the same 14px padding, per the user's clarification.

The scrolling gallery explicitly restores its document gutter and symmetric
24px padding; its production-shell witness removes and then restores those
overrides. Direct native geometry checks require root auto/work stable and 24/14px
padding, plus an actual 24px right content gap outside forced colors. Internal
table/detail/rail scroll owners, native input and action behavior remain intact.

All 2,105 interface tests and nine installed cases pass; eight native cases passed
initially and larger execution passed unchanged on rerun. The retained failed
attempt waited for ordinary Resume; its underlying cause is unestablished.
Independent review found no remaining issue. Normal-theme gallery assertions
confirm the actual 24px page right gap, and the minimum-window capture was viewed.
Evidence lives in build/gui-gutter-20261029/. Subject docs, delivery register and
changelog updated. No public contracts, worktrees, recovery refs, push or PR.
Inventory recents, queued-input coordinator, M1-12, release and DOC-2 stay inactive.
