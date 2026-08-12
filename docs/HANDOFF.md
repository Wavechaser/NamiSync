# NamiSync Session Handoff

Date: 2026-08-12
Branch: `milestone1`

## Session Outcome

Stage 6 is implemented through Slice 3 and GUI Break 1. The installed WebView2
host, strict three-command transport, opaque server-side path slots,
transactional task observation, bounded event drain, and browser recovery
manager are complete. GUI Break 1 now supplies the shared token, component,
motion, fixed local Fluent icon, and native Windows appearance foundation that
the production surfaces will consume.

This is not a claim that the desktop product views exist. Slice 4 is next.
SH-G-11, SH-G-12, and SH-G-13 retain their production-tree/renderer clauses
through Slices 4-6; GUI Break 1 closes their foundation evidence only. SH-G-14's
fixed icon-infrastructure boundary is complete, while actual surface glyph
choices remain ordinary later-slice work.

The authored palette remains exactly the 13 requested GUI Break 1 inputs, using
`main`, `dark`, and available `light` names. Yellow and purple have no authored
`light` input. This is not a permanent ban on color growth: a future hardcoded
or derived value requires prior product-author discussion and a same-change
contract, token, and evidence update.

## Commit Record

- `98d25d3` closed the installed, secured Slice 1 host gates.
- `15d8117` through `da5232f` defined and implemented Slice 2's strict bridge,
  slots, native picker, plan admission, and real headed transport evidence.
- `973ac01` through `79ed251` defined, implemented, reviewed, and documented
  Slice 3's transactional observation, bounded task drain, recovery manager,
  and SH-G-8/BR-G-33 evidence.
- `e4c9e9f` defined the closed Fluent icon foundation contract.
- `bf22e67` added the design tokens, semantic components, motion rules, fixed
  four-glyph registry, pinned local SVGs, provenance, and ordinary evidence.
- `ce601fc` added Windows theme/accent observation and progressive native Mica
  with system-color opaque fallback.
- `b1f36eb` moved inert DOM appearance publication off the native UI thread to
  avoid pywebview's synchronous return deadlock while retaining UI-thread-only
  native mutation.
- `29e04a2` closed GUI Break 1 with the installed-wheel component gallery,
  real-stack material/fallback gates, forced-colors interaction hardening,
  pre-material fallback correction, refreshed active documentation, and the
  independent final review.

## GUI Break 1 Evidence Boundary

- The clean-wheel gallery loads the installed production `index.html`,
  `tokens.css`, `components.css`, `icons.js`, and fixed local icon files. It
  proves exact installed bytes, light/dark/forced-colors/reduced-motion modes,
  semantic aliases, non-color cues, control states, contrast, currentColor
  icons, and test-gallery exclusion from package data.
- The real material gate preserves the production host, security, dispatcher,
  and appearance lifecycle. On the capable Windows 11 stack it records actual
  DWM backdrop/dark-mode readback, transparent WebView/controller and document
  seams, an opaque content card, and unchanged frame/dispatch health. Separate
  injected controller and MAINWINDOW failures prove complete opaque rollback.
- The CDP screenshot is renderer-layer alpha evidence, not a compositor capture
  of Mica. The material claim rests on the native DWM/controller/form readbacks
  plus transparent page seams; documentation must keep that distinction.
- Pre-22621 builds skip the attr-38 headed scenarios before launch. Ordinary
  evidence proves those builds never require unsupported backdrop reset and
  still land the Windows `COLOR_WINDOW` form/controller fallback.
- No gate calls `SetForegroundWindow`, sends keys, or otherwise forces
  foreground. The headed runs may naturally show normal application windows;
  each child is isolated under a kill-on-close Job Object and hard deadline.

## Final Verification

- Full ordinary suite: `1976 passed, 2 skipped, 21 deselected`.
- Ordinary web adapter suite: `364 passed, 21 deselected`.
- GUI-foundation documentation/contract suite: `72 passed, 6 deselected`.
- Refreshed clean-wheel component gallery: `3 passed, 6 deselected`.
- Refreshed real-stack native materials: `3 passed, 7 deselected`.
- Focused material/host/logging verification after prebuild hardening:
  `102 passed, 3 deselected`.
- `git diff --check` passed.
- Independent adversarial review returned ACCEPT with no remaining P1/P2
  blocker across product code, both headed harnesses, package evidence, and
  active documentation.
- The final import-linter retry could not start because Windows intermittently
  returned Access Denied for the virtual-environment launcher. The latest
  successful run before the test/document-only gate work was `11 kept,
  0 broken`; the final full Python suite passed and the checkpoint introduced no
  package import edge beyond the already-linted appearance module.

## Immediate Next-Session Context

1. Start Slice 4 from `M1_SHELL.md`: implement the pure presentation core and
   shell frame against the existing tokens/components/icon boundary. Do not
   reopen transport commands, native asset authority, or the GUI Break palette.
2. Surface renderers must consume semantic/component contracts, never palette
   names or raw colors. Any proposed new hardcoded or derived color must be
   discussed with the product author before code and must update contract,
   tokens, gallery, contrast, and no-raw-color evidence together.
3. Keep icons in the frozen source-owned registry with local inert assets and
   `currentColor`. Add actual glyph mappings only when a Slice 4-7 surface owns
   them; do not add runtime registration, remote assets, dynamic SVG, or
   data-derived paths.
4. Preserve the host order: security registration, appearance registration,
   load; and on close, appearance stop before observation/service/window
   teardown. Native DWM/WebView mutation remains on the WinForms UI thread;
   inert DOM appearance publication remains revisioned and off that thread.
5. Reuse the installed-wheel headed helpers, unique test identities,
   absolute-physical-local roots, Job Objects, and one whole-scenario deadline.
   Warn before every headed run; never add foreground-forcing APIs.
6. Keep the retained executor settlement oracle unchanged. Stage 6
   presentation work does not authorize baseline regeneration or executor,
   verifier, database, or workflow-policy changes.
