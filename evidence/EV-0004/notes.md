Notes for "AB-8 installed native shell evidence (2026-09-26)": text files chosen from `build/ab8-20260926`, `build/ab8-resume-20260926/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/ab8-resume-20260926/independent-review.md`

# AB-8 independent read-only review — 2026-09-26

Base: `4f1537c2`. Candidate: current working tree, including the untracked `namisync/interfaces/web/task_snapshot.py` and `tests/interfaces/web/test_task_snapshot.py`. Recovery `f7a170a` was used only to identify the resumed correction; the full candidate was compared with the base and the physical untracked files were read. Product and tests were not edited or run by this reviewer.

## Verdict

No supported product defect found in the reviewed AB-8 candidate. This is source-review evidence, not checkpoint acceptance: the root's installed reruns and final documentation/gate reconciliation are still pending.

## Adversarial checks

- **Session identity and terminal custody.** `app.js:1910-1931` clears the Plan snapshot at execution admission. `app.js:576-634` compares revisions only within one session and does not let a lower revision suppress a terminal record. `task_status.js:95-97` and `plan_review.js:1190-1207` bind presentation to the current session, and the latter uses a snapshot Gap only for execution. `bridge.js:1971-2001` retains the exact record and snapshot on callback failure and releases only after the callback succeeds. The added page transition witness carries a Plan revision 40 into an execution revision 1 and a failed record.
- **Native state and replay.** `task_snapshot.py:93-167` ignores old non-Gap replay, retains explicit Gap uncertainty, clears active presentation at terminal settlement, and keeps a bounded current-item state without an outcome map. The old replay Gap can retain the earliest observed Gap sequence and reset estimates without rolling back newer progress. `drain.py:2165-2217` stages reduction under task custody and commits it with the admitted prefix; superseded drains do not commit it. A failed capture keeps the queue and presentation state for retry.
- **Byte admission.** `bridge.py:1665-1741` snapshots each candidate before counting it, includes the candidate snapshot plus prefix updates in the complete response ceiling, and stops at the first update that cannot fit. The prior Opus sweep of 1,343 byte ceilings and current prefix/failure tests support this calculation. I found no path that commits an unadmitted candidate.
- **Progress semantics.** `task_snapshot.py:169-238` preserves aggregate sampling across ordinary item handoffs and outcomes, resets it when a prior non-null attempt ID changes on the same item, and performs exact integer byte subtraction before rate conversion. Aggregate and current-item high water, phase authority, reliable outcome retirement, and Gap reset follow the stated BRIDGE and DESKTOP_UI contracts. The new native handoff/retry tests cover the corrected boundary.
- **Direct consumers.** The rail reads snapshot presentation facts; the Plan panel retains bounded window/detail ownership and uses nominal active identity for row decoration. The bridge still owns cursor, replay, validation and terminal release. No changed path introduces a per-item outcome map or moves domain effect authority into the page.

## Evidence boundary

The earlier failed candidate's false completed state and missing handoff rate were reproduced in `build/ab8-20260926/claude-review.md` and addressed by the resumed diff. Focused page and native snapshot receipts are in `build/ab8-resume-20260926/`; the root owns the installed reruns and broader gate. I did not treat passing probes as proof against unobserved lifecycle cases, but found no concrete counterexample in the current source. The larger installed status-layout assertion was previously unclassified and must be judged from the root's current rerun, not from this read-only review.

## Narrow sampler follow-up

The subsequent Opus review found that a same-item transition from no attempt ID to its first attempt ID still reset aggregate sampling. I read the correction at `task_snapshot.py:203-220` and the emitting paths: executor `runtime.py:727-760` publishes the active operation with no attempt from `start()`, then mints its first token in `begin_byte_stream()`; verifier `engine.py:323-339` does the same from `item_started()` to `stream_started()`. The old predicate treated that normal first stream as a retry. The current predicate resets only when the previous attempt ID is non-null and changes, preserving a true retry reset and aggregate sampling through first-stream admission. The extended handoff witness failed at the first attempt before the correction (`f2-first-attempt-red.log`) and passes afterward (`f2-first-attempt-green.log`, `f2-first-attempt-final.log`); I did not rerun it. I found no supported defect in this narrow correction.

# `build/ab8-resume-20260926/review-disposition.md`

# AB-8 review disposition

Target: physical AB-8 candidate on `milestone1`, base `4f1537c2`, including both
new snapshot files. Model/effort: **claude-opus-5-5 / high**. Invocation used the
[claude-code-reviewer skill](C:/Users/Spectrum/.codex/skills/claude-code-reviewer/SKILL.md).

The original resume could not locate transcript
`82edad2f-d91a-4e16-9e90-b55ef9f5ed86` (`claude-stderr.log`). Retry used that same
ID, directory, model/effort and tool profile, supplying the saved report and
fixtures explicitly. The final narrow call successfully resumed that retry.

Accepted findings: F1 session replacement/terminal custody; Plan Gap scoping;
F2 aggregate handoff and first-stream identity; settled-control feedback.
All have direct source/producer evidence and red/green witnesses. Opus reran
its original F1/Gap diagnostics, an independent F2 diagnostic, and nine native
snapshot tests. The fresh independent reviewer read the same owners/corrections.
Both conclude no remaining supported blocker. The low first-attempt finding
was corrected despite being called nonblocking, because it was incomplete F2
restoration. See `claude-final.md` for the final confirmation.

Optional page guard mutation controls did not warrant more tests: admission
retirement is witnessed, while the real bridge already rejects stale/foreign
snapshots before the page. Test clock/token fidelity and doc indentation were
corrected. Neither reviewer established a cause for the earlier installed
stack/wrap assertion; unchanged reruns passed, not proof of a fix.

Ten fixture files are preserved in `claude-final-fixtures/`; reviewer-mutated
temporary copies were removed by the reviewer. Original and copied physical
source inventories matched before/after both rounds. The disposable copy was
removed only after preservation (`review-cleanup-final.json`).

## CLI usage and cost

Raw JSON is retained. `usage` reports each call; `modelUsage` and total cost in
the final resumed receipt are cumulative for this reconstructed conversation.
Thinking is a subset of output, not an additional token total.

| Receipt | Input | Cache creation | Cache read | Output | Thinking | Reported cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `claude-retry.json` | 84 | 101,054 | 2,901,090 | 27,187 | 14,870 | $1.932726 |
| `claude-final.json` call usage | 8 | 8,375 | 450,401 | 2,737 | 1,065 | $2.1445782 cumulative |
| `claude-final.json` modelUsage, Opus 5.5 only | 92 | 109,429 | 3,351,491 | 29,924 | 15,935 | $2.1445782 cumulative |

Final follow-up increment: $0.2118522. Prior review in
`build/ab8-20260926/claude-followup.json` reported $5.903408; combined reported
AB-8 review cost is $8.0479862. No authentication, CLI update or paid tool call
outside the authorized review was performed during this resumption.

# `build/ab8-resume-20260926/verification.md`

# AB-8 resumed verification — 2026-09-26

Base `4f1537c2`; restored physical candidate from recovery `f7a170a`, then
corrected within user-adjudicated AB-8 scope. No recovery merge/cherry-pick.

- F1: prior root reproduction and this session's page red/green witnesses
  establish Plan revision 40 no longer suppresses execution revision 1 or its
  failed terminal record. Renderers require current-session identity; Plan Gap
  is not execution event loss. Final page probes: 3 passed (`page-final3.log`).
- F2: `f2-red.log` failed expected aggregate rate 10 vs None at item handoff;
  `f2-green.log` has 9 native snapshot passes, including same-item retry reset.
- Settled Pause feedback: `control-red2.log` reproduced stale Pausing after
  Paused and recovery; final page probes verify current feedback after retiring
  the settled control attempt. Unresolved/cancel ownership remains separate.
- Earlier larger-shell failure maps to the existing narrow status-feedback
  stack/wrap assertion. No CSS or harness assertion changed. Both installed
  shell variants passed (`shell.xml`: 2 passed, 71.07s). Its cause remains
  unexplained; a passing rerun does not prove it fixed.
- Complete suite (`complete.xml`, `complete.log`): **5,366 passed, 4 skipped**,
  473.96s, including all installed cases. All four skips are unavailable Windows
  symlink/reparse creation privilege (WinError 1314). Native desktop access,
  PIP_NO_CACHE_DIR=1, process-only PSExecutionPolicyPreference=RemoteSigned,
  unique basetemp; no suite exclusions or changed assertions.
- Import contracts (`imports.log`): **12 kept, 0 broken**.
- Fresh read-only independent review (`independent-review.md`): no supported
  product defect; source and direct consumers inspected, no reviewer tests.

`gate-inputs.json` identifies the frozen physical source. Earlier failed and
intermediate receipts remain here and in `build/ab8-20260926/`. Claude follow-up
and final documentation/commit remain pending at this evidence cut.

## Opus follow-up correction

Opus 5.5/high confirmed F1, Plan Gap and original F2 reproductions now pass;
no substantive blocker. It found normal None-to-first-attempt identity still
resetting the estimate. Root confirmed both executor/verifier report this
producer transition. This is incomplete F2 correction, within the admitted
sampler boundary, not a new recovery protocol or ownership change. Correct it
and rerun the affected gate; the complete pass above identifies the earlier
frozen candidate, not the subsequently corrected source. Optional redundant
page guard mutation controls do not justify additional implementation tests.

## Final accepted candidate

The first-attempt witness failed before correction (`f2-first-attempt-red.log`);
the final native file passed 9 tests (`f2-first-attempt-final.log`). The existing
handoff test now uses monotonic time, distinct attempt IDs and coherent counters.
No separate redundant test population was added. Independent review confirmed
both real producer paths; Opus reran its own diagnostic and the native tests,
confirmed the correction and found no remaining blocker (`claude-final.md`).

`final-gate-inputs.json` identifies the unchanged source for the final complete
run: **5,366 passed, 4 Windows symlink-privilege skips, 476.82s**
(`final-complete.xml/.log`). **12 import contracts kept** (`final-imports.log`).
All installed cases passed. No foreground/review process remains running.
Only documentation closeout changed afterward. Documentation check:
262 links, no link errors; staged diff/whitespace verification before commit.
Final source accounting: product +68 lines, tests -181, tools +1 (net -112).

`review-disposition.md` records findings, scope, reconstructed session continuity
and usage/cost. Original/copied source was unchanged during each invocation;
ten fixture files were preserved and the copy removed. The recovery is bundled
before removing its task-owned ref; `integration.json` records final commit and
accounting. No AB-9/10 implementation, push or PR. Pause for user recap.
