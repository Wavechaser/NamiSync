# Latest session — Plan GUI refinements

2026-10-04 on `milestone1`, starting from `99e65c8`. The user authorized the
three units in M1_PLAN: RF1 refusal disclosure, RF2 move groups/pills and reveal
navigation, RF3 Delete/Recase labels and pause/resume/two-click cancel controls. Each
unit is independently reviewed and committed before the next implementation.

RF1 adds bounded refusal origin and closed preflight codes to existing retained
execution review and admission responses. The page explains preflight,
commitment and other refusals, retaining the message after release/navigation.
No task-snapshot version, effect authority or recovery policy changed. Unrun
filesystem disposition does not imply a null dispatcher start timestamp.

Evidence is in `build/gui-refinements-20261004/`. The baseline installed default
task-shell passed. RF1 focused checks pass 628 cases and all twelve import
contracts pass. The ordinary run has 5,854 passes, four skips and one direct
fixture migration failure: the old service artifact double lacked a verdict.
Its corrected module passes 40 cases with dispatcher-failure/retry guarantees
unchanged; unaffected ordinary passes remain valid. Installed verification has
34 passes and one inventory foreground-focus failure before its action; that
unchanged case passes its isolated retry. All 35 cases are covered across these
receipts; no broad clean-pass claim is made. Independent source review approved.
Earlier focused assertion corrections and temporary-directory permission errors
remain recorded in the evidence directory.

RF1 is committed as `1865d66`; independent final evidence review approved.
RF2 is implementing from that revision. Prior groups now attach to surviving
scanned ancestors and carry source-owned count/destination facts; revisioned
reveal preserves selection and clears only obstructing query settings. The
renderer applies its destination scroll after installing the new virtual rows.
Projection/scale checks pass 311 cases and frontend/driver checks pass 367.
Both installed task-shell sizes pass. The ordinary suite has 5,866 passes/four
skips plus one exact host-command catalog migration; the corrected full host
module passes 84 cases; the other corrected catalog consumers pass 96. All 35
installed cases pass across the two task-shell cases, 25 unaffected cases and
eight corrected-catalog reruns. Independent review accepts the source and checker
migrations. Native
failed receipts and bounded geometry diagnostics are retained: the terminal-row
witness needed bottom-clamped visibility and one physical pixel of fractional
layout tolerance, without a product change.
The benchmark's seven pre-existing inventory-command omissions are recorded as
deferred in BUGS and `rf2-command-catalog-audit.json`; RF2 claims functional/scale
and native evidence, not a new quantitative benchmark receipt.
The user confirmed grouping by move target parent, not the moved directory
itself. Root destinations jump to the first canonical moved item. Informational
rows remain outside selection and byte totals. RF3 uses existing regular
pause/play plus pinned regular/filled Stop artwork; local Cancel arming lasts
five seconds, survives ordinary renders, and is discarded on task/session or
panel retirement. No later milestone, push or PR is authorized by this batch.
