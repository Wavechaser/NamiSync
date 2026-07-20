# Features

This document lists implemented and planned NamiSync features. Within each
section, bullets before the first blank line describe settled, built-toward
behavior; bullets after it are unrealized future work — some already
reflected as a seam in the settled design, some not yet begun.

Reference documentation imported from the proof-of-concept lives in
`PoC_import/`; its `BUGS.md` is the evidence base behind many of this
document's rules.

## PROJECT ARCHITECTURE

- **Layered Domain Design**. Core owns shared contracts and the session machine, isolated modules (scanner, planner, preflight, executor, verifier) own sync behavior, the database owns persistence, application workflows coordinate them, and interfaces adapt those workflows.
- **Headless Workflows**. Planning, execution, inventory, integrity, and history workflows run without Qt and are shared by the desktop UI and CLI.
- **Thin Desktop Adapter**. The desktop UI presents workflow state and delegates sync decisions to headless layers; it never owns sync policy regardless of which UI toolkit implements it.
- **Typed Core Contracts**. Explicit dataclasses carry scan, plan, execution, progress, verification, and result data across layers.
- **Separate State Stores**. The working ledger and append-oriented audit history use independent local SQLite databases.
- **Session-Typed Operations**. Every long-running activity (scan, plan, execute, verify, baseline, import) runs inside one typed session contract: a shared state machine, a tagged-union event stream, and a cooperative checkpoint that pause and cancellation both resolve through, so no module invents its own lifecycle or terminal shape.
- **Workflow-Sequenced Pipelines**. Modules never call each other directly; an application workflow function sequences scan, plan, preflight, and execute by passing typed data forward, so coordination stays readable top to bottom instead of emergent from signals or callbacks.
- **Preflight as a Callable, Not a Gate**. Preflight validates a plan-and-selection pair against current filesystem state and can be invoked repeatedly — at start, at resume, after a selection change — instead of running once as an unrepeatable ritual.
- **Recorded Ledger, Observed History**. Execution and verification report through the Recorder module rather than writing SQL directly; the recorder commits ledger evidence in a bounded window rather than one write per operation, while the independent history store consumes the same session's event stream asynchronously with guaranteed, bounded delivery, matching its append-only role.
- **Policy Extension Points**. New behavior (copy backends, retry and failure handling, deletion policy) plugs in as a protocol that returns a decision to the machine, never as a hook that receives control, so invariants stay enforced centrally regardless of which policy is active.
- **Pipeline-Only Mutation**. Every mutation to user data inside a managed root flows through plan, preflight, and execute — including undo and repair — so a corrective action's conflicts with later changes surface in ordinary plan review instead of a special-cased overwrite. App-owned artifacts (trash purge, database maintenance) are exempt from this law but stay type- and ownership-guarded and history-logged.
- **Sessions Never Block on a Human**. A conflict or error during execution is logged and the run continues past it; nothing pauses mid-run to wait on a decision. Review and any corrective action happen after the run ends, through the same pipeline as any other plan.
- **Never Wrong, Only Behind**. Because the recorder commits only after a filesystem mutation succeeds, every committed row is a true statement about a past observation; recovery from a crash or interruption never discards committed evidence to reach a tidier state — it reconciles by marking the interrupted session and re-scanning to converge.
- **Injected Clock**. Time-dependent behavior — retention sweeps, staleness views, day-boundary filters — reads the current time through one injected clock dependency, keeping timezone- and DST-edge behavior testable rather than incidental.
- **Degenerate First Implementations**. A protocol earns its sophistication before its first implementation does; the recorder's batching, the event stream's conflation, and the queue's persistence each ship as the simplest correct behavior behind their real interface, with the interface — not a rewrite — absorbing later hardening.
- **Layer Benchmarks Before Scale-Up**. The recorder, the event pipeline, and the scanner walk are each benchmarked in isolation under synthetic load before broader features build on top of them, rather than discovering per-item overhead only at full scale.
- **Interaction Clusters**. Most feature interactions concentrate around four shared resources — disk space, inventory semantics, volume locks, and run bookkeeping. Features outside these clusters are reviewed for orthogonality alone; features touching them get deliberate pairwise review and note what they interact with inline.

- **Queue and Service Reuse**. The same headless workflows will support future queue and service entry points without moving sync policy into the GUI.

## SYNC WORKFLOW

- **One-Way Root Mapping**. NamiSync reconciles a distinct source folder into a distinct, non-nested destination folder.
- **Dry-Run Review**. Every sync scans both roots and produces a reviewable plan before filesystem mutation.
- **Commit-to-Execute**. Execution happens only for a plan the user has reviewed and explicitly committed; the commitment binds to the plan's deterministic fingerprint and to the reviewed selection, so neither can change under an approval. A committed plan runs immediately when its volumes are free, otherwise it queues, and committed plans execute sequentially in commit order. An uncommitted plan is never executed and never expires into execution — it simply remains reviewable. Scripted and queued execution replay committed plans; nothing plans and executes in one unreviewed step, and every committed execution still preflights first, with material drift refused back to review rather than silently re-planned.
- **Deletion Policies**. Paired sync supports `trash` by default and `additive`, while `mirror` is available only as an internal policy.
- **Recent Folders**. The application remembers up to five recent source and destination folders separately.

- **Durable Job Queue**. Queued jobs persist in the dispatcher's own session table, retain stale-plan defenses through the same preflight re-check every resume uses, and support optional re-planning with material-difference review before execution.

## INGEST

Ingest copies media from a card or mirrored directory into a library organized
by capture metadata instead of preserving directory structure — DIT-style
offload built on the same scan → enrich → plan → preflight → execute pipeline.
All unrealized; the settled Destination Policy Seam (see Planner) is its
provision.

- **Metadata-Sorted Ingest**. Files will be copied into a destination structure computed from capture metadata (date, camera body) by a naming template, rather than mirroring the source layout.
- **Enrichment Stage**. An extraction pass will read capture metadata between scan and plan as its own cancellable pipeline stage; a file whose metadata cannot be read falls back to a policy destination (filesystem times or an unsorted bucket) and never fails the run.
- **Naming Templates**. Templates will compose tokens (capture date, camera, original name, sequence) into destination paths; two source files computing the same destination resolve deterministically by sequence policy, and every collision is visible in plan review.
- **Companion Grouping**. Sidecar and pair files (RAW+JPEG, XMP, THM) will travel to the same destination folder with consistent renames, as one reviewable group.
- **Additive by Contract**. Ingest never trashes, mirrors, or otherwise touches target-only files, and never mutates the source card.
- **Ingest Review**. Ingest uses the same plan-review-execute two-session shape as sync, with each file's computed destination shown for review; ingest execution follows the same commit-to-execute contract as sync — a committed ingest plan may run queued or scripted, but no ingest ever executes without a reviewed commitment.
- **Untracked Ingest Sources**. Ledger locations are created only by sync and integrity workflows; ingest never creates ledger state for its source. A card is scanned in memory, planned against, copied from, and forgotten — nothing to rebind, recognize, or clean up when it is formatted. Temporariness is a property of the workflow, not of any filesystem type.
- **Origin Provenance**. Ingest stamps each library file's ledger row with its origin evidence — original filename, capture time, source size — through the generic annotations table, so all ingest evidence lives on the tracked library side.
- **Stateless Resume**. Re-ingesting a partially ingested card is just planning again: files whose computed or provenance-matched destination already exists plan as no-ops, including files that landed under a collision suffix, with no card-side state consulted.
- **Ingest Profiles**. A recurring ingest configuration (target library, template, options) will anchor to the destination and accept whatever source volume is presented; it is its own small entity, not a mapping, and accrues no per-card rows.
- **Content Dedup**. Optionally, a file whose content hash already exists in the library will plan as a skip regardless of destination path.
- **Verified Offload**. Post-execution verification will confirm the library copies against the card before the user formats it; a whole-card check across multiple past runs derives from origin provenance plus hash comparison, with no card-side state.
- **ExifTool Extraction**. Metadata extraction sits behind a protocol; an ExifTool batch-mode implementation is the intended first extractor.

## DISPATCHER

Implementation status (M0): generic process-local admission/control, bounded
event delivery, opaque continuation snapshots, and real cross-process Windows
volume custody are implemented. SQLite session persistence, startup
reconciliation, and unique durable queue ownership remain M2; their bullets
below describe settled behavior, not current M0 runtime claims.

- **Domain-Blind Session Scheduling**. The dispatcher admits, schedules, and tracks sessions by their generic contract alone; no dispatcher method or code path is named for a specific activity such as sync or verify.
- **Volume-Scoped Concurrency**. Sessions whose required volumes don't overlap may run concurrently; sessions contending for the same volume queue behind each other. Concurrency is a property of the resources a session needs, not a single global one-at-a-time rule.
- **Single Queue Owner**. Multiple NamiSync processes may run at once; cross-process volume locks arbitrate disk access between them, and a file lock on the persisted queue ensures exactly one process at a time owns queued-session admission.
- **Resource Custody**. The dispatcher acquires each session's required volume locks on start and releases them on every terminal transition or pause-drain, so lock lifetime has exactly one owner.
- **Control Plane**. Pause, resume, and cancel are dispatcher operations that flip a flag a running session's checkpoint resolves against; the dispatcher enforces the legal state-transition table so illegal requests fail cleanly instead of corrupting session state. Pause is a per-kind capability declared at workflow registration: only session kinds with a continuation state (sync execution; verification's item-list sessions) accept it, while short continuation-less sessions refuse pause cleanly and stay cancelable.
- **Resume Outcomes**. Resuming a paused or interrupted session always preflights first and either continues or is refused with reasons if the remaining plan is no longer valid; the user replans and re-attempts rather than the system attempting a silent partial continuation.
- **Resume Never Preempts**. A resumed session re-enters admission at the back of its volumes' queue: if another session took over the contended volume while it was paused, the resumed session runs when that session finishes or is itself paused or canceled. Jumping the queue would mean either force-pausing the running session or running two sessions on one volume — the first is confusing, the second is forbidden.
- **Persisted Session Table**. The dispatcher persists its own session table — lifecycle state and an opaque per-workflow payload — independent of the ledger and history; this is the one exception to never writing a database, and the dispatcher never interprets the payload it stores.
- **Startup Reconciliation**. On launch, the dispatcher reloads its session table; anything left running by a process that is no longer alive is marked interrupted, queued sessions become pending again, and interrupted sessions flow into the same preflight-then-continue path as any other resume.
- **Event Plumbing**. The dispatcher sequences and fans out each session's event stream to GUI, CLI, history recorder — and buffers for replay so a late or reconnecting subscriber can catch up without the operation knowing.
- **Event Delivery Classes**. Progress events may be coalesced or dropped in favor of the latest snapshot; item outcomes and state transitions reach the history observer under the timeout-guarded audit guarantee, and are never silently dropped for any subscriber — ejection is always announced explicitly. A subscriber attaching late instead receives current state plus a bounded tail, using the envelope's gap-free sequence number to detect what it missed.
- **Versioned Event Envelope**. Every event carries a schema version, so a persisted or cached event can still be read correctly after the shape evolves.
- **Session Table**. The dispatcher is the single source of truth for which sessions exist and their current state; the desktop task rail and any CLI status surface are both just views over this table.
- **Orderly Teardown**. Application shutdown stops admission, drains or cancels running sessions, and confirms every lock released before exit.
- **What the Dispatcher Is Not**. The dispatcher never sequences a workflow's internal steps, never interprets a domain result beyond its terminal status, and never writes to the main ledger or history database (its own persisted session table is the sole exception); coordination, recording, and domain meaning stay in workflows, the recorder, and observers.

- **Queue Launch Policy**. Committed sessions found queued on GUI launch will wait for explicit confirmation before running; a CLI flag will authorize executing already-committed queued plans without that per-launch confirmation. The flag releases the queue; it never waives plan review.

## SCANNER

- **Recursive Metadata Scan**. The scanner records root-relative regular files with size, nanosecond modification time, and filesystem identity.
- **Directory Inventory**. Every walked directory is retained as a directory record carrying the same metadata snapshot as files plus optional filesystem identity — created directories need reviewed metadata, empty directories need creation and cleanup planning, and a future directory-level move operation needs identity, all served by the same record.
- **Ignored-Path Filtering**. NamiSync excludes application databases, checksum sidecars, common Windows metadata files, sync trash, and generated temporary files — always by exact, fully-qualified name shape, never by suffix or substring, so a user file can never be silently excluded for resembling an application artifact.
- **Scan Warnings**. Access errors, filesystem case collisions, and names outside the safe root-relative path contract are retained in scan results for plan review; hostile names are escaped for display and make the scan incomplete without aborting safe siblings.
- **Cooperative Scan Cancellation**. Scans check for cancellation while walking directories and files.
- **Placeholder Detection**. Cloud-backed placeholder files (OneDrive, Dropbox, and similar reparse-tagged files) are recognized from their attributes without being opened, recorded as unsupported, and reported as scan warnings instead of being read and silently hydrated. Unsupported entries are typed scan records in their own right — they flow through inventory and plan review as blocked, never-executable items rather than living only in warning text.
- **Filesystem Capability Profile**. Each scanned root records its filesystem type, timestamp granularity, and whether stable file identity is available, so the planner and preflight can reason about what a root's metadata can and can't prove.
- **Junction Cycle Protection**. The scanner tracks visited directory identities while walking so a directory junction or reparse loop cannot recurse indefinitely.
- **M0 Scanner Implemented**. Native walking and selected-path observation produce deterministic typed snapshots with exact owned-artifact ignores, conservative capabilities, cooperative cancellation, placeholder/reparse blocking, collision/hostile-path warnings, and explicit completeness. On stable-identity volumes, the native walk recovers an entry identity with a second metadata-only stat when Windows directory enumeration omits it, preserving correspondence-qualified moves without inventing evidence.

- **Change-Journal Scanning**. The scanner sits behind a pluggable change-source interface; a future NTFS USN-journal-backed source will supply incremental changes without the planner or executor knowing the difference. It requires elevated access or a background service and remains unrealized.

## FILTERS

- **Location Ignores**. A location can carry ignore patterns evaluated during the scan walk itself, so ignored subtrees are never read; a complete scan is complete modulo its own ignores, and the missing-marking sweep respects that boundary.
- **Mapping Filters**. A mapping can carry filter patterns applied symmetrically to both scanned sides before diffing, so an excluded file never appears as a one-sided change; filters never affect scan completeness, only what the planner is allowed to see.
- **Filtered Rows Stay Evidence**. A tracked row that becomes excluded is marked excluded, not missing or deleted; its prior evidence is retained and it leaves the default view the same way an acknowledged-missing row does.
- **Filter Snapshot in Plans**. A plan records the filter set it was built under, so preflight can detect when filters changed since planning and treat the plan as stale.

- **Filter Rule Editor**. The desktop UI will offer a rule editor with a live preview of what a filter set would exclude.

## PLANNER

- **Scoped Planning**. The planner accepts a scope over candidate files as a first-class input — everything, a pattern, an explicit selection, or the file set recorded by a past run — so ordinary sync, filtered execution, and history replay are the same mechanism applied to different scopes.
- **Destination Policy Seam**. Every operation's target path comes through a destination policy, and diffing matches source to target through that computed destination — path-preserving is simply the default policy — so restructure-on-copy workflows such as ingest change a policy implementation, never the planner's diff logic.
- **Filesystem Capability Awareness**. Diffing compares timestamps within the coarser of the two roots' recorded timestamp granularity, and move detection is disabled on any root whose filesystem doesn't support stable file identity, instead of silently misreading FAT-family timestamps and identities as reliable.
- **Metadata-Based Diffing**. Matching size, modification time within filesystem granularity, and standard attributes produces a no-op; changed size, time, or attributes produces an update. Content-aware comparison remains later work.
- **Copy and Update Planning**. Source-only files become copies and changed matched files become updates.
- **Case-Mismatch Conflict**. One source and target entry with the same Windows key but different exact casing becomes a typed blocked conflict rather than an invisible no-op; a directory mismatch blocks its dependent subtree until reviewed.
- **Move Detection**. Unambiguous source filesystem-identity changes can become target-side moves; an identity observed at more than one scanned path is excluded from consideration.
- **Composite Move-Update**. A detected move whose content also changed is planned as one composite operation whose evidence records only at full completion, so a crash partway can never leave old content at the new path while the ledger claims consistency.
- **Directory Operations**. Every directory the plan will create — empty, or the parent chain of planned copies — is an explicit reviewed `mkdir` operation carrying its source directory's metadata; the executor never creates a directory implicitly. Removable target-only empty directories become policy-controlled operations.
- **Directory Rename Decomposition**. A renamed or moved source folder is never a directory-level operation: it decomposes into per-file identity moves, the full `mkdir` chain for new locations, and cleanup of the directories it emptied. Target-side file moves are same-volume renames, so a folder rename copies no content bytes. Plan review presents the decomposition grouped under the folder so it reads as one rename, not thousands of rows.
- **Conflict Blocking**. Case collisions and file-directory conflicts remain visible as blocked conflict operations instead of being guessed through.
- **Capacity Planning**. Plans conservatively compute required bytes for all copy and update work, with temporary-file accounting sized for the maximum number of concurrently in-flight temp files rather than assuming one at a time; target free space is never baked into the plan — it is observed at review and preflight time, where the one shared capacity formula judges it.
- **Stable Plan Ordering**. Operations receive deterministic per-plan identifiers and dependency-aware ordering.
- **M0 Planner Implemented**. Pure path-preserving planning now emits deterministic copy, update, no-op, correspondence-qualified move/move-update, explicit directory, policy removal, cleanup, case-mismatch conflict, and blocked review items using the shared capacity function; canonical serialization is total for malformed surrogate code units without changing valid-Unicode fingerprints.

- **Content-Aware No-Op Detection**. Planning will use hashes or another content check before accepting metadata-equal files as unchanged.
- **Hash-Based Move Detection**. Move detection will extend beyond source filesystem identity to evidence-aware content matching.
- **Human Conflict Resolution**. Unresolved conflicts remain retained for post-run user review and re-planning instead of staying permanently blocked with no path forward.

## PREFLIGHT

- **Pure Verdict Function**. Preflight takes a plan-and-selection pair plus current filesystem state and returns a verdict; it never mutates the plan or the filesystem.
- **Repeatable, Not One-Shot**. The same function runs at plan review, at the start of every execution session, after any resume, and on queued-job wakeup — always invoked by the owning workflow. The executor never calls preflight itself; its own defense is re-validating each operation's direct preconditions at the moment of touch, because preflight is one stage of TOCTOU prevention, never the last.
- **Scoped Re-Check**. Only the remaining selected operations are re-stated; preflight never re-walks the full tree.
- **Plan Integrity Check**. Confirms the selection is dependency-closed and no selected operation depends on a deferred, failed, or blocked one.
- **Selection-Aware Scan Completeness**. An incomplete or errored scan makes absence- and identity-dependent `move`, `move_update`, `trash`, and `delete` operations unexecutable, but does not refuse evidence-positive `copy`, `update`, `mkdir`, or guarded `noop` work. The degraded run is therefore additive and may be incomplete, never destructive on incomplete knowledge.
- **Staleness Check**. Confirms each remaining operation's source and target evidence still matches what the plan recorded.
- **Capacity Check**. Recomputes required bytes for the remaining selection against current target free space, counting only exact prior-run NamiSync temps in the observed touched-parent scope as recoverable so a nearly-full target cannot loop-refuse over space the run itself will free.
- **Safety Check**. Confirms roots still resolve to their recorded volume identity, and that the trash directory resolves onto the target root's own volume without escaping through a reparse point and is writable.
- **No Repair**. A refused verdict carries per-operation reasons and the observed snapshot; preflight never re-plans, drops, or patches operations to make them pass. Workflow derives the reviewed safe subset before preflight, and preflight independently rejects any caller that reintroduces blocked, quarantined, or completeness-unsafe work.
- **M0 Preflight Implemented**. Scoped read-only observation and pure judgment now validate selection-aware scan completeness, blocked correspondence, remaining dependencies, touched evidence and parents, roots/volumes, semantic settings, capacity, trash safety, containment, and path representation with typed refusal reasons.

## EXECUTOR

- **M0 Native Executor Implemented**. A single-worker Windows executor now runs
  reviewed copy, update, move, move-update, mkdir, trash, delete, and no-op
  operations with operation-local evidence guards, typed continuation outcomes,
  injected copy/failure/filesystem seams, and post-filesystem recorder calls.
- **Atomic Copy and Update**. File content is written to a target-volume temporary file, flushed and fsynced, metadata-preserved, atomically published, and followed by a best-effort parent-directory flush through a writable Windows directory handle; a flush the filesystem refuses downgrades to a per-operation warning, and power-loss durability is claimed only for what was actually flushed.
- **Source-Drift Guard**. Copy and update operations re-stat the source after the read stream closes; a mismatch against the plan's recorded evidence fails the operation instead of recording a hash for content that changed underneath it.
- **Hash on Copy**. Successful copies and updates calculate a SHA-256 digest from the source byte stream during copying.
- **Contention Retry Policy**. A failure policy distinguishes transient sharing violations, which retry with bounded backoff, from persistent locks, which fail with a typed reason the plan view can show. Multi-step update and move-update retries retain and revalidate their completed backup/publish sub-step, then resume at replace or old-to-trash rename instead of restarting into false drift or destination occupancy.
- **Metadata Preservation Scope**. Copies and updates preserve modification time and standard attributes (readonly, hidden, system) by default; creation time is preserved where supported, and ACL/owner preservation is an explicit, off-by-default policy flag whose security descriptor is copied at execution time. Observed and intended metadata travel as a typed snapshot on scan records and plan operations, and the readonly attribute is applied only after publish. Alternate data streams are **not** yet preserved — a loudly documented limitation, never a silent one (see the deferred ADS bullet below).
- **Guarded Target Moves**. Target-side moves refuse existing destinations and preserve the existing target file record when recorded.
- **Root-Local Trash**. Trash operations move items to `.synctrash/<run-id>/<relative-path>` on the target volume.
- **Trash-on-Update**. Updating a file preserves its existing target version into the run's trash before the replacement publishes — by an atomic same-volume hardlink where the volume supports one, or by a crash-safe backup copy (temp-flush-publish inside the trash run directory) where it doesn't, with capacity planning counting those backup bytes — and only then atomically replaces the live path, so no crash point ever leaves the target absent; this is on by default and can be disabled per mapping.
- **Guarded Deletion**. Internal mirror deletes and empty-directory cleanup validate type and emptiness before removal. Cleanup of a directory emptied by its successful child operations requires exact kind, size, and immutable metadata while tolerating only self-induced mtime/link-count churn; stable identity binds when the reviewed scan supplied it, and absent identity is absent evidence rather than a veto. `RemoveDirectory` remains the atomic final emptiness guard.
- **Directory Metadata**. Created directories receive the source directory's recorded attributes, and directory timestamps are applied only after every child operation inside that directory has settled — child creates and renames churn parent directory times, so directory times are restored last.
- **Partial Result Reporting**. Independent operations continue after failures, with per-operation succeeded, skipped, failed, and canceled results.
- **Validated Safe-Subset Execution**. M0 derives and commits the maximal safe dependency-closed selection. Directly blocked plan items are excluded as `BLOCKED`; operations overlapping their source/target correspondence or depending on them are `DEFERRED`; and incomplete scans withhold move, move-update, trash, and delete globally. Copy, update, mkdir, and guarded no-op work continues. Exclusions are itemized in result/history without changing successful selected filesystem work to failure.
- **Progress and Cancellation**. Execution reports overall and per-file byte progress and checks cancellation between operations and copy chunks.
- **Content-Byte Accounting**. Progress and throughput totals count transferred copy and update content only; same-volume move, trash, and delete metadata operations never inflate byte progress or ETA.
- **Temporary-File Recovery**. Once per successfully preflighted execution, before copying, orphaned NamiSync temporary files are cleaned from the same touched target-parent set used for capacity accounting. Recovery matches only `<name>.synctmp-<run-id>-<op-id>`, removes only same-volume regular files owned by a different run, preserves current-run temps, off-volume mounts, and substring lookalikes, never enters `.synctrash`, and never walks the full tree.

- **ADS Preservation**. Alternate-data-stream preservation remains unrealized executor flesh, but its contract is settled: enumeration happens at copy time in the executor, which already holds the file — no scanner, planner, or schema change, and the scanner stays role-free. NTFS updates a file's modification time when any stream is written, so ordinary metadata diffing already schedules the update that re-copies streams (a test-verified assumption before the feature ships) — though a writer that suppresses or restores mtime evades that signal, so the feature claims stream refresh only through ordinary update scheduling, never independent ADS-only convergence. Streams are user data: a requested stream that fails to copy on a capable target fails the operation, and a mapping requesting ADS onto a stream-incapable target volume surfaces as a mapping-level warning at plan time. Documented residuals: stream bytes are not counted by capacity planning, and stream content is copied but not attested — ledger hashes cover the main data stream only.
- **User-Edited Partial Execution**. Future user-selected subsets will reuse M0's dependency closure, summary/capacity recomputation, commitment binding, and explicit deferred-outcome foundation.
- **Restartable Large-File Copy**. Large-file copies will support resuming from an interrupted offset with a persisted partial digest, instead of restarting from zero.
- **Multithreaded Copy Workers**. Independent copy operations will run across parallel workers under one session, with merged progress and ordering handled by the session rather than the copy loop, and capacity accounting already sized for every concurrent in-flight temp file.
- **Background IO Throttling**. Execution will support a pacing knob for background or lower-priority runs, independent of the progress-reporting throttle.
- **Robocopy Copy Backend**. NamiSync will evaluate an optional Robocopy backend for bulk moves that accept copy-now, baseline-later trust, while retaining its own planning, trash, and safety controls.

## INVENTORY

- **Role-Free Location Inventory**. A location can be scanned and retained independently of any source or destination role.
- **Mapping Guidance**. Inventory displays zero, one, or many stored mapping relationships and requires explicit paired roots when relationships are ambiguous.
- **Missing Retention**. Complete scans mark unseen tracked files missing while preserving their prior metadata and hashes.
- **Missing Acknowledgement**. Missing rows can be acknowledged to hide them from the default view without deleting their evidence.
- **Acknowledgement Restore**. Acknowledged missing rows can be restored to the normal missing view.
- **Reappearance Tracking**. Files returning after being marked missing are surfaced as reappeared until a matching hash or new baseline resolves the state.
- **Selected Inventory Refresh**. Selected paths can be refreshed without walking the entire location or inferring unselected absences.
- **Evidence Staleness**. Inventory can filter and summarize rows by hash and verification age, and select every row older than a chosen cutoff for re-verification, turning last-seen, hash-observed, and last-verified timestamps into a visible freshness signal instead of silent bookkeeping.

- **Shared Network Inventory**. Inventory merging across hosts and network locations remains unrealized.

## VERIFIER

- **Baseline Creation**. Baseline creates SHA-256 hashes for present inventory rows that do not already have a hash.
- **Location Verification**. Verification rereads present files against retained size, modification time, and SHA-256 evidence.
- **Cache-Honest Reads**. Verification reads bypass the page cache, or are deliberately deferred after a fresh write, so a match attests the medium rather than a buffer NamiSync itself just filled.
- **Integrity Outcomes**. Verification distinguishes verified, baselined, mismatched, modified, missing, unsupported, canceled, and error results.
- **Selected Verification**. Present inventory files selected in the UI can be verified without verifying the entire location.
- **Post-Execution Verification**. A sync can automatically verify eligible copied, updated, and moved files after execution.
- **Safe Conditional Recording**. Hash and verification results are persisted only when the file state remains consistent with the observation being recorded.
- **Accept and Re-Baseline**. A file correctly reported as modified can be explicitly re-baselined, accepting its current content as new evidence through the same conditional-recording path, instead of remaining reported modified forever with no path forward.
- **Verifier Operation Implemented**. The isolated baseline, verify, and explicit rebaseline operation now provides cache-honest Windows reads, typed per-file outcomes, safe conditional ledger recording, and lossless pause/cancel continuation. Inventory selection, workflow registration, history detail, and UI/CLI composition remain the M1 product surface.

- **Multithreaded Verification**. Verification speed can be CPU-bound on faster disks, the verifier should run multithreaded conditionally.
- **Automatic Background Integrity**. Background hashing and verification remain unrealized.
- **Repair Guidance**. When one side of a mapping mismatches its evidence, verification will compare both sides' current hashes against recorded evidence and diagnose which side is damaged, as a first step toward a guided restore from the healthy side.

## TERACOPY HASH IMPORT

- **SHA-256 Sidecar Parsing**. NamiSync reads UTF-8 TeraCopy `.sha256` sidecars with safe relative paths and duplicate-entry checks.
- **Existing-Inventory Import**. Sidecar hashes are accepted only for existing, present, unchanged, unhashed inventory rows inside the selected location.
- **Hash Protection**. Established database hashes are never overwritten; matching values are reported as known and differing values as conflicts.

## RECORDER

- **Single Write Path**. The recorder is the only code path that writes the main ledger; execution, verification, baseline, and TeraCopy import all call it rather than issuing SQL of their own.
- **Conditional Recording Primitive**. Every hash or verification write is conditional on the row's current id, state, size, and modification time still matching what was observed; a mismatch discards the write instead of recording evidence about a file that has already moved on. This one primitive is what makes hash-on-copy, baseline, verify, and sidecar import all safe against the same race.
- **Provenance Tagging**. Every hash write records how it was attested — inherited from a copy's source stream, a direct read-back, or an independent verification — so displayed trust never overstates what was actually checked.
- **Bounded-Window Durability**. Ledger commits batch by operation count or elapsed time rather than one write per operation, with an immediate forced flush before any destructive operation, at pause-drain, and at session terminal — bounding the crash window to at most one batch without weakening the never-wrong-only-behind guarantee.
- **Idempotent Recording**. The recorder treats a repeated run token as a no-op, backed by the ledger's own uniqueness constraint as the last line of defense.
- **Serialized Writer**. All in-process sessions record through one serialized writer, so legitimately parallel disjoint-volume runs can never silently lose bookkeeping to ledger lock contention; cross-process writers get a generous busy timeout with bounded retry, and a recording failure is always surfaced, never swallowed.
- **Axis-Separated Truth**. A session's terminal state reports its filesystem work alone; ledger bookkeeping and audit history report through separate recording and audit statuses carried in the result. Completed work with a failed or lagging write on either store surfaces as completed-with-degraded-recording (or -audit) — loudly, in the UI, CLI exit detail, and history — and the behind store converges rather than the result lying on any axis.
- **M0 Recorder Implemented**. One run-bound serialized recorder now covers every sync operation, eager per-command durability behind the final flush seam, idempotent run/operation tokens, bounded cross-process retry, scalable inventory reconciliation, and the shared conditional baseline/verify/rebaseline evidence transaction.

## FILES LEDGER

- **Local SQLite Ledger**. NamiSync stores hosts, physical locations, inventories, mappings, runs, and mapping-specific file correspondence in a local schema-versioned database.
- **Windows Path Identity**. Location and relative-path keys normalize Windows separators and case without relying on SQLite `NOCASE`; ambiguous suffixes and malformed surrogate code units remain typed scan evidence rather than persisted path identity.
- **Volume-Anchored Location Identity**. Locations key off stable volume identity — on-disk serial plus filesystem type — and a volume-relative path; label and similar mutable attributes are corroborating evidence, not key material, so a relabel is a silently-noted footnote while a reformat (same serial, different filesystem) demands explicit rebind. The drive-lettered path is a derived display value, never stored identity.
- **Host as Provenance, Not Identity**. Hosts tag observations and runs with which host produced them rather than anchoring location identity, so two hosts sharing one physical volume each keep truthful, independent evidence without needing to arbitrate authority.
- **Offline Volumes**. A location whose volume is not currently mounted is offline, not missing; a complete scan never marks its rows missing because the disk itself is absent.
- **Known-Volume Recognition**. A previously known volume serial reappearing under a different drive letter resolves automatically and silently; this is letter resolution, not rebind, and needs no user action.
- **Manual Rebind**. Moving a location to a new path or volume is always a user-initiated rebind that spot-checks a sample of tracked rows against the new location before committing; NamiSync never infers a rebind automatically.
- **Cloned-Volume Ambiguity**. Two mounted volumes reporting the same identity evidence are never silently resolved; NamiSync demands an explicit user choice.
- **Hardlink Disqualification**. A file identity observed at more than one scanned path, or reporting more than one hard link, is disqualified from move detection and recorded as a scan warning.
- **Mapping-Scoped State**. Shared physical locations can participate in multiple mappings while retaining independent source identity and correspondence state.
- **Run Idempotency**. Executor run tokens uniquely correlate and protect repeated ledger recording.
- **Generic Annotations**. A generic entity-scoped annotations table (kind, id, key, value) carries small user-authored labels — a session note, a future task annotation — without a schema change each time a new place wants one.
- **Local Settings File**. Cosmetic and semantic application settings live in a local settings file beside the databases, not inside the ledger schema; settings that shape a plan, such as filters, are snapshotted into the plan itself when used, so preflight reasons about the values in effect at the time rather than values that may have since changed.
- **Database Safety Settings**. Ledger connections use foreign keys, WAL mode, and a bounded busy timeout.
- **M0 Ledger Implemented**. Versioned ledger/history schemas now freeze identity and evidence fields, enforce mapping-correspondence location integrity, separate observed from attested stats, expose read-only typed inventory/mapping/run repositories, and refuse configured database paths inside managed roots.

- **Hardlink Groups**. Schema room is reserved for grouping paths that share one file identity, so hard-link-aware correspondence and, later, hard-link preservation on copy remain additive rather than a rework.
- **Named Mappings**. A mapping will carry a user-assigned display name distinct from its source and target paths.
- **Legacy Data Migration**. Migrating or merging version 1 and version 2 ledger data remains unrealized.
- **Schema Migration**. A dedicated migration module, independent of the core sync path, will carry the ledger and history schemas forward through an ordered, versioned sequence of steps with an automatic pre-migration backup, replacing the reset-and-refuse posture once real evidence needs to survive an upgrade.

## DATA PROTECTION

- **Scheduled Integrity Maintenance**. Database health checks and backups will run as an ordinary dispatcher session rather than a separate daemon, performing a quick integrity check and writing a dated, atomic backup snapshot on a schedule or on demand.
- **Backup Rotation**. Dated backup snapshots will be pruned by age or count, with an optional second-volume destination for the snapshots themselves.
- **Manual Export and Import**. Either database will be exportable to a portable file and re-importable, independent of the scheduled backup path.
- **Trash Retention Policy**. Trashed items, including versions displaced by trash-on-update, will be pruned by an age or size cap; capacity planning counts live trash as consumed target space so the cap is enforced before it becomes a full disk.
- **Undo From Trash**. Restoring a run's trashed items will be generated as an ordinary plan through preflight and the executor, so conflicts from later runs touching the same paths surface as ordinary plan conflicts. Before running, the restore will show whether it can fully restore the run or only part of it, and why.
- **Soft-Deleted Mappings**. Deleting a mapping will hide it and its evidence behind a deleted-at marker rather than discarding anything immediately; deletion will show an impact summary first, the mapping will stay restorable until an explicit purge, and creating a mapping matching a soft-deleted one's source and target will offer restore instead of a duplicate.

## HISTORY

- **Independent Audit Store**. Sync, baseline, verification, and TeraCopy import attempts are recorded in a separate local history database.
- **Audit Delivery Guarantee**. History subscribes at session admission on the reliable event plane under one clear contract: every audit event is delivered within the timeout, or the session result says `audit=DEGRADED` — nothing is ever silently lost behind a result claiming OK. When its bounded buffer fills, the producer briefly waits at a checkpoint boundary rather than discarding audit events, with the wait capped by a generous timeout — a stalled or failed history writer degrades the session's audit status loudly and blocking stops, rather than holding filesystem work hostage. History finalizes each run in a bounded two-phase step: it acknowledges its final write before the immutable terminal event is released to other subscribers, so the result's audit status already tells the truth about the history row itself; an acknowledgement timeout degrades the audit status and releases the terminal anyway. A history write failure is surfaced loudly on the session result but never blocks, fails, or falsifies filesystem work, and a process crash loses at most the bounded in-flight buffer — the same never-wrong-only-behind posture as the ledger.
- **Typed Run Details**. History retains activity-specific summaries and ordered sync operations or integrity issues.
- **No-Op and Cancellation Audit**. Explicit no-op and canceled activities are recorded alongside successful and failed activities.
- **Blocked And Deferred Audit**. Safe-subset runs retain every direct blocker as the sixth `BLOCKED` outcome and retain quarantined or incomplete-scan-withheld work as `DEFERRED` with typed reasons and itemized paths. The history schema stores a blocked summary count without multiplying quarantine/withholding into new top-level categories.
- **History Idempotency**. Repeating a recorded run token does not create a duplicate history entry.
- **History Retention**. Summary and detail retention settings can prune old history detail while preserving the run envelope and summary.
- **History Browsing**. Retained runs and their details can be inspected in the desktop History dialog or through the CLI.
- **M0 Sync History Implemented**. The independent store consumes the dispatcher's reliable preterminal observer protocol and persists idempotent sync envelopes, axis-separated summaries, and ordered typed operation details; the workflow composition root now exposes those reads to the CLI.

- **Task-Grouped History**. GUI activities will be grouped under durable task records while CLI and service activities remain valid without a task parent.
- **Task Annotations**. Users will be able to add a trimmed plain-text task annotation of up to 256 characters.
- **Restorable Task Setup**. Opening history will restore a task's saved inputs and options while requiring a fresh plan before execution.
- **History Replay**. A retained run will be replayable by rebuilding the planner's scope from its recorded file set and planning fresh against a newly selected target; plan review will diff current content against recorded evidence and surface any drift instead of assuming the files are unchanged. Replay stays available only while a run's detail remains unpruned.
- **Queue Discard Audit**. A queued session discarded before it ran will still be recorded as a discarded, unrun history entry — typed as a canceled terminal carrying the `unrun` disposition, never inferred from a zero-length operation list or a parsed string — so the browsable timeline accounts for planned-but-abandoned work alongside completed runs.
- **History Export**. Retained runs and their detail will be exportable to CSV or JSON for external audit trails.

## COMMANDLINE

- **Sync Command**. `nami-sync sync` runs the plan session, prints the reviewable plan, and asks for explicit terminal confirmation; confirming commits the plan and immediately runs the execution session, declining leaves it uncommitted. A separate flag executes already-committed queued plans for scripted use; no flag combination plans and executes without a review.
- **Inventory Command**. `nami-sync inventory` scans one location and prints its retained inventory and mapping guidance.
- **Baseline Command**. `nami-sync baseline` creates missing baselines and reports integrity counts and issues.
- **Verify Command**. `nami-sync verify` verifies one location and returns a failing exit code when integrity issues are found.
- **Hash Import Command**. `nami-sync import-hashes` imports explicit TeraCopy sidecars for one location.
- **History Command**. `nami-sync history` lists recent audit runs or prints one retained entry with detail.
- **Database Overrides**. CLI integrity commands can select separate main-ledger and history database paths.
- **No-Subcommand Behavior**. Until a desktop implementation exists, running `nami-sync` or `python -m namisync` with no subcommand prints usage and exits nonzero; nothing ever runs implicitly.
- **Concurrent Read-Only Commands**. Read-only CLI commands such as history and status run alongside a GUI session or other CLI invocations; mutating commands are subject to the same volume and queue arbitration as any other session.
- **M0 Workflow And CLI Implemented**. `nami-sync sync` and `python -m namisync sync` now execute the real two-session scanner → planner → safe-selection/preflight → explicit commitment → fresh-preflight → executor/recorder pipeline through dispatcher custody. Review and execution distinguish runnable, blocked, and deferred work; completed safe subsets exit with the dedicated partial status while `nami-sync history` retains itemized exclusions. Real entry points, no-op correspondence/history, stale-plan refusal, declined-review non-mutation, database isolation, and import boundaries have integration coverage.

- **GUI Entry Points**. Once the desktop application exists, running `nami-sync`, `nami-sync-gui`, or `python -m namisync` with no subcommand will launch it.

## DESKTOP UI

- **Task Rail**. The window provides a scrollable newest-first rail of task cards with status, paths, completion date, close controls, and mini progress bars.
- **Single-Page Task Shell**. Each task keeps source, destination, options, status, progress, plan, inventory, and log controls on one page.
- **Folder Selection**. Source and destination support editable recent-folder dropdowns and folder browser buttons.
- **Plan Tree**. The Plan view displays operations in a directory-nested tree with rolled-up counts, sizes, reasons, hashes, and statuses; a decomposed folder rename reads as one folder-level group, not a flat run of per-file moves.
- **Inventory Tree**. The Inventory view displays retained files in a directory-nested tree with presence and integrity states.
- **Plan Filters**. Plan review can filter All, Changes, Moves, and Conflicts with live counts.
- **Inventory Filters**. Inventory review can filter All, Verified, Baseline, Unbaselined, Missing, Reappeared, and Acknowledged rows with live counts.
- **View Toggle**. A persistent Plan | Inventory toggle switches between retained plan and location-inventory views without conflating them.
- **Inventory Actions**. Menus and row context actions support selected verification, missing acknowledgement, acknowledgement restore, path copying, inventory, baseline, and import workflows.
- **Live Progress**. Sync, scan, baseline, verification, and import workers update overall and per-file progress with current paths and counters.
- **Cooperative UI Workers**. Long-running operations run through cancellable worker sessions with guarded cleanup and release handling, independent of whichever UI toolkit hosts them.
- **GUI Single Instance**. A second desktop launch is refused with a message naming what the running instance is doing, rather than starting a duplicate window; read-only CLI commands and non-conflicting CLI mutations are not subject to this restriction.
- **Mismatch Severity**. A mismatched-hash row — content differing from recorded evidence while its stats look unchanged — renders distinctly from an ordinary modified row, with a persistent badge on the location until acknowledged; it is the one signal this application exists to surface and it never reads as just another list row.
- **Dark Theme**. The desktop shell uses a dark-only theme with status colors, operation-kind colors, alternating tree rows, and styled progress controls, regardless of the underlying UI toolkit.
- **History Dialog**. The desktop UI lists history runs, shows retained activity detail, and applies history-only retention settings.

- **Drag-and-Drop Setup**. Dropping folders onto a task will populate its source and destination fields.
- **Status Layout Refinement**. The task header will unify live and completed detail while promoting activity state over the affected-byte figure.
- **Rolling Transfer Metrics**. A rolling estimator will provide responsive throughput and phase-aware ETA instead of the current whole-run average.
- **Throughput Graph**. The UI will graph current transfer rate against execution progress.
- **Plan Follow Mode**. The Plan view will follow the active operation until the user deliberately scrolls away, including collapsed-tree handling.
- **Live Integrity Feedback**. The Inventory view will follow the file being hashed and later update per-file outcomes as verification progresses.
- **Failure Triage**. Failed operations will group by cause and common path prefix with a suggested action, instead of presenting a long flat list of individual failures.
- **Cancel and Pause Safety Messaging**. The cancel and pause affordances will state what happens to the in-flight operation and what's kept, phrased from the session's current phase rather than one generic warning.
- **Completion Notification**. A run that finishes while the window isn't focused will raise a system notification summarizing the outcome, including a call-out when it includes any mismatched files.
- **Guided Empty States**. Views with no data yet will explain the next step in the application's own vocabulary (locations, mappings, baselines) rather than showing a bare empty list.
- **Tree Search**. Plan and Inventory trees will support type-to-search filtering in addition to the existing category filters.
- **Mapping List View**. Stored mappings will be browsable and manageable as named, recurring relationships, not just visible as the source and destination of individual task cards.

## CROSS-PROCESS SAFETY

- **Physical-Volume Guard**. Filesystem workflows acquire deterministic cross-process locks for all required local physical volumes and refuse unsafe or contended volumes.
- **Root-Constrained Paths**. Planner, executor, and sidecar workflows reject absolute, drive-qualified, parent-traversing, or root-escaping relative paths.
- **Long-Path Support**. Filesystem workflows use `\\?\`-prefixed paths throughout so path length never becomes a silent failure mode, including for planned destination paths that are longer than their source.
- **External-Writer Boundary**. Volume locks arbitrate NamiSync processes only; external processes writing into a managed root mid-execution are outside the safety contract on every mutation, not just some. Conditional primitives enforce exactly their own condition — non-replacing renames guarantee destination absence, `CREATE_NEW` guarantees temp freshness, `RemoveDirectory` guarantees emptiness — and no path-based primitive binds source identity, so each residual race is bounded by its data consequence, never by elapsed time (the window is usually tiny, but a descheduled process can stretch it): trash-routed operations at worst preserve the wrong item recoverably, moves at worst misplace without destroying, and only update's replace and internal mirror deletes can destroy an external writer's file — never NamiSync's own displaced version, and never its evidence. `ReplaceFileW`, the supported single-call replacement with optional backup, is deliberately not used: it merges the replaced file's attributes, ACLs, and named streams into the replacement and documents partial-state failure cases — hardlink/copy-backup-then-replace is a chosen tradeoff, not the only Windows primitive.

- **Reparse-Point Preservation**. Preserving non-placeholder reparse points (symlinks, junctions) through copy and update remains unrealized; placeholder detection (see Scanner) is a separate, already-handled concern.
- **Network-Share Coordination**. Cross-process locking and scheduling for network shares remain unrealized.
