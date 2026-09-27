# Latest session — cold admission guidance

2026-09-27, `milestone1`, starting revision `0e4595e4`. The user authorized
two commits: CLI-DRIFT (`5e4bf87`), then DOC-PRECISION (this commit).
M1_PLAN owns the delivery record;
evidence lives in `build/cold-admission-followup-20260927/`.

CLI-DRIFT distinguishes observed file changes from confirmed incompatibility
and unavailable artifacts. One three-attempt policy retries validation only;
persistent drift gives retry guidance without reset advice. Provisional schema
errors recheck source stability, and failed cleanup prevents retry. Live-owner
availability failures also retain non-destructive guidance. CLI history admission
refusals use exit 3; unrelated later read failures retain exit 4. Creation,
reservations, task submission and effects are outside the retry operation.

The six new regressions failed on the baseline and passed after implementation.
Focused verification: 571 passed, plus 27 exact drift-count controls; all 12
import contracts pass. The final ordinary suite passed 5,410 tests, with 4
privilege-related skips and 34 headed deselections (`cli-ordinary.xml/log`).
Independent source review found no blocking findings (`cli-review.md`).
Retain `cli-red.xml`, the intermediate expectation-migration receipt,
`cli-focused-progress.xml` and `cli-drift-counts.xml` alongside final evidence.

DOC-PRECISION replaces TESTS' unverified already-visible-notice rationale with
the helper's actual readiness checks, and narrows DATABASE's per-connection
snapshot statement to connections opened through DatabaseConnectionOwner.
HistoryStore's two internal direct readers remain unchanged. Source comparison,
documentation links/diff checks and independent review cover this documentation-only
commit; the product/test evidence above remains valid.

Desktop Setup refusal mapping, cross-process exclusion and unrelated CLI
tooling remain excluded. AB-8 stays deferred; AB-7 focus loss remains an
environmental testing limitation, with no focus/DWM detector. Previous incident
closeout evidence remains under `build/admission-bridge-closeout-20260927/`;
historical failures and trace evidence must be retained. No task-created branch
or worktree needs cleanup, and no remote update is part of this task.
