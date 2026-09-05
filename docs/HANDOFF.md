# Session Handoff

Status (2026-09-05): TS-R0 through TS-R2 are complete; TS-R3 is active.
The user authorized continuation through TS-R5 followed by a recap before TS-R6.

## Outcome and verification

- TS-R2 reduces 18 redundant rows; no production changes. Distinct scanner,
  planner, preflight, selection, inventory, and persistence boundaries remain.
- Focused old/new: 417/399 passed. Neighborhood: 2,222 passed, one established
  skip. Ordinary: 4,625 passed, four established skips, 28 headed deselected.
- All 12 import contracts pass. Independent adversarial review is clear after
  explicitly observing the retained history validator route.
- Six isolated witness groups are recorded under `probes/TS-R2/`; controls and
  allowed builder variation pass, and old/new detectors reject named defects.
- Current collection: 4,657. Original population remains 4,964; TS-R0/R1
  provenance, ten mandatory repair rows, oracle and SH-G-8 remain unchanged.

## Immediate context

- Next: TS-R3 normal service construction, cleanup retry and adapter replay.
  Independent no-history reviewers have inspected TS-R3, TS-R4, and TS-R5.
- Ignored evidence and prepared edit tooling live under
  `build/test-simplification/536915fb28068c141f59b2243119530205538b4d/`.
  The prepared `scripts/r3-edit.py` has not yet been applied.
- Sandboxed PowerShell and apply_patch fail before accessing files with
  `helper_unknown_error: setup refresh had errors`. Explicit PowerShell 7,
  login disabled and reviewed unsandboxed execution works. Do not switch shells.
- Keep the original settlement oracle; do not start TS-R6 in this session.
