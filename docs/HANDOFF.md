# Latest session — guarded preflight invocation holds

2026-09-28, `milestone1-adelbert`. Core/executor attribute correction is
integrated as `8cdd669`, after executor holds `90b57646` and core `6536c04`.
Preflight's three recovery files were rebuilt from `7eb8c19d`; the complete
candidate adds a current held-handle attribute guard before its sole cached
admission return. All five observation families retain existing dispatch,
refusal/error boundaries, physical resolution, leaf/parent/trash checks and
fallback. Invocation state is invalidated on exit, including copied contexts.

## Verification and measurements

Evidence root: `build/root-admission-optimization-20260928/`.

- `preflight/resumed-frozen-inputs.json`: product SHA256
  `983EFB8F4445C227A78B45368683450AD6BAECFFFEABB54CA82273E61DC2EFD8`, tests
  `57852556DDBD9B1E4FAB36CB0D6A676F2347F46B1B2DCD19F5F2EAACF67BFE83`, doc
  `A5B1F38FAE6B94499C499E66EF6793956D49B4717273863347DE902406AB2534`.
  All old tests remain. 92 focused and 314 direct-consumer tests pass, including
  attribute-only junction conversion refusal at all five backend methods and
  typed placeholder/query-failure handling before further path work.
- `resume/preflight-guarded-*`: 5,480 ordinary passes, four privilege skips,
  34 headed deselections; 12 imports; unchanged settlement oracle 30 × 3;
  guard scan 70 rows/391 effects/zero missing admissions. All 492 input/output
  hash records match.
- `differential/runs/candidate-preflight-guarded-de75f6c180eb45979f357bb73a7471a8`:
  46 groups, zero unexpected differences. Three required preflight swaps are
  blocked; mixed source fallback stays strict; pre-execution behavior remains.
  Prior executor groups pass. Unchanged producer `243d2173` and checked baseline
  pair are reusable; frozen product/test/doc hashes match after capture.
- Same unwrapped driver and empty G: target, three serialized samples after
  gates: median observation 2.722 seconds at baseline `b8baf42d`, 0.551 seconds
  at candidate; pure judgment about 0.010 seconds on both. The candidate includes
  earlier core improvements. Source scan/target emptiness/manifests/cleanup pass.
  Separate project binding counts: anchor 4,009→3, volume information 2,005→3,
  two holds/final-path confirmations and 2,002 current BasicInfo queries.
- F:→K: exFAT BA1F1F45 observation-only and counted runs pass with those same
  candidate counts and successful source/empty-target checks. Their elapsed
  times overlapped ordinary tests and are not performance evidence. No executor
  copy was attempted. PERFORMANCE owns methods and limitations.
- Independent whole-outcome review approves source, tests, measurements and
  documentation without actionable findings:
  `preflight/independent-review-guarded-preflight-20260928.md`.

## Immediate continuation

Preflight is ready for its atomic commit. Then follow the user's order:
verifier, then further executor optimization.
`verifier/next-verifier-design.md` holds the read-only finite proposal inspected
at `8cdd669` plus frozen preflight. Two atomic outcomes: invocation holds with
current-attribute checks and explicit native-reader handoff, then sector size
from the opened file handle with existing capability/error fallback. M1_PLAN
must record each activated population/gate before implementation.

The native FileStorageInfo16 query succeeds on NTFS and exFAT, matches old
512-byte logical sector observations, closes handles and preserves stat facts.
Raw split-context receipts and the first access-denied probe are retained in
`verifier/`; no verifier product/tests have changed. Public reader protocols,
wire/identity/recording contracts and all per-file snapshots remain protected.

## Prior correction and accounting

Core `RootHold.require_ordinary()` queries FileBasicInfo0 before admission reuse,
rejecting reparse/placeholder state and query failures. BasicInfo works on K:
where FileAttributeTagInfo9 failed with 87. Write sharing, root flushes and child
operations remain. NTFS nonempty root/ancestor conversion refuses with 145.
The existing DEFENSE quiescence rule covers the check/use interval.
`rootguard/independent-review-held-attributes-20260928.md` approves that correction;
its guarded executor measurement was median 15.271 seconds / 0.256 MiB/s, still
below the 1 MiB/s goal. Later executor changes require their own concrete scope;
no descendant-check retirement is inferred from probability arguments.

Retain recovery refs `7eb8c19d`, `cfcc6ef` and `0a04921` until final accounting.
Never merge/cherry-pick WIPs as-is. Preserve native fixtures, ignored receipts,
F: corpus and managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. No remote, unrelated stash/branch,
or user work was changed. The separate K: executor FileIdInfo compatibility
issue remains deferred in BUGS; this preflight result does not fix or accept it.
