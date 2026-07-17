# History Module

Status: draft contract. Priority: minimal sync history in M0; integrity detail
and retention in M1; task grouping, replay, discard audit, and export later.
DR-16 must finalize whether history is guaranteed audit or best-effort telemetry.

## Purpose

History observes session events and writes an independent append-oriented local
SQLite database. It records what NamiSync attempted and reported without
participating in filesystem or ledger transactions. No history failure may roll
back real file work or ledger truth.

## Observer Contract

The history observer attaches at session admission as a reliable subscriber. It
creates an activity envelope using session/run token, activity kind, actual UTC
start, host provenance, subject or source/target context, and schema version. It
consumes ordered phase/item events and finalizes exactly once from terminal.

Every explicit attempt is recordable: success, partial failure, all-noop,
blocked, capacity/preflight refusal, cancellation, unexpected exception,
baseline, verify, import, maintenance, and later queued discard. Early returns
must not bypass the envelope.

Run-token uniqueness makes repeated delivery idempotent. Sequence gaps,
duplicate terminal, or payload-version failure are recorded/surfaced as observer
integrity errors, not silently ignored.

## Activity Detail

- Sync: immutable reviewed plan/run context, ordered operation id/kind/path,
  outcome/reason, content bytes, and summary counts.
- Integrity: selected scope, typed per-file integrity issues/outcomes, counts,
  and evidence provenance.
- Hash import: imported/known/conflict/invalid/stale outcomes.
- Subject-only activities render one location/subject, never `None → None`.
- No-op/refused/canceled attempts retain an envelope and truthful zero-work
  detail where applicable.

M0 stores sync envelopes, summaries, and ordered operations sufficient for CLI
history. M1 adds integrity/import detail and retention.

## Failure Semantics

DR-16 must choose the guarantee. Until resolved, implementation must at least
surface observer/database failure in session diagnostics and system health,
while preserving filesystem and ledger results. If audit is mandatory, reliable
events need durable spill/retry consistent with DR-09; an in-memory subscriber
cannot claim guaranteed audit across process death.

An unexpected workflow error still emits/finalizes a failed attempt through the
generic session wrapper. History code catches its own SQLite/serialization
errors and does not replace the domain result.

## Retention

Retention can prune old detail by age/count while preserving envelope and
summary. Timestamps are canonical UTC and compared semantically. Settings are
history-specific and use a writable connection. Pruning is transactional,
idempotent, and never runs through a read-only helper.

History replay remains available only while required detail exists. Replay
constructs a `Scope.from_run` and plans fresh; history rows are never direct
execution instructions.

## Task And Export Provision

Future GUI task ids are optional parents; CLI/service sessions remain valid
without one. Task annotations are trimmed plain text up to 256 characters and
do not alter results. Restoring setup restores inputs/options only and forces a
new plan. Export to CSV/JSON is read-only, stable-schema/versioned, and escapes
spreadsheet formula injection where relevant.

## Expectations

- Dispatcher attaches observer before reliable events begin and supplies gap-free
  envelopes.
- Generic session runner guarantees actual start and exactly one terminal.
- Modules emit typed item outcomes; history does not parse UI strings.
- Ledger has no foreign key/reference dependency on history.
- Interfaces render by activity kind and disclose unavailable/pruned detail.
- One shared clock/host formatter is used across databases.

## PoC Hardening

- Actual run timestamps replace post-hoc identical start/end values.
- All-noop, blocked, capacity-refused, canceled, guard-refused, and unexpected
  exceptions retain history.
- Integrity detail repository reads match writes.
- Writable retention and canonical timestamps make pruning effective.
- Subject-only rendering fixes `None → None`.
- Partial failure summaries derive from item outcomes, not mutating-op count.
- Database override plumbing keeps tests/CLI out of real user history.

## Acceptance Criteria

- Every terminal path listed above produces exactly one idempotent envelope with
  actual start/end ordering and activity kind.
- Duplicate event/run delivery does not duplicate envelopes or detail; conflicting
  duplicate payload is diagnosed.
- Reliable item order and sequence round-trip; an injected gap is detected and
  surfaced.
- Sync, integrity, import, maintenance, and subject-only renderers return their
  typed detail and never invent source/target roles.
- All-noop and zero-mutation refusal remain browseable.
- Unexpected SQLite/OS/domain exceptions still attempt truthful failed history
  without changing the original result.
- Observer failure follows finalized DR-16 behavior and never rolls back ledger
  or filesystem work.
- Retention on a writable connection prunes eligible detail, preserves envelope
  and summary, handles timezone/precision boundaries, and is idempotent.
- Replay is unavailable with an explicit reason after detail pruning and always
  plans fresh when available.
- CLI database overrides isolate history; concurrent readonly browsing works
  during active writes under WAL.
- Export escapes formula-leading cells and preserves typed/schema-versioned
  values.
