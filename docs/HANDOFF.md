# NamiSync Session Handoff

Date: 2026-08-06
Branch: `milestone1`

## Session Outcome

Hardened and flattened the development-only executor/verifier harness introduced
in `134f235`.

- Moved the package from `tools/rig/` to `tools/`; the entry point is now
  `python -m tools`, and the focused guide is `docs/TOOLS.md`.
- Bound destructive corpus operations to a live directory-identity claim with
  a signed exclusive lease. Nonempty unowned roots, stale or malformed
  authority, directory replacement/reparse aliases, overlapping roots, and
  unrecognized lease artifacts are refused. Generation now replaces the owned
  corpus deterministically.
- Enforced output isolation before writes. Reports and sidecars stay outside
  measured/materialized roots, cannot collide with ownership artifacts or each
  other, and cannot reuse an existing multi-link file.
- Made sidecar writes atomic and reads schema-strict, including exact fields,
  duplicate-member refusal, supported algorithms, bound-identity completeness,
  and fresh whole-corpus validation.
- Rejects incomplete scans, safety-excluded executor plans, inconsistent
  terminal/result/evidence state, partial verifier priming, mixed integrity
  outcomes, and incomplete item or byte coverage before reporting a sample.
  Synthetic verifier mismatches remain an intentional accepted measurement.
- Executor diagnostics are on by default only in the tools. `--no-metrics`
  disables both production-backend diagnostics and the per-copy timing wrapper;
  `namisync/modules/executor.py` was not changed.
- Executor reports disclose empty correspondence and therefore represent
  first-run/no-history plans without MOVE or MOVE_UPDATE. Optional readback is
  always visible and must exactly verify all published candidates.

## Verification

- Complete pytest suite: `1091 passed, 1 skipped in 40.87s`. The skip is the
  optional real directory-symlink substitution test on a host without symlink
  privilege; the same guard also has a deterministic non-skipped test.
- Focused tools plus production executor/planner/preflight/verifier regression
  suite: `422 passed, 1 skipped in 10.51s`.
- Final tools-only suite after bounded marker/lease reads: `96 passed, 1
  skipped in 1.33s`.
- Import linter: `8 kept, 0 broken`.
- Real CLI smoke: generated a three-file corpus, completed two primed verifier
  passes with three `VERIFIED` results each, executed four successful operations
  with diagnostics enabled, verified all three readback candidates, and removed
  both owned workspaces.

## Immediate Next Context

- No logger integration was added. `docs/M1_SHELL.md` places future logging in
  the GUI host under `interfaces/web`, with GUI paths and pywebview sequencing;
  importing it into measurement tools would invert the boundary and perturb
  timings.
- Keep `python -m tools` separate from the shipped `nami-sync` CLI. If the rig
  later needs distribution, add a distinct development entry point only after
  an explicit packaging and destructive-workspace safety review.
- A future MOVE/MOVE_UPDATE benchmark needs an explicit retained-correspondence
  input. Do not synthesize mapping state and present it as production history.
