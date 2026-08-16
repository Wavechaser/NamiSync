# Session Handoff

Status (2026-08-16): the repository now has a documented five-level test run
policy and an executable primary-ownership selector. Exact module membership
lives only in `tests/_departments.py`; `docs/TESTS.md` explains how to choose
focused, department, cross-department, ordinary, and complete/headed runs.

## Delivered

- Added repeatable `--dept` with equivalent `--department`, union selection,
  clear unknown-department errors, and fail-closed validation that every pytest
  module has exactly one primary owner. Both pytest default module naming forms
  are covered.
- Added a repository guard against imports between collected test modules and
  moved the existing shared web, inventory-runtime, and database helpers into
  non-collected underscore-prefixed support modules.
- Made the ordinary installed-wheel fixture use a pip-less venv installed by
  the parent pip while retaining target-prefix, package-resource, and pip-
  absence evidence. The headed installed-wheel fixture remains unchanged.
- Cached only successful directory-junction capability probes by source/target
  device pair. Every behavioral test still creates its own actual junction;
  failed probes remain uncached.
- Sized the native verifier witness to exactly one 4 MiB chunk plus a tail and
  the rollover mechanism fixture to a test-only threshold while preserving
  independent production-configuration assertions.
- Made gallery modes and transport scenarios lazy for focused headed reruns.
  Complete headed selection still requests all four gallery modes and both
  transport scenarios. Successes and failures are cached so later nodes cannot
  retry a used root or obscure the original failure.
- Removed the duplicate six-case WebView2 version matrix from the bridge tests;
  the runtime-owned matrix remains authoritative.

## Rigor Boundaries

- Departments indicate primary ownership and routing, never complete blast-
  radius analysis. Public contracts require explicit consumer departments;
  uncertain or cross-cutting changes require the ordinary repository suite.
- `--dept` intersects explicit path and node selections. It does not expand
  dependencies or imply headed coverage.
- Protected transport-custody calibration, holdout, and live guards were not
  changed. Settlement capture caching, the proposed SQLite-limit substitution
  for the live 33k-row guard, CLI lifecycle repartition, and default xdist were
  deliberately deferred.

## Verification

- Affected helper owners and consumers: 208 passed, 7 capability skips.
- Department policy after adversarial correction: 15 passed.
- Ordinary repository: 2,287 passed, 9 capability skips, 27 headed deselected.
- Headed interface gate on the real installed-wheel/WebView2 host: 27 passed.
- Import boundary lint: 11 contracts kept, 0 broken.
- Independent adversarial review found two issues before closure: incomplete
  pytest filename discovery and lazy scenario failure retries. Both received
  regressions, were corrected, and passed re-review; no other actionable
  finding remained.

The next test operation should begin at the narrowest useful level in
`docs/TESTS.md`. A release still uses the documented unfiltered complete command
and import lint; no case catalog or timing threshold belongs in the policy.
