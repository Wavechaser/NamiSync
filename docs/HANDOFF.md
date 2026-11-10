# Latest session — authorized release repair, 2026-11-10

## Active outcome

The user authorized the bounded release repair and renewed gates proposed by R5.
[M1_PLAN](M1_PLAN.md#approved-release-repair--2026-11-10) owns RR1–RR4:
standard-integrity GUI admission, exact serviced build inputs, runtime-dependent
R3 renewal and complete R4 verification under unchanged budgets. External
delivery and the Microsoft agreement remain separate final decisions. Do not
request repair authorization again.

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
  independent reviews pass. Genuine elevated evidence is pending Windows
  consent and must finish before the guard commit.
- RR2 selected official PSF Python 3.15.2; runtime locks are not yet changed.
  Official Python 3.14.10 retains SQLite 3.50.4's published WAL-reset bug;
  NamiSync uses WAL. Official 3.15.2 includes SQLite 3.53.4 but requires compatible
  pythonnet 3.2.1 and xxhash 3.8.2 upgrades, plus setuptools 84.1.0. Both this
  candidate and Astral 3.13.18 passed the initial native compatibility probe;
  official PSF preserves distribution/CI provenance and includes newer SQLite.
  Final applicability, notice and complete native reviews remain. No
  supported-path corruption was observed in this investigation.
- The read-only renewal design maps exact runtime consumers and acceptance.
  Preserve historical SH-G-8 qualification separately from the live drift
  guard and unchanged 1,966,080-byte ceiling. Full acceptance needs a disposable
  checkout with its own selected-runtime `.venv`: two tooling tests explicitly
  launch that path. Keep the user's current venv.

## Evidence and operational context

`build/m1-release-repair-20261110/README.md` defines evidence conventions.
`guard/` retains focused/native receipts and the elevated-source helper;
`runtime/` retains downloads and private environments; `renewal-design.md` maps
five-child R3 collections, the complete release suite, settlement audit, native
artifact witnesses and unchanged 17-run resource schedule. Preserve failed
attempts. Serialize shared writers and acceptance measurements. Default shell
is Low integrity; ordinary unsandboxed execution is Medium, not elevated.
Genuine elevated evidence needs a measured High token and Windows consent.

Earlier R5 evidence remains in `build/m1-r5-20261110/`, including security review,
desktop-gate mapping and the prepared old-candidate delivery set. Its ZIP hash is
`5b9163ce26b2a20734058069c03b966225be5bef6c7aac4b90477a54408f7319`.
Original R4 evidence remains in `build/m1-r4-20261109/`: 6,556 passes/four privilege
skips, 546 BR-G and 69 SH-G cases. Its resource validator remains FAIL for 100k
peak, soak slope and one retained shift, separately accepted by the user for that
artifact only. No upload, tag, push or external handoff occurred. No measuring
session process, profile, corpus or old artifact is task-owned.
