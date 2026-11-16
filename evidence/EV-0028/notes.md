Notes for "Projection tuning (2026-11-09)": text files chosen from `build/projection-tuning-20261109/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/projection-tuning-20261109/README.md`

# Projection tuning evidence

Task-owned diagnostic scripts, source snapshots, raw runs and summaries.
Keep baseline/candidate and failed attempts in separate named files. No product
inputs or accepted performance budgets live here. Retain evidence at closeout;
disposable native profiles/installations, if any, may be removed only after their
processes exit. Do not touch other build directories or measuring-session data.

# `build/projection-tuning-20261109/findings.md`

# Projection tuning diagnostic findings

Base: `c4fb6340`. Product candidate changes only `_append_operation_tree` in
`namisync/workflows/plan_projection.py`: extract the basename once, casefold once,
share the original display string when the folded value is equal, and reuse
that key for any operation members. No public fields, constructor, freezing,
path spelling, sorting semantics, caches, GC policy or budget changed.

## Method and source identity

`baseline/` and `sharing/` are exact 303-file source-package snapshots, not
installed-wheel evidence. `source-identity.json` records their hashes;
`verification.json` verifies the sharing snapshot still matches the checkout,
and the only differing package path is `workflows/plan_projection.py`.
`descriptor-trial/` is an ignored experimental derivative of sharing; its
copied `source-identity.json` identifies the sharing input, while the exact
trial hashes are recorded separately in `verification.json`.

The existing bounded `tools.performance._child.run_child` launches each fresh
process with its named snapshot first in PYTHONPATH. The diagnostic wrapper
asserts the actual imported package path and records Python 3.13.17. It calls
the existing `run_component_child` with the unchanged fixture contract, whose
result correctness checks remain active. All children exited successfully.
No native app was launched. Product/tests were frozen during measurements.

Three fresh children per arm per metric, serialized: baseline/sharing order
in repetitions 1 and 3, reversed in repetition 2. Existing 120k base, 240k
information-heavy and two-state construction-overlap fixtures are unchanged.
No acceptance collection, quiet-machine or runtime-profile certification is
claimed. Timings drifted materially during the session and exceed the earlier
1.82 s base observations for both baseline and candidate.

## Minimal sharing results

| Metric | Baseline, three children | Sharing, three children |
| --- | --- | --- |
| Base cold ms | 2263.20, 2200.54, 2189.90 | 2169.23, 2127.59, 2225.64 |
| Heavy cold ms | 3289.21, 3124.40, 3329.21 | 3384.11, 3176.66, 3097.08 |
| Incremental peak private bytes | 324644864, 324018176, 324440064 | 310128640, 306835456, 309129216 |

The peak metric fell in all three comparisons: about 13.84–16.39 MiB, mean
14.94 MiB (4.83%). This is sampled construction-overlap private memory, not
settled/live-object size or a leak guarantee. Earlier object census identified
6,139,876 shallow bytes of equal-but-distinct sort-key strings per fixture;
allocator and intermediate-lifetime effects are not separately attributed.
Timing comparisons are mixed; there is no stable speed-improvement claim or
repeatable timing regression established by this small diagnostic collection.
Keep this small change for its consistent memory reduction.

`comparison-baseline-sharing.json` and individual raw receipts contain all
measurements/correctness values. SHA-256 fingerprints over every node field
match exactly for base and heavy in both arms; published values are unchanged.

## Descriptor trial, deliberately not shipped

`prepare_descriptor.py` creates an ignored snapshot replacing generated frozen
initialization only within materialization: bind 35 slot setters once, allocate
the same class with `object.__new__`, set all 35 fields, then preserve existing
draft release and final projection validation. The public class is unchanged.
This adds a second explicit initialization mapping and about 35 binding lines.

Three additional paired base measurements, sharing → descriptor, in ms:
2471.14 → 2088.51; 2149.46 → 2020.04; 1881.99 → 1608.84. Order alternates
as above. Each pair favors the trial, but both arms fall substantially with
time, so these do not provide a stable saving estimate. Base/heavy full-field
fingerprints match the baseline exactly. Heavy timing and a full behavioral
gate were not run for this unshipped trial. It is a credible future lever if
needed, but the extra field-initialization maintenance is unnecessary for the
current modest optimization scope.

## Verification

The first focused projection/review run passed 105 tests. Final group-sharing
assertions additionally establish two real member children with distinct action
labels. A frozen-baseline negative control running the current focused tests
fails exactly three sharing assertions while both nonsharing Unicode/casefold
cases pass (3 failed, 2 passed, 49 deselected); checkout source was not swapped.
Final workflows/interfaces neighborhood: 3,257 passed, 3,281 deselected in
231.27 seconds (`neighborhood-01.log` and JUnit). All intended new tests and existing raw Unicode,
selection, topology and view behaviors are included there.
