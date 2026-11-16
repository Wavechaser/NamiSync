Notes for "Follow-mode allocation reduction (2026-11-08)": text files chosen from `build/follow-allocation-20261108`, `build/follow-memory-20261108/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/follow-allocation-20261108/README.md`

Task-owned ignored evidence for loaded-target Follow and bounded overlapping Plan row reuse. Keep scripts, logs and raw counters through review. Product/tests remain in their existing owners; no study profiles or fixtures are changed.
`headed-receipts/` retains the first two installed execution-review receipts by default/larger size, including captures and wheel/install identities. A final combined native gate will use `headed-final-receipts/` with scenario and size subdirectories. `identity.json` binds final changed source/tests; `row-counts.json` records the contained deterministic panel comparison. Do not remove native Temp or study artifacts during evidence retention.

# `build/follow-allocation-20261108/findings.md`

# Follow allocation implementation

Base: b5b6071ba1b55c8643ec2c95cbfe5fd9b8c91b65.

Product ownership is app.js (loaded Plan target navigation) and plan_review.js
(bounded active committed row reuse). Tests extend existing task_shell_probe and
plan_review_probe. No GC, backend, transport, or verification target changes.

Loaded operation identity is reused only within current view/highlight/session.
Prior-location rows never carry an operation id in the projection, so an exact
loaded match is the canonical operation target. Hidden Settings rejects admission.
Off-window and collapsed targets keep the server anchor path. Local Plan landing
retires exact prior Follow/viewport work using existing generation/cancel rules,
while retaining highlight custody. Same automatic target remains a no-op.

Active committed Plan windows reuse only overlap rows within the same review,
view, highlight, total and nonnull current execution session. Static facts must
match. Only changed execution cells are replaced; unchanged row elements and
handlers remain. Mutable row bindings let retained listeners consume current
facts. No off-window row cache exists. Other projections retain full rebuild.
The orphan executionRefresh flag was removed after eligibility moved to actual
projection identity rather than one background-read producer.

Baseline existing two probes passed. Initial and final focused probes passed.
A test-only absence expectation used undefined instead of the helper's null;
its failed receipt is retained. Review corrections and one mechanism-level
navigation custody adjudication are recorded in navigation-review.md.

First interface department passed 2261 tests before the final viewport-custody
correction. It is retained as pre-correction evidence, not final acceptance.
Final department passes 2,261 tests in 167.62 seconds (interfaces-navigation-final.log). Both installed execution-review sizes pass in 30.24 seconds (headed.log/headed.xml), with real copied-byte/identity/capture and normal host-return assertions.

Paired deterministic panel counts use the existing real rendering fixture under
the standard contained Node runner. One entering row plus one changed execution
row, at widths8/64/256, creates98/770/3074 elements on baseline versus26/26/26 on
candidate. row-counts.json records source/fixture/driver hashes. This is a counted
DOM-work observation, not a timing or heap-footprint claim.

No live app or measuring-session artifact was touched by this builder. Parent
coordinates the separate native memory probe. No branch, worktree or commit.


Final combined native gate explicitly cleared addopts and passed all four cases (task-shell Follow/navigation plus execution-review, default/larger), 53.28 seconds. headed-final.log/xml and headed-final-receipts retain exact child ready/final/capture records, installed/wheel identities and hash-checked copy provenance. The invocation was python -m pytest -q -o "addopts=" -m headed with the two exact installed test nodes. No basetemp override. Original pytest-432 remains owned by pytest; no unrelated cleanup.

# `build/follow-allocation-20261108/navigation-review.md`

# Local Follow navigation custody review

The synchronous loaded-target path must preserve the existing navigation owners.
Two review findings shared bypassed navigation custody: Settings could mutate a
hidden panel, and a coalesced viewport could settle/retry after an explicit local
jump. Parent adjudicated one narrow reorganization before further implementation.

| Boundary | Existing owner | Local landing disposition |
| --- | --- | --- |
| Settings/task/pane | currentReviewTask, settingsVisible | Refuse before either local or asynchronous navigation. |
| Session/view/highlight/action | current review and loaded-window revisions | Reuse only exact matching loaded operation window. No mutation or revision relaxation. |
| Follow request | cancelReviewFollow | Retire exact Follow request on an accepted local jump. |
| Viewport read/retry | windowRequestRevision and viewportRead.cancel | Advance revision before cancel, clear exact viewport intent. Late success/failure/retry cannot overwrite the jump. |
| Highlight/selection | existing highlight/action ownership | Preserve; local Go does not retire additional highlight intent. |
| Same automatic target | cached anchor | No-op, retaining manual within-window position. |

Approved correction factors existing viewport retirement from
interruptPlanNavigation and calls it for PLAN loaded/new target and legacy
cached explicit Go. No new epoch or foreground owner, no Inventory change, and
no broader cancellation primitive. Deterministic blocked/coalesced viewport
success/failure witnesses cover the exact consequence.

# `build/follow-allocation-20261108/review.md`

# Independent review of Plan Follow allocation

Approved for one coherent commit from `b5b6071ba1b55c8643ec2c95cbfe5fd9b8c91b65`.

- The local landing uses the canonical loaded operation in the current task, session, view and highlight. Settings blocks admission. An accepted local Plan landing retires the exact earlier viewport and Follow intent before setting scroll. Late viewport success or failure leaves the accepted window in place. The highlight and selection owners are preserved. The same automatic target retains the current scroll position.
- Renderer reuse applies to active committed windows in the same review, execution session, view, highlight and total. The bounded prior window supplies compatible keyed rows. Structural changes rebuild affected rows. Dynamic cells and listener bindings take current facts. The current row/focus rules still apply. Actual shifted Follow and viewport publications reach this path after removal of the old refresh-only marker.
- All four product and test hashes match `identity.json`. Two focused probes and 2,261 interface tests passed on the corrected candidate. The four final installed task-shell and execution-review cases passed at both sizes with zero skips or failures. Shell raw receipts confirm all six Follow navigation assertions. Execution-review raw receipts confirm exact capture and retention. All four hosts returned with exit 0. The installed assets match the recorded source hashes, and all 20 retained headed receipt hashes match their manifest.
- Replayed `count_rows.mjs` independently under Node v24.22.1. The baseline renderer is the exact Git blob from the stated base. The one-row shifted render with one changed execution row creates 98, 770 and 3,074 elements at widths 8, 64 and 256 on baseline and 26 at each width on candidate. The retained functional witness checks row and listener identity, fresh handler facts, static-change fallback and retirement of departed rows.
- Independently reaggregated all four 10k native runs from `events.jsonl`, `samples.jsonl` and `heap.jsonl`. Renderer private peaks were 976.2–1,079.8 MiB on baseline and 776.3–779.4 MiB on candidate. Sampled DOM maxima were 137,903–159,745 and 64,225–68,455. The raw receipts and aggregate hashes match. Both source variants contain 303 package files and differ only in the two approved assets. All runs used the same Edge runtime and passed exact mirrors, durable audits of 10,100 operations and 10,000 verified target paths, and normal empty-Job exit. These values describe the measured 10k profile.
- The completion register, component documentation, performance table, changelog and handoff match the observed scope and results. The local-link check covered 173 targets and found none missing. `git diff --check` passed.

The independent review performed read-only checks on tracked work and retained the early failure findings and their corrections in `navigation-review.md` and `findings.md`.

# `build/follow-memory-20261108/README.md`

# Follow allocation memory probe

Task-owned ignored evidence. `trees/baseline` freezes package files at
`b5b6071b`; `trees/candidate` will freeze the reviewed candidate after explicit
source freeze. `manifest.json` records every source and helper hash. Scripts
stay here, run logs and raw process/heap/DOM samples live in `runs/`, and owned
WebView profiles in `runs/profiles/`. `fixtures.jsonl` records only newly created
probe fixture roots outside the repository. Existing study sources/profiles and
running applications are never modified.

The bounded diagnostic is two paired fresh-process 10k x 32 B copy+automatic
verification runs, ordered baseline/candidate then candidate/baseline. Keep
default collection policy and Follow target behavior. No heap caps or execution
GC. Require exact file mirrors, unchanged source metadata, clean terminal status,
normal host exit and an empty owned Job. Sampled peaks remain diagnostics, not a
release budget or a claim about 100k. Fixtures and evidence remain for review;
cleanup must be exact registered paths only and is not automatic.

`manifest-baseline.json` preserves the initial manifest used by baseline-01 and
its durable audit. `manifest.json` adds the candidate freeze without changing
the common measurement driver. Git archive produced CRLF text on this checkout.
`freeze_candidate.py` copies all baseline bytes unchanged except the two approved
assets, serialized in that same CRLF style, and compares all 303 package files
against normalized checkout bytes. Its initial precheck assumed LF archive text
and refused before creating a candidate directory; the corrected freezer records
both raw and normalized checkout hashes. No measured source was changed.

Each run has a two-second passive terminal-settled delay before Close, identical
across arms, to avoid the separately reported very-early close gesture race.
`audit.py` audits copied closed-profile ledger/history databases and verifies
10100 exact operations, 10000 verified target paths and exact Execute/Verify
phase totals. It records original database hashes and confirms no original
database mutation. This remains a source-host diagnostic, not installed-package
release or long-run stability acceptance.

The first candidate freeze was never launched. Independent review corrected
navigation custody before final measurement. Its exact tree and manifest remain
in `trees/candidate-pre-review` and `manifest-pre-review.json`. The final
`trees/candidate` is refrozen from the approved checkout, again with exactly the
two raw asset differences from baseline and normalized equality for all 303
package files. Native candidate runs wait until interface and installed headed
gates finish, avoiding those heavy test jobs during the measured intervals.

# `build/follow-memory-20261108/results.md`

# Follow allocation native comparison

All four runs passed. The sampled peak reduction is consistent across both
10k pairs, with the final Follow behavior retained. These are bounded source-host
diagnostics, not installed-package release, 100k, throughput or long-run leak
acceptance.

## Method and provenance

- Baseline: frozen package source at `b5b6071b`.
- Candidate: approved checkout, exactly `app.js` and `plan_review.js` differ.
  All 303 package files match the checkout after newline normalization. Baseline
  archive text is CRLF here. Candidate copies every unchanged baseline byte,
  and the two changed assets use that same CRLF style. Both raw checkout and
  normalized hashes are in `manifest.json`.
- Order: baseline-01, candidate-01, candidate-02, baseline-02, one fresh native
  process/profile/Windows Job per run. Baseline-01 preceded final implementation;
  the remaining three ran sequentially after the final ordinary interface and
  initial installed headed gates, with no heavy test job alongside them.
- Same own 10,000 x 32 B source, 100 directories, fresh registered H: target for
  each run. Source is read/hash/metadata checked before and after each run.
  Existing study fixtures/profiles and measuring applications were untouched.
- The unchanged resource collector samples Job process private memory every
  second. `probe.py` adds heap and DOM samples around its half-second predicate
  polling. Native CDP gestures go only to the owned page. `wrapper.py` counts
  bridge commands without changing the collector, Follow or GC behavior.
- Same Edge `157.0.4341.42`, V8 `15.7.11.4` and revision in every run. Manifest
  hashes Python and 194 relevant pywebview/pythonnet/clr-loader/xxhash/cffi files.
  Source, runtime and helper identities are checked before and after each run.
- Default production GC stays enabled. No execution GC, heap cap or memory
  target is added. Every run uses the same two-second passive terminal-settled
  delay before Close and a ten-second post-Close observation window. The delay
  avoids the separately reported very-early Close gesture race without fixing
  or accepting that unresolved report.

`manifest-baseline.json` binds the initial baseline audit. `manifest.json` adds
the final candidate freeze. The first, never-launched candidate freeze remains
in `trees/candidate-pre-review` and `manifest-pre-review.json`. The only producer
precheck failure assumed archive LF and stopped before creating a candidate
directory. Its correction affected only freezing, not the common measurement
driver or any measured source.

## Observations

Whole-run private-memory maxima all occurred during `task-execute`, which
includes Execute and automatic Verify. DOM, listener, embedder and V8 figures
below are maxima among samples in that phase. Columns contain ranges over two
fresh processes per variant, not confidence intervals or hard bounds.

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Whole-app private peak, MiB | 1,400.1–1,505.0 | 1,201.1–1,212.1 |
| Renderer private peak, MiB | 976.2–1,079.8 | 776.3–779.4 |
| DOM nodes, sampled phase maximum | 137,903–159,745 | 64,225–68,455 |
| JS listeners, sampled phase maximum | 51,035–59,091 | 16,435–16,466 |
| Embedder heap maximum, MiB | 415.14–483.56 | 212.04–220.83 |
| V8 used heap maximum, MiB | 372.26–373.16 | 335.01–337.55 |
| `get_plan_window` calls, whole run | 340–347 | 271–281 |
| `get_plan_anchor` calls, whole run | 213–219 | 52–57 |
| Execute + Verify phase, seconds | 118.3–121.6 | 117.2–121.2 |

This supports reduced request/DOM churn and lower sampled peak footprint on
this fixture. It does not establish a throughput gain. Natural collection timing,
background activity and sample intervals remain variable. It does not claim
that restored verification Follow costs as little as the old behavior that did
not follow those settled items. Post-Close whole-app medians overlap
(532.6–583.4 versus 524.9–541.1 MiB), so no separate reclamation improvement is
claimed.

## Correctness and cleanup

Each run reports successful terminal completion and passes exact 10,000-file
SHA-256 mirror, unchanged source hashes/metadata, unchanged frozen source,
runtime and helper checks. All four apps exit 0 normally with empty owned Jobs.
`audit.py` independently copies the closed profile's SQLite database/WAL/SHM
files, then verifies exact 10,100 successful operation identities, 10,000
verified target paths and exact Execute/Verify history totals. Original database
hashes are unchanged by auditing. No accepted run failed or was retried.

`summary.json` is produced by `report.py` from raw receipts and pins their
hashes. `identity-check.json` verifies both frozen trees, current raw checkout,
exact two-file source delta, common measurement dependencies and all aggregate
receipt hashes. `runs/runs/<name>/` holds events, process samples, heap samples,
result, summary and audit receipts. `runs/profiles/<name>/` holds owned profiles.

No native app/process remains. Registered fixture roots, profiles, frozen trees
and ignored evidence are retained for independent review. No tracked files,
branches or worktrees were changed by this lane. Cleanup, if later requested,
must use only the exact roots in this directory's `fixtures.jsonl`.
