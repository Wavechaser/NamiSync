# NamiSync Session Handoff

Date: 2026-07-18

## Session Outcome

Sanity-checked the DR-32–DR-37 revisions in `FEATURES.md`,
`ARCHITECTURE.md`, and `DESIGN_REVIEW.md`, then propagated the settled contracts
through the focused module documents.

The propagation intentionally simplified ADS provisioning:

- scanner remains role-free and never enumerates streams;
- `MetadataSnapshot`, inventory, and database schemas contain no stream state;
- plans contain no stream manifest and M0 has no ADS-enabled mapping or ADS
  acceptance matrix;
- the dormant `supports_ads` / unexposed `preserve_ads` seam remains, with the
  future behavior documented once as executor-time enumeration.

Other propagated changes:

- `CORE.md`, `DISPATCHER.md`, `HISTORY.md`, and `WORKFLOWS.md` now specify the
  bounded preterminal audit-finalization handshake instead of leaving a
  Terminal/history causality review note.
- `CORE.md`, `EXECUTOR.md`, and `VERIFIER.md` now require cancel-unwind emission
  for in-flight and unreached selected items, while pause emits nothing for
  pending work.
- `EXECUTOR.md` now names the conditional Windows primitives used where
  available and explicitly bounds the remaining update race by its data
  consequence, without pretending a preceding path stat is compare-and-swap.

## Remaining Review Notes

All six notes below were resolved on 2026-07-18: DR-34 carries a correction
record (consequence-bounded wording, `ReplaceFileW` acknowledged as the
supported single-call alternative and a deliberate non-choice, external-writer
boundary applied to all mutations with per-family consequence classes), DR-32's
amendment gains the mtime-evasion caveat and the keep-the-latent-fields
decision (note 5: kept, per the declared-but-unreached pattern), and the
`FEATURES.md` audit bullet now leads with the delivered-or-DEGRADED contract
(note 6). The original statements are retained for context:

1. Calling the update race a “microsecond” window is too strong. It is normally
   short, but the interval between syscalls is not scheduler-bounded. Tests
   should assert the possible data outcome, not elapsed time.
2. Calling the current sequence the absolute “platform floor” is also too
   strong. Microsoft documents `ReplaceFileW` with an optional backup as the
   supported single-file alternative to deprecated TxF. It is not a drop-in for
   NamiSync because it merges target attributes, ACLs, and named streams into
   the replacement and documents partial-state error cases. The current
   hardlink/copy-backup plus replace design remains reasonable, but it is a
   chosen tradeoff rather than the only Windows primitive.
3. The listed conditional primitives do not close every non-update path swap.
   Non-replacing rename protects destination absence, not the identity of the
   source pathname; `RemoveDirectory` protects emptiness, not directory
   identity. Either specify handle-bound source mutation where that guarantee
   is required, or apply the external-writer boundary to all mutations and test
   only the exact condition each primitive enforces. The latter is simpler for
   M0.
4. Executor-time ADS enumeration preserves streams only for files already
   scheduled for copy/update. ADS-only drift is discovered through the stated
   mtime assumption; a writer that restores/suppresses mtime can evade it. That
   is a future limitation, not an M0 blocker, but the feature should not claim
   independent ADS convergence without another change signal.
5. `supports_ads` and `preserve_ads` are dead M0 fields. Because ADS has no
   schema representation and event/plan formats are versioned, adding them when
   the first implementation exists may be simpler than carrying unreachable
   states now. Keep them only if freezing this seam is worth that cost.
6. The `FEATURES.md` audit bullet still says the history subscriber “is never
   dropped” before qualifying timeout/failure degradation. The event contract
   is clearer: delivery is guaranteed within the timeout, or the result says
   `audit=DEGRADED`; nothing is silently lost while claiming `OK`.

## Verification

- Documentation-only source change; no project runtime tests were run.
- A local ADS probe confirmed that an ordinary named-stream write advanced the
  file mtime on this workspace volume. This supports the normal-case assumption
  but does not turn it into an unbypassable change signal.
- `rg` found no active focused-document references to `StreamInfo`, scan-time
  stream manifests, ADS scan depth, or unresolved terminal-finalization notes.
- `git diff --check` passes, and the probe artifact was removed.

## Next Work

The six review notes are resolved in the authoritative docs and the decision
log. Next: propagate the corrected DR-32/DR-34 wording into the affected
module drafts (`EXECUTOR.md` in particular), then freeze the M0 core shapes
and import-law tests. ADS implementation remains deferred.
