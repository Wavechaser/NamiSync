Notes for "Release repair R3 renewal, resource collections and package 04 at cfeac2d9 (2026-11-10)": text files chosen from `build/m1-release-repair-20261110/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/m1-release-repair-20261110/acceptance/20261110-04/package/artifact-comparison-review.md`

# Independent Package04 artifact comparison review

Approved as the rebuilt input for the two targeted resource profiles. Package04
identifies clean source `1d93687638562dbed776f116da37504c9e3a1d08`, the retained
Python and dependency inputs, and the reviewed runner. I rehashed the actual
portable ZIP to `fca5c839cb9e4fb7a47e343656b08a9587961e2cdf2ccf8a920652875970311f`.
Package03 still hashes to
`a840c9b0fedc31a442e677cb81c7281d5901ed9eafa1e1d25f31c991d9ceff5a`.

The original comparison receipt failed because its allowlist omitted the
generated Bottle and CFFI installed RECORD deltas. Both comparison receipts
identify the same three Package04 archive hashes. The second receipt keeps
the existing package census and restricts those RECORD deltas to generated
launcher rows. I independently compared the CSV rows, found no duplicate
paths, and rehashed each changed target in both package environments. Bottle
changes `bottle.exe` and `bottle.py`; CFFI changes `cffi-gen-src.exe`. NamiSync
changes its two generated launchers, the corrected rail, and the resulting
metadata and direct wheel reference. The five launcher files each contain
one package-environment path in the prefix or script. Replacing that exact
path yields identical prefixes or scripts, and each executable has one
embedded `__main__.py` with identical bytes.

Both portable PE executables differ only in the COFF and debug-directory
timestamps and the optional-header checksum. I compared the raw appended
PyInstaller archives byte-for-byte in addition to the comparator's per-entry
checks. The console archive SHA-256 is
`f766441593d268185c06593750ee5f108c21fc072c11901968c255ea77dc174f` and the GUI
archive SHA-256 is
`e92eafd8994dd1606908e437f528535480e1d92ac172bc3b503125d8aa5b5b94` in both
packages. The remaining app assets, native payloads, package member counts
and 52 notices reconcile with the census. The source payload delta is the rail and
README, which flows into the wheel description and RECORD. This review covers
the package comparison for the resource follow-up. R5 release review remains
separate.

- Initial `independent-comparison.json` SHA-256
  `529268122322d87ea31a0979bd6fa58ac788082b3a8848f54555e096e7d359b2`.
- Passing `independent-comparison-02.json` SHA-256
  `63767d7b23b3bc8f7ef4fee1d5291d267bcbac076543ce136ef733dfd9425a0c`.
- Reviewed comparator SHA-256
  `632db76f2055f165c029ee8d536a694d8015fd90bf35c4e7ec5579f5ecdb8492`.

# `build/m1-release-repair-20261110/acceptance/20261110-04/resources/review.md`

# Independent Resources04 review

Approved the two requested observations. The collection ran on clean commit
`1d93687638562dbed776f116da37504c9e3a1d08` and Package04 portable SHA-256
`fca5c839cb9e4fb7a47e343656b08a9587961e2cdf2ccf8a920652875970311f`.
I rehashed the portable ZIP, extracted GUI and rail asset, the reference
profile and all six collector/helper/validator files. These match the
pre-collection and collector manifests. The runner recorded Medium integrity,
CPython 3.15.2, SQLite 3.53.4, xxhash 4.1.0 with native 0.8.4, and the successful
pythonnet 3.2.1 check. The module-origin receipt resolves the collector and
validator from the clean checkout. The recorded host used AC power and
WebView2 `157.0.4341.42`.

Both profiles completed. The 10,000-file open-idle target and both payload
targets passed their post-exit mirror audits. All three task Close gestures
advanced to the expected idle phase. Both hosts exited 0 with no remaining
owned Job PIDs, as recorded in the final Close events and run receipts.

| Profile | Sampled peak | Closed-idle median or maximum | Other observation |
| --- | ---: | ---: | --- |
| `idle-open-01` | 1,129.746 MiB | 551.262 MiB | 554.715 MiB open-idle median, +0.001 MiB per 10 minutes |
| `payload-01` | 442.828 MiB | 405.535 MiB maximum | 359.598 MiB after 1 × 4 GiB, 405.535 MiB after 64 × 4 MiB, 404.104 MiB final idle |

I independently recomputed the peaks, medians and open-idle slope from the
complete whole-Job private-memory samples. The open-idle events span exactly
3,600 seconds. The final 3,000-second statistic span contains 3,000 complete
samples, with a maximum observed gap of 1.016 seconds. The two raw runs retain
3,859 and 192 complete samples respectively, including their final Close
phases. Both validator rows are valid and every evaluated predicate passes.

`commands.jsonl` records the collector's exit 0 and the unchanged validator's
exit 1. The raw `FAIL` is for the 15 profiles deliberately outside this
collection. It remains separate from the two valid observations and the
historical Resources03 incomplete receipt.

- `identity.json` SHA-256
  `e4f6db261ab019b4622fd96e73dd8ab9bbf9683e218a076562cc6076184ca43e`.
- `schedule/collection.json` SHA-256
  `cfd5dee330f5048f92eb1c084febf183f1b233fd6e103e1d6117b7d12fb8ebdb`.
- `validation.json` SHA-256
  `5016624f352d49b55947c662cff3c2b03fec2638a62e17cbfbcfae82abf5e38e`.

# `build/m1-release-repair-20261110/renewal/r3-review.md`

# Independent R3 renewal review

R3 attempt `20261110-03` passed on clean `cfeac2d95a6db83107854d17d9e6c4e9a774b77e`.
The journal records exit zero for runtime qualification, Inventory correctness,
both collections and both validators. Runner and profile-driver hashes match.
The recorded Medium token, CPython 3.15.2 x64, SQLite 3.53.4, Windows 11 Pro
26200.9711, i7-13700K, 63.7 GiB RAM, SN850X NVMe and AC power match the
declared profile. Pre-run CPU readings were 12.46%, 6.92% and 4.30%. The
operator confirmed the quiet window. [Identity](../acceptance/20261110-03/r3/identity.json),
[profile](../acceptance/20261110-03/r3/reference-profile.json),
[journal](../acceptance/20261110-03/r3/commands.jsonl).

| Obligation | Complete population | Recomputed result | Existing limit |
| --- | --- | --- | --- |
| Inventory cold base | 5 children, 120,000 public rows each | 1.4609754–1.4793711 s | 3 s max |
| Inventory cold information-heavy | 5 children, 240,000 public rows each | 2.0742710–2.1139741 s | 6 s max |
| History 50-run summary | 5 children, 10 readings | 1.6812297999858856 s max | 3 s max |
| History item and event 256-row pages | 5 children, 200 samples per stream | p95 18.92910012975335 / 19.304899964481592 ms, max 33.82419981062412 / 29.808100312948227 ms | 500 ms p95 / 1 s max |
| History recording | 5 release fixtures, largest run 100,000 items | 54.030700121074915 ms worst commit, 256 events and 109,568 B peak pending, audit OK | Commit below 5 s, 256 events / 1,048,576 B pending, audit OK |
| Bridge reliable and terminal | 5 children, 3,100 observations | 6 ms worst child p95, 51 ms max, zero Gaps | 100 ms p95 / 250 ms max, zero Gaps |
| Bridge progress | 5 children, 7,490 observations | 42 ms worst child p95, 47 ms max, monotonic | 1 s p95 / 2 s max, monotonic |

Inventory raw, validator, profile and all 11 source hashes match. The ten
launches have unique invocation IDs and child PIDs, the expected five child
indexes per case and successful exits. Recomputed extrema match the raw and
separate validation records. [Inventory raw](../acceptance-checkout/build/m1-9-20261001/measurement-inventory-cold-20261110T070332Z-148ef4e1/raw.json),
[Inventory verdict](../acceptance-checkout/build/m1-9-20261001/measurement-inventory-cold-20261110T070332Z-148ef4e1/validation.json).

The BR-G-42 index is complete with five children per case and exit zero for all
ten. All ten report hashes match the separate validator in child order. Each
report names the clean successor. History applies the unchanged producer
assertions for audit status, recording and pending bounds, and the separate
validator uses pooled nearest-rank page p95. The installed bridge children use
clean archived source, pywebview 6.2.1, Python.NET 3.2.1, WebView2 157.0.4341.42
and .NET Framework. Each has matching machine and runtime qualification,
complete Job samples and valid measurements. Recomputing each stream's p95
from the child raw latencies agrees with the receipts. The checker and driver
diffs change runtime qualifiers only. [Index](../acceptance/20261110-03/r3/br-g-42/index.json),
[BR-G-42 verdict](../acceptance/20261110-03/r3/br-g-42/validation.json).

For the versioned record under `tests/interfaces/web/`, copy the three raw
receipt files to the following new names. Preserve the original CRLF working
bytes for SHA-256 verification, consistent with the historical Git checkout
policy. The three 2026-11-09 files match their accepted Git blobs.

| New file | Source SHA-256 |
| --- | --- |
| `r3_inventory_cold_20261110_raw.json` | `03b952df7cf994edcb703269e63d3ed4e3462c5192b4bc52e43064770b3fbdbd` |
| `r3_inventory_cold_20261110_validation.json` | `c99d6ccf3b566a3ca5d1f9e5752b3bd7971abf9dcf9f661992636ce693038d6a` |
| `r3_br_g_42_validation_20261110.json` | `cb7fc756bea868f3d2df9c0ef57b4c0a829fad2640c41fe55990276ade9a6b2f` |

# `build/m1-release-repair-20261110/renewal/resources-review.md`

# Independent SH-G-15 Resources03 review

**FAIL and incomplete.** The unchanged SH-G-15 v1 validator recorded 15 valid
runs, invalid `payload-01`, and missing `idle-open-01`. Of the 15 valid runs,
six had numerical exceedances and nine had none. Both collection and validation
exited 1. The accepted R4 disposition applies to its complete 17-run schedule
on `1f632b13`, carried to the equivalent app content on `3ece185f`.
[Resources03 verdict](../acceptance/20261110-03/resources/validation.json),
[journal](../acceptance/20261110-03/resources/commands.jsonl),
[accepted R4 raw verdict](../../m1-r4-20261109/soak-validation.json).

Values are in run order 01, 02, 03 unless a single value is shown. Bold marks
an exceedance. Settled means startup idle for startup and the maximum across
applicable post-task-close windows for workloads.

| Predicate | Unchanged limit | Accepted R4 raw measurements | Resources03 raw measurements |
| --- | ---: | --- | --- |
| Plain startup peak, MiB | 600 | 339.391 / 342.750 / 338.059 | 353.027 / 365.605 / 359.176 |
| Plain startup settled, MiB | 450 | 336.293 / 338.465 / 334.117 | 348.619 / 355.133 / 353.979 |
| Plain startup idle CPU, % | 1 | 0.132 / 0.397 / 0.291 | 0.344 / 0.662 / 0.503 |
| 10k work peak, MiB | 2,048 | 1,111.145 / 981.230 / 963.969 | 1,085.902 / 1,018.930 / 991.633 |
| 10k settled, MiB | 1,024 | 557.613 / 522.281 / 501.070 | 542.223 / 532.590 / 551.770 |
| 100k work peak, MiB | 2,048 | **2,316.105 / 2,394.113 / 2,403.746** | **2,309.039 / 2,348.285 / 2,346.273** |
| 100k settled, MiB | 1,024 | 721.414 / 718.992 / 725.641 | 708.125 / 703.098 / 717.770 |
| Soak work peak, MiB | 2,048 | 618.223 / 607.398 / 607.555 | 626.074 / 628.250 / 623.824 |
| Soak settled, MiB | 1,024 | 551.551 / 530.766 / 539.121 | 544.797 / 549.363 / 541.277 |
| Soak slope, MiB/cycle | 0.2 | **0.346 / 0.281 / 0.314** | **0.366 / 0.448 / 0.347** |
| Soak retained shift, MiB | 20 | **26.629** / 18.883 / 19.079 | **24.129 / 28.631 / 20.109** |
| Soak handle slope, handles/cycle | 1 | 0.874 / −1.085 / −2.467 | **2.699** / −1.780 / **2.575** |
| Soak GUI-object growth | 10 | 1 / 0.5 / −1 | 0.5 / −1.5 / −0.5 |
| Payload work peak / settled, MiB | 2,048 / 1,024 | 439.934 / 417.871 | Invalid. Partial 453.559 / 365.115 |
| Open-idle slope, MiB/10 min | 2 | 0.015 | Missing |

Resources03 has 11 failed run/predicate pairs across four predicates. R4 had
seven across three. The 100k peak remained above budget in all three runs,
although each was lower than its R4 counterpart. Soak memory slope exceeded
budget in all three soak runs in each collection. Retained shift exceeded it
in all three this time, up from one. Two handle slopes exceeded it for the
first time in these two collections. GUI-object growth remained within limit.
Recomputed soak slopes and shifts from the published window medians agree at
their available precision. The three DevTools startup runs were valid controls
without numeric gate predicates. Their median settled contrast was −8.643 MiB
versus +2.848 MiB in R4. These are descriptive comparisons across two runs of
the schedule. The receipts do not identify a cause for the resource differences.

## Provenance and coverage

The collection names clean `cfeac2d95a6db83107854d17d9e6c4e9a774b77e` and
the Package03 ZIP with SHA-256
`a840c9b0fedc31a442e677cb81c7281d5901ed9eafa1e1d25f31c991d9ceff5a`.
I rehashed the ZIP, extracted GUI, source ZIP, wheel, reference profile and six
recorded tools. They match their manifests and the independent artifact review.
The collector, checker and numerical budgets match R4's Git source. The
collection records the same workload corpus and pre-run corpus metadata as R4.
The Medium runner qualified CPython 3.15.2 x64, SQLite 3.53.4, xxhash 4.1.0
with native 0.8.4 and Python.NET 3.2.1. The reference profile records Windows
11 Pro 26200.9711, 16 cores / 24 logical CPUs, 63.7 GiB RAM, AC power, SN850X
repository storage, .NET Framework and registered WebView2 157.0.4341.42.
[Identity](../acceptance/20261110-03/resources/identity.json),
[collection](../acceptance/20261110-03/resources/schedule/collection.json),
[profile](../acceptance/20261110-03/resources/reference-profile.json),
[artifact review](../portable/final-artifact-review.md).

The six startup runs, three 100-cycle soaks and six scale runs have retained
sample and event logs, complete results, normal process exit and empty Jobs.
The 300 soak mirror checks and six scale mirror checks passed. The payload
log records completion of both copy operations. The first task closed and its
deferred mirror check passed. The driver clicked Close for the second task and
timed out after about 60 seconds. It retained the failure screenshot. The app
then exited normally with code 0 and an empty Job. The separate retained mirror
receipt has 64 source and 64 target relative paths with zero SHA-256 mismatches.
It establishes copy fidelity for that group. The required task-close observation
and final idle window are missing. The payload timeout's cause is undetermined.
[Payload events](../acceptance/20261110-03/resources/schedule/runs/payload-01/events.jsonl),
[result](../acceptance/20261110-03/resources/schedule/runs/payload-01/result.json),
[independent mirror](../acceptance/20261110-03/resources/payload-failure-mirror.json).

The early return skipped the collector's final corpus and extracted-tree
rechecks. A separate read-only check matched all 65 supplied-corpus sizes and
modification timestamps to the pre-run manifest. The raw attempt remains
intact. Any payload-only pilots are diagnostic and stay separate from this
17-run acceptance obligation.

## Manual post-stop extracted bundle check

At 11:21:35 UTC on 2026-11-10, a read-only check enumerated the retained
`schedule/app/NamiSync` tree, including hidden entries. All 341 relative file
paths and SHA-256 values matched `collection.json` exactly, with zero extra
or missing paths, hash mismatches, or reparse points. The manifest SHA-256
was `1533e4e7f723cdc24846cf19bdcea23ad9eafaa60bc61d44c0004e9f95e79c8d`
before and after the check. The original `FAIL` verdict likewise retained
SHA-256 `7b0cf59af94c28ddffdd8efedc8a14e1ad90ffa5ae8e9b53ea31d5d5dfd3f2b5`.
This supplemental check records the extracted bytes after the stop. The
payload and idle-open coverage gaps remain.

## Supplemental soak observations by process role

For each role, I summed private bytes and handles in each complete Job sample,
took the median over the final 10 seconds of each post-close window for cycles
21–100, and fit ordinary least squares over those cycle medians. The whole-Job
calculation matches the validator in both collections. Role medians are
independent, so the role slopes need not sum to the whole-Job slope. Values are
ordered by soak run 01, 02 and 03.

| Process role | R4 MiB/cycle | Resources03 MiB/cycle | R4 handles/cycle | Resources03 handles/cycle |
| --- | --- | --- | --- | --- |
| Whole Job | 0.346 / 0.281 / 0.314 | 0.366 / 0.448 / 0.347 | 0.874 / −1.085 / −2.467 | 2.699 / −1.780 / 2.575 |
| Host | 0.074 / 0.034 / 0.035 | 0.050 / 0.080 / 0.068 | −1.332 / −1.151 / −2.624 | 2.645 / −1.766 / 2.631 |
| WebView2 browser | 0.020 / −0.004 / 0.000 | −0.002 / 0.010 / 0.006 | 2.123 / −0.017 / −0.059 | −0.017 / −0.001 / −0.046 |
| WebView2 renderer | 0.203 / 0.220 / 0.203 | 0.206 / 0.222 / 0.205 | 0.090 / 0.041 / 0.070 | 0.089 / 0.000 / 0.000 |
| WebView2 GPU | 0.050 / 0.031 / 0.077 | 0.114 / 0.139 / 0.069 | −0.004 / 0.024 / 0.073 | 0.012 / −0.013 / 0.011 |
| Other Job roles | −0.002 / −0.002 / −0.001 | −0.002 / −0.002 / −0.001 | −0.004 / 0.019 / 0.072 | −0.029 / 0.001 / −0.021 |

The two positive whole-Job handle exceedances track the host role. In R4's
first run, the browser had a positive handle slope alongside a falling host
handle series. Renderer memory slopes stayed in a narrow range across both
collections. GPU slopes were higher in Resources03 runs 01 and 02, and the
host memory slope was higher in runs 02 and 03. These samples identify where
the trends were observed. They provide no handle type, allocation site, or
lifetime evidence. The existing budgets apply to the whole Job.
[R4 samples](../../m1-r4-20261109/soak/runs),
[Resources03 samples](../acceptance/20261110-03/resources/schedule/runs).

### Host handle counts at the end of each soak

Each median uses the last 10 seconds of its named window and ten complete
samples. Plain startup used separate launches. Each soak's four windows have
one stable host PID.

| Resources03 soak | Plain startup | Soak initial idle | Cycle 21 closed | Cycle 100 closed | Final idle | Final minus initial idle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 679 | 683 | 815 | 1,248 | 1,243 | +560 |
| 02 | 680 | 685 | 1,754 | 1,536 | 1,531 | +846 |
| 03 | 681 | 686 | 757 | 865 | 860 | +174 |

The full 120-second final idle windows each have 120 complete samples. The
host count ranged from 1,243 to 1,248, 1,531 to 1,536, and 860 to 865,
respectively. Each ended five below the cycle 100 median, with the last ten
samples flat and above its initial level. These counts show a small net
decrease during final idle. They cannot establish what closed or the lifetime
of the remaining handles.
