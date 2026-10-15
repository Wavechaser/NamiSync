# Latest session — Verify hardening rebuild

2026-10-16. The user approved the async-read recurrence proposal and resumed
implementation, including bounded shell/execution foreground handling. Readiness
must land before or together with Refresh confirmation. Revalidate the saved
Inventory overlay correction against the same ownership/re-read rule during the
table rebuild. M1_PLAN owns scope, verification and commit boundaries.

## Checkout and preservation

Working branch: `codex/verify-ux-rebuild`, based on `milestone1` at `47a4bcae`.
Recovery branch `codex/wip-20261015-1621-verify-table` retains table candidate
`d1c3b325` and investigation `fb2253e2`. Never merge/cherry-pick these WIPs as-is.
Rebuild their useful changes into independently reviewed, verified commits.
The five pre-existing stashes and all raw receipts remain untouched.

The prior user handoff is preserved byte-for-byte at
`build/verify-ux-20261015/recurrence-input-handoff-01.md`. Investigation census,
evidence audit, independent review and recovery manifests share that evidence
root. The shell diagnosis is corrected: eight untraced cases refused foreground
after Plan again succeeded; native11 rejected its own trace overflow. Existing
failed receipts are incomplete checks, not product Plan-again failures.

## Immediate work and verification

Rebuild in atomic outcomes: harness correction; readiness reconciliation; table
alignment with overlay revalidation; Refresh warning; final ablation study.
Readiness tests must use real production release/pane/adoption paths: prior
scratch probes directly assign the Plan window and prove only consumer behavior.
Separate execution-fact observation from permission to repaint Plan. Keep
coalesced demand bounded, exact Start singular, and conflict/error recovery
actionable without mutation replay.

Harness `8a780ac` and readiness changes are implemented and independently reviewed.
Focused checks pass (70 harness, 59 frontend). The frozen combined candidate
passes all four installed shell/execution cases, both trace-enabled shell cases,
2,029 owning interface cases and 12 import contracts. Receipts are
`rebuild-{native,trace,interfaces}-20261016-01` under the evidence root; frozen
file identities are in `rebuild-freeze-20261016-01.json`. Final evidence review
approves both atomic outcomes. Readiness is committed as `b891285`.

The 34-path table rebuild is frozen in
`table-rebuild-source-freeze-20261016-01.json`, with readiness preserved and the
overlay rejection-settlement gap reproduced and corrected. Its focused checks
pass 357 cases plus 10 composition cases; the full ordinary gate passes 6,070
with four skips, and all 12 import contracts hold. Installed Inventory and four
gallery cases pass native01; execution passes both sizes in execution02 after
foreground refusals in native01. The shell's page acknowledgement expired
before the new foreground deadline; its two native waits are corrected, with
38 owning ordinary passes and installed shell default04/larger05 passes.
The extra Alt key-up and foreground-refused attempts remain retained.
The harness correction is committed as `c6dc0a0`, table alignment as `a594b3c`.
All named table gates are closed. Refresh is now implemented and frozen in
`refresh-builder-freeze-20261016-01.json`: exact Verify is primary, warned scans
retain captured scope, Cancel leaves reads/task untouched, and Confirm submits
once after current ownership checks. Focused06 passes 26; native01 passes all
nine cases, ordinary01 passes 6,073 with four skips, and all 12 import contracts
hold. Fresh source/native review has no findings; final delivery review precedes
the atomic Refresh commit. Next run the approved read-only ablation study, then
final documentation and fast-forward integration. Root owns subject/delivery docs.
`rebuild-recovery-accounting-20261016.json` accounts all 48 saved path entries;
the prior handoff, recovery refs and five pre-existing stashes remain preserved.

Prior Inventory/gallery/ordinary evidence remains recorded in M1_PLAN and must
be reused only where all producer, checker and driver dependencies remain
unchanged. Announce native-input runs; retain foreground/focus/hit guards. No gate
waiver is authorized. Final integration and the ablation study remain outstanding;
Refresh and table verification are complete.

Root owns delivery docs and integration; builders must not overlap shared files
or commit before independent review. M1-12, release, DOC-2, push/PR and backend
eligibility preservation through Refresh remain inactive.
