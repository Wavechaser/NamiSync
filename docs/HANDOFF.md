# Latest session — M2-A4 review fixes and stamp revision, 2026-11-26

The six defects from the review at `48ab4718` are fixed, and the v0.1.0 stamp
rule is replaced under the revised
[DEFENSE §2.5.4](DEFENSE.md#254-migrating-a-released-database). Work is on
`milestone2`; nothing is pushed. M2-A1 to M2-A4 are complete and M2-A5 is the
next row, still proposed. [M2_PLAN](M2_PLAN.md)'s A4 row holds the decisions
and what is open; [DATABASE](DATABASE.md#data-protection) owns the behavior.

## Changes

- `41e020b7`: a plan made with no ledger instance reads no ledger. A run's
  History stamp is read again once the observer holds its claim, and
  admission is refused if the ledger was replaced in between.
- `c29ebe18`:
  - Backup, restore source and restore image share one content check
    (integrity and foreign keys). A database with foreign key violations is
    not backed up, and restore renames it aside instead of overwriting it.
  - Rotation never removes a live database.
  - A restore that stops after moving only sidecars names the files moved.
  - The CLI decides its closing lines from the result, validates paths before
    folder checks, and repeats custom database options with its guidance.
- `e1f40f63`:
  - A v0.1.0 History is stamped only when the same operation migrated its
    ledger. The `migrated-released` lineage kind, `without_ledger` and
    `MigratedDatabase.unstamped` with its notices are gone.
  - `upgrade_database_pair` replaces the separate migrate and complete
    operations for the CLI and desktop startup.
  - A ledger restore is refused only beside a swapped or newer History, or
    over a healthy older pair (`pair-older`).

Of the review's five consolidation opportunities, all are done.

## Verification

- Ordinary suite on the bytes of `e1f40f63` before its last test assertion
  was restored: 7326 passed, 4 skipped, 35 deselected, with the seven known
  interpreter-bound failures; `lint-imports` 13 kept. Builder and reviewer
  each ran it.
- Each of the three commits had an independent adversarial review with
  out-of-tree mutations. The reviewer could not construct a History stamped
  with a ledger the same call did not migrate.
- Changed after review and not seen by a reviewer:
  - In `c29ebe18`: the custom-path line's quoting, the order of the
    foreign-key and classification checks on a restore source, and a README
    sentence. 272 focused tests passed.
  - In `e1f40f63`: one assertion restored in
    `test_lone_released_history_migrates_then_gains_a_new_ledger`, which pins
    that a lone v0.1.0 History's runs stay earlier. 65 tests in the two pair
    files passed; the full suite was not rerun after it.
- Not run: a headed desktop launch, the installed `namisync.exe`, and a real
  two-process race for the two admission fixes (driven by in-process hooks).
- Review scratch under `build/a4-*` was deleted. No evidence record was
  promoted.

## Immediate context

- Open for a user decision (also in the A4 row):
  - A `--location-id` command can create a missing database if a database
    file vanishes between the CLI's first read and the upgrade. A `create`
    argument on the operation would close it.
  - A zero-byte History is classified with the direction to archive or
    delete both databases. A ledger restore beside it now succeeds and then
    prints that advice; `check` printed it before this work.
  - The `history` command and the "Plan again" refusal do not repeat custom
    database options.
  - No pair-level test covers the refusal-reason mapping or reclassification
    under the claims.
  - The History stamp handling sits in generic engine code (`_copy_rows` and
    `_verify` in `namisync/db/migration.py`), not in the v8 step.
- For the first post-M2 schema step: the stamp condition is "the ledger
  migrated in this call", which equals "from 0.1.0" only while v4 and v8 are
  the sole registered steps.
- Consequences of the foreign-key rule:
  - While either database has violations, `backup` cannot succeed; restoring
    an earlier backup is the way out.
  - If only History has them, each `backup` run publishes a ledger backup
    that is never rotated.
  - Restore over such a database needs every NamiSync process closed.
- A source-tree ledger made while the marker kind existed (between
  `93185248` and `e1f40f63`) is refused with reset guidance.
- `evidence/EV-0045` scripts import `migrate_database_pair`, which no longer
  exists; they run only at their recorded revision.
- Review notes left as they are:
  - `--database ""` falls back to the default pair, as it does for `sync`.
  - The same file given for both database flags through different spellings
    is not recognized as one path; it ends as `database-in-use`.
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
