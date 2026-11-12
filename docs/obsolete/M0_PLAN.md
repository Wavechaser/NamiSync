# M0 Plan (Retrospective Criteria Archive)

Compiled retrospectively on 2026-08-27. This is historical material, not a
contemporaneous M0 plan, current implementation guidance, or proof that every
listed gate passed.

## Provenance And Authority

The per-module documentation family began in commit
`98ba89d59640b9c22d661ef983121fea73260f01` (2026-07-17). This compilation
preserves each component's `Acceptance Criteria` section through end of file
from the pre-M1 snapshot
`5b6a0013098f4e73febd6630831daeaa40abc686` (2026-07-21), the parent of the
`170237b` commit that introduced `M1_PLAN.md`. It includes the original database
future-gate and recorder latent-batching qualifiers, and the trailing scanner,
planner, and preflight M0 verification notes. Historical test counts and
verification statements below are source text, not a new signoff.

Extraction used `git show <source-commit>:docs/<COMPONENT>.md`, starting at the
exact `## Acceptance Criteria` heading and retaining the rest of each file.
Source paragraphs and bullets are unchanged; only heading depth is adjusted to
nest the excerpts below. Inline paths, component filenames, and references to
surrounding text such as "above" retain their original repository context, not
a path relative to this archive. The excerpts contain no Markdown links that
need rebasing.

The inherited appendices at `bba64ec` also contained post-M0 amendments. Those
later additions are not relabeled as M0 here. Current facts remain in active
component prose and applicable M1/H2 plans; the exact removed appendices remain
available in Git as `bba64ec:docs/<COMPONENT>.md`. In particular, the current
verifier frozen-clock progress contract remains in its active owning document,
not in this M0 compilation.

Current authority is [CORE](../CORE.md), [SCANNER](../SCANNER.md),
[PLANNER](../PLANNER.md), [PREFLIGHT](../PREFLIGHT.md),
[EXECUTOR](../EXECUTOR.md), [VERIFIER](../VERIFIER.md),
[DISPATCHER](../DISPATCHER.md), [DATABASE](../DATABASE.md),
[RECORDER](../RECORDER.md), [WORKFLOWS](../WORKFLOWS.md),
[COMMANDLINE](../COMMANDLINE.md), [INTERFACES](../INTERFACES.md), and
[INVENTORY](../INVENTORY.md), together with the applicable active plans.
Those links identify current contract owners; they are not archival signoff.

## Known Supersessions

These examples explain known conflicts without repairing the preserved source
text or claiming an exhaustive compatibility map.

- Superseded: the historical executor directory-cleanup criterion rejects
  identity-less directories. Current authority:
  [executor directory cleanup](../EXECUTOR.md#delete-and-directory-cleanup).
- Superseded: the historical executor criterion says copy leaves
  `last_verified_at` unchanged. Current authority:
  [verifier evidence freshness](../VERIFIER.md#baseline-and-re-baseline).
- Superseded broad claim: the historical scanner criterion treats disappearing
  entries as incomplete without qualification. Current authority:
  [scanner scope semantics](../SCANNER.md#completeness-and-scope).
- Superseded: the historical dispatcher criterion round-trips opaque blobs
  through the store. Current authority:
  [dispatcher session store](../DISPATCHER.md#session-store).
- Later M1 amendment, now superseded: the removed `bba64ec` workflow appendix
  described an open durable UPDATE/MOVE_UPDATE sub-step limitation. That text
  is absent from the pre-M1 excerpts below. Current authority:
  [executor control handling](../EXECUTOR.md#cancellation-pause-and-failure).

## Scope

Only the 13 inherited component acceptance tails below are compiled here.
INGEST remains a latent feature outside M0/M1 and is not relabeled as an M0
delivery gate. Current M1 history/desktop gates, executor settlement authority,
and protected measurement contracts remain active and are not moved here.

## CORE

### Acceptance Criteria

- Exhaustive tests prove every legal session edge and reject every other edge
  without changing state.
- Every session path—success, refusal, cancellation, exception, and later
  interruption—produces exactly one terminal from the core runner; pause
  produces none until that same session resumes and terminates.
- Concurrent event emission yields gap-free monotonically increasing sequence
  numbers per session and no sequence sharing across sessions.
- Event serialization round-trips every body and rejects unsupported schema
  versions explicitly.
- A slow-subscriber stress test proves timeout-bounded history backpressure,
  degrades `audit` on timeout/failure, ejects an overrun non-history reliable
  subscriber with `Gap`, and never silently loses an event while claiming OK.
- Unicode corpus tests preserve NTFS-distinct paths and normalize separator and
  ordinary case variants identically.
- Path tests reject drive, UNC, device, traversal, NUL, mixed-separator escape,
  and reparse-root escape cases while accepting valid long relative paths.
- UTC/DST boundary tests prove all core timestamps are aware UTC values.
- Attestations cannot be constructed without algorithm, digest, provenance,
  subject stat evidence, and observation time.
- A changed selection invalidates a `Commitment` even when the plan fingerprint
  is unchanged; uncommitted and mismatched execution sets are unexecutable.
- `recording` and `audit` can degrade independently without rewriting a
  successful filesystem terminal; terminal-finalization fault injection proves
  the audit axis reflects failure to write the final history envelope.
- Cancel/pause fault injection preserves earned item results and continuation
  state through the runner; pause emits no terminal and exception surfacing
  cannot trigger a second terminal.
- `Disposition` round-trips and distinguishes `CANCELED+UNRUN` queue discard,
  `REFUSED+UNRUN`, and work that actually ran.
- Import-linter proves `namisync.core` imports no project layer.

## SCANNER

### Acceptance Criteria

- A clean tree returns `complete=True`, stable deterministic ordering, all
  regular files, every walked directory as `DirRecord`, and every unsupported
  entry as `UnsupportedRecord`.
- Permission denial, disappearing entries, and enumeration errors are retained
  as warnings, return the reachable snapshot, and force `complete=False`.
- A junction to an ancestor, sibling, or another volume never recurses twice or
  escapes the root; cycle tests terminate within the entry-step bound.
- Placeholder tripwire tests prove no content handle is opened and no hydration
  occurs.
- Exact-ignore regression tests retain `customer.db`, `my.synctmp-notes.txt`,
  and sidecar-like user files while excluding configured ledger/history/WAL/SHM,
  exact temp grammar, and `.synctrash` artifacts.
- Cancellation is observed within one directory/file enumeration step. Scanner
  registration refuses pause cleanly because scan has no continuation.
- Case-collision and multi-link/duplicate-identity cases are reported without
  merging records.
- exFAT/FAT fixtures report coarse timestamp granularity and no stable identity;
  NTFS fixtures and the real native walk report usable identity when the OS
  supplies it, including directory-entry omission fallback.
- Every file/directory carries attributes and creation-time metadata; scans do
  not vary by mapping role or preservation policy and never enumerate ADS.
- Capability fixtures prove `supports_hardlinks` follows the authoritative
  volume flag independently of filesystem-name assumptions.
- Long paths above legacy `MAX_PATH` scan successfully without truncation.
- An offline volume never returns a complete empty snapshot and never causes a
  missing sweep.
- A scoped refresh of two paths performs no full walk and cannot mark a third
  row missing.
- Import-linter proves scanner code imports core but no sibling module.

### M0 Verification

`tests/test_scanner.py` contains 15 focused scanner tests. Shared path and
artifact-grammar coverage lives in `tests/test_core_scanplan.py`; the complete
suite and import-linter are the release gates.

## PLANNER

### Acceptance Criteria

- Repeated serialization of identical inputs is byte-identical, including ids,
  ordering, reasons, summaries, and assignment.
- Randomized input ordering produces the same plan.
- Nested empty directory fixtures create every level parent-first and an
  immediate rescan/replan converges to no mutations.
- Non-empty parent chains also produce explicit metadata-bearing mkdirs, and
  every file/child operation depends on its nearest created parent.
- Renamed-directory fixtures decompose into per-file moves, mkdir dependencies,
  and safe emptied-directory cleanup; UI grouping does not change executable
  operation ids or dependency order.
- Target directories emptied by same-plan operations receive safe dependent
  cleanup; nonempty/unselected directories never do.
- Additive emits no target-only mutation; trash is default; mirror is rejected
  unless internal authorization is explicit.
- Every operation path passes core validation, remains under its root, and
  supports long destination paths.
- Stable-identity-less, duplicated-identity, multi-link, ambiguous prior
  correspondence, and cross-location cases emit no move.
- Persisted paired-noop evidence enables an unambiguous later rename to plan a
  target-side move.
- Move-update has one operation id and no intermediate state that can be
  recorded as final success.
- Same-side case collisions and file/directory collisions are blocked and
  visible; one-to-one case and NFC/NFD spelling mismatches are non-blocking
  typed advisories whose underlying update/no-op work remains executable.
- Default planning preserves target spelling. Opt-in source-basename casing is
  fingerprinted, survives workflow-payload round trips, and emits a zero-byte
  same-key `recase` only when matching metadata makes content replacement
  unnecessary. The payload field is required because omitting a fingerprinted
  policy input cannot be losslessly defaulted during decode.
- Incomplete source or target scans yield a reviewable full plan whose workflow
  selection admits copy/update/mkdir/noop/recase and withholds move/move-update/
  trash/delete; preflight refuses any caller that reintroduces withheld
  operations.
- Capacity property tests never undercount any allowed worker schedule and use
  the exact same function as preflight.
- No-hardlink update fixtures include displaced-version backup bytes under every
  allowed worker schedule; hardlink-capable fixtures do not charge content bytes
  for the link itself.
- Filter application is symmetric; excluded retained rows are not planned as
  missing/deleted, and the filter snapshot is serialized.
- A readonly/hidden/system-only difference with unchanged size and mtime plans
  an update and propagates through the real sync workflow.
- Destination policy collision and companion-group property tests produce
  deterministic, unique, reviewable assignments.
- Planner tests use no filesystem/database fixture, proving purity.
- Import-linter proves planner imports core but no sibling module.

### M0 Verification

`tests/test_planner.py` contains 31 filesystem-free planner tests covering
random input order, byte-identical serialization, directory convergence,
cleanup dependencies, move disqualifiers, policy collisions, symmetric
filters, case/NFC advisory behavior, long paths, and hardlink-aware capacity.
Payload and native rename coverage proves the latent recasing seam; a
reviewed-sync regression proves changed content is not suppressed by a casing
advisory and default target spelling is retained.
Shared path/serialization contracts are covered in
`tests/test_core_scanplan.py`.

## PREFLIGHT

### Acceptance Criteria

- Pure-preflight tests run with no filesystem object and cover every refusal
  combination without mutation.
- Read-only harness proves observation creates, deletes, renames, hydrates, or
  writes nothing.
- Instrumentation proves observation stats only selected touched paths and
  required parents/roots; an unrelated change never refuses the plan.
- Incomplete-scan copy/update/mkdir/noop/recase selections pass, while any
  manually selected move/move-update/trash/delete is refused with the
  applicable source/target completeness code.
- A manually selected operation overlapping blocked correspondence is refused;
  ordinary workflow selection quarantines it before commitment.
- Source drift, target drift, type change, identity change, destination
  appearance, root swap, volume clone ambiguity, filter drift, and dependency
  break each yield typed refusals.
- Same-volume, contained, writable trash passes; reparse, off-volume, readonly,
  and unresolved trash fails before mutation.
- Capacity boundary/property tests agree with planner for full and partial
  selections, include no-hardlink backup copies, and count only prior-run exact
  regular-file temps in the same touched-parent scope execution sweeps; current
  run, lookalike, untouched-parent, off-volume, and `.synctrash` entries are
  excluded.
- Review, immediate execution, resume, and queue wakeup return identical
  verdicts for identical snapshots and fresh different verdicts after drift.
- Refusal leaves plan, selection, statuses, filesystem, and ledger byte-for-byte
  unchanged.
- Missing or mismatched plan/selection commitment is refused by execution entry
  before observation; ordinary review preflight remains usable without one.
- A test changes an unrelated file between plan and execution and still passes;
  a touched file change refuses.
- Long-path and root-escape cases are judged through canonical validated paths.
- Import-linter proves preflight imports core but no sibling module.

### M0 Verification

`tests/test_preflight.py` contains focused pure-verdict and instrumented
observation tests proving selection-aware completeness, blocked-correspondence
defense, scoped reads, fresh-world behavior, run-aware exact temp accounting,
retained recovery scope, and no managed-data mutation.

## EXECUTOR

### Acceptance Criteria

- Fault injection before/after every state-machine step proves no partial file
  is published, no success is recorded early, and every owned artifact is
  recoverable without touching user lookalikes.
- Copy/update publish is same-volume atomic; target bytes are either the complete
  prior version or complete new version, and the displaced version exists in
  exact run trash before replacement publishes.
- Fault injection between hardlink/copy-backup, readonly clearing, replace,
  metadata, flush, and record leaves a recoverable state; an interrupted
  hardlink backup is a documented `nlink>1` warning and rerun converges.
- On a no-hardlink target, backup fault injection leaves only an exact temp or a
  complete published trash version; restore ignores the former and capacity
  includes its content bytes.
- Source mutation during any chunk or before final stat fails the operation and
  records no digest/attestation.
- Opt-in ACL copy failure fails before publish and leaves the prior live target
  untouched. ADS has no M0 acceptance case because the policy is not exposed.
- Target appearance/change after preflight but before mutation is detected by
  the final guard when it occurs before that guard. Faults injected between
  guard and touch prove only the condition owned by the mutation primitive:
  non-replacing rename rejects destination appearance and `RemoveDirectory`
  rejects nonempty directories. Source-object swaps are rejected only by an
  explicitly handle-bound mutation; otherwise they remain inside the disclosed
  external-writer boundary. Update fault injection proves an external swap may
  replace the swapped file without trashing it but cannot create a false ledger
  attestation or publish partial bytes.
- First blocked/failed work does not abort later independent operations; broken
  dependents receive explicit outcomes.
- Exact temp recovery removes prior-run regular files only from preflight's
  touched-parent scope; current-run temps, substring lookalikes, exact-name
  directories, untouched parents, off-volume mounts, and `.synctrash` survive.
  Cleanup failure stops before copy allocation or publication after preflight
  credited those bytes.
- Trash cannot escape through reparse points, cross volumes, overwrite a trash
  collision, or degrade to copy-delete.
- Move occupancy, vanished-old-path, wrong type, and retained-missing-row cases
  produce correct filesystem and recorder outcomes without rolling back other
  earned records.
- Recase preserves target identity/metadata and requested basename spelling,
  transfers zero bytes, creates no trash, rejects source/old-target drift, and
  cannot overwrite a distinct destination.
- Directory create/delete tests cover full chains, wrong types, nonempty races,
  no recursive unplanned deletion, and metadata application only after every
  child operation has settled; every created empty or non-empty directory comes
  from its own reviewed `DirRecord` operation.
- Same-run trash/move cleanup tolerates only directory mtime/link-count churn,
  rejects replacement and identity-less directories, and removes only when
  `RemoveDirectory` confirms emptiness.
- Native NTFS parent-directory flush succeeds with a writable directory handle;
  injected refusal remains an honest per-operation durability warning.
- No-op drift cannot refresh identity, last-seen, hash, or correspondence.
- Multi-GiB simulated copy cancellation and pause occur within one configured
  chunk; pause persists completed status, emits no terminal, releases custody,
  and resume performs fresh preflight at the back of the queue.
- Progress totals equal copy/update content bytes exactly and remain monotonic;
  event rate stays under the configured bound.
- Transient sharing violations retry within bound, including update replace and
  move-update old-to-trash failures after an earlier sub-step committed;
  persistent locks fail with actionable `sharing-violation` rather than false
  drift/occupancy and do not hang the session.
- Copy-stream evidence is tagged `copy`, target identity comes from post-publish
  stat, and `last_verified_at` remains unchanged until real verification.
- Recorder failure test preserves the successful filesystem result, reports the
  ledger-behind condition, and permits later reconciliation.
- All volume locks and open handles release on success, refusal, cancel, policy
  stop, recorder failure, and unexpected exception.
- Immediate rerun after success, crash recovery, or partial failure converges to
  an accurate no-op/remaining-work plan.
- Import-linter proves executor imports core but no sibling module.

## VERIFIER

### Acceptance Criteria

- Stat-changed content is `modified`; only stat-stable digest divergence is
  `mismatched` across a full classification matrix.
- Null-hash verify is `baselined`, stores verify provenance, and does not claim a
  prior verification match.
- Copy-stream-only evidence never sets or renders `last_verified_at`.
- Missing, unsupported, canceled, and read/error paths each emit one item result
  and no unsafe write.
- Drift between pre-stat, hash, post-stat, and recorder call causes the
  conditional write to affect zero rows.
- Reappeared first-baseline clears `reappeared_at` atomically; rollback leaves
  both old states intact.
- Selected casing/separator variants resolve by canonical key and never target a
  row from another location.
- Selected refresh observes only selected paths and cannot mark others missing.
- Post-execution scope includes only successful eligible operation ids; manual
  verify cannot mark plan noops executed/verified.
- Cache-honest integration tests prove the declared Windows read strategy or
  produce a disclosed unsupported/deferred outcome.
- Progress emission is throttled under fast-disk simulation and remains
  monotonic; a chunk flood cannot drive full-widget updates per MiB.
- Parallel verifier tests, when enabled, preserve one outcome/write per row and
  respect per-volume worker policy.
- Unexpected SQLite/OS errors still produce an audited activity envelope and a
  truthful terminal.
- Pause after any item count preserves exactly those outcomes/writes, releases
  custody with no terminal, and resume neither repeats outcomes nor skips an
  unreached selected row.
- Cancellation after any item count emits exactly one result for every selected
  row, including in-flight and unreached canceled rows, before runner unwind.
- Import-linter proves verifier imports core but no sibling module.

## DISPATCHER

### Acceptance Criteria

- Import-linter and symbol scan prove dispatcher imports core only and contains
  no domain activity names/methods.
- Exhaustive transition/control tests reject illegal pause/resume/cancel without
  state corruption; pause capability tests accept execution/verify/baseline and
  refuse scan/plan/import by generic registration metadata.
- Disjoint-volume sessions overlap; shared-volume sessions serialize in
  deterministic commit/lock order; cross-process M0 mutation contention is
  actually refused/queued by the OS-level lock.
- Fault injection at admission, lock acquisition, workflow start, every event,
  pause, cancel, terminal, store write, subscriber failure, and teardown releases
  exactly acquired resources and emits one terminal from the core runner.
- Paused session holds no volume lock/open workflow stack and resume starts with
  fresh preflight at the back of the volume queue.
- Progress flood remains bounded/coalesced; history delivery backpressures only
  at a safe boundary until timeout, then degrades `audit`; an overrun
  non-history reliable subscriber gets `Gap` and ejection rather than silent
  loss.
- Late subscription returns current state/tail and exposes sequence gaps.
- Opaque blobs round-trip through store without dispatcher deserialization.
- M0 process restart loses in-memory sessions honestly and requires rescan.
- **M2 gate:** simulated kill marks only orphan running records interrupted and
  safely re-admits pending work; the queue owner is unique across processes and
  remains independent from volume locks.
- Orderly teardown completes without UI-thread deadlock and reports any session
  that could not drain within policy.
- Terminal records survive until explicit close; queued discard is observed as
  `CANCELED+UNRUN` before `drop()` and never requires a dispatcher-to-history
  import or string parsing.

M0 verification covers the non-M2 criteria with named regression/fault tests:
52 focused core/dispatcher tests exercise the transition/control matrices,
concurrency, pause/resume/cancel, pre-pause outcome retention, opacity, bounded
events/audit, store/lock/adapter/observer faults, teardown deadlines, and a real
subprocess holder-kill mutex recovery. The full shared suite and import-linter
remain the release gate because registry adapters and core event types are
cross-module contracts.

## DATABASE

### Acceptance Criteria

Fresh-schema, pragma, read-only, cross-location trigger, canonical path,
volume/rebind, 33k reconciliation, bounded repository query, WAL concurrency,
independent history round-trip, and the additive history v1-to-v2 migration are
covered in the M0 suite. Criteria for retention, general migrations, backups,
exports, and cloud-provider discovery remain future gates rather than current
implementation claims.

- Fresh schemas contain every freeze field, version stamp, index, uniqueness,
  and foreign-key/trigger constraint required above.
- `PRAGMA foreign_keys`, WAL, and busy timeout are verified on every connection
  type; readonly connections reject writes by construction.
- Schema rejects cross-location mapping correspondence despite valid row ids.
- Windows path-key corpus stores NTFS-distinct names separately and ordinary
  case/separator variants as one key.
- Volume mount-letter/label changes preserve location identity; a changed
  filesystem type requires rebind, and simultaneous duplicate identities require
  explicit user choice.
- Complete/scoped/offline inventory reconciliation obeys `INVENTORY.md` and
  scales beyond 33k rows without variable overflow.
- Large mapping/inventory selections use bounded query counts demonstrated by
  instrumentation benchmarks.
- History integrity detail, sync operations, and subject-only activities all
  round-trip through typed repository reads.
- History run envelopes round-trip filesystem status, independent
  recording/audit axes, and `Disposition` without deriving them from detail
  count or text.
- Version-1 history upgrades transactionally to version 2, preserving prior runs
  and initializing `blocked_count` to zero.
- Retention uses a writable connection, canonical time comparison, preserves
  summaries when pruning detail, and is idempotent.
- Concurrent recorder/repository/history access does not lose committed evidence
  or return partial transactions.
- Migration fault injection at backup, each step, validation, and publish leaves
  either the old valid database or new valid database, never a half migration.
- Backup snapshots pass integrity check and rotation never deletes the newest
  sole good backup.
- Databases/settings/backups are refused inside managed/cloud-synced roots unless
  an explicit safe external location policy says otherwise.

## RECORDER

### Acceptance Criteria

The M0-owned criteria below are covered by focused schema, sync, inventory,
integrity, concurrency, repository, and verifier-recorder integration tests.
Workflow result aggregation and executor flush placement are verified by their
own layer tests; bounded multi-operation batching remains latent because M0
commits every command eagerly.

- Static/import tests prove no production ledger write occurs outside recorder
  and schema/migration ownership.
- Every mutation command is preceded by a successful matching filesystem result
  in integration traces; fault injection cannot commit future intent.
- Conditional writes under every drift dimension affect zero rows and return
  `stale` without altering prior evidence.
- Repeating identical run/op commands is a no-op; token reuse with different
  payload is rejected.
- Two disjoint-volume sessions record completely through one serialized writer
  under stress; cross-process contention retries within bound and surfaces final
  failure.
- A late verifier failure preserves earlier committed per-file evidence.
- Flush occurs before each destructive operation, on pause drain, and before
  terminal delivery; crash loses at most the declared batch window.
- Recorder failure preserves the original filesystem `ExecResult` and produces
  `RecordingStatus.DEGRADED` without changing the filesystem terminal.
- Complete inventory over 33k entries and large path selections use bounded
  batches with no SQL parameter overflow.
- Move onto a retained missing row reconciles that row and keeps unrelated run
  writes; location mismatch is rejected by schema.
- No-op recording requires matching source/target snapshots and persists source
  identity correspondence needed for later rename detection.
- Copy-attested digest stores correct provenance and never advances true
  verification time.
- One shared UTC/host runtime produces identical representations across ledger
  and history boundaries.

## WORKFLOWS

### Acceptance Criteria

- Workflow source reads visibly top-to-bottom and contains no signal loop,
  domain operation implementation, raw SQL, or UI import.
- Plan session persists no mapping/settings/user-data mutation and releases all
  custody before review.
- Execution always uses the exact reviewed plan/selection, fresh observation,
  and preflight; drift refuses without mutation.
- A blocked item cannot refuse independent safe work merely by existing in the
  plan; its overlapping target correspondence and dependent operations remain
  excluded.
- Incomplete scans allow guarded copy/update/mkdir/noop/recase work but never
  admit move, move-update, trash, or delete operations.
- No workflow waits for human input; mandatory review is between terminated and
  newly submitted sessions.
- An uncommitted execution or one whose plan/selection no longer matches is
  refused before preflight; queue/script paths can replay but never mint a
  commitment without human review.
- Baseline/verify with no prior inventory automatically inventories then hashes;
  selected verify refreshes only selected canonical paths.
- Location integrity requires only the selected location and never silently
  falls back to another root.
- Refusal, all-noop, partial failure, cancel, recorder failure, observer failure,
  and unexpected exception each preserve truthful typed results and history
  behavior.
- Pause/resume preserves completed execution and verifier-item outcomes and
  fresh-guards remaining work; scan/plan/import refuse pause without losing
  cancelability.
- Linked verify selection equals successful eligible executed operations and is
  handed to UI at the execution-to-verification phase boundary.
- Replay/undo/repair never execute retained historical operations directly and
  always create a new reviewed plan.
- Plan-only option changes invalidate plan but preserve inventory; location
  changes invalidate only state whose identity depends on that location.
- Import-linter proves workflows may import core/modules/db but not dispatcher
  or interfaces.

## COMMANDLINE

### Acceptance Criteria

- Subprocess tests invoke `nami-sync` and `python -m namisync` with real argv for
  every command and compare dispatch/results.
- M0 exposes reviewed `sync` and `history`; default behavior is defined for both
  pre-desktop and desktop installations.
- Plan command/session mutates no files/ledger configuration and releases locks
  before commitment input.
- Execution cannot proceed without a matching plan-and-selection commitment and
  always freshly preflights; queue release accepts already committed sets only.
- Refusal, no-op, safe-subset partial completion, partial failure, cancel,
  mismatch, and ledger-behind return
  distinct documented exit categories and truthful output.
- Ledger-behind and audit-behind output/exit detail are independently testable;
  `CANCELED+UNRUN` renders queued discard rather than in-run cancellation.
- Ctrl+C during multi-GiB simulated copy/import reaches cooperative terminal and
  releases custody.
- Integrity commands with temporary DB overrides write neither real ledger nor
  real history; omission uses documented safe local paths.
- Read-only history runs during active writer; contending mutation follows
  dispatcher volume policy.
- Location-only commands require exactly the selected usable location and never
  require/fallback to a paired root.
- History prints sync operations and integrity/import detail by activity kind,
  including pruned-detail explanation.
- Invalid path, permission, volume ambiguity, stale plan, and capacity refusal
  messages each state the next user action.
- `python -O` retains all runtime guards and behavior.

## INTERFACES

### Acceptance Criteria

- Import-linter proves interfaces import workflows/dispatcher but not
  core/modules/db directly under the agreed composition-root arrangement.
- Equivalent CLI/desktop requests produce equivalent workflow payloads and
  result classification.
- No interface mutation path bypasses dispatcher, mandatory review, preflight,
  executor, or recorder.
- Invalid/unusable paths show a specific next action rather than silently
  disabling everything.
- Refused zero-op, all-noop, partial failure, cancellation, mismatch, and
  ledger-behind states render distinctly.
- Audit-behind is independent of ledger-behind; queued discard renders from
  `CANCELED+UNRUN`, not byte count or free-form reason.
- Event reconnect handles current state/tail/gap without duplicate row outcomes.
- Changing plan selection after review invalidates commitment; neither UI nor
  CLI can submit the stale commitment.
- Action source-of-truth tests cover menu/button/context presentation equality.
- Presentation-selection tests run without modal loops or live filesystem/DB.
- Thread/result callbacks execute on the required presentation thread and raise
  explicit runtime errors on violation even under `python -O`.
- Database override tests write neither ledger nor history to real user paths.
- Read-only history/status remains usable during an active mutating session.

## INVENTORY

### Acceptance Criteria

- A first complete scan creates one role-free location and deterministic rows
  without creating a mapping.
- Complete scans retain every walked directory and one canonical role-free
  observation shape regardless of mapping policy.
- Complete rescan marks only truly unseen in-scope rows missing and preserves
  their hash/stat evidence.
- Incomplete scan and offline volume mark no unseen row missing.
- Scoped refresh changes only requested keys and performs bounded queries.
- Returning missing rows become reappeared; matching verify or explicit
  baseline clears reappearance atomically.
- Acknowledgement/restore changes visibility state without deleting evidence.
- Mapping filters preserve physical rows and cannot turn exclusions into target
  deletion candidates.
- Hashed baseline stats are not overwritten by ordinary observation of modified
  content; verifier classifies it `modified`.
- A location with >33k files reconciles without SQL variable overflow and with
  bounded transaction/round-trip behavior.
- Mapping-state foreign keys/composite checks reject target rows from another
  location.
- Drive-letter/label change resolves the same known volume; filesystem-type
  change requires rebind; simultaneous clone ambiguity requires a choice.
- Inventory queries expose zero/one/many mappings without guessing.
- UI filtering and Plan invalidation cannot clear or mutate inventory state.
