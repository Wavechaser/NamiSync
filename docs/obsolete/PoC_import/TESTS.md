# Test Coverage

The test suite collects 201 tests across 23 test modules; the entries below
summarize what each module protects.

## TEST HARNESS

- **Headless Qt**. `tests/conftest.py` configures Qt for offscreen execution so GUI tests run without a display.
- **Qt Diagnostic Guard**. An autouse message handler turns exercised thread-affinity and timer warnings into test failures while preserving unrelated diagnostics.

## APP WORKFLOWS

- **Planning Safety**. `test_app_workflows.py` verifies that incomplete scans produce reviewable but non-executable plans.
- **Execution Bookkeeping**. The workflow tests verify partial results reach both the ledger and history and that execution tokens are UUIDs.

## CLI

- **Entrypoints**. `test_cli_entrypoints.py` verifies console-script and module invocation, argument dispatch, and rejection of obsolete paired arguments.
- **One-Location Commands**. CLI tests cover inventory, baseline-first behavior, verification, output, and integrity exit codes.

## CORE SCANNER

- **Filesystem Discovery**. `test_scanner.py` covers recursive regular-file and directory metadata, stable ordering, and root validation.
- **Exclusions**. Scanner tests protect database, sidecar, Windows metadata, trash, and generated temporary-file filtering.
- **Collision and Key Rules**. Tests cover case collisions and Windows-style path normalization without Unicode case-expansion over-merging.
- **Error and Cancellation Handling**. Scanner tests verify recorded walk errors and cooperative cancellation.

## CORE PLANNER

- **Diff Operations**. `test_planner.py` covers copy, update, no-op, trash, additive, and internal mirror planning.
- **Rename Planning**. Planner tests cover unambiguous identity-based moves, move-then-update plans, and ambiguous-identity fallback.
- **Directory Planning**. Tests cover empty-directory creation, policy-controlled cleanup, ignored-file protection, and convergent reruns.
- **Capacity and Warnings**. Planner tests cover insufficient or unavailable target space, scan warnings, incomplete scans, and blocked conflicts.
- **Input Validation**. Tests reject unsupported policies, duplicate file records, and unsafe plan inputs.

## CORE EXECUTOR

- **Filesystem Operations**. `test_executor.py` covers copy, update, move, mkdir, trash, delete, noop, and plan-generated move-then-update execution.
- **Atomic Copy Safety**. Executor tests verify source-stream SHA-256 results, temporary-file cleanup, orphan cleanup, and trash-volume containment.
- **Preflight Protection**. Tests cover capacity rechecks, stale touched paths, missing targets, existing move/trash destinations, incomplete scans, blocked operations, and safe ignoring of unrelated changes.
- **Failure and Cancellation Semantics**. Executor tests verify per-operation failures do not stop independent work and cancellation works before operations and during copies.
- **Path and Directory Safety**. Tests reject root escapes and drive-qualified paths and protect empty-directory cleanup behavior.

## CORE INTEGRITY

- **Baseline and Verification States**. `test_verifier.py` distinguishes baseline creation from verification and covers matches, metadata modification, hash mismatch, missing files, and null-hash backfill.
- **Inventory and Hash Safety**. Integrity tests cover inventory-before-baseline, reappearance resolution, cancellation, per-file commit boundaries, and protection against ledger updates during hashing.
- **Scoped Verification**. Tests verify normalized selected paths, selected-row queries, and selected disappearance reporting without a full-location scan.
- **Rename and Identity Safety**. Tests prevent recycled file IDs and hardlink ambiguity from rekeying retained hashes without matching content.

## TERACOPY IMPORT

- **Sidecar Import Rules**. `test_teracopy.py` verifies imports require existing unhashed inventory rows and never bootstrap locations or overwrite established hashes.
- **Import Cancellation and Audit**. Integrity tests cover canceled imports leaving inventory unchanged while still recording history.

## CORE VOLUME GUARD

- **Cross-Process Locking**. `test_volume_guard.py` verifies same-volume contention is refused and the lock becomes available after the holder exits, on Windows.

## APP INVENTORY

- **Role-Free Inventory Workflow**. `test_inventory_workflow.py` verifies scanning creates inventory without creating a mapping and reports zero, one, or many mapping context.
- **Selected Refresh**. Inventory tests verify explicit path refresh updates only selected retained rows.

## DATABASE SCHEMA

- **Ledger Schema**. `test_db_schema.py` verifies fresh v3 tables, schema versioning, foreign keys, and refusal of legacy schemas without mutation.
- **Database Constraints**. Schema tests reject invalid file, mapping, and mapping-state relationships.

## DATABASE REPOSITORY

- **Path and Row Identity**. `test_db_repository.py` covers normalized Windows keys, case-only renames, and preservation of row identity and hashes.
- **Missing Evidence**. Repository tests cover missing-row pruning, acknowledgement and reappearance state, and invalidation of mapping evidence.
- **Query and Constraint Efficiency**. Tests verify batched path reads and safe handling of large inventories.

## DATABASE STATE

- **Inventory Reconciliation**. `test_db_state.py` covers paired location creation without implicit mappings, complete versus partial scan semantics, missing retention, and reappearance.
- **Mapping Correspondence**. State tests verify shared-target authority, move rekeying, skipped-move missing state, no-op evidence rules, and stale correspondence invalidation.
- **Bookkeeping Robustness**. Tests protect large-scan parameter handling and prevent unsafe snapshot paths from rolling back valid execution bookkeeping.

## HISTORY

- **History Schema and Lifecycle**. `test_history.py` covers typed v2 envelopes, legacy-schema refusal, no-op idempotency, activity-specific summaries, retained integrity details, selected scope, and pruning.
- **History CLI**. `test_history_cli.py` verifies run listing, missing-entry handling, and rendering of sync and integrity detail.
- **History Dialog**. `test_history_dialog.py` verifies run listing, compact hash display with full-hash tooltips, subject locations, and integrity issue detail.

## PHASE 2 INTEGRATION

- **Shared-Target Isolation**. `test_phase2_hardening.py` verifies mappings sharing one target keep independent source authority and invalidate stale correspondence after mutation.
- **Hash-Preserving Moves**. Integration tests verify executor-confirmed moves preserve the target row, hash, and integrity timestamps.
- **First-Sync Rename Evidence**. Tests verify a first-sync no-op records enough correspondence for a later source rename to plan as a move.

## UI PLAN MODEL

- **Plan Tree Structure**. `test_plan_model.py` covers directory nesting, directory-operation attachment, rollups, and operation visibility.
- **Plan Filtering and Status**. Model tests cover All, Changes, Moves, and Conflicts filters, live operation status, cancellation, and status persistence across filtering.
- **Plan Hash and Verification Display**. Tests cover compact known and fresh hash formatting and `copy+verify`/`move+verify` labeling.

## UI WORKERS

- **Workflow Bridges**. `test_ui_workers.py` verifies Qt workers preserve plan, inventory, baseline, import, verification, and execution workflow contracts.
- **Inventory Handoffs**. Worker tests cover inventory-before-hash progress, linked execution scope, selected verification, refreshed results, and cancellation reporting.

## UI TASK SHELL

- **Task Rail Lifecycle**. `test_task_shell.py` covers task creation, newest-first ordering, selection, close behavior, and keeping one task alive.
- **Action Gating**. Task-shell tests cover source/destination validation, integrity-role selection, mapping guidance, paired-action enablement, and cross-task locking.
- **Plan and Inventory Presentation**. Tests cover dedicated models, filters, conditional chips, Plan | Inventory switching, plan invalidation, and inventory retention.
- **Progress and Status**. Tests verify shared counter ordering, path elision, progress-bar updates, card tone/status, options summaries, and execution refusal display.
- **Menu and Context Actions**. Tests cover active-page action dispatch, background-task isolation, shared menu/page action state, inventory context selection, filtered relabeling, absolute path copying, and blank-space safety.
- **Integrity Flow Ordering**. Task-shell tests verify manual and linked verification render inventory before hashing, preserve plans appropriately, and wait for worker-session release.

## UI WORKER SESSION

- **Terminal Delivery**. `test_worker_session.py` covers result, cancel, and failure delivery, cleanup, release, duplicate-terminal suppression, and wrong-thread rejection.
- **Cancellation and Shutdown**. Session tests verify live cancel dispatch, cooperative shutdown, timeout ownership, and delayed release of slow workers.
- **Callback Safety**. Tests reject request-state closures and protect the Qt warning boundary.
- **Real-Thread Workers**. `test_ui_worker_sessions.py` runs every concrete GUI worker in a real `QThread` for success and failure paths.

## PROJECT IMPORTS AND STARTUP

- **Import Surface**. `test_project_imports.py` verifies package, GUI, worker, and application entry-point imports.
- **Startup Maintenance**. Startup tests verify history retention maintenance runs and the main window constructs with an initial task and recent-folder controls.

Run the complete suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
