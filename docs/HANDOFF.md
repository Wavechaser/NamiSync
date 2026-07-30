# NamiSync Session Handoff

Date: 2026-07-30

## Session Outcome

Landed M1 Stage 5.5 as four reviewed slices on `milestone1`.

- Tree substrate: pushed `e959341` (`Land Stage 5.5 tree substrate`). Promoted
  the planner's relative-path hierarchy helpers without semantic drift and
  added the pure, deterministic, scope-qualified workflow node tree with an
  addressable root, pre-order parent/depth/subtree indexes, read-only maps,
  direct member ids, on-demand subtree membership, and bottom-up counts.
- Scan scope: pushed `01413d6` (`Land Stage 5.5 scan scope`). Added canonical
  `FULL`/exact `PATHS`/recursive `SUBTREES`, shared full/subtree walking,
  literal indexed subtree reconciliation, inventory payload v2, typed warning
  retention, and narrow subject-local integrity continuation.
- Selection semantics: pushed `bb537db` (`Land Stage 5.5 selection semantics`).
  Added canonical `user_deselected` provenance, direct-vs-dependency outcomes,
  upward reselection closure, strict execution payload v4, authoritative
  selection re-derivation before preflight, empty-selection refusal, and
  kind/reason-based `all-noop`.
- Facade integration: added service-owned selection revision and
  `reviewing → committing → committed` state, recoverable admission failure,
  authoritative risk preview, folder-wide plan gestures, opaque inventory ids,
  recursive refresh and frozen integrity expansion, retry receipts, the four
  missing inventory facade lifts, primitive disposition/warning views, and
  runtime commitment from the frozen user-provenance snapshot.

No database schema or migration changed. `tests/test_cli.py` stayed
byte-for-byte unchanged. Stage 6 projection caches, view ids, paging,
presentation flattening/filtering, progress identity, web transport, and the
headed desktop remain deliberately unimplemented.

## Verification

- Stage 5.5 bridge files: `54 passed in 1.08s`; D integration files alone
  collect 16 named BR-G cases covering BR-G-1, 10, 11, 13–18, 20, 21, 24, and
  29.
- Full repository: `761 passed in 21.78s`.
- Mandatory regression rows: 225, 86, 72, 28, 28, 206, 35, 53, 39, 57, 31,
  22, 9, 60, and 23 tests passed in their exact named groups. XV-19 remains
  deferred because the three Stage 6 web test files do not exist.
- Import boundaries: 49 files / 181 dependencies; all eight contracts kept,
  zero broken.
- Lane B's production query plan uses
  `inventory_location_presence_idx` with constrained location, presence, and
  literal `rel_path_key` range.
- Final `git diff --check` was clean apart from Git's expected LF→CRLF notices.

## Adversarial Findings Closed

- Restored the ordinary-directory guard accidentally lost when the full walk
  was parameterized. Full roots refuse file/placeholder/reparse shapes while
  subtree roots keep their distinct conclusive-file and incomplete-directory
  semantics.
- Preserved Windows no-follow directory-reparse classification through
  `FILE_ATTRIBUTE_DIRECTORY`; otherwise a reparse could be treated as a file
  and permit false missing inference.
- Bound subtree roots into inventory receipts, kept hostile `%`, `_`, and `]`
  names literal, and proved the covering-index range rather than merely the
  index's existence.
- Defeated a circular carried-selection commitment check by re-deriving from
  plan plus provenance on fresh, execute-resume, and verify-resume paths.
- Kept `NOOP` selected work distinct from user-skipped work, made dependency
  closure cycle-safe, and refused unknown or safety-excluded selection ids.
- Protected replan/review and replan/commit races with artifact identity,
  reset selection even when deterministic operation ids repeat, and guaranteed
  an escaping admission exception returns selection to `reviewing`.
- Verified a real service NOOP-only session records items and reports
  `all-noop`, and a real folder verify reports one unreadable frozen subject
  once as `unsupported` while a readable sibling verifies and the facade
  reports `verification-incomplete`.

No unresolved actionable Stage 5.5 finding remains.

## Immediate Next Context

Stage 6 should consume these seams, not replace them:

- Inventory tree scope identity is `str(location_id)`; plan tree scope identity
  is the plan request id. Node ids are workflow-only and never persistence or
  operation ids. `subtree_end` is exclusive; do not pre-materialize descendant
  sets per ancestor.
- `ScanScope.scoped()` is authoritative. No paths/roots and root `""` mean
  `FULL`; exact-only means `PATHS`; any minimized non-root recursive roots mean
  `SUBTREES`. The service already refuses an explicit empty opaque-id
  collection before translation.
- Refresh folder ids become subtree roots so newly created descendants are
  discovered. Integrity folder ids freeze current indexed member rows to exact
  paths before admission. A row id, including a directory row id, stays exact.
- Selection state belongs to `NamiSyncService`. Clients send expected revision,
  never a digest. A recognized command id is a retry; `close_session` releases
  its session receipt and shutdown clears retained state.
- Omitted execution revision exists only for the untouched CLI-compatible
  revision-zero selection. Stage 6 must always send its displayed revision and
  honor named conflict, in-flight, frozen, and confirmation-required responses.
- Stage 6 still owns plan memoization, inventory projection/view-id lifecycle,
  flatten/filter/search/window logic, progress identity/autoscroll, database-
  paged history, web security/transport, task lifecycle, and the scale gates.
