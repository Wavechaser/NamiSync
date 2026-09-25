# Latest session — native test interaction prerequisites

2026-09-25; `milestone1`, delivery base `1cb75fb` (AB-5). AB-1–5 are integrated;
M1_PLAN retains their commit identities. The user requested sorting the picker
and gesture issues before continuing AB-6. No product files changed in this
session; AB-6 reload containment and AB-7–10 remain pending.

The folder-picker helper now verifies exact Unicode edit readback, posts one
confirmation and reports `dialog_closed`, leaving the actual selected-path
verdict to the transport fixture. Wrong readback or ownership refuses the post;
a still-open dialog does not trigger another click. The final focused controls
pass, and executing the old helper against the open-dialog control produces
two posts and the expected failure. This repairs the automation assumptions;
the original intermittent wrong-directory cause remains unconfirmed.

Gesture attempt 06 delivered all five native inputs to an owned foreground/
focused window and closed cleanly. F5, Ctrl+R and Alt+Left did not navigate;
mouse Back moved through fragment history without replacing the document.
Right click produced a DOM context-menu event with no sampled owned native
popup; other menu-rendering paths are not excluded by that observation.
The user saw attempt 05 and then clicked another window during its hold;
the causes of attempts 01–04 remain unknown. Native input checks now have
documented brief uninterrupted foreground-input intervals.

Verification: 33 final focused tests, six installed transport cases, 1,771
interface department tests and the complete 33-case headed gate passed.
Fresh independent H1/H2 source/evidence reviews and documentation link/diff
checks passed. Do not infer AB-6 completion from these
prerequisites. All evidence, including failed diagnostics and the original
picker failure, remains under ignored `build/post-m1-8-ablation-20260925/`;
`harness-verification.md` maps receipts and evidence reuse.

For eventual AB-6 work, read `ab6-design.md` and refresh its affected helpers.
Pinned pywebview reinjects after canceled navigation/popup while retaining the
same document; a second `before_load` alone cannot identify replacement.
Preserve original mutation outcomes, worker custody and clean close; D2 and D4
remain settled. The saved `56802606` recovery contains only superseded planning/
handoff state, not product changes; do not merge or cherry-pick it. Keep that
branch, the AB-3 worktree/branch and all raw evidence for AB-10 accounting.
