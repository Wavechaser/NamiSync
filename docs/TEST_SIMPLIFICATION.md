# M1 Test Simplification

Accepted implementation plan, opened 2026-09-04. This is a subtractive delivery
register, not a new permanent test-policy authority. `AGENTS.md`, `DEFENSE.md`,
and `TESTS.md` govern containment, supported guarantees, evidence, and execution.

## Main objectives

- Reduce independently maintained test policy, fixtures, scenarios, and
  implementation assumptions while preserving effective failure detection.
- Permit retaining, rewriting, merging, deleting, or deferring tests, including
  individual parameter rows. Lower test counts and source mass are diagnostics,
  never coverage evidence or deletion quotas.
- Preserve supported failures, meaningful interactions, boundary violations,
  and distinguishing regression triggers. Keep production behavior unchanged.
- Conditionally replace the procedural settlement oracle with a smaller,
  independently authored decision table and invariant suite. Retirement is an
  evidence-gated outcome, not a predetermined target.

## Scope and decisions

### Frozen population and baseline

The accepted source baseline is
`536915fb28068c141f59b2243119530205538b4d`. Implementation starts from that
commit with a clean worktree. Planning collected 4,964 cases, with 4,936
ordinary cases and 28 headed cases; it did not run the runtime baseline. The
Python inventory found 27 support files without test functions (17,477 lines)
and seven `_file`, seven `_operation`, and six `_scan` builders.

The bounded population is the test tree at the baseline commit, its test-owned
JavaScript probes/support, and the settlement oracle/reference closure. Other
production tools and unrelated product behavior are out of scope. Materialize
case ids, expanded parameter rows, support consumers, and checkpoint assignments
in the temporary delivery inventory before reduction. Each candidate belongs to
one checkpoint; ambiguous candidates remain unchanged. Later-added tests do not
silently expand the register. The department manifest remains the sole primary
module-ownership authority; this inventory is temporary delivery routing only.

### Documentation authority

Classify each affected claim individually:

1. **Normative guarantee:** supported behavior, authority boundary, ownership,
   hard wall, public/persisted contract, or protected acceptance requirement.
   Preserve it unless the user explicitly approves a change.
2. **Current mechanism:** filenames, private fields, representation, helper
   structure, implementation sequence, or incidental call transcript. A current
   description does not automatically require a permanent test.
3. **Historical evidence:** earlier delivery gates, migration snapshots, retired
   transports, or corrected-monolith attribution. Preserve necessary provenance
   without treating every historical mechanism as current behavior.

Neither document location nor imperative wording alone settles this class.
Update descriptions before changing the practice they describe. A conflict
between supported behavior and a normative guarantee requires adjudication.
Reflective corruption of trusted values is distinguished from malformed
external input as specified in `DEFENSE.md` section 2; reflection used to set up
a real boundary test is not itself a reason to delete that test.

### Permitted product seams

Use existing collaborators first. Only these additions/naming changes are
preauthorized, with existing calls, defaults, settings, wire formats, persisted
state, and behavior preserved:

- `UiStateOwner(..., *, write_delay_seconds=0.250)`, accepting a finite
  nonnegative delay.
- `NativeCopyBackend(..., *, queue_items=32, poll_seconds=0.01)`, with strict
  integer queue capacity 1..32 and a finite positive poll interval; the byte
  budget is unchanged.
- Stable names for the existing appearance, instance, and path-lease native
  protocols at their existing boundaries, without another abstraction layer or
  expanded capabilities.

Other patched constants are classified, not automatically promoted. Protocol
constants, numerical/security bounds, and protected evidence values stay fixed.
Service tests prefer normal construction with test-owned replacements at the
existing runtime/dispatcher/observer composition points, not a new dependency
container or production private-state inspection API.

Production operation kinds, journal, settlement algebra, reducer, retries, and
mutation policy are unchanged. Oracle fact/vocabulary simplification applies
only to test machinery.

### Non-goals and stop policy

- No product fixes, features, lifecycle redesign, schema changes, new user
  configuration, broadened supported inputs, or unrelated cleanup.
- No blanket ban on monkeypatch/private assertions, blanket subset assertions,
  automatic pairwise reduction, coverage/mutation-score targets, or count quota.
- No unrelated evidence recalibration/retirement. SH-G-8 contracts, frozen
  validators, baselines, and pinned source closures stay unchanged.
- No permanent inventory framework, duplicate policy registry, or generic mock
  framework. Temporary delivery machinery is retired at closeout.

A red rewritten test is first investigated as a setup, timing, assumption, or
observation problem against unchanged production. A supported latent product
defect is reduced to a reproducer, logged in `BUGS.md`, and reported, **not
fixed**. This stricter task rule overrides the ordinary permission to fix a
bounded pre-existing defect. Do not weaken a check or add skip/xfail for green.
Block the owning checkpoint if a named gate cannot pass; follow repository hard
stops immediately. A regression introduced by an approved seam must be corrected
or the seam withdrawn. Intentional isolated defect witnesses are not baseline
product findings.

Stop and return for review on a supported hard-wall consequence, an unfixable
checkpoint regression within scope, a latent defect blocking a required gate,
missing independent evidence, need to change production settlement or another
normative guarantee, or scope exceeding the accepted population/mechanism.
Repository recovery and repeated-mechanism rules remain active. Findings do not
add register rows. No required gate is waived by a green ordinary run.

## Investigation and regression map

| Family | Maintenance pressure | Detection retained |
| --- | --- | --- |
| Structural guards | File/export/signature snapshots, field-name blacklists, source fragments | Forbidden dependencies, supported calls, restricted capabilities, real retention |
| Construction | Duplicate builders and private-state installation | Explicit scenario differences, valid defaults, invalid inputs, independent expectations |
| Boundary policy | Repeated constructor/decoder/persistence/consumer matrices | Canonical bytes/types, admission before mutation, route translation and bypass |
| Review/inventory | Repeated producer/workflow policy | Completeness, fresh authority, bounds, selection/dependencies, refusal without partial artifacts |
| Lifecycle/custody | Private maps, constructor bypass, cleanup transcripts | Exact owners, rollback/replay, control/concurrency, release/delivery, truthful termination |
| Execution/integrity | Similar scaffolds and operation/failure products | Before/after effects, publication/metadata/recording, pause/resume, cleanup, native identity |
| Desktop | Native patches, timing constants, source witnesses | Origin/startup security, cleanup ownership, safe fallback, cosmetic persistence, real native behavior |
| Harness/oracle | Process boilerplate and procedural expected values | Installed-product execution, trustworthy evidence, consumed faults, independent acceptance/rejection |

The 48-row event-recording matrix across three routes and the 24-case compound
workflow product are candidates, not predetermined deletions. Establish shared
enforcement and route-specific bypass detection before removing repeated policy.
Retain workflow dimensions affecting termination, accepted prefixes, phase
projection, or error rendering unless irrelevance is demonstrated. Equal
outcomes or reaching the same lines is insufficient.

## Reduction and evidence protocol

### Candidate dispositions

For each causal reduction group record original case ids/removed parameter
rows; supported trigger, state, and guarantee; the plausible escaping defect;
surviving owner detector and additional integration witness; why removed
dimensions add no interaction/boundary; rejection evidence; and disposition
(`retain`, `rewrite`, `merge`, `delete`, or `defer`). Group equivalent cases
rather than making one documentation row per assertion.

An obsolete-mechanism case needs evidence that its sole obligation is gone and
surviving tests for remaining product responsibilities. No replacement is
required only when no supported obligation survives, with explicit review.

### Detection equivalence

For every reduced causal group:

1. Run original and replacement tests against unchanged production.
2. Introduce a named bounded defect in an isolated source copy or existing
   collaborator seam.
3. Show old detection where applicable and surviving detection for the intended
   behavioral reason, not collection/fixture errors or unrelated timeouts.
4. Restore the control and demonstrate green again.

Report mutation proves validator behavior; application tests need production-
path or collaborator-effect faults at the relevant transition. For structural
guards also prove an allowed variation (harmless internal module, compatible
optional parameter, renamed private field, or irrelevant call) no longer fails,
while forbidden imports/capabilities/effects remain detected. Name the finite
witness domain before editing each family. A newly distinguished condition
requires evidence classification, not silent implementation scope growth.

An interception fixture must prove that its recorder observed the intended call
before the test's behavioral assertions run. A nonempty recorder is only the
minimum safeguard: each qualifying hit must be tied to a causal request, token,
owner, operation, or exact effect so unrelated traffic cannot satisfy it. A
patch target that still exists is not evidence that it remains on the call path.
Tests whose supported guarantee is that no call occurs continue to assert an
empty recorder instead. Apply this rule to fixtures touched by the cleanup
without introducing a general-purpose interception framework.

Comprehensive policy belongs at its owner. Consumers keep routing, translation,
lifetime, and integration responsibilities. Preserve causal differences such
as before/after effect, file/directory primitive, identity strength, control, and
competing owners. Use explicit meaningful rows instead of automatic pairwise
sampling. Parameterizing unchanged cases is scaffold reduction, not a reduction
of behavioral obligations. Builders share assembly, not production-derived
expected policy.

### Common checkpoint gate

Before each coherent commit, close dispositions, focused tests, affected
departments, required broader checks, documentation, and adversarial review.
Review circular expectations, lost triggers, permissive assertions, fixture
shortcuts, hidden abstractions, and merely relocated mass. Temporary inventories
and mutation drivers are not permanent contracts. Persistent guard self-tests
must protect a reusable detector rather than recreate the removed obligation.

## Checkpoint register

Only explicit user adjudication may change these accepted outcomes after work
starts. Status/evidence updates do not change the denominator.

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| TS-0 | Freeze population, authority classifications, references, and baseline | - | Collection, ordinary/headed baseline, imports, original oracle | active: baseline green |
| TS-1 | Replace incidental structural locks with contract-focused guards | TS-0 | Allowed and forbidden change witnesses | pending |
| TS-2 | Consolidate the named domain-builder population | TS-1 | Construction equivalence and all consumers | pending |
| TS-3 | Consolidate canonical boundary policy without weakening ingress | TS-2 | Owner matrices and route bypass/translation witnesses | pending |
| TS-4 | Consolidate review, selection, and inventory policy cases | TS-3 | Admission/refusal, completeness, bounds, integration | pending |
| TS-5 | Consolidate session/task lifecycle and custody cases | TS-3 | Exact effects, concurrency, release, delivery | pending |
| TS-6 | Simplify native desktop and cosmetic test seams | TS-1, TS-5 | Defaults, native failures, installed headed witnesses | pending |
| TS-7 | Produce and evaluate a smaller shadow settlement oracle | TS-0, TS-1 | Frozen traces and independent rejections | pending |
| TS-8 | Adopt the proven replacement or close with justified retention | TS-7 | Authority migration or clean retention decision | pending |
| TS-9 | Consolidate execution, integrity, and compound-workflow cases | TS-2, TS-8 | Active oracle and owner/native/integration faults | pending |
| TS-10 | Reduce remaining support and top-five scaffold obligations | TS-4, TS-5, TS-6, TS-9 | Consumers, selection independence, headed evidence | pending |
| TS-11 | Close integrated verification and retire temporary delivery machinery | All preceding | Complete suite, imports, active oracle, final review | pending |

Dependencies do not authorize parallel tests against shared native resources.

## Detailed checkpoints

Every checkpoint inherits the common evidence/commit and stop rules above.

### TS-0 - Baseline and closed population

**Objective/approach:** Freeze case ids, parameter rows, JavaScript scenarios,
support consumers, and checkpoint assignments before reductions. Freeze oracle
source, companion tests, baseline, normalization, scenario/row ids, semantic pin,
and policy references using Git blob identities and byte hashes; do not change
the baseline. Record artifact conventions before creating their directory.

**Acceptance/evidence:** Establish ordinary and headed results separately, all
import contracts, and the official three-run oracle. Record capability skips and
pre-existing headed failure precisely; exclusion is not a green gate.

**Regression/adversarial review:** Exclusions cannot be chosen to make green;
protected closures must be complete; candidates have one owning checkpoint;
unclassified cases remain unchanged.

**Docs/commit:** This register, authority classifications, evidence conventions,
and README index. `docs: define the test simplification register`.

### TS-1 - Structural/source guards

**Objective/approach:** Review structural assertions in the frozen population:
file/import sets, exports/signatures, state shape/name checks, and source text,
count, and order. Remove incidental locks; keep closed schemas/capabilities.
Use import-linter rather than parallel filename architecture, and exercise
supported calls rather than rendering the entire signature.

**Acceptance/evidence:** Allowed additions/private rearrangements pass;
forbidden dependencies/capabilities and real retained resources fail. A surviving
source assertion protects an actual structural guarantee not already subsumed.
Run ordinary tests and import-linter plus allowed/forbidden probes.

**Regression/adversarial review:** Export compatibility, restricted task-port
authority, native-security exclusions, false positives, permissive replacement.

**Docs/commit:** Update `TESTS.md` and affected architecture/mechanism prose
without weakening guarantees. `test: replace incidental structural locks with
contract guards`.

### TS-2 - Domain builders

**Objective/approach:** Consolidate the 20 named builders and direct consumer
construction. Extract common assembly only; preserve explicit identity,
metadata, completeness, directories, and fingerprint differences. Use
non-collected underscore-prefixed support, not a universal fixture DSL.

**Acceptance/evidence:** Relevant constructed values and deliberate invalidity
remain equivalent; expectations stay independent; consumers work alone without
collected-test imports. Run all consumer departments and the ordinary suite.

**Regression/adversarial review:** Changed defaults, invented identity,
normalization masking bad input, shared mutation, and hidden policy calculation.

**Docs/commit:** Builder ownership and extension rules in `TESTS.md`.
`test: consolidate shared domain-value construction`.

### TS-3 - Canonical boundary policy

**Objective/approach:** Reduce repeated scalar, timestamp, Unicode, event/result,
serialized-shape, and persistence-decoder policy in core/database and direct
consumers. Comprehensive cases stay at each distinct enforcement owner;
consumers prove invocation, complete-request admission, translation, rejection
atomicity, and canonical round trips. Independent grammars/implementations keep
independent tests.

**Acceptance/evidence:** Exact boundary/first excess, Boolean refusal,
version/shape/cross-field truth, canonical bytes, and no state/cursor/queue/DB
mutation on refusal survive. Reduced route matrices still catch bypass. Run
core/database/workflows/interfaces, required JavaScript probes, and ordinary.

**Regression/adversarial review:** Shared-validator assumptions, Python/JS
differences, allowlists, history compatibility, and lossy normalization. A live
constructor is not a substitute for a persisted-format check.

**Docs/commit:** Owning core/database/history/interface responsibilities, with
formats unchanged. `test: consolidate boundary policy coverage at its owners`.

### TS-4 - Review/selection/inventory

**Objective/approach:** Review scanner/planner/preflight and workflow cases for
completeness, admission, selection, inventory population, and typed outcomes.
Remove repeated policy, obsolete transports, and irrelevant combinations while
keeping producer-specific enforcement points.

**Acceptance/evidence:** Incomplete-scan safety, fresh admission, selection and
dependencies, stable reruns, exact bounds/excess, typed refusal, and no partial
saved artifacts survive. Consumers catch omitted invocation/translation. Run
core/scanner/planner/preflight/workflows, relevant database consumers, ordinary.

**Regression/adversarial review:** Enumeration versus returned-population
faults, strong/weak identity, missing/unsupported, and effect-relevant timing.

**Docs/commit:** Owning component prose and regression references.
`test: consolidate review and inventory admission cases`.

### TS-5 - Lifecycle/custody

**Objective/approach:** Consolidate dispatcher/service/task-lifecycle/observer/
drain tests by owner, retaining association, rollback, delivery, and shutdown
integration. Replace normal-path constructor bypass with existing composition
seams. Keep pre/post-effect and exact-subject triggers; replace incidental maps
and call transcripts with effects, reusable capacity, release, necessary order.

**Acceptance/evidence:** Detect lost/duplicate/wrong-owner effects, unannounced
reliable loss, duplicate delivery, stale/replayed admission, unreachable control,
false terminal success, retained callbacks/streams, and failed-close retry loss.
Force races with events/barriers, not longer sleeps. Run dispatcher/interfaces/
workflows, relevant history cases, and ordinary.

**Regression/adversarial review:** Repeated calls are not repeated effects;
preserve same-owner exclusion, different-owner independence, close/cancel races,
generation replacement, and recoverable cleanup.

**Docs/commit:** Dispatcher/interfaces ownership and behavior descriptions.
`test: consolidate lifecycle and custody failure coverage`.

### TS-6 - Native desktop/cosmetics

**Objective/approach:** Simplify host/appearance/path/instance/startup/cosmetic
tests; name the three native protocols and add only the permitted write delay.
Preserve syscall/flag checks with real semantic value. Replace source spelling
and duplicate host setup only after behavioral/native replacements exist.

**Acceptance/evidence:** Defaults are identical and invalid seam values refuse.
Origin/startup denial, owned shutdown, persistence coalescing/flush/close, and
safe fallback survive. Run interfaces, ordinary, and affected installed-wheel
headed gates.

**Regression/adversarial review:** Fakes cannot manufacture readiness, bypass
security, release unrelated processes/handles, or turn timeout into success.
Headed evidence must exercise the installed production stack.

**Docs/commit:** Interfaces/native and headed evidence mechanisms.
`test(web): simplify native and cosmetic test seams`.

### TS-7 - Shadow settlement oracle

**Objective/approach:** Build one smaller candidate beside untouched reference.
Separate fixture/fault execution and observed facts from independently authored
expected decision rows and cross-row/reference invariants. Group common
mechanics without erasing operation identity or effects. Preserve publication,
backup, metadata/non-byte mutation, control, and recording axes. All 30 original
scenarios and 70 reference rows remain through proof. Derive expectations from
supported policy and scenario intent, not actual reports, the production
reducer, or mechanical translation of the old expected-value generator.

**Acceptance/evidence:** Original official gate passes three identical runs.
Candidate execution matches every normalized reference trace with the frozen
normalizer: no dropped fields or newly erased distinctions. Current typed
recording truth stays independent of historical trace adapters. Every injected
fault fires exactly as declared. Reject the meaningful old negative corpus and
distinguishing false-success, wrong-attribution, missing/duplicate outcome,
replayed-effect, bad cleanup/tree, unused-fault, altered-reference, and
continuation/progress counterexamples. Unknown/unclassified facts fail closed;
trace matching cannot override policy rejection. Freeze expectations and the
rejection corpus before final comparison; edits invalidate affected evidence and
need a newly reviewed version. Run executor/tools, both checkers, and ordinary.

**Regression/adversarial review:** Reject a procedural oracle disguised as a
table, production-shared expected logic, or mere recorded answers. Include all
new tables, runners, adapters, tests, and support in reduction assessment.

**Docs/commit:** Record identities, fact meanings, independence, agreements,
rejections, and limitations. Commit only a verified shadow:
`test(executor): add an independent table-driven settlement oracle`. If it
cannot qualify within this boundary, retain the original and close the attempt
with evidence, without a production refactor.

### TS-8 - Oracle disposition

**Objective/approach:** On adoption record versioned expectations, invariants,
validator identities, and unchanged historical reference; revise `AGENTS.md`,
affected `DEFENSE.md` authority, executor/tools prose before retiring the old
implementation and its mechanism-only tests. Preserve official `check --repeat
3`; retain other documented commands through the smaller runner unless their
retirement is explicit here. Preserve old-source Git identities, baseline, and
provenance. On retention remove candidate-only machinery with no adopted value
and document why it did not qualify.

**Acceptance/evidence:** Agreements and rejections, independent meaning, and a
materially simpler complete implementation are required, not moved code or
duplicate authority. The active checker cannot import retired implementation.
Retention keeps the original gate intact. Run executor/tools, ordinary, and the
active official check after cutover.

**Regression/adversarial review:** Reference substitution, missing rows,
permissive normalization, policy bypass, and stale authority links/callers.

**Docs/commit:** Adopt with `test(executor): replace the procedural settlement
oracle`, or document retention without claiming retirement.

### TS-9 - Execution/integrity/compound workflows

**Objective/approach:** Consolidate executor/verifier and linked execution/
integrity/recording tests against the decided oracle; preserve native and
integration distinctions. Introduce only permitted pipeline scheduling
parameters. Small configurations do not replace default-capacity evidence.

**Acceptance/evidence:** Before/after publication or mutation, metadata/backup
composition, recording prerequisites/finalization, retry escapes, pause/resume,
cancel, file/directory primitives, cleanup, digest identity, and terminal truth
survive. Every operation family retains a real-path witness that obtains and
uses policy facts; a decision table cannot replace probing or integration.
Run executor/verifier/workflows/core/tools, relevant recorder integrations,
ordinary, and the active oracle.

**Regression/adversarial review:** Distinguish COPY/UPDATE/MOVE_UPDATE,
file/directory DELETE, strong/weak identity, and pre/post-effect faults by cause.

**Docs/commit:** Executor/verifier/workflow responsibilities and seam docs.
`test: consolidate execution and integrity failure families`.

### TS-10 - Support/scaffold mass

**Objective/approach:** Review the frozen 27 support files and remaining
top-level scaffolding in component-gallery headed, executor runtime, settlement,
pipeline, and post-execution workflow tests. Delete support orphaned by prior
reductions; share genuinely common launch/evidence/teardown, assembly, and fault
mechanics with visible local scenario policy, not a general harness. Preserve
SH-G-8 closures; absence of test functions never establishes dead code.

**Acceptance/evidence:** Consumers work alone and under department selection.
Installed-wheel isolation, exact process ownership, original failure reporting,
immutable milestones, collision refusal, and fail-closed child outcomes remain.
No collected-test import back edge or hidden global dependency. Fault shared
harnesses before readiness, with missing/contradictory evidence, teardown
failure, and missing capabilities. Run tools/interfaces, all changed consumers,
ordinary, and affected headed gates.

**Regression/adversarial review:** No false pass, masked original failure,
weakened evidence, or relocated equivalent mass.

**Docs/commit:** `TESTS.md`/`TOOLS.md` conventions and mechanisms, protected
authority unchanged. `test: consolidate shared harness ownership and remove
obsolete support`.

### TS-11 - Integrated closeout

**Objective/approach:** Verify the replacement test system as a whole; retire
temporary delivery machinery rather than make it another standing obligation.

**Acceptance/evidence:** All populations have dispositions; reductions have
surviving detectors or justified obsolete obligations; required counterexamples
are neither missed nor unclassified. Demonstrate removed duplicate policy,
setup schemas, incidental rules, products, or authorities, not just counts.
Run the complete final sweep below.

**Regression/adversarial review:** Detect reductions jointly removing the last
detector, circular shared helpers, authority drift, production changes, and
new implicit fixture dependencies.

**Docs/commit:** Update/extend the appropriate changelog task, replace
`HANDOFF.md`, archive this completed delivery record, remove temporary drivers
and self-tests, retain reproducible essential evidence and enduring detectors.
`docs: close the test simplification delivery`.

## Artifact conventions

Temporary delivery artifacts live only under ignored
`build/test-simplification/536915fb28068c141f59b2243119530205538b4d/`.
This directory contains `scripts/` for temporary reproducible inventory/gate
drivers; `inventory.json` and `references.json` for baseline identities/routing;
and `runs/<gate>-<UTC timestamp>/` for command metadata, logs, exit status, and
optional JUnit results. Each run gets a new directory; no result is overwritten.
Failed headed runs may retain exact child milestone/scenario files under their
run's `child-evidence/`, with a source/destination SHA-256 manifest beside them.
Copy only the named run's generated evidence, not databases, installed runtimes,
or unrelated temporary files. Preserve the original immutable milestone bytes.
Future defect/allowed-change probes use `probes/<checkpoint>/<case>/`, never the
live product checkout. Only task-owned exact paths may be cleaned. Failed
evidence remains until adjudication; temporary drivers retire at TS-11. These
files are generated delivery evidence, not a new permanent test framework.

## Overall final sweep

Run serially with the project virtual environment and verified Node runtime:

```powershell
$env:NAMISYNC_TEST_NODE = 'C:\Users\Spectrum\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces -o "addopts=" -m headed
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3
git diff --check
git status --short
```

Replay the final finite defect and allowed-variation corpora; verify defaults,
cross-checkpoint detection mappings, Python/JS and live/history boundaries,
protected identities, and unchanged scale/native evidence. Do not substitute
timing for analytical/structural checks. Record failures/skips faithfully; no
ordinary pass waives headed/oracle evidence. Compare all test/support/checker
machinery including tables as diagnostics. Verify no latent fix, weakened
contract, broad refactor, or unrelated cleanup entered the diff. Completion
requires the integrated sweep, not only individual green checkpoints.

## TS-0 evidence and disposition (2026-09-04 - 2026-09-05)

All commands used the unchanged baseline product/tests, the project Python
3.13 environment, and the Node runtime named above. Runs were serial. Full
commands, exit status, stdout, and pytest JUnit results are under the artifact
root's `runs/` directories:

| Gate | Run directory | Observation |
| --- | --- | --- |
| Complete collection/inventory | `inventory-20260904-133002-420` | 4,964 cases; 28 headed; 27 support files / 17,477 lines; builders 7/7/6 |
| Ordinary baseline | `ordinary-20260904-133009-887` | 4,932 passed, 4 skipped, 28 deselected; 232.63 seconds |
| Import contracts | `imports-20260904-133428-243` | All 12 kept; none broken |
| Original official oracle | `oracle-20260904-133445-446` | 30 scenarios x 3 runs passed |
| Headed baseline | `headed-20260904-133529-146` | **9 failed, 19 passed**, 4,936 deselected; 120.69 seconds |

The ordinary skips are existing unavailable symlink/reparse capabilities
(`WinError 1314`), at `test_core_scanplan.py:622`, `test_tools_cli.py:95`,
`test_tools_cli.py:1236`, and `test_tools_corpus.py:189`. No new exclusion,
skip, xfail, or test/source change was introduced. Timings/counts are diagnostics.

`inventory.json` retains expanded Python node ids, department ownership, the
20 builder locations, 27 support files with textual consumer candidates, and
baseline test-owned JavaScript/HTML paths. Initial family routing is **not** a
semantic reduction disposition. Support consumers and JavaScript scenario
obligations still require direct review; ambiguous candidates stay unchanged.
`references.json` freezes Git blob identities and working-tree byte hashes for
the baseline test/product files and named oracle/governing sources. The original
reference semantic SHA-256 is
`ada1a5f0e5987a2dade41931319d2535a3c9e72dcdbfa9a292964623fff4ecf3`.
The gate accepted that unchanged reference; no rebaseline was attempted.
After the run, all 280 frozen file byte hashes still matched. Seventeen exact
child milestone/scenario files were copied without byte changes into the headed
run's `child-evidence/`; its manifest records original and preserved paths and
SHA-256 values. No installed runtime or database was copied.

Initial claim-level authority review, not permission to remove tests:

| Claim | Classification and treatment |
| --- | --- |
| Forbidden component imports and independent native leaves | Normative dependency law; existing import-linter contracts remain authority |
| Supported facade names and calling forms | Normative compatibility; retain invocation detectors |
| Exact package file list, export ordering, rendered signatures | Mechanism candidates; only reduce with compatible-change and negative witnesses |
| TaskLifecyclePort's limited task authority | Normative restricted capability, not an incidental exact-set check |
| Exact-owner cleanup, unique effects, release and truthful settlement | Normative; private names/maps alone are not equivalent evidence |
| Retired in-process transports and migration snapshots | Historical; confirm no surviving responsibility before removal |
| Original oracle trace lineage versus current typed recording truth | Historical provenance and independent current guarantees respectively; preserve both under TS-7/TS-8 gates |
| SH-G-8 frozen authority and native/security bounds | Protected requirements; no recalibration or weakening authorized |

### Initial headed baseline blockers (historical)

The complete failed case ids and tracebacks are retained in the headed JUnit
and log. Grouping below avoids nine independent incident stories; it does not
claim all causes are established.

| Population / consequence | Observation, owner, and unresolved distinction |
| --- | --- |
| Six SH-G-12 material scenarios: capable, controller failure, main-window failure, light/dark no-material, high contrast | Five surfaced sanitized `page_probe` / `RuntimeError`; dark no-material surfaced invalid window handle (`WinError 1400`) and also published a page-probe failure. Material child/harness evidence is incomplete; sanitized records do not identify a product cause. |
| BR-G-30 real installed host assumptions | Two `delayed_return.evaluate.begin` events where `_only_event` requires one. `_native_gate_child.py` labels any return callback after handler completion until an event is set in `finally`; the check/set is not atomic. This observation does not establish duplicated domain effects; causality needs separate review. |
| SH-G-5 database-contract refusal | Dialog correctly reported `history-contract`, but the test requires old wording absent from current `database_pair.py`. It failed before the subsequent read-only check, so that guarantee is not signed off by this run. This is a confirmed stale test expectation, not a product fix request. |
| BR-G-32 independent origin recheck | Existing `ElementNotAvailableException` recurred. Immutable ready evidence reports `bridge_unavailable` and no handler calls, but UI Automation cannot expose the refusal. These facts do not waive the required headed assertion. |

At this point in the investigation, no product defect or hard-wall escape had
been established and no repair had been attempted. A blind rerun could not
resolve the deterministic wording mismatch, so the complete run remained a
**TS-0 blocker** pending a bounded baseline-repair decision. The observations
below are superseded by the adjudication and rerun record in the next section;
they remain here as baseline evidence rather than current defect status.

Adversarial review: ordinary green did not conceal headed failures; no test was
excluded to manufacture green; preserved milestone bytes are observations, not
substitute acceptance; inventory routing and textual consumers are not claimed
as completed semantic review. TS-0 is incomplete and has no merge-ready commit.

### Headed baseline repair and rerun

The user separately authorized the minimum product correction needed to keep an
off-origin refusal recognizable; commit `3499ad2` made exact response-token
acknowledgment cleanup-only without granting dispatch authority or releasing
capacity before worker exit. Four bounded test families then repaired the
measuring system:

| Family | Reduction or rewrite | Detection retained |
| --- | --- | --- |
| SH-G-12 materials, six cases | Deleted an unrelated direct native-dispatch refusal, two report fields, and their source/schema assertions | All six distinct native material, failure-unwind, fallback, forced-color, installed-source, screenshot, and process-health witnesses |
| SH-G-5 database refusal | Replaced obsolete sentence fragments with semantic action checks | Exact reason, close-all instruction, both mains, every sidecar, restart guidance, native dialog, exit 1, and unchanged bytes; owner and CLI policy tests remain comprehensive |
| BR-G-32 off-origin | Recorded the already-unwrapped command refusal once, removed duplicate helper assertions, and replaced source-shape UIA checks with bounded behavioral observation | Exact intended-window text, exact command refusal, zero handler calls, committed source, process ownership, transient-only retry, diagnostic truth, and parent hard deadline |
| BR-G-30 delayed return | Correlated interception with the serialized `returned-delayed_return` value and collapsed begin/end/ack chronology into one terminal observation | Reinjection, actual old-document return attempt, lost callback, working post-navigation bridge, and exact event ordering relevant to those effects |

No behavioral headed case was deleted: matching failure symptoms did not make
the six material mechanisms equivalent, and the database, off-origin, and
pinned-host cases remain unique integration witnesses. The obsolete source-
shape check and cross-layer assertions were the removed obligations. The UIA
regressions added during baseline repair are evidence for the measuring
apparatus, not silently added reduction candidates in the frozen population.

Focused verification passed: nine ordinary and six headed material checks; the
database dialog plus 205 owner-policy and one CLI integration checks; 50
headed-helper/transport checks and the installed off-origin witness; three
ordinary native-host checks and three serial installed BR-G-30 repetitions.
The final integrated observations were:

| Gate | Run directory or result | Observation |
| --- | --- | --- |
| Ordinary rerun | `ordinary-final-20260905-four-families` | 4,941 passed, 4 established capability skips, 28 headed deselected; 200.20 seconds |
| Headed rerun | `headed-final-20260905-four-families` | 28 passed, 4,945 deselected; 116.48 seconds |
| Import contracts | direct rerun | All 12 kept; none broken |
| Original official oracle | direct rerun | 30 scenarios x 3 runs passed |

The frozen baseline inventory remains 4,964 cases. The nine additional
collected cases comprise one refusal regression for the separately authorized
product fix and eight observer regressions from the adjudicated baseline
repair; they do not change the reduction denominator. Protected settlement and
SH-G-8 authority were not modified.

## Resumption and current evidence

- **Current:** TS-0 baseline gates are green; its remaining frozen
  consumer/JavaScript semantic review is still active. TS-1 through TS-11 remain
  shelved, and no reduction checkpoint has started.
- **Base:** `536915fb28068c141f59b2243119530205538b4d`, initially clean.
- **Established:** frozen inventory and identities, green ordinary and headed
  baselines, all import contracts, the original three-run oracle, and bounded
  causal dispositions for the four headed repair families. The integrated
  complete-suite command remains a later closeout gate, not implied by separate
  ordinary/headed runs.
- **Next:** complete the remaining frozen support-consumer and test-owned
  JavaScript semantic routing before closing TS-0. Do not start TS-1 without
  explicit resumption. Temporary scripts and raw evidence stay under the
  artifact root.
- **Protected:** original oracle until gated cutover, SH-G-8 authority, user
  changes, and existing public/persisted behavior.
- **Known context:** all original headed failure families now pass through
  ordinary commits. Both WIP refs remain until every remaining documentation,
  inventory, and diagnostic path is confirmed merged, superseded, or
  deliberately discarded; recovery commits remain non-mergeable.
- **Decisions:** bounded seams allowed; product fixes forbidden; production
  settlement excluded; oracle retention/adoption both permitted under the gates.
- **Stop:** apply the task and repository stop/recovery rules above; do not
  expand a row to repair a newly exposed product or evidence defect.
