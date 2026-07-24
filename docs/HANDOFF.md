# NamiSync Session Handoff

Date: 2026-07-24

## Session Outcome

The finalized M1 decisions are now promoted from `M1_PLAN.md` and
`HASH_REFACTOR.md` into the active cross-cutting product and architecture
documents. This was a documentation-only reconciliation; no runtime behavior
changed.

The active documents now consistently specify canonical XXH3-128 content
evidence, the exact adaptive copy policy and Windows finalization work, the
in-session execute-to-verify workflow, four independent result axes, explicit
pause continuation, split settings ownership, the coordinated database reset,
retention deferral, and the dependency-ordered M1 build.

## Changes

- Updated `FEATURES.md` with canonical content evidence, exact adaptive
  pipelining, finalization/preallocation/readahead decisions, linked
  verification semantics, split settings, reset posture, and deferred copy and
  retention work.
- Updated `ARCHITECTURE.md` with the XXH3-128 and attestation contracts,
  nominal mixed results and phase summaries, hasher/copy seams, executor
  pipeline architecture, transient verification candidates, explicit compound
  continuation, facade/desktop boundaries, and the full M1 build order.
- Updated `WORKFLOWS.md` to derive post-copy candidates from execution-owned
  published evidence rather than the ledger, retain volume custody through
  readback, and preserve separate phase progress and truth axes.
- Reconciled `M1_PLAN.md` with the fixed 256 KiB / 1 MiB / 4 MiB policy and
  marked its former workflow-document blocker resolved.
- Updated `README.md` so its development overview and documentation index match
  the promoted M1 design.
- Pinned linked execution/verification type ownership: core owns
  `PublishedCopyEvidence` and `PostCopyCandidate`, workflows own the
  discriminated continuation payloads, and the dispatcher remains opaque.
- Deliberately left component-specific documents unchanged; they update with
  the corresponding implementation stages.

## Verification

- `git diff --check`: clean apart from expected LF-to-CRLF notices.
- Cross-document searches found no remaining active cross-cutting claim that
  content evidence stays SHA-256, linked verification is ledger-first,
  execution preflight rereads global settings, or retention ships in M1.
- No pytest or import-linter run: only Markdown documentation changed.

## Immediate Next Context

- Implement M1 in the order frozen in `ARCHITECTURE.md` and `M1_PLAN.md`:
  contracts/semantics, HASH Track 1 then Track 2, inventory/standalone
  integrity, post-execution integration, facade/CLI, then GUI shell.
- HASH Track 1 uses the fixed chunk bands but still benchmarks them and measures
  the conditional preallocation crossover before landing tunables.
- Component docs such as `CORE.md`, `EXECUTOR.md`, `VERIFIER.md`, `DATABASE.md`,
  `INTERFACES.md`, and `DESKTOP_UI.md` intentionally remain implementation-time
  updates, not sources that override the promoted cross-cutting contracts.
