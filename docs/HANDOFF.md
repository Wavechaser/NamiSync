# Latest session handoff

## Compact Setup tables and scrollbars (2026-09-13)

Delivered on milestone1 from 46da897, with user-authorized implementation,
independent review and commits:

- GUI-S6, 28eafcd: conditional origin-owned batch table retains settled results
  until cleared. Paths, attempted settings, truthful short status and queued
  dismissal share five 56px slots under 28px headers with recent pairs.
  Add pair precedes Create plan at the right; single Create remains visible but
  disabled during batching. Create batch is right-aligned under the table.
  Matched folder/header insets, fixed horizontal overflow, removed the visible
  Actions heading and routine Setup/Ready guidance.
- GUI-R1, 65bd02a: native closing/retry text explicitly reveals the status label
  after Ready hides it. Legacy installed-host tests expose their test-only
  marker while still waiting for literal post-handshake Ready. Readiness,
  shutdown, failure ordering and process ownership are unchanged.
- GUI-S7, 5897d2f: CSS styles eight existing native scroll owners with a fixed
  10px gutter, 2px pane-hover thumb and 6px direct-hover/drag thumb. Rounded
  neutral paint is unchanged when pressed. Native input and forced-color
  defaults remain; true overlay painting, fading and input-mode parity are
  not promised.
- GUI-S8: adds an 8px token-based gap above the batch footer, preserving table
  geometry and action alignment. Installed Setup and final interface checks
  passed; independent review closed the outcome.

The existing 48-entry bound, one serial runner, origin ownership, membership
rechecks, fresh admission and exact uncertain retry remain intact. Clearing
receipts never closes created tasks or drops unresolved requests. No vendor,
dependency, host-flag or Mica changes were made; WCG shadow diagnosis stays open.

Verification evidence is in ignored build/gui-icons/:

- gui-s6-ordinary-01.txt: 4,979 passed, four existing skips.
- gui-s6-imports-01.txt: all 12 import contracts kept.
- gui-r1-focused-01.txt: 118 host/harness checks passed.
- gui-r1-interfaces-01.txt: 1,526 interface tests passed.
- gui-r1-headed-01.txt: all 30 installed interface scenarios passed, including
  gallery, Setup, native scrollbar pointer/geometry and legacy readiness checks.
- gui-s8-interfaces-01.txt: final interface run passed all 1,526 tests.
- gui-s8-headed-01.txt: both installed Setup scenarios passed with measured
  8px footer spacing and retained table/action assertions.

All completed outcomes received independent adversarial review. An earlier
single dark-gallery measurement failed and did not reproduce; no workaround
was added. Ready fixture consumers were migrated without retiring readiness
assertions. DPI-quantized scrollbar borders are compared against the actual
idle border; static checks retain exact authored 2px/4px border expectations.

No task-created worktree or branch needs cleanup. Root owns one pytest/Node
slot. Test outputs use unique external basetemps and PIP_NO_CACHE_DIR=1. Do not
close user-owned windows; relaunch the development app to load the changes.
