# Latest session — DOM work and bridge costs, 2026-11-09

## Delivered change

Base `fb448fac`, branch `milestone1`. Four product files change: `app.js`,
`plan_review.js`, `tree.js` and `table_controller.js`. Compatible overlapping
rows remain attached; Plan retains spacers and preserves scroll during structural
publication. Passive Follow caches height and rechecks a pending landing in the
existing geometry frame, respecting newer navigation. Read-only ticks skip an
unchanged prepaint; accepted reads and new progress still paint promptly.
Duplicate synchronous execution-pane paints are removed. Keep the existing
250/500 ms cadence, 25 ms collection, ACK custody and GC policy.

## Verification

- 2,289 interface cases pass; all six affected installed journeys pass, including
  both sizes for execution review and task shell. The frontend/API-floor checks
  and focused negative controls pass. Final product bytes match native wheel
  staging and the complete 303-file measurement freeze.
- Two initial-candidate findings were corrected: stale positive/zero geometry
  before resize observation, and temporary list shrinkage resetting Plan scroll.
  The latter explains all four initial execution/task-shell native failures.
  Original native assertions remain unchanged. An independent actual-window
  resize witness now matches baseline coverage without an extra read.
- Sandbox setup/attachment and one diagnostic selector failure are retained,
  along with initial product failures, under `build/dom-costs-20261109/builder/`
  and `review/`. Source/functional and measurement reviews are independent.

## Measurements and next discussion

[PERFORMANCE](PERFORMANCE.md#dom-mutation-and-bridge-follow-up--2026-11-09)
owns the methods, tables, attribution limits and source/evidence pointers.
All twelve diagnostic runs passed exact source/data audits and closed normally
with empty Jobs. The user reported activity before 11:47 Asia/Shanghai, so four
pre-idle Plan runs are excluded. Two fresh opposite-order quiet Plan pairs
reverse the apparent gain; no stable CPU/speed improvement or regression is
established. Inventory time/combined renderer CPU is effectively unchanged;
sampled renderer peaks fall about 6–9% in its one pair. Fewer DOM mutations are
verified separately from aggregate resource claims.

The separate post-DOM 25/200 ms collection pair reduces bridge threads
7,052 → 1,758 and execution host CPU 80.34 → 69.81 seconds, but elapsed time only
113.45 → 112.18 seconds. Renderer and worker CPU barely change. Ordinary ACK
call-thread CPU is 1.45 seconds at 25 ms and 0.25 seconds at 200 ms; drain and
window payload work dominate the remaining measured bridge-body CPU. These
whole-lifetime thread figures exclude caller-side creation and are not predicted
removable savings: custody cleanup must still execute.

Collection remains a CPU/resource tradeoff with extra clean-result latency.
If ACK reduction is pursued, the narrow candidate is a validated drain receipt
piggybacked on the next pull, cleaned before successor admission, with standalone
cleanup for terminal/no-successor/error/uncertain delivery. It needs explicit
custody/ingress review and tests, not deletion of ACK calls. Neither change is
implemented or approved. Slower local painting and frontend pulling are deferred.
Verification pipelining and durable/small-file batching remain outside this work.

## Operational context

No task-owned native process remains. Only owned profiles, targets and evidence
were used; measuring-session resources were not touched. Ignored evidence and
fixtures under `build/dom-costs-20261109/` are deliberately retained. No new
branch/worktree was created, and the older cadence recovery reference is untouched.
No further product/test edits are pending for this checkpoint.
