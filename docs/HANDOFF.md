# Session Handoff

Status (2026-08-18): the editable GUI development launcher is implemented,
reviewed, documented, and committed in `bd21b38`. This handoff records the
final repository-wide verification sweep.

## Delivered

- Added `tools/gui.ps1` as a PowerShell 7 foreground launcher. Bare invocation
  starts the real editable development shell; `gallery` starts the dark
  component gallery, and `-Mode light|dark|forced|reduced` selects the explicit
  gallery environment. Implicit and explicit dark use the same child, data
  root, mutex, title, and test-owned scenario.
- Used only `.venv\Scripts\python.exe`, verified that isolated import resolution
  points into this checkout, removed inherited `PYTHON*` behavior controls, and
  restored controlled UTF-8 mode. The launcher does not build a wheel, create
  or clean a venv, fall back to PATH, watch files, or implement hot reload.
- Gave shell and gallery profiles development-only titles, child mutexes,
  launcher-control mutexes, persistent data roots, and logs beneath
  `%LOCALAPPDATA%\NamiSync-Development`. Production launcher behavior and
  identity are unchanged.
- Started children with `ProcessStartInfo.ArgumentList`, inherited their live
  console streams, and waited on only the returned process object. Existing
  same-profile launcher or child ownership is refused at the pre-launch check;
  there is no process-name enumeration or termination.
- Printed source, interpreter, data, log, gallery scenario, diagnostic output,
  PID, exit, and status around each launch. Enter relaunches with a fresh
  diagnostic directory; Q or unavailable input exits. An abnormal launch shows
  a bounded log tail and labels an unchanged persistent log as old.
- Reused the unchanged `_headed_host_child.py`,
  `_component_gallery_child.py`, and gallery scenario. Editable gallery
  milestones remain diagnostics, not clean-wheel acceptance evidence.
- Bound normal gallery cleanup to a random marker, exact ready/final entry set,
  regular non-reparse files, and unchanged reviewed stats. The launcher prints
  the complete plan, each successful removal, and completed/root/marker state
  after a partial failure. Any abnormal lifecycle, unknown entry, replacement,
  stat drift, or cleanup error fails closed and retains the remaining output.

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

## Verification

- Focused launcher suite: `23 passed` in `8.73s`.
- Tools department: `274 passed, 3 skipped, 2270 deselected` in `32.25s`.
  The three skips require unavailable Windows symlink privileges; the launcher
  cleanup still has ownership, unknown-entry, and injected stat-drift coverage,
  while its source guard explicitly refuses reparse entries.
- Ordinary repository suite: `2506 passed, 14 skipped, 27 deselected` in
  `133.20s`.
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
  secondary-activation-and-return behavior. Concurrent wrapper launches are
  serialized by the separate launcher mutex.
- Normal gallery diagnostics are removed only after exact validation. Abnormal
  or suspicious directories and persistent data/log roots are intentionally
  retained at the printed locations for operator inspection; there is no broad
  automatic cleanup command.
- The launcher deliberately depends on private test-owned child compositions
  for development convenience. If those child arguments or final milestone
  contract change, update `tools/gui.ps1`, its focused tests, and `TOOLS.md`
  together. This does not make the launcher or its output release evidence.
