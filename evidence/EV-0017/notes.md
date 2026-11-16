Notes for "Executor simplification, differential and direct-write measurements (2026-09-29)": text files chosen from `build/executor-simplification-20260929/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/executor-simplification-20260929/README.md`

# Executor simplification evidence — 2026-09-29

This ignored directory holds task-owned execution evidence for M1_PLAN results
1–3. Product, tests, tracked documentation and settlement baseline are owned by
the execution checkout and are never edited by these helpers.

- `differential/` contains byte-identical copies of the retained differential
  driver and audit producer. Its `runs/<label>-<uuid>/` directories retain raw
  reports, comparison projections, provenance, source snapshots and owned
  fixture trees. Labels use lowercase letters, digits and hyphens.
- `scripts/` contains adapted evidence drivers and their source. Five-band
  measurement uses the existing `python -m tools executor` rig and its owned
  target/sidecar cleanup. It never changes the original F: source corpus.
- `measurements/` holds uniquely prefixed commands, before/after manifests,
  environment observations, raw JSON/log reports and derived comparisons.
- Existing `ceilings/` scripts/results remain unchanged. The authorized threshold
  probe adds a standalone helper, its immutable reviewed copy, append-only
  `threshold-<uuid>/` raw receipts and derived observations there; PERFORMANCE
  owns its method and conclusions. These are diagnostic experiments, not product code.
- Evidence is append-only. Failed receipts and fixtures remain available;
  these helpers do not remove evidence or silently retry failures.
- Product, helper, driver and source dependencies must match before/after a
  measurement. A precommit candidate is permitted when its exact physical
  bytes and worktree status remain stable throughout the run. Every raw sample
  is retained; benchmark timings are diagnostics, not correctness acceptance.

Baseline checkout: `C:/Users/Spectrum/.codex/worktrees/executor-simplification-baseline/NamiSync`,
at `b1b58476c80462d1f9a299d74eae3db6c86ee52e`.

## Baseline capture

`differential/runs/baseline-b1b58476-1677e16405314dbfbe06e27ba745d8e6/`
captured all 67 groups from that exact baseline. Its six retained audit scenario
groups report no independent oracle errors, and no group recorded an unhandled
exception. The baseline checkout remained clean. This is preparation evidence;
candidate differences still require classification and independent review.

The copied driver SHA-256 is
`e7ba9b8df71233a0418ae77454db35b2f61783c447ffaf41dfc9f4066a55234b`;
the copied audit producer SHA-256 is
`d0a68eacd75312f5147f336fca649ad16c5e2954f55b623cff72dbc509817f01`.
Both match the retained source bytes. `provenance.json` records the selected
checkout/import, interpreter, product/helper manifests and finite corpus.

`differential/baseline-b1b58476-safe-directory.log` retains the successful
invocation. It used process-local Git configuration for this exact baseline
checkout, because the managed checkout and sandbox shell have different Windows
owners. No global Git configuration changed. The initial failure is retained in
`differential/baseline-b1b58476.log` and its incomplete run tree; it failed at Git
provenance enumeration before any scenario execution.

The retained admission scan checks root admission before its recognized effects.
It does not prove plan fidelity before every effect. For the current finite
slice, explicit source/effect fidelity inspection complements that existing
scan; there is no new checker.

`scripts/five_band.ps1` and `scripts/five_band_receipt.py` passed their respective
PowerShell parser and Python AST checks.

## Result 1 evidence

`differential/runs/candidate-result1-source-753c89f8c7934b22b4f823532fc3252a/`
captures all 67 groups with no comparison differences. Its post-capture
dependency receipt confirms product/helper/adapter bytes match the capture.
`differential/checkout-byte-provenance.json` classifies all 23 physical product
manifest differences: 22 are CRLF-only; the other is the intended executor
runtime change. Every product Git blob at the baseline and candidate base is
identical, and no raw producer manifest or comparison receipt was rewritten.

`differential/result1-oracle-classification.json` classifies 27 changed and 43
unchanged rows of the 70-row, 30-scenario candidate snapshot. All changes are
successful source observation/admission removal plus exact corresponding count
and timeline deltas. All other settlement fields are equal. Candidate semantic
SHA-256, computed using the oracle's `_canonical`, is
`2509b4e543afb32efdc347149a34be05838335c59fc86b71b1b56ecee82f22a9`.
The tracked oracle/baseline re-pin and official gate are owned by the parent
execution lane, outside these evidence-only helpers.

The five-band measurement prefix is
`measurements/result1-dadc1fef-20260929-153840-0bb41f93`. All 25 executions and
readbacks passed the existing rig's complete-result checks. Before/after source
stat identity and product/tool/test/driver hashes/status match; all five owned
targets and rig sidecars were absent after manifest-owned cleanup. All samples
remain in their raw JSON/log reports. `-latest-comparison.json` compares them
with the latest pre-result `23589bd` endpoint and preserves source, policy,
report and provenance validation.

| Band | Current median seconds | Current MiB/s | Time delta vs `23589bd` |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.357801 | 1.163 | −7.4% |
| 512 × 128 KiB | 1.775342 | 36.049 | −9.4% |
| 64 × 4 MiB | 0.349377 | 732.733 | −6.2% |
| 4 × 128 MiB | 0.316469 | 1,617.852 | +4.0% |
| 1 × 4 GiB | 2.134753 | 1,918.723 | +6.5% |

All historical/current sample ranges overlap. These sequential, buffered
repeated-source observations make no isolated causal or cold-cache/device-peak
claim. The 4 KiB goal of 1.6 MiB/s remains unmet: its median backend time is
0.417234 seconds, versus 2.940567 seconds outside the backend. Direct writes
remain excluded. Measurement scripts did not edit product, tests or tracked
documentation.

## Result 2 independent evidence inspection

`differential/result2-independent-evidence-audit.json` and
`result2-current-manifests.json` independently record the exact 67-group capture
`candidate-result2-handles-790e67a4c7e44f9bb3af36c594f6cfb9`, zero differences,
equal baseline producer/helper/corpus dependencies, and the current physical
product/helper/adapter manifests. Runtime source-fidelity/effect declarations
remain AST-identical to result 1 except descriptor retirement in `_settle` and
`_backstop_operation`; public native filesystem signatures remain unchanged.
`result2-guard-scan.log` retains 70 rows, 391 recognized effects and zero missing
admissions. Its fidelity limit remains the one described above.

`handle-exfat-witness.json` matches the inspected native/script hashes and records
two completed cases on K: exFAT. Its scope is low-level retained-handle rename,
collision refusal/replacement, contents, close/stable timestamps, directory flush
and exact fixture removal. It deliberately avoids FileIdInfo and does not run
full `finalize_temp`, `ensure_published_metadata` or public execution; it is not
full exFAT executor acceptance.

The first ordinary result-2 failure remains in
`differential/result2-ordinary.log`. The independent parent review found WinError 5
blocking its injected mid-invocation replacement, truthful recorder failure,
removed owned temp and unchanged live bytes; all 13 original assertions passed
through the process-local path-finish fallback. The parent authorized only the
test-fixture migration and a current-native blocked-attempt witness. Production
dependencies and the original differential remain unchanged; corrected test
gates and measurements are still owned by the parent execution lane.

`scripts/summarize_five_band_predecessor.py` compares a future measurement prefix
against an explicitly supplied immediate-predecessor prefix and commit
attribution. It preserves actual measurement HEAD/status/hashes separately from
that attribution and validates all raw samples and common source identity/policy.

## Result 3A fixed differential evidence

`differential/runs/candidate-result3a-fidelity-563226ff78a748799e044bd17741fb48/`
captures all 67 groups at the dirty `0d7dd6bf` predecessor. `differences.json` is
empty; its six retained oracle subsets have no independent errors. Driver,
fixed audit producer, helper corpus and adapter hashes equal the saved starting
baseline. `post-capture-dependency-check.json` is empty, confirming captured
product/helper/adapter bytes still match. `result3a-current-manifests.json`
retains those complete physical manifests plus tracked tools/test hashes.
The fixed driver records and asserts the selected product package import path.

`result3a-oracle.log` records the unchanged 30-scenario three-run check;
`result3a-imports.log` records all 12 contracts kept. The existing unchanged
admission scanner produces `result3a-guard-scan.log`: 70 rows, 391 recognized
effects and zero missing admissions. Its fidelity limit remains unchanged.
The finite source/effect review is separate from these receipts. This fixed
differential corpus does not contain incidental metadata/link-count drift
cases; focused migration tests cover that declared behavior.

The optional `audit_result3a_receipts.py` did not succeed. Its original AST
assertion counted an intentional docstring change; the single corrected retry
then referenced a nonexistent `_guard_update_live` declaration. Both failed
logs and exact script copies remain (`-failed-docstring.py` and
`-failed-missing-symbol.py`). No successful independent AST-audit receipt is
claimed; work on that optional checker stopped. The already-produced fixed
differential, current manifests and admission-scan receipts remain valid.

The completed five-band prefix is
`measurements/result3a-0d7dd6bf-20260929-173343-1dcc369e`. The unchanged existing
predecessor comparator records result 2's raw measurement HEAD separately from
its accepted `0d7dd6bf585383608f26537bf403e695df49c460` attribution.
`-existing-receipt-audit.log` reuses the existing receipt's observations to
validate all 25 raw completed executions, recording, exact operation/byte
populations, readback and zero reservations. Before/after source, product,
tool, test, driver, relevant status and runtime dependency fields are equal;
the original 1,587-entry source manifest is unchanged. All raw report hashes
match the producer's comparison. `-correctness-dependency-audit.log` confirms
the measurement's product/helper/adapter hashes match the fixed differential.
Every rig log records an unchanged source recheck and exact manifest-owned
successful teardown. The elevated producer's successful existing summary
also asserted absence of each owned target and sidecar.

| Band | Median seconds | Median MiB/s | Time delta vs result 2 | Sample ranges overlap |
| --- | ---: | ---: | ---: | --- |
| 1,000 × 4 KiB | 6.489094 | 0.602 | +22.5% | Yes |
| 512 × 128 KiB | 3.503481 | 18.268 | +28.8% | No |
| 64 × 4 MiB | 0.708085 | 361.539 | +34.6% | Yes |
| 4 × 128 MiB | 0.354306 | 1,445.077 | −3.0% | Yes |
| 1 × 4 GiB | 2.481875 | 1,650.365 | +11.2% | Yes |

The small-file backend median is 0.775883 seconds and the outside-backend
median is 5.719772 seconds. The throughput goal remains unmet. These are
sequential repeated-source diagnostic endpoints; no causal benefit, host cause
or cold-cache/device-peak result is claimed. No extra measurement or checker
was created for this comparison.

## Final verifier outcome and closeout

`differential/result3b-*` retains the 239 focused, 1,465 neighborhood and
5,702 ordinary passes, 12 kept import contracts, unchanged 30×3 oracle and
70-row/391-effect admission scan. The initial `db` department selection failed
before any test; its separate receipt remains. A final README precision
correction invalidated only its package consumers; their five modules rebuilt
and passed all 85 checks after the correction (`result3b-package-final.log`).
The fixed 67-group capture is
`differential/runs/candidate-result3b-verifier-05d1c814c4754f52a91799bd755e0d9a/`;
the independent fixed-differential audit and current manifests report no drift.

The final measurement prefix is
`measurements/result3b-84ce0fb2-20260929-175649-85162057`. All 25 samples and
readbacks pass, with matching source/dependency manifests and complete owned
target/sidecar cleanup. Existing predecessor comparison, receipt audit and
correctness-dependency audit retain raw inputs and their hashes. All timing
ranges overlap the preceding run, and no causal throughput lift is established.

The task-created baseline checkout was clean at `b1b58476` and was archived
through the Codex app after the final measurement. The archived-worktree
attachment retains recoverability. The pre-existing root-admission worktree,
original F: benchmark source and all raw evidence remain untouched.

## User-requested cleanup and target-check follow-up

The user reported F: contention during the earlier finishing benchmarks and
provided a separate rerun table, now recorded in PERFORMANCE. Historical slower
endpoints do not establish a regression. The user's `measurements/claude-ab/`
files were not changed.

Protected witness ACLs granted only the sandbox account after the old restore,
so the user still could not list them. `differential/acl-fixture-restoration*.json`
retains original/restored ACLs. `acl-fixture-cleanup.json` records four exact
removed fixture roots (6,173 entries) and maps three preserved witness receipts
by SHA-256 to `differential/handle-acl-<original-id>-receipt.json`. Their old
in-fixture paths no longer exist. Reparse entries were unlinked without traversal.
The four new development-test fixture roots were also removed (7,546 entries),
recorded in `target-fixture-cleanup.json`; test outputs remain.

`target-test-tool-transcripts.json` labels the builder's focused/department runs
as default-sandbox development evidence. `target-ordinary-tool-transcript.json`
records the root's explicitly escalated, standard-temp full-suite request and
completion; `target-ordinary.log` reports 5,704 passed, four skipped, 34 deselected.
No fixture ownership observation substitutes for process-identity evidence.

The oracle baseline and candidate snapshots plus `target-oracle-classification.json`
retain the independent deletion-only review: 21 successful null target stats,
18 changed rows, 52 unchanged, no changed effect/recorder/tree/settlement fact.
The candidate custom-baseline three-run diagnostic passed before commit; it is
not mislabeled as the official clean-HEAD pinned check.
The fixed differential capture is
`differential/runs/candidate-target-consolidation-acafd1f5d6a14de48d3f222136ea7b55/`.

All 25 measurement/readback samples passed under prefix
`measurements/target-9c96893b-20260929-191353-d421178a`, with fixed dependencies,
unchanged original source manifest and complete owned-target teardown.
Independent review recomputed the raw observations and checked all target and
sidecar paths were absent. The historical predecessor comparison retains the
contended result3b identity separately from accepted commit `d444a6a`; it does
not isolate an effect of removing the two target checks.

## Result 3B fixed differential evidence

`differential/runs/candidate-result3b-verifier-05d1c814c4754f52a91799bd755e0d9a/`
captures all 67 groups at the dirty `84ce0fb` predecessor. Raw and comparison
populations are both 67, differences are empty, and all six oracle subsets
report no errors. `result3b-fixed-differential-audit.json` and its log retain
the direct read-only inspection: fixed driver/audit/helper/adapter/corpus hashes
equal the saved starting baseline, current product/helper/adapter drift is
empty, and the fixed driver records/asserts the selected package import path.
`result3b-current-manifests.json` retains the full physical manifests and
tracked tools/tests hashes. No optional AST checker was used. Official gate
completion and measurement evidence are recorded separately when available.

The final five-band prefix is
`measurements/result3b-84ce0fb2-20260929-175649-85162057`. Its retained predecessor
comparison uses result 3A's actual raw measurement provenance, separately
attributed to accepted `84ce0fb2790127cee5aedd53af0963dbc5cdd32b`.
The unchanged receipt helper revalidated all 25 raw samples: completed execution,
recording, exact operation and byte populations, readback, and zero reservations.
Raw report hashes match the producer comparison. All before/after source,
product/tool/test/driver/status and runtime dependency fields match; the original
1,587-entry source remains unchanged. Product/helper/adapter hashes match the
fixed result-3B correctness capture. All five logs record unchanged source
rechecks and exact manifest-owned teardown; the successful elevated producer
also asserted target and sidecar absence. Audit logs retain these observations.

| Band | Median seconds | Median MiB/s | Time delta vs result 3A | Backend / outside medians, seconds |
| --- | ---: | ---: | ---: | ---: |
| 1,000 × 4 KiB | 6.217505 | 0.628 | −4.2% | 0.763806 / 5.463032 |
| 512 × 128 KiB | 3.452010 | 18.540 | −1.5% | 0.458765 / 2.986123 |
| 64 × 4 MiB | 0.488839 | 523.690 | −31.0% | 0.208658 / 0.280181 |
| 4 × 128 MiB | 0.328943 | 1,556.501 | −7.2% | 0.186597 / 0.143207 |
| 1 × 4 GiB | 2.319795 | 1,765.673 | −6.5% | 1.904910 / 0.414607 |

Every sample range overlaps its predecessor. These are sequential diagnostic
endpoints, without causal benefit, host-cause, cold-cache or device-peak claims.
The 4 KiB goal remains unmet. No additional measurement or checker was added.

## Remaining simplifications — 2026-09-30

This evidence root also holds authorized results 5–7. Existing structure and append-only rules apply; differential/result5-*, result6-* and result7-* and matching measurement labels identify each atomic outcome. Direct writes are excluded.

# `build/executor-simplification-20260929/ceilings/results.md`

# Device ceiling probes — 2026-09-29

Run from `103f3e48` checkout with the project venv (Python 3.13, xxhash 3.8.1).
`flush_ceiling.py G:\` wrote into a uniquely named owned scratch folder on G:
and removed it (`cleaned: True`). `read_ceiling.py` only read
`F:\NamiSyncExecutorBenchSource\1x4GiB\file-0000.bin`.

## G: 4 GiB writes, 4 MiB chunks, one outstanding request

| Mode | Write s | Flush s | Total s |
| --- | --- | --- | --- |
| Buffered | 0.882 / 0.997 / 0.953 | 0.662 / 0.651 / 0.627 | 1.544 / 1.648 / 1.579 |
| Unbuffered | 0.730 / 0.738 / 0.733 | 0.000 | 0.731 / 0.738 / 0.733 |
| Buffered write-through | 1.968 / 1.797 | 0.000 / 0.001 | 1.968 / 1.798 |

## G: 4 KiB create/write/close/rename, ms per file (3 × 500 files)

| Sequence | Runs | Median |
| --- | --- | --- |
| No flush | 0.164, 0.208, 0.162 | 0.164 |
| File flush | 0.447, 0.473, 0.437 | 0.447 |
| File flush + directory flush per file | 0.657, 0.677, 3.409 | 0.677 |
| File flush + one directory flush per batch | 0.469, 0.460, 0.426 | 0.460 |
| Write-through + directory flush per file | 0.627, 0.705, 0.622 | 0.627 |

## F: 4 GiB reads, 4 MiB chunks, one outstanding request

| Mode | Seconds | MiB/s |
| --- | --- | --- |
| Unbuffered | 0.832 / 0.837 | 4925 / 4891 |
| Unbuffered + xxh3_128 | 1.083 / 1.082 | 3782 / 3785 |
| Buffered sequential | 1.083 / 1.000 | 3784 / 4096 |
| Buffered sequential + xxh3_128 | 1.073 / 1.071 | 3817 / 3825 |

# `build/executor-simplification-20260929/differential/result5-final-focused.log`

````text
...........................                                              [100%]
27 passed, 337 deselected in 2.08s
````

# `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-dependencies.txt`

````text
bottle==0.13.4
cffi==2.1.0
click==8.4.2
clr_loader==0.3.1
colorama==0.4.6
grimp==3.15
import-linter==2.13
iniconfig==2.3.0
markdown-it-py==4.2.0
mdurl==0.1.2
-e git+https://github.com/Wavechaser/NamiSync.git@b9c4ad3eced994e9958e8ad685e2450486284213#egg=namisync
packaging==26.2
pluggy==1.6.0
proxy_tools==0.1.0
pycparser==3.0
Pygments==2.20.0
pytest==9.1.1
pythonnet==3.1.0
pywebview==6.2.1
rich==15.0.0
setuptools==83.0.0
typing_extensions==4.16.0
xxhash==3.8.1
````
