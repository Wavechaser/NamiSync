# Changelog

This file is the detailed task history. Entries are newest-first and use three
levels: `##` for a milestone or released version, `###` for a phase, and
`#### task (YYYY-MM-DD)` or `#### task (YYYY-MM-DD – YYYY-MM-DD)` for a
task-level delivery. The date or date range covers the summarized delivery;
related sessions and commits stay under one task. Before adding a new task,
first decide whether the session advances an existing one; extend that entry
when it does, and create a new task only when no existing entry accurately fits
the outcome. `README.md` repeats only milestone and phase summaries.

Before named releases, milestone headings use names such as `M1`. After
versioning begins, headings use the version and codename, such as
`v0.1.0 "Gertrud"`.

## M1

M1 expands the reviewed-sync runtime into a complete headless integrity,
history, and workflow product while building its secured headed WebView2 shell.

### M1 Performance

Executor, verifier, Plan and development measurements use the fixtures,
provenance and comparison limits in [PERFORMANCE.md](docs/PERFORMANCE.md).
Observed speed is diagnostic; component acceptance and safety remain with their
owning contracts.

#### Deliver bounded direct target writes (2026-09-29 – 2026-09-30)

- On supported local volumes, copies at or above 8 MiB use aligned unbuffered
  target writes with one 32 MiB bounded buffer pool. Hashing consumes borrowed
  real-byte views before buffer reuse; arbitrary input chunk sizes, tail padding and
  exact logical EOF retain the same handle through metadata, one flush and
  atomic publication. Remote roots, unknown geometry and refused direct opens
  fall back to buffered writes before streaming; a later write or EOF failure
  fails the private temp without publishing or switching modes. Source reads
  remain buffered; unbuffered reads are deferred to M2.
- Create the exclusive temp before attempting guarded leftover recovery, and
  give regular-file single-chunk buffered copies a synchronous EOF-proven path.
  Preserve custom `BinaryIO` backends, pause/cancel, error identity, pool release,
  recorder ordering and verifier readback. A follow-up confirmed aligned bulk
  writes use the original buffer address and one native call without changing
  runtime behavior.
- Native failure and ownership controls, copy-to-ledger-to-verifier integration,
  5,720 ordinary tests and, after one obsolete assertion was corrected, 95 audit
  tests, imports, oracle and differential review,
  and all 25 production readbacks passed. Five-band medians were 2.789 / 1.474
  / 0.351 / 0.129 / 0.909 s. The 4 KiB band reached 1.40 MiB/s but its goal
  remains unmet; the 4 GiB band reached 4,505 MiB/s. Device-specific standalone
  threshold candidates were studied but did not alter the chosen blanket 8 MiB
  policy; PERFORMANCE keeps their samples and comparison limits.

#### Consolidate executor and verifier work without claiming a speed lift (2026-09-29 – 2026-09-30)

- Reuse planner-used metadata facts, a fresh COPY/MOVE_UPDATE target observation,
  and admitted own-effect file versions while keeping UPDATE, retries, final
  target-root admission, conditional publication, durable settlement and
  recording independent. Retain the native temp handle across finalization.
  Remove duplicate source/target observations, method-identity dispatch,
  conversion-only probes and the verifier's duplicate placeholder classifier.
  Delegate held-root admission only for concrete `NativeFileSystem`; subclasses
  keep their resolver admission. The pre-existing NORMAL→ARCHIVE rename/hardlink
  mismatch was fixed through own-effect version recognition and marked resolved
  in BUGS.
- Each reviewed outcome passed its ordinary, import, settlement-oracle and
  differential gates with native refusal and recovery controls. Across the
  sequential 25-readback bands, predecessor ranges overlapped and no isolated
  throughput lift was established. The final pre-direct-write 4 KiB/4 GiB
  medians were 1.169/2,128.908 MiB/s. PERFORMANCE holds all samples, the F: occupancy
  correction, ACL/fixture provenance and limits on cross-run attribution.

#### Reduce root-admission cost with invocation-scoped holds (2026-09-27 – 2026-09-29)

- Core holds an admitted local root only after exact normalized final-path
  confirmation. Executor, preflight and verifier reuse the hold for one
  invocation with fresh handle attributes before each access; descendant guards
  remain, and remote, unholdable, uncorroborated or custom paths retain
  per-access admission. Native path conversion, checked leaf snapshots and
  volume/geometry observation were reduced without caching filesystem truth.
  A fail-open descendant walk was separately corrected: only not-found ends
  the walk; permission and observation failures refuse access.
- The final five-band root-admission run passed 25 executions/readbacks and the
  unchanged differential/oracle gates. Its 4 KiB median was 3.627 s / 1.077
  MiB/s, compared with 7.992 s in the retained full-corpus predecessor and
  28.248 s before optimization; those runs do not isolate one mechanism.
  Preflight's 1,000-file observation fell from 2.72 to 0.55 s, and verifier's
  1,000-file run from 3.885 to 1.998 s before its handle-geometry improvement.
  Evidence remains in PERFORMANCE. The separately observed exFAT
  handle-metadata compatibility issue remains deferred.

#### Establish current measurement tooling and Plan-scale evidence (2026-09-15 – 2026-09-27)

- Move optional Plan, installed receipt/UI, bridge-event and history samples
  into `python -m tools performance`, retaining raw samples, runtime/source
  identity, bounded children and honest incomplete reports. PERFORMANCE owns
  methods and historical results; DEFENSE owns evidence authority. The stale
  bridge-event diagnostic was repaired for event v5, then completed its
  60-second installed run; earlier incomplete runs remain non-acceptance.
- M1-7 Plan review and execution overhead reductions kept bounded windows,
  stable selection and fresh commitment. After separate readiness/authority
  repairs and a failed fixed run, the final clean-source run passed all 35
  fixed criteria across 175 children and 775 samples. Six changed-sort p95s
  were 0.756–1.109 s, review memory 267.762 MiB, and execution admission
  p95/max 54.6/55.4 ms. Earlier failures and criterion limits remain in
  PERFORMANCE; the final integrated GUI behavior is recorded below.

### M1 Consolidation

Product, test and documentation reductions removed repeated machinery while
preserving operational safety, externally visible contracts and independent
behavioral evidence.

#### Simplify executor ownership and post-M1-8 machinery (2026-09-25 – 2026-09-30)

- The executor/verifier reductions above kept each effect and refusal boundary
  in its owning layer. Shared admitted path composition, target fidelity and
  source-version recognition replaced repeated checks; method-identity
  dispatch and stale oracle spelling variants were removed. The protected
  settlement oracle, differential comparison and native no-effect witnesses
  remained acceptance authorities rather than test-count preservation.
- AB-1–AB-10 reduced copied bridge/page state, recovery flags and duplicate
  CSS/visual assertions. Current-state view/highlight/theme commands refresh
  from revisions; effect and lifecycle commands retain original-result custody,
  bounded Check and duplicate protection. Valid late results are accepted
  independently of cleanup ACK. AB-8 moved task progress and rate reduction
  into one native-owned snapshot per admitted drain; page adoption retains Gap,
  replay, terminal custody and bounded item windows. Unreadable final results
  remain fixed-unknown and cannot invite mutation replay.
- Keep rendered forced-color, focus, native geometry, security and interaction
  detectors while removing duplicate CSS recipes. Desktop Plan receives a
  compact revision/aggregate summary instead of full operation previews;
  workflow selection and mutation admission remain authoritative. Remove the
  unused historical mapping lookup while preserving live scan-scoped move
  detection, hardlink guards and durable history. Ordinary, headed, import and
  independent review gates passed for these reductions; their detailed
  evidence and deferred AB-8 stack/wrap investigation remain in M1_PLAN,
  TESTS and PERFORMANCE.
- Close the delivered executor register and compact this history under the new
  Performance phase. Remove the clean, integrated `b8baf42d` baseline checkout
  after accounting for its revision and ignored outputs; carry unbuffered source
  reads into M2_PROPOSAL as a measurement-dependent proposal.

#### Consolidate product, tests and documentation (2026-09-01 – 2026-09-09)

- Remove internal workflow JSON transports and repeated event certification;
  share admitted stats, event/progress projections, finishing and bounded query
  policy while retaining external and persistence validation. Consolidate task
  effects, plan retirement, observer lifetime and idempotent cleanup. History
  schema/shared data epoch is 7 and ledger schema is 4; old or mixed pairs
  require coordinated reset. Native copy and settlement policy were unchanged
  in this earlier reduction.
- Consolidate behavioral tests by owner while retaining settlement, native
  mutation, source admission, snapshot, atomicity, visual/privacy and scale
  witnesses. Isolated fault/harmless-variation replay and the final 4,862-test
  ordinary, headed, import and three-run oracle gates checked detection, not
  merely test color; TEST_REFINEMENT and TEST_ABLATION retain qualified evidence.
- Make M1_PLAN the sole active delivery register and move superseded studies
  to `docs/obsolete/`. Component docs own behavior, PERFORMANCE owns methods,
  and DEFENSE owns evidence authority. Retain fresh Plan-again review and
  pending inventory, capacity/trash and integrity surfaces; terminal domain
  retries and user-invoked session cleanup remain proposed for M2.

#### Align historical criteria and layered verification (2026-08-10 – 2026-08-27)

- Separate retrospective M0 criteria from active contracts, archive imported
  PoC and superseded checklists, and keep current M1 gates in their owners.
  Establish focused, department, ordinary and headed test routes through one
  fail-closed primary-ownership manifest without relaxing protected custody,
  settlement, 33k-row database or CLI lifecycle evidence.
- Centralize fresh root-authority evidence in core while consumers retain
  distinct admission policies. Split executor and verifier behind stable
  facades only after freezing the three-run 30-scenario settlement oracle;
  typed effects and a pure reducer replace monolithic settlement code.

### M1 Hardening

Safety, settlement and authority work made high-consequence release claims
explicit, reviewable and regression-backed.

#### Correct inventory lifecycle feedback (2026-10-02)

- Label each displayed scan with its producing scope, qualify scoped completion
  and counts, and identify notices as belonging to that scan. Retained prior
  publications preserve their scope across newer scans and refusals.
  Scope-label verification passes 406 focused and 2,797 workflow/interface
  checks, twelve import contracts, and all 35 headed cases across the main run
  and focused reruns; the initial execution capture-readiness timeout is retained.
- Record independent command-result retirement as an M2 design item so routine
  inventory actions need not eventually force task closure. Keep M1's shared
  capacity and original-result recovery behavior unchanged.
- Preserve observed session state when a delayed start receipt arrives after
  that same session has finished, while still invalidating older task-list reads.
- After a refused Refresh leaves only a prior publication, direct users to
  check the location/reconnect its drive and Refresh instead of retrying an
  unavailable view. Clear the transient Refresh message on confirmed admission;
  the existing current-scan indicator owns subsequent progress and completion.
- Reproduce all three failures and pass 58 focused frontend checks, all 1,890
  ordinary interfaces checks and all 35 headed cases across the full run and a
  manually focused inventory rerun. Independent review approves the correction.

#### Resolve reviewed open bugs (2026-10-01)

- After failed handle identity queries, probe that handle's filesystem and permit
  absent identity only outside NTFS/ReFS. Scanner and native adapters share the
  same predicate; successful queries add no lookup. Database ownership leases
  keep their strict identity refusal. Native exFAT COPY/UPDATE/readback and
  immediate NOOP replanning pass; reviewed-volume verifier policy is unchanged.
  Independent review, 5,733 ordinary tests, 12 import contracts and the
  30-scenario × three-run settlement gate pass.
- Make replacement-option advice optional. Performance reports now refuse
  overwrite with guidance to choose a new `--json` path; existing replacement
  commands retain their flag advice. Focused CLI tests preserve refusal before
  launch and existing report bytes.
- Close the open-ended exception-retirement remainder as a bounded disposition,
  without product changes. Host/document follow-up now requires measured
  product-owned retention past named lifecycle endpoints; the diagnostic that
  deliberately held a returned exception does not establish that trigger.

#### Ratify proportional defense and root safety (2026-09-28 – 2026-09-29)

- DEFENSE distinguishes plausible accident from adversarial content and
  out-of-baseline crafted structure, requires one planner-used fidelity check
  per effect, and retains only catastrophe backstops with demonstrable triggers.
  Accurate refusal reasons may vary without changing publication or durable
  truth. Held-root admission requires current attributes and exact binding;
  descendant checks and per-access fallback remain. The fail-open descendant
  observation correction and the concrete native-only delegation witness pass
  without allowing subclass resolution to bypass admission.
- Historical RO continuity proposals were narrowed to invocation binding and
  then superseded by the held-root contract. Directory-flush batching remains
  proposed for M2; direct target writes were authorized separately and are
  recorded under Performance.

#### Separate cold and live database admission (2026-09-27)

- Runtime database adoption now validates through a pinned SQLite connection
  and current SQL snapshot, so its own WAL/SHM activity does not look like
  incompatible cold drift. Standalone cold checks keep byte-preserving
  pair/schema/journal refusals; observed database-file drift receives one
  bounded retry, while only confirmed incompatibility receives reset advice.
  Reader lifetime, noncreating planning, recorder placement and retryable
  shutdown remain guarded. Native, installed Setup, ordinary and import checks
  passed with independent review.

#### Classify installed incidents and preserve truthful diagnostics (2026-09-25 – 2026-09-27)

- Repair the optional bridge diagnostic's event-v5 fixture and failure
  cleanup; retain original failure and incomplete-stream evidence. The
  installed run completed after repair, without promoting old timing samples
  to acceptance. The AB-7 focus-ring failure was classified as external test
  interruption; no actor or product fix is inferred. The separate AB-8
  stack/wrap race remains an uncaptured, deferred investigation in TESTS.
- Retire the unrealized DWM sentinel obligation without treating a green
  headed test as compositor-health evidence. Earlier focus, picker and bridge
  incident traces remain qualified by their recorded limits; the original
  wrong-directory picker observation has no confirmed cause.

#### Preserve command outcomes and desktop recovery (2026-09-25 – 2026-09-26)

- Remove timed page-side mutation abandonment/replay. Recover the original
  native-owned outcome through bounded observation while keeping identity,
  duplicate protection, dependent Start/Close fences and explicit unavailable
  feedback. Genuine document replacement retires page authority but preserves
  admitted work and gives close/reopen and fresh-review guidance. Lifecycle
  and resource deadlines, process-loss limits and retryable shutdown remain.
  Ordinary, installed and import gates plus independent review passed; two
  earlier intermittent installed observations remain unexplained.

#### Preserve move detection across repeated renames (2026-09-25)

- Planning correspondence no longer treats retained inventory paths or link
  counts as current aliases. Fresh scans still reject hardlinks and duplicate
  identities; ambiguous correspondence is ineligible. Native rename/no-op
  convergence, repository history, ordinary and import checks passed without
  schema reset or history deletion.

#### Bound task inputs, custody and cross-layer truth (2026-08-26 – 2026-08-30)

- Admit complete raw populations before normalization, bound 120,000-item
  support targets and reject excess without partial artifacts. Task reservation,
  document/response custody, longest-prefix drains and exception-graph
  retirement preserve exact ownership across reload, cancellation and
  reentrancy. Execution retains reliable outcomes before callbacks, immutable
  selection identities, ordered pause/resume and recording settlement.
- Align event v5, signed-64 scalars, full-width file identity, canonical JSON
  and database WAL-visible topology so malformed inputs fail before custody or
  mutation. Ledger/history data epoch 6 at that cut required paired reset;
  the later consolidation advanced the shared epoch to 7. Native and workflow
  controls covered mounted roots, verifier chunks and shutdown release.

<a id="close-the-m1-safety-and-post-refactor-audit-2026-08-08--2026-08-11"></a>
<a id="ratify-measurement-and-documentation-authority-2026-08-14--2026-08-18"></a>

#### Establish the safety and evidence model (2026-07-30 – 2026-08-18)

- DEFENSE became the normative source for supported assumptions, hard walls,
  tolerances and residual-risk decisions. Measurement targets, drift guards,
  reference acceptance and protected release authority were separated; bug
  severity follows worst supported consequence. Architecture and subject docs
  replaced stale implementation checklists without changing those contracts.
- M1 safety audits re-probed roots and volumes, guarded junction/remount,
  target/trash and hostile-name paths, and preserved publication, backup,
  non-byte mutation, retry, cancellation, recorder and hash-mismatch truth.
  SQLite snapshots, malformed persisted/bridge input and integrated lifecycle
  settlement gained native race, deep-path, temporal and recovery witnesses.

### M1 GUI

Stage 6 delivered the secured desktop host, process-live tasks, frozen Setup,
bounded Plan review/selection and execution, and live/retained result review.
Integrity controls, manual post-copy handoff and beta packaging remain open.

#### Deliver M1-9 inventory review (2026-10-01 – 2026-10-02)

- Complete the desktop inventory actions: same-task Refresh, exact item/folder
  scope, acknowledge missing and restore visibility, with original-command
  recovery and truthful partial-result feedback. Refresh adopts the shared
  admitted identity immediately; prior complete results remain readable.
  The installed witness proves real folder-command clicks, replacement results,
  missing-row hide/return, screenshot and task/host Close. Final ordinary checks
  pass 5,829 cases/four skips; all 35 headed cases pass across dependency-scoped
  runs, with initial incomplete/failed receipts retained. Stop after M1-9 for
  user recap and GUI tweaks; no next-checkpoint work is activated.
- Correct the existing live host witness's local native-completion wait budget
  after diagnostics showed matching canceled events arriving beyond ten seconds.
  Preserve the whole-scenario limit and every cancellation, identity, ordering
  and post-cancellation transport assertion; product behavior is unchanged.
  Both actual live-host gates and all 1,890 interfaces checks pass. Migrate the
  existing exact production/extended command catalogs for the seven delivered
  inventory commands without weakening the security assertions.
- Adopt admitted starts directly in the desktop rather than relying on a later
  task-list read. Share the lifecycle correction across Plan, inventory and
  Plan again, including serial pair-batch starts, and Refresh. Ignore pre-admission
  list responses, contain later read failures and replace the old event drain.
  Fresh Plan requests no longer imply execution merely because a review exists.
  Failed/stale-list and Plan-again probes reproduce the old failure and pass
  after correction, including the delivered Refresh call site.
  The corrected interfaces suite passes all 1,890 checks; independent review
  also verifies batch admission and the migrated Plan-again trace helper.
- Add the immutable workflow inventory projection with independent domain and
  warning populations, complete-folder membership, raw evidence provenance,
  checked rollups and explicit partial byte totals. Share canonical sibling
  ordering with Plan while preserving its existing sort and selection behavior.
  Real rows use their raw basename even when mixed-case descendants choose a
  different tree spelling; independent review supplied that regression witness.
  Corrected focused/workflow checks pass 160/894 cases; imports and independent
  correction review pass. Ordinary evidence and environment reruns are retained
  by dependency under `build/m1-9-20261001/`.
- Add a dedicated cold inventory projection collector and independent checker,
  including real Windows venv launch provenance and incomplete-evidence controls.
  Five fresh samples per fixture pass the retained reference-profile maxima:
  1.97 s base and 2.81 s information-heavy. Commit the raw samples and validation;
  keep the failed first launch receipt and detailed logs in the task evidence.
- Add task-bound inventory review reads: retain scan metadata through release,
  lazily publish a whole ledger projection, cache revisioned search/filter/
  collapse/sort windows, and query fresh exact-row evidence for Details.
  Warning rows remain outside domain scope; acknowledged folders may remain
  as ancestor context for visible descendants. Native/browser validation and
  stale task/view/Close guards are covered. Independent review and real composed
  scan-to-Details checks pass; the combined affected departments pass 3,109 tests
  with three skips.
- Add the desktop inventory read pane with server-owned search, facets,
  collapse, paging and sibling sort/reset. Details distinguish observed facts
  from current attestation; warnings stay informational and prior publications
  stay visibly distinct from newer scans. Independent review corrected stale
  viewport adoption and nested-row indentation. Focused browser checks and the
  installed tree/keyboard/reflow witness pass.
- Add same-task inventory Refresh through the service and production bridge.
  Full, exact-item and complete-folder scans admit the location afresh, preserve
  prior complete reads during failure/replacement and retain original success
  or failure until task Close. Repeated starts share the existing bounded
  response capacity; no automatic resubmission occurs. Fresh review and composed
  admission, replay, offline recovery and replacement checks pass; the final
  workflows/interfaces neighborhood passes 2,769 cases.
- Add task-bound missing-row acknowledge/restore through the production bridge.
  Complete server-owned folder scope includes hidden and off-window subjects;
  conditional writes preserve reappeared rows. Frozen command facts and bounded
  actual disposition counts survive response loss and failed view replacement,
  including explicit unresolved rows after a partial failure. A dirty prior view
  remains readable but cannot authorize another visibility change until rebuilt.
  Task Close waits for active writes and retires the task's receipts.
  Fresh review, 795 focused and 2,785 workflow/interface checks pass.

#### Mitigate the Advanced Color flyout halo (2026-09-24)

- The dark translucent flyout shadow halo was reproduced in DWM Advanced Color
  composition, including a raw Win32 probe; an 8-bit screenshot cannot prove
  it absent. Native appearance v3 follows the window display's state, and dark
  flyouts suppress CSS elevation shadows on Advanced Color displays. The
  underlying compositor behavior remains deferred. Focused, installed gallery,
  interface and import gates passed; evidence is retained under
  `build/wcg-review-20260924/`.

#### Complete M1-8 execution review and task recovery (2026-09-20 – 2026-09-24)

- Bind M1-8 integration to the accepted tree and exact package/artifact
  identity, preserving recovery evidence. The Plan window shares live and
  terminal status, bounded row facts and requested detail; automatic
  verification, recording and capacity failures remain separate. Recognized
  disk-full/quota stops later executor work after current settlement while
  retaining truthful prior results and recovery. Installed receipt latency
  stayed within its existing budgets.
- A suspended observation drain offers Retry updates on the same task. Pending
  Close fences new admission, requests cancellation and waits for terminal
  settlement; uncertain Close retains an exact Retry close action. Independent
  action/error feedback, stale-callback rejection and bounded terminal review
  remain. The final R0–R2 integration, ordinary, 33 installed headed and import
  gates passed; the fresh U series completed 78 attempts. Filter/Search and
  the later reduction study stayed deferred at this checkpoint.

#### Deliver bounded Plan review, selection and execution (2026-09-14 – 2026-09-20)

- Build a revision-bound hierarchy with literal search, counted filters,
  stable sorting, bounded row windows, server-owned selection and snapshot-
  bound destructive confirmation. Tri-state header/folder gestures act on the
  active filtered view, including off-window descendants; navigation does not
  silently change selection. Highlight ranges, keyboard/pointer distinction,
  stale-revision refusal and workflow dependency closure remain guarded.
- Distinguish a built Plan from execution readiness; no selection or preflight
  refusal may start work. Same-task Execute preserves rollback, live controls,
  exact session binding and terminal facts. Plan again re-resolves retained
  identities into a new task; closing and settlement races cannot replay
  effects. User-facing status, density, table sizing, semantic colors and
  bytes/metadata labels were refined without changing numeric sort facts.
  The final installed desktop and ordinary gates passed; M1-7's fixed scale
  criteria and earlier failed readiness attempts are recorded under Performance.

#### Deliver Setup, task navigation and selective icons (2026-09-09 – 2026-09-14)

- Process-live blank tasks have newest-first navigation, safe busy Close,
  retained terminal status and generation-safe reinjection. Bounded async
  create/start/release/close commands separate admission from delivery. Setup
  uses fresh shared location admission, typed/picker/recent inputs, frozen task
  options, serial best-effort pair creation, per-row queued setting snapshots
  and current-root re-admission. Remembered locations are run-derived hints,
  never lasting authority; Add pair and removal retain exact retry ownership.
- Settings/About preserves active tasks. Compact recent/batch tables, scoped
  feedback, accessible control states and the fixed offline Fluent icon
  catalog refine the headed shell. Native overlay scrollbars, verify-only
  batching and persistent custom pair presets remain deferred to M2. The
  transparent-host rendering issue and intermittent disabled-label blur retain
  their qualified diagnostics; neither is claimed fixed. Ordinary, installed
  and import gates passed with independent review.

#### Establish exact events and presentation semantics (2026-08-19 – 2026-08-25)

- Core event v5 has exact bounded reliable envelopes, ordered item reasons,
  signed-64 scalars and full-width Windows file identity. The coordinated
  persistence cut used ledger v4/history v6 at data epoch 5; later revisions
  advanced the shared epoch as recorded above. The v4 per-item progress model
  distinguishes attempted bytes from durable publication, survives retry and
  Gap, and feeds an O(1) browser reducer without inferring domain outcomes.
- Ratify a compact semantic palette across operation, task and integrity
  channels with labels and accessible state authoritative over hue. Persisted
  System/Light/Dark choice belongs to a bounded cosmetic document, not plan or
  workflow state; Windows retains forced-color, accent and motion authority.
  The shared file-row renderer began dormant and test-only before Plan wiring;
  its bounded hierarchy, controls and responsive layout gained headed
  light/dark/forced-color/reduced-motion evidence. Bridge contract authority
  was consolidated without weakening origin or custody limits.

<a id="complete-and-harden-the-accessible-desktop-foundation-2026-08-12--2026-08-18"></a>
<a id="close-transport-custody-and-realign-the-bridge-boundary-2026-08-13--2026-08-14"></a>

#### Secure the headed desktop foundation (2026-07-31 – 2026-08-18)

- Pin WebView2, exact packaged origins, navigation/frame/popup guards and a
  strict bounded bridge; no MSHTML fallback. The installed host owns document
  readiness, command admission, observation custody and shutdown. A workflow-
  owned visible tree and bounded virtualized row windows retain keyboard,
  zoom, forced-color, hostile-text, geometry and stale-generation evidence.
- The editable-source GUI launcher isolates development data and processes
  from clean-wheel evidence. Transport drains coalesce progress for at most
  150 ms while receipts, reliable and terminal feedback bypass that wait.
  Historical compositor-health limits remain explicit; inventory and later
  release closure were not delivered by this foundation.

### M1 Features

Stages 1–5.5 delivered the headless reviewed-sync, inventory/integrity, history,
CLI, and reusable workflow product plus its development measurement tooling.

#### Harden development measurement tooling (2026-08-06 – 2026-08-18)

- Added a reusable empty-target executor profile that resets the target before
  each sample, scans/plans once per batch, preflights the first fresh execution
  set, and then measures full copy-plus-finishing work with fresh mutable state
  per sample; mutable template/update workloads remain prepare-each.
- Kept diagnostics on by default, made executor pipeline and verifier reader
  splits useful on the console, bound repeated samples to one fixture, retained
  unrounded raw samples, and separated setup, samples, validation, and summaries
  in one atomic versioned report.
- Replaced marker-wide descendant deletion with strict root-bound output
  manifests, exact printed-plan application, whole-tree and per-entry
  revalidation, generic reparse/alias refusal, truthful partial-state receipts,
  and explicit inspected `--force-all` recovery.
- Made benchmark reports and baseline sidecars create-exclusive and
  destination-identity-bound, required explicit sidecar paths and replacement
  authority, removed implicit append/cleanup behavior, and added adversarial
  corpus, verifier, sidecar, artifact-race, cleanup, and CLI regressions.

#### Add bounded durable history readback (2026-08-05 – 2026-08-06)

- Added windowed durable reliable-event history, bounded keyset detail pages,
  and incomplete-prefix recovery.
- Hardened replay and close behavior without allowing audit/history failure to
  rewrite sync truth.

#### Add scoped review trees and revisioned selection (2026-07-30)

- Added deterministic review trees, full/path/subtree inventory scopes, and
  folder-level operations.
- Added deselection provenance, dependency closure, authoritative selection
  re-derivation, risk previews, and retry-safe facade admission.

#### Complete headless integrity workflows, service, and CLI (2026-07-25)

- Added the bounded XXH3 copy pipeline, role-free inventory,
  baseline/verify/rebaseline, and optional post-copy verification.
- Completed the reusable service facade and typed CLI commands/results for
  sync, history, and integrity work.

#### Establish M1 contracts and persistence boundaries (2026-07-24 – 2026-07-27)

- Made reviewed plans immutable at execution, separated semantic settings from
  cosmetic UI state, and added the XXH3 hashing seam.
- Established reset-only ledger v2/history v3 contracts and strict bridge/
  UI-state inputs.
- Removed persisted mapping-filter projections: filters stay immutable per-plan
  scan input while the ledger retains role-free inventory and mapping
  correspondence.

## M0

M0 established the reusable headless reviewed-sync baseline and its explicit-
plan safety model.

### M0 Hardening

Filesystem and reporting edge cases were hardened without weakening explicit
review or guarded execution.

#### Make filename-form differences safe and reviewable (2026-07-20 – 2026-07-21)

- Made invalid raw names incomplete-scan evidence without aborting safe sibling
  work; case-only and unique NFC/NFD differences remain visible to reviewers.
- Kept filename-form advisories from suppressing ordinary update/no-op work and
  made review output show the prior target path for move, move-update, and
  recase operations.

#### Recover interrupted work and harden Windows finalization (2026-07-20)

- Made directory cleanup tolerate only same-run child-induced metadata churn
  while preserving replacement and nonempty-directory refusal.
- Corrected directory flush access, restored identity-less FAT-style cleanup
  where identity was never reviewed, and reclaimed only exact prior-run
  temporary files after preflight.

### M0 Features

The first milestone shipped reviewed one-way sync through reusable core,
runtime, persistence, workflow, and CLI layers.

#### Add safe-subset execution (2026-07-20)

- Quarantined blocked and dependent operations while allowing independent safe
  work; incomplete scans use an additive-only subset that withholds moves and
  deletions.
- Added itemized blocked/deferred results, history, and CLI partial-completion
  reporting.

#### Deliver reviewed-sync workflows and CLI (2026-07-19)

- Composed scan, deterministic plan, commitment validation, fresh preflight,
  execution, ledger recording, dispatcher custody, and independent history
  into the reusable workflow layer.
- Added the reviewed two-session `nami-sync sync` flow, read-only `history`
  browsing, real process entry points, and safe retry/admission fixes.

#### Establish the M0 backend foundation (2026-07-18)

- Added core session/event/evidence contracts; scanner, planner, preflight,
  guarded Windows executor, and standalone integrity-verifier primitives.
- Added bounded dispatcher custody/event fan-out plus WAL-backed ledger, typed
  repositories, and independent history persistence.
