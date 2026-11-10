# Latest session — release repair preserved at decision boundary, 2026-11-10

## Active outcome

The user authorized the bounded release repair and renewed gates proposed by R5.
[M1_PLAN](M1_PLAN.md#approved-release-repair--2026-11-10) owns RR1–RR4:
standard-integrity GUI admission, exact serviced build inputs, runtime-dependent
R3 renewal and complete R4 verification under unchanged budgets. External
delivery and the Microsoft agreement remain separate final decisions. Do not
request repair authorization again.

The v2 custody-authority extension below has no answer yet. Independent work
is finished; dependent repair and acceptance are paused. The first genuine
elevation attempt was canceled by Windows/user and produced no receipt. The
separate question about the visible UAC prompt also has no answer. Do not
retry elevation until the user resolves that interaction.

Task-owned source is preserved at `ed18ad3e` on
`codex/wip-20261110-release-repair`, based on `89bbd0e7`.
It is a disposable recovery, not a merge unit. Rebuild its useful
changes into reviewed, verified RR1 and RR2/RR3 commits; do not merge or
cherry-pick the WIP. `milestone1` retains the wheel-header test fix and current
decision/resumption documentation only. No unrelated dirty work was present.

Starting point is `milestone1` at `4cd41dda`, which records the R5 review and
archives the mockup under `docs/obsolete/ui_mockup/`. Preserve the accepted R4
artifact `3ece185f` and historical receipts. No old pass or resource exception
certifies a changed candidate.

## Work in progress

- RR1 adds a primary process-token check before singleton activation, path
  leases, logging, services or browser exposure. Only medium/non-elevated is
  admitted; unreadable facts cause actionable refusal. Focused host/logging
  checks pass (148). Native low/medium source witnesses retain host hashes.
  The interfaces department passes all 2,302 cases after correcting its temp
  placement and the pre-existing wheel-header assertion. Source and test-fix
  independent reviews pass. The first Windows elevation request returned
  canceled, so no genuine High-token receipt exists yet. Await the user's UAC
  interaction response before retrying; this witness must finish before the
  guard commit. The wheel fix and repair context are committed in `89bbd0e7`.
- RR2's recovery draft selects official PSF Python 3.15.2 and updates
  CI, hash locks, build guidance, exact notices and their direct consumers.
  Official Python 3.14.10 retains SQLite 3.50.4's published WAL-reset bug;
  NamiSync uses WAL. Official 3.15.2 includes SQLite 3.53.4 and needs the compatible
  pythonnet update; xxhash 4.1.0 and setuptools 84.1.0 provide native/build
  servicing. Both this
  candidate and Astral 3.13.18 passed the initial native compatibility probe;
  official PSF preserves distribution/CI provenance and includes newer SQLite.
  Frozen-artifact reconciliation and complete native review remain. No
  supported-path corruption was observed in this investigation.
- RR3's draft qualification edits are paused: the ceiling pins the original
  verifier's working bytes, which require 3.13. A v2 authority proposal in
  M1_PLAN awaits the user's decision; do not implement it or silently repin v1.
  The selected 3.15.2/xxhash 4.1.0 diagnostic measured 1,433,387 ordinary and
  1,642,935 maximum-no-Gap bytes, then correctly failed the authority check.
  The unchanged ceiling is 1,966,080 bytes; this is not acceptance. Astral 3.13.18
  passes all 66 unchanged custody cases but retains unresolved SQLite FTS5
  applicability, so it was not selected. Full acceptance needs a disposable
  checkout with its own selected-runtime `.venv`: two tooling tests explicitly
  launch that path. Keep the user's current venv.

## Completed verification and review

- RR1: 148 focused host/logging cases, 2,302 interfaces cases and 12 import
  contracts pass on the existing 3.13 environment. Actual low/medium token receipts and independent source
  review pass. The high-token witness, final-runtime complete suite and frozen
  artifact witness remain open.
- RR2: selected-input compatibility has 337 passes; two reparse fixture access
  denials reproduce on the old Python in the sandbox and both pass on the
  selected runtime on the native host. Final wheel/frontend/metadata checks
  pass 84 cases. Independent source/input/notice review found no remaining
  blocker in this bounded draft. The diagnostic freezer verifies 338 files,
  38 native origins and 52 notice records, with system-only CLI startup.
  Fourteen default XXH3-128 digest sizes match old/new one-shot and streaming
  results. These are not complete release acceptance.
- RR3: 82 unaffected profile/control cases pass. The selected live custody
  diagnostic retains its expected authority failure, not a green gate. V1
  calibration/ceiling/holdout bytes and their Git authority were not changed.
  The complete suite, clean-source R3 collections, settlement renewal and
  17-run SH-G-15 schedule have not run for the new candidate.

The proposal is one versioned active authority record and matching controls,
authenticating the original v1 decision and keeping its numerical claim scoped
to its recorded runtime. It does not approve a new empirical limit, waive the
live guard or introduce a second-runtime framework. M1_PLAN owns the finite
population and gate; obtain the pending decision before implementation.

## Evidence and operational context

`build/m1-release-repair-20261110/README.md` defines evidence conventions.
`guard/` retains focused/native receipts and the elevated-source helper;
`runtime/` retains downloads and private environments; `renewal-design.md` maps
five-child R3 collections, the complete release suite, settlement audit, native
artifact witnesses and unchanged 17-run resource schedule. Preserve failed
attempts. Serialize shared writers and acceptance measurements. Default shell
is Low integrity; ordinary unsandboxed execution is Medium, not elevated.
Genuine elevated evidence needs a measured High token and Windows consent.
The reviewed source helper is `guard/run-elevated-source.ps1`; it pins the
original base interpreter/host/launcher/probe and writes an exclusive receipt.
`guard/uac-attempt-01.txt` records the canceled request. Runtime logs include
`pytest-rr2-02`, `pytest-rr2-baseline-acl`, `pytest-rr2-host-acl` and
`pytest-rr2-wheel-03`; final draft snapshots live in
`runtime/psf-rr2-xxhash410-preservation/`. The isolated local clone
`renewal/astral-custody-probe/checkout/` remains at clean `89bbd0e7` with full local Git
history available; its private environments and receipts are retained.
`renewal/custody-315-xxhash-4/` holds the final diagnostic's exact raw identities.
No task-created checkout, environment or evidence has been deleted.

Earlier R5 evidence remains in `build/m1-r5-20261110/`, including security review,
desktop-gate mapping and the prepared old-candidate delivery set. Its ZIP hash is
`5b9163ce26b2a20734058069c03b966225be5bef6c7aac4b90477a54408f7319`.
Original R4 evidence remains in `build/m1-r4-20261109/`: 6,556 passes/four privilege
skips, 546 BR-G and 69 SH-G cases. Its resource validator remains FAIL for 100k
peak, soak slope and one retained shift, separately accepted by the user for that
artifact only. No upload, tag, push or external handoff occurred. No measuring
session process, profile, corpus or old artifact is task-owned.
