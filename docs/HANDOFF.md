# Latest session — shared review consolidation

2026-10-16. The user reviewed the stopped RV2B candidate and authorized its
bounded rebuild, plus a separate fix for the enabled copied-Verify action when
execution copied nothing. [M1_PLAN](M1_PLAN.md) owns RV0–RV6 and dependencies.
Inventory remains a separate panel using shared infrastructure. M1-12, release,
DOC-2, push and PR remain inactive.

Integrated: `01089be` (rules/register), `fd461e5` (ordinary copied Verify) and
`e3d1fb7` (shared server review mechanics). Current rebuild branch
`codex/review-controller-rebuild` starts at `e3d1fb7`; recovery `0556322` is
preserved on `codex/wip-20261016-2159-review-controller` and is not ancestry.
No WIP may be merged or cherry-picked as-is.

RV2B now shares browser viewport/window-demand/generation/settlement/reveal
mechanics. The finite transition reconciliation preserves tree request retirement
and Plan's app-owned reads across panel reuse, fixes short-window resize and
settled-frame scheduling, restores scroll before active-row choice, and updates
direct probe/catalog/instrumentation consumers. No tests retired; production
net reduction is 172 lines. Evidence is under
`build/review-consolidation-20261016/`: `rv2b-transition-rebuild-01.md`,
`rv2b-candidate-rebuild-01.md`, `rv2b-freeze-manifest-01.json` and
`rv2b-review-01.md`. The independent user review remains at
`build/review-rv1-rv2b-20261016/review-rv1-rv2b-01.md`.

Current B verification: all 103 owning tests, 2,459 interfaces/tools tests
(three unchanged Windows privilege skips), and 12 import contracts pass.
Seven installed cases passed native01; both Execution Review sizes passed
native02; Inventory passed native04. All 13 frozen inputs and the installed runs'
286 source/283 package-file identities match.
Native01's three failures and native03's refusal have explicit foreground
evidence. Native02 Inventory timed out before context-escape readiness; no Escape
was sent. Its receipt lacks the popup/trusted-event/document-focus facts needed
to establish a cause. Preserve its complete fixture and failed receipt even if a
later run passes. `rv2b-native02-diagnosis-01.md` records those limits.

Next: finish B's independent final review, then commit/integrate.
The known-empty copied action has a finite design in
`rv1-empty-action-design-01.md`: one workflow-derived retained Boolean; only
identity-admitted explicit false disables with guidance, unknown retains server
admission. No new readiness read/pump. Revalidate overlapping consumers after B.
Then continue shared app read ownership (read-only `rv2c-design-01.md`), Inventory
Follow/Go, narrow snapshot/attempt sharing, catalog/test/doc reductions and RV6.
Source/test writers are serialized; root owns docs/Git/native gates.

Final integrated ordinary/RV6 gates remain pending. RV1's earlier full suite had
one boundary failure corrected before integration; do not call it a green full
suite. Its final workflow/interface and installed gates and Stage A's complete
gates are recorded in their candidate/review/integration receipts.

Keep both stopped recovery refs, the original user handoff
`build/verify-ux-20261015/recurrence-input-handoff-01.md`, prior 48-entry accounting,
both ablation reports and all five pre-existing stashes. Keep RV1 native01's
unexplained larger fixture and native02's incompletely diagnosed larger receipt.
No evidence cleanup or remote operation occurred. Announce native input runs
and preserve foreground/focus/hit guards.
