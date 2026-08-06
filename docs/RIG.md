# Module Rig

`tools/rig/` is a development harness for benchmarking and optimizing the
executor and verifier in an environment close to the one they run in
production. It is not part of the shipped package, is not collected by pytest,
and enforces no product behavior.

## What it stands in for

The rig replaces the workflow layer only. It supplies the two ledger seams and
the run seam, and uses the real collaborator for everything else:

| Seam | Production | Rig |
| --- | --- | --- |
| `Recorder` | `db.recorder.SyncRunRecorder` | `LedgerlessRecorder` (in memory) |
| `IntegrityRecorder` | `db.recorder.LedgerRecorder` | `CapturingIntegrityRecorder` |
| `RunContext` | dispatcher fan-out | `Tape` (timestamped events) |
| Execution set | `workflows.sync.run_plan` | real `scan` -> `plan` -> `derive_execution_selection` |
| Integrity selection | ledger inventory rows | real scan plus one of three evidence sources |
| Filesystem, copy backend, reader | native | native, unchanged |

Inputs come from the real scanner and planner rather than hand-built
operations, so the measured operation mix, dependency edges, and blocked flags
are the ones the product would produce for those roots.

The rig imports `core`, `modules`, and the pure `workflows.selection`
safe-subset helper. It does not import `db`, `dispatcher`, `interfaces`, or the
workflow runtime. `tools/` sits outside `root_package`, so it is invisible to
the import contracts in `pyproject.toml`.

## Executor runs

The rig owns the target tree. It claims a workspace, optionally materializes a
pre-state template into it, executes, and tears it down.

```powershell
.\.venv\Scripts\python.exe -m tools.rig executor E:\Corpus E:\RigWork --verify-readback
.\.venv\Scripts\python.exe -m tools.rig executor E:\Corpus E:\RigWork --template E:\PreState --repeat 5 --json runs.jsonl
```

Ownership markers live *beside* the workspace as `<name>.rig-owned`, never
inside it: a marker within the target root would be scanned as target content,
would change the planned operation mix, and under a deletion policy could be
trashed by the run whose teardown depends on it. Teardown refuses any directory
without a marker, refuses filesystem roots, the home directory, the working
directory, and anything inside this repository, and handles the read-only
attributes and long paths the executor legitimately produces. It runs in a
`finally`, so a failed run still tidies; `--keep` suppresses it.

Without `--template` each iteration executes into an empty target, which is the
all-`COPY` benchmark. A template is what gives repeatable non-trivial operation
mixes: the planner sees the same pre-state every iteration. Template
materialization is reported as `setup_seconds` and is excluded from
`execute_seconds`.

### Telemetry

`NativeCopyBackend.last_metrics` retains only the most recent copy, so the rig
wraps the injected `copy_backend` and samples one snapshot per operation.
Reported per run: `reader_blocked_seconds`, `writer_starved_seconds`,
`payload_high_water`, `reserved_bytes`, the chunk sizes `_copy_chunk_size`
actually chose across the size distribution, and the wall time inside the
backend as distinct from total execution time. `--no-metrics` turns the
executor's opt-in diagnostics off.

## Verifier runs

The verifier only reads, so it needs no workspace. The variable is where prior
evidence comes from.

```powershell
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --mode baseline
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --baselines primed --repeat 5
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --seed-baselines
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --baselines sidecar
```

| `--baselines` | Setup | Path exercised | Detects corpus drift |
| --- | --- | --- | --- |
| `primed` (default) | one in-process baseline pass | `VERIFIED` | no |
| `sidecar` | one `--seed-baselines` pass, once per corpus | `VERIFIED` | yes |
| `synthetic` | none | `MISMATCHED` | no |
| `none` | none | `BASELINED` | no |

`synthetic` builds well-formed evidence with a deliberately wrong digest. The
digest is compared only after the full read-and-hash loop, so every byte of the
pipeline still runs; the run settles as `MISMATCHED`, which skips the evidence
construction and recorder call that a real `VERIFIED` settlement performs. That
tail is negligible against large files and material on a corpus of small ones.

### The sidecar

`--seed-baselines` writes `<corpus>.baseline.jsonl` beside the corpus root, one
JSON row per canonical path key. It must live outside the scanned root:
`IgnoreSet` covers `.synctrash` and `.synctmp-*` only, so a file inside the
corpus would be scanned as corpus content.

Every load validates against a fresh scan and refuses to proceed on any
mismatch, including files present on disk with no stored evidence. This is not
defensive politeness. A stale baseline short-circuits at `STAT_CHANGED` *before
hashing*, so it does not fail loudly — it silently converts a throughput
benchmark into a guard benchmark with suspiciously good numbers.

Identity mode decides whether stored evidence enforces NTFS file identity.
`portable` (default) compares kind, size, and mtime only, so the corpus
survives being moved or restored; `bound` also pins volume serial and file
index. Identity is recorded either way; the header decides enforcement.
`mtime_ns` must survive any relocation — the executor preserves timestamps and
`robocopy /COPY:DAT` does, a plain `Copy-Item` does not.

### Isolating hash cost

The verifier has no diagnostics emitter yet, so measurement is external.
`--null-hasher` swaps the injected `hasher_factory` for a constant-digest stub.
Priming with the same stub lands on the real `VERIFIED` path with hashing
removed, so a paired run isolates hash cost exactly:

```powershell
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --baselines primed
.\.venv\Scripts\python.exe -m tools.rig verifier E:\Corpus --baselines primed --null-hasher
```

This is valid for the verifier because it reads synchronously, so removing the
hasher cannot reshuffle a bottleneck. It is **not** valid for the executor,
whose bounded reader/hasher/writer pipeline moves its bottleneck when the
hasher is stubbed, making `reader_blocked_seconds` and `writer_starved_seconds`
incomparable across the pair.

`TappedReader` additionally reports per-subject open and read time by
decorating the `VerificationReader` seam. It costs one `perf_counter` pair per
chunk; `--no-tap` removes it for clean wall-clock numbers when sweeping small
chunk sizes. When the verifier grows its own emitter, the tap becomes the
cross-check rather than the primary source.

## Cache honesty

The verifier reads with `FILE_FLAG_NO_BUFFERING`, so its numbers are cold by
construction. The executor reads through the buffer cache, so a second run over
the same corpus is warm and not comparable to the first. Regenerate or vary the
corpus when comparing first-touch throughput, and keep workspaces on the volume
under test.

## Corpus generation

The rig accepts an existing fixed corpus by path. `generate` writes a
deterministic tree when a different size distribution is wanted; the same seed
produces the same bytes.

```powershell
.\.venv\Scripts\python.exe -m tools.rig generate E:\Corpus "2000@4KiB,200@1MiB,4@256MiB" --seed 7
.\.venv\Scripts\python.exe -m tools.rig clean E:\RigWork
```

## Output

Every run prints a one-line summary and, with `--json PATH`, appends one JSON
object per iteration so optimization passes can be diffed rather than eyeballed.
