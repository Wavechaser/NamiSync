# Bug Log

Substantive defects found during code review — correctness bugs, silent data loss,
unsafe assumptions, and design gaps with real behavioral consequences. Cosmetic-only
issues are listed only when they masqueraded as something worse. Pure style/naming
observations are excluded.

Format: `- SEVERITY - STATUS. Category. What happened. (cause: why).`

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last point an entry was directly re-verified, not
  necessarily the current code.

**Scope note:** entries are grouped by implementation stage. Later
restructurings can supersede earlier defects; see `docs/phase2.md`,
`docs/phase3.md`, `docs/UI_overhaul.md`, and `docs/handoff.md` for current
behavior and replacement context.
Entries marked **UNCONFIRMED** were last seen at the point noted and were not
re-checked against later code.

---

## SCANNER

### MVP
- SEVERE - FIXED. Silent data loss. Exclude filter matched any file ending in
  `.db`, not just NamiSync's own database, so user `.db` files anywhere in
  source were silently never synced. (cause: generic suffix match instead of
  exact filenames.)
- MODERATE - FIXED. Crash-safety. Unhandled `os.walk` errors (e.g. permission
  denied) could abort the whole scan instead of being recorded. (cause: no
  try/except around the walk.)
- MINOR - FIXED. Availability. Scans had no cooperative cancellation. (cause:
  no cancel check in the walk loop.)
- MODERATE - OPEN. Safety gap. `os.walk` follows NTFS junctions/reparse
  points, risking duplicate traversal or a cycle on drives with mount points.
  (cause: no reparse-point check before recursing.)

### Phase 1 hardening
- MINOR - FIXED. Excludes gap. `history.db`/-wal/-shm were missing from the
  exclude list, so a history DB inside a scanned root could be copied/hashed
  mid-write. (cause: exclude list only covered the main ledger and queue DB
  names.)

## PLANNER

### MVP
- MODERATE - FIXED. False success. Nested empty source directories only had
  their topmost level planned, so deeper empty levels were never created and
  reruns never converged. (cause: `mkdir` reused trash/delete's
  "collapse to topmost" logic, wrong for a full-chain create.)
- MINOR - FIXED. Mirror-fidelity. Target directories emptied by the plan's
  own trash/delete in the same run were left behind as orphaned empty dirs.
  (cause: emptiness check only looked at the pre-run scan, not the plan's own
  removals.)
- MODERATE - OPEN (mitigated by verify mode). Design gap. Same size+mtime
  plans as `noop` even if content differs; normal-run planning stays
  metadata-only by design. (cause: no hash comparison in the plan path;
  verify mode checks content out-of-band, not during planning.)

### Post-MVP
- MODERATE - FIXED. Correctness. Free-space check undercounted multi-update
  growth, risking ENOSPC mid-run on an accepted plan. (cause: formula assumed
  at most one update's temp file exists at a time.)
- MINOR - FIXED. Robustness. `build_sync_plan` called `shutil.disk_usage`
  directly with no error handling. (cause: no guard around the FS call.)
- MINOR - FIXED. Consistency. The free-space formula was duplicated
  independently in planner and executor. (cause: no single source of truth.)

## EXECUTOR

### MVP
- SEVERE - FIXED. Availability. Execution aborted the entire remaining plan
  on the first failed/blocked operation, contradicting the "walk away for
  hours" design goal. (cause: no per-operation continue-on-failure.)
- SEVERE - FIXED (narrowed, not eliminated). TOCTOU. No re-validation between
  plan and execution, so execution could run stale operations against a tree
  that no longer matched the plan. (cause: no re-scan/state comparison before
  mutating; a preflight now checks touched paths, residual TOCTOU is
  inherent.)
- MODERATE - FIXED. Resource leak. Orphaned `.synctmp-` files from a
  killed/crashed run were never cleaned up. (cause: no cleanup pass on the
  next run.)
- MODERATE - OPEN (documented). Crash-safety gap. A changed rename plans as
  `move` then `update`; a crash between them leaves old content at the new
  path while the DB claims "present." (cause: no single-transaction guarantee
  across a move+update pair; self-heals on next metadata mismatch.)
- MODERATE - OPEN (phase2.md proposes a fix). Design gap. Move detection is
  keyed on source-side NTFS identity, not content hash, so a cross-volume
  relocation silently degrades to copy+trash. (cause: chosen for cheap
  disambiguation of duplicate-content bursts; diverges from the spec's
  hash-keyed model.)
- MODERATE - FIXED. Functional failure. Toy-directory testing reported trash
  as the one non-working operation; later file/directory trash tests pass.
  (cause: the original failure was not isolated in the conversation.)
- MODERATE - FIXED. Feature gap. Move/rename operations were not applied to the
  target, so a detected rename could not preserve the existing target file.
  (cause: executor lacked target-side `os.replace()` move handling.)
- MODERATE - FIXED. Availability. Canceling a large copy waited until the
  whole file operation returned, making cancellation ineffective for big files.
  (cause: the copy loop did not poll cancellation between chunks.)
- MODERATE - FIXED. Crash-safety. Published replacements did not fsync the
  parent directory, so a power loss after `os.replace()` could lose the rename.
  (cause: durability covered the file but not its containing directory.)
- MINOR - FIXED. Cancellation semantics. A callback that canceled on its
  second poll canceled before the first operation despite the first poll being
  false. (cause: preflight consumed a cancellation check before the operation
  loop.)
- MODERATE - FIXED. Feature gap. Empty directories were ignored, so source-only
  empty trees were not created and target-only empty trees were not removed or
  trashed. (cause: executor handled regular-file operations only.)
- MODERATE - FIXED. Over-broad check. The first preflight implementation
  compared entire source/target scans for exact equality, so an unrelated
  change anywhere in either tree aborted the whole plan. (cause: preflight
  scope was the whole tree instead of just the touched paths.)
- MODERATE - FIXED. Performance. The first preflight implementation added two
  full metadata walks before execution, noticeably delaying the first copy on
  very large trees. (cause: validation rescanned both complete roots instead
  of statting only operation-touched paths.)

### Phase 1
- SEVERE - FIXED. Destructive over-reach. Orphaned-temp cleanup walked the
  entire target tree every run and deleted any file with `.synctmp-` anywhere
  in its name — a real user file with that substring would be silently
  deleted. (cause: substring match over a full-tree walk instead of scoping
  to the plan's own touched directories and exact temp-name shape.)
- MINOR - FIXED. Cosmetic. Progress/ETA byte accounting counted move/trash/
  delete at full file size, double-counting a moved-then-edited file and
  overstating throughput for near-instant renames. (cause: byte total
  included non-content-transfer operation kinds.)
- SEVERE - FIXED. Unsafe execution. A plan built from an incomplete/errored
  source or target scan could still execute, risking trash/delete of files
  that only looked target-only because an unscanned source subtree hid
  them. (cause: `SyncPlan` carried no "scan was incomplete" signal, so
  neither the GUI nor the executor refused it.)
- MODERATE - FIXED. Trash performance/safety. A redirected or reparse-point
  `.synctrash` could land on another physical volume, turning an intended
  metadata move into a cross-volume failure or copy-plus-delete path. (cause:
  trash placement was not checked against the target volume.)

### Phase 2
- MODERATE - OPEN. Executor. Capacity preflight can loop-refuse indefinitely
  on a nearly-full target because reclaimable orphaned-temp-file bytes are
  not freed before the free-space check runs. (cause: orphaned-temp cleanup
  executes after the capacity check instead of before it.)

## VERIFIER

### Phase 1 hardening
- MODERATE - FIXED. Misclassification. Verify reported a target edited since
  sync as a hash mismatch instead of distinguishing external metadata change
  from metadata-stable bitrot. (cause: it hashed first and compared only the
  digest, without checking the ledger's size/mtime baseline.)

### Phase 2
- MINOR - OPEN. Design gap. An externally-modified baselined file is
  correctly detected and permanently reported "modified," but there is no
  exposed workflow to accept the new content and re-baseline it. (cause: the
  conditional hash-write only fires when no hash is stored yet; no
  accept/re-baseline path exists.)
- MODERATE - FIXED. Wrong-target action. Scoped verification (Verify
  selected / linked post-execution) matched requested paths by exact string
  instead of the normalized `rel_path_key`, so a casing/separator mismatch
  reported a present, correct file as "no present inventory row." (cause:
  the lookup dict was keyed on raw `rel_path` instead of
  `normalize_relative_path`.)
- MODERATE - FIXED. Stale reappearance state. A reappeared file that received
  its first baseline during verification remained flagged `Reappeared` until
  a second verify, making a successful baseline appear ineffective. (cause:
  the backfill path wrote the new hash but did not clear `reappeared_at`.)

## DATABASE

### MVP
- SEVERE - FIXED. Feature gap. The SQLite ledger was fully built but never
  called from the sync pipeline. (cause: nothing wired the DB into planning
  or execution.)
- SEVERE - FIXED. Trust/UX. A DB bookkeeping failure was reported to the
  user as a failed sync, discarding the real successful `RunResult`. (cause:
  inverted the "filesystem is truth, DB commit is best-effort" contract.)
- MINOR - FIXED. Audit accuracy. `runs.started_at`/`ended_at` were both
  stamped after execution had already finished. (cause: timestamps taken
  post-hoc instead of threaded from the actual run window.)
- MODERATE - FIXED. Rename tracking. A scanner `file_id` was computed but not
  persisted or compared, so source renames degraded to copy plus target-only
  cleanup instead of a move. (cause: DB state stored path/size/mtime only.)

### Phase 1
- MODERATE - FIXED. Inconsistent ledger row. Null-hash backfill wrote the
  hash of current content without re-checking the row hadn't drifted, so a
  target edited since last sync could get a baseline hash attached to stale
  metadata. (cause: backfill didn't compare current metadata against the
  ledger before writing.)
- MODERATE - FIXED. Lock contention / all-or-nothing. Verify held one write
  transaction open for the entire multi-hour pass, risking "database is
  locked" against a concurrent sync and losing every earned backfill on one
  late failure. (cause: single commit at the end instead of per-record
  commits.)
- MINOR - FIXED. Side effect. Plan preview (`Scan/Plan`) persisted the root
  mapping and deletion policy even if the user never executed. (cause:
  `configure_root` was called from the plan worker instead of execution
  recording.)
- MODERATE - FIXED. Audit gap. A failed/blocked run on an
  all-noop or capacity-blocked plan wrote no history entry at all. (cause:
  history recording returned early for any plan with zero mutating operation
  kinds, before checking whether the run itself failed.)
- MODERATE - FIXED. Stale evidence. A skipped no-op could refresh ledger
  state (identity, last-seen run) even when source or target no longer
  matched the planning snapshot, risking corrupted move-detection evidence
  or a wrongly retained hash. (cause: the no-op ledger refresh didn't
  re-validate current source/target metadata and file identity against the
  planning snapshot before writing.)
- MINOR - FIXED. Retention fragility. History pruning compared timestamp text
  directly, so a future writer using another valid ISO-8601 offset or precision
  could silently misorder age/count retention. (cause: timestamps were stored
  without normalization at the history write boundary.)
- MODERATE - OPEN (phase2.md proposes a fix). Role coupling. The ledger treated
  every inventory row as belonging to a source/target-root relationship, so a
  single-sided hash baseline had no natural place to persist without inventing
  a mapping. (cause: inventory identity was keyed through role-bearing roots;
  role-free locations/files were not first-class records.)
- MODERATE - OPEN (phase2.md proposes a fix). Referential-integrity gap. A
  mapping-state row keyed only by `target_file_id` can point at a file from an
  unrelated location even though the foreign key and cascade succeed. (cause:
  the schema does not constrain the target file's `location_id` to the
  mapping's target location.)
- MODERATE - OPEN (phase2.md proposes a fix). Retention gap. Keeping missing
  inventory rows preserves useful evidence but can accumulate stale tombstones
  without bound. (cause: no age/manual pruning policy was part of the original
  role-bound ledger.)

### Phase 2
- MODERATE - OPEN. Database/concurrency. Two legitimately parallel
  disjoint-volume runs share one SQLite ledger guarded only by a 1-second
  busy timeout; a completed filesystem run's bookkeeping can silently fail to
  record under contention. (cause: the volume guard serializes per physical
  volume only, not per ledger connection, and the busy timeout is short
  relative to a large recording transaction.)
- MINOR - OPEN. Database/integrity. Executor-confirmed copy/update rows are
  stamped `last_verified_at` from the source-stream hash alone, contradicting
  the documented "not a write-readback verification" caveat, so a row can
  read as verified without ever being read back off target media. (cause: the
  post-execution file-state writer sets `last_verified_at` for any digested
  transfer instead of reserving it for an actual verify pass.)
- MODERATE - OPEN. Database/audit. An unexpected `sqlite3.Error`/`OSError`
  raised inside a guarded baseline/verify run propagates past history
  recording entirely, leaving no audit trail for that failure — asymmetric
  with sync execution, which records history on every path including
  refusal. (cause: the guarded-activity wrapper only catches
  `ValueError`/`VolumeGuardUnavailable` before recording.)
- SEVERE - FIXED. Crash-safety. `mark_unseen_missing` bound one SQL
  parameter per seen file in a single `NOT IN` clause, so scanning/planning
  a location past ~32,765 files raised `sqlite3.OperationalError` and
  aborted reconciliation entirely. (cause: no batching after moving off the
  old 500-item chunking.)
- SEVERE - FIXED. Silent data loss. A move onto a target path already
  occupied by a retained missing row hit the
  `UNIQUE(location_id, rel_path_key)` constraint, rolling back and losing
  every ledger write for the whole run — not just the move. (cause:
  `rekey_after_move` didn't clear a colliding missing row first, unlike its
  sibling `confirm_rename_rekey`.)
- SEVERE - FIXED. Write-through-readonly. `prune_history` opened the
  history database via the read-only connection helper, so every retention
  sweep (startup and "Apply retention") raised "attempt to write a readonly
  database" and retention was never enforced. (cause: used `_open_existing`
  instead of the writable `_open`.)
- MODERATE - FIXED. Misclassification. `observe_file` refreshed a hashed
  row's size/mtime/file_id on every scan, so a legitimately edited
  baselined file was reported "mismatch" (bit-rot) instead of "modified" on
  the next verify. (cause: the metadata write wasn't gated on whether the
  row already carried a hash.)
- MODERATE - FIXED. Audit gap. Retained baseline/verify issue detail was
  written to `history_integrity_issues` but never queried back, so the
  History dialog and CLI always showed "no detail recorded" for integrity
  runs. (cause: `get_history_entry` only read `history_sync_operations`.)
- MODERATE - FIXED. Stale ledger row. A move reported "skipped" (source
  vanished before execution) left the old-path row `state='present'`,
  producing spurious re-verify issues and stale planner evidence. (cause:
  `_record_operation` handled move+succeeded but not move+skipped.)
- MODERATE - FIXED. Audit asymmetry. A volume-guard refusal during
  TeraCopy import raised uncaught instead of recording an error result, so
  refused imports left no history row, unlike baseline/verify. (cause:
  import had its own guard wrapper instead of sharing the baseline/verify
  envelope.)
- MODERATE - FIXED. Lock contention. Per-noop linear scans over the full
  source/target planning snapshots made `record_execution_result`
  O(operations × snapshot size) inside the open ledger write transaction,
  risking minutes-long lock hold on large mirrors. (cause: no
  rel_path-keyed dict built once per snapshot.)
- MODERATE - FIXED. Identity over-merge. `normalize_relative_path` used
  `str.casefold()`, which merges NTFS-distinct filenames (e.g.
  "Straße.txt"/"strasse.txt") into one ledger row, cross-contaminating two
  real files' metadata and hashes. (cause: casefold applies Unicode
  special-casing beyond Windows' simple uppercase table.)
- SEVERE - FIXED. Regression. The O(n²) fix's rewrite of
  `_noop_matches_plan_snapshots` dropped the prior `try/except ValueError`
  guard, so one rel path escaping the root (e.g. via a junction) rolled
  back and lost the entire run's bookkeeping. (cause: guard lost during the
  dict-based rewrite.)
- MODERATE - FIXED. Move-evidence loss. The initial Phase 2 mapping-state
  write rule omitted paired noops, so a file matching from its first sync had
  no persisted source identity and a later source rename planned as copy plus
  trash instead of move. (cause: correspondence writes were limited to
  materially mutating operations even though noop was the only evidence path.)
- MODERATE - FIXED. Reconciliation performance. Inventory reconciliation ran
  an upsert plus a lookup for every scanned file, and path-scoped reads issued
  one query per requested path, causing large inventories to hold the ledger
  guard open for excessive round trips. (cause: `_reconcile_scan` and
  `list_files_at_paths` lacked batched writes/reads.)
- MODERATE - FIXED. Cross-database key drift. Host identity and lexical
  timestamps were formatted independently in the state database, history
  database, and integrity app layer, allowing silent joins or ordering to
  diverge. (cause: duplicated `_host_name()`/`_time()` helpers instead of one
  shared runtime implementation.)

## CLI

### Phase 1
- SEVERE - FIXED. Dead feature. `main()` defaulted to `None` instead of
  reading `sys.argv` when called with no explicit argv, so every real
  invocation (`nami-sync`, `python -m nami_sync`) launched the GUI regardless
  of the subcommand typed — `import-hashes`, `verify`, and `history` were
  unreachable outside tests. (cause: every test passed an explicit argv
  tuple, so nothing exercised the real default path.)

### Phase 2
- MODERATE - FIXED. Test/data isolation. `baseline`/`verify`/
  `import-hashes` never accepted a history database path, so every
  invocation — including the test suite — wrote audit history into the
  real per-user `%LOCALAPPDATA%\NamiSync\history.db`. (cause: no
  `--history-database` CLI argument existed.)

## GUI

### MVP
- MODERATE - UNCONFIRMED. Availability. `_can_execute_plan()` refused to
  enable execution if any single operation was `blocked`, preventing all
  unrelated work in the same plan from running. (cause: block check was
  plan-wide instead of scoped to the blocked operations.)

### Phase 1
- SEVERE - FIXED. Threading/GC. `_release_worker` was wired to every
  thread's `finished`; a stale queued release from a finished plan-worker
  thread could arrive after a new execute-worker started, nulling the only
  Python reference to the live worker and letting it be garbage-collected
  mid-run — task stuck busy forever, Cancel dead, no exception. (cause:
  release didn't check whether the finishing thread was still the page's
  current thread.)
- SEVERE - FIXED. Threading/lifetime. Closing a busy tab removed the page —
  and its parented `QThread` — as soon as `busy_changed(False)` fired, but
  that signal fires from the worker-result handler before `QThread.finished`,
  risking destruction of a still-running thread. (cause: removal keyed off
  the busy flag instead of the thread actually stopping.)
- MODERATE - FIXED. Misleading status. The cross-tab "another task running"
  lock permanently overwrote a task's real status line and never restored it
  once the lock cleared. (cause: the hint was written directly into the
  status label instead of layered over stored status text.)
- MINOR - FIXED. Qt/QSS interaction. Styling a border on `QComboBox` silently
  took over its native arrow subcontrol, making every dropdown's arrow
  disappear. (cause: QSS border rule with no replacement down-arrow image.)
- MINOR - FIXED. Cosmetic. The collapsed one-line breadcrumb header rendered
  at the full height of the multi-row setup form it replaced. (cause:
  `QStackedWidget` sizes to its tallest page by default.)
- MODERATE - FIXED. Perf. Verify posted a queued progress signal per 1 MiB
  chunk, risking thousands of full-widget UI updates per second on fast
  disks. (cause: no throttling on the progress callback.)
- MODERATE - FIXED. Responsiveness. Hash-import had no cancellation, but
  tab/window close unconditionally offered "cancel and close" and waited on
  the thread — closing during a large import hung until it finished on its
  own. (cause: cancellation wasn't threaded through
  `import_teracopy_hashes`.)
- MODERATE - FIXED. Workflow gap. Verify could be started without a current
  plan, but did not refresh/inventory the selected location first, leaving the
  action inconsistent with the scan-driven execution workflow. (cause: verify
  was wired as a plan-dependent action instead of forcing the required
  inventory/plan refresh.)
- MODERATE - FIXED. Stale status. Verification changed the summary but left
  file-list rows at `planned`, so the display claimed a plan state after the
  integrity pass had finished. (cause: verification results were not mapped
  back to per-row status updates.)
- MODERATE - FIXED. Incorrect gating. Manual target verification required both
  source and target folders even though it reads only one selected location,
  blocking valid target-only baseline/verification work. (cause: integrity
  actions reused the paired-sync folder validation.)
- MODERATE - FIXED. Partial-failure reporting. The executor could continue
  independent operations after blocked/failed ones, but the GUI/history path
  did not consistently surface that run as a partial failure. (cause: UI
  completion handling and history bookkeeping treated blocked or non-mutating
  plans as all-or-nothing.)

### Phase 2
- SEVERE - FIXED (self-caught, pre-review). Crash. Constructing the vertical
  tab-bar proxy style from the shared application style crashed the app with
  a Windows access violation. (cause: `QProxyStyle` was given the shared app
  style as its base, which Qt then double-freed.)
- MINOR - FIXED (self-caught, pre-review). Qt/QSS interaction. Vertical tab
  labels stayed rotated 90° despite the new horizontal-card proxy style.
  (cause: `QTabBar::tab` QSS rules make Qt's stylesheet engine render tabs
  directly, bypassing the proxy style's paint logic.)
- MINOR - FIXED (self-caught, pre-review). Cosmetic. The tab close button
  overlapped the card's label text. (cause: Qt positions the close button
  for a rotated tab; the transposed horizontal card geometry wasn't
  accounted for.)
- MINOR - FIXED (self-caught, pre-review). Cosmetic. The "+ New" corner
  button rendered with zero height, effectively invisible. (cause: no
  explicit minimum height was set for the corner widget.)
- MODERATE - OPEN (deferred; accepted as low-impact). Misleading status.
  Manual (non-linked) verify can mark plan-tree `noop` rows "verified" even
  though they were never executed this run. (cause: the manual-verify path's
  operation-id map includes `noop` kind operations, unlike the stricter
  post-execution linked-verify map that is scoped to actually-executed
  successful operations.)
- MINOR - FIXED (later superseded). Stale display. After a linked copy+verify
  completed while the user viewed Inventory, the tree refreshed but the
  affected-size headline stayed stale. (cause: inventory repopulation updated
  the tree but not the size readout; moot once handover was changed to switch
  views outright.)
- MINOR - FIXED. Wrong-target context menu. Right-clicking an inventory row
  acted on whatever row was previously selected rather than the row under the
  cursor, contradicting standard Windows right-click behavior. (cause: the
  context-menu handler read the existing selection instead of selecting under
  the click point.)
- MODERATE - FIXED. Missed handover. After an exec+verify run finished, the
  page stayed on the Plan view until verification had finished instead of
  switching to the freshly populated Inventory view at the execution-to-
  verification handoff, so users saw stale plan state during verification.
  (cause: the linked verifier did not emit its committed inventory before
  hashing, and the UI only rendered/switched from the final completion path.)
- MINOR - FIXED. Layout jitter. Task-rail card heights grew once source/target
  path and date strings appeared instead of staying constant. (cause: an
  empty label's size hint falls back to the base font and ignores the
  filled-label QSS font-size rule, so empty vs. filled cards measured
  different heights.)
- MINOR - FIXED. Cosmetic-as-bug. The Exit menu action displayed a bogus
  `[Exit]` string as its shortcut instead of a real key sequence or none.
  (cause: the standard "Quit" key sequence resolves incorrectly through the
  int-constructor path on Windows and has no standard binding there anyway.)
- MINOR - FIXED (unverified, self-reported). Progress display. The live
  throughput/ETA line did not render for roughly a second after a transfer
  began, until a whole-run average rate could be computed. (cause: the line
  was gated on having a computed rate instead of shown immediately with a
  deferred number.)
- SEVERE - FIXED. Qt thread affinity. Acknowledging missing files (and
  potentially other worker actions) reliably produced
  `QObject::setParent: Cannot set parent, new parent is in a different
  thread` / `QBasicTimer` warnings and corrupted GUI-thread state (model
  resets, tree timers, widget reparenting all ran off the GUI thread).
  (cause: a worker's `finished` signal was connected to a bare lambda instead
  of a declared `QObject` receiver, so Qt's auto-connection fell back to a
  direct call on the emitting worker thread instead of queuing to the GUI
  thread.) This is the defect that motivated centralizing worker lifecycle in
  `nami_sync/ui/worker_session.py` (`CancellableWorker`/`WorkerSession`),
  which retired the older `_release_worker` sender-guard mechanism entirely
  — see the "UI — tab shell" section above for that superseded mechanism's
  own bugs.

- MINOR - FIXED. Shutdown race. `WorkerSession.shutdown` could burn its full
  timeout and report failure even though the session had already released
  cleanly. (cause: the thread's `finished` signal was connected to the wait
  loop after an `isRunning()` check, so a thread finishing in that gap was
  missed; the loop now connects first.)
- MINOR - FIXED. Silent guard loss. The GUI-thread guard for worker result
  callbacks disappeared when the app ran with Python optimizations enabled.
  (cause: it was a bare `assert`; it now raises an explicit `RuntimeError`.)
- MODERATE - FIXED. Misleading display. History dialog and CLI rendered
  every run as "source → target"; baseline/verify/import runs (subject-only)
  displayed literally "None → None". (cause: the renderer had no
  `activity_kind` branch.)
- MODERATE - FIXED. Misleading status. `_execution_finished` never checked
  `RunResult.refused`, so a volume-guard-refused sync (zero operations)
  rendered as green "Execution complete." (cause: the headline logic
  branched only on canceled/failed counts.)
- MODERATE - FIXED. Wrong-target action. When the selected integrity-
  location role pointed at an invalid/empty folder, the GUI silently fell
  back to the other folder combo instead of warning, so baseline/verify/
  inventory could run against the location the user didn't select. (cause:
  the fallback tried both combos without checking which one was actually
  chosen.)
- SEVERE - FIXED. Test/process defect. A test exercising the inventory
  context-menu handler hung indefinitely (~15 minutes, required manual
  interrupt) instead of completing. (cause: the test path reached
  `QMenu.exec()`, which opens a real modal loop even under the offscreen
  platform; fixed by splitting the exec-free row-selection logic into its
  own method so the test never calls `exec()`.)
- MODERATE - FIXED. Action consistency. The same operation could have
  different enablement, wording, shortcut, or dispatch behavior depending on
  whether it was invoked from the page, menu bar, or context menu. (cause:
  each presentation owned its own action wiring instead of sharing a
  window-owned `QAction` source of truth.)
- MODERATE - FIXED. Scope ambiguity. Filtered inventory verification was still
  labelled `Verify selected` and gave no visible-file count, obscuring that
  only present rows in the active filter would be verified. (cause: action
  presentation and tooltip ignored the active inventory filter.)
- MODERATE - FIXED. State invalidation. Changing a plan-only option while
  viewing Inventory discarded the populated inventory and its status context,
  forcing an unnecessary refresh. (cause: plan invalidation treated the plan
  and inventory caches as one state and always cleared both.)
- MODERATE - FIXED. Wrong-target action. Right-clicking blank inventory space
  could open actions for a previously selected row and apply them to that old
  selection. (cause: the context-menu path trusted the existing selection
  without first requiring a valid model index under the pointer.)
- MINOR - FIXED. View-state regression. Editing Source or Destination always
  snapped the Plan | Inventory switcher back to Plan, interrupting work in the
  selected Inventory view. (cause: location-edit invalidation unconditionally
  selected the Plan segment instead of preserving `_current_view`.)
- MODERATE - FIXED. Workflow failure. Creating a baseline at a location with
  no existing inventory did nothing and surfaced a nondescript UI error instead
  of inventorying the location and proceeding to baseline creation. (cause:
  baseline assumed an inventory already existed and the GUI did not chain the
  required inventory phase.)
- MODERATE - FIXED. Workflow stall. Starting verification without a preexisting
  inventory failed generically instead of creating the required inventory and
  continuing to hash the location. (cause: the verifier's no-inventory path
  did not invoke scan/reconciliation before verification.)
- MODERATE - FIXED. Stale display. Manual verification left the file list empty
  or showing the previous run during and after hashing, even though the
  inventory refresh had already produced the rows to display. (cause: the
  verifier did not emit the refreshed inventory at the scan-to-hash handoff and
  the completion path did not replace stale rows consistently.)
- MODERATE - FIXED. Misleading summary. Verification completion omitted the
  missing-file count while the inventory view correctly listed missing rows.
  (cause: the post-verification message retained the pre-Phase-2 counters and
  did not derive missing results from the refreshed inventory/issues.)
- MODERATE - FIXED. Verification performance. Verify selected refreshed the
  entire location before hashing a small visible selection, making a 100k-file
  inventory pay a full metadata scan. (cause: the selected path was treated as
  an ordinary manual verify with `inventory_location` instead of the scoped
  `refresh_inventory_paths` path.)
- MODERATE - FIXED. Scope misreporting. Exec+verify mutated and verified only
  changed files, but the UI marked the whole scanned directory verified and
  displayed the directory's total size. (cause: completion rendering used the
  full inventory rather than the execution/verification subset for row status
  and affected-byte presentation.)
- MODERATE - FIXED. Teardown deadlock. The first `WorkerSession.shutdown`
  implementation blocked on `QThread.wait` while terminal delivery was queued
  to the GUI thread, so the dispatcher could not run and quit the worker.
  (cause: shutdown used a blocking wait instead of a nested event loop.)
- MODERATE - FIXED. Teardown crash. A successful nested-loop shutdown could
  access a `QThread` wrapper after the release path had scheduled it for
  deletion. (cause: shutdown queried `thread.isRunning()` after deferred
  `thread.deleteLater`; it now returns from the timer/finish state.)
- MODERATE - FIXED. Silent invalid input. Typing a nonexistent or unusable
  source/destination path caused NamiSync to refuse actions as if no input had
  been supplied, without telling the user what was wrong. (cause: path
  validation only disabled actions and did not surface an actionable warning.)
- MODERATE - FIXED. Scope disclosure. The plan operation-kind column showed
  `copy`, `move`, and similar base operations even when Verify execution was
  enabled, hiding that a verification phase was scheduled. (cause: the display
  formatter rendered only the planner kind and ignored the verification option.)
