# Session Handoff

Status (2026-08-14): the progress-only drain behavior checkpoint has landed.
Each task retains one fixed 150 ms deadline from first progress-only
availability; replacement, supersession, and retry cannot restart it, and the
original long-poll deadline remains the outer cap. Reliable, `Gap`, terminal,
recovery, close, and supersession wake immediately. The 174 focused
drain/command/host checks pass. SH-G-8 remains open for realistic-payload
transport-custody calibration, a limit fixed in a later commit, and an
independent holdout. BR-G-45 separately remains open for the
complete 100,000-subject terminal artifact set and aggregate completed-task
retention policy. Shell-owned SH-G-15 separately remains open for version-bound
whole-runtime containment. Slices 5-8 remain product work.

## Contract Realignment

- SH-G-8 and BR-G-42's event clause now count one identity-deduplicated deep
  Python graph rooted only at dispatcher replay, subscriber, and adapter task
  queues. Corrected evidence uses distinct realistic path/detail values,
  reports each root class and the union, exercises the ordinary event envelope
  and maximum reachable no-`Gap` custody shape, calibrates first, freezes a
  limit in a later commit, then applies it to an independent holdout.
- BR-G-33/SH-G-8 now require a single non-extending 150 ms server linger when a
  drain first sees progress alone. Replacement progress does not slide the
  deadline. Reliable, `Gap`, terminal, close, supersession, and recovery values
  wake immediately. This behavior and its stale-prequeue, supersession/retry,
  fixed-anchor, immediate-wake, ordering, and cursor regressions have landed.
- BR-G-45 owns the entire subject-scaled completion set: core
  `Terminal(OperationResult.items)`, adapter terminal event view,
  `SessionRecordView`/`OperationResultView.items`, serialized/native return,
  browser retry/presentation values, and post-callback retention. It also
  requires a byte policy across completed tasks; the current 48-task count is
  not treated as one. The policy must preserve reviewed plans, retry truth, and
  a truthful degraded-history fallback. No policy, calibration ceilings, or
  holdout exists yet.
- SH-G-15 owns complete headed-runtime containment. Its future evidence records
  absolute cold peak and settled plateau plus symmetric repeated/long warm
  marginal and plateau growth. Telemetry is bounded or streamed outside the
  Job, final serialization occurs after measurement, and each member records
  PID plus creation time, role, private bytes, threads, handles, and topology.
  Calibration fixes ceilings and a predeclared headroom rule before independent
  holdouts. A changed Windows/Python/CLR/pywebview/WebView2 tuple has no inherited
  pass and requires explicit restatement. No calibrated limits or holdout
  exists yet.

`M1_BRIDGE.md` remains the sole bridge protocol and BR-G authority.
`M1_SHELL.md` owns SH-G-8/SH-G-15 definitions, delivery placement, packaging,
and release evidence. The split does not weaken queue capacities, ordering,
`Gap`, terminal reconciliation, terminal-session release, or explicit task
close.

## Prior Reference Run, Reclassified

The valid 2026-08-13 run tested archived commit
`288969426d6e005bac7a7e540e0cfdbacf28f9eb` with matching archive,
reference-machine, and runtime profiles. Its temporary output was
`%TEMP%\namisync-bridge-event-benchmark-final3.json`, SHA-256
`FF40563C6E720D189130D28D59B48505716C8E0DB2A4EFD1C91D8452BD4DF9E4`.
It completed all four sessions with 6,000 `Progress`, 600 exactly-once ordered
`ItemOutcome`, 12 `StateChanged`, four `Terminal`, and four terminal records.
Progress reached 1,500 per task monotonically, no `Gap` occurred, producer rates
were 100.043 Progress/s and 10.004 reliable items/s, and shutdown completed
without a recorded failure.

- Progress latency: 4 ms p95, 17 ms maximum.
- Reliable/terminal latency: 5 ms p95, 28 ms maximum.
- Whole-Job idle baseline: 287,506,432 bytes.
- Whole-Job sampled peak: 354,881,536 bytes.
- Incremental peak: 67,375,104 bytes (64.254 MiB).
- Sampling: 50 complete baseline samples and 3,006 complete fixture samples
  over 60.100 seconds, with a 21.042 ms maximum interval.

The event, identity, latency, cadence, and shutdown facts remain valid evidence
about that run. Its whole-Job delta is neither corrected SH-G-8 transport
custody nor a valid SH-G-15 containment result: the old contract used one idle
delta rather than absolute cold/settled and repeated/long warm plateaus, had no
calibration/frozen-limit/independent-holdout sequence, and retained benchmark
telemetry inside the measured child. It also cannot set BR-G-45's terminal
artifact ceilings. No gate is closed or newly failed by reclassification.

## Memory Triage To Preserve

Best-effort inspection found one stable nine-process Job membership with no
missing member throughout the old sample series. Private memory was 288,976,896
bytes at fixture start, about 301.2M by +1 s, 310.1M at +5 s, 323.7M at +20 s,
330.5M at +30 s, 338.1M at +50 s, and 350.0M at +60 s. The 354,881,536-byte
peak occurred near completion; the final sample remained 354,574,336 bytes.
The former 16 MiB line was crossed near +2.68 s, and the largest periodic drop
was about 9.1 MB. Aggregate samples cannot attribute that broad, stepwise
growth to a member because the old harness discarded per-PID byte values after
summing them.

The diagnostic deep sizer reported only 289,147 bytes at peak across the live
Python queue/terminal roots, over 1,998 samples with a 163.516 ms maximum
interval. That number is not corrected custody evidence: it mixed terminal
records into the root set, used short/shared benchmark values, and did not
establish the maximum reachable no-`Gap` shape. The child also retained 6,620
decoded latency/event samples until final evidence serialization; the final
JSON was about 3.56 MB, excluding Python object overhead. Runtime warm-up,
renderer/CLR/native state, IPC, allocator behavior, and benchmark telemetry may
all have contributed to the Job trend, but none is proven causal.

Later diagnostic reproductions, still outside any acceptance contract, observed
roughly 62–66 MiB whole-Job growth. Per-process probes attributed about 63–68%
of that growth to an Evergreen WebView2 renderer, with most of the remainder in
the Python/.NET host. The shape included a large fixed turn-on cost plus smaller
duration- or call-correlated growth whose plateau is not yet proven. The
benchmark itself contributed several MiB, and runtime/topology variation moved
the totals between runs. These observations narrow where to measure; they do
not prove the residual is either a leak or harmless bounded warm-up.

Separate 100,000-subject result probes measured roughly 21–30 MiB for one
realistic item set before populated detail values and before simultaneous
core/adapter/browser copies. That makes multiplicative completed-task retention
a real BR-G-45 design input, not a reason to adopt those numbers as ceilings.

Earlier terminal/shutdown failures are not memory evidence. They were traced to
the `plan`/`sync-plan` validator mismatch, a redundant blocking UI Automation
wait, live polling of a large JSON file on Windows, and response/close
acknowledgment races; those paths were fixed or removed before the valid run.

## Immediate Next Work

1. Replace the old deep-size diagnostic with an explicit SH-G-8 custody
   instrument. Use production offer/observation paths, distinct realistic
   path/detail values, exact replay/subscriber/adapter roots, strong identity
   deduplication, achieved high-water marks, and a quiescent maximum no-`Gap`
   snapshot. Bound or stream telemetry and perform no growing full serialization
   during the measured interval.
2. Record calibration without a pass/fail limit. In a later commit freeze the
   corpus, allocation method, interpreter, ceiling, and headroom; only a later
   independent artifact may close SH-G-8.
3. Design BR-G-45 before clearing terminal state. Measure every simultaneous
   core/adapter/browser representation at 100,000 subjects and decide what may
   survive presentation/release when history is degraded. Then freeze both
   per-completion and aggregate limits before holdout.
4. Build SH-G-15 as a distinct artifact and `passed` field, not an extension of
   SH-G-8's result. Move raw telemetry ownership outside the Job; retain
   per-PID/role/thread/handle/topology series; use equal pre/post windows; add
   repeated and long warm fixtures plus cold absolute/settled phases. Diagnose
   by process role and event-free controls, but never subtract a control or
   retune a frozen bound after seeing holdout data.

The diagnostic matrix before calibration is exact: run event-free controls at
the same 15/30/60/120/300-second durations; run consecutive 60-second fixtures
in one unchanged host; record fixed post-idle windows plus a diagnostic-only
forced-GC/renderer heap snapshot; sweep event rate and 150 ms batching without
changing correctness; then repeat on a second qualifying machine or after a
recorded WebView2 update. Use the matrix to choose hypotheses and a headroom
rule, never to subtract a friendly control from acceptance or declare a plateau
from one duration.

## Verification

- `tests/interfaces/web/test_drain.py`: 48 passed.
- `tests/interfaces/web/test_commands.py`: 77 passed.
- `tests/interfaces/web/test_host.py`: 49 passed.
- Total focused Python evidence: 174 passed. No new custody, BR-G-45, SH-G-15,
  or headed benchmark result is claimed by this checkpoint.
- Required before commit: active-doc contradiction search and `git diff --check`.

## Immediate Context

The 150 ms linger is implemented; the corrected custody instrument is not. Do
not reuse the old 67,375,104-byte delta as SH-G-8 failure, SH-G-15 calibration
limit, or BR-G-45 evidence. Preserve explicit
terminal-session-release versus task-close authority while designing aggregate
terminal retention, and keep all three gates open until their own frozen
holdout evidence exists.
