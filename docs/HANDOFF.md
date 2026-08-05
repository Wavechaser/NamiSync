# NamiSync Session Handoff

Date: 2026-08-04
Branch: `milestone1`

## Session Outcome

Completed the remaining simplifications from the review that produced the
minimal post-publication retry guard in `4655317`.

- COPY, UPDATE, and MOVE_UPDATE now share one published-operation completion
  helper. It owns the resumed-target guard, target metadata/stat, size guard,
  operation-safe attestation/filesystem ordering, directory durability,
  recording, and `PublishedCopyEvidence` construction. MOVE_UPDATE attests
  before its destructive old-to-trash finish; COPY/UPDATE attest after their
  completion/durability work.
- UPDATE now has explicit backup creation and repaired-version evidence for
  hardlink and copy backups. Copied-backup metadata must finish before target
  replacement; hardlink metadata finishes after replacement. Retry preserves
  the pre-backup live-target stat, accounts only for NamiSync's hardlink-count
  increment, and rejects an external swap instead of rebinding to it.
- Cancellation validates retained backup evidence, reports
  `retained|changed|absent|unverified`, uses target-root-relative backup/trash
  paths, and no longer implies that a cleaned temp remains durable. Running
  execute cancellation returns a typed result in both verification modes with
  complete plan-ordered items and the executor's recording axis intact.
- Serialized database contention spends one monotonic budget across the local
  writer lock, SQLite busy waits, and retry sleep. Audit-pump close likewise
  spends one deadline across stop enqueue and thread join.
- History sequence admission retains one highest-sequence scalar instead of
  rescanning the event hash map for every envelope.
- WebView2 availability and refusal diagnosis now come from one typed,
  read-only probe snapshot. Missing .NET/WebView2 and malformed or unreadable
  detection state remain distinct without a second .NET registry read.

`BUGS.md`, the focused component documents, the README changelog, and this
handoff describe the repaired behavior and remaining threat boundaries.

## Verification

- Combined focused regression suite: `287 passed in 10.65s`.
- Complete test suite: `912 passed in 29.18s`.
- Import linter: `8 kept, 0 broken`.
- Independent adversarial review caught and drove corrections for canceled-item
  completeness, copied-backup repair ordering, MOVE_UPDATE failure consequence,
  hardlink-backup repair ordering, and pre-backup live-evidence rebinding.
- `git diff --check` is clean.

## Immediate Next Context

No blocker remains in the requested simplification scope. The concurrent-drift
contract is still evidence-based rather than adversarial exclusion: an
identity-weak same-kind/same-size substitution before repaired evidence is
cached, or a path swap after the final guard, remains outside the claim.

Two pre-existing audit lifecycle seams were observed but deliberately not
changed here: a queued finalization that reaches an already-degraded pump exits
without calling the observer's `close()`, and an observer-close failure shares
the same degraded result path as durable-finalization failure. The current
history observer's close is only an in-memory state transition, but those
protocol semantics should be decided before a resource-owning observer is added.
