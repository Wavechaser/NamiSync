# Latest session — reviewed open-bug resolutions

2026-10-01 on `milestone1`, base `1d17883`. The user authorized three bounded
outcomes through execute-task: optional report advice, filesystem-aware handle
identity fallback, and a bounded exception-retention disposition. The response-
copy entry remains untouched. M1_PLAN owns the scope and gates.

## Current changes and evidence

- Report advice: performance passes no replacement flag and directs the user to
  a new `--json` path. Existing report bytes and prelaunch refusal are preserved.
  Focused CLI verification: 77 passed, two capability skips; tools department:
  336 passed, three capability skips. Independent review approved; separately
  committed as `fix(tools): make replacement advice optional`.
- Identity fallback is being implemented independently; successful identity
  queries must add no volume lookup, and NTFS/ReFS failures remain failures.
- Retention review supports bounded closure without product edits. The original
  finalizer probe itself retained the exception; it did not demonstrate excess
  product ownership. Host/document endpoints and reopening evidence will be
  documented in INTERFACES before the disposition commit.

Evidence root: `build/open-bugs-20261001/`. Prechange `current.json` reproduces
report advice and exFAT target failure; `reader.json` reproduces the verifier's
same native identity failure. Their temporary F:/K: fixtures were removed.
Current product changes invalidate those probes as final acceptance; native
postchange probes, affected tests, ordinary suite/imports and settlement gate
remain required for the identity outcome. No changes to protected oracle
baseline, response-copy disposition, or future M1 delivery are authorized.
