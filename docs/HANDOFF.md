# NamiSync Session Handoff

Date: 2026-08-13
Branch: `milestone1`

## Session Outcome

Stage 6 is implemented through Slice 4. The installed WebView2 host, exact
three-command transport, GUI Break 1 design foundation, and now the shared
presentation core and honest accessible shell frame are complete. Slice 5's
real sync/plan surface is next.

This is not a claim that the product desktop is complete. The shell currently
shows labelled, keyboard-focusable task navigation and work regions with
truthful empty guidance. It has no real task card, plan row, inventory row,
history view, selection or execution control, or additional bridge command.
Slices 5-7, GUI Break 2, packaging, the as-built pass, and the broader M1/beta
claims remain open. SH-G-11, SH-G-12, and SH-G-13 also retain their remaining
production-surface clauses through Slice 6.

## Slice 4 Delivery

- `interfaces/web/visible_sequence.py` defines the frozen generic node,
  parameter, sequence, window, and anchor values. Its pure functions validate
  one workflow-owned pre-order array and own literal case-folded display
  search, sparse caller-decided match counts, match retention before collapse,
  exact 1..256 windows, and deepest-visible ancestor resolution. It imports no
  domain policy, parses no path, and retains no projection or parameter cache.
- Installed `tree.js` consumes only `{offset,total,rows}` with the exact generic
  row fields. It owns a fixed 28-CSS-pixel accessible tree, exactly two virtual
  spacers, inert full-display labels, and one monotonic generation whose stale
  commits are rejected before their payload is read. The Python window boundary
  keeps the production DOM at no more than 256 data rows plus those spacers.
- Installed `rail.js` and `panels.js` create only focusable labelled task
  navigation and work regions with honest empty text. `app.js` appends those
  regions beneath the existing header/status element; responsive card geometry
  stacks without fixed-height clipping.
- Production remains exactly `pick_folder`, `start_plan`, and `next_events`.
  Slice 4 creates no task, session, plan, inventory, history item, domain
  filter, or bridge registration.

## Commit Record

- `c5ae370` froze the Slice 4 structural, search, filter, window, anchor,
  renderer, empty-shell, and installed-wheel SH-G-7 contract before code.
- `0f29299` added the pure visible-sequence implementation and focused contract
  coverage.
- `3a687ea` added the fixed-height bounded accessible tree renderer and package
  asset evidence.
- `6204f40` added the responsive accessible task/work shell frame with honest
  empty states and no synthetic domain state.
- `331e28d` added the installed-wheel SH-G-7 harness under
  `tests/interfaces/web/`, including the renderer-level shell Tab, native zoom,
  forced-colors, hostile-text, row-bound, and stale-generation scenario.

## SH-G-7 Evidence Boundary

- One clean installed wheel supplies the production host, page, CSP, security
  hooks, bridge, appearance handling, and exact frontend assets. Asset hashes
  and sizes are matched back to the wheel; the source tree is not substituted.
- The headed scenario uses renderer-level Tab events rather than OS keystrokes,
  sets the real WebView2 control's zoom factor to 200%, and emulates forced
  colors. It proves focus order and visibility, positive stacked card geometry
  within the horizontal viewport, no horizontal overflow, and a visible
  system-color focus cue.
- The scenario imports the installed `tree.js` and `render.js`, renders hostile
  and long Unicode labels through the production text path, measures every row
  at exactly 28 CSS pixels, and observes exactly 256 data rows plus two fixed
  spacers at the bound.
- A newer 256-row generation is committed and fingerprinted before an older
  unreadable stale payload is delivered. The stale commit returns false,
  performs no payload read, and leaves the newer DOM unchanged.
- No gate calls `SetForegroundWindow`, sends OS keys, or otherwise forces
  foreground. The child has one 75-second whole-scenario deadline and a
  kill-on-close Job Object; a normal NamiSync window may appear during the run.

## Final Verification

- Full ordinary repository suite: `2027 passed, 2 skipped, 22 deselected` in
  105.49 seconds.
- Focused Slice 4 ownership set: `141 passed, 1 deselected` in 8.83 seconds.
- New SH-G-7 harness ordinary checks: `2 passed, 1 deselected`.
- Named BR-G-34/SH-G-7 discovery: 49 collected nodes; ordinary named run:
  `48 passed, 33 deselected` in 2.64 seconds.
- Clean-installed-wheel headed SH-G-7: `1 passed, 2 deselected` in 14.32
  seconds with cleared project `addopts`.
- Final `lint-imports` shim and direct-module attempts could not start because
  Windows intermittently returned `Access is denied` before process creation,
  so this checkpoint has no new import-contract result. The only new production
  Python module, `visible_sequence.py`, imports the standard library only; the
  independent adversary classified the launcher failure as environmental and
  nonblocking.
- Independent adversarial review of the shell and headed gate returned ACCEPT
  with no P1/P2 finding.

## Immediate Next-Session Context

1. Start Slice 5 from `M1_SHELL.md` with its docs-first contract and real plan
   surface. Do not treat the empty Slice 4 frame as a partial product plan UI.
2. Reuse `visible_sequence.py` for structural/search/filter/window/anchor
   mechanics and feed `tree.js` only server-decided generic windows. Do not add
   a plan-specific flatten implementation or move domain policy into the
   renderer.
3. The production command table remains the exact three Slice 3 rows until a
   Slice 5 contract and tests add the first real plan-surface command. Do not
   add placeholders or dormant registrations.
4. Surface CSS must consume semantic/component contracts, never raw colors or
   palette primitives. Any proposed new hardcoded or derived color requires
   prior product-author discussion and a same-change contract, token, contrast,
   and ownership-evidence update.
5. Keep icons in the frozen source-owned local registry and `currentColor`
   path. Add a glyph only for a real Slice 5 control, with provenance, package
   manifest, CSS registry, and tests in the same reviewed change.
6. Warn before every headed run and retain installed-wheel, unique-identity,
   physical-local-root, Job Object, bounded-deadline, and no-foreground-forcing
   discipline.
7. Keep the retained executor settlement oracle unchanged. Stage 6
   presentation work does not authorize baseline regeneration or executor,
   verifier, database, workflow-policy, or history-policy changes.
