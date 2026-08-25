# Session Handoff

Status (2026-08-25): Stage 6 second-half checkpoint 3.2 is complete at the
second safe stop in `M1_SHELL_H2.md`. Production emits, persists, and consumes
only exact core event v5 at ledger v4/history v6/data epoch 5. Checkpoint 3.3
has not started.

## Delivered

- Published exact event v5 across core reporters, dispatcher/service views,
  history, CLI, and packaged JavaScript. Reliable envelopes are validated at a
  1,048,576-byte canonical ceiling before sequence, replay, queue, or history
  mutation; terminal transport carries a bounded item-free summary.
- Activated closed operation/integrity item variants, independent recording and
  audit axes, ordered task recording issues, bounded diagnostics with omission
  witnesses, exact review-limit facts, and strict Python/JavaScript scalar and
  cross-field validation.
- Moved byte and filesystem-nanosecond quantities into checked nonnegative
  signed-64 arithmetic internally and canonical decimal text at public wire
  boundaries. Planner aggregate overflow becomes the exact plan/domain
  `logical-bytes` refusal; path-local scanner scalar failures remain warnings.
- Widened `FileIdentity` to the complete unsigned 128-bit Windows file-index
  domain. Scanner, preflight, executor, verifier, and database-pair custody use
  the core adapters; ledger and every JSON persistence codec store canonical
  text. The verifier-rig sidecar is now `namisync-rig-baseline-2`; version 1 is
  refused and must be deliberately reseeded.
- Reset the pair contract to ledger v4/history v6/data epoch 5 with exact
  contract ids. Old, mixed, one-present, markerless, incomplete, and orphan-
  sidecar pairs refuse without mutation and give coordinated archive/delete
  guidance for both mains and all SQLite sidecars.
- Preserved CLI itemized output when observation begins after a fast terminal
  by reading canonical items through the finalized fixed history watermark.
  Audit-degraded results retain their explicit live-only fallback.
- Adapted only the retained settlement oracle's normalization layer to project
  event-v5 item fields into its historical trace shape. The committed baseline,
  protected row/scenario manifest, and semantic policy remained unchanged.
- Reconciled active component, architecture, defense, feature, shell, bridge,
  test, tool, README, and changelog wording. The user-revised
  `docs/M1_SHELL_H2.md` was reread from checkpoint 2 onward and was not edited.

## Safe Stop

`namisync/core/events.py` still contains the private
`_LEGACY_CORE_EVENT_SCHEMA_VERSIONS`, `_LegacyEnvelope`, and
`_legacy_envelope_from_dict` read-only source seam. No public constant,
producer, dispatcher, persistence reader, service route, CLI path, browser
route, or positive runtime fixture can select it. This is the exact checkpoint-
3.2 safe stop; deleting that seam belongs only to checkpoint 3.3.

The working tree is expected to be clean after the named checkpoint-3.2 commit.
No generated artifacts or settlement-baseline changes belong to this delivery.

## Verification

- Final ordinary suite with the required bundled-Node validator/reducer:
  `3153 passed, 4 skipped, 28 deselected`.
- Affected core, executor, verifier, database, workflows, dispatcher, and
  interfaces departments: `2665 passed, 1 skipped, 513 deselected` before the
  later tool-only sidecar correction; the final ordinary suite supersedes it.
- Focused protocol/product neighborhoods included `447 passed`, `173 passed`,
  `51 passed` for full-width native identity with the Windows witness executed,
  and `199 passed` for CLI/workflow/history reconstruction.
- Settlement-oracle tests: `91 passed`; required stability gate:
  `30 scenarios x 3 runs`, identical and clean. The committed baseline is
  byte-for-byte unchanged.
- Verifier-sidecar regression: `38 passed`; tools department after the review
  fix: `301 passed, 3 skipped, 2881 deselected`.
- Import architecture: `11 kept, 0 broken`.
- Final source scans found no legacy `nFileIndexHigh/Low`, old basic handle-
  identity call, numeric SQLite file-index column, numeric JSON file-index
  codec, stale active-v4 documentation, or reachable legacy event route.
- `git diff --check` and staged-snapshot inspection are the final pre-commit
  gates.

## Immediate Next Context

Stop here before checkpoint 3.3. On resumption, first inventory the clean tree
and reread revised `M1_SHELL_H2.md` checkpoint 3. Remove only the unreachable
private v3/v4 decoder branch and its source-only compatibility evidence, prove
that production behavior remains exact v5 and no positive v3/v4 source/fixture
remains, then run the ordinary suite and settlement oracle three times. Commit
that closure as `refactor(protocol): remove legacy event compatibility`.
