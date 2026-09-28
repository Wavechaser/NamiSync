# Latest session — narrow runtime admission and corpus comparison

2026-09-28–29, `milestone1-adelbert`, starting clean at `eaf62d7d`.

## Delivered

Implementation commit `23589bd` removes only adjacent `_resolve_target_path`
admission for the concrete native adapter with its exact reviewed authority in
an active confirmed hold. The resolver retains current held attributes and
all descendant guards. Subclass/custom, unheld, mismatched and malformed paths
retain admission and error ordering. Other source, paired and trash guards stay.
The ACL descendant refusal was already committed as `db03926`; its regressions
passed again. Broader runtime/error-classification work remains deferred while
the user reconsiders those boundaries. No further implementation is pending here.

## Verification

Final tests pass: 496 native/runtime/settlement, 585 executor-department and
5,611 ordinary (four skips, 34 headed exclusions). All 12 import contracts,
settlement 30 × three, guard scan 70 rows/391 effects/zero missing admissions
and 67 qualified baseline comparisons pass. Four frozen files and 492 gate
entries match. The predecessor control detects the duplicate query, and the
subclass-order correction has red/green witnesses. The initial interrupted
ordinary gate and pre-correction receipts remain excluded from acceptance.
Independent review: `executor/independent-review-runtime-narrow-20260929.md`.

## Full corpus

After committing, all five original F: to G: executor bands ran serially with
five samples each, preparation/initial preflight once per band, normal metrics
and readback every sample. All 25 executions/readbacks pass; source identity,
product/rig/driver hashes and manifest-owned target cleanup validate.
Medians for 4 KiB, 128 KiB, 4 MiB, 128 MiB and 4 GiB bands are 3.627, 1.958,
0.372, 0.304 and 2.004 seconds. The first three improve 54.6%, 54.0% and 41.9%
against the retained `db05e317` full-corpus readings. The last two change −2.1%
and +2.5% with overlapping ranges. PERFORMANCE owns full tables and limits.
These endpoint observations include intervening optimizations; they do not
isolate this runtime commit. The current 4 KiB result is 1.077 MiB/s, above the
non-gating goal but slower than the earlier isolated 3.387-second reading.

## Evidence and preservation

Evidence root: `build/root-admission-optimization-20260928/`. Implementation
receipts use `executor/runtime-narrow-*` and `resume/executor-runtime-narrow-final-*`.
Full-corpus receipts use resume prefix
`executor-runtime-full-23589bd3-20260929-000521-7fea29aa`, including raw reports,
comparison, commands, environment and before/after manifests. Retained drivers:
`resume/runtime_full_corpus.ps1` and `resume/runtime_full_corpus_receipt.py`.
Historical reports remain in `build/executor-bench-20260928-db05e317/` and
`build/executor-assessment-20260927/`.
Preserve original `F:\NamiSyncExecutorBenchSource`, the clean `b8baf42d`
comparison worktree, raw/failed receipts and historical recovery refs. All five
new benchmark target roots and sidecars were cleaned by the rig. No unrelated
work is included; no push or worktree cleanup was performed.
