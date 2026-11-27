# Latest session — A5 and A8 review findings fixed, 2026-11-27

## Closing-review findings

The independent review of `b7985075` reported five findings. Each was
validated against its reproducer and fixed or answered; both rows stay
closed with the fixes recorded in them.

- **P1, resumed run reported UNRUN** — `b429cd8c`,
  [BUG-0323](BUGS.md#bug-0323). The worker's custody and `open` failure paths
  hard-coded `UNRUN`; they now derive it from the start time. A real-copy
  reproducer then ended `FAILED+RAN`. The resumed attempt's ledger
  run still stays unfinished (residual in the A5 row).
- **P2, Pause all snapshot race** — `67e8ac0e`,
  [BUG-0324](BUGS.md#bug-0324). Bulk calls are now serialized and take
  pending sessions' locks first; a pending session can still start before
  its own lock is taken and is then treated as running.
- **P2, remounted binding keyed by old letter** — `d7ae58cc`,
  [BUG-0325](BUGS.md#bug-0325). The reader finds the binding's volume at its
  current mount (recorded mounts first, then every letter).
- **P2, reservations per dispatcher** — no product trigger: every product
  entry point composes one service and so one dispatcher per process. Not a
  bug; `4045a949` states the scope in DISPATCHER and WORKFLOWS.
- **P3, queued scans read as scanning** — `22ec81b9`,
  [BUG-0326](BUGS.md#bug-0326). A pending task now reads "Waiting to start"
  with an idle bar.

**M2-A5 and M2-A8 are closed.** [M2_PLAN](M2_PLAN.md) holds both rows with
their gates and residuals; A4's row was compacted and its deferred work moved
to B3. A6 and A7 (GUI) are the next Segment A rows, grouped by the user.
Nothing was pushed; `milestone2` carries the commits below.

## M2-A5: Pause all and Resume all

- `46c461a5`: holding (`PENDING` to `PAUSED` with no start time), session
  progress, and dispatcher `pause_all` and `resume_all`.
- `bb2f048e`: the `control_all_tasks` bridge command, task snapshot v4 with
  `session_progress`, `can_pause`, `can_resume` and `can_stop`, and Gap
  recovery that adopts the session record.
- `61b675fa`: the rail buttons and capability-driven task pages.
- `5ceaaa08`: BUG-0322, an accepted Stop lost when a resume raced the paused
  worker; a release now requires no cancel request.
- `bc985d95`: row closure, CHANGELOG and BUGS.
- User decisions: held is paused and never started; two rail buttons; a
  resume refused at preflight keeps ending `FAILED+RAN`.

## M2-A8: physical-disk scheduling

- `4e80056d`: core `disk_topology` (volume extents, bus type, seek penalty).
- `47cfaa83`: dispatcher scheduling keys, read outside the lock on each pass
  and used only from the current pass for the same record.
- `0c92160a`: `workflows/disk_scheduling.py` and the reader on all six
  registrations. Roots are resolved from their paths at each read, not from a
  volume GUID captured at admission (a design change recorded in the row).
  Only `\Device\HarddiskVolume` letters are read, after a mapped network letter
  was shown to block the scheduler for 41–80 s.
- `7da7af2e`: [EV-0046](../evidence/EV-0046/README.md), the real inventory
  pair on `J:` and `M:` (serialized 3 of 3) and an NVMe control pair
  (overlapped 3 of 3).
- User decisions: in-process serialization only; the unreadable-key advisory
  moves to the drive-type notices item.

## Verification

- Review fixes on `22ec81b9`: 7569 ordinary tests passed, 4 skipped, 36
  deselected, with the seven known interpreter-bound failures; dispatcher department 209 passed in index
  isolation; all twelve background headed tests passed with the new wording.
- Final A5/A8 head `7da7af2e` plus those closeout docs: 7558 ordinary tests passed, 4 skipped, 36 deselected, with the seven known interpreter-bound failures; `lint-imports` 13 kept.
- Every outcome, each correction round and both whole checkpoints had a fresh
  adversarial review. A5 dispatcher guards and nine A8 scheduler mutants were
  killed by the existing tests. The A8 closure review found nothing to fix
  beyond closeout records; it confirmed the INTERFACES sentence on cancel
  settlements was stale (fixed in the closing commit).
- The headed rail journey and all twelve background headed tests passed for
  A5. Not run: a headed desktop check of A8 (it has no UI), a spun-down disk,
  and real mapped or `subst` letters (tested through a fake).

## Immediate context

- Deferred by the user to B3 (moved from the A4 row): the inventory review's
  two row sources, and the integrity page's missing run-level recording and
  audit status. See B3 in [M2_PLAN](M2_PLAN.md).
- Deferred to M2-C2: Resume all skips `INTERRUPTED` while its snapshot offers
  resume.
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
- This session's `build/` output, including the review reproducers, was
  deleted once each finding was recorded in BUGS.
