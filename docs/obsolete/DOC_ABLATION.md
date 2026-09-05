> Historical study and completed migration record. Current subject contracts are in BRIDGE, PRESENTATION, INTERFACES and M1_PLAN in the parent directory.

# Documentation Ablation Study

Baseline: `cab2259a622014637c0611b2575a6b09be74b8e5`, 2026-09-05.
Diagnostic study, not authorization to remove product requirements or change
code. Existing untracked `docs/TEST_ABLATION.md` belongs to separate work and
is excluded from edits. This file owns the study register and findings;
The original study preserves existing authority; the dated resource-policy follow-up below records the subsequently authorized change.

## Closed study register

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DA-1 | Map active documentation ownership and the four M1 plan dependencies | Census root README/AGENTS/CHANGELOG and tracked active docs; section map of four plans; inspect standing and incoming references | Complete |
| DA-2 | Evaluate six finite documentation ablations | For each cohort, name removed material, retained answer locations, lost information, and counterexample; distinguish editorial changes from policy decisions | Complete |
| DA-3 | Recommend a minimal documentation structure and expose design decisions for discussion | Trace candidate destinations and residual dependencies; adversarial review of combined losses; verify task-owned diff | Complete |

Corpus: tracked root README.md, AGENTS.md, CHANGELOG.md and direct docs/*.md.
Archived docs are reference targets and provenance, not a second full audit.
Code/tests/tools are read-only corroboration for selected claims, not an audit
of implementation correctness. Counts are diagnostic, not acceptance thresholds.

Six cohorts: repeated delivery status; completed/superseded plan material;
bridge decision/protocol/gate mixing; exact contract duplication; prospective
task/resource machinery; historical prohibitions and audit ritual.

Method: counterfactual removal and finite lookup witnesses, not deleting live
documents and calling a successful link check proof of semantic equivalence.
Record specific losses and unanswered questions. No production/test changes,
permanent document deletion, bulk rewriting, or new policy enforcement.
Repository stop rules apply. Findings do not enlarge this register.

## Finding and census

The main removable burden is overlapping authority across time. Historical
execution instructions remain beside current contracts and future mechanism
specifications. Readers must apply supersession rules to interpret local prose.
Splitting files alone preserves this burden; deleting all plans loses unique
wire contracts, pending requirements, and evidence qualifications.

| File | Lines | Disk bytes | Actual responsibilities |
| --- | ---: | ---: | --- |
| M1_PLAN.md | 1,719 | 105,821 | Decision history, completed stages, pending scope, integration gates, precedence |
| M1_BRIDGE.md | 5,073 | 349,973 | Active/future protocol, rationale, concurrency design, gates, evidence |
| M1_SHELL.md | 1,343 | 82,723 | Host/package decisions, old/current sequencing, SH-G contracts, evidence |
| M1_SHELL_H2.md | 857 | 81,833 | Completed/retired checkpoints, pending requirements, execution rules, review history |

The four files total 8,992 lines / 620,350 bytes. The census contains three root
files and 28 tracked direct docs files; the latter total 1,656,822 bytes. The
plans account for about 37% of those bytes. These are diagnostics, not token
estimates or achievable deletion forecasts. FEATURES alone is 97,280 bytes in
550 lines; long bullets make line counts particularly weak.

Incoming-reference search across the other direct docs found 107 matching lines
in 21 files. CORE, EXECUTOR, RECORDER, HISTORY, DATABASE, WORKFLOWS and COMMANDLINE
refer into the bridge for domain event/result vocabulary. This is an authority
hub, not simply a large navigation index.

Procedure: git ls-files over the three root files and docs/*.md, excluding
obsolete; PowerShell line/byte inventory; heading extraction for the four plans;
rg for the four filenames across direct docs, excluding the four plans and both
study files. Inspect standing/ownership clauses and the selected bodies below.
This is a structural census and selected semantic study, not a sentence-by-
sentence correctness audit of all 31 documents. Line references below use the
baseline checkout. Archived files were inspected only as reference targets.

## Six counterfactual ablations

Each removes only the named cohort from active lookup. A surviving answer must
contain the relevant rule, not link back to removed material. Required extraction
is a condition, never credited as an already surviving answer. No live document
was removed, and no lookup-speed improvement was measured.

### A1. Repeated build and evidence recaps

Remove historical measurement/build recaps from PLAN lines 9-44, SHELL's opening
status, and DESKTOP_UI lines 3-40. Keep local active/unrealized applicability,
dated outcomes in CHANGELOG, and exact acceptance scope at the evidence owner.

- Witness: does SH-G-8 prove complete runtime containment? Bridge BR-G-42 and
  shell SH-G-15 independently delimit that claim. Visual rules do not need the
  calibration byte figures to answer visual questions.
- Loss: introductions stop being standalone build reports; historical results
  require the evidence link. No product obligation needs removal.
- Counterexample: deleting all status prose makes dormant surfaces appear active.
- Verdict: editorial removal is justified, with a clause inventory before edits.
  Entire introductions are not disposable.

### A2. Completed/superseded execution instructions

Remove completed-stage instructions and resolved review narratives from active
PLAN sections 3/5/6 and H2 checkpoints 0-3R/4P plus its checkpoint-0 audit record.
Archive the closed SIMPLIFICATION delivery record while preserving provenance.

- Witness: what can start next? H2 checkpoint 4 requires a new finite register;
  5-12 are pending. SIMPLIFICATION's resumption block says active row and next
  action are none. Completed instructions add no next-step authority.
- Loss: wholesale PLAN archival loses section 4's deferrals unless their current
  disposition is retained. SHELL section 1 owns host/toolchain/package choices.
  H2 checkpoints 7/9/10 retain accepted sorting/rebaseline detail.
- Counterexample: EXECUTOR and TOOLS still refer to delivery material for scenario
  provenance. Age does not retire protected settlement evidence.
- Verdict: archive completed history after extracting unique live obligations.
  Reject wholesale deletion and automatic expiration of old gates.

### A3. Bridge decision/protocol/gate layering

Remove the need to consult a DR-BR narrative, shared exact register, and BR-G
paragraph for one rule. Place each rule once by subject, keep short rationale
beside it, and link its evidence. Preserve referenced identifiers as provenance.

- Witness: what keys does a task response contain? The shared result-shape section
  answers keys, but its status notice makes most task shapes prospective. The
  decision map alone does not give a current schema.
- Witness: why test unaffected inventory siblings? BR-G-5/6 explains how counts
  and wildcard-matched successes can pass while unrelated rows change.
- Loss: wholesale gate removal loses unique counterexamples and BR-G-42's exact
  evidence scope. Keep those rather than retaining three owners for one rule.
- Counterexample: BR-G-3 requires relocation-only history and an unmodified
  planner test. That is a migration proof, not enduring path semantics.
  tests/test_bridge_tree.py:323 still checks promoted-helper identity. Its
  retirement belongs to the separate test study, not this docs study.
- Verdict: organize by subject and applicability, not decision chronology.

### A4. Exact internal shape duplication

Remove duplicated implemented Python field/enum inventories; retain meaning and
link canonical source. Do not apply this to external wire grammar or future types.

- Witness: ARCHITECTURE section 3.1 already makes core source canonical for exact
  fields. TerminalSummary is in namisync/core/events.py:359; Commitment is in
  namisync/core/execution.py:115. A bridge plan need not own those Python shapes.
- Loss: code alone does not explain public JSON decimal strings, absent versus
  null, compatibility, or refusal precedence. Preserve the protocol contract.
- Counterexample: source cannot replace a future TaskSummary that has no active
  implementation. Its binding design status requires a decision.
- Verdict: consistently distinguish internal shape, external encoding and meaning.

### A5. Prospective task/resource machinery

Remove already-retired aggregate reservation prescriptions from active prose;
separately reopen still-accepted future mechanisms under the user decision below.

- Witness: must the next implementation reserve a complete owner graph? DEFENSE
  section 1.3, H2 checkpoint 4 and BR-G-45 explicitly retire that requirement.
  Yet bridge lines 929-942 prescribe replacement/diagnostic charging, 986-995
  prescribe precharged leases/response capacity, and 1060-1099 describe an
  enforced byte budget and analytical maximum task. These local imperatives
  require applying the earlier retirement notice before they can be interpreted.
- Drift: CORE lines 10-11 calls the complete reservation model accepted but
  unrealized. BUGS lines 1394-1404 refers to the accepted complete task/artifact
  graph. Those references cannot restore retired authority.
- Loss: removing retired byte/graph requirements loses no active guarantee.
  Removing all nearby lifecycle rules loses useful obligations: retry identity,
  stale-session isolation, closability at capacity, truthful publication, and
  retention of reviewed results.
- Counterexample: independent 120,000-row admission is active in core models,
  integrity, review and DEFENSE. Retiring aggregate bytes does not retire rows.
- Verdict: move retired machinery out of active prose, retaining one short
  disposition and archive pointer. Redesign mechanisms against retained outcomes.
  This study establishes no runtime simplification or safety result.

### A6. Repeated process rules and historical prohibitions

Remove generic execution rules repeated in H2 lines 112-171 in favor of AGENTS
and TESTS. Keep unique activation/evidence conditions. Treat SH-G-15 separately.

- Witness: AGENTS Task Containment/Testing and TESTS Accepted-target verification
  already specify finite registers, stop routing, departments, ordinary/headed
  scope and evidence authority. H2 also says BR-G prose alone is no extra gate.
- Loss: H2's atomic activation rule and named non-skippable evidence still need
  an owner; not every sentence is duplicated procedure.
- Witness: does a changed runtime tuple inherit SH-G-15 acceptance? SHELL lines
  1160-1198 says no and requires reaffirmation or recalibration. DEFENSE section 7
  explains evidence tiers but does not substitute for that release-policy choice.
- Counterexample: deleting that condition changes release policy. Likewise,
  AGENTS specifically requires repeated settlement-oracle stability runs;
  they cannot be removed as generic ritual.
- Verdict: remove repeated procedure. Discuss release-policy changes explicitly.

## Proposed ownership after migration

These are proposed conventions, not activated edits. Amend AGENTS and ownership
sections before migration. Extract unique obligations once; do not keep synopsis
copies in every former owner.

| Subject | Proposed single active home | Treatment |
| --- | --- | --- |
| Active/accepted user behavior | FEATURES | Keep outcomes/status; remove build recaps and mechanism recipes |
| Cross-layer meaning and source locator | ARCHITECTURE | Extract unique rationale; source owns implemented internal shape |
| Supported boundaries, active walls, evidence policy | DEFENSE | Other docs link directly |
| Wire commands, encoding, transport/retry semantics | BRIDGE.md, renamed/reduced from M1_BRIDGE | Current protocol separated from future outcomes |
| Host/startup/package and adapter mechanisms | INTERFACES | Extract unique SHELL section 1 rules; visuals stay in DESKTOP_UI |
| Remaining order and named verification | Rewritten M1_PLAN | Sole delivery register; archive old body and completed SHELL/H2 history |
| Exact fixtures, artifacts, rerun scope | Owning bridge/interface/component section | Keep evidence-qualified references, not duplicate build summaries |
| Completed outcomes and rationale provenance | CHANGELOG and obsolete | No historical next-step instructions presented as current |

A work item links directly to its subject contract and named checks. It does not
require a parent/child/grandchild plan chain to reconstruct precedence. Shared
DEFENSE and ARCHITECTURE dependencies remain legitimate; this does not promise
one-file understanding of every task.

Do not create a document per decision, a global authority database, or generated
copies. If the reduced bridge still has independently maintained protocol and
presentation subjects, split only then. A word-count target would reward moving
text rather than removing obligations or duplication.

## Design dispositions

1. **Ratified by the user in this study:** preserve accepted outcomes and reopen
   unrealized mechanisms when implementation begins. Active code contracts are
   unchanged. Future DTOs, lease/reservation designs and exact command expansion
   recipes need not dictate their eventual implementation. H2 checkpoint 6's
   prescribed 18-command table partly derives from retired checkpoint 4; replace
   that recipe only after the retained outcomes are mapped. Retry, close,
   staleness and concurrency consequences still need explicit solutions.
2. **Ratified by the user, 2026-09-06:** SH-G-15 becomes scoped cold-start
   resource-budget and repeated/long-workload leak/growth acceptance. Existing
   runtime-enforced request/population bounds remain independent obligations.
   DEFENSE section 7 and the shell gate now implement this policy; numeric
   budgets and acceptance artifacts remain future work, so the gate stays open.
   Early extraction of live contracts from the M1 plans is also accepted.
3. **Proposed:** completed relocation/diff-shape proofs become historical evidence;
   enduring behavioral counterexamples remain. Protected evidence with explicit
   ongoing obligations remains active. No test or oracle deletion is authorized.

## Combined adversarial review and terminal observation

Assume each removed paragraph was the last owner of an obligation. Blanket plan
archival fails that test: pending sorting/rebaseline, packaging, deferrals and
evidence would be lost. Blanket gate removal loses counterexamples. Source-only
docs lose wire meaning and future intent. Retiring every resource number loses
active ingress/population bounds. The conditional migration above instead extracts
unique obligations once and distinguishes policy changes from editorial removal.
This review was performed by the same agent in a separate reviewer pass.

The finite study closes with six cohort dispositions and their explicit losses;
it does not claim full-doc equivalence, measured lookup improvement, implementation
correctness or runtime safety improvement. No production tests were needed or run.
At the original study close, production, tests and authoritative contracts were
unchanged. The dated follow-up below subsequently revises release policy only.
Plan-file migration remains separate work. After disposition, archive this study
rather than turning it into another permanent authority.

## Resource-policy follow-up register (2026-09-06)

User decision: early extraction of live contracts from the M1 plans is acceptable;
SH-G-15 becomes scoped resource and leak/growth acceptance. Cold-start budgets
and repeated/long-workload checks remain mandatory. Existing runtime request and
population bounds remain active. This follow-up changes documentation policy,
not code, test authorities, numeric budgets, or milestone1 branch history.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DA-R1 | Ratify scoped SH-G-15, reconcile active references, and record milestone1 memory-work provenance | Read last 45 milestone1 commit subjects, four branch-only commit summaries and compact-plan register diffs; inspect affected policy bodies; search direct docs/README for obsolete SH-G-15 claims; review documentation-only diff | Complete |

Finite edit domain: SH-G-15 definition, DEFENSE claim classification, direct
active documentation references to that gate, this study and delivery metadata.
Non-goals: plan-file migration, code optimization, removing active bounds, retiring
SH-G-8/oracle authority, or designing/running the future resource harness. The
study's original closed register is unchanged. Repository stop rules apply.

### milestone1 provenance and consequence

Read branch tip `9ec12776f9131b7819977bf96a8bc9c0ce8951b3` without checkout,
merge, or changes to that branch. The four commits unique to it relative to the
current branch are `dc11972`, `9ec27e6`, `8d8c798`, and `9ec1277`: register,
semantic baseline, and corrections. Their diffs change docs/tests, not production.
MEM-02 through MEM-05 remain pending in that branch's handoff; packed scans,
ordinal execution overlays, and packed projections were proposed, not delivered.

The direct prerequisite was BR-G-45's compact-plan model: 128 MiB, a mandatory
15% reserve (114,085,068-byte charge ceiling), an exact 15,360,000-byte text
profile, and 18 construction high-water rows. This is distinct from SH-G-15's
whole-runtime gate. Weakening SH-G-15 alone would not have removed that blocker.
The current branch already retired the complete-graph model; do not import
milestone1's MEM register or stale continuation instructions to reactivate it.

Earlier landed examples have separately intelligible benefits: `93c5000` changes
integrity reconciliation to incremental settlement with runner-return auditing;
`035e5ba` reuses admitted membership instead of rebuilding/scanning it repeatedly;
`e48c7e4` folds validated paths once; `524247c` slots planning records. Read their
commit summaries, relevant diffs, and documentation, not merely the titles when
assessing the mechanism. This is evidence of their changes, not a fresh benchmark
or a proof that every implementation choice should be retained. No revert is
warranted solely by the changed motivation.

DA-R1 verification: revised gate retains cold-start peak/settled budgets,
repeated/long-workload retained-growth/trend criteria, separate resource axes,
profile provenance and incomplete-evidence refusal. DEFENSE permits scoped
Tier-2 acceptance against independently predeclared budgets, retaining Tier-3
conditions for derived ceilings or failed/invalidated acceptance authority.
Relevant runtime changes rerun affected checks; they do not automatically invent
new budgets. SH-G-8 and settlement authority are unchanged. Direct active-doc
reference search and documentation diff checks pass; no runtime tests were run.
No resource measurement or actual gate pass is claimed.

The file migration can now proceed before M1 completes: preserve each unique
live contract or accepted outcome once, archive completed delivery narrative,
and reopen future mechanisms under the ratified decision. The subject ownership
map above is the migration direction; a finite extraction inventory still needs
to precede moves. The completed study and this follow-up are not another durable
contract layer.

## Documentation migration register (2026-09-06)

Authorized: apply all remaining study ablations, keep retired/completed source
material in obsolete, split bridge responsibilities, and archive SIMPLIFICATION
as M1_SIMPLIFICATION.md. Prior uncommitted study/policy edits belong to this task;
TEST_ABLATION.md is excluded. Base remains cab2259; migration archives snapshot
the current working documents, including the already-ratified SH-G-15 revision.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| DM-1 | Preserve historical sources and establish single subject ownership | Non-overwriting archives of four plans and simplification; source hash receipt; AGENTS conventions precede edits | Complete |
| DM-2 | Extract bridge/presentation contracts and remove retired/future mechanism prescriptions | Full source heading disposition; retained wire/behavior/evidence witnesses; independent review against archive | Complete |
| DM-3 | Replace plan ancestry with remaining outcomes and retain host/lifecycle/release contracts | PLAN/SHELL/H2 section disposition; remaining feature and SH-G coverage; independent review | Complete |
| DM-4 | Remove duplicated recaps/shapes/procedure and reconcile direct references | Direct docs corpus sweep; no active retired aggregate authority; link/anchor checks against baseline; documentation-only diff | Complete |

Non-goals: production/test/tool changes; new numeric budgets; deleting protected
oracle or SH-G-8 authority; weakening active admission or supported safety;
reopening user outcomes; changing the separate test study. No new requirement is
created from a discovered finding. Repository stop rules apply. Counts are
observations, not deletion targets. Archive banners distinguish history from
current policy; historical links resolve to their original peer archive where
present and otherwise to the active subject. No redirect-only active plan stubs.

Ownership: BRIDGE owns external protocol/transport/retry and its exact evidence;
PRESENTATION owns trees, views, search/sort/selection presentation and focused
scale evidence; INTERFACES owns host/package and implemented lifecycle; M1_PLAN
owns remaining outcomes/order/named verification. FEATURES owns product outcomes,
ARCHITECTURE cross-layer meaning/source locators, DEFENSE boundaries and evidence
policy. Exact implemented internal shapes remain source-owned. Source sections
may be grouped in the disposition ledger when their treatment is identical.

## Completed migration disposition

| Source family | Disposition |
| --- | --- |
| M1_BRIDGE goals, deferred/resolved choices and delivery lanes | FEATURES/DESKTOP_UI outcomes; M1_PLAN remaining work; completed chronology and rejected recipes archived |
| Shared register epochs/scalars/implemented results | BRIDGE external encoding; CORE/ARCHITECTURE source locators; future exact DTO catalogs archived |
| Shared register task ordering, future commands, location/handoff | INTERFACES and component behavior retained; M1_PLAN outcomes; future lease/reservation/command-count recipes reopened |
| Bridge section 1 facade/selection/location | Existing INTERFACES, CORE, WORKFLOWS, INVENTORY and VERIFIER contracts retained; decision chronology archived |
| Bridge section 2 compute ownership | ARCHITECTURE/WORKFLOWS and PRESENTATION |
| Bridge sections 3–4 trees/paging/live state | PRESENTATION views/search/sort/selection; BRIDGE progress/drain; HISTORY database paging |
| Bridge sections 5–7 lifecycle/concurrency/posture | INTERFACES host/service; BRIDGE admission, recovery, current command/error/envelope contracts and cosmetics |
| Bridge section 8 verification and gates | Subject-owned witnesses; BR-G-42 focused criteria in BRIDGE/PRESENTATION/HISTORY; BR-G-43/44 in M1_PLAN; BR-G-45 retired |
| M1_PLAN stages/appendices | Snapshot archived; active document replaced by remaining accepted outcomes and release closure |
| M1_SHELL host/package/SH-G | INTERFACES host and gates; BRIDGE protocol/evidence; DESKTOP_UI visuals; chronology archived |
| M1_SHELL_H2 checkpoints/recording gate | M1_PLAN remaining rows; component behavior retained; historical protected recording catalog archived and linked from TOOLS/EXECUTOR |
| SIMPLIFICATION | Complete delivery record archived as M1_SIMPLIFICATION |
| Component recaps/shapes and stale model prescriptions | Removed duplicates; two retired acceptance-target ledger entries archived in obsolete/BUGS |

DM-1: archives were created before extraction without overwriting historical
files; original source SHA-256 receipts are in their banners. Archive adaptations
are banners and relative-link relocation. Ownership conventions preceded edits.
DM-2/3: independent Terra reviews compared current contracts with source plans.
Corrections preserved exact command/error/envelope/readiness contracts, handler
lifetime, byte-admitted drain prefixes, progress reducer relations, the 256-row
helper contract, focused scale criteria, SH-G evidence and release completeness.
Future cache/pinning/patch recipes reopened; live-reader coherence remains required.
DM-4: direct active-reference and retired-model sweep, relative Markdown link/
anchor checks and diff integrity checks. Review also corrected accidental text
formatting damage. Production, tests, tools and protected artifacts are unchanged.
No runtime tests or resource measurements were run; no product gate was closed.
The separate pre-existing TEST_ABLATION.md remains untouched and excluded.

This completed report is historical. It is not another active contract layer.
