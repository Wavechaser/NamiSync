# Development Tools

`tools/` contains two distinct development-only surfaces. `python -m tools`
owns the executor/verifier measurement harness and deterministic corpus
generator. `tools/gui.ps1` is a standalone editable-source desktop convenience
launcher. Neither is part of the shipped `namisync` package, and both are
covered by pytest without turning their output into product acceptance.

## Editable GUI launcher

Use PowerShell 7 and the repository virtual environment for ordinary UI
iteration. Windows PowerShell 5.1 is refused before the launcher runs:

```powershell
# Real development shell
.\tools\gui.ps1

# Component gallery; dark when -Mode is omitted
.\tools\gui.ps1 gallery
.\tools\gui.ps1 gallery -Mode light
.\tools\gui.ps1 gallery -Mode dark
.\tools\gui.ps1 gallery -Mode forced
.\tools\gui.ps1 gallery -Mode reduced

# Grouped gallery profiles
.\tools\gui.ps1 gallery -Mode fluent  # light + dark
.\tools\gui.ps1 gallery -Mode all     # all four modes
```

Bare `gui.ps1` always selects the real shell. `gallery` defaults to `dark`, and
explicit `gallery -Mode dark` selects the identical child, mode, data root,
mutex, title, and scenario. `-Mode` without `gallery`, an unknown command, an
unknown mode, and extra arguments are refused before launch. `fluent` expands
to light and dark; `all` expands to light, dark, forced, and reduced.

The launcher resolves the repository from its own path, uses only
`.venv\Scripts\python.exe`, and verifies under isolated Python startup that
`namisync` resolves inside this checkout. It never builds a wheel, creates or
cleans an environment, falls back to a PATH interpreter, watches files, or
implements hot reload. Source changes take effect on the next manual relaunch.

The real shell enters the normal secured `run_desktop` composition through the
existing test-owned headed child with a development-only identity:
`Local\NamiSync.Development.Desktop` and `NamiSync [Development]`. Each gallery
mode has its own corresponding development mutex/title and invokes the existing
`_component_gallery_child.py` with the test-owned
`tests/assets/component_gallery/gallery.js` scenario. Production launcher
arguments, the production `Local\NamiSync.Desktop` mutex and `NamiSync` title,
packaged assets, and both clean-wheel children remain unchanged.

Data is persistent and isolated beneath
`%LOCALAPPDATA%\NamiSync-Development`: `shell` for the real development host and
`gallery\<mode>\data` for each gallery mode. A launcher-control mutex refuses a
second wrapper for the same concrete mode, and a child mutex already held at the
pre-launch check is refused rather than treated as a window this invocation
opened. There is no global gallery mutex: light, dark, forced, and reduced may
run alongside one another, but a second instance of the same mode is refused.
The real shell keeps its separate existing launcher/child mutexes.

Grouped profiles acquire the same concrete per-mode launcher mutexes in fixed
light/dark/forced/reduced order. `fluent` therefore reserves only light and
dark and may coexist with forced or reduced; `all` reserves all four. Every
selected child-mutex precheck completes before any grouped child starts. The
launcher then starts every selected GUI process before waiting, waits on those
exact process objects, and never enumerates, waits for, or terminates processes
by image name.

Before every launch the console prints the source, interpreter, data, and log
paths plus the gallery scenario and diagnostic output when applicable. The
window remains open until the operator closes it; the clean-wheel pytest parent,
not the gallery child, is what normally closes a gallery after `ready`. After
every window in the selected profile closes, Enter relaunches that same profile
and Q quits.

Gallery data remains stable, but each launch receives a fresh GUID-named
diagnostic directory and a random ownership marker. After a normal ready/final
lifecycle, cleanup requires that marker, the exact three-entry set, regular
non-reparse files, and unchanged reviewed file stats. Successful cleanup prints
one receipt for the selected profile:

```text
Exit [dark]: exit code 0; generated diagnostics removed.
Exit [fluent]: exit code 0 on 2/2; generated diagnostics removed.
Exit [all]: exit code 0 on 4/4; generated diagnostics removed.
```

The cleanup plan, each exact file/marker/directory removal, and final removal
confirmation are available through PowerShell's `-Verbose` stream. They are
hidden during routine success because the resolved `%LOCALAPPDATA%` paths were
already printed before launch. This changes presentation only: the ownership,
entry-set, identity-revalidation, and nonrecursive-deletion checks remain
mandatory.

A partial cleanup stays explicit on the normal warning stream: it prints the
gallery mode, exit/status reason, retained diagnostic directory, completed
paths, and whether the root and marker remain. Any unknown entry, replaced
marker, changed file, or cleanup error retains the remaining directory. A
nonzero exit, published failure, missing ready/final diagnostic, malformed or
mismatched final record, or post-ready failure likewise names the failed mode,
retains its diagnostic directory, and prints a bounded 80-line log tail.
The clean-wheel parent remains the only complete evidence validator. The
console labels an unchanged persistent log as old rather than attributing it to
the failed launch; an unreadable log warns without bypassing the relaunch prompt.

This is a dirty editable preview for interaction speed. Its manual interaction
observations and logs are diagnostics, not clean-wheel, release, headed-gate, or
compositor-health evidence. Use the commands in `TESTS.md` for acceptance.

## Measurement authority

`DEFENSE.md` §7 is the sole normative definition of the repository's
measurement tiers and escalation rules. Development tools declare which tier
they serve, keep observation separate from verdict, and refuse input shapes
they cannot account for. Compatible Tier 2 measurements may share one vertical-
slice harness; structural count tests or serializer round trips do not promote
a timing or memory target.

Executor throughput/pipeline timings and verifier throughput/read timings are
Tier 0 diagnostics: they vary with the runtime, storage topology, cache state,
and concurrent load, and no shipped NamiSync boundary accepts or rejects work
from these numbers. Repetition, structured output, and drift checks make the
observations more interpretable; they do not promote them into release evidence
or a performance gate.

The existing SH-G-8 transport-custody authority remains frozen in place as an
accepted historical exception, not a template. Its fixed corpus and structural
sizer form a deterministic calculation; identical fresh children strengthened
provenance but supplied no statistical power. It and the Tier-1 live check guard
only the named realistic corpus, not a complete-domain hard wall. Do not extend
or recalibrate that v1 apparatus by default.

When a current event representation changes without changing the named scale
axes, correct the live fixture, preserve the frozen calibration/holdout/ceiling,
and rerun the installed-wheel event harness plus the one-child Tier-1 custody
guard from clean committed source. Record the live drift and its ceiling margin;
passing that guard is regression evidence, not a new calibration or acceptance
artifact.

The former BR-G-45 complete-graph model is retired and is retained only as
historical provenance. Active tools preserve the runtime request/population
bounds and the evidence authorities named by `DEFENSE.md`; no aggregate graph
reservation or owner census is required for a future task surface.
SH-G-15 owns scoped cold-start resource and repeated/long-workload leak/growth
acceptance under DEFENSE section 7; runtime dependence alone does not require
a universal containment model or a new calibration for every version. Shared `tools`
support may be extracted for an actual empirical consumer, but only for
canonical artifact/schema/digest checks, process isolation, source/runtime
receipts, verdict exclusion, and frozen-contract validation. Corpus generation,
root selection, measurement statistic, scaling axes, aggregate policy, and the
component validator remain component-owned.

## Measurement harness boundary

The harness replaces the workflow and persistence edges while keeping the
domain operations real:

| Seam | Production | Tools |
| --- | --- | --- |
| `Recorder` | `db.recorder.SyncRunRecorder` | `LedgerlessRecorder` in memory |
| `IntegrityRecorder` | `db.recorder.LedgerRecorder` | `CapturingIntegrityRecorder` |
| `RunContext` | dispatcher fan-out | in-memory `Tape` |
| Execution selection | reviewed workflow plan | real scan, plan, and safe-subset derivation once per reusable empty-target batch, or once per sample for mutable target pre-states |
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

The in-code oracle also carries a typed recording projection for the exact
seven protected rows recorded by [archived recording acceptance](obsolete/M1_SHELL_H2.md); that catalog
is part of the fail-closed manifest. Before normalization, an oracle-only side channel
snapshots authoritative production `ExecutionSet.status`,
`recording_reasons`, `recording_issues`, and aggregate recording alongside the
typed reliable-item order. The projection keeps filesystem, item recording,
task recording issues, and aggregate recording as separate axes, and rejects
cross-axis combinations that could relabel a filesystem outcome or assign task
degradation to an item.

The side channel is removed only after the independent oracle validates it and
before normalized capture. Separately, `_oracle_item_detail` and
`_oracle_item_reason` remain explicit historical event-v4 trace adapters for
the frozen normalized report. Those adapters protect trace compatibility; they
are not recording-attribution authority. The normalized trace, JSON baseline,
and current event contract therefore remain unchanged.

`snapshot` requires at least three byte-identical complete runs, refuses every
oracle mismatch, writes atomically, and will not replace an existing baseline
unless `--replace` is explicit. `--baseline PATH` redirects snapshot and diff;
on `check`, a path other than the default is explicitly labeled as an unpinned
custom-baseline diagnostic and is not the resume gate. Resolving an alias of the
default path cannot bypass its Git and semantic-pin checks. A snapshot is never
an "accept current behavior" mechanism:
when the oracle exposes a policy defect, fix and document that defect in its
own commit, add its focused regression, restart the three-run gate, and only
then replace the corrected baseline in a dedicated reviewed commit. Executor
split, journal, reducer, verifier, and test-consolidation commits run `check`;
they do not refresh the snapshot to make a difference pass.

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

The retained baseline still uses tool `format_version: 1`; that number is not
the core event schema. Its reviewed projection now projects and protects the
integrated consequences of the historical core-event-v4 phase and attempt lifecycle, live
control-boundary aggregates/path, continuation byte high-water, and
reliable-outcome item counts. Opaque attempt ids are normalized
by first-seen lifecycle ordinal, and a retired token may not resurrect. Future
executor/verifier restructuring must not edit or regenerate the baseline.
Only a separately reviewed policy correction may produce another replacement,
after its focused transition regression and independent oracle expectations
land and the three-run gate is restarted.

## Workspace safety

Executor targets and generated corpora are tool-owned workspaces. Their control
and output evidence lives in sibling files outside the measured tree:

- `<name>.rig-owned` is JSON bound to the resolved path, volume/device, and
  directory identity.
- `<name>.rig-lease` carries a tools signature and is locked exclusively for
  the active operation.
- `<name>.rig-outputs.json` binds the exact paths and filesystem identities
  created by the last complete generator, materializer, or executor sample.

The output manifest is one ordinary single-link, non-reparse JSON file with a
bounded size, exact schema, duplicate-key rejection, sorted unique entries, and
root path/device/inode binding. Its atomic replacement revalidates the prior
occupant identity; malformed, oversized, hard-linked, replaced, or misbound
manifests never authorize deletion.

The tools refuse nonempty unowned directories, malformed or stale markers,
replaced directories, concurrent claims, filesystem roots, the home or current
directory, any requested workspace alias or generic reparse point, unrecognized
lease files, and anything in or containing this repository. CLI admission keeps
the requested absolute workspace path until this check, so resolving a junction
before `claim` cannot erase the evidence. An empty unowned directory may be
claimed because it contains no user data. Mutating helpers require the live
claim object; marker- or lease-shaped files alone are not authority.

The root marker proves only the directory boundary; it does not claim every
descendant later placed there. Automatic reset and teardown first inventory the
whole root without following reparse points. Every current path must appear in
the output manifest; files must retain their full recorded identity and stat,
directories must retain identity, and hard-link count must not drift. Unknown,
replaced, modified, hard-linked, unreadable, or reparse entries refuse cleanup
before mutation. The immutable plan printed to the operator is passed to the
mutation seam; the complete live tree is compared with that exact plan again
immediately before the first unlink. Passing a plan is not authority: an exact
plan must re-bind to the expected output-manifest path and identity, and every
entry must still be vouched for by that manifest. A path arriving after
inspection is therefore refused rather than adopted into a second deletion
set. Missing expected entries are tolerated when a new plan is inspected so an
interrupted cleanup can be retried. Files are revalidated and unlinked
individually, then
identity-matched directories are removed deepest-first with `rmdir`; there is
no recursive catch-all in the automatic path.

Before every reset, teardown, or `clean`, the console prints the resolved root,
manifest or explicit authority, and file/directory/byte counts. `--force-all`
also prints every sorted relative path and kind because no manifest vouches for
that set. A second receipt states exactly what was removed and whether the root
and marker remain. Reset completion is printed before generator or template
population starts, so a later write failure cannot hide an already completed
deletion. Failed executor batches call the live manifest validator before
describing output as exact and print the exact recovery command; mere sibling
file existence is never called authority. `--keep` prints both workspace and
manifest paths. Every partial-cleanup error reports completed counts and paths,
plus retained root, marker, or manifest state.

Markers and output manifests remain after `generate` and executor `--keep`, so
known outputs can be regenerated or cleaned exactly. `clean --dry-run` prints
the same boundary without mutation. A marker-only, partial, or legacy nonempty
workspace is preserved by ordinary `clean`; after inspecting it, the operator
may use `clean TARGET --force-all`, which still requires the valid root-bound
marker and lease, inventories and prints the whole deletion set, applies only
that displayed plan, and refuses reparse content or late arrivals. A malformed
or stale sibling output manifest is preserved rather than guessed or deleted;
the completion receipt names it and says it must be inspected and removed
explicitly before that workspace name is reused. Older unbound text markers are
never adopted.

The manifest intentionally records identity and stat rather than hashing every
file again before deletion. Deliberate same-inode byte modification followed by
complete metadata restoration is therefore outside this development guard.
Each path is revalidated immediately before deletion and the root is inventoried
again afterward, but pathname deletion still has a small concurrent-substitution
window; use a quiescent dedicated rig root.

Templates and executor targets may not overlap in either direction. Template
walk errors fail the setup instead of producing a partial pre-state. JSON and
sidecar artifacts must be outside every measured/materialized root and may not
alias each other or reserved marker, lease, or output-manifest paths. Artifact
aliases and generic reparse points are refused before resolution. Existing
output files with multiple hard links are refused because a distinct path is
not a distinct artifact in that case.

## Executor measurements

```powershell
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --repeat 5
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --prepare-each --repeat 5
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --template E:\PreState --verify-readback
```

Without `--template`, the default repeated benchmark prepares one static plan
in memory. The target must be empty and the selected plan may contain only
MKDIR and absent-target COPY operations. The harness first performs an exact
owned-target reset, then scans, plans, and selects once. Every sample receives a
fresh `ExecutionSet`, run ID, event tape, recorder, backend, and filesystem
adapter. Unless `--no-preflight` is explicit, the first fresh set is preflighted
immediately before execution; later samples reset the target and execute a new
set without replanning or re-preflighting. Execution time still covers the
complete public executor call, including copy publication, metadata, recording,
and final directory finishing. Output-manifest validation/publication and reset
receipts happen outside `execute_seconds`.

Every repeated sample must publish the same operation-keyed digest and size
evidence. After the last sample the harness rescans the source and requires the
complete source snapshot to match preparation; any membership, identity, stat,
or digest drift invalidates the batch. The plan is never serialized. Use
`--prepare-each` to rescan, replan, and preflight every empty-target sample.
Template workloads always prepare each sample because rematerialization changes
target identities; update, delete, NOOP, and other target-dependent plans are
therefore never fed through the static-plan path. Template setup time is
reported separately from scan, plan, preflight, and execution time. Supplying
`--prepare-each` with `--template` is refused because it would be a misleading
no-op.

The executor's published digest comparison detects same-stat content changes
between samples. Content changed after preparation but before the first sample,
with all scanned stat fields deliberately restored and then held stable, is not
distinguishable without another full plan-time content read; use a quiescent
source corpus.

Pipeline diagnostics are enabled by default in the tools while remaining off by
default in production. The harness samples each copy because
`NativeCopyBackend.last_metrics` retains only the most recent one. Reports
include reader blocking, writer starvation, payload high-water, reserved bytes,
chosen chunk sizes, and copy-backend wall time. `--no-metrics` disables both the
executor diagnostics and the per-copy timing wrapper. With diagnostics enabled,
each accepted sample prints copy count and bytes, summed backend wall time,
executor time outside the copy backends, summed reader-blocked and
writer-starved time, maximum payload high-water, reserved bytes, and the
distinct chunk sizes used. Detailed metrics therefore remain useful without a
JSON report.

Every selected operation must settle with a complete successful terminal
result whose typed items agree with the reviewed operation paths and outcomes,
non-degraded recording/audit, and complete invariant-valid published evidence.
A NOOP's normal `SKIPPED` outcome is accepted. Plans with safety exclusions and
any other failed, deferred, incomplete, degraded, or drifted sample invalidate
the whole batch.

All accepted raw samples are retained in order without report-time rounding.
For repeated runs the console prints N, minimum, median, and maximum execution
time plus the median of the per-sample throughput values. No percentile,
outlier deletion, or implicit warm-up discard is applied.

`--verify-readback` prints its own result even without `--json`. Zero candidates
is valid for an all-NOOP/non-copy plan; otherwise every published candidate and
byte must verify with non-degraded recording.

### Benchmark reports

Console output is the artifact-free default. `--json PATH` opt-in publishes one
versioned JSON document for the complete valid invocation, not one JSONL row per
sample. The envelope separately owns configuration, one-time batch preparation,
post-batch validation, ordered raw samples, and the N/minimum/median/maximum
summary; static-plan samples do not duplicate scan, plan, or preflight time. It
also records the plan and policy fingerprints. The document is written to a
private same-directory temporary, flushed, and atomically renamed only after
every sample and drift check succeeds. Executor reports are published only
after exact workspace cleanup succeeds, except that explicit `--keep` retains
the validated manifest-owned workspace and records that choice before report
publication. A failed later sample or required cleanup leaves no final or
partial report.

The destination is create-exclusive. An existing ordinary single-link file is
preserved unless `--replace-report` is explicit, and its identity is revalidated
immediately before atomic replacement. The exact published path is printed.
There is no implicit append, rotation, time-based deletion, or report cleanup;
the operator chooses the path and retention period.

A quantitative claim must retain the report together with the source fixture
(including generator specification and seed when applicable), source/target
roots, empty-target/static-plan profile, operation mix, correspondence,
deletion/preflight/diagnostic flags, runtime/dependency versions, OS, concurrent
load, and storage/device topology. Relevant scaling axes are file count, size
distribution and total bytes, directory shape, operation mix, source/target
device topology, and repeat count; chunk or memory settings are axes only when
varied. The report records rig configuration and raw samples, but it cannot
discover every environmental receipt automatically.

## Verifier measurements

```powershell
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --mode baseline
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed --repeat 5
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --seed-baselines --sidecar E:\RigEvidence\corpus.baseline.jsonl
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines sidecar --sidecar E:\RigEvidence\corpus.baseline.jsonl
```

For `--mode verify`, the evidence-source matrix is:

| `--baselines` | Setup | Required result | Batch fixture anchor |
| --- | --- | --- | --- |
| `primed` (default) | one in-process baseline pass | `VERIFIED` | priming evidence |
| `sidecar` | prior `--seed-baselines` pass | `VERIFIED` | validated sidecar evidence |
| `synthetic` | deliberately wrong digest | `MISMATCHED` | setup scan |
| `none` | no prior evidence | `BASELINED` | first accepted sample |

Baseline mode always runs bare despite the parser's default baseline-source
value. Baseline and rebaseline modes require homogeneous `BASELINED` results;
when rebaseline is given an evidence source, that source still anchors its
fixture even though the new attestations are the measured output.
Synthetic mismatch is an intentional successful measurement because comparison
happens only after the full read-and-hash loop. Every other mixed, shortened,
modified, erroneous, or degraded result invalidates the sample. Incomplete
scans, unsupported entries, and canonical-path collisions are refused before
measurement. Outcome IDs and final item/byte totals must exactly cover the
selection. Priming requires exactly one applied attestation per scanned file.
Every measured scan must have the same canonical keys and stat subjects as its
setup evidence, or as the first sample when no setup evidence exists. Primed
and synthetic in-process anchors require exact `FileStat` equality; a sidecar
uses its declared portable or bound core matching predicate. This
closes the gap between a priming/sidecar scan and the timed pass instead of
allowing a shorter corpus to remain all-`VERIFIED`. For baseline, rebaseline,
and no-baseline verification, every repeated sample must also produce identical
operation-keyed content evidence, detecting same-stat content drift after the
first sample when the real hasher is active. `--null-hasher` deliberately makes
that content evidence constant for hash-cost isolation, so its source must stay
quiescent; stat and membership drift still refuse. Any detected fixture drift
invalidates the whole batch and suppresses its report.

Reader instrumentation remains enabled by default. Each accepted sample prints
open time, read time, and verifier time outside those calls; `--no-tap` removes
that split. Repeated verifier batches print N, minimum, median, and maximum run
time plus median sample throughput. Baseline preparation is labeled and timed
separately as setup, not silently counted as a sample. Reports retain that setup
receipt, and sidecar-backed reports include the explicit path, validation
counts, and stored identity mode.

### Sidecars

Baseline persistence is separate retained input evidence, not benchmark output.
Both `--seed-baselines` and `--baselines sidecar` require an explicit `--sidecar
PATH`; the CLI never infers `<corpus>.baseline.jsonl`. A seed write uses a
same-directory temporary and create-exclusive atomic publication. Existing
sidecars are preserved unless `--replace-sidecar` is explicit. Replacement
captures the ordinary single-link destination identity before the potentially
long priming pass and revalidates that same occupant immediately before atomic
publication; a file swapped in during priming is preserved and refused.
Workspace `clean` never guesses or removes a sidecar.

Seeding is a distinct evidence-creation action. It runs exactly one untapped
baseline pass and rejects incompatible repeat, mode, baseline-source, tap, and
report settings instead of silently ignoring them. `--identity` and
`--replace-sidecar` apply only to seeding.

Loads require an explicit format and identity mode, exact row schemas without
duplicate JSON members, XXH3-128 evidence, complete key coverage, and a fresh
stat match through the same pure core predicate used by verifier classification.
The active `namisync-rig-baseline-2` format stores a bound Windows file index as
canonical `FileIndex128` decimal text, never a JSON number. Version-1 sidecars
are refused at the format boundary and must be reseeded explicitly.

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
source are warm and are not comparable to first-touch throughput. A static-plan
batch is specifically a buffered repeated-source/warm-profile observation; the
preparation reuse does not make it a cold or first-touch benchmark.

## Corpus generation and cleanup

```powershell
.\.venv\Scripts\python.exe -m tools generate E:\Corpus "2000@4KiB,200@1MiB,4@256MiB" --seed 7
.\.venv\Scripts\python.exe -m tools clean E:\Corpus --dry-run
.\.venv\Scripts\python.exe -m tools clean E:\Corpus
.\.venv\Scripts\python.exe -m tools clean E:\LegacyRigWork --force-all
```

Generation accepts a new or empty directory, or a directory carrying a valid
bound marker plus an exact output manifest. Each successful run publishes the
generated file and directory set into that manifest. Regeneration removes only
the validated recorded set, so the same seed and specification produce the same
complete tree; an unlisted descendant refuses replacement and is preserved.

Ordinary `clean` requires an existing valid marker and either an empty root or
an exact output manifest. It never creates or adopts a workspace merely because
the command was given a path. Reports and verifier sidecars are operator-owned
artifacts outside the root and are never guessed or removed by workspace
cleanup.

`--repeat` must be positive. Accepted iterations print their raw summary and a
repeated batch prints its aggregate. `--json PATH` writes the one atomic batch
report described above. Unsafe configuration or an invalid sample returns exit
code 2 with an actionable error and publishes no report.

## Measurement integration boundary

No logger or product-CLI integration is appropriate for the measurement
package. `INTERFACES.md` defines logging as a GUI-host facility under
`interfaces/web`, consuming GUI paths and capturing pywebview. Importing it into
the Python harness would invert the measurement boundary and could perturb
results through rotation or concurrent log writers. The standalone `gui.ps1`
does not import that package into the harness; it starts the existing headed
composition externally and uses that host's isolated development log.

Keep `python -m tools` separate from `nami-sync`: the latter is a shipped product
surface with lazy GUI imports and reviewed domain workflows, while the
measurement commands use fake persistence seams and destructive owned
workspaces. If distributing those commands is later required, prefer a separate
development entry point after an explicit packaging and workspace-safety review.
