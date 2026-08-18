# Session Handoff

Status (2026-08-18): the editable GUI launcher supports concurrent grouped
gallery profiles while preserving its concrete per-mode mutexes, and routine
gallery closure now uses one concise profile receipt. The real shell profile
and every diagnostic cleanup safety check remain unchanged. This handoff
records the reviewed delivery and final repository-wide verification sweep.

## Delivered

- Added `tools/gui.ps1` as a PowerShell 7 foreground launcher. Bare invocation
  starts the real editable development shell; `gallery` starts the dark
  component gallery, and `-Mode light|dark|forced|reduced` selects the explicit
  gallery environment. Implicit and explicit dark use the same child, data
  root, mutex, title, and test-owned scenario.
- Added `-Mode fluent` for concurrent light/dark galleries and `-Mode all` for
  concurrent light/dark/forced/reduced galleries. Grouped launch starts every
  selected child before waiting and offers one relaunch/Q prompt after all
  selected windows close.
- Used only `.venv\Scripts\python.exe`, verified that isolated import resolution
  points into this checkout, removed inherited `PYTHON*` behavior controls, and
  restored controlled UTF-8 mode. The launcher does not build a wheel, create
  or clean a venv, fall back to PATH, watch files, or implement hot reload.
- Gave shell and gallery profiles development-only titles, child mutexes,
  launcher-control mutexes, persistent data roots, and logs beneath
  `%LOCALAPPDATA%\NamiSync-Development`. Production launcher behavior and
  identity are unchanged. Gallery locks remain concrete per-mode: different
  modes may coexist, but a second instance of the same mode is refused.
- Started children with `ProcessStartInfo.ArgumentList`, inherited their live
  console streams, and waited on only the returned process objects. `fluent`
  acquires the existing light/dark locks; `all` acquires all four locks in fixed
  order. Neither adds a global gallery lock or touches the shell lock.
- Printed source, interpreter, data, log, gallery scenario, diagnostic output,
  and PID around each launch. Normal closure prints one receipt for the selected
  single or grouped profile; Enter relaunches with a fresh diagnostic directory,
  while Q or unavailable input exits. An abnormal launch names its mode and
  reason, retains the exact diagnostic directory, shows a bounded log tail, and
  labels an unchanged persistent log as old.
- Reused the unchanged `_headed_host_child.py`,
  `_component_gallery_child.py`, and gallery scenario. Editable gallery
  milestones remain diagnostics, not clean-wheel acceptance evidence.
- Bound normal gallery cleanup to a random marker, exact ready/final entry set,
  regular non-reparse files, and unchanged reviewed stats. Routine success hides
  the complete cleanup plan and each removal on PowerShell's `-Verbose` stream;
  partial failure still prints completed paths and remaining root/marker state.
  Any abnormal lifecycle, unknown entry, replacement, stat drift, or cleanup
  error fails closed and retains the remaining output.

## Adversarial Review

- Independent PowerShell, lifecycle, and documentation reviewers challenged
  environment parity, secondary-activation ambiguity, output ownership,
  coercive JSON, prompt failures, stale log attribution, argument quoting, and
  fixed test mutex collisions.
- The final child environment removes every inherited case-insensitive
  `PYTHON*` key before setting `PYTHONUTF8=1`; the same process seam serves the
  editable probe and GUI child.
- Full ready-payload validation was removed from the convenience launcher. It
  validates only the final host-return/exit/post-ready facts needed to decide
  whether a launch was abnormal; the clean-wheel pytest parent remains the
  complete evidence authority.
- Runtime loop tests mock launcher mutex acquisition, while the real contention
  regression uses a bounded GUID-scoped mutex. Tests therefore do not collide
  with an operator's active development GUI.
- A forced mid-cleanup mutation proves truthful partial receipts: the already
  removed path is reported, the changed file is preserved, root/marker state is
  printed, logical exit becomes nonzero, and the relaunch prompt remains.
- Focused presentation regressions prove normal single and grouped launches emit
  one profile receipt without per-mode exit/status chatter, while `-Verbose`
  restores the successful cleanup plan and every exact removal line.
- Grouped-profile review required all per-mode launcher locks and child-mutex
  prechecks before the first child starts. A busy later launcher lock releases
  earlier acquisitions, and a later child start failure still waits for every
  child that did start before reporting and prompting.
- Tests prove all selected `start-*` events precede the first `wait-*` event,
  individual mode locks remain distinct, grouped locks release in reverse
  order, and `fluent` may not create a duplicate dark window while one exists.

## Verification

- Focused launcher suite: `31 passed` in `12.61s`.
- Tools department: `282 passed, 3 skipped, 2270 deselected` in `35.91s`.
  The three skips require unavailable Windows symlink privileges; the launcher
  cleanup still has ownership, unknown-entry, and injected stat-drift coverage,
  while its source guard explicitly refuses reparse entries.
- Ordinary repository suite: `2514 passed, 14 skipped, 27 deselected` in
  `133.70s`.
- Import boundary lint: `11 kept, 0 broken` across 71 files and 253
  dependencies.
- PowerShell parsing, `git diff --check`, and the clean-wheel child/scenario
  diff check are clean. No production package, headed acceptance child,
  gallery scenario, or clean-wheel test changed.

## Remaining Work

- No automated headed smoke opened the new convenience launcher during this
  closeout, because it intentionally waits for the operator to close the real
  window. The existing headed acceptance paths remain unchanged; the next
  ordinary UI-tinkering invocation is the direct manual smoke.
- A directly launched same-profile child can still win the narrow interval
  between the wrapper's child-mutex precheck and child admission. Gallery mode
  reports missing/failure diagnostics; shell mode inherits the host's
  secondary-activation-and-return behavior. Concurrent wrappers are serialized
  only when their concrete mode sets overlap; unrelated modes remain concurrent.
- Normal gallery diagnostics are removed only after exact validation. Abnormal
  or suspicious directories and persistent data/log roots are intentionally
  retained at the printed locations for operator inspection; there is no broad
  automatic cleanup command.
- The launcher deliberately depends on private test-owned child compositions
  for development convenience. If those child arguments or final milestone
  contract change, update `tools/gui.ps1`, its focused tests, and `TOOLS.md`
  together. This does not make the launcher or its output release evidence.
