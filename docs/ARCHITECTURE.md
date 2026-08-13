# NamiSync Architecture

This document is the structural reference. `FEATURES.md` says *what NamiSync
does*; this says *how the pieces are shaped and how they talk*. Where the two
overlap, FEATURES.md owns behavior and this owns contracts.

Every section separates **bones** from **flesh**:

- **Bones** are load-bearing structure — types, protocol shapes, invariants,
  and identity decisions that are expensive or impossible to change once data
  and dependents exist. A bone lands at the last responsible irreversible
  boundary or with its first consumer; “bone” is not permission to merge
  speculative caches, projections, or presentation helpers early.
- **Flesh** is behavior that hangs off the bones and grows additively — new
  operations, new policies, new features. A missing piece of flesh is a later
  commit, not a rewrite.

The guiding rule (see FEATURES.md → *Degenerate First Implementations*): settle
each required bone before dependents make it costly to change, ship the simplest
correct first consumer, and let later flesh arrive through that proven seam.

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
interfaces/    launcher, cli, api, web
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
- **A domain component may be a module or a package.** Package internals may
  collaborate behind one component facade; that is not a sideways dependency.
  Import linting applies independence to the five component roots (`scanner`,
  `planner`, `preflight`, `executor`, and `verifier`), not to every descendant
  file. Code outside a component imports its public facade. Tests patch the
  internal submodule that owns a private symbol rather than a facade re-export.
- **Adapters are siblings.** `interfaces/launcher.py` may dispatch to `cli` or
  `web`; neither adapter imports the other, and both reach domain behavior only
  through `interfaces/service.py`.
- **Database-pair policy belongs to composition.** `workflows/database_pair.py`
  classifies and initializes the ledger/history pair because workflows may
  import the database layer; `interfaces/service.py` exposes only its primitive
  view. Adapters neither import SQLite ownership nor recreate pair policy.
  Mutating workflow preparation ensures both stores before dispatcher audit
  observation, while pure plan review and standalone history reads do not
  create a missing peer.
  Fresh-pair ownership is delegated to its Windows native leaf: reservations
  retain artifact identity, and rollback derives a delete-capable handle from
  that reservation for exact-object disposition so pathname replacement cannot
  redirect cleanup.
- **Desktop pathname leases belong to the adapter.** `interfaces/web/paths.py`
  pins the app directories and ready database mains against reparse/rename
  substitution for the headed process lifetime. This protects composition
  artifacts without moving filesystem sync policy into the interface layer.

### Dependency direction (bones)

Every collaborator a module needs — recorder, clock, policies — is **received**
as an argument, wired once at a single composition root. No module constructs
its own collaborator. This is what makes every module testable with fakes and
what keeps the SQLite/desktop-host/OS surfaces injectable rather than hardcoded.

The settled maintenance packages have explicit internal direction:

```text
executor/__init__.py  -> runtime.py, native.py, pipeline.py
executor/runtime.py   -> native.py, pipeline.py
executor/native.py    -> core + stdlib
executor/pipeline.py  -> core + stdlib

verifier/__init__.py  -> engine.py, native.py
verifier/engine.py    -> native.py
verifier/native.py    -> core + stdlib
```

`native.py` and `pipeline.py` are executor leaves: neither imports the other or
`runtime.py`. Verifier `native.py` likewise never imports `engine.py`. Both
component packages implement these boundaries behind unchanged public facades.
Verifier reader polymorphism crosses a core
`AuthorityBoundVerificationReader` protocol: engine owns selected-root and
opened-volume policy, while an authority-bound native open derives its only
root from the supplied ephemeral authority.

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

Pause normally unwinds rather than blocking in place — a blocked stack would
hold the volume custody that `PAUSED` promises to release. The narrow exception
is a retry-backoff checkpoint while process-local COPY/UPDATE/MOVE_UPDATE state
owns staged or published filesystem state, or a non-byte mutation marker owns
unsettled durable truth: pause is latched until that operation settles, then
unwinds at its ordinary boundary. Production backoff contributes
at most 350 ms; remaining delay is uncapped I/O over already-staged data, never
another main-file copy. Cancellation still unwinds immediately and preempts the
latch. The continuation state a pause must preserve is explicit. In the execute phase,
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
item-processing module's own unwind finalizer emits a state-derived outcome for
the in-flight item and `CANCELED` for every unreached selected item before
`Canceled` leaves the module. An unfinished byte operation whose target already
published is `FAILED/canceled-after-publish`, recording is degraded, and no
success-only published evidence is invented; a durable or ambiguous non-byte
attempt is `FAILED/canceled-after-mutation`; and an unpublished prepared or
proven-unchanged attempt remains `CANCELED`. On `PauseRequested` the finalizer
emits nothing for unreached work, because it remains pending for resume.
Emit-as-you-go plus this unwind finalizer means the runner never introspects
module internals.

Audit finalization is a two-phase step, not a circularity: before the runner
emits the one immutable `Terminal`, it drains the audit subscriber and races
the pump against the production ownership cutoff through one atomic decision
latch. If the caller wins, it releases `audit=DEGRADED`, and any row the late
pump commits carries that same degraded axis. If the pump wins, the caller
waits for its actual commit result: success stamps both live and retained
`audit=OK`, while failure stamps live `audit=DEGRADED` and leaves no
contradictory row. Production derives a six-second audit cutoff from the
five-second history-writer retry bound, which is deliberately shorter than the
generic serialized-writer bound because exhausting it costs one audit row and
an honest degraded axis, never filesystem or integrity truth. Its
twelve-second service shutdown allowance covers the cutoff followed by a
pump-owned retry, plus one second of margin; none of these limits is an
independent literal. Audit *offer* backpressure is a separate bound and does
not scale with them: it exists only so a wedged writer degrades quickly
instead of stalling the emitting workflow thread. History never parses
the `Terminal` it already settled, and no second terminal or corrective write
exists. (The
`recording` axis has no such loop: the recorder is call-driven, and its terminal
flush completes before result assembly.)

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
                    item_id: str | None; item_type: str | None
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
  otherwise*, never silently absent. The observer's explicit status may also
  report a contained durable rejection: that degrades audit while the pump
  remains accepting. Only an exception/timeout breaks the authenticated prefix.
  Any
  *other* reliable subscriber that overruns its bounded queue is ejected with
  an explicit `Gap` event rather than silently thinned. The replay buffer is
  bounded per session; a late subscriber gets current state plus a bounded
  tail and detects what it missed from the gap-free `seq`.
- `Progress.item_id` and `item_type` are an optional pair. Current decoders use
  additive `.get(...)` reads so legacy envelopes remain valid; `current_path`
  is display-only and never row identity.
- The verifier emits `ItemOutcome` per file *because that is the only way to
  report a per-file result*. Silent-until-done is not expressible.

### 2.4 Outcome vocabulary (bones)

```python
class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED   = "skipped"    # intentionally excluded, including user deselection
    FAILED    = "failed"     # attempted, errored
    CANCELED  = "canceled"   # not reached due to cancellation
    DEFERRED  = "deferred"   # valid but held back (dependency, partial-exec)
    BLOCKED   = "blocked"    # intrinsically unexecutable reviewed plan item
```

Every reviewed operation ends in exactly one of these. M0 safe-subset workflow
produces `BLOCKED` for direct blockers and `DEFERRED` for quarantined,
dependency-excluded, or incomplete-scan-withheld work. Quarantine and
withholding remain reason codes rather than additional top-level outcomes.
`NOOP` is an operation kind, not `SKIPPED`: a selected no-op still runs its
guard and records correspondence. An all-skipped review has no work and refuses
before admission; an all-noop execution remains meaningful and history-worthy.

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
    attributes: int             # complete observed Windows attribute bitmap;
                                # planner/executor share a smaller managed mask
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

class ScanScopeKind(StrEnum):
    FULL = "full"
    PATHS = "paths"             # exact named entries only
    SUBTREES = "subtrees"       # recursive canonical roots

@dataclass(frozen=True)
class ScanScope:
    kind: ScanScopeKind
    selected_paths: tuple[str, ...] = ()
    subtree_roots: tuple[str, ...] = ()
    # FULL carries neither; PATHS carries nonempty selected_paths only;
    # SUBTREES carries >=1 root and may also carry exact paths. Overlapping
    # roots and covered exact paths canonicalize, and selecting the location
    # root normalizes the entire mixed request to FULL.

@dataclass(frozen=True)
class ScanResult:
    root: Root
    scope: ScanScope
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
class RecordedCopyIdentity:     # complete identity from one copy transaction
    row_id: str
    location_id: str
    scope_token: str
    rel_path_key: str

@dataclass(frozen=True)
class PublishedCopyEvidence:        # core/execution.py
    attestation: "Attestation"      # core/evidence.py; defined in §2.6
    recorded_identity: RecordedCopyIdentity | None
    # copy_recorded is the derived ``recorded_identity is not None`` property

@dataclass
class ExecutionSet:           # plan + selection + mutable per-op status
    plan: Plan
    selection: Selection        # dependency-closed subset
    user_deselected: frozenset[OpId]  # direct user intent, distinct from
                                      # plan-derived safety exclusions
    run_id: RunId
    commitment: Commitment | None   # execution REFUSES a None or mismatched one
    status: dict[OpId, Outcome] # doubles as the pause/resume continuation:
                                # everything unreached is the remaining work
    published_evidence: dict[OpId, PublishedCopyEvidence]
                                # exactly one per settled COPY/UPDATE/MOVE_UPDATE
    recording: RecordingStatus  # frozen execution-phase recording truth

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
    recording: RecordingStatus  # ledger truth — never folded into status
    audit: RecordingStatus      # history truth — same axis rules (§2.3)
    disposition: Disposition    # CANCELED + UNRUN = discarded before start
    canceled: bool
    items: tuple[ResultItem, ...]       # ordered execution + integrity items
    phases: tuple[PhaseResult, ...]     # phase-local truth and byte totals
    bytes_done: int
    bytes_total: int
    error: FailureDetail | None
```

Integrity and headline are single derived projections over the nominal
items/phases and the other persisted axes; they are not competing mutable
fields on `OperationResult`. Live and retained views both use
`operation_result_view` for that classification.

`PublishedCopyEvidence` is execution continuation state and therefore lives
beside `ExecutionSet` in `core/execution.py`. `PostCopyCandidate` is the
cross-boundary verifier-input contract and lives in `core/integrity.py`; its
fields bind a published target to expected content evidence and may carry a
complete durable row identity only when recording already returned one.
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
    def record_copied(self, op: OpId, at: Attestation) -> RecordedCopyIdentity: ...
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

M1 Stage 1 removed the fingerprinted `worker_count` setting rather than
replacing it with another file-concurrency protocol, placed the parameterless
`StreamingHasher`/`HasherFactory` shape in standard-library-only core, and
declared the compatible `xxhash` runtime dependency. Stage 2 workflow
composition imports the one concrete XXH3-128 constructor and supplies that
factory to `NativeCopyBackend` and `VerifierContext`; `core` and the operation
modules do not construct or import the third-party implementation.

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

M1 uses deliberate pre-release schema boundaries, not incremental migrations:
the ledger advances to v3 for canonical XXH3-128 content evidence plus durable
verification invalidation, and history
advances to v5 for the bounded, incrementally durable reliable-receipt journal,
typed canonical item projections, semantic duplicate/rejection receipts and
rolling aggregates, and terminal-only phase summaries and result axes. The
versions are qualified by immutable
final-contract markers: ledger
`m1-ledger-xxh3-128-invalidation-v1` and history
`m1-history-windowed-receipts-v1`. A nonempty
database is checked read-only for its numeric version and then exact marker
before any writer or schema script is opened. Ledger v1-v2, history v1-v4, and
missing/mismatched markers are refused with one actionable reset posture, and
development setup deletes/recreates both databases together. There is no
v4-to-v5 history migration because v4 lacks the disposition, semantic link,
hash-only rejection, and receipt-chain facts needed to reconstruct v5. Settings
files survive this reset. A general
migration framework remains later work.

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
Pure relative-path parent/depth/descendant and suffix helpers also live here so
planner, workflow node trees, and scope validation share one lexical contract.
Absolute root containment remains a separate filesystem-safety operation.
Domain and persisted absolute paths use lexically normalized ordinary drive/UNC
spelling; normalization never follows a final filesystem link. Shared inverse
helpers add `\\?\` only at native I/O and strip it from native results. Native
admission no-follow checks every configured-root component below its trusted
volume mount before physical resolution and rejects a reparse in that chain.
The helpers also refuse NT/device namespaces and any
absolute component that cannot round-trip without Windows retargeting
(including trailing dot/space and reserved DOS names). Native error filename
fields are normalized before warnings, evidence, history, or interface
rendering.

**Settled root-authority boundary (implemented).**
`core/root_authority.py` owns an immutable, ephemeral `RootAuthority`: the
ordinary logical root, optional reviewed volume anchor, and optional expected
`VolumeId`. It also owns stateless no-follow component inspection and native
volume observation shapes shared by scanner, preflight, executor, verifier,
and their workflows. `core/pathing.py` retains lexical spelling and relative
path algebra. An authority is reviewed evidence, not a permission token: it is
never persisted, fingerprinted separately, cached as fresh, or substituted for
a consumer's live probe.

Shared authority code reports typed observations and failures but does not
choose domain outcomes. Scanner retains traversal and its exact FULL mounted-
root exception; preflight retains read-only observation and refusal mapping;
workflows retain mount ambiguity and overlap policy; executor runtime retains
every final-touch validation point; verifier retains per-item revalidation and
handle-bound final-path, volume, sharing, and cache-honest read guarantees.
Native adapters translate the shared mechanics into each component's existing
error vocabulary without broadening what a prior successful check authorizes.
The public chain-only admission performs no volume probe. Scanner uses it at
its established chain checkpoints while retaining separate chain-first binding
precedence and capability policy; inventory and initial sync path validation
reuse it without moving resolution/overlap policy; verifier uses it for the
native reader's distinct final-touch root walk without replacing engine volume
admission or handle-bound checks.
Executor runtime derives source and target authority from the fingerprinted
plan facts at each retained guard call. Its native adapter uses process-cached
Windows bindings for fresh probes and supplies the executor's pre-existing
component classification to the shared admission functions, preserves
the anchor -> chain -> optional-volume probe order and legacy errors, and
never carries an observation into a later guard.

**Flesh.** None. Core is all bones by definition.

**Acceptance criteria.**
- The transition table permits exactly the legal edges and rejects all others,
  proven by an exhaustive table test.
- `normalize_relative_path` keeps NTFS-distinct names distinct across a Unicode
  special-casing corpus (`ß`, Turkish `İ/ı`, fullwidth forms).
- Path validation rejects every escape form and non-scalar surrogate while
  accepting every contract-legitimate root-relative path; absolute drive/UNC
  conversion round-trips without prefix leakage or ambiguous-name retargeting;
  canonical JSON never raises while encoding malformed free-form Unicode.
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

**Contract.** `scan(root, scope, ignores, ctx) -> ScanResult`. Implements
`ChangeSource`.

**Bones.** The `ScanResult`/`ScanScope`/`FileRecord`/`CapabilityProfile` shapes;
three-way `FULL`/`PATHS`/`SUBTREES` scope; the `complete` flag; cancellation via
`ctx.checkpoint()`; visited-identity tracking so junctions/reparse loops cannot
recurse forever.

**Flesh — now.** Recursive metadata walk (size, mtime_ns, identity, nlink;
every directory recorded with metadata); pre-use raw-name validation; fixed
exact qualified filtering for `DESKTOP.INI`, `THUMBS.DB`, owned temporary names,
and `.SYNCTRASH` (no per-location ignore snapshot); capability profiling; placeholder detection
(classify reparse/offline files `unsupported`, never open them); scan warnings.
**Flesh — M1 Stage 5.5.** Parameterize the proven full-walk helper for recursive
subtree roots instead of generalizing the exact-path observer. Mixed exact and
subtree requests deduplicate deterministically. Owned artifacts and file
placeholder/reparse exclusions do not alone make a scan incomplete; unreadable
directories, directory placeholder/reparse points, repeated directory identity,
collisions, and unsafe names do.
**Flesh — M1 hardening.** An exact FULL root may retain the reparse tag of a
folder-mounted volume anchor only when its resolved path, reviewed/current
anchor, and volume-evidence mount agree. The walker classifies that anchor
without following, then follows only its metadata so the root record and visited
identity belong to the mounted volume. Configured-root-chain components below
the anchor, exact scoped starts, and enumerated descendants retain ordinary
no-follow reparse refusal, and the anchor plus full `VolumeId` still bracket
enumeration.
**Flesh — deferred.** USN change-journal `ChangeSource`; network-share awareness.

**Acceptance criteria.**
- A directory junction that points into its own ancestor terminates the walk;
  it never recurses twice or hangs.
- A cloud placeholder file is recorded `unsupported` and is **never opened**
  (asserted by a read-tripwire in test).
- A partial/errored walk yields `complete=False`; a clean walk yields `True`.
- Exact paths never imply descendant absence; a completed subtree covers every
  descendant, and a selected root normalizes to the full-scan branch.
- A contract-invalid file or directory name is escaped into typed evidence,
  makes the scan incomplete, is never opened/descended, and does not prevent a
  safe sibling from being retained.
- Ignored artifacts are matched only by exact qualified name; a user file named
  `my.synctmp-notes.txt` or `data.db` is **never** excluded (direct PoC
  regression tests).
- Cancellation observed within one directory/file step.
- exFAT root reports `stable_file_identity=False` and coarse
  `mtime_granularity_ns`.
- A FULL scan rooted exactly at a reviewed/native folder-volume mount records
  the followed mounted-root identity and completes; a forged anchor, ordinary
  final/intermediate configured-root junction, invalid followed root, subtree
  start, or descendant reparse cannot inherit that exception.

### 4.3 planner

**Implementation status (2026-08-10).** The pure M0 planner and its core plan
contracts are implemented: identity assignment, timestamp- and
managed-attribute-aware metadata diffing with complete raw snapshots, explicit
directory chains, correspondence-qualified file moves, composite move-update,
planned-removal cleanup, symmetric filters, deterministic surrogate-safe
serialization, non-blocking exact-case and canonical-Unicode advisories,
zero-byte conditional source-basename recasing, and the shared hardlink-aware
capacity function. Non-everything scopes and content evidence remain deferred.

**Contract.**
`plan(source: ScanResult, target: ScanResult, correspondence: MappingSnapshot,
options, scope) -> Plan`. Pure — every input is an immutable snapshot; the
workflow reads correspondence from repositories and passes it in. The plan is
the complete review artifact; blocked intent and corresponding removal rows
remain present while workflow derives a separate executable safe selection.

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
exact comparison of the core-owned readonly/hidden/system/not-content-indexed
mask; unmanaged bits remain observed evidence but do not schedule mutations;
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
state. It is off by default, is available through the primitive semantic
settings facade but has no settings CLI/UI, and does not recase parent
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
- A blocked COPY or unsupported source item does not erase the matching
  target-side removal from the raw plan; safe selection excludes that removal
  and every dependency/correspondence consequence while unrelated safe work
  remains selectable.

### 4.4 preflight

**Implementation status (2026-07-24).** Scoped read-only observation and pure
typed judgment are implemented for selection-aware scan completeness, blocked
correspondence, root/volume, dependency, direct and parent evidence, capacity,
trash, containment, and path representation checks. M1 Stage 1 removed the
obsolete live-settings collaborator and drift checks; commitment validation
remains correctly outside this module at execution-workflow entry.

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

The local observer derives ephemeral `RootAuthority` values from the plan's
reviewed anchors and volume identities. Root, subject, capacity, temp-parent,
and trash calls re-admit independently; existing relative components are
no-follow checked before resolution, volume probes, access checks, or
enumeration. Typed authority failures remain observation evidence, while the
pure judge alone maps changed authority to `root_changed` and unavailable
authority to `root_unavailable`.

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
**Flesh — M1 Stage 5.5.** User-edited review selection is service-owned and
re-derived before this preflight; preflight itself remains a pure judge of the
resulting exact selection. **Flesh — deferred.** A graceful
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

**Implementation status (2026-08-09).** The M0 native single-worker executor
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

**Implemented component boundary.** `executor/__init__.py`
preserves the existing public imports. `runtime.py` remains the operations
engine: dispatch, all operations, executor-specific path guards, retries,
continuations, cancellation, recording, settlement, progress, and outcomes.
`native.py` owns Windows filesystem primitives, metadata, handles, publication,
trash, and adaptation of core root
authority to executor errors. `pipeline.py` owns only the bounded one-file
read/hash/write flow, queues, backpressure, teardown, metrics, and `CopyDigest`
production; it never publishes, records, retries, or interprets an operation.
Final-touch timing remains in runtime even when the observation mechanics are
shared through core.

**Implemented effect journal and settlement reducer.** Runtime retains one
operation-keyed typed journal entry with independent byte/publication and
non-byte mutation channels, the last retry error, and an optional owned
temporary path. Typed mutation variants cover readonly clearing, rename/recase,
trash rename, removal, and directory creation. Entries are snapshotted before
cleanup and retired only after terminal item settlement; retry-error-only and
temporary-only entries do not latch pause as durable effects. Failure-only
observers perform filesystem probes and return typed publication and mutation
verdicts; they do not select terminal policy. One pure reducer consumes those
verdicts and a typed terminal cause and owns reason precedence, outcome/detail
vocabulary, recording degradation, and byte/mutation composition for ordinary
failure, cancellation, and MKDIR settlement. Confirmed publication is
authoritative; otherwise unchanged mutation is ignored and durable, ambiguous,
or unreadable mutation evidence degrades recording. The reducer performs no
I/O, leaves inputs unchanged, and never produces published success evidence.
Cleanup timing, recorder ordering, retry/control behavior, and successful-path
probes remain unchanged. Ordinary collaborator exceptions cannot bypass this
lifecycle: runtime reduces active effects from the original operation error,
finalizes pending directory effects, and retires already-statused entries
before propagating the collaborator exception. Process-fatal `BaseException`
remains a nonterminal cleanup-only unwind. A discovered policy discrepancy is
still isolated as a separate bug fix rather than folded into this
contract-preserving refactor.

**Settlement stability barrier.** The monolithic corrected baseline is not
declared stable merely because a differential run reproduces it. Before the
file-to-package split, and again before journal or reducer adoption, the
retained public-facade settlement oracle must have a complete classified
manifest, pass three identical normalized runs, and report no expected-policy
or committed-snapshot difference. Any mismatch is investigated as a possible
latent defect; a confirmed fix lands alone with a persistent regression and
restarts the barrier. The oracle and committed baseline stay in `tools/`
through package splitting, journal/reducer work, verifier restructuring, test
consolidation, and final acceptance. Its original 58 rows preserve attribution
to the corrected monolith; 12 independently reviewed post-refactor rows extend
that corrected-baseline lineage without rewriting the earlier trace.

Single-file throughput work belongs primarily in `pipeline.py`; Windows I/O
flags and handle mechanics belong in `native.py`; multi-file scheduling and
per-volume concurrency belong in `runtime.py`. These ownership boundaries are
stabilized; no finer executor split is planned without new evidence that one of
them fails.

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
scheduler-bounded): a source-leaf substitution routed to an unchanged owned
trash destination preserves the wrong item recoverably, while a
destination-parent substitution can preserve bytes outside owned trash and lose
NamiSync's location/recovery truth. Moves can misplace without destroying, and
only update's replace and internal mirror deletes can destroy an external
writer's file. Stable identity binds a substituted
prepared/published inode before attestation, but identity-weak same-size
substitution and same-object byte mutation remain outside the path-based
contract. `ReplaceFileW` — the
supported single-call replacement with optional backup — is deliberately not
used: it merges the replaced file's attributes, ACLs, and named streams into
the replacement and documents partial-state failure cases;
hardlink/copy-backup-then-replace is a chosen tradeoff, not the only Windows
primitive; readonly applied only after publish; directory metadata applied
only after the directory's children settle (child creates and renames churn
parent times — directory times are restored last); the cancel-unwind finalizer
(§2.2a — canceled outcomes for in-flight and unreached items emitted before
unwind); content-only byte accounting; the `FailurePolicy`/`CopyBackend` seams;
and process-local retry continuations covering COPY plus committed
update/move-update sub-steps. Lightweight markers retain the already-observed
pre-state for MOVE, RECASE, TRASH, DELETE, MKDIR, and readonly clearing until
recording or failure settlement; they add state probes only after failure. Both
kinds of retained state survive retry and latch a retry-backoff pause until
operation settlement rather than unwinding into the executor's own prior
mutation. Byte continuations revalidate exact prepared/published and
backup/trash evidence before resuming. An attempt that enters with an
already-published continuation performs one target stat before remaining
post-publish work, binding the cached published version when available or
kind/size plus available stable identity while mtime is still repairable;
normal first-pass execution adds no stat, and the check is drift detection
rather than an adversarial path lock. Cancellation instead derives
the current item's outcome from that state immediately: retained UPDATE backups
remain visible, published-but-unfinished work is failed with a typed reason and
degraded recording, and no rollback or false success evidence is attempted.
Ordinary failure and cancellation evaluate byte continuations and mutation
markers independently unless publication is confirmed. An unavailable
byte-state probe cannot suppress changed, ambiguous, or unreadable
readonly/non-byte mutation truth; combined detail retains publication
diagnostics and names marker durability separately, while an exact restored
pre-state does not itself degrade recording.
UPDATE, DELETE, MOVE, RECASE, MOVE_UPDATE old-path cleanup, and TRASH force
prior recorder evidence durable before their final destructive
source/destination guards, leaving no writer wait between those guards and
mutation. A MOVE_UPDATE retry that observes its old version already in owned
trash has no remaining destructive mutation and skips the redundant barrier.
Ordinary failure probes durable publish state before temp cleanup: if COPY,
UPDATE, or MOVE_UPDATE committed and then raised, the operation reports the
surviving target/backup/old-path state with `recording=DEGRADED` and never
manufactures success evidence. The same rule covers committed, ambiguous, or
unreadable non-byte attempts, deferred/resumed directory metadata, and failed
readonly restoration; exact unchanged pre-state keeps the ordinary recording
result. A changed or missing published target is named as such rather than
contradicted by a `target-published` durability label; an unsuccessful state
probe degrades recording as publication-unverified.

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

Executor pipeline and verifier both use the lifecycle helpers owned by core
evidence to construct, structurally validate, update, and finalize the injected
hasher. Those helpers preserve one error vocabulary and exception boundary;
core still imports no concrete hashing implementation.

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
`content.size == subject.size`. Before attestation, the cached post-publish stat
must also match the prepared temp's kind, size, and stable identity when the
target profile supplies it; this reuses the existing observation rather than
adding a stat. Copy and verifier both use the required XXH3-128 factory, but the
verifier retains its independent cache-honest opener and fixed 4 MiB reads.

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
- Recorder contention happens before every final destructive source/destination
  guard; same-size/same-mtime foreign replacements introduced during the flush
  are not overwritten, deleted, relocated, or falsely recorded by UPDATE,
  DELETE, MOVE, RECASE, MOVE_UPDATE cleanup, or TRASH.
- A publish primitive that commits then raises yields one truthful failed item
  with degraded recording and explicit durable-state detail for COPY, UPDATE,
  and MOVE_UPDATE.
- UPDATE rejects recorder-flush temp substitution before publish, and
  COPY/UPDATE/MOVE_UPDATE reject a stable-identity post-guard inode substitution
  before attestation without another success-path stat.
- MOVE/RECASE/TRASH/DELETE/MKDIR commit-then-raise, exact pre-state,
  ambiguous/probe-failed state, readonly restoration, deferred/resumed mkdir,
  and retry pause/cancel cases preserve recording and durable-state truth.
- Readonly UPDATE cancellation composes failed publication probing with restored
  or changed marker state, while confirmed publication remains authoritative;
  all three cases omit false success evidence.
- Temp recovery deletes only exact-shape, different-run regular files in the
  preflight-retained touched parents. Current-run temps, lookalikes, exact-name
  directories, untouched parents, off-volume mounts, and `.synctrash` survive;
  a sweep failure occurs before copy allocation, so credited capacity is never
  used unsafely.
- Trash whose destination chain is redirected before its final guard is refused
  before any move. A substitution after that guard remains within the disclosed
  path-validation-to-rename boundary and may preserve bytes outside owned
  trash.
- Fault tests exercise an external path swap *between* a final guard and its
  destructive call, not only drift before the guard, and assert the **data
  consequence**, never elapsed time: each conditional primitive fails cleanly
  on exactly the condition it enforces, a source-leaf trash swap is retained
  recoverably when the destination chain stays admitted, and the update
  residual's worst case matches the documented bound
  without claiming handle-bound protection against identity-weak substitution
  or same-object content mutation.
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

**Implemented component boundary.** `verifier/__init__.py`
preserves the existing public imports. `engine.py` owns selection processing,
classification, progress, cancellation, conditional recording, settlement,
verifier outcome policy, selected-root admission, and opened-handle volume
corroboration. `native.py` owns the Windows bindings and the cache-honest,
handle-bound reader, including root-chain admission and final-path checks. The
native leaf uses core root-authority mechanics but never imports the engine;
the engine imports the native implementation at its reader boundary and
otherwise operates through core protocols.

Each production invocation is bound to one exact reviewed logical root, its
reviewed anchor when available, and its expected `VolumeId`. Selection-root
equality is checked after existing display-path validation and before every
inventory-state or existing-baseline shortcut, reader open, or evidence write.
Authority is freshly admitted for each readable item and does not replace the
reader's second root-chain walk, opened-handle volume check, or final-path
check. A runtime-checkable core reader protocol routes native subclasses and
decorators through `open_with_authority(relative_path, authority)`; that method
derives its root only from the authority, and engine rejects every such reader
when the context is unbound. Unbound operation is reserved for explicitly
injected fake/custom readers. The same pure core expected-stat matcher serves
engine classification and tool sidecar validation; same-open read-drift
matching remains stricter when only one observation has identity. Standalone
and post-copy verification continue through the same ledger-neutral
classifier; executor publication policy and verifier read policy remain
independent.

**Bones.** Per-file `IntegrityOutcome` emission (no silent-until-done); the
cancel-unwind finalizer (§2.2a — canceled outcomes for in-flight and unreached
items emitted before unwind); the integrity-outcome vocabulary (verified,
baselined, mismatched, modified, missing, unsupported, canceled, error);
attestation provenance tagging.

**Flesh — operation module and standalone M1 integration implemented.**
Baseline creation; location verification against the
size/mtime/identity/hash unit; selected verification; cache-honest reads; safe
conditional recording; accept/re-baseline of a modified file; and item-status
continuation. Standalone verify/baseline/rebaseline sessions refresh inventory,
re-resolve volume/root state on initial start and every resume/queued wakeup,
and pause/resume over the exact originally admitted selection. Their ordered
integrity items reach history, and all three kinds are registered with the
dispatcher. Stage 5 exposes the explicit location commands through the shared
facade; desktop actions remain Stage 6.

M1 replaces content SHA-256 in baseline, verify, rebaseline, and copy together
with canonical XXH3-128; no interval exists where the two consumers write
different evidence formats. The verifier's guarded
open/stat/hash/classification body is ledger-neutral so standalone ledger-bound
selections and transient post-copy candidates share it without changing
byte classification. The latter are constructed by the workflow from
`PublishedCopyEvidence` and remain
classifiable when the copy-ledger transaction failed; only a candidate with
durable matching row evidence may conditionally advance ledger verification
state. Immediate
readback is independent evidence against ordinary copy/IO/recording failures,
not a defense against malicious in-process executor code.
Baseline-backed `missing`/`modified` observations conditionally persist
metadata-drift invalidation, while a stable digest mismatch persists
hash-mismatch. The marker is sticky across ordinary matching scans, mismatch
dominates later metadata drift, and only a guarded positive evidence write
clears it; repositories derive inventory verification state from this marker
and retained evidence rather than age alone.

Conditional recorder calls remain I/O observations. A private pure settlement
reducer receives only the typed disposition or normalized recorder error plus
the truthful classification reason/detail, then selects recording precedence
without constructing outcomes or calling the ledger. Separate item and
post-copy, positive and invalidation wrappers retain their command and outcome
identity contracts. Rowless successful post-copy classification remains a
distinct no-recording path and is not reinterpreted by the reducer.

**Flesh — deferred.** Benchmark-justified multithreaded verification with
per-volume safety policy (no worker-count setting is reserved);
IO/CPU pipelining even on HDD; automatic background integrity; repair guidance
(diagnose which side is damaged).

**Acceptance criteria.**
- A fresh verifier classification reports changed size/mtime as `modified`, not
  `mismatched`; when a durable hash-mismatch invalidation already exists, that
  stronger sticky state continues to dominate later metadata drift until a
  successful evidence write clears it.
- A null-hash row encountered during verify is a `baselined` outcome, never a
  `verified` one; `last_verified_at` is never set from a copy-stream digest
  alone (PoC open integrity-lie bug).
- A reappeared file that gets its first baseline during verify has
  `reappeared_at` cleared in the same pass (PoC stale-state bug).
- Scoped verification matches rows by `rel_path_key`, not raw path (PoC
  casing/separator bug).
- Every per-file write is conditional; a file that drifts between hash and write
  records nothing.
- Negative missing/modified/mismatched evidence is conditional too; stale,
  conflicting, or failed persistence degrades recording without changing the
  content verdict.
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
admitted execution never rereads it. Runtime defaults this file beside the
selected ledger and translates it to primitive service views; interfaces never
import database settings types.

**Implementation status (2026-08-08).** Ledger v3 and history v5 are active.
Their safe writer/read-only connection factories, canonical UTC codec,
serialized retrying writer, run-bound sync recorder, batched inventory
reconciliation, conditional baseline/verify/rebaseline/invalidation writes,
typed ledger
repositories, and bounded history observer/repository are implemented. The
history observer appends disposition-bound reliable receipts in atomic windows,
projects typed canonical result items through writer-derived immutable columns for
dense paging and fixed conditional aggregates, keeps strict composite-key
receipt rows append-only without a hidden SQLite `rowid`, and writes terminal
axes plus bounded phase summaries only during finalization. Ledger v1-v2 and
history v1-v4 are refused without mutation; the temporary pre-migrator
recovery is manual deletion of both local databases or the explicit
development reset helper, never automatic startup deletion. `settings.py`
implements named-mutex-serialized partial semantic-settings commits. M0
commands commit eagerly, so `flush()` preserves the final boundary while the
crash window is zero completed commands. Cross-process contention is bounded
and visible.

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
verifier during M0 construction. **Flesh — implemented through current M1.**
History v5 stores reliable lifecycle, phase, and ordered generic `ResultItem`
receipts for sync, standalone integrity, and linked verification. Exact
semantic duplicates retain full non-counting envelopes; supported oversized
events retain bounded hash-only rejection receipts and degrade audit without
stopping later history. Oversized result-item receipts retain only fixed-size
identity/semantic hashes, preserving changed-identity fail-stop semantics.
Compound
terminal results add bounded `PhaseResult` summaries; standalone producers
leave that table empty.
Semantic-settings commits hold a named cross-process mutex only across
read-current → modify-owned-keys → temp-write → atomic-replace, so concurrent
GUI/CLI writers cannot lose one another's updates. The Stage 5 facade reads the
full snapshot and commits an all-optional patch; omitted fields survive because
the store rereads under that mutex. Planning captures the resulting complete
snapshot once, and a request-level deletion override replaces no other semantic
field.
The review model carries that complete frozen semantic snapshot. Public
snapshot/patch views enforce exact booleans, tuple-of-string filters, supported
deletion values, and the nested preservation type before any atomic settings
write; settings may neither alias a database nor live inside a managed root.
**Flesh — M1 Stage 5.5/6.** Inventory reconciliation has three explicit shapes:
full-location missing marking, exact-path replacement without inferred absence,
and completed-subtree missing marking. Subtree descendants use the canonical
literal range
`rel_path_key >= root || '\' AND rel_path_key < root || ']'`, served by
`inventory_location_presence_idx`; SQL `LIKE` is forbidden because `%` and `_`
are valid hostile-name characters. Acknowledgement/restore recording is
idempotent per gesture and row with a caller-supplied timestamp.

History commits reliable receipts by a shared `HistoryWindowPolicy`: at 256
receipts, 1 MiB of retained serialized data, one second from the first event, pause,
clean close, or finalization. The dispatcher owns the monotonic age deadline
and pause barrier; the observer owns canonical bytes and transactions. Each
committed prefix remains independently queryable under WAL. A restarted
nonterminal row is `incomplete`, never inferred to be interrupted or resumable.
Summary classification remains bounded even when item kinds and reasons are
free-form: the database returns one conditional-aggregate fact object per run,
using finite predicates supplied by workflows, and workflows retain all
headline and integrity interpretation. Finalized sessions that never ran keep
`started_at` null rather than fabricating `created_at` as an execution start.
Terminal summary text is bounded at the history boundary: phase/failure type
names permit 256 UTF-8 bytes and phase/failure messages permit 4,096. Each
receipt hash authenticates retained metadata, disposition, item
identity/semantics/link or rejection, and canonical order. Each run's prefix
projection binds context and receipt-chain hashes to lifecycle projections,
watermarks, timestamps, and every rolling count. Incomplete and finalized
summary reads validate that prefix; finalized reads and repeated finalization
also bind terminal axes and ordered phases. Writer-derived projections are
checked against decoded envelopes on detail reads, while append-only receipt
rows keep fixed-query classification aligned with the authenticated envelope.
Indexed physical event/item tails must equal the
official watermarks on summary/page reads, observer reopen, and writer
admission; finalized run rows are immutable and committed runs cannot be
deleted or replaced.
Window commit time is never earlier than any envelope newly committed in that
window, including phase and result-item events during wall-clock rollback.

History browsing obtains summaries with a fixed query count from run rows,
bounded phase summaries, and grouped primitive item facts. It never selects
event JSON for classification. Item and reliable-event detail use database
keyset pages of at most 256 rows under a fixed durable watermark captured in
the first page's read transaction. Reliable-event sequence space is sparse:
caller-supplied inclusive bounds may land on omitted lossy progress, while each
request independently verifies that the run's official durable watermark equals
the indexed maximum retained reliable event. Event pages fetch one raw
lookahead row but decode only the requested limit; recorded/duplicate receipts
expose envelopes and rejected receipts expose only their validated
metadata/hash/reason. A fresh traversal whose live cursor is
ahead of durability ends empty; its next attempt omits the fixed watermark and
captures a new prefix. The service has separate summary, item-page, and
event-page methods; the unbounded full-run path is removed.
**Flesh — deferred.** History retention waits for a maintenance session with
cross-process history-writer custody; no M1 retention setting, facade action, or
direct UI SQL exists. Also deferred: general migration module; legacy import;
scheduled backup/quick-check (as an ordinary session); export/import; ledger
merge across hosts.

**Acceptance criteria.**
- Two parallel disjoint-volume runs both record completely; neither silently
  loses bookkeeping to lock contention (PoC open concurrency bug — the reason
  for the single serialized writer).
- A completed subtree scan marks every absent descendant and no sibling missing,
  including roots containing literal `%` or `_`, through the indexed range.
- History summary classification agrees with live classification, including
  genuine selected no-op versus `SKIPPED/user_deselected`, without loading
  detail JSON; every detail page is bounded and stable by `item_order`.
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
volume sets run in parallel, contenders queue); generation-owned resource
custody (each process-local worker attempt owns exactly its reservations and
lease, and each session has one current attempt); the control plane
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
Pause/resume/cancel handoff may make PAUSED/CANCELING/PENDING visible while the
prior attempt is retiring, but the scheduler does not install a successor until
that generation relinquishes current ownership. Custody release and worker
cleanup identity-check the generation, so stale teardown cannot release or
remove a successor's lease/reservations. The generation is runtime-only and is
never serialized into session payloads or stores.
Terminal session records are retained until explicitly closed, then dropped;
history is the durable trail. Session identity is not desktop task identity:
the M1 adapter may retain a reviewed plan in a task while no session exists,
and closes each plan or execution session only after consuming its terminal
record. A queued session discarded before running writes its history entry
first. Close distinguishes a reversible timeout before the hub gate from
irreversible stream detachment followed by pending audit/store cleanup. Only the
former reopens attachment; the latter retains all ownership for caller or
shutdown retry and reports typed `SessionCleanupPending` rather than pretending
the still-listed terminal session does not exist.

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
- Immediate resume and cancel-from-visible-PAUSED wait for the retiring current
  generation; no second session worker overlaps it, and handoff settles once.
- Stale generation cleanup cannot alter a successor's current key, lease, or
  reservations; a lease is released on the same thread that acquired it.
- Every ordinary `Exception`/cooperative-control path reaches one terminal and
  releases every lock; `BaseException` escapes unnormalized while teardown
  still releases custody.
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
- Shutdown remains incomplete and names a session whose canceled acquisition
  has not retired; completion requires empty attempt, current-owner, lease, and
  reservation maps as well as an exited scheduler.

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
    verify_after_execute: bool

@dataclass(frozen=True)
class VerifyContinuation:
    phase: Literal["verify"]
    execution_set: ExecutionSet
    candidates: PostCopySelection       # frozen candidates + completed ids/bytes
    filesystem_status: SessionState     # settled execute filesystem truth
    recording: RecordingStatus          # compound-current recording truth
    execute_phase: PhaseResult
    missing_evidence_ids: tuple[str, ...]

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

M1 does not split integrity continuation storage speculatively. The whole
candidate/completed-state payload remains until the bridge's named late-run
pause reserialization benchmark proves it misses budget; only that evidence
authorizes a restructuring.

At execute→verify handoff, candidate ids and `missing_evidence_ids` are
disjoint, retain plan order, and together equal exactly the successfully
settled COPY/UPDATE/MOVE_UPDATE ids. `ExecutionSet.recording` remains frozen
execution truth; the continuation's separate `recording` value is
compound-current and may degrade later but cannot improve a degraded execution.

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
  pause may close and idempotently reopen the same run token on resume. If a
  resumed continuation is invalid, settlement finishes the already-established
  token directly under same-runtime custody instead of attempting to begin it
  again from untrusted carried selection.
- **Standalone integrity freezes mode-aware scope.** A fresh baseline filters to
  eligible rows without evidence, a fresh rebaseline filters to rows with
  evidence, and verify keeps both. Once candidate ids exist, resume preserves
  that ordered admitted set and completed counters without reapplying filters
  after evidence changes.
- **Stage 5.5 review selection is service-owned.** Plan-derived safety
  exclusions and canonical `user_deselected` are distinct. Mutations are
  revision-guarded, dependency closure is recalculated server-side, commit
  freezes the state, and execution re-derives the authoritative selection
  before admitting it. Replan discards prior user selection while advancing a
  monotonic request revision and retaining recognized retry tombstones.
- **Location scope is resolved before work.** Opaque location-scoped node ids
  resolve through the workflow tree/index to exact paths or recursive subtree
  roots. Folder integrity freezes every eligible indexed descendant regardless
  of presentation filter/window. One unreadable subject becomes a visible
  unsupported result and verification-incomplete while siblings proceed;
  non-subject-specific incompleteness refuses.

**Bones.** The two-session split; top-to-bottom sequencing (scan → plan →
observe → preflight → execute [→ verify], or location resolve/register → scan
→ inventory → standalone integrity); the explicit execute/verify continuation;
no signals, no callbacks-for-control; every dependency arrives via `deps`.

**Implementation status (2026-07-25).** M0 paired sync runs both dispatcher
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
**Flesh — implemented through M1 Stage 3.** Role-free one-location inventory;
standalone inventory/baseline/verify/rebaseline sessions; integrity preflight
on start, resume, and queued wakeup; exact-candidate continuation; nominal
result/history items; and production
dispatcher registration. **Flesh — implemented through M1 Stage 4.** Optional
in-session post-execution verification, explicit execute/verify continuation,
one finish-once run window, compound phase summaries/history/views, and
independent filesystem/integrity/recording/audit/canceled truth. **Flesh —
implemented through M1 Stage 5.** Primitive semantic-settings snapshot/patch
translation, mode-aware fresh baseline/rebaseline admission, frozen resume
selection, explicit location facade starts, the four location CLI commands,
and final headline/exit classification. **Flesh — implemented through M1 Stage 5.5.**
Reusable pure node-tree/index construction, recursive subtree
scan/reconciliation, typed inventory warning projection, user-selection
provenance and re-derivation, and the facade commands/review state needed by the
desktop. **Flesh — implemented through M1 Stage 6 Slice 4.** The secured web
desktop host, production bridge transport, shared design foundation, pure
visible-sequence presentation core, bounded tree renderer, and honest empty
shell frame. **Flesh — planned remainder of M1 Stage 6.** Plan, inventory,
history, settings, and lifecycle presentation projections and controls.
**Flesh — deferred.** Queue-driven durable second sessions;
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
- A refused fresh/unstarted execution preflight short-circuits to `REFUSED`
  with no mutation. A started execute-resume refusal instead becomes
  `FAILED+RAN` with a failed execute phase and settled counters. A
  verify-resume refusal preserves the settled filesystem status and adds an
  incomplete verify phase. Both finish the existing logical run rather than
  reporting terminal `REFUSED`.
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

### 4.10 interfaces (launcher / cli / api / web)

**Contract.** Adapt dispatcher + workflow state to a surface. Own no sync policy.

**Bones.** Read dispatcher session state, subscribe to event streams, and
translate user intent into service calls. Interface-owned task identity may
outlive a session but never becomes a second session-state authority.

**Flesh — now (M0).** CLI `sync` (plan → terminal review → commit → execute) +
`history`; runnable/blocked/deferred review and partial-completion exit 6; real
entry-point wiring; no-subcommand prints usage and exits nonzero.
**Flesh — M1.** `interfaces/service.py` is the shared facade/composition
surface for both adapters, with typed commands/views, session observation,
result classification across all four axes, and process-local
`save_plan`/`get_plan`/`drop_plan` methods (no speculative `PlanStore`). The CLI
preserves equivalent M0 behavior and adds inventory,
baseline, verify, and rebaseline. CLI and desktop adapters may import the
service but not one another; the service reaches database-owned settings
through its injected workflow/runtime dependency and never imports `db`
directly.

**Stage 5 implemented (2026-07-25).** The process-local service
owns the six-kind registry, runtime/dispatcher lifetime, sync sequencing,
history access, controls, primitive view projection, and a sink-only blocking
`SessionObserver`. The CLI is retargeted without changing its existing
`sync`/`history` behavior and exposes all four location commands through
keyword-only facade starts. Each start binds one explicit root or retained
location id plus optional exact selected paths and ambiguity-resolving mount
before dispatcher admission. Observer shutdown closes streams before
joins, dispatcher shutdown precedes runtime close, and runtime plan access uses
the named process-local methods without a storage abstraction. The compound
workflow is available through the opt-in `verify_after_execute` flag.

Runtime owns semantic-settings persistence and defaults it to `settings.json`
beside the selected ledger. Service read/commit methods expose only primitive
full-snapshot/all-optional-patch workflow views. Planning reads one snapshot;
`deletion_policy=None` uses it unchanged, while an explicit override replaces
only that policy. The captured plan remains immutable if settings later change.

`ResultCategory` chooses one headline without hiding secondary axes:
`failed > partial > refused > mismatch > canceled >
verification-incomplete > recording/audit degradation > all-noop > success`.
Filesystem, integrity, recording, and audit details remain individually
renderable regardless of the headline. CLI exits map success/all-noop to 0,
usage to 2, refused to 3, failed to 4, canceled to 5, partial to 6, degradation
to 7, mismatch to 8, and verification-incomplete to 9.

**Stage 5.5 implemented contract (landed 2026-07-30).** The service adds
revisioned review selection/commit state, `preview_selection`, opaque-id
location commands, missing acknowledgement/restore/listing, stale-row listing,
typed scan warnings, and primitive `APPLIED`/`NOOP`/`STALE`/`CONFLICT`
mutation dispositions. Location-scoped deterministic node identity and the
pure hierarchy/index builder live in `workflows/node_tree.py`; no interface
parses paths or rebuilds domain rollups. The inventory request codec advances
to v2 while integrity stays v1 under an exact-integer, kind-aware validator; sync
plan/execution advances to v4 for `user_deselected`.

Within Stage 6, `M1_BRIDGE.md` is the sole normative authority for bridge
envelopes/limits, command schemas/errors, retry/deadline and revision identity,
sequence/`Gap`/terminal behavior, terminal-session release versus task close,
visible-sequence wire behavior, and every BR-G acceptance gate. This section
summarizes component ownership and must not refine that protocol.

The M1 desktop is a pywebview host forced to Edge Chromium/WebView2. It exposes
one versioned allowlisted `dispatch` endpoint, uses structured pull/RPC and a
bounded event drain that coalesces only replaceable progress and preserves
reliable events, cancels untrusted top-level navigation, every frame
navigation, and new-window requests through native hooks, and rejects dispatch
outside the exact packaged origin. Before `create_window` it hardens pywebview's
external-link, file-URL, download, and remote-debugging settings and performs a
read-only WebView2 runtime registry probe; `start_edge_chromium` repeats that
preparation before native initialization and passes `debug=False`. The probe
lives in one compatibility module that mirrors the pinned pywebview 6.2.1
detector and is behavior-checked against its source without importing WinForms.
It includes pywebview's .NET prerequisite, four accepted Edge channels, and
HKCU/HKLM architecture routing. The `86.0.622.0` token is retained because the
pinned backend passes that exact value to its compatibility helper; NamiSync
mirrors the helper's actual comparison and does not treat it as a security
patch-freshness claim. A configured `WEBVIEW2_RUNTIME_PATH` short-circuits only
Edge-channel discovery; the shared .NET/netfx prerequisite is still read. One pre-start
zero-argument `initialized` callback first refuses any non-Edge-Chromium
backend and only then invokes the host callback, which derives the origin from
the complete `window.real_url` with `urlsplit` after the asset server chooses
its loopback port and registers one idempotent synchronous `before_load`
callback. Native
`CoreWebView2` access and event subscription occur only in that callback on the
WinForms UI thread; setup and bridge workers never touch the UI-affine object.
A sticky attachment state keeps dispatch closed and lets the host tear down
actionably when pywebview logs and swallows a callback failure.
A lock-protected snapshot follows native committed `CoreWebView2.Source`, not pywebview's
managed `Source` or `get_current_url()`, because those can report a canceled
navigation target while the trusted document remains active. Each dispatch
checks the snapshot without UI-thread marshaling. UI commands carry opaque ids
rather than paths; rendered filenames use
escaped display strings and `textContent`, never raw HTML. The task rail, plan
tree, inventory tree, and history dialog consume service/workflow views only.
NamiSync-owned code never constructs JavaScript for application data; pinned
pywebview's internal exposed-function return escaper remains a version-audited,
real-browser-tested part of the security boundary.
Appearance is the sole presentation-only exception to the RPC transport. Its
native-to-page envelope and receiver contract live in `M1_BRIDGE.md`; this
layer only records that appearance has no browser-to-native sender and grants
no command, URL, path, HTML, or general-purpose property authority.
The snapshot follows Windows light/dark/high-contrast state and live
`UISettings` `Accent`, `AccentLight1`, and `AccentDark1` values, with fixed
contrast-foreground roles. Publication is asynchronous `PostWebMessageAsJson`
on the UI thread; no publisher worker, dynamic script, or whole-style sink is
part of the boundary. Native fallback is a structured combination of backdrop,
glass, form, and WebView-controller landing evidence and never claims opacity
from a partial boolean. If a later system-change reapply cannot confirm either
native path, the next exact envelope reports `degraded`; only `mica` makes the
page base transparent, so this truthful state immediately restores the
theme-correct opaque CSS base instead of leaving the prior snapshot visible.
The implemented host composition acquires its fixed instance mutex before any
local artifact or diagnostic ownership, then prepares pywebview, constructs the
shared service, validates/initializes the coordinated database pair, and only
then resolves the wheel-packaged page and creates a window. A pending document
authority keeps dispatch closed until native guard attachment; once trusted,
the host exposes only the immutable production mapping defined in
`M1_BRIDGE.md`.
Initialized failure aborts before native creation; UI-thread guard or
loaded-watchdog failure destroys once. One finalizer owns service, logging, and
mutex release without allowing cleanup failure to replace startup truth.
For a normal user close, a private bridge-admission gate first rejects new
calls, closes the task registry to wake drains and capacity-blocked sinks,
waits for already-admitted calls, then runs the service close off the WinForms
thread. Task observation cleanup and window-owned appearance cleanup are
separate owners. Appearance remains subscribed through incomplete or
exceptional service closure; only a complete shutdown closes it exactly once
and then permits one recursive-safe programmatic destroy. Incomplete or
exceptional attempts retain the window and expose a fixed native Retry/Cancel action; another title-bar X
can reopen that action but cannot itself retry or force destruction.
The loaded callback binds the current fixed status element before asynchronous
close presentation. Repeated loads replace that cached target, avoiding a late
DOM lookup against a destroyed document; a presentation failure is sanitized
and cannot alter shutdown state.
The native folder picker is the sole path-input exception: the host retains the
real path in a server slot and returns only an opaque id plus display string.
`pywebview` is an M1 runtime dependency, not an optional GUI extra. One
`interfaces.launcher` layer sits above sibling `cli` and `web` adapters. The
console entry points `nami-sync` and `python -m namisync` remain CLI-only;
no-subcommand use prints usage and points to `nami-sync-gui`. The
GUI-subsystem `nami-sync-gui` entry point starts the same web adapter without a
retained console. This is one GUI implementation exposed through correctly
classified Windows launchers, not a second desktop.

The adapter owns task cards and cosmetics, not review or projection authority.
A task may retain a plan with no live session. `M1_BRIDGE.md` exclusively
defines terminal-session release and explicit task close; application shutdown
still quiesces handlers and wakes drains/producers before closing observers and
the service. A second GUI launch activates the existing window and exits
successfully; activation failure is visible.

Presentation color has one dependency direction. GUI Break 1 places the exact
13 authored palette primitives and all status/operation semantic aliases in
`interfaces/web/assets/tokens.css`; yellow and purple have no authored `light`
primitive in the GUI Break 1 foundation. This is not a permanent ban on future
color growth: another hardcoded or derived color requires prior product-author
discussion plus a same-change contract, token, and evidence update.
The same file transcribes a minimum Microsoft Fluent light/dark neutral and
scale subset from pinned `@fluentui/tokens@1.0.0-alpha.24` source at commit
`32b42a5bf79c1836047dfc7fae07b1320731bce4`, with exact source hashes and
values retained in tests. Accessible stroke roles own visible control/focus
boundaries. It receives distinct Windows `Accent`, `AccentLight1`, and
`AccentDark1` roles from the native appearance snapshot. Those externally
owned inputs are provenance- and value-tested separately from the authored
palette. `components.css` may consume semantic aliases but never raw colors or
palette primitives, and Slice 4-7 surface renderers may consume only semantic
and component contracts. Gallery contrast/visual evidence selects theme pairs;
primitive names are not theme policy. Windows forced colors replace the authored
palette with system colors, and status views retain non-color cues. This makes a
palette change a token-boundary change rather than a renderer-wide rewrite.

Icon authority follows the same one-way boundary. `assets/icons/` contains
exactly four locally shipped monochrome SVGs selected from
`@fluentui/svg-icons@1.1.334`, plus their MIT license and a source record with
exact package/file URLs, version, and per-file SHA-256 hashes. `icons.js` is a
frozen source-owned glyph-name-to-class registry; it has no registration seam
and never contains or constructs markup, a URL, or a filesystem/web path.
`components.css` alone maps those fixed classes to local CSS masks and paints
them with `currentColor`; `tokens.css` alone owns shared icon sizes. Renderers
may choose a registered visual glyph but cannot make returned data authoritative
over a class, asset path, or SVG payload. Extending the set is a reviewed source,
provenance, package-manifest, and test change, not runtime composition.

Each open plan or inventory view uses one canonical server projection. Workflow code
owns generic node structure, subtree membership, rollups, and opaque id lookup;
`interfaces/web` owns tree-agnostic flatten/filter/search/window/anchor
presentation mechanics. The interface consumes a typed structural view of the
workflow-owned array directly, retains immutable source/visible indexes, and
creates accessibility row wrappers only for the bounded window. The exact
query/envelope/window bounds and anchor behavior live in `M1_BRIDGE.md`; other
external adapters impose an equal-or-stricter complete-request ingress bound.
Plan trees are memoized per request. Inventory uses immutable copy/swap
projections in a six-view LRU, built from a slim whole-location structure query
and detail-fetched only for visible row ids. History summary/detail paging is
performed by repository queries, not by loading then slicing.

Inventory has no database generation/snapshot token. Its causal refresh points
are view open, an observed terminal for the same location, and completed
acknowledge/restore. Acknowledged rows are hidden by the default server filter,
participate in no rollup, and carry their count on the filter chip; only an
`APPLIED` visibility mutation reflows/refetches the list. M1 never auto-scans.

Bridge handlers are concurrent: service review/projection state and adapter
task state have explicit locks, and no task lock spans a facade call or
encoding. `M1_BRIDGE.md` exclusively defines per-task drain concurrency, queue
and deadline bounds, progress replacement, reliable backpressure, recovery
cursors, and explicit-`Gap` behavior. Numeric sequence holes alone are not a
recovery signal. `Progress` supplies paired item identity for row updates.
Visibility receipts use a reproducible per-(gesture,row) key and one
caller-supplied timestamp. Session-creating commands instead retain
`command_id -> (request_id, session_id)` in the service until `close_session`
or shutdown. Plan/inventory/integrity receipt lookup, mutable scope resolution,
admission, and publication are single-flight per command id; a recognized raw
ID-gesture receipt is checked before mutable inventory is read again.

For an adapter-requested admission observation, dispatcher remains
domain-blind. It creates an unpublished record/hub/store row and preopened
stream while unschedulable, lets a callback adopt `(session_id, stream)` and
return idempotent rollback, emits `PENDING` into that stream, then atomically
publishes maps/pending and notifies the scheduler. Attach failure or shutdown
before publication rolls back the adoption, stream, hub, and store row and
starts no work. A terminal plan session is no longer live rail work but its
record/replay/receipt lifetime follows the release-versus-close contract in
`M1_BRIDGE.md`.

Interfaces own cosmetic `ui-state.json` (recents, geometry, columns, sorting,
collapsed paths, filter chips) directly. It persists no request, session, task,
selection, view id, or projection revision; it is separate from database-owned
semantic settings and needs no cross-interface writer mutex.

**Stage 6 host Slice 1 status (updated 2026-08-12).** The isolated UI-state
store and promoted hostile-navigation/bridge boundary implement and test the
forced-renderer call shape, UI-thread-only native `CoreWebView2` guards,
native committed-origin dispatch recheck, strict versioned allowlist, and
structured return boundary. Pywebview 6.2.1 is pinned from the Stage 6
reality run. Classified launchers, exact-CSP wheel assets, fixed instance
identity, database-pair gate, and secured product host are now composed. The
host was promoted with no commands; Slice 2 supplied its initial command
transport, and Slice 3 now supplies the event drain.
Installed native probes can inject an absolute physical local index file at
Python construction only; product launch retains the package-resource index and
has no external override surface.

**Stage 6 Slice 2 status (completed 2026-08-12).**
`interfaces/web/commands.py` is the sole owner of immutable production command
rows and payload policy. `interfaces/web/bridge.py` remains domain-blind and
owns parsing, origin/admission checks, the primitive-view codec, and sanitized
response envelopes. `interfaces/web/slots.py` alone retains picker paths;
`host.py` composes one snapshotted mapping; only `assets/bridge.js` touches
`window.pywebview`. The exact command/envelope/retry contract is exclusively in
`M1_BRIDGE.md`. At Slice 2 closure the wheel's frontend set was
`index.html`, `app.css`, `app.js`, `bridge.js`, and `render.js`; the last is the
strict production `textContent` sink. Browserless probes and the headed page
stay under `tests/assets/`. SH-G-3 and the installed real-WebView2
browser-behavior witness migration are closed; the plan/inventory DOM clauses
assigned to later slices remain open.

**Stage 6 Slice 3 status (completed 2026-08-12).** Adapter-owned tasks attach
their observation transactionally before dispatcher publication, and the
bounded drain implementation preserves reliable ordering/backpressure while
coalescing replaceable progress. The exact queue, deadline, recovery,
sequence, terminal, and release behavior is exclusively in `M1_BRIDGE.md`.
The explicit-`Gap`-only decision and command-specific `start_plan` revision
decision are ratified with landed named regressions. BR-G-33 implementation is
present. Its deterministic fixture now drives four attached-before-tick-zero
tasks through 60 logical seconds with exactly 6,000 `Progress` and 600 ordered,
exactly-once reliable item emissions, monotonic coalesced progress, four exact
terminal records, no `Gap`, and no queue above 64. The separate 260-reliable
overflow regression remains explicitly beyond-envelope and proves visible
`Gap`, retained-tail recovery, and terminal reconciliation. The standalone
installed-wheel real-WebView2 harness implements the conservative whole-Job
memory contract and real 60-second latency measurement. Its valid 2026-08-13
reference run passed event truth, ordering, latency, no-`Gap`, and clean-exit
checks, but its 67,375,104-byte whole-Job private-memory delta exceeded the
16,777,216-byte ceiling. SH-G-8 remains open without relaxing the bound;
reproduce with `.\.venv\Scripts\python.exe tests\bridge_event_benchmark.py --output "$env:TEMP\namisync-bridge-event-benchmark.json"`.

**Stage 6 GUI Break 1 status (completed and realigned 2026-08-13).**
`interfaces/web/appearance.py` owns Windows preference probes and observation,
native DWM/WebView material application with a theme-correct opaque fallback,
and fixed host-to-page appearance publication. `host.py` registers appearance
after the security boundary, retains it through retryable service shutdown, and
closes it immediately before terminal window destruction.
`appearance.js`, `tokens.css`, `components.css`, `icons.js`, and the fixed package-local icon
assets implement the color, component, motion, and icon authority described
above. At GUI Break 1 closure the wheel added exactly those four top-level
files, four pinned SVGs, and their `SOURCE.json` and `LICENSE.txt` records to
Slice 2's five assets; the gallery scenario remains test-only.
SH-G-11 through SH-G-14 foundations are closed. The realigned clean-wheel
gallery and material scenarios prove the pinned source, accessible strokes,
distinct task-card states, compatible dialog exit, live UISettings publication,
structured capable/fallback landing, and appearance lifetime. Their later
plan/inventory clauses remain with Slices 5 and 6.

**Stage 6 Slice 4 status (completed and realigned 2026-08-13).**
`interfaces/web/visible_sequence.py` is the sole tree-agnostic presentation
owner for strict workflow-array validation, collapse/search/caller-decided
filter retention, bounded windows, and deepest-visible ancestor anchoring.
Its typed structural view and pure functions retain no path, domain vocabulary,
projection lifecycle, active cache, or duplicate full-tree DTO. The installed
`tree.js` consumes only the already-decided generic window and server-derived
accessibility metadata, renders a fixed 28-pixel operable tree
with exactly two spacers, writes labels through `render.js`, and refuses stale
generations before reading their payload. `rail.js` and `panels.js` add only
labelled task-navigation and work regions with truthful empty text;
they create no task, session, plan, inventory, or history state. Slice 4 adds
no command. Python remains the structural-validation/window owner while
JavaScript performs no duplicate hierarchy or field validation; the exact
wire view and bounds live in `M1_BRIDGE.md`. The audit's roles-only
keyboard claim, 256-byte search limit, repeated anchor allocation, duplicate
full-tree DTO, and opaque rail have been removed. The 120,000-node scale
regression and real clean-wheel keyboard, platform-accessibility, geometry,
hostile-text, forced-colors, zoom, and stale-generation evidence pass, closing
BR-G-34, BR-G-2's Stage 6 clause, and SH-G-7. Slice 5 remains the first owner
of the real plan surface, and broader Stage 6/beta closure remains open. The
installed real-WebView2 browser witnesses now also cover the named transport
and drain-manager behaviors.

**Flesh — deferred.** Web API, durable cross-process task visibility, richer
desktop surfaces, and other interfaces behind the same facade.

**Acceptance criteria.**
- The real entry points (`nami-sync`, `python -m namisync`) dispatch by actual
  `sys.argv`; no command is reachable only under an explicit test argv (PoC
  SEVERE dead-CLI bug — smoke-test the real default path).
- Read-only CLI commands run concurrently with a GUI session; mutating commands
  obey the same volume/queue arbitration as any session.
- Location CLI starts require one explicit root/id and preserve both database
  overrides through service/runtime composition; no interface imports SQL or
  mapping policy to infer a location.
- Primitive settings patches preserve omitted fields, and a plan's captured
  semantic snapshot is unchanged by later commits.
- Adjacent headline-precedence pairs, compound secondary axes, and zero-byte
  `RAN` versus `UNRUN` cases determine exits from typed views only.
- Runtime guards raise real exceptions, not bare `assert` (which vanished under
  `python -O` in the PoC).
- Any presentation-triggering logic is separable from an event loop, so tests
  never enter a modal loop (PoC 15-minute `QMenu.exec()` hang).
- `M1_BRIDGE.md` BR-G-1 through BR-G-44 are the executable acceptance contract
  for Stage 5.5/6, including the 100k-file/120k-node/one-million-history-item
  performance envelope, 256-row bound, bridge security, race, shutdown, hostile
  name, selection, subtree, paging, and regression guards.

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
- **M1 — integrity product and executor refactor.** Stages 1–5.5 are implemented;
  Stage 6 remains. The settled dependency order is:
  1. contracts and semantics — canonical XXH3-128 evidence, nominal result
     items/phase summaries, four truth axes, execute→verify continuation,
     two-database reset boundary, split settings ownership, and facade/bridge
     security contracts;
  2. executor refactor — first the complete adaptive pipeline and Windows
     IO/finalization reductions from `obsolete/M1_HASH_REFACTOR.md` Track 1, then the
     coordinated executor+verifier XXH3-128 replacement and the ledger-v2
     reset from Track 2; history has since advanced to the reset-only v5
     receipt-journal contract;
  3. role-free inventory plus standalone baseline/verify/rebaseline workflows;
  4. in-session post-execution verification as one vertical integration slice;
  5. shared facade and CLI expansion;
  6. Stage 5.5 bridge-facing facade completion in parallel tree-substrate, scan-scope,
     and selection-semantics lanes, converging on the service; and
  7. Stage 6 pywebview/WebView2 desktop shell in the host → transport → event-drain
     → presentation-core chain, followed by parallel sync/inventory surfaces,
     lifecycle integration, and documentation/release.

  Implementation honored the dependency chain: standalone hashing followed
  HASH Track 2, post-execution integration followed standalone integrity, and
  the CLI commands followed their workflows. The delivery graph, slices, gates,
  regression watchlist, and performance budgets are recorded in
  `M1_BRIDGE.md`; its Stage 6 requirements remain normative. History retention
  is not part of M1.
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
