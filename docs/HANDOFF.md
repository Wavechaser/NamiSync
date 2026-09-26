# Latest session — unexplained ablation incident investigation

2026-09-27, `milestone1`, inspected revision `25514f12`. User authorized a
best-effort investigation of five AB-2/7/8/10 incidents; two sessions traced
them in parallel. No product, collected test or acceptance-contract changes.
Detailed evidence: `build/incident-trace-20260927/findings.md` (bridge chain,
installed reruns, Windows events, exact input hashes) and
`build/trace-20260927/` (third bridge trace, headless Setup replay and
database-pair race scripts with results).

Current bridge diagnostic failure is reproduced: decimal-string Progress
positions fail the helper's integer sample validator; rejected chained reports
retain pending counters until reporting saturation escapes the page callback
near 17 s, as in AB-10. The parent then closes while four synthetic workers
still run their fixed 60-second, uncancelable loop. Service Close reports
incomplete/unreleased; the normal host Retry/Cancel prompt waits until the
110-second parent deadline. The helper formerly retained the browser error only
in memory until host exit. Its terminal summaries also read the retired result
`items` array, so a position-only migration would fail at the first Terminal.
BUGS records an OPEN diagnostic defect. Historical AB-2/AB-10 evidence is
compatible, not causal proof of those exact runs. Migration is unimplemented.

AB-7 Setup: a headless replay of its call sequence with UI-like concurrent
reads reproduced the generic `task start failed` in 1 of 300 serial starts.
The retired cause was `DatabasePairRefusedError(ledger-contract)` from
`prepare_plan`, before any session effect. Pair preflight hashes main/WAL/SHM
and refuses any drift, including the same process's reads and recording:
deterministic beside a raw reader, about 1 in 900 checks beside
`remembered_locations` or `list_history`. BUGS records it MODERATE/OPEN.
Repair changes the DATABASE/DEFENSE drift-refusal contract and needs user
adjudication. The original AB-7 exception was not retained, so that incident
is a probable, not proven, instance. Unverified: the unleased CLI's refusal
text directs users to delete both databases.

AB-8 stack/wrap: the narrow witness writes renderer-owned status text and
`hidden` state, then yields one animation frame. Every review render resets
`status.hidden` from its action message, and a hidden node measures top 0,
exactly the failing clause. Source-supported hypothesis only. AB-7 Plan again:
pending review work disables the button and a disabled click is a silent
no-op, but the original click had no trace; cause unknown. Neither is in BUGS.

Setup and both task-shell variants passed unchanged (3, 78.12s) and with
copied-helper diagnostics that capture pre-normalization start errors and
narrow-layout geometry (3, 79.99s); no one-off failure recurred. Bounded Windows
Application/System error history supplied no matching explanation; absence is
not environmental health proof.

Preserve `build/incident-trace-20260927/` (both bridge raw-incomplete
directories, 22 hash-checked copied native receipts/logs) and
`build/trace-20260927/`. Native fixtures are the external TEMP roots
`NamiSync-incident-20260927-01` and `-02`. All task-owned native processes
exited; the unowned Claude bridge trace the first session observed was
`build/trace-20260927/bridge-event-01`. Announce future native input batches
and serialize desktop use with other active work.

No next product checkpoint is active. M1_PLAN still owns pending M1-9/10/12,
Release and DOC-2 decisions; the drift-refusal repair is unallocated. Prior
integration/cleanup is unchanged: AB-10 `cb57c41a`, documentation consolidation
`25514f12`, archived study in `docs/obsolete/POST_M1_8_ABLATION.md`, recovery
bundle/accounting and 78 preserved AB-3 files in `build/ab10-20260926/`.
Documentation is committed on `milestone1`; no branch cleanup, push or PR.
All unrelated work and stashes remain untouched.

## Addendum — AB-7 Plan-again reclassification

Neither AB-7 "Plan-again" failure was a Plan-again failure. Both receipts are
named from the last checkpoint, `plan_again`, which the helper sets only after
Task 53 was created, selected and rendered; a fresh-task timeout would report
`plan_notice`. The final-run plan script equals `2b4a2214`'s, and CDP line
numbers are 0-based (validated by the `until` throw at 9 and AB-8's stack/wrap
throw at 425). Final run (default): line 490 is the `keyboard focus re-entry
ring` wait with `document_has_focus: false`; Chromium does not match `:focus` or
`:focus-visible` in an unfocused page, confirmed in a built-in browser control.
Concurrent orchestrator scripts at 01:22–01:24:25 are a plausible, unproven
focus source. BUGS records the unguarded focus precondition MINOR/OPEN.
Acceptance run (larger): a direct throw at line 411 with focus present; the
unpreserved intermediate diagnostic block, in its 15-line traced shape, places
it on the narrow stack/wrap throw (default-row or metadata checks if its size
differed). Stack/wrap has therefore probably failed twice, both in the larger
variant. AB-7's settle-before-click wait hardened a step that was not failing.
Line-mapping scripts: `build/trace-20260927/scripts/plan-again/`.