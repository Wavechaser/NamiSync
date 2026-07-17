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
- Immutable scan, plan, observation, attestation, item-result, and run-result
  dataclasses; `ExecutionSet` is the explicit mutable execution-status carrier.
- `SessionState`, its legal transition table, and terminal-state predicate.
- `Outcome` and typed reason codes; free-form text is presentation detail, not
  control flow.
- Versioned event envelopes and typed event bodies.
- `RunContext` and cooperative pause/cancel checkpoint protocol.
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

Pause semantics must be resolved in [DESIGN_REVIEW.md](DESIGN_REVIEW.md)
(DR-02) before implementation. Core must not ship a checkpoint contract that allows a
workflow stack to remain blocked while the dispatcher claims volume locks have
been released.

Terminal emission ownership must likewise be singular. The recommended core
shape is a generic session-runner result from which the dispatcher emits one
`Terminal`; modules return results and never emit a terminal themselves. See
DR-03.

## Event Contract

Every envelope contains a session id, gap-free per-session sequence, injected
UTC timestamp, and schema version. State, phase, item, and terminal events are
reliable; progress is a replaceable snapshot. Event details must be typed or
schema-versioned—consumers must not infer semantics by parsing user-facing
strings.

Reliable delivery policy remains open under DR-09. The type system must expose
delivery class and detectable gaps without promising an impossible combination
of bounded memory, zero producer blocking, and zero reliable-event loss.

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

Volume identity matching must separate stable key material from mutable label
evidence as required by DR-10. File identity is nullable and never fabricated
on filesystems that cannot supply stable identity.

## Time And Evidence

All domain timestamps come from one injected `Clock`, are timezone-aware UTC,
and are normalized once before persistence or event emission. Presentation
converts to local time.

An attestation joins a SHA-256 digest to the exact stat snapshot it attests and
its provenance. DR-07 must resolve source-stream versus published-target
identity before the final type freezes. No consumer may treat copy-stream
evidence as readback verification.

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
opaque workflow payloads, and attestation provenance. A latent protocol need
not have an M0 implementation unless an M0 consumer uses it; this corrects the
ambiguity in DR-20 without adding speculative runtime behavior.

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
  interruption—can produce exactly one terminal from the agreed owner.
- Concurrent event emission yields gap-free monotonically increasing sequence
  numbers per session and no sequence sharing across sessions.
- Event serialization round-trips every body and rejects unsupported schema
  versions explicitly.
- A slow-subscriber stress test proves the selected DR-09 delivery policy and
  reports detectable loss/failure rather than silently violating it.
- Unicode corpus tests preserve NTFS-distinct paths and normalize separator and
  ordinary case variants identically.
- Path tests reject drive, UNC, device, traversal, NUL, mixed-separator escape,
  and reparse-root escape cases while accepting valid long relative paths.
- UTC/DST boundary tests prove all core timestamps are aware UTC values.
- Attestations cannot be constructed without algorithm, digest, provenance,
  subject stat evidence, and observation time.
- Import-linter proves `namisync.core` imports no project layer.
