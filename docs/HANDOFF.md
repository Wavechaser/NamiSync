# Session Handoff

Status (2026-08-13): the early-shell realignment through checkpoint 10 is
implemented. `M1_BRIDGE.md` is the sole protocol and BR-G authority; terminal
delivery releases observation/session authority without destroying the retained
plan; installed real-WebView2 tests own browser behavior; Node probes are
supplemental. SH-G-8 remains open solely because the valid reference run
exceeded its fixed whole-Job private-memory ceiling. Slices 5-8 remain product
work.

## Delivered

- Split terminal-session release from explicit task close. Terminal callback
  failure retains exact retry authority, release/close share compensating
  cleanup, and only explicit close drops the reviewed plan and frees the task.
- Added one typed post-logging `startup.failed` traceback before fail-closed
  teardown, without allowing diagnostic failure to replace startup truth.
- Ratified explicit-`Gap`-only recovery and command-specific `start_plan`
  identity with named regressions; numeric sequence holes do not recover.
- Reduced `M1_SHELL.md` to delivery, packaging, and SH-G ownership and moved
  exact protocol/error/retry/lifecycle authority into `M1_BRIDGE.md`.
- Migrated named browser behavior to the installed production bridge and
  renderer in real WebView2. All seven Node-backed probes are marked
  supplemental and discover only a declared `node` on `PATH`.
- Added literal witnesses for every approved public-view dataclass and crossed
  every witness plus hostile return types through production dispatch.
- Rebuilt the ordinary SH-G-8 fixture around four tasks, 60 logical seconds,
  6,000 `Progress`, 600 reliable items, terminal truth, no normal `Gap`, and
  independently observed dispatcher/adapter queue high-water bounds of 64.
- Added the archived-wheel 60-second headed reference harness and hardened its
  evidence boundary. During live diagnosis it exposed and fixed a production
  client defect: real terminal records use `PLAN_KIND == "sync-plan"`, while
  the validator and synthetic fixtures had accepted only the invented `plan`.
  Remaining plan-record witnesses now derive from the real constant.

## SH-G-8 Reference Attempt

The valid run tested archived commit
`288969426d6e005bac7a7e540e0cfdbacf28f9eb`; archive, reference-machine, and
runtime profiles matched. The recorded worktree contained only the two approved
temporary root references, which final cleanup removed. The run completed all
four sessions with 6,000 `Progress`, 600 exactly-once ordered `ItemOutcome`, 12
`StateChanged`, four `Terminal`, and four terminal records. Progress was
monotonic to 1,500 per task, no `Gap` occurred, producer rates were 100.043
Progress/s and 10.004 reliable items/s, and browser/native shutdown completed
without a recorded failure.

The uncommitted temporary output was
`%TEMP%\namisync-bridge-event-benchmark-final3.json`, SHA-256
`FF40563C6E720D189130D28D59B48505716C8E0DB2A4EFD1C91D8452BD4DF9E4`.
The durable facts needed for triage are recorded below; the temporary JSON is
not treated as a linked passing artifact.

- Progress latency: 4 ms p95, 17 ms maximum.
- Reliable/terminal latency: 5 ms p95, 28 ms maximum.
- Whole-Job idle baseline: 287,506,432 bytes.
- Whole-Job sampled peak: 354,881,536 bytes.
- Incremental peak: 67,375,104 bytes (64.254 MiB), versus the fixed
  16,777,216-byte ceiling.
- Sampling: 50 complete baseline samples, 3,006 complete fixture samples over
  60.100 seconds, with a 21.042 ms maximum interval.

Every acceptance predicate except whole-Job memory passed. The failure is
intentionally non-diagnostic under the contract, so no product leak is claimed,
no capacity was raised, and no budget was relaxed.

## Memory Triage Notes

Best-effort inspection of the final artifact found one stable nine-process Job
membership with no missing member for the entire sample series. Private memory
was 288,976,896 bytes at fixture start, rose to about 301.2 million bytes
within the first second, then grew broadly and stepwise rather than as one short
spike: approximately 310.1M at +5 s, 323.7M at +20 s, 330.5M at +30 s,
338.1M at +50 s, and 350.0M at +60 s. The 354,881,536-byte peak occurred near
fixture completion; the final sample remained 354,574,336 bytes. This is
consistent with retained or warmed runtime state, but aggregate Job samples
cannot identify which member owned the growth because the harness discards
per-PID byte values after summing them. The ceiling was first crossed around
+2.68 s, and later periodic drops (the largest about 9.1 MB) did not reverse
the sustained trend.

The diagnostic deep-size sampler saw only 289,147 bytes at peak in the live
Python EventHub/TaskRegistry queue graphs across 1,998 samples; its own maximum
interval was 163.516 ms. That makes those retained Python queues an unlikely
explanation for the 67.4 MB Job delta, but the diagnostic is
not acceptance evidence and does not measure renderer, CLR, pywebview/native,
IPC, allocator slack, or benchmark telemetry. In particular, the child retains
6,620 decoded latency/event samples until final evidence serialization; the
final JSON is about 3.56 MB, and its Python object overhead was not separately
measured. Benchmark telemetry or runtime warm-up may therefore contribute, but
neither is proven causal.

Earlier apparent terminal/shutdown failures are not usable memory evidence.
They were traced separately to the `plan`/`sync-plan` validator mismatch, a
redundant blocking UI Automation wait, live polling of a large JSON file on
Windows, and response/close acknowledgment races. Those defects were fixed or
removed before the final valid run; diagnostic close tracing that rewrote the
large evidence object was also absent from it.

Recommended next triage, without changing acceptance accounting:

1. Record per-PID private-byte diagnostics alongside the existing aggregate
   samples to identify whether Python, WebView2 renderer, or another Job member
   dominates and when its growth begins.
2. Add diagnostic-only Python heap/tracemalloc, CLR/native, and precise
   WebView2 used-heap series correlated to the same monotonic clock. Bound or
   stream the raw evidence recorder so its retained-object cost is separately
   observable.
3. Run repeated archived-commit trials plus an event-free 60-second control on
   the same reference profile to separate ordinary WebView/runtime warm-up from
   event-correlated retention. Do not subtract that control from the normative
   whole-Job result or change the 16 MiB ceiling without an explicit contract
   decision.

## Verification

- Focused dispatcher/web/service lane: 352 passed; three supplemental Node
  probes skipped because Node is absent.
- Full default suite: 2,187 passed, nine skipped, 27 headed deselected. Seven
  skips are supplemental Node probes; two are environment-only reparse/symlink
  privilege skips. No BR-G or SH-G node skipped, xfailed, or xpassed.
- Real headed WebView2 lane: 27 passed, 566 non-headed tests deselected.
- Full suite with all markers enabled: 2,214 passed, nine permissible skips.
- Import Linter: all 11 architectural contracts kept, zero broken.
- The valid standalone benchmark result above is the current reference
  evidence; it exits nonzero only because the fixed memory ceiling failed.

## Immediate Context

SH-G-8 stays open. Preserve the explicit terminal-session-release/task-close
split and the exact `sync-plan` terminal identity. The next useful work is the
diagnostic attribution above or Slice 5's user-facing plan surface; do not call
the conservative whole-Job overage a bridge leak without causal evidence, and
do not manufacture gate closure by relaxing its budget.
