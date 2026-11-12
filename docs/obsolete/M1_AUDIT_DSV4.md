# NamiSync — Milestone 1 Branch Core-Logic Audit

**Status: closed historical audit (2026-08-08).** The report remains a
point-in-time record of `417aab5`; active behavior and future work are governed
by the focused architecture, module, and M1-stage documents.

- **Branch audited:** `milestone1`
- **Head commit:** `417aab5` (Add Claude Code project config)
- **Audit date:** 2026-08-07
- **Scope:** All 24 package source files (~20k lines) under `namisync/core`, `namisync/modules`, `namisync/db`, `namisync/workflows`, `namisync/dispatcher`, plus the full test suite.
- **Method:** Four parallel code audits by functional area (executor/verifier, scanner/planner/preflight, database/history, workflows/dispatcher), followed by manual line-level verification of every high-severity finding and a full test run on an isolated worktree.
- **Test baseline:** `1087 passed, 4 failed, 1 skipped`. Three failures are environmental (`nami-sync.exe` not installed — the editable install was not performed); one failure is a real defect, see M1.

## Resolution (2026-08-08)

This report remains the point-in-time audit at `417aab5`; the findings below
are preserved rather than rewritten after implementation. The planned HIGH
resolution and its coupled dispatcher findings landed as follows:

- **H1/H2 — contract pinned, not hidden.** The findings treated the raw plan as
  direct executable authority. NamiSync's safety contract instead preserves the
  full review intent, including the policy removal, and derives a separate
  dependency/correspondence-safe selection. Regressions now prove the blocked
  COPY/NOOP and removal remain visible under `trash` and `mirror`, the matching
  removal is deferred, and unrelated removal remains executable. Suppressing
  the raw row would weaken the review contract, so planner production code did
  not change.
- **H3 — fixed and follow-up-completed.** UPDATE and DELETE perform the recorder
  durability wait before their final live guard. The same ordering now covers
  MOVE, RECASE, MOVE_UPDATE old-path cleanup, and TRASH after follow-up review
  found their rename form of the race. A same-size/same-mtime replacement
  introduced during that wait is detected rather than overwritten, deleted,
  relocated, or falsely recorded. The smaller documented path-stat-to-syscall
  external-writer boundary remains non-atomic.
- **H4 — fixed and adversarially extended.** Ordinary failure now probes
  durable COPY/UPDATE/MOVE_UPDATE publication before temp cleanup, including a
  publish primitive that commits and then raises. Confirmed, drifted, missing,
  or unverified publication settles failed with truthful durable-state detail
  and degraded recording, without success evidence.
- **H5 — fixed at a reset boundary.** Ledger v3 stores a constrained sticky
  metadata-drift/hash-mismatch invalidation. Scans and negative verifier
  evidence set it conditionally, mismatch dominates later metadata drift, the
  stale query and four-state inventory projection honor it, and only guarded
  replacement evidence clears it.
- **H6/M9/M10 — fixed together.** Each dispatcher attempt has a process-local
  generation key owning its worker, reservation, and lease. Scheduler state is
  explicit, successor handoff waits for current-attempt retirement, stale
  cleanup is identity-scoped, and shutdown reports terminal-but-unretired or
  canceled-acquisition owners as unfinished.

Selected MEDIUM findings were resolved in the next hardening delivery:

- **M3/M15 — fixed together at history v5.** Exact same-item re-emission under
  a new sequence now produces a full, authenticated, non-counting duplicate
  receipt; changed semantics remain fatal producer corruption. A supported
  oversized event produces a bounded hash-only receipt, degrades audit, and
  permits the later stream and terminal row to persist. Storage/integrity
  failures still break the prefix, while replay reads retry only bounded
  SQLite BUSY/LOCKED failures. Receipt metadata/order, immutable item
  projections, lifecycle/count projections, and terminal truth are
  authenticated; oversized items retain bounded identity/semantic hashes so a
  changed reuse cannot bypass the corruption check. Strict `WITHOUT ROWID`
  receipts, append/finality guards, and physical-tail validation prevent
  replacement, reopening, or unauthenticated summary rows.
- **M6 — fixed across the complete native-I/O chain.** Service/workflow root
  validation, managed-root containment, scanner, preflight, executor, verifier,
  and inventory binding now add extended spelling at Windows I/O only and
  return logical paths. Device/ambiguous absolute roots are refused rather than
  normalized onto another tree, and native error filenames are sanitized
  before durable or user-facing detail.
- **M14 — fixed at its actual hot paths.** Explicit selected-path reads were
  already bounded. Frozen resume now fetches only canonical location-owned row
  IDs in 400-ID snapshot chunks, and stale-before selection consumes the stale
  query directly plus exact completed rows. Full Verify All intentionally
  remains proportional to the location.

The following findings remain documented release gates, not current M1 work:

- **M1:** require a typed not-ready history read or earlier visibility barrier
  before exposing any poll-based paused-history consumer; event subscribers are
  already ordered after the audit flush.
- **M2:** bound late pump-owned finalization when interruptible writer/late
  commit ownership semantics are designed; current persistence would need to be
  genuinely wedged.
- **M4:** add an age/liveness ownership guard before orphan-temp reclamation is
  relied on under a broader same-root multiprocess contract; current GUI
  single-instance behavior is not a GUI-versus-CLI or CLI-versus-CLI mutex.
- **M7:** non-`EVERYTHING` scoped deletion must not ship until a vanished
  subtree marks the scan incomplete and suppresses destructive inference.
- **M11:** define and test persistence-failure semantics before replacing the
  process-local session store with a durable M2 store.
- **M12:** define the future-cursor `Gap` contract before exposing arbitrary
  sequence-validating replay consumers.
- **History cleanup visibility:** a close-only observer failure after durable
  finalization cannot rewrite terminal truth and remains internal cleanup
  health; define a public projection before a persistent dispatcher/store
  makes that distinction user-actionable.

Final verification after rename-race follow-up: `1125 passed, 1 skipped`;
pytest treats unhandled worker thread exceptions as errors. Import-law
verification kept all 8 contracts, and
`git diff --check` was clean. Medium/LOW findings not coupled to this planned
delivery remain recorded below rather than being silently swept into scope.

## Severity definitions

| Level | Meaning |
|---|---|
| **CRITICAL** | Unconditional data loss, corruption, or a security vulnerability. |
| **HIGH** | A real functional defect or integrity violation with meaningful user impact under plausible conditions. |
| **MEDIUM** | Edge-case correctness bug, resource problem, or non-friendly failure surface. |
| **LOW** | Robustness, diagnostics, or performance nit. |

## Executive summary

No CRITICAL issues were confirmed. There is no path that unconditionally loses or corrupts data. The path-safety contract (relative-path validation, `join_under_root`, reparse/junction refusal), atomic same-volume publish, retry/continuation logic, verifier handle-bound reads, lock ordering, payload validation, and WAL-based transactions were all reviewed and found sound.

The six HIGH findings cluster into three themes:

1. **The planner's blocked/unsupported states do not participate in deletion decisions** (H1, H2). Files on the target that conflict with a blocked operation are still planned for TRASH/DELETE, and cloud placeholders on the source cause the target's only usable copy to be treated as surplus.
2. **The executor's destructive steps retain a documented-but-real TOCTOU window** (H3, H4), and one post-publish failure path leaves the ledger out of sync with the filesystem.
3. **Durable integrity state can go stale** (H5) and the dispatcher has an uncaught-exception race under cancel (H6).

The codebase quality is high overall — this is a hardening-heavy codebase with an extensive, honest bug log (see `docs/BUGS.md`) and a large regression suite. Most findings are narrow races or explicitly documented residual boundaries rather than systemic defects.

---

## HIGH findings

### H1 — Blocked operations do not claim target keys; colliding target files are still planned for deletion

**Location:** `namisync/modules/planner.py:368-382` (blocked COPY via `inherited_block`), `planner.py:283-294` (blocked MKDIR on TYPE_COLLISION), `planner.py:496-513` (removal loop).

**Problem:** The `inherited_block` branch of the COPY planning path returns a blocked operation without adding the target key to `claimed_target_keys` (the adjacent CASE_COLLISION and TYPE_COLLISION branches at lines 350 and 366 do claim). The blocked-MKDIR branch likewise never claims the key of the file it is blocked by. The removal loop then treats any unclaimed target file as TARGET_ONLY and plans TRASH (default policy) or DELETE (mirror) for it.

**Trigger:** Source wants `A\B\C` as a file while the target has a file at `A\B` (or a file where the source needs a directory), so the parent MKDIR is blocked. The plan then shows a *blocked* COPY/MKDIR alongside a *delete* of the very file blocking it.

**Impact:** Executing the plan moves or deletes the target's only copy of that file while the blocked operation never publishes the replacement — the target ends up with neither. Under `trash` the data is recoverable; under `mirror` it is permanently lost. The plan is self-contradictory on its face, which also undermines the review-before-execution safety model.

**Recommendation:** Have every blocked operation claim the target key(s) it is blocked by, so removal planning treats them as protected. Add a regression asserting that a blocked COPY/MKDIR and a TRASH/DELETE for the same path can never coexist in one plan.

### H2 — Source `unsupported` files (cloud placeholders / reparse points) cause the target's only usable copy to be deleted

**Location:** `namisync/modules/planner.py:515-533` (blocked NOOP for unsupported records), `namisync/modules/scanner.py:597-605` (file placeholders do not set `complete = False`).

**Problem:** When the source file is an offline cloud placeholder or a reparse point, the scanner files it under `unsupported` but keeps the scan `complete` (only *directory* placeholders set `complete = False`). The planner emits a blocked NOOP whose target key is unclaimed, so a real file with the same path on the target is classified TARGET_ONLY and planned for TRASH/DELETE.

**Trigger:** OneDrive/cloud placeholders or reparse-point files on the source, with a real materialized copy of the same file on the target — often the *only* usable copy of that data.

**Impact:** The only available copy is moved to trash (recoverable) or permanently deleted under `mirror`. This is the most dangerous of the planner findings because placeholder files are common on modern Windows with cloud storage.

**Recommendation:** When the source record is unsupported, the planner should refuse to delete the matching target path (protect it) or require an explicit acknowledgment. Cover the placeholder-file scenario with a planning regression test.

### H3 — UPDATE/DELETE keep a guard→flush→mutate window during which an externally replaced target is overwritten/deleted

**Location:** `namisync/modules/executor.py:2530-2543` (UPDATE: stat guard, then `clear_readonly` + `_flush_before_destructive`, then `fs.replace`), `executor.py:2952-2973` (DELETE: guard, then `_flush_before_destructive`, then `fs.remove_file`).

**Problem:** The final stat guard is not a compare-and-swap. Between the guard and the destructive call the executor runs a SQLite fsync (`_flush_before_destructive`) that can take tens to hundreds of milliseconds. If another process replaces the target path inside that window, `fs.replace` silently overwrites (UPDATE) or `os.unlink` deletes (DELETE) the foreign file. The UPDATE backup protects only the old reviewed file, not the foreign replacement; DELETE has no backup at all.

**Trigger:** Any external writer (antivirus, another sync tool, a human) touching the same path during the flush window. This is explicitly documented as the remaining "non-atomic threat boundary" in `docs/BUGS.md`, so it is a known, accepted residual risk — but it remains the largest external-data-loss window in the product.

**Impact:** External data loss in a narrow but real window; the operation still settles as success against the wrong file.

**Recommendation:** Shrink or eliminate the window — move the flush before the final guard, or replace path-based checks with handle/identity-bound publication where the platform allows it. At minimum, document the window's size and the failure mode for users running other sync tooling against the same tree.

### H4 — Post-publish metadata repair failure produces "filesystem changed + recording=OK + no durable record"

**Location:** `namisync/modules/executor.py:1013-1108` (`ensure_published_metadata`), `executor.py:3213-3245` (`_settle_failure`).

**Problem:** After `fs.replace` publishes the new file, metadata repair (reopening with GENERIC_WRITE to restore readonly bits, timestamps, attributes) can fail — e.g., the source ACL denies write. The operation is then marked FAILED and settled via `_settle_failure`, which does **not** degrade `recording` (the cancel path has an explicit `_mark_unrecorded_publish` for exactly this). The result is a tri-state contradiction: the filesystem has the new file, the ledger has no record of the mutation, and the audit claims `recording=OK`.

**Trigger:** Readonly-attribute repair on a file whose current ACL forbids the user write access, after publish succeeded.

**Impact:** History is untrustworthy for this item — a user consulting history believes nothing happened while the target was in fact replaced. Violates the invariant "record durable state only after the corresponding filesystem operation succeeds" (here, the operation *did* succeed and was still mis-recorded).

**Recommendation:** Route post-publish failure through the same "unrecorded publish" settlement as the cancel path, degrade `recording`, and include the published state in item detail.

### H5 — Content attestation and `last_verified_at` are never invalidated when observed state changes

**Location:** `namisync/db/recorder.py:553-573` (`_upsert_observation` ON CONFLICT list), `recorder.py:895-954`, `recorder.py:1311-1336` (move update); `namisync/db/repositories.py:250-265` (`get_stale_inventory` selects only on `last_verified_at`).

**Problem:** Re-scanning or moving a file updates only the `observed_*` columns; `content_*`, `attested_*`, and `last_verified_at` are preserved as-is. `get_stale_inventory` then selects verification candidates only by `last_verified_at`, so a file modified after verification never re-enters the stale set.

**Trigger:** A file is verified, then modified or moved, then re-scanned without re-verification.

**Impact:** The inventory keeps a "verified ✓" attestation for content that no longer matches the observed state — a false integrity guarantee. This is a core-function defect (inventory/integrity is an active product surface, not a placeholder), and it silently defeats the stale-verification pipeline.

**Recommendation:** Clear `content_*` / `last_verified_at` whenever the observed stat or identity diverges from the attested values, or add a schema-level CHECK that forbids attested/observed contradiction.

### H6 — Cancel in the queued-but-not-RUNNING window starts a second worker; the losing worker dies on an uncaught `IllegalTransition`

**Location:** `namisync/dispatcher/dispatcher.py:386-395` (cancel re-appends a PENDING session to `_pending`), `dispatcher.py:678-680` (CANCELING is admitted unconditionally), `dispatcher.py:766-768, 940` (`require_transition`), `namisync/core/session.py:411` (`settle` called outside the exception guard).

**Problem:** If worker W1 is queued (removed from `_pending`) but still blocked acquiring its resource lock when the user cancels, the session transitions to CANCELING and is re-appended. The scheduler starts worker W2. Both workers settle `CANCELED`; whichever settles second hits `require_transition` and raises `IllegalTransition`. The settle callback sits outside `run_session`'s exception handling, so the exception escapes to the thread top level — the worker thread dies unhandled, and W1's `finally` teardown can pop and release the lease/worker registration that W2 owns (a third, same-volume session could then be admitted concurrently, with the associated corruption potential).

**Trigger:** A session waiting on contested resources at the moment cancel is issued — exactly the contention scenario the scheduler exists to support.

**Impact:** Unhandled thread exception, duplicate settlement attempt, and a resource-lease release path that is only safe by GIL timing. Final session state is correct (CANCELED), so this is a crash/robustness defect rather than data loss.

**Recommendation:** Serialize settle per session (e.g., a per-session settlement gate that makes the second settle a no-op), and make teardown validate "I am still the registered worker" before releasing leases.

---

## MEDIUM findings

- **M1 — PAUSED state becomes visible before history is committed; `get_history_summary` raises a bare `KeyError`.** The dispatcher publishes PAUSED (state transition) before the audit flush inside `EventHub.emit` completes (`event_bus.py:556-561`), so a poll-based consumer can observe PAUSED while the history DB is still empty; `history.py:1031` then raises `KeyError` instead of a domain-typed result. Event-subscribing consumers (the UI) are safe because the PAUSED envelope is delivered only after the flush returns. **Verified:** `tests/test_inventory_runtime.py::test_paused_verify_resumes_without_repeating_or_losing_items` fails deterministically (also at `93e7b94`, where the test was introduced) — the events are all committed a moment later and a manual flush proves the pipeline is intact. Recommendation: commit the audit window before the PAUSED transition is observable, or return an empty/incomplete page instead of `KeyError`.
- **M2 — `event_bus.py:255-259`: unbounded finalize wait.** If the audit pump owns a finalize whose SQLite work exceeds the retry bound, the caller waits forever (the comment acknowledges this). Consequence: the session worker thread hangs permanently and the session never settles — requires the writer to be wedged, which is rare, but the bound is genuinely not closed.
- **M3 — `history.py:825-873` + `schema.py:369`: a duplicate `(run_id, item_type, item_id)` aborts the whole window transaction.** A second event for the same item in one run (e.g., verifier emitting twice for one file) violates the UNIQUE constraint, the INSERT raises, the entire transaction rolls back, and the observer degrades — the whole run's history is lost over one duplicate. Recommendation: dedupe by `payload_hash` before insert instead of aborting.
- **M4 — `executor.py:786-827`: `remove_orphaned_temps` can delete a concurrent process's in-flight temp.** Any `.synctmp-<runid>-<opid>` file not owned by the current run is unlinked without liveness checks. CLI + service (or any two processes) pointed at the same target root: A's preflight destroys B's in-progress temp, failing B's copy. Given the stated goal of reusing core logic across CLI/queue/service entry points, this collision is realistic.
- **M5 — `executor.py:3742-3768`: `except Exception` swallows `Canceled`/`PauseRequested`.** `_record`/`_flush_before_destructive` catch everything, including the control-flow exceptions every other path explicitly re-raises (`except (Canceled, PauseRequested): raise`). A recorder implementation raising `Canceled` would be converted into a recording failure while the operation settles SUCCEEDED — the cancel signal is lost.
- **M6 — `preflight.py:124`: long-path preflight effectively caps at 260 characters.** The per-subject `os.stat` and `Path.resolve(strict=True)` run without the `\\?\` prefix, so any root whose resolved length exceeds ~260 chars fails preflight with PATH_UNREPRESENTABLE. The scanner and executor both support extended-length paths; the preflight gate makes long-path mirroring unusable end to end.
- **M7 — `scanner.py:349-357`: a subtree that disappears during scan does not set `complete = False`** (only root-path and enumeration failures do). The planner's current scope restriction (`NotImplementedError` for non-EVERYTHING scopes) masks this today; once scoped scans are wired in, this becomes a deletion-safety hole.
- **M8 — `planning.py:365-387`: `calculate_required_bytes` undercounts peak space by one displaced copy** when `trash_on_update` is set on a volume without hardlink support (peak = new + 2×old, budget = new + old). Failure mode is an INSUFFICIENT_SPACE mid-run — no data loss, but the "conservative" claim is inaccurate.
- **M9 — `dispatcher.py:964-977` + `789-813`: worker teardown can release another worker's lease.** W1's `finally` pops `_leases[session_id]` and `_workers[session_id]` by session key, not identity; if W2 has already registered itself for the resumed session, W1's teardown releases W2's resource lease and deregisters W2. Currently safe only by GIL timing; should validate worker identity before cleanup.
- **M10 — `dispatcher.py:681-683`: implicit assumption about schedulable states.** Non-PENDING, non-CANCELING records in `_pending` are admitted without a resource check. Unreachable today (only CANCELING reaches `_pending` non-PENDING), but any future path that queues a PAUSED session would run it without resource licensing and crash on `IllegalTransition`. Make schedulable states explicit and guarded.
- **M11 — `dispatcher.py:958-962`: `_persist_locked` swallows store failures into `_store_failures`, which is never read.** Harmless while the store is in-memory; silently forks memory state from durable state the moment a persistent store lands.
- **M12 — `event_bus.py:570-611`: subscribing `from_seq > current seq` yields no Gap and an initial stream whose first seq is *below* the requested seq.** A strict sequence-validating consumer misreads this as regression/loss.
- **M13 — `runtime.py:416-445`: `_execution_started` run-token leak.** If `settle_canceled_execution` raises, the token is never released; a later submission with the same run id is rejected as "already in use". Cleanup should live in a `finally`.
- **M14 — `inventory.py:920-979`: `_integrity_rows` materializes the full inventory table and filters in memory** for selected-path/stale-before queries — O(n) per integrity run on large locations. Performance only.
- **M15 — `history.py:525-531, 604-618`: one bad event poisons the entire run's history.** Any single oversized/duplicate/illegal event or transient read failure sets `_failed` permanently, discarding all subsequent events and the finalize for that run. Distinguish per-event rejection from storage corruption.

## LOW findings

- `pathing.py:158-166`: `to_extended_length_path` mishandles device-namespace (`\\.\`) roots, producing `\\?\UNC\.\...`.
- `writer.py:31-33`: busy detection matches substrings `"busy"/"locked"` in error text; unrelated errors containing those words retry to timeout. Use SQLite error codes.
- `history.py` (M15-related): single-event failure semantics as above; also `connections.py:76-84` builds `?mode=ro` URIs with `Path.as_uri()` — a `?`/`#` in the path corrupts the query string.
- `schema.py:585-624`: `reset_databases` can leave a half-deleted state (unlinks the main DB, then fails on a locked `-wal`), and `schema.py:431-473`: concurrent first-time init can raise SQLITE_BUSY (executescript has no busy retry).
- `recorder.py:386-389`: bare `KeyError` for a missing location in `_validate_run_context`; `recorder.py:1070`: `plan_op.source_rel_path or ""` can feed an empty path into `validate_relative_path` and fail the whole transaction; `recorder.py:619-642`: temp table `current_scan_keys` is never dropped, and duplicate keys in `observed_keys` collide with its PRIMARY KEY; `recorder.py` root entries are intentionally skipped at line 521 while `_upsert_observation` rejects empty paths — inconsistent root semantics.
- `schema.py:134-144`: inventory CHECK constraints omit `attested_file_identity_*` / `attested_created_ns`, allowing partial attestation rows that the reader reconstructs as full `FileStat`s (`repositories.py:111-134`).
- `settings.py:292-307`: `os.replace` without directory fsync (benign on NTFS, inconsistent with the DB's crash semantics).
- `executor.py:1126-1156`: copy backup collects `source_stat` after the copy finishes — a live modification during the copy leaves backup metadata that does not match the backup content.
- `executor.py:780-784`: `remove_owned_temp` catches only `FileNotFoundError`; a readonly/held leftover temp raises `PermissionError` and blocks the whole preflight.
- `executor.py:2459-2473`: failed-update backups accumulate in `.synctrash/<run>` with no reclamation (deferred maintenance-workflow territory, but nothing backstops it).
- `executor.py:3277-3283`: policy-stop sweep silently drops a concurrent pause request.
- `verifier.py:1201`: fresh `bytes` per chunk + `VirtualAlloc`/`VirtualFree` per iteration — bounded (4 MiB) but allocation-heavy on large files; `verifier.py:232-238`: bytes of an interrupted item are counted twice across pause/resume (progress-only distortion).
- `planner.py:48-53`: metadata equality compares the full attribute bitmap; if a write sets FILE_ATTRIBUTE_ARCHIVE and the executor does not clear it, every rescan plans an UPDATE (no-op convergence risk — pending executor verification).
- `preflight.py:135`: `_volume_observation` runs per subject inside the loop — repeated `GetVolumePathNameW`/`GetVolumeInformationW` per file on large plans.
- `pathing.py:16-23`: reserved device names (`CONIN$`, `CONOUT$`, …) are not in the reject set.
- `payloads.py:1252-1266` vs `inventory.py:1120-1143`: payload encoder does not pass `parse_constant` to reject JSON NaN/Infinity (relies on `type() is int` typing), while inventory does — inconsistent validation.
- `runtime.py:267-270, 1000-1006`: `_plans`/`_execution_details`/`_inventory_details` grow monotonically (`drop_plan` has no callers).
- `dispatcher.py:396-400`: public `cancel()` never passes `audit_offer_timeout`; the parameter is dead code.
- `event_bus.py:88-111`: reliable-overflow ejects and closes the whole stream rather than dropping the burst — correct Gap semantics, but consumers must handle mid-stream ejection.
- `dispatcher.py:895-905`: terminal state becomes visible before `_publish_result` (intentional, commented; consumers must tolerate terminal-without-result).

## Areas verified clean

- **Path safety:** relative-path contract, `.`/`..`/streams/trailing-dot-space/NUL/surrogate rejection (`pathing.py:41-76`), `join_under_root` component-level containment, reparse/junction refusal in the scanner (incomplete-scan isolation), root-overlap and volume-identity checks (`preflight.py:367-382`), trash-volume ownership checks.
- **Atomic publish & retry:** same-volume rename-based publish; UPDATE via `os.replace` semantics; `_CopyContinuation` resume points are correct (temp-presence distinguishes published vs not); no checkpoint between publish and settlement — no pause-resume window that loses a published-but-unrecorded mutation; verification: handle-bound reads, `require_expected_final_path`, `OPEN_REPARSE_POINT`, `_same_open_subject` defenses are strong.
- **Copy pipeline resources:** byte budget (32 MiB), bounded queues (32), workers joined in `finally`, Windows handles closed on both paths.
- **Concurrency:** consistent lock ordering (`publication_lock → _condition → hub_lock`), no deadlock cycle found; audit-pump backpressure correctly decoupled from finalization.
- **Payload validation:** exact integer/boolean/string decoding, duplicate-key rejection, version exactness, UTC timestamps, valid-Unicode enforcement — no type-coercion or injection path found.
- **Database:** transaction boundaries, idempotency receipts, append-only event journal with rolling hashes/watermarks, WAL mode, keyset-paged reads (mostly), multi-batch read snapshots.

## Overall assessment

A mature, defense-in-depth codebase with an unusually honest defect history. No CRITICAL issues. The highest-value fixes, in order:

1. **H1 + H2 (planner)** — make blocked/unsupported states participate in deletion decisions; they share one root cause and are the only findings that can move (or delete) user data on their own.
2. **H5 (recorder)** — invalidate attestation on observed divergence; a core integrity feature currently can report stale "verified" truth.
3. **H3 (executor window), H4 (post-publish settlement)** — reduce the destructive window and close the record/audit contradiction.
4. **H6 (dispatcher cancel race) + M1 (pause/history visibility)** — crash/robustness races in high-frequency user actions; M1 also fails the existing test suite.
