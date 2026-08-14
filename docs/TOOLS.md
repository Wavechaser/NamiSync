# Development Tools

`tools/` contains the development-only executor and verifier measurement
harness plus its deterministic corpus generator. Run it with
`python -m tools`. It is outside the shipped `namisync` package, but its safety
and result-validation behavior is covered by pytest.

## Measurement authority

`AGENTS.md` is the sole normative definition of the repository's measurement
tiers and escalation rules. Development tools declare which tier they serve,
keep observation separate from verdict, and refuse input shapes they cannot
account for. Compatible Tier 2 measurements may share one vertical-slice
harness; structural count tests or serializer round trips do not promote a
timing or memory target.

The existing SH-G-8 files remain frozen in place. When BR-G-45 or SH-G-15
becomes the second empirical Tier 3 consumer, shared `tools` support may extract
only canonical artifact/schema/digest checks, process isolation, source/runtime
receipts, verdict exclusion, and frozen-contract validation. Corpus generation,
root selection, measurement statistic, scaling axes, aggregate policy, and the
component validator remain component-owned.

## Boundary

The harness replaces the workflow and persistence edges while keeping the
domain operations real:

| Seam | Production | Tools |
| --- | --- | --- |
| `Recorder` | `db.recorder.SyncRunRecorder` | `LedgerlessRecorder` in memory |
| `IntegrityRecorder` | `db.recorder.LedgerRecorder` | `CapturingIntegrityRecorder` |
| `RunContext` | dispatcher fan-out | in-memory `Tape` |
| Execution selection | reviewed workflow plan | real scan, plan, and safe-subset derivation |
| Integrity selection | ledger inventory rows | fresh scan plus explicit evidence source |
| Filesystem, copy backend, reader | native | native inner, optionally instrumented |

Executor correspondence is intentionally empty. Executor measurements therefore
represent a first run with no retained history: COPY, UPDATE, NOOP, directory,
and deletion-policy operations are available, but MOVE and MOVE_UPDATE are not.
JSON output records `"correspondence": "empty"`. Adding invented mapping state
would make the harness less trustworthy; a move benchmark should be added only
with an explicit persisted-correspondence input contract.

The package may import `core`, `modules`, and the pure
`workflows.selection` helper. It does not import `db`, `dispatcher`,
`interfaces`, or workflow runtime composition.

## Executor settlement oracle

`tools/executor_settlement_audit.py` is a retained maintenance gate for the
executor settlement refactor. Unlike the measurement rig, it builds exact
small plans through core contracts, injects a synchronous copy backend and
public filesystem/recorder seams, and deliberately exercises success, failure,
retry, cancellation, cleanup, and recording outcomes. It imports the executor
only through the public `namisync.modules.executor` facade and does not import
planner, scanner, preflight, workflow composition, tests, or executor-private
symbols.

This is the deterministic-semantic Tier 3 form: the in-code oracle declares
expected truth independently, the committed baseline protects the complete
observed trace, and three fresh normalized runs must be identical. Numeric
calibration, headroom, and holdout are inapplicable; the common discipline is
protected observations plus independently declared acceptance.

```powershell
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit list
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit run failure.byte-published
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit oracle --repeat 3
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit snapshot --repeat 3
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit diff --repeat 3
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3
```

The portable resume gate is exactly:

```powershell
python -m tools.executor_settlement_audit check --repeat 3
```

For the current 30-scenario, 70-row manifest, a successful gate ends with
`settlement check passed: 30 scenarios x 3 runs`. `check` performs three fresh
complete captures, requires every in-code policy row to pass, requires the
three normalized traces to be byte-identical, and then compares that trace and
manifest with the clean baseline stored at `HEAD`. The default baseline's
canonical JSON also must match the separately reviewed semantic SHA-256 pinned
in the tool. Staged or unstaged changes to that file make the official check
fail; unrelated worktree changes do not. The command is read-only and never
refreshes the baseline.

The in-code oracle is independent of
`tools/executor_settlement_baseline.json`. Each manifest row declares its
expected terminal outcome, reason, recording state, durable-state detail,
recorder behavior, retry/control behavior, cleanup, evidence, and final tree.
Every installed filesystem fault rule must fire its declared number of times;
an unused or partly consumed rule invalidates the fixture. The cleanup matrix
includes failed pre-retry temp cleanup and proves it settles immediately as
`cleanup-failed`, without sleeping or entering another control checkpoint.
The observer matrices also pin restored MOVE/TRASH/DELETE subjects, a
disappeared committed MKDIR, unreadable DELETE/UPDATE state, and changed,
missing, or unreadable targets after confirmed publication. Three fail-closed
collaborator rows require a committed MOVE to settle from its original
operation error when failure policy or retry sleep raises, and a pending MKDIR
to finalize when the next checkpoint raises; the collaborator injection itself
must be consumed and its `RuntimeError` must still propagate.
The JSON baseline separately retains the complete normalized collaborator and
filesystem-boundary trace from the reviewed corrected-baseline lineage: 58
unchanged rows from the corrected monolith plus 12 independently reviewed
post-refactor stabilization rows. `check` requires both the policy oracle and
the committed trace to match; either can fail while the other passes.

`snapshot` requires at least three byte-identical complete runs, refuses every
oracle mismatch, writes atomically, and will not replace an existing baseline
unless `--replace` is explicit. `--baseline PATH` redirects snapshot and diff;
on `check`, a path other than the default is explicitly labeled as an unpinned
custom-baseline diagnostic and is not the resume gate. Resolving an alias of the
default path cannot bypass its Git and semantic-pin checks. A snapshot is never
an "accept current behavior" mechanism:
when the oracle exposes a policy defect, fix and document that defect in its
own commit, add its focused regression, restart the three-run gate, and only
then replace the corrected baseline in a separate checkpoint. Executor split,
journal, reducer, verifier, and test-consolidation commits run `check`; they do
not refresh the snapshot to make a difference pass.

After a reviewed policy correction expands or changes the baseline, commit the
replacement baseline and the explicit `REVIEWED_BASELINE_SHA256` update together
in one dedicated baseline-replacement commit, separate from the oracle or
behavior correction. Only then does the restarted three-run `check` establish
the new structural-refactor gate. This makes a baseline replacement visible
even if it accompanies an accidental behavior change.

Absolute roots, volatile timestamps, native identities, handles, and wall time
are removed from retained output. Symbolic paths preserve source/target/temp/
trash relationships, identity equality is retained without raw inode values,
and reliable event, recorder, retry, checkpoint, cleanup, and public
filesystem-call order remains exact. The manifest has no skip, expected-fail,
or unclassified state. A missing committed baseline is a hard `check` failure,
not permission to proceed. Keep the oracle and corrected baseline through final
refactor acceptance and at least the following settlement-hardening window.

The retained baseline currently uses `format_version: 1`. Executor package
splitting, effect-journal/reducer work, verifier splitting, and their immediate
stabilization commits must not edit or regenerate it. Only a separately
reviewed policy correction may produce a replacement, after its focused
regression and independent oracle expectations land and the three-run gate is
restarted.

## Workspace safety

Executor targets and generated corpora are tool-owned workspaces. A claim uses
two sibling files outside the measured tree:

- `<name>.rig-owned` is JSON bound to the resolved path, volume/device, and
  directory identity.
- `<name>.rig-lease` carries a tools signature and is locked exclusively for
  the active operation.

The tools refuse nonempty unowned directories, malformed or stale markers,
replaced directories, concurrent claims, filesystem roots, the home or current
directory, reparse-point substitution, unrecognized lease files, and anything
in or containing this repository. An empty unowned directory may be claimed
because it contains no user data. Mutating helpers require the live claim
object; marker- or lease-shaped files alone are not authority.

Markers remain after `generate` and after executor `--keep`, allowing the same
workspace to be safely regenerated or reused. `clean` removes a claimed tree
and its marker. Older unbound text markers are deliberately not adopted: inspect
their directory manually rather than treating them as deletion authority.

Templates and executor targets may not overlap in either direction. Template
walk errors fail the setup instead of producing a partial pre-state. JSON and
sidecar artifacts must be outside every measured/materialized root and may not
alias each other, a default sidecar, or ownership files. Existing output files
with multiple hard links are refused because a distinct path is not a distinct
artifact in that case.

## Executor measurements

```powershell
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --verify-readback
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --template E:\PreState --repeat 5 --json runs.jsonl
```

Without `--template`, every iteration starts with an empty target. A template
provides a repeatable target pre-state; setup time is reported separately from
scan, plan, preflight, and execution time.

Pipeline diagnostics are enabled by default in the tools while remaining off by
default in production. The harness samples each copy because
`NativeCopyBackend.last_metrics` retains only the most recent one. Reports
include reader blocking, writer starvation, payload high-water, reserved bytes,
chosen chunk sizes, and copy-backend wall time. `--no-metrics` disables both the
executor diagnostics and the per-copy timing wrapper.

Every selected operation must settle with a complete successful terminal
result whose typed items agree with the reviewed operation paths and outcomes,
non-degraded recording/audit, and complete invariant-valid published evidence.
A NOOP's normal `SKIPPED` outcome is accepted. Plans with safety exclusions and
any other failed, deferred, incomplete, or degraded sample are rejected and are
not appended to JSON.

`--verify-readback` prints its own result even without `--json`. Zero candidates
is valid for an all-NOOP/non-copy plan; otherwise every published candidate and
byte must verify with non-degraded recording.

## Verifier measurements

```powershell
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --mode baseline
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed --repeat 5
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --seed-baselines
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines sidecar
```

| `--baselines` | Setup | Required result | Detects pre-run drift |
| --- | --- | --- | --- |
| `primed` (default) | one in-process baseline pass | `VERIFIED` | no |
| `sidecar` | prior `--seed-baselines` pass | `VERIFIED` | yes |
| `synthetic` | deliberately wrong digest | `MISMATCHED` | no |
| `none` | no prior evidence | `BASELINED` | no |

Baseline and rebaseline modes require homogeneous `BASELINED` results.
Synthetic mismatch is an intentional successful measurement because comparison
happens only after the full read-and-hash loop. Every other mixed, shortened,
modified, erroneous, or degraded result invalidates the sample. Incomplete
scans, unsupported entries, and canonical-path collisions are refused before
measurement. Outcome IDs and final item/byte totals must exactly cover the
selection. Priming requires exactly one applied attestation per scanned file.

### Sidecars

The default sidecar is `<corpus>.baseline.jsonl` beside the corpus. Writes use a
same-directory temporary file and atomic replace. Loads require an explicit
format and identity mode, exact row schemas without duplicate JSON members,
XXH3-128 evidence, complete key coverage, and a fresh stat match through the
same pure core predicate used by verifier classification.

`portable` identity compares kind, size, and mtime and survives relocation.
`bound` additionally requires volume serial and file index for every row; it
never silently falls back to portable matching. Relocation must preserve
`mtime_ns`.

### Isolating hash cost

`--null-hasher` consumes every chunk but returns a constant digest. With primed
baselines, both passes use that same hasher and still reach `VERIFIED`:

```powershell
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed --null-hasher
```

Verifier sidecar plus `--null-hasher` is refused because a real sidecar and a
constant digest would create a misleading mismatch. `--no-tap` removes the
per-chunk reader timing when clean wall-clock measurements matter more than the
open/read split. The timing decorator forwards the authority-bound reader seam,
so enabling the tap cannot downgrade a reviewed native read to the unbound
custom-reader route. Its authority-bound subtype is used only when the wrapped
reader supports that protocol; the base tap preserves an unbound custom
reader's ordinary `open(root, path)` capability.

## Cache honesty

The verifier uses Windows unbuffered reads, so its numbers are cache-honest by
construction. Executor reads use the buffer cache; repeated reads of the same
source are warm and are not comparable to first-touch throughput.

## Corpus generation and cleanup

```powershell
.\.venv\Scripts\python.exe -m tools generate E:\Corpus "2000@4KiB,200@1MiB,4@256MiB" --seed 7
.\.venv\Scripts\python.exe -m tools clean E:\Corpus
```

Generation accepts a new or empty directory, or a directory carrying a valid
bound marker. Each run clears only that claimed root before writing, so the same
seed and specification produce the same complete tree without stale files.

`--repeat` must be positive. Accepted iterations print one summary and, with
`--json PATH`, append one JSON object. Unsafe configuration or an invalid sample
returns exit code 2 with an actionable error.

## Future integration boundary

No logger or product-CLI integration is appropriate yet. `M1_SHELL.md` defines
logging as a GUI-host facility under `interfaces/web`, consuming GUI paths and
capturing pywebview. Importing it here would invert the tools boundary and could
perturb measurements through rotation or concurrent log writers.

Keep `python -m tools` separate from `nami-sync`: the latter is a shipped product
surface with lazy GUI imports and reviewed domain workflows, while these tools
use fake persistence seams and destructive owned workspaces. If distribution is
later required, prefer a separate development entry point after an explicit
packaging and workspace-safety review.
