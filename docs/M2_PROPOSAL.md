# M2 Proposal

This is the single record of proposed later features: the list below, then
detail sections for proposals that need them. It is not an implementation plan,
and becomes the M2 plan when M2 is activated.
[FEATURES](FEATURES.md) owns product behavior and accepted future boundaries;
[ARCHITECTURE](ARCHITECTURE.md#m2--durable-sessions-and-queue-ownership) owns M2
direction. Accepted future outcomes remain binding; unrealized representation
and implementation recipes are reconsidered at first use under [AGENTS](../AGENTS.md).
Listing an outcome does not activate implementation or change current M1 limits.

Design review here is bounded (user decision, 2026-11-20). This proposal
settles only contracts between features, safety and durability rules, and what
the user sees and what it means. Field shapes, mechanisms and exact wording are
decided in each segment's design, where implementation can still choose.
Remaining smaller issues get one triage pass: those that cross features or touch
safety are settled here, and the rest are deferred to the owning segment.

- **Execution retries.** Folded into Same-task retry: retrying a run is a fresh attempt. Retrying a reviewed subset of the same plan is dropped, because idempotent replanning after a partial run already yields only the remaining work for a small new review. Revisit only if rescanning large HDD trees measures as a real cost.
- **Verification retries.** Let users retry terminal verification or verify remaining files, including standalone verification. Same-task retry's routing and close-at-admission rules apply. “Remaining” means what the new attempt finds; the old attempt's candidates and progress do not carry over (user decision, 2026-11-20), which is the simplest model to implement.
- **Same-task retry.** User decisions (2026-11-18, refined 2026-11-19). A retry is a fresh attempt: new scans, plan, review and sessions, with no selection, commitment or authorization carried over. To the user it happens in the same tab, as Inventory Refresh does.
  - **Model.** The in-place model is the priority. It is built from new-task parts: Retry and Edit setup create a new task from the old task's settings, which takes the old task's place in the rail, and the old task closes through the ordinary task Close when the new task's first session is admitted. Old and new are different tasks, so no attempt identity, per-attempt start-response retirement or finished-to-planning transition is needed, and a late control aimed at the closed task gets `not-found`, reported as “already finished”. The three-button alternative (Retry, Plan again in a new task and Edit setup in a new task, always offered and never closing the old task) stays available if the in-place rules prove unworkable: it is that same mechanism without the close, always predictable, but grows tabs and resident plans with every rerun. In place is the default (user decision, 2026-11-20); FEATURES' [Plan Again](FEATURES.md) fresh-task outcome survives only as the secondary “Plan again in a new task” and is reconciled when this design is accepted. Durable task recovery's lineage link keeps Task-Grouped History whole across replacements.
  - **Where it runs.** Every result already says whether the attempt ran. An unrun attempt (a reviewed plan never started, an execution refused at preflight, a canceled scan or plan) changed no files and is rebuilt by planning again, so it always closes at admission; history is irrelevant to it. An attempt that ran closes only while its history is reliable. When its audit degraded, history holds only a committed prefix and the old page holds the only complete per-item account ([HISTORY](HISTORY.md)), so the old task is kept and the new task says why. While any outcome of the old attempt is unknown (lost updates, an unknown control or close result), no retry is offered, because it could overlap work whose result is not yet known. The user does not choose: one Retry, routed by these rules. Plan again in a new task, which never closes the old one, stays as a secondary action for comparing two setups side by side.
  - **When the old task closes.** At admission of the new task's first session. An opened but unsent Edit setup draft, a submitted start awaiting its answer, and a refused start all keep the old task; an unknown start answer keeps it behind the existing recovery fence until resolved. The old plan is closed before the new scan can produce one, so memory stays at one plan per tab.
  - **Availability.** Edit setup is offered while no session of the task is running, pausing or canceling: on finished, paused and held tasks. Otherwise it is disabled with guidance (“Pause or stop the run to change its setup”); scans and plans cannot pause, and use Stop. Opening the draft has no side effect: NamiSync never pauses a run because a form opened. For a paused run (user decision, 2026-11-20): the new task's session is admitted waiting on its predecessor (Session progress and hold reason), so a refused start still costs nothing; then the paused run is canceled. No user action releases that wait: not Resume, Resume all or a relaunch. When the cancel settles, its terminal is recorded in History, the new session becomes an ordinary pending session and the old task closes under the routing above. If the cancel fails, its outcome is unknown or it passes its deadline, the new pending session is canceled instead, which affects no files, and the old task stays. The same applies when the paused run is waiting to resume. The two tasks never both run, and the old one is never left beside a running replacement. Replacing a held or queued committed execution is intended: it was unrun, so it closes at admission like any unrun attempt, after Edit setup's confirmation, and History keeps its admission record (FEATURES' Queue Discard Audit).
  - **Confirmation and notice.** Admission happens server-side after submit, so any confirmation is on submit, and only when something would be lost: when the old task is not safe to close (Task rail batch actions), such as a paused run that could still resume, a reviewed plan whose selection a new plan does not carry, or a held or queued committed execution. Otherwise the new task shows a quiet notice (“Replaced the previous attempt”) with the “Previous run” link when the old attempt ran.
  - **Full rail.** One task slot and its start-response slot are reserved for replacements (user decision, 2026-11-20), so Retry and Edit setup still work on a full rail. Only a replacement may use them; a second replacement submitted while one is still being admitted gets a brief busy refusal. The reserved slot is lent once (user decision, 2026-11-20). If both tasks stay (the old one kept for a degraded audit, or the new one canceled because the old run's cancel failed), the rail is over its bound by one until the user closes a task. Meanwhile new tasks and further replacements are refused with “Rail full: close a finished task”; existing tasks are unaffected.
  - **Back.** The Edit setup draft is page state on the old tab; nothing exists server-side until submit, and the old review stays intact behind it. Back means leaving the draft, or returning after a refused start. After admission there is no back: stopping the new scan leaves a canceled task, and the user edits Setup again from there. An attempt that ran is reached from the new task's “Previous run” link into History.
  - **Dependencies.** The History page, only for attempts that ran, since the app would be closing their only GUI view. Editing Setup before starting needs nothing from History.
  - **Batch actions.** Each task has at most one live session at a time, and Pause all, Stop all and the rail filter act on those sessions. Which tasks a batch action or filter group covers comes from the task's status, not from whether a session is live (user decision, 2026-11-20; see Task rail batch actions): a reviewed plan waiting to start has no live session but is not finished.
- **Edit setup.** Opportunistic, bundled with Same-task retry. Opens a new Setup draft in the same tab, prefilled from the task, so the user can adjust some settings before planning. Nothing is reverted: the draft becomes a new task that replaces the old one at admission, under Same-task retry's rules. Settings are already available: every started plan task keeps a frozen Setup snapshot with the complete options, including filters and the linked-verification choice, in the editable form's shape, even when canceled before an artifact exists. Paths need work: the snapshot keeps only display text and a `location_id`, and the reviewed volume binding lives only in the plan artifact, which a canceled scan or plan never produces. Display text is not authority after drive-letter reassignment ([BUGS](BUGS.md#bug-0167)), and admission by `location_id` fails for locations never executed, which is exactly the first-setup case. The task therefore keeps its admitted bindings on its own process-live record, and one new admission candidate naming a task and side resolves them server-side (the resolution Plan again already uses) into an ordinary choice slot, with the existing offline, ambiguous and changed states. That is one ingress grammar addition under [BRIDGE](BRIDGE.md), one service method and page wiring; inventory roots work the same way. Plan again is then Edit setup followed by an immediate start.
- **Verification open lookahead.** Investigate bounded concurrent first opens within automatic post-copy Verify before changing scheduling. Current serial fresh-file measurements do not establish a concurrency benefit. Preserve ordered classification/recording, honest native readback, bounded handle/buffer ownership and full worker settlement on control; review earlier observation and sharing-lock timing explicitly. Keep Execute→Verify sequential unless a separate workflow redesign is accepted. [PERFORMANCE](PERFORMANCE.md#verification-overlap-scope) owns the scope investigation. This proposal is not implementation authorization.
- **Session cleanup.** Let users explicitly clean up NamiSync-owned session temporary files and trash. Holding volume custody shows that nothing is using the volume now, not that a saved run has given up its artifacts (user decision, 2026-11-20). Cleanup therefore touches only artifacts of runs whose History record is terminal. Artifacts of paused, held, unknown or unrecorded runs are kept and counted (“Kept 3 folders from runs that haven't finished”). Pruned runs keep their summary, so their terminal status survives pruning, and the rule holds before and after Durable work. `.synctrash/<run-id>` is the artifact that clearly needs this. M1's preflight temp recovery already deletes other runs' temps in the touched target folders ([EXECUTOR](EXECUTOR.md)); that stays safe under durable pause only if a paused run owns no temps, which M1's pause at an operation boundary suggests but the design must confirm.
- **Small-file copy batching.** Design grouped parent-directory flushes and grouped ledger commits together. Preserve durability before acknowledging an item, and define how to settle published files after interruption, pause, cancellation or retry. The historical measured-volume saving for directory flushes alone was about 0.22 ms per 4 KiB file. [PERFORMANCE](PERFORMANCE.md) owns the measurement.
- **Unbuffered source reads.** Compare with buffered sequential reads on controlled cold-source workloads; implement only if end-to-end throughput or cache-pressure benefits justify it. Preserve small-file behavior, source admission, exact tail/hash semantics and bounded buffers; reconcile source/target alignment and capability fallback. M1 keeps buffered reads: its repeated-source results and standalone probes do not establish an integrated cold-read gain. [PERFORMANCE](PERFORMANCE.md) owns those observations.
- **Specific I/O errors.** Explain filesystem failures with specific typed causes beyond the generic `IO_ERROR` classification.
- **Hydration-proof scanning.** Postponed, low priority (user decision, 2026-11-20); moved here from [SCANNER](SCANNER.md). The stronger guarantee is that scanning downloads no file content bytes from any cloud provider. Scans already request metadata only and do not trigger OneDrive rehydration in ordinary cases, but directory listing, extra metadata reads and other providers are not covered, and the recall advisory makes no such claim. The study defines the boundary as no file-content hydration attributable to scan access, separately from namespace population and network traffic. It evaluates a metadata-only, no-recall backend across root and ancestor admission, scoped observations, identity fallback and folder mounts, preserving errors, identity, sharing and containment, and verifies online, partially local, local, recall-on-open, virtual-directory, failure and changing-residency cases with provider fetch evidence as well as allocation observations. Adding the no-recall flag to single calls is not partial hardening worth doing alone: it would not cover enumeration, and no recall by scan has been observed. See Microsoft's [attribute definitions](https://learn.microsoft.com/windows/win32/fileio/file-attribute-constants) and [placeholder guidance](https://learn.microsoft.com/windows-hardware/drivers/ifs/placeholders_guidance).
- **Durable task recovery.** Preserve tasks and recoverable session state across application closure or restart. User decisions (2026-11-20):
  - **Recovery store.** A separate SQLite database, the protected recovery-store contract [ARCHITECTURE](ARCHITECTURE.md#m2--durable-sessions-and-queue-ownership) requires. Only the single-instance desktop process writes it. It commits each task's settings and admitted bindings at admission, and records later state transitions as they happen, so holds come back held. It also keeps every reviewed plan, committed or not, with the user's selection, so closing the app loses no review work (user decision, 2026-11-20). Startup reconciliation and the preflight that always runs before the executor acts detect a stale plan. The dispatcher reaches the store through a core protocol that db implements, as with the recorder. A corrupt store or a schema mismatch is rejected; that loses tabs and queue, never evidence, which History keeps.
  - **Paused executions.** A paused execution's continuation (plan, selection, per-operation status, published copy evidence and, during linked Verify, its candidates and progress; [ARCHITECTURE](ARCHITECTURE.md#25-workflow-continuation)) is saved once when it pauses, never per file, and resumes after a restart through the ordinary resume preflight. Resuming keeps linked post-copy verification for files copied before the pause, which Retry's new attempt would not cover. An unstarted execution's continuation is its plan with nothing done, so stored plans and paused state share one versioned format with a bounded check on load. A rejected or mismatched continuation, or a run that crashed while running, comes back interrupted, and Retry continues from there. Before filesystem work resumes, the saved paused state is marked resuming rather than deleted, and it is removed when the run settles (user decision, 2026-11-20); a stored reviewed plan is likewise marked used before execution's first effect. Otherwise a crash after resuming would leave a paused state, or a ready plan, that is behind the files.
  - **Crash, process kill and power loss** (user decisions, 2026-11-20). M1 already keeps files and the ledger never wrong, only behind: the executor flushes file data before publishing, the databases keep SQLite's durable default, custody accepts a mutex abandoned by a dead process, and orphaned temp files are removed. M2's new records each need a launch rule. The rule throughout is that work that was running when the process died is planned again and never resumed; only a deliberate pause resumes. Launch reads the most specific evidence first (user decision, 2026-11-21): the recovery store explains a run before History's missing terminal does, because every valid paused run also has no terminal.
    - A paused state still marked paused: resumable, after the ledger-instance check (Database maintenance gate).
    - A paused state marked resuming, or a stored plan marked used: needs attention with an unknown outcome, offering Retry.
    - A History run with no terminal is only the fallback: it means interrupted, as above, only when nothing in the recovery store explains it, as when the run has no saved record or the store was rejected or lost.
    - Nothing can still be running for an interrupted run once its process is gone, so Same-task retry's unknown-outcome guard, which protects against overlapping live work, does not block Retry. A run counts as interrupted only once its writer is shown to be gone, never merely because the desktop launched: a CLI run may still be writing.
    - A replacement still waiting on its predecessor: dropped; the old task's saved state wins.
    - A restore or migration cut short: each swap is all or nothing, so launch finds either the old database or the new one.

    Process kill and power loss behave alike. Only Windows sign-out and shutdown get the best-effort save under Closing the app.
  - **Launch.** Nothing runs at launch. A committed execution that was queued when the app closed comes back held, as held ones do. Scans, including Browse comparisons, do not start at launch or when the user switches to their tab: a restored task whose content came from a scan shows that it has not been scanned since the restart, with a Scan button. This replaces FEATURES' [Queue Launch Policy](FEATURES.md) CLI flag, reconciled when this design is accepted.
  - **Closing the app.** Today a window close cancels every session and closes only after they settle, without saying so ([DISPATCHER](DISPATCHER.md)). Instead, a close attempt while anything is running reuses Stop all's path: it immediately applies Pause all, then asks for confirmation with counts. On regret nothing further happens, and everything stays paused or held. On confirm, paused and pending sessions are saved, everything else (running scans and plans) is canceled as today, and the window closes once all have settled, showing what it is waiting for (“Closing: waiting for 3 tasks to stop”). Saved sessions are not canceled. With nothing running, close saves and closes without asking. Windows sign-out and shutdown, including Windows Update restarts (user decision, 2026-11-20), allow no dialog and kill the app after a short grace period: NamiSync pauses and saves what it can in that time, and anything unsettled comes back interrupted. Nothing more can be done there.
  - **Bindings.** On relaunch, Edit setup re-resolves the stored bindings into its existing offline, ambiguous and changed states. Stored bindings are evidence for a new admission, never authority ([BUGS](BUGS.md#bug-0167)). A removable drive that comes back under a different letter is matched by volume identity, never by the letter; one that cannot be matched shows as offline or changed (user decision, 2026-11-20).
  - **Lazy restore.** Launch restores only the light parts: rail tabs, state, paths, settings and pointers. A task's heavy data loads when its tab opens. Before loading it, the store records that the task is opening, and clears that after success. A task whose record is still set at the next launch comes back without its heavy data and says NamiSync closed while opening it, with Open anyway and Close; other tasks restore normally. A process killed for memory cannot clear the record, so one bad task cannot cause a launch loop.
  - **Lineage.** Each task records the task it replaced, under Same-task retry. History holds the link, so Task-Grouped History survives losing the recovery store; the store only refers to it. Every attempt is linked, including attempts that never ran.
- **Command-result retention independent of task lifetime.** Allow routine repeated inventory Refresh, acknowledge and restore without eventually requiring task closure to reclaim command capacity. M1 shares 48 retained start/visibility-response slots across the desktop; task-owned entries survive until Close, so a long-lived inventory task can exhaust capacity for other tasks too. Design bounded retirement of settled results while preserving unresolved original-outcome recovery and preventing retired commands from executing again. Coordinate adapter replay and application receipt ownership; increasing the cap alone does not resolve the lifetime issue. The M1 limit and clean refusal remain unchanged until this design is accepted.
- **Durable queue.** Retain queued work across application restarts. M1's queue has no hold: a pending session starts as soon as its volumes are free. From M2, every queue, durable or not, respects holds. User decisions (2026-11-18):
  - Everything in the queue is visible and acted on without distinction: a task created this session and a durable task inherited from an earlier run both look like pending sessions to Pause all, Stop all and the rail.
  - Held is persisted like any other state and comes back held after a restart. A held pending execution must never return wanting to start.
  - Ownership (2026-11-19): the GUI owns the queue. Queue logic stays in the dispatcher, where FEATURES already places it; the desktop process holds the single queue-owner lock while it runs. CLI runs stay foreground runs outside the queue, still kept off busy disks by the cross-process volume locks, and the GUI shows “Waiting for another NamiSync process” while a CLI run holds a volume it needs. The CLI may be aware of the queue in the same way (user decision, 2026-11-20), but never owns it. FEATURES' [Queue Launch Policy](FEATURES.md) CLI flag is reconciled to this when the design is accepted.
  - Nothing in the queue starts an execution through a path that bypasses or takes over a hold. Every execution is created up front, when the user commits, and waits as a visible, holdable entry. The queue may clear an existing entry to run; it never creates one. [WORKFLOWS](WORKFLOWS.md)' “queue releases may replay” a commitment is read this way and is reconciled when this design is accepted.

  This is a precaution: nothing in M1 starts execution or verification without a confirmation behind it (post-copy Verify runs inside the execution session's continuation), and no planned design requires an exception. Scheduled, conditional and recurring runs are deferred beyond M2 (see Scheduling); any later design must fit these rules or be an explicit, separately reviewed exception.
- **Session progress and hold reason.** User decisions (2026-11-20). A session's lifecycle state alone stood in for two other facts, which produced three gaps: a replacement's hold that Resume could release, a paused run waiting in pending to resume that Pause all, closing the app or Edit setup could take for never started and discard, and a saved paused state left behind the files after a crash. Each session therefore also carries:
  - **Progress:** none, a saved continuation, or unknown.
  - **Hold reason:** none, held by the user (Pause all), or waiting on a predecessor (Same-task retry's Edit setup on a paused run).

  The server derives can pause, can stop and safe to close (Task rail batch actions), and Pause all, Stop all, closing the app and Edit setup classify sessions, from progress and hold reason, never from the state name. A paused execution waiting for custody to resume keeps its continuation: Pause all returns it to paused, not held; closing the app saves it as paused; Edit setup treats it as a paused run; and it is not safe to close. Resume and Resume all release only user holds, and a relaunch restores them as held; only the predecessor's settlement ends a wait on it, and the predecessor's cancel has a deadline after which it counts as unknown. A durable claim that the next effect would make false is withdrawn before that effect (Durable task recovery's resuming and used marks). This includes the new edge from `PENDING` to held that Pause all needs, so it is one core contract change in `namisync/core/session.py`, and the foundation for Same-task retry, Task rail batch actions and Durable work.
- **Completion notification.** Investigate in M2 and deliver opportunistically; it implements FEATURES' [Completion Notification](FEATURES.md). NamiSync has no toasts or tray today. Windows toasts for an unpackaged portable app likely need registration (a Start menu shortcut carrying the AppUserModelID, or Windows App SDK registration), which conflicts with the current no-shortcut, no-registry stance ([INTERFACES](INTERFACES.md)); a spike confirms the requirement and the stance is a user decision. Taskbar flash and taskbar progress need no registration and are the cheaper signal while the app is open.
- **Scheduling.** User decision (2026-11-19): deferred beyond M2, kept as an available future feature. A reviewed plan scheduled for later is usually refused by drift by the time it runs; a conditional run (“when this disk appears”) needs preauthorizing an unreviewed plan; recurring runs need a process that outlives the window, starts itself or lives in the tray. A planning-only reminder avoids all three, because planning changes nothing and still ends in review. Its smallest form needs no scheduler: show how long ago each recent pair or preset last synced, and let presets carry an optional “remind after N days” checked at launch and while the app runs. Due pairs are highlighted; plan tasks are not created unasked.
- **Native Fluent overlay scrollbars.** Integrate WebView2's environment option through the Windows host when the backend work is justified. The current pywebview path needs coordinated startup, early navigation/HTML-loading and rendering-test changes; retain the CSS approximation for M1.
- **Verify-only batches.** Batch standalone verification directories. The current Setup runner admits source/target pairs; extending it to single-directory tasks belongs with a reviewed M2 Setup change.
- **Disk usage view.** Answer “what exists here, and what is taking up space?” for a folder or volume, including target capacity shortfalls and `.synctrash` growth. It is the Storage card's view on the Browse page: a sunburst navigator beside a flat one-level table of logical sizes, built from a retained directory-aggregate tree and a listing-only walk. It is read-only, makes no ledger writes, and has no mutation path. [Disk Usage View Detail](#disk-usage-view-detail) records the user's direction, constraints and remaining questions. It is not implementation authorization.
- **Volume overview.** User direction (2026-11-19): the Storage card shows something like Explorer's “This PC” below its path box. Each lettered volume shows its letter and label, space, disk type (SSD, HDD, optical, removable, network, RAM disk), connection (SATA, NVMe, USB, SAS, virtual) and filesystem. Space reads “120 GB free of 1 TB” beside a used-space bar in the progress bar's style, exposed as a meter rather than progress, with the warning color when nearly full. Reusing the progress bar also reuses its indeterminate animation while a drive is still being read, and while a disk usage scan is running. Clicking a row starts a volume-wide disk usage scan. It reads volume metadata only: no scan, no ledger.
  - **Sources.** Already read: `GetDriveTypeW` (drive class), `GetVolumeInformationW` (label, serial and filesystem; root authority keeps the label as evidence) and `shutil.disk_usage` (preflight keeps only free space, but total and used arrive with it). New: `GetLogicalDrives` for the list, and `IOCTL_STORAGE_QUERY_PROPERTY` on a volume handle opened without data access: the device property gives the bus type and removability, and the seek-penalty property separates HDD from SSD. Pulling these through is cheap; the rest is GUI work.
  - **Honest unknowns.** An optical drive without media shows “No disc”. A volume spanning several disks (Storage Spaces, dynamic volumes), or a driver that does not answer, shows “Unknown” rather than a guess. Scheduling treats unknown and USB disks as spinning (Physical-disk scheduling); the label shows only what Windows reports. RAM disks often report themselves as fixed disks and are labelled only when Windows says so.
  - **Bounds.** Each drive is queried independently, off the UI thread, with a deadline: a disconnected network mapping can block for seconds, so it shows “Not responding” while the others render. Network drives are listed, but Disk usage still refuses remote roots and says so. The list refreshes on open and on request.
  - **Spike.** Confirm the queries need no elevation, whether any of them spins up a sleeping HDD, and the per-drive deadline.
- **New browse page.** User decisions (2026-11-19). One page with two cards:
  - **Browse card.** Answers “what exists in A and B, and how do they differ?” without planning a sync: a title, two path boxes and a row with the button and options, so it stays shorter than Sync's Setup. Difference means existence and metadata only: a file on one side only, a possibly modified version of the same file, or the same. Comparison data always comes from fresh scans, subject to the row limits. The verdict comes from the planner's own comparison, called as a pure function (user decision, 2026-11-20), so Browse never says “same” where Send to Sync would plan an update.
  - **Storage card.** A path box with Scan on one row, then the Volume overview. A path scans that folder; a volume row scans the whole volume (Disk usage view).
  - **Moving between them.** A folder shown on the Storage card can be compared with another on the same page. A comparison can send its paths to a new Sync task's Setup draft, the same prefill Edit setup uses; it never closes the Browse task.
  - **Tasks and pages** (user decision, 2026-11-20). Every started comparison or disk usage scan is a rail task, beside Sync and Integrity tasks, and counts toward the task bound. Pause all and Stop all treat a running one as a scan and leave a finished one alone. Open Browse and Storage tasks are restored after a restart; for them that means only their paths and the ledger switch, under Durable task recovery's Scan button. History and Data are not tasks: like Settings, they are mostly static pages, with their own entry points at the bottom of the rail above Settings.
  - **Ledger access.** An on/off switch on comparisons, off by default. Off, both scans stay in memory and the ledger is never touched. On, the two scans run as ordinary Inventory scans, so last-observed times, last-used paths, evidence status beside each file and checksum adoption come with them. There is no read-only ledger mode: showing evidence against a fresh scan needs Inventory's stale and missing reconciliation, which would be duplicated without its writes. Volume-wide disk usage scans never record.
  - **Row limits.** Display is allowed up to 150,000 rows with an advisory past 120,000: before the scan only when a count is known from a previous recorded scan, and during the scan when the count passes 120,000 (“approaching the limit; a narrower folder avoids a refusal”), without stopping it.
  - **Same disk.** Two scans on one spinning disk queue one after the other under Physical-disk scheduling.
  - **Snapshots and custody** (user decisions, 2026-11-20). Both cards show snapshots, so the filesystem can change under them; that is intended and harmless because they are read-only, and Rescan gives the current census. A comparison is a snapshot in full: nothing is read again until Rescan. Disk usage keeps only the folder tree and its totals, and lists the focused folder's files from disk, showing “Changed since scan” on a mismatch ([Size](#size)). Full walks, including a rescan of one folder's subtree, wait for volume custody. Listing one focused folder does not: it is a read-only glance bounded by the per-folder entry wall and a deadline, still admitted against the scanned root like any other read, and its drift is already reported. Waiting would hang a finished view for the length of an unrelated sync without preventing any harm.
- **Physical-disk scheduling.** User decisions (2026-11-19). Volume custody and the scheduler key on volume serial ([DISPATCHER](DISPATCHER.md#admission-and-volume-scheduling)), so two partitions of one HDD count as different disks and their sessions run at once, fighting over the drive head. That costs speed, not safety: each volume keeps its exclusive lock unchanged. Add a scheduling key per physical disk for spinning disks only, from `IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS`; a volume spanning several disks takes all of them, and SSD and NVMe sessions keep today's concurrency. Disk numbers change across restarts and device changes, including within one session, so they are never stored and are read again at every start attempt, fresh, resumed or restored (user decision, 2026-11-20). Whether a disk spins is stable per volume in practice but is re-read each time, because the query is cheap. User decisions (2026-11-20):
  - **Reading.** The scheduler needs the key before it decides to start a session, which is before preflight. Each session supplies a key-reading callback at admission, and the dispatcher calls it at each start attempt, just before custody, so the dispatcher stays domain-blind.
  - **Unreadable keys.** A volume whose disk extents cannot be read (RAM disks, encrypted containers, some virtual volumes) falls back to today's per-volume custody with a quiet advisory (“Couldn't tell which physical disk this is; it may share the disk with other work”). It is not refused: the key affects speed only, and volume custody still protects every volume.
  - **Spinning or not.** Whatever Windows does not answer, or answers unreliably, counts as spinning: a failed or unanswered seek-penalty query, and every USB disk regardless of what it reports, since many USB bridges do not pass the drive's rotation through. No guessing and no further checks. The worst a wrong answer does is serialize SSD work, thrash a disk or show a wrong label.
- **Drive-type awareness.** The same seek-penalty query, under Physical-disk scheduling's rule that unknown and USB disks count as spinning, informs scans elsewhere: a notice when a scan runs on a spinning disk, separate HDD and SSD time estimates, and possibly parallel folder listing on SSDs, only after measurement shows it helps. HDD scans stay serial.
- **Shell actions.** Copy Path, Open in Explorer and Properties for rows on every page, with optional click-through. Each action resolves a server-owned node id to a path on the host side; the browser never supplies path text. No file is ever launched, and NamiSync performs no mutation. On Plan, side-labelled Source and Target actions avoid an implicit side choice. Missing items keep only Copy Path and Open containing folder. [Shell Actions Detail](#shell-actions-detail) holds the policy and cost notes.
- **Checksum adoption.** Copy content evidence from one location to another for metadata-equal pairs (no-op pairs), so existing duplicate backups gain checksums without hashing. The next Verify confirms or mismatches them. Sync execution is the natural first home: each selected paired no-op already re-checks both live stats against the review and calls `record_noop` ([RECORDER](RECORDER.md)), so adoption would extend that recording as a reviewed, fingerprinted plan option, with the adoptable count shown in review. The Browse card is a second home when its ledger switch is on, behind a counted confirmation because it writes evidence, possibly in either direction. The origin's evidence must be current: its attested stats match its current observation and carry no invalidation. The receiving row must have no evidence; a different existing digest is never overwritten and is reported as disagreement. Recording uses the conditional primitive. Adopted evidence gets a new provenance naming its origin. It never advances `last_verified_at`, and the state stays unverified. Baseline skips it, so Verify is the check, and a later mismatch is labelled as differing from the adopted origin. The row then states what was observed (a metadata match plus the origin's evidence), not that target bytes were read, which preserves never-wrong-only-behind. Adoption may chain (user decision, 2026-11-20): evidence adopted from A into B may be adopted again from B into C, because metadata sameness is already the premise and each step stays unverified until Verify. The provenance names the original origin, the row whose bytes were actually read, plus how many adoption steps the evidence went through, never the intermediate row. Eligibility that changes after review (user decisions, 2026-11-21) is rejected in both directions, because adoption acts only on what was reviewed or confirmed and only while it still holds. Each pair is checked again as it is written, through the conditional primitive: the origin's evidence is still current with the reviewed digest, the receiving row still has no evidence, and both live stats still match. Any change skips that pair, including the receiving row gaining any checksum, same or different. A skip is not a failure, because adoption only adds evidence: the no-op is still recorded and the result says “12 adoptions skipped because evidence changed since review”. A pair that becomes eligible after review, such as an origin gaining a checksum, is never adopted, since the reviewed count and the fingerprint cover it. Disagreement found at review is still reported. Both homes call one workflow operation over the db layer's conditional primitive, so they cannot diverge: Browse re-checks live stats as execution already does, its counted confirmation plays review's role, and its write takes the Database maintenance gate's shared claim like any writer. A new `Provenance` value is a core, ledger and history contract change, carried by Schema migration's format versions; data epochs are dropped.
- **User-defined presets.** Create, customize and persist reusable sync pairs and inventory roots that otherwise populate Setup and use availability checks like ledger-derived recent pairs. Persistent records and bridge commands are new work; presets do not retain admission or execution authority.
- **Schema migration.** Add the ordered migration that [DATABASE → Schema Evolution](DATABASE.md#schema-evolution) describes (backup, supported-source check, transactional migration, integrity check, restore or refuse on failure) before a released version's data must survive a schema or contract change. Every later item that changes stored data depends on it. User decisions (2026-11-17): each database migrates on its own, in its own transaction. Data epochs are dropped (epoch 8 reset the ledger for a history-only constraint), while schema-version and contract checks stay. The migrator does not check `data_epoch` at all (user decision, 2026-11-19): every existing database is treated as epoch 8, the format v0.1.0 “Gertrud” released with. Epoch-7 databases exist only from early pre-release M1 builds, none of which should still be running. A replacement guard must catch two things: our own mistakes, such as a shared format changing while only one database is bumped; and user-side mismatches, such as databases left at different formats by an interrupted upgrade or a backup restore. Candidate measures:
  - Core-owned version constants for each shared format (event encoding, evidence and hash preimage, identity text, numeric encoding), each with known-answer test vectors. Changing an encoding without a new constant and vector fails tests.
  - Each database stores its role, schema version and every embedded format version as separate metadata rows instead of one contract string. Schema code declares which formats each database embeds. A test fails when a core format changes and an embedding database has no migration or invalidating step for it.
  - At open, each database must match the application's current formats after its own migration; a newer database is refused. Pairwise agreement follows.
  - The ledger gets a random instance id at creation, and every history run records the ledger instance it was recorded against. Cross-database lookups apply only to matching runs; other runs are shown as belonging to an earlier ledger. A ledger restore gives the ledger a new instance id and records its predecessor's id and the backup's cut-off time, a lineage boundary like the missing-ledger case below (user decision, 2026-11-20). A run then joins the ledger if its instance matches, or if it belongs to the predecessor and started before the cut-off. Without this, a restore keeps the id while ledger ids are reused: `locations.id` is a plain `INTEGER PRIMARY KEY` that History stores as `subject_id`, so a location created after the restore takes the id of one created after the backup, and History runs from that period would resolve to the wrong location.
  - **Ids are never reused** (user decision, 2026-11-21). Reuse needs no restore. No table uses `AUTOINCREMENT` (`namisync/db/schema.py`), so SQLite gives a new row the highest id plus one: forgetting the highest-numbered location (Data page) frees its id for the next new location, and History, which keeps referring to forgotten locations, would silently resolve their runs to the new path. History pruning exposes History ids the same way. M1 never deletes location rows, so the hazard arrives with Forget and pruning. Rule: an id referenced from outside its own database is never reused. Every table whose ids are referenced elsewhere gets `AUTOINCREMENT`, so SQLite never hands out a deleted id again within that database file: in the ledger at least `locations`, and in History any run id something outside History refers to. Which tables qualify is a design-time inventory; adding it rebuilds the table under this migration. The instance id still covers restore, because a restored database also brings back its old id counter. A stale reference then fails cleanly: History, the recovery store's bindings, stored plans and, if they stay in the ledger, annotations get not-found instead of a wrong match, and History shows a forgotten location as such, never as another path.

  Missing databases: with only a ledger, create a history and notify the user. With only a history, notify, create a ledger with a new instance id, and record a durable lineage boundary that the History page shows. The old history is kept and never treated as describing the new ledger, and ledger records are never rebuilt from history. More history than ledger is acceptable, including after a ledger restore. Less history than ledger, after a History restore, is equivalent to History pruning, which the ledger already tolerates. Policy refinements with no open decision: an invalidating step for values that cannot be converted keeps observations and marks attestations unverified instead of resetting; `settings.json` and UI state carry their own versions; and a fixture database saved from every released version (today only v0.1.0) is migrated in tests.
- **Database maintenance gate.** User decisions (2026-11-20). Migration, restore, archive-and-reset, reclaiming file space, history pruning and purge must not run while any run's records are still being written to either database, including overlapping scans and syncs and their recording tails. [DATABASE](DATABASE.md) has no such gate today.
  - **Owner.** The db layer, because only its writers know when a run's last write has landed; the dispatcher stays domain-blind. Every writer holds a shared claim from its first write until its last is flushed: the ledger recorder, and the History observer, which can start writing before the recorder and keep writing after it finishes. One gate covers both databases, and maintenance on either takes it exclusively, because a ledger restore while History is still writing location ids is exactly the id-reuse hazard under Schema migration. Maintenance takes the claim exclusively and refuses, rather than waits, while any shared claim is held. While maintenance holds it, new runs are refused. Readers take no claim: SQLite reads are consistent snapshots, and a stale view is only behind. Maintenance that touches files still takes volume custody through the dispatcher.
  - **Cross-process, including the CLI.** CLI parity gives the CLI maintenance commands, and CLI runs write the same pair, so an unguarded overlap would leave a false record: a purge orphaning a run's items, a restore receiving a run's tail, or a migration under a running writer. Ordinary concurrent runs need no gate; SQLite orders their writes. Candidate mechanism: `LockFileEx` shared and exclusive locks on a lock file beside the pair, which Windows releases when a process dies. Dispatcher custody's named mutexes are exclusive only.
  - **Waiting work.** Every stored plan and paused continuation records the ledger instance it was planned against, and preflight refuses a mismatch (user decision, 2026-11-20). Because restore and archive-and-reset give the ledger a new instance id (Schema migration), work planned before them can never record against reused ids. On top of that, restore and archive-and-reset refuse while any reviewed plan, held or queued execution or paused run exists, and name them (“3 queued syncs were reviewed against the current ledger; stop them first”), so the user is not surprised later. The gate alone does not see this work because it is not writing.
  - **Residual.** Processes from versions released before the gate do not take it, so the first migration is unprotected against them; accepted.
  - Settings keep their own named mutex, and the recovery store has a single writer, so neither is behind the gate.
- **History page.** The desktop form of the [History Dialog](FEATURES.md) feature: a run list and paged run detail over the existing history readers, with an activity-kind filter, so inventory and later pages need no history page of their own. [INTERFACES](INTERFACES.md) SH-G-9 applies. User decisions (2026-11-19): History storage stays as it is. A reopened run is a static record page, not a revived task: it shows the summary and per-item outcomes it retains (history keeps outcomes, not the plan's review tree), and only the summary once detail retention prunes items. It offers no Retry. “Open in Setup” opens a new task's Setup draft with the run's paths entered as typed paths, admitted by the ordinary checks, and settings at the current defaults, which the page says. Run settings are not stored: storing them would need a schema change and compatibility rules for every later settings change, to save a few clicks. History is permanent, so it would carry those rules forever, unlike the recovery store, which may discard a mismatch. FEATURES' [Restorable Task Setup](FEATURES.md) is narrowed to paths when this design is accepted. Recording location ids for the paths stays negotiable; sync runs already share a `run_token` with the ledger's run row.
- **Task annotations.** Implements FEATURES' [Task Annotations](FEATURES.md#history) over [Generic Annotations](FEATURES.md#files-ledger) (added 2026-11-20). A note attaches to a History run, so replacing a task in place strands nothing, and the lineage link shows the chain. Only the ledger's `annotations` table exists today (`namisync/db/schema.py`); there is no repository, writer path, workflow or bridge command. Because the table is in the ledger while runs live in History, a ledger restore or archive-and-reset would roll back or lose notes on runs History keeps, and after a History restore, reused History run ids could attach notes to the wrong runs. Both favor moving the table to History through Schema migration; decide at design. Where the note box goes is open; History's run detail is the likely first home.
- **Data page.** Location-level ledger management plus database maintenance, without per-record browsing. Each tracked location shows its row count, last scan and verified, unverified, stale, missing and acknowledged counts. Actions: purge acknowledged-missing rows, forget a location (refused or paired with forgetting its mappings while one uses it), and the [Data Protection](DATABASE.md#data-protection) maintenance sessions: check, backup, restore, history pruning and a guided archive-and-reset. Purging is irreversible evidence loss. User decisions (2026-11-19): it asks for confirmation in a modal with the count, like destructive confirmations; the modal need not offer a backup, since Backup is a separate action beside it. It runs as an ordinary maintenance session holding the location's volume custody, so it never overlaps a scan, plan or execution there, and deletes in bounded batched recorder transactions. Forgetting is the user's explicit choice: a later scan that includes the folder records it again, and a preset's filters are the way to keep it out, since exclusions belong to one run. Forgetting is an immediate, non-restorable delete behind the same counted confirmation modal as purge, since it loses more evidence than a purge (user decisions, 2026-11-20); FEATURES' [Soft-Deleted Mappings](FEATURES.md#data-protection) is reconciled to that when this design is accepted. History keeps referring to forgotten locations, by ids that are never reused (Schema migration). Maintenance sessions are not rail tasks: their progress shows on the Data page. Pause all leaves them alone, and a restore never stops mid-swap, so Stop all and closing the app wait for it (user decision, 2026-11-20). Reclaiming file space, purging and pruning take the Database maintenance gate. Restore returns the ledger to the backup's state (user decision, 2026-11-20): evidence recorded after the backup, including mismatches and missing files, is gone until the next scan or Verify finds it again, as with any restored file. The restored ledger gets a new instance id with a lineage link to the one it replaced (Schema migration), so History never resolves later runs against reused ids. That is behind, not wrong, because every attestation is a dated claim. Evidence is therefore shown with its date: Inventory's details already show Last observed and Last verified, which stays as is.
- **Recent locations.** Sync recents are a bounded ledger query (five each) over sync runs that started execution on active mappings; they are not a stored list and do not use history. History is the wrong source, because it stores path text instead of volume identity and has its own retention. Inventory roots have no ledger run row. To study: one ledger-owned last-used record per location and purpose (sync source or target, inventory root, browse), written only by runs, as FEATURES' Run-Derived Recent Locations requires. Planned pairs that never executed are not recorded (user decision, 2026-11-20): Durable task recovery already keeps their reviewed plans across restarts. It is a schema change, so it follows Schema migration. Read-only use of the Browse page (disk usage scans, and comparisons with the ledger switch off) keeps no recents (user decision, 2026-11-19), as the disk usage [Non-Goals](#non-goals) already state; a comparison with the switch on records last-used paths as Inventory does. The write itself would be harmless (one small upsert behind SQLite's single writer, invisible to WAL readers), but it would make a read-only page create and write the ledger, and tie it to Schema migration and the Data page's forget and purge. If they are wanted later, they belong in UI state, not the ledger.
- **Shared review surface.** Plan and Inventory each build their own header, view switcher, status card, table and details pane (Plan composes the table controller directly, Inventory through `tree.js`), and they drifted repeatedly in M1. Examples: switcher labels Plan/Verify versus Sync/Integrity, and differing details empty-state and missing-value text. Build one review component that owns the shared chrome, the table and the details fact list and its states. Pages supply columns, cells, facts, a data source and actions; any deviation is an explicit option. Guard it with a parity test that renders both pages from one fixture against a documented list of allowed differences, plus a static check that pages do not assemble shared parts directly. The gallery shows the real component. It lands before any new M2 table.
  - **One table component** (user decision, 2026-11-19). Two table families exist today and share only base scroll and layout classes: Recent pairs and the batch table are native tables with 56 px two-line rows, five fixed slots and about 40 Setup-specific style rules; the review tables are windowed `div` rows of 24 px with sorting, selection and details. Having two families is itself the defect. Every table becomes one component built on the windowed review substrate, which can also render a few rows; the review chrome is a layer above it. Each instance configures row height and line count, wrapping, columns, sorting (available to small tables too), growth (fixed slots that scroll, or filling the page) and row interaction (a click runs an action, or selects and shows details). The row-action hover and press behavior Recent pairs needed many fixes to get right is solved once in the component. Recent pairs and the batch table move onto it before the Volume overview lands.
- **Custom title bar.** Extend content into the caption area while keeping the native frame (pywebview's `frameless` mode removes it), and move the task view switcher into a SelectorBar-style control beside the title. A framing spike comes before the GUI change and must keep Snap Layouts, resizing from every edge, double-click maximize, Alt+Space, high contrast, mixed-DPI monitors and Mica. The selector itself is small; settle the switcher label drift first.
- **Easier exclusions.** Extends FEATURES' [Filter Rule Editor and Filter Exclusion Explanation](FEATURES.md#filters). Plan and Inventory row menus offer “Exclude this folder”, “Exclude this file” and “Exclude files like this”. Each composes a pattern, shows the pattern and its effect before applying it, and starts a fresh plan or scan; a reviewed plan's frozen filters never change. Patterns get plain-language explanations while typing, and presets carry their filters. Inventory has no user exclusions today. Exclusions are temporary and belong to one run, as in Sync, and Inventory's work the same way (user decision, 2026-11-20): during a filtered scan an excluded subtree gets no coverage and is never marked missing; its rows simply fall behind until a scan includes it again. Nothing is stored per location, and a sync recording rows inside a subtree that an earlier Inventory scan excluded is ordinary. Keeping a folder out every time is a preset's job, since presets carry their filters.
- **Drag-and-drop Setup.** Refines FEATURES' [Drag-and-Drop Setup](FEATURES.md#desktop-ui). Each path field is its own drop target, with no guessing of source or target order. One dropped folder fills that field and goes through the same admission as a picker choice. A dropped file shows the existing “not a folder” refusal, and several items are refused with guidance. The paths come from WebView2's native dropped-file objects, received by the host; the page only forwards the drop. pywebview's own drop helper matches paths by bare file name, so NamiSync needs its own bounded host handler instead. A spike confirms folder paths and the elevation boundary.
- **Task rail filter.** The rail holds up to the task bound (48 today, at most 256 under Task capacity), and batches can fill it. A presentation-only filter by state group (active, ready for review, needs attention, finished), using existing snapshot facts. Each task status maps to exactly one group, by the precedence in Task rail batch actions. It never hides the current task, shows how many tasks are hidden, and resets for newly created tasks. Durable tasks make it more valuable.
- **Task rail batch actions.** A rail context menu first: Close finished tasks, Close other finished tasks, Pause all, Resume all paused and Stop all. Batch Close acts only on tasks in the finished group; closing a running task stays a deliberate single-task cancel-then-close. A finished task whose page holds the only complete per-item account (degraded audit) closes like any other, as it does individually; Batch Close's count names such tasks (“2 of these have item details that History doesn't”) (user decision, 2026-11-20).
  - **Eligibility** (user decisions, 2026-11-20). Bulk eligibility and filter groups come from the task's status, which every task already has, never from whether a session is live: a reviewed but uncommitted plan has no live session and is not finished. Each status maps to exactly one group, with the precedence needs attention, ready for review, active, finished, so Close finished tasks never reaches a plan awaiting review. The server derives three capabilities from status in the interface layer, never in page code: can pause, can stop, and safe to close. Safe to close is false while a task holds a resumable paused run, a reviewed plan (committed or not), a held or queued execution, a page with a degraded audit, or an unknown outcome. It does not change a task's group; it feeds Batch Close's count, the app-close dialog's counts and Edit setup's confirmation.

  User decisions (2026-11-18):
  - **Pause all** stops everything that can stop and starts nothing new. Running execution, Verify and Baseline pause as today. Running scans and plans are left alone: they are usually done in seconds, and pause is not stop. Every session that has not started, of any kind, is held and does not start. Holding is not pausing, so FEATURES' per-kind pause capability still governs running sessions only. This needs a new edge from `PENDING` to held in core's session transitions (Session progress and hold reason): a never-started held session has no custody and no continuation, so resuming it starts it fresh, and the UI labels it as not started rather than implying progress. A paused run waiting in pending to resume has a continuation and returns to paused instead. Pause all is one atomic dispatcher operation. Pausing running sessions one at a time would release their volumes and let the scheduler start queued sessions before they are held. The result reports paused, held, already pausing and still-running counts.
  - **Resume all paused** re-queues paused and held sessions in their original admission order (`admission_order` is already kept on each record). Sessions started while everything was held stay ahead of them. Resume still never preempts. It also resumes runs the user paused individually before Pause all; that is intended (user decision, 2026-11-20).
  - **Stop all** applies Pause all first, then asks for confirmation with a count, like destructive confirmations. Confirm cancels every unfinished session; regret leaves everything paused for an explicit resume. Pausing includes tasks with an Edit setup draft open: Edit setup's rule only means that opening the draft is not itself a reason to pause (user decision, 2026-11-20). Pausing first closes the race window for everything except running scans and plans: if they finish, they are harmless; if not, they receive the blanket stop. No preflight or fingerprint is needed. A late stop must be harmless by contract, not by accident. Finished states have no outgoing transitions and cancel on them returns `illegal-state` without a change; a released session returns `not-found`. Both are reported as “already finished”, and a test names this guarantee. Batch admissions (user decisions, 2026-11-20): a batch only ever starts scans, which are read-only, cost nothing to rerun and are canceled on confirmation if still running; no batch row starts execution or verification. The preferred design pauses the batch runner too, best-effort and page-side: the runner is a serial page loop that already checks before each row whether it may still submit, so Pause all sets a page flag before sending its command, the loop stops before its next row, and unstarted rows stay queued. Resume all restarts the runner for a batch it stopped, and Stop all's confirmation leaves queued rows queued, since they are not sessions. One row already being submitted can still start a scan, which confirmation cancels, and a close dialog the page does not own falls back to the plain race. That plain race is also an acceptable fallback if pausing the runner proves costly: the batch was started before the pause, scans it starts during the dialog are covered by the blanket stop, and the worst case is a count race (the dialog counts x and x+n are stopped). Harm would lie only where execution or verification could start without user confirmation; Durable queue rules that out.

  Same-task retry defines “finished” and which session a batch action targets. A server-side bulk command keeps a full rail within the bridge's 64-exchange bound. Ctrl/Shift multi-select, like browser tabs, is optional later; it needs listbox keyboard and screen-reader semantics, and a selected set distinct from the current task.
- **Stop while checking, scanning or planning.** The review shell shows Checking, Scanning and Planning with no Stop control; Stop exists only for execution, so stopping a scan today means closing the task. Add the existing Stop control there. The scanner already checks cancellation between directory entries, and cancellation releases volume custody at settlement, so stopping should take well under a second. A single blocking Windows call cannot be interrupted, so a sleeping HDD's spin-up or an unresponsive network share can take longer. Planning computation after the scan has no checkpoints, but it does not use the scanned volumes. To measure: cancel-to-release latency on the HDD fixture ([PERFORMANCE](PERFORMANCE.md)). A stopped scan or plan has no artifact, but the task keeps its setup and admitted bindings, so Retry and Edit setup rebuild it in place under Same-task retry.
- **Task capacity and resource policy.** User direction (2026-11-17): NamiSync bounds what it promises, not what users may attempt. Twenty 100k-file syncs are allowed. Keep a task count only as a transport-safety bound, raised from 48 to at most 256 (user preference, 2026-11-19; the value is chosen after profiling) together with the start-response slots, which each open task holds until Close ([INTERFACES](INTERFACES.md)). Raising one without the other only moves the refusal; Command-result retention is the lasting fix. Do not refuse on memory. Instead, inform: the README notes that open tasks keep their plans in memory, and the app shows a quiet notice when open tasks hold many rows, suggesting closing finished ones. Optimize large tasks first. The measured roughly 2.4 GB whole-application peak at 100k entries is about 23 KB per entry, browser included. Profile the plan, presentation projections, view windows and renderer before choosing compact row storage or releasing execution-only state after settlement. [PERFORMANCE](PERFORMANCE.md) owns the measurements.
- **CLI parity.** Make the CLI good by M2. Anything with shell access may commit; NamiSync is not a barrier against file operations that other tools can perform anyway. A plan must still be reviewed, by a person or an agent. Additions:
  - `--json` on every command: event lines and one final result object.
  - `sync --plan-only` prints the plan and one commitment token; `sync --commit <token>` plans again and executes only on a match. The interactive prompt remains for people, and no flag plans and executes unreviewed. User decisions (2026-11-20): the token reuses the existing `Commitment` (`namisync/core/execution.py`), covering both the plan fingerprint and the selection digest, so a commit binds which operations were approved, not only the plan. `--commit` repeats the selection flags, and they must reproduce the token. The digest is taken after dependency closure, so different spellings of the same selection match. No selection flags means every operation, which is also a digest. A mismatch is refused with the difference named (“The plan matches, but this command selects 1,310 operations and you reviewed 1,204”).
  - Per-run plan options matching Setup (`--exclude`, `--preserve-created`, `--preserve-acl`, `--propagate-casing`, `--trash-on-update`), never saved as settings.
  - Partial runs by exact operation id. Ids are deterministic hashes of operation intent, so a fingerprint-matched replan reproduces them. Use `--select-op` and `--exclude-op`, or a file of ids for long lists, with dependency closure applied as in the GUI and the result shown before commit. Kind and path filters cover broader selections.
  - A `settings` command (`show`, `set`); ledger browsing by location without rescanning; acknowledge and restore missing files; the Data page maintenance actions; history filters (`--kind`, `--since`); `verify --run <token>` for a past run's copies; `recent` locations. A command scoped to a run refuses when History can no longer define that scope, and never silently widens it (user decision, 2026-11-20): after pruning, `verify --run` names the reason and the wider command (“Run X's file details were pruned on <date>; to verify the whole destination, run `namisync verify <target>`”). After a degraded audit, History holds only a prefix of the run, so it says how much it covers (“History has 1,204 of this run's 1,310 copies”) or refuses rather than silently verifying less. The History page's run detail follows the same rule.
  - Review output an agent can use. A 100k-operation plan is tens of megabytes, far beyond any model context, so output leads with a sufficient summary (counts and bytes per kind, the destructive breakdown, refusals, filters and options), lists destructive operations in full up to a bound, and writes the complete operation list as JSON lines to a file that tools can query. A harnessed agent reviews the summary and destructive subset, then searches the file as needed.

  Not ported: tree browsing, search and sort (query the JSON instead), batches (shell loops and exit codes), the folder picker, appearance, Plan Again (run the command again) and Pause/Resume (Ctrl+C cancels a foreground run).
- **MCP adapter.** Postponed; study and deliver opportunistically after CLI parity. It would be a thin adapter over the same service and commands, subject to [BRIDGE](BRIDGE.md)'s ingress contract. Read-only and planning tools come first; commitment follows the CLI's fingerprint rule.
- **Progress chart.** Implements FEATURES' [Throughput Graph](FEATURES.md#desktop-ui) together with Status Layout Refinement. The compact bar expands into an Explorer-style chart of transfer rate against progress. The Python adapter already keeps a monotonic sample history for estimates. It would add a bounded, progress-bucketed rate series to the task snapshot (a new internal snapshot version), so a page reload keeps the chart. Pause, a new phase and Gap show as breaks rather than invented rates. Execution and post-copy Verify are separate series.

No further Settings are planned. A setting arrives only with a feature that brings a user choice.

## Grouping And Order

A proposed order, not scope activation. M2 is delivered in three larger
segments (user direction, 2026-11-20), each with its own aim in place of one M2
thesis. The first carries mostly backend work with little immediate user value,
but later user-facing features rest on it. To keep its contracts from being
designed for imagined needs, each foundation piece ships with its first real
consumer, even a thin one. Rows within a segment are in dependency order.

| Segment | Group | Items | Depends on |
| --- | --- | --- | --- |
| 1. Safe to change the databases | Early spikes | Live checks and measurements (user decision, 2026-11-18): framing; drag-and-drop paths; completion notification; volume overview queries; Stop's cancel-to-release time on the HDD fixture | None; each informs its feature's design. |
| 1 | Persistence foundation | Schema migration; Database maintenance gate; Data page maintenance sessions, the gate's first consumer | Must be ready before released data has to survive a change; the gate comes before any maintenance session. |
| 1 | Session states | Session progress and hold reason, including the held edge | None. |
| 1 | Shared review surface | Shared review surface, including one table component and moving Recent pairs and the batch table onto it | Must land before any new table. |
| 1 | Capacity | Large-task memory profiling and optimization; raised task and start-response bounds; README and in-app notices | Profiling before choosing bounds; Command-result retention for the lasting fix. |
| 1 | Disk awareness | Physical-disk scheduling; Drive-type awareness | The volume overview queries spike. |
| 2. See and act on what happened | History and data | History page; Task annotations; Data page location management; their entry points above Settings | Persistence foundation. |
| 2 | Retry | Same-task retry (absorbing Execution retries); Verification retries; Edit setup | Session states (the wait on a predecessor); History page, for closing attempts that ran. |
| 2 | Task presentation | Task rail filter; Task rail batch actions; Stop while checking, scanning or planning; Progress chart | Session states (held and capabilities); Same-task retry's close-at-admission and “finished” rules. |
| 2 | CLI | CLI parity | The maintenance sessions in Persistence foundation for its maintenance commands, not the Data page; the rest is independent. |
| 2 | Setup | Recent locations; Verify-only batches; User-defined presets; Drag-and-drop Setup; Easier exclusions | Schema migration where records change; the drop spike. |
| 3. Work survives the app | Durable work | Durable task recovery; Durable queue | Schema migration (the lineage link); Session states; Same-task retry (lineage, reserved slot); Task rail batch actions (Stop all's path for closing the app). |
| Unassigned | New pages | New browse page (Browse and Storage cards); Disk usage view; Volume overview; Shell actions | Shared review surface; Edit setup's prefill for sending paths to Sync; the planner's comparison as a pure function. May join segment 2 or follow it as its own. |
| Unassigned | Window | Framing spike, Custom title bar, Native Fluent overlay scrollbars | The spike comes first. |
| Unassigned | Evidence | Checksum adoption | Schema migration. |
| — | Independent | Verification open lookahead, session cleanup, small-file copy batching, unbuffered source reads, specific I/O errors, command-result retention; Completion notification | None; the notification spike comes first. |
| Later | Postponed | MCP adapter | CLI parity. |
| Later | Postponed | Hydration-proof scanning | None; low priority. |
| Later | Beyond M2 | Scheduling | Durable work; a process that outlives the window. |

## Disk Usage View Detail

Study detail for the Disk usage view, the Storage card's view on the Browse page.
Merged from the former disk usage study (2026-11-19); its inspected revision was
`ebf72fbe`. Nothing here activates implementation or changes an M1 limit.

### Prompt

Spaceketeer was a Windows disk-usage viewer. It is no longer distributed: its
Store listing is gone, and its website remains without its web apps or contact
links. It scanned a drive or folder and showed a sunburst chart next to a flat,
Explorer-like table with Name / Contents (“N files, M folders”) / Size columns.
The table lists one level only. The sunburst goes a few rings deep, shows
folders but not individual files, and caps how many segments it draws. It
offered Pause / Resume / Rescan, Copy Path, Open in Explorer and Properties.
NamiSync's scanner and inventory already compute most of that data. The
question is whether NamiSync should present it the same way.

### User Goal

The view answers **“what exists here, and what is taking up space?”** Each
view answers a different question:

| View | Question |
| --- | --- |
| Plan / execution | What will change on the target? Rows describe operations, mostly from the target's side, so it is a poor view of what simply exists. |
| Inventory | What evidence do we hold for a tracked location? |
| **Disk usage (Storage card)** | What exists in one folder or volume, and how big is it? |
| Browse card | What exists in A and B, and how do they differ? |

Inside NamiSync the question also comes up without being asked:

- Plan review reports a capacity shortfall on the target, and the user needs to
  know what to clear.
- `.synctrash` and displaced update versions grow on the target. Nothing shows
  how much space they use until a trash retention policy exists
  ([FEATURES → Trash Retention Policy](FEATURES.md#data-protection)).
- Before a first sync, the user wants to see the shape of a source tree.

### Decisions (2026-11-15)

| Question | User direction | Consequence |
| --- | --- | --- |
| Placement | Revised 2026-11-19: one Browse page with two cards. The Storage card (a path box with Scan, then the Volume overview) opens this view; the Browse card compares two locations. | See [Page](#page) and New browse page above. The cards share a page but not their scans, so neither feature blocks the other. |
| Size meaning | Logical (end-of-file) size from `os.scandir`. The small difference from allocated size is tolerated; Properties shows the exact on-disk figure. Probe the known divergent cases before implementation, for rigor. | No new enumeration backend; see [Size](#size). |
| Shape and scale | Spaceketeer-like: one flat level of files and folders, and a few-ring sunburst of folders. | The whole tree is still walked, but only directory aggregates are retained; see [Scale](#scale). |
| Volume custody | Wait. Say so visibly, so the user can choose to pause a sync on that volume. | No new dispatcher custody mode; see [Session behavior](#session-behavior). |
| Chart | Sunburst. Each ring shows only the largest few child folders above a size threshold, so it stays readable. | Parent totals come from the aggregate tree, so no separate slice-merging pass is needed; see [Chart](#chart). |
| Copy Path, Open in Explorer, Properties | Wanted on every page regardless of this feature. Click-through is nice to have. Plan prefers the target side, but copies and updates point naturally at the source. Missing items get no item actions; their folder can still open if it exists. | Separate proposal (Shell actions above). Side policy is under [Shell actions detail](#shell-actions-detail). |

### What Exists Today

| Spaceketeer capability | NamiSync now | Gap |
| --- | --- | --- |
| Recursive walk of a folder or whole drive | Scanner FULL scan. Volume roots are admissible locations (displayed as “Volume root”). | The sync scanner opens every entry on NTFS to read file identity; see [Size](#size). |
| Per-folder total size | Inventory projection rolls up complete file bytes. Overflow and unknown bytes are explicit, never clamped ([INVENTORY](INVENTORY.md#stage-6-desktop-contracts-protocol-subset-active)). | Requires a ledger-backed inventory. |
| Contents (“N files, M folders”) | Rollup counters already include descendant row and file counts (`inventory_projection._row_counters`). | No column. |
| Largest-first table | Server-owned sibling sort on Size ([PRESENTATION](PRESENTATION.md#search-filters-sorting-and-follow)). | **Folders cannot be ranked by total.** `sibling_order.sorted_siblings` sorts files first, then folders by their own size, not their aggregate bytes. |
| Flat one-level list with drill-down | Bounded tree with expand and collapse. | No flat “focus folder” list or breadcrumb. |
| Chart | None. | New. |
| Rescan | Whole, exact or recursive-folder Refresh. This is already finer than Spaceketeer's. | None. |
| Pause / Resume | Inventory scan is cancel-only (pause unsupported). | Not needed. |
| Copy Path, Open in Explorer, Properties | Copy Path is listed as a future Inventory action. The host already exposes one native call, the folder picker (`interfaces/web/host.py`). | Separate proposal. |

### Why Inventory Is Not the Engine

Pointing the current Inventory at a drive would fail for four reasons:

1. **Population wall.** Inventory admits at most 150,000 rows per population
   ([DEFENSE](DEFENSE.md) capacity policy). The screenshot's `F:` holds about
   422,000 files in about 46,000 folders, more than three times that limit, so
   the scan refuses.
2. **Ledger side effect.** Inventory is durable evidence. A casual space check
   would register a location and write every row. Disk usage belongs outside
   the ledger (feature orthogonality). Untracked ingest sources set the
   precedent: they are scanned in memory, used, and forgotten
   ([FEATURES → Untracked Ingest Sources](FEATURES.md#ingest)).
3. **Ignored artifacts are exactly what eats target space.** The default
   `IgnoreSet` hides `.synctrash`, owned temporary files, `DESKTOP.INI` and
   `THUMBS.DB`. A space scan turns off the trash and temp exclusions (both are
   flags on `IgnoreSet`) and labels those entries as NamiSync-owned.
4. **Unreadable areas are normal at drive scope.** System Volume Information,
   other users' `$RECYCLE.BIN` and `WindowsApps` deny access. The host refuses
   elevated launch, so these areas stay unreadable. They become an explicit
   “unreadable” entry with unknown size, not a failed scan.

The space view therefore gets its own read-only workflow: a new entry point that
uses the scanner module and a pure projection, with no recorder or ledger. The
shared `visible_sequence.py`, sibling ordering and windowed table renderer are
reused. A folder-total sort and Contents column could later be added to
Inventory too, but that is a separate change to the DR-BR-15 sort contract.

### Page

The view has two panes:

- **Left:** the sunburst, centered on the focused folder. A breadcrumb above it
  re-roots the view. Clicking a segment focuses that folder.
- **Right:** a flat table of the focused folder's direct children. Folders are
  listed first by default, or mixed with files when sorted by size. Columns:
  Name, Contents, Size (with a “% of parent” bar), Modified. Double-clicking a
  folder focuses it, as Explorer does.

Hovering a segment highlights its table row, and the reverse. The table is the
accessible source of truth; the chart is a navigator.

### Size

Size is logical (end-of-file) size, the figure Explorer's Properties dialog
shows as “Size”. The Properties action gives the exact “Size on disk” when a
user needs it.

- **No per-file opens.** On Windows, `os.scandir` returns size, modification
  time and attributes from the directory listing itself; `DirEntry.stat()`
  needs no extra call for them. File identity and link count are not in the
  listing. On NTFS the sync scanner therefore calls `lstat` for every entry,
  which opens each one (`modules/scanner.py`, the `entry.stat` /
  `self._backend.lstat` fallback). A space walk needs no file identity, so it
  reads listing data only. Directories still get identity for loop defense:
  about 46,000 opens on `F:` instead of about 468,000. Skipping file opens also
  avoids the per-file cloud-recall question
  ([SCANNER → Cloud availability](SCANNER.md#cloud-availability-and-hydration-boundary)).
  Whether this is a scanner mode or a separate walk is an implementation
  choice. The sync scanner's behavior does not change.
- **Accepted consequences:**
  - Hard links are counted once per path, as in Explorer's “Size”.
  - Online-only cloud files show their full logical size. Their row already
    carries the cloud indicator.
- **Probe before implementation.** For rigor, measure logical size against
  allocated size, and check that directory-listing sizes match `lstat`, on
  these cases:
  - a file being written (NTFS updates directory-entry sizes lazily);
  - NTFS- and WOF-compressed files;
  - sparse files;
  - block-cloned (ReFS) or deduplicated files;
  - tiny files stored inside the MFT;
  - hard links;
  - online-only cloud placeholders.

  Record results in PERFORMANCE. A surprising divergence reopens this decision.
- **Volume summary.** For a volume root, the view shows used space from
  `GetDiskFreeSpaceExW` next to the scanned total. Used space minus the walked
  total is shown as one “Not scanned” entry (user decision, 2026-11-20): it
  covers what cannot be walked (`WindowsApps`, other users' recycle bins, page
  and hibernation files that deny access) and what NamiSync chooses not to
  walk. The two figures use different units (allocated versus logical), so the
  entry's details say it also includes the difference between file sizes and
  space on disk, and a negative remainder shows no size instead of a number.

### Scale

No Windows API returns a folder's recursive size. Explorer's Properties dialog
walks the tree itself, and reading the MFT directly needs elevation, which a
Store app would not have had. Spaceketeer almost certainly walked too. The walk
is unavoidable; what matters is what gets retained.

- **Retain directories only.** Keep a compact aggregate tree: one entry per
  directory with its parent, name, and subtree totals for files, folders and
  bytes. Also keep each directory's direct-file count and bytes. Memory then
  grows with the number of directories (about 46,000 on `F:`), not the number
  of files. The sunburst needs only this tree.
- **Read files when a folder is focused.** The flat table re-enumerates the
  focused directory's direct entries. Its folder rows come from the aggregate
  tree. If the fresh direct-file total differs from the scanned one, the header
  says “Changed since scan” and offers Rescan for that folder, instead of
  silently mixing two snapshots.
- **Bounds.** Directory count and direct entries per directory each need a
  wall, sized from measurement (directory-heavy shapes such as `node_modules`
  matter). The table still serves 1..256-row windows over a server-sorted
  directory. A single folder holding more than 150,000 entries is realistic
  (machine-learning datasets, one-file-per-message mail stores, log dumps), so
  the per-folder wall is not a refusal (user decision, 2026-11-19): past it,
  the listing keeps only the largest few thousand files, in memory bounded by
  that count, plus a summary row (“and 1,170,000 smaller files, 40 GB”). Size
  order stays correct; name order is unavailable past the wall, and the header
  says why.
- **System volume** (user decision, 2026-11-20). A volume-wide scan never reads
  the Windows folder (resolved with `GetWindowsDirectoryW`, not a fixed path);
  its space falls into the volume summary's “Not scanned”. Walking it would
  cost about as much as `AppData` on a typical installation; it is skipped for
  its low utility, since acting on its contents is generally a bad idea.
  Program Files is walked. Everything else is walked too, including large `AppData`
  trees, which many users will want sized: a long walk the user chose and can
  stop, within the display policies above.
- **Measurement first.** PERFORMANCE should record walk time and peak memory on
  a large real volume (the screenshot's `F:` is a good profile), comparing the
  listing-only walk with the sync scanner's per-entry `lstat`.

### Chart

Drawing a sunburst is cheap: hand-written SVG arc paths, with no third-party
chart library. That keeps the packaged-document and closed-asset rules intact.

- **Server layout, top children only.** Lay the chart out on the server from
  the focus folder, about 4 rings deep.
  - In each ring, draw only the largest *N* child folders (about 5) whose share
    passes a threshold (for example 2% of the focus folder).
  - Each parent's total comes from the aggregate tree, so everything not drawn
    is simply parent total minus drawn children. That remainder includes the
    parent's direct files and every small or unranked folder, and it appears as
    a neutral arc, much as Spaceketeer left it unfilled.

  No separate merge pass exists, and the payload size is fixed by
  *N* × depth.
- **Accessibility.** The chart is `aria-hidden` and supplementary. The table,
  breadcrumb and keyboard focus carry the same navigation. Forced colors use
  system colors with outlines.
- **Palette (open).** Spaceketeer gave each top-level branch its own hue. That
  conflicts with NamiSync's reserved semantic hues
  ([FEATURES → Semantic Color Channels](FEATURES.md#desktop-ui)). The proposed
  default is a single accent or neutral lightness ramp by depth, with the
  hovered or focused path emphasized. A categorical palette needs an explicit
  product-author decision.

### Session Behavior

- **Waiting for a volume.** A space scan, being a full walk, takes ordinary
  volume custody and queues behind any session that holds the volume. Listing
  one focused folder takes none (the Browse page's Snapshots and custody). While waiting, the view
  names the blocking task (with a link) and says: “Waiting for *task* to finish
  on F:. Pausing it lets this scan run now; it resumes after the scan.” This
  matches existing behavior: pausing releases custody, and a resumed session
  re-enters the back of its volumes' queue
  ([FEATURES → Resume Never Preempts](FEATURES.md#dispatcher)). The dispatcher
  stays domain-blind; the adapter maps the blocking session to its task.
- **Cancel and Rescan, no Pause.** A read-only scan has no continuation worth
  keeping.
- **Settled-only first.** The chart appears when the scan completes, matching
  inventory's no-partial publication; until then the progress bar's
  indeterminate animation shows the scan is running. A progressive chart is a
  later option.

### Shell Actions Detail

The cross-page Shell actions proposal above is consumed by this view. The
remaining work is mostly policy. The plumbing is modest.

- **Plumbing.** The folder picker is already a host-side callable injected into
  the web adapter. Each action follows the same pattern: a bridge command
  carries a server-owned node id, the server resolves it to a path, and a host
  callable acts. The browser never supplies path text. Primitives:
  - Copy Path: host clipboard.
  - Open in Explorer: `SHOpenFolderAndSelectItems`.
  - Properties: `SHObjectProperties` on a COM-initialized (STA) host thread.
  - Never `ShellExecute` “open” on a file: that would launch it.

  Each command needs BRIDGE ingress bounds and a DEFENSE note for the new
  external effect.
- **Plan side policy (proposed).** Plan rows can describe two paths. A silent
  default makes copies point at the source and everything else at the target,
  and that is the confusion to avoid. The proposal is to never choose
  implicitly:
  - The row menu shows explicitly labelled actions, “Source: Open in Explorer”
    and “Target: Open in Explorer”.
  - Each label is offered only when that side's path exists now. For example,
    a planned copy has no target file yet, so it gets “Target: Open folder” if
    the parent exists.
  - Move rows label the previous and new paths the same way.
  - Plan has no double-click shell default. One-sided views (Inventory, Disk
    usage, the Browse card's per-side tables) may use double-click, because
    the side is unambiguous.
- **Changed drive letters** (user decision, 2026-11-20). Open in Explorer and
  Properties first compare the drive's current volume identity with the scanned
  root's, one Windows call. On a mismatch they use the volume's current letter
  if it can be found, and otherwise say the drive is not connected. Otherwise,
  after a USB letter swap, they would open the same path on whichever drive now
  has that letter. This is a check, not Edit setup's full re-resolution. Copy
  Path keeps the cached text, which is harmless and works offline.
- **Missing items.** Missing items get no Open or Properties actions; “Open
  containing folder” appears when the parent exists. Copy Path stays available,
  because the text is harmless and useful for finding the file. This is a
  proposed refinement of the user's rule.
- **Mutation boundary.** Explorer and the Properties dialog let the user change
  files outside NamiSync. That is the user's own action, as with any Explorer
  use. NamiSync performs none itself and adds no delete, move or cleanup path.

### Non-Goals

- No delete, move, or cleanup from this view. Mutation inside a managed root
  stays pipeline-only (plan → preflight → execute).
- No ledger writes, recents, history runs or background or scheduled scans.
  Checksum adoption belongs to sync execution and to the Browse card with
  ledger recording on, not to this view.
- No elevation and no MFT or USN reading. The future
  [Change-Journal Scanning](FEATURES.md#scanner) protocol is the lawful route
  to faster rescans.
- No duplicate finder (content dedup belongs to ingest) and no network shares
  (remote roots are refused by admission).

### Open Questions

1. Sunburst palette: depth ramp (proposed) or a categorical palette.
2. Whether the Plan capacity link (“See what's using target space”, opening
   this view on the target with `.synctrash` highlighted) belongs in the first
   slice or later.
3. Ring count, *N* and the threshold. Tune these on real volumes.
4. Wall values, after measurement.

### Suggested Slices (Not Commitments)

1. Size-case probes and the walk measurement (listing-only versus per-entry
   `lstat`), recorded in PERFORMANCE.
2. Read-only space workflow, aggregate tree and view:
   - flat table and breadcrumb;
   - trash and temps visible and labelled;
   - unreadable and not-accounted-for entries;
   - visible wait-for-volume notice.
3. Sunburst navigator.
4. Shell actions on every page (separate proposal; can ship before slices 1–3).
5. Plan capacity link.
