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

### M1 GUI

Stage 6 delivered the secured desktop host, command/event transport, design
foundation with a fixed local Fluent icon vocabulary, bounded presentation core, process-live task navigation and closure,
bounded asynchronous task commands, frozen Setup using shared location admission
and remembered locations, bounded Plan review/selection/sorting and same-task
execution with live controls. Execution-result/inventory review and beta
packaging remain open.

#### Refine Plan density, readiness and row highlighting (2026-09-17 – 2026-09-20)

- Match actionable feedback to secondary status typography, tighten aligned
  path labels, use caption-sized Plan paths/settings, and shift semantic icons
  into optical alignment with the reset action.
- Add tertiary metadata/path text, dedicated filter counters with right-aligned
  menu counts, aligned path-label slots, square reset action and lighter progress
  tracks. Align Setup's Sync/Integrity labels and task-detail endpoints; show
  exact integer bytes below 1 KiB and two decimal places for larger byte labels.

- Use friendly sentence-case Plan/filter labels and an explicit low-risk Notes
  hiding policy; preserve unknown notes, warnings and previous-location context.
  Add fixed semantic-setting icon slots using pinned Fluent artwork, and show
  indeterminate progress during planning with an immediate dispatch repaint.
- Sum static folder sizes from distinct destination-oriented plan file facts,
  independent of selection and view state. Report partial facts and null with
  an overflow note above signed-64; keep file/folder size-sort groups stable.
- Move execution/reset actions and concise feedback into the status card; let
  the table reach its card bottom. Match WinUI's translucent progress track,
  subdue metadata columns and omit dependency counts and neutral risk labels.
- Align checkbox glyphs and disabled strokes, Light button elevation, Plan
  spacing, status progress and switcher corners with the shared control design;
  refresh the gallery using production Plan controls and task cards.
- Restore server-owned arrow navigation across row windows and keep modified
  pointer clicks distinct from keyboard focus-ring activation.
- Format shared byte labels with four significant digits and retained zeros,
  preserving exact small-byte labels and backend numeric sort facts.
- Polish Plan column order, full-cell sorting, inset search/Clear controls,
  aligned semantic settings and compact planning-issue status. Keep actionable
  feedback without idle/success noise (subsequently moved into the status card).
- Tighten task-tab text and progress spacing, adjust selection markers, and
  report selected operations rather than all scanned items in the short digest.
- Fix selection refresh for operation-bearing directories with descendants;
  validate own-operation eligibility rather than the subtree rollup. Cover
  short/long nested paths and real row, bulk and highlighted checkbox gestures.
- Tighten category filter buttons against Fluent button fills, align search on
  the same row, preserve Plan/Status cards and loaded rows during refresh, and
  show ISO Modified labels.
- Distinguish **Plan ready** from **Ready to execute**; empty selections and
  preflight refusals cannot advertise or start execution.
- Add compact revision-guarded row-highlight gestures with complete-view range
  resolution, keyboard navigation, window flags, and atomic highlighted-range
  checkbox application through existing selection safety rules.
- Restore ordinary button sizes and group filters into counted split toggles;
  retain detail filtering and add guarded immediate search submission.
- Fit the compact Plan/Status cards and remaining-height table inside the work
  panel, align footer actions right, and align Action's drag/default minima.
- Supersede the earlier readiness labels with neutral **Plan ready** for every
  built, unexecuted plan; keep execution admission independent. Distinguish
  truly empty plans and share state, short detail, paths and progress with task tabs.

#### Keep Plan search editable and count filter toggles (2026-09-17)

- Keep search focused and editable through a pending view refresh; apply only
  the newest queued query after the current request settles.
- Replace Plan filter pills with themed toggle buttons. All resets category
  filters; complete-plan counts label each button, and less-common categories
  appear only when present. Inactive Trash text turns red above one item.

#### Scope Plan bulk selection to the active view (2026-09-17)

- Add a tri-state Plan header checkbox and make folder gestures target every
  selectable operation matching current search/filter, including off-window
  and collapsed descendants. Navigation alone leaves the complete selection
  unchanged, and Execute retains hidden selections.
- Resolve compact gestures in Python under both view and selection revisions,
  preserving workflow dependency/safety closure and command receipt identity.
  Add focused stale/hidden/filter/window tests and a 120,000-operation cost
  witness; update the former filter-independent folder-selection contract.
- Omit the synthetic Plan root row while preserving its internal rollups;
  translate public row/window/anchor coordinates to the rootless table and
  keep the header checkbox as the only whole-view control.

#### Refine Plan review table and controls (2026-09-17)

- Rehouse frozen Plan settings, status, search/filter, seven-column table and
  execution controls in clear cards. Bring gallery-style pointer/keyboard
  column resizing and header/body scrollbar alignment to production.
- Add a Modified column to the gallery and production Plan table, put
  dependencies in Notes, use filter pills and catalog chevrons for the
  three-state header sort cycle, and display exact byte counts in binary units.

#### Consolidate the delivered Plan shell (2026-09-17)

- Reassess the goal after R7-4: suspend remaining implementation and investigate
  larger test/evidence capability retirement. Record the actual net test growth,
  producer/validator/driver ownership, diagnostic tradeoffs and a proposed
  single current acceptance path. Compare preserving all 35 SLOs with explicitly
  reducing numeric claims; no production, test or evidence authority changes.

- Record the clean baseline and first checkpoint's provider/consumer working set
  for the authorized R7-1–R7-8 consolidation and R7-G closeout.
- Use affected local measurement drift checks per checkpoint and one full
  current-source measurement suite at closeout; retain fixed criteria,
  independent validators and historical evidence. No new acceptance claimed.
- Separate synthetic scale-test expectations from live generator observations;
  retain live population/order/retained-buffer checks and independent corruption
  detection. Focused scale tests pass 55 and interfaces pass 1,673, each with
  one historical-artifact skip; copied-source faults are detected and all 41
  synthetic cohort cases pass with live generation disabled.
- Replace the unused general canonical comparator with a direct path/node key,
  preserving the separate real-sort algorithm. Ordering checks pass 169;
  workflow/interface checks pass 2,480 with one historical-artifact skip, and
  all 12 import contracts pass. Five-child baseline/candidate memory guards pass
  the existing 320 MiB maximum; no memory improvement is claimed.
- Retire unused in-place projection replacement while preserving constructor,
  selection and view-publication checks. Focused checks pass 171, workflows and
  interfaces pass 2,482 with one historical-artifact skip, all 12 import contracts
  pass, and 30 installed headed checks pass. Copied faults detect lost sort,
  malformed acquisition and early publication; independent review approves.
- Consolidate validator-local receipt shape, process identity and sample rules
  while retaining boundary-specific refusal, uniqueness and completeness checks.
  Remove an extraction that only added a forwarding layer. Scale checks pass 55
  and interfaces pass 1,675, each with one historical-artifact skip; public-entry
  baseline comparison and isolated correctness/identity/maximum faults protect
  the independent evidence checks. Full measurement acceptance remains due.

#### Reduce Plan review and execution overhead (2026-09-15 – 2026-09-16)

- Avoid covered-window refetches and whole-card pending flashes. Fuse matching
  and ancestor retention, preserve Unicode casefold semantics, and fast-path
  empty queries. Keep projection nodes stable while sorting compact position
  buffers; derive bounded accessibility metadata without global object graphs.
- Reduce construction overlap and reuse exact revision-bound selection facts
  and prepared digests. Share validated execution structure through checkpoints
  while detaching mutable overlays and retaining public validation, fresh
  commitment time and receipts after actual admission. ARCHITECTURE records the
  shared index's extended paused lifetime.
- Complete the single P9 full run: all 35 fixed criteria pass across 175 fresh
  children and 775 samples after all 35 readiness cases. Six changed-sort p95s
  are 0.756–1.109 s; review memory is 267.762 MiB; execution admission p95/max is
  54.6/55.4 ms. Independent provenance and budget validation pass. Criteria and
  historical evidence remain unchanged; M1_PLAN and HANDOFF record final closure
  checks and the reconstructed integration series.
- Activate the real-artifact validation gate: 55 scale checks and 5,158 ordinary
  tests pass, with unchanged import and installed Plan evidence. Independently
  review the reconstructed outcomes and condense the active delivery register.
- Close M1-7 with clean committed-source evidence and integrate six coherent
  outcomes into `milestone1`. Preserve original recovery history under an
  archive tag and verified bundle before pruning task branches; stop for GUI review.

#### Correct measurement readiness and evidence retention (2026-09-15)

- Investigated the three failed measurement groups from retained evidence and
  source only. Identified repeated view rebuilding, projection construction
  overlap, duplicate execution admission work and accumulating fixture workers;
  recorded bounded proposals and attribution limits. Stopped for discussion
  without implementation changes or reruns.
- Completed the subsequently authorized single measurement run: 175 children,
  35 metrics and 775 samples, with complete independently checked provenance.
  Fixed acceptance failed on ten changed-window latency cases, projection staging
  memory, and typed execution-start receipt latency; the other 23 metrics meet
  criteria. Preserved the raw result and stopped without repair, rerun or merge.
- Registered the shared typed-execution receipt observer
  on the document-message channel. The missing registration caused deterministic
  timeouts after successful admission across nine execution/control cases.
  Gave only the 21-case component readiness group a 600-second process watchdog;
  other readiness and measurement children retain 300 seconds.
- Verified 46 owner tests (one pending-artifact skip), final listener/ablation and
  four watchdog controls, independent source/authority review, and full readiness:
  all 35 cases across 15 children. The repair stop preceded the separately
  authorized measurement run above; M1-7 remains unmerged.
- Implemented the reviewed framework boundary: semantic selection warmup, untimed
  readiness before sampling, and incremental receipts with explicit incomplete
  collection state. Preserve production behavior, timing criteria and terminal
  validation; no automatic resume or cross-revision reuse.
- Earlier failed readiness collections remain preserved; the repairs and successful
  readiness use separate authority. M1-7 quantitative acceptance remains unmet.

#### Correct measurement runtime initialization (2026-09-15)

- Moved the authority probe's `System.Action` import into the host's loaded
  callback. Exact-diff review and compilation pass; the single Freeze retry
  succeeds using the existing reviewed smoke. Frozen authority independently
  passes; the correction and authority are separate commit `30d35f3`.
- The fixed run stops at the selection-click pending-frame prerequisite, without
  producing a measurement artifact. No retry, repair or diagnostic expansion
  follows. Quantitative acceptance remains blocked for framework review;
  `cf5a00b` and `milestone1` remain unchanged.

#### Preserve bounded Plan review implementation (2026-09-14)

- Added bounded hierarchical review with literal search, filters, raw-key sibling
  sorting, server-owned selection and destructive confirmation. Same-task Execute
  preserves admission rollback and committed-but-unrun preflight truth.
- Corrected the user-approved closing race: retirement fences follow-up admission,
  settlement rechecks claim ownership after waits, and exact Plan-again replay
  survives source task closure. Live controls retain exact task/session binding.
- Replaced persistent acknowledgment with a snapshot-bound Fluent smoke modal;
  added workflow-owned aggregate/breakdown counts and an inert gallery preview.
  All four installed gallery appearance modes pass.
- Corrected execution terminal-record consumers, Plan-again readiness/visibility,
  current-session control-state ordering, and the advertised selection retry after
  a failed Plan load. The complete installed desktop gate passes 30 cases; final
  affected native reruns and 5,083 ordinary tests pass. Recovery retains the
  candidate at the user's stop boundary. The reviewed sequential fixture barrier
  passes its sole smoke at 27 ms against the unchanged 50 ms budget, but authority
  freeze fails before runtime initialization. No measurements or further repair
  loop followed. M1-7 is not yet delivered or integrated.

#### Condense completed M1 delivery records (2026-09-14)

- Replaced the long completed GUI/documentation register with grouped delivered
  outcomes and subject-owner links. Git history retains exact studies and evidence.
- Preserved pending product rows, the separate DOC-2 branch proposal, unresolved
  rendering investigations and active batch/admission guarantees.
- Corrected six root AGENTS documentation-owner links to their existing `docs/`
  targets after the user authorized repair of the preexisting broken references.
- Independent documentation review, local-link and whitespace checks passed.
  M1-7 study continues separately; no product delivery is claimed by this cleanup.

#### Clarify agent execution boundaries (2026-09-12–14)

- Condensed AGENTS.md through deduplication, tighter wording and conditional
  component/documentation routing; removed obsolete migration history while
  preserving execution boundaries and safety gates.
- Clarified routine consumer updates within accepted boundaries, completion and
  task-relevant documentation/testing. Preserved hard-wall and recurrence stops.
- Retired the completed monolith prerequisite while retaining the current
  executor settlement stability gate and protected oracle.
- Aligned the two personal execution/review skills outside this repository:
  retained GPT-5.6 cost preference and explicit-only execution invocation;
  clarified existing review authorization and removed the plan-work dependency.

#### Refine task navigation, Settings and Setup (2026-09-11–14)

- Matched closed combobox triggers to the authored 1.2px button/textbox
  perimeter while retaining the popup's separate 1px material border.

- Limited the dual textbox focus ring to keyboard-origin focus while keeping
  pointer-focused fill and accent feedback. Repainted the lower strip as a
  straight 2px layer with tapered rounded-corner ends rather than a border that
  curves up both sides.

- Investigated intermittent disabled-button label blur without changing CSS:
  disabled text is an opaque dedicated color with no whole-button alpha,
  filter or transform; recorded the WebView2 reproduction tuple needed to
  distinguish DPI/rasterization from transparent-composition behavior.

- Replaced the textbox's overlapping full border and inset underline with a
  clipped 1.2px perimeter whose 2px bottom edge carries the resting/focused
  neutral or accent state; disabled inputs flatten all edges.

- Aligned ordinary and accent button boundaries with Microsoft WinUI elevation
  resources, retaining the authored 1.2px stroke and clipping neutral fills to
  the inner border edge.

- Scoped the current batch queue to editable Sync Setup projection. Inventory
  hides retained sync rows and can start while queued sync work remains; active
  batch serialization and close/retry ownership are unchanged.

- Replaced the selected checkbox font glyph with the pinned local Fluent
  `checkmark_16_regular.svg` mask; the mixed-state minus and unrelated status cue
  remain unchanged.

- Made Add pair capture its own settings snapshot, removing the later
  current-form overwrite. Queued settings survive form edits, prepare per row,
  and retain exact retry; removal during preparation prevents submission.

- Replaced opaque button, textbox and combobox trigger fills with WinUI alpha
  roles in both themes, including disabled/input-active states and off-state
  switches/checkboxes. Accent-on and independent popup materials remain.

- Tuned dark ordinary-button fill and edge opacity, softened disabled textbox
  top/side strokes, and matched buttons, toggles and checkboxes to the selected 1.2px border
  adjustment for fractional-DPI Chromium rendering.

- Matched WinUI logical stroke sizing and button edge tones, centered switch
  thumbs with native hover/press proportions and disabled colors, and ratified
  the shared path Clear button in the gallery. Fractional-DPI pixel snapping
  remains browser-owned.
- Replaced Setup carets with pinned Fluent chevrons, aligned availability dots,
  and removed automatic pointer-open recent-folder selection. Batch footer
  actions now stay with their table and disable when they have no work.
- Tightened Setup path-label spacing, separated option toggles and aligned
  Source/Target values in paired rows. Lightened disabled dark controls to
  #2a2a2a while preserving light and transparent-control styles.
- Restricted the Ready-label test override to explicit smoke launches, restoring
  the intended hidden Ready label in the editable development shell.
- Deferred native overlay scrollbar integration, verify-only batching and
  persistent customizable pair presets to M2, keeping their new backend and
  persistence contracts out of the M1 GUI refinement.
- Added a Fluent-style CSS scrollbar approximation with a fixed small gutter,
  an always-visible softened thin thumb and wider direct-hover/drag thumb.
  Tables share stable header/body column widths and reserve the vertical gutter
  below the header; horizontal scrolling moves both together only when needed.
  Native scrolling and forced-color defaults remain; hover does not shift content.
- Added a conditional batch table with paths, attempted settings, short statuses,
  queued removal and explicit clearing of settled results. Single and batch
  creation actions align right; single Create stays disabled while batching.
  Results remain with their origin. An 8px gap separates the batch table from
  its footer actions.
- Compacted recent and batch tables to five 56px row slots under 28px headers,
  with labelled paths and overflow scrolling. Removed routine Setup headings
  and hid the app's ordinary Ready label while preserving visible native
  closing and retry guidance.

- Investigated native Fluent overlay scrollbars: the pinned wrapper does not
  expose the required environment option. Recorded the native-hook limitation
  before adopting the bounded CSS approximation.
- Scoped batch feedback to its originating Setup, labelled both paths, and
  allowed queued-row removal without canceling submitted requests. Pending
  reconciliation remains accessible; fresh tasks no longer inherit messages.
- Matched recent-pair folder-column insets and unavailable-row hover behavior.
- Added a minimal Settings/About work page with the existing theme selector,
  preserving task drafts and activity. Task items scroll independently above
  the rail's Settings button.
- Simplified Setup to Verify execution and Additive sync toggles, local path
  Clear actions, compact transparent icon controls, and right-aligned pair
  actions. Recent pairs match gallery table styling and interact as whole rows.
- Added the pinned Arrow Clockwise glyph through icon maintenance, documented
  exclude-filter syntax and effects, and condensed completed GUI plan history.
- Preserved the gallery's natural-height layout alongside the bounded task
  shell, with an installed check against overlapping specimen sections.

- Refined alignment and density: removed the repeated task heading and extra
  dividers, grouped the primary options, and placed More options
  on the right. Recent pairs show a separate availability result per path.
- Expanded task cards with inset dismiss icons and 24px selection marks;
  transparent idle icon controls retain hover/press and keyboard-focus feedback.
- Kept standard path textboxes with inset caret buttons and accented active
  underlines; removed extra textbox rings, default dropdown-option borders and
  empty/ready hints. Advanced labels follow their toggles; Add filter is inline.
- Split Setup and Recent pairs into two cards. Reused the segmented task switch,
  inline path/recent-folder controls and folder-open Browse icons; kept deletion
  and verification visible while folding remaining toggles and filters.
- Added a taller two-column recent-pair table with stacked truncated paths and
  neutral status text beside green/red availability dots. Unavailable rows stay
  visible and cannot be selected.
- Added a bounded read-only asynchronous availability probe through the existing
  location resolver, without choice slots or retained authority. Refresh is
  coalesced; stale replies are ignored and starts still re-admit roots.
- Preserved actual hidden-mode/action visibility and keyboard focus through
  rerenders. Verified with 4,979 ordinary tests (four skips), all 30 installed
  headed tests, 12 import contracts and independent adversarial review.

#### Expand the icon vocabulary and selective usage guidance (2026-09-11)

- Registered all 47 requested Regular Fluent glyphs from the existing pinned
  package, with 136 native SVGs covering 16/20/24 px and five explicit size
  fallbacks. Preserved static local masks, provenance, accessibility and status
  semantics; no blanket icon placement or startup layout change.
- Established selective placement and restrained density as stronger rules
  than the flexible action examples and glyph mappings. Badges retain their
  existing operation/status cues.
- Replaced per-icon multi-file editing with one JSON catalog and an authenticated
  archive sync/check tool. Generated registry, CSS and provenance remain fixed
  shipped source; independent safety and rendering checks remain. Removed the
  superseded root icon list with user authorization.
- Registered maintenance command syntax and options in TOOLS.md, linked from
  the desktop icon guidance.
- Verified removal and package-version transitions with synthetic archives and
  documented caller cleanup, fallback reconciliation and upgrade refusal rules.
  All 29 maintenance tests and 334 tools-department tests passed (three skips);
  pinned-archive check and independent review passed. Tool behavior was sufficient.
- Verified 61 focused checks, 4,972 ordinary tests (four skips), all 30 installed
  headed tests, authentic archive correspondence and a zero-change sync. Fresh
  adversarial review passed.


#### Deliver frozen task Setup and location flows (2026-09-11)

- Added editable typed, picker and recent folder inputs, standalone inventory
  starts, complete backend-canonical task options, and serial best-effort pair
  creation. Editing invalidates a prior choice; starts re-admit current roots.
  Defaults only seed Setup and are never changed by a task.
- Reused task/session ownership to attach the first session to an existing
  blank task. Async results and task lists stay small; per-task readback restores
  frozen Setup. Plan again resolves retained reviewed identities afresh, creates
  a separate task and preserves options without copying selection or authority.
- Condensed completed M1-5 history and recorded the unresolved transparent-host
  rendering issue in BUGS with indefinite deferral. No material workaround,
  M1-7 review/execution content or durable task recovery is included.
- Verification: 1027 passed, 2 deselected in 28.13s; neighborhood 2731 passed, 2249 deselected in 113.29s (0:01:53);
  ordinary 4946 passed, 4 skipped, 30 deselected in 212.33s (0:03:32); installed headed 30 passed, 4950 deselected in 150.10s (0:02:30);
  all 12 import contracts. Four unchanged core/tool symlink cases were skipped
  for unavailable Windows privilege; final independent adversarial review passed.

#### Restore live task-rail selection cues (2026-09-11)

- Aligned the live rail's current-page state with the gallery task-card styles:
  persistent neutral selection fill and a 3 px accent marker, including hover,
  press, keyboard focus and forced-color treatment. Close remains a text button.
- Added live installed-wheel selection-paint and transfer assertions alongside
  the existing navigation/closure checks, retaining the gallery state variants.
- Verified the pre-fix failure, 56 focused and 1,503 interface checks, all 29
  installed-wheel headed tests, import contracts and fresh adversarial review.
- Investigated the SDR dark dropdown halo without changing shadows. User
  comparisons and native probes identify automatic-color-management and
  transparent-host dependencies at unchanged 10 bpc, without proving a renderer
  cause. The opaque diagnostic host appeared unaffected; Mica is retained and
  the unresolved issue is tracked in BUGS.
- Re-audited shadow composition and ran paired Mica diagnostics. User observes
  the WCG SDR halo with broad key shadows over translucent receivers, not opaque
  receivers; alpha-zero white/black makes no noticeable difference. No wrong
  shadow token or duplicate elevation was found, and no rendering fix is claimed.

#### Deliver bounded M1 command and location prerequisites (2026-09-10)

- Detailed M1-5's finite production, test and documentation population, one
  acceptance gate and atomic outcome, current owners/seams, archived-clause
  dispositions, preimplementation regression probes and final adversarial review.
  The user authorized M1-async followed by M1-5 after the M1-4 recap.
- Separated native admission and completion for create/start/release/close,
  preserving direct/custom command behavior and current task/session effect
  owners. One shared exchange budget retains both worker exits and both delivery
  phases; reload retires delivery while admitted work continues. The existing
  document channel carries bounded completions with readiness priority and
  appearance fairness, and browser uncertainty uses existing recovery.
- Kept command delivery independent of cosmetic acknowledgement and prior
  lost-delivery receipts while preserving one native send and the shared bound.
  Async closure passed 4,884 ordinary tests (four existing privilege skips),
  all 29 installed headed tests, the affected neighborhood, imports and fresh
  adversarial review.
- Unified fresh plan and inventory/integrity location admission in the workflow,
  preserving literal inputs, current identity resolution and point-of-use
  re-probes. Equal task-plan replays return before location work; fresh refusal
  rolls back the claim before delivery or session creation.
- Added read-only, run-derived source/target/pair suggestions, each limited to
  five results after stable-identity deduplication. Remembered activation resolves
  identity afresh. Setup widgets, schema indexes and later M1 work remain pending.
- M1-5 closure passed 4,912 ordinary tests (four existing privilege skips),
  all 29 installed headed tests, focused and neighborhood checks, imports,
  documentation checks and independent review.
- Condensed completed M1-4 into its delivered/excluded outcomes and added
  explicit product-checkpoint status. Ratified lightweight expansion with a
  next-checkpoint design lane that refreshes against the predecessor's final
  state before implementation.
- Separated repository scope/stop requirements from the installed execute-task
  skill's probing, in-turn adjudication, bounded waiting and recovery procedure.
  Unanswered decisions never authorize scope; architectural and hard-wall stops
  retain their distinct handling.

#### Activate process-live desktop tasks (2026-09-09 – 2026-09-10)

- Added blank task creation, newest-first navigation, retained task enumeration,
  and explicit close through the existing lifecycle and observer owners.
- Busy close requests cancellation and retains the card until settlement;
  failed close remains retryable. Terminal session release preserves the task,
  and reinjection reconstructs current identities without repeating domain work.
- Preserved the shared 48-task bound, exact bridge validation and observer
  custody. Added installed-WebView2 task-shell witnesses and migrated exact
  command/close-result, gallery, keyboard, native-return and diagnostic-fixture
  consumers after scope adjudication. The 29-test headed gate and 4,862-test
  ordinary suite pass, with four existing capability skips in the latter.
- Contained obsolete pywebview return callbacks across reload using the existing
  document generation and a one-shot worker marker. Stable-generation JavaScript
  and non-JS errors remain visible; command effects, receipts and actual worker
  exit retain their existing owners and bounds.

#### Activate exact core event v5 (2026-08-25)

- Pinned executor recording settlement truth in the retained oracle, then made
  operation-local reasons and ordered task issues active without changing
  filesystem outcomes or oracle traces.
- Staged strict v5 consumers before atomically switching core producers,
  dispatcher admission, service views, history, CLI, and packaged JavaScript to
  one exact event schema. Reliable envelopes are rejected above 1,048,576
  canonical bytes before sequence or queue mutation, and terminal summaries no
  longer duplicate item arrays.
- Activated checked signed-64 arithmetic and canonical decimal public scalars,
  typed logical-byte review refusal, bounded diagnostic omission witnesses, and
  the complete core-owned Windows `FILE_ID_128` adapter with no legacy high/low
  narrowing. Workflow payloads and the version-2 verifier-rig sidecar keep the
  complete file index as canonical text rather than a JSON number.
- Reset persistence to ledger v4/history v6 at shared data epoch 5, stored
  `FileIndex128` as canonical text, strengthened ledger/history integrity
  checks, and made old, mixed, markerless, one-present, and orphan-sidecar pairs
  refuse with coordinated reset guidance.
- Preserved canonical CLI item detail for sessions that finish before
  observation by reading the finalized fixed history watermark; degraded audit
  remains an explicit live-only fallback. The now-unreachable private v3/v4
  decoder source was removed separately after the protocol cutover.

#### Ratify the Stage 6 second-half reslice (2026-08-24 – 2026-08-25)

- Accepted the ordered prerequisites for Slices 5–6 and early Slice 7 while
  keeping every target contract inactive until implementation; split the
  foundation documentation into five serviceable commits.
- Centralized exact protocol, command, result, task-authority, and retry shapes
  in one Bridge register mapped back to the owning DR-BR records, with explicit
  supersession instead of a blanket precedence clause.
- Made Defense the normative owner of the signed-64 and retained-resource hard
  walls, replaced Core's decoder-debt discussion with current and accepted
  boundaries, and reduced component docs to local consequences and pointers.
- Kept Features at product behavior and Tests free of a parallel implementation
  or case catalog. Independent authority, component, Bridge, and final integration
  reviews closed the discovered selection, publication, epoch, recents, and
  mixed-version contradictions before ratification.
- Restored useful retry after an execution that did not run: the unchanged
  plan's selection reopens at a new revision and a retry mints a fresh
  commitment, while `disposition=ran` permanently consumes the authority.
  Added identity-safe **Plan again** through `activate_task_pair`, and reopened
  BR-G-46 with exact 12/18/36 command-map totals.
- Re-audited the retained findings; separated reachable timestamp/aggregate
  scalar walls from assertion-only capacity and post-admission arithmetic,
  corrected native file identity to full-width canonical text from one shared
  adapter, and assigned reachable plan/timestamp failures exact typed outcomes.
  Retained the protocol transition before its v5-dependent task foundation with
  three independently testable landing stops and added four nonduplicative
  causal bug records.
- Bound every command-activating delivery step to BR-G-32's executable exact-
  order production table and JavaScript mirror, while keeping BR-G-46's
  command-map status scoped to the later task-rail and Setup revisions.

#### Extract truthful per-item progress (2026-08-21 – 2026-08-23)

- Established core Progress v4 as the central phase/item/attempt protocol:
  selected and reliably settled item counts, monotonic attempted-byte
  high-water, display-only paths, authoritative control boundaries, and
  explicit `Gap` recovery. Terminal and history byte counters describe
  attempted work, not durable publication.
- Aligned executor, standalone integrity, and linked post-copy reporting across
  pause, resume, retry, cancellation, failure, overrun, and missing-evidence
  work. Attempt identity begins at real byte-stream entry and renews on retry or
  reconstructed resume; reliable outcomes remain settlement authority.
- Added an O(1) browser reducer with exact v4 validation, phase/attempt
  monotonicity, outcome/Terminal precedence, immutable projections, and atomic
  whole-batch replay. The real coalesced MKDIR handoff proves a newer active item
  can follow an omitted inactive boundary without weakening same-item ownership.
- Kept bridge envelopes v1, execution continuations v5, and database/page
  schemas unchanged; supported reliable v3 history remains readable while v3
  live Progress is refused. Strict live versus compatibility decoding remains
  tracked debt with executable separation guards. The dormant row gallery now
  consumes only an explicitly projected 0–100 value to render 4 px Copying and
  Verifying bars inside the standard 8 px cell padding; production row matching
  and live binding remain Slice 5 work.
- Rebaselined the protected settlement oracle only after semantics stabilized;
  all 30 scenarios and 70 policy rows passed three identical runs. Updated
  installed event/custody fixtures retained frozen v1 authority; a failed
  latency diagnostic and clean repeat were both retained without promoting a
  new acceptance claim. Slice 5 row projection and rendering remain open.

#### Ratify desktop color semantics (2026-08-21 – 2026-08-23)

- Ratified one 15-token authored palette and separated operation intent,
  task-lifecycle, and integrity channels. Hue identifies class while labels,
  structure, and accessible state remain authoritative; presentation form
  distinguishes ordinary text from attention badges.
- Defined paused progress as frozen yellow, canceled as neutral gray, resumed as
  accent, and aligned operation filters plus integrity/task labels to the same
  channel semantics. Every filled text pair meets the normal-text contrast
  floor, with system colors retaining forced-color authority.
- Kept plan and integrity renderers narrow and presentation-only while tightening
  unchecked-checkbox, dark-button, and semantic-label treatment; no form payload
  or JavaScript domain inference was introduced.
- Aligned compact filled labels to the checkbox radius and text edge, and made
  active operation chips use family main/90%/80% fills without lift or scale.
- Matched compact badge bleed and inner padding at 4 px, restored inline progress
  to the shared 8 px column inset, and returned inactive Delete to the normal
  filter's distinct hover/press backgrounds without changing its red-main text.
- Expanded the test-only gallery across intent, lifecycle, integrity, progress,
  light/dark, forced-color, and reduced-motion states, including projected sync
  and integrity lifecycle rows. Production file-list surfaces remain dormant.

#### Establish the dormant file-list row renderer (2026-08-20 – 2026-08-21)

- Added a shared packaged `file_row.js` skeleton with presentation-only plan
  and integrity specializations. It consumes explicit defended display values,
  imports no bridge or domain code, and remains absent from production startup,
  so the shipped workflow surfaces are still honestly dormant.
- Defined aligned six-column plan/integrity tables with compact rows, folder
  disclosure and tri-state selection, a master checkbox, five accessible
  resizers, row-only striping, one flexible path column, preserved Notes
  reserve, and bounded horizontal overflow.
- Drove the production renderer from test-only data covering every operation
  tone, representative integrity/error states, hierarchy, collapse/restore,
  selection reconciliation, column resizing, width transfer, minimum clamps,
  and all four appearance profiles. No provisional wire payload, workflow, or
  session contract was added.

#### Tune solid desktop control states (2026-08-20 – 2026-08-21)

- Consolidated controls around two button tiers, borderless filters/badges/
  progress, contrast-safe operation states, accent progress and selection, an
  exact-one-selected mode switch, and distinct content/task-card surfaces.
- Mapped the native Windows accent ramp into shared appearance-v2 interaction
  roles and replaced the native theme selector with a production-owned,
  keyboard-operable DOM combobox. Forced colors, reduced motion, Mica, and the
  dark-HDR shadowless fallback retain independent authority.
- Standardized Fluent focus strokes, checkbox/textbox/toggle geometry, compact
  file rows, and responsive host/container bounds without reintroducing the
  removed viewport media query.
- Expanded installed-wheel gallery evidence across light, dark, forced-color,
  and reduced-motion profiles for control hierarchy, interaction states,
  contrast, flyout/card composition, table geometry, and responsive layout.

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
  it; installed WebView2 witnesses are authoritative and Node is supplemental
  for that historical custody claim.

#### Establish the secured WebView2 bridge foundation (2026-07-31 – 2026-08-03)

- Pinned and validated the Edge WebView2 host path, refusing an MSHTML fallback
  before window creation.
- Enforced exact packaged origins, native navigation/frame/popup guards, and a
  strict bridge boundary resilient to reinjection.

### M1 Consolidation

Product, test, and documentation maintenance clarified ownership and removed
repeated machinery while preserving operational safety and boundary contracts.

#### Product simplification (2026-09-01 – 2026-09-08)

- Removed internal workflow JSON transports and repeated event certification;
  shared admitted immutable stats, progress, event details, history encoding,
  and item projections while preserving external and persistence validation.
- Consolidated task effect ownership, plan retirement, session observation,
  metadata storage, and idempotent cleanup replay. Fixed the plan-selection
  retirement race and bounded CLI ingress without changing mutation authority.
- Shared sync recording finishing, verification terminal projection, event
  vocabularies, clock contracts, and bounded database query batching. Removed
  the redundant history update trigger: history schema/shared data epoch is 7,
  ledger schema is 4, and old or mixed pairs require coordinated reset.
- Narrowed repeated scan validation; shared MOVE/RECASE rename mechanics and
  new-file/publication observation; removed named unused executor plumbing.
  Recording tails, pause/cancel blocks, and mutation-verdict constructors remain
  shelved. Native/pipeline behavior and settlement policy remain unchanged.
- Final integrated verification passed 4,862 tests with four unchanged privilege
  skips, including all 28 headed cases, plus 12 import contracts and the retained
  30-scenario oracle across three identical runs. Narrow-reduction replay
  detected 17 faults and passed eight harmless variations. Reviewed temporary
  branches/worktrees were removed; evidence remains in REDUCTION_FOLLOWUP.

#### Test consolidation (2026-09-01 – 2026-09-07)

- Consolidated boundary, lifecycle, review, inventory, executor, integrity, and
  browser witnesses around their behavioral owners. Shared fixtures, SQL,
  selection, theme, and required Node harness setup; retired redundant spelling
  assertions and temporary migration corpora without losing protected cases.
- Used isolated cohort ablation, fault probes, harmless variations, and fresh
  review to distinguish duplicate machinery from detection loss. Preserved the
  executor settlement oracle, native operation families, source-owner guards,
  population bounds, snapshot/atomicity checks, and visual/privacy evidence.
- Corrected headed native-return and reinjection observations separately from
  consolidation. The refinement closeout passed 4,678 tests with four capability
  skips, 12 import contracts, and replay of 63 faults plus five harmless
  variations; TEST_REFINEMENT and TEST_ABLATION retain the qualified evidence.

#### Documentation consolidation (2026-09-05 – 2026-09-09)

- Tested documentation removal against retained answers and counterexamples;
  separated active contracts from delivery history. BRIDGE and PRESENTATION
  own their subjects, INTERFACES owns lifecycle/host criteria, and M1_PLAN is
  the sole remaining delivery register. Superseded plans and studies are archived.
- Retired aggregate object-graph prescriptions while preserving admission walls
  and scoped resource-release evidence. The superseded compact-plan memory
  prerequisite does not govern frontend delivery; no new resource pass is claimed.
- Scoped the next task slice to page creation, rail/navigation, and safe close;
  folded later lifecycle closure into integrated verification. Retained fresh
  Plan-again review after refusal, first manual post-copy verification, and
  planned capacity/trash information. Deferred terminal domain retries,
  user-invoked session cleanup, and richer I/O categories to the M2 feature list.
- Reconciled behavior/status prose, inspected defect ownership, and consolidated
  this history. Documentation review and link/diff checks do not substitute for
  implementing or testing the remaining product features.

#### Separate historical criteria from active contracts (2026-08-27)

- Reconstructed a retrospective M0 plan from the final pre-M1 documentation
  snapshot, preserving historical qualifications and verification notes without
  treating them as current acceptance evidence.
- Removed 13 inherited component checklists after checking their later contract
  prose; retained the few unique current rules and measurement-fixture details
  in their owning documents. Newer prose prevails over stale criteria.
- Kept current M1 gates and explicitly deferred ingest criteria separate;
  updated references to the archived M0 source without changing runtime policy.
- Relocated all five imported PoC documents to `docs/obsolete/PoC_import/`
  byte-for-byte, updating references to identify them as historical evidence.

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

### M1 Hardening

Safety, settlement, authority, and measurement work made high-risk release
claims explicit, independently reviewable, and regression-backed.

#### Study and plan M1-7 ablation after delivery (2026-09-16)

- Study `ae3daf6` through `5986c57` from diff/structure to selected behaviors
  and consumers. Record twelve bounded candidates covering receipt/evidence
  machinery, retry/admission duplication, test coupling, internal selection
  transfers, repeated safety derivation and conditional historical retirement.
- Validate a canonical-comparator ablation with 33 focused tests before/after,
  and a synthetic-fixture separation with five controls before/after, exclusively
  in disposable copies. Retained tests detect both deliberately seeded faults;
  record the cohorts' limits and preserve live-fixture obligations.
- Reconcile two Codex sidecar reviews and one Opus 5 xhigh session, including a
  same-session challenge that corrects overclaims and rejects validation/API
  weakening. Preserve prompts, raw responses, usage and experiment provenance.
- Preserve the original study in user-requested commit `dbeb7a5`, then convert
  it into eight bounded implementation checkpoints and a final integration gate.
  Keep A1–A12, distinguish selected portions from deferred redesign/cleanup,
  and absorb peer-review reconciliation into the plan's actual constraints.
- Require baseline comparison, independent fault detection, exact evidence
  lineage and checkpoint-local acceptance. Latent product defects are report-only;
  no product fix or lighter rerun policy is implied by test simplification.
- Review and commit the documentation plan; production/tests and accepted
  measurements remain unchanged. No implementation, benchmark rerun, push or PR.

#### Bound task inputs, custody, and retained settlement (2026-08-27 – 2026-08-30)

- In scanner, planner, inventory, integrity, and repository paths, admitted raw
  populations before normalization or retention, detached collaborator results,
  and applied the shared 120,000-item support target to actual returned values.
  First excess now fails with the owning workflow's typed result and never saves
  a partial plan, inventory, or integrity artifact.
- In dispatcher, service, and the web bridge, attached exact task reservations
  before scheduling, scoped rollback and compensation to the returned session,
  bounded document/response custody and receipts, and consumed only the longest
  admitted drain prefix. Reload, timeout, collision, and reentrant paths cannot
  release another task's capacity or discard reliable updates.
- Across the core runner, workflows, history, dispatcher, and service adapters,
  retired consumed traceback, cause, context, callback, and dependency graphs
  while preserving public error identity, redaction, fail-stop behavior,
  cancellation precedence, retry state, and durable watermarks.
- In execution and integrity, retained reliable outcomes before reentrant work,
  added a plan-ordered exclusion cursor for pause/resume, revalidated settlement
  around recording finalization, and replaced repeated candidate reconciliation
  with one immutable selection-owned identity index.
- In root resolution, verifier I/O, and runtime shutdown, detached and rechecked
  mounted-volume facts before effects, bounded verifier chunks to 1 byte–4 MiB,
  and released or coherently retained all workflow custody maps according to
  dependency-close success.
- In core contracts and policy docs, separated cumulative review budgets from
  producer gates, recorded one-time adoption and scaling-evidence rules, slotted
  retained immutable values, removed a dormant Python patch-version gate, and
  kept Python 3.13+ without an upper-version restriction.

#### Close cross-layer contract review findings (2026-08-26 – 2026-08-27)

- Restored execution settlement and continuation authority, then aligned event
  v5, scalar/native identity, timestamp, reliable-byte, and browser transport
  contracts so malformed updates fail before custody changes.
- Made database admission inspect complete WAL-visible topology, reused admitted
  readers for fresh reads, stored private snapshots beside the local database,
  and separated payload-free session metadata/results from live continuations.
- Replaced inferred hash forms with explicit canonical projections, advanced
  full-width file identity to data epoch 6 with paired-reset guidance, and made
  JSON/UTF-8 boundaries reject non-scalar Unicode without changing valid bytes.
- Retired residual adapter/dispatcher exception graphs, removed private legacy
  event decoders, corrected the stale canonical-plan test vector, and recorded
  future server-owned sorting and null-evidence rebaseline behavior as accepted
  but unimplemented product work.

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
