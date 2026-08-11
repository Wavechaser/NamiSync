# NamiSync Session Handoff

Date: 2026-08-11
Branch: `milestone1`

## Session Outcome

Completed the maintenance-refactor work through the retained settlement-oracle
checkpoint and stopped before the executor package split. The corrected
monolithic executor source is commit `d99743a`; checkpoint 8 has not started.
There is no `namisync/modules/executor/` package, typed effect journal, settlement
reducer, or verifier package split yet.

The work landed as these reviewable checkpoints:

- `f31c83a` establishes component-package/import rules before restructuring.
- `fd79a83` fixes ordinary failure composition of unverified publication and
  sibling readonly-mutation evidence.
- `6c2d61f` adds the ephemeral core `RootAuthority` substrate without changing
  plans, fingerprints, payloads, databases, or other persisted contracts.
- `e5a214f`, `1d220c1`, and `7350f72` harden scoped scanner admission,
  preflight reviewed authority, and verifier exact-root binding respectively.
- `0299db3` and `5a15f61` consolidate scanner and workflow root admission while
  preserving consumer-specific timing and outcome policy.
- `28d27de` records the settlement stability trigger that blocks structural
  executor work until a corrected retained oracle is committed and green.
- `f890c06`, `0b94d42`, and `eb5b556` fix the three settlement defects exposed
  before freezing behavior: post-cleanup re-observation, retained UPDATE backup
  composition, and failed pre-retry temporary cleanup.
- `d99743a` makes the retry-cleanup regression explicitly prove a Retry decision.
- `07f08fe` commits the independent public-facade settlement oracle, its focused
  tests and AST import-boundary gate, and the operating documentation.
- `840c183` commits the corrected normalized trace baseline separately from its
  oracle implementation.

The oracle is retained project infrastructure, not a temporary differential
harness. It exercises 30 scenario IDs and 57 exact policy rows through public
executor/core contracts. Independent expectations cover outcomes, details,
recording, evidence, filesystem trees and metadata relations, recorder/flush
payloads and order, retries, controls, cleanup, Stop sweeping, and repeated use
of one `ExecutionSet`. The historical baseline separately retains the normalized
collaborator/filesystem trace.

## Corrected Baseline Provenance

- Corrected monolithic executor source: `d99743a`.
- Oracle implementation and contract: `07f08fe`.
- Baseline commit: `840c183` (its parent is the oracle implementation commit).
- Baseline: `tools/executor_settlement_baseline.json`.
- Oracle schema: `format_version: 1`.
- Capture eligibility: `repeat: 3`, 30 scenarios, 57 rows, with all three
  complete normalized captures byte-identical.
- Committed baseline Git blob: `387ed7aeb377dbd9c43461e06da7239b95c68dde`.

The exact resume gate is:

```powershell
python -m tools.executor_settlement_audit check --repeat 3
```

Expected final line:

```text
settlement check passed: 30 scenarios x 3 runs
```

Checkpoint 8 must not edit, regenerate, or replace the baseline. The same rule
continues through the effect-journal/reducer work, verifier split, test
consolidation, and the immediate post-refactor stabilization period. If the
gate fails, diagnose the divergence against the committed baseline; do not use
`snapshot --replace` to make structural drift pass. A real settlement-policy
correction requires its own documented bug-fix commit and persistent regression,
followed by a fresh adversarial review and restarted three-run gate before any
separate baseline replacement is considered.

## Final Verification

- Retained oracle policy/stability gate: `30 scenarios x 3 runs` passed from
  committed oracle source.
- Committed-baseline resume gate: `30 scenarios x 3 runs` passed.
- Focused oracle/tool tests: `54 passed`.
- Retry-cleanup regression: passed with exactly one explicit Retry decision;
  the broader cleanup/retry and control reviews found no remaining blocker.
- Complete pytest gate: `1512 passed, 2 skipped` across 1514 collected tests.
- Import linter: `8 kept, 0 broken` across 51 files and 199 dependencies.
- `python -m compileall -q namisync tests tools` passed.
- `git diff --check` passed; the worktree was clean before this handoff edit.
- Independent adversarial review found no unresolved executor-settlement or
  oracle-design blocker.

## Immediate Resume Context

1. Start by running the exact three-repeat `check` command above. Treat any
   failure as a stop condition for structural executor work.
2. Resume with checkpoint 8 only: atomically convert the monolithic executor to
   `executor/__init__.py`, `runtime.py`, `native.py`, and `pipeline.py`, preserve
   all public facade imports/signatures, and update tests to patch the owning
   internal module. Do not leave both the file and package in the tree.
3. Preserve runtime/native/pipeline ownership and import rules already recorded
   in `AGENTS.md` and `docs/ARCHITECTURE.md`. In particular, final-touch checks
   remain in runtime, Windows primitives and UPDATE backup drift mechanics live
   in native, and pipeline never publishes, records, retries, or interprets an
   operation.
4. Apply shared root authority to executor native only after the structural
   split boundary is stable, retaining every existing guard and syscall timing.
   Do not cache an authority observation or treat a checked path as a durable
   capability.
5. Do not begin the typed effect journal or reducer until the executor package
   split itself passes the retained oracle and the full checkpoint-8 gates.
   Do not assume or introduce another executor subdivision.

No README changelog entry was added at this intermediate maintenance checkpoint;
the original plan reserves the compact project-level hardening/refactor entry
for final documentation closure after all structural checkpoints stabilize.
