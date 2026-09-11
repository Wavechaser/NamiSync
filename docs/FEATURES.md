# Features

The headless sync/inventory/integrity/history/CLI capabilities and secured
desktop host/transport/presentation foundation are active. Production desktop
workflow surfaces remain unrealized unless stated otherwise below. Each feature
owns its behavior/status; M1_PLAN owns remaining delivery, and BRIDGE,
PRESENTATION and INTERFACES own protocol, projection and host contracts.

Reference documentation imported from the proof-of-concept lives in
[obsolete/PoC_import/](obsolete/PoC_import/); its `BUGS.md` preserves the
historical evidence behind many of this document's rules. These imported notes
are not current behavior or implementation guidance.

## PROJECT ARCHITECTURE

- **Layered Domain Design**. Core owns shared contracts and the session machine, isolated modules (scanner, planner, preflight, executor, verifier) own sync behavior, the database owns persistence, application workflows coordinate them, and interfaces adapt those workflows.
- **Headless Workflows**. Planning, execution, inventory, integrity, history, and reusable node-tree construction run without a desktop host and are shared by the desktop UI and CLI.
- **Thin Desktop Adapter**. The desktop UI presents workflow state and delegates sync decisions to headless layers; it owns disposable task/presentation state but never sync policy, authoritative selection, inventory reconciliation, or path interpretation.
- **Defense Policy**. `DEFENSE.md` owns the supported environment, trusted boundaries, hard walls, tolerance classes, and residual-risk dispositions that qualify every feature claim; a feature or defect residual is not accepted merely because this document describes it.
- **Typed Core Contracts**. Explicit dataclasses carry scan, plan, execution, progress, verification, and result data across layers.
- **Defensive JSON Boundaries**. Hash, persistence, and interface encoders require Unicode scalar text and preserve its established UTF-8 bytes; external command decoders reject malformed strings and keys before constructing requests. Malformed filenames and required text refuse, optional scan-warning detail is omitted without dropping observations, and invalid optional item diagnostics are omitted and counted before history storage. Process-local workflow checkpoints are typed domain values, not JSON boundaries.
- **Separate State Stores**. The working ledger and append-oriented audit history use independent local SQLite databases.
- **Session-Typed Operations**. Every long-running activity (scan, plan, execute, verify, baseline, import) runs inside one typed session contract: a shared state machine, a tagged-union event stream, and a cooperative checkpoint that pause and cancellation both resolve through, so no module invents its own lifecycle or terminal shape.
- **Workflow-Sequenced Pipelines**. Modules never call each other directly; an application workflow function sequences scan, plan, preflight, and execute by passing typed data forward, so coordination stays readable top to bottom instead of emergent from signals or callbacks.
- **Preflight as a Callable, Not a Gate**. Preflight validates a plan-and-selection pair against current filesystem state and can be invoked repeatedly — at start, at resume, after a selection change — instead of running once as an unrepeatable ritual.
- **Recorded Ledger, Observed History**. Execution and verification report through the Recorder module rather than writing SQL directly. Ledger commands commit through explicit durability boundaries, while the independent append-only history stream commits incrementally in bounded windows.
- **Axis-Separated Compound Results**. Filesystem execution, integrity readback, ledger recording, and audit history remain four independent truths. A copied file can be published successfully, verify as matching, and still report degraded ledger recording; no later phase rewrites an already-settled earlier phase.
- **Canonical Content Evidence**. Copy attestation, baseline, and verification use one fixed `xxh3_128` evidence format with a 16-byte digest and matching content/subject sizes. Plan fingerprints, dispatcher custody, history identity, and other small non-content hashes remain SHA-256.
- **Policy Extension Points**. New behavior (copy backends, retry and failure handling, deletion policy) plugs in as a protocol that returns a decision to the machine, never as a hook that receives control, so invariants stay enforced centrally regardless of which policy is active.
- **Pipeline-Only Mutation**. Every mutation to user data inside a managed root flows through plan, preflight, and execute — including undo and repair — so a corrective action's conflicts with later changes surface in ordinary plan review instead of a special-cased overwrite. App-owned artifacts (trash purge, database maintenance) are exempt from this law but stay type- and ownership-guarded and history-logged.
- **Sessions Never Block on a Human**. A conflict or error during execution is logged and the run continues past it; nothing pauses mid-run to wait on a decision. Review and any corrective action happen after the run ends, through the same pipeline as any other plan.
- **Never Wrong, Only Behind**. Because the recorder commits only after a filesystem mutation succeeds, every committed row is a true statement about a past observation. Current process-loss recovery re-scans and re-plans from that evidence; M2 durable-session recovery will additionally mark abandoned work interrupted before converging.
- **Injected Clock**. Time-dependent behavior — retention sweeps, staleness views, day-boundary filters — reads the current time through one injected clock dependency, keeping timezone- and DST-edge behavior testable rather than incidental.
- **Degenerate First Implementations**. A protocol earns its sophistication before its first implementation does; the recorder's batching, the event stream's conflation, and the queue's persistence each ship as the simplest correct behavior behind their real interface, with the interface — not a rewrite — absorbing later hardening.
- **Layer Benchmarks Before Scale-Up**. The recorder, the event pipeline, and the scanner walk are each benchmarked in isolation under synthetic load before broader features build on top of them, rather than discovering per-item overhead only at full scale.
- **Interaction Clusters**. Most feature interactions concentrate around four shared resources — disk space, inventory semantics, volume locks, and run bookkeeping. Features outside these clusters are reviewed for orthogonality alone; features touching them get deliberate pairwise review and note what they interact with inline.

- **Queue and Service Reuse**. The same headless workflows serve the active process-local queue, service facade, CLI, and desktop host without moving sync policy into an interface. Durable queue ownership extends those workflows in M2 rather than replacing them.

## SYNC WORKFLOW

- **One-Way Root Mapping**. NamiSync reconciles a distinct source folder into a distinct, non-nested destination folder.
- **Dry-Run Review**. Every sync scans both roots and produces a reviewable plan before filesystem mutation. Rename-shaped rows show the observed prior target path and planned target path, including visually meaningful case-only changes such as `keep.txt -> KEEP.txt` and the actual old-to-new paths for move and move-update operations.
- **Commit-to-Execute**. Execution happens only for a plan the user has reviewed and explicitly committed; each commitment binds the immutable plan, current reviewed selection, and approved task options for one attempt. The accepted Stage 6 flow includes linked verification in that commitment rather than asking again at execution. Selection freezes during admission and becomes editable again only if admission fails. Successful admission leaves it committed, including after preflight refusal or zero-byte execution. Every attempt still preflights first; the accepted M1 desktop recovery after post-admission refusal is fresh Plan Again work, without automatic retry.
- **Authoritative Review Selection**. Safety exclusions and direct user deselections are separate sets. The service owns revisioned review state, dependency-closes user changes, and re-derives the runnable selection from the plan plus canonical `user_deselected` provenance before accepting it. Plan Again creates a fresh task and fresh authorization; it never carries the old selection forward. An all-skipped selection is not executable; selected `NOOP` operations remain meaningful executable and auditable work.
- **Deletion Policies**. Paired sync supports `trash` by default and `additive`, while `mirror` is available only as an internal policy.
- **Trash Location Information** *(accepted M1 target; unrealized)*. Completion reports the trash location. An exact completed count is reported only when outcome evidence proves it complete; no planned count or full trash inventory is promised.
- **Run-Derived Recent Locations**. The workflow returns up to five recent sources, five targets, and five active pairings derived from durable ledger run activity, never merely from typing, picking, or probing. Soft-deleted mappings disappear; failed, canceled, degraded, unfinished, offline, and remounted locations remain in truthful history. Remembered identity is resolved afresh before use; a stored drive hint is not a current path. Setup displays the best current identity-based label available.

- **Durable Job Queue**. Durable queued jobs remain unrealized until M2. They will persist in the dispatcher's own session table, retain stale-plan defenses through the same preflight re-check every resume uses, and support optional re-planning with material-difference review before execution.

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

- **Domain-Blind Session Scheduling**. The dispatcher admits, schedules, and tracks sessions by their generic contract alone; no dispatcher method or code path is named for a specific activity such as sync or verify.
- **Volume-Scoped Concurrency**. Sessions whose required volumes don't overlap may run concurrently; sessions contending for the same volume queue behind each other. Concurrency is a property of the resources a session needs, not a single global one-at-a-time rule.
- **Cross-Process Volume Custody**. Multiple NamiSync processes may run at once; cross-process volume locks arbitrate managed disk access between them.
- **Durable Single Queue Owner**. M2 will add a file lock on the persisted queue so exactly one process at a time owns durable queued-session admission.
- **Resource Custody**. Each dispatcher worker attempt has a process-local generation key that owns its reservations and lease. A session has exactly one current attempt through pause/resume/cancel retirement handoffs, and custody is released only by the generation that acquired it.
- **Control Plane**. Pause, resume, and cancel are dispatcher operations that flip a flag a running session's checkpoint resolves against; the dispatcher enforces the legal state-transition table so illegal requests fail cleanly instead of corrupting session state. Pause is a per-kind capability declared at workflow registration: only session kinds with a continuation state (sync execution; verification's item-list sessions) accept it, while short continuation-less sessions refuse pause cleanly and stay cancelable.
- **Resume Outcomes**. Resuming a paused or interrupted session always preflights first. Fresh/unstarted work may be refused with reasons, but a started execute resume that has already mutated settles `FAILED+RAN` with its partial counters, and a verify resume preserves settled filesystem truth while reporting an incomplete verify phase; neither is mislabeled as a fresh refusal.
- **Resume Never Preempts**. A resumed session re-enters admission at the back of its volumes' queue: if another session took over the contended volume while it was paused, the resumed session runs when that session finishes or is itself paused or canceled. Jumping the queue would mean either force-pausing the running session or running two sessions on one volume — the first is confusing, the second is forbidden.
- **Session Metadata Storage**. M1 stores only lifecycle metadata and full results through a checkpoint-free stored-record contract; typed continuation checkpoints stay in live process memory, even when a metadata write fails. M2 durable metadata remains independent of ledger and history, but swapping metadata stores alone will not enable restart. Continuation recovery needs a separate protected recovery-store contract; current typed checkpoints and transient execution attestations are not durable recovery formats.
- **Startup Reconciliation**. M2 launch will require that separate protected recovery contract before reloading resumable work, marking work abandoned by a dead process interrupted, returning queued sessions to pending, and routing interrupted sessions through fresh authority/custody checks and preflight. M1 process close still offers no resume.
- **Event Plumbing**. The dispatcher sequences and fans out each session's event stream to GUI, CLI, history recorder — and buffers for replay so a late or reconnecting subscriber can catch up without the operation knowing.
- **Event Delivery Classes**. Progress events may be coalesced or dropped in favor of the latest snapshot; item outcomes and state transitions reach the history observer under the timeout-guarded audit guarantee, and are never silently dropped for any subscriber — ejection is always announced explicitly. A subscriber attaching late receives current state plus a bounded tail and a detectable gap; sparse committed reliable-event pages provide bounded catch-up through a fixed watermark, while a live cursor ahead of durability ends that traversal cleanly and retries against a fresh watermark.
- **Versioned Event Envelope**. Every event names its exact schema. Persistence readback rejects an unsupported envelope, and browser delivery rejects an unsupported transport marker rather than guessing how to read an older persisted or cached shape; trusted internal projections are not independently decoded. A version tag does not promise backward compatibility.
- **Session Table**. The dispatcher is the single source of truth for which sessions exist and their current state. It does not own desktop task identity: a desktop task is adapter state that can retain a reviewed plan while no session exists, and sessions come and go beneath it.
- **Orderly Teardown**. Application shutdown stops admission, drains or cancels running sessions, and confirms every lock released before exit. Terminal close distinguishes a reversible pre-hub timeout from irreversible stream detachment, retains unfinished ownership for caller/shutdown retry, and reports cleanup-pending attachment truthfully. The desktop vetoes synchronous WinForms close, performs teardown on one worker, destroys only after complete service shutdown, and offers Retry without a force-close path after an incomplete attempt.
- **What the Dispatcher Is Not**. The dispatcher never sequences a workflow's internal steps, never interprets a domain result beyond its terminal status, and never writes to the main ledger or history database (its own persisted session table is the sole exception); coordination, recording, and domain meaning stay in workflows, the recorder, and observers.

- **Queue Launch Policy**. Committed sessions found queued on GUI launch will wait for explicit confirmation before running; a CLI flag will authorize executing already-committed queued plans without that per-launch confirmation. The flag releases the queue; it never waives plan review.

## SCANNER

- **Recursive Metadata Scan**. The scanner records root-relative regular files with size, nanosecond modification time, and filesystem identity.
- **Directory Inventory**. Every walked directory is retained as a directory record carrying the same metadata snapshot as files plus optional filesystem identity, supporting reviewed metadata, empty-directory creation and cleanup, and conservative correspondence evidence.
- **Ignored-Path Filtering**. NamiSync excludes application databases, checksum sidecars, common Windows metadata files, sync trash, and generated temporary files — always by exact, fully-qualified name shape, never by suffix or substring, so a user file can never be silently excluded for resembling an application artifact.
- **Scan Warnings**. Access errors, filesystem case collisions, and names outside the safe root-relative path contract are retained in scan results for plan review; hostile names are escaped for display and make the scan incomplete without aborting safe siblings.
- **Cooperative Scan Cancellation**. Scans check for cancellation while walking directories and files.
- **Placeholder Detection**. Cloud-backed placeholder files (OneDrive, Dropbox, and similar reparse-tagged files) are recognized from their attributes without being opened, recorded as unsupported, and reported as scan warnings instead of being read and silently hydrated. Unsupported entries are typed scan records in their own right — they flow through inventory and plan review as blocked, never-executable items rather than living only in warning text.
- **Filesystem Capability Profile**. Each scanned root records its filesystem type, timestamp granularity, and whether stable file identity is available, so the planner and preflight can reason about what a root's metadata can and can't prove.
- **Trusted Mount-Root Admission**. A FULL scan may use the exact reviewed/native folder-mounted volume anchor as its root even though Windows marks that anchor as a mount-point reparse. The exception requires matching current mount and full volume identity, records followed mounted-root metadata, and never extends to final/intermediate configured-root junctions, scoped starts, placeholders, or descendants.
- **Junction Cycle Protection**. The scanner tracks visited directory identities while walking so a directory junction or reparse loop cannot recurse indefinitely.
- **Explicit Scan Scope Shapes**. Scanner scope distinguishes a full root, exact paths, and recursive subtrees. Mixed exact/subtree requests canonicalize overlapping roots, and a selected root becomes a full scan; reconciliation mirrors those three shapes rather than treating a subtree as one selected path.
- **Scope-Honest Completeness**. Owned artifacts and harmless file placeholders/reparse entries are typed exclusions without making the scan incomplete. Unreadable directories, directory placeholders/reparse points, repeated directory identity, collisions, and unsafe names retain typed warnings and make the affected scope incomplete. PATHS and SUBTREES no-follow admit every existing intermediate component before observing their requested subjects.

- **Change-Journal Scanning**. An unrealized change-source protocol will allow a future NTFS USN-journal-backed scanner to supply incremental changes without the planner or executor knowing the difference. The exact protocol will be standardized with its first production consumer; journal access may require elevation or a background service.

## FILTERS

- **Scanner-Owned Ignores**. The scanner invisibly excludes only fixed
  application/Windows artifacts (`DESKTOP.INI`, `THUMBS.DB`, owned temporary
  names, and `.SYNCTRASH`) by exact qualified grammar. They are intentional
  non-subjects and do not make a scan incomplete. User filters remain a separate
  fingerprinted planning policy, not a mutable scanner ignore snapshot.
- **Filter Snapshot in Plans**. Planning applies filters symmetrically, records and fingerprints the resulting snapshot, and never lets later default changes alter a reviewed plan. In the accepted Stage 6 desktop, changing filters creates a new planning task requiring fresh review and commitment.
- **Bounded Setup Filters**. Setup accepts nonempty bounded Unicode glob patterns and retains literal whitespace. Planning freezes their canonical snapshot; later defaults never replace it. [PLANNER.md](PLANNER.md#exclude-filter-syntax-and-effect) explains syntax, examples and symmetric source/target protection; `BRIDGE.md` owns bridge admission.

- **Filter Rule Editor**. The desktop UI will offer a rule editor with a live preview of what a filter set would exclude.
- **Filter Exclusion Explanation**. Plan review will eventually explain why a filtered file has no operation row; current interfaces do not invent such rows or claim this gap is solved.

## PLANNER

- **Scoped Planning**. The planner accepts a scope over candidate files as a first-class input — everything, a pattern, an explicit selection, or the file set recorded by a past run — so ordinary sync, filtered execution, and history replay are the same mechanism applied to different scopes.
- **Destination Policy Seam**. Every operation's target path comes through a destination policy, and diffing matches source to target through that computed destination — path-preserving is simply the default policy — so restructure-on-copy workflows such as ingest change a policy implementation, never the planner's diff logic.
- **Filesystem Capability Awareness**. Diffing compares timestamps within the coarser of the two roots' recorded timestamp granularity, and move detection is disabled on any root whose filesystem doesn't support stable file identity, instead of silently misreading FAT-family timestamps and identities as reliable.
- **Metadata-Based Diffing**. Matching size, modification time within filesystem granularity, and the shared managed attribute mask (readonly, hidden, system, not-content-indexed) produces a no-op; drift in one of those managed bits produces an update. The full raw attribute bitmap remains scan/plan evidence, but unmanaged bits such as ARCHIVE and TEMPORARY do not schedule work the executor cannot converge. Content-aware comparison remains later work.
- **Copy and Update Planning**. Source-only files become copies and changed matched files become updates.
- **Filename-Spelling Advisories**. One source and target file with the same Windows key but different exact casing retains its normal update/no-op result and carries a non-blocking `case_mismatch` advisory. A one-to-one same-parent pair whose basenames differ only by NFC/NFD representation likewise carries `unicode_normalization_mismatch`. Neither advisory hides changed content, blocks execution, or silently rewrites spelling.
- **Conditional Source Casing Propagation**. Target spelling is preserved by default. A fingerprinted source-casing option emits a zero-byte, no-trash recase for metadata-equal files and lets an already-required content update use source spelling. It defaults off, never recases parent directories, and never replaces a distinct case-sensitive destination. The Setup surface exposes this task-local option without changing global defaults.
- **Move Detection**. Unambiguous source filesystem-identity changes can become target-side moves; an identity observed at more than one scanned path is excluded from consideration.
- **Composite Move-Update**. A detected move whose content also changed is planned as one composite operation whose evidence records only at full completion, so a crash partway can never leave old content at the new path while the ledger claims consistency.
- **Directory Operations**. Every directory the plan will create — empty, or the parent chain of planned copies — is an explicit reviewed `mkdir` operation carrying its source directory's metadata; the executor never creates a directory implicitly. Removable target-only empty directories become policy-controlled operations.
- **Directory Rename Decomposition**. A renamed or moved source folder is never a directory-level operation: it decomposes into per-file identity moves, the full `mkdir` chain for new locations, and cleanup of the directories it emptied. Target-side file moves are same-volume renames, so a folder move copies no content bytes. Plan review may annotate paired old/new structure, but it never reclassifies the literal operations as one rename or invents a second selection unit.
- **Conflict Blocking**. Case collisions and file-directory conflicts remain visible as blocked conflict operations instead of being guessed through. Planning preserves the full reviewed intent, including related removal operations, while the derived safe selection quarantines blocked correspondence and dependencies without erasing them from review.
- **Capacity Planning**. Plans conservatively compute required bytes for all copy and update work, with temporary-file accounting sized for the maximum number of concurrently in-flight temp files rather than assuming one at a time; target free space is never baked into the plan — it is observed at review and preflight time, where the one shared capacity formula judges it. Accepted, unrealized M1 work will distinguish recognized disk-capacity I/O failures, settle the current operation, stop admission of later work, and show yellow capacity guidance without hiding independent failures. Pre-execution refusal retains the task without automatic retry or close. Generic `IO_ERROR` is already typed; richer I/O categories are deferred to M2.
- **Stable Plan Ordering**. Operations receive deterministic per-plan identifiers and dependency-aware ordering.

- **Content-Aware No-Op Detection**. Planning will use hashes or another content check before accepting metadata-equal files as unchanged.
- **Hash-Based Move Detection**. Move detection will extend beyond source filesystem identity to evidence-aware content matching.
- **Human Conflict Resolution**. Unresolved conflicts remain retained for post-run user review and re-planning instead of staying permanently blocked with no path forward.

## PREFLIGHT

- **Pure Verdict Function**. Preflight takes a plan-and-selection pair plus current filesystem state and returns a verdict; it never mutates the plan or the filesystem.
- **Repeatable, Not One-Shot**. The same function runs at plan review, at the start of every execution session, after any resume, and on queued-job wakeup — always invoked by the owning workflow. It rechecks filesystem, volume, dependency, and capacity facts, not mutable global defaults: admitted execution consumes the immutable semantic snapshot bound into the reviewed plan. The executor never calls preflight itself; its own defense is re-validating each operation's direct preconditions at the moment of touch, because preflight is one stage of TOCTOU prevention, never the last.
- **Scoped Re-Check**. Only the remaining selected operations are re-stated; preflight never re-walks the full tree.
- **Plan Integrity Check**. Confirms the selection is dependency-closed and no selected operation depends on a deferred, failed, or blocked one.
- **Selection-Aware Scan Completeness**. An incomplete or errored scan makes absence- and identity-dependent `move`, `move_update`, `trash`, and `delete` operations unexecutable, but does not refuse evidence-positive `copy`, `update`, `mkdir`, or guarded `noop` work. The degraded run is therefore additive and may be incomplete, never destructive on incomplete knowledge.
- **Staleness Check**. Confirms each remaining operation's source and target evidence still matches what the plan recorded.
- **Capacity Check**. Recomputes required bytes for the remaining selection against current target free space, counting only exact prior-run NamiSync temps in the observed touched-parent scope as recoverable so a nearly-full target cannot loop-refuse over space the run itself will free.
- **Safety Check**. No-follow admits every component in each configured root path below its trusted volume anchor before physical or volume observation, confirms roots still resolve to their recorded volume identity, and confirms the trash directory remains writable on the target root's own volume without crossing an admitted reparse component.
- **No Repair**. A refused verdict carries per-operation reasons and the observed snapshot; preflight never re-plans, drops, or patches operations to make them pass. Workflow derives the reviewed safe subset before preflight, and preflight independently rejects any caller that reintroduces blocked, quarantined, or completeness-unsafe work.

## EXECUTOR

- **Atomic Copy and Update**. File content is written to a target-volume temporary file, finalized with intended metadata and one pre-publish `FlushFileBuffers`, atomically published, and followed by a best-effort parent-directory flush through a writable Windows directory handle. Post-publish metadata is observed and repaired only when publication changed a required value; a refused directory flush remains a per-operation warning, and durability is claimed only for barriers that actually succeeded.
- **Source-Drift Guard**. Copy and update operations re-stat the source after the read stream closes; a mismatch against the plan's recorded evidence fails the operation instead of recording a hash for content that changed underneath it.
- **Hash on Copy**. Successful copies and updates calculate the canonical XXH3-128 digest from the source stream while copying, then bind its byte count to the published target's observed size before evidence can be recorded.
- **Contention Retry Policy**. A failure policy distinguishes transient sharing violations, which retry with bounded backoff, from persistent locks, which fail with a typed reason the plan view can show. COPY, UPDATE, and MOVE_UPDATE retain and revalidate prepared or completed backup/publish stages, then resume without recopying the main payload or restarting into false drift/destination occupancy. Every attempt that enters with an already-published continuation performs one current target stat before finishing metadata, durability, attestation, or recording; an identity-detectable replacement fails as `target-drift` with no false evidence, repairable mtime remains repairable before the final stat is cached, and normal first-pass execution pays no added stat. A pause requested during that durable retry window remains visibly `PAUSING` until the operation settles; production retry sleep is bounded to 350 ms, while filesystem/recorder I/O over already-staged data has no false elapsed-time claim.
- **Destructive Durability Boundary**. UPDATE, DELETE, MOVE, RECASE, MOVE_UPDATE old-path cleanup, and TRASH flush all previously earned recorder evidence before their final destructive source/destination guards, so writer contention cannot reopen a guard-to-mutation window. UPDATE's wait precedes every final backup/temp/source/live check, and the already-observed published stat binds prepared kind/size and available stable identity before attestation. Failed COPY/UPDATE/MOVE_UPDATE publication and MOVE/RECASE/TRASH/DELETE/MKDIR or readonly mutation attempts report confirmed, ambiguous, or unreadable durable state as recording-degraded without inventing evidence. The non-byte probes are failure-only, so successful execution adds no filesystem call.
- **Metadata Preservation Scope**. Copies and updates preserve modification time and the managed attributes readonly, hidden, system, and not-content-indexed by default; creation time is preserved where supported, and ACL/owner preservation is an explicit, off-by-default policy flag whose security descriptor is copied at execution time. Observed and intended metadata travel as a typed snapshot on scan records and plan operations, and the readonly attribute is applied only after publish. Alternate data streams are **not** yet preserved — a loudly documented limitation, never a silent one (see the deferred ADS bullet below).
- **Guarded Target Moves**. Target-side moves refuse existing destinations and preserve the existing target file record when recorded.
- **Root-Local Trash**. Trash operations move items to `.synctrash/<run-id>/<relative-path>` on the target volume.
- **Trash-on-Update**. Updating a file preserves its existing target version into the run's trash before the replacement publishes — by an atomic same-volume hardlink where the volume supports one, or by a crash-safe backup copy (temp-flush-publish inside the trash run directory) where it doesn't, with capacity planning counting those backup bytes. A copied backup binds the reviewed target to pre/post evidence from one open handle plus an exact byte count; detected grow, truncation, or metadata drift publishes neither the backup nor the update. Only then does the live replacement publish, so no crash point ever leaves the target absent; this is on by default and can be disabled per mapping.
- **Guarded Deletion**. Internal mirror deletes and empty-directory cleanup validate type and emptiness before removal. Cleanup of a directory emptied by its successful child operations requires exact kind, size, and immutable metadata while tolerating only self-induced mtime/link-count churn; stable identity binds when the reviewed scan supplied it, and absent identity is absent evidence rather than a veto. `RemoveDirectory` remains the atomic final emptiness guard.
- **Directory Metadata**. Created directories receive the source directory's recorded attributes, and directory timestamps are applied only after every child operation inside that directory has settled — child creates and renames churn parent directory times, so directory times are restored last.
- **Partial Result Reporting**. Independent operations continue after failures, with per-operation succeeded, skipped, failed, and canceled results.
- **Validated Safe-Subset Execution**. The workflow derives and commits the maximal safe dependency-closed selection. Directly blocked plan items are excluded as `BLOCKED`; operations overlapping their source/target correspondence or depending on them are `DEFERRED`; and incomplete scans withhold move, move-update, trash, and delete globally. Copy, update, recase, mkdir, and guarded no-op work continues. Exclusions are itemized in result/history without changing successful selected filesystem work to failure.
- **User-Edited Partial Execution**. Reviewers can change the runnable subset through revisioned service-owned selection state. The service recalculates dependency closure, summary and capacity, binds the exact selection into commitment, and re-derives it before execution; direct user deselection remains distinct from plan-derived safety exclusion.
- **Progress and Cancellation**. Execution reports monotonic aggregate bytes and active-operation identity; byte-producing work additionally reports attempt-local progress. The attempt counter starts at byte-pipeline entry and resets only when a retry or resumed run re-enters that pipeline. Retained post-copy continuations do not reset it. Aggregate bytes hold their high-water until rerun work catches up, including across a typed pause/resume checkpoint. Executor pause force-publishes one coherent authoritative-live snapshot without falsely settling the active operation: aggregate items/bytes and the current path/item/attempt all reflect the pause boundary, and the aggregate high-water remains continuation state for resume. Cancellation and escaping failure force-publish an inactive snapshot after reliable unwind outcomes, with live aggregate items and byte high-water but no nominal item or `current_path`. Execution checks pause/cancellation between operations, at adaptive copy-chunk admission, while a bounded pipeline is backpressured, and around retry backoff. Cancellation remains immediate: a retained pre-publish UPDATE backup is reported without deletion, a published-but-unfinished byte operation fails with `canceled-after-publish`, and a durable or ambiguous non-byte attempt fails with `canceled-after-mutation`; both mutation cases carry explicit state detail, degraded recording, and no false success evidence. When byte-continuation state and a readonly/non-byte marker coexist, cancellation settles both: confirmed publication remains authoritative, while a byte-probe failure cannot mask changed or unverified marker truth.
- **Content-Byte Accounting**. Progress and throughput totals count transferred copy and update content only; same-volume move, trash, and delete metadata operations never inflate byte progress or ETA.
- **Temporary-File Recovery**. Once per successfully preflighted execution, before copying, orphaned NamiSync temporary files are cleaned from the same touched target-parent set used for capacity accounting. Recovery matches only `<name>.synctmp-<run-id>-<op-id>`, removes only same-volume regular files owned by a different run, preserves current-run temps, off-volume mounts, and substring lookalikes, never enters `.synctrash`, and never walks the full tree.
- **Adaptive Pipelined Single-File Copy**. Every normal copy uses one bounded `reader → hasher → writer` pipeline with an adaptive chunk size. Progress advances only after each chunk is both hashed and fully written; this is internal pipelining, not concurrent file execution.
- **Reduced Windows Copy Finalization**. Native bindings are reused, source reads carry the sequential-access hint, large temporary files may be preallocated, and metadata plus the required pre-publish flush share one finalization handle. Publication repairs only metadata that actually changed.

- **ADS Preservation**. Alternate-data-stream preservation remains unrealized, but its contract is settled: enumeration happens at copy time in the executor, which already holds the file — no scanner, planner, or schema change, and the scanner stays role-free. NTFS updates a file's modification time when any stream is written, so ordinary metadata diffing already schedules the update that re-copies streams (a test-verified assumption before the feature ships) — though a writer that suppresses or restores mtime evades that signal, so the feature claims stream refresh only through ordinary update scheduling, never independent ADS-only convergence. Streams are user data: a requested stream that fails to copy on a capable target fails the operation, and a mapping requesting ADS onto a stream-incapable target volume surfaces as a mapping-level warning at plan time. Documented residuals: stream bytes are not counted by capacity planning, and stream content is copied but not attested — ledger hashes cover the main data stream only.
- **Restartable Large-File Copy**. Large-file copies will support resuming from an interrupted offset with a persisted partial digest, instead of restarting from zero.
- **Conditional Parallel File Execution**. File-level workers remain deferred after the XXH3-128 content-hash replacement; they are introduced only if post-replacement measurements show a real multi-device or small-file workload leaving relevant devices underutilized. Single-file read/write/hash pipelining is independent of this decision.
- **Deferred Copy Experiments**. File batching, direct/unbuffered copy IO, overlapping one file's publish with another file's write, and size-selected serial/pipelined engines remain unrealized. If directory-level measurements later show worker startup matters, prefer lazy worker startup within the one pipeline over maintaining two engines.
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
- **Recursive Folder Refresh**. Refreshing a folder scans and reconciles its complete subtree. Completed subtree reconciliation marks missing descendants with an indexed literal prefix range, never SQL wildcard matching; exact-path refresh still never infers descendant absence.
- **Causal Inventory Re-Read**. Inventory has no database generation token. A
  view re-reads on open, after an observed terminal for its location, and after
  acknowledge/restore; current inventory does not pretend to provide partial
  cross-process snapshot consistency and never auto-scans in the background.
- **Evidence Staleness**. Inventory derives `unverified`, `verified`, `modified`, or `mismatched` from retained evidence and a durable invalidation marker; age remains a separate stale-selection filter. Scan/verifier drift invalidates immediately regardless of age, ordinary matching scans cannot restore trust, and a hash mismatch dominates later metadata drift until guarded positive evidence replaces it.
- **Five-State Volume Resolution**. Every inventory/integrity start, resume, and queued wakeup distinguishes resolved, offline, ambiguous clone, missing root, and unavailable root before scan/hash work; only resolved state can reconcile.

- **Shared Network Inventory**. Inventory merging across hosts and network locations remains unrealized.

## VERIFIER

- **Baseline Creation**. Baseline creates canonical XXH3-128 evidence for present inventory rows that do not already have content evidence.
- **Location Verification**. Verification rereads present files against retained size, modification time, and XXH3-128 evidence.
- **Cache-Honest Reads**. Verification reads bypass the page cache, or are deliberately deferred after a fresh write, so a match attests the medium rather than a buffer NamiSync itself just filled.
- **Integrity Outcomes**. Verification distinguishes verified, baselined, mismatched, modified, missing, unsupported, canceled, and error results.
- **Selected Verification**. Exact rows or folders selected by an interface resolve from opaque location-scoped ids. A folder freezes all eligible indexed descendants independent of the current filter or viewport. An unreadable frozen subject becomes a visible `unsupported` item and verification-incomplete while eligible siblings continue; non-subject-specific scan incompleteness still refuses admission.
- **Post-Execution Verification**. A sync can continue directly into an optional verification phase while retaining the same session and volume custody. Every successfully published copy, update, or move-update carries transient published evidence into readback even if its ledger write failed; no-op, metadata-only move, directory, trash, and delete work is ineligible. Readback mismatch or incompleteness changes the integrity axis, never the already-settled filesystem result. Same-process pause retains an explicit execute/verify continuation; process close offers no resume. Cancellation starts no new verification work, preserves already-settled filesystem truth, and attempts terminal finish once without ever double-finishing; a finish failure degrades recording.
- **Deferred Exact Post-Copy Verification** *(accepted Stage 6 target; unrealized)*. A completed task can manually verify its successfully copied or updated files without rescanning or persisting operation-time hashes. NamiSync uses current same-run ledger evidence, distinguishes ready, already verified, incomplete, unrecorded, and superseded work, and blocks mixtures it cannot prove exact. It rechecks evidence and target admission at Start; all-already-verified work starts nothing, while no applicable work explains why. This result has its own post-copy slot and never rewrites execution truth; ordinary “verify current state” remains the fallback.
- **Safe Conditional Recording**. Positive hash/verification evidence and negative missing/modified/mismatched invalidations are persisted only when the file state and prior evidence still match the observation being recorded.
- **Accept and Re-Baseline**. Explicit rebaseline hashes current content and conditionally replaces evidence, even when it matches, clearing verification freshness rather than reporting a verified comparison. Rebaseline asks for explicit confirmation; baseline and verify do not. Compare-and-accept for genuine matches is deferred beyond M1.
- **Standalone Integrity**. Baseline, verify, and explicit rebaseline compose cache-honest Windows reads with fresh inventory selection, conditional ledger recording, exact-candidate pause continuation, subject-scoped generic history, and volume-custodied dispatcher registrations. The CLI reaches them through the shared facade; desktop controls remain unrealized.
- **Mode-Aware Integrity Admission**. Currently a fresh baseline admits only eligible files without evidence, a fresh rebaseline only files with evidence, and verify admits both. The accepted but unrealized rebaseline change also admits null-evidence files, without weakening explicit selected scope or confirmation. Resume retains the frozen ordered candidate ids instead of reapplying mode filters after evidence changes. The [accepted verifier policy](VERIFIER.md#accepted-standalone-operation-policy) specifies all three operations.

- **Conditional Parallel Verification**. Verification remains single-stream after the XXH3-128 content-hash replacement unless post-replacement measurements demonstrate an IO-utilization problem that file-level workers solve.
- **Automatic Background Integrity**. Background hashing and verification remain unrealized.
- **Repair Guidance**. When one side of a mapping mismatches its evidence, verification will compare both sides' current hashes against recorded evidence and diagnose which side is damaged, as a first step toward a guided restore from the healthy side.

## RECORDER

- **Single Write Path**. The recorder is the only code path that writes the main ledger; execution, verification, and baseline all call it rather than issuing SQL of their own.
- **Conditional Recording Primitive**. Every hash or verification write is conditional on the row's current id, state, size, and modification time still matching what was observed; a mismatch discards the write instead of recording evidence about a file that has already moved on. This one primitive makes hash-on-copy, baseline, and verify safe against the same race.
- **Provenance Tagging**. Every hash write records how it was attested — inherited from a copy's source stream, a direct read-back, or an independent verification — so displayed trust never overstates what was actually checked.
- **Explicit Durability Boundaries**. The active recorder commits each command eagerly behind a real `flush()` seam. Any later bounded batching must force that seam before destructive operations, at pause-drain, and at session terminal so the crash window stays bounded without weakening the never-wrong-only-behind guarantee.
- **Idempotent Recording**. The recorder treats a repeated run token as a no-op, backed by the ledger's own uniqueness constraint as the last line of defense.
- **Serialized Writer**. All in-process sessions record through one serialized writer, so legitimately parallel disjoint-volume runs can never silently lose bookkeeping to ledger lock contention; cross-process writers get a generous busy timeout with bounded retry only for SQLite `BUSY`/`LOCKED` result codes, never message text, and a recording failure is always surfaced, never swallowed.
- **Axis-Separated Truth**. A session's terminal state reports its filesystem work alone; ledger bookkeeping and audit history report through separate recording and audit statuses carried in the result. Completed work with a failed or lagging write on either store surfaces as completed-with-degraded-recording (or -audit) — loudly, in the UI, CLI exit detail, and history — and the behind store converges rather than the result lying on any axis.
- **Typed Recording Attribution**. Active item-local recording status and bounded task-level recording problems remain independent of filesystem, integrity, and audit truth; diagnostic text never controls behavior. Once an item receipt is committed, later flush, finish, close, audit, or reconciliation trouble cannot rewrite its outcome or hide its durable evidence. Producer and presentation-only omissions remain distinct. Desktop execution review of these facts is still unrealized. Exact reasons, bounds, and result shapes live in `BRIDGE.md`.

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
- **Ledger-Current Execution Evidence** *(accepted Stage 6 target; unrealized)*. Execution review exposes a digest only when a successful byte-producing operation has coherent current evidence from the same retained run. It distinguishes recorded copy, already verified, unrecorded, superseded, and not-applicable states; coincidental inventory hashes and transient copy digests never become durable execution evidence. Current inventory detail may show separately labelled current-state evidence, while plan review contains no content digest.
- **Exact Large Values**. File sizes, byte totals, and filesystem timestamps use checked signed-64 arithmetic and canonical decimal public values. An unrepresentable timestamp or aggregate plan total is refused instead of clamped or rounded, while inventory aggregate overflow remains explicit. Full Windows file indexes use opaque canonical 128-bit text. Later desktop surfaces consume this active protocol without changing it. `DEFENSE.md` §1.3 and `BRIDGE.md` own reachability and mechanics.
- **Generic Annotations**. A generic entity-scoped annotations table (kind, id, key, value) carries small user-authored labels — a session note, a future task annotation — without a schema change each time a new place wants one.
- **Split Local Settings**. Semantic defaults live beside the selected ledger and are snapshotted into plans so admitted execution never rereads them. Cosmetic desktop preferences live separately in `ui-state.json`. Accepted Stage 6 recents come from ledger runs rather than UI state, and process-local tasks or requests are never presented as durable state.
- **Database Safety Settings**. Ledger connections use foreign keys, WAL mode, and a bounded busy timeout.
- **M1 Evidence Reset Boundary**. Ledger v4/history v7 share data epoch 7 and exact validated contract markers. Ledger v1-v3, every history v1-v6 file, and current-version files from an older epoch or with missing/mismatching markers are refused read-only; normal startup never deletes data. Settings and UI state survive.
- **Coordinated Evidence Reset**. The active Stage 6 evidence cutover refuses an old, mixed, incomplete, markerless, or orphan-sidecar local database pair before mutating work and tells the user to archive or delete both databases and sidecars together. It does not migrate or delete data automatically. `DATABASE.md` and `HISTORY.md` own the persistence consequences; the exact event and scalar contracts live in `BRIDGE.md` and `DEFENSE.md` §1.3.
- **M1 Windowed History Contract**. History v7 stores exact event-v5 append-only reliable receipts, dense canonical item projections, exact semantic-duplicate links, bounded defensive rejection receipts, provisional run watermarks/counts, and bounded item-free terminal summaries. The reset boundary is deliberate: older epochs cannot reconstruct the exact authenticated contract.

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

- **Independent Audit Store**. Sync, baseline, and verification attempts are recorded in a separate local history database.
- **Audit Delivery Guarantee**. History subscribes at session admission on the reliable event plane under one clear contract: every audit event is delivered within the timeout, or the session result says `audit=DEGRADED` — nothing is silently lost behind a result claiming OK. A durable per-event rejection can degrade while later delivery continues; an observer exception or timeout breaks the prefix without changing filesystem or ledger truth. Durable finalization success is latched before exact-once observer cleanup, so cleanup failure cannot rewrite the committed/live terminal axis.
- **Bounded Incremental History**. Reliable producer admission measures canonical event bytes and rejects an over-1-MiB projection before sequencing or queue mutation. The observer separately retains at most 256 reliable receipts and 1 MiB of canonical data per pending window; count/byte, one-second age, pause, clean close, and finalization boundaries commit. Continuous events never postpone the original age deadline; a crash loses at most the uncommitted window.
- **Typed Run Details**. History v7 retains ordered reliable receipts, dense typed canonical result-item projections, non-counting exact duplicate envelopes, bounded phase summaries, and the exact v5 recording/omission/review-limit terminal facts. Every item carries explicit phase and item-type tags, so sync and integrity outcomes coexist without duck typing or parallel domain lists.
- **No-Op and Cancellation Audit**. Explicit no-op and canceled activities are recorded alongside successful and failed activities.
- **Blocked And Deferred Audit**. Safe-subset runs retain every direct blocker as the sixth `BLOCKED` outcome and retain quarantined or incomplete-scan-withheld work as `DEFERRED` with typed reasons and itemized paths. The history schema stores a blocked summary count without multiplying quarantine/withholding into new top-level categories.
- **History Idempotency**. Repeating a recorded run token or the same sequence/payload is idempotent. A new sequence carrying an exact semantic item duplicate remains a visible non-counting receipt; changing that item's payload is producer corruption.
- **History Retention**. Summary and detail retention will preserve the run envelope while pruning eligible old detail, but it is deferred beyond M1 until a maintenance session can coordinate cross-process custody with every audit writer. M1 exposes no retention setting, command, or GUI action.
- **History Browsing**. Retained runs and their details can be inspected through the CLI; the desktop History dialog remains unrealized.
- **Database-Paged History**. Summary listing uses fixed-query primitive aggregates without decoding event JSON. Item and reliable-event readback use keyset pages of at most 256 rows through a captured immutable watermark, so an active writer can append later windows without changing the reader's selected prefix.
- **Incomplete History Views**. A provisional run exposes current lifecycle/phase, durable sequence/item watermarks, counts, and commit time with nullable terminal axes. Restart shows that prefix as `incomplete`; it never infers interruption or filesystem-execution resumability before M2 process/session custody exists.
- **Generic History**. The independent store consumes the dispatcher's reliable preterminal observer/flush protocol and incrementally persists idempotent sync/inventory/integrity envelopes, axis-separated summaries, ordered operation/integrity details, and compound phase summaries. Retained summary/item/event views expose the same finalized classification as live results and bounded recovery data for incomplete runs.

- **Task-Grouped History**. GUI activities will be grouped under durable task records while CLI and service activities remain valid without a task parent.
- **Task Annotations**. Users will be able to add a trimmed plain-text task annotation of up to 256 characters.
- **Restorable Task Setup**. Opening history will restore a task's saved inputs and options while requiring a fresh plan before execution.
- **History Replay**. A retained run will be replayable by rebuilding the planner's scope from its recorded file set and planning fresh against a newly selected target; plan review will diff current content against recorded evidence and surface any drift instead of assuming the files are unchanged. Replay stays available only while a run's detail remains unpruned.
- **Queue Discard Audit**. A queued session discarded before it ran will still be recorded as a discarded, unrun history entry — typed as a canceled terminal carrying the `unrun` disposition, never inferred from a zero-length operation list or a parsed string — so the browsable timeline accounts for planned-but-abandoned work alongside completed runs.
- **History Export**. Retained runs and their detail will be exportable to CSV or JSON for external audit trails.

## COMMANDLINE

The parser and production registry expose reviewed sync/history plus all four
location activities through the shared service.

- **Sync Command**. `nami-sync sync` runs the plan session, prints the reviewable plan, and asks for explicit terminal confirmation; confirming commits the plan and immediately runs the execution session, declining leaves it uncommitted. `--verify-after-copy` retains the same session/custody for readback. No flag combination plans and executes without a review.
- **Inventory Command**. `nami-sync inventory` scans one explicitly selected root or retained location and prints its inventory plus zero/one/many mapping guidance.
- **Baseline Command**. `nami-sync baseline` creates only missing baselines and reports typed integrity counts and issues.
- **Verify Command**. `nami-sync verify` verifies one explicit location and returns exit 8 for mismatch or 9 when verification is incomplete.
- **Rebaseline Command**. `nami-sync rebaseline` requires selected exact paths plus explicit current-evidence acceptance before replacing existing evidence. The accepted but unrealized extension also creates evidence for selected eligible files that lack it; no flag or confirmation is relaxed.
- **History Command**. `nami-sync history` lists recent finalized or incomplete audit summaries, or prints one summary while streaming its typed item detail in 256-row database pages.
- **Database Overrides**. CLI integrity commands can select separate main-ledger and history database paths.
- **Location Binding**. Location commands require exactly one positional root or named location id; repeatable exact paths define scope, and clone ambiguity requires a listed mount rather than inferred fallback.
- **Typed Exit Classification**. The workflow headline precedence is failed, partial, refused, mismatch, canceled, verification-incomplete, recording/audit degradation, all-noop, then success. CLI codes 0 and 2-9 map those categories without hiding secondary axes or parsing diagnostic text.
- **No-Subcommand Behavior**. Running `nami-sync` or `python -m namisync` with no subcommand prints usage, points to `nami-sync-gui`, and exits nonzero; nothing ever runs implicitly.
- **Concurrent Read-Only Commands**. The read-only history command runs alongside a GUI session or other CLI invocations; mutating commands are subject to the same volume and queue arbitration as any other session.
- **Service Facade And CLI**. One process-local service owns the exact registry, runtime/dispatcher lifecycle, sink-only observation, primitive settings/inventory/result views, and both database overrides. The CLI exposes all four location commands, optional execute-to-verify, actionable five-state binding, guarded selected rebaseline, typed phase/item rendering, and deterministic exit codes.

- **GUI Entry Points**. `interfaces.launcher` sits above the sibling CLI and web adapters. Console entry points retain CLI behavior, while the `nami-sync-gui` GUI-subsystem entry point opens the sole desktop implementation without a retained console window.
- **Secured Desktop Host**. The installed wheel now opens only through the pinned Edge Chromium/WebView2 stack, binds bridge authority to the committed loopback origin, blocks external navigation and popups, validates the coordinated database pair before window admission, owns one fixed production instance, and closes through bounded retryable service teardown. Native load does not admit ordinary commands: on startup and same-origin reload, the fixed packaged shell must acknowledge receiver/DOM installation, settle a readable base surface, and complete a neutral current-generation host challenge/page echo within five seconds. Appearance publication and enhancement quality remain independently degradable. Close presentation binds the current loaded document before asynchronous work and cannot change shutdown truth on a DOM failure. The packaged document is trusted code while every value it handles remains untrusted data; `DEFENSE.md` owns that trusted-base decision and its reopen trigger. Enforced refusal of an elevated host remains unrealized beta-release work.
- **Explicit Desktop Geometry**. The public pywebview construction contract sets
  a 1280 x 800 logical-pixel initial window and 1024 x 640 logical-pixel
  minimum. Pywebview owns DPI conversion; NamiSync performs no late native or
  JavaScript correction. The former viewport media query is gone; WebView2
  zoom can still reach the CSS stacked layout through its inline-size container.
- **Desktop Command Transport**. One function-only pywebview dispatch entry provides bounded requests, opaque folder authority, sanitized failures, idempotent replay, and bounded task/event-drain ownership. Reliable events retain ordering and explicit-gap recovery while progress is coalesced without delaying terminal or control feedback. `BRIDGE.md` owns the exact envelopes, capacities, timing, recovery rules, browser evidence, and acceptance status.

## DESKTOP UI

The appearance, bridge, shell, generic presentation, task lifecycle and frozen
Setup surfaces are active. Plan/inventory review and history surfaces remain
unrealized unless an entry says otherwise.

- **Desktop Presentation Foundation Realignment**. One pure tree-agnostic
  `visible_sequence.py` consumes workflow-owned pre-order arrays directly and owns literal
  case-folded display search, caller-decided filter counts, collapse, exact
  1..256 windows, server-derived accessibility metadata, and indexed
  visible-ancestor anchoring without domain policy, a duplicate tree, or
  retained projections. Expansion is Boolean only for an active-projection
  parent with a retained child; leaves, empty roots, and filtered-empty
  containers expose no disclosure. The installed `tree.js` renders only those decided
  windows as an operable single-tab-stop fixed-height tree with two spacers, an
  exact 28-pixel row, inert full labels, visible active-descendant navigation,
  pointer-owned disclosure toggles that never activate a row, and stale-generation refusal. Passive
  scroll paging coalesces each burst to its final viewport, requests a missing
  leading or trailing global index through the tree-owned generation, preserves
  scroll position across the replacement, and keeps presentation focus on a
  fully visible row when one is available, otherwise clearing it until the
  covering commit; neither path invokes domain activation. External projection changes
  remain authoritative over scroll state from an older window. A valid narrow
  page cannot self-retry for an unchanged viewport; a later viewport change is
  the only owner of another passive request. The production
  filesystem-label sink replaces the fixed layout-control set and literal
  marker delimiters with injective `⟦U+XXXX⟧` markers and isolates the label;
  raw filename display remains exact in workflow, wire, and search and receives
  no presentation-specific cap, while callbacks receive raw opaque node ids.
  Ordinary Unicode and long labels are unchanged.
  The production
  shell exposes labelled task navigation and work regions. Its empty guidance
  and sessionless task Setup fabricate no session or product row. The exact bridge
  surface remains solely in `BRIDGE.md`.
- **Task Rail**. The transparent rail exposes the window's Mica or opaque
  fallback base. Resting cards are transparent; hover/press and selected/current
  states use the primary translucent content tint, with a weaker secondary tint
  while an active card is hovered or pressed. Task cards remain borderless and
  do not conflate selection with running status. This visual contract is active.
  The newest-first process-live rail now creates, selects, reconstructs, and
  closes blank task pages while preserving stable labels and current selection.
  Retaining each task's plan, execution, inventory, integrity, and optional
  post-copy results activates with those later content surfaces.
  Busy close requests cooperative cancellation and closes only after settlement and
  release are complete; there is no force-close or purge path. Open tasks are
  never silently evicted; capacity guidance asks the user to close a task or
  wait. `BRIDGE.md` and `DEFENSE.md` §1.3 own exact lifetime and containment
  rules.
- **Single-Page Task Shell**. Each task keeps its applicable Setup, status,
  progress, review, and log controls on one page without fabricating a paired
  source/target scope for standalone inventory work. M1 task creation,
  navigation, rail retention, and explicit close are process-live; task bodies
  expose editable or frozen Setup while review content remains pending.
- **Frozen Setup**. Source, target, and standalone-inventory rows accept typed, picked, or remembered local folders through one admission path. Inputs are treated literally—never as shell, URI, environment, or current-directory expressions—and unsupported, remote, ambiguous, unavailable, file, reparse, placeholder, or overlong choices receive distinct guidance. Accepted choices are process-local, expire, and are freshly checked when real work starts; editing invalidates the prior choice. `BRIDGE.md` owns the exact grammar, supported-volume matrix, bounds, and slot policy.
- **Explicit Setup Options**. Setup exposes trash/additive deletion, update-to-trash, filters, creation-time and ACL preservation, source-casing propagation, and linked verification. Mirror remains unavailable and alternate data streams remain visibly unsupported. Defaults only prepopulate the row: planning freezes the complete approved options, and execution cannot resupply or silently change them.
- **Serial Multi-Pair Creation**. One gesture can create several plan tasks serially from one frozen option snapshot. Each row succeeds or fails independently with no rollback; navigation preserves already admitted tasks, while replacing the document may leave unsent rows for the user to resubmit.
- **Folder Selection**. The Setup surface gives source, destination and standalone inventory roots editable typed/recent controls plus folder-browser buttons. All three paths share the same admission rules, never turn a selected file into its parent, and never trust a stale remembered path.
- **Plan Again**. The explicit action resolves both reviewed location identities afresh and creates a separate task with the old frozen options and default selection. Offline or ambiguous identities require correction or a current mount choice; old display paths, selection and execution authorization are never reused.
- **Plan Tree**. The Plan view shows every immutable operation exactly once in a safe, directory-nested tree with rollups, reasons, selection, dependencies, and execution/post-copy status. Same-target collisions become an explicit operation group whose members remain individually reviewable; ambiguous move relationships stay literal rather than implying a false pair. Hostile filenames remain text-only and accessible. `PRESENTATION.md` owns identity, projection, and move-pairing mechanics.
- **Plan Review View** *(accepted Stage 6 target; unrealized)*. Plan review combines frozen locations and review-time facts with the current selection, required bytes, risks, notices, search, filters, facets, and rollups. Selection changes do not rewrite the original review result or notices. Execute commits the current nonempty selection and then performs fresh preflight. An admission failure rolls back to review; a preflight refusal after admission remains committed. **Plan again** resolves the old task's reviewed volume identities into fresh Setup, creates a separate task with its frozen options, then scans again for a new review with default selection. It never treats the old display path as authority or carries selection/authorization forward.
- **Execution Review** *(accepted Stage 6 target; unrealized)*. Live and settled plan rows show filesystem, recording, integrity, and audit truth independently. Every admitted operation has one coherent result and completed execution is immutable. Manual post-copy verification is available only after a normal execution-only completion and occupies a separate replaceable axis; canceled or abnormal executions are read-only, and a normal degraded result is reviewed like a green result without item retry. Excess diagnostic detail is omitted visibly rather than truncated or allowed to hide the typed result. Exact event/result mechanics remain in `BRIDGE.md`.
- **Inventory Tree**. Inventory appears as a directory tree with current presence, integrity, reappeared, acknowledgement, and typed-warning states kept distinct. Refresh or verification replaces a complete settled result rather than mixing old and new fields; folders and warnings never masquerade as file outcomes. Folder totals report overflow explicitly instead of clamping, and current hashes remain labelled with their provenance and validity. Exact projection and scalar rules live in `PRESENTATION.md` and `DEFENSE.md` §1.3.
- **Inventory Review View** *(accepted Stage 6 target; unrealized)*. Inventory review combines search, filters, facets, completeness, location state, and counts while hiding acknowledged missing rows by default. Choosing the Acknowledged filter reveals those rows for restoration. Warnings remain informational, visible as errors where appropriate, and cannot become file or folder action targets.
- **Plan Filters**. Plan review filters by operation and blocked/unsupported state with truthful counts. Search, filters, and collapse never change selection, and informational notices remain visible context rather than operations. `PRESENTATION.md` owns filtering behavior; exact future facet DTOs are reopened.
- **Inventory Filters**. Inventory review filters by presence, evidence, mismatch/error, reappearance, and acknowledgement with truthful overlapping counts. Hiding acknowledged rows changes presentation only, never inventory truth. `PRESENTATION.md` owns filtering behavior; exact future facet DTOs are reopened.
- **View Toggle**. A persistent Plan | Inventory toggle switches between retained plan and location-inventory views without conflating them.
- **Inventory Actions**. Menus and row actions support exact-file or recursive-folder refresh and integrity work, missing acknowledgement/restore, and path copying. Acknowledgement hides a missing row without changing canonical totals; warning rows remain informational. Baseline and verify need no extra confirmation, while rebaseline explicitly confirms replacement of current evidence and carries that approval through retries.
- **Server-Owned Selection**. Plan selection belongs to the complete server-side operation tree, not the current viewport or filter. Selecting a folder includes its operations and descendants; selecting an operation group includes its direct members without granting that group filesystem-folder scope. The desktop previews and batches changes but cannot invent selection authority.
- **Bounded Tree Views**. Large plan and inventory reviews load in bounded pages without retaining a hidden complete browser list. An oversized initial review gives a typed no-partial refusal; a failed refresh preserves the last complete view. `PRESENTATION.md` and `DEFENSE.md` §1.3 own exact limits.
- **Sibling Sorting** *(accepted; unrealized)*. New plan and inventory views use path-key order, and reset restores it. Users may choose filename, size, or mtime in either direction. The server orders complete sibling sets before windowing, preserves hierarchy, selection, collapse and execution authority/order, uses raw numeric facts with deterministic ties and unavailable values last, and never invents descendant-derived folder times. Full command/raw-mtime support is independent of the later 48rem-table column/reset layout. Status/progress sorting, global flat sorting, and durable sort preferences are excluded from M1; [Bridge decision](PRESENTATION.md#search-filters-sorting-and-follow) owns the exact contract.
- **Tree Search**. Plan and Inventory search matches literal display text, preserves ancestor context, and reports authoritative facet counts. A stale response or failure never replaces the current valid view; an active off-screen item resolves to visible context instead of being guessed from paths. Exact query behavior lives in `PRESENTATION.md`.
- **Live Progress**. The active protocol preserves exact recording problems and large quantities, with stable active-item, phase, retry-attempt, and monotonic progress that never substitutes for settlement. Binding that protocol to the desktop execution and verification surfaces remains unrealized. `BRIDGE.md` owns the transport contract.
- **Plan Follow Mode**. Plan review follows the active operation until the user scrolls away. If that row is collapsed or filtered, the server identifies the nearest visible ancestor; if no chain is visible the UI reports that state instead of guessing from paths or a retained page.
- **Live Integrity Feedback**. The Inventory view follows the file being hashed while keeping provisional progress visually distinct from settled outcomes; live telemetry never changes which rows belong in the settled review.
- **Cooperative UI Workers**. Long-running operations run through cancellable worker sessions with guarded cleanup and release handling, independent of whichever UI toolkit hosts them.
- **GUI Single Instance**. A second desktop launch activates the existing window and exits successfully; activation failure is visible. Read-only CLI commands and non-conflicting CLI mutations are not subject to the GUI-instance restriction.
- **Mismatch Severity**. A mismatched-hash row — content differing from recorded evidence while its stats look unchanged — renders distinctly from an ordinary modified row, with a persistent badge on the location until acknowledged; it is the one signal this application exists to surface and it never reads as just another list row.
- **System Theme And Accessibility**. A labelled selector persists System,
  Light, or Dark independently from semantic settings. System follows Windows;
  an ordinary Light/Dark override drives both native material and page tokens,
  while active high contrast temporarily retains Windows authority without
  overwriting the stored choice. Accent and reduced-motion remain system-owned.
  Mica is a progressive native enhancement; opaque high-contrast/no-material fallbacks
  preserve readability, focus, and status semantics without relying on color
  alone.
- **Fluent Neutral And Windows Accent Roles**. `tokens.css` owns a pinned
  transcribed Microsoft Fluent light/dark neutral subset. Native appearance
  retains raw Windows `Accent`, `AccentLight1`, `AccentLight2`, and
  `AccentDark1` values, then publishes only semantic fill roles through the
  revisioned appearance v2 host-to-page envelope. Light uses `AccentDark1`,
  Dark uses `AccentLight2`, hover/press apply 90%/80% opacity, and one
  base-fill contrast foreground stays fixed through interaction; forced colors
  remain system-owned.
- **Solid Desktop Control States**. The active component foundation exposes
  exactly two command-button tiers: WinUI-neutral fills with subtle boundaries
  for ordinary actions and live Windows accent for primary
  Execute/Verify-class actions. Primary and
  other accent-filled labels use the native base accent's contrast-selected
  exact black or white, stay fixed through interaction, and use 90%/80%
  base-fill opacity for hover/press. Filter pills
  use inverse grayscale when inactive and exact operation-family main swatches
  at rest with contrast-selected grayscale text when active. Hover and press
  retain the same main RGB at 90%/80% strength without lift or scale; inactive Delete uses exact
  red-main text while sharing the ordinary inactive pill's distinct grayscale
  hover/press ladder, and active Delete uses the shared contrast-safe neutral label.
  Channel-scoped
  intent/lifecycle/integrity labels use either semantic text or a borderless
  18 logical px filled form. Hued fills use light-family surfaces in Light and
  dark-family surfaces in Dark; red/yellow Light badges use their dark-family
  text while Dark badges use main text. Progress keeps its
  gray track and uses accent when
  active/resumed, frozen yellow when paused, and frozen neutral gray when plain
  canceled; forced colors use a `Canvas` track and `Highlight` fill. Ordinary
  keyboard focus uses opposing inner/outer Fluent strokes
  and forced colors retain system outlines. The Sync/Integrity
  two-half state specimen uses radio-group semantics and highlights its checked
  half with the accent roles. Unchecked checkboxes use a softer 1 logical px
  neutral boundary; textboxes use a subtle 2 px boundary plus neutral/accent
  resting/focused underline. Task-backed switching, keyboard behavior, and
  actions remain part of the later unrealized work surfaces.
- **Content Cards**. Background/content cards are static translucent material
  layers rather than controls: white 70% with a black 6% blended stroke in
  Light, white 5% with a black 10% blended stroke in Dark, plus opaque solid
  stroke fallbacks and system-color forced-color fallbacks. They never acquire
  task-card hover or active behavior, and clip their translucent fill to the
  padding box to avoid rounded-corner alpha seams.
- **Flyouts And Theme Combobox**. Dialogs, menus, and the production-owned DOM
  theme listbox use a dedicated black 6% Light/20% Dark flyout stroke rather
  than the conspicuous accessible control border. The combobox owns WinUI-like
  selected-option placement, viewport clamping, an opaque M1 popup layer,
  a persistent filled selected option with a 3 px accent pill, one shared
  hover/selected overlay with a weaker pressed state, subtle raised/flat
  closed-control boundaries, and keyboard-only focus indication. Task cards
  use the same transparent-rest, hover/selected, and weaker-pressed roles.
  Ordinary SDR elevation remains; dark HDR
  suppresses CSS flyout shadows to avoid transparent WebView2/Mica alpha halos,
  while forced colors use system surfaces without acrylic or shadow.
- **Dormant File-List Row Foundation**. Packaged `file_row.js` owns the shared
  compact row skeleton, while `plan.js` and `integrity.js` expose narrow
  presentation-local renderers. Both consume already-projected 16 px checkbox,
  mixed/folder/disclosure, basename, size, status, and notes values in a 24 px
  row with 12 px text and a 48 rem horizontally scrolling content floor. In
  the six-column layout, the sync specialization adds operation and eight-character
  checksum cells, while integrity adds a combined presence/status cell and an
  eight-character checksum cell. Actual
  projection, transport, selection/tree policy, execution, and progress remain
  unrealized Slice 5 work: production imports neither specialization and still
  renders no rows. Test-only static fixtures settle plain and partially selected
  folder hierarchies with two basename-only children, all operations, all three
  intent exceptions, and every integrity state. Both renderers wrap supplied
  status text in the channel-scoped semantic-label component and accept exact
  already-projected keys. Test-only execution rows additionally exercise
  a 4 px Copying progress bar across the 8 px-inset cell content and Completed text, while integrity rows
  exercise the same Verifying/Completed forms. Active specimens accept an
  already-projected 0–100 percentage and retain supplied status text as the
  accessible progress label. They carry no form field and infer no domain
  result, transport ratio, row identity, hue, or urgency in JavaScript. Compact
  filled labels use the checkbox's 4 px radius, 4 px inner padding, and a
  matching 4 px leading bleed to align label text. Forced colors retain system authority. The
  gallery headers also support pointer-drag and arrow-key column resizing
  without persistence. The first interaction freezes five pixel tracks while
  File/path remains the sole 12 rem-minimum flexible track; each of the five
  internal dividers transfers space against a 14 rem-minimum Notes reserve.
  Viewport changes affect File/path alone, and the grid overflows at the greater
  of its 48 rem floor or the stored-width minimum. A master checkbox derives
  and changes all selectable specimen rows.
- **Authored Semantic Palette**. The active foundation preserves exactly 15
  authored red/green/blue/yellow/purple `main`, `dark`, and `light` inputs in
  `tokens.css` only. Yellow main becomes `#FFAA22` and purple main becomes
  `#8844CC`; their former main values become yellow light `#FFDD44` and purple
  light `#BB88EE`. Operation consumers remain main-bound; semantic badges use
  the family light/dark tones as supporting surfaces, and Dark relocating text
  uses purple-light while Light retains purple-main.
  Further hardcoded or derived color values remain possible after an explicit
  product-author design decision and coordinated contract/token/evidence update.
  Gallery-tested channel-specific aliases, not palette names, feed controls
  and later surfaces. Light/dark pairs are measured; the explicit main-text
  exceptions are disclosed rather than claimed contrast-conformant. Filled
  badge pairs remain contrast-conformant in both ordinary themes. Forced
  colors use Windows
  system colors, and every meaning retains text and non-color cues.
- **Semantic Color Channels**. The implemented visual contract separates plan
  intent, task lifecycle, and integrity. Hue identifies a class; form expresses
  attention, and neither replaces visible text, structural cues, or accessible
  state. A rendered signal belongs to one channel at a time. Intent follows
  reversibility; lifecycle distinguishes ordinary progress from attention and
  failure; integrity keeps healthy inventory as text while reappearance,
  unsupported entries, missing files, mismatches, and read errors use filled
  attention badges. Filled forms are 18 logical px badges with theme-aware
  family-secondary fills, dark red/yellow labels in Light, and main-color
  labels in Dark; compact file-list forms use the checkbox's small radius while
  standalone badges may remain pill-shaped. Paused progress is frozen
  yellow, plain canceled
  progress is frozen neutral gray, and resume returns accent. A future stopped
  count/percentage for paused or canceled work is a recorded decision point,
  not a current payload or renderer feature. Channel-specific aliases,
  component forms, complete static gallery fixtures, and their evidence are
  active; production workflow-list color consumers remain dormant.
- **Closed Fluent Icon Foundation**. GUI Break 1 seeds a minimal frozen registry
  with four pinned local regular Microsoft Fluent SVG masks and their source,
  hash, and license record. Icons inherit `currentColor`; tokens own shared
  sizes and components own alignment/states. Remote loading, runtime
  registration, icon fonts, generated SVG, and data-derived asset paths are
  absent. Later surfaces add only the glyphs their real controls need.
- **History Dialog**. The unrealized desktop History dialog will list runs and retained activity detail. Retention controls remain out of scope until coordinated maintenance exists.
- **Desktop Resource Acceptance** *(accepted; unrealized)*. Release requires cold-start resource budgets and repeated/long-workload leak and growth checks on declared supported profiles. Application-owned requests and populations retain independently enforced runtime bounds. This is scoped acceptance, not universal whole-runtime memory containment; DEFENSE section 7 owns the claim policy and INTERFACES SH-G-15 owns the acceptance requirements.
- **Bridge Responsiveness Envelope**. The desktop bridge has bounded scale, paging, latency, and retained-memory contracts. Execute/control feedback is immediate, progress may be late but never incorrect, and `BRIDGE.md` / `PRESENTATION.md` own the scoped limits and evidence.

- **Settings Surface**. The rail opens a nonmodal Settings/About page with the existing theme preference and initial version line. Tasks and drafts remain available, and the task list scrolls independently above Settings. Global semantic-settings editing remains deferred; Setup choices never write global settings.
- **Durable Desktop Tasks** *(proposed M2)*. Tasks, Setup, and recoverable session state will survive process closure or restart; process loss will not claim durable task recovery before the M2 recovery contract exists.
- **Drag-and-Drop Setup**. Dropping folders onto a task will populate its source and destination fields.
- **Status Layout Refinement**. The task header will unify live and completed detail while promoting activity state over the affected-byte figure.
- **Rolling Transfer Metrics**. A rolling estimator will provide responsive throughput and phase-aware ETA instead of the current whole-run average.
- **Throughput Graph**. The UI will graph current transfer rate against execution progress.
- **Failure Triage**. Failed operations will group by cause and common path prefix with a suggested action, instead of presenting a long flat list of individual failures.
- **Cancel and Pause Safety Messaging**. The cancel and pause affordances will state what happens to the in-flight operation and what's kept, phrased from the session's current phase rather than one generic warning.
- **Visible Pause Drain**. The task rail will render the existing `PAUSING` session state as “Pausing…” until the executor reaches an operation-safe boundary, distinct from `PAUSED`; repeated pause/resume controls remain unavailable during that drain while cancellation stays available.
- **Completion Notification**. A run that finishes while the window isn't focused will raise a system notification summarizing the outcome, including a call-out when it includes any mismatched files.
- **Guided Empty States**. Views with no data yet will explain the next step in the application's own vocabulary (locations, mappings, baselines) rather than showing a bare empty list.
- **Mapping List View**. Stored mappings will be browsable and manageable as named, recurring relationships, not just visible as the source and destination of individual task cards.

## M2 PROPOSED

- **User-Facing Execution Retry**. Retry a complete execution, an executor failure, or a reviewed safe subset.
- **Terminal Verification Retry**. Retry terminal verification, including a standalone verification and a request to verify remaining files.
- **User Session Cleanup**. Let users request cleanup of NamiSync-owned session temporary files and trash.
- **Richer I/O Failure Types**. Expose more specific typed filesystem I/O causes than the current generic `IO_ERROR` classification.

Durable desktop tasks and queued work retain their M2 status in the feature
sections above. [M2_PROPOSAL.md](M2_PROPOSAL.md) collects the proposed outcomes
without defining an implementation plan.

## CROSS-PROCESS SAFETY

- **Physical-Volume Guard**. Filesystem workflows acquire deterministic cross-process locks for all required local physical volumes and refuse unsafe or contended volumes.
- **Root-Constrained Paths**. Planner and executor workflows reject absolute, drive-qualified, parent-traversing, or root-escaping relative paths. Native workflows keep configured roots lexical and no-follow admit their root-path components below trusted or reviewed volume anchors before physical resolution or volume observation.
- **Long-Path Support**. The service, workflow, scanner, preflight, executor, verifier, and managed-root containment chain explicitly converts ordinary logical paths to `\\?\` spelling at native Windows I/O boundaries, including destinations longer than their source. Plans, evidence, history, and UI paths stay unprefixed; device namespaces and ordinary-ambiguous absolute components are refused rather than retargeted.
- **External-Writer Boundary**. Volume locks arbitrate NamiSync processes only. Under `DEFENSE.md`, full data preservation requires managed roots to remain quiescent from non-NamiSync mutation while execution touches them; observable drift is still refused or reported. Conditional primitives enforce exactly their own condition — non-replacing renames guarantee destination absence, `CREATE_NEW` guarantees temp freshness, `RemoveDirectory` guarantees emptiness — and no path-based primitive binds source identity. Residuals are therefore bounded and classified by data consequence, never elapsed time: a source-leaf substitution routed to an unchanged owned-trash destination is the recoverable EW-1 case; destination-parent redirection, destructive target replacement, and identity-weak content substitution are EW-2 through EW-4 and are outside the supported quiescent baseline rather than automatically accepted. Available stable identity rejects a substituted prepared/published inode before attestation, but an identity-weak same-size substitution or same-object byte mutation is not a handle-bound content guarantee. `ReplaceFileW`, the supported single-call replacement with optional backup, is deliberately not used: it merges the replaced file's attributes, ACLs, and named streams into the replacement and documents partial-state failure cases — hardlink/copy-backup-then-replace is a chosen tradeoff, not the only Windows primitive.

- **Reparse-Point Preservation**. Preserving non-placeholder reparse points (symlinks, junctions) through copy and update remains unrealized; placeholder detection (see Scanner) is a separate, already-handled concern.
- **Network-Share Coordination**. Cross-process locking and scheduling for network shares remain unrealized.
