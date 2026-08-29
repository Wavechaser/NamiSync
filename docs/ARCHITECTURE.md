# NamiSync Architecture

This document is the structural reference for NamiSync. `FEATURES.md` says
what the product does; this document defines the durable boundaries, contracts,
coordination model, and design rules that keep those features coherent.
Module documents own component-specific behavior and implementation detail.
`CHANGELOG.md` owns dated delivery history.

Architectural elements are described by stability tier:

- **Core** — identity, safety, lifecycle, and persistence contracts whose change
  would invalidate stored evidence or multiple layers.
- **Capability** — domain behavior implemented behind core contracts, such as
  scanning, planning, execution, and verification.
- **Interface** — workflows and adapters that coordinate or present
  capabilities without redefining their policy.
- **Periphery** — replaceable platform integrations, presentation choices, and
  optional optimizations.

Status is stated only where the roadmap needs it: **active** means the contract
is in use; **unrealized** means the direction is accepted but has no production
consumer yet. Status does not turn implementation detail into architecture.

---

## 1. Layering and the import law

```text
core/          contracts, session machine, events, path safety, protocols
                 imports: standard library only
modules/       scanner, planner, preflight, executor, verifier
                 imports: core
db/            recorder, repositories, schemas, history observer
                 imports: core
workflows/     sync and integrity coordination; the only place modules meet
                 imports: core, modules, db
dispatcher/    session admission, custody, control, event fan-out
                 imports: core only
interfaces/    launcher, CLI, service facade, desktop adapter
                 imports: workflows and dispatcher through composition
```

The import law is:

1. `core` imports no project package.
2. Domain modules import `core`, never sibling modules.
3. `workflows` is the only layer where domain modules meet.
4. `dispatcher` is domain-blind and imports neither workflows nor modules.
5. Interfaces adapt the service/workflow surface and own no domain policy.
6. Dependencies do not point upward or sideways across component roots.

A domain component may be one module or a package. Files inside a component
package may collaborate behind its public facade; this does not make them
sibling domain components. Outside callers import the facade, while tests that
patch private collaborators patch the submodule that owns the symbol.

### 1.1 Dependency injection and composition

Modules receive recorders, clocks, policies, filesystem adapters, and other
collaborators as arguments. They do not construct infrastructure. One
composition root wires concrete dependencies for CLI and desktop entry points.

Database-pair initialization belongs to workflow composition because it may
coordinate ledger and history ownership. Interfaces expose primitive requests
and results; they do not import SQLite policy. Desktop pathname leases belong
to the desktop adapter because they protect process-owned application paths,
not managed-root sync behavior.

### 1.2 Component package direction

The executor and verifier use stable public facades with one-way internal
dependencies:

```text
executor/__init__.py  -> runtime.py, native.py, pipeline.py
executor/runtime.py   -> native.py, pipeline.py
executor/native.py    -> core + stdlib
executor/pipeline.py  -> core + stdlib

verifier/__init__.py  -> engine.py, native.py
verifier/engine.py    -> native.py
verifier/native.py    -> core + stdlib
```

Executor `native.py` and `pipeline.py` are independent leaves. Verifier
`native.py` never imports `engine.py`. Runtime/engine own domain policy;
native leaves own Windows primitives; the executor pipeline owns only bounded
single-file byte flow.

---

## 2. Coordination model

### 2.1 Session lifecycle

Every long-running operation uses one state machine:

```python
class SessionState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELING = "canceling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUSED = "refused"
    INTERRUPTED = "interrupted"
```

`COMPLETED`, `FAILED`, `CANCELED`, and `REFUSED` are terminal.
`INTERRUPTED` is reserved for durable-session reconciliation. The legal
transition table lives in `core/session.py` and is enforced by the dispatcher.

There is no waiting-for-input state. Sessions never hold resources while a
human decides. Planning terminates before review; execution is a separate
session started only after commitment.

### 2.2 Cooperative control and terminal ownership

Every cancellable loop receives the same non-blocking checkpoint through its
`RunContext`. The checkpoint returns to continue or raises typed control flow
for pause/cancel. Pause normally unwinds so volume custody can be released;
an operation with unsettled mutation state may defer the pause only until that
operation reaches a truthful settlement boundary. Resume always re-enters
admission and fresh preflight.

One generic session runner owns terminal emission. Modules and workflows return
typed results and never emit `Terminal` themselves. The runner converts normal
return, cooperative cancel, or ordinary failure into exactly one terminal
record; pause changes lifecycle state without producing a terminal. Dispatcher
custody wraps the runner and releases reservations on every exit path.

Item-processing modules must settle the in-flight item and classify unreached
items before cancellation leaves the module. The runner does not inspect module
internals or reconstruct domain outcomes.

### 2.3 Events and delivery classes

Every event is wrapped in a versioned envelope with session identity, a
gap-free per-session sequence, and injected UTC time.

```python
class DeliveryClass(StrEnum):
    LOSSY = "lossy"
    RELIABLE = "reliable"
```

- `Progress` is lossy and replaceable by a newer snapshot.
- lifecycle changes, item outcomes, explicit gaps, and terminal results are
  reliable.
- slow ordinary subscribers are bounded and ejected visibly with `Gap` rather
  than silently losing reliable events.
- the history observer receives bounded, timeout-guarded delivery. A contained
  failure degrades the result's audit axis instead of blocking or rewriting
  filesystem truth.
- late subscribers receive current state and a bounded replay tail, with
  sequence information sufficient to detect missing history.

The event plane is observation, not control. A module emits facts; it does not
wait for an event consumer to decide what happens next.

#### Progress v5 protocol

The active exact core event-envelope v5 contract below is the shared authority for
Progress producers, adapters, and consumers.

Under this protocol, a forced Progress emission bypasses source throttling but
remains lossy and coalescible. It is always derived from authoritative live
reporter state, never copied from an earlier lossy emission.

Progress is a phase-scoped observation of admitted work, not a settlement
ledger:

- `items_total` is the selected-item admission for that phase. `None` means the
  admission is not truthfully known; zero means a known empty admission.
- `items_done` is the number of distinct selected items for which a reliable
  terminal item outcome has been emitted, regardless of success, failure,
  deferral, blocking, skipping, or cancellation. Duplicate observation cannot
  increment it.
- `bytes_done` is the monotonic high-water of work observed in the phase, not
  necessarily durable published or recorded bytes. It carries across retries
  and pause/resume of the same task and may stall while a new attempt catches
  the high-water; it never regresses.
- `bytes_total` is a work budget. Executor progress keeps the reviewed selected
  content budget fixed. Verifier progress reports a physical-read budget that
  may grow monotonically when truthful work exceeds its prior admission.
- `item_id` and `item_type` together identify the active selected item and its
  opaque lookup namespace. `item_type` does not identify the producing module,
  phase, or outcome kind.
- `item_attempt_id` identifies one entry into an item's byte pipeline. It is an
  opaque bounded token, not an ordering counter or continuation-generation
  number. Item-byte counters describe only that attempt and may reset only
  under a new token.
- `current_path` is optional presentation context. It never identifies
  activity, joins a plan row, or substitutes for nominal item identity.
- `phase` is required self-description. Monotonic comparisons and totals are
  scoped to that phase rather than carried across phase changes.

For nullable scalars, `None` always means the fact is unavailable or
inapplicable; it never means zero. Item-byte counters are both present or both
absent. Active identity without an attempt represents non-byte or pre-stream
work. An attempt id without counters represents an active indeterminate byte
attempt, including truthful overshoot after its admitted item total is no
longer usable. Zero-byte streaming work still receives an attempt id and a
known `0/0` counter pair.

Item counts, sequences, and other bounded counters are exact JavaScript-safe
integers. Byte-work counters are checked nonnegative signed-64 integers in
Python and canonical decimal `Scalar64` strings on event/public wires. Every
reliable envelope is validated and bounded to 1,048,576 canonical bytes before
sequence, replay, audit, or subscriber mutation.

The normative reporter transitions are below. They describe authoritative
reporter state; because Progress is lossy, a transition guarantees delivery
only where the table explicitly requires a forced emission.

| Boundary | Required snapshot semantics |
| --- | --- |
| Phase entry | Start a new monotonic domain and force a snapshot from the phase's live admission and continuation state. |
| Item activation | Publish nominal item identity; do not manufacture an attempt or byte counters before byte-pipeline entry. |
| Item deactivation before settlement | Clear the current item, attempt, and item-byte reporter state without incrementing `items_done`. This ordinary lossy transition is required when an operation leaves the execution spotlight but its reliable settlement remains deferred. |
| Stream entry | Mint a fresh opaque attempt id and expose the attempt-local byte pair, including `0/0` when the known total is zero. |
| Stream progress | Advance attempt-local work monotonically and advance aggregate work only beyond its prior high-water. |
| Retry | Keep aggregate work at its high-water; mint a new attempt id exactly when the byte pipeline will run again, permitting only that new attempt's counters to restart. |
| Resume | Restore authoritative aggregate/item settlement state; a reconstructed byte-pipeline entry mints a new attempt id, while retained post-byte work does not invent a replacement attempt. |
| Overshoot | Preserve active item and attempt identity, make the item-byte pair absent, and apply the module's aggregate-budget rule. The pair cannot reappear for that attempt. |
| Reliable item outcome | Count that selected identity once in `items_done` and clear its active item, attempt, and item-byte reporter state. The resulting ordinary Progress remains subject to throttling; the next emitted snapshot must reflect the clear. |
| Pause | Emit no false settlement or Terminal; force the complete live snapshot and retain truthful active identity/attempt state. |
| Cancel | Emit reliable terminal outcomes according to cancellation policy, then force a live inactive snapshot with `current_path=None`. |
| Unexpected failure | Preserve the original failure, settle/classify items according to module policy, and force a live inactive snapshot with `current_path=None` without letting Progress-sink failure replace the cause. |
| Normal completion | Force a live inactive snapshot whose item count reflects every reliable terminal outcome emitted for the admission. |

Within one uninterrupted phase, `items_done` and `bytes_done` are
nondecreasing, `items_total` is fixed when known, executor `bytes_total` is
fixed when known, and verifier `bytes_total` is nondecreasing. Within one
item/attempt identity, present item counters are nondecreasing and the item
total is fixed. A phase change or explicit `Gap` ends those temporal comparison
domains.

Active item identity is the current presentation and execution spotlight, not
the set of selected work still awaiting outcomes. A newer Progress snapshot
may therefore repoint that spotlight without proving that the former item
settled. Consumers cannot require observation of an intermediate inactive
snapshot: Progress is replaceable, so an ordinary deactivation may be
coalesced away. Temporal attempt checks apply within one item identity, and one
non-null attempt token is a producer-wide identity that must never move between
items. The bounded consumer detects directly observed cross-item token reuse;
it does not retain an unbounded token history. Only a reliable item outcome
establishes settlement.

Terminal counter projection preserves those work semantics. A
`PhaseResult.bytes_done` value is that phase's final attempted-work high-water,
and `OperationResult.bytes_done` is the final high-water for the workflow's
primary byte-work domain. A compound sync keeps execute and verify counters in
their separate phase results and uses execute as its top-level byte domain; it
never sums the two. Bytes written into an owned temporary file and later
removed after a failed or canceled attempt still count as attempted work.
Neither terminal nor retained-history byte counters prove publication,
successful content, or ledger durability. Reliable item outcomes, executor
publication evidence, and the filesystem ledger retain those authorities.
The live `Terminal` wraps an item-free `TerminalSummary`; ordered item truth
travels through reliable outcomes and bounded history pages rather than being
duplicated in every terminal transport.

#### Authority, replay, and exact versioning

Consumers use this precedence rather than reconstructing truth from whichever
event arrived last:

1. Reliable item outcomes own item settlement and outcome classification.
2. Reliable `PhaseChanged` owns phase continuity when it is available. Its
   phase is always a nonempty string, so an empty token can never become phase
   authority.
3. Progress owns only its phase-scoped work snapshot and active presentation
   state; it never creates a terminal item outcome.
4. `Terminal` and the workflow result own final run truth.

On `Gap`, a consumer discards pre-gap Progress, active-item derivation, and
phase-dependent temporal comparisons. A later v5 Progress may restore
displayable progress through its embedded phase even when its `PhaseChanged`
was lost, but it does not reconstruct missed reliable outcomes or history. If
sequence continuity is known, Progress whose phase disagrees with the latest
reliable `PhaseChanged` is a protocol error. Terminal truth always supersedes
retained Progress.

Version numbers are boundary-specific, not one global product number. The
active core event envelope is exact v5; the desktop bridge command/response
envelope remains v1, plan continuation remains v5, execution continuation is
v7, and the persistence cut is ledger v4/history v6 at data epoch 6. The exact
browser-facing `SessionEventView` carries nested core version 5, and current
history cannot contain another event version. No private compatibility decoder
or positive older-version fixture remains.

Protocol evidence is intentionally layered:

1. Core and JavaScript validation prove snapshot structure and cross-field
   coherence.
2. Reporter transition tests prove executor and verifier state machines.
3. Workflow/session tests prove phase coordination, continuation, and terminal
   authority.
4. The settlement oracle proves integrated executor policy across its complete
   settlement matrix and stable normalized traces.
5. Browser tests prove delivery, replay, Gap recovery, atomic batch rejection,
   and consumer precedence.

### 2.4 Review, commitment, and execution

A sync is two sessions:

```text
planning session:
  scan -> plan -> observe -> preflight -> terminal review artifact

execution session:
  verify commitment -> observe -> preflight -> execute [-> verify] -> terminal
```

The human reviews between sessions, with no volume locks held. A commitment
binds the deterministic plan fingerprint and the exact reviewed selection.
Execution never accepts an uncommitted or mismatched set and never silently
replans after drift.

The same split supports queues and resume: a queued job is a committed
execution set awaiting admission, and a paused job is that set plus explicit
continuation state. Every start, queue wakeup, and resume freshly observes and
preflights the remaining selection.

### 2.5 Workflow continuation

Execution and linked verification use a discriminated workflow-owned
continuation. The execute phase carries the plan, authoritative selection,
per-operation status, and published copy evidence. The verify phase adds
frozen candidates, completed verification identities and byte counters, and
the already-settled filesystem/recording truth.

Phase is explicit; it is never inferred from past events. The workflow alone
translates executor-owned publication evidence into verifier-owned candidates,
so executor and verifier remain independent modules. Process-local resume is
active. Live session records hold continuation bytes; the separate stored
metadata/result contract has no continuation or live-record reference. Durable
restart recovery requires a separate protected continuation/recovery contract
and fresh authority/custody reconciliation in a later milestone.

### 2.6 Result truth

Terminal results keep independent axes:

- **filesystem** — what mutation actually settled;
- **integrity** — what independent readback or baseline established;
- **recording** — whether the main ledger accepted its evidence;
- **audit** — whether history retained its required event prefix.

One axis never rewrites another. A copy may publish successfully, verify as
matching, and still report degraded recording. Ordered nominal result items and
phase summaries are the common live/history projection source.

---

## 3. Core contracts

### 3.1 Contract authority and source locator

Architecture defines what a shared contract means and the invariants that all
consumers must preserve. The owning symbol in `namisync/core/` is authoritative
for its exact fields, enum values, inheritance, protocol methods, and function
signature. Module documents explain how a component uses or extends that
contract; they do not redefine its standardized shape.

If prose and source disagree about exact shape, treat the source as canonical
and repair the stale prose. Do not introduce an adjacent dataclass, enum, or
protocol merely because a module document omits or misstates the existing one.
Architectural snippets remain only when the shape itself explains a decision,
such as the session states, outcome vocabulary, or observation/judgment split.

| Contract family | Canonical source |
| --- | --- |
| Live/stored session records, phase/run results, and `SessionStore` | `namisync/core/session.py` |
| Event bodies, envelopes, delivery classes, codec, and exact-v5 validator | `namisync/core/events.py`, `namisync/core/event_v5.py` |
| Filesystem identity, complete Windows file-id adaptation, capability, metadata, records, and scan scopes | `namisync/core/models.py`, `namisync/core/file_identity.py` |
| Safe integer, signed-64, canonical scalar/file-index codecs, shared population-measure/excess primitives, distinct retained-plan and stateless-producer admissions, current issuer-bound typed review-limit facts, scanner population-admission protocol, exact immutable scan adoption, and final shallow-slot admission | `namisync/core/scalars.py`, `namisync/core/review.py` |
| Relative-path validation, keys, hierarchy, containment, and Windows spelling | `namisync/core/pathing.py` |
| Ephemeral root authority, native volume evidence, and admission probes | `namisync/core/root_authority.py` |
| Planning policy, operations, mappings, scopes, plans, fingerprints, and selection digests | `namisync/core/planning.py` |
| Deeply read-only preflight subjects, observations, refusals, and verdicts | `namisync/core/preflight.py` |
| Outcomes, recording status, provenance, content evidence, attestation, and hashing protocols | `namisync/core/evidence.py` |
| Commitments, mutable execution state/evidence, reduced execution authority, immutable execution-review and recording projections, scoped recording reasons/issues, failure decisions, copy/recorder/filesystem protocols | `namisync/core/execution.py` |
| Integrity state, selections, outcomes, commands, and verifier/recorder protocols | `namisync/core/integrity.py` |
| Ledger-bound host, volume, location, mapping, run, and inventory commands | `namisync/core/recording.py` |

Workflow-owned continuation envelopes and interface wire views are not core
contracts. Their owning workflow or interface source defines exact shape,
subject to the meanings and invariants established here.

### 3.2 Identity and path meaning

- Persisted relative paths are root-relative strings with a Windows canonical
  key based on one-codepoint uppercase, never Unicode `casefold()`.
- Absolute drive letters are presentation/mount facts, not persisted location
  identity.
- A volume is identified conservatively by stable volume evidence; labels and
  mount paths corroborate but do not silently replace identity.
- File identity is nullable because some filesystems cannot supply a stable
  value. Its index spans the complete unsigned Windows 128-bit domain and
  persists as opaque canonical decimal text paired with volume identity.
  Features that cannot obtain the complete identity degrade or refuse rather
  than inventing, narrowing, or ordering one.
- Path validation rejects absolute/drive-qualified relatives, traversal,
  ambiguous Windows suffixes and device names, alternate-stream syntax, NUL,
  malformed Unicode, and root escape.
- Ordinary logical spelling is retained in domain values. Extended Windows
  spelling is added only at native I/O and removed before evidence or display.

### 3.3 Root authority

`RootAuthority` is immutable, ephemeral evidence binding a logical root to its
reviewed mount and expected volume identity. It is never persisted, cached as
fresh, fingerprinted as a separate permission, or treated as authorization for
a later touch.

Shared core code performs stateless no-follow component inspection and returns
typed observations. Each consumer retains its own policy and timing:

- scanner decides traversal and mounted-root admission;
- preflight maps read-only observations to refusals;
- workflows decide overlap and mount ambiguity;
- executor re-probes at each final mutation guard;
- verifier re-probes per item and corroborates opened handles.

The remaining path-check-to-use boundary is explicit. A prior successful probe
never authorizes a later filesystem action.

### 3.4 Scan and inventory types

| Contract | Meaning |
| --- | --- |
| `VolumeId` | Stable matching material for a volume. |
| `CapabilityProfile` | Filesystem behavior relevant to planning/execution, including timestamp granularity, stable identity, and hardlink support. |
| `MetadataSnapshot` | Observed or intended managed metadata. |
| `FileRecord` / `DirRecord` | Root-relative inventory evidence with optional filesystem identity. |
| `UnsupportedRecord` | Review-visible evidence that is never silently treated as a file. |
| `ScanScope` | `FULL`, exact `PATHS`, or recursive `SUBTREES`. |
| `ScanResult` | Immutable scoped snapshot with records, warnings, capabilities, and explicit completeness. |

Completeness is a property of the observed scope. An incomplete scan may still
authorize evidence-positive additive work, but cannot authorize conclusions
that depend on absence or stable identity.

### 3.5 Plan and execution types

| Contract | Meaning |
| --- | --- |
| `MappingSnapshot` | Prior accepted correspondence supplied to the pure planner by a workflow. |
| `Plan` | Deterministic immutable intent, operations, dependencies, semantic settings, capacity requirement, and fingerprint. |
| `ExecutionSet.selection` | Dependency-closed executable subset, distinct from the full reviewed plan. |
| `Commitment` | Binding from human approval to plan fingerprint and selection digest. |
| `ExecutionSet` | Plan, authoritative selection, commitment, operation status, sparse item recording reasons, ordered task recording issues, continuation evidence, and validated aggregate byte high-water. |
| `ExecutionSetAuthority` | Canonical immutable execution references plus detached prior mutable-overlay baselines; it carries no duplicate plan fingerprint or operation-fact graph. |
| `ExecutionReview` | Frozen read-only projection of plan, selection, run id, and privately copied status supplied to observation and judgment. |
| `RecordingSpec` | Frozen shallow projection of plan, selection, run id, and commitment supplied at run-recording boundaries without exposing mutable execution continuation. |
| `ObservedWorld` | Fresh, scoped filesystem facts whose mappings and frozen leaves are deeply read-only for pure preflight judgment. |
| `Verdict` | Typed per-operation refusals plus the observation judged. |

Observed free space is not stored in a plan. Capacity need is a pure property of
operations and capabilities; available capacity is observed at review and
again immediately before execution.

Direct blockers remain visible as `BLOCKED`. Dependency, correspondence, user,
or incomplete-scan exclusions are represented explicitly rather than erased.
Every reviewed operation settles to one outcome:

```python
class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELED = "canceled"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
```

`NOOP` is an operation kind, not a skipped outcome: a selected no-op still
checks current evidence and records correspondence.

### 3.6 Evidence and attestation

Copy, baseline, and verification use one canonical `xxh3_128` content format.
Content evidence carries algorithm, digest, byte count, provenance, and time;
an `Attestation` binds that evidence to the observed subject it describes.
The attested byte count must equal the subject size.

Copy evidence describes the published target, never the source identity.
Plan fingerprints, custody keys, history identities, and other small
non-content hashes use SHA-256. Repositories retain the algorithm identifier so
stored evidence remains self-describing.

Plan and recorder hash inputs are explicit, producer-owned projections of the
declared contract fields. The canonical encoder accepts only its closed set of
primitive forms; unknown domain objects, coercive mapping keys, and non-finite
numbers refuse instead of acquiring a wire form through dataclass reflection.
File identities use canonical file-index text in these projections, while
ordinary integer fields remain numeric. A domain contract change therefore
requires an explicit projection and compatibility decision; it cannot silently
change idempotency identity by adding a dataclass field.

### 3.7 Protocol seams

The core declares narrow protocols for infrastructure and replaceable policy:

- `execution.Recorder` and `integrity.IntegrityRecorder` are the core ledger
  mutation protocols; database-owned recording commands cover the remaining
  ledger boundaries.
- Core clock protocols are the only source of current time.
- `FailurePolicy` returns retry/continue/stop decisions to the executor.
- `StreamingHasher` and `HasherFactory` abstract the concrete content hasher
  without importing it into core.
- `CopyBackend` owns byte transfer, not publication, retry, or recording.
- `DestinationPolicy` assigns target paths for a batch before diffing.
- `SessionStore` retains exact `StoredSessionRecord` metadata and full results,
  without continuation bytes or a live-record backreference. `SessionRecord`
  retains the separate live lifecycle/payload invariant. Durable metadata and
  protected continuation recovery are unrealized M2 contracts, not one
  interchangeable store implementation.

Incremental `ChangeSource` and ingest `MetadataExtractor` seams are accepted
but unrealized directions, not standardized core protocols. Their exact shapes
will be defined only with their first production consumer.

Protocols return data or decisions. They do not receive control of the state
machine.

For NamiSync-owned modules, the boundary owner's public return is the named
adoption point. The workflow checks the returned compound value once, then
passes immutable base values to first-party read-only consumers without
rebuilding or revalidating them at each package boundary. Mutable execution or
continuation overlays remain separately checked at the ownership transfers
where a fallible producer may legitimately change them. Reentrant callbacks
are different: reliable local state is committed before the call, regardless
of whether an immutable reference can be shared safely.

### 3.8 Persistence boundary

The main ledger and audit history are independent SQLite databases in WAL
mode. The ledger stores current inventory, correspondence, and integrity
evidence; history stores append-oriented session observation. History never has
a foreign key to the ledger and cannot roll back filesystem or ledger truth.

The schema reserves durable identity and interpretation fields from their first
version: volume-relative location identity, host provenance, content algorithm
and provenance, nullable file identity, soft deletion, generic namespaced
annotations, and schema/contract markers.

Before a named release, incompatible pre-release schema changes may use an
explicit paired reset boundary when older rows cannot be reconstructed
truthfully. Released formats require explicit migration policy; automatic
best-effort reinterpretation is forbidden. Exact active schema versions and
reset procedures belong in `DATABASE.md`.

---

## 4. Module boundaries

This section records ownership and coordination only. Detailed behavior,
acceptance cases, current implementation notes, and performance evidence live
in the linked module documents.

### 4.1 Core

**Tier:** Core · **Status:** Active

Owns shared dataclasses, enums, protocols, session state, event envelopes,
lexical path safety, root-authority evidence, canonical serialization, and
pure evidence helpers. It imports only the standard library and contains no
domain workflow or persistence implementation.

See `CORE.md`.

### 4.2 Scanner

**Tier:** Capability · **Status:** Active

```python
scan(root, ignores, ctx, scope=None, *, trusted_anchor=None,
     population_admission=None) -> ScanResult
```

Owns filesystem enumeration, capability observation, typed unsupported and
warning evidence, scope completeness, and cancellation checkpoints. It records
what exists without assigning source/destination roles or deciding sync work.
Walking is active. An incremental change-source protocol and journal/network
implementations are unrealized and will be standardized with their first
production consumer.
The optional scanner gate is structural. Plan review supplies its exact
stateless producer admission and inventory supplies its independent private
gate; scanner never receives the plan's cumulative retained-budget authority.

See `SCANNER.md` and `INVENTORY.md`.

### 4.3 Planner

**Tier:** Capability · **Status:** Active

```python
plan(source, target, correspondence, options, scope, *,
     review_admission=None) -> Plan
```

Purely converts immutable evidence and policy into deterministic reviewed
intent. It owns operation identity, dependencies, conflict/advisory
classification, correspondence-aware moves, destination assignment, semantic
settings snapshots, and capacity need. It never observes free space or mutates
the filesystem.

Path-preserving sync is active. Content-aware no-op detection, hash-based move
matching, retained conflict resolution, and ingest destination policies remain
unrealized.

See `PLANNER.md`.

### 4.4 Preflight

**Tier:** Capability · **Status:** Active

```python
observe(execution_review, filesystem, *, review_admission=None) -> ObservedWorld
preflight(execution_review, observed_world, *, review_admission=None) -> Verdict
```

`observe` performs scoped read-only I/O and decides nothing. `preflight` is a
pure judge over the returned snapshot. One immutable review and one admitted
world are shared across both calls in each cycle; neither collaborator receives
the mutable execution continuation. Workflows invoke both at review,
execution start, queue wakeup, and resume. The executor does not import
preflight; it retains operation-local final-touch guards.

Planner, observer, and preflight `review_admission` parameters accept the exact
stateless `PlanReviewProducerAdmission`. Their separate retained-result helpers
accept only cumulative `PlanReviewAdmission`; the two capabilities are not
interchangeable.

See `PREFLIGHT.md`.

### 4.5 Executor

**Tier:** Capability · **Status:** Active

`execute(execution_set, ctx, recorder, policies, filesystem) -> OperationResult`

Owns operation policy, dispatch, final-touch validation, retry, continuation,
cancellation settlement, progress, and post-mutation recording. Its native leaf
owns Windows handles and mutation primitives; its pipeline leaf owns bounded
single-file read/hash/write flow. Publication, non-byte mutation, recovery
state, and settlement are typed effects reduced through one policy path.

Mutation follows reviewed operation order, atomic same-volume publication,
truthful post-failure settlement, and record-after-success ordering. Any future
parallel file execution, restartable copies, alternate-stream support, or copy
backend must preserve those contracts.

See `EXECUTOR.md` and `TOOLS.md`.

### 4.6 Verifier

**Tier:** Capability · **Status:** Active

`verify|baseline|rebaseline(selection, ctx, recorder, reader) -> IntegrityRunResult`

Owns per-item classification, progress, conditional evidence recording, and
integrity outcome policy. Its native reader owns cache-honest, handle-bound
Windows reads and fresh root/volume corroboration. Standalone and linked
post-copy verification share classification but not executor publication
policy.

Background integrity, repair guidance, and benchmark-justified parallel reads
are unrealized.

See `VERIFIER.md` and `INVENTORY.md`.

### 4.7 Database

**Tier:** Core/Capability boundary · **Status:** Active

The recorder is the sole main-ledger writer; repositories own reads; schema
code owns format identity; settings own semantic defaults; the history observer
subscribes to events and writes its independent store. Conditional evidence
writes bind a row and its observed state so stale observations cannot become
current claims. Serialized writers bound contention, and persistence failures
surface on their own result axes.

History detail is paged and bounded. Retention and maintenance require their
own cross-process-coordinated session and remain unrealized.

See `DATABASE.md`, `RECORDER.md`, and `HISTORY.md`.

### 4.8 Dispatcher

**Tier:** Interface coordination · **Status:** Active process-locally; durable
custody unrealized

`submit(kind, request) -> SessionId`, plus generic pause, resume, cancel,
subscribe, list, get, and close operations.

Owns domain-blind admission, volume-scoped concurrency, worker-generation
custody, cross-process mutation exclusion, lifecycle control, event sequencing,
bounded replay, and orderly teardown. Workflow kinds and pause capability are
registry data; the dispatcher never interprets domain payloads.

The active store is process-local metadata; dispatcher reads its live records
for session state and continuation. Durable queue ownership, startup
reconciliation, and cross-process task visibility belong to M2. A durable
`SessionStore` implementation alone cannot supply restart: protected
continuation recovery needs its own contract and fresh authority/custody checks.

See `DISPATCHER.md`.

### 4.9 Workflows

**Tier:** Interface coordination · **Status:** Active

Plain workflow functions are the only place modules meet. They sequence typed
calls, translate between sibling component contracts, own continuation payloads,
derive authoritative safe/user selections, and maintain one logical recording
across compound phases.

Primary shapes are:

- sync planning: scan → plan → observe → preflight;
- committed execution: commitment → observe → preflight → execute → optional
  linked verify;
- inventory/integrity: resolve location → scan/reconcile → baseline, verify, or
  rebaseline.

Undo, repair, replay, and ingest must enter as ordinary planned workflows so
managed user-data mutation continues through review, preflight, and execution.

See `WORKFLOWS.md`.

### 4.10 Interfaces

**Tier:** Interface/Periphery · **Status:** CLI active; desktop foundation and
shared presentation active; remaining product surfaces unrealized

The service facade exposes primitive typed views over workflows and dispatcher
state. CLI and desktop adapters are siblings and own no sync, selection,
inventory, or history policy. Interface-owned task identity may outlive an
individual session but does not replace plan or session authority.

The desktop bridge exposes one versioned, allowlisted command surface and
bounds the complete serialized request to 65,536 UTF-8 bytes before
constructing presentation values. It uses packaged local assets and treats
server projections as authoritative.
Workflow code owns hierarchy and membership; the web adapter owns generic
flattening, filtering, windowing, and accessible presentation. Cosmetic state
is stored separately from semantic settings and never persists authority.
The active typed `ui-state.json` owner provides versioned full-section reads
and guarded replacements inside the interface layer; it does not pass through
the service facade, workflows, database settings, plan hashing, or sync
admission. Revisions are process-local concurrency evidence, while the
document schema protects durable compatibility. Adding a recognized section
or changing an on-disk value shape advances the global schema so older
binaries preserve rather than erase newer cosmetic state. The exact read and
guarded-replace rows and their appearance consumer are active at the desktop
bridge. One pre-window snapshot drives the opaque background and native
controller; later cosmetic revisions compose effective appearance without
reclassifying raw Windows evidence or entering sync authority.

Windows host security, bridge transport, presentation tokens, and lifecycle
policy remain adapter concerns. `interfaces/web/readiness.py` is the named owner
of the current-document readiness state machine and its exact phase contexts.
Normal desktop command availability depends on current-generation bilateral
document liveness: native security/load and shell acknowledgement first join
with a confirmed readable base surface, then a neutral host-to-page challenge
must be posted and echoed by that same page. The random challenge is a
short-lived liveness nonce, not authorization; it is neither logged nor
persisted and never replaces exact-origin trust, bounded handler reservation,
or dispatcher session admission. Appearance publication and enhancement
quality are orthogonal after base-surface safety settles; only an unconfirmed
rollback after native surface mutation may refuse startup.

Host composition owns the `admit(name)` join between the final immutable
command mapping and readiness context, making the durable dependency edge
normal command availability <- bilateral document liveness. The bridge
separately owns exact-document trust and bounded handler reservation; it
consumes only an exact generic admission verdict and forwards a granted opaque
context without interpreting readiness. `interfaces/web/document_channel.py`
is the sole production WebView2 host-to-page message sink and rechecks document
currency inside its queued UI callback. Exact limits, evidence, and delivery
status belong to `M1_BRIDGE.md`, `M1_SHELL.md`, `INTERFACES.md`, and
`DESKTOP_UI.md`, not this document.

See also `COMMANDLINE.md`.

---

## 5. Cross-cutting invariants

These invariants apply under the supported assumptions and tolerance policy in
`DEFENSE.md`.

1. **One terminal for every ordinary runner exit.** The session runner owns
   terminal emission for return, cooperative cancel, and ordinary failure;
   process termination may preclude emission and is recovered as incomplete
   work rather than invented terminal truth.
2. **Checkpoint everywhere.** Long loops yield to one pause/cancel contract.
3. **Never wrong, only behind.** Durable evidence truthfully describes its
   observation or effect time; reconciliation advances from it instead of
   deleting truth to make state look tidy.
4. **Records fail loudly; telemetry may be replaced.** Ledger and required
   audit failures are visible. Progress is explicitly lossy.
5. **Policies decide; machines enforce.** Extension points return decisions and
   cannot bypass lifecycle or safety rules.
6. **Pipeline-only mutation.** Managed user data changes only through reviewed
   plan → preflight → execute workflows.
7. **Sessions never block on a human.** Review occurs between sessions.
8. **Identity uses conservative evidence.** Ambiguity refuses or degrades; it
   is never guessed through.
9. **Owned artifacts use exact recognition.** Substring/suffix matching never
   grants cleanup authority.
10. **One injected UTC clock.** Local conversion happens only for presentation.
11. **Commit-to-execute.** Mutation requires a fingerprint- and
    selection-bound reviewed commitment.
12. **Truth axes stay separate.** Filesystem, integrity, recording, and audit
    cannot rewrite one another.
13. **Content evidence is canonical.** Copy and verification share one
    self-describing content format and byte/subject-size invariant.
14. **Continuation is explicit.** Phase and completed work are stored facts,
    never reconstructed from event history.
15. **Evidence authority matches the claim.** A target, drift guard,
    named-reference result, and protected release authority are distinct.
16. **External writers remain external.** Volume custody coordinates NamiSync
    processes, not arbitrary filesystem writers. Full preservation is
    conditional on the quiescent-root baseline in `DEFENSE.md`; fresh final-
    touch guards detect observable drift, while a pathname check never claims
    handle-bound exclusion it does not provide.
17. **Validate once at adoption.** External values are admitted at ingress;
    first-party module results are checked once at the boundary-owning public
    return or another explicitly named ownership transfer. Downstream consumers
    do not reconstruct or revalidate immutable base values. Mutable overlays
    are checked only at transfers where their owner may have changed them.
    Capacity admission and filesystem freshness remain separate obligations.
18. **One authority per fact.** Each reliable item, state transition, durable
    receipt, and presentation projection has one named semantic owner. Copies
    and views may transport that fact but cannot become peer authorities or
    reinterpret another truth axis.

### 5.1 Measurement authority

Quantitative acceptance separates observation from judgment. An instrument
records exact observations and refuses unknown shapes; an independent contract
names the fixture, reference profile, statistic, scaling axes, retention or
aggregation policy, authority tier, and rerun trigger. A validator applies the
predeclared bound.

The tier definitions and required evidence are normative policy in
`DEFENSE.md` §7. Architecture adds one constraint: incompatible scaling axes
are never merged because one tool can measure them. Transport custody, retained
terminal results, projection caches, and whole-runtime containment have
distinct owners and acceptance claims. Exact datasets, byte counts, run
results, validator identities, and open/closed gate status belong to the owning
module or delivery document.

Current claim and evidence ownership is:

| Claim | Owner |
| --- | --- |
| Executor settlement semantics | `TOOLS.md` |
| Desktop bridge behavior and transport custody | `M1_BRIDGE.md` |
| Desktop host/runtime containment | `M1_SHELL.md` |
| Component-specific performance | Owning module document |

---

## 6. Milestone roadmap

### M0 — safe headless mirroring

**Status:** Complete

Established the reusable core: typed sessions and events, domain-blind
dispatcher custody, walking scans, deterministic plans, repeatable preflight,
atomic guarded execution, ledger/history persistence, explicit review and
commitment, and a functional CLI. M0 deliberately used process-local session
state and conservative single-file execution while freezing the contracts that
later milestones build on.

### M1 — integrity product and headed desktop

**Status:** Active

Adds canonical content evidence, role-free inventory, standalone and linked
integrity workflows, bounded durable history readback, shared service/selection
facades, and the secured WebView2 desktop. The remaining work is product-facing
desktop completion and beta hardening, not a new domain architecture. Exact
delivery slices, gates, and current status live in `M1_PLAN.md`,
`M1_BRIDGE.md`, and `M1_SHELL.md`.

### M2 — durable sessions and queue ownership

**Status:** Unrealized

Adds durable session metadata, exclusive queue ownership, startup reconciliation
and the first production use of `INTERRUPTED`, durable committed plans, launch
policy, and cross-process task visibility. Restartable continuations require a
separate protected recovery-store contract with explicit retention and fresh
workflow authority/custody reconciliation; persisting current process-local
payloads through the metadata store is not that design. Coordination remains
domain-blind and workflow-owned continuation meaning remains outside dispatcher.

### M3+ — maintenance, scale, and new workflows

**Status:** Unrealized

Adds cross-process-coordinated history retention and data protection, explicit
schema migration, incremental change sources, evidence-justified parallelism,
ingest, replay/repair, and additional interfaces. New workflows reuse the same
typed plan/review/preflight/execution path; optimizations must preserve the
existing identity, evidence, custody, and settlement contracts.

---

## 7. Documentation ownership

- `DEFENSE.md` owns supported assumptions, trusted boundaries, hard walls,
  tolerance classes, quantitative-evidence authority, and residual-risk
  dispositions.
- `ARCHITECTURE.md` owns durable structure, coordination, contracts, and
  milestone direction.
- `FEATURES.md` owns implemented and planned product behavior.
- Module documents own implemented component policy, algorithms, local tests,
  current state, and limits that do not redefine a cross-cutting defense or
  bridge contract.
- `M1_PLAN.md`, `M1_BRIDGE.md`, and `M1_SHELL.md` own active delivery plans and
  gates.
- `CHANGELOG.md` owns dated task outcomes.
- `HANDOFF.md` owns only immediate next-session context.

When a detail changes without altering a cross-module contract, update its
owning module document rather than copying it here. Add architecture detail
only when multiple layers must coordinate around the decision or when changing
it would reinterpret durable state or public contracts.

The accepted Stage 6 second-half target is intentionally not restated here.
`M1_BRIDGE.md` maps its event, database, task-authority, publication, and
retention decisions to the existing DR-BR records; `DEFENSE.md` §1.3 owns the
normative scalar and containment walls. Until each implementation checkpoint
lands, the current-version contracts above remain the description of running
code. Their coordinated replacement must update this document and the
contract-to-source locator in the same implementation commit.
