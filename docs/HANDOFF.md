# Latest session — AB-7R command recovery reduction

2026-09-26, `milestone1`, base `895710fb`. AB-7R is delivered as a separate
reviewed reduction checkpoint before AB-8. [M1_PLAN AB-7R](M1_PLAN.md#ab-7r--reduce-command-recovery-and-uncertainty-state)
owns the compact outcome record. **AB-8 remains paused and unauthorized.**

Five current-state commands drop original-response retention/observation;
revisioned Refresh or deliberate folder rechoice rejects stale adoption without
claiming the old effect settled. Eleven protected commands keep original
observation, with bounded feedback/Check and the original promise as sole result
adopter. Preserve true dependency fences, duplicate protection, D4 and resource
bounds. No automatic replay, new protocol or native domain-owner changes.
Production is net 55 lines smaller; tests net 157 larger. The study's blanket
receipt-resend proposal remains rejected because receipt lifetime and adapter
paths leave gaps. POST_M1_8_ABLATION §14 records the qualified disposition.

Verification: ordinary run 5,323 passed, 4 skipped and one obsolete policy
assertion subsequently corrected. Current full interfaces rerun: 1,785 passed;
unchanged domain/tool results retained by dependency. Installed headed suite:
34 passed on frozen corrected inputs. Twelve import contracts and independent
adversarial source/evidence review passed. Final documentation link/diff checks
passed. Evidence and failed receipts remain under
`build/post-m1-8-ablation-20260925/ab7r-*`; start with `ab7r-verification.md`,
`ab7r-frozen-inputs.json` and `ab7r-review.md`. No new checkout/ref was allocated.

Use unique test basetemps outside the repository. Announce foreground batches
before launch and when finished. Two earlier AB-7 installed observations (Setup
start `internal_error`, Plan-again timeouts) remain unexplained; these passing
journeys do not establish their cause or claim a fix. Retain the AB-3 worktree/ref
`codex/ab3-mapping` and AB-6 recovery `56802606` for AB-10 accounting. Prior AB-7
cleanup is in `ab7-cleanup.json`.
