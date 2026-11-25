# Latest session — M2-A3 review fixes, 2026-11-25

The adversarial review of `60b43078` through `af4b8d6c` (`d721ac63`) found
five issues. All five are fixed in `f80c1c88` and `f0162d19`, each with a
regression test that fails against the earlier code.

- **CLI placement safety:** the CLI admits a command's roots and `--path`
  values, and checks both databases lie outside the roots, before migrating.
  A refused input migrates nothing; planning refuses a pair that still needs
  migration. Left as a documented limit: with `--location-id` the root is
  known only from the ledger, so that case migrates first.
- **Pair refusal guidance:** a role needing reset no longer answers before the
  other role is classified, so a newer or wrong-role database is reported
  instead of the direction to discard both.
- **History replay identity:** an observer refuses a run token under a
  different ledger instance, at construction and on each write.
- **Backup temporary ownership:** the temporary is created exclusively. Its
  `-journal` sibling is not reserved the same way.
- **Fixture producer timeout:** a watchdog bounds the whole step.

Verification on `f0162d19`: 7098 ordinary tests passed, 4 skipped, 35
deselected, with the seven known interpreter-bound failures; `lint-imports`
13 kept. An independent reviewer required one change (an unsafe `--path` still
migrated first), which was made, and then approved; its mutations of each fix
were caught by the new tests. Not rerun: the kill trials and a headed desktop
launch. Review scratch is under `build/a3-review-25/` and
`build/a3-fix-review/`.
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
