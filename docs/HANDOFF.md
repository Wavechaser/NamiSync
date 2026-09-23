# Latest session — R1 ablation scope and workflow priorities

The investigation and this documentation update are one reviewed commit on
`codex/m1-8-r0-ready`, based on R0 `8f7555b`, in
`F:/GitHubRepositories/NamiSync/build/m1-8-r0`. No product/test implementation,
acceptance rerun, milestone integration, push or cleanup is part of this task.

## Decisions

- R1 now includes current T1–T5 as R1-A–E: gallery verdict consolidation,
  short-native choreography removal, identified source-spelling assertions,
  local request counts and redundant identity scans. M1_PLAN owns the finite
  population, surviving detectors and gates; product optimization stays separate.
- AGENTS and personal execute-task have five concise priorities: work by
  mechanism, check real seams early, settle inputs before acceptance, reuse
  evidence by dependency and keep one current decision record. Stop rules and
  acceptance gates remain binding; no new preflight protocol is introduced.
- Retain M1_7_ABLATION_STUDY but defer revisiting it until after M1-8 closes and
  the user resumes it. It cannot expand R2's frozen historical dependencies.
- The preceding investigation found recurring consumer/oracle drift, late native
  layout checks and weak diagnostics, alongside genuine product defects. Its
  report is `build/delivery-investigation-20260923/report.md`; recommendations
  there describe the pre-update snapshot. The decisions above supersede its
  proposed R1 limit and timing of M1-7 reconsideration.

## Review and verification

Fresh independent review of the complete delta from `8f7555b`, investigation
reports and external skill diff passed. All 110 local documentation links resolve;
`git diff --check` and the skill-creator validator pass. R2 is unchanged. Product
tests were not run: no executable contract or test authority changed.
The skill is updated in place at
`C:/Users/Spectrum/.codex/skills/execute-task/SKILL.md`, outside the Git commit.
Its before-copy and diff are retained in the investigation evidence; updated
SHA-256: `ed4193ac57179fb5491ff04d9f5388ded63289563e8d0aefec54a4dae5cae179`.

## R0 acceptance and open observations

`build/r0-layout-20260923-01/delivery.json` binds the R0 commit and evidence.
Ordinary-04: 5,321 passed/five skips/33 deselected; full-headed-03: all 33 pass
under an 8 GiB Windows Job cap; all 12 import contracts pass. Final v4 source/tests,
source/staging/wheel/install identity, native captures and independent review
remain R0 acceptance. The previous handoff is preserved in the investigation
evidence as `handoff-before-investigation.md`; original detailed chronology is
`build/r0-layout-20260923-01/plan-before-final-closeout.md`.

Theme/contrast and filter/Search overflow remain deferred. One earlier short
larger-window pre-click focus-or-hit failure remains unclassified: its operand
was not retained, while one bounded diagnostic and final gate passed unchanged
guards. Preserve those receipts if it recurs. R1–R3, quantitative acceptance and
milestone integration remain pending; this documentation update does not start implementation.

Memory incident: `build/r0-focused-01/MEMORY_INCIDENT.md` identifies cyclic mock-DOM
assertion formatting as the Node allocation cause. Keep Boolean diagnostics and
capped launchers; never rerun the old unrestricted probe. These task-local limits
are not a product memory guarantee.

## Preservation

Original checkout remains on `codex/m1-8-r0` at P2 `4bbf943`; milestone1 remains
`055325b`. Protected stash `93414b7...`, unrelated `af02913`, recovery `8b2a0fb`
and `6ada8ca`, old U/UV2/P2 evidence and `build/m1-8-uv1-parent` remain untouched.
No recovery ancestry was integrated. Investigation evidence is retained under `build/delivery-investigation-20260923/`.
Review the R0 GUI before resuming implementation; this task only commits the
combined investigation and documentation/rule update. No branch integration or
cleanup is included.
