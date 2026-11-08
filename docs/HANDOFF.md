# Latest session — table cadence and integrity delivery, 2026-11-08–09

## Delivered changes

Base `39255ca30672a0d978a9e8ad423b389cbbd27244`, branch `milestone1`.
The user approved the final split for both tables: 250 ms local cursor/progress
painting and exact/cached loaded landings; 500 ms routine automatic full-window
reads and potential Follow jumps. One timer keeps independent clocks, with
actual dispatch stamps preventing early successors after slow anchors.
Explicit, reentry and first/control/phase/Gap/terminal paths stay immediate.
Latest demand, foreground/read custody and exact highlighted detail are preserved.

Automatic Inventory loaded-row Follow, passive coverage clamping, direct Plan
dynamic-cell updates and current detail-node reuse reduce allocation. Successful
ordinary and linked integrity outcomes share COPY's fixed wakeable 25 ms
collection, retaining ordered individual delivery and urgent bypasses. This
does not batch filesystem operations or durable recording.

## Verification and observations

Final interface gate: 2,289 passed, 4,237 deselected in 173.16 seconds.
Seven installed/API-floor cases pass
across five initial passes and two unchanged-candidate retries. The initial
confirmation-dialog Tab observations failed before execution, outside the new
scheduler path; no product/helper/assertion change was made for the retry.
Focused clock tests cover local250/read500, nonstarvation, held ownership,
late anchors, stale/failure/recovery and immediate exceptions. All 295 drain
tests and both packaged drain consumers pass. Independent review and local
document/diff checks pass.

Separate native delivery compares 1,327 exact ordered reliable identities
through production browser validation: six sessions, four 256-subject integrity
populations, no Gap, exact terminal/record/release order and two successful closes.
The first diagnostic title-fixture mismatch is preserved; a fresh retry passes.

Eight matched performance runs preserve baseline, frontend-only, first
integrated and final 303-file freezes, unchanged measurement helpers and exact
durable/mirror/source/runtime audits. Final Inventory full reads fall 83–85%
and renderer peaks 73–75% (327–357 versus 1,246–1,367 MiB). Plan changes from
157.98 to 135.68 seconds, 320 to 260 windows and 840 to 644 MiB. Its renderer
CPU still rises 12.2%, despite lower host CPU and total duration. Local painting,
full-window decode/validation, row comparisons and entering/changed cells remain
costs. These single-run diagnostics are not leak, stable throughput or 100k claims.

Evidence: `build/read-cadence-20261109/` owns final cadence/gates/review;
`build/cadence-measurement-20261108/final-summary.md` and `comparison-final.json`
own four-way measurements. `build/refresh-cadence-20261108/` retains earlier
functional gates/failures; `build/render-costs-20261108/` owns corrected full-asset
26→15 Plan element counts; `build/integrity-drain-20261108/` owns native delivery
and drain controls. PERFORMANCE holds the full tables and provenance.

## Resumption and operational context

Recovery `ce09180e` on `codex/wip-20261109-0022-table-cadence` preserved the
unfavorable intermediate candidate and handoff. After the user's approval it
was restored as uncommitted work and rebuilt into this delivery, never merged
or cherry-picked. Its reference and evidence are deliberately retained; it is
not a merge unit. No worktree was created or unrelated dirty work absorbed.

All owned native apps/producers exited normally with empty Jobs. Measuring-session
apps/profiles/fixtures were untouched; retain registered diagnostic fixtures.
The optional table-loading profiler's pre-existing bridge anchor mismatch stays
deferred; changed app/Plan/tree transforms parse, without certifying the whole
profiler. The suspected Inventory detail status-cache bug was disproved.

GC policy, heap limits and row limits are unchanged. Verification pipelining,
grouped durable recording and small-file batching remain M2. Prior close,
resource and path studies stay in their existing owners.
