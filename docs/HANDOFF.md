# NamiSync Session Handoff

Date: 2026-08-03
Branch: `milestone1`

## Session Outcome

Strengthened the completed audit-parity and missing-WebView2 fixes after
adversarial review.

- Centralized the default SQLite writer retry bound at ten seconds. Production
  history construction uses that bound explicitly; the audit ownership cutoff
  is derived as eleven seconds, and the service-close allowance is derived as
  twenty-two seconds so a late pump claim can consume both sequential bounds
  plus margin. Regression tests pin the formulas and the composition values.
- Replaced the second local WebView2 registry implementation with one
  side-effect-free compatibility module used by host preparation. It mirrors
  pinned pywebview 6.2.1's .NET prerequisite, stable/beta/dev/canary client
  keys, HKCU/HKLM architecture routing (including x86's plain HKLM path), fixed
  runtime short circuit, and actual version-helper behavior.
- Added executable parity tests that extract and run only pywebview's pinned
  detector functions with a fake registry. Importing the WinForms backend
  itself is intentionally avoided because that import is the side-effectful
  renderer-selection trip wire this preflight must precede.
- Documented why `86.0.622.0` is retained: it is the exact argument used by the
  pinned backend's compatibility helper, not a NamiSync security-patch
  freshness threshold. The initialized renderer check remains defense in
  depth against a preflight false positive.
- Updated `BUGS.md`, architecture, dispatcher/history, interface/desktop,
  bridge/plan, feature, and README descriptions to match the hardened behavior.

## Verification

- Focused dispatcher/history/service/WebView2 regression suite: `136 passed in
  3.47s`.
- Full repository: `864 passed in 31.16s`.
- Import boundaries: 50 files / 183 dependencies; all eight contracts kept,
  zero broken.
- Package health: `pip check` reported no broken requirements.
- `git diff --check` was clean apart from expected LF-to-CRLF notices.

## Immediate Next Context

The open substantive bug in `BUGS.md` remains executor pause after a durable
retry sub-step. The proposed M1 design is to latch pause while an UPDATE or
MOVE_UPDATE continuation owns durable backup/temp state, finish that operation,
then raise `PauseRequested` at the settled boundary. No executor code was
changed in this session; discussion should resume before implementation.

Also complete the requested read-only audit of cancellation in the same durable
window: confirm whether settling the operation canceled leaves its run-scoped
backup orphaned and whether any existing cleanup reclaims it. If not, log that
as a separate sibling defect rather than folding it into the pause fix.

For the fixes delivered here, preserve these invariants:

1. The production audit cutoff is strictly longer than the history writer's
   retry bound, and default service shutdown covers both bounds in sequence.
2. The finalization latch is claimed before history builds the payload hash, so
   live and retained audit axes cannot disagree.
3. WebView2 absence is decided before `create_window`/`webview.start` by the
   shared read-only detector, while renderer verification still runs first in
   the synchronous initialized callback.
4. Changes to the pinned pywebview detector must fail the executable parity
   tests and trigger a host security re-audit.
