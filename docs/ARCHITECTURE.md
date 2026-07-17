# NamiSync Architecture

This document is the structural reference. `FEATURES.md` says *what NamiSync
does*; this says *how the pieces are shaped and how they talk*. Where the two
overlap, FEATURES.md owns behavior and this owns contracts.

Every section separates **bones** from **flesh**:

- **Bones** are load-bearing structure — types, protocol shapes, invariants,
  and identity decisions that are expensive or impossible to change once data
  and dependents exist. Bones are built in full up front even when nothing uses
  them yet. A missing bone is a rewrite later.
- **Flesh** is behavior that hangs off the bones and grows additively — new
  operations, new policies, new features. A missing piece of flesh is a later
  commit, not a rewrite.

The guiding rule (see FEATURES.md → *Degenerate First Implementations*): build
every bone now; give each one the simplest correct flesh that the first
milestone needs; let new flesh arrive through the seams the bones already
provide.

---

## 1. Layering and the import law

```
core/          contracts, session machine, events, path safety, protocols
                 imports: nothing (stdlib only)
modules/       scanner, planner, preflight, executor, verifier
                 imports: core
db/            recorder (sole ledger writer), repositories, schema, history observer
                 imports: core
workflows/     sync, integrity — the ONLY place modules meet
                 imports: core, modules, db
dispatcher/    session admission, custody, control plane, event fan-out
                 imports: core   (never modules, never workflows)
interfaces/    cli, api, desktop
                 imports: dispatcher, workflows (via a registry)
```

**The law:** core imports nothing; everything imports core; workflows are the
only place modules meet; the dispatcher imports core alone and never learns a
domain word; nothing imports upward or sideways. This is enforced with an
import-lint rule from the first commit, so a boundary violation is a failing
build, not a code review's job.

Two consequences worth stating outright:

- **The dispatcher is domain-blind.** It schedules `Session`s, not syncs. It
  cannot import a workflow, so it cannot grow a `start_sync()` method.
- **Modules never call each other.** The scanner does not know the planner
  exists. A workflow function passes one module's typed return value into the
  next. Control flows through calls and returns; observation flows out through
  events; records flow down through the recorder. Nothing flows sideways.

### Dependency direction (bones)

Every collaborator a module needs — recorder, clock, policies — is **received**
as an argument, wired once at a single composition root. No module constructs
its own collaborator. This is what makes every module testable with fakes and
what keeps the SQLite/Qt/OS surfaces injectable rather than hardcoded.

---

## 2. Type reference

The type reference is the spine of the whole system: the contract that made the
proof-of-concept's "chatty copier, silent verifier" divergence structurally
impossible to repeat. Types are shown in Python-shaped pseudocode; exact field
sets will firm up in code, but the *shapes* and *invariants* here are bones.

### 2.1 Session lifecycle (bones)

```python
class SessionState(StrEnum):
    PENDING    = "pending"      # admitted, not yet running
    RUNNING    = "running"
    PAUSING    = "pausing"      # drain-to-boundary requested
    PAUSED     = "paused"       # drained; volume locks RELEASED
    CANCELING  = "canceling"
    COMPLETED  = "completed"    # terminal: ran to success
    FAILED     = "failed"       # terminal: ran, did not fully succeed
    CANCELED   = "canceled"     # terminal: user-stopped
    REFUSED    = "refused"      # terminal: preflight rejected; NO mutation occurred
    INTERRUPTED = "interrupted" # reload-only: owning process died mid-run

TERMINAL = {COMPLETED, FAILED, CANCELED, REFUSED}
```

- `PAUSED` releasing locks is a bone, not a detail: pause exists so the user can
  use the disk. Resume therefore always re-preflights.
- `INTERRUPTED` is assigned only by startup reconciliation when a session was
  left `RUNNING` by a process that no longer holds the single-instance/queue
  lock. It flows into the same preflight-then-continue path as resume.
- There is deliberately **no `WAITING_INPUT` state**. Sessions never block on a
  human; conflicts and errors are logged and the run continues, with review
  after the terminal. (FEATURES.md → *Sessions Never Block on a Human*.)

The legal transition table lives in exactly one place (`core/session.py`) and is
enforced by the dispatcher. Illegal requests fail cleanly; they never corrupt
state.

### 2.2 Cooperative checkpoint (bones)

```python
class Canceled(Exception): ...

class Checkpoint(Protocol):
    def __call__(self) -> None:
        """Return normally to proceed. Block while the session is paused.
        Raise Canceled if the session is being canceled."""

@dataclass(frozen=True)
class RunContext:
    emit: Callable[[EventBody], None]   # observation out
    checkpoint: Checkpoint              # pause + cancel, one call site
```

Every loop in every module — scanner between entries, executor between
operations and between copy chunks, verifier between files — calls
`ctx.checkpoint()` where the proof-of-concept called an ad-hoc cancel check.
Pause and cancel are the same call site with two answers. This single decision
is why pause is free instead of an unpayable retrofit.

### 2.3 Events (bones)

```python
@dataclass(frozen=True)
class Envelope:
    session_id: SessionId
    seq: int                 # gap-free per session; lets a late subscriber detect loss
    at: datetime             # from the injected Clock, UTC
    schema_version: int      # the envelope is versioned from day one

class DeliveryClass(StrEnum):
    LOSSY    = "lossy"       # may be coalesced/dropped in favor of latest
    RELIABLE = "reliable"    # never dropped for admission-time subscribers

# Event bodies (each pairs with an Envelope):
class StateChanged: state: SessionState                       # RELIABLE
class PhaseChanged: phase: str                                # RELIABLE
class Progress:     items_done: int; items_total: int | None  # LOSSY
                    bytes_done: int; bytes_total: int | None
                    current_path: str | None
class ItemOutcome:  item_id: str; kind: str; path: str        # RELIABLE
                    outcome: Outcome; reason: str | None
                    detail: Mapping[str, object]
class Terminal:     result: OperationResult                   # RELIABLE
```

Invariants (bones):

- Exactly **one** `Terminal` per session, guaranteed by control flow, not
  discipline (§4 executor/session `finally`).
- `Progress` is the only lossy class. A slow subscriber gets the latest progress
  snapshot, never a backlog, and can never stall a producer or a faster
  subscriber. Outcomes and state transitions are never dropped for a subscriber
  attached at admission (the history observer is always such a subscriber).
- The verifier emits `ItemOutcome` per file *because that is the only way to
  report a per-file result*. Silent-until-done is not expressible.

### 2.4 Outcome vocabulary (bones)

```python
class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED   = "skipped"    # intentionally not acted on (noop, ignored)
    FAILED    = "failed"     # attempted, errored
    CANCELED  = "canceled"   # not reached due to cancellation
    DEFERRED  = "deferred"   # valid but held back (dependency, partial-exec)
```

Every operation every module performs ends in exactly one of these. `DEFERRED`
exists in the enum from day one though only partial execution produces it —
consumers handle all five now; producers grow into them.

### 2.5 Scan, plan, execution (bones = shapes; flesh = fields)

```python
@dataclass(frozen=True)
class VolumeId:                 # identity by EVIDENCE, matched conservatively
    serial: str                 # on-disk NTFS serial (travels with the drive)
    fs_type: str
    label: str | None

@dataclass(frozen=True)
class CapabilityProfile:        # one per scanned root
    fs_type: str
    mtime_granularity_ns: int   # NTFS 100ns … FAT 2s
    stable_file_identity: bool  # False on exFAT/FAT — disables identity moves
    incurs_seek_penalty: bool | None   # HDD vs SSD; None = unknown → treat as HDD
    max_path: int
    supports_ads: bool

@dataclass(frozen=True)
class FileRecord:
    rel_path: str
    rel_path_key: str           # Windows one-codepoint uppercase; never casefold
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None   # None where the fs has none
    nlink: int                  # >1 disqualifies from move detection

@dataclass(frozen=True)
class ScanResult:
    root: Root
    profile: CapabilityProfile
    files: tuple[FileRecord, ...]
    directories: tuple[DirRecord, ...]
    warnings: tuple[ScanWarning, ...]   # access errors, case collisions, placeholders, hardlinks
    complete: bool              # False ⇒ reviewable, never executable

@dataclass(frozen=True)
class Scope:                    # first-class planner input
    kind: Literal["everything", "pattern", "explicit", "recorded_run"]
    # constructors: Scope.everything() | .pattern(f) | .explicit(ids) | .from_run(token)

@dataclass(frozen=True)
class Plan:                    # immutable snapshot of intent
    operations: tuple[PlanOperation, ...]   # deterministic ids, dependency-ordered
    target_free_space: int
    required_bytes: int         # sized for MAX concurrent in-flight temps
    filter_snapshot: FilterSet  # the filters this plan was built under
    required_volumes: frozenset[VolumeId]

@dataclass
class ExecutionSet:           # plan + selection + mutable per-op status
    plan: Plan
    selection: Selection        # dependency-closed subset
    status: dict[OpId, Outcome]

@dataclass(frozen=True)
class Verdict:
    ok: bool
    refusals: tuple[Refusal, ...]   # per-operation reason + observed snapshot
    observed: ObservedWorld
```

### 2.6 Attestation and results (bones)

```python
class Provenance(StrEnum):
    COPY_ATTESTED    = "copy"      # digest from the source stream during copy
    READBACK_ATTESTED = "readback" # re-read off target medium
    VERIFY_ATTESTED  = "verify"    # independent verification pass

@dataclass(frozen=True)
class Attestation:              # hash + the stats it attests, as ONE unit
    algorithm: Literal["sha256"]
    digest: bytes
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None
    provenance: Provenance
    observed_at: datetime

@dataclass(frozen=True)
class OperationResult:
    status: SessionState        # terminal member
    canceled: bool
    operations: tuple[ItemResult, ...]
    bytes_done: int
    bytes_total: int
```

### 2.7 Protocols — the extension seams (bones = the protocol; flesh = each impl)

```python
class Recorder(Protocol):
    """The ONLY path that writes the main ledger. Calls may fail loudly.
    One serialized writer backs all in-process sessions."""
    def record_copied(self, op: OpId, at: Attestation) -> None: ...
    def record_moved(self, op: OpId, ...) -> None: ...
    def record_verified(self, row: RowId, at: Attestation) -> None: ...
    def record_baselined(self, row: RowId, at: Attestation) -> None: ...
    def record_run(self, token: RunToken, status: SessionState, ...) -> None: ...
    def flush(self) -> None: ...          # exists day one; degenerate impl = no-op

class Clock(Protocol):
    def now(self) -> datetime: ...        # UTC; the only source of time

class FailurePolicy(Protocol):
    def on_item_failed(self, op, error) -> Decision: ...   # Continue | Stop | Retry(after)

class CopyBackend(Protocol):
    def copy(self, src, dst_tmp, ctx: RunContext) -> Digest: ...  # bytes only; publish is the machine's

class WorkerCountPolicy(Protocol):
    def workers_for(self, profile: CapabilityProfile) -> int: ...

class ChangeSource(Protocol):
    def scan(self, root: Root, ctx: RunContext) -> ScanResult: ...  # walking impl now; USN later
```

Each protocol ships in M0 with its degenerate implementation: `flush()` is a
no-op, `FailurePolicy` always returns `Continue` (skip-and-record), `CopyBackend`
is native-only, `WorkerCountPolicy` always returns 1, `ChangeSource` is the
walking scanner. New behavior is a new implementation behind the same shape —
never an edit to a consumer.

---

## 3. Schema-freeze bones

These must exist in the initial schema even though early code writes none of
them. Retrofitting identity is the worst migration there is.

- **`volumes` table**; locations keyed `(volume_id, volume_relative_path)`;
  drive-lettered path is derived display, never stored identity.
- **Host as provenance** — a column on observations/runs, never a component of
  location identity.
- **`hash_provenance`** alongside every stored digest (§2.6).
- **Nullable `file_identity`** — exFAT/FAT and placeholder rows legitimately
  lack it; rename/move logic degrades rather than lies.
- **`deleted_at`** on mappings (soft delete before purge).
- **Generic `annotations(entity_kind, entity_id, key, value)`** — absorbs the
  whole "users want a small note/label on X" class without future schema churn.
- **Nullable file-identity group** — room for future hardlink grouping.
- **Schema-version stamp** on both databases; the migration module is separate
  from the sync path but the stamp is present from row zero.

---

## 4. Modules

Each module lists its **contract** (signature), **bones**, **flesh**
(now / deferred), and **acceptance criteria** — the definition of done that
doubles as the test target.

### 4.1 core

**Contract.** Defines every type in §2, the session state machine, the event
sequencer, path-safety helpers, and all protocol shapes. Imports nothing.

**Bones.** All of §2. The transition table. `normalize_relative_path` (Windows
one-codepoint uppercase — never `casefold()`, which merged `Straße`/`strasse`
into one row in the PoC). Root-constrained path validation (rejects absolute,
drive-qualified, `..`, root-escaping).

**Flesh.** None. Core is all bones by definition.

**Acceptance criteria.**
- The transition table permits exactly the legal edges and rejects all others,
  proven by an exhaustive table test.
- `normalize_relative_path` keeps NTFS-distinct names distinct across a Unicode
  special-casing corpus (`ß`, Turkish `İ/ı`, fullwidth forms).
- Path validation rejects every escape form and accepts every legitimate
  root-relative path.
- Event `seq` is gap-free and monotonic per session under concurrent emit.

### 4.2 scanner

**Contract.** `scan(root, ignores, ctx) -> ScanResult`. Implements
`ChangeSource`.

**Bones.** The `ScanResult`/`FileRecord`/`CapabilityProfile` shapes; the
`complete` flag; cancellation via `ctx.checkpoint()`; visited-identity tracking
so junctions/reparse loops cannot recurse forever.

**Flesh — now.** Recursive metadata walk (size, mtime_ns, identity, nlink);
exact-name ignore filtering; capability profiling; placeholder detection
(classify reparse/offline files `unsupported`, never open them); scan warnings.
**Flesh — deferred.** USN change-journal `ChangeSource`; network-share awareness.

**Acceptance criteria.**
- A directory junction that points into its own ancestor terminates the walk;
  it never recurses twice or hangs.
- A cloud placeholder file is recorded `unsupported` and is **never opened**
  (asserted by a read-tripwire in test).
- A partial/errored walk yields `complete=False`; a clean walk yields `True`.
- Ignored artifacts are matched only by exact qualified name; a user file named
  `my.synctmp-notes.txt` or `data.db` is **never** excluded (direct PoC
  regression tests).
- Cancellation observed within one directory/file step.
- exFAT root reports `stable_file_identity=False` and coarse
  `mtime_granularity_ns`.

### 4.3 planner

**Contract.**
`plan(source: ScanResult, target: ScanResult, options, scope) -> Plan`. Pure.

**Bones.** `Plan`/`PlanOperation`/`Scope` shapes; deterministic op ids and
dependency ordering; the capacity formula (single source of truth, sized for max
concurrent temps); `filter_snapshot` embedded in the plan.

**Flesh — now.** Metadata diffing within the coarser root's granularity;
copy/update/mkdir/trash/delete/noop planning; identity-based move detection
(disabled where identity is absent or `nlink>1` or an id appears at multiple
paths); composite move-update as one operation; conflict blocking; capacity
planning; `Scope.everything()`.
**Flesh — deferred.** Content-aware no-op; hash-based move detection; retained
human conflict resolution; `Scope.pattern/explicit/recorded_run` (filters,
partial exec, replay — all new scope constructors, zero planner-shape change).

**Acceptance criteria.**
- Same input scans always yield byte-identical plans (determinism).
- Nested empty source directories plan the **full** mkdir chain, and a rerun
  converges to zero operations (PoC regression).
- A directory emptied by the plan's own trash/delete in the same run is itself
  cleaned up (plan reasons about its own removals, not just the pre-scan).
- Capacity `required_bytes` never undercounts concurrent updates; a plan
  accepted by capacity never hits ENOSPC that the formula could have predicted.
- On a stable-identity-less root, no `move` operation is ever emitted.
- A file whose identity appears at two paths, or with `nlink>1`, is never part
  of a move.

### 4.4 preflight

**Contract.** `preflight(xset: ExecutionSet, world: ObservedWorld) -> Verdict`.
Pure; no mutation of plan or filesystem.

**Bones.** The `Verdict` shape carrying per-op refusals plus the observed
snapshot; scoped re-stat of only the remaining selected operations.

**Flesh — now.** All checks: plan integrity (dependency-closed, no dep on a
deferred/failed/blocked op), complete-scan requirement, staleness, capacity
(counting reclaimable orphaned-temp bytes as recoverable), safety (roots resolve
to recorded `VolumeId`; trash resolves onto the target volume without reparse
escape and is writable), filter-snapshot drift.
**Flesh — deferred.** Graceful `continue-with-skips` resume tier (M0 resume is
continue-or-refuse).

**Acceptance criteria.**
- Preflight never writes to disk or mutates the plan (asserted by a
  read-only-filesystem test harness).
- It re-stats only operation-touched paths; an unrelated change elsewhere in
  either tree never causes refusal (PoC regression — the original whole-tree
  preflight over-refused and was slow).
- A plan from an incomplete scan is always refused.
- A nearly-full target whose own orphaned temps would free the needed space is
  **not** refused (PoC open-bug fix).
- Running the same `preflight` at review, at execute-guard, and at resume
  yields consistent verdicts for an unchanged world.

### 4.5 executor

**Contract.**
`execute(xset, ctx, recorder, policies) -> ExecResult`. Guards itself with
`preflight` as its first act; records only through `recorder`.

**Bones.** The single-`Terminal` guarantee via `try/finally`; atomic
temp-then-`os.replace` publish with parent-dir fsync; the temp-name shape
`<name>.synctmp-<run-id>-<op-id>`; per-operation final guards (no overwrite of
unexpected targets, type/emptiness checks before directory trash/delete);
content-only byte accounting; the `FailurePolicy`/`CopyBackend` seams.

**Flesh — now.** copy/update/move/mkdir/trash/delete/noop; hash-on-copy;
source-drift guard (re-stat source after read; mismatch fails the op, records
nothing); trash-on-update; root-local trash with volume-identity resolution;
temp recovery by exact name in touched dirs only; per-op continue-on-failure;
chunked cancellation.
**Flesh — deferred.** Validated partial execution (`DEFERRED` outcomes);
restartable large-file copy; multithreaded copy workers; background IO
throttling; Robocopy backend.

**Acceptance criteria.**
- Exactly one `Terminal` per run on every path — success, failure, cancel,
  refusal, exception — proven by fault injection at each operation.
- A crash after temp write but before publish leaves the real target untouched;
  a rerun converges. No partial file is ever published.
- Source changed mid-copy ⇒ op `FAILED`, **no** attestation recorded (PoC gap).
- A first blocked/failed operation never aborts later independent operations
  (the "walk away for hours" guarantee — the PoC's original SEVERE bug).
- Temp recovery deletes only exact-shape temp names in copy/update parent dirs;
  a user file containing `.synctmp-` survives (PoC SEVERE regression).
- Trash that would land off-volume or through a reparse point is refused before
  any move.
- Cancellation during a multi-GiB copy takes effect within one chunk.
- All volume locks are released on every terminal path (custody is the
  session's, not the executor's — but the executor must not leak temps).

### 4.6 verifier

**Contract.** `verify(selection, ctx, recorder) -> VerifyResult`;
`baseline(selection, ctx, recorder) -> ...`. Records through `recorder`.

**Bones.** Per-file `ItemOutcome` emission (no silent-until-done); the
integrity-outcome vocabulary (verified, baselined, mismatched, modified,
missing, unsupported, canceled, error); attestation provenance tagging.

**Flesh — now.** Baseline creation; location verification against the
size/mtime/identity/hash unit; selected and post-execution verification;
cache-honest reads; safe conditional recording; accept/re-baseline of a modified
file.
**Flesh — deferred.** Multithreaded verification (per-volume-side worker policy);
IO/CPU pipelining even on HDD; automatic background integrity; repair guidance
(diagnose which side is damaged).

**Acceptance criteria.**
- A file with changed size/mtime is reported `modified`, **not** `mismatched`;
  only stats-stable content divergence is `mismatched` (the bitrot signal — PoC
  misclassification bug).
- A null-hash row encountered during verify is a `baselined` outcome, never a
  `verified` one; `last_verified_at` is never set from a copy-stream digest
  alone (PoC open integrity-lie bug).
- A reappeared file that gets its first baseline during verify has
  `reappeared_at` cleared in the same pass (PoC stale-state bug).
- Scoped verification matches rows by `rel_path_key`, not raw path (PoC
  casing/separator bug).
- Every per-file write is conditional; a file that drifts between hash and write
  records nothing.
- Reads bypass the page cache (or defer past cache pressure) so a match attests
  the medium, not a just-written buffer.

### 4.7 db (recorder + repositories + history observer)

**Contract.** `recorder.py` implements `Recorder` and is the sole ledger writer.
`repositories.py` holds all reads. `history.py` is an event-stream observer with
its own database. `schema.py` owns both schemas and the version stamps.

**Bones.** Single serialized writer; the conditional-recording primitive (write
gated on row id + state + size + mtime still matching the observation) shared by
copy/verify/baseline/import; bounded-window durability with forced flush before
any destructive op, at pause-drain, and at terminal; run-token idempotency;
WAL + foreign keys + bounded busy timeout; the §3 schema-freeze columns. History
has **no** foreign key to the ledger and its failures never roll back real work.

**Flesh — now.** Recording for sync/verify/baseline/import; missing-marking
sweep (batched — never one giant `NOT IN`); inventory reconciliation; history
envelopes, summaries, typed detail; retention sweeps (writable connection).
**Flesh — deferred.** Migration module; legacy import; scheduled backup/quick-check
(as an ordinary session); export/import; ledger merge across hosts.

**Acceptance criteria.**
- Two parallel disjoint-volume runs both record completely; neither silently
  loses bookkeeping to lock contention (PoC open concurrency bug — the reason
  for the single serialized writer).
- A recording failure is always surfaced to the caller, never swallowed, and
  never inverts a successful `RunResult` into a reported failure (PoC trust bug).
- The conditional primitive discards a write whose row drifted; a baseline hash
  is never attached to stale metadata (PoC inconsistent-row bug).
- Missing-marking survives a location of >33k files without an
  `OperationalError` (PoC SEVERE parameter-limit bug).
- A move onto a path occupied by a retained missing row clears that row first
  and does not roll back the whole run (PoC SEVERE data-loss bug).
- Retention runs on a writable connection and actually removes expired rows (PoC
  SEVERE write-through-readonly bug).
- Every ledger commit follows its filesystem observation and precedes the next
  batch boundary; a crash loses at most one batch and never a committed truth.
- A repeated run token is a no-op in both databases.

### 4.8 dispatcher

**Contract.** `submit(kind, request) -> SessionId`; `pause/resume/cancel(id)`;
`subscribe(id) -> stream`; `list()/get(id)`. Imports core only; resolves `kind`
through an injected workflow registry it never introspects.

**Bones.** Generic session admission; volume-scoped concurrency (non-overlapping
volume sets run in parallel, contenders queue); single queue-owner via a
persisted-queue file lock; resource custody (locks acquired on start, released on
terminal or pause-drain — one owner); the control plane over the transition
table; event sequencing + fan-out + bounded replay; the persisted session table
(lifecycle + **opaque** per-workflow blob — the sole DB-write exception); startup
reconciliation (dead-process `RUNNING` ⇒ `INTERRUPTED`); orderly teardown.

**Flesh — now.** In-process serial-to-volume-scoped admission; keep-everything
replay buffer (degenerate); pause/resume/cancel.
**Flesh — deferred.** Durable queue with launch policy; event conflation policy
(degenerate = simple rate limit now); local-pipe CLI-as-client.

**Acceptance criteria.**
- No dispatcher symbol names a domain activity; it never imports modules or
  workflows (import-lint enforced).
- Two sessions on disjoint volume sets run concurrently; two contending for one
  volume serialize.
- Every session reaches a terminal and releases every lock on every path,
  including exceptions and teardown (custody conformance).
- The stored per-workflow blob is never deserialized by the dispatcher.
- After a simulated process kill, reconciliation marks the orphan `INTERRUPTED`
  and routes it through preflight-then-continue.
- A `Progress` flood never stalls a slow subscriber or the producer; a
  `RELIABLE` event is never dropped for an admission-time subscriber.

### 4.9 workflows

**Contract.** Plain functions — `run_paired_sync(req, ctx, deps)`,
`run_integrity(req, ctx, deps)` — that sequence modules by passing typed data
forward. The only place modules meet. Each runs as one session.

**Bones.** Top-to-bottom sequencing (scan → plan → preflight → execute/verify);
no signals, no callbacks-for-control; every dependency arrives via `deps`.

**Flesh — now.** Paired sync; one-location integrity (inventory/baseline/verify/
import).
**Flesh — deferred.** Queue-driven runs; replay-from-history; DB maintenance
session; undo/repair (each generated as an ordinary plan through the same
pipeline — the *Pipeline-Only Mutation* law).

**Acceptance criteria.**
- The workflow reads top-to-bottom as sequential calls; control flow is visible,
  not emergent.
- A refused preflight short-circuits to a `REFUSED` terminal with no mutation.
- Every mutation of managed user data flows through plan → preflight → execute —
  including future undo and repair — so their conflicts with later runs surface
  in ordinary plan review.

### 4.10 interfaces (cli / api / desktop)

**Contract.** Adapt dispatcher + workflow state to a surface. Own no sync policy.

**Bones.** Read dispatcher session table for status; subscribe to event streams;
translate user intent into `submit`.

**Flesh — now (M0).** CLI `sync` + `history`; real entry-point wiring.
**Flesh — deferred.** Full CLI surface; web API; desktop UI (task rail, trees,
mismatch-severity, cancel/pause safety messaging, completion toasts, mapping
list). Toolkit choice deliberately deferred — the doc names no GUI framework.

**Acceptance criteria.**
- The real entry points (`nami-sync`, `python -m nami_sync`) dispatch by actual
  `sys.argv`; no command is reachable only under an explicit test argv (PoC
  SEVERE dead-CLI bug — smoke-test the real default path).
- Read-only CLI commands run concurrently with a GUI session; mutating commands
  obey the same volume/queue arbitration as any session.
- Runtime guards raise real exceptions, not bare `assert` (which vanished under
  `python -O` in the PoC).
- Any presentation-triggering logic is separable from an event loop, so tests
  never enter a modal loop (PoC 15-minute `QMenu.exec()` hang).

---

## 5. Cross-cutting invariants (bones)

1. **One terminal, always** — control flow guarantees it (§4.5).
2. **Checkpoint everywhere** — every loop yields to pause/cancel at one call.
3. **Never wrong, only behind** — committed evidence is always true; recovery
   reconciles, never rolls back true evidence to look tidy.
4. **Records are calls that may fail loudly; telemetry is a stream that may be
   missed silently.** History is telemetry; the ledger is a record. Never route
   a record through a telemetry pipe.
5. **Policies decide, the machine enforces.** Extension points return decisions,
   never receive control.
6. **Pipeline-only mutation** of managed user data (§4.9); app-owned artifacts
   are exempt but stay guarded and logged.
7. **Sessions never block on a human.**
8. **Identity by conservative evidence** — volumes, files, renames all match on
   corroborated evidence and refuse to guess when ambiguous.
9. **Exact-name recognition** of NamiSync's own artifacts — never suffix/substring.
10. **One injected clock**, UTC everywhere, converted only at the presentation edge.

---

## 6. Build order

- **M0 — walking skeleton.** core contracts → degenerate dispatcher → two dummy
  operations proving pause/cancel/lock-release → scanner→planner→preflight→
  executor on plain NTFS → recorder + minimal ledger (schema-freeze columns
  present, `flush` a no-op) → CLI `sync`/`history`. Ships a real, safe,
  hash-on-copy sync tool.
- **M1 — integrity.** verifier + baseline + inventory + history observer. Verify
  is additive once inventory rows and the recorder exist.
- **M2 — durability & scope.** persisted session table, durable queue, filters
  (via new `Scope` constructors), event conflation.
- **M3+ — surface & scale.** web/desktop UI against the then-stable event
  protocol; multithreaded copy/verify; USN change source; migration module;
  data-protection features.

Each milestone is gated by its modules' §4 acceptance criteria. A criterion is
not "tested" until it has a failure-injection or regression test named after the
behavior it protects — most of them trace directly to a PoC bug, and that bug is
the test's reason to exist.
