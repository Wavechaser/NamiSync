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

### M1 Hardening

Safety, settlement, authority, and measurement work made high-risk release
claims explicit, independently reviewable, and regression-backed.

#### Ratify measurement and documentation authority (2026-08-14 – 2026-08-18)

- Separated reasoned targets, live drift guards, named-reference acceptance,
  and protected release authority; moved their governing policy from universal
  agent instructions into the defense model, with concise routing left behind.
- Put consequence and production enforceability ahead of tier selection,
  separated deterministic protected values from noisy empirical quantities,
  and froze SH-G-8 v1 as a non-precedential exception rather than a BR-G-45
  template.
- Consolidated shell acceptance evidence in its owning gate, reduced the README
  to product and status summaries, and made category-prefixed commits plus
  task-level changelog grouping repository conventions.
- Audited the bug ledger against cause-based categories and consequence-based
  severity, then made that classification rule explicit for future entries.
- Recast the architecture reference around durable contracts, layering,
  coordination, and milestone direction; indexed each standardized contract
  family to its authoritative core source while removing build/evidence
  duplication and stale feature status.

#### Establish the threat and tolerance model (2026-08-15)

- Added one normative defense model for supported assumptions, trusted
  boundaries, hard walls, user authorization, tolerance classes, and explicit
  residual-risk dispositions.
- Reconciled the external-writer, TOCTOU, and WebView contracts around a
  quiescent-root preservation baseline, a trusted packaged renderer with
  untrusted data, and consequence-based stopping and mitigation rules.
- Indexed the new authority across the current compact architecture, feature,
  defect, executor, preflight, interface, bridge, and project documentation
  without duplicating its policy tables, and archived the stale pre-M0 design
  review under `docs/obsolete/`.

#### Close the M1 safety and post-refactor audit (2026-08-08 – 2026-08-11)

- Bound scanning, preflight, execution, and verification to freshly re-probed
  roots and volumes; guarded mounted roots, junction/remount redirection,
  target/trash parents, long/device/reserved paths, and hostile names.
- Made publication, backup, non-byte mutation, cancellation, retry, recorder-
  failure, and hash-mismatch settlement expose durable filesystem, integrity,
  and ledger truth; expanded the retained oracle after the component split.
- Hardened SQLite contention and recorder rollback, history receipts and
  selection, and malformed workflow/persisted inputs, with native race,
  remount, deep-path, and substitution regressions.

#### Harden integrated lifecycle and durable truth (2026-07-30 – 2026-08-05)

- Shared ordered publication settlement across COPY, UPDATE, and MOVE_UPDATE;
  retries preserve owned state and disclose only validated backup, publication,
  and drift truth.
- Bounded audit, close, cleanup, and repair work; closed service custody,
  replan, command, cancellation, and shutdown races.
- Hardened database snapshots and incomplete-scan authority, rejected coercive
  persisted and bridge JSON, and added temporal/concurrency/recovery stress
  coverage.

### M1 Maintenance Refactor

Shared root authority, stable executor/verifier package boundaries, an oracle-
guarded typed settlement reducer, and layered test operations made internal
ownership explicit without changing public or persisted contracts.

#### Establish layered test operations (2026-08-16)

- Added focused, department, cross-department, ordinary, and complete/headed
  run policy with short and long department selectors backed by one exhaustive,
  fail-closed primary-ownership manifest.
- Reduced evidence-neutral fixture cost through pip-less ordinary wheel
  installation, success-only junction capability reuse, exact-boundary native
  verifier data, test-sized log rollover, and lazy headed scenario evidence.
- Consolidated duplicate coverage and shared helpers without merging behavioral
  cases; selection-independence guards reject test-tree back edges into
  collected modules, while lazy-failure guards preserve original headed
  failures.
- Left protected custody and settlement evidence, the live 33k-row database
  scale guard, CLI lifecycle coverage, and serial execution policy unchanged.

#### Complete the maintenance refactor (2026-08-10 – 2026-08-11)

- Centralized fresh root-authority evidence in core while preserving the
  distinct admission policies and probe timing of scanner, preflight,
  workflows, executor, and verifier.
- Corrected and froze executor settlement behavior in a retained three-run,
  30-scenario oracle before splitting executor and verifier behind stable
  facades; a typed effect journal, pure reducer, and ownership-aligned tests
  replaced the monolithic implementation.

### M1 GUI

Stage 6 delivered the secured desktop host, command/event transport, design
foundation, bounded presentation core, and dormant sync/integrity file-list row renderers;
later workflow surfaces and beta packaging remain future phases.

#### Establish the dormant file-list row renderer (2026-08-20 – 2026-08-21)

- Added a shared packaged `file_row.js` skeleton plus presentation-only
  `renderPlanRow(element, rowView)` and `renderIntegrityRow(element, rowView)`
  specializations. They consume explicit display values through the defended
  text helpers, import no bridge or domain code, and remain unimported by
  production startup, so the shipped GUI remains honestly empty.
- Expanded the responsive grid to six columns. Both lists order selection,
  basename, and size first; sync adds operation/status and eight-character
  checksum, while integrity adds combined presence/status and eight-character
  checksum cells before notes.
  Rows are 24 px with 12 px text, checkboxes are 16 px, and projected folders expose disclosure
  buttons, mixed selection, and indented basename-only children. The test-only
  driver collapses/restores actual computed rows and reconciles each folder's
  checkbox from its two direct children. Focusable header separators resize
  each grid track by pointer drag or arrow key without persistence. Zebra
  backgrounds belong only to rendered row elements—including folders—and stop
  at the last row; cells stay transparent and constrained widths scroll the
  complete aligned grid horizontally from a 48 rem content floor. The gallery specimen fills the wide work
  area. Plan operation and integrity-state aliases use authored family main
  colors in both ordinary themes—including red-main negative states—while
  forced colors retain system authority.
- Drove the installed production renderer from a test-only static gallery
  arrays covering a plain row, all nine operation tones exactly once, a folder
  with two children, error/unsupported statuses, and representative integrity
  states under another two-child folder. No bridge command,
  `SyncPlan`, workflow, dispatcher, session, or provisional wire payload was
  introduced, and exact wheel checks exclude both fixture markers.
- Extended four-profile headed evidence for roles and blank selection header,
  checkbox labels/states and exact compact geometry, six columns, computed
  collapse/restore, child-to-parent selection reconciliation, a measured 40 px
  column drag, basename hierarchy, main status mappings, display-ready checksums,
  finite row-only striping, transparent cells, wide work-area fill, and
  narrow-container overflow.
- Added a test-owned header master checkbox to both file-list specimens. It
  derives checked/mixed state from every selectable row and exercises select
  all/deselect all without defining Slice 5 selection authority.

#### Tune solid desktop control states (2026-08-20 – 2026-08-21)

- Kept primary buttons, filter pills, operation/file badges, and progress
  tracks borderless, while ordinary buttons now use the WinUI-neutral
  `#fbfbfb`/`#2d2d2d` fills and subtle `#e5e5e5`/`#353535` boundaries.
  Keyboard focus and forced-color authority remain separate.
- Made inactive filters inverse grayscale and active filters consume the exact
  main swatch for their operation family with contrast-selected neutral text.
  Delete uses exact red-main text at rest; its active pairing uses
  red-main/red-dark, while a stronger inverse hover surface fixes
  the 4.09:1 light-theme regression exposed by the headed matrix. Active-chip
  interaction stays fully opaque and uses geometry instead of contrast-eroding
  opacity.
- Kept exactly two button tiers—solid gray and live Windows-accent primary—and
  made the Sync/Integrity specimen an exact-one-selected radiogroup with the
  checked half highlighted by accent rest/hover/pressed tokens.
- Expanded installed-wheel gallery evidence for default/primary hierarchy,
  active/inactive Copy and Delete filters, borderless file/status chips,
  gray-track live-accent progress, and selected segmented state across light, dark,
  forced-color, and reduced-motion profiles.
- Made content cards static translucent material layers with the requested
  Light/Dark fill and stroke blends, and separated borderless task cards into
  transparent-rest, primary-tint hover/selection, and weaker active-hover states.
- Kept inactive Delete text and light Error/Unsupported list states on exact
  red-main, moved progress fill to the live Windows accent, and kept active
  Delete's existing red-main/red-dark pairing.
- Kept the raw Windows Accent/Light1/Light2/Dark1 ramp native-side and replaced
  the old page roles with appearance v2 semantic fills: AccentDark1 in Light,
  AccentLight2 in Dark, then 90% hover and 80% pressed opacity. Primary-button,
  segmented, checkbox, and toggle states share that ladder and one stable
  contrast-selected black/white foreground; progress and selection markers use
  the base fill.
- Replaced the packaged native theme selector with a production-owned DOM
  combobox: a subtle gradient trigger boundary becomes flat while open, the
  elevation-16 opaque listbox aligns its selected option and clamps to
  the viewport, and forced colors retain system authority. The gallery now
  includes three left-rail task-card state specimens outside content cards.
- Split elevated-surface strokes from accessible control borders at black 6%
  Light/20% Dark, clipped content-card fill to the padding box, and added a
  dark-HDR shadowless flyout fallback plus normal/shadowless/opaque gallery
  isolates for the transparent WebView2/Mica halo diagnosis.
- Made the M1 combobox popup opaque and aligned options with task cards:
  transparent rest, one visible hover/selected overlay, a weaker pressed
  overlay, and one accent-pill/marker for selection. The gallery rail carries
  only one highlighted task even when it exposes both current and selected
  semantics.
- Reopened the native base-accent black/white contrast result for all
  accent-filled labels without allowing hover/press reversal; added opposing
  inner/outer Fluent focus strokes, stabilized plain-chip labels, corrected
  toggle-knob travel, and reduced only file-table rows from 28 px to 24 px.
- Added a neutral Fluent strong-stroke 2 px unchecked-checkbox boundary, a
  subtle 2 px textbox boundary with neutral-to-accent underline, and explicit
  1280 x 800 initial / 1024 x 640 minimum
  logical host geometry through pywebview's public construction arguments.
  Removed the former 48 rem viewport media query while preserving the proven
  zoom-responsive stacked layout with an inline-size container query.

#### Thaw and refreeze the cosmetic state channel (2026-08-19)

- Ratified `ui-state.json` as a strict, interface-owned cosmetic document,
  implemented its bounded typed lifecycle, and kept it outside semantic
  settings, plan hashing, service state, and sync-plan construction.
- Added the fixed `read_cosmetic_section` and `replace_cosmetic_section` bridge
  rows with guarded revisions, bounded retry/reconciliation policy, host
  quiescence ownership, and no new authority for session or workflow state.
- Made the persisted System/Light/Dark choice drive both native material and
  page tokens while preserving Windows ownership of high contrast, accent, and
  reduced motion; selector initialization remains independent of readiness.
- Repaired the component gallery to seed the real cosmetic owner before window
  creation and added installed-WebView2 evidence for accepted-only selector
  reconciliation, native/page agreement, and keyboard order, plus focused
  coverage for reusable development relaunches.
- Independently reviewed persistence races, shutdown custody, browser
  reincarnation, attachment rollback, forward-version preservation, and
  evidence honesty. Kept the file-list/treegrid consumer and its durable keys
  for the owning later slice without reopening the refrozen bridge protocol.

#### Concentrate bridge contract authority (2026-08-19)

- Reduced `M1_BRIDGE.md` to standing scope, one owner-oriented decision map,
  ruling-first live contracts, concise dispositions, and the authoritative
  BR-G gate register; moved dated status to this changelog and removed obsolete
  deliberation without weakening ids, limits, or gate criteria.
- Kept the fixed scale and transport-custody contract with BR-G-42, retained
  current delivery ordering while compressing lane narrative, and redirected
  shell references from the retired §9.4 location.

#### Add an editable GUI development launcher (2026-08-18)

- Added `tools/gui.ps1` for a foreground editable-source development shell and
  light, dark, forced-colors, and reduced-motion component galleries, with dark
  as the gallery default and Enter-to-relaunch interaction. Added `fluent` for
  concurrent light/dark launch and `all` for all four galleries.
- Isolated development data, mutexes, titles, logs, and per-launch gallery
  diagnostics from production; waited only for exact spawned child process
  objects and refused secondary-launch ambiguity without process-name
  termination. Grouped profiles reuse the concrete per-mode locks, start all
  selected children before waiting, and do not introduce a global gallery mutex.
- Reused the unchanged clean-wheel child compositions and test-owned gallery
  scenario while classifying editable output as non-evidence, retaining
  abnormal diagnostics/log tails, and cleaning only ownership-marked,
  revalidated normal-run milestones without recursive deletion.
- Condensed normal closure to one single/grouped profile receipt and moved the
  exact successful cleanup plan and removal transcript to `-Verbose`; abnormal
  lifecycle, retained-output, log-tail, and partial-cleanup receipts remain
  explicit on the normal console streams.

#### Complete and harden the accessible desktop foundation (2026-08-12 – 2026-08-18)

- Secured the installed-wheel host lifecycle with bounded admission, drains,
  recovery, and shutdown; pinned app/database identity, activation, native
  picker/path confinement, receipt-safe plan replay, and sanitized logging.
- Removed the service/workflow `ResultCategory` collision, made enum codec
  coverage follow public-view annotations and witnesses, and pinned the shared
  64-handler sizing rationale against the 48-task capacity.
- Gave current-document readiness one named state-machine owner, moved the
  command-phase join into host composition, and reduced the bridge to consuming
  an opaque admission verdict. Ordinary commands now wait on a neutral
  current-generation host challenge/page echo, while appearance publication
  remains independently degradable after safe-surface settlement.
- Made Python/JavaScript availability, timeout, and retry agreement mechanical;
  consolidated positive headed startup and command composition behind shared
  drivers; and replaced live result-snapshot replacement with bounded,
  canonical, immutable `ready`/`failure`/`final` evidence milestones.
- Added the authored Fluent palette and local icons, live Windows theme/accent,
  Mica and dark-mode handling, truthful opaque fallback, and motion/contrast
  guardrails.
- Built a workflow-owned visible tree, exact bounded row windows, and an
  accessible virtualized shell, with headed keyboard, zoom, forced-color,
  hostile-text, scale, geometry, and stale-generation coverage.
- Hardened the foundation for the admitted renderer floor, presentation-ready
  document generations, fail-closed loaded refusal, projected expansion,
  pointer operation, visible active descendants, and last-state-wins passive
  scroll paging, including layout-only resize reconciliation and bounded tree-
  controller disposal.
- Neutralized the fixed filesystem layout-control set only at the final text
  sink while preserving raw workflow/wire/search values, and bound Python,
  direct Node, and installed WebView2 tree evidence to one canonical manifest
  and SHA-256.
- Added exact `Highlight`/`HighlightText` pairing for enabled selected/current
  cards to the native/high-contrast forced-color composition evidence while
  retaining the selected-card boundary and disabled-state distinctions.
- Kept Slice 5–7 product surfaces, GUI Break 2, current-source BR-G-42 event
  timing and product-view rows, BR-G-45 terminal retention, Slice 8 release
  closure, and SH-G-15 whole-runtime containment open.
- Recorded that a green headed checkpoint is not compositor-health evidence:
  one checkpoint coincided with a DWM restart but had no session event sentinel
  capable of detecting it. The event correlation does not establish NamiSync
  causality; shared headed-session compositor monitoring remains open.

#### Close transport custody and realign the bridge boundary (2026-08-13 – 2026-08-14)

- Realigned bridge ownership around one function-only dispatch entry, the exact
  packaged origin, task/session separation, command-specific plan identity,
  and explicit-`Gap`-only recovery.
- Closed event correctness and transport custody on the production queue path
  with bounded no-`Gap`, ordering, cleanup, and terminal evidence plus frozen
  calibration/holdout and a live drift guard; terminal-result retention and
  whole-runtime containment remain separate gates.
- Coalesced progress-only drains behind a fixed 150 ms maximum wait while
  receipts, reliable state, terminal, recovery, and lifecycle feedback bypass
  it; installed WebView2 witnesses are authoritative and Node is supplemental.

#### Establish the secured WebView2 bridge foundation (2026-07-31 – 2026-08-03)

- Pinned and validated the Edge WebView2 host path, refusing an MSHTML fallback
  before window creation.
- Enforced exact packaged origins, native navigation/frame/popup guards, and a
  strict bridge boundary resilient to reinjection.

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
