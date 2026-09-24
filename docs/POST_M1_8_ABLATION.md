# Post-M1-8 Ablation Study

## Disposition (2026-09-25)

Completed read-only investigation, requested by the user after M1-7 and M1-8
were delivered at high cost. Baseline: clean `milestone1` at `549f3b4`.

This document records findings and proposals only. It authorizes no product,
test, evidence-policy or documentation-ownership change. Each proposal needs an
explicit user decision and, where [AGENTS](../AGENTS.md) requires it, a closed
register in [M1_PLAN](M1_PLAN.md) before implementation. It does not resume the
deferred [M1-7 study](M1_7_ABLATION_STUDY.md); overlaps are noted in §7.

## Question and method

Question: which mechanisms, tests and workflow steps can be removed or merged
while delivering the same user-visible behavior and the same data-safety
invariants? Logical simplification is the goal; line counts are a consequence.

- Outside-in: architecture, behaviors, seams, modules, transactions, then code.
  Nine read-only `claude-sonnet-5` analysts covered disjoint areas (task
  lifecycle/dispatcher, web transport/host, frontend assets, plan-review
  pipeline, core events/history, executor/sync/recorder, scanner through
  inventory, test coupling, measurement/tools) with one classification:
  essential, supporting, defensive-internal, speculative, unintegrated, or
  evidence/process.
- Headline claims were re-verified in code by the orchestrating session; rows
  marked *analyst* were traced by one analyst and not independently re-read.
  Two analyst figures were corrected (the `bridge.js` validator share, and
  per-commit counts that double-counted merge commits).
- Quantitative census from Git, BUGS and the active documents. Experiments ran
  in a disposable local clone of `549f3b4`, with Node v22.18.0 supplied through
  `NAMISYNC_TEST_NODE`. Logs and scripts are retained in ignored
  `build/post-m1-8-ablation-20260925/`.
- Limits: no timing or headed runs, no new product-correctness claim, no
  mutation framework. Line counts are physical lines at `549f3b4` and are
  diagnostics, not promised savings.

## 1. Findings

The filesystem engine (scan, plan, preflight, execute, verify and ledger) mostly
earns its complexity: nearly every executor guard examined maps to a SEVERE
entry in [BUGS](BUGS.md). The avoidable cost comes from three sources:

1. **Orchestration sized for situations the shipped app does not have.** One
   desktop task spans about 28 named types in six owners. The transport recovers
   from page reloads users cannot trigger, and from deadlines the page imposes
   on its own local calls. Interface and dispatcher/history entries are 47% of
   all recorded bugs, and their titles describe the machinery (custody,
   generations, receipts, races) rather than file synchronization.
2. **Re-validation of first-party output at each boundary.** ARCHITECTURE
   invariant 17 ("validate once at adoption") is stated but not practiced. MOVE-1
   (`549f3b4`) is the precedent: a duplicate check with different evidence
   disagreed with the authoritative one and caused the defect.
3. **Mechanisms recorded as contracts.** Documents state mechanisms and even
   pixel values normatively, acceptance evidence hash-binds about 40 source
   files, and a typical product commit edits five documents. Earlier reduction
   passes therefore had to rewrite the documents that prescribed each mechanism
   before removing it, and removed little.

The ordinary tests are healthier than expected: three behavior-preserving
refactors broke no behavioral test (§6). Brittleness is concentrated in
visual/source-literal tests and in the measurement machinery.

## 2. Cost census

| Signal | Measurement at `549f3b4` |
| --- | --- |
| Size | Product: 67.5k Python + 15.2k JS/CSS/HTML. Tests: 182k Python + 16.7k JS (2.7× product Python). Tools: 14k + a 63k-line settlement baseline JSON. Docs: 23k active + 20k obsolete. `build/`: 260 evidence directories, about 11 GB |
| Bug origin (268 BUGS entries) | Interfaces 99 + dispatcher/history 28 = 47%. Scanner, planner, preflight, executor, verifier and database/inventory together 74 = 28% |
| September churn (173 non-merge commits) | Changed lines: docs 48.4k, product 37.7k, tests 71.3k. 49 docs-only commits versus 22 `feat`. Product-touching commits edit 5.2 documents on average (maximum 17) |
| Example | `f6c9471`, a two-line CSS stroke fix, also changed CHANGELOG, DESKTOP_UI, FEATURES, HANDOFF, M1_PLAN and two tests. The `1.2px` value now lives in CSS, a test literal and the feature catalog |
| Documentation register | 211k words in active docs; "exact" 1,108 times, "never" 550 times; about 3,900 code identifiers. "custody" appears in 30 documents, "settlement" in 27, "receipt" in 24 |
| Ordinary suite time | About 4.5 minutes. The slowest tests are the scale/evidence family (about 50 s of the 80 slowest). Maintenance, not runtime, is the cost |

## 3. Behavior-to-mechanism map

| User-visible behavior | What it needs | What exists in addition |
| --- | --- | --- |
| Start a plan or inventory from Setup | Fresh location admission, a task record, session submission, visible state | Three replay layers: JS automatic replay and manual retry, a 48-entry adapter start-response cache, and `TaskLifecycle` receipts with a 64-way command guard. Two-phase asynchronous admission/completion with separate acknowledgments. Shell, start, admission and association claims. Two independent admission-cleanup implementations (dispatcher and lifecycle) |
| Review a 120,000-row plan | Workflow projection and window, dependency-closed selection, revision guard | `NodeTree` rebuilt on every folder gesture because layering keeps the service from the adapter's projection. Full dependency derivation four times per gesture, two unused. A full O(operations) preview built and discarded on each view open. A second round-trip re-reading membership already returned (*analyst*) |
| Execute with pause/resume/cancel | Commitment digest, preflight, executor guards, progress, control flags | Execution-authority snapshot/revalidate/audit calls at 38 sites in `workflows/sync.py`. Progress attempt semantics enforced in Python and again by a JS reducer. Three envelope encoders/validators |
| Close a task | Cancel when busy, release resources, remove the card | Four-phase settlement claims, a 48-entry close-response cache, and a six-step teardown chain whose steps must each tolerate repetition |
| Survive page reload | Nothing: production launches pywebview with `debug=False` (`interfaces/web/bridge.py:602-611`), and pinned pywebview 6.2.1 sets `AreBrowserAcceleratorKeysEnabled` and `AreDefaultContextMenusEnabled` from that flag (`webview/platforms/edgechromium.py:287-288`). Product code never navigates or reloads | Three independent document generations advanced by one `before_load` event (`interfaces/web/host.py:877-934`), native-return containment, reinjection cursor recovery and "Retry updates". Only tests reload the page (46 occurrences in 11 files) |

## 4. Structural proposals

Ordered by recommended sequence in §12, not by size.

**S1 — Declare reload unsupported and collapse generation machinery.**
First verify on an installed build that F5, Ctrl+R, Alt+Left, mouse Back and the
context menu cannot reload. Then keep one startup handshake and fail closed on
any second document load with a "restart NamiSync" message. Removes the three
generation owners, native-return containment, drain/browser reinjection recovery
and most reload scenarios in headed harnesses. Loses in-place recovery from a
renderer crash, which the host does not implement today. Risk: low once the
manual check passes.

**S2 — Remove self-inflicted command uncertainty.** The page applies 5 s and
30 s deadlines to in-process calls (`assets/bridge.js:55-108`). A deadline turns
a call into "uncertain", which drives automatic replay (`createTask`,
`submitStart`, `startExecution`), the delayed `closeTask` retry loop, the
manual-retry UI and attempt machines in `app.js` (*analyst*), the server replay
caches and the asynchronous completion channel. The M1-async design was framed
around reload survival and a 30 s browser deadline over a 25 s server close
wait. Alternative: commands return right after admission, long waits (close
settlement) become task state reported through the existing drain, and the page
shows a working state instead of timing out. Keep one `command_id` check at the
task owner against double submission. Loses automatic retry of a genuinely hung
handler; show "still working" instead. Risk: medium; after S1.

**S3 — Render server snapshots instead of reducing events in the browser.** The
Python drain already replaces pending Progress in place, and the server already
builds execution overlays; the page reduces the same stream again with Gap,
attempt and high-water rules (about 750 lines, *analyst*). Deliver a per-task
snapshot (state, latest progress, counts, revision) plus bounded outcomes, and
keep Python as the single reducer. The frontend analyst classified the reducer
as essential against a lossy transport; this study disagrees because that
lossiness is a server design choice, not a platform property. Loses an
independent second protocol implementation. Risk: medium-high (protocol change;
`drain_manager_probe.mjs` and related tests retire with it).

**S4 — Validate at ingress and trust first-party output.** Keep strict bounds on
page-to-Python requests and on reads of externally corruptible storage, and keep
the history receipt/prefix hash chain for torn writes. Stop re-validating values
the same process just produced:

- `core/events.py:630-634` reruns the full `event_v5` validator on history
  readback of bytes written and validated by the same process;
- the history schema carries 71 `CHECK` clauses and 10 triggers restating
  groupings that Python enforces before insert;
- `assets/bridge.js` spends 75 functions and 1,175 of 3,501 lines on response
  validation (the frontend analyst's region estimate of about 1,750 includes
  neighboring helpers);
- `interfaces/web/bridge.py` walks each response tree three times (*analyst*);
- `workflows/sync.py` calls execution-authority snapshot/revalidate/audit at 38
  sites.

Keep the collaborator-callback audit that BUGS records catching a real incident.
Move second-implementation oracles into tests, where own-code defects belong.
Risk: low to medium per item; the lowest-risk structural proposal.

**S5 — One owner per task.** `interfaces/task_lifecycle.py:32-166` defines 16
dataclasses implementing begin/complete/abandon protocols for plan mutation,
plan retirement and admission rollback, plus a four-phase settlement: a
hand-built transaction manager for one user's tasks. Merge lifecycle claims,
drain task state and the retained-review registry into one per-task record under
one lock. Keep dispatcher custody (the cross-process volume mutex is real,
because CLI and GUI may mutate concurrently; worker generations serve
pause/resume overlap) and the observer's thread lifetime separate. Unify the two
admission-cleanup implementations. Consider one workflow-owned plan-review
object shared by service and adapter. Risk: highest; after S1 and S2, which
remove many of the claims' reasons to exist.

## 5. Local reductions

Each item is independently committable and preserves behavior.

| ID | Change | Where | Evidence |
| --- | --- | --- | --- |
| L1 | Delete the unused mapping lookup (`find_mapping`, `get_mapping_snapshot`, `_disqualified_identities`, about 110 lines); it still embeds the stale-alias pattern MOVE-1 removed from planning | `db/repositories.py:1022-1120`, `:1259` | Verified: no production caller |
| L2 | Derive `toggleable` only when a folder id needs resolution (the M1-7 study's R7-7, marked "deliver now", never landed) | `interfaces/service.py:2499-2503` | Experiment B1: no failure |
| L3 | Summary-only selection preview on view open; drop the redundant membership round-trip | `service.py`, `web/drain.py` | *Analyst* |
| L4 | Encode each bridge response in one pass | `web/bridge.py` | *Analyst* |
| L5 | Merge `PlanReviewProducerAdmission` and `PlanReviewAdmission`; keep all four axes | `core/review.py` | *Analyst*: identical `_limit_signal` bodies |
| L6 | One owner each for the `required_volumes` check (three sites) and `Verdict.ok` (two) | `core/planning.py`, `modules/planner.py`, `modules/preflight.py` | *Analyst* |
| L7 | Remove default-off copy diagnostics from the copy path | `modules/executor/pipeline.py` | *Analyst*: never reaches users |
| L8 | Merge three byte-continuation classes; express about 50 internal state-enum members as a few orthogonal facts (users see 22 reasons and six outcomes) | `modules/executor/runtime.py:242-458` | *Analyst*; needs one settlement-baseline refresh |
| L9 | Replace the native Advanced Color detection (about 150 lines and appearance v3) with CSS `dynamic-range`/`color-gamut` queries | `web/appearance.py` | Needs a spike showing WebView2 tracks the Windows toggle |

Lower-value options: the `StoredSessionRecord`/`SessionRecord` split exists for
M2; `workflows/_database_pair_native.py` (317 lines) serves only first-run
failure cleanup.

## 6. Tests

### Experiments

All runs used the same clone environment and the ordinary default selection
(33 headed tests deselected).

| Run | Change | Result |
| --- | --- | --- |
| Baseline | Clean `549f3b4` | 5,403 passed, 5 skipped, 14 failed. All 14 are environmental: 12 `test_tools_gui.py` cases expect a `.venv` inside the checkout, and 2 `test_plan_review_scale.py` cases invoke bare `node` rather than `NAMISYNC_TEST_NODE` |
| A | One trailing comment in 12 product files (Python, JS, CSS) | Pass and failure sets identical to baseline |
| B1 | Lazy `toggleable` derivation (L2) | No new failure |
| B2 | One shared dispatch helper for the four plan-view mutation wrappers in `bridge.js` | No new failure |
| B3 | Combobox stroke as `var(--nami-combobox-trigger-stroke-width, 1.2px)` (identical computed style) | Two new failures in `test_design_tokens.py`: a literal pin on `border: 1.2px solid …`, and the raw-color scanner (`_has_raw_color` is false before, true after): a lexical false positive |

B1–B3 ran together (5,401 passed, 16 failed); both new failures belong to B3 by
their assertions. Of 17 sampled private product names, 15 have no test
reference. A comment breaks no ordinary test, but the plan-review and
execution-UI authority artifacts hash-bind 38–43 product files each (including
`dispatcher.py`, `service.py` and `core/session.py`), so under current evidence
policy the same comment stales their recorded acceptance. That coupling is
procedural, not test-level.

### Recommendations

- **T1 — Remove visual and source-literal pins.** The most-churned test files
  since 2026-09-01 are this family (*analyst*): `test_frontend_static.py` in 26
  commits, in step with `app.css`'s 26; `test_component_gallery_headed.py` 24;
  `task_shell_probe.mjs` 23; `test_design_tokens.py` 18. Remove exact CSS
  declaration asserts, the 16 source occurrence counts in
  `test_frontend_static.py`, and the 58-literal gallery exact-matrix test. Keep
  security bans (no `innerHTML`, `evaluate_js` or `localStorage`) and a few
  computed-style checks for accessibility invariants such as focus visibility
  and forced colors.
- **T2 — Retire tests with their mechanisms.** S1–S5 shrink
  `test_task_lifecycle.py`, `test_drain.py`, the transport-custody tests, the
  drain and task-shell JavaScript probes and the reload scenarios of headed
  children. An intentionally retired mechanism needs no one-to-one replacement
  detector.
- **T3 — Stop procedure-driven test reduction.** The previous refinement closed
  at a diagnostic net +27 lines ([TEST_REFINEMENT](TEST_REFINEMENT.md)).
  Approximate corpus shares (*analyst*): 15% headed harness (about 20% of the
  tests in those files need a desktop), 9% scale evidence, 8.5% tests of tools
  and evidence protocols.

Keep the executor settlement tests and 30-scenario in-code oracle, the
`FailureDetail` construction AST guard, integrity-selection duplicate/unknown-id
rejection, and the security bans.

## 7. Measurement and evidence

- Families (*analyst*): plan-review scale 7.4k lines + 1.3 MB JSON; M1-8
  execution UI/receipt about 3.4k + 0.75 MB; bridge event benchmark 3.5k;
  transport custody 4.3k + 0.15 MB; settlement oracle 8.6k + a 63k-line baseline
  + 2.6k tests; headed children about 10k.
- An estimated 20–30% certifies the evidence itself: readiness passes, partial
  collection indexes, legacy-family replay and per-family authority/identity
  records.
- Root cause is policy. [DEFENSE §7](DEFENSE.md#7-quantitative-evidence-and-measurement-authority)
  applies Tier 2/3 procedure to UI latency and states that an unclassified
  retained-representation change invalidates acceptance evidence, so a
  plan-review dataclass edit re-arms a 78–175-child measurement.

**E1 — Proposal.** Keep counted-work witnesses (such as the 120,000-row scoped
and highlighted selection costs) as ordinary regression tests. Move wall-clock
timing into one manual script with plain JSON output, run before release.
Retire readiness, partial indexes, legacy replay, the optional Plan-again tracer
and per-family authority binding. This extends the M1-7 study's Option A in
place of its Option B redesign. Decide whether all 35 + 13 budgets are needed
(Option C). The settlement baseline has not changed since 2026-08-22 and is low
priority.

## 8. Development workflow and documentation

Documents currently prescribe mechanisms: FEATURES carries pixel values and
mechanism names, PRESENTATION prescribes evidence mechanisms, and AGENTS adds
closed registers, finite populations, regression studies, recurrence stops,
recovery branches, evidence retention and multi-document updates per commit.
Each mechanism therefore has three to five normative restatements to
renegotiate before it can change.

- **W1 — Separate contract from description.** FEATURES states user-observable
  behavior; DEFENSE states safety invariants; ARCHITECTURE states cross-layer
  invariants; module documents describe current mechanisms without binding
  them. A behavior-preserving mechanism change then needs no document approval.
- **W2 — Scale process to the change.** A small fix is a commit plus one
  CHANGELOG line. Registers only for multi-commit work; HANDOFF only when pausing
  mid-task; one retained log per gate.
- **W3 — Archive completed studies.** Move TEST_ABLATION, TEST_REFINEMENT,
  PRODUCTION_REDUCTION, REDUCTION_FOLLOWUP and M1_7_ABLATION_STUDY (about 3.1k
  lines) to `obsolete/`; they still constrain future work.
- **W4 — Reduce AGENTS** to layering, safety invariants and commit conventions.

## 9. Retain

These look reducible but protect real behavior:

- Executor final-touch guards, recorder flush before destructive guards,
  publication observation and `canceled-after-publish`/`canceled-after-mutation`,
  UPDATE `live_stat` retention across retries and trash parent-chain
  revalidation; each maps to a SEVERE BUGS entry.
- Preflight's distinct root, subject, temporary and trash probes, and the
  scanner's before/after root bracket.
- The cross-process volume mutex and worker-generation custody.
- The history receipt/prefix hash chain, and `Scalar64`/`FileIndex128`
  handling.
- The complete-request bound and command allowlist, CSP, navigation blocking and
  the filesystem-label layout-control sink.
- Two SQLite files, and the four plan-review admission axes (dependency fan-out
  is not proportional to rows).

## 10. Feature classification

| Class | Items |
| --- | --- |
| Features to keep (simplify their mechanisms) | Plan review with search, filters, sort, selection and highlight ranges; commit-bound execution; pause/resume/cancel; live and retained execution review; Plan again; serial batch pair creation; recent locations; CLI integrity baseline/verify/rebaseline; history CLI; concurrent tasks on disjoint volumes |
| Implemented, not yet integrated (expected) | `tree.js`, `integrity.js`, gallery-only chip/badge/banner CSS, inventory acknowledge/restore (no CLI or desktop surface), desktop inventory projection contracts |
| Speculative (M2 or later) | `SessionStore` record split, destination-policy seam for ingest, recorder `flush()` batching seam, copy-pipeline metrics |
| Dead | The mapping lookup in `db/repositories.py` (L1) |
| Reachable only by tests | Page reload and reinjection recovery (S1) |

## 11. Decisions required

| ID | Question |
| --- | --- |
| D1 | Is page reload a supported user action? If not, S1 proceeds and most of S2 follows. |
| D2 | May local commands drop page-side deadlines (S2)? |
| D3 | Which of the 35 plan-review and 13 execution-UI budgets matter? |
| D4 | Is a highlight set separate from checkbox selection worth its machinery? |
| D5 | Keep the native Advanced Color shadow mitigation, or use CSS only (L9)? |
| D6 | Wire or shelve inventory acknowledge/restore? |
| D7 | Change DEFENSE §7 and document ownership (§7–8)? Without it, S1–S5 cost about what M1-7 and M1-8 cost. |

## 12. Suggested order

1. W1–W3 and E1: no product risk; they make the remaining work cheaper.
2. L1–L9 and T1.
3. S4, then S1, S2 and S3, then S5.

## Evidence

`build/post-m1-8-ablation-20260925/` (ignored) retains `run-base.log`,
`run-A.log`, `run-B.log`, the earlier Node-less `run-no-node-durations.log`
(durations source), and `scripts/` with the census and experiment scripts:
`sizes.ps1`, `churn.ps1`, `doctax2.ps1` (merges excluded), `bugs.ps1`,
`docpin.ps1`, `refs.ps1`, `prepA.ps1`, `prepB.ps1` and `run3.ps1`. The disposable
clone and its worktrees were deleted after the runs.
