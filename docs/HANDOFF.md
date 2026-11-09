# Latest session — Plan margin investigation, 2026-11-09

## Outcome

Inspected `6673fc43` on `milestone1`. Documentation-only correction and
investigation; no product, driver or test implementation, no native app launch.

- The earlier 17.9 MiB folder-path attribution was wrong. Its allocation site
  creates existing node IDs. The ten additional node slots cost 27.47 MiB
  across 360,000 nodes; this retained-object calculation does not decompose
  the historical construction-overlap private-byte peak difference.
- A census of both reference fixtures found only 60 strings / 10,586 bytes
  per fixture exclusive to `path` among the inspected artifact/node fields.
  Most paths already share objects. This is not process-memory savings;
  further aliases can only reduce that bound. Do not implement path removal
  or derivation on the basis of the previous 17.9 MiB claim.
- Both table-loading failures have one stale instrumentation anchor after
  `cbf3f090`: direct settlement now uses `native.response`. The proposed
  correction must change both the anchor and observer argument, keep the
  settlement-before-ACK boundary, and must not restore the removed clone.

## Verification and evidence

- Projection census covers 120,000 base and 240,000 heavy nodes. Source and
  historical allocation-site inspection corroborate the correction.
  `build/projection-investigation-20261109/` contains the helper, complete
  occupancy JSON and `findings.md` with ownership and verification seams.
- Table-loading focused reproduction with an owned temporary directory:
  two failures, 40 passes (`focused-tests-owned-temp-02.txt`). All 15 anchors
  inspected, only one absent. In-memory correction parses four modules and
  passes the existing bounded Plan bridge probe: 125 observed window requests,
  zero pending, complete response timing fields. No installed timing renewal.
  `build/table-driver-investigation-20261109/summary.md` indexes successful
  evidence and retained sandbox/helper failures.
- [PERFORMANCE](PERFORMANCE.md#current-source-br-g-42-diagnostics--2026-11-09)
  owns the corrected results. Historical budgets and R3 acceptance remain
  unchanged; earlier current-source diagnostics are still diagnostics.

## Recommended next scope

1. Repair the optional table-loading hook independently. Verify focused/tools
   tests, fixture checks and one owned installed probe per table; retain
   fail-before-write and byte-for-byte restoration controls.
2. Trial a private materialization-only constructor for the same frozen node
   class, with full-field parity, immutable/public-constructor behavior,
   selection replacement and sorting tests. Existing descriptor microbenchmarks
   suggest about 100 ms at 120k nodes; a full candidate has not been measured.
3. Defer sparse metadata representation. Seven fields replaced by one optional
   record could save about 16.48 MiB on these sparse fixtures, but fully
   populated workloads could cost about 40 extra bytes/node. Public constructor,
   dataclass replacement and direct consumers require a separate design.

Tree/draft loop simplifications remain profiling candidates. No combined
builder rewrite, validation removal, performance-budget change or acceptance
promotion is authorized by this investigation.

## Operational context

No task-owned native process remains. Ignored evidence is retained; unrelated
cleanup and measuring-session resources were untouched. Earlier cleanup logs
remain under `build/cleanup-20261109/`; old inaccessible pytest folders and
other sessions' temporary folders were not part of this task.
