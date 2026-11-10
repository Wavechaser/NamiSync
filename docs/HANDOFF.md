# Latest session — release repair resumed, 2026-11-10

## Active scope and decisions

The user approved the versioned SH-G-8 authority extension and the complete
native/quiet resource schedule. [M1_PLAN](M1_PLAN.md#approved-release-repair--2026-11-10)
owns RR1–RR4, including the v2 population and gate. Keep all v1 artifacts,
provenance and the 1,966,080-byte ceiling unchanged. No second-runtime framework,
new calibration or broader empirical claim is authorized. External delivery
and the Microsoft agreement remain separate final decisions.

Resumed from clean `milestone1` at `529d7bbf`. Recovered task source from
`ed18ad3e` as an uncommitted patch, preserving current M1/HANDOFF; no WIP merge
or cherry-pick. Keep `codex/wip-20261110-release-repair` until every saved change
is accounted for. `89bbd0e7` already delivered the wheel METADATA-header fix.

## Current checkpoints

- RR1 is verified and independently reviewed. The desktop host admits only an
  actual non-elevated medium token, before singleton, path lease, logging,
  service or browser admission. Focused host/logging 148, interfaces 2,302 and
  12 import contracts pass on the original 3.13 environment. Actual low and
  High/elevated tokens refuse; medium reaches singleton admission. The user
  reported no first prompt and possible absence during timeout. Attempt 02
  through built-in Windows PowerShell succeeded: High SID 12288, elevation 1,
  GUI exit 1, no singleton/data/WebView, exact reviewed host/launcher hashes.
  Final selected-runtime and frozen-artifact gates still follow.
- RR2 source/input/notices draft has independent review: official PSF CPython
  3.15.2 x64 / SQLite 3.53.4, setuptools 84.1.0, pythonnet 3.2.1 and xxhash 4.1.0
  with native 0.8.4. The current wheel and notices match. Selected compatibility
  checks recorded 337 passes; two sandbox reparse denials reproduce on old
  Python and both pass natively on selected Python. Final wheel/frontend and
  metadata rerun passes 84. Scratch freezer: 338 files, 38 native origins,
  52 notices and system-only CLI. Fourteen old/new default hashing vectors
  match one-shot and streaming. None is complete release acceptance.
- RR3 v2 implementation is active. The prior 3.15.2/xxhash 4.1 diagnostic measured
  1,433,387 ordinary and 1,642,935 maximum-no-Gap bytes, then correctly failed
  the v1 working-validator pin. The new authority must authenticate original
  v1 decisions separately and pin current verifier/helper identities. Independent
  review and isolated authority freeze precede the real controls/live gate and
  integration. The unrelated profile controls passed 82 cases. Preserve failed
  receipts; do not reuse an unqualified diagnostic as acceptance.
- RR4 needs the clean selected-runtime checkout, complete release command,
  settlement renewal, exact portable build/census/native journeys and unchanged
  17-run SH-G-15 schedule. The user confirmed this machine may stay plugged in,
  unlocked and mostly idle. Serialize measurements with all builders/tests.

## Evidence and resumption details

`build/m1-release-repair-20261110/README.md` owns evidence conventions.
`guard/elevated-source-admission.json` and `uac-attempt-02.json` close the real
source High-token witness; the canceled first receipt remains. The helper pins
its exact original base interpreter/host/launcher/probe and uses no site or
bytecode cache. Runtime logs: `pytest-rr2-02`, `pytest-rr2-baseline-acl`,
`pytest-rr2-host-acl`, `pytest-rr2-wheel-03`; private final environments:
`runtime/psf315-xxhash410/{package-env,verify-env}`. Complete frozen acceptance
needs its own checkout `.venv`, because two tooling tests explicitly launch it.
Keep the user's root `.venv` and global Python unchanged.

`renewal-design.md` maps R3/R4 commands and the 17-run schedule. The isolated
Astral comparison clone `renewal/astral-custody-probe/checkout/` remains at
`89bbd0e7`; no task clone/environment/evidence has been deleted. Astral's 66
unchanged custody passes remain diagnostic; its older SQLite applicability
was unresolved, so it is not the chosen runtime. The selected custody raw
receipt is in `renewal/custody-315-xxhash-4/`.

Keep accepted R4 `3ece185f`, `build/m1-r4-20261109/` and the unchanged R5 delivery
set under `build/m1-r5-20261110/` immutable. Old resource exceptions certify only
that artifact. No upload, tag, push, external handoff or measuring-session
process/profile/corpus changes occurred. Reconcile final candidate evidence
before asking for the separate delivery decision.
