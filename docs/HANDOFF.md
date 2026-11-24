# Latest session — M2-A3 maintenance claim and schema migration, 2026-11-25

Work remains on `milestone2`; nothing is pushed. M2-A1 to M2-A3 are complete.
M2-A4 is the next row and is still proposed, not accepted.

## Changes

- `60b43078` saved a database pair written by the released v0.1.0 binary under
  `tests/assets/v0_1_0/`, with `tools/fixtures/v0_1_0_pair.py` to reproduce it.
- `37187dea` added `namisync/core/formats.py` and its known-answer vectors.
- `ebc2ce77` added the maintenance claim (`namisync/db/claims.py`): writers
  hold it shared, schema creation and migration hold it exclusive.
- `880c3ad7` moved the ledger to schema 5 and history to schema 9, added
  `namisync/db/migration.py`, and wired migration into pair admission, desktop
  startup and the CLI. The row's schema and admission outcomes landed together.
- [M2_PLAN](M2_PLAN.md)'s A3 row holds the outcome, design decisions, accepted
  residuals and what A4 inherits. [DATABASE](DATABASE.md#schema-evolution)
  owns the behavior. [EV-0045](../evidence/EV-0045/README.md) is the gate
  record.

## Verification

- Ordinary suite on `880c3ad7`: 7079 passed, 4 skipped, 35 deselected, and the
  seven known interpreter-bound failures. `lint-imports`: 13 kept.
- Each of the four outcomes had its own independent adversarial review; every
  required change was corrected and confirmed by the same reviewer.
- Kill trials on the committed code: 15 of 15 left the old or the new database,
  and the next call finished the migration (EV-0045).
- After the last review one message was changed by hand, so a damaged-database
  refusal no longer shows a private class name. It has a test and ran in the
  final suite, but no reviewer saw it.

## Immediate context

- **A source-tree run now migrates any v0.1.0 pair it is pointed at.** The pair
  becomes schema 5 and 9, with backups beside it named
  `<database>.backup-v4-…` and `.backup-v8-…`, and the v0.1.0 binary then
  refuses it and suggests archiving or deleting it. The `NamiSync-Development`
  root holds no pair today, so a first run there creates a fresh one. The
  release's own data folder was not touched by this work.
- Open, outside A3: the copied-dispatcher pause, resume and cancel cases in
  `tests/interfaces/web/test_drain.py` miss their fixed deadlines under heavy
  parallel load, also before this work. One "DID NOT RAISE ValueError" report
  from a single full run was never reproduced and is unexplained (EV-0045).
- Review notes left as they are: a source read error during backup gets
  write-access advice instead of damage advice; the damage message says
  "integrity check" when the backup failed on row counts or classification;
  the unknown-role message quotes the stored value without a length limit.
- For M2-R1's release notes: a v0.1.0 binary pointed at a migrated database
  shows its own reset guidance.
- A8's gate needs an HDD that carries two lettered partitions; none exists on
  the reference machine.
- `J:\NamiSyncSpike\stop-latency` (about 157 MB) is kept as the HDD fixture
  until the user decides. Leaving Do Not Disturb off was the user's choice.
- Carried over: the M2-A2 prototype may still be open from
  `build/m2-a2-maximized/probe.py`; close it normally before clearing that
  workspace.
- Carried over: the local `.venv` is CPython 3.13.17, not the release
  interpreter 3.15.2, and has `xxhash` 3.8.1 where 4.1.0 or newer is required.
  Six custody tests and one native-gate test (pythonnet 3.1.0 vs 3.2.1) fail
  locally because of it; rebuild the venv per TOOLS before relying on them.
  Also carried over:
  - Elevated cleanup of the Codex-sandbox `build/` residue.
  - Frozen `sh_g_8_*` artifacts must not move.
  - Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir`, `dist/v0.1.0/` and
    `build/inventory-cold/`.
