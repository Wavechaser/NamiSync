# Latest session — M2-A4 maintenance commands, 2026-11-26

M2-A4 is complete on `milestone2`; nothing is pushed. M2-A1 to M2-A4 are done
and M2-A5 is the next row, still proposed.
[M2_PLAN](M2_PLAN.md)'s A4 row holds the decisions, outcomes, gate result and
what is left for B2 and B3. [DATABASE](DATABASE.md#data-protection) owns the
behavior and [COMMANDLINE](COMMANDLINE.md#maintenance-commands) the commands.

## Changes

Six outcomes, one reviewed commit each:

- `650110fd`: a session started while maintenance holds the claim is refused at
  admission (bridge error `database_maintenance`, CLI exit `3`).
- `14c4e661`: a plan records its ledger instance and execution refuses a
  mismatch.
- `6655ddcc`: the `ledger_lineage` table, the ancestor-chain read rule, and
  refusal of a ledger backup copied into place.
- `f0280e4d`: check, backup, restore and rotation in
  `namisync/db/maintenance.py` and
  `namisync/workflows/database_maintenance.py`.
- `93185248`: completion of a pair with one database missing, and the rule
  that a v0.1.0 History is stamped only beside its own migrated ledger.
- `78246b75`: CLI `check`, `backup` and `restore`, and damage refusals that
  point to them.

Ledger schema 5 was amended in place twice (the lineage table, then its
`migrated-released` kind). A schema-5 pair made by a source-tree run between
A3 and this work is refused with reset guidance.

## Verification

- Ordinary suite on the final outcome's bytes: 7310 passed, 4 skipped, 35
  deselected, with the seven known interpreter-bound failures. `lint-imports`:
  13 kept.
- Rerun on `78246b75`: the six A4 test files, 177 passed, which include the
  three closing conditions with real child processes and the restore kill
  trials.
- Each outcome had an independent adversarial review with out-of-tree
  mutations; every required change was corrected and confirmed by the same
  reviewer.
- A recurrence pause was taken during outcome 5 (two unplanned cases of
  History runs stamped with the wrong ledger). The user chose the marker rule
  recorded in the A4 row.
- No evidence record was promoted: the gate is the tracked tests, and the
  counts are here and in CHANGELOG. Review scratch under `build/a4-*` was
  deleted.

## Immediate context

- Not exercised by a real fault, only through patched tests or the renderer:
  an unconfirmed or failed restore through the CLI, an in-place restore
  stopped mid-copy by a lock, and a backup-removal failure. The console
  `namisync.exe` entry was not run for the new commands (`python -m namisync`
  was). No desktop run was made.
- Review notes left as they are:
  - `--database ""` falls back to the default pair, as it does for `sync`, so
    `restore` with an empty value targets the default database.
  - The same file given for both database flags through different spellings
    (`\\?\` or UNC against a drive path) is not recognized as one path; it
    ends as `database-in-use` with nothing changed.
  - A `\\?\` database path passes the per-role check but not the pair check,
    so `check` prints both roles `ok` and then `database-unavailable`.
  - `check` exits `4` both for a problem found and for a check that could not
    finish; the output tells them apart.
  - A cold probe reports `database-unavailable` during any WAL write
    transaction, which predates A4.
- For B3: the desktop still shows its generic commitment refusal for a plan
  whose ledger was replaced, and inventory acknowledge and restore by row id
  are not covered by the instance check.
- Carried over from A3: the copied-dispatcher pause, resume and cancel cases
  in `tests/interfaces/web/test_drain.py` miss their deadlines under heavy
  parallel load. For M2-R1's release notes: a v0.1.0 binary pointed at a
  migrated database shows its own reset guidance.
- A source-tree run migrates any v0.1.0 pair it is pointed at and completes a
  pair with one database missing. The `NamiSync-Development` root holds no
  pair today.
- A8's gate needs an HDD that carries two lettered partitions; none exists on
  the reference machine.
- `J:\NamiSyncSpike\stop-latency` (about 157 MB) is kept as the HDD fixture
  until the user decides.
- The M2-A2 prototype may still be open from `build/m2-a2-maximized/probe.py`;
  close it normally before clearing that workspace.
- The local `.venv` is CPython 3.13.17, not the release interpreter 3.15.2,
  and has `xxhash` 3.8.1 where 4.1.0 or newer is required. Six custody tests
  and one native-gate test (pythonnet 3.1.0 vs 3.2.1) fail locally because of
  it; rebuild the venv per TOOLS before relying on them.
- Also carried over:
  - Elevated cleanup of the Codex-sandbox `build/` residue.
  - A3 review scratch is still under `build/a3-review-25/` and
    `build/a3-fix-review/`.
  - Frozen `sh_g_8_*` artifacts must not move.
  - Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir`, `dist/v0.1.0/` and
    `build/inventory-cold/`.
