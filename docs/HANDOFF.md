# NamiSync Session Handoff

Date: 2026-08-04
Branch: `milestone1`

## Session Outcome

Stage 6 now has one consolidated implementation and packaging plan:
`M1_SHELL.md`.

- A pre-shell Phase 0 owns the single `0.1.0` runtime version source,
  injectable local-data paths, rotating file logging installed before
  pywebview import, exact pythonnet and Bottle declarations, and project
  license metadata. It creates no window.
- Slices 1-7 deliver the production host, strict bridge transport, reusable
  headed harness, bounded drain, shared virtual presentation core, sync,
  inventory/integrity, and lifecycle/history surfaces.
- PyInstaller, the resolved build environment, CI, third-party notices and GPL
  source directions, as-built documentation, and release evidence are deferred
  together to Slice 8, after a running vertical shell exists.
- Console entry points remain CLI-only and point no-subcommand users to the
  GUI-subsystem `nami-sync-gui` launcher. Both route lazily through
  `interfaces.launcher`; there is still one GUI implementation.
- The plan records the plain-ES-module asset layout, deterministic WebView2
  storage, fixed 28-pixel virtual rows, single JavaScript bridge wrapper,
  child-process headed harness, shutdown order, and best-effort single-instance
  activation.

`DESKTOP_UI.md` now reflects those packaging/host decisions. Narrow consistency
edits remove the superseded no-subcommand desktop-launch claim from active
architecture, feature, CLI, interface, M1 plan, and BR-G-31 text. `M1_BRIDGE.md`
remains authoritative for bridge semantics and gates; its release command now
explicitly clears the default headed-test exclusion.

## Verification

- Documentation-only change; no product code or dependency declaration changed.
- `git diff --check` is clean.
- Active-document searches find no remaining claim that bare `nami-sync` opens
  the desktop.

## Immediate Next Context

Implement `M1_SHELL.md` Phase 0 before creating the product window. Keep the
product version at `0.1.0`. Phase 0 ends after version/path/logging/dependency/
license declarations and focused tests; it does not pull forward assets,
launchers, PyInstaller, CI, or the dependency lock.

Slice 1 then renames `security_spike.py` to `bridge.py` and lands the smallest
installed-wheel shell through the documented startup and shutdown state
machines. Treat `M1_BRIDGE.md` BR-G gates as acceptance criteria, not optional
follow-up hardening.
