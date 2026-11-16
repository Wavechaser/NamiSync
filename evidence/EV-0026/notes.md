Notes for "Path consolidation (2026-11-07)": text files chosen from `build/path-consolidation-20261107/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/path-consolidation-20261107/README.md`

# Copy path consolidation evidence

Task-owned ignored evidence for exact held root/anchor spelling reuse. Logs, frozen baseline source, counted native COPY and microbench receipts remain here through independent review. Disposable fixtures live only under this directory and drivers remove exact owned files after verification. No measuring session artifacts are touched.

# `build/path-consolidation-20261107/findings.md`

# Exact root and anchor spelling consolidation

Base: `323b5377b94551e628e051dc1fa8b2636556fba7`. Product owner:
`namisync/modules/executor/native.py`; tests: `tests/test_executor_native.py`.
No tracked documentation or commits written by the builder. Parent owns those.

## Change and preserved behavior

`revalidate_root` finds the exact raw invocation root before converting it. The
shortcut requires an active invocation, this filesystem's native ownership, an
exact authority root spelling and the native prefix installed only after full
admission and local hold confirmation. It reuses that root spelling and, when
equal, its exact reviewed anchor. No new cached state or observation exists.
Expected volume matching, `held` confirmation, `require_ordinary` and all fresh
root/descendant/leaf checks remain. A known root does not make a different volume
or anchor admissible. Nonmatching spellings still convert; unheld/different-owner
or expired contexts retain original full conversion and admission. The initial
full root admission remains unchanged. `resolve`'s own lexical conversion and
descendant work are deliberately unchanged.

## Shared operation benefit

Each eligible explicit `_revalidate_source_root` / `_revalidate_target_root`
call supplies the exact root and reviewed anchor, removing **two** lexical
conversions per such call. Each native `resolve` root revalidation supplies just
the root, removing **one** inner conversion; `resolve`'s outer conversion remains.
These are per-call source-derived counts, not a per-operation timing estimate.

| Operation family | Existing consumers of the same optimized owner |
| --- | --- |
| COPY, UPDATE, MOVE_UPDATE | Shared dispatch entry (target and applicable source), `_prepare_copy`, source/target guards, all native stat/resolve calls, publication and recovery guards. |
| MOVE, RECASE | Shared dispatch entry, their explicit paired/final guards and native stat/resolve calls. |
| TRASH, DELETE | Shared dispatch target guard, each operation's target guards around its recorder barrier and mutation, native stat/resolve calls. |
| NOOP | Shared dispatch target/applicable source and two-sided native stats. |
| MKDIR | Dedicated `_start_directory`: two explicit source and one target guard, source/absence checks and target resolve; `_finalize_directories` uses shared target resolve/stat. It does not need the ordinary `_execute_operation` branch. |

Locators in unchanged `runtime.py`: `_execute_operation`1552,
`_prepare_copy`1637, COPY2030, UPDATE2141, MOVE2476, RECASE2592,
MOVE_UPDATE2708, TRASH2857, DELETE2937, NOOP3015,
`_start_directory`3065, `_finalize_directories`3111,
shared root guards4623/4641, `_resolve_target_path`4735.
No operation-specific optimization or changed effect ordering was needed.
Custom overrides remain dynamically dispatched; no verifier/scanner/preflight
or core owner is changed.

## Verification and diagnostics

- Baseline native gate: **193 passed**, 8.45s (`native-before-unrestricted.log`).
- Candidate native gate: **203 passed**, 8.68s (`native-after.log`). Ten added
  cases cover exact root/anchor/volume combinations with a real fresh held query,
  root and anchor aliases, wrong anchor/volume, other adapter and retained
  inactive context. Existing reparse, placeholder, query-failure, fallback,
  length, mutation and operation composition tests remain.
- Executor department: **658 passed**, 5,836 deselected, 43.04s
  (`executor-after.log`).
- Unchanged settlement oracle: **30 scenarios x 3 runs**, passed
  (`settlement-after.log`). No scenario, baseline or oracle edits.
- `git diff --check`: passed.
- Initial sandbox baseline run could not create pytest's numbered Windows
  temporary directory. It had 187 fixture setup errors and six fixture-free
  passes; retained as `native-before.log`, not product evidence. Running with
  normal native temporary-fixture access passed. No approval rejection occurred.

`trace_copy.py` is unchanged from the prior investigation, now run separately
against this task's baseline and candidate. Each run verifies 48 fresh 4KiB
copies (16 at depths1/2/5), successful terminal/recording/publication identities,
SHA256 mirror, unchanged source and exact fixture cleanup. The COPY-body trace
excludes the outer entry root guards and directory work. Each COPY removes20
lexical conversions (30→10) and20 `_held_native_path` calls. The fresh held
queries remain19; descendant attribute reads remain10/20/50; leaf stats remain6;
existence checks remain3. Native resolve remains10. Add two unchanged outer
entry queries for21 ordinary COPY executor held queries. Inclusive instrumented
timers are not throughput acceptance.

`bench_revalidate.py` and `run_bench.ps1` measure actual confirmed-held
`revalidate_root(root, trusted_anchor=anchor, expected_volume=volume)` calls,
including each real fresh attribute query. Five fresh-process pairs alternate
before/after order; every process warms100 calls and measures five1000-call
batches. Baseline method AST comes from `native-before.py` and all collaborators
are unchanged. Across-process median of process medians is **15.1984µs before**
(range14.9767–16.1512) and **2.0871µs after** (range2.0813–2.1972). Paired
savings range12.7795–14.0641µs. This is a bounded primitive diagnostic, **not an
integrated copy/host speedup claim**. No end-to-end throughput sample was added.

Raw receipts: `trace-before.json`, `trace-after.json`, ten `bench-*-*.json`.
`summary.json` recomputes per-depth comparisons, process medians and pinned
product/test/driver/raw-trace hashes. Baseline native SHA256:
`e9e6356305614392fc205ccac5c77094e0751f1646bd7b8c5f7caad39e1bcbab`;
candidate native:
`a663e3adf4bd771ef98fe74e8798f4a2958d7437943d8565b516ede2ac1f57c8`.

All task-created COPY/microbench fixture roots were removed through exact-name
cleanup after content/ownership checks and released holds. No live app, renderer,
measuring profile or resource monitor was touched. No verification pipelining,
post-close GC, descendant-walk fusion or per-file cache was implemented.

# `build/path-consolidation-20261107/review.md`

# Independent adversarial review

Reviewed the uncommitted executor candidate over base `323b5377b94551e628e051dc1fa8b2636556fba7`. The reviewed native source SHA-256 is `a663e3adf4bd771ef98fe74e8798f4a2958d7437943d8565b516ede2ac1f57c8`. The focused native test source SHA-256 is `ba1150287170d186da477d4092da4182a7672d3ef520e67b51b4db21990658fd`.

## Code and behavioral checks

- The new lookup runs for the active invocation. `_scoped_root` requires the owning native adapter and exact logical path text. A prefix can first be set only after reviewed admission and held final-path confirmation. Invocation teardown clears the prefix before releasing the hold, including when another context retains the invocation object.
- Exact trusted-anchor spelling bypasses lexical conversion. The existing matching predicate still compares expected volume and falls back to lexical conversion for nonexact anchors. Initial admission, alternate spellings, unavailable holds, foreign adapters and inactive invocations follow existing conversion and admission rules. Custom adapters retain runtime dispatch.
- `_require_held_root` still freshly queries attributes on successful reuse. Its refusal and error translation remain at the same call site. Descendant guards and the ordering of effects, recorder calls and settlement are outside the changed code. The implementation adds no stored path or filesystem observations.
- The ten focused cases cover exact root revalidation across optional reviewed arguments and six fallback variants. Existing native tests cover current query failure, placeholder refusal and actual in-place junction conversion. The executor department includes held target refusal before MOVE, RECASE, DELETE and MKDIR effects. Settlement tracing forwards the same native activation.

## Evidence checked

- `native-before-unrestricted.log`, `native-after.log`, `executor-after.log` and `settlement-after.log` report 193 baseline native, 203 candidate native, 658 executor and 30 settlement scenarios across three runs. The original restricted Temp setup failure is retained in `native-before.log`. Gate verdicts are from the retained runs.
- The frozen baseline native source matches the base Git blob `051d4b3bce8064e7c3c8e77692f7641d725316f9`. The raw trace receipts match the baseline and candidate source, the unchanged runtime and the same trace driver. At relative depths 1, 2 and 5 the paired traces show 20 fewer lexical calls per COPY body, all at the revalidation site, and 20 fewer held-spelling calls. All other instrumented counts agree, including 19 current held queries and 10, 20 and 50 descendant attribute reads. The driver verifies 48 completed copies with exact SHA-256 mirrors and 48 published-evidence entries, preserving source content and cleaning its fixtures.
- The ten benchmark receipts have distinct process IDs and matching driver/source hashes. The baseline substitutes the method from the verified frozen source and both variants use the real held query. Recomputed process medians yield 15.1984 µs before and 2.0871 µs after. Paired savings range from 12.7795 to 14.0641 µs for this isolated call. The benchmark is diagnostic.
- The tracked scope covers one native module, one focused test file and five delivery documents. The verifier, descendant walk, GC policies, settlement oracle and baseline remain outside the diff. `git diff --check` exits zero. The documentation check covers 176 local targets with zero missing.

## Verdict

Approved for one atomic executor commit. The documentation now distinguishes alternate-spelling conversion from fallback admission, separates the fresh-attribute rule from spelling reuse, and reports exactly what the diagnostic COPY driver checked. No unresolved review findings remain.
