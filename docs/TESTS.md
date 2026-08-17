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

### 5. Complete and headed release

Headed acceptance requires an interactive supported Windows desktop and the
real WebView2 host. Run the interface-owned headed gate when desktop behavior,
packaging, or headed harnesses change.
Readiness changes require focused coverage of the order-independent gate,
queued document-currentness check, exact bootstrap command policy, browser
supersession/retry behavior, and both degradable and unsafe native-surface
outcomes. Every headed page that performs startup must complete the neutral
challenge/echo protocol; an appearance envelope is not a substitute witness.
Positive custom pages use the shared browser bootstrap driver, and positive
host seams use the shared Python lifecycle driver and document channel. Keep
negative or renderer-only fault seams explicit so a helper cannot manufacture
their readiness evidence. Headed command additions use the shared immutable,
collision-refusing composition wrapper rather than rebuilding production rows.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces -o "addopts=" -m headed
```

Release evidence clears the configured ordinary-only default and runs every
collected test without a department filter.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
```

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
| `tools` | Repository diagnostics, audits, corpora, and test infrastructure |

When adding, moving, or deleting a collected test module, update
`tests/_departments.py` in the same change. Shared test support belongs in a
non-collected underscore-prefixed module rather than another collected test
module. No Python source under `tests/` may import a collected test module.

## Markers and skips

- `headed` requires the real interactive desktop host. It is excluded by the
  configured `-m "not headed"` ordinary default. A filename containing
  `headed` does not determine marker behavior; some headed-harness modules also
  contain ordinary contract tests.
- `supplemental_node` identifies optional deterministic JavaScript probes. They
  may skip when Node.js is unavailable and do not replace native or headed
  acceptance evidence.
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
