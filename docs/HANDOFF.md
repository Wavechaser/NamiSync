# Latest session — Inventory reuse and visual controls, 2026-10-27

Work is on `milestone1`, from `c7868abd`, using execute-task, GPT-6.1 Sol
builders and fresh independent reviews. No worktree/recovery ref, push or PR.
M1-12, release and DOC-2 remain inactive. Inventory recents remain shelved.

- `d5b4a25` reuses confirmed Inventory views on navigation, invalidates on
  session/freshness changes, separates reads from scan activity, and retains
  the mounted table and expanded Details during replacement. Review found
  interrupted-highlight freshness and foreground queued-search races; the
  user approved the recurrence reorganization. Foreground ownership now uses
  its own session/navigation/invalidation, independently of cache freshness.
- `637a4d6` renders cloud indicators at 12 px with a 6 px filename gap, uses
  pinned Fluent Filled Play for Resume, and makes Go/Follow opaque icon-only
  eye/location-ripple controls. Existing action emphasis, accessible names,
  tooltips and forced colors remain. Exactly two documented dynamic-accent
  blends implement opaque hover/press states; other token restrictions remain.

V1: final 2,098 interface tests and all five installed Inventory/shell/execution
checks pass. V2: 45 focused checks, 2,505 department passes and three existing
skips, then all 12 owning token-policy tests pass after its narrow checker
migration; these counts overlap, not sum. All seven final installed checks pass,
including gallery light/dark/forced/reduced modes. Pinned icon archive and diff
checks pass. Independent reviews approve both implementations. Earlier native
Details-fixture mismatches, foreground refusals, report-size and token-owner
failures remain in evidence; no input, effect, or report-size guard was relaxed.

## Read-only queued-input investigation

V3 inspected committed `637a4d6` after the visual update. Nine bounded
production-app probes used controlled bridge/panel seams; no production or
tracked-test changes followed. Counts below exclude the initial view load.

| Sequence | Observation |
| --- | --- |
| Stale cache, held search, newer queued search, ordinary background refresh | Latest query survives; two search commands, no full opens. |
| Active, unreleased Verify receives a Gap during search, followed by background refresh | Unsent latest query is cleared; one search command, two full opens and three windows (including overlay); final query is the first submitted query. |
| Settings/return, or explicit Reload during delayed search | Queued latest query is retired; one search command and two opens. If the first command applies after Reload reads, its settlement triggers the necessary later observation. |
| Session replacement | New session/publication survives late browser receipt; old queued intent is retired. This mocked-host case does not prove native cancellation/isolation. |

The common full-load path clears pending/queued presentation state when it
supersedes foreground work. Submitted-command custody and unsent user intent
are different: no mutation replay or durable loss was demonstrated. Genuine
invalidation plus background refresh can silently lose newer same-context
unsent input. Navigation/session retirement is context-bound; explicit Reload's
queued-input policy needs a decision.

A small Inventory full-refresh decision coordinator on existing `tableReadOwner`
is a bounded option for a future round, not an established necessity. First decide
whether each reason preserves or explicitly retires queued input; a local change
may suffice. If coordination remains split across callers, a small shared decision
could centralize background invalidation, Reload, context retirement and
post-command observation. Do not turn the generic reader into a mutation queue
or remove later observation merely to reduce read counts. No coordinator, policy
implementation, or new public contract is authorized this round.

Review corrected the original released-scan Gap premise: released scans do not
normally receive a new Gap. Three earlier released-state Gap/selection probes
are conditional mechanism controls, not supported live interactions. The added
active-Verify probe establishes the reachable app-callback premise and includes
its deferred overlay, with bridge transport and server replies still mocked.
Real host FIFO/refusal timing, combined lost responses, broader live overlay
interleavings and actual renderer draft/focus remain unverified. The report
names the finite next-round proposal and preserves session/navigation/publication/
effect guarantees.

Evidence: ignored `build/gui-inventory-reuse-20261027/receipts.md`;
`v1-native-r3.txt`, `v1-interfaces-r2.txt`, `v2-native-r2.txt`,
`v2-departments.txt`, `v2-token-authority.txt`, and `v3-findings.md` with nine
`v3-*.txt` raw receipts and reproducible bounded scripts. No headed test remains
running. Investigation is read-only; await the user's next-round direction.
