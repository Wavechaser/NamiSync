# Session Handoff

Status (2026-08-22): the dormant plan and integrity row renderers now expose a
test-only visual model for per-item progress without binding the production
shell to Slice 5 data. Operation-chip interaction and compact row-label geometry
are aligned with the current Fluent-derived control behavior. The focused and
installed-wheel component-gallery gates pass.

## Delivered

- Added a narrow `progressPercent` presentation value for projected
  `executing` and `verifying` rows. It must be finite and between 0 and 100;
  every other row rejects it.
- Replaced visible Copying/Verifying row text with a 4 logical px mini progress
  bar that spans the full Operation/Presence cell. Supplied text remains the
  accessible progressbar label, and Completed remains ordinary visible text.
- Kept the new visual boundary deliberately downstream of the v4 transport.
  The renderer does not read `item_bytes_done`/`item_bytes_total`, calculate a
  ratio, match item identity, import bridge code, or activate production rows.
  Slice 5 still owns validated projection, row matching, and live binding.
- Changed active operation filters from opaque main plus lift/scale to family
  main at rest and the same RGB at 90%/80% strength for hover/press. No chip
  state now translates or scales; the selected label remains stable.
- Changed compact filled row labels to the checkbox's 4 px radius. A 2 px
  leading fill bleed paired with 2 px leading label padding aligns badge text
  with unfilled text without adding content characters.
- Advanced the exact component-gallery evidence schema to v5. It records and
  validates the inline bar's accessible value, 4 px height, full-cell width,
  track/fill distinction, system-accent fill, and forced-color Canvas/Highlight
  authority. Chip evidence independently proves main/90%/80% RGB and no motion
  transform.
- Updated `DESKTOP_UI.md`, `FEATURES.md`, `M1_SHELL.md`, and the active
  changelog tasks. Production file lists remain empty and no persistence,
  bridge state, or production row payload was added.

## Verification

- Focused ordinary interface checks:
  `65 passed, 7 skipped, 4 deselected`.
- Installed-wheel WebView2 component-gallery neighborhood:
  `4 passed, 15 deselected` across Light, Dark, forced colors, and reduced
  motion.
- Bundled Node syntax checks passed for `file_row.js`, `plan.js`,
  `integrity.js`, and the test-only gallery driver.
- `git diff --check` passes apart from expected Windows line-ending notices.

## Immediate Next Context

- Slice 5 may project an active row by the browser reducer's
  `item_type`/`item_id` identity and provide a display-ready percentage when the
  attempt byte pair exists. `current_path` remains informational and must not
  identify activity.
- Active pre-stream or otherwise non-determinate item presentation remains a
  later projection decision; this checkpoint intentionally models only the
  requested determinate mini bar and does not invent a null/indeterminate row
  contract.
- Column behavior remains gallery-only and is the next expected cosmetic area;
  do not turn its DOM widths into persistence or a production layout protocol.
