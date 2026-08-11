# NamiSync Session Handoff

Date: 2026-08-11
Branch: `milestone1`

## Session Outcome

The maintenance refactor is complete through checkpoints 1-15. The executor
and verifier now have their intended coarse package boundaries, root authority
is shared through core while every consumer retains its own policy and probe
timing, executor retained effects are typed and settled through one pure
reducer, verifier recording policy is centralized, and the tests mirror those
ownership boundaries. The temporary pathing-to-root-authority compatibility
export is gone; `core/pathing.py` is lexical only.

No public executor or verifier import changed. Plans, fingerprints, workflow
payloads, evidence and event schemas, database schemas, error vocabulary,
operation ordering, retry/control behavior, and successful-path filesystem
timing remain compatible apart from the isolated safety corrections that
preceded structural work. Executor's cached native root probes and verifier's
handle-bound volume/final-path checks remain deliberate component adapters;
they were audited and were not removed as apparent duplicates.

## Checkpoint Record

1. `f31c83a` established component-package ownership and import rules before
   restructuring.
2. `fd79a83` fixed ordinary-failure composition of unverified publication and
   sibling readonly-mutation evidence.
3. `6c2d61f` added the ephemeral core `RootAuthority` substrate without
   changing persisted contracts.
4. `e5a214f` admitted every scoped scanner ancestor without following reparses.
5. `1d220c1` bound preflight observations to the reviewed anchor and volume.
6. `7350f72` bound verifier selections to one exact reviewed logical root.
7. `0299db3` and `5a15f61` migrated scanner and workflow authority users to
   core probes while preserving their distinct admission policy.
8. `dd6a718` atomically split executor into the public facade plus
   `runtime.py`, `native.py`, and `pipeline.py`.
9. `8e50cae` applied shared root authority to executor native while retaining
   every guard and final-touch boundary.
10. `c22ffc4` replaced parallel retained-state dictionaries with one typed
    operation effect journal.
11. `6f8bde4` centralized ordinary failure, cancellation, and deferred-MKDIR
    settlement in the pure executor reducer.
12. `c2e0354` centralized the shared hasher lifecycle and verifier recording
    settlement while keeping item and post-copy flows distinct.
13. `2888fca` atomically split verifier into its facade, engine, and native
    files without changing public signatures.
14. `8a9b6c7` consolidated exact-equivalent fixtures/matrices; `21bef5f`
    organized executor and verifier tests by ownership while preserving the
    frozen 421-row focused surface.
15. The final cleanup removes the pathing compatibility export, closes active
    monolithic-file/private-symbol references, reconciles focused architecture
    documentation, adds the compact README hardening entry, and replaces this
    handoff. This file is part of that checkpoint, so it cannot name its own
    commit hash.

The settlement stability barrier between checkpoints 7 and 8 was substantive,
not ceremonial. `28d27de` documented the trigger. `f890c06`, `0b94d42`,
`eb5b556`, and `d99743a` isolated and fixed pre-freeze settlement defects in
post-cleanup observation, retained UPDATE backup composition, and failed
pre-retry temp cleanup. `07f08fe` introduced the retained independent oracle;
`51eacf7` hardened its fail-closed fault and baseline checks; `2b8b996`
stabilized partial-temp timestamp normalization. Reviewed baseline replacements
landed separately, ending at `50d676b`.

## Corrected Baseline Provenance

- Corrected monolithic executor: `d99743a`.
- Retained oracle introduced at `07f08fe` and hardened through `51eacf7`, with
  timestamp normalization completed at `2b8b996`.
- Current separately reviewed baseline commit: `50d676b`.
- Baseline file: `tools/executor_settlement_baseline.json`.
- Oracle format/schema: `format_version: 1`; the exact top-level baseline
  fields are `format_version`, `repeat`, `manifest`, and `scenarios`.
- Coverage: 30 scenario IDs and 58 unique policy rows; the default capture
  requires three complete byte-identical normalized runs.
- Baseline Git blob at `50d676b`, current `HEAD`, and the working tree:
  `4da5c3401d73a1c03be07ae0af9779fd22df8f9b`.
- Independent canonical-JSON pin used by the official gate:
  `ed760ac0d4a90e766415018cf6db98e442f14b785cce5e25b32b82b2255bce2d`.

The exact default resume gate is:

```powershell
python -m tools.executor_settlement_audit check --repeat 3
```

Its successful final line is:

```text
settlement check passed: 30 scenarios x 3 runs
```

The baseline remained byte-for-byte immutable through checkpoints 8-14:
`dd6a718`, `8e50cae`, `c22ffc4`, `6f8bde4`, `c2e0354`, `2888fca`, `8a9b6c7`,
and `21bef5f`. Checkpoint 15 also does not edit it. Do not regenerate the
baseline to make a future structural or settlement mismatch pass. A genuine
policy correction still requires an isolated bug-fix commit, a persistent
regression, independent oracle expectations, adversarial review, and a
restarted three-run gate before a separate reviewed baseline replacement.

## Final Verification

Checkpoint 14's frozen structural gate completed with:

- Focused executor/verifier/core-authority ownership surface: `421 passed`.
- Complete suite: `1544 passed, 2 skipped`.
- Retained oracle: `30 scenarios x 3 runs`.
- Import linter: `11 kept, 0 broken` across 56 files and 220 dependencies.
- Compile and diff checks passed; the baseline blob was unchanged.
- Independent AST preservation gate: 468 top-level nodes, 261 test functions,
  147 classes, digest
  `59adb51327382c3f7882d0d57ad595da96265c31798f876f955b4d1577e210fd`.

Checkpoint 15's frozen cleanup gate completed with:

- Core root-authority/package tests: `35 passed`.
- Sidecar/private-reference tests: `29 passed`.
- Complete suite: `1543 passed, 2 skipped`; the one-test reduction is exactly
  the deleted compatibility-alias regression, not a behavioral oracle.
- Retained oracle: `30 scenarios x 3 runs` against the unchanged baseline.
- Import linter: `11 kept, 0 broken` across 56 files and 219 dependencies.
- `python -m compileall -q namisync tests tools`, `git diff --check`, and the
  active stale-reference/import-boundary searches passed.

## Immediate Next-Session Context

1. Start with the exact three-run oracle command above. Keep the oracle and
   baseline as retained project infrastructure through the immediate
   post-refactor hardening period.
2. There is no remaining executor/verifier split, journal/reducer, authority,
   or test-consolidation checkpoint. Do not infer another subdivision from
   this work; reassess only if the stabilized boundaries produce concrete
   ownership failures.
3. Future single-file throughput work belongs primarily in executor
   `pipeline.py`; Windows flags/handles remain in `native.py`; multi-file and
   per-volume scheduling remain in `runtime.py`.
4. Root authority is fresh evidence at a check, never durable authorization.
   Keep scanner, preflight, executor, verifier, inventory, and workflow outcome
   mappings and probe timing component-local.
5. Historical monolith paths remain only in the explicitly point-in-time
   `M1_AUDIT_DSV4.md` and PoC/obsolete records. Active code, tests, focused
   documentation, and patch targets use current owner modules.
6. After checkpoint 15 is committed and pushed, verify a clean synchronized
   `milestone1` branch. Product work can then resume from the active feature
   and Stage 6 documents; the maintenance refactor itself has no open blocker.
