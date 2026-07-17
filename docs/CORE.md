# Core Module

Status: draft contract. Priority: M0 bones, required before every other module.

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
  `PreservationPolicy`, `MetadataSnapshot`, and the stable `VolumeId`/
  corroborating `VolumeEvidence` split.
- `SessionState`, its legal transition table, and terminal-state predicate.
- `Outcome` and typed reason codes; free-form text is presentation detail, not
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

An execution's continuation is its mutable `ExecutionSet.status`: completed
operations remain completed and unreached operations remain eligible after
fresh preflight. The corresponding restart/continuation representation for
scan, verify, baseline, and import sessions is not yet defined by the
authoritative architecture; those session kinds must not claim resumable pause
until that gap is resolved.

The runner pseudocode's bare `Canceled`/`PauseRequested` exceptions also carry
no typed partial result. Core therefore has no specified way to build a canceled
`OperationResult` containing already-earned item outcomes, or to persist the
continuation before announcing `PAUSED`. The exception payload/result-builder
contract and the rule for surfacing an unexpected exception after terminal
emission must be frozen before the runner is implemented; otherwise outcome
loss or duplicate terminal handling is likely.

## Event Contract

Every envelope contains a session id, gap-free per-session sequence, injected
UTC timestamp, and schema version. State, phase, item, and terminal events are
reliable; progress is a replaceable snapshot. Event details must be typed or
schema-versioned—consumers must not infer semantics by parsing user-facing
strings.

History is attached at admission as the distinguished reliable audit
subscriber. Its bounded queue may apply producer backpressure only at a safe
checkpoint boundary and never drops an admitted event. Other reliable
subscribers that overrun their bounded queue are ejected; the first thing they
observe is a typed `Gap(first_missed_seq)`. Late subscribers receive current
state plus a bounded tail and use sequence numbers to detect omitted history.
Progress alone is lossy/coalescible.

The policy for a history writer that stalls indefinitely (rather than failing
promptly) remains an implementation blocker: bounded memory plus guaranteed
delivery requires waiting, while the current architecture also says history
must not block filesystem work. No implementation may hide that tradeoff with
an unbounded queue or silent drop.

## Path And Identity Rules

Persisted paths are root-relative with `\` as the canonical separator. Reject
empty components where Windows would reinterpret them, absolute paths, drive or
UNC qualification, `.`/`..`, alternate root syntax, embedded NUL, and any path
whose resolved handle escapes its root through a reparse point.

Lexical validation and handle-based containment are separate checks: lexical
validation is pure and always available; filesystem containment belongs in
observation/preflight. Long-path conversion happens only after validation.

`rel_path_key` follows Windows/NTFS one-codepoint case mapping, not
`str.casefold()` and not unrestricted Python `upper()` when it expands a code
point. The implementation must use a tested Windows-equivalent mapping strategy
and preserve NTFS-distinct names such as `Straße.txt` and `strasse.txt`.

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

`OperationResult.status` reports filesystem truth only. Ledger persistence is
the independent `RecordingStatus.OK|DEGRADED` axis; neither rewrites the other.
The architecture also requires history-write degradation on the session result,
but its type reference currently has no audit/history status field. That shape
must be added or explicitly folded into a renamed generalized persistence axis
before result schemas freeze.

## Expectations Of Other Modules

- Modules consume core types without mutating frozen values or extending enums
  locally.
- Workflows pass typed outputs between modules and own coordination.
- Dispatcher alone enforces transitions and custody; it remains domain-blind.
- Recorder is the only main-ledger writer and receives complete evidence units.
- Interfaces render reason codes but never branch on free-form detail text.
- Every long loop calls the single checkpoint at documented safe boundaries.

## Provisioning For Latent Features

Declare expensive-to-retrofit shapes now: `DEFERRED`, schema-versioned events,
all `Scope` kinds, nullable file identity/hardlink group, policy protocols,
opaque workflow payloads, and attestation provenance. A latent protocol is
declared shape-only and has no implementation until its first consumer; this
provisions the seam without speculative runtime behavior.

## PoC Hardening

- Central path normalization prevents the PoC `casefold()` identity merge.
- Runtime guards raise typed exceptions rather than `assert`, which disappeared
  under `python -O`.
- One clock prevents cross-database host/timestamp drift and lexical retention
  ordering errors.
- One event/result vocabulary prevents verifier, history, CLI, and GUI from
  disagreeing about partial failure, refusal, and integrity state.
- Exact artifact recognition prevents generic `.db` and `.synctmp-` matches
  from excluding or deleting user data.

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
- A slow-subscriber stress test proves bounded history backpressure, ejects an
  overrun non-history reliable subscriber with `Gap`, and never silently loses
  a reliable event.
- Unicode corpus tests preserve NTFS-distinct paths and normalize separator and
  ordinary case variants identically.
- Path tests reject drive, UNC, device, traversal, NUL, mixed-separator escape,
  and reparse-root escape cases while accepting valid long relative paths.
- UTC/DST boundary tests prove all core timestamps are aware UTC values.
- Attestations cannot be constructed without algorithm, digest, provenance,
  subject stat evidence, and observation time.
- A changed selection invalidates a `Commitment` even when the plan fingerprint
  is unchanged; uncommitted and mismatched execution sets are unexecutable.
- `RecordingStatus` can degrade without rewriting a successful filesystem
  terminal; the unresolved history-status representation is covered before the
  public result schema freezes.
- Cancel/pause fault injection preserves earned item results and continuation
  state through the runner; exception surfacing cannot trigger a second terminal.
- Import-linter proves `namisync.core` imports no project layer.
