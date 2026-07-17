# NamiSync Handoff

## Changes

- Added thorough draft contracts for every architectural module and the major
  cross-module domains: `CORE`, `SCANNER`, `PLANNER`, `PREFLIGHT`, `EXECUTOR`,
  `VERIFIER`, `INVENTORY`, `HASH_IMPORT`, `INGEST`, `RECORDER`, `DATABASE`,
  `HISTORY`, `DISPATCHER`, `WORKFLOWS`, `INTERFACES`, `COMMANDLINE`, and
  `DESKTOP_UI`.
- Each draft defines responsibility/non-responsibility, inputs and outputs,
  collaborator expectations, atomicity/idempotency/data-safety invariants,
  milestone priority, latent-feature seams, PoC hardening, and acceptance
  criteria.
- Added `DESIGN_REVIEW.md` with 23 unresolved source-contract issues, ordered by
  milestone impact, plus traceability from all 111 PoC bug-log entries to owning
  drafts and regression themes.
- Added the new active documentation set to the root `README.md` index.

No product code or authoritative `FEATURES.md`/`ARCHITECTURE.md` contract was
changed in this session. The drafts explicitly flag unresolved issues rather
than silently overriding those sources.

## Highest-Priority Review

Resolve these before M0 mutates user files:

1. Mandatory review versus `run_unattended_sync`/unattended ingest (DR-01).
2. Pause checkpoint blocking versus lock release and fresh resume preflight
   (DR-02).
3. Exactly-one-terminal ownership across every session kind (DR-03).
4. Missing planner correspondence/capacity/current-filter inputs (DR-04 through
   DR-06).
5. Source-versus-target attestation identity and trash-on-update crash recovery
   (DR-07/DR-08).
6. Reliable event capacity, volume identity, unsupported scan representation,
   Windows directory durability, and real M0 cross-process volume custody
   (DR-09 through DR-13).
7. Root-aware `ObservedWorld` keys and a typed metadata-preservation snapshot
   (DR-21/DR-22).

## Verification

- Read all 775 lines of `ARCHITECTURE.md`, 297 lines of `FEATURES.md`, and 551
  lines/111 entries of `PoC_import/BUGS.md`.
- All 17 module/domain drafts contain acceptance criteria and explicit
  collaborator expectations.
- Markdown relative-link check: passed.
- Design-review reference check: 23 defined items, no missing references.
- Encoding/stale-package-name scan over new docs: clean.
- `git diff --check`: no whitespace errors.
- `.\.venv\Scripts\python.exe -m pytest`: 1 passed.
- `.\.venv\Scripts\lint-imports.exe`: 7 contracts kept, 0 broken.

## Immediate Next Context

- Review `DESIGN_REVIEW.md` in its stated order before freezing M0 core types.
- Once decisions are made, update `FEATURES.md`/`ARCHITECTURE.md` first, then
  revise affected module drafts so authoritative and focused docs agree.
- No files were staged or committed.
