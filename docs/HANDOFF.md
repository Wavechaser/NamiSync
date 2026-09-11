# Latest session handoff

## Setup and task-rail refinement (2026-09-11)

GUI-S2 starts at 9ba6538 on milestone1. User authorized implementation, review
and commit. M1-6 task effects, frozen options, serial batch starts and fresh
folder admission remain the baseline. No icon-package upgrade or shadow fix.

Setup starts at the work-area top without a repeated task heading. Grayscale
Trash/Additive and Verify sit left, More options right, with advanced choices
below and no divider. Caret/Browse and inset task dismiss buttons are transparent
at rest; the task selection mark is 1.5rem tall (24 CSS px by default). Path fields
remain standard textboxes with an inset trailing caret, including the accented
active underline. The compact caret button is inset on all sides. Textboxes omit
the extra outer ring. Dropdown-option buttons
reset native borders and keep keyboard focus feedback; no custom path-focus state
is retained. Setup ARIA ID references use real attributes, with only their three
literal inert names added to the sink guard. Recent pairs retain stacked paths
and now show each endpoint's own neutral status text and colored dot. Both
endpoints must be online for selection. Empty and ready hints are suppressed;
errors and recovery guidance remain. Keyboard focus remains visible.
Advanced captions immediately follow their toggles; Add filter shares the
textbox row. Disabled caret and Browse controls stay transparent.

The read-only async-small probe_recent_pairs command composes existing recents
and candidate-resolution primitives: at most five exact pair/endpoint identity
rows and ten deduplicated resolutions. No slots, continuations, persistence or
task starts. Setup loads independently; Refresh coalesces without polling, stale
page/list/identity replies are ignored, and unknown/unavailable rows stay disabled.
Selecting or starting still freshly admits roots.

GUI-S2 verification and independent adversarial review passed: ordinary suite
4,979 passed, four skipped; final interfaces 1,524 passed; final installed headed
suite 30 passed; 12 import contracts kept. Logs: gui-s2-ordinary-01.txt,
gui-s2-interfaces-final-02.txt, gui-s2-setup-final-01.txt and
gui-s2-headed-all-03.txt under build/gui-icons/. Final interface/headed runs
cover refinements after the ordinary baseline. Stable root scrollbar space
prevents disclosure-induced sideways movement; exact bounds remain asserted.
Headed fixtures retain real
ledger pairs with one removed source to verify mixed endpoint state and long-path
truncation. Existing typed/picker/mount, frozen/navigation, Plan again, inventory,
batch and reload witnesses remain.
Tests use one slot, fresh external basetemps and PIP_NO_CACHE_DIR=1. Avoid window
interaction during headed tests; logs remain in ignored build/gui-icons/.
Collapsed, expanded and frozen captures were inspected for layout. Their PNGs
retain transparent WebView pixels (dark card white at alpha 13/255); a viewer
that ignores alpha displays white cards, so these are not native Mica color
evidence. Actual control visibility and neutral status colors have computed
browser assertions. Setup-scoped hidden styling prevents component display
rules from exposing inapplicable mode/actions.

GUI-S1 baseline evidence: setup-ordinary-02.txt, setup-headed-all-01.txt and
setup-imports.txt under build/gui-icons/. M1-7 implementation remains outside
this session. The development launcher does not hot reload: relaunch to load
new source after delivery; do not close user-owned windows for testing.

Prior icon commits: 5e83f9a, fe3c11c and b08a05b. TOOLS owns CLI syntax;
DESKTOP_UI owns selective placement. Shadow investigation d6b27ec and BUGS retain
10-bpc WCG SDR findings: broad key shadows over translucent receivers reproduce
the reported halo; opaque receivers and ambient-only shadows appear unaffected.
Exact renderer cause remains unproven, Mica remains required, no fix is implemented.
Ignored build/gui-tuning/halo-10bit/ retains diagnostic artifacts. Display
settings and user-owned windows are outside this task.
