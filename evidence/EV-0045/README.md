# EV-0045: M2-A3 migration gate, design probe and review experiments (2026-11-25)

Gate record for [M2_PLAN](../../docs/M2_PLAN.md)'s M2-A3 row. Source identity:
`milestone2` at `880c3ad7`, after `60b43078` (v0.1.0 fixture), `37187dea`
(format constants) and `ebc2ce77` (maintenance claim). Profile: Windows 11 Pro
26200, CPython 3.13.17 (the local venv, not the release interpreter 3.15.2),
SQLite 3.50.4. The released pair is `tests/assets/v0_1_0/` with its
`PROVENANCE.json`. Nothing here ran against the live data root.

## Design probe

`probe_exclusive.py` asks whether SQLite itself can prove a connection is the
only one on a WAL database; `probe-output.txt` is its output. With
`PRAGMA locking_mode=EXCLUSIVE`, the first write lock was refused while another
process had the database open as an idle reader, in an open read transaction or
as an idle writer, and was granted once that process was killed. While held,
another connection could neither read nor write, including after the holder's
`COMMIT`. `Connection.backup()` worked from the holder. A process killed
mid-transaction left the old table and row. Rename-old, create-fresh, copy and
drop-old produced the same `sqlite_schema` text as a fresh database and set
`sqlite_sequence`.

One case the lock cannot see: a process that created a connection and never
touched the database holds no file handle and no lock. That is the row's
accepted residual.

## Gate

| Gate clause | Where it is checked |
| --- | --- |
| Fixture migrates with every id and row kept and reopens as ready | `tests/test_database_pair_migration.py` (9 tests), `tests/test_cli_migration.py` (7) |
| A killed migration leaves the old or the new database | `test_killed_migration_leaves_old_or_new_and_the_next_call_finishes`, and the kill trials below |
| A newer database is refused without reset guidance | `tests/test_db_migration.py` (20 tests) and the pair and CLI tests above |
| A format changed without its constant and vector fails | `tests/core/test_format_vectors.py` |
| Migration refuses under another process's claim or open handle; a killed process releases its claim | `tests/test_db_claims.py`, `tests/test_db_migration.py`, `tests/test_database_pair_migration.py` |
| Ordinary suite and import law | 7079 passed, 7 failed, 4 skipped, 35 deselected in 367 s; `lint-imports` 13 kept, 0 broken |

The seven failures are the known interpreter-bound ones: six
`test_bridge_transport_custody*` tests and
`test_native_host_gate_page_keeps_the_probe_in_inert_page_data` (pythonnet
3.1.0 where 3.2.1 is required).

## Kill trials

Written by the independent reviewer and rerun on `880c3ad7`; `kills-output.txt`
is that rerun. `kill_child.py` runs the real `migrate_database_pair` and calls
`TerminateProcess` on itself at a chosen point. `make_large.py` builds a
v0.1.0-shaped ledger with 400,000 more inventory rows, all in a 149 MB `-wal`.
Each trial compares a per-table digest of every released column before the
kill, after it, and after a second, unkilled call.

| Kill point | Trials | Ledger after kill | After the next call |
| --- | --- | --- | --- |
| During backup (fixture and large) | 2 | old; an unpublished `.tmp` remains | current, content same |
| Before the backup rename (fixture) | 1 | old; an unpublished `.tmp` remains | current, content same |
| During row copy, 0.2 s to 3 s in (large) | 3 | old; one published backup | current, content same |
| During `COMMIT`, 0 to 0.05 s in (large) | 4 | old; one published backup | current, content same |
| During `COMMIT`, 0.2 s in (large) | 1 | new | current, content same |
| During or after close (large) | 4 | new | current, content same |

All 15 left the old or the new database and no other state. A kill that left
the old ledger makes the next call publish a second backup.

`e9_rollback_large.py` forces the pre-commit verification to fail on the large
ledger: the result is `refused migration-failed`, the main file is
byte-identical, an ordinary connection still reads schema 4 with 400,030
inventory rows and `quick_check` ok, the content digest is unchanged, and the
next call migrates. The `-wal` grew from 148,736,152 to 295,531,752 bytes: the
rolled-back pages stay in it as a discarded tail.

The reviews also ran mutation checks, fault injection in the backup path (disk
full, `fsync` failure, `SQLITE_IOERR`, `SQLITE_CORRUPT`, a real index
corruption), and swapped, unknown and newer role cases; their findings were
corrected and are covered by the tests above.

## Failure record: drain tests under load (open, outside M2-A3)

Kept apart from the gate. One full-suite run during the last correction round
reported an eighth failure,
`tests/interfaces/web/test_drain.py::test_copied_dispatcher_partial_pause_and_terminal_reconciliation[1-resume]`,
with "DID NOT RAISE ValueError". The next full run, with no edit between, and
the final gate run above showed only the known seven. Run alone, the test's
four cases passed 48 of 48.

- **That message was not reproduced and is unexplained.** The test and its
  helpers contain no `pytest.raises(ValueError)`, and no test in the tree
  expects `ValueError` inside a thread target, so the message cannot have come
  from the test it was attributed to. It was observed once, as a builder's
  report of its own run; no log of that run was kept.
- **What did reproduce** is a deadline miss under load. `stress_drain.py`
  repeats the 17 neighbouring cases while parallel `test_drain.py` runs load
  the machine.

  | Code under test | Loaders | Rounds with a failure |
  | --- | --- | --- |
  | Candidate, with other experiments also running | 12 | 6 of 30 |
  | Candidate | 12 | 3 of 30 |
  | `37187dea`, before the claim and migrator work | 12 | 1 of 30 |

  Every failure was one of the tests' own deadline messages: "session did not
  reach terminal truth" (limit 5 s), `started.wait(5)` false, or "terminal
  task record was not drained" (8 polls of 0.1 s). The sample does not show a
  difference between the candidate and the earlier commit.
- **Checked and excluded:** delays of 1 s on the candidate's one new ledger
  read at session admission, and of 0.5 s on every claim acquire and every
  claim release, each left all 17 cases passing. `test_drain.py`, `drain.py`
  and the inventory fixtures are unchanged by this row's commits.
- **Disposition:** open. The deadline misses predate M2-A3 and no fix was made.

## Rerun

Copy the scripts to a folder two levels below `build/` (they find the
repository as their third parent) and run them with the project venv:

- `probe_exclusive.py` needs nothing else.
- `make_large.py`, then `e3_kills.py small backup-large copy commit close`,
  then `e9_rollback_large.py`. About 12 minutes; the scratch folders hold
  several copies of a 149 MB ledger while it runs.
- `stress_drain.py <rounds> <loaders>`.
