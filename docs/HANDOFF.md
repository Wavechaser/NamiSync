# NamiSync Session Handoff

Date: 2026-08-11
Branch: `milestone1`

## Session Outcome

The checkpoint 1-15 maintenance refactor remains complete at `2b38407`, and
the immediate post-refactor review is also complete. Four reported findings
were reproduced and fixed: generic collaborator exceptions can no longer leave
active executor effects or pending MKDIRs without terminal truth; executor root
guards bind the operational root to the reviewed authority; the retained
settlement oracle now covers the previously selective observer states; and
verifier native subclasses/decorators use an explicit authority-bound protocol
instead of exact concrete-type dispatch.

No public executor or verifier facade signature, persisted payload, evidence or
database schema, operation ordering, successful-path filesystem sequence, or
process-fatal `BaseException` contract changed. The ordinary-`Exception`
behavior is intentionally stronger: before the collaborator exception is
re-raised, active effects settle from the original operation error, pending
directories finalize, and already-statused journal entries retire without
replaying filesystem or recorder effects.

## Commit Record

- `2b38407` closed maintenance-refactor checkpoints 1-15. Its detailed
  checkpoint ancestry remains in Git history and the focused architecture
  documents.
- `8a3d64e` replaced verifier exact-type routing with the core
  `AuthorityBoundVerificationReader` protocol, kept selected-root/opened-volume
  policy in engine, made the tools timing tap capability-transparent, and
  shared the pure verifier/sidecar expected-stat predicate.
- `824055f` added the executor generic-exception settlement/finalization
  backstop and made source/target root guards fail closed on a supplied root
  that differs from reviewed authority.
- `5abf08a` expanded the independent settlement oracle from 58 to 70 exact rows
  and added direct observer/reducer coverage. It did not edit the baseline or
  reviewed semantic pin.
- `0c4d9a9` atomically replaced the independently reviewed baseline and its
  semantic pin after all 58 prior rows were proven type-strict identical and
  exactly 12 authorized rows were added.
- `767c5e8` reconciled README and this handoff after the review; `dd5677b`
  clarified the original-58/post-refactor-12 baseline lineage across the
  active architecture, executor, and tools documents. The documentation-only
  commit archiving and indexing the completed maintenance plan contains this
  updated handoff, so this file does not name that commit.

## Corrected Baseline Provenance

- Corrected monolithic executor source: `d99743a`.
- Original retained oracle: `07f08fe`; hardening through `51eacf7`; timestamp
  normalization at `2b8b996`.
- Previous reviewed baseline: `50d676b` (30 scenarios / 58 rows).
- Current reviewed baseline commit: `0c4d9a9`.
- Baseline file: `tools/executor_settlement_baseline.json`.
- Oracle schema: `format_version: 1`; exact top-level fields remain
  `format_version`, `repeat`, `manifest`, and `scenarios`.
- Current coverage: 30 scenario IDs and 70 globally unique exact policy rows,
  captured in three complete byte-identical runs.
- Current baseline Git blob: `97ebd0a37264dd52989f23ccd36358fbe67886e0`.
- Current canonical-JSON semantic pin:
  `df69bf65979c3838e3df9bcc262cd9961945e6a8603c348c22f8136f4d6547b2`.

The exact resume gate is:

```powershell
python -m tools.executor_settlement_audit check --repeat 3
```

Its successful final line is:

```text
settlement check passed: 30 scenarios x 3 runs
```

Checkpoint 8 did not edit the baseline; neither did checkpoints 9-15. That
immutability rule remains: a structural executor split, journal/reducer change,
verifier split, or stabilization refactor must not regenerate the snapshot to
make itself pass. The replacement at `0c4d9a9` is deliberately separate because
it follows isolated behavior fixes, persistent regressions, independent exact
expectations, a three-run oracle, and row-by-row adversarial review. A future
replacement requires the same sequence and a separately reviewed baseline/pin
commit.

## Final Verification

- Complete suite: `1568 passed, 2 skipped`.
- Executor runtime + settlement suites: `210 passed` before the oracle
  expansion; final settlement suite: `124 passed`.
- Verifier/core/tool/workflow focused gate: `149 passed`.
- Oracle/tool focused gate after expansion: `202 passed` across settlement and
  audit tests; audit-only baseline safety gate: `78 passed`.
- Retained oracle: `30 scenarios x 3 runs`, first as independent exact-policy
  capture, then as an unpinned candidate check, and finally through the official
  committed baseline/pin gate.
- Import linter: `11 kept, 0 broken` across 56 files and 219 dependencies.
- `python -m compileall -q namisync tests tools` and `git diff --check` passed.
- Independent reviews found no remaining executor, verifier, oracle, or
  baseline blocker. The candidate review proved all 58 old rows unchanged,
  exactly 12 additions, stable scenario metadata, and no raw path, identity,
  timestamp, object-repr, or non-finite leakage.

## Immediate Next-Session Context

1. Start with the exact three-run oracle command above. Keep the oracle and
   reviewed baseline as retained infrastructure through the immediate
   post-refactor stabilization period and later executor/verifier work.
2. The four findings from this review are closed. Whole-publication UNVERIFIED,
   changed-after-publish, and some unreadable mutation paths already had unit
   coverage; the new rows deliberately fill the restored, missing, unreadable,
   and collaborator-exit gaps rather than duplicating every existing case.
3. Process-fatal `BaseException` remains cleanup-only and nonterminal. Generic
   `Exception` is the terminal-effect backstop boundary. Do not broaden one into
   the other without a separate policy decision and oracle row.
4. Unbound verifier readers remain an explicit fake/custom seam. Any reader or
   decorator that implements `AuthorityBoundVerificationReader` must be given
   `VerifierContext.root_authority`; its bound open derives the root only from
   that authority.
5. No maintenance checkpoint or structural split remains open. Resume product
   work from the active Stage 6 documents unless new evidence identifies a
   concrete stabilized-boundary failure.
   `obsolete/M1_MAINTENANCE_REFACTOR.md` is the retained completed delivery
   record, linked from `M1_PLAN.md`; its historical checkpoint wording does
   not reopen maintenance work.
