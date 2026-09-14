# M1 Delivery Register

This is the sole active M1 delivery register. It records remaining accepted outcomes, their order, and the verification that closes each one. Implemented contracts are owned by their active subject documents; completed delivery history and superseded mechanisms are in [obsolete](obsolete/). The archived plan files retain historical staging and review but are not instructions for new work.

[BRIDGE.md](BRIDGE.md) owns external command, transport, retry/recovery, and bridge-gate contracts. [PRESENTATION.md](PRESENTATION.md) owns trees, views, search, selection, sorting, and scale evidence. [INTERFACES.md](INTERFACES.md) owns implemented task lifecycle and desktop host/package rules. [FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [DEFENSE.md](DEFENSE.md) remain the owners of product behavior, cross-layer meaning, and safety/evidence policy.

[PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) is the closed maintenance
subregister for the completed production-ablation pass under M1-12. Its PR-0
through PR-9 rows remove redundant implementation and test prescriptions; they
do not add, defer, or reinterpret an M1 product outcome.

## Main objectives and current boundary

[REDUCTION_FOLLOWUP.md](REDUCTION_FOLLOWUP.md) owns the accepted narrow
immutable-value, scan-validation, history encoding/projection, and executor
simplification follow-up under M1-12. Its NR-0–NR-9 register and migrated RF-E/RF-X
dispositions preserve existing product outcomes; implementation and integrated
verification are complete. Further product simplification is outside the
remaining frontend delivery scope.

The secured desktop host and transport, presentation foundation, current service/CLI surface, and implemented ledger/history boundary are active. The frozen v1 event-and-transport custody claim remains closed at its bridge evidence owner. That closure does not establish whole-runtime containment.

The process-live desktop task shell, shared location admission and frozen Setup
are active, including plan/inventory starts and Plan again. Finish reviewed
execution, execution/inventory projections, integrity controls and first manual
post-copy verification, then release closure. These remain unrealized frontend outcomes. The history page, global-settings mutation
page, drag-and-drop, file-scoped planning, durable task survival across a process
restart, durable sort preferences, status/progress or global-flat sorting, and
compare-and-accept rebaseline semantics remain deferred. User-facing terminal
execution/verification retries (including Verify remaining), user-invoked session
cleanup/trash purge, and richer I/O error categories are deferred to M2; see the
feature-only [M2 proposal](M2_PROPOSAL.md). Existing automatic retries, owned-temp
recovery, transport replay, close/shutdown recovery, and live pause/resume are
not removed by those deferrals.

The prior aggregate complete-owner-graph model and BR-G-45 are retired. No future work inherits its reservation, DTO, lease, byte-budget, command-count, or representation recipe. Completed M1-4 replaced the former task lifecycle/retention preservation checkpoint. Existing externally enforced ingress and population bounds remain active independently.

## Remaining checkpoints

### Translucent controls and queued options (2026-09-14)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S14 | Replace opaque ordinary control fills with WinUI translucent roles for buttons, textboxes, combobox triggers and off-state switches/checkboxes; retain accent-on treatment. | Official mapping, 31 focused checks, complete suite (5,013 passed, 4 existing skips), independent review. | Complete |
| GUI-S15 | Each added pair owns a cloned options snapshot through display, canonical preparation, submission and exact retry. | Setup/coordinator regressions, complete suite (5,013 passed, 4 existing skips, including installed Setup), independent review. | Complete |

Delivered from f711386 in two independent commits. S14 uses control-specific
WinUI alpha roles and one combobox fill paint with independent elevation edges.
Authored 1.2px strokes, tuned button/textbox borders, accent-on behavior and
forced colors remain. Popup materials, Mica and shadow composition are unchanged.
S15 captures settings at Add pair, renders them from the row and independently
canonicalizes each queued snapshot, eliminating the current-form overwrite.
Fresh admission, serial best effort, exact retry, removal during preparation,
epoch/close guards, the 48-row bound and origin ownership remain verified.
No protocol, backend or persistence changes; existing M2/shadow work stays
deferred. Evidence: build/gui-icons/gui-s14-focused05.txt, gui-s15-probes.txt
and gui-s14-s15-complete.txt. DESKTOP_UI owns the active behavior contract.

### Final GUI control polish (2026-09-13)

Follow-up GUI-S13 (2026-09-14): dark control palette tuning.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S13 | Tune dark ordinary-button fill/edges and soften disabled textbox top/side borders; retain the user's 1.2px button/toggle strokes and match checkbox strokes to them. | 31 focused token/installed-gallery checks, 1,528 interface tests and independent review passed. | Complete |

Bounded population: tokens.css, components.css, direct token/gallery test
consumers, DESKTOP_UI, HANDOFF and CHANGELOG. At 23c7b64 plus the user's two
1.2px edits, control-fill is used only by ordinary buttons; disabled textboxes
inherit the shared subtle border. Override only their top/side colors after
that shared rule, preserving bottom border, underline, fill and light/forced
colors. No toggle styling changes beyond retaining the user's edit, no backend
or other GUI behavior changes. The user additionally authorized matching
checkbox strokes to 1.2px during implementation; retain their equality witness
with buttons in the existing gallery. One palette commit includes the user edit and
its direct test/documentation updates; existing repository stop classes apply.
Evidence: build/gui-icons/gui-s13-focused02.txt and gui-s13-interfaces.txt.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S11 | Reference Microsoft button/switch strokes and switch thumb states, correct centering and disabled appearance, and ratify the clear-button gallery sample. | 78 focused, 1,528 interface and all 30 installed checks; official source study and independent review passed. | Complete |
| GUI-S12 | Use pinned Fluent chevrons in Setup, align availability dots, make pointer-open recents neutral, and retain both batch footer actions whenever the batch table exists. | Pinned-archive icon check, 100 focused, 1,528 interface, 4,983 ordinary (4 existing skips), all 30 installed checks and independent review passed. | Complete |

Boundary: browser presentation and local interaction only. No native backend,
Mica/shadow, dispatcher, admission, batch-runner or persistence changes. Preserve
keyboard/focus/disabled semantics, local clear behavior, same-command retry,
task-local batch results and existing table/scroll guarantees. Repository stop
classes apply. Each row is an atomic commit; root owns the sole test-run slot.

S11 delivers native logical stroke sizing and per-edge ordinary button tones,
centered 12/14/17x14 switch thumb states with preserved sliding motion, native
disabled fill/thumb roles and the shared path-Clear/gallery modifier. Existing
enabled fills, borderless primary buttons and system forced colors remain.
Inactive off-switch/button strokes deliberately stay stable. The official
source and browser pixel-snapping limitation are recorded in DESKTOP_UI;
verification observes the installed environment, not a controlled OS DPI matrix.
Evidence: build/gui-icons/gui-s11-{focused03,interfaces,headed}.txt.

S12 was studied at 014613c and revalidated against ffc3e6c. It removes the
automatic first-item highlight on pointer opening while retaining keyboard
focus, navigation and selection across pointer handoff. The batch container
owns footer visibility; each action preserves its eligibility guards. Four
directional Fluent chevrons are generated from the existing pinned catalog;
Setup uses centered 16px up/down glyphs and CSS-only optical dot alignment.
Production remains confined to Setup, app styles and generated icon assets;
the existing Setup/icon/gallery consumers verify it. The composition-action
geometry probe now scopes its selector to that row, excluding footer buttons
inside a hidden ancestor without weakening either row's alignment checks.
Evidence: build/gui-icons/gui-s12-{focused02,interfaces,ordinary,headed}.txt.

### Scrollbar layout and Setup polish (2026-09-13)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-R2 | Development windows hide ordinary Ready; only explicit smoke-test launches expose their readiness witness. | 55 focused, 11 installed and 1,528 interface checks plus independent review passed. | Complete |
| GUI-S9 | Always-visible softened thin scrollbars widen on hover; tables reserve a stable vertical gutter below their headers through shared column/layout ownership, with horizontal scrolling only as needed. | 84 focused checks, 4,983 ordinary checks (including interfaces), all 30 installed scenarios and independent review. | Complete |
| GUI-S10 | Tighten path-label spacing, separate primary and expanded options, align paired path values, and lighten disabled dark buttons to #2a2a2a. | 78 focused/installed checks, 1,528 interface checks and independent review passed. | Complete |
| GUI-D6 | Record native overlay integration, verify-only batching and persistent customizable pair presets as M2 outcomes. | Active feature/roadmap cross-reference and independent review passed. | Complete |

Non-goals: native backend/dependency changes, new batching or persistence commands,
Mica/shadow work, and JavaScript measurement loops for column alignment. Existing
task/admission authority, virtualized row bounds, keyboard/accessibility behavior,
column resizing and horizontal scrolling must remain intact. Repository stop
classes apply. Each row is an independently reviewed atomic commit; completed studies are
condensed below.

GUI-D6 records only accepted future outcomes in M2_PROPOSAL and FEATURES,
with matching DESKTOP_UI, README and changelog references. Presets are deferred:
existing recent-pair admission can be reused, but durable records and bridge
commands are not present. No current product behavior or M1 admission contract
changes. Gate: finite search of these active documents and independent review.

GUI-R2 (1398490) makes the development helper's Ready-label override an explicit
smoke-test opt-in. Normal development launches use the production hidden-Ready
behavior; readiness witnesses and close/error handling remain intact.

GUI-S9 delivers shared CSS header/body tracks and stable gutters for Setup and
file-list galleries, with one outer horizontal scroll area and body-only vertical
scrolling. It preserves native Setup table semantics, five 56px slots, column
resizing and forced-color fallback. Intrinsic header sizing keeps resized tracks
reachable without JavaScript alignment correction. Softened thumbs stay visible
and widen on direct hover/drag. Token ownership and independent upstream checks
remain intact. Evidence: build/gui-icons/gui-s9-final-{focused,ordinary,headed}.txt;
the ordinary suite includes the interface department. Four existing Windows
symlink-privilege skips remain; no GUI gate was skipped.

GUI-S10 follows S9 (42e86d1): compact form label tracks, 16px primary-option
spacing, 8px expanded-row spacing and shared-width Source/Target labels with
value-only ellipsis. The authored #2a2a2a dark disabled surface preserves light,
forced-color and transparent overrides; upstream Fluent provenance is unchanged.
Evidence: build/gui-icons/gui-s10-{focused,interfaces}.txt. No task, admission,
input-state or table-row-height behavior changed.

### Compact Setup tables and scrollbars (2026-09-13)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S6 | Conditional batch table retains results until cleared, shows paths/settings/short truthful status and queued removal; both tables use five 56px row slots and 28px headers with matching folder insets. Add pair precedes Create plan at the right; Create plan remains disabled during batching, and Create batch sits below the table at the right. Ordinary Setup guidance and app Ready status are hidden. | Browser behavior probes, installed Setup/shell/gallery checks, ordinary suite and independent adversarial review passed. HANDOFF records evidence. | Complete |
| GUI-S7 | Best-effort Fluent CSS scrollbars preserve native input, thin idle appearance and stable layout, with rounded hover styling where practical. | Official guidance, focused CSS checks, 1,526 interface tests, all 30 installed scenarios and independent review passed. | Complete |
| GUI-S8 | Separate the batch footer buttons from the table with a small vertical gap. | Both installed Setup checks, 1,526 interface tests and independent review passed. | Complete |
| GUI-R1 | Complete the S6 host-status visibility migration: native close messages become visible, and legacy smoke fixtures retain a truthful Ready witness. | 118 focused host/harness tests, all 30 installed interface scenarios and independent review passed. | Complete |

GUI-S6 shipped in 28eafcd. Batch receipts remain origin-owned under the existing
48-entry bound, serial runner, fresh admission and exact uncertain retry.
Prepared settings are frozen for each attempt; uncertain work is never labelled
Failed or Created. Clear results removes settled receipts, not tasks or pending
work. Blank slots are inert, and ordinary Ready remains internal readiness state.

GUI-S7 adds CSS styling for the eight existing native scroll owners: a fixed
10px gutter, 2px pane-hover thumb and 6px direct-hover/drag thumb, rounded ends
and neutral theme tokens. Forced colors retain browser defaults. Native wheel,
track and drag input remain browser-owned; true overlay painting, fading and
input-mode detection are not claimed. No host flags, dependencies, Mica changes
or replacement JavaScript scrollbar were introduced. DESKTOP_UI owns the
behavior and reference links; HANDOFF records verification. Independent review
and the complete interface/headed gates passed after the GUI-R1 correction.
GUI-S8 adds an 8px token-based gap above the batch footer. Installed geometry
checks preserve table height, footer alignment and action guards; no wider
layout or behavior changed.

GUI-R1 completes the S6 visibility-consumer migration. The native close renderer
writes fixed closing/retry guidance before revealing the label; text-write
failure leaves stale Ready hidden. The legacy installed-host fixture explicitly
displays its test marker while retaining the literal post-handshake Ready waits.
The earlier materials/shell/native completion-marker corrections remain intact.
No readiness, shutdown, process-ownership or error policy changed. Independent
mechanism and final reviews passed, with 118 focused tests and all 30 installed
interface scenarios (gui-r1-focused-01.txt and gui-r1-headed-01.txt).
### Scrollbars and batch feedback (2026-09-12)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S4 | Investigate native Fluent overlay scrollbar support in the pinned host; enable it only through a narrow supported integration, otherwise retain current behavior and document alternatives. | Official API and pinned initialization path inspected: pywebview lacks the environment-options hook. No product change; DESKTOP_UI records native/CSS options. Independent review passed. | Complete |
| GUI-S5 | Recent pairs use 60px rows, increased folder-column inset and consistent disabled-row hover; batch rows identify both paths, stay with their originating Setup, and allow removal before submission. | Focused browser checks, ordinary suite including interfaces, all installed headed checks and independent review passed. HANDOFF records evidence. | Complete |
| GUI-D5 | Assess better housing for batch composition and status without implementing a new batching surface. | Existing Setup/coordinator/rail inspected; DESKTOP_UI compares conditional disclosure, action popover, page tray and dedicated page. No new surface implemented. | Complete |

Delivered from 1bbbeb4: native scrollbar integration was assessed and deferred
without a workaround (`1159abc`). Batch rows now retain origin identity inside
the existing page-wide 48-pair coordinator; queued removal never cancels a
submitted effect. Origin/adopted-task controls keep unresolved requests visible
and preserve exact retry. Pending close cannot start a batch. Recent pairs use
60px rows, 12px folder insets and uniform disabled-cell feedback. DESKTOP_UI owns
the details and nonbinding batch-housing options. No backend/protocol change,
vendor patch, dependency upgrade, scrollbar CSS or Mica workaround was added.

### Agent instruction maintenance (2026-09-12)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| AI-1 | Clarify repository execution boundaries and retire the completed monolith prerequisite; update only the personal execute-task and claude-code-reviewer skills to handle those boundaries. | Diff and adversarial scenario review passed; both skill validators passed; Git whitespace and exact staged scope checked before commit. | Complete |

Population: AGENTS.md, this register, CHANGELOG.md and HANDOFF.md; outside the
repository, only the two named personal SKILL.md files. Repository rules own
scope, acceptance and stops; execute-task owns operating mechanics. One repository
documentation commit; personal skill edits remain outside repository history.
Non-goals: product/test changes, global AGENTS.md, supplied skills, invocation
metadata, model-family changes, new references or relaxed hard-wall stops.
Regression study: check routine in-bound consumer edits versus explicit exclusions,
changed safety/ownership models, repeated findings, unanswered scope questions,
existing review authorization and completion before reporting. Preserve numerical
recurrence gates, oracle retention and independent review. The completed split is
recorded in CHANGELOG's August 10–11 maintenance entry; its historical prerequisite
must not be presented as a pending operation. No product suite is needed for these
instruction-only edits; final review must account for each preserved boundary.

### Settings shell and GUI refinement (2026-09-12)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-S3 | Minimal Settings/About work page with relocated theme control and preserved tasks; independently scrolling rail above Settings; refined Setup controls, row-wide recent-pair interaction, one refresh glyph, filter documentation and condensed completed GUI history. | Ordinary suite, installed shell/Setup/gallery checks, icon provenance, import contracts and independent adversarial review passed; HANDOFF retains evidence pointers. | Complete |

Delivered from 76028db: Settings preserves task identity, drafts and live updates;
About initially contains only the version line. Clear invalidates a local path
without admission, including rejection of stale replies. Existing task custody,
frozen options, fresh admission, batch effects and navigation restrictions remain.
The gallery retains natural document height, with an overlap guard, while the
production rail and work area scroll independently. DESKTOP_UI owns the controls,
PLANNER owns exclude-filter syntax. No backend setting, legal content, lifecycle
change or Mica/shadow workaround was added.

### Completed GUI integration

| IDs | Delivered |
| --- | --- |
| GUI-1, GUI-S1, GUI-S2 | Gallery-consistent task selection cues; two-card Setup with task switch, path recents, Browse, progressive options and per-endpoint recent-pair availability; full-width task cards with inset dismiss; standard textbox focus and stable disclosure layout. |
| GUI-I1, GUI-I2, GUI-I3 | Selective Fluent icon vocabulary and size fallbacks, one authored catalog with offline sync/check maintenance, provenance/safety/packaging checks, and documented removal/version-upgrade workflow. |
| GUI-D1–GUI-D4 | Diagnostic shadow audit: dark dropdown key shadows over translucent cards can halo in 10-bpc WCG SDR; disabling automatic color management or using an opaque host removes the reported effect. Ambient-only/opaque receivers appear unaffected. No exact renderer cause or fix established. |

[DESKTOP_UI.md](DESKTOP_UI.md) owns current controls and icon placement;
[TOOLS.md](TOOLS.md) owns icon maintenance. Recent-pair availability is a bounded,
coalesced read-only observation, not admission authority; starts re-admit roots.
[BUGS.md](BUGS.md#desktop-material-composition) retains the unresolved shadow
issue and investigation boundaries. Mica remains required; no workaround or
new release gate was added. Superseded GUI implementation studies and test-run
counts are retained in Git history rather than this delivery register.

### Documentation reconciliation pass (2026-09-09)

This closed maintenance register covers the accepted frontend decisions and
branch reconciliation only. It does not authorize product or test changes,
executor restructuring, new retry/cleanup mechanisms, or revival of compact-plan
memory prescriptions. Existing safety and measurement policy in `AGENTS.md` and
`DEFENSE.md` remains unchanged.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DOC-1 | Reconcile M1 lifecycle, fresh replanning, terminal actions, capacity/I/O presentation, trash information, and M2 deferrals across active subject docs; consolidate maintenance history and inspect defect sections. | Reviewed against service/executor behavior and accepted decisions; active-doc contradiction search, all 148 local links/anchors in 34 active Markdown files, history-preservation checks, docs-only scope, diff whitespace, and fresh adversarial review passed. BUGS module sections remain appropriate; no entry changes. | Verified for documentation commit |
| DOC-2 | Remove only the four superseded compact-plan commits from `milestone1` after DOC-1 is committed and verified, then open a draft PR from `milestone1-anthony`. | Verify exact divergence and remote tips, preserve the old tip in a recovery ref, reset only the named base branch, verify the resulting PR base/head/draft state and clean current worktree. Unexpected additional base-branch commits or unaccounted work stop this row for adjudication. | Pending |

Discovery is limited to active Markdown documentation and the service, workflow,
executor, projection, and test evidence needed to distinguish current behavior
from accepted targets. Findings outside these decisions are reported, not fixed.
No product suite rerun is claimed by a documentation-only check. DOC-2 depends
on DOC-1; no merge or implementation of remaining M1 rows is authorized here.

### Documentation and procedure pass (2026-09-10)

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DOC-3 | Condense completed M1-4; expose product checkpoint status; register and expand M1-async; reconcile repository policy with the installed execute-task procedure and ratify lightweight checkpoint expansion. | Docs-only scope, all existing pending outcomes and alternate ordering preserved, 60 local links, exact skill installation, diff checks and adversarial scenario/design review passed; applied drafts cleaned. | Verified for documentation commit |

This user-authorized pass changes only `AGENTS.md`, this register, README,
CHANGELOG, HANDOFF and the installed
`C:\Users\Spectrum\.codex\skills\execute-task\SKILL.md`. The referenced
plan-work skill is read-only. No product, test, measurement authority, branch
reconciliation or pending checkpoint implementation is included. Diagnostic
artifacts use ignored `build/m1-procedures/`: `inputs/` holds original skill
content, `drafts/` holds reviewed replacements, and `evidence/` holds checks;
remove applied drafts at closure and retain the original and verification
receipt. The skill is outside repository Git history; verify its separate
installation and record that distinction. Existing hard-wall stops still apply.

### Product delivery register

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification | Status |
| --- | --- | --- | --- |
| M1-4 | Process-live blank task creation, navigation and explicit closure through existing lifecycle owners, with generation-aware callback containment. | Delivered in `ab453e1`; ordinary/headed checks and adversarial review passed. Active contracts are in BRIDGE and INTERFACES; concise delivery record below. | Complete |
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Complete |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Pending |
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Before M1-8, use the existing failure-policy/Stop and settlement paths; verify direct and wrapped capacity failures, ordinary I/O distinction, current-effect/recording truth, later work left unrun, terminal projection, and unchanged sharing-violation retries. Run executor plus core/workflow/interface consumers and the retained settlement oracle. No general I/O taxonomy or settlement restructuring. | Pending |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | Pending |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


## Checkpoint expansion and scope decisions

Use this lightweight expansion before each pending checkpoint, drawing on
`plan-work` without duplicating its full template. AGENTS owns the boundaries;
`execute-task` supplies the decision, waiting and recovery procedure. These
requirements remain usable without either personal skill installed.

1. Start from the accepted outcome and current repository revision. Trace the
   owners, state/effect transitions, direct consumers and harness dependencies;
   include helpers outside the initially selected directory. Record the finite
   corpus, relevant observations and remaining uncertainty.
2. Name the finite production, test and documentation population, current
   owners/seams, one acceptance gate and atomic commit boundary. State preserved
   guarantees, excluded/archived clauses and dependencies. Add only the detail
   needed to implement and review that outcome; findings do not silently become
   scope.
3. Probe likely regressions during design: lost guarantees, false states,
   unauthorized/duplicate effects and newly unbounded work. Tie each concrete
   risk to a reached seam and named verification. Record baseline evidence;
   red tests indicate a question, green tests do not prove absence of defects.
   Implementation validates this map rather than starting a broad discovery pass.
4. Require final adversarial review of source, tests, documentation and evidence
   at the checkpoint gate. Completion requires the gate and preserved baseline,
   not a favorable test count. After delivery, replace detailed working/recovery
   notes with what happened, what did not, and commit/contract/evidence pointers.

One next-checkpoint design lane may begin during the current checkpoint's final
product implementation and continue through testing, verification and review.
It is read-only toward product and test sources; serialize shared plan edits.
Record the inspected revision, then compare affected seams against the final
integrated predecessor before implementation. Refresh only changed assumptions,
consumers and probes. A current finding that changes those seams reopens that
part of the next design. Design readiness cannot waive predecessor completion,
implementation authorization or the user's pause.

Elaborating an accepted pending outcome within these boundaries is planning;
enlarging an active implementation population or its mechanism is a scope
decision. For the latter, suspend dependent edits and first complete the finite
dependency probe and one consolidated proposal. A narrow, understood extension
may obtain explicit adjudication in-turn using the available permitted input
mechanism; unanswered requests within the bounded procedure become a full stop.
Architectural or unresolved changes require a full stop with the design study.
Hard-wall stops take precedence immediately. Record approved scope before edits;
silence never expands it, and unchanged approvals are not requested again.

## M1-4 delivered

Delivered in `ab453e1` on `milestone1`: process-live blank task creation,
newest-first navigation, reinjection/recovery and explicit closure using the
existing lifecycle, observer and service owners. Terminal release retains the
task; busy close requests cancellation and removes the card only after
settlement and successful close. Failed close remains retryable. Existing
48-task admission and command/receipt/worker bounds remain enforced.

Generation-aware native callback containment prevents obsolete pywebview return
errors after reload while preserving command effects, recovery, current error
visibility and actual worker-exit accounting. This is not an atomic JavaScript
delivery fence; [BRIDGE](BRIDGE.md) and [INTERFACES](INTERFACES.md) own the active
contracts and limitation. Exact test consumers were migrated without filtering
stderr or relaxing their independent assertions.

No Setup/workflow content, durable task survival, domain retry/purge controls,
asynchronous command boundary or new timing/whole-runtime memory acceptance was
delivered in M1-4. Acceptance passed 4,862 ordinary
tests (four existing capability skips), 29 installed headed tests, all 12 import
contracts, documentation checks and independent adversarial review. Detailed
task history is in CHANGELOG; recovery chronology remains in Git history.

## M1-async delivered

Native create/start/release/close now separate admission from bounded completion
through the existing document channel. Ordinary/custom dispatch stays
synchronous. Task/session owners still execute and recover effects; reload
retires delivery without canceling admitted work. One shared 64-exchange budget
retains both actual worker exits and both delivery phases before reuse.
Completions are capped at 65,536 UTF-8 bytes, with a bounded FIFO, readiness
priority and appearance fairness. Browser correlation distinguishes host and
page generations, bounds early delivery, and uses existing recovery after
uncertainty. The atomic native final-epoch/send guard remains intact.

No generic scheduler, cancellation framework, durable command history,
whole-runtime resource certification, retired reservation/lease recipe or
M1-5 location behavior was delivered. Direct-response limits and all M1-4
effect, recovery and lifecycle guarantees remain active. The user-approved
README status update and logging startup-fixture migration are included.

M1-async-G covers the declared transition matrix, four command projections,
replay/timeout/reload, two-worker custody, first-excess population/size refusal,
post-effect delivery failure, saturation cleanup and shutdown recovery. Its
focused, neighborhood, ordinary, installed headed, import and documentation
checks accompany fresh adversarial source/evidence review. BRIDGE and
INTERFACES own the implemented contracts. The checkpoint is delivered by
`feat(web): add bounded asynchronous command completion` on `milestone1`
from `74aa6b7`; Git history identifies the atomic commit.

The preimplementation twelve-selector baseline and pinned runtime/source
receipt remain in `build/m1-async-design/evidence/`. The finite accepted plan,
replay inputs, transition matrix, per-run candidate hashes and raw closure
results remain in ignored `build/m1-async/inputs/` and `evidence/`.
HANDOFF records the final counts and immediate next work. These functional
checks do not change protected measurement authority or close release gates.

## M1-5 delivered

Delivered in `e19ed9d` on `milestone1` after M1-async. Fresh picker-backed
plan starts and inventory/integrity share typed location admission. Inputs
are literal and bounded; current volume identity, remount/clone resolution,
no-follow admission and existing point-of-use re-probes remain effective.
Remembered sources, targets and active pairs derive from durable sync activity,
each limited to five identity-deduplicated results. Remembered hints grant no
authority, and merely selecting or admitting a location writes no recent record.

Task refusal creates no delivery/session effect; equal replay performs no new
native admission. Two introduced service regressions were corrected before
delivery: exception-context retention and oversized input entering task custody.
Preimplementation probes were refreshed on integrated `675181a` before coding.
Closure passed 680 focused, 2,697 neighborhood and 4,912 ordinary tests (four
existing privilege skips), all 29 installed WebView2 tests, twelve import
contracts, documentation checks and independent adversarial review.

No Setup widgets, frozen options, Plan-again UI, schema/index changes, domain
policy changes or new resource certification were delivered. Retired DTO,
reservation and command-count recipes were not revived. Raw evidence remains
under `build/m1-5/evidence/`; later checkpoints implement the remaining user
outcomes through their own accepted gates.

## M1-6 delivery

M1-6 delivers backend-canonical frozen Setup with typed, picker and run-derived
recent folders/pairs; task-local options; standalone inventory; serial
best-effort pair creation; and fresh-identity Plan again in a new task.
Existing task/session owners attach the first session to a blank task and
preserve stable replay, recovery, close and admission bounds. Picker ambiguity
uses the user-approved purpose-bound continuation within the existing slot
population; an explicit current mount is required before Start.

Whole-gesture revisions prevent stale edits from restoring folder authority.
Form and batch starts exclude one another; uncertainty retains the same command
for retry. Per-task readback restores frozen inputs, and plan readiness requires
an actual artifact. Global defaults remain unchanged.

The same checkpoint condenses M1-5's delivered history and records the substantive
transparent-host rendering issue in BUGS without changing its header/policy.
Its cause remains unconfirmed and investigation is deferred indefinitely.
Changes to native Mica/material or global settings, durable tasks, M1-7
review/execution, inventory projections and new resource certification remain
excluded. Retired
command-count, reservation and aggregate-owner-graph recipes remain retired.

M1-6-G verification: 1027 passed, 2 deselected in 28.13s; neighborhood
2731 passed, 2249 deselected in 113.29s (0:01:53); ordinary 4946 passed, 4 skipped, 30 deselected in 212.33s (0:03:32);
installed headed 30 passed, 4950 deselected in 150.10s (0:02:30); all 12 import contracts.
The four ordinary skips are unchanged core/tool symlink cases lacking Windows
privilege (WinError 1314); no M1-6 or bridge gate was skipped. This checkpoint is
not release-wide or compositor-health acceptance. Final independent adversarial
review and documentation/hash checks passed before its atomic commit.

Delivery is one `feat(web): deliver frozen task setup and location flows` commit
on `milestone1`, based on `b98dce4`. The accepted study is retained in
[the archive](obsolete/M1_6_SETUP.md). Exact commands, candidate hashes, raw
results, review dispositions and screenshots are in ignored `build/m1-6/`;
successful gate directories are `focused-final05`, `neighborhood-final04`, `ordinary-final04`, `headed-final03`, `imports-final02`.
No test was retired and no recovery branch or worktree was created.

## Investigation and regression map

The current service rolls `committing` back only when admission fails;
post-admission preflight refusal remains committed. `run_plan` saves a plan
with its review-preflight verdict even when that verdict is negative; a typed
plan-admission limit instead saves no artifact. Existing preflight tests pin
the exact capacity boundary, fresh-world drift, and refusal without plan or
selection mutation. Existing core/planner tests pin operation identities,
selection digests, and dependency closure. Preserve these behavioral witnesses
when implementing fresh Plan again; a digest is not a filesystem snapshot.

The executor already projects generic I/O reasons and accepts `Stop` after
ordinary failure settlement, but its default policy continues non-sharing
failures. M1-8-capacity is a separate reviewable behavior commit before its
frontend consumer. Verify classification through the real error wrapping path,
post-effect and recording outcomes, and the later-operation stop sweep in the
executor runtime/settlement tests, then core/workflow/interface consumers.
Run the ordinary suite and unchanged retained oracle; final review must reject
any new settlement mechanism or capacity label that masks an unrelated failure.
Update EXECUTOR, FEATURES, DESKTOP_UI, and the register with the implemented
boundary and evidence before `feat(executor): stop on recognized capacity failure`.

For test cleanup, retire only unimplemented UI retry/reopening/cleanup promises
from future acceptance lists. Keep direct-service artifact replacement,
admission rollback, protocol replay, close recovery, automatic operation/read
retry, and pause/resume tests. They protect different behavior. Add terminal
action-availability witnesses when each surface activates, including degraded
completion, abnormal termination, and first manual verification. Add trash
location-only and evidence-backed count cases without requiring a full trash
inventory. Green existing tests cannot prove these new frontend outcomes; red
tests justify removal only when their exact retired product promise is named.

All remaining rows are pending product work. The baseline is the implemented
public/CLI, schema/event, authority, and settlement behavior recorded by the
closed reduction registers; those guarantees remain protected. The future
capacity checkpoint changes only the explicitly accepted failure classification
and later-operation admission policy. No implementation recipe from the discarded
compact-plan branch is an additional prerequisite. Product changes follow the
finite rows above, owning subject docs, and AGENTS/DEFENSE stop rules.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses, and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps the normal review experience with visible issues. Canceled or
abnormally terminated sessions retain terminal truth without resume, domain
retry, or session cleanup. Live pause/resume remains separate. Busy task close
requests immediate best-effort cancellation and keeps the card until settlement
and resource release permit closure; close never implies trash purge. Forced
process exit provides no durable task/resume guarantee.

Capacity refusal before execution (including queued wakeup) retains the task
without execution, automatic retry, or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again, and requires fresh review. It
never copies selection/authorization or changes the old artifact. Disk space
freed by removing source/target entries is accounted for by that fresh scan,
not by assuming that a prior selection digest binds the changed filesystem.

Recognized execution-time disk-capacity failure is the narrow planned addition
above; the current default failure policy continues past non-sharing failures.
Generic I/O already has a typed reason and needs ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence and display placement is
open. No filesystem inventory or purge is added to populate that information.

Location admission is workflow-owned and reused by typed, picker, and recent Setup/inventory inputs. A remembered location is not authorization; every consumer retains its point-of-use re-probe. Setup freezes its semantic plan options in a backend-derived snapshot and never writes global defaults or makes browser text/filter normalization authority.

Plan review must preserve operation, selection, scope, and fresh-preflight truth across view gestures. New views use canonical path-key order; filename, raw size, and raw mtime sorting in either direction and reset to canonical order are accepted M1 behavior. Sorting is process-live view state only and cannot alter selection, commitment, operation/dependency order, risk/counts, or action scope. It orders complete siblings before windowing and preserves node identity/hierarchy. Its exact protocol, validation, and scale evidence belong to BRIDGE and PRESENTATION.

Execution, inventory, and post-copy overlays stay distinct from each other and from ledger-derived state. A zero-byte activity that ran is never presented as unrun. Inventory warnings stay outside path/action scope and publication is complete or retains the prior complete generation. Baseline, verify, and rebaseline remain distinct operations. Rebaseline requires acknowledgement, includes eligible selected null-evidence files, replaces/creates evidence after a fresh hash, clears verification freshness, and does not become compare-and-accept. Manual exact post-copy verification uses an atomic handoff classification, works only on a ready subset, preserves original execution truth, and reports ineligible outcomes truthfully.

Release remains an accepted outcome. [INTERFACES.md](INTERFACES.md#sh-g-release-criteria) owns the open SH-G-15 scoped cold-start and repeated/long-workload resource policy. It has no numeric budget or acceptance artifact yet; runtime request/population bounds and the separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status must describe shipped behavior.
Map every active DESKTOP_UI acceptance item to its subject check or an explicitly
approved deferral; an omitted item or copied unmapped checklist is not closure.
BR-G-44: from a clean checkout, run the complete suite including ordinary-default
exclusions, lint-imports and diff checks. All test_br_g cases must be collected
and pass without skip/xfail on Windows; narrow selections do not substitute for
release evidence. TESTS owns collection commands and routing. These requirements
remain open release obligations, not an assertion that this checkpoint delivery
performed a product release run.

## Resumption

M1-4, M1-async (`675181a`), M1-5 (`e19ed9d`), GUI-1 (`b98dce4`) and M1-6
are delivered on `milestone1`. Pause before M1-7. Its expansion and implementation require a new
user instruction. No halo workaround, push or PR is part of this delivery.
HANDOFF owns current operational context; AGENTS owns containment boundaries.
