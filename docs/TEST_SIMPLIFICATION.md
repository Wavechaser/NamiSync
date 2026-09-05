# M1 Test Simplification

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
| TS-R3 | Simplify lifecycle, custody, service, observer, and drain tests | TS-R1 | Owner, concurrency, rollback, release, delivery | active |
| TS-R4 | Simplify desktop, browser, native, appearance, and cosmetic tests | TS-R1, TS-R3 | Required Node and installed headed witnesses | pending |
| TS-R5 | Simplify executor, verifier, recording, and compound workflows | TS-R1 | Existing oracle plus owner/native/integration faults | pending |
| TS-R6 | Build and evaluate a smaller shadow settlement oracle | TS-R5 | Frozen trace equality and rejection corpus | pending |
| TS-R7 | Adopt replacement or retain original with evidence | TS-R6 | Authority cutover or clean candidate removal | pending |
| TS-R8 | Remove orphaned support and residual top-file scaffolding | TS-R2 through TS-R7 | Consumer isolation and harness faults | pending |
| TS-R9 | Integrated verification and temporary-machinery retirement | all prior | Complete suite, headed, imports, active oracle, witnesses | pending |

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

### TS-R7 - Oracle disposition

For adoption, update `AGENTS.md`, `DEFENSE.md`, and executor/tool authority before
retirement, preserve `check --repeat 3` and provenance, and prove no retired
implementation import. For retention, remove candidate-only machinery with no
adopted detector and record the failed criterion. Adopt with
`test(executor): replace the procedural settlement oracle`; document retention
without claiming replacement.

### TS-R8 - Residual support and scaffold cleanup

Reinventory all 28 support files and repair-era support. Delete prior-checkpoint
orphans, then review remaining large files by obligation. Share child launch,
evidence reading, teardown, or fault mechanics only when ownership and failure
semantics match. Fault shared support before readiness and for missing or
contradictory evidence, teardown failure, absent capability, unrelated traffic,
and inert negative interception. Preserve SH-G-8 closure. Verify every consumer
alone, under department selection, and installed where required. Commit
`test: remove orphaned support and residual scaffold duplication`.

### TS-R9 - Integrated closeout

Replay the complete retained defect and allowed-variation corpora, verify no
overlapping reductions removed the last detector, required JS cannot skip,
approved seams preserve defaults, and protected identities remain unchanged.
Compare complete test/support/checker machinery including additions as a
diagnostic. Update the M1 consolidation changelog task, replace `HANDOFF.md`,
archive this register, and retire temporary inventory/mutation drivers. Commit
`docs: close the test simplification delivery` only after the final sweep.

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
documented diagnostic consumer.

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

## Resumption

- **Current:** TS-R0 through TS-R2 are complete; TS-R3 is active. TS-R4 through
  TS-R9 remain pending. Current collection is 4,657 rows.
- **Next:** normal service construction and lifecycle/custody detectors under
  TS-R3. Continue through TS-R5, then stop for the requested recap before TS-R6.
- **Protected:** original oracle/SH-G-8 identities, persisted/public behavior,
  and all ten headed-repair witnesses. TS-R2 did not change production or
  headed behavior; the 28/28 headed run remains execution-baseline evidence.
