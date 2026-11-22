# Latest session — agent procedures and tools layout, 2026-11-23

Branch `refactor/procedures-and-tools` (from `main` at `7b2b014f`, not pushed or
merged) splits the working rules and reorganizes `tools/` in small commits.

## Changes

- AGENTS keeps only always-on rules (269 → 137 lines) and a trigger table for
  `docs/procedures/`: SCOPE (scope, findings, recurrence, recovery, sibling
  analysis), CLOSEOUT (commits, session boundaries, evidence retention moved
  from PERFORMANCE) and DOCUMENTS (subject ownership merged from AGENTS,
  ARCHITECTURE §7 and DEFENSE §8; changelog rules). CLAUDE.md lost its stale
  "Windows Rules" pointer and duplicated HANDOFF line. README indexes every
  active subject document, including six that were missing.
- Header maintenance instructions in BUGS and CHANGELOG stay local by the
  user's decision (local copies keep compliance up); an early commit that
  replaced BUGS's with links was reverted.
- `tools/` folders: `harness/` (rigs, seams, sidecar, corpus), `settlement/`
  (`audit.py`, `baseline.json`), `performance/` (unchanged; `br_g_42.py` is now
  `release_timing.py`, schema IDs unchanged), `packaging/`, `repo/` (bugs,
  evidence, icons) and `desktop/` (`gui.ps1`, `headed_background.py`).
  `python -m tools ...` is unchanged; direct commands follow the new paths.
- import-linter analyzes `tools` too; a new contract limits `tools.harness` to
  core, modules and `workflows.selection`. A new test pins the corpus guard to
  the whole checkout.

## Verification

- Ordinary suite: 6,588 passed, 4 skipped, 8 failed. Seven failures (five
  `test_bridge_transport_custody`, the live custody check and
  `test_native_host_gates` page probe) fail identically on `main`: the local
  `.venv` runs CPython 3.13.17, outside the frozen 3.15.2 custody qualifier,
  and has a 3.1.0 dependency where 3.2.1 is expected. The eighth was residue
  from this session's deliberate wrong-depth corpus mutation check; after
  removing it the corpus tests pass (38 passed, 1 skipped). `--dept tools`
  passed earlier (504 passed, 3 skipped).

- `lint-imports`: 13 contracts kept; a probe `import namisync.db` in the harness
  broke the new contract. `tools.settlement.audit check --repeat 3` passed
  (30 scenarios × 3). `tools.repo.evidence check`: 38 records, zero problems.
  A scratch link checker over active Markdown: 453 relative links and anchors
  resolve. `git diff --check` clean.

## Open items

- `tests/interfaces/web/` is untouched apart from import/path updates: the
  gate-coded `m1_7_*`, `m1_8_*`, `m1_9_*` and `r3_*` JSON files (about 16 read
  by no test) await review and compaction before any move to `evidence/`. The
  execution receipt/UI scale tests dropped their `m1_8_` prefix. Frozen
  `sh_g_8_*` custody artifacts must not be renamed.
- Pending user decision: ARCHITECTURE §7 and DEFENSE §8 now point to
  DOCUMENTS instead of keeping their own ownership lists, and PERFORMANCE
  points to CLOSEOUT for retention. Restore local copies if they matter for
  compliance the way the BUGS and CHANGELOG headers do.
- The local `.venv` is not on the selected release interpreter (3.15.2); rebuild
  it per TOOLS' portable build preparation before relying on custody or gate
  results locally.
- Proposed, not built: Markdown link/anchor test, commit-subject check,
  changelog structure test, advisory `python -m tools closeout`.
- Carried over: four `build/` folders with Codex-sandbox pytest residue and 55
  empty `build/move-history-20260925/` folders need an elevated
  `Remove-Item -Recurse -Force`; keep `build/inventory-cold/` and the icon
  archive. Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir\source`/`target`
  and `dist/v0.1.0/` (final package `b0a3fe13` / Package05).
