# NamiSync Handoff

Date: 2026-07-18

## Session Outcome

Sanity-checked the revised `FEATURES.md` and `ARCHITECTURE.md`, including the
seven DR-25–DR-31 resolutions and the stronger executor-side TOCTOU language.
The seven original propagation blockers are resolved coherently and have been
propagated into the focused module contracts. The authoritative documents were
not edited in this session.

Updated module docs:

- `CORE.md`, `DISPATCHER.md`, `WORKFLOWS.md`: per-kind pause capability,
  payload-free control unwind, runner-owned terminal, independent filesystem /
  ledger / audit axes, timeout-bounded history backpressure, and typed
  `Disposition`.
- `SCANNER.md`, `INVENTORY.md`, `DATABASE.md`: all-directory `DirRecord`,
  `supports_hardlinks`, policy-depth ADS manifests, stream-aware retained
  metadata, and result/disposition persistence.
- `PLANNER.md`, `PREFLIGHT.md`, `EXECUTOR.md`: workflow-owned fresh preflight,
  profile-aware no-hardlink capacity, crash-safe trash backup copy, explicit
  mkdir-with-metadata dependencies, ADS/ACL failure semantics, and per-operation
  live TOCTOU guards.
- `VERIFIER.md`, `HASH_IMPORT.md`: verify/baseline item-status pause
  continuation and explicit pause refusal for import.
- `HISTORY.md`, `RECORDER.md`, `COMMANDLINE.md`, `INTERFACES.md`,
  `DESKTOP_UI.md`: audit degradation, timeout behavior, axis-separated
  presentation, and `CANCELED+UNRUN` queue-discard rendering.
- `README.md`: documentation index now describes `DESIGN_REVIEW.md` as the
  resolved decision ledger rather than an unresolved-issues list.

The old blocker paragraphs were removed. New review notes below are retained in
the affected focused docs instead of silently filling holes in the authority.

## Sanity Findings Requiring Review

All six findings below were resolved on 2026-07-18: decision records live in
`DESIGN_REVIEW.md` as DR-32 through DR-37, and `FEATURES.md`/`ARCHITECTURE.md`
are updated to match. Notably, finding 1 was resolved by deferring ADS
preservation wholesale (DR-32, superseding DR-27's ADS half). The original
statements are retained for context.

### 1. Policy-driven ADS scan has no contract input

Architecture keeps `scan(root, ignores, ctx)` / `ChangeSource.scan(root, ctx)`,
but also says the scanner enumerates stream manifests only when the mapping's
preservation policy requests ADS. A role-free scan cannot infer that policy and
one location can participate in mappings with different policies. Add a typed
metadata projection/scan-depth input or a separate enrichment operation.

Related: `MetadataSnapshot` references `StreamInfo` without defining its type,
canonical ADS name syntax, duplicate handling, supported stream types, or
validation. Those are serialization/path-safety bones and should freeze before
schema/code.

### 2. Fresh execution observation is contradicted once

Features and Architecture §4.9 require `run_execution` to always re-observe and
re-preflight. Architecture §4.4 still says review and execution start can share
an observation when close in time. Time closeness is not evidence of unchanged
state. Focused docs retain the safer rule: execution/resume/queue wakeup always
observe fresh.

### 3. Immediate re-stat is not an atomic TOCTOU condition

The new per-operation guards are necessary and materially improve the design,
but a path-based stat followed by `os.replace`, rename, or delete still permits
an external process to swap the path between calls; NamiSync volume locks only
coordinate NamiSync. Architecture simultaneously promises no overwrite of an
unexpected target.

Define the conditional Windows primitive/handle protocol per operation (for
example non-replacing destination creation/rename where absence is expected,
and object-conditional source mutation where available), or explicitly state
which external-writer races remain residual. Fault tests must exercise a swap
between final guard and destructive call, not only drift before the guard.

### 4. Audit status and Terminal finalization are circular

History consumes `Terminal` to finalize the history row, but
`Terminal.result.audit` must already report whether that final write succeeded.
If history fails while consuming Terminal, ordinary subscribers have already
received an immutable result claiming `audit=OK` unless event delivery has a
special ordering contract.

Define a bounded two-phase terminal acknowledgement or equivalent: history must
attempt/ack finalization before the one immutable Terminal is released to
ordinary subscribers, without history consuming a second contradictory
Terminal. Timeout/failure then sets `audit=DEGRADED` and releases blocking.

### 5. Runner aggregation needs an unwind-emission rule

Architecture says the runner assembles cancel/failure results from already
emitted reliable outcomes, but a checkpoint can raise during an item and
unreached selected items have not emitted anything. Focused executor/verifier
docs now require an unwind finalizer to emit current/unreached canceled outcomes
before re-raising. Put that obligation in the authoritative runner/module
contract (or give the runner a generic item catalog/status accessor).

Also correct §2.2a's phrase “Terminal results for cancel, pause, and failure”:
pause emits no Terminal.

### 6. A few Architecture assertions still use pre-resolution wording

- `DeliveryClass.RELIABLE` and dispatcher acceptance say admission-time reliable
  events are never dropped, but non-history subscribers may be ejected and
  history may time out with `audit=DEGRADED`.
- Database acceptance still calls filesystem/ledger/audit “two-axis truth.”

These are documentation defects, but they should be corrected before tests are
named directly from those acceptance criteria.

## Verification

- `git diff --check` passes.
- Focused docs contain no old DR-25–DR-31 blocker language.
- `FEATURES.md`, `ARCHITECTURE.md`, and `DESIGN_REVIEW.md` are unchanged by this
  propagation pass.
- No runtime tests were run; changes are documentation-only.

## Next Work

Findings 1–6 are resolved in the authoritative docs (DR-32 through DR-37):
ADS deferred wholesale to a latent seam; fresh observation per judging
session; operation-matched conditional primitives with documented
external-swap residual; bounded two-phase audit finalization before Terminal
release; the module-side cancel-unwind finalizer (nothing emitted on pause);
and the stale "never dropped"/"two-axis" assertions reworded. DR-32 has since
been amended: executor-time ADS enumeration is promoted from sketch to settled
contract (still deferred executor flesh — no scan input, mtime-driven re-copy,
mapping-level incapable-target warning, uncounted stream bytes and unattested
stream content as documented residuals), and DR-34 gained the platform-floor
note (Explorer's replace flow shares the window; TxF is deprecated).
Remaining: remove the corresponding explicit review notes from `CORE.md`,
`SCANNER.md`, `HISTORY.md`, and `EXECUTOR.md`, propagate the DR-32–DR-37
details into the module drafts, then freeze the M0 bones.
