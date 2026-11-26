# Latest session — M2-A4 second review round, 2026-11-26

Eight findings from the user's second review of M2-A4 are fixed. Work is on
`milestone2`; nothing is pushed. M2-A1 to M2-A4 are complete and M2-A5 is the
next row, still proposed. [M2_PLAN](M2_PLAN.md)'s A4 row holds the decisions
and what is open; [DATABASE](DATABASE.md#data-protection) owns the behavior.

## Changes

- `4993a244`: the v0.1.0 History step owns its stamp and verifies that every
  run carries exactly the id given. The generic engine no longer knows it.
- `aa61dfe6`: `upgrade_database_pair` takes the caller's permission to create
  and enforces it under both claims. A `--location-id` command never grants
  it.
- `007fe988`: a reset direction names only the database that needs it and
  says to keep the other. `check` prints the pair direction for a reset.
- `317861bc`: an admitted run's observer holds the ledger's shared claim,
  taken before its stamp is read, until it closes. The re-read from
  `41e020b7` is removed.
- `129e2968`: a `history` refusal repeats exactly the database options given;
  the replaced-ledger refusal says to rerun the same sync command; pasteable
  paths double every PowerShell single-quote character.
- `72176b46`: an integrity continuation keeps the ledger instance read under
  its recorder claim, and a resume that finds another instance is refused
  before the scan.

## Verification

- Ordinary suite on `72176b46`: 7366 passed, 4 skipped, 35 deselected, with
  the seven known interpreter-bound failures; `lint-imports` 13 kept.
- Each of the six commits had an independent adversarial review with
  out-of-tree mutations. Three needed corrections, which the same reviewer
  confirmed.
- Reproduced with real child processes, before and after:
  - `check` and `restore ledger` naming the run's ledger with another
    History, while a run sat between its stamp and its recorder.
  - A paused baseline, verify and rebaseline run resumed after
    `restore ledger`, with degraded audit and with History failing mid-run.
- The path quoting was fuzzed through the parser of PowerShell 7 and 5.1
  (4043 lines, no failures) by its reviewer.
- Changed after review and not seen by a reviewer:
  - In `aa61dfe6`: the ID-only refusal ends "Nothing else was changed." when
    a database had already been updated. 173 focused tests passed.
  - In `72176b46`: two DATABASE sentences and one code comment reworded as
    the reviewer advised.
  - After the gate: one assertion that a refused resume's record holds the
    item reported before the pause exactly once. 44 tests in
    `tests/test_inventory_runtime.py` passed; the full suite was not rerun.
- Not run: a headed desktop launch, the installed `namisync.exe`, and the
  headed SH-G-5 case whose expected text changed in `007fe988`.
- Review scratch under `build/a4-review-*` was deleted. No evidence record
  was promoted.

## Immediate context

- Open for a user decision (also in the A4 row):
  - The desktop inventory review labels a row from the session's item before
    the row's own ledger state (`inventory_review.js`), so after a refused
    integrity resume it shows rows reported before the pause as "Baselined"
    or "Verified", which the current ledger does not attest. Keeping those
    items in the failed record is intended and tested (user decision); the
    defect is in that view.
  - A paused integrity run canceled after a restore ends canceled with its
    earlier items listed and no mention of the ledger.
  - When both databases need a reset, the direction names no paths.
  - A pasteable path holding characters shown as `[U+XXXX]` markers names
    the marker text, not the path.
- Known limits recorded in DATABASE:
  - A session admitted with degraded audit, or whose audit degraded after
    admission, holds neither claim while paused. Sync and integrity resumes
    are checked against the ledger instance; inventory acknowledge and
    restore by row id are not (B3).
  - If the dispatcher's `EventHub` or `_AuditPump` constructor raises a
    configuration error, the observer is never closed and both claims stay
    held. The service passes valid constants, so production cannot reach it.
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
