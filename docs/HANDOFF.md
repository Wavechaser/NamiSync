# Session Handoff

Status (2026-08-22): the centrally versioned Progress protocol is implemented
end to end. Executor and verifier reporters publish coherent, self-describing
core event v4 snapshots; workflow/session results retain authoritative
continuation truth; and the browser validates, reduces, rejects, and recovers
the protocol before presentation. Slice 5 still owns stable row projection and
visual consumption.

## Delivered

- Ratified the shared field meanings, transition model, authority precedence,
  Gap/replay behavior, and five-layer evidence model in the central core and
  architecture contracts. `items_done` counts selected items with successfully
  emitted reliable terminal outcomes regardless of category. Aggregate bytes
  are monotonic attempted-work high-water, not evidence of durable publication.
- Bumped only the core event envelope from v3 to v4. Exact Progress now has 11
  keys: `phase` is required and nonempty, while paired item identity and opaque
  32-lowercase-hex `item_attempt_id`/counter state are nullable. Exact
  `SessionEventView` carries the nested core version;
  the bridge remains v1, execution payload remains v5, standalone integrity
  continuation is v2, and database/UI/page schemas are unchanged. Persisted
  reliable v3 history remains readable; v3 Progress is explicitly unsupported
  and Progress is still refused from history.
- Removed the throttle-artifact-preserving executor remedy. Every forced
  boundary derives from authoritative live state: pause retains live aggregate
  and active-attempt truth; cancellation and exceptional unwind settle reliable
  outcomes, publish live aggregate high-water, and clear item identity and path.
  Downstream emission must succeed before session accumulation advances.
- Aligned executor, standalone verifier, and linked post-copy state machines.
  A byte-pipeline entry mints one opaque attempt id; chunks, pause, and overshoot
  retain it; retry/resumed re-entry mints a new id; retained non-byte
  continuations do not. Executor totals stay fixed to reviewed selected content,
  while verifier physical-read budget may grow by incremental overrun.
- Made `item_type` the row-lookup namespace. Executor and linked post-copy
  snapshots use `operation`; standalone integrity uses `integrity`; linked
  reliable settlement remains `IntegrityOutcome`. Unexpected verifier failures
  publish an inactive live boundary without replacing the primary exception.
- Aligned linked post-copy admission authority across telemetry and results.
  Progress now starts from the full continuation's selected-item admission and
  centrally derived physical-read budget, including missing-evidence work;
  direct, resumed, paused, canceled, failed, and overrun paths therefore cannot
  expose a candidate-only `0/0` phase before a nonzero terminal result.
- Exposed `ExecutionSet.bytes_done_high_water` as public equality-significant
  continuation state, retained exact payload-v5 wire shape, and made the derived
  selected-content bound comparison-neutral. Standalone integrity continuation
  v2 carries its physical-read budget and one-way recording degradation.
- Added an O(1) browser reducer behind exact live-v4 validation. It preflights a
  whole drain batch before cursor or callback mutation; enforces phase,
  aggregate, and same-attempt temporal rules; recovers from `Gap` through a
  later self-described Progress; clears activity on matching reliable outcomes
  or terminal truth; and supplies an immutable optional reducer view to existing
  callbacks without breaking one-argument consumers.
- Updated the protected executor settlement oracle only after reporter semantics
  stabilized. Its v4 phase/attempt projection, continuation high-water, token
  lifecycle checks, and reviewed policy outcomes pass all 30 scenarios for
  three identical runs.
- Reworked current event/custody fixtures into truthful v4 transitions and
  production-valid mixed-version history witnesses. Frozen v1 custody
  calibration, ceiling, holdout, validator, and retained sizer remain unchanged.
  Current v4 measurement is diagnostic/Tier-1 drift evidence only, not a new
  calibration or acceptance authority.

## Measurement Disposition

- Clean installed-wheel event run at
  `7ea8e08666b9079dbb402711f1380c91ae90ef9e`: artifact SHA-256
  `7bb456329fa950fa9c7447bb353590e7902d716233a99c035e58d9467168ab8f`;
  6,000 Progress / 600 reliable item emissions over 59.96114979998674 seconds
  at 100.06479228657697 Progress and 10.006479228657698 reliable emissions per
  second; no Gap; all four terminal records. The 1,497 sampled Progress events
  measured 40 ms p95 / 48 ms maximum, and the 620 sampled reliable-plus-terminal
  events measured 3.05 ms p95 / 15 ms maximum. Job-private-byte growth was a
  diagnostic 40,828,928 bytes. Its own `incomplete-without-custody` and
  undefined whole-runtime acceptance remain controlling.
- Clean current-source custody at
  `7ea8e08666b9079dbb402711f1380c91ae90ef9e`: one-child protected guard passed;
  three children were identical at 1,378,867 ordinary bytes / 4,901 objects and
  1,536,994 maximum-no-Gap bytes / 5,499 objects. Those retain 587,213 and
  429,086 bytes of margin to the unchanged 1,966,080-byte historical ceiling.
  Artifact SHA-256
  `a4ba30a99fb3ccc27a20a1fe436ccb8f19ce10e4d7be70572190629abc84ae9c`.
  This is Tier-1 representation/drift evidence only: no v4 custody
  recalibration or empirical-acceptance promotion occurred. `M1_BRIDGE.md` owns
  the full receipts and non-promotion disposition.

## Verification

- Ordinary repository with required Node runtime:
  2,884 passed, 4 skipped, 28 deselected.
- Real WebView2 headed interface gate: 28 passed, 2,888 deselected on the
  immediate repeat. The first invocation's four component-gallery failures
  shared a non-reproducing `WinError 1400` after the native window had already
  closed; its other 24 headed cases passed.
- Schema/facade/history compatibility neighborhood:
  330 passed.
- Protected custody, holdout, and current-source guard:
  65 passed.
- Executor settlement oracle: 30 scenarios x 3 stable runs.
- Import law: 71 files / 257 dependencies analyzed; 11 contracts kept,
  0 broken.
- Installed-wheel event benchmark and final three-child custody
  characterization completed from clean named commits; `M1_BRIDGE.md` records
  their exact scope and authority class.
- The settlement-oracle authority is unchanged after its separately reviewed
  `c90e769` replacement; the frozen custody authorities were unchanged for the
  full delivery. Final repository hygiene: `git diff --check` passed and the
  post-commit worktree is clean.

## Commits

- `1e8b0b0 docs(progress): ratify the versioned progress protocol`
- `63231c8 fix(executor): publish coherent live control progress`
- `bd0dcde feat(progress): publish versioned self-describing snapshots`
- `7407beb fix(progress): align reporter and continuation semantics`
- `62f9dd2 feat(web): reduce versioned progress recovery`
- `985f162 refactor(core): expose execution progress high-water`
- `c90e769 test(executor): update progress settlement authority`
- `9332e5b test(web): align progress measurement fixtures`
- `edab456 test(web): align progress benchmark validator`
- `93cabfb test(web): classify v4 custody representation`
- `400fd5f docs(web): record v4 progress measurements`
- `9a1d42b fix(web): recover self-described phase after gap`
- `7ea8e08 fix(progress): align post-copy admission authority`

## Next Checkpoint

- Slice 5 can project stable operation/integrity row ids and consume the
  browser reducer's phase and active-item state. Join only on
  `item_type`/`item_id`; `current_path` is informational and must not identify
  activity. Render determinate counters only when the attempt byte pair exists;
  active pre-stream and overshot attempts are indeterminate.
- Icons and their existing fixed local infrastructure, explanatory tooltips,
  and click-to-copy full hashes remain intentionally shelved.
- Developers running the ordinary suite must keep Node available through
  `NAMISYNC_TEST_NODE` or `PATH`; the required Progress contract/reducer gate is
  non-skippable.
