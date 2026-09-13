# M2 Proposal

- **Execution retries.** Let users retry a whole run or a reviewed subset after an unsuccessful execution.
- **Verification retries.** Let users retry terminal verification or verify remaining files, including standalone verification.
- **Session cleanup.** Let users explicitly clean up NamiSync-owned session temporary files and trash.
- **Specific I/O errors.** Explain filesystem failures with more specific causes than the generic I/O message.
- **Durable task recovery.** Preserve tasks and recoverable session state across application closure or restart.
- **Durable queue.** Retain queued work across application restarts.
- **Native Fluent overlay scrollbars.** Integrate WebView2's environment option through the Windows host when the backend work is justified. The current pywebview path needs coordinated startup, early navigation/HTML-loading and rendering-test changes; retain the CSS approximation for M1.
- **Verify-only batches.** Batch standalone verification directories. The current Setup runner admits source/target pairs; extending it to single-directory tasks belongs with a reviewed M2 Setup change.
- **User-defined sync pair presets.** Create, customize and persist reusable pairs that otherwise populate Setup and use availability checks like history-derived recent pairs. Persistent records and bridge commands are new work; presets do not retain admission or execution authority.
