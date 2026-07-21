# Core Module

Status: M0 scan/plan/preflight, session/event/evidence, execution, integrity,
and recording contracts implemented with their owning operation modules.

## Purpose

`namisync.core` defines the vocabulary and invariants shared by the system. It
contains no scanner, planner, executor, database, dispatcher, workflow, or UI
behavior. It imports only the Python standard library and never constructs an
OS, SQLite, clock, policy, or presentation collaborator.

Core exists to make unsafe or inconsistent states difficult to express. A
module may add behavior behind these contracts, but it may not invent a second
session state machine, event shape, path identity rule, outcome vocabulary, or
attestation format.

## Owned Contracts

- Stable identifier value types: session, run, operation, row, mapping, host,
  volume, and file identity.
- Immutable scan (`FileRecord`, `DirRecord`, `UnsupportedRecord`), plan,
  observation, content-evidence, attestation, item-result, and run-result
  dataclasses; `ExecutionSet` is the explicit mutable execution-status carrier.
- `MappingSnapshot`, root-qualified `Subject`, `Commitment`,
  `PreservationPolicy`, `MetadataSnapshot`, capability profile,
  and the stable `VolumeId`/corroborating `VolumeEvidence` split.
- `SessionState`, its legal transition table, and terminal-state predicate.
- Six-value `Outcome` (`succeeded`, `skipped`, `failed`, `canceled`, `deferred`,
  `blocked`) and typed reason codes; free-form text is presentation detail, not
  control flow.
- Versioned event envelopes and typed event bodies, including `Gap` and the M1
  `IntegrityOutcome`/eight-value `IntegrityResult` vocabulary.
- `RunContext`, nonblocking cooperative pause/cancel checkpoint protocol, and
  the generic session runner that alone resolves pause/cancel and emits
  `Terminal`.
- Protocols for recorder, clock, failure policy, copy backend, worker count,
  change source, destination policy, metadata extraction, session storage, and
  filesystem observations needed by module contracts.
- Windows relative-path normalization, validation, containment, and long-path
  conversion helpers.
- Pure shared calculations such as capacity requirements and deterministic
  operation identifiers when those rules cross module boundaries.

The M0 scan/plan/preflight portion is implemented in `core/pathing.py`,
`core/models.py`, `core/planning.py`, and `core/preflight.py`. These files own
canonical Windows relative paths, immutable filesystem evidence, deterministic
plan serialization and capacity, and root-qualified observation/refusal
shapes. OS walking and observation remain in operation modules; core stays
standard-library-only and behavior-free.

`SyncOptions.propagate_source_casing` is a latent, fingerprinted planning
policy. It defaults to false and survives workflow payload round trips so a
future configuration or GUI control can expose it without changing the plan
shape. `OperationReason.CASE_MISMATCH` and
`UNICODE_NORMALIZATION_MISMATCH` are non-blocking review advisories; collision
states remain separate typed blockers. The old `BlockedReason.CASE_MISMATCH`
value remains decodable for compatibility with prior serialized plans, but the
current planner does not emit it. `OperationKind.RECASE` represents a
same-Windows-key filename spelling change explicitly, carries prior-target
evidence, contributes zero content bytes, and never implies update/trash
semantics.

Executor continuation and collaborator contracts are implemented in
`core/execution.py`: the mutable `ExecutionSet`, fixed-format `RunId`, typed
failure decisions/reasons, copy digest, and filesystem/copy/recorder protocols.

`core/recording.py` now owns the immutable host, volume, location, mapping, sync
run, finish, and inventory commands used at the ledger boundary. Per-operation
sync evidence remains behind `core.execution.Recorder`, while conditional
integrity evidence remains behind `core.integrity.IntegrityRecorder`; the
database implements both without moving SQL or persistence policy into core.

## Session Contract

The transition table is defined once and consumed by the dispatcher. Every
request is either a legal transition or a typed rejection with no state change.
`INTERRUPTED` is resumable and is produced only by durable-store reconciliation;
it is not a normal runtime terminal.

`Checkpoint` never waits. It returns normally, raises `PauseRequested`, or
raises `Canceled`; either exception unwinds the workflow stack to the generic
runner. A pause transitions to `PAUSED` without a terminal and releases volume
custody. Resume re-enters admission at the back of the required volumes' queue
and performs fresh observation/preflight. Cancellation produces the one
`CANCELED` terminal.

The generic runner in `core/session.py` is the sole `Terminal` producer for
every workflow. Modules and workflows return typed results and emit only
nonterminal bodies. The dispatcher wraps the runner with custody acquisition
and unconditional release; it does not add a second terminal path.

Pause is a generic per-workflow-registration capability. Execution supports it
from M0 through mutable `ExecutionSet.status`; verify and baseline add an
item-status continuation in M1. Scan, plan, and hash import refuse pause cleanly
and remain cancelable. A pause unwinds, forces recorder flush where applicable,
persists the workflow-owned continuation, releases custody, and emits no
terminal.

`Canceled` and `PauseRequested` remain payload-free. The runner consumes them
and aggregates already emitted RELIABLE item outcomes into the session result;
unexpected exceptions are likewise consumed after typed detail is attached to
the one terminal/log path, so no exception can escape to create a second
terminal. Operation modules emit outcomes as work settles rather than holding a
private result list until return. Before `Canceled` leaves an item-processing
module, its unwind finalizer emits `CANCELED` for the in-flight and every
unreached selected item. The same finalizer emits nothing for unreached work on
`PauseRequested`, because that work remains pending for resume.

The runner accepts a dispatcher-owned item accumulator. It is retained across
pause attempts and cleared only after terminal settlement, so a resumed session
that later cancels or fails includes reliable outcomes earned before the pause.
The registry adapter snapshots continuation bytes before `PAUSED`; the
dispatcher stores those bytes without decoding them and opens a fresh adapter
invocation on resume.

## Event Contract

Every envelope contains a session id, gap-free per-session sequence, injected
UTC timestamp, and schema version. State, phase, item, and terminal events are
reliable; progress is a replaceable snapshot. Event details must be typed or
schema-versioned—consumers must not infer semantics by parsing user-facing
strings.

History is attached at admission as the distinguished reliable audit
subscriber. Its bounded queue may apply producer backpressure only at a safe
checkpoint boundary and only until an injected generous timeout. Drain within
the timeout guarantees delivery; writer failure or timeout degrades the
session's audit axis loudly and ends backpressure. Other reliable subscribers
that overrun their bounded queue are ejected; the first thing they observe is a
typed `Gap(first_missed_seq)`. Late subscribers receive current state plus a
bounded tail and use sequence numbers to detect omitted history. Progress alone
is lossy/coalescible.

Terminal finalization is a bounded two-phase handshake. The runner first drains
the audit subscriber and asks it to finalize the run from the preterminal event
stream and provisional result. An acknowledgement within the same generous
timeout sets `audit=OK`; failure or timeout sets `audit=DEGRADED` and ends
blocking. The runner then constructs and releases the one immutable `Terminal`
to ordinary subscribers. History never needs to consume or parse that Terminal,
so no corrective second terminal or circular acknowledgement exists.

The version-2 M0 envelope codec round-trips `StateChanged`, `PhaseChanged`, `Progress`,
`ItemOutcome`, `Gap`, and `Terminal` and rejects unknown schema/body versions.
Integrity-specific event serialization remains part of its M1 integration; the
live event plane already transports verifier-defined bodies structurally and
treats every non-`Progress` body as reliable.

## Path And Identity Rules

Persisted paths are root-relative with `\` as the canonical separator. Reject
empty components where Windows would reinterpret them, absolute paths, drive or
UNC qualification, `.`/`..`, alternate root syntax, embedded NUL, and any path
with an ambiguous suffix, stream/device qualifier, or unpaired surrogate, plus
any path whose resolved handle escapes its root through a reparse point.

Lexical validation and handle-based containment are separate checks: lexical
validation is pure and always available; filesystem containment belongs in
observation/preflight. Long-path conversion happens only after validation.

`rel_path_key` follows Windows/NTFS one-codepoint case mapping, not
`str.casefold()` and not unrestricted Python `upper()` when it expands a code
point. The implementation must use a tested Windows-equivalent mapping strategy
and preserve NTFS-distinct names such as `Straße.txt` and `strasse.txt`.

Unicode normalization is deliberately not part of path identity: NFC and NFD
spellings remain distinct stored paths. Planner may identify a unique
same-parent canonical-equivalence pair for review, but no core path helper
rewrites either spelling.

Filesystem enumeration may observe names outside this lexical contract. Those
names never enter `FileRecord`, `DirRecord`, `UnsupportedRecord`, or operation
paths: the scanner retains an escaped typed warning at the nearest valid parent
and marks the scan incomplete. Canonical plan JSON preserves established UTF-8
bytes for valid Unicode and defensively emits JSON surrogate escapes for any
malformed free-form string that reaches serialization.

The same final UTF-8 rule applies at ledger command hashing, history
hash/detail serialization, and opaque workflow payload encoding: valid Unicode
bytes remain unchanged, while an unpaired surrogate is emitted as its JSON
escape instead of raising. Path validation remains the primary boundary; this
serializer defense prevents a future relaxation or unrelated free-form detail
from reintroducing raw encoding failures.

`VolumeId(serial, fs_type)` is the stable key. Label and other mutable mount
facts live in `VolumeEvidence`: relabeling is only noted, a matching serial with
a changed filesystem type requires explicit rebind, and two mounted volumes
with one key require explicit user choice. File identity is nullable and never
fabricated on filesystems that cannot supply stable identity.

## Time And Evidence

All domain timestamps come from one injected `Clock`, are timezone-aware UTC,
and are normalized once before persistence or event emission. Presentation
converts to local time.

`ContentEvidence` owns SHA-256 digest, size, provenance, and observation time.
`Attestation` joins that content to the exact subject `FileStat`. For copy and
update, the subject is the published target re-statted after publication; the
source's post-read stat is separate drift-guard evidence. No consumer may treat
copy-stream evidence as readback verification.

`OperationResult.status` reports filesystem truth only. Ledger persistence and
history persistence are independent `recording` and `audit`
`RecordingStatus.OK|DEGRADED` axes; no axis rewrites another. Typed
`Disposition.RAN|UNRUN` distinguishes a canceled discarded queue entry and a
refusal from sessions that actually began domain work without parsing strings
or inferring from an empty operation list.

## Expectations Of Other Modules

- Modules consume core types without mutating frozen values or extending enums
  locally.
- Workflows pass typed outputs between modules and own coordination.
- Dispatcher alone enforces transitions and custody; it remains domain-blind.
- Recorder is the only main-ledger writer and receives complete evidence units.
- Interfaces render reason codes but never branch on free-form detail text.
- Every long loop calls the single checkpoint at documented safe boundaries.

## Provisioning For Latent Features

Declare expensive-to-retrofit shapes now: `DEFERRED`, `BLOCKED`, schema-versioned events,
all `Scope` kinds, nullable file identity/hardlink group, policy protocols,
opaque workflow payloads, and attestation provenance. A latent protocol is
declared shape-only and has no implementation until its first consumer; this
provisions the seam without speculative runtime behavior.

ADS is deliberately lighter than a cross-module protocol: `supports_ads` and
the unexposed `preserve_ads` flag reserve the decision, while scan records,
plans, schemas, and M0 acceptance tests contain no stream manifest. When the
feature is implemented, enumeration and validation belong to executor-time copy
logic; no scanner role or inventory representation is added.

## PoC Hardening

- Central path normalization prevents the PoC `casefold()` identity merge.
- Runtime guards raise typed exceptions rather than `assert`, which disappeared
  under `python -O`.
- One clock prevents cross-database host/timestamp drift and lexical retention
  ordering errors.
- One event/result vocabulary prevents verifier, history, CLI, and GUI from
  disagreeing about partial failure, refusal, and integrity state.
- One exact temp-name parser supplies scanner ignore, preflight capacity, and
  executor recovery with the same ownership grammar, preventing generic
  `.synctmp-` matches from excluding, counting, or deleting user data.

## Acceptance Criteria

- Exhaustive tests prove every legal session edge and reject every other edge
  without changing state.
- Every session path—success, refusal, cancellation, exception, and later
  interruption—produces exactly one terminal from the core runner; pause
  produces none until that same session resumes and terminates.
- Concurrent event emission yields gap-free monotonically increasing sequence
  numbers per session and no sequence sharing across sessions.
- Event serialization round-trips every body and rejects unsupported schema
  versions explicitly.
- A slow-subscriber stress test proves timeout-bounded history backpressure,
  degrades `audit` on timeout/failure, ejects an overrun non-history reliable
  subscriber with `Gap`, and never silently loses an event while claiming OK.
- Unicode corpus tests preserve NTFS-distinct paths and normalize separator and
  ordinary case variants identically.
- Path tests reject drive, UNC, device, traversal, NUL, mixed-separator escape,
  and reparse-root escape cases while accepting valid long relative paths.
- UTC/DST boundary tests prove all core timestamps are aware UTC values.
- Attestations cannot be constructed without algorithm, digest, provenance,
  subject stat evidence, and observation time.
- A changed selection invalidates a `Commitment` even when the plan fingerprint
  is unchanged; uncommitted and mismatched execution sets are unexecutable.
- `recording` and `audit` can degrade independently without rewriting a
  successful filesystem terminal; terminal-finalization fault injection proves
  the audit axis reflects failure to write the final history envelope.
- Cancel/pause fault injection preserves earned item results and continuation
  state through the runner; pause emits no terminal and exception surfacing
  cannot trigger a second terminal.
- `Disposition` round-trips and distinguishes `CANCELED+UNRUN` queue discard,
  `REFUSED+UNRUN`, and work that actually ran.
- Import-linter proves `namisync.core` imports no project layer.
