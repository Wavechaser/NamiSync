# Latest session — direct-write follow-up review

2026-09-30, `milestone1-adelbert`, base `6b116a58`. Validated the user's three
minor observations. Runtime behavior is unchanged; the follow-up clarifies
ownership/compatibility and strengthens an existing native regression witness.

## Decisions and verification

- Preserve sector staging for ordinary BinaryIO inputs and unaligned custom
  chunk sizes. A blanket alignment assertion would reject supported callers.
  Existing 512/4096-sector tests now require aligned bulk input to make one
  native write at its original address, preventing accidental staging.
- Do not add a speculative `BufferError` catch. Consumers receive derived views;
  a retained Python view or C export of a child does not prevent parent release.
  A C export of the exact private parent does, but no supported consumer receives
  it. The executable CPython probe preserves all three observations.
- Keep per-file geometry queries. No cache or unbuffered source read was added.

Eight focused tests and all 640 executor tests pass as the actual user with
default pytest temp. Independent source/evidence review found no blocker.
Receipts are under `build/executor-simplification-20260929/differential/`:
`result8-followup-focused.log`, `result8-followup-executor.log` and
`result8-followup-release-probe.json`. The probe source is
`scripts/probe_memoryview_release.py` in the same task evidence root.

## Immediate context

`b9c4ad3e` fixed subclass admission delegation; `6b116a58` delivered the blanket
8 MiB direct-write policy. Its official committed-baseline oracle passed all
30 scenarios three times (`result8-oracle-official.log`). M1_PLAN retains its
ordinary-test and classified differential dispositions; PERFORMANCE owns all
25 readbacks and measurements. The 4 GiB median was 0.909 s / 4,505 MiB/s;
the small-file result was 1.40 MiB/s, below the 1.6 MiB/s goal. Those measurements
remain attributed to their original product/driver hashes.

Recommend deferring unbuffered source reads pending a controlled cold-source
comparison with integrated throughput and cache-pressure evidence. Historical
standalone read probes suggest a lead, but are not directly comparable to the
current repeated-source pipeline. No read refactor or new probe is active.

Original F benchmark sources, retained failure receipts, and the unrelated
detached `b8baf42d` worktree remain untouched. The earlier invalid workspace-temp
fixture was already removed with exact hashes retained; no new fixture or
recovery worktree was created in this follow-up.
