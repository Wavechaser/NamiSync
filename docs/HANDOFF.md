# Session Handoff

Status (2026-08-17): the desktop readiness subsystem and headed acceptance
harness consolidation are implemented in five independently reviewable commits
from `8bf6ab0` through `d667917`. This handoff records their documentation
closeout and final verification state.

## Delivered

- Moved the desktop document-readiness state machine, phase vocabulary, exact
  contexts, and generation ownership into `interfaces/web/readiness.py`.
- Inverted command readiness into host-owned `admit(name)`: composition joins
  the final immutable command row with current readiness, while the bridge
  consumes an exact generic verdict, forwards granted context opaquely, and
  retains its independent document-trust and 64-handler guards.
- Replaced appearance publication as the liveness token with a neutral,
  current-generation host challenge/page `readiness_echo` roundtrip. Appearance
  configuration, observation, and publication now degrade over a confirmed
  opaque base; only an unconfirmed rollback after native surface mutation is a
  hard startup refusal.
- Added the sole bounded/current-document WebView2 message sink in
  `document_channel.py`, the packaged neutral receiver in `readiness.js`, and a
  mechanical Python/JavaScript mirror for every production command's phase,
  timeout, and retry policy.
- Consolidated positive custom pages behind `bootstrapTestBridge()`, positive
  host seams behind `drive_startup_handshake()`, and headed command additions
  behind one immutable collision-refusing extension helper. Negative and
  renderer-only fault seams remain explicit.
- Replaced parent polling of repeatedly replaced live JSON snapshots with a
  tests-only immutable milestone protocol: one `ready` or `failure`, followed
  by `final`, each canonical, bounded, and published without replacement.
  Final-only completion/refusal witnesses opt in explicitly; benchmark streams
  remain append-only measurement artifacts rather than milestones.

## Adversarial Review

- Separate builder/reviewer passes checked generation supersession, queued
  document currency, echo replay, phase drift, malformed verdicts, appearance
  degradation versus unsafe rollback, exact JSON typing, bounded reads,
  contradiction/final ordering, held-file behavior, and child-exit reporting.
- The resulting architecture keeps readiness, dispatcher session admission,
  and bridge handler admission at their distinct granularities; no grand shared
  admission abstraction was introduced.
- A later Windows-event review found that checkpoint 4's green result was not
  compositor-health evidence. At 2026-08-17 18:29:25, Application Error record
  63156 and WER report `854b76c5-b80c-4127-acc8-404d18814e0d` accompanied
  the incident. Dwminit record 63157 reported restart 1; WER subcode `0x23`
  names an unexpected heap exception. No contemporaneous GPU/TDR event was
  found in the inspected logs. DWM restarts on 2025-07-23 and
  2026-07-26 had different `MILERR_DISPLAYSTATEINVALID` signatures, and
  checkpoint 5 had no later DWM event. This establishes a headed-evidence blind
  spot and temporal correlation only; it does not establish NamiSync causality.
  WER recorded `memory.hdmp` among the attached files and named the
  ACL-protected archive
  `C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_dwm.exe_df609f70188a5f8b3be1496f1c39c52b1ad9_1b1372ac_e7ec54db-cfb8-49f8-a2a2-6473171dfcdf`;
  this session could not verify the archive contents. An administrator should
  preserve and inspect any retained dump locally as sensitive desktop-process
  memory before WER cleanup.

## Verification

- Each checkpoint passed its matching focused ordinary, direct bundled-Node,
  and/or installed-wheel real-WebView2 tests before commit.
- Final ordinary repository suite: `2,419 passed, 12 skipped, 27 deselected`.
- Latest post-incident combined installed-wheel headed run:
  `27 passed, 53 deselected`; the Application log contains no later DWM restart.
- The complete unfiltered repository suite was deliberately not rerun after the
  DWM incident; ordinary and post-incident headed evidence remain stated
  separately rather than manufacturing another stress pass.
- Import boundary lint: `11 kept, 0 broken`.
- Documentation truth/stale-text scan and `git diff --check`: clean; only the
  expected working-copy CRLF notices were emitted.

## Remaining Work

- Add a shared current-session DWM sentinel before treating a green headed run
  as compositor-health evidence. It must bracket the complete run, detect a
  restart independently of child/page success, report corroborating event-log
  or GPU/TDR evidence, distinguish older events, and avoid inferring causality.
- Slice 5–7 product plan, inventory, history, settings, and lifecycle surfaces;
  GUI Break 2 visual cohesion; and Slice 8 beta/release closure remain open.
- BR-G-32's plan- and inventory-DOM clauses, full BR-G-41 lifecycle closure,
  BR-G-42 current-source event timing and later product-view rows, BR-G-45
  terminal-artifact/completed-task retention, and SH-G-15 version-bound whole-
  runtime containment remain open on their owning phases.
- Slice 4's 120,000-node evidence is a retained-representation witness and
  deterministic scaling guard, not Tier 2 latency acceptance. Slice 5/6 must
  supply the named product-view measurements without retuning these contracts.
- The temporary pre-Stage-6 root `M1_SHELL.md` remains absent after verified
  realignment; active delivery authority remains `docs/M1_SHELL.md`.
