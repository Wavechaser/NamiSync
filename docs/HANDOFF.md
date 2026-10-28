# Latest session — Revised Filter button counter, 2026-10-28

User rejected the standalone counter/layout containment in269736f6. Exact revert
2a8d1843 restored the b185f48b tree after independent review. The revised counter
commit containing this handoff implements the approved replacement on milestone1.

## Delivered

Filter displays matching/total items inside its existing button. No standalone
caption or CSS/containment change. Existing All-neutral/active-category accent,
menu interaction and Search layout remain. Plan reuses filter_counts.all,
including mkdir and notices while excluding ordinary structural/prior context.
Inventory All/default excludes acknowledged rows; denominator includes them;
explicit acknowledged views can match them. The dropdown now displays All count.

One exact matched_item_count field per summary is accumulated in the existing
scope pass. Selection prefixes are unchanged. Validators, producers and fixtures
migrated. No synthetic retained-count machinery restored. The previous icon,
square-control and leading-navigation-context commits remain intact.

## Verification

6,250 ordinary tests passed, four existing skips; all12 import contracts pass.
Focused116, count-owner81 and migrated driver33 pass. Initial native run passed
both Plan and execution sizes; four gallery checks and Inventory stopped on old
category-badge/hidden-All assertions. Product source was unchanged while the
finite gallery/native/report consumers were migrated. Final native-r2 passes
all five affected checks. Together all nine installed gates pass.

Parent and independent reviewer viewed the actual minimum-window capture:
Filter3/21 inside the accented button, Search beside it on the same line.
NeutralAll21/21 and Inventory304/304→303/304→304/304 interactions retain styling,
exact identity, counts and positive All-dropdown agreement checks.

Evidence: build/gui-filter-button-20261028/ (red, focused, counts, ordinary,
native and native-r2 plus driver-r3). Retained initial failures document stale
fixtures/assertions; they were not product-effect failures. Native roots under
C:/Users/Spectrum/AppData/Local/Temp/namisync-filterbutton28-native[-r2].

No pending batch work, recovery branch, worktree, push or PR. Recents,
queued-input coordinator, M1-12, release and DOC-2 remain inactive.
