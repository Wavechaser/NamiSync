# Latest session — Command recovery follow-up fixes

2026-09-26, `milestone1`, follow-up base `514d71d`. The user authorized these
validated AB-7R/S fixes as separate commits without a new checkpoint/register.
AB-8 remains paused; M1_PLAN still owns the delivered AB-7S record.

- `1aecc87`: preserve Plan again's icon and update its accessible action label.
- `4838c86`: adopt valid async results independently of cleanup ACK success;
  rename command policy metadata and migrate native/browser/tool consumers.
- Current follow-up: each issuing page owner retains the original bridge
  attempt's stable recovery handle. Remove copied recovery flags and the
  string-key Check helper; retain workflow stages and exact ownership guards.
  Lost direct delivery offers Check; unavailable communication offers normal
  close/reopen guidance; matching unreadable results remain visibly faulted,
  fenced and recoverable. Settled attempts emit no later observation feedback.

Native effect/receipt owners, wire, mutation non-replay, selection→Execute/D4,
fixed-error Cancel exception and read/lifecycle/resource bounds are preserved.
No timeout or communication failure establishes whether an effect happened.

Evidence is under `build/post-m1-8-ablation-20260925/`, with `followup-` names;
the initial diagnosis is `ab7s-followup-claims.log`. Each commit received fresh
independent review. Initial icon/ACK verification: 1,782 interface cases and
34 installed cases passed. Final handle verification: 7 focused cases and all
34 installed cases covered (29 unchanged passes in `followup-handle-headed.xml`,
5 corrected-fixture passes in `followup-handle-transport.xml`); 12 import
contracts and documentation link/diff checks pass. The final ordinary suite
passed 5,321 cases with 4 skips. Failed receipts remain: the policy migration
missed two performance
helpers, and the shared native fixture still counted callbacks instead of
observing delayed/checkable feedback. Those direct consumers are corrected.

Use unique external test basetemps and announce each foreground batch before
launch and when finished. Earlier AB-7 Setup `internal_error` and Plan-again
timeouts remain unexplained; this follow-up does not claim their cause or fix.
No new checkout/ref was allocated or deleted. Retain `codex/ab3-mapping` and
AB-6 recovery `56802606` for AB-10; prior AB-7 cleanup remains in
`ab7-cleanup.json`.
