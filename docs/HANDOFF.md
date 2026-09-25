# Latest session — settle D2/D4 and narrow AB-7

2026-09-25; revision baseline `0c74ee7` on `milestone1`. User requested plan
revision and commit only. [M1_PLAN](M1_PLAN.md#post-m1-8-reduction-plan) owns
AB-1–AB-10; [POST_M1_8_ABLATION](POST_M1_8_ABLATION.md) owns the study/dispositions.
All implementation checkpoints remain pending; no product, test or operative
transport/evidence-policy change is delivered here.

D2 is settled: remove page-side elapsed-time deadlines that abandon mutating
command results or automatically replay mutations. Keep delayed feedback, bounded
observation recovery, command identity/duplicate-effect protection, original-result
retention/recovery and lifecycle/resource/observation timeouts. Native delivery
failure after an effect remains possible. Exhausted/failed observation shows
explicit "outcome unavailable", not a fabricated operation verdict or indefinite
unqualified "working…"; later valid observation can recover the original result.

AB-7 reuses the delivered CommandSpec/bridge/DocumentChannel admission/completion
path and existing effect receipts. No whole-command-system redesign, parallel
result protocol or unlimited retention. Its regression gates cover slow results,
post-effect delivery loss, observation exhaustion/late recovery, duplicates and
Close/shutdown custody. AB-8 now depends on AB-7; no pending D2 decision remains.
D4 highlighting/focus and checkbox separation are explicitly retained without
feature reduction. Other exclusions and deferred decisions are unchanged.

Verification: inspected current command policy, asynchronous transport source
locations and BRIDGE's post-effect failure contract; reviewed the four-document
diff for stale decisions, dependency consistency and failure truthfulness. Link,
plan-shape and diff checks are recorded in
`build/post-m1-8-ablation-20260925/plan-revision-checks.json`. No runtime tests or
benchmarks are needed for this planning-only revision. Earlier study evidence
and all raw JSON remain untouched.

Next: activate AB-1, the documentation pass; implementation is not authorized by
this revision. Preserve pending DOC-2, unrelated refs/stashes and raw evidence.
No push, PR or branch rewrite requested.
