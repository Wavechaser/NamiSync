# NamiSync Session Handoff

Date: 2026-07-24

## Session Outcome

M1 Stage 1 (contracts and semantics) is implemented on `milestone1`.
The work removes misleading M0 settings/concurrency semantics, activates the
single pre-release database boundary, adds the two correctly owned settings
stores, and proves the security-sensitive WebView2 bridge shape. Active
documentation now distinguishes this landed foundation from Stages 2-6.

No user database was deleted in this session. Normal startup never deletes a
database. During the temporary pre-migrator period, an old schema tells the
user to close NamiSync and manually delete/reset both configured database files.

## Changes

- Removed `worker_count` from `SyncOptions`, `Plan`, capacity validation,
  policy/plan fingerprints, planner construction, tests, and workflow
  payloads. Payload schema version 2 rejects version 1.
- Removed `SettingsReader`, `StaticSettingsReader`, live settings fields from
  `ObservedWorld`, and `FILTER_DRIFT`/`OPTIONS_DRIFT`. Fresh preflight now
  observes filesystem/volume safety only; admitted execution consumes the
  immutable reviewed plan snapshot.
- Added the standard-library-only `StreamingHasher`/`HasherFactory` core seam.
  Declared the installed `xxhash` line as `xxhash>=3.8.1,<4` in
  `pyproject.toml`.
- Activated ledger schema v2 and history schema v3. Ledger v1 and history v1/v2
  are refused without changing the old schema, content, journal mode, or
  sidecar state. Removed the old history v1-to-v2 migrator.
- Added the explicit development/test-only `reset_databases()` procedure, which
  validates distinct exact paths and recreates both current schemas. No startup
  or composition path calls it.
- Replaced operation-only history storage with v3 `history_items` carrying
  `item_type` and `phase`, and reserved `history_phases`. The current sync
  observer writes `operation`/`execute` items only and writes zero phase rows;
  the typed sync repository remains compatible.
- Added `db/settings.py`: strict schema-versioned semantic defaults, immutable
  planning capture, hidden-mirror rejection, atomic replace, and a deterministic
  Windows named mutex around partial read-modify-replace commits.
- Added `interfaces/ui_state.py`: separate source/target recents capped at five
  plus cosmetic window/column/sort state, with strict JSON validation and
  atomic replacement.
- Added `interfaces/web/security_spike.py`: forced `edgechromium` startup,
  actionable missing-WebView2 failure, native `CoreWebView2`
  `NavigationStarting`/`NewWindowRequested` guards, exact-origin recheck on
  every call, and one strict versioned allowlisted `dispatch` returning only
  structured JSON-safe data.
- Updated README/changelog and the active architecture, command-line, core,
  database, executor, features, hash, history, interfaces, M1 plan, planner,
  preflight, scanner, verifier, and workflow documents.

## Adversarial Review

The review checked requirement drift, hidden mutations, bridge/XSS boundaries,
cross-process lost updates, import direction, and speculative seams.

- Found and fixed an old-schema refusal weakness: opening through a writer first
  could persist WAL mode. Existing databases are now inspected read-only before
  any writer configuration, with regression checks for journal mode and absent
  WAL/SHM artifacts.
- Tightened bridge and UI-state validation to reject nested non-string object
  keys, non-finite numbers, and Python's nonstandard `NaN` JSON input.
- Converted `managed_roots` to a tuple before coordinated reset validation so a
  one-shot iterable cannot leave the history path unchecked.
- Confirmed `reset_databases()` has no production caller, the retired settings
  and worker-count symbols have no package references, and core has no
  third-party imports.
- Kept nominal integrity result/event producers and compound continuation code
  out of Stage 1; their first consumers belong to Stages 3 and 4.

## Verification

- Focused Stage 1 suite: `164 passed`.
- Full suite: `329 passed in 11.16s`.
- Import Linter: 45 files / 138 dependencies; all 7 contracts kept.
- `git diff --check`: no whitespace errors; only expected LF-to-CRLF notices.
- Static searches found no package references to `worker_count`,
  `SettingsReader`, `StaticSettingsReader`, `FILTER_DRIFT`, `OPTIONS_DRIFT`, or
  retired live-settings fields.

## Immediate Next Context

1. Stage 2 Track 1 comes first. Validate the fixed chunk bands and record the
   required synthetic workload measurements before changing the native copy
   pipeline/finalization path.
2. Stage 2 Track 2 then switches `ContentEvidence`, `CopyDigest`, executor,
   verifier, repository reconstruction, and fixtures to 16-byte `xxh3_128` as
   one atomic change using the already declared dependency and core factory
   seam. Current content producers intentionally still use SHA-256.
3. Recreate both development databases at the Track 2 evidence switch even
   though the final version numbers/shapes are already v2/v3; otherwise
   SHA-256 evidence written during this transition could remain in a current-
   version ledger. Do not add mixed-algorithm compatibility or a second schema
   bump.
4. `SemanticSettingsStore` is not yet wired into a facade/planning action;
   Stage 5 should snapshot it while constructing a new plan request. Execution
   must never receive the store. `UiStateStore` remains interface-only.
5. The WebView2 module is a dependency-free spike, not a desktop host:
   pywebview/frontend assets/event drain/CSP/DOM rendering arrive in Stage 6
   and must preserve its one-method structured bridge and native guards.
6. History v3 is storage reservation only beyond current sync operations.
   Stage 3 adds nominal integrity items without phase summaries; Stage 4 adds
   compound phase summaries without another schema migration.
