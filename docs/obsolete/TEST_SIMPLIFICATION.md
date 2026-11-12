# M1 Test Simplification

**Standing (2026-09-05): archived completed delivery record.** This register
records the accepted denominator, conditional oracle retention, and verification.
It is historical evidence, not authority for new implementation.

Accepted subtractive delivery register, revised 2026-09-05. This is temporary
delivery control rather than permanent test-policy authority. `AGENTS.md`,
`DEFENSE.md`, and `TESTS.md` retain their existing authority.

## Objective and closed scope

Reduce independently maintained test policy, cases, fixtures, scenarios, and
implementation assumptions while preserving effective detection of supported
failures, boundary violations, meaningful interactions, and distinct regression
causes. Deleting a test or parameter row is an expected outcome when a surviving
detector catches the same plausible defect for the same causal reason and no
additional interaction or boundary is lost. Counts remain diagnostics.

The **reduction population** is the test tree, test-owned JavaScript/HTML, and
settlement-oracle/reference closure at
`536915fb28068c141f59b2243119530205538b4d`: 4,964 cases, 28 headed cases, 20
named builders, and an originally reported 27 support files. The corrected
support population is 28: `_native_gate_child.py` was missed because its nested
factory is named `test_spec`; support is determined by collection role and
consumers rather than nested function spelling.

The **execution baseline** is
`ca7ef881c77e2ec3a96da87fa700d3c95b4ff926`. It has 4,941 ordinary passes,
four established capability skips, 28 headed cases, all 12 import contracts,
and the unchanged 30-scenario three-run settlement oracle. The repair added nine
test functions that produce ten current-only collected rows and superseded one
original mechanism row: `4,964 - 1 + 10 = 4,973`. All ten current-only rows are
mandatory verification witnesses, not reduction candidates; the superseded row
is recorded as repair provenance, not a cleanup deletion. The original
population identities remain historical provenance; current hashes cover the
headed repair closure.

Other production tooling, behavior, schemas, settings, inputs, and unrelated
cleanup are outside scope. A finding does not expand the register. Ambiguous
tests remain unchanged.

## Governing decisions

### Claim classification

- A **normative guarantee** is supported behavior, an authority boundary, a
  hard wall, ownership rule, public/persisted contract, or protected acceptance
  requirement. Preserve it unless the user approves a contract change.
- A **current mechanism** is a private field, filename, representation, helper,
  sequence detail, or incidental transcript. It does not automatically require
  a permanent test.
- **Historical evidence** records an earlier gate, migration, retired transport,
  or corrected-monolith attribution. Preserve provenance without treating the
  old mechanism as current behavior.

Classify each claim individually. Document location, imperative wording, and
line coverage do not settle the classification. Persisted grammars remain
distinct from live constructors. Reflective mutation may remain when it sets up
a real boundary or detachment test.

The exact-response acknowledgment guarantee added at the execution baseline is
normative: matching browser custody may be released after document trust is
lost, but acknowledgment grants no dispatch authority, exposes no response,
and cannot release the native worker before that worker exits.

### Reduction method

Choose surviving cases before extracting shared setup. For each bounded causal
group, record in the checkpoint evidence:

- original node IDs and removed parameter rows;
- trigger, state/transition, and supported guarantee;
- the plausible defect that could escape;
- surviving owner detector and any additional integration witness;
- why removed dimensions add no interaction or boundary;
- old/new control and bounded defect-witness results; and
- disposition: retain, rewrite, merge, delete, or defer.

Remove an obsolete observation through its complete chain: producer, transported
field, validator, assertions, and support. Parameterizing unchanged scenarios
reduces scaffold only, not behavioral obligations. Shared builders assemble
values and never compute expected policy from production code.

Apply these rules:

- Private layout and map assertions yield to observable effects, capacity reuse,
  exact release, and public results. Private mutation that injects malformed
  boundary input may remain.
- Exact order remains for irreversible effects and before/after-effect failure.
  Incidental complete transcripts become causal or partial-order assertions.
- Exact sets remain for public, persisted, wire, security, and immutable-evidence
  schemas. Internal diagnostic reports require consumed facts while allowing
  irrelevant additions.
- Source inspection remains only when no existing static authority or behavioral
  detector establishes the property.
- A required source guard may yield to JavaScript only when the executable probe
  is required and cannot skip for missing Node.

Interception evidence must prove observability. A positive observation identifies
the exact request, token, owner, operation, or effect. A negative observation
needs an existing positive control at the same observation point or a bounded
mutation showing removal of the prohibition is detected. A valid patch target,
nonempty recorder, or empty recorder alone is insufficient. Do not create a
general interception framework.

For each reduction, run old and replacement tests against unchanged production,
introduce one finite named defect through an isolated source copy or existing
collaborator seam, show both intended detectors reject it where applicable, then
restore and demonstrate green. Fixture errors, unrelated exceptions, and
timeouts are not detection. Structural reductions also require one harmless
allowed variation and one forbidden variation.

### Permitted production seams

Only these product-side changes are preauthorized, preserving defaults and
existing calls:

- `UiStateOwner(..., *, write_delay_seconds=0.250)`: finite numeric value at
  least zero; reject Booleans, non-numbers, infinities, NaN, and negatives.
- `NativeCopyBackend(..., *, queue_items=32, poll_seconds=0.01)`:
  `queue_items` is a strict non-Boolean integer from 1 through 32;
  `poll_seconds` is finite, numeric, and positive; byte budget unchanged.
- Rename the existing module-local protocols to `AppearanceNative`,
  `InstanceNative`, and `PathLeaseNative`, without facade export, added layer,
  or capability growth.
- Service tests may replace existing runtime, dispatcher, and observer
  composition points around normal construction. No dependency container or
  private-state inspection API.

Other constants are classified rather than automatically parameterized.
Production operation kinds, journal, settlement algebra, reducer, retry policy,
and mutation policy remain unchanged.

### Failure and stop policy

A rewritten red test is first investigated as a test setup, timing, assumption,
or observation problem. A supported latent product defect gets a minimal
reproducer and `BUGS.md` entry and is reported; this task does not fix it, add a
skip/xfail, or weaken the detector. A seam regression is corrected or withdrawn.
Repository hard-stop and recovery rules remain active. Stop on missing
independent evidence, a required normative change, or checkpoint scope escaping
its declared family.

## Regression map

| Family | Maintenance pressure | Detection that survives |
| --- | --- | --- |
| Event and boundary contracts | Cross-products across constructors, validators, decoders, persistence, and browser | Canonical types/bytes, rejection before mutation, persisted grammar, route bypass and translation |
| Review and inventory | Repeated producer/workflow policy and builders | Completeness, fresh authority, bounds, selection/dependencies, typed refusal, no partial artifact |
| Lifecycle and custody | Constructor bypass, private maps, cleanup transcripts | Exact owners/effects, rollback, replay, cancellation, races, release, reliable delivery, truthful terminal state |
| Desktop/browser/native | Source spelling, private constants, exact diagnostic schemas, repeated JS primitives | Origin/startup security, native semantics, owned shutdown, safe appearance, persistence, installed behavior |
| Execution/integrity | Operation/fault products and large local scaffolds | Pre/post-effect truth, publication, metadata, backup, recording, retries, control, cleanup, native identity |
| Oracle/support | Procedural expected machinery and child-process boilerplate | Independent acceptance/rejection, consumed faults, installed isolation, immutable evidence, fail-closed harnesses |

TS-R1 proved the event non-v5 version/body independence: version rejection
precedes body dispatch. Recording and cancellation policy now have explicit
owner matrices plus bounded consumer witnesses rather than repeated route
products. The six SH-G-12 material scenarios remain distinct native/fallback
mechanisms.

## Checkpoint register

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| TS-R0 | Close corrected population and dual-baseline record | - | Inventory review, baseline artifacts, protected identities | complete |
| TS-R1 | Prove reduction method on event-v5 contracts | TS-R0 | Owner matrix and route-bypass witnesses | complete |
| TS-R2 | Simplify review, selection, inventory, scanner, planner, and preflight tests | TS-R1 | Admission, completeness, bounds, selection, persistence | complete |
| TS-R3 | Simplify lifecycle, custody, service, observer, and drain tests | TS-R1 | Owner, concurrency, rollback, release, delivery | complete |
| TS-R4 | Simplify desktop, browser, native, appearance, and cosmetic tests | TS-R1, TS-R3 | Required Node and installed headed witnesses | complete |
| TS-R5 | Simplify executor, verifier, recording, and compound workflows | TS-R1 | Existing oracle plus owner/native/integration faults | complete |
| TS-R6 | Build and evaluate a smaller shadow settlement oracle | TS-R5 | Frozen trace equality and rejection corpus | rejected candidate; closed |
| TS-R7 | Adopt replacement or retain original with evidence | TS-R6 | Authority cutover or clean candidate removal | retained original |
| TS-R8 | Remove orphaned support and residual top-file scaffolding | TS-R2 through TS-R7 | Consumer isolation and harness faults | complete |
| TS-R9 | Integrated verification and temporary-machinery retirement | all prior | Complete suite, headed, imports, active oracle, witnesses | complete |

Native-resource gates run serially. TS-R2, TS-R3, and TS-R5 have no dependency
on one another beyond TS-R1.

## Detailed checkpoints

### TS-R0 - Corrected population and dual baseline

Classify support by collection role, add `_native_gate_child.py`, route every
original Python row, support consumer, and JavaScript/HTML behavioral section
to one checkpoint, and retain ambiguous items. Record `536915f` as population
provenance and `ca7ef88` as execution authority; classify the nine repair test
functions as ten mandatory collected witnesses, and record the one superseded
original mechanism row. Freeze current repair-file hashes and verify unchanged
oracle/SH-G-8 identities. Commit `docs: revise the test simplification register`.

### TS-R1 - Event-v5 pilot

Reduce the four rejected versions by seven body types while retaining every
version class, every successful body conversion, and a decoder-validator bypass
witness. Place comprehensive recording policy at its owner; consumers retain
accepted round trips and bypass, mistranslation, and persisted-shape mutations.
Apply the split to cancellation, timestamp, scalar, and shape policy. Delete
historical private-name blacklists only when current-version refusal and absence
of legacy decoding authority remain proven. Run focused old/new and defect
witnesses, core/database/interface neighborhoods, required JS event probes,
ordinary, and import-linter. Commit
`test(core): consolidate event contract coverage at its owners`.

The accepted TS-R1 dispositions are:

| Causal group | Original obligations | Surviving obligations | Disposition |
| --- | ---: | ---: | --- |
| Event epoch and legacy mechanism | 33 | 8 | Keep each rejected version class and constructor type/value boundary; remove body multiplication, duplicate far-future integer, and private-name blacklist |
| Item recording policy | 145 | 11 | Keep full reason/outcome policy at its owner and focused typed/persisted shape and bypass checks; remove three-route product and count meta-test |
| Cancellation truth | 92 | 27 | Keep all 23 owner rules and four consumer-axis witnesses; remove full policy repetition at each consumer |
| UTC timestamp grammar | 100 | 51 | Keep all 50 persisted-validator rows and one accepted decoder-translation witness |
| Scalar64 event routing | 21 | 5 | Keep distinct route/error-family boundaries; rely on the scalar owner for the rest of its grammar |
| Unicode field routing | 33 | 24 | Keep complete UTF-16 path and UTF-8 detail corpora plus two recording-detail route witnesses |

This removes 298 collected rows: the focused unchanged-product control was 925
passes and its replacement is 627 passes; repository collection moved from
4,973 to 4,675. The test files add 44 net source lines because previously
implicit recording and cancellation ownership is now explicit; this is a mass
cost, not a claimed reduction. The generated 48-row recording fixture and its
count authority are gone.

The finite witness driver ran each selected old and replacement detector against
an isolated unchanged control and isolated mutation. Every control was green;
mutants produced only assertion failures in the intended tests, with no errors,
skips, or timeouts:

| Witness | Old mutant failures | Replacement mutant failures | Result |
| --- | ---: | ---: | --- |
| Harmless private legacy-spelled symbol | 1 | 0 | Old incidental lock removed; public replacement allows it |
| Decoder bypasses exact validator | 28 | 5 | Both behavioral detector sets reject |
| Typed constructor admits future version 6 | 1 | 1 | Both constructor detector sets reject |
| Recording owner widens failed-only reasons | 6 | 2 | Both reject |
| Typed and persisted recording consumers bypass owner | 42 | 2 | Both reject |
| Cancellation owner omits compound verify rule | 12 | 3 | Both reject |
| Cancellation consumers bypass owner | 48 | 4 | Both reject |
| Timestamp validator admits `Z` spelling | 2 | 1 | Both reject |
| Event Scalar64 coerces raw values | 8 | 4 | Both reject |
| Recording detail bypasses Unicode validation | 7 | 1 | Both reject |

Focused verification passed 627 tests. The core/database/interfaces
neighborhood passed 2,718 tests with one established capability skip, including
the required Node event probes. The ordinary repository gate passed 4,643 tests
with four established capability skips and 28 headed tests deselected. All 12
import contracts remain kept. No product source changed and no latent product
defect was found.

### TS-R2 - Review, selection, and inventory

Group scanner/planner/preflight/inventory cases by incomplete output, first
excess, root authority, unsupported/missing selection, dependency closure,
partial-artifact prevention, and stable rerun. Keep comprehensive producer
policy plus workflow bypass/translation and persistence-atomicity witnesses.
Replace option/failure products only when options do not alter these effects.
After dispositions, consolidate this family's `_file`, `_scan`, and `_operation`
assembly without hiding malformed values or expected policy. Run core, scanner,
planner, preflight, workflows, database consumers, ordinary, and imports. Commit
`test: consolidate review and inventory failure families`.

TS-R2 completed from `dec317f` with independent adversarial review. Pre-edit
node IDs and dispositions remain under `probes/TS-R2/`. Scanner initial root
admission retains three root categories and all scope routes (9 -> 5); plan
signal provenance retains all ten retirement paths and foreign-run token
rejection at the shared catch (20 -> 11); snapshot cleanup retains six owner
precedence rows and an explicitly observed history validator route (12 -> 7).
Bridge scan-scope tests now reuse the exactly equivalent database file builder.
The other thirteen named builders retain their distinct defaults; all remaining
TS-R2 populations, selection/dependency, authority, and persistence cases remain.

Focused old/new controls passed 417/399 cases. The final neighborhood passed
2,222 with one established capability skip; ordinary passed 4,625 with four
established capability skips and 28 headed deselections. Collection is 4,657.
All 12 import contracts and diff checks pass. No production source changed.
Independent review identified an unobserved history-validator route; adding
an exact invocation assertion resolved it before acceptance. Six isolated
old/new witness groups cover root-admission bypass, foreign-token admission,
cleanup precedence, history-validator bypass, equivalent keyword construction,
and identity corruption. Controls and the allowed variation pass; every named
defect is detected. `witness-02` supplies the first three groups and
`witness-03` the remaining three. Earlier driver stops are retained: cleanup
mutants intentionally change the raised exception class, and the classifier
was corrected to recognize those exact outcomes. No product defect was found.

### TS-R3 - Lifecycle and custody

Use normal service construction for normal paths. Retain constructor bypass only
for partial-construction/teardown subjects. Consolidate by cause while preserving
pre/post effect, same/different owner, rollback, replay/generation, cancellation,
close races, retry, exact acknowledgment after trust loss, terminal truth, and
release. Replace maps/transcripts with capacity, exact subject/effect, delivery,
and necessary partial order. Use barriers/events and prove negative interception
observability. Run dispatcher, interfaces, workflows, history consumers,
ordinary, and imports. Commit
`test: consolidate lifecycle and custody detection`.

TS-R3 completed from `c058e88`. All 31 normal-path manual service setups in
`test_service.py` and `test_bridge_service.py` now invoke the real constructor
with the three existing composition points replaced by explicit collaborators.
The shared helper restores its patches before returning. Custom lifecycle/fault
state remains explicit; partial-runtime teardown tests remain unchanged.
One observer timeout retry duplicate yields to the stronger ordinary/fatal
failure-retirement matrix. Response capacity is observed through exact replay,
retirement, replacement admission, and renewed first-excess refusal instead of
two private map lengths. Distinct custody, rollback, generation, concurrency,
release, and cleanup-order witnesses remain retained.

Focused old/new controls passed 253/252. The dispatcher/interfaces/workflows/
database neighborhood passed 2,696. Ordinary passed 4,624 with the four established
capability skips and 28 headed deselections; collection is 4,656. All 12 import
contracts pass. Six isolated witness groups cover service/response private
renames, skipped observer initialization, lost observer retry, response excess,
and failed retirement. The old constructor bypass misses the initialization
fault while the replacement detects it; both detect the retry/capacity defects.
Renames fail only the retired structural assumptions. `witness-01` contains the
first five completed groups and `witness-02` completes retirement after the
classifier recognized its exact expected capacity refusal. Independent review
is clear. No product source changed or product defect was found.

### TS-R4 - Desktop, browser, native, appearance, and cosmetics

Add the approved UI delay and protocol names. Replace private timing patches
while preserving default behavior. Review source guards across frontend, host,
transport, materials, instance, and runtime: retain sink scans, dependency pins,
syscall/flag semantics, and properties without stronger detectors; otherwise
prefer required Node or installed behavior. Promote a supplemental probe before
using it to replace a required guard. Consider shared event-target/deferred
primitives only across the four named bridge/cosmetic/drain probes; keep policy
local. Exact milestone envelopes and consumed evidence fields remain strict,
while irrelevant diagnostics may grow. Remove obsolete observations end to end.
Run interfaces, required Node probes, ordinary, and affected headed gates.
Commit `test(web): simplify desktop and browser evidence`.

TS-R4 pre-edit dispositions are fixed under `probes/TS-R4/`: approved delay
and protocol seams, two promoted required Node probes replacing two source
spelling guards, shared listener mechanics across the four named probes, and
extra runtime diagnostics in two headed reports. All consumed/native/security
fields, six material scenarios, and mandatory repair witnesses remain.

TS-R4 completed from `a8290b2`. Eighteen private delay patches now use the
approved per-owner constructor seam; all three protocols retain their original
module boundaries. Sixteen seam cases cover invalid, independent, zero, and
large finite delays. Integer nanosecond deadlines and bounded native waits
preserve the complete finite domain. Two required Node probes replace two source
spelling guards; the other static/native/security guards remain. Four probes
share listener mechanics while retaining local policy and timers. Only extra
runtime diagnostics are permitted in the two headed schemas.

Old focused control passed 325; the corrected replacement passed 336 before
three large-delay cases were added, and the final timing/cosmetic run passed
68. Interfaces passed 1,450; ordinary passed 4,638 with four established skips
and 28 headed deselections. Collection is 4,670. All 28 installed headed cases
and all 12 import contracts passed. Six old/new witness groups, ten listener
observations, explicit failure of both gates without Node, and 108 schema
observations from seven real installed reports all meet their expected results.
Independent adversarial review is clear. Initial UTF-8 edit damage was repaired
from Git provenance, including task-owned changelog damage from earlier scripts;
failed evidence is retained. No latent product defect was found.

### TS-R5 - Executor, verifier, and compound workflows

Proceed with the existing oracle. Add approved queue/poll seams and preserve
default capacity/byte-budget evidence. Group cases by pre/post publication,
metadata/non-byte mutation, backup/trash, recording/finalization, retry,
cancellation/control, file/directory primitive, identity strength, and digest.
Reduce operation/fault products only when operation identity changes none of
those facts. Keep production-path witnesses for each material operation family.
Consolidate surviving builders and the runtime/settlement/pipeline/post-execution
scaffolds within their causal owners. Run executor, verifier, workflows, core,
recorder integrations, tools, ordinary, imports, and the original oracle. Commit
`test: consolidate execution and integrity failure families`.

TS-R5 pre-edit dispositions are fixed under `probes/TS-R5/`: four bounded
reductions (verifier sink, executor diagnostics, compound exclusion diagnostics,
and adaptive-size forwarding), approved queue/poll seams, and retained distinct
builders/native operation families. All before/after-effect, recording boundary,
identity, exclusion delivery, and verification-admission distinctions remain.

TS-R5 completed from `fe88f31`. The approved queue/poll constructor seams
replace five private constant patches in four pipeline tests, preserving literal
32-item/32 MiB/default 0.01-second evidence. Native waits saturate safely for
large finite intervals. Twenty-one new cases cover invalid classes and actual
copy behavior with defaults, small handoffs, and huge integer/float intervals.

Seventeen redundant rows are removed: verifier sink 4 -> 3, executor diagnostic
6 -> 4, compound exclusion 24 -> 13, and adaptive forwarding 5 -> 2. The exact owner
bands remain; forwarding expectations are independently stated literals. Both
verifier routes, all three recording boundaries, all compound exit/exclusion/
verification combinations, dispatcher exception retirement, and every material
native operation family remain. The six surviving builders keep their distinct
causal owners; a generic builder would add policy switches.

Focused controls passed 625 before editing and 629 after correction. The first replacement run
passed 628 and rejected one stale public-signature expectation; it was aligned
with the explicitly approved constructor parameters. The required executor/
verifier/workflows/core/database/tools neighborhood passed 2,827 with
4 established capability skips. Ordinary passed 4,642 with the same
four established skips and 28 headed deselections; collection is 4,674.
All 12 import contracts and the original 30-scenario three-run oracle passed.
All eight protected identities and all ten repair witnesses are preserved.

Fifteen isolated old/new groups (60 runs, 30 green controls) prove retained
secondary-error handling and both verifier routes, shared diagnostic handling,
three recording attributions, first-error precedence, exclusion non-replay,
verification admission, fallback-message preservation, chunk/allocation
forwarding, and prompt shutdown. The replacement alone accepts the harmless
private queue/poll rename. No JUnit error or skip occurs in that corpus.
Independent adversarial review is clear; no latent product defect was found.
TS-R6 has not started. This is the requested recap boundary.

### TS-R6 - Shadow settlement oracle

Build one candidate beside the untouched original, retaining all 30 scenarios
and 70 rows through proof. Separate observed facts, independently authored
decisions, cross-row invariants, and reference validation. Require trace equality
without dropped fields, exact fault consumption, independent typed-recording
truth, fail-closed unknowns, and rejection of false success/attribution,
missing/duplicate/replayed outcomes, bad cleanup/tree, unused faults, altered
references, and inconsistent continuation/progress. Count all candidate code,
data, adapters, tests, and support. Commit a shadow only if fully qualified:
`test(executor): add an independent table-driven settlement oracle`.


TS-R6 evaluated one standalone transitive factual-runner extraction beside the
untouched original. It ran all 30 scenarios and 70 rows, retaining seven typed
recording side channels. Exactly 69 rows matched the frozen normalized reports.
The resume row lost source metadata-reference/equality values because its
imperative binding installer reads the old expected declarations. This is a
candidate observation defect, not a production or original-oracle regression.

A fresh Codex/GPT reviewer independently read the factual injections, core
contracts and supported executor rules without reading the baseline, old
expected declarations/generators, or production reducer. It could not establish
exact decisions for committed MOVE retry, the four prepublication UPDATE backup
states on failure/cancellation, and disappeared-after-create MKDIR. In
particular, byte-stage resume rules do not decide committed non-byte retry;
backup diagnostics plus prepared/unpublished cancellation do not alone select
all outcome/recording cells. Copying old decisions would fail the independent
authoring criterion. These are candidate evidence gaps, not verified product
defects or changes to existing authority.

Reject this candidate at the trace and independent-decision prerequisites under
the explicit conditional path. No qualified shadow is committed. Independent
recording validation, exact fault-consumption proof, the full candidate rejection
corpus, and complete implementation-size qualification were not completed.
The extracted 3,887 lines versus 8,602 original lines omit unfinished decision,
invariant, reference and test machinery; this is neither a simplicity claim nor
a size-failure claim. The projection mismatch is repairable and a redesigned
replacement remains possible. A second fresh adversarial reviewer verified the
mismatch and accepted this bounded early-rejection disposition.

Evidence: `probes/TS-R6/{extraction-result,row-admission,candidate-observations}.json`
and `independent-review.txt` under the declared ignored evidence root. The
original 95 checker tests pass; official `check --repeat 3` passes all 30
scenarios. Retain existing normative authority rather than inventing missing
candidate decisions.

### TS-R7 - Oracle disposition

For adoption, update `AGENTS.md`, `DEFENSE.md`, and executor/tool authority before
retirement, preserve `check --repeat 3` and provenance, and prove no retired
implementation import. For retention, remove candidate-only machinery with no
adopted detector and record the failed criterion. Adopt with
`test(executor): replace the procedural settlement oracle`; document retention
without claiming replacement.

TS-R7 retains the original checker, all 30 scenarios/70 rows, committed baseline,
95 checker tests, semantic pin and authority unchanged. Candidate-only source
and extraction/execution drivers were removed after recording their hash and
observations; no active import or detector depends on them. No oracle
replacement or authority cutover is claimed.

### TS-R8 - Residual support and scaffold cleanup

Reinventory the 28 baseline support files, repair-era support, and support added
by later checkpoints, including `_service_fixtures.py` and `_event_target.mjs`.
Delete prior-checkpoint
orphans, then review remaining large files by obligation. Share child launch,
evidence reading, teardown, or fault mechanics only when ownership and failure
semantics match. Fault shared support before readiness and for missing or
contradictory evidence, teardown failure, absent capability, unrelated traffic,
and inert negative interception. Preserve SH-G-8 closure. Verify every consumer
alone, under department selection, and installed where required. Commit
`test: remove orphaned support and residual scaffold duplication`.

TS-R8's census retains all 28 original support files plus the service fixture
and event-target additions. All retain named consumers. Three unused helper
definitions predate the population baseline and remain outside cleanup scope.
The only remaining proven same-owner extraction is the identical required Node
launch scaffold in the timeout and interactive probes in `test_transport.py`.
A local helper retains their fixed probe identities, required capability policy,
10-second deadline, subprocess cleanup, complete output and failure diagnostics.
BR-G-36 and supplemental probes keep their distinct fixture/diagnostic policies.
No benchmark, custody, headed-evidence or native launcher authority is merged.
Before/after consumer controls and exact argument, absent/invalid executable,
launch exception, timeout, nonzero return, and output-preservation witnesses
verify this extraction; interfaces selection and the installed headed closeout
verify its surrounding consumers. No new shared support module is introduced.

TS-R8 is complete: both consumers passed independently, all 124 transport tests
passed, and interfaces passed 1,450. Thirty-two old/new launch observations
proved exact arguments and deadlines, required failures, and preserved stdout/
stderr. Wrong-probe and wrong-timeout mutations were rejected. Independent
adversarial AST comparison found the two bodies exactly equivalent after fixed
filename substitution, with every other module AST unchanged. No rows or
support files were deleted; the shared scaffold removes 20 net test lines.
All 28 baseline Python support files retain consumers (18,747 current lines);
the 21-line service fixture makes 29/18,768, and the added JS event target has
33 lines. The largest remaining modules retain distinct settlement, workflow,
observer, custody and concurrency obligations. No further reduction was proved.

### TS-R9 - Integrated closeout

Replay the complete retained defect and allowed-variation corpora, verify no
overlapping reductions removed the last detector, required JS cannot skip,
approved seams preserve defaults, and protected identities remain unchanged.
Compare complete test/support/checker machinery including additions as a
diagnostic. Update the M1 consolidation changelog task, replace `HANDOFF.md`,
archive this register, and retire temporary inventory/mutation drivers. Commit
`docs: close the test simplification delivery` only after the final sweep.


TS-R9 is complete. Final ordinary verification passed 4,642 tests with the same
four capability skips and 28 headed deselections. The installed interfaces
headed run passed all 28; the complete suite passed 4,670 with the same four
skips. All 12 import contracts and the retained original 30-scenario three-run
oracle pass. All ten repair-era witnesses pass and all eight protected Git blob
identities match the frozen references. The first headed attempt had five
folder-dialog automation RuntimeErrors and 23 passes. A diagnostic-only isolated
picker run passed without exposing the error cause; it is not acceptance
evidence. The subsequent unmodified headed rerun and complete suite passed.
The initial failure remains preserved and unclassified; no environment cause or
product defect is asserted and no synchronization/acceptance rule was changed.

The finite control/defect/allowed-variation corpus was replayed against the
integrated tree, including the post-R5 service/Node corrections and R8 launches.
Reconciliation detected saved R2/R3 drivers narrowed to calibration tails; fresh
completion runs covered the omitted registered groups. All six R2 and six R3
groups are included, alongside ten R1, six R4 and fifteen R5 groups, listener,
required-capability and 108 schema observations. Expected injected failures are
classified by their original causal checks; no fixture error or skip is credited.
Independent fresh Codex/GPT adversarial reviews found no lost final detector,
unapproved seam/behavior/schema change, or protected-authority drift. No Claude
opinion was requested in this continuation.

Complete tracked machinery accounting includes every `tests/` file and both
active settlement checker/reference files, including additions, using Git blobs
at each ref. Population baseline: 166 files / 7,702,026 bytes / 228,876 lines.
Repaired execution baseline: 166 / 7,711,328 / 229,184. Final: 168 / 7,709,188 /
229,113. The total is 71 lines smaller than execution but 237 lines larger than
population; source volume is essentially unchanged. Collection falls from
4,973 execution rows to 4,674 (299 fewer), or 290 fewer than the 4,964-row
population; the ten repairs and one superseded historical row explain the dual
baseline. These counts are diagnostics, not evidence of detection strength.

Delivery inventory/mutation drivers are retired into a hash-verified
source-only `retired-drivers.zip`, with exact membership/hash manifest. Loose
active drivers and candidate-only bytecode were removed. Append-only JSON,
JUnit, logs and isolated run fixtures remain ignored local evidence. The
protected oracle/baseline and SH-G-8 authority are not retired. Final evidence is
`probes/TS-R9/` under the declared root; failed earlier calibration evidence is
preserved separately. This register is archived and the active README index and
latest-session handoff are updated.

## Post-checkpoint Claude review

The user requested a read-only `claude-opus-5`/`xhigh` review of TS-R2 through
TS-R5 and authorized a separate correction commit for valid findings. This
bounded follow-up does not start TS-R6 or change the original population.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| TS-R5-CR | Complete the three missed normal-service fixture migrations; align both promoted Node gates' launch diagnostics; clarify checkpoint-added support and required-probe documentation | Existing lifecycle/settings/transport controls; missing-initialization and unusable/timeout Node witnesses; interface/dispatcher neighborhood; ordinary suite; imports; same-session Claude reconciliation; exact Git status comparison | complete |

Keep the explicitly authorized protocol renames. An isolated deletion of
`_close_lock` initialization already fails the existing concurrent-close test;
pre-existing production fallbacks remain outside this test correction. Historical
28-support/24-JS counts remain baseline provenance, with additions tracked below.
No production policy change, new test framework, or TS-R6 work is included.

TS-R5-CR is complete. All three remaining constructor bypasses use the shared
real-construction helper. Both promoted Node gates now identify invalid paths
and report launch/timeout failures with executable guidance. README and the
owning interface/desktop/test documents describe their actual required scope;
TS-R8 explicitly includes checkpoint-added support without changing frozen
baseline counts. Production source is unchanged.

Focused old/new controls passed 164/164; standalone transport passed 124;
interfaces/dispatcher passed 1,605; ordinary passed 4,642 with the same
four capability skips and 28 headed deselections. All 12 import contracts pass.
Existing original-oracle/headed evidence remains TS-R5/TS-R4 provenance; these
unchanged production gates were not rerun for the test/document correction.

Independent review used `claude-opus-5` at `xhigh` for two exchanges in the same
persisted session. Claude withdrew the protocol-rename and missing-lock claims
after checking authorization and the existing concurrent-close mutation witness;
it narrowed the Node claim to diagnostic quality and accepted the scoped fixes.
Initialization faults missed by the bypasses are detected by the replacements;
both Node gates' missing/invalid/launch/timeout witnesses remain non-skippable.
The settings closed-flag variant leaves early malformed-settings validation
unchanged; its constructor witness instead drops the runtime collaborator.
Failed or incomplete driver runs remain append-only evidence.

Review artifacts, exact Git status comparisons, and claim dispositions are in
`build/claude-review/ts-r2-r5-20260905-191946/`. CLI-reported list-price cost was
$20.565848. The first session violated read-only scope by creating then deleting
one temporary file; its attempted plan write was disabled. Git status before
and after was identical. The follow-up allowed only Read/Grep/Glob, with shell
and write tools disabled, and preserved its pre-existing dirty status.

## Artifact conventions and baseline evidence

Temporary evidence lives under ignored
`build/test-simplification/536915fb28068c141f59b2243119530205538b4d/`.
Use append-only run/probe directories; do not overwrite failures. Inventories
and mutation drivers are delivery evidence and retire at TS-R9. Copy only named
milestone/scenario evidence, with source/destination hashes; do not copy test
databases or installed runtimes.

| Gate | Evidence | Observation |
| --- | --- | --- |
| Original inventory | `inventory-20260904-133002-420` | 4,964 cases; original 27-file heuristic; builders 7/7/6 |
| Original ordinary | `ordinary-20260904-133009-887` | 4,932 passed, 4 capability skips, 28 deselected |
| Original imports | `imports-20260904-133428-243` | 12 kept, 0 broken |
| Original oracle | `oracle-20260904-133445-446` | 30 scenarios x 3 runs passed |
| Historical headed failure | `headed-20260904-133529-146` | 9 failed, 19 passed; preserved as superseded evidence |
| Repaired ordinary | `ordinary-final-20260905-four-families` | 4,941 passed, 4 established skips, 28 deselected |
| Repaired headed | `headed-final-20260905-four-families` | 28 passed, 4,945 deselected |
| Corrected inventory | `inventory-r0.json` | 4,964 original rows; 10 current-only witnesses; 1 superseded row; 28 support files / 18,738 lines; 24 JS/HTML files |
| Repaired references | `references-r0.json` | 21 execution-commit files frozen; 8 protected files unchanged |

TS-R0 routes 824 original rows to TS-R1, 919 to TS-R2, 641 to TS-R3,
1,102 to TS-R4, 949 to TS-R5, 95 to TS-R6, and 279 to TS-R8. The
remaining 155 database/settings rows are explicitly retained outside the
bounded reduction families and assigned to TS-R9 verification. The 20 builders
route 14 to TS-R2 and 6 to TS-R5. Every support file has a named code or
documented diagnostic consumer. TS-R3 adds `tests/_service_fixtures.py` and TS-R4
adds `tests/assets/_event_target.mjs`: the current delivery has 29 Python support
files and 25 JS/HTML files. These additions belong to TS-R8 consumer/fault review
and TS-R9 complete-machinery accounting; the baseline counts above stay frozen.

The superseded row is
`test_transport_gate_uia_subcommands_parse_their_exact_headless_shapes`; its
folder parsing responsibility remains in a renamed focused test and its UIA
source-spelling assertions were replaced by required behavioral witnesses.
After confirming the current branch contains those guarantees and neither ref
has a worktree, recovery branches
`codex/wip-20260904-2142-test-simplification` (tip `a1aa71c`) and
`codex/wip-20260904-2300-uia-observer` (tip `63b9fa9`) were deleted.
No working-tree files or ignored evidence were removed.

The original oracle semantic SHA-256 remains
`ada1a5f0e5987a2dade41931319d2535a3c9e72dcdbfa9a292964623fff4ecf3`.
SH-G-8 validators, baselines, and source closure are unchanged.

## Final commands

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

## Closed disposition

TS-R0 through TS-R9 are closed, including the conditional rejection/retention
path at R6/R7 and the bounded post-R5 correction. No checkpoint remains pending.
The original settlement checker remains active. New work requires its own scope;
this archived register does not authorize further implementation or Claude use.
