# Latest session handoff

## Plan presentation polish (2026-09-18)

Follow-up: the user reported selection failures, initially correlated with
OneDrive/long paths. Dev logs confirmed internal errors in all three mutation
commands. A short local nested-directory fixture reproduced the cause:
`apply_plan_projection_selection` compared subtree eligibility against one for
an operation-bearing directory. It now subtracts immediate-child rollups before
validating own eligibility. No cloud/path/safety policy changes were made.
Focused projection/Plan checks pass (52); workflows+interfaces pass (2,503,
one skipped), including the 120,000-operation scoped-mutation witness. Installed
checkbox coverage now includes nested directories and individual, whole-view,
and highlighted selection roundtrips. The dev app needs a restart to load the
Python correction. The user confirmed selection now works on the reported
Optics plan, with a remaining noticeable refresh delay. This was not profiled
on that real plan and is not claimed fixed. A diagnostic rerun on the existing
120,000-row fixture measured scoped mutation at 1.205 s and highlighted mutation
at 1.053 s; these are fixture observations, not real-plan latency guarantees.
Installed nested-plan checks passed at both sizes (two). A prior completed
run failed the native second-Tab focus assertion; unchanged repeat passed,
with the assertion retained. New test setup also corrected a stale row DOM
reference after highlight refresh. Follow-up evidence directories are
`k-selection-neighborhood` and `k-selection-native-repeat` under the root below.

Shared byte labels retain four significant digits and trailing zeros, with
exact small-byte integers and integer-safe unit rounding. GUI-K1 is committed
as `4ef526e`; numeric sort facts are unchanged.

Production Plan columns now read Select, Name, Action, Checksum, Size, Modified,
Notes. Sort targets fill padded header cells with right-aligned chevrons.
Search/Clear use compact Setup-style inset controls. The details card aligns
Verify on/off and Trash/Additive with the two path rows. Status detail shows
selected counts, required bytes and combined planning issues.

Footer idle/success text is hidden. Warnings, errors and in-flight feedback
remain on the same row, left of Plan again/Execute. Task tabs show selected
operation counts, semibold state, compact detail/path spacing, roomier progress
spacing and adjusted markers (live tasks 2rem, Settings 1rem). Detail/path/
progress fields extend under the close button; title keeps its reserved space.

Verification: interfaces department 1,693 passed, one skipped. Final focused
frontend/token/helper checks: 63 passed. Installed default/larger checks: two
passed, each covering empty and populated plans, aligned semantic settings,
column order, full-cell sorting, inset icons and same-row footer feedback.
Final focused/installed reruns cover the footer clarification and settings
margin correction after the department run. Screenshot inspection and separate
adversarial review found no remaining regression. Full repository suite was
not run for these presentation-only changes.

Evidence root:
`C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/`
contains `k-interfaces` and `k-headed-final`. Local focused results are under
`build/pytest-gui-k-focus3`; screenshot is
`build/evidence/execution-confirmation.png`. Selection, safety, execution
admission, gallery order, M1-8 execution results and M1-9 inventory review are
unchanged/out of scope. GUI-K is recorded in M1_PLAN.
