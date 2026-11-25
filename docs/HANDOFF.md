# Latest session — M2-A4 adversarial review, 2026-11-26

The read-only review at `48ab4718` covered all six M2-A4 outcomes, starting
with the installed `namisync.exe` on isolated database pairs. A4 passed its
three closing conditions, but backup rotation can discard the last usable
recovery point. That is the first defect to address. The delivery status and
deferred B2/B3 work are in [M2_PLAN](M2_PLAN.md). All six findings are open.

## Six defects

1. **High — Rotation can discard every restorable backup.** With a dangling
   foreign key in the ledger, `check` advised taking a backup. Three successive
   `backup` commands exited 0 and rotated out the good copies. All three
   retained ledger backups then failed to restore into an empty target with
   exit 4. Backup verification accepts foreign-key violations that restore
   image verification rejects. [Backup and restore verification](../namisync/db/maintenance.py)
2. **High — A plan can read a ledger and carry no instance ID.** Planning
   started with a fresh pair. A second process created the pair with
   `inventory` before the first plan queried correspondence. The query ran and
   the commitment still carried `ledger_instance_id=None`. Source inspection
   shows that execution skips the replacement check for that value.
   [Plan preparation and correspondence](../namisync/workflows/runtime.py) ·
   [Execution check](../namisync/workflows/sync.py)
3. **High, with custom filenames — Rotation can select the live peer for
   deletion.** A valid History path can match the ledger's backup filename
   pattern. Rotation protects the new backup and selects other regular files
   by name and age. An old enough, closed History main is eligible for removal.
   This follows from inspection of the candidate selection and unlink path.
   [Pair rotation](../namisync/workflows/database_maintenance.py) ·
   [Candidate selection](../namisync/db/maintenance.py)
4. **Medium — A new M2 run can acquire a stale History stamp.** Sync,
   inventory and integrity admission read the ledger instance before the
   observer acquires History's shared claim. A restore that finishes in that
   interval can leave a run writing against the new ledger with the old stamp
   in History. Inspection confirmed the ordering. The review did not observe
   a misattributed run. Read the instance under the observer's existing claim.
   [Admission](../namisync/workflows/runtime.py) · [Observer](../namisync/db/history.py)
5. **Medium — Recovery instructions lose custom database paths.** For a
   custom pair with a missing ledger, the CLI suggested
   `namisync restore ledger <backup file>`. With the default data directory
   redirected into the fixture, an unqualified command selected the default
   pair. Following the advice could replace its ledger and leave the intended
   pair unrepaired. [CLI recovery guidance and path selection](../namisync/interfaces/cli.py)
6. **Medium — A partial rename can report a kept file that does not exist.**
   Restore moves sidecars first. If a later rename fails before the main
   moves, the failure reports the proposed kept main path, although the main
   is still at its original path. Inspection found that the code already
   records each successful move. [Restore failure handling](../namisync/db/maintenance.py)

## Five consolidation opportunities

1. Use the same content checks for ordinary backups eligible for rotation
   and for restore sources. A diagnostic copy must never displace the last
   restorable backup. Migration backups retain their distinct rollback purpose.
2. Classify a database once per open snapshot. Both `check_database` and
   restore-source validation repeat metadata and topology classification
   through the reader contract. Read the additional backup-cut fact directly.
   Keep revalidation at a new snapshot or after publication.
3. Give CLI and desktop startup one workflow operation to upgrade or complete
   an existing pair under the claims. Return what migrated and what was
   created. Keep CLI placement checks, desktop path pinning and their
   respective reporting at the adapter boundaries.
4. Render recovery guidance from the refusal reason, effective paths and
   files actually kept or moved. The CLI currently searches English guidance
   for phrases and pathnames to decide what else to print.
5. Reconsider requiring a healthy or missing History peer before ledger
   restore. Allowing repair beside a damaged History would let the user repair
   either role first when both are damaged. Keep swapped-path and newer-version
   protections and advise upgrading a healthy older pair first. This proposal
   would change the accepted A4 restore policy.

## What held up

- At the reviewed revision, 177 checkpoint tests and 36 related consumer tests
  passed, and all 13 import contracts held. The tests covered refusal in both
  directions under maintenance, refusal of a normally stamped plan after
  restore, ancestor membership, a backup copied into place, pair migration
  and completion, interrupted restore, and bridge refusal handling.
- The installed executable completed a healthy check, backup and ledger
  restore. A real Windows sharing violation during rotation produced a
  warning and preserved the locked file. A different SQLite page size
  exercised the CLI's `restore-unconfirmed` outcome.
- A real SQLite writer lock taken immediately before the destination copy
  produced exit 3, preserved the ledger instance and named the pre-restore
  backup. The checkpoint's kill trials covered interruption after copying
  began. The lock trial covered copy entry only.
- Two safeguards have distinct jobs. Shared claims protect cooperating M2
  writers, while the migration open-handle check also sees M1 processes.
  The writer-side ledger-instance check covers the interval after plan-start
  validation when degraded audit leaves a run without a History claim.
- Desktop coverage came from child-process, host, bridge and JavaScript tests.
  The review did not launch a headed desktop or rerun the ordinary suite.
  The delivery run at `78246b75` recorded 7310 ordinary passes, 4 skips,
  35 deselections and the seven known interpreter-bound failures. Review
  fixtures were removed.

## Immediate context

- Two smaller discrepancies surfaced during review. With an invalid Windows
  parent in both database paths, `check` returned 0 because the missing-folder
  shortcut precedes path validation. The [CLI manual](COMMANDLINE.md#maintenance-commands)
  also says backup never creates a WAL, while the [database contract](DATABASE.md#data-protection)
  and tests allow SQLite to leave an empty WAL.
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
