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
    REFUSED    = "refused"      # terminal: preflight or commitment check rejected; NO mutation occurred
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
class Canceled(Exception): ...        # control flow, not an error
class PauseRequested(Exception): ...  # control flow, not an error

class Checkpoint(Protocol):
    def __call__(self) -> None:
        """Return normally to proceed. NEVER blocks. Raise Canceled if the
        session is being canceled, PauseRequested if a pause was requested;
        either exception unwinds the workflow to the session runner, which
        owns the resulting transition."""

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

Pause never blocks in place — a blocked stack would hold the volume custody
that `PAUSED` promises to release. Both pause and cancel *unwind*. The
continuation state a pause must preserve is explicit. In the execute phase,
`ExecutionSet` records completed operation status plus published copy evidence,
so everything unreached is remaining work. In the optional M1 verify phase, the
discriminated continuation also records transient candidates, completed ids,
and verified bytes. Resume is the same fresh observe/preflight path as any queue
wakeup and never infers phase from emitted events. An in-flight temp abandoned
by a mid-copy pause is reclaimed by ordinary orphaned-temp recovery.

Pause is a per-kind capability, declared once at workflow registration and
enforced through the transition table: only session kinds with a continuation
state accept it — execution from M0 and the verifier's item-list sessions
(verify/baseline) from M1 — while scan/plan sessions (seconds of work, no
continuation) refuse pause cleanly and remain cancelable. The
recorder needs no pause behavior at all: it is call-driven, not stream-driven —
while nothing executes it simply receives no calls, and the pause-drain forced
flush (§4.7) has already committed every completed operation's evidence before
locks release.

### 2.2a Session runner (bones)

One generic runner, in `core/session.py`, wraps every workflow invocation and
is the **only** place a `Terminal` is emitted or a pause/cancel resolves.
Modules and workflows return typed results; none of them ever emits `Terminal`.

```python
def run_session(work: Callable[[RunContext], SessionResult], ctx) -> None:
    try:
        result = work(ctx)                 # a workflow function
        emit(Terminal(result))             # COMPLETED / FAILED per result
    except Canceled:
        emit(Terminal(canceled_result()))  # CANCELED
    except PauseRequested:
        transition(PAUSED)                 # no Terminal — session isn't over
    except BaseException as e:
        emit(Terminal(failed_result(e)))   # FAILED; the runner CONSUMES the
                                           # exception — typed detail rides the
                                           # Terminal and the log; nothing
                                           # re-raises past here, so a second
                                           # terminal is unconstructible
```

The dispatcher wraps `run_session` with lock custody: acquire before, release
in its own `finally` on every terminal *and* on pause. Exactly-one-terminal is
a property of this one `finally`-shaped function, not of any module's
discipline — scan, plan, execute, verify, import, maintenance, and dummy
sessions all inherit it identically.

Terminal results for cancel and failure paths are assembled by the runner from
the session's emitted RELIABLE events whose payload nominally implements
`ResultItem` — execution `ItemOutcome` and integrity `IntegrityOutcome`; it
never duck-types on `item_id`/`path` (pause emits no terminal at all — the
session isn't over). Control-flow exceptions carry no payload; what makes the
unwind lossless is a **module obligation**: an
item-processing module's own `finally` emits a `CANCELED` outcome for the
in-flight item and every unreached selected item before `Canceled` leaves the
module — while on `PauseRequested` it emits nothing for them, because they
remain pending for resume. Emit-as-you-go plus this unwind finalizer means the
runner never introspects module internals.

Audit finalization is a bounded two-phase step, not a circularity: before the
runner emits the one immutable `Terminal`, it drains the audit subscriber and
history attempts its final write, acknowledging within the same generous
timeout. Success stamps `audit=OK`; timeout or failure stamps `audit=DEGRADED`
and releases any blocking. Only then is `Terminal` — carrying the settled
audit axis — released to ordinary subscribers. History finalizes from the
drain step; it never parses the `Terminal` it already acknowledged, and no
second terminal exists. (The `recording` axis has no such loop: the recorder
is call-driven, and its terminal flush completes before result assembly.)

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
    RELIABLE = "reliable"    # guaranteed to the audit subscriber (timeout-
                             # guarded); ejection of any other subscriber is
                             # announced by Gap — never silent thinning

# Event bodies (each pairs with an Envelope):
class StateChanged: state: SessionState                       # RELIABLE
class PhaseChanged: phase: str                                # RELIABLE
class Progress:     items_done: int; items_total: int | None  # LOSSY
                    bytes_done: int; bytes_total: int | None
                    current_path: str | None
class ItemOutcome:  item_id: str; item_type: Literal["operation"] # RELIABLE
                    phase: Literal["execute"]; kind: str; path: str
                    outcome: Outcome; reason: str | None
                    detail: Mapping[str, object]
class IntegrityOutcome:                                       # RELIABLE; M1 producer
                    item_id: str; item_type: Literal["integrity"]
                    phase: str; path: str   # baseline|verify|rebaseline; typed
                    result: IntegrityResult   # verified|baselined|mismatched|modified|
                                              # missing|unsupported|canceled|error
class Gap:          first_missed_seq: int     # ejection notice: the FIRST event an
                                              # ejected subscriber sees on its stream
class Terminal:     result: OperationResult                   # RELIABLE
```

Invariants (bones):

- Exactly **one** `Terminal` per session, guaranteed by control flow, not
  discipline (the session runner's `finally`, §2.2a — modules never emit it).
- `Progress` is the only lossy class. A slow subscriber gets the latest progress
  snapshot, never a backlog, and can never stall a producer or a faster
  subscriber. Outcomes and state transitions reach the history observer under
  the timeout-guarded audit guarantee below, and are never *silently* dropped
  for any subscriber — ejection is always announced by `Gap`.
- RELIABLE is bounded, not magical. The history observer gets guaranteed
  delivery via bounded producer backpressure at checkpoint boundaries — never a
  drop. Its buffer is sized to absorb at least the events emitted between two
  adjacent checkpoints (≈ one outcome per operation), so backpressure engages
  between operations at a checkpoint-adjacent emit — never as a mid-operation
  stall — and the wait is capped by a generous injected timeout: a writer that
  stalls past it or fails outright degrades that session's `audit` axis loudly
  and blocking stops, so delivery is guaranteed *unless the result says
  otherwise*, never silently absent. Any
  *other* reliable subscriber that overruns its bounded queue is ejected with
  an explicit `Gap` event rather than silently thinned. The replay buffer is
  bounded per session; a late subscriber gets current state plus a bounded
  tail and detects what it missed from the gap-free `seq`.
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
    BLOCKED   = "blocked"    # intrinsically unexecutable reviewed plan item
```

Every reviewed operation ends in exactly one of these. M0 safe-subset workflow
produces `BLOCKED` for direct blockers and `DEFERRED` for quarantined,
dependency-excluded, or incomplete-scan-withheld work. Quarantine and
withholding remain reason codes rather than additional top-level outcomes.

### 2.5 Scan, plan, execution (bones = shapes; flesh = fields)

```python
@dataclass(frozen=True)
class VolumeId:                 # STABLE key material — the ONLY match fields
    serial: str                 # on-disk serial (travels with the drive)
    fs_type: str                # same serial, new fs ⇒ in-place conversion
                                # (e.g. convert.exe preserves the serial) ⇒
                                # explicit rebind. A true reformat regenerates
                                # the serial and presents as an unknown volume.

@dataclass(frozen=True)
class VolumeEvidence:           # mutable corroboration, never identity
    label: str | None           # relabel ⇒ matched anyway, noted silently
    # matching rules: key match ⇒ same volume; key match + evidence drift ⇒
    # note and re-corroborate; two mounted volumes with one key ⇒ explicit
    # user choice, never silent resolution (FEATURES → Cloned-Volume Ambiguity)

@dataclass(frozen=True)
class CapabilityProfile:        # one per scanned root
    fs_type: str
    mtime_granularity_ns: int   # NTFS 100ns … FAT 2s
    stable_file_identity: bool  # False on exFAT/FAT — disables identity moves
    incurs_seek_penalty: bool | None   # HDD vs SSD; None = unknown → treat as HDD
    max_path: int
    supports_ads: bool
    supports_hardlinks: bool    # FILE_SUPPORTS_HARD_LINKS volume flag — drives
                                # the trash-on-update backup fallback and its
                                # capacity accounting

@dataclass(frozen=True)
class MetadataSnapshot:         # what "preserve metadata" observed / intends
    attributes: int             # readonly / hidden / system bits
    created_ns: int | None      # None where the fs can't say
    # no stream manifest — ever (DR-32, amended): ADS is settled as
    # executor-time enumeration at copy (the executor already holds the file),
    # so no scan-time manifest is needed and the scanner stays role-free; ADS
    # writes bump the file's NTFS mtime, so metadata diffing already schedules
    # the re-copy that refreshes streams

@dataclass(frozen=True)
class FileRecord:
    rel_path: str
    rel_path_key: str           # Windows one-codepoint uppercase; never casefold
    size: int
    mtime_ns: int
    file_identity: FileIdentity | None   # None where the fs has none
    nlink: int                  # >1 disqualifies from move detection
    metadata: MetadataSnapshot

@dataclass(frozen=True)
class DirRecord:                # EVERY walked directory is recorded — created
    rel_path: str               # directories need reviewed metadata, and
    rel_path_key: str           # dir-level move detection later needs identity
    metadata: MetadataSnapshot
    file_identity: FileIdentity | None   # present now so dir-level move
                                # detection needs no shape change later

@dataclass(frozen=True)
class UnsupportedRecord:        # typed, review-visible; never plannable as work
    rel_path: str
    rel_path_key: str
    reason: str                 # placeholder | reparse | access-denied | ...

@dataclass(frozen=True)
class ScanResult:
    root: Root
    profile: CapabilityProfile
    files: tuple[FileRecord, ...]
    directories: tuple[DirRecord, ...]
    unsupported: tuple[UnsupportedRecord, ...]  # its own collection — a consumer
                                # must decide about them explicitly; a flag on
                                # FileRecord would be a forgettable discipline
    warnings: tuple[ScanWarning, ...]   # access/path errors, collisions, hardlinks
    complete: bool              # False ⇒ reviewable; absence/identity-dependent
                                # operations are withheld from execution

@dataclass(frozen=True)
class MappingSnapshot:          # prior accepted correspondence — read from
    pairs: ...                  # repositories BY THE WORKFLOW, passed in
    missing: ...                # immutable: paired no-ops, retained missing
    ambiguous: ...              # rows, hardlink/multi-path disqualifiers —
                                # all keyed by rel_path_key. Without this the
                                # planner cannot see which identity used to
                                # live at which target path (the PoC lost move
                                # evidence exactly here).

@dataclass(frozen=True)
class Scope:                    # first-class planner input
    kind: Literal["everything", "pattern", "explicit", "recorded_run"]
    # constructors: Scope.everything() | .pattern(f) | .explicit(ids) | .from_run(token)

@dataclass(frozen=True)
class Plan:                    # immutable snapshot of intent — PURE of observation
    operations: tuple[PlanOperation, ...]   # deterministic ids, dependency-ordered
    required_bytes: int         # pure formula output; sized for MAX concurrent temps
    preservation: PreservationPolicy        # metadata intent, snapshotted
    filter_snapshot: FilterSet  # the filters this plan was built under
    required_volumes: frozenset[VolumeId]
    fingerprint: PlanFingerprint            # deterministic identity (plans are
                                # byte-identical for identical inputs); the
                                # user's commitment binds to this
    # free space is deliberately NOT here — it is observed reality, read by
    # observe() at review and preflight time and judged by the one shared
    # capacity formula. A number baked into an immutable plan is stale the
    # moment it is written.

@dataclass(frozen=True)
class PreservationPolicy:
    preserve_ads: bool          # LATENT seam (DR-32, amended): declared,
                                # unimplemented, not user-exposed; contract is
                                # settled — executor-time enumeration, no scan
                                # input, streams are USER DATA (a requested
                                # stream that fails to copy FAILS the op),
                                # incapable target = mapping-level plan warning
    preserve_created: bool      # where supported
    preserve_acl: bool = False  # explicit opt-in; the security descriptor is
                                # copied at execution time (preserve-current,
                                # not preserve-scanned — a scan-time ACL
                                # snapshot would be heavy and stale); failure
                                # when opted in FAILS the op

@dataclass(frozen=True)
class Commitment:               # the durable preauthorization (commit-to-execute)
    plan_fingerprint: PlanFingerprint   # must match ExecutionSet.plan.fingerprint
    selection_digest: bytes     # the human reviewed plan AND selection; a
                                # selection changed after commit invalidates it
    committed_at: datetime

@dataclass(frozen=True)
class PublishedCopyEvidence:    # core/execution.py
    attestation: "Attestation"  # core/evidence.py; defined in §2.6
    copy_recorded: bool

@dataclass
class ExecutionSet:           # plan + selection + mutable per-op status
    plan: Plan
    selection: Selection        # dependency-closed subset
    commitment: Commitment | None   # execution REFUSES a None or mismatched one
    status: dict[OpId, Outcome] # doubles as the pause/resume continuation:
                                # everything unreached is the remaining work
    published_evidence: dict[OpId, PublishedCopyEvidence]
                                # exactly one per settled COPY/UPDATE/MOVE_UPDATE

class Subject(NamedTuple):      # never a bare string key — both roots share
    root: RootId                # the same rel paths on almost every operation
    rel_path_key: str

@dataclass(frozen=True)
class ObservedWorld:            # a scoped SNAPSHOT — the impure half of preflight
    stats: Mapping[Subject, FileStat | None]   # only subjects the remaining ops touch
    target_parent_paths: frozenset[str]        # exact temp-count/recovery scope
    free_space: int
    reclaimable_temp_bytes: int
    volumes: Mapping[Root, VolumeId | None]
    observed_at: datetime

@dataclass(frozen=True)
class Verdict:
    ok: bool
    refusals: tuple[Refusal, ...]   # per-operation reason + observed snapshot
    observed: ObservedWorld
```

`ObservedWorld` is what keeps preflight pure: **`observe()` touches the
filesystem, `preflight()` only reads the snapshot it produced** (§4.4).

### 2.6 Attestation and results (bones)

```python
class Provenance(StrEnum):
    COPY_ATTESTED    = "copy"      # digest from the source stream during copy
    READBACK_ATTESTED = "readback" # re-read off target medium
    VERIFY_ATTESTED  = "verify"    # independent verification pass

@dataclass(frozen=True)
class ContentEvidence:          # what the BYTES are
    algorithm: Literal["xxh3_128"]  # the one canonical bulk-content algorithm
    digest: bytes                # exactly 16 bytes
    size: int
    provenance: Provenance
    observed_at: datetime

@dataclass(frozen=True)
class Attestation:              # content + the SUBJECT it describes, as one unit
    content: ContentEvidence
    subject: FileStat           # for a copy: the PUBLISHED TARGET, re-statted
                                # after publish — never the source's stat, whose
                                # file identity would poison the target row's
                                # move and drift evidence. The source's own
                                # post-read stat lives separately as the drift
                                # guard's evidence.
    # global invariant: content.size == subject.size

class ResultItem:               # nominal base, never attribute duck typing
    item_id: str
    item_type: str              # serialized discriminator
    phase: str

@dataclass(frozen=True)
class PhaseResult:
    phase: str
    status: str
    items_done: int
    items_total: int | None
    bytes_done: int
    bytes_total: int | None
    error: str | None           # preserves phase-wide failure before item 1

class RecordingStatus(StrEnum):
    OK       = "ok"
    DEGRADED = "degraded"       # work is true, bookkeeping is behind — loud,
                                # separate axis, converges on next scan

class Disposition(StrEnum):
    RAN   = "ran"
    UNRUN = "unrun"             # never started working: discarded queue
                                # entries, refusals — typed, never inferred
                                # from a zero-length operation list or a
                                # parsed string

@dataclass(frozen=True)
class OperationResult:
    status: SessionState        # terminal member — FILESYSTEM truth only
    integrity: IntegritySummary # typed aggregate of per-item integrity truth;
                                # independent from filesystem status
    recording: RecordingStatus  # ledger truth — never folded into status
    audit: RecordingStatus      # history truth — same axis rules (§2.3)
    disposition: Disposition    # CANCELED + UNRUN = discarded before start
    canceled: bool
    items: tuple[ResultItem, ...]       # ordered execution + integrity items
    phases: tuple[PhaseResult, ...]     # phase-local truth and byte totals
```

`PublishedCopyEvidence` is execution continuation state and therefore lives
beside `ExecutionSet` in `core/execution.py`. `PostCopyCandidate` is the
cross-boundary verifier-input contract and lives in `core/integrity.py`; its
final Stage 4 fields bind a published target to expected content evidence and
may carry a durable row identity only when recording already returned one.
It does not embed or import `PublishedCopyEvidence`: the workflow copies the
verifier-facing values while translating between the two contracts.
Constructing either type never requires a ledger query.

Copy, baseline, and verification evidence are deliberately single-valued:
`xxh3_128` is not a user setting and there is no dual-algorithm transition.
Repositories still reconstruct from the stored algorithm identifier so the
field remains self-describing and a future schema change cannot silently
reinterpret old bytes. Plan fingerprints, custody keys, history identities,
and other small non-content hashes remain SHA-256.

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

class StreamingHasher(Protocol):       # stdlib-only core seam
    def update(self, data: bytes) -> None: ...
    def digest(self) -> bytes: ...

HasherFactory = Callable[[], StreamingHasher]

@dataclass(frozen=True)
class CopyDigest:
    digest: bytes
    size: int

class CopyBackend(Protocol):
    def copy(self, src, dst_tmp, *, chunk_size: int,
             checkpoint: Checkpoint,
             on_chunk: Callable[[int], None]) -> CopyDigest: ...
    # chunk_size is the positive actual read size selected by the executor,
    # never a ceiling or an engine-selection hint; publish stays in the machine

class ChangeSource(Protocol):
    def scan(self, root: Root, ctx: RunContext) -> ScanResult: ...  # walking impl now; USN later

class DestinationPolicy(Protocol):
    """Computes target rel paths for a WHOLE batch. Diffing matches source to
    target THROUGH this computation — path-preserving is just the default.
    Batch-shaped because collisions are between files and companion groups are
    across files; a per-file signature cannot express either."""
    def assign(self, records: Sequence[FileRecord],
               meta: Mapping[str, FileMeta],
               target: ScanResult) -> Assignment: ...
    # Assignment: source rel_path -> dest rel_path, plus group and collision
    # detail for plan review.

class MetadataExtractor(Protocol):   # ships with ingest, not M0; ExifTool -stay_open batch mode first
    """IO only, decides nothing — the enrich stage's analogue of observe()."""
    def extract(self, paths: Sequence[str], ctx: RunContext) -> Mapping[str, FileMeta]: ...
```

Every protocol **used** in M0 ships with its degenerate implementation:
`flush()` is a no-op, `FailurePolicy` always returns `Continue`
(skip-and-record), `CopyBackend` is native-only, `ChangeSource` is the walking
scanner, and `DestinationPolicy`
assigns every file its own relative path (`meta` is always empty in M0). A
*latent* protocol — one no M0 code calls, like `MetadataExtractor` — is
declared shape-only, with no implementation at all until its first consumer
arrives. New behavior is a new implementation behind the same shape — never an
edit to a consumer.

M1 removes the fingerprinted `worker_count` setting rather than replacing it
with another file-concurrency protocol. Workflow composition imports the one
concrete XXH3-128 constructor and supplies the same required, parameterless
`HasherFactory` to `NativeCopyBackend` and `VerifierContext`; `core` and the
operation modules do not construct or import the third-party implementation.

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
- **Annotation key namespace** — annotation keys are dot-namespaced by owning
  feature (`ingest.origin.*`, `task.note`, …) from row zero, so latent
  features' provenance keys (ingest origin evidence in particular) can never
  collide with early ad-hoc labels.
- **Nullable file-identity group** — room for future hardlink grouping.

M1 is one deliberate pre-release schema boundary, not an incremental migration:
the ledger advances to v2 for canonical XXH3-128 content evidence and history
advances to v3 for nominal phase-tagged result items plus reserved compound
phase summaries. Ledger v1 and history v1/v2 are refused with one actionable
reset posture, and development setup deletes/recreates both databases together.
The existing narrow history v1→v2 migrator must not stamp a v3 database.
Settings files survive this reset. A general migration framework remains later
work.
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
drive-qualified, `..`, ambiguous suffix/device/stream spellings, NUL, unpaired
surrogates, and root-escaping). Canonical JSON preserves valid-Unicode bytes and
escapes malformed surrogate code units rather than raising. Ledger command
hashing, history hash/detail serialization, and opaque workflow payloads use
the same final UTF-8 rule so free-form evidence cannot reopen that raw encoding
failure; path validation still rejects malformed path spellings upstream.

**Flesh.** None. Core is all bones by definition.

**Acceptance criteria.**
- The transition table permits exactly the legal edges and rejects all others,
  proven by an exhaustive table test.
- `normalize_relative_path` keeps NTFS-distinct names distinct across a Unicode
  special-casing corpus (`ß`, Turkish `İ/ı`, fullwidth forms).
- Path validation rejects every escape form and non-scalar surrogate while
  accepting every contract-legitimate root-relative path; canonical JSON never
  raises while encoding malformed free-form Unicode.
- Event `seq` is gap-free and monotonic per session under concurrent emit.

### 4.2 scanner

**Implementation status (2026-07-20).** The M0 native walking scanner,
injectable fault backend, full/scoped result distinction, exact ignores,
capability evidence, placeholder/reparse handling, deterministic records, and
typed incomplete snapshots are implemented and acceptance-tested. Raw names
outside the lexical path contract become escaped `PATH_UNREPRESENTABLE`
warnings without aborting safe siblings. Stable-ID volumes recover a
directory-entry identity omission with one exact-path metadata stat. USN and
network change sources remain deferred.

**Contract.** `scan(root, ignores, ctx) -> ScanResult`. Implements
`ChangeSource`.

**Bones.** The `ScanResult`/`FileRecord`/`CapabilityProfile` shapes; the
`complete` flag; cancellation via `ctx.checkpoint()`; visited-identity tracking
so junctions/reparse loops cannot recurse forever.

**Flesh — now.** Recursive metadata walk (size, mtime_ns, identity, nlink;
every directory recorded with metadata); pre-use raw-name validation; exact-name
ignore filtering; capability profiling; placeholder detection
(classify reparse/offline files `unsupported`, never open them); scan warnings.
**Flesh — deferred.** USN change-journal `ChangeSource`; network-share awareness.

**Acceptance criteria.**
- A directory junction that points into its own ancestor terminates the walk;
  it never recurses twice or hangs.
- A cloud placeholder file is recorded `unsupported` and is **never opened**
  (asserted by a read-tripwire in test).
- A partial/errored walk yields `complete=False`; a clean walk yields `True`.
- A contract-invalid file or directory name is escaped into typed evidence,
  makes the scan incomplete, is never opened/descended, and does not prevent a
  safe sibling from being retained.
- Ignored artifacts are matched only by exact qualified name; a user file named
  `my.synctmp-notes.txt` or `data.db` is **never** excluded (direct PoC
  regression tests).
- Cancellation observed within one directory/file step.
- exFAT root reports `stable_file_identity=False` and coarse
  `mtime_granularity_ns`.

### 4.3 planner

**Implementation status (2026-07-21).** The pure M0 planner and its core plan
contracts are implemented: identity assignment, timestamp- and
standard-attribute-aware metadata diffing, explicit
directory chains, correspondence-qualified file moves, composite move-update,
planned-removal cleanup, symmetric filters, deterministic surrogate-safe
serialization, non-blocking exact-case and canonical-Unicode advisories,
zero-byte conditional source-basename recasing, and the shared hardlink-aware
capacity function. Non-everything scopes and content evidence remain deferred.

**Contract.**
`plan(source: ScanResult, target: ScanResult, correspondence: MappingSnapshot,
options, scope) -> Plan`. Pure — every input is an immutable snapshot; the
workflow reads correspondence from repositories and passes it in.

**Bones.** `Plan`/`PlanOperation`/`Scope`/`MappingSnapshot` shapes;
deterministic op ids, dependency ordering, and the plan `fingerprint`; the
capacity formula (single source of truth, sized for max concurrent temps, and
profile-aware — an update on a target without hardlink support also counts the
displaced version's backup-copy bytes) with
**no observed free space anywhere in the plan** — capacity is a pure formula
over operations and capability profiles, free space is preflight's
observation; correspondence-aware
move detection (prior accepted identity↔path pairs — the PoC lost move
evidence because paired no-ops were never persisted); `filter_snapshot`
embedded in the plan; **diffing keyed through `DestinationPolicy.assign()`** —
the diff never compares `source.rel_path` to `target.rel_path` directly, even
though the M0 policy is the identity assignment. This one indirection is what
makes ingest a policy change instead of a planner rewrite.

**Flesh — now.** Mtime diffing within the coarser root's granularity plus
exact standard-attribute diffing;
copy/update/trash/delete/noop planning, with an explicit mkdir-with-metadata
operation for every directory the plan creates (full chain — file operations
depend on their parent's mkdir; the executor never creates a directory
implicitly); identity-based move detection
(disabled where identity is absent or `nlink>1` or an id appears at multiple
paths); directory rename decomposition (per-file identity moves + full mkdir
chain + emptied-dir cleanup — no directory-level move op exists in M0, and the
decomposition must exist regardless: a folder whose children also changed
content cannot collapse into one rename); composite move-update as one
operation; conflict blocking; capacity planning; `Scope.everything()`.
Exact-case mismatches across one source/target Windows key are typed advisories
on the ordinary update/no-op operation, not conflicts that suppress changed
content. The default keeps the observed target spelling. A fingerprinted,
payload-stable `propagate_source_casing` seam emits an explicit zero-byte
`recase` operation for metadata-equal files; changed files still use their
required update at the requested spelling. Recasing is a same-key,
non-replacing rename that preserves content, identity, metadata, and trash
state. It is off and unexposed by default and does not recase parent
directories. One-to-one same-parent file pairs whose basenames
are canonically equivalent under NFC carry a separate non-blocking Unicode
normalization advisory; the planner preserves observed spelling, performs no
normalization, and refuses to guess among ambiguous candidates or steal an
exactly matched target. Same-side case collisions and type collisions remain
blocked.
**Flesh — deferred.** Content-aware no-op; hash-based move detection; retained
human conflict resolution; `Scope.pattern/explicit/recorded_run` (filters,
partial exec, replay — all new scope constructors, zero planner-shape change);
ingest destination policies (naming templates, collision sequencing, companion
grouping) with enrichment metadata supplied by the workflow.

**Acceptance criteria.**
- Same input scans always yield byte-identical plans (determinism).
- Nested empty source directories plan the **full** mkdir chain, and a rerun
  converges to zero operations (PoC regression).
- A directory emptied by the plan's own trash/delete in the same run is itself
  cleaned up (plan reasons about its own removals, not just the pre-scan).
- Capacity `required_bytes` never undercounts concurrent updates; a selection
  preflight accepted against observed free space never hits ENOSPC the shared
  formula could have predicted. On a no-hardlink target, the formula includes
  the displaced versions' backup-copy bytes.
- Move detection consults prior correspondence: a rename whose evidence lives
  only in the mapping's recorded no-ops is still detected; with an empty
  correspondence snapshot, no false move is ever invented.
- On a stable-identity-less root, no `move` operation is ever emitted.
- A file whose identity appears at two paths, or with `nlink>1`, is never part
  of a move.
- `KEEP.txt`/`keep.txt` evidence produces a visible typed advisory while changed
  metadata still updates and matching metadata remains a no-op. Default target
  spelling is stable; the opt-in policy recases only the file basename through
  a zero-byte non-replacing rename with no trash entry.
- A one-to-one NFC/NFD basename pair produces exactly one non-blocking advisory
  update/no-op at the observed target spelling. Canonical ambiguity is never
  guessed through and an exact match is never reassigned.
- A renamed source folder decomposes into per-file moves, a full mkdir chain,
  and emptied-dir cleanup; the rerun converges to zero operations and the
  rename itself copies no content bytes.

### 4.4 preflight

**Implementation status (2026-07-20).** Scoped read-only observation and pure
typed judgment are implemented for selection-aware scan completeness, blocked
correspondence, root/volume, dependency, direct and parent evidence, capacity,
trash, containment, and path representation checks. M1 removes the obsolete
live-settings collaborator and drift checks; commitment validation remains
correctly outside this module at execution-workflow entry.

**Contract.** Two functions, deliberately split so purity is real rather than
claimed:

```python
def observe(xset: ExecutionSet, fs: FileSystem) -> ObservedWorld: ... # impure IO only
def preflight(xset: ExecutionSet, world: ObservedWorld) -> Verdict: ... # pure, judgement only, no IO
```

`observe()` does the scoped re-stat — it touches only the subjects the
remaining selected operations name (keyed `(root, rel_path_key)`, never a bare
string — both roots share the same rel paths), reads free space, resolves root
volume identity, retains the touched target-parent set, sums only exact
different-run temp bytes that execution will sweep from that set, and decides
nothing. `preflight()` renders every verdict from that snapshot alone and never
touches the filesystem. Planning already embedded the reviewed semantic
snapshot in the committed plan; execution consumes it and never rereads global
defaults.

The split is a bone, for three reasons: `preflight()` becomes exhaustively
testable against synthetic worlds with no temp directories; the expensive IO
happens exactly once per judgment and is never entangled with it — and every
judging session observes *fresh*: review, execution start, resume, and queue
wakeup each observe their own world, because closeness in time is not evidence
of unchanged state; and "pure" stops being an honor system. All IO lives in
one small function whose only job is statting.

**Bones.** The `observe`/`preflight` split; the `ObservedWorld` snapshot shape,
including the immutable touched-target-parent recovery scope;
the `Verdict` shape carrying per-op refusals plus the snapshot it judged;
observation scoped to operation-touched paths only.

**Flesh — now.** All checks: plan integrity (dependency-closed, no dep on a
deferred/failed/blocked op), blocked-correspondence quarantine, operation-class
scan-completeness gating, staleness, capacity
(counting reclaimable orphaned-temp bytes as recoverable), safety (roots resolve
to recorded `VolumeId`; trash resolves onto the target volume without reparse
escape and is writable). Commitment/policy-fingerprint checking is deliberately
**not** a preflight check — preflight also runs at review time, before any
commitment exists. The execution session entry verifies the captured semantic
snapshot and refuses an uncommitted or mismatched set before preflight runs
(§4.9); a later global-default change affects only future plans.
**Flesh — deferred.** User-edited partial selections and a graceful
`continue-with-skips` resume tier (M0 automatic safe-subset execution exists;
resume remains continue-or-refuse).

**Acceptance criteria.**
- `preflight()` performs no IO at all — it is called with no filesystem
  available in test and still renders every verdict.
- `observe()` never mutates anything (asserted by a read-only-filesystem
  harness) and never judges — it has no refusal logic.
- `observe()` stats only operation-touched paths; an unrelated change elsewhere
  in either tree never causes refusal (PoC regression — the original whole-tree
  preflight over-refused and was slow).
- An incomplete scan permits selected copy/update/mkdir/noop/recase work but
  refuses selected move/move-update/trash/delete work; manually reintroduced
  blocked correspondence is also refused.
- A nearly-full target whose exact prior-run temps in touched parents free the
  needed space is **not** refused; current-run temps and out-of-scope artifacts
  are not credited to the run-level sweep.
- Running the same `preflight` at review, at execution start, and at resume
  yields consistent verdicts for an unchanged world.
- Changing global semantic defaults after commitment does not alter or refuse
  the admitted plan; changing a task-local bound value during review invalidates
  that plan and requires a new fingerprint and commitment.

### 4.5 executor

**Implementation status (2026-07-21).** The M0 native single-worker executor
and its core execution contracts are implemented for all nine operation kinds,
with conditional publish, zero-byte non-replacing recase, guarded trash/delete,
deferred directory metadata, continuation state, bounded retries, throttled
progress, and post-mutation typed recording. ADS, restartable copies, parallel
workers, and IO throttling remain deferred as described below.

**Contract.**
`execute(xset, ctx, recorder, policies, fs) -> OperationResult`. The workflow owns the
observe → preflight → execute sequence on every start and every resume (§4.9);
the executor never imports or calls preflight. Its own defense is
**per-operation**: immediately before each mutation it re-validates that
operation's direct preconditions against the live filesystem — preflight is
one stage of TOCTOU prevention, never the last, because the world can change
between preflight and touch. Records only through `recorder`.

**Bones.** Typed-result return — the session runner owns `Terminal` (§2.2a);
atomic temp-then-`os.replace` publish with best-effort parent-dir flush through
a directory handle opened with `GENERIC_WRITE` access and
`FILE_FLAG_BACKUP_SEMANTICS` (a refused flush is a per-op warning; durability is
claimed only for what was flushed);
**displace-then-replace update order** — the live target is preserved
into trash by atomic same-volume hardlink — with a copy fallback on volumes
reporting no hardlink support, itself written temp-flush-publish *inside the
trash run directory* so a partial backup only ever exists under a temp name —
*before* `os.replace` publishes over it, so no crash point leaves the
live path absent — a readonly live target has its readonly bit cleared before
replace (Windows refuses to rename over a readonly file), with the original
attribute preserved in the plan's metadata snapshot — and composite
move-update publishes at the new path before trashing the old, so a crash
leaves both versions present, never neither; the
temp-name shape `<name>.synctmp-<run-id>-<op-id>`; trash-restore planning
ignores exact-shape temp names (a partial backup is never restorable) and
orphaned trash temps age out with the trash run directory — temp recovery
itself still never walks `.synctrash`; per-operation final guards — the
executor's own last line of TOCTOU defense (no overwrite of unexpected
targets, source evidence re-checked at touch, type/emptiness checks before
directory trash/delete), enforced through operation-matched **conditional
primitives** where the OS provides them: publishes and moves that expect an
absent destination use non-replacing rename (atomically fails if something
appeared), temp files are created `CREATE_NEW`, and directory deletion relies
on `RemoveDirectory`'s own atomic emptiness refusal. Dependency-complete
`directory_cleanup` deletes retain exact kind, size, attributes, and creation
time but ignore mtime/link-count churn caused by their own child removals;
identity binds when the reviewed scan supplied it, while absent identity remains
absent evidence rather than a veto. A primitive guarantees
exactly its own condition and nothing more — none binds *source* identity to
a pathname — so the external-writer boundary applies to **every** mutation,
and each residual race is bounded by its **data consequence**, never by
elapsed time (the gap between syscalls is usually tiny but not
scheduler-bounded): trash-routed operations at worst preserve the wrong item
recoverably, moves at worst misplace without destroying, and only update's
replace and internal mirror deletes can destroy an external writer's file —
never NamiSync's displaced version, never its evidence, since attestation
subjects are always NamiSync's own published files. `ReplaceFileW` — the
supported single-call replacement with optional backup — is deliberately not
used: it merges the replaced file's attributes, ACLs, and named streams into
the replacement and documents partial-state failure cases;
hardlink/copy-backup-then-replace is a chosen tradeoff, not the only Windows
primitive; readonly applied only after publish; directory metadata applied
only after the directory's children settle (child creates and renames churn
parent times — directory times are restored last); the cancel-unwind finalizer
(§2.2a — canceled outcomes for in-flight and unreached items emitted before
unwind); content-only byte accounting; the `FailurePolicy`/`CopyBackend` seams;
and process-local retry continuations for committed update/move-update sub-steps,
which revalidate the exact prepared/published and backup/trash evidence before
resuming rather than restarting against the executor's own prior mutation.

**Flesh — now.** copy/update/recase/move/mkdir-with-metadata/trash/delete/noop;
hash-on-copy; source-drift guard (re-stat source after read; mismatch fails
the op, records nothing); trash-on-update; root-local trash with volume-identity resolution;
one post-verdict, pre-copy prior-run temp sweep over preflight's exact touched
parents plus per-operation current-run temp cleanup; per-op continue-on-failure;
chunked cancellation.

**Flesh — M1 executor/hash refactor.** Every normal copy uses one immutable
linear `caller/reader → hasher worker → writer worker` pipeline; there is no
size-selected serial engine and no concurrent file execution. `_prepare_copy()`
selects the actual read size from reviewed source size and the 4 MiB
`max_chunk_size` default:

| Reviewed size | Actual chunk before policy ceiling |
| --- | ---: |
| less than 8 MiB | 256 KiB |
| at least 8 MiB and less than 32 MiB | 1 MiB |
| at least 32 MiB | 4 MiB |

One combined 32 MiB payload ledger owns each immutable chunk across both
bounded FIFOs; each FIFO has 32 entries. The caller performs checkpoint and
progress callbacks, and `on_chunk(size)` occurs only after the hasher consumed
and the writer fully wrote that chunk. The selected size remains fixed if the
source grows; the backend reads to actual EOF and the executor reports
`SOURCE_DRIFT`. A deliberately lower `max_chunk_size` may reduce the effective
window but cannot weaken correctness or deadlock freedom.

Normal target temps are conditionally preallocated above a measured crossover.
Windows bindings are hoisted and bound once. Buffered source handles carry the
sequential-access cache hint, complementary to the application's bounded
payload lookahead; no second application readahead queue exists. Temp metadata
and the sole pre-publish `FlushFileBuffers` call share one finalization handle.
After atomic publish, the executor observes metadata and reopens for repair only
when publication changed a required value, especially readonly application.
The copied-backup fallback shares finalization primitives but retains its
dedicated serial, hashless 4 MiB byte loop without preallocation.

The source stream and published target are bound by two size invariants:
`CopyDigest.size` must equal the reviewed/observed copy byte count at the
executor boundary, and every `Attestation` globally requires
`content.size == subject.size`. Copy and verifier both use the required
XXH3-128 factory, but the verifier retains its independent cache-honest opener
and fixed 4 MiB reads.

**Flesh — deferred.** Validated partial execution (`DEFERRED` outcomes);
executor-time ADS stream copy (per the settled FEATURES → *ADS Preservation*
contract); restartable large-file copy; concurrent file workers; background
IO throttling; Robocopy backend; batching; direct/unbuffered copy IO;
overlapped cross-file publish; and lazy worker startup for zero/one-chunk files.
If directory-level measurements justify the last item, it remains one pipeline
with an inline first-chunk fast exit rather than a maintained serial engine.

**Acceptance criteria.**
- Every executor path — success, failure, cancel, pause, refusal, exception —
  returns or raises such that the session runner emits exactly one `Terminal`,
  proven by fault injection at each operation.
- A crash after temp write but before publish leaves the real target untouched;
  a rerun converges. No partial file is ever published.
- No crash point in an update leaves the live target absent: before publish the
  old content is still live, after publish the new content is, and the trash
  hardlink/copy preserves the displaced version across every interleaving
  (fault injection between each step).
- An update interrupted between displace and replace leaves the live target
  with a benign extra link into `.synctrash`; the next scan reports it as a
  hardlink warning (conservatively excluded from move detection), and a rerun
  converges — a documented interaction, not a defect, resolved when the trash
  entry is purged.
- Source changed mid-copy ⇒ op `FAILED`, **no** attestation recorded (PoC gap).
- A first blocked/failed operation never aborts later independent operations
  (the "walk away for hours" guarantee — the PoC's original SEVERE bug).
- Temp recovery deletes only exact-shape, different-run regular files in the
  preflight-retained touched parents. Current-run temps, lookalikes, exact-name
  directories, untouched parents, off-volume mounts, and `.synctrash` survive;
  a sweep failure occurs before copy allocation, so credited capacity is never
  used unsafely.
- Trash that would land off-volume or through a reparse point is refused before
  any move.
- Fault tests exercise an external path swap *between* a final guard and its
  destructive call, not only drift before the guard, and assert the **data
  consequence**, never elapsed time: each conditional primitive fails cleanly
  on exactly the condition it enforces, trash-routed swaps land recoverably in
  trash, and the update residual's worst case matches the documented bound
  with no silent ledger corruption.
- Cancellation during a multi-GiB copy takes effect within one chunk.
- The adaptive helper selects and caps the exact three bands at both
  boundaries; empty, partial, exact, and multi-chunk files all exercise the
  same backend, and a growing source keeps its initial selection before failing
  as `SOURCE_DRIFT`.
- Pipeline failure, pause, cancellation, callback error, full-queue EOF, and
  worker teardown release every payload charge exactly once, join both workers,
  preserve the initiating error, and publish no partial target.
- A successful copy cannot construct evidence whose hashed byte count differs
  from the published target size.
- All volume locks are released on every terminal path (custody is the
  session's, not the executor's — but the executor must not leak temps).

### 4.6 verifier

**Contract.** `verify|baseline|rebaseline(selection, ctx, recorder,
reader=None) -> IntegrityRunResult`. `VerifierContext` requires the same
parameterless `HasherFactory` used by the copy backend. Records through
`recorder`.

**Bones.** Per-file `IntegrityOutcome` emission (no silent-until-done); the
cancel-unwind finalizer (§2.2a — canceled outcomes for in-flight and unreached
items emitted before unwind); the integrity-outcome vocabulary (verified,
baselined, mismatched, modified, missing, unsupported, canceled, error);
attestation provenance tagging.

**Flesh — operation module implemented early during M0 construction; integrated
in M1.** Baseline creation; location verification against the
size/mtime/identity/hash unit; selected and post-execution verification;
cache-honest reads; safe conditional recording; accept/re-baseline of a modified
file; item-status continuation — verify/baseline sessions pause and resume over
their remaining selection exactly like execution (same continuation pattern,
same preflight-on-resume posture). The callable module, real Windows unbuffered
reader, and conditional ledger primitive are present before M1, but inventory
refresh, integrity workflow/history detail, dispatcher registration, and
interfaces remain the M1 product gate.

M1 replaces content SHA-256 in baseline, verify, rebaseline, and copy together
with canonical XXH3-128; no interval exists where the two consumers write
different evidence formats. Ledger-bound selections and transient post-copy
candidates share one guarded open/stat/hash/classification body. The latter are
constructed by the workflow from `PublishedCopyEvidence` and remain
classifiable when the copy-ledger transaction failed; only a candidate with
durable matching row evidence may conditionally advance ledger verification
state. Immediate
readback is independent evidence against ordinary copy/IO/recording failures,
not a defense against malicious in-process executor code.

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
- A matching transient post-copy candidate is classified even when no ledger
  row was written; recording remains degraded instead of suppressing readback.
- Copy and verifier evidence round-trip through the same XXH3-128 factory and
  16-byte encoding while retaining different source/readback opener semantics.

### 4.7 db (recorder + repositories + history observer)

**Contract.** `recorder.py` implements `Recorder` and is the sole ledger writer.
`repositories.py` holds all reads. `history.py` is an event-stream observer with
its own database. `schema.py` owns both schemas and the version stamps.
`settings.py` owns schema-versioned semantic defaults in `settings.json`;
planning receives a snapshot through injected runtime composition, while
admitted execution never rereads it.

**Implementation status (2026-07-20).** The versioned ledger/history schemas,
safe writer/read-only connection factories, canonical UTC codec, serialized
retrying writer, run-bound sync recorder, batched inventory reconciliation,
conditional baseline/verify/rebaseline writes, typed ledger repositories, and
minimal sync history observer/repository, blocked/deferred item audit, and the
transactional additive history v1-to-v2 migration are implemented. M0 commands commit
eagerly, so `flush()` preserves the final boundary while the crash window is
zero completed commands. Cross-process contention is bounded and visible.

**Bones.** Single serialized writer; the conditional-recording primitive (write
gated on row id + state + size + mtime still matching the observation) shared by
copy/verify/baseline; bounded-window durability with forced flush before
any destructive op, at pause-drain, and at terminal; run-token idempotency;
WAL + foreign keys + bounded busy timeout; the §3 schema-freeze columns. History
has **no** foreign key to the ledger and its failures never roll back real work —
but history is audit, not disposable telemetry: it subscribes at admission with
guaranteed (timeout-guarded, backpressured) delivery, acknowledges its final
write before the `Terminal` is released (the two-phase finalization of §2.2a),
and its write failures surface on the session result's `audit` axis (§2.3).

**Flesh — implemented (M0).** Recorder for sync operations; missing-marking sweep
(batched — never one giant `NOT IN`); inventory reconciliation. History observer
in minimal form: run envelopes plus sync summaries and ordered operations,
including a sixth blocked outcome and deferred exclusion reasons —
enough to satisfy *every explicit sync is history-worthy* and to back the CLI's
`history` command. The observer is cheap precisely because it is only an event
subscriber; nothing calls it.
Conditional verify/baseline/rebaseline recording landed early with the isolated
verifier during M0 construction. **Flesh — M1.** History integrity summaries
and retained issue detail; generic `ResultItem` persistence; reserved compound
`PhaseResult` storage used by linked verification; integrity workflow
composition; and the coordinated ledger-v2/history-v3 reset.
Semantic-settings commits hold a named cross-process mutex only across
read-current → modify-owned-keys → temp-write → atomic-replace, so concurrent
GUI/CLI writers cannot lose one another's updates.
**Flesh — deferred.** History retention waits for a maintenance session with
cross-process history-writer custody; no M1 retention setting, facade action, or
direct UI SQL exists. Also deferred: general migration module; legacy import;
scheduled backup/quick-check (as an ordinary session); export/import; ledger
merge across hosts.

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
- When retention eventually returns, it runs on a writable connection under
  cross-process history-writer custody and actually removes expired rows (PoC
  SEVERE write-through-readonly bug); this is not an M1 gate.
- Every ledger commit follows its filesystem observation and precedes the next
  batch boundary; a crash loses at most one batch and never a committed truth.
- A repeated run token is a no-op in both databases.
- A completed run with a failed ledger write reports `COMPLETED` with
  `recording=DEGRADED`, both visibly; the next scan converges the ledger
  (axis-separated truth — never inverts a successful result, never hides a
  behind ledger).

### 4.8 dispatcher

**Contract.** `submit(kind, request) -> SessionId`; `pause/resume/cancel(id)`;
`subscribe(id) -> stream`; `list()/get(id)`. Imports core only; resolves `kind`
through an injected workflow registry it never introspects; a registry entry
declares generic per-kind capabilities (today: pause support) that the control
plane enforces without learning a domain word.

**Bones.** Generic session admission; volume-scoped concurrency (non-overlapping
volume sets run in parallel, contenders queue); resource custody (locks acquired
on start, released on terminal or pause-drain — one owner); the control plane
over the transition table; event sequencing + fan-out; the **`SessionStore`
protocol** and the serialized session-record shape (lifecycle fields + an
**opaque** per-workflow blob the dispatcher never deserializes) — this store is
the sole exception to *the dispatcher never writes a database*; orderly teardown.

```python
class SessionStore(Protocol):
    def put(self, rec: SessionRecord) -> None: ...
    def load_all(self) -> Sequence[SessionRecord]: ...   # in-memory impl returns ()
    def drop(self, sid: SessionId) -> None: ...
```

**Flesh — implemented (M0).** `InMemorySessionStore` — the degenerate implementation;
`load_all()` returns nothing, so there is no reload and nothing to reconcile. A
process death in M0 simply loses the session table, and recovery is the ordinary
convergence model: rescan, replan. `INTERRUPTED` exists in the enum from day one
but nothing produces it yet — a declared-but-unreached state, the same
shape-only rule as latent protocols (§2.7). Also now: volume-scoped admission;
**real cross-process volume locks** — a named OS mutex or lock file keyed by
volume serial, with abandoned-holder recovery defined — because two CLI
processes exist on day one and in-process scheduling alone cannot make the M0
executor safe (the durable queue-*owner* lock stays M2; mutation *exclusion*
does not wait); pause/resume/cancel — resume re-enters admission at the back
of its volumes' queue and never preempts a running session (FEATURES → *Resume
Never Preempts*); a bounded per-session replay buffer (late subscribers get
current state plus a bounded tail plus an explicit `Gap`).
Terminal session records are retained until explicitly closed (the task-card
dismissal), then dropped — the session table is the live view, history is the
durable trail — and a queued session discarded before running writes its
history entry first.

**Flesh — deferred (M2).** `SqliteSessionStore` — the durable implementation
behind the same protocol; reload on launch; startup reconciliation (dead-process
`RUNNING` ⇒ `INTERRUPTED`, routed into preflight-then-continue); single
queue-owner via a file lock on the persisted store; durable queue with launch
policy; configurable event-conflation policy (M0 already coalesces progress in
bounded live/replay buffers); local-pipe CLI-as-client.

**Acceptance criteria.**
- No dispatcher symbol names a domain activity; it never imports modules or
  workflows (import-lint enforced).
- Two sessions on disjoint volume sets run concurrently; two contending for one
  volume serialize.
- Every session reaches a terminal and releases every lock on every path,
  including exceptions and teardown (custody conformance).
- The stored per-workflow blob is never deserialized by the dispatcher.
- **M2:** after a simulated process kill, reconciliation marks the orphan
  `INTERRUPTED` and routes it through preflight-then-continue. M0 instead proves
  honest process-local loss plus abandoned volume-lock recovery.
- A `Progress` flood never stalls a slow subscriber or the producer; a
  `RELIABLE` event reaches the history observer or the session's `audit` axis
  reads `DEGRADED`; an ejected subscriber always sees an explicit `Gap`.
- Two processes contending for one volume serialize through the OS-level lock;
  killing the holder mid-run releases it (abandoned-lock recovery proven by a
  process-kill test).

### 4.9 workflows

**Contract.** Plain functions that sequence modules by passing typed data
forward. The only place modules meet.

```python
def run_plan(req: PlanRequest, ctx, deps) -> Plan: ...            # session 1: scan → plan → observe → preflight
def run_execution(cont: ExecutionContinuation, ctx, deps) -> OperationResult: ...
    # session 2: observe → preflight → execute [→ verify];
    # consumes a COMMITTED ExecutionSet only
def run_integrity(req, ctx, deps) -> IntegrityRunResult: ...
    # standalone inventory / baseline / verify / rebaseline

@dataclass(frozen=True)
class ExecuteContinuation:
    phase: Literal["execute"]
    execution_set: ExecutionSet

@dataclass(frozen=True)
class VerifyContinuation:
    phase: Literal["verify"]
    execution_set: ExecutionSet
    candidates: tuple[PostCopyCandidate, ...]       # verify phase only
    completed_verification_ids: frozenset[str]     # verify phase only
    verified_bytes: int                            # verify phase only

ExecutionContinuation = ExecuteContinuation | VerifyContinuation
```

`ExecuteContinuation` and `VerifyContinuation` are workflow-owned payload
contracts. They may reference the core-owned `ExecutionSet`,
`PublishedCopyEvidence`, and `PostCopyCandidate`; core never imports workflow
payload types. The dispatcher stores and returns their schema-versioned JSON
envelopes opaquely. The workflow is the sole translator from executor-produced
`PublishedCopyEvidence` to verifier-consumed `PostCopyCandidate`, so executor
and verifier remain sibling modules with no direct dependency; the integrity
contract does not import the execution contract.

**A sync is two sessions, not one.** This is how mandatory dry-run review
coexists with *sessions never block on a human*: review happens **between**
sessions, not inside one. `run_plan` terminates with a `Plan` as its result —
locks released, nothing running, no state pending. The human reviews while the
M1 process retains that plan. Closing the application loses process-local plans
and continuations; durable plan/session recovery remains M2 and M1 never claims
otherwise. Submitting the reviewed `ExecutionSet` starts `run_execution`, which
re-observes and re-preflights because the world has moved on since review.

Everything downstream falls out of this split:

- A **queued job** is exactly a *committed* `ExecutionSet` awaiting its second
  session — which is why `ExecutionSet` is serializable and why the
  dispatcher's opaque blob has something to hold. A *paused* execution is the
  same object again (§2.2), so queue wakeup and resume are one path.
- **Stale-plan defense** is not a special queue feature; the second session
  always preflights, whether the gap was 5 seconds or 5 days.
- **Partial execution, filters, and replay** change only the `Selection` or
  `Scope` carried between the two sessions — neither session's shape changes.
- **M0 safe-subset execution** derives that selection deterministically from
  the full reviewed plan. Direct blockers are `BLOCKED`; path-correspondence or
  dependency collateral is `DEFERRED`; incomplete scans globally withhold
  move, move-update, trash, and delete while retaining guarded copy, update,
  mkdir, noop, and recase. The plan fingerprint still binds full intent and the
  commitment digest binds the exact runnable subset.
- **There is no no-gate path.** Every execution session consumes a *committed*
  `ExecutionSet` — one a human reviewed and explicitly committed, bound to the
  plan's fingerprint. The commitment is the durable preauthorization: its
  scope is the `ExecutionSet`, its fingerprint is the plan's, and it never
  expires — an uncommitted plan stays a plan forever, and a committed one
  whose world drifted parks as refused for re-review, never silently
  re-planned. Scripted and queued execution *replay* commitments (the CLI
  confirms in the terminal between the two sessions; a queue-release flag runs
  already-committed sets); nothing plans and executes in one unreviewed
  breath. Committed sets execute sequentially in commit order when they
  contend, immediately when their volumes are free.
- **Linked verification is a phase, not a chained session.** If requested,
  `run_execution` retains the same session and volume custody after execution,
  derives transient candidates from every successfully settled `COPY`,
  `UPDATE`, and `MOVE_UPDATE`, and calls the verifier's shared guarded
  classifier. It does not query the ledger to rediscover candidates: a failed
  copy-ledger transaction degrades recording but cannot suppress immediate
  readback of published bytes.
- **Published evidence is continuation state.** `_settle()` stores operation
  success and its `PublishedCopyEvidence` together before emitting the reliable
  result. A successful byte-producing status without evidence makes
  verification incomplete. `phase=execute` preserves statuses plus published
  evidence; `phase=verify` additionally preserves candidates and completed
  verification ids/bytes. Same-process pause/resume is lossless; application
  restart is not supported until M2.
- **Compound truth remains separable.** One ordered nominal `ResultItem` list
  preserves execution and integrity outcomes with explicit phase/type tags,
  while `PhaseResult` keeps transfer and readback progress separate.
  Filesystem, integrity, recording, and audit axes never rewrite one another.
  A target stat change is `modified`; only stat-stable byte divergence is a
  mismatch.
- **One logical recording spans both phases.** Workflow opens one recorder
  invocation and exposes narrow execution/integrity views rather than competing
  writers. It finishes the logical run once at compound terminal settlement; a
  pause may close and idempotently reopen the same run token on resume.

**Bones.** The two-session split; top-to-bottom sequencing (scan → plan →
observe → preflight → execute [→ verify], or location resolve/register → scan
→ inventory → standalone integrity); the explicit execute/verify continuation;
no signals, no callbacks-for-control; every dependency arrives via `deps`.

**Implementation status (2026-07-20).** M0 paired sync now runs both dispatcher
sessions through schema-versioned opaque payloads. Planning reads prior
correspondence without creating configuration, derives and reviews the maximal
safe dependency-closed subset, and preflights that selection. Execution verifies
commitment, freshly observes/preflights under volume custody, then opens the sole
ledger writer and independent history observer. Exclusions are emitted as
itemized blocked/deferred audit outcomes after selected execution settles; they
never become main-ledger evidence. The CLI commits only between terminal
sessions and exposes the resulting typed history reads.

**Flesh — implemented (M0).** Paired sync (both phases), automatic safe-subset
selection, local composition, CLI terminal review/commit, and history browsing.
**Flesh — M1.** Role-free one-location inventory; standalone
inventory/baseline/verify/rebaseline sessions; integrity preflight on start and
resume; in-session post-execution verification; nominal mixed result/history
items and phase summaries; a shared facade and expanded CLI; and the desktop
shell. **Flesh — deferred.** Queue-driven durable second sessions;
replay-from-history; DB maintenance/retention session; undo/repair (each
generated as an ordinary plan through the same pipeline — the
*Pipeline-Only Mutation* law); `run_ingest` — scan → enrich
(`MetadataExtractor`, its own cancellable stage) → plan (template
`DestinationPolicy`) → the same review gate, preflight, and executor as sync.

**Acceptance criteria.**
- The workflow reads top-to-bottom as sequential calls; control flow is visible,
  not emergent.
- No workflow ever waits on user input; `run_plan` terminates and releases every
  lock while a plan awaits review.
- `run_execution` always re-observes and re-preflights, regardless of how
  recently `run_plan` ran — it is the sole pre-mutation preflight; the
  executor's own defense is per-operation precondition re-checking, never a
  preflight import.
- A refused preflight short-circuits to a `REFUSED` terminal with no mutation.
- A direct blocker cannot refuse independent safe work. Corresponding paths and
  dependencies remain quarantined, and incomplete scans cannot authorize any
  destructive or identity-move operation.
- Successful selected work remains filesystem `COMPLETED`; blocked/deferred
  exclusions are separately itemized and presented as partial completion.
- An execution session refuses an uncommitted or fingerprint-mismatched
  `ExecutionSet` before preflight even runs.
- Every successful byte-producing operation supplies exactly one published
  evidence entry, and linked verification consumes that handoff even when the
  copy-ledger write failed.
- Pause in either compound phase resumes only remaining work from the explicit
  phase discriminator, without repeating reliable outcomes; restarting the M1
  process offers no false resume.
- Verify mismatch, incomplete verification, ledger degradation, and audit
  degradation remain visible without changing an already successful
  filesystem phase.
- Every mutation of managed user data flows through plan → preflight → execute —
  including future undo and repair — so their conflicts with later runs surface
  in ordinary plan review.

### 4.10 interfaces (cli / api / desktop)

**Contract.** Adapt dispatcher + workflow state to a surface. Own no sync policy.

**Bones.** Read dispatcher session table for status; subscribe to event streams;
translate user intent into `submit`.

**Flesh — now (M0).** CLI `sync` (plan → terminal review → commit → execute) +
`history`; runnable/blocked/deferred review and partial-completion exit 6; real
entry-point wiring; no-subcommand prints usage and exits nonzero until the
desktop exists.
**Flesh — M1.** `interfaces/service.py` becomes the shared facade/composition
surface for both adapters, with typed commands/views, session observation,
result classification across all four axes, and process-local
`save_plan`/`get_plan`/`drop_plan` methods (no speculative `PlanStore`). The CLI
is retargeted without changing equivalent M0 behavior, then gains inventory,
baseline, verify, and rebaseline. CLI and desktop adapters may import the
service but not one another; the service reaches database-owned settings
through its injected workflow/runtime dependency and never imports `db`
directly.

`ResultCategory` chooses one headline without hiding secondary axes:
`failed > partial > refused > mismatch > canceled >
verification-incomplete > recording/audit degradation > all-noop > success`.
Filesystem, integrity, recording, and audit details remain individually
renderable regardless of the headline.

The M1 desktop is a pywebview host forced to Edge Chromium/WebView2. It exposes
one versioned allowlisted `dispatch` endpoint, uses structured pull/RPC and a
bounded/coalescing event drain, cancels untrusted navigation/new-window
requests through native hooks, and rejects dispatch outside the exact packaged
origin. UI commands carry opaque ids rather than paths; rendered filenames use
escaped display strings and `textContent`, never raw HTML. The task rail, plan
tree, inventory tree, and history dialog consume facade views only.
Interfaces own cosmetic `ui-state.json` (recents, geometry, columns, sorting)
directly; it is separate from database-owned semantic settings and needs no
cross-interface writer mutex.
**Flesh — deferred.** Web API, durable cross-process task visibility, richer
desktop surfaces, and other interfaces behind the same facade.

**Acceptance criteria.**
- The real entry points (`nami-sync`, `python -m namisync`) dispatch by actual
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

1. **One terminal, always** — control flow guarantees it (the session runner,
   §2.2a).
2. **Checkpoint everywhere** — every loop yields to pause/cancel at one call.
3. **Never wrong, only behind** — committed evidence is always true; recovery
   reconciles, never rolls back true evidence to look tidy.
4. **Records are calls that may fail loudly; telemetry is a stream that may be
   missed silently.** The ledger is a record. History is *audit*: guaranteed
   delivery over the event plane (bounded, timeout-guarded backpressure) unless
   the session result's `audit` axis loudly says otherwise — never silently
   absent — with best-effort durability, and it never alters or blocks a
   filesystem outcome. Progress is telemetry.
5. **Policies decide, the machine enforces.** Extension points return decisions,
   never receive control.
6. **Pipeline-only mutation** of managed user data (§4.9); app-owned artifacts
   are exempt but stay guarded and logged.
7. **Sessions never block on a human.**
8. **Identity by conservative evidence** — volumes, files, renames all match on
   corroborated evidence and refuse to guess when ambiguous.
9. **Exact-name recognition** of NamiSync's own artifacts — never suffix/substring.
10. **One injected clock**, UTC everywhere, converted only at the presentation edge.
11. **Commit-to-execute** — mutation of managed user data happens only under a
    committed, fingerprint-bound, human-reviewed plan; scripts and queues
    replay commitments, never mint them.
12. **Axis-separated truth** — filesystem, integrity, ledger recording, and
    audit status are reported separately; no axis ever rewrites another.
13. **Canonical content evidence** — copy, baseline, and verification use only
    XXH3-128 with a 16-byte digest, and attested byte count equals subject size.
    Non-content identity hashes remain SHA-256.
14. **Explicit compound continuation** — execute/verify phase, published
    evidence, candidates, and completed readback state are serialized facts;
    phase is never inferred from prior events.

---

## 6. Build order

- **M0 — walking skeleton.** core contracts (incl. the session runner) →
  dispatcher with `InMemorySessionStore` + cross-process volume locks → two
  dummy operations proving pause/cancel/lock-release → scanner → planner (with
  correspondence input) → observe/preflight → executor on plain NTFS
  (displace-then-replace updates) → recorder + minimal ledger (schema-freeze
  columns present, `flush` a no-op) → minimal history observer (sync envelopes
  + summaries) → CLI `sync` (plan → terminal review → commit → execute) and
  `history`. Ships a real, safe, hash-on-copy sync tool with an audit trail. The
  isolated verifier operation may land in parallel during M0 construction, but
  does not broaden this shipping gate without its inventory/workflow surface.
- **M1 — integrity product and executor refactor.** Build in this dependency
  order:
  1. contracts and semantics — canonical XXH3-128 evidence, nominal result
     items/phase summaries, four truth axes, execute→verify continuation,
     two-database reset boundary, split settings ownership, and facade/bridge
     security contracts;
  2. executor refactor — first the complete adaptive pipeline and Windows
     IO/finalization reductions from `HASH_REFACTOR.md` Track 1, then the
     coordinated executor+verifier XXH3-128 replacement and ledger-v2/
     history-v3 reset from Track 2;
  3. role-free inventory plus standalone baseline/verify/rebaseline workflows;
  4. in-session post-execution verification as one vertical integration slice;
  5. shared facade and CLI expansion; and
  6. the pywebview/WebView2 desktop shell against settled facade views.

  After the contracts are fixed, HASH Track 1 may proceed beside inventory
  production and standalone result/event work. Standalone hashing waits for
  HASH Track 2; post-execution integration waits for standalone integrity;
  new CLI commands wait for their workflows; GUI data binding waits for the
  facade and compound contracts. History retention is not part of M1.
- **M2 — durability & scope.** `SqliteSessionStore` behind the existing
  protocol; reload + startup reconciliation (`INTERRUPTED` gets its first
  producer); single queue-owner lock; durable queue and plans; event
  conflation; and cross-process task visibility.
- **M3+ — maintenance & scale.** Cross-process-coordinated history retention
  and data protection; file-level copy/verify concurrency only after new
  utilization evidence; USN change source; migration module; ingest,
  replay/repair, and additional interfaces.

Each milestone is gated by its modules' §4 acceptance criteria. A criterion is
not "tested" until it has a failure-injection or regression test named after the
behavior it protects — most of them trace directly to a PoC bug, and that bug is
the test's reason to exist.
