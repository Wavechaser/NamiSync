# M2 Proposal

This is the single index of proposed later features, not an implementation plan.
[FEATURES](FEATURES.md) owns product behavior and accepted future boundaries;
[ARCHITECTURE](ARCHITECTURE.md#m2--durable-sessions-and-queue-ownership) owns M2
direction. Accepted future outcomes remain binding; unrealized representation
and implementation recipes are reconsidered at first use under [AGENTS](../AGENTS.md).
Listing an outcome does not activate implementation or change current M1 limits.

- **Execution retries.** Let users retry a whole run, an executor failure or a reviewed safe subset after an unsuccessful execution.
- **Verification retries.** Let users retry terminal verification or verify remaining files, including standalone verification.
- **Session cleanup.** Let users explicitly clean up NamiSync-owned session temporary files and trash.
- **Batched directory flushes.** Publish a group of small files, flush their parent directory once, then record the group, keeping durability before recording. The historical measured-volume saving was about 0.22 ms per 4 KiB file; it changes recording cadence and pause/cancel/resume settlement. [PERFORMANCE](PERFORMANCE.md) owns measurement evidence, not a universal saving.
- **Unbuffered source reads.** Compare with buffered sequential reads on controlled cold-source workloads; implement only if end-to-end throughput or cache-pressure benefits justify it. Preserve small-file behavior, source admission, exact tail/hash semantics and bounded buffers; reconcile source/target alignment and capability fallback. M1 keeps buffered reads: its repeated-source results and standalone probes do not establish an integrated cold-read gain. [PERFORMANCE](PERFORMANCE.md) owns those observations.
- **Specific I/O errors.** Explain filesystem failures with specific typed causes beyond the generic `IO_ERROR` classification.
- **Durable task recovery.** Preserve tasks and recoverable session state across application closure or restart.
- **Command-result retention independent of task lifetime.** Allow routine repeated inventory Refresh, acknowledge and restore without eventually requiring task closure to reclaim command capacity. M1 shares 48 retained start/visibility-response slots across the desktop; task-owned entries survive until Close, so a long-lived inventory task can exhaust capacity for other tasks too. Design bounded retirement of settled results while preserving unresolved original-outcome recovery and preventing retired commands from executing again. Coordinate adapter replay and application receipt ownership; increasing the cap alone does not resolve the lifetime issue. The M1 limit and clean refusal remain unchanged until this design is accepted.
- **Durable queue.** Retain queued work across application restarts.
- **Native Fluent overlay scrollbars.** Integrate WebView2's environment option through the Windows host when the backend work is justified. The current pywebview path needs coordinated startup, early navigation/HTML-loading and rendering-test changes; retain the CSS approximation for M1.
- **Verify-only batches.** Batch standalone verification directories. The current Setup runner admits source/target pairs; extending it to single-directory tasks belongs with a reviewed M2 Setup change.
- **User-defined sync pair presets.** Create, customize and persist reusable pairs that otherwise populate Setup and use availability checks like history-derived recent pairs. Persistent records and bridge commands are new work; presets do not retain admission or execution authority.
