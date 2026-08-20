# Session Handoff

Status (2026-08-20): the pre-Slice-5 sync and integrity file-list visual
foundation is implemented and remains dormant in production. Only the
test-owned installed-wheel gallery supplies projected specimens. Real
projection, transport, selection/tree policy, and execution remain Slice 5+
work.

## Delivered

- Added shared packaged `file_row.js` presentation structure and kept
  `plan.js` and `integrity.js` as separate narrow, display-ready row renderers.
  None imports the bridge or domain code, and production imports none of them.
- Standardized both lists on six columns and compact geometry: 28 px rows,
  16 px native checkboxes, selection/filename/size first, and notes last. Sync
  uses operation/checksum middle columns; integrity uses presence/integrity.
- Added projected folder disclosure, mixed checkbox state, depth indentation,
  and basename-only child labels. Gallery folders each have two children and
  the test-owned driver proves computed collapse/restore and reconciles mixed,
  fully selected, and unselected direct-child states without defining product
  recursive hierarchy semantics.
- Added focusable separator handles to all six gallery headers. Pointer drag
  and Left/Right arrows resize the shared grid tracks for the current DOM only;
  no persistence, cosmetic state, or bridge contract was added.
- Changed light-theme sync operation text from dark-family variants to exact
  authored main swatches. Added dedicated file-status aliases so integrity
  presence/integrity text likewise uses green, yellow, purple, red, or blue
  main swatches in both ordinary themes. Forced colors still use `CanvasText`.
- Extended the static gallery with representative integrity rows while keeping
  all fixtures under `tests/assets/component_gallery/` and outside the wheel.

## Adversarial Review

- Kept the row-view inputs page-local and already projected: renderers do not
  split paths, aggregate file sizes, truncate hashes, infer status families,
  reconstruct trees, or dispatch commands.
- Confirmed `app.js` and `panels.js` remain unchanged and import neither list,
  so the production GUI still has no Slice 5 content.
- Verified folders render their full visual context once, while child rows show
  only `DSC_1000.jpeg`/`DSC_1001.jpeg` or the integrity fixture basenames with
  greater indentation.
- Fixed a headed-evidence false positive: the grid display rule had overridden
  the browser's default `[hidden]` behavior. An explicit hidden-row rule now
  collapses computed layout, and evidence checks computed display rather than
  only the DOM property.
- Verified both folder checkboxes are genuinely indeterminate with
  `aria-checked="mixed"`; selecting the second child selects the parent, and
  clearing it restores the mixed parent state. Disclosures return to expanded
  state after the test, cells remain transparent, zebra backgrounds stop at
  the final row, and the
  aligned grid scrolls rather than collapsing when constrained.
- Verified a synthetic 40 px pointer drag changes the corresponding rendered
  filename track by 40 px in both sync and integrity specimens, then resets the
  fixture before remaining measurements.
- Documented the main-first palette rule: light/dark tones support or
  contextualize the main and may replace it only as an explicit designed
  exception. The light main-colored list labels are an explicit measured
  contrast exception whose visible words preserve non-color meaning; Windows
  forced colors remain authoritative.

## Verification

- Focused ordinary token, frontend, and component-gallery contracts: `64
  passed, 7 skipped, 4 deselected` in `3.03s`.
- Neighborhood installed-wheel component-gallery headed tests: `4 passed, 15
  deselected` in `31.77s`, covering light, dark, forced-color, and
  reduced-motion profiles.
- Per user scope, no department or full repository suite was run.

## Remaining Work

- Slice 5+ must own validated Python projections, bridge commands, real list
  scaffolding/controllers, selection propagation, hierarchy updates, and live
  workflow state. The page-local row views are not wire contracts.
- Product list ownership must decide keyboard tree/table interaction and zebra
  parity across dynamically hidden or virtualized descendants; this visual
  checkpoint intentionally does not invent those semantics.
- The in-app Browser had no open user tab to claim for an additional manual
  inspection. The native installed-wheel WebView2 gallery remained the
  rendered verification authority.
