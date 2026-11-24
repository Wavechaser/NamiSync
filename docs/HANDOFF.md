# Latest session — commit policy and bug categories, 2026-11-23 – 2026-11-24

`refactor/procedures-and-tools` was fast-forwarded into `main` (22 commits) and
deleted; nothing is pushed. Work then continued on `milestone2`, where a
parallel session committed the M2 documentation start.

## Changes

- AGENTS: commit as you go, in small self-contained units that revert
  independently, staged by path with only the task's files; recovery or `wip`
  commits at a stop are exempt, and push and merge need an explicit request.
  CLAUDE.md now counts committing as part of an edit/implement request.
- BUGS categories are titles that end in a singular mechanism noun. The header
  points to `python -m tools.repo.bugs --mechanisms`, which lists the nouns in
  use with counts, and asks writers to reuse one when it fits. 59 entries whose
  final word named a subject, plural or clause were retitled; the most used
  nouns are now gap 30, conflation 27, omission 26, race 20 and drift 18.

## Verification

- `tests/test_tools_bugs.py` and `tests/test_tools_cli.py`: 102 passed,
  2 skipped, including a new `--mechanisms` test.
- The retitle script parsed all 319 records before and after and confirmed that
  only the 59 categories changed, with every ID and body unchanged; the
  validator reports 319 records. `git diff --check` clean.

## Open items

- Retitling stopped at clear violations. Titles shaped as a flaw adjective plus
  an operation (`Premature custody acquisition`, `Quadratic sequence tracking`)
  were left as coined mechanisms; normalize one when its entry is next edited.
- Frozen `sh_g_8_*` custody artifacts must not be renamed or moved.
- Proposed, not built: Markdown link/anchor test, commit-subject check,
  changelog structure test, advisory `python -m tools closeout`.
- The local `.venv` is not on the selected release interpreter (3.15.2); seven
  custody and native-gate tests fail locally for that reason alone. Rebuild it
  per TOOLS' portable build preparation before relying on those results.
- Carried over: four `build/` folders with Codex-sandbox pytest residue and 55
  empty `build/move-history-20260925/` folders need an elevated
  `Remove-Item -Recurse -Force`; keep `build/inventory-cold/` and the icon
  archive. Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir\source`/`target`
  and `dist/v0.1.0/` (final package `b0a3fe13` / Package05).
