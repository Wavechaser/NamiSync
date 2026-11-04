# Latest session — manual workload diagnostics, 2026-11-04

The requested diagnostic continuation and measured retry are complete. No product
code changed. The actual measured workload contains three sync/close cycles and
four verification runs; the user confirmed the extra one-file verification in
cycle 2. Results are diagnostic, not an exact-three-verification profile pass or
release acceptance. This replaced handoff is included in the delivery commit.

## Package and prior evidence

Packaging commit `027f7e64`; prior behavioral closeout `448e7ba3`.
Artifact: `build/m1-release-20261104/attempt-03/NamiSync-windows-x64-dev.zip`.
SHA-256: `acc2c253057bce8af3c497053dfab3765da0621c9c507792b2aa4fb6e553bd69`.
Recorded source is `3aa03caa` plus staged host/icon/packaging inputs, not a clean
release candidate. Source ZIP, wheel and resolved environment remain adjacent.
All 471 extracted files matched before/after each continuation run. Commands
are `namisync` and `namisync-gui`; Windows identity is `NamiSync.Desktop`.

Earlier portable evidence remains in
`build/bughunt-20261104/packaged-round/evidence/summary.md`: 30 frozen CLI
invocations/70 checks, the small native GUI workflow/settings/restart journey,
and three fresh-process idle observations. Packaging retains 6,359 ordinary
passes/four capability skips and separate 35 headed obligations. No product
gates were rerun for this documentation-only delivery; GitHub CI execution,
clean-candidate release proof and publication remain open. No push occurred.

## Continuation results and limits

Evidence root:
`build/bughunt-20261104/packaged-round/continuation-native-20261104/`.
Its `summary.md` and final review index exact scripts, raw samples, user
witnesses, screenshots, specimen archives and private-copy database queries.

- Both SendInput diagnostics accepted two events but reached Plan only after
  manual activation. One may have had physical mouse interference; a controlled
  hands-off repeat also needed a manual click. Browser delivery/root cause is
  unresolved; no product fix is inferred.
- Whole-tree UIA observation failed during startup and execution. Its old failure
  cleanup closed the active copy; archived private-copy history correctly records
  118 succeeded/138 canceled, recording/audit ok. No false success was found.
- The user approved passive Job sampling with manual workflow witnesses instead.
  Three sync cycles copied/updated 256/1/1 files with 0/255/255 no-ops. Managed
  hashes and prior-version backups passed after every cycle. All three sync and
  four verification history runs completed with recording/audit ok.
- The 818.51-second session yielded 1,633 complete samples out of 1,637. Fixed
  idle medians were 353 MiB initially, 853/665/628 MiB after each task close and
  624 MiB finally. The sampled peak was 1,270.89 MiB. Final idle remained
  271 MiB above startup while successive post-close medians decreased. These
  observations do not prove a leak or long-session stability; PERFORMANCE owns
  methods, units, sampling gaps and the extra-verification deviation.
- Normal shutdown exited 0 with an empty Job; all eight sampled identities and
  wrapper are gone. Sampler/app/workload-driver dependencies stayed unchanged.
  One cropped parent screenshot is retained unused; corrected DPI-aware
  captures have separate producer provenance. UI witnesses are manual.

The strict three-verification oracle remains failed, alongside the user's
confirmation and `passive-review-reconciliation.json`. Do not relabel it as
passing or remove the fourth verification from resource accounting.

## Preservation, cleanup and resumption

`continuation-specimens.zip` preserves all five diagnostic/observer fixtures;
`passive-specimens.zip` preserves the final workload, databases and backups.
Their manifests bind exact hashes/metadata and reproducible bundle contents.
Original databases were never opened for inspection; only archived private
copies were queried. All original failed receipts remain intact.

Nine continuation runtime/cache/private-query roots were removed after archive
and process review; `cleanup-result-20261104-115823.json` records every root.
The previous round's 16 removals/four already-absent roots remain separately
accounted. Evidence stays in build. The packaging-owned original
`namisync-portable-debug-6ru3eo_p` extraction/native profiles remain excluded.

M1_PLAN remains the sole scope owner. Longer/heavier resource profiles and
predeclared release criteria remain open; do not infer a resource budget here.
Other untested areas include fresh Integrity GUI setup, explicit busy/pause/
cancel controls, malformed-profile startup and clean-machine prerequisites.
Final dependency hashes/notices/source obligations, beta version/signing and
distribution also remain open. Any further automation investigation should
separate native input delivery from live accessibility-tree enumeration and
preserve an active app on observer failure.
