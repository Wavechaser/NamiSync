# TeraCopy Hash Import Module

Status: draft contract. Priority: M1 integrity workflow.

## Purpose

Hash import reads an explicitly selected TeraCopy UTF-8 `.sha256` sidecar and
offers external SHA-256 evidence to existing present inventory rows. It never
creates files, inventories an unknown location by implication, overwrites an
established conflicting hash, or trusts a sidecar path outside the selected
root.

## Pipeline

1. Inventory or scoped-refresh the selected location.
2. Acquire the same mutating volume/database custody as other evidence writes.
3. Parse the explicitly selected sidecar with cancellation checkpoints.
4. Validate every relative path through core lexical and resolved containment
   rules; reject absolute, drive, UNC, traversal, duplicate canonical keys, NUL,
   and root escape.
5. Join by location plus `rel_path_key` to a present unchanged inventory row.
6. Classify each entry as imported, already-known match, conflict, missing,
   modified/stale, unsupported, duplicate, invalid, canceled, or error.
7. Submit only eligible unhashed rows to Recorder's conditional evidence write.
8. Emit reliable per-entry outcomes and a history envelope on every terminal
   path, including guard refusal and unexpected exception.

Scanner ignores sidecars during ordinary sync by exact configured/name grammar;
hash import can read one only because the user selected it as workflow input.

## Trust And Provenance

Imported hashes are external evidence and require their own provenance value or
annotation; they are not `VERIFY_ATTESTED` unless NamiSync reads the file. They
do not set `last_verified_at`. Existing equal hashes are known/no-op; differing
hashes are conflicts retained for review and never overwritten automatically.

The sidecar itself is untrusted input. Parsing has explicit size/line/path
limits, deterministic duplicate handling, and no implicit encoding fallback.

## Expectations

- Workflow refreshes inventory and supplies explicit database paths/clock.
- Core supplies path validation and typed import outcomes.
- Repository performs batched canonical-key lookup.
- Recorder conditionally writes only if row id, state, size, and mtime still
  match.
- Dispatcher supplies checkpoint/custody; history observes all outcomes.
- Workflow registration refuses pause for import (no continuation) while
  cooperative cancellation remains available between lines/batches.
- UI/CLI disclose scope and conflicts without offering overwrite-established.

## PoC Hardening

The shared guarded integrity envelope prevents volume-lock refusal from escaping
without history. Canonical path lookup, conditional writes, cancel checkpoints,
and paired database overrides cover the PoC's wrong-target, stale-evidence,
uncancelable-close, and real-user-history defects.

## Acceptance Criteria

- Valid UTF-8 SHA-256 entries import only into present unchanged unhashed rows.
- Absolute, drive, UNC, traversal, mixed-separator escape, duplicate canonical
  key, malformed digest, invalid UTF-8, oversized line/file, and reparse escape
  are rejected with no out-of-root read/write.
- Existing matching hash reports known and does not rewrite timestamps;
  conflicting established hash reports conflict and remains unchanged.
- File drift between lookup and recorder call affects zero rows.
- Import never sets `last_verified_at` and persists explicit external
  provenance.
- Cancellation is observed between lines/batches and closing UI never waits for
  an uncancelable import.
- A pause request is rejected without changing session state or losing
  cancelability.
- Volume-guard refusal and unexpected SQLite/OS exceptions still create a
  truthful history attempt.
- CLI database overrides isolate both ledger and history from real user data.
- Batched lookup/import handles large sidecars without one query per path or an
  unbounded transaction.
- Scanner regression proves an explicitly importable sidecar is ignored only by
  ordinary scanning's exact rule, not a broad suffix that hides user content.
