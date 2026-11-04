# Latest session — portable-package behavioral round, 2026-11-04

The bounded investigation is complete. No new product defect was established;
repeated-workload resource measurement remains unavailable. No product code
changed in this round. This handoff replaces accumulated prior-session notes
and is included in the delivery commit as requested. M1_PLAN owns release scope;
this development-package investigation does not close release acceptance.

## Package and retained baseline

Packaging commit: `027f7e64`; Setup visibility fixture correction: `a583904e`.
Artifact: `build/m1-release-20261104/attempt-03/NamiSync-windows-x64-dev.zip`.
SHA-256: `acc2c253057bce8af3c497053dfab3765da0621c9c507792b2aa4fb6e553bd69`.
The directory also retains source ZIP, wheel, checksums and resolved environment.
Recorded source is `3aa03caa` plus staged host/icon/packaging inputs, not a clean
release candidate. All 312 source-manifest files and 471 bundle files were
checked. Extract the whole bundle; START-HERE documents prerequisites and an
isolated absolute `--data-dir`. Installed commands are `namisync` and
`namisync-gui`; stable Windows identity is `NamiSync.Desktop`.

Prior packaging evidence remains valid by dependency: 6,359 ordinary passes,
four capability skips, 35 separate installed headed obligations, 2,208 accounted
interface cases, 167 focused host/bridge cases and twelve import contracts.
These gates were not rerun for this documentation-only closeout. GitHub CI is
authored but has not run on GitHub. No publication or push occurred here.

## This round's evidence

`build/bughunt-20261104/packaged-round/evidence/summary.md` indexes raw receipts,
drivers, screenshots, provenance and independent reviews.

- Actual frozen CLI: 30 invocations, 70 checks pass. Covers reviewed Unicode
  copy/readback, restart/no-op/history, integrity mismatch/rebaseline, eight
  malformed database-pair refusals, standalone history, settings isolation,
  default versus explicit placement and bundle relocation from unrelated cwd.
- Native GUI: reviewed three-file Unicode copy, retained inventory, Verify
  copied, saved additive default and recent roots after restart, normal close.
  Final file hashes/mtimes and both database quick checks agree. No separate
  immediate pre-Execute filesystem snapshot was captured.
- Three fresh-process 60-second idle diagnostics: settled private bytes about
  354–360 MiB, 357/360 complete samples, normal exit and no residual Job members.
  PERFORMANCE owns scope, raw values and caveats; no budget or SH-G-15 pass.
- Repeated workload: both attempts timed out at the first Create plan transition.
  Retry proves exact cursor/button placement, not mouse-event delivery. The user
  likewise saw cursor movement but could not confirm a click. The harness then
  closed the window; host exit 0 and shutdown logs do not establish a crash.
  Two retry WebView descendants required final Job cleanup. No repeated cycles
  or retention results exist; no third attempt was made.

Failed repeated profiles, all 512 source files and exact driver dependencies are
preserved by `gui-repeat-preservation-02.json` and
`gui-repeat-failed-profiles-02.zip`; archive SHA-256 is
`e5672f4af92399fbfc9ec78641922782fa342c5f6778b4cdf4e72ae2232f6890`.
Both omitted duplicate bundles have complete hash maps matching the original ZIP.
All observed test process identities are gone. Product logs also retain an empty
WebView2-root deletion warning; no retained browser content or data failure was
observed. Do not promote that diagnostic to a substantive defect without evidence.

## Cleanup and next work

Cleanup completed against the independently reviewed `cleanup-plan.json`:
16 registered roots removed, four already absent, seven child reparse entries
unlinked without traversal. `cleanup-result-20261104-105734.json` records every
root; preserved native/repeated specimens and evidence remain in
`build/bughunt-20261104/`. The original packaging-owned
`namisync-portable-debug-6ru3eo_p` extraction and its native profiles are excluded.

Next investigation should resolve native Create plan input delivery before
attempting another repeated workload. GUI standalone Integrity setup, busy/
pause/cancel, malformed-profile startup and clean-machine prerequisites remain
untested here. Resource budgets, representative longer/heavier sessions and a
clean release candidate remain open, alongside final dependency hashes,
distribution notices/source obligations, beta version/signing and publication.
No product fix is implied by the unresolved synthetic-input failure.

Earlier bug-hunt sweep/fix evidence remains in `build/bughunt-20261104/evidence/`:
84 invariant cells, historical sibling probes, A-1 request bounds, A-2 encoding
fix (`3aa03caa`) and database/history test consolidation (`a40fd2f7`). Their current
dispositions remain in M1_PLAN/BUGS; historical failed receipts are retained.
Build cleanup restore rules remain in `build/build_cleanup_*_summary.json`.
