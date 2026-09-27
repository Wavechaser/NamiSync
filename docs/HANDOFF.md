# Latest session — executor and verifier performance assessment

2026-09-27, `milestone1-adelbert`, measured revision
`0e4595e4142fc78cfbf8e274832520a4344f3b5e`. The user authorized assessment and
temporary fixtures only, with Luna assistance; no production changes or
optimization implementation. The initially clean checkout was switched from
`milestone1` to the requested existing branch. The user subsequently requested
verifier investigation and a documentation commit of investigations so far.
No merge or remote update was performed. PERFORMANCE owns results and method;
CHANGELOG records delivery. Production optimization remains unauthorized.

At user-review follow-up the branch was at `6de6d1c0` (two existing commits beyond
the measured revision); the agent did not move it. Core/executor source is
unchanged across those commits. Historical rig/test receipts retain their original
revision. The original exact-HEAD audit refusal is preserved in
`review-followup-audit.log`; explicit review-followup checking permits only that
ancestor advancement with unchanged core/executor code.

The verifier follow-up measured `6de6d1c002fa0b9f22a4d76c25519b6d0dbfae8a`
using the same read-only F: corpus. Five samples per size band plus two separate
instrumented passes and three no-tap controls produced 30 fully verified samples
in eight rig invocations. Small-file median: 3.652 s; 4 GiB: 1.926 s. A separate
small pass measured 4,000 GetVolumePathNameW calls at 1.1566 s versus 0.5209 s
inside ReadFile. Four handle snapshots per file cost only 0.0786 s combined.
RootAuthority is already reused in the verifier context; repeated native API
binding and consecutive opening snapshots offer additional smaller candidates.
Post-copy readback shares the same classifier/native reader. No-tap comparisons
were sequential, not interleaved, and do not isolate tap cost.

`verifier_baseline.ps1`, `verifier_diagnostic.py`, `verifier-*.json/log` and
`verifier_audit.py` retain commands, raw data and count/result checks. Existing
rig/native/engine tests pass **148/148** (`verifier-focused-final.xml/log`). The
first attempt's 135 setup errors were denied access to pytest's default external
temporary directory; its failed receipt remains. The rerun used a new workspace
basetemp and passed, with a non-fatal pytest cache permission warning. The
executor audit now filters executor report envelopes explicitly so verifier
reports cannot contaminate its historical 47-sample count.

User follow-up added preflight to the source review. It reuses authority values
but performs a full admission per distinct subject; a flat unique 1,000-COPY
plan has 2,004 full admissions including root/capacity observations, plus other
native calls. This count is source-derived, not a preflight timing result.
Scanner brackets enumeration rather than fully admitting every file. PERFORMANCE
records the distinction and the resolution-order constraint on leaf-check reuse.

Evidence is retained in `build/executor-assessment-20260927/`, with directory
conventions in its AGENTS.md. Baseline/followup/finalcases scripts preserve exact
commands. Raw rig JSON/logs, synchronous stage timings, supplementary profiles,
source/fixture/environment receipts and `summary.json` remain local ignored
evidence. Reruns need fresh target/report names. The temporary summary reader was
corrected to handle the rig's diagnostics-off shape; raw reports were unchanged.

Five F: → G: bands ran five times each with readback. Small-file median is
28.248 s for 1,000 × 4 KiB; 4 GiB median is 2.287 s (1,791.3 MiB/s).
Three reverse 4 GiB samples gave 1.987 s median. Stage instrumentation found
27,000 root revalidations costing 16.832 s inclusive in a 27.901 s small-file
run; supplementary profiles counted 1,401 spelling validations per file.
Temp finalization, rename and directory flush were much smaller. Whole-tree
and four-hardlink-UPDATE cases completed and read back successfully.

The 10/1/0.1 ms interleaved polling probe showed no material backend gain.
Diagnostics-off small-file runs still took about 27 s. User review corrected the
original optimization ordering: preserve necessary fresh evidence, not current
probe counts/APIs. `root_probe_review.py/json` times 1,000 read-only admissions:
2,000 GetVolumePathNameW calls consumed 0.577 of 1.131 s total. A separate root
open/identity/attributes/close probe had a 30.4 microsecond median. Observed st_dev
matches the full handle serial; its low 32 bits match existing volume identity.
PERFORMANCE now prioritizes immutable authority reuse, fewer native calls,
admission per access/effect step and possible root-handle binding. Explicitly
resolve current second-anchor observation, lstat classification, mounted-root,
child-chain and resume-lifetime semantics before implementation. Never cache
successful admission across accesses. Other runtime condensation has one modest candidate:
combine progress initialization's two plan walks. Existing pause/cancel and
settlement distinctions, plus prior shelved reductions, remain intact.

Verification: 23 rig invocations, 47 successful executions, 42 successful
readbacks; all accepted metrics have zero residual reservations. Existing
`test_tools_executor.py` and `test_executor_pipeline.py`: **80 passed**
(`focused.xml/log`). Source/instrument review checked timing boundaries and
poll overrides. Preflight is excluded from execute timing; nested stage times
overlap, cProfile timings are perturbed/overlapping, and queue waits/high-water
are not device utilization. These are diagnostic observations, not release gates.

All task-created F:/G: roots and sibling rig artifacts were removed through
manifest-validated cleanup, including the retained reverse-source fixture.
The original `F:\NamiSyncExecutorBenchSource` was kept read-only. Only
PERFORMANCE, CHANGELOG and this handoff are tracked changes; production/tests
remain unchanged. No recovery branch/worktree was needed.

Prior incident and AB-10 evidence remains untouched under
`build/admission-bridge-closeout-20260927/`, `build/incident-trace-20260927/`,
`build/trace-20260927/` and `build/ab10-20260926/`. Existing M1 decisions and
deferred findings are not reopened by this assessment.
