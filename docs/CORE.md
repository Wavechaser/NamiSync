# Core Module

Status: M0 scan/plan/preflight, session/event/evidence, execution, integrity,
and recording contracts are implemented. M1 Stages 2-4 add the fixed XXH3-128
content contract, nominal heterogeneous result vocabulary,
published-copy/post-copy evidence, compound phase results, and the continuation
state consumed by standalone and linked integrity workflows. Current hardening
advances the core event codec to v4.
Stage 5.5 promotes the planner's relative-path hierarchy helpers here for the
shared workflow tree substrate without changing their semantics, and makes
recursive inventory scope an explicit core contract.

## Purpose

`namisync.core` defines the vocabulary and invariants shared by the system. It
contains no scanner, planner, executor, database, dispatcher, workflow, or UI
policy. It imports only the Python standard library; direct filesystem access
is limited to shared root-authority mechanics, and core owns no SQLite, clock,
or presentation collaborator.

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
- `MANAGED_FILE_ATTRIBUTE_MASK`, the shared readonly/hidden/system/
  not-content-indexed policy used by planner equality and executor mutation;
  `MetadataSnapshot.attributes` still retains the complete observed bitmap.
- `SessionState`, its legal transition table, and terminal-state predicate.
- Six-value `Outcome` (`succeeded`, `skipped`, `failed`, `canceled`, `deferred`,
  `blocked`) and typed reason codes; free-form text is presentation detail, not
  control flow.
- Versioned event envelopes and typed event bodies, including `Gap` and the M1
  `IntegrityOutcome`/eight-value `IntegrityResult` vocabulary.
- `RunContext`, nonblocking cooperative pause/cancel checkpoint protocol, and
  the generic session runner that alone resolves pause/cancel and emits
  `Terminal`.
- Protocols for recorder, clock, failure policy, copy backend, streaming hasher
  factory, change source, destination policy, metadata extraction, session
  storage, and filesystem observations needed by module contracts.
- Windows relative-path normalization, validation, hierarchy, containment, and
  long-path conversion helpers.
- Ephemeral `RootAuthority` facts plus stateless native anchor, volume, and
  no-follow component probes; every admission uses fresh evidence and typed
  failures rather than cached or persisted authorization.
- Pure shared calculations such as capacity requirements and deterministic
  operation identifiers when those rules cross module boundaries.

The M0 scan/plan/preflight portion is implemented in `core/pathing.py`,
`core/root_authority.py`, `core/models.py`, `core/planning.py`, and
`core/preflight.py`. These files own canonical Windows relative paths,
immutable filesystem evidence, shared native root-admission mechanics,
deterministic plan serialization and capacity, and root-qualified
observation/refusal shapes. General filesystem walking and domain observation
remain in operation modules; core's stateless probes carry no module policy and
remain standard-library-only. `core/pathing.py` stays purely lexical and does
not re-export native anchor or volume probes from `core/root_authority.py`.

`ScanScope` has exactly three canonical shapes. `FULL` carries neither exact
paths nor subtree roots; `PATHS` carries only exact paths; and `SUBTREES`
carries one or more minimal subtree roots plus any exact paths outside those
roots. Scope factories normalize and deduplicate relative Windows keys,
remove descendant roots by path-segment ancestry, remove exact paths already
covered by a root, and promote root `""` to `FULL`. Direct construction
enforces the same shape invariants, so scanner and recorder branches cannot
silently reinterpret malformed scope. Root minimization and exact-path coverage
walk canonical parent keys rather than comparing every declared path with every
root, so normalization work scales with total path depth.

`SyncOptions.propagate_source_casing` is a fingerprinted planning policy. It
defaults to false, is available through the primitive semantic-settings
facade, and survives workflow payload round trips without changing the plan
shape; M1 has no dedicated settings CLI or GUI control.
`OperationReason.CASE_MISMATCH` and
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
Every successful selected COPY/UPDATE/MOVE_UPDATE has exactly one
`PublishedCopyEvidence`: its copy-stream attestation plus either a complete
`RecordedCopyIdentity` returned by the same ledger transaction or no identity
with frozen `recording=DEGRADED`. Recorded scope/path/location values are
validated against the execution run and reviewed target; partial or invented
identity is unrepresentable.

`core/integrity.py` owns `PostCopyCandidate` and its mutable
`PostCopySelection`. Candidates copy verifier-facing values from published
evidence without embedding the execution type or requiring a ledger row.
Completion ids and processed bytes are validated continuation state.

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
raises `Canceled`. Modules normally let either exception unwind to the generic
runner. Executor alone may catch `PauseRequested` at a durable retry-backoff
checkpoint, latch it until the current operation settles, and then re-raise at
the operation boundary; `Canceled` is never latched. A pause transitions to
`PAUSED` without a terminal and releases volume custody. Resume re-enters
admission at the back of the required volumes' queue and performs fresh
observation/preflight. Cancellation produces the one `CANCELED` terminal.

The generic runner in `core/session.py` is the sole `Terminal` producer for
every workflow. Modules and workflows return typed results and emit only
nonterminal bodies. The dispatcher wraps the runner with custody acquisition
and unconditional release; it does not add a second terminal path.

Pause is a generic per-workflow-registration capability. Execution supports it
from M0 through mutable `ExecutionSet.status`; its continuation also retains a
validated aggregate byte high-water so one resumed task cannot report progress
regression. Verify and baseline add an item-status and physical-read
continuation in M1. Scan and plan refuse pause cleanly
and remain cancelable. A pause unwinds, forces recorder flush where applicable,
persists the workflow-owned continuation, releases custody, and emits no
terminal.

`Canceled` and `PauseRequested` remain payload-free. The runner consumes them
and aggregates RELIABLE item outcomes only after the downstream emitter returns
successfully; a rejected outcome never becomes terminal-result authority.
Only successfully emitted Progress can seed the runner's generic cancel/failure
fallback. Ordinary unexpected `Exception` values are likewise consumed after
typed detail is attached to the one terminal/log path. `KeyboardInterrupt`,
`SystemExit`,
and other `BaseException` subclasses deliberately escape without being
normalized into a workflow result. Operation modules emit outcomes as work settles rather than holding a
private result list until return. Before `Canceled` leaves an item-processing
module, its unwind finalizer emits an outcome derived from any durable in-flight
state and `CANCELED` for every unreached selected item. The same finalizer emits
nothing for unreached work on `PauseRequested`, because that work remains
pending for resume.

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
the timeout guarantees delivery. The observer returns `RecordingStatus` from
event admission and finalization: a contained status degradation keeps the
prefix accepting, while an exception, writer failure, or timeout breaks the
prefix and degrades the session's audit axis loudly. Other reliable subscribers
that overrun their bounded queue are ejected; the first thing they observe is a
typed `Gap(first_missed_seq)`. Late subscribers receive current state plus a
bounded tail and use sequence numbers to detect omitted history. Progress alone
is lossy/coalescible.

Terminal finalization is a two-phase handshake. The runner first drains the
audit subscriber and asks it to finalize the run from the preterminal event
stream and provisional result. One atomic latch decides ownership at the
production cutoff: a caller win makes both the Terminal and any late row
degraded, while a pump win makes the caller wait for the actual commit result.
The runner then constructs and releases the one immutable `Terminal` to
ordinary subscribers. History never needs to consume or parse that Terminal,
so no corrective second terminal or circular acknowledgement exists.

The current event codec emits core event-envelope v4 and round-trips
`StateChanged`, `PhaseChanged`, `Progress`, nominal `ItemOutcome` and
`IntegrityOutcome` values, `Gap`, and `Terminal`. It also retains explicit v3
decode support for persisted reliable history without rewriting its hash
chain. Unknown schema/body versions and v3 Progress are rejected: history
never admitted lossy Progress, so there is no persisted legacy Progress shape
to recover. Reliable `PhaseChanged.phase` is an exact nonempty string, matching
the phase authority required by Progress consumers rather than allowing an
empty phase token below the browser boundary.

### Progress v4 shape

Version 4 makes every Progress body an exact eleven-key object:

```text
phase
items_done
items_total
bytes_done
bytes_total
current_path
item_id
item_type
item_attempt_id
item_bytes_done
item_bytes_total
```

`phase` is a nonempty string. `items_done` and `bytes_done` are exact
non-boolean, nonnegative integers. Each total is either an exact non-boolean,
nonnegative integer or `None`; every done value is bounded by its known total.
Every Progress integer is also bounded by JavaScript's maximum safe integer so
core cannot emit a snapshot that the exact browser boundary must refuse.
`current_path` is a string or `None`. Item id and type are both present or both
`None`; the id is a nonempty string and the type is exactly `operation` or
`integrity`. An active item requires `items_done < items_total` when the item
total is known.

`item_attempt_id` is either `None` or exactly 32 lowercase hexadecimal
characters. It requires paired item identity. Item-byte counters require an
attempt id, are both present or both absent, use exact non-boolean nonnegative
integers, and are mutually bounded when present. `item_bytes_done` cannot
exceed aggregate `bytes_done`, and `item_bytes_total` cannot exceed known
aggregate `bytes_total`. An attempt id with an absent byte pair is the only
active indeterminate-byte shape; an item without an attempt has no item-byte
counters. Extra or missing keys are rejected.

Attempt ids are minted at actual byte-pipeline entry and identify only that
attempt. Retry or reconstructed resume mints a new token exactly when it will
rerun the byte pipeline; retained post-byte work does not invent a replacement
attempt. Overshoot retains item and attempt identity while making the byte pair
absent. Settlement clears item, attempt, and item-byte fields. The tokens are
opaque and deliberately are not persisted generation counters.

The scalar decoder remains non-coercive: schema, sequence, and counter fields
require exact integers, booleans cannot impersonate numbers, and string fields
remain strings. `item_type` names the row-lookup namespace of the opaque id,
not the phase or module producing the event; post-copy verifier progress keyed
by an executor operation id therefore uses `operation`, even though its
reliable outcome remains an `IntegrityOutcome`. The central meanings,
transition table, authority order, and Gap/replay rules live in
`ARCHITECTURE.md` §2.3 rather than being redefined by module documents.

Core event versioning is independent of every containing or adjacent schema.
The exact browser-facing `SessionEventView` has `session_id`, `sequence`, `at`,
`schema_version`, `body_type`, and `body`; its nested `schema_version` carries
the originating envelope's core event version unchanged. The desktop bridge
command/response schema stays v1 and workflow continuation stays v5. History
database, UI state, shell, and page schema versions do not change. An
unversioned browser-facing event is not a supported compatibility boundary.

Every reliable result item carries an explicit `item_type` and `phase`;
`run_session` accumulates only the nominal `ResultItem` base after successful
downstream emission, in that emission order, including prior items retained
across pause/resume. A reliable item's degraded recording axis is a one-way
floor for the aggregate terminal recording result; a later workflow return or
paused-cancel callback cannot relabel it `OK`. Structural
`hasattr(item_id/path)` guessing is forbidden.

## Path And Identity Rules

Persisted paths are root-relative with `\` as the canonical separator. Reject
empty components where Windows would reinterpret them, absolute paths, drive or
UNC qualification, `.`/`..`, alternate root syntax, embedded NUL, and any path
with an ambiguous suffix, stream/device qualifier, or unpaired surrogate, plus
any path whose resolved handle escapes its root through a reparse point.

Lexical validation and handle-based containment are separate checks: lexical
validation is pure and always available; filesystem containment belongs in
observation/preflight. Long-path conversion happens only after validation.

Absolute managed roots have two spellings with one identity contract.
`Root.path`, plans, continuations, evidence, history, and interface views carry
lexically normalized ordinary drive/UNC paths without `\\?\`; this normalization
does not follow a final junction or symlink. Native backends add the
extended-length prefix only to the operand passed to Windows I/O, no-follow
validate every lexical-root component below a trusted drive/share or reviewed
volume mount before physical resolution, and strip native spelling from
returned paths. Physical root resolution is separate observation evidence for
overlap/containment and never replaces the lexical domain identity. The inverse
conversion accepts only drive and complete UNC filesystem namespaces that
round-trip to a stable ordinary spelling. Device/NT namespaces, malformed
extended UNC anchors, trailing-dot/space or reserved DOS components, and other
ordinary-ambiguous absolute names are refused rather than normalized onto
another tree. Reserved DOS aliases include `CONIN$`, `CONOUT$`, and the
superscript-one/two/three `COM`/`LPT` forms as well as the ordinary numbered
devices. Native
`OSError` filename fields are rendered back into logical spelling before
entering warnings, durable detail, or user-facing diagnostics.

`RootAuthority` is ephemeral reviewed context: a logical root plus an optional
reviewed native anchor and `VolumeId`. `admit_root_chain()` observes the current
anchor through its supplied/native probe and no-follow checks each root
component below it without observing volume identity; it returns the admitted
anchor. `admit_root()` performs that exact chain admission once, then requires
the volume probe's own anchor evidence to match before accepting its identity.
Authority is never cached or persisted. Non-Windows probe branches are
development/test fallbacks only, not production mount-boundary authority.

`rel_path_key` follows Windows/NTFS one-codepoint case mapping, not
`str.casefold()` and not unrestricted Python `upper()` when it expands a code
point. The implementation must use a tested Windows-equivalent mapping strategy
and preserve NTFS-distinct names such as `Straße.txt` and `strasse.txt`.

Unicode normalization is deliberately not part of path identity: NFC and NFD
spellings remain distinct stored paths. Planner may identify a unique
same-parent canonical-equivalence pair for review, but no core path helper
rewrites either spelling.

Relative hierarchy uses `relative_path_depth()`, `relative_path_parent()`, and
strict `is_relative_path_descendant()`. They operate on relative Windows path
segments and remain distinct from `is_path_below()`, which checks resolved
absolute-root containment. `strip_common_relative_path_suffix()` removes equal
trailing segments under the same one-codepoint case mapping while preserving
the original spelling of both remaining prefixes; it never performs a raw
character-suffix match.

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

`StreamingHasher` and `HasherFactory` define the parameterless,
standard-library-only dependency boundary shared by both content producers.
Core never imports the concrete implementation; workflow composition supplies
the exact same `xxhash.xxh3_128` constructor to executor and verifier. Core
evidence also owns the shared construction, update, and finalization lifecycle:
it validates the structural protocol, wraps ordinary collaborator exceptions
in the existing `HasherContractError` vocabulary, lets `BaseException`
control flow escape, and validates the raw digest only after `digest()` returns.

`ContentEvidence` and `CopyDigest` accept only raw 16-byte `xxh3_128` content
digests. Mixed algorithms are invalid, hasher collaborator failures raise the
typed core `HasherContractError`, and `Attestation` requires content size to
equal its exact subject `FileStat` size. For copy and update, the subject is the
published target re-statted after publication; the source's post-read stat is
separate drift-guard evidence. No consumer may treat copy-stream evidence as
readback verification. SHA-256 remains intentionally limited to plan,
selection, custody, history, settings, and idempotency identity hashes.

`OperationResult.status` reports filesystem truth only. Ledger persistence and
history persistence are independent `recording` and `audit`
`RecordingStatus.OK|DEGRADED` axes; no axis rewrites another. Typed
`Disposition.RAN|UNRUN` distinguishes a canceled discarded queue entry and a
refusal from sessions that actually began domain work without parsing strings
or inferring from an empty result-item list. `OperationResult.bytes_done` is
the terminal attempted-work high-water for the workflow's primary byte domain,
not a durable-content counter; its matching total is that domain's final work
budget. `PhaseResult` applies the same meaning within one entered phase. A
failed pre-publication copy may therefore report bytes that existed only in an
owned temporary file before rollback. Durable publication remains owned by
reliable successful outcomes, executor publication evidence, and ledger state.
`OperationResult.items` accepts only nominal `ResultItem` instances and
preserves the one heterogeneous event order; operation and integrity consumers
use explicit tags rather than parallel domain lists. Compound results add one
`PhaseResult` per entered phase with phase-local counters that are never
summed; the top-level sync byte pair projects execute rather than execute plus
verify. Cancellation is a separate fact:
verify cancellation may retain filesystem `COMPLETED` or `FAILED`, while
`result_terminal_state()` is the sole projection to dispatcher lifecycle
`CANCELED`. These combinations require `Disposition.RAN`, matching execute
truth, and a canceled verify phase; execute cancellation cannot claim a
completed execute phase.

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
the semantic-settings `preserve_ads` flag (with no dedicated CLI/UI control)
reserve the decision, while scan records,
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
- Every success, refusal, cancellation, ordinary `Exception`, and later
  interruption path produces exactly one terminal from the core runner;
  `BaseException` escapes unnormalized, and pause produces no terminal until
  that same session resumes and terminates.
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
  ambiguous absolute components, console/superscript DOS aliases, and
  reparse-root escape cases while accepting valid long relative paths.
  Drive/UNC logical-native round trips and logical error rendering are pinned
  separately.
- Scan-scope tests prove exact-only, recursive-subtree, and full shapes are
  canonical, segment-aware, and reject malformed direct construction.
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
