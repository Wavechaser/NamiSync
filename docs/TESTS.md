# Tests

NamiSync uses pytest for behavioral verification and import-linter for package
boundaries. Test modules have one primary architectural owner recorded in
`tests/_departments.py`. That executable manifest, not this document, is the
authority for exact module membership.

Departments route routine verification. They do not claim that a change can
affect only its primary owner. Changes to public contracts add the affected
consumer departments explicitly; uncertain or broad changes use the ordinary
repository suite.

## Run levels

### 1. Focused

Use an exact node or file while editing and diagnosing a failure.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_executor_runtime.py::test_executor_rejects_a_nonpositive_maximum_chunk
.\.venv\Scripts\python.exe -m pytest -q tests\test_executor_runtime.py
```

Run focused verification after each local change. It is not handoff evidence
when the change affects a wider component.

### 2. Department

Run the primary owning department before handing off or committing a local
change.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --dept executor
```

`--department` is the equivalent long spelling of `--dept`.
When combined with explicit files or nodes, the department remains a filter;
items owned by other departments are deselected.

### 3. Cross-department neighborhood

Name both producers and consumers when a public contract crosses ownership
boundaries. Repeated department options form a union.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --dept executor --dept workflows
.\.venv\Scripts\python.exe -m pytest -q --dept workflows --dept interfaces
```

Use an explicit neighborhood for shared payloads, views, events, persistence
contracts, or composition behavior. Selection never expands dependencies
automatically.

### 4. Ordinary repository

The configured default runs every ordinary test and excludes tests marked
`headed`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run it for phase integration, global fixtures or pytest configuration, the
department manifest, broad shared contracts, uncertain blast radius, and before
considering a non-headed phase complete.

Required ordinary JavaScript tests are unmarked and non-skippable. They execute
the packaged public event consumers, start-plan deadline/replay and interactive
bridge wrappers, and the production drain-manager live-event
transport/replay and Progress reducer. Node.js must be available through
`NAMISYNC_TEST_NODE` or `PATH`; the explicit environment setting takes
precedence. A missing or unusable executable fails these gates rather than
silently reducing the ordinary suite to source-text inspection. The drain probe
executes the packaged transport check and proves whole-batch rejection: an
invalid event envelope, wrapper, lifecycle transition, or reducer transition
cannot partially deliver co-batched reliable updates or advance the accepted
cursor, and a clean replay delivers those reliable updates. It also
executes the Progress reducer across reliable phase authority, numeric holes,
Gap recovery without retained `PhaseChanged` (including a newer self-described
phase in the retained tail), retry attempts, overshoot,
aggregate and attempt regression refusal, reliable outcome/Terminal
precedence, compound post-copy identity, immutable callback projections, and
bridge reincarnation cursor recovery. Its deferred-directory handoff case is a
cross-boundary fixture: the public Python executor emits real envelopes through
the lossy event subscriber and exact `SessionEventView`, then the packaged
JavaScript reducer accepts the coalesced direct change from directory activity
to child-copy activity without treating it as settlement. These are behavior
checks against production producers and the packaged JavaScript, not
source-text witnesses.

Current boundary guards divide responsibilities instead of running one event
graph through duplicate semantic validators. Persistence-decoder tests reject
wrong-version, noncanonical `Scalar64`, Boolean-as-integer, exact-shape, and
cross-field corruption before returning a stored value. Producer tests pin the
exact reliable-envelope maximum and first excess before `EventHub` mutation;
the exact maximum event drains alone. Browser tests admit all seven canonical
producer projections, then atomically reject invalid transport version,
session, sequence, tag, body-object, lifecycle, or reducer input without
advancing the cursor; clean replay remains exact. History-v6 pages cannot carry
a prior event version. The consolidation closeout search found no downstream
event-body certifier; retained core guards pin prior, future, and coercive
version rejection through the public validator/decoder and require the exact
persisted shape. Private helper names are not test authority.

```powershell
$env:NAMISYNC_TEST_NODE = 'C:\path\to\node.exe'
.\.venv\Scripts\python.exe -m pytest -q
```

### 5. Complete and headed release

Headed acceptance requires an interactive supported Windows desktop and the
real WebView2 host. Run the interface-owned headed gate when desktop behavior,
packaging, or headed harnesses change.
Readiness changes require focused coverage of the order-independent gate,
queued document-currentness check, exact bootstrap command policy, browser
supersession/retry behavior, and both degradable and unsafe native-surface
outcomes. Every headed page that performs startup must complete the neutral
challenge/echo protocol; an appearance envelope is not a substitute witness.
Positive custom pages use `bootstrapTestBridge()` from
`tests/assets/bootstrap_test_bridge.js`; positive host seams use
`drive_startup_handshake()` from
`tests/interfaces/web/_startup_test_support.py` and its test document channel.
Keep negative or renderer-only fault seams explicit so a helper cannot
manufacture their readiness evidence. Headed command additions use that
module's shared immutable, collision-refusing `headed_command_extension()`
rather than rebuilding production rows.

Headed subprocesses publish lifecycle evidence through the tests-only immutable
milestone protocol owned by `tests/interfaces/web/_headed_evidence.py` and its
`EvidencePublisher`/`EvidenceReader`. A child may publish one `ready.json` or
`failure.json`, then one `final.json`; each is canonical JSON written completely
to a private same-directory temporary and published without replacement.
Parents poll names,
read each published milestone once, cache it, and reject contradictions, late
milestone names after an observed final, noncanonical records, or orphan
protocol temporaries. Final-only evidence requires an explicit reader opt-in
and is reserved for completion or expected-refusal witnesses that have no
interactive ready phase. The
1 MiB record ceiling is a tests-only anti-runaway ingress bound, not a product
request or acceptance limit. Benchmark reports remain separate atomic
per-invocation measurement artifacts; retained baseline sidecars are distinct
input evidence. Neither is a live child-to-parent snapshot or part of the
milestone state machine. The tree-window fixture likewise remains a one-shot
parent-created input.

`tools/gui.ps1 gallery` reuses the child and milestone format for an editable
manual preview, but its GUID-named output is diagnostic only. It is not produced
from the clean installed wheel, is not parent-validated as an acceptance run,
and cannot satisfy a headed gate. A normal preview removes only its
ownership-marked, exact ready/final diagnostic set after revalidation; abnormal,
changed, or unknown output is retained for operator inspection.

A green headed result proves only its declared NamiSync/page contract; it is not
evidence that the surrounding Windows compositor remained healthy. A headed
acceptance run completed green while the same Windows session contained a DWM
restart, which the child/page evidence protocol could not see; `BUGS.md` owns
the exact incident record and does not attribute causality to NamiSync. A shared
current-session DWM sentinel is accepted but unrealized. When active, it will
bracket headed runs, detect a compositor restart independently of child/page
success, and report event-log or GPU/TDR evidence without conflating temporal
overlap with cause. Until then, compositor health is an explicit evidence
limitation rather than an inferred pass.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces -o "addopts=" -m headed
```

Release evidence clears the configured ordinary-only default and runs every
collected test without a department filter.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
```

## Accepted-target verification

Accepted but unrealized M1 Stage 6 contracts are neither current behavior nor
acceptance evidence. `M1_SHELL_H2.md` is the current delivery plan where it
overlaps `M1_SHELL.md`; its acceptance/test clauses and the referenced
`M1_BRIDGE.md` gates own the target cases. Do not reproduce delivery, command,
module, or case catalogs here.

While implementing an accepted target, run focused tests, every affected
producer and consumer department, and the ordinary suite when a public contract
crosses departments. Exact primary ownership remains only in
`tests/_departments.py`. Surface work also runs the real installed WebView2
witnesses with default addopts cleared. Quantitative evidence follows
`DEFENSE.md`; a benchmark is not acceptance merely because it ran.

## Departments

| Department | Primary ownership |
|---|---|
| `core` | Shared contracts, protocols, path safety, evidence, and session state |
| `scanner` | Filesystem discovery and scan completeness |
| `planner` | Plan derivation and operation ordering |
| `preflight` | Pre-execution admission and refreshed safety checks |
| `executor` | Native mutation, pipeline, runtime, and settlement |
| `verifier` | Integrity classification and cache-honest native reading |
| `database` | Schema, repositories, recorder, and settings persistence |
| `workflows` | Cross-component sync and integrity coordination |
| `dispatcher` | Admission, custody, control, and event fan-out |
| `interfaces` | CLI, service, launcher, packaging, and desktop adapters |
| `tools` | Repository diagnostics, audits, corpora, development launchers, and test infrastructure |

When adding, moving, or deleting a collected test module, update
`tests/_departments.py` in the same change. Shared test support belongs in a
non-collected underscore-prefixed module rather than another collected test
module. No Python source under `tests/` may import a collected test module.

Tests that isolate `NamiSyncService` with explicit runtime, dispatcher, or
observer collaborators use `tests/_service_fixtures.py` to construct the real
service at the existing composition points. Constructor-owned state is not
copied into test helpers; scenario-specific lifecycle and malformed-boundary
state remains explicit.

## Markers and skips

- `headed` requires the real interactive desktop host. It is excluded by the
  configured `-m "not headed"` ordinary default. A filename containing
  `headed` does not determine marker behavior; some headed-harness modules also
  contain ordinary contract tests.
- `supplemental_node` identifies optional deterministic
  JavaScript probes. They may skip when Node.js is unavailable and do not
  replace native or headed acceptance evidence. They use the same
  `NAMISYNC_TEST_NODE`-then-`PATH` resolution as the required ordinary tests,
  which are deliberately unmarked and cannot skip.
- Other skips must name a concrete unavailable platform capability. Review
  skip reasons in verification output; a skipped required gate cannot sign off
  that gate.

## Diagnostics

Rerun prior failures first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --lf
.\.venv\Scripts\python.exe -m pytest -q --ff
```

Inspect collection or collect timing evidence without turning it into an
acceptance threshold:

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
.\.venv\Scripts\python.exe -m pytest -q --durations=25 --durations-min=0.05
```

Show skip reasons for a selected run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs --dept tools
```

The suite remains serial by default. Do not introduce a default xdist worker
count without a separate benchmark and native-resource collision review.
