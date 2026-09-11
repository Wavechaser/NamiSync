# Latest session handoff

## Setup layout and recent-pair availability (2026-09-11)

GUI-S1 starts at b08a05b on milestone1. User authorized implementation, review
and commit. M1-6 task effects, frozen options, serial batch starts and fresh
folder admission remain the baseline. No icon-package upgrade or shadow fix.

Setup uses separate Setup and Recent pairs cards, the gallery segmented task
switch, inline path/recent dropdowns and separate folder-open Browse buttons.
Deletion policy retains two descriptive choices; verification is a visible
switch. More options folds other switches and filters without changing values.
Recent pairs have two stacked truncated paths and green/red dots beside neutral
status text. Only online pairs are selectable.

The read-only async-small probe_recent_pairs command composes existing recents
and candidate-resolution primitives: at most five exact pair/endpoint identity
rows and ten deduplicated resolutions. No slots, continuations, persistence or
task starts. Setup loads independently; Refresh coalesces without polling, stale
page/list/identity replies are ignored, and unknown/unavailable rows stay disabled.
Selecting or starting still freshly admits roots.

Combined focused checks passed (385); the ordinary repository gate passed
(4,979 passed, four skips, 30 headed deselected). All 12 import contracts pass;
fresh adversarial review approved the integrated change. All 30 installed headed
interface tests passed (including Setup and gallery). Headed fixtures use real ledger pairs with one removed source
to verify offline display and long-path truncation. Existing typed/picker/mount,
frozen/navigation, Plan again, inventory, batch and reload witnesses remain.
Tests use one slot, fresh external basetemps and PIP_NO_CACHE_DIR=1. Avoid window
interaction during headed tests; logs remain in ignored build/gui-icons/.
Collapsed, expanded and frozen captures were inspected for layout. Their PNGs
retain transparent WebView pixels (dark card white at alpha 13/255); a viewer
that ignores alpha displays white cards, so these are not native Mica color
evidence. Actual control visibility and neutral status colors have computed
browser assertions. Setup-scoped hidden styling prevents component display
rules from exposing inapplicable mode/actions.

Final evidence: setup-ordinary-02.txt, setup-headed-all-01.txt and
setup-imports.txt under build/gui-icons/. GUI-S1 is complete; continue GUI tuning
only as requested. M1-7 implementation remains outside this session.

Prior icon commits: 5e83f9a, fe3c11c and b08a05b. TOOLS owns CLI syntax;
DESKTOP_UI owns selective placement. Shadow investigation d6b27ec and BUGS retain
10-bpc WCG SDR findings: broad key shadows over translucent receivers reproduce
the reported halo; opaque receivers and ambient-only shadows appear unaffected.
Exact renderer cause remains unproven, Mica remains required, no fix is implemented.
Ignored build/gui-tuning/halo-10bit/ retains diagnostic artifacts. Display
settings and user-owned windows are outside this task.
