# Latest session — AB-7 review and recovery tiering (synopsis)

2026-09-26, `milestone1` after AB-7 (`6287db0c`). Documentation-only: the user
asked for a read-only review of AB-7 and a tiering assessment, recorded as
[POST_M1_8_ABLATION §14](POST_M1_8_ABLATION.md#14-ab-7-follow-up-review-original-outcome-recovery-2026-09-26).
No product, test, tool or M1_PLAN change.

Synopsis: the requirement to learn an original outcome without repeating its
effect stands, but retaining transport responses and observing them is
redundant. It created a third outcome record while the domain receipts and
drain start cache became reachable only from tests, and it reports a healthy
command still `pending` after about 5.4 s as "outcome unavailable". The
recommendation makes domain records the single authority: user-triggered
identical resend for `command_id` commands, resend or settlement for
Close/release/control, and authoritative re-read for view and cosmetic
commands, as one declared per-command recovery column with no outcome timers
or cross-surface fences. It is a proposal awaiting the user's decision.

Verification: findings were traced in the AB-7 diff, current source and the
retained AB-7 evidence; no tests or experiments were run. `git diff --check`
and local documentation-link checks passed.

Operational context: AB-8 remains paused and unauthorized; decide §14 before
AB-8 freezes its snapshot shape, which currently preserves AB-7's outcome
states. AB-7 cleanup is recorded in `ab7-cleanup.json`. Keep the AB-3
worktree/ref `codex/ab3-mapping` and AB-6 recovery `56802606` for AB-10
accounting. Use unique test basetemps outside the source repository and
announce foreground batches. Two AB-7 installed observations (Setup start
`internal_error`, Plan-again timeouts) remain unexplained; do not claim them
fixed.
