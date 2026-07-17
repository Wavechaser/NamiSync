# NamiSync Handoff

## Changes

- Aligned `AGENTS.md` directory and dependency rules with the newer
  `ARCHITECTURE.md`: `core`, `modules`, `db`, `workflows`, `dispatcher`, and
  `interfaces` now have explicit responsibilities and import directions.
- Standardized the Python package spelling on `namisync` across active docs,
  imported PoC references, and the UI mockup. The `nami-sync` executable name
  remains hyphenated by design.
- Added empty package boundaries for every architecture layer and changed
  setuptools configuration to discover all `namisync*` packages.
- Added import-linter contracts that enforce the architecture's direct and
  indirect dependency restrictions, including independence between operation
  modules.
- Added a pytest smoke test that imports the canonical package and all layer
  packages, giving the repository a real green test baseline.
- Ignored generated `*.egg-info/` metadata and documented the import-boundary
  command in `README.md`.
- Repaired the moved `.venv`: its metadata and the `pip`, `pytest`, and
  `lint-imports` launchers now reference `F:\GitHubRepositories\NamiSync`.

The pre-existing architecture revisions that split observation from preflight,
split reviewed sync into plan and execution sessions, define M0 history, and
clarify dispatcher persistence were preserved. This session changed only the
stale underscored module spelling in that document.

## Verification

- `.\.venv\Scripts\python.exe -m pytest` — 1 passed.
- `.\.venv\Scripts\lint-imports.exe` — 7 contracts kept, 0 broken.
- A temporary sibling-module import broke the independence contract as
  expected; the probe files were removed before the final clean lint run.
- `.\.venv\Scripts\python.exe -m pip check` — no broken requirements.
- Setuptools discovery returned `namisync` plus all six architecture
  subpackages.
- `git diff --check` — no whitespace errors.

## Immediate Next Context

- No sync behavior has been implemented; the next architecture step is M0 core
  contracts.
- `docs/ARCHITECTURE.md` still contains the user's unstaged structural edits;
  do not discard or rewrite them.
- Generated `namisync.egg-info/` remains local but is now ignored by Git.
