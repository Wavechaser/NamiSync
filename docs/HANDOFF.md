# Latest session — fix placement, BUG-0327 residuals, A8 consolidation, 2026-11-28

## Changes

- **Fix placement policy** — `9a6e0c9d`. [DEFENSE §2.6](DEFENSE.md#26-fix-placement)
  says where a warranted fix goes: name the broken invariant, fix it at its
  owner and never past it, count sibling paths and facets, and take the
  owner fix when it costs about the same as a local one, or more now but less
  over time. A considerably larger owner fix is a scope decision. Reopen triggers are now
  §2.7. AGENTS routes to it, and BUGS entries name invariant, owner and level.
- **BUG-0327 third review** — `222b89b7`, [BUG-0327](BUGS.md#bug-0327).
  Both reported facets reproduced through the real service: a ledger
  refusing the settlement's finish read recording `ok`, and a 1025-byte
  reacquisition message skipped settlement (0 bytes, unfinished ledger,
  retained token). Under §2.6 this was a recurrence. The user adjudicated
  the pause: fix both at the settlement seam and record core's collapse of
  an unexplained `DEGRADED` to `ok` as an A5 residual. `settle_failed_execution`
  now takes the ordinary terminal projection on both branches. Dispatcher
  eligibility now follows the `FAILED` result; an omitted diagnostic is
  passed as `None` and counted once.
- **A8 consolidation** — `35bf01d2`. Drive-letter listing moved to core
  (`logical_drive_roots`) and is shared with inventory's resolver; the two
  lookups keep their own stopping rules. The scheduling reader lists letters
  only when the recorded mounts miss and names the matching volume once.
- **M2-A10 Task lifecycle on the wire** — formalized in [M2_PLAN](M2_PLAN.md)
  as accepted, not started: snapshot v5 exposes the lifecycle (including
  `pending`) in place of `control_state`, keeps the capability fields and
  `session_progress`, and removes the page's capability inference. It closes
  two A5 wording residuals; the "in progress" review wording and the notice's
  "Paused" count stay A5 residuals as separate causes.

## Verification

- BUG-0327: the real-service reproducer is parametrized over plain, bulk,
  refused finish and long diagnostic; dispatcher and workflow cases cover the
  omitted diagnostic, the settlement fallback and both execute branches.
  Mutants that restore the diagnostic-keyed eligibility, drop the omission
  count or drop the recording projection each failed tests. Dispatcher,
  exception-graph and affected workflow departments passed.
- A8: disk topology, scheduling (including the real `J:`/`M:` reference
  test) and inventory workflow tests passed, 235 in all; 13 import contracts
  kept.
- Full ordinary suite at `222b89b7`: 7606 passed, 4 skipped, 7 failed. The
  failures are the known interpreter-bound ones: six transport-custody tests
  and the native-gate test.
- The user re-checked both A5 and A8 and accepted them. The user's probe then
  found a latent overwrite after a guard-refused finish. It is traced and
  recorded as an A5 residual, not fixed. By inspection it is unreachable in
  production.
- Not run: headed desktop tests (no page change); a stock Windows custody
  error longer than the bound (the reproducer injects one).

## Immediate context

- **M2-A10** is the next A5 follow-up; A6 and A7 (GUI) remain the next
  Segment A rows as grouped by the user.
- Deferred to M2-C2: Resume all skips `INTERRUPTED` while its snapshot offers
  resume. Refused resume stays [Unowned](M2_PLAN.md#unowned); it can reuse
  the `settle_failed` path.
- Deferred by the user to B3: the inventory review's two row sources, and the
  integrity page's missing run-level recording and audit status.
- Open in BUGS: BUG-0320 (concurrent-inventory exit `7`) and BUG-0321 (nested
  custom database paths).
- Fixtures kept: `J:\NamiSyncSpike\stop-latency` (read only) and
  `M:\NamiSyncA8` (384 files, 52 MB, seed 20261127), until the user decides.
- The local `.venv` is CPython 3.13.17, not the release interpreter 3.15.2,
  and has `xxhash` 3.8.1 where 4.1.0 or newer is required. Six custody tests
  and one native-gate test (pythonnet 3.1.0 vs 3.2.1) fail locally because of
  it; rebuild the venv per TOOLS before relying on them.
- The copied-dispatcher pause, resume and cancel cases in
  `tests/interfaces/web/test_drain.py` miss their deadlines under heavy
  parallel load (from A3).
- `evidence/EV-0045` scripts import `migrate_database_pair`, which no longer
  exists; they run only at their recorded revision.
- For M2-R1's release notes: a v0.1.0 binary pointed at a migrated database
  shows its own reset guidance.
- The M2-A2 prototype may still be open from `build/m2-a2-maximized/probe.py`;
  close it normally before clearing that workspace.
- Also carried over:
  - Elevated cleanup of the Codex-sandbox `build/` residue.
  - A3 review scratch is still under `build/a3-review-25/` and
    `build/a3-fix-review/`.
  - Frozen `sh_g_8_*` artifacts must not move.
  - Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir`, `dist/v0.1.0/` and
    `build/inventory-cold/`.
- This session wrote nothing to `build/`. Nothing was pushed; `milestone2`
  carries the commits above.
