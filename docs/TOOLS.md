# Development Tools

`tools/` contains development-only utilities. `python -m tools`
owns the executor/verifier measurement harness, deterministic corpus generator
and selected performance cases. `tools/gui.ps1` is a standalone editable-source desktop convenience
launcher. `tools/icons.py` maintains the fixed local icon vocabulary from
`tools/icons.json`. None is part of the shipped `namisync` package. Pytest covers
their behavior; measurement output remains subject to the authority rules below.

## Icon maintenance

`namisync/interfaces/web/assets/icons/` contains fixed local monochrome SVGs
from pinned `@fluentui/svg-icons`. `tools/icons.json` is the reviewed, development-
only authority for package version, glyph selection and deliberate size fallbacks.
Keep upstream filenames, exact package/file URLs, version, per-file SHA-256
hashes and MIT license with the assets. Runtime registration, remote loading,
generated SVG/path markup and data-derived asset paths are forbidden.

`tools/icons.py` verifies archive integrity and copies native SVGs, generating
provenance and marked fixed registry/CSS sections offline. Commit the generated
source; the app never loads the catalog or generator. Tests belong in `tests/`
and independently check catalog/output correspondence, SVG safety, packaging
and rendering without a second glyph/hash catalog. Temporary archives, fixtures
and command evidence belong in ignored `build/`.

Edit `tools/icons.json` to select glyph names and declare missing-size fallbacks,
then synchronize and review the generated diff:

```powershell
.\.venv\Scripts\python.exe tools/icons.py sync
.\.venv\Scripts\python.exe tools/icons.py check

# Use an already downloaded pinned npm archive without network access
.\.venv\Scripts\python.exe tools/icons.py sync --archive "build/gui-icons/svg-icons-1.1.334.tgz"
.\.venv\Scripts\python.exe tools/icons.py check --archive "build/gui-icons/svg-icons-1.1.334.tgz"

# Optional explicit checkout root; otherwise inferred from the script's location
.\.venv\Scripts\python.exe tools/icons.py check --root "F:\GitHubRepositories\NamiSync"
.\.venv\Scripts\python.exe tools/icons.py --help
```

Both commands accept `--archive` and `--root`. Without `--archive`, the command
downloads the official npm archive pinned by the catalog. It verifies SHA-512
integrity before parsing selected members; it never extracts arbitrary archive
paths. Native 16/20/24 px selection is automatic. Missing sizes require explicit
20 px fallbacks; obsolete fallbacks are refused when native artwork exists.

`sync` updates native SVGs, SOURCE provenance, and marked JavaScript/CSS regions.
It removes only unchanged stale assets owned by the previous receipt. Do not
hand-edit these generated outputs. `check` writes nothing and exits with status
1 for drift or invalid input, or 0 when outputs match. A successful sync also
exits 0. The tool is not a runtime loader and introduces no app dependency.

For package updates, review the catalog's version, integrity, commit and license
hash together. The archive omits the license file: retain or deliberately update
the reviewed local `LICENSE.txt`; a missing file or hash mismatch is refused.
Archive verification establishes upstream correspondence; receipt consistency
tests alone do not. Run the icon/tool tests and installed gallery gate described
in [TESTS.md](TESTS.md). Placement policy and icon semantics remain owned by
[DESKTOP_UI.md](DESKTOP_UI.md#icon-placement-and-meaning).

### Remove a glyph

Remove its name from `glyphs` and its entry from `fallbacks`, if present. Run
`check` to see pending drift, then `sync`. The tool removes its registry entry,
CSS mappings, receipt records and unchanged previously owned SVGs. A modified
stale SVG or unrelated file in the icon directory causes refusal before writes;
review that local work before retrying. At least one glyph must remain.

The tool does not rewrite or scan application callers. Remove or replace uses
of the glyph in the same change: a remaining `createIcon` call with that name
will be rejected by the fixed registry. Run the relevant caller tests and gallery
gate. Deleting SVGs manually is not a catalog removal; `sync` restores selected
assets from the pinned archive.

### Upgrade Fluent artwork

Choose a reviewed package version and update `upstream.version`, `integrity`
and `git_commit` together. Verify the license at that revision and update its
local file and catalog hash if needed. Changing only the version is insufficient:
the old archive integrity will not authenticate the new download. The commit is
reviewed provenance; when the tarball omits `gitHead`, the tool cannot independently
prove the package-to-Git association.

Run `check`, resolve any compatibility refusal, then run `sync` and review the
diff. Same-name artwork is replaced, and all package URLs, hashes and provenance
are regenerated. Names newly offered upstream are not added to the catalog.
If upstream adds a native size previously covered by a fallback, remove that
fallback explicitly. If a native size disappears, declare a supported 20 px
fallback; missing 20 px artwork, renamed/removed glyphs or a changed SVG format
require a deliberate selection or implementation decision. The tool refuses
these cases rather than silently retaining old-version artwork or substituting
another glyph. Existing locally edited selected files are regenerated by sync;
review or preserve such work first.

Finish with `check`, icon/tool tests and the installed gallery gate; new artwork
still needs visual review. The tool does not discover or install the latest
version automatically. Synthetic tests cover version transitions without
changing the repository's actual package pin.

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

The shell keeps the ordinary Ready label hidden. Only smoke-test invocations
explicitly pass the helper's `--expose-ready-status` switch for their UI Automation
witness; `tools/gui.ps1` does not opt in to this test presentation override.

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
measurement tiers and escalation rules. [PERFORMANCE](PERFORMANCE.md) owns
measurement methods and results. Development tools declare which tier they
serve, keep observation separate from verdict, and refuse input shapes they
cannot account for. Compatible Tier 2 measurements may share one vertical-
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
component validator follow the declared measurement method in PERFORMANCE.

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

The executor/verifier rigs may import `core`, `modules`, and the pure
`workflows.selection` helper. They do not import `db`, `dispatcher`,
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

## Performance drivers

`python -m tools executor`, `python -m tools verifier`, `python -m tools
generate` and `python -m tools clean` remain development-only entry points.
The executor/verifier harness uses the isolated seams above and the workspace
safety policy in this document. [PERFORMANCE](PERFORMANCE.md#executor-and-verifier-methods)
owns their measurement commands, fixtures, statistics, sidecars, cache
interpretation, reports and rerun policy. Driver structure is under
`tools/`; tests stay under `tests/`; generated output belongs in ignored
`build/` or an explicitly owned external workspace.

`tools/performance/` owns selected Plan, execution receipt/UI, bridge-event and
history measurements. Assets live beside their driver; small fixture/runner
helpers are shared only where used. These drivers may compose the real
interface and database endpoints they measure. They may reuse uncollected
native test helpers; they must not import collected test modules. Tests stay
under `tests/`, including independent fixture/action and failure controls.
The frozen custody memory helper remains at its existing test path.

Use `python -m tools performance --list` to discover cases, then
`python -m tools performance FAMILY CASE --json OUTPUT` to run one. Installed
receipt/UI cases additionally take `--installed-root`; Plan's public cases use
component endpoints. Bridge-event builds
its own wheel from committed HEAD and uses the working-tree driver. Reports
distinguish those sources. See [PERFORMANCE](PERFORMANCE.md) for exact cases,
installation methods, profiles and interpretation.

Reports are published without overwriting an existing result. Repository-local
output belongs under ignored `build/`; keep raw child evidence beside its report.
An incomplete measurement returns nonzero and remains explicitly incomplete;
completion means a valid observation, not acceptance of the historical timing
target. Plan/UI latency and empirical representation memory are advisory.
Correctness, counted scale behavior, custody, lifecycle/resource containment,
history release limits, SH-G-15 and executor settlement retain their named gates.
