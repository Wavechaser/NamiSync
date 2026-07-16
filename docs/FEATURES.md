# Features

This document lists implemented and planned NamiSync features.

## PROJECT ARCHITECTURE

- **Layered Domain Design**. Core owns sync behavior, the database owns persistence, application workflows coordinate them, and interfaces adapt those workflows.
- **Headless Workflows**. Planning, execution, inventory, integrity, and history workflows run without Qt and are shared by the desktop UI and CLI.
- **Thin Desktop Adapter**. The PySide6 UI presents workflow state and delegates sync decisions to non-Qt layers.
- **Typed Core Contracts**. Explicit dataclasses carry scan, plan, execution, progress, verification, and result data across layers.
- **Separate State Stores**. The working ledger and append-oriented audit history use independent local SQLite databases.

- **Queue and Service Reuse**. The same headless workflows will support future queue and service entry points without moving sync policy into the GUI.

## SYNC WORKFLOW

- **One-Way Root Mapping**. NamiSync reconciles a distinct source folder into a distinct, non-nested destination folder.
- **Dry-Run Review**. Every sync scans both roots and produces a reviewable plan before filesystem mutation.
- **Deletion Policies**. Paired sync supports `trash` by default and `additive`, while `mirror` is available only as an internal policy.
- **Recent Folders**. The application remembers up to five recent source and destination folders separately.

- **Durable Job Queue**. Queued jobs will retain stale-plan defenses and support optional re-planning with material-difference review before execution.

## SCANNER

- **Recursive Metadata Scan**. The scanner records root-relative regular files with size, nanosecond modification time, and filesystem identity.
- **Directory Inventory**. Empty directories are retained as directory records so they can be planned for creation or cleanup.
- **Ignored-Path Filtering**. NamiSync excludes application databases, checksum sidecars, common Windows metadata files, sync trash, and generated temporary files.
- **Scan Warnings**. Access errors and filesystem case collisions are retained in scan results for plan review.
- **Cooperative Scan Cancellation**. Scans check for cancellation while walking directories and files.

## PLANNER

- **Metadata-Based Diffing**. Matching size and modification time produces a no-op, while changed metadata produces an update.
- **Copy and Update Planning**. Source-only files become copies and changed matched files become updates.
- **Move Detection**. Unambiguous source filesystem-identity changes can become target-side moves, with a follow-up update when metadata differs.
- **Directory Operations**. Source-only empty directories become `mkdir` operations and removable target-only empty directories become policy-controlled operations.
- **Conflict Blocking**. Case collisions and file-directory conflicts remain visible as blocked conflict operations instead of being guessed through.
- **Capacity Planning**. Plans record target free space and conservatively require room for all copy and update bytes.
- **Stable Plan Ordering**. Operations receive deterministic per-plan identifiers and dependency-aware ordering.

- **Content-Aware No-Op Detection**. Planning will use hashes or another content check before accepting metadata-equal files as unchanged.
- **Hash-Based Move Detection**. Move detection will extend beyond source filesystem identity to evidence-aware content matching.
- **Human Conflict Resolution**. Unresolved conflicts will be retained for user review instead of remaining permanently blocked.

## EXECUTOR

- **Plan Preflight**. Execution refuses incomplete, stale, unsafe, or insufficient-capacity plans before mutation.
- **Atomic Copy and Update**. File content is written to a target-volume temporary file, flushed, metadata-preserved, and atomically published.
- **Hash on Copy**. Successful copies and updates calculate a SHA-256 digest from the source byte stream during copying.
- **Guarded Target Moves**. Target-side moves refuse existing destinations and preserve the existing target file record when recorded.
- **Root-Local Trash**. Trash operations move items to `.synctrash/<run-id>/<relative-path>` on the target volume.
- **Guarded Deletion**. Internal mirror deletes and empty-directory cleanup validate type and emptiness before removal.
- **Partial Result Reporting**. Independent operations continue after failures, with per-operation succeeded, skipped, failed, and canceled results.
- **Progress and Cancellation**. Execution reports overall and per-file byte progress and checks cancellation between operations and copy chunks.
- **Temporary-File Recovery**. Relevant orphaned NamiSync temporary files are cleaned from touched target parent directories before copying.

- **Validated Partial Execution**. Selected plan operations will execute only after dependency closure, summary and capacity recomputation, and explicit deferred outcomes are recorded.
- **Robocopy Copy Backend**. NamiSync will evaluate an optional Robocopy backend while retaining its own planning, trash, and safety controls.

## INVENTORY

- **Role-Free Location Inventory**. A location can be scanned and retained independently of any source or destination role.
- **Mapping Guidance**. Inventory displays zero, one, or many stored mapping relationships and requires explicit paired roots when relationships are ambiguous.
- **Missing Retention**. Complete scans mark unseen tracked files missing while preserving their prior metadata and hashes.
- **Missing Acknowledgement**. Missing rows can be acknowledged to hide them from the default view without deleting their evidence.
- **Acknowledgement Restore**. Acknowledged missing rows can be restored to the normal missing view.
- **Reappearance Tracking**. Files returning after being marked missing are surfaced as reappeared until a matching hash or new baseline resolves the state.
- **Selected Inventory Refresh**. Selected paths can be refreshed without walking the entire location or inferring unselected absences.

- **Shared Network Inventory**. Inventory merging across hosts and network locations remains unrealized.

## VERIFIER

- **Baseline Creation**. Baseline creates SHA-256 hashes for present inventory rows that do not already have a hash.
- **Location Verification**. Verification rereads present files against retained size, modification time, and SHA-256 evidence.
- **Integrity Outcomes**. Verification distinguishes verified, baselined, mismatched, modified, missing, unsupported, canceled, and error results.
- **Selected Verification**. Present inventory files selected in the UI can be verified without verifying the entire location.
- **Post-Execution Verification**. A sync can automatically verify eligible copied, updated, and moved files after execution.
- **Safe Conditional Recording**. Hash and verification results are persisted only when the file state remains consistent with the observation being recorded.

- **Multithreaded Verification**. Verification speed can be CPU-bound on faster disks, the verifier should run multithreaded conditionally.
- **Automatic Background Integrity**. Background hashing and verification remain unrealized.

## TERACOPY HASH IMPORT

- **SHA-256 Sidecar Parsing**. NamiSync reads UTF-8 TeraCopy `.sha256` sidecars with safe relative paths and duplicate-entry checks.
- **Existing-Inventory Import**. Sidecar hashes are accepted only for existing, present, unchanged, unhashed inventory rows inside the selected location.
- **Hash Protection**. Established database hashes are never overwritten; matching values are reported as known and differing values as conflicts.

## FILES LEDGER

- **Local SQLite Ledger**. NamiSync stores hosts, physical locations, inventories, mappings, runs, configuration, and mapping-specific file correspondence in a local schema-versioned database.
- **Windows Path Identity**. Location and relative-path keys normalize Windows separators and case without relying on SQLite `NOCASE`.
- **Mapping-Scoped State**. Shared physical locations can participate in multiple mappings while retaining independent source identity and correspondence state.
- **Durable State Ordering**. Ledger updates are committed after the corresponding filesystem observation or mutation succeeds.
- **Run Idempotency**. Executor run tokens uniquely correlate and protect repeated ledger recording.
- **Database Safety Settings**. Ledger connections use foreign keys, WAL mode, and a bounded busy timeout.

- **Legacy Data Migration**. Migrating or merging version 1 and version 2 ledger data remains unrealized.

## HISTORY

- **Independent Audit Store**. Sync, baseline, verification, and TeraCopy import attempts are recorded in a separate local history database.
- **Typed Run Details**. History retains activity-specific summaries and ordered sync operations or integrity issues.
- **No-Op and Cancellation Audit**. Explicit no-op and canceled activities are recorded alongside successful and failed activities.
- **History Idempotency**. Repeating a recorded run token does not create a duplicate history entry.
- **History Retention**. Summary and detail retention settings can prune old history detail while preserving the run envelope and summary.
- **History Browsing**. Retained runs and their details can be inspected in the desktop History dialog or through the CLI.

- **Task-Grouped History**. GUI activities will be grouped under durable task records while CLI and service activities remain valid without a task parent.
- **Task Annotations**. Users will be able to add a trimmed plain-text task annotation of up to 256 characters.
- **Restorable Task Setup**. Opening history will restore a task's saved inputs and options while requiring a fresh plan before execution.
- **History Replay**. Retained history will be replayable from a recorded source to a newly selected target when sufficient detail remains.

## COMMANDLINE

- **Inventory Command**. `nami-sync inventory` scans one location and prints its retained inventory and mapping guidance.
- **Baseline Command**. `nami-sync baseline` creates missing baselines and reports integrity counts and issues.
- **Verify Command**. `nami-sync verify` verifies one location and returns a failing exit code when integrity issues are found.
- **Hash Import Command**. `nami-sync import-hashes` imports explicit TeraCopy sidecars for one location.
- **History Command**. `nami-sync history` lists recent audit runs or prints one retained entry with detail.
- **Database Overrides**. CLI integrity commands can select separate main-ledger and history database paths.
- **GUI Entry Points**. Running `nami-sync`, `nami-sync-gui`, or `python -m nami_sync` launches the desktop application when no subcommand is given.

## DESKTOP UI

- **Task Rail**. The window provides a scrollable newest-first rail of task cards with status, paths, completion date, close controls, and mini progress bars.
- **Single-Page Task Shell**. Each task keeps source, destination, options, status, progress, plan, inventory, and log controls on one page.
- **Folder Selection**. Source and destination support editable recent-folder dropdowns and folder browser buttons.
- **Plan Tree**. The Plan view displays operations in a directory-nested tree with rolled-up counts, sizes, reasons, hashes, and statuses.
- **Inventory Tree**. The Inventory view displays retained files in a directory-nested tree with presence and integrity states.
- **Plan Filters**. Plan review can filter All, Changes, Moves, and Conflicts with live counts.
- **Inventory Filters**. Inventory review can filter All, Verified, Baseline, Unbaselined, Missing, Reappeared, and Acknowledged rows with live counts.
- **View Toggle**. A persistent Plan | Inventory toggle switches between retained plan and location-inventory views without conflating them.
- **Inventory Actions**. Menus and row context actions support selected verification, missing acknowledgement, acknowledgement restore, path copying, inventory, baseline, and import workflows.
- **Live Progress**. Sync, scan, baseline, verification, and import workers update overall and per-file progress with current paths and counters.
- **Cooperative UI Workers**. Long-running operations run through cancellable Qt worker sessions with guarded cleanup and release handling.
- **Task Concurrency Guard**. Only one task may scan or execute at a time within an application instance.
- **Dark Theme**. The desktop shell uses a dark-only PySide6 theme with status colors, operation-kind colors, alternating tree rows, and styled progress controls.
- **History Dialog**. The desktop UI lists history runs, shows retained activity detail, and applies history-only retention settings.

- **Drag-and-Drop Setup**. Dropping folders onto a task will populate its source and destination fields.
- **Status Layout Refinement**. The task header will unify live and completed detail while promoting activity state over the affected-byte figure.
- **Rolling Transfer Metrics**. A rolling estimator will provide responsive throughput and phase-aware ETA instead of the current whole-run average.
- **Throughput Graph**. The UI will graph current transfer rate against execution progress.
- **Plan Follow Mode**. The Plan view will follow the active operation until the user deliberately scrolls away, including collapsed-tree handling.
- **Live Integrity Feedback**. The Inventory view will follow the file being hashed and later update per-file outcomes as verification progresses.
- **Data Management UI**. Database export, import, and settings screens remain unrealized.

## CROSS-PROCESS SAFETY

- **Physical-Volume Guard**. Filesystem workflows acquire deterministic cross-process locks for all required local physical volumes and refuse unsafe or contended volumes.
- **Root-Constrained Paths**. Planner, executor, and sidecar workflows reject absolute, drive-qualified, parent-traversing, or root-escaping relative paths.

- **Long-Path Support**. NamiSync will add explicit Windows long-path-safe handling across filesystem workflows.
- **Reparse-Point Preservation**. Reparse-point handling and preservation remain unrealized.
- **Network-Share Coordination**. Cross-process locking and scheduling for network shares remain unrealized.
- **Disk-Aware Parallel Execution**. Independent queued jobs on separate physical disks will be able to run in parallel through the existing volume-identity model.
