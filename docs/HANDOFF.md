# NamiSync Session Handoff

Date: 2026-07-27

## Session Outcome

Simplified the scanner ignore contract without changing its active behavior.

- `IgnoreSet` remains the workflow-supplied scan policy and continues to exclude
  `desktop.ini`, `Thumbs.db`, `.synctrash`, and exact NamiSync temporary names.
- `ScanResult` carries observable records, warnings, scope, and completeness;
  ignored entries remain absent from scan records by design.
- Live database placement guards remain responsible for keeping the ledger,
  history database, and settings outside managed roots.

## Verification

- Focused scanner, planner, preflight, inventory, recorder, and verifier tests
  pass.
- The full pytest suite and import-boundary checks pass.
- Repository search finds no removed owned-path or scan-snapshot contract names.
- `git diff --check` passes.

## Immediate Next Context

The scanner still accepts one immutable `IgnoreSet` for full and selected scans.
If the UI later needs to show what was actually ignored, add explicit encountered
ignore evidence rather than duplicating the supplied policy on the scan result.
