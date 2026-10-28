# Latest session — Navigation context and filter counter, 2026-10-28

Completed the approved P1–P3 GUI batch on milestone1 from b8a2aabb.

## Delivered

- 7ab4b52: pinned Microsoft Go/Follow glyphs, 16px floating insets and square
  compact action controls, preserving ordinary styles and opaque wrappers.
- b185f48b: shared four-row leading context for Go/Follow/move jumps, preserving
  target identity, keyboard focus and refresh viewport.
- The counter commit containing this handoff: matching/total synthetic rows
  beside Filter on both pages. Matching includes folded/offscreen search/filter
  matches and retained structural ancestors. Both counts exclude the hidden
  root. Cached derivation, exact summary validators and consumers are migrated.
  Toolbars respond to actual table width and stack Search when needed.

## Verification

Independent execute-task review approved each atomic outcome.
P1: 2,511 interface/tool passes (three existing skips), focused checks and all
seven installed checks. P2: 2,104 interface passes, focused probes and native
Inventory/default/larger Plan passes.
P3: 6,250 ordinary passes, four existing skips, 12 import contracts. After the
layout correction, 2,105 interface passes; focused layout94, gallery driver29.
Final native-r4.txt: all nine installed checks pass, 70 deselected, 132.52s.
Reviewer inspected raw exits and minimum-window screenshots; literal counts,
Search separation and all five move-specimen rows are verified.

## Evidence and recovery accounting

Evidence remains under build/gui-position-20261028/, build/gui-context-20261028/
and build/gui-filter-count-20261028/. Native roots use matching namisync prefixes
under C:/Users/Spectrum/AppData/Local/Temp/. Final root:
namisync-filtercount28-native-r4.

Failed receipts remain: native P2 expectations assumed first-row navigation;
P3 gallery manual summaries omitted counts and its initial oracle echoed the
bad fixture. Corrected complete fixture population, independent literal counts,
Search nonoverlap and actual-width containment. The resulting wrapped toolbar
required a test-only move specimen height512px to fit five rows; strict
all-rows-visible assertion stayed intact. Foreground refusals sent no input at
the rejected stages. Final user-ready run passes all gates.

Recovery278e0b77 preserved P3 while the user waited. Its reviewed delta was rebuilt
on b185f48b without merging/cherry-picking the WIP. Product/test bytes match the
verified candidate; recovery-only handoff/status prose was replaced. Recovery
branch may be removed after final commit accounting. No worktrees, PR or push.

No pending batch work. Recents, queued-input coordinator, M1-12, release and
DOC-2 remain inactive. No domain effects, selection or persistence changed.
