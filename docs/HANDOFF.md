# Latest session — inventory feedback corrections

2026-10-02 on `milestone1`, starting from `0160f87` after M1-9 delivery.
The user requested three small follow-up fixes. No later checkpoint is activated.

## Changes

- Preserve newer observed state/release when the admitted-start receipt names
  the same session; still advance the task-list revision fence.
- For an unavailable view after a refused Refresh retains an older publication,
  advise checking the location/reconnecting its drive and Refresh. Ordinary
  read failures retain Reload guidance.
- Clear the transient Refresh message on confirmed admission. The existing
  current-scan indicator owns progress and terminal feedback; uncertain action
  recovery and visibility result counts remain intact.

## Verification and immediate context

Evidence is retained under `build/m1-9-20261001/minor-feedback-*` and independent
review in `review-minor-feedback.md`. Focused frontend checks pass 58 cases;
the external-temp ordinary interfaces run passes all 1,890 cases.
All 35 headed cases pass across the full run's 34 passes and the final manual-
focus inventory run (`minor-feedback-inventory-manual.log`, one pass in 22.70 s).
The first two inventory attempts stopped at `wait-foreground` before sending
clicks; those incomplete observations remain recorded separately.
The new probe exercises delayed admission after list discovery and drain
completion, failed reconciliation, stale-list fencing, refused-view guidance,
ordinary read failure and cleared Refresh feedback.

The first ordinary run used a workspace-local temporary directory, which the
custody tests correctly reject as a source-tree pycache location. Its 1,860
passes, two failures and 28 setup errors remain recorded; the corrected
external-temp run passes without changing product or test expectations.

M1-9 delivery and prior evidence remain recorded in M1_PLAN. This follow-up
changes page state/feedback only. TESTS.md still requires the interfaces headed
gate for desktop behavior. All native-input intervals have ended and their
test windows closed. No further measurements are needed. Stop for the user's
GUI review after these corrections.
