# Latest session — M2-A4 closed, 2026-11-27

**M2-A4 is closed** (user decision). Its closure blocker is fixed in
`1c940e60`, and two findings stay open in
[BUGS](BUGS.md#database-artifact-ownership-and-rollback) without holding the
row. M2-A5 is the next proposed row. [M2_PLAN](M2_PLAN.md) records the A4
closure and [DATABASE](DATABASE.md#maintenance-claim) owns the maintenance
contract.

## The blocker and its fix

A child-process `restore history`, stopped inside SQLite's copy transaction
after inventory preparation and before observer admission, used to end in an
admitted run with degraded audit: exit `4` when the restore named the run's
ledger, exit `7` when it named another ledger and the same History. The cold
History open failed before any claim was asked for.

Since `1c940e60`, `LocalWorkflowRuntime._stamped_observer` takes both shared claims, ledger
first, before it opens the History store or reads the ledger's instance. Both
cases are refused at admission with the maintenance retry message, nothing
stored and no scan
(`test_a_history_restore_begun_after_preparation_refuses_admission_before_history_is_opened`;
it fails both ways on the earlier runtime).

- Verification: 7399 ordinary tests passed with the seven known
  interpreter-bound failures; 13 import contracts held.
- An independent reviewer approved the change with no findings. It ran the
  new test against an export of `44fdfd61` and saw both cases fail there.
- Not run: the real `namisync inventory` command beside a child restore. The
  exit `3` rests on the test above and on the CLI's existing mapping of an
  admission refusal.
- Not covered by a test: the order of the two claims inside the observer's
  opening.

## Two open findings, recorded in BUGS

- **BUG-0320, the concurrent-inventory exit `7`.** Accepted for A4 as
  bounded and harmless. It is not maintenance and predates A4. A CLI command
  first opens its ledger connection owner when the observer reads the
  ledger's instance. That open runs the cold file validation, which reads the
  main file, `-wal` and `-shm` whole before and after the schema check.
  Another process writing the ledger at that moment fails it in two ways,
  both traced in 60 rounds of four commands (55 clean, 5 exit `7`, 2 exit
  `4`):
  - The files differ between the two reads three times in a row
    (`DatabaseBusyError` after two 10 ms waits).
  - Reading `-shm` meets another process's SQLite lock and raises
    `PermissionError`, reported as `database-unavailable` at once, with no
    retry.

  At observer admission either one degrades audit, so the run completes with
  exit `7` and a closing line that directs the user to History although the
  ledger was the file read. That direction is to be corrected with the race
  fix (user decision). The same validation during preparation gives exit `4`.
- **BUG-0321, nested custom database paths.** `nested.db` as the ledger with
  `nested.db/history.db` as History creates a directory at the ledger's main
  path and both claim files, then exits `4` with `inconsistent-pair`;
  reproduced again this session, with no database written. It should be a
  configuration error before any directory is created.

## Closure review verification

595 focused tests passed, including first-use sync resume after restore,
migration, pair completion, restore interruption, lineage and Inventory
frontend regressions. All 13 import contracts held. The installed CLI refused
a claim-path overlap before file creation, retained three backups per role
after four backups, restored each role and checked the resulting pair healthy.
The full ordinary suite and headed desktop journey were not rerun in this
review. Disposable review fixtures were removed.

## Previous round's changes

- `d07cb246`: the dispatcher closes the audit observer when the event hub
  refuses its configuration.
- `f02624f1`: a sync run planned before any ledger existed is bound to the
  ledger its first recorder opened; a resume after a replacement is refused
  (finding 1).
- `4972133c`: the inventory review labels a row from the ledger after a run
  that failed, was canceled or was refused. The integrity context carries
  the released run's `outcome`.
- `57ca297a`: a database path at the other database's `.claim`, `-wal`,
  `-shm` or `-journal` path is a configuration error (finding 3); a claim
  refusal while creating a first pair is an admission refusal, exit `3`
  (finding 4); the direction to discard both databases names both paths.
- `0ce55b6f`: a role's `check` states only what was found and the pair
  decides the recovery (finding 2); wrong-role and live-backup refusals no
  longer say "Nothing was changed." (finding 5); a database path that cannot
  be written as it is, to the stream in use, is described, not quoted.
- The commit after `165fa4e9` (user decision, 2026-11-27): creating a first
  pair holds both exclusive claims until it is published, and admission
  checks for a held claim before it reports a pair as unusable
  (`classify_database_pair`). Commands that lose the race to create a pair,
  and work started during a restore's copy, exit `3` with the claim's retry
  message.

## Previous round's verification

- Ordinary suite on `0ce55b6f`: 7392 passed, 4 skipped, 35 deselected, with
  the seven known interpreter-bound failures; `lint-imports` 13 kept.
- The claim change: 7397 ordinary tests passed with the same seven
  failures, 13 contracts kept. Its reviewer required three corrections
  (sync planning exited `4`, an unusable folder surfaced as a raw error,
  stale sentences) and confirmed them; two COMMANDLINE sentences were then
  corrected as it specified and not seen again.
- Each commit had an independent adversarial review with out-of-tree
  mutations. `57ca297a` needed one doc correction and `0ce55b6f` three code
  corrections, which its reviewer confirmed.
- Reproduced with real child processes before the fix, and rerun after:
  findings 2, 3, 4 and 5, and both marker-path cases. Finding 1 was
  reproduced in the runtime with a real backup and `restore_database_from_backup`.
- A 99-pair state matrix (11 ledger states by 9 History states) through
  `check` and `inventory` showed discard advice only where the pair decision
  gives it, and never twice.
- Changed after review and not seen by a reviewer:
  - In `57ca297a`: two DATABASE sentences corrected as the reviewer required.
  - In `0ce55b6f`: the unsupported-database next step reads "whether a reset
    is needed and which database it discards", as the reviewer advised. 186
    CLI tests passed.
- Not covered by a test: which stream a selected-databases line is built
  for at each print site (three mutants survived; the code is right today).
- Not run: a headed desktop launch, the installed `namisync.exe`, the headed
  SH-G-5 case, and the inventory review after a refused resume in the real
  app (pause, `restore ledger`, resume or cancel, then a failed Refresh).
- Review scratch under `build/a4-review-*` was deleted. No evidence record
  was promoted.

## Immediate context

- Decided by the user on 2026-11-27 and left for B3 (also in the A4 row):
  - The inventory review has two sources for a row, the run's live items and
    the ledger. Accepted until B3: a canceled or failed verify whose mismatch
    could not be recorded shows it only in Details, and rows keep a run's
    labels after a CLI restore until the run is resumed or canceled, or
    until Refresh.
  - The integrity page shows no run-level status when item recording or
    audit degraded, though the terminal result carries `recording` and
    `audit`; the plan review shows both for sync. No session reports audit
    degradation before it ends: the event hub's `audit_degraded` is unread.
    One fix family, the status lines first.
- From the three-process runs for the claim change:
  - Before it, 77 of 80 losing commands exited `4` (`inconsistent-pair`,
    `database-unavailable`, once `history-missing`); none was told to
    discard a database. After it, 60 rounds gave no exit `4`.
  - The process that created the pair can itself be told to retry when a
    later one holds the claims for its own look.
  - Three `inventory` commands at once on an existing pair: 2 of 40 rounds
    had one exit `7`, "History recording is degraded". The closure review
    above reproduced this and traced one occurrence.
- An ordinary failed or canceled integrity run now also shows ledger states
  on its rows, with the run's result in Details; this is wider than the
  replaced-ledger case and is intended.
- Known limits recorded in DATABASE:
  - A session admitted with degraded audit, or whose audit degraded after
    admission, holds neither claim while paused. Sync and integrity resumes
    are checked against the ledger instance; inventory acknowledge and
    restore by row id are not (B3).
  - A first-use sync run paused before its first recorder opened binds on
    resume to whatever ledger is current; nothing of it was recorded.
  - A ledger file copied back by hand keeps its instance id, so the instance
    checks do not see it.
  - The path check does not see 8.3 short-name aliases.
- Review notes from this round, left as they are:
  - The `history` command, reading History alone, still prints the
    single-database reset direction for an unsupported History.
  - A completed run's item with `record_disposition` stale or conflict still
    labels its row; only the tooltip names the disposition.
  - The dispatcher's handler covers `ValueError` only; an out-of-range or
    `None` setting raises another type and leaves the observer open.
    Production passes valid constants.
- For the first post-M2 schema step: the stamp condition is "the ledger
  migrated in this call", which equals "from 0.1.0" only while v4 and v8 are
  the sole registered steps. Deleting the v8 step leaves two unused
  `MigrationStep` fields and the `ledger_instance_id` parameter as orphans.
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
  - "run a sync or inventory command, once to create a new one" is not true
    of a `--location-id` command, whose own refusal says to use ROOT.
  - `cli.py`'s "Resolve the listed refusals, then plan again." keeps its
    wording.
- For B3: the desktop still shows its generic commitment refusal for a plan
  whose ledger was replaced.
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
