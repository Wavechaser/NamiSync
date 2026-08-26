# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Each entry records `SEVERITY - STATUS (YYYY-MM-DD)`, a reusable causal failure
class, the observed behavior and consequence, `Cause: why`, and, when fixed,
the corrective change. Write it as one compact paragraph rather than labels for
symptom, cause, and fix.

- **Severity:** SEVERE (plausible data loss/corruption, a security-boundary
  escape, an indefinite hang or crash, a core workflow unusable, or materially
  false durable truth after mutation) · MODERATE (a bounded feature failure or
  safe refusal, recoverable misleading state, or material performance/UX harm)
  · MINOR (diagnostic, test/evidence-quality, or small usability harm with no
  mutation, integrity, security, or availability consequence). Pure style is
  excluded.
- **Status** reflects the last direct verification of the entry.
- **Category** is a short noun phrase for a class that could name another bug
  with the same mechanism (for example, `TOCTOU parent redirection`, `shutdown
  ownership race`, or `schema type coercion`). Put the affected operation,
  pathname, and observed outcome in the description. Do not use a sentence,
  milestone, review gate, test outcome, fix, or broad result such as availability
  or convergence as the category.
- Assign severity from the worst consequence supported by the admitted product
  path, not the importance of the audit or test that found it. A safe refusal,
  test-only race, or hypothetical future caller does not inherit the severity
  of the production bug it was guarding against.

`DEFENSE.md` owns supported assumptions, tolerance classes, and residual-risk
dispositions. A residual sentence here records the remaining technical
boundary; it does not accept that boundary or close policy work by itself.

Entries are module/function-first, not a project-wide timeline: `##` headings
are owning modules or feature boundaries, and `###` headings are their
functional scope or delivery phase. Add an entry under the module/function that
owns the behavior, retain its relevant subheading, and keep entries newest first
within that section. Do not add date-based sections or append unrelated entries
to a global chronological list. Target 6–12 rendered lines per entry; include
only the test conditions or residual threat boundary needed to explain the
defect, and move implementation-level test choreography out of the log.

---

## DEVELOPMENT TOOLS

### Executor settlement authority

- MINOR - FIXED (2026-08-26). Derived oracle acceptance truth. The seven-row
  recording oracle reconstructed item attribution from frozen event-v4 detail
  and task issues from recorder calls, so producer-side `ExecutionSet` reason
  or issue drift could pass; deleting a catalog row also disabled that check,
  and the reducer matrix compared expectations only when reduction returned a
  value. Cause: compatibility evidence was reused as semantic authority and
  the catalog/matrix checks were incomplete. Fixed with an authoritative typed
  side channel stripped before normalized capture, an exact manifest-protected
  catalog, typed producer-drift regressions, and unconditional reducer result
  comparison. The protected trace, baseline, and semantic hash are unchanged.

### Workspace and measurement integrity

- MINOR - FIXED (2026-08-18). Cross-sample fixture drift. Verifier repetitions
  could aggregate different corpus memberships or stats, and priming or sidecar
  validation did not bind the following measured scan; a shorter corpus could
  therefore remain homogeneously `VERIFIED`. Cause: result coverage was checked
  only against each run's self-declared selection. Fixed by setup-to-sample or
  first-sample fixture binding, exact key/stat coverage, repeated baselining
  content-evidence comparison, visible setup timing, and whole-batch report
  refusal on drift.
- SEVERE - FIXED (2026-08-18). Implicit artifact replacement authority.
  Baseline seeding could silently replace an unrelated ordinary file at the
  inferred sibling name, while report files appended partial or semantically
  mixed invocations forever and could be confused with retained baseline
  evidence. Cause: path-shape validation was treated as write authority and no
  invocation owned publication as a transaction. Fixed by explicit sidecar
  paths, create-exclusive report/sidecar publication, separately named replace
  authority with pre-work destination binding and immediate identity/reparse
  revalidation, one versioned atomic batch report, and no guessed cleanup or
  retention policy.
- SEVERE - FIXED (2026-08-18). Coarse descendant deletion authority. A valid
  marker on an old rig directory allowed reset, executor teardown, generation,
  or `clean` to recursively erase unrelated files later placed anywhere below
  that root. Cause: root path/device/inode ownership was treated as provenance
  for every current descendant. Fixed with a root-bound exact-output manifest,
  full-set validation before mutation, per-file identity/stat and hard-link
  checks, directory identity checks, generic reparse/alias refusal, exact
  printed-plan application, individual unlink/rmdir cleanup, failure retention,
  and truthful pre/post/partial deletion receipts. Marker-only or unknown
  content now requires an inspected explicit `clean --force-all`.
- SEVERE - FIXED (2026-08-06). Unbound destructive workspace authority. Corpus
  generation could overwrite matching files in any existing directory and
  retain stale files, while executor teardown trusted only the existence of a
  fixed sibling marker. Cause: neither path was bound to a directory instance
  or exclusive run, and generator reuse had no owned reset boundary. Fixed with
  schema-checked path/device/inode markers, nonblocking exclusive leases,
  signed lease artifacts, live-claim-only mutators, deterministic owned
  regeneration, and refusal of nonempty unowned roots, replacement/reparse
  aliases, overlap, and partial template walks.
- MODERATE - FIXED (2026-08-06). Measurement artifact self-contamination.
  Sidecar or JSON paths could overwrite corpus content, alter later repeats,
  collide with ownership state, or disappear with target teardown. Cause: the
  CLI documented external artifact placement without enforcing resolved
  containment and file-identity alias rules. Fixed by validating every used
  artifact before claiming or writing, refusing existing multi-link outputs,
  reserving ownership paths and explicit report/sidecar collisions, and testing
  corpus-file preservation, repeat bounds, template overlap, and path aliases.
- MINOR - FIXED (2026-08-06). Invalid-sample acceptance. Partial
  scans and priming, failed execution, mixed verifier outcomes, degraded
  recording, and readback mismatches could still report throughput and exit 0;
  empty correspondence also made the documented operation mix overbroad. Fixed
  with complete scan/evidence/result/progress validation, explicit accepted
  outcome matrices, visible readback settlement, diagnostics opt-out that
  removes its timing tap, and first-run/no-history correspondence disclosure.

## EXECUTOR

### M1 Hardening

- MODERATE - FIXED (2026-08-26). Cancellation settlement ownership gap.
  A reliable collaborator raising `Canceled` after outcome retention could
  replace cancellation with an invariant error despite publication and a
  committed receipt. Interrupted directory finalization also discarded its
  untouched queue tail, misclassifying already-created directories. Fixed by
  replaying retained outcomes unchanged and returning only the unprocessed
  directory tail to its finalizer on cancellation; ready directories remain
  under that owner's settlement. Recording and metadata are not repeated, and
  persistent sink refusal never fabricates acceptance. The production EventHub
  does not raise this control exception; the boundary is latent.
- MODERATE - FIXED (2026-08-26). Diagnostic-coupled recording attribution.
  Executor and workflow recording boundaries rendered exception text before
  establishing the typed cause. A failing `__str__` or logical filename access
  could erase or misclassify recording failure, replace the primary error, or
  turn filesystem success into failure. Fixed by establishing typed causes
  before guarded optional rendering and retaining `detail=None` on renderer
  failure. Result messages and secondary notes have a fixed safe fallback;
  ordinary rendered details retain existing bounds and first-observation rules.
- MODERATE - FIXED (2026-08-26). Exception-bound recording attribution.
  A safely refused UPDATE could report recording clean when owned-temp cleanup
  replaced its flush error or a retained-backup retry settled through the
  durable-effect reducer. Cause: prerequisite attribution lived on dynamic
  exception fields, while filesystem settlement could select another error.
  Fixed by retaining the typed cause in the operation journal and composing it
  before reliable settlement; reducer-proven unrecorded mutation takes
  precedence without changing filesystem truth. A successful retry barrier
  clears the cause, and a newly refused barrier replaces its diagnostic.
  Accepted-journal validation is guarded once: inconsistency preserves the
  original external error and retained evidence rather than retiring it.
- SEVERE - FIXED (2026-08-26). Reliable-sink settlement receipt loss. A
  successful recorder transaction lived only in a transient settlement while
  its item outcome was offered, so sink rejection sent the exception backstop
  through filesystem re-observation without the committed receipt. An accepted
  retry could then contradict durable success as failed and unrecorded. Fixed
  by retaining the complete typed settlement in the operation journal before
  emission and replaying that exact value once. Only accepted delivery advances
  continuation state or retires the journal; persistent rejection remains
  pending and terminalizes from accepted items under the original sink error.
- MODERATE - FIXED (2026-08-22). Deferred-settlement activity conflation. A
  successful directory create remained the active Progress item until later
  descendant and metadata finalization, so the next operation replaced its
  identity without an intervening reliable outcome. The browser reducer treated
  that valid handoff as a protocol violation; repeated whole-batch refusal could
  freeze observation and eventually stop the browser task drain. Fixed by
  deactivating the directory spotlight when create work returns, allowing a
  newer lossy snapshot to repoint activity without implying settlement, and
  exercising the real executor/event-view stream through the packaged reducer.
- MODERATE - FIXED (2026-08-21). Continuation progress-state loss. Pausing
  after a partial copy retained operation status and mutation evidence but not
  the aggregate byte high-water, so a resumed task could rebuild its reporter
  below the value already shown and regress the aggregate bar; throttling could
  also leave the paused attempt counters stale. Cause: `ExecutionSet` had no
  aggregate telemetry continuation or forced pause boundary. Fixed with an
  exact reviewed-content-bounded high-water, strict workflow payload v5, and an
  authoritative live pause emission that coherently refreshes aggregate items,
  bytes, path, and nominal item/attempt state. Resume stalls at retained
  high-water until new work catches up.
- MODERATE - FIXED (2026-08-21). Throttled terminal-progress settlement.
  Cancellation or an escaping executor failure could reliably settle every
  operation yet leave the session's last lossy `Progress` snapshot naming a
  partially complete in-flight item, so terminal presentation retained a
  phantom active row. Cause: those unwinds relied on interval-throttled item
  settlement and lacked the forced final boundary used by normal completion.
  Fixed with a forced authoritative-live unwind emission after reliable
  settlement: aggregate items and byte high-water remain current, while nominal
  item fields and `current_path` clear. An emitter failure remains secondary to
  the original executor exception.
- SEVERE - FIXED (2026-08-11). Exception-safety settlement gap. A
  failure policy or retry sleep could raise after MOVE or another mutation had
  committed, and a later checkpoint could raise with a completed MKDIR still
  pending; the exception escaped with filesystem effects present but no item
  outcome, execution status, or degraded recording truth. Cause: these calls
  preceded durable reduction, while the outer generic unwind only cleaned the
  current temp. Fixed with local original-error settlement and a generic
  exception backstop that finalizes pending directories and retires every
  active effect before propagation. Process-fatal `BaseException` retains its
  cleanup-only contract.
- MINOR - FIXED (2026-08-11). Authority-source mismatch. Executor root
  guards derived and admitted the reviewed plan root but ignored the root
  argument that the following resolver used. Existing callers supplied the
  same path, but an extension or future call-site error could validate one root
  and touch another. Fixed by requiring lexical equality with the derived
  source or target authority before any probe or resolution.
- MODERATE - FIXED (2026-08-10). Retry-cleanup error suppression. A retryable copy
  failure before continuation installation attempted owned-temp cleanup but
  discarded its error and cleared process-local ownership. Cancellation at the
  next retry checkpoint then reported a plain canceled item while the current
  run's temp remained without diagnostics. Fixed by requiring cleanup to
  succeed before retry sleep or control checkpoints and settling a failed
  cleanup immediately as `cleanup-failed`; exact-name rerun recovery remains.
- MODERATE - FIXED (2026-08-10). Multi-effect settlement omission. UPDATE
  could retain its reviewed backup in owned trash, fail replacement and
  readonly restoration, then discard all backup evidence from ordinary or
  cancellation settlement while reporting only the metadata mutation. Cause:
  a not-published byte verdict was treated as no byte channel even when its
  backup was durable. Fixed by retaining backup detail as the primary byte
  state and composing readonly truth under `mutation_durable_state`; confirmed
  publication still suppresses the subordinate marker.
- MODERATE - FIXED (2026-08-10). Non-atomic settlement re-observation. An
  ordinary operation failure with retained byte or mutation state was probed
  before owned-temp cleanup, then probed again if cleanup failed. A one-shot
  unavailable probe or cleanup's own filesystem effect could therefore erase
  the first truthful durable verdict and replace the underlying reason with
  `cleanup-failed`. Fixed by taking one pre-cleanup settlement snapshot and
  adding cleanup diagnostics without another probe; failures with no retained
  effect keep the existing cleanup-owned reason.
- MODERATE - FIXED (2026-08-10). Sibling-effect settlement short-circuit. UPDATE could
  clear readonly, fail replacement and restoration, then lose its publication
  state probe; the resulting publication-unverified settlement short-circuited
  the retained mutation marker. Recording was already degraded, but item detail
  omitted the changed metadata needed for accurate recovery. Fixed by making
  only confirmed publication authoritative and composing unverified byte
  diagnostics with marker truth under `mutation_durable_state`. A regression
  covers failed restoration plus an unavailable ordinary publication probe.
- MODERATE - FIXED (2026-08-10). TOCTOU backup-evidence mismatch. On a target without
  hardlink support, UPDATE copied the reviewed live file and then sampled its
  path for backup metadata; a concurrent grow, truncation, or rewrite could
  leave mixed recovery bytes decorated with a later stat. The final live guard
  prevented ordinary drift from being overwritten, but the retained backup was
  not trustworthy. Fixed by binding the reviewed target snapshot to pre/post
  stats from one open read handle, requiring the exact copied byte count, and
  publishing neither backup nor update on detectable drift. Same-size mutation
  with restored metadata remains inside the documented inference boundary.
- SEVERE - FIXED (2026-08-09). Cancellation settlement short-circuit. UPDATE
  could clear readonly, fail replacement and restoration into retry, then
  cancel while publication probing failed; the failed byte settlement returned
  before the retained mutation marker was inspected, leaving changed metadata
  with `recording=OK`. Fixed by settling both retained channels unless
  publication is confirmed, preserving publication diagnostics while changed
  or unverified marker truth owns `canceled-after-mutation` and recording
  degradation. Exact restored pre-state remains recording-OK; regressions cover
  restored, changed, and committed-publication precedence without success
  evidence.
- SEVERE - FIXED (2026-08-09). TOCTOU parent redirection. TRASH,
  MOVE_UPDATE, and UPDATE validated `.synctrash/<run>` before a recorder or
  copy barrier but checked only the destination leaf afterward; a same-volume
  junction swap could relocate a reviewed file or backup outside owned trash
  while retaining a false lexical trash path. Fixed with an exact
  run-destination contract, full parent revalidation after recorder and copy
  preparation, and guards before path-based finalize, publish, cleanup, and
  recovery probes.
  Real junction regressions cover all three operation families. The final
  validation-to-syscall external-writer micro-window remains path-based.
- SEVERE - FIXED (2026-08-09). Non-byte effect settlement omission. MOVE, RECASE,
  TRASH, DELETE, and MKDIR could commit and then raise while the failed item
  still reported `recording=OK`; failed readonly restoration could likewise
  leave UPDATE or DELETE metadata changed without ledger-behind status. Cause:
  failure settlement inspected only byte-copy continuations. Fixed with
  process-local pre-mutation markers, synchronous commit facts, and failure-only
  state probes retained across retry/pause/cancel and deferred mkdir metadata.
  Exact unchanged pre-state stays recording-OK; ambiguous, unreadable, and
  case-only RECASE state degrades conservatively without success evidence.
- SEVERE - FIXED (2026-08-09). TOCTOU prepared-artifact substitution. UPDATE
  validated its prepared temp before a recorder flush, allowing a same-size,
  same-mtime replacement during that wait to publish foreign bytes under the
  original digest. Fixed by moving the existing flush before final
  backup/temp/source/live validation and binding the cached post-publish
  kind/size plus available stable identity to the prepared temp for COPY,
  UPDATE, and MOVE_UPDATE before attestation, with no added steady-state
  filesystem call. Identity-weak substitution and same-object byte mutation
  still require handle-bound publication or a byte reread and remain outside
  the external-writer contract.
- SEVERE - FIXED (2026-08-08). TOCTOU guard-to-rename race. MOVE, RECASE,
  MOVE_UPDATE old-path cleanup, and TRASH performed their recorder flush after
  a path guard and before the non-replacing rename. An external writer could
  replace the guarded source during that wait, causing NamiSync to relocate an
  unreviewed occupant and, for MOVE_UPDATE/TRASH, settlement could falsely report
  success. Cause: these operation-specific barriers retained the ordering
  removed from UPDATE/DELETE. Fixed by moving each wait before the final
  source/destination guards, re-reading MOVE_UPDATE state after the wait, and
  gating same-size/same-mtime foreign replacements across all four operations.
  The smaller path-guard-to-rename external-writer boundary remains non-atomic.
- SEVERE - FIXED (2026-08-08). Post-publication settlement omission. COPY,
  UPDATE, or MOVE_UPDATE could publish its new target and then fail metadata
  repair or another completion step while reporting `recording=OK`, leaving a
  real filesystem mutation without matching ledger evidence. Cause: ordinary
  retry exhaustion ignored the continuation's confirmed publish state, unlike
  cancellation settlement. Fixed by probing durable state before temp cleanup,
  including a publish primitive that commits and then raises, retaining
  target/backup/old-path drift detail, settling the item failed, and degrading
  recording without inventing success-only published evidence. An unsuccessful
  state probe degrades as publication-unverified rather than claiming OK.
- SEVERE - FIXED (2026-08-08). TOCTOU guard-to-mutation race. UPDATE and DELETE
  performed their recorder durability flush after the final target guard, so a
  foreign replacement during that potentially long wait could be overwritten
  or removed without another check. Cause: durability ordering placed blocking
  recorder work inside the guard-to-mutation interval. Fixed by flushing before
  the final live guard. The remaining path-based `stat`/readonly/syscall gap is
  still non-atomic and remains the documented external-writer boundary.
- MINOR - FIXED (2026-08-06). Test-observation race. The one-core
  `test_b2_hash_fifo_independently_plateaus_at_32_items` intermittently failed
  although both FIFOs remained capped at 32 items. Cause: separately sampled
  full queues can momentarily straddle a worker's get/put, letting the first
  sample precede reader quiescence. Fixed by freezing three stable full samples
  before signaling and proving no reader advance after two blocked-enqueue
  checkpoints. Delay stress and an injected hidden read validate the gate;
  production queue-cap behavior passed throughout.
- SEVERE - FIXED (2026-08-04). TOCTOU backup-baseline replacement. An external
  replacement of the live UPDATE
  target while NamiSync created its backup could become the continuation's new
  baseline and then be overwritten, even though the owned trash entry preserved
  only the reviewed older version. Cause: executor refreshed `live_stat` after
  backup creation instead of retaining the pre-backup point-of-touch evidence.
  Fixed by keeping that original stat across retry, accounting only for the
  owned hardlink's expected link-count increment, and guarding it again before
  copied-backup repair and target replacement. An external swap after the final
  guard but before the path-based replace remains the documented non-atomic
  threat boundary.
- MODERATE - FIXED (2026-08-04). Backup provenance confusion. UPDATE
  cancellation called any file present at
  its planned backup path `retained`, even if another process replaced the owned
  backup during retry, and exposed a machine-specific absolute path in durable
  result detail. Cause: cancellation kept only the path and tested existence.
  Fixed with explicit backup creation/repaired-version evidence shared by
  hardlink and copy backups, current-version classification as `retained`,
  `changed`, `absent`, or `unverified`, and target-root-relative detail paths.
  Before repaired evidence is cached, stable identity binds the backup when the
  target profile supplies it; an identity-weak same-kind/same-size replacement
  remains outside the evidence available to this minimal guard.
- MODERATE - FIXED (2026-08-04). Retry-stage omission. A copied UPDATE
  backup whose atomic publish
  succeeded but post-publish metadata repair hit a sharing violation could
  resume past that repair and leave the recovery copy with publication-damaged
  metadata. Cause: copy-backup metadata completion lived inside the copy helper,
  while retry state represented only backup presence and the outer continuation
  repaired hardlinks alone. Fixed with one explicit backup completion stage for
  both backup methods, separate creation and repaired stats, retry validation,
  and a regression that fails the first copied-backup repair then verifies the
  second attempt restores the displaced target metadata before replacing the
  live target. Hardlink repair remains after replacement because its backup
  still shares the displaced live inode until then.
- MODERATE - FIXED (2026-08-04). Retry-state revalidation gap. A sharing retry
  could record COPY, UPDATE, or MOVE_UPDATE success for a same-size/same-mtime
  target replaced during backoff. Cause: resumed continuations reused prepared
  or cached stats before metadata, durability, attestation, and recording.
  Fixed with one entry guard that re-stats the target, compares cached evidence
  when available, otherwise binds kind/size and stable identity, and settles
  detectable replacement or absence as `target-drift` without success evidence.
  First-pass execution adds no stat; replacement after the guard, or before a
  cache on an identity-weak volume, remains outside this non-locking guarantee.
- SEVERE - FIXED (2026-08-03). Publication provenance misattribution. Cancel
  after a failed UPDATE replace could claim
  `canceled-after-publish` for a foreign write made by the process that held the
  target lock during backoff; COPY had the same false-credit shape if a foreign
  destination appeared. Cause: cancellation required the target still match
  reviewed/prepared evidence before accepting an intact owned temp as proof of
  non-publication, then treated every classification failure as publication.
  Fixed by making an intact matching temp decisive negative evidence regardless
  of target drift, recording the unexpected target state in item detail,
  preferring the continuation's synchronous/cached publish evidence, and
  keeping genuinely unverified state failed under its drift/I/O reason without
  degrading recording or claiming publication.
- SEVERE - FIXED (2026-08-03). Cancellation post-commit settlement gap.
  Cancellation after a published byte operation
  could label COPY or UPDATE `CANCELED` even though the new target was already
  live, omit the mutation from item detail, and leave recording falsely `OK`.
  Cause: the blanket cancel unwind never consulted operation-local retry state;
  fixed by classifying prepared versus published state before temp cleanup,
  settling a published-but-unfinished operation `FAILED` with the typed
  `canceled-after-publish` reason and explicit durable-state detail, degrading
  recording, and never attaching success-only `PublishedCopyEvidence`.
- SEVERE - FIXED (2026-08-03). Composite cancellation settlement gap. Cancellation
  during MOVE_UPDATE's durable retry
  could report `CANCELED` after the new target published, whether the old target
  was still live or had already reached trash. Cause: cancel settlement ignored
  the composite continuation; fixed by reporting the observed `new-and-old` or
  `new-and-trash` state, settling the unfinished operation `FAILED` with
  `canceled-after-publish`, degrading recording, and leaving the next reviewed
  scan/plan to converge without rollback.
- MODERATE - FIXED (2026-08-03). Cancellation recovery-evidence omission. Cancellation
  after UPDATE created its durable
  backup but before replacement hid that retained old version from the canceled
  item's detail. Cause: cleanup considered only the staged temp and the blanket
  outcome carried no continuation facts; fixed by retaining the backup, removing
  only the owned temp, and reporting its path, backup method, and retained state.
  M1 still has no trash purge: reclamation remains with the deferred
  maintenance-session retention workflow, and cancellation never deletes the
  only recoverable old version.
- SEVERE - FIXED (2026-08-03). Pause/resume continuation loss. Pausing UPDATE after a
  backup, MOVE_UPDATE after publication, or COPY during metadata retry made
  resume reapply scan-time guards and reject NamiSync's own durable state.
  Cause: checkpoints unwound process-local retry state. Fixed by installing
  validated COPY/UPDATE/MOVE_UPDATE continuations at the first owned durable
  boundary, latching pause through settlement, and reusing staged bytes before
  raising `PauseRequested`. Cancellation remains immediate; policy `Stop`
  suppresses a latched pause and settles later operations as `policy-stop`.
- MODERATE - FIXED (2026-07-30). Rename-attestation policy mismatch. Pure-move
  recording within timestamp granularity. A valid MOVE could rename the
  reviewed target and then degrade recording when its timestamp differed
  exactly from the source while still
  falling within the target volume's equality granularity. Cause: the recorder
  compared a pure rename result to source-derived intended metadata before
  checking the reviewed old-target version; fixed by making
  `prior_target_expected` the complete pure MOVE/RECASE attestation while
  retaining intended-content validation for MOVE_UPDATE.
- SEVERE - FIXED (2026-07-30). Point-of-touch revalidation omission. Pure rename and
  directory source revalidation.
  MOVE could rename a reviewed old target after the corresponding source
  subject vanished, MKDIR could create a target for a vanished source
  directory, and MOVE/RECASE recording could bless a substituted post-rename
  target with matching size/mtime. Cause: those handlers skipped the universal
  source point-of-touch guard and accepted intended metadata without binding the
  rename result to the reviewed old target identity; fixed with source guards,
  post-rename version checks, and the same defensive recorder check.
- MODERATE - FIXED (2026-07-25). Managed-metadata policy drift. Post-publish
  metadata repair on volumes with
  last-access updates enabled, observing a renamed file could change its access
  time and force the otherwise conditional second metadata rewrite and flush on
  every copy. Cause: executor normalized and compared access time as managed
  metadata; fixed by removing access time from executor policy while retaining
  mtime, creation-time, and standard-attribute repair.

### M0 hardening

- MODERATE - FIXED (2026-07-20). Orphaned-artifact lifecycle gap. Temps left
  by killed or crashed runs accumulated permanently while preflight counted
  their bytes as reclaimable, leaking target capacity and potentially stranding
  a nearly-full sync. Cause: executor removed only the current run's exact
  per-operation temp, while every rerun has a new run id and scanner correctly
  ignores owned temps; fixed with one post-preflight, pre-copy exact-grammar
  sweep over preflight's touched target parents, excluding current-run files and
  `.synctrash`.
- MODERATE - FIXED (2026-07-20). Self-induced drift misclassification. Cleanup of a
  directory emptied by same-run moves or trash operations was rejected as target
  drift, preventing folder rename/removal in one run. Cause: the final guard
  compared scan-time mtime and link count that planned child removal changes;
  fixed with a cleanup matcher that validates stable metadata and treats absent
  reviewed identity as absent evidence before atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Native access-right mismatch. Every Windows
  parent-directory flush failed and warned despite successful mutations. Cause:
  `CreateFileW` requested `GENERIC_READ`, while `FlushFileBuffers` requires
  write access; fixed by requesting `GENERIC_WRITE` on the existing directory
  handle.
- MODERATE - FIXED (2026-07-19). Retry-stage replay. A transient sharing
  violation after update backup or publish restarted against the operation's own
  mutation, causing false target drift or destination occupancy. Cause: generic
  retry assumed every operation could restart; fixed by validated continuation
  from the last durable sub-step.

## DISPATCHER AND HISTORY

### M1 Hardening

- MODERATE - FIXED (2026-08-27). Worker retirement ownership gap. Terminal
  publication and retirement handoff could expose a session as closable while
  its exact worker, invocation frame, or exception hook was still live. Cause:
  `_worker_done` removed the attempt before the thread exited. Fixed by keeping
  the current-generation fence and thread registration through actual death,
  reaping only started marked attempts, and making close join the exact worker
  outside dispatcher locks under its existing bounded deadline. Timeout and
  self-close leave all cleanup ownership retryable; failing-first regressions
  cover ordinary exit, exception-hook exit, successor fencing, and shutdown.
- MODERATE - FIXED (2026-08-27). Audit factory exception retention. A failed
  observer factory kept its original exception, traceback, and any attached
  private graph in the degraded observer for the session lifetime. Cause: the
  sentinel stored the caught exception only to chain later fixed failures.
  Fixed by discarding it at the boundary and raising fresh fixed errors from no
  cause, while preserving degraded audit and failed-prefix behavior. A weak-
  reference regression proves the factory graph retires during the live run.
- MODERATE - FIXED (2026-08-27). Exception graph retention. Contained
  store-write and custody-release failures could retain earlier session,
  continuation, or result graphs after close, accumulating across sessions.
  Cause: two dispatcher-lifetime lists kept original exceptions and their
  traceback, cause, context, and custom attributes without any consumer.
  Fixed by retaining only separate sticky failure flags, preserving the
  existing store fallback, resource-release ordering, and terminal truth.
  Failing-first weak-reference regressions cover both dependency boundaries
  through real admission, session close, and shutdown. This does not claim
  whole-process erasure or close the complete task-retention gate.
- MODERATE - FIXED (2026-08-26). Live/store record aliasing. A store accepting
  admission but rejecting later updates retained the original continuation,
  including execution attestations, after successful terminal live scrubbing.
  Cause: the persistence boundary accepted the same payload-bearing type as
  the live session table. Fixed by explicitly projecting every store write to
  a separate frozen metadata/result type with no continuation field or live-
  record reference, and rejecting live records in the in-memory store. Current-
  process pause/resume and full terminal result axes remain intact. Terminal
  live scrubbing stays required; this does not erase other live references or
  turn metadata persistence into restart recovery.
- MINOR - FIXED (2026-08-19). Audit-barrier observation race. The paused-
  verification integration regression could read retained history before its
  `PAUSED` event reached the durable-audit attempt, intermittently producing a
  missing-run failure although dispatcher and history behavior were correct.
  Cause: the test synchronized on direct session state, which intentionally may
  lead live event and audit publication, then treated that observation as an
  audit-read barrier. Fixed by subscribing after submit and waiting for live
  `StateChanged(PAUSED)` before reading history; production ordering is
  unchanged.
- MODERATE - FIXED (2026-08-08). Observer failure-domain poisoning. One
  oversized valid event or exact repeated item could make the observer reject
  its whole window, permanently discard every later event, and omit terminal
  history. Cause: all admission/storage exceptions shared one poison flag and
  item identity had only a table-wide uniqueness failure. Fixed at reset-only
  history v5 with authenticated recorded/duplicate/rejected receipts,
  non-counting semantic duplicates, bounded hash-only oversize rejection,
  explicit degraded-but-accepting pump state, and bounded BUSY/LOCKED replay
  reads. Receipt metadata/order, immutable item projections, rolling summary
  state, and terminal truth are hash-bound; oversized items keep bounded
  identity/semantic hashes so changed reuse remains fail-stop. Strict
  `WITHOUT ROWID` receipt storage, append/finality guards, and physical-tail
  checks prevent replacement, reopening, or unauthenticated summary rows.
- SEVERE - FIXED (2026-08-08). Worker-generation ABA race. Canceling a session
  after scheduler dequeue but before RUNNING could launch a second worker; the
  losing worker could then settle twice or release the successor's reservation
  and lease. Resume had the same identity-free cleanup boundary. Cause: workers,
  reservations, and leases were keyed only by session id. Fixed with one
  process-local generation owner per session, generation-keyed custody, strict
  stale-callback rejection, serialized retirement handoff, and shutdown that
  reports terminal-but-not-retired attempts as unfinished.
- MODERATE - FIXED (2026-08-06). Sparse-sequence pagination assumption. Event-page
  repair rejected two valid recovery
  states: a live subscriber cursor ahead of the last committed history window,
  and a caller-supplied inclusive watermark that landed on an omitted lossy
  `Progress` sequence. The first stopped catch-up before durability could
  advance; the second mislabeled a sparse reliable-event interval as history
  corruption. Cause: one dense-page helper treated the watermark as a required
  row and the initial validator required every cursor to be at or below current
  durability. Fixed with the specified empty terminal page for fresh live-ahead
  traversal, sparse fixed bounds, indexed verification of the official durable
  maximum on every request, and a raw `limit + 1` lookahead that decodes only
  the requested rows.
- MODERATE - FIXED (2026-08-06). Close-state conflation. A terminal close
  that timed out before it
  acquired the hub publication gate left the session in `_closing`, so attach
  reported a nonexistent session even though its replay and subscriptions were
  still intact. The same state was truthful after subscriptions had already
  been detached, but the boolean hub result could not distinguish those stages.
  Fixed with explicit complete/publication-timeout/audit-cleanup-pending
  outcomes: ordinary close releases only a reversible pre-gate claim, shutdown
  keeps its global claim, irreversible cleanup and store-drop failures retain
  ownership for retry, and attach reports typed `SessionCleanupPending` rather
  than `SessionNotFound`.
- MODERATE - FIXED (2026-08-05). Gap-reservation capacity off-by-one.
  Subscribing to a hub whose retained replay was
  longer than one subscriber's bound produced a stream holding
  `subscriber_capacity + 1` envelopes, so the next reliable event ejected a
  consumer that had not been given a chance to drain. Cause: the truncation
  branch reserved a slot for the leading `Gap` only when a gap was already
  needed before truncating, not when truncation itself created it. Production
  sizing (128-event replay, 64-event subscriber bound) reaches this on any
  session that has emitted more events than the subscriber bound. Fixed by
  recomputing the allowance once truncation forces the gap; a regression pins
  the initial buffer at the bound.
- MODERATE - FIXED (2026-08-05). Broken-worker queue retention. A broken audit
  prefix stopped the pump without
  draining its bounded command queue. Each degraded terminal hub could therefore
  retain a full queue of large reliable envelopes; a timed-out flush that later
  succeeded could instead leave the degraded pump alive and idle forever. Fixed
  with an atomic queue-admission/close gate, pre-cleanup command draining with
  waiter completion and balanced task accounting, and a post-flush broken-prefix
  check plus a best-effort stop wakeup for the timeout-boundary race.
  Full-capacity blocking-cleanup, idle-wakeup, and late-flush regressions cover
  these exits.
- MODERATE - FIXED (2026-08-05). Premature cleanup-ownership release. Explicit close
  could discard the terminal
  session record, store row, hub owner, and cleanup lock before audit-observer
  cleanup finished, then ignore the hub timeout; shutdown could consequently
  report complete while the only cleanup worker was still blocked. A concurrent
  close could also remove a hub between shutdown's record and hub snapshots.
  Fixed by serializing close/shutdown per session, closing the hub before
  ownership removal, retaining timed-out cleanup for retry, and snapshotting
  hub/lock pairs under the dispatcher condition.
- MODERATE - FIXED (2026-08-05). Split shutdown-deadline budgeting. Shutdown's shared
  deadline stopped at the
  session publication gate: cancellation could persist `CANCELING` and then
  wait the full audit-offer timeout for a hub lock held by another reliable
  event, while hub cleanup itself waited without a bound for that same lock.
  Closed hubs also retained their replay tail. Fixed by reserving the hub
  within the remaining shutdown deadline before changing lifecycle state,
  using a nonblocking audit offer for the paired cancellation event, spending
  one close deadline across hub-lock and observer cleanup, and clearing replay
  with subscribers under the hub lock. Blocked-offer, lock-deadline, and
  replay-cleanup regressions cover the boundary.
- MODERATE - FIXED (2026-08-05). Concurrent commit-time regression. Concurrent
  history observers could advance the
  committed sequence while regressing `last_committed_at`. Cause: commit time
  was sampled before serialized writer ownership, and wall-clock rollback was
  accepted verbatim; the first commit could also precede its RUNNING event.
  Fixed by sampling inside the owned transaction and clamping the logical commit
  timestamp to prior durability, admission, and actual start; tail finalization
  uses that same effective time.
- MODERATE - FIXED (2026-08-05). Nullable lifecycle-timestamp conflation.
  Finalized queued cancellations fabricated an
  execution start at admission time even though their disposition was `UNRUN`.
  Cause: finalization replaced a missing observed start with `created_at`, and
  the v4 terminal constraint required every final row to have `started_at`.
  Fixed by retaining the nullable actual-start field, checking an unstarted
  terminal end against `created_at`, and returning an exact reopened terminal
  replay before validating any newly sampled end time. Queued cancellation and
  regressed-clock replay are both covered.
- MODERATE - FIXED (2026-08-05). Unbounded-cardinality aggregation. Fixed-query
  history summaries could still
  allocate one Python aggregate object for every distinct free-form item kind
  and reason, so a valid run could defeat the readback memory bound without
  decoding event JSON. Cause: the third summary query grouped all projection
  strings. Fixed with one conditional aggregate fact object per selected run;
  workflows supply finite selection/no-op predicates and retain classification
  policy while SQL returns only bounded primitive counts.
- SEVERE - FIXED (2026-08-05). Unbounded preterminal buffering. History claimed
  a bounded crash window while
  retaining every reliable-event hash and result item until terminal
  finalization. A long run or paused process therefore had unbounded history
  memory and could lose its entire audit on a crash, leaving no durable prefix
  for UI recovery. Cause: the bounded dispatcher queue limited delivery
  pressure, not observer retention or transaction scope. Fixed by history v4's
  append-only reliable-event journal, 256-event/1-MiB/one-second windows,
  pause/close/finalization flushes, rolling hashes/counts and watermarks, and
  explicit `incomplete` restart views. Oversized events and failed windows
  degrade audit without changing domain or ledger truth.
- MODERATE - FIXED (2026-08-05). Post-materialization read bound. History readback was
  bounded only after
  materialization. `list_recent()` invoked the full-run getter once per run,
  and that getter selected and decoded every item, making a 50-run summary an
  N+1 query path with work and memory proportional to all selected detail.
  Fixed with fixed-query-count primitive summaries, shared live/retained fact
  classification, 1..256-row keyset item/event pages under captured durable
  watermarks, and streamed CLI detail. The unbounded full-run API was removed.
- MODERATE - FIXED (2026-08-04). Split close-deadline budgeting. Audit-pump close
  could spend the complete
  caller timeout waiting to enqueue its stop command and then spend the complete
  timeout again joining the worker, so the advertised shutdown allowance was
  not an end-to-end bound. Cause: queue and thread APIs each received the
  original duration. Fixed with one monotonic close deadline and recomputed
  remaining time for enqueue and join.
- MODERATE - FIXED (2026-08-04). Quadratic sequence tracking. History event
  admission recalculated `max(event_hashes)` for every new reliable envelope,
  making a large result stream quadratic before finalization and increasing
  audit-backpressure risk.
  Cause: the duplicate hash map was also used as an ordered-sequence index.
  Fixed by retaining one highest-accepted-sequence scalar while preserving exact
  duplicate idempotency and conflicting/out-of-order rejection.
- MODERATE - FIXED (2026-08-03). Cross-axis timeout coupling. Audit backpressure
  coupled to finalization.
  One `audit_timeout` fed three unrelated bounds — the finalization cutoff, the
  per-envelope `offer` enqueue wait, and hub close — so deriving a longer
  finalization cutoff from the writer's retry bound silently multiplied how
  long a wedged audit writer could stall the emitting workflow thread with a
  full queue, freezing live progress. Cause: producer backpressure and durable
  finalization were treated as one knob although only finalization must outlast
  a writer retry. Fixed with an independent `audit_offer_timeout` on
  `Dispatcher`/`EventHub`, a service constant that must not scale with the
  history writer, and a regression that emits under a long finalization cutoff
  and asserts the producer still degrades promptly.
- MODERATE - FIXED (2026-08-03). Cross-axis retry-budget coupling. Shutdown allowance was
  visibly long: deriving
  every audit bound from the generic ten-second serialized-writer retry made
  worst-case service close twenty-two seconds, long enough to read as an
  unresponsive window once Stage 6 calls it during teardown. Cause: history
  finalization reused the ledger's retry bound although it is an independently
  degradable axis whose exhaustion costs one audit row rather than filesystem
  or integrity truth. Fixed by giving history its own five-second retry bound,
  which carries the derived cutoff to six seconds and service close to twelve,
  with tests pinning both the ordering and a shutdown ceiling.
- MODERATE - FIXED (2026-08-02). Finalization deadline race. A finalization
  that committed after its audit acknowledgement deadline delivered
  `audit=degraded` but retained `audit=ok`. Cause: the observer persisted a
  provisional result before the pump knew who owned the deadline. Fixed with an
  atomic finalization decision latch: an expired caller wins degraded truth, or
  a pump owner determines the final result. The immutable payload and its
  existing transaction now persist the decided audit axis; derived writer,
  audit, and close bounds are regression-tested in order.
- SEVERE - FIXED (2026-07-30). Pre-invocation cancellation settlement gap. Canceling a
  paused execution just after resume published RUNNING but before
  `invocation.run()` produced a generic canceled terminal while leaving runtime
  custody and the ledger run unfinished. Cause: the dispatcher's initial
  checkpoint bypassed the registration-owned cancellation settlement for an
  already-started attempt; fixed by routing that race through the retained
  payload settlement before terminal publication.
- SEVERE - FIXED (2026-07-30). Independent-axis construction coupling. A corrupt
  or unwritable history database raised from the observer factory before the
  session was admitted, preventing filesystem and ledger work even though
  history is an independent axis. Cause: admission isolated observer delivery
  failures but not factory/open failures; fixed with a degraded-audit sentinel
  that preserves admission and yields `audit=degraded`.
- MODERATE - FIXED (2026-07-30). State/event publication race. A delayed
  `StateChanged(PAUSING)` publication could be overtaken by persisted
  `PAUSED`, leaving existing and late subscribers with a regressed current
  state. Cause: record transitions were locked but their reliable events were
  emitted after releasing the transition lock; fixed with a per-session
  publication gate spanning each transition and matching state event.
- MODERATE - FIXED (2026-07-30). Subscribe/close registration race. Subscription
  could capture a terminal session hub, lose a race with explicit close, and
  then append a stream to the already-closed hub; after replay drained, the
  stream never closed. Cause: hub lookup and subscription registration were
  separate critical sections; fixed by registering under the dispatcher
  condition so either subscribe or terminal close wins completely.

## INTERFACES

### Desktop bridge and native-owner lifecycle

- MODERATE - FIXED (2026-08-27). Observation stream accumulation. Repeated
  Gap recovery retained every closed stream until the session observation was
  removed, so valid long-running sessions grew with recovery count. Cause: a
  cleanup history doubled as stream ownership. Fixed by retaining only the
  current stream, synchronizing stop and replacement adoption, and closing
  retired/rejected streams outside the observer lock. Weak-reference churn and
  both stop/adopt orderings preserve close-before-join and retry behavior.
- MODERATE - FIXED (2026-08-27). Premature return-custody retirement. The
  admitted-handler ceiling released positions before pywebview serialized and
  delivered replies, permitting accumulated return graphs and shutdown before
  those workers finished. Cause: domain-call completion stood in for native
  worker completion. Fixed by retaining each native position against its exact
  thread until exit and joining outside the bridge lock with one retryable
  deadline. Direct Python calls retain call-return semantics; pre-admission
  threads and renderer allocations remain outside this bound.
- MODERATE - FIXED (2026-08-27). Unused callback retention. Every synchronous
  pywebview return left a new UUID-to-None entry in the window's callback
  registry, so completed calls caused lifetime growth. Cause: the pinned
  runtime stored synchronous placeholders that no return path consumed. Fixed
  with a window-local registry that discards only None writes while preserving
  asynchronous callback lookup and deletion. Pinned-source and actual-runtime
  tests guard that dependency assumption; a runtime upgrade must revalidate it.
- MINOR - FIXED (2026-08-26). Cross-version gate aliasing. The unreachable
  private browser seam accepted v5-stamped numeric-v4 bodies and rejected v4,
  while source gates could find legacy text instead of the live route or active
  Progress validator. Cause: a shared version constant and overbroad source
  slices conflated retained and current contracts. Fixed with literal v4 at the
  private seam, exact live-function isolation, active-v5 shape/vocabulary checks,
  and mutation regressions. No production legacy route was added.
- MINOR - FIXED (2026-08-26). Unbound producer fixtures. Separate Python public
  view witnesses and browser literals could stay green while the real codec
  drifted away from JavaScript. Cause: no differential check passed the actual
  Python primitive projection to the packaged consumer. Fixed by binding all
  seven event families and relevant public-view witnesses through that codec
  and the live event arm, retaining independent literal expectations and
  post-projection negative mutations.
- MODERATE - FIXED (2026-08-26). Shallow view admission. Exact dataclass wrappers
  could carry old-version events, malformed nested results, or result-free
  terminal records through Python task drains and bridge serialization. Queue
  consumption and terminal-delivery receipts could precede semantic refusal,
  while the browser accepted null terminal results and released session custody.
  Cause: outer type checks substituted for the v5 view contract. Fixed with
  shared primitive/typed validation at each consuming boundary, whole-candidate
  validation before drain mutation, and matching result-bearing terminal gates.
  Valid result-free recovery snapshots do not earn receipts; replay cache
  invalidation does not revoke a prior validated delivery receipt.
- MODERATE - FIXED (2026-08-25). Execution-authority state conflation. The
  accepted desktop design permanently froze a committed selection even when
  submission failed or the attached attempt terminated `unrun`, making its
  documented subset-retry and result-replacement path unusable. Cause: immutable
  plan evidence, mutable selection authorization, and consumed execution
  authority shared one terminal meaning. Fixed by reopening the unchanged
  plan's selection at a new revision after submission failure or `unrun`,
  minting a fresh commitment for retry, and freezing permanently only at the
  first `ran` result.
- MODERATE - FIXED (2026-08-25). Display-path reactivation authority. A new
  plan requested from an unrun task had no ledger-derived recent pair and could
  only reuse `ReviewedLocation.display`; after drive-letter reassignment that
  spelling could identify a different volume. Cause: presentation text was the
  only proposed bridge from retained review evidence back to Setup admission.
  Fixed with `activate_task_pair`, which resolves both reviewed volume
  identities and relative paths afresh, publishes two slots only when both
  accept, and creates a separate default-selection task without carrying old
  authorization.
- MODERATE - FIXED (2026-08-22). Post-Gap phase-authority lock. After a Gap,
  the first self-described Progress established only lossy phase context, but
  the reducer treated it like reliable `PhaseChanged` authority and rejected a
  later valid phase when the intervening change was outside replay; atomic
  preflight could also withhold reliable siblings. Fixed by locking phase only
  under reliable authority, resetting progress-only temporal state on a newer
  self-described phase, retaining same-phase regression checks, and proving
  whole-batch refusal plus exact clean replay in the executable Node gate.
- MODERATE - FIXED (2026-08-22). Live event-version erasure. The bridge's
  `SessionEventView` discarded the core envelope version, leaving JavaScript to
  infer an exact live Progress contract only from body keys and inviting future
  history rows to reuse a current-live validator. Fixed by carrying the nested
  core event version, requiring exact live v4 through a deliberately named
  live-only validator, and keeping mixed persisted v3/v4 `HistoryEventView`
  validation version-dispatched per row.
- MINOR - FIXED (2026-08-21). Executable consumer-evidence omission. The
  ordinary suite checked the expanded Progress validator through source-text
  tokens while its actual JavaScript behavior lived in an optional Node probe,
  so dead or unconditional validation could pass when Node was unavailable.
  Fixed by making the packaged drain-manager probe non-skippable, resolving an
  explicit `NAMISYNC_TEST_NODE` before `PATH`, and executing malformed-batch
  rejection plus clean reliable replay. Other Node probes remain supplemental;
  installed WebView2 still owns their named browser-behavior acceptance.
- MODERATE - FIXED (2026-08-19). Partial-attachment rollback gap. If `loaded`
  event registration failed and removal of the already-installed `before_load`
  handler also raised, appearance configuration escaped without aborting its
  controller. The window retained the bound callback after configuration was
  reported failed; once cosmetic binding preceded attachment, it also retained
  a live subscription. Cause: inline handler removal could short-circuit all
  remaining resource retirement. Fixed by fault-isolating removal, always
  aborting partial attachment, closing the cosmetic subscription exactly once,
  and invalidating the controller so a retained handler is inert.
- MODERATE - OPEN (2026-08-17). Headed compositor-restart evidence blindness. A
  headed checkpoint can report green while Windows DWM restarts during the same
  session because the harness observes its child/page result but has no shared
  compositor event sentinel. Checkpoint 4 coincided with the 18:29:25
  Application Error record 63156 and WER report
  `854b76c5-b80c-4127-acc8-404d18814e0d`; Dwminit record 63157 reports restart
  1, while WER subcode `0x23` names an unexpected heap exception. No
  contemporaneous GPU/TDR event was found in the inspected logs. Earlier
  2025-07-23 and 2026-07-26 DWM restarts had different
  `MILERR_DISPLAYSTATEINVALID` signatures, and checkpoint 5 had no later DWM
  event. This proves an evidence blind spot, not NamiSync causality. A shared
  headed-session compositor sentinel remains required before a green checkpoint
  can make any compositor-health claim.
- MINOR - FIXED (2026-08-17). Headed-evidence replacement contention. Headed
  children repeatedly replaced one live JSON snapshot while parents polled and
  opened it, so Windows delete sharing could reject an otherwise correct final
  publication and force every new witness to copy a retry loop. Fixed with one
  tests-only immutable milestone protocol: closed same-directory temporaries
  publish `ready` or `failure`, then `final`, without replacing an observed
  file. Parents read each canonical bounded record once; held-file evidence
  proves final publication is independent of the open ready handle. Atomic
  per-invocation benchmark reports remain separate measurement artifacts, not
  milestones.
- MODERATE - FIXED (2026-08-17). Raw-readiness supersession race. On initial
  injection the bridge listener could resolve raw API readiness before the app
  listener rejected its old startup epoch, allowing that stale attempt and its
  required rerun to dispatch `shell_ready` for one native generation. Native
  acknowledgement was idempotent, but the fresh attempt could then be refused
  and never mark the JavaScript bridge operational. Fixed by rechecking epoch
  ownership after every raced readiness wait; a bridge-first pending-readiness
  probe proves the superseded attempt sends no acknowledgement.
- SEVERE - FIXED (2026-08-17). Document-readiness admission gap. The
  desktop marked ordinary bridge commands available after native load, and
  kept them open across reload, even when the current packaged receiver had
  not acknowledged initialization or its first appearance message could not
  be posted. Fixed with a five-second current-generation gate joining native
  load, `shell_ready`, safe base-surface settlement, and a neutral host
  challenge/page `readiness_echo` roundtrip before normal admission. The nonce
  is unlogged liveness evidence, not authorization. Appearance publication is
  degradable and orthogonal; only unconfirmed rollback after native surface
  mutation refuses. Timeout, reload, close, and queued callbacks cannot settle
  a later document.
- MODERATE - FIXED (2026-08-17). Appearance observation ordering race.
  Independent callback-thread reads let an older Windows snapshot queue after
  a newer one and receive the newest publication revision; the initial read
  also preceded subscription. Fixed by subscribing before the mandatory read
  and coalescing generations into one UI-owned current-state drain. Each UI
  turn handles one generation and defers newer work, so sustained events yield;
  dispatch/read failures remain recoverable and close invalidates queued work.
- MODERATE - FIXED (2026-08-17). High-contrast composition evidence gap. The
  headed materials case injected a native high-contrast snapshot but left the
  renderer in normal-color mode, so it could claim palette coverage without
  exercising the production forced-colors branch. Fixed by activating CDP
  `forced-colors` in that same clean-wheel WebView2 child and comparing body and
  card styles with independently resolved `Canvas`, `CanvasText`, and
  `ButtonBorder` values while retaining every native Mica-off assertion. This
  is a composition witness, not a real Windows contrast-theme toggle witness.
- MODERATE - FIXED (2026-08-17). Selected-state forced-color mismatch. Enabled
  selected/current task cards resolved their background to `Highlight` but
  inherited `CanvasText` at rest and focus, so contrast-theme text could lose
  its intended foreground pairing. Fixed by binding those cards to
  `HighlightText` under forced colors, suppressing their decorative shadow,
  and retaining `GrayText` for disabled cards. Static and clean-wheel gallery
  evidence covers both selectors, all enabled states, exact system colors, and
  text contrast; ordinary transparent, hover, and press behavior is unchanged.
- SEVERE - FIXED (2026-08-17). Startup-refusal authority gap. An initial,
  pre-open appearance or guard refusal attempted window destruction while the
  exposed dispatcher was still accepting; if public destruction threw or
  returned without closing, the real GUI loop could remain alive with trusted
  command authority. Fixed by rejecting dispatch and waking the registry
  before presentation teardown, making the refusal transition idempotent,
  checking the closed event, and posting one owner-bound `WM_CLOSE` after a
  failed or ineffective public destroy. Both close paths may still fail, but
  authority then remains rejected. Manual or later native closure lets the GUI
  loop return, after which the startup-refused finalizer runs.
- MODERATE - FIXED (2026-08-17). Selected-state boundary contrast. Selected
  and current task cards used the subtle neutral boundary that belongs to
  quiet surfaces, leaving their actionable edge below the 3:1 non-text
  contrast requirement in light mode. Fixed with the opaque selected surface,
  accessible neutral boundary, retained elevation/focus, and distinct
  forced-colors hover/press outlines. Transparent unselected rest cards remain
  intentionally boundary-free and outside that selected-state assertion.
- MODERATE - FIXED (2026-08-17). Renderer API floor mismatch. The packaged
  shell used `Object.hasOwn`, reflected `role` properties, and
  `crypto.randomUUID` even though the admitted WebView2 floor predates those
  APIs. Icons, accessibility roles, and every command requiring an opaque id
  could therefore fail on a supported runtime. Fixed with own-property calls,
  explicit role attributes, and `getRandomValues`-backed 32-hex identities,
  plus a shipped-asset floor guard and supplemental/real-browser evidence.
- MODERATE - FIXED (2026-08-17). Passive viewport resize paging gap. The
  virtual tree reconciled its mounted window after scroll and commit but not
  after a layout-only viewport resize, so newly exposed rows could remain a
  blank spacer until another interaction. Fixed with one per-root
  `ResizeObserver` feeding the existing coalesced viewport frame; it creates no
  paging authority. Its idempotent controller disposal disconnects observation,
  removes root listeners, invalidates pending work, and makes a queued frame
  inert before root removal. Direct-module and installed-wheel WebView2
  witnesses grow a settled two-row viewport to four without scrolling, prove
  the newly exposed index is covered, then prove disposal admits no later page.
- MINOR - FIXED (2026-08-14). Acceptance drift-guard omission. Ordinary
  suites exercised the real current-source custody shape but checked only
  positive size, plausible density, and component/union relations; the frozen
  ceiling was applied only to committed or synthetic datasets. A retained view
  could therefore grow past the accepted bound without failing current-source
  tests. Fixed with a separate one-child live drift guard that authenticates
  the unchanged ceiling contract and applies 1,966,080 bytes to both ordinary
  and maximum no-`Gap` custody. The verdict-free runner and blob-pinned
  acceptance validator remain unchanged.
- MODERATE - FIXED (2026-08-14). Progress wakeup-coalescing race. An attentive client
  could return and rearm once per progress snapshot, making adapter coalescing
  schedule-dependent and multiplying cross-runtime work. Cause: the waiter
  returned for any nonempty queue and retained no task-owned first-availability
  deadline across replacement, supersession, or retry. Fixed with one capped,
  non-sliding 150 ms progress-only deadline; reliable, `Gap`, terminal,
  recovery, close, and supersession still wake immediately. The 175 focused
  drain/command/host regressions cover cadence, stale custody, races, ordering,
  and unchanged cursor behavior. With an active long poll, the first detailed
  progress value intentionally may wait the full 150 ms; command receipt and
  reliable running-state feedback bypass it.
- MINOR - FIXED (2026-08-14). Measurement-boundary conflation. The headed
  harness retained every decoded browser sample, repeatedly serialized growing
  producer documents inside the measured child, admitted a wrapper rather than
  the actual host to the Job, and let one 16 MiB whole-Job line decide the event
  result. Cause: evidence collection, process membership, transport custody,
  and runtime acceptance had no separate owners. Fixed with bounded streamed
  SHA-256-manifested browser/producer evidence, post-exit final assembly,
  pre-composition direct-Job child admission, and per-PID role/private-byte plus
  thread/handle/topology diagnostics. Event acceptance is now independent of
  diagnostic completeness; whole-runtime acceptance remains undefined.
- MINOR - FIXED (2026-08-14). Reserved-capacity starvation. The bounded
  browser reporter reserved only four pending sample batches, so four tasks
  reaching terminal together could fill that allowance with ordinary reports
  and make a valid terminal callback throw before presentation. Fixed by
  retaining the four-batch ordinary limit while reserving a separately bounded
  16-batch total for the known terminal-adjacent burst; terminal reports remain
  isolated below bridge ingress size and cannot be mistaken for product loss.
- MINOR - FIXED (2026-08-14). Measurement-domain conflation. The old
  SH-G-8 evidence charged the complete headed Job, while its Python diagnostic
  mixed subject-scaled terminal results and short/shared values into queue
  custody. Cause: transport custody, completed artifacts, and whole-runtime
  containment shared one memory predicate. Fixed with path-local,
  identity-deduplicated queue sizing, disjoint realistic corpora, and real
  production-deque calibration/holdout runs. The independent three-process
  holdout passed at 1,351,794 ordinary and 1,513,014 exact-maximum bytes against
  the frozen 1,966,080-byte ceiling, with exact source/runtime/dependency
  authority plus no-`Gap`, ordering, 128/64/64, cleanup, and terminal truth.
  This closes SH-G-8 and BR-G-42 event/transport custody only. BR-G-45
  terminal-artifact retention and SH-G-15 whole-runtime containment remain
  open and untested by this evidence.
- MINOR - FIXED (2026-08-13). Split protocol authority. Active
  documents delegated exact errors and retry rules to `M1_SHELL.md` while also
  retaining stale command, sequence, and lifecycle summaries, so reviewers
  could follow incompatible contracts and SH-G-8 appeared closed without its
  normal-envelope evidence. Cause: the Stage 6 delivery plan was promoted into
  a second protocol authority after `M1_BRIDGE.md` had already settled the
  seam. Fixed by making `M1_BRIDGE.md` the sole bridge/BR-G authority, reducing
  `M1_SHELL.md` to delivery/package/SH-G ownership, and correcting active links
  and status. Numeric-hole, `start_plan`, and installed real-WebView2 browser
  witnesses have landed. Realigned SH-G-8 later closed under its separate
  transport-custody contract rather than the former whole-Job predicate.
- MODERATE - FIXED (2026-08-13). Cross-lifetime cleanup coupling. Appearance
  authority was retired during task quiescence before `service.close()` proved
  terminal completion. An incomplete
  or exceptional close correctly leaves the window open for retry but silently
  loses future theme, accent, and high-contrast observation. Cause: task-owned
  observations and window-owned appearance shared one cleanup hook. Fixed by
  keeping appearance live until complete service shutdown, then closing it once
  immediately before destruction.
- MODERATE - FIXED (2026-08-13). Fallback-state evidence conflation. Opaque
  fallback could be white in dark mode and report success after only the form
  background landed while full-client glass
  and a transparent WebView controller remained. Cause: fallback ignored the
  captured theme and collapsed backdrop, glass, form, and controller evidence
  into permissive booleans. Fixed with theme-correct Fluent canvases and an
  opaque claim based only on sufficient structured landing evidence; a later
  unconfirmed reapply publishes a truthful `degraded` state whose CSS base is
  opaque rather than retaining the prior material claim.
- MODERATE - FIXED (2026-08-13). Implementation-derived contract drift.
  A new 256-byte field cap rejected ordinary literal searches even though the
  external request envelope already had a 65,536-byte ceiling, while every
  anchor call rebuilt a complete id map and the exact DTO forced a second full
  120,000-node tree. Cause: implementation-specific limits and adapters were
  promoted into requirements without boundary or scale evidence. Fixed by
  restoring the 65,536-byte field ceiling, direct workflow-node view, and indexed
  O(chain-depth) anchoring.
- MODERATE - FIXED (2026-08-13). Semantic-only accessibility implementation.
  The renderer advertised
  `tree`/`treeitem` roles but exposed no Tab stop, active descendant, keyboard
  navigation, or off-DOM sibling metadata, so keyboard and assistive-technology
  users could not operate or perceive the virtual hierarchy. Cause: tests
  asserted role strings and focusable landmarks instead of widget behavior.
  Fixed with server-derived structure, an exact Python-owned wire view, and one
  operable recycled focus model.
- SEVERE - FIXED (2026-08-17). Review-text layout-control injection.
  Filesystem display text rendered inertly with `textContent` but could still
  carry bidirectional, isolation, line, and invisible controls that reorder or
  hide the operation a reviewer believed they were approving. Cause: the XSS
  defense treated non-executable text as presentation-safe and its headed test
  required every hostile label to remain byte-exact in the DOM. Fixed at the
  filesystem-only render sink by mapping the exact defended set and literal
  marker delimiters to injective `⟦U+XXXX⟧` markers, isolating each label, and
  retaining raw filename display in workflow, wire, and search while callbacks
  receive raw opaque node ids. Installed DOM and accessibility evidence proves
  exact markers, no surviving active controls, exact ordinary Unicode/long
  text, and raw ids;
  `DEFENSE.md` owns the narrower confusable-text residual.
- MODERATE - FIXED (2026-08-17). Projected-parent accessibility drift.
  Empty inventory roots and folders retained only by their own filter match
  exposed `aria-expanded=true` and a disclosure even though the active tree
  contained no child row. Cause: expansion was derived from the workflow
  container bit rather than the filtered projection. Fixed with immutable
  retained-child metadata: only projected parents emit Boolean expansion;
  leaves and containers with no retained child emit `null` and no disclosure.
- MODERATE - FIXED (2026-08-17). Virtual-tree interaction ownership gaps.
  Keyboard navigation changed the active descendant without ensuring its row
  stayed inside the scroll viewport, while the visible disclosure had no
  pointer-owned toggle path and bubbled to row activation. Fixed with exact
  fixed-row reveal math and a disclosure listener that stops propagation,
  focuses the tree, and requests one toggle without activation. A projected
  end node remains inert, and callback failure cannot leak into row activation.
- MODERATE - FIXED (2026-08-17). Virtual-window request omission. The tree
  exposed full-height spacers but did not convert user scrolling into a missing-
  window request, leaving a blank viewport and an offscreen active descendant.
  Cause: paging existed only for keyboard navigation. Fixed with one passive-
  scroll/animation-frame owner that maps the final viewport to a missing global
  index, owns the request generation, preserves external projection priority
  and scroll position, rejects stale commits before reading them, and moves only
  presentation focus to a fully visible row. The request binds its viewport
  snapshot, so a valid narrow response cannot start an automatic edge-to-edge
  retry loop while that viewport remains unchanged.
- MINOR - FIXED (2026-08-13). Presentation-state acceptance drift.
  The entire task rail inherited an opaque generic card, neutral hover/pressed
  and primary rest/pressed states collapsed visually, and dialog exit motion was
  absent while selector-only tests claimed closure. Cause: reduced requirements
  were committed with implementation-mirroring tests. Fixed with a
  transparent rail/task rest surface, distinct Fluent/Windows states, real exit
  behavior, and computed/pixel headed evidence.
- SEVERE - FIXED (2026-08-13). Bridge object-capability exposure. Passing the
  dispatcher as `js_api` let pywebview recursively discover receiver members,
  so underscore-prefixed bridge state was not a security boundary and crafted
  raw WebMessages could name private call paths. Fixed by creating the window
  with no `js_api` object and exposing one function-only `dispatch` entry.
  Ordinary and real-WebView2 probes send private dotted names and confirm that
  no private receiver or document mutation is reachable.
- SEVERE - FIXED (2026-08-13). Unbounded domain admission and teardown
  ownership. Pinned pywebview creates an exposed-call thread before NamiSync
  admission; the dispatcher then had no cap, and teardown could wait forever or
  release logging, path, and instance owners after quiescence failed. Fixed with
  a 64-handler admitted-work ceiling, bounded monotonic handler wait, one fail-
  closed quiescence sequence, retryable close, and owner release only after
  complete service shutdown. Drains and producers wake before the wait;
  saturation returns `bridge_busy`. Raw exposed-call thread creation remains a
  dependency-owned availability boundary classified in `DEFENSE.md` §4.
- MODERATE - FIXED (2026-08-13). Unbounded task retention and recovery retry.
  Terminal tasks and start receipts had no production release command, an
  uncertain start could lose replay when its folder slots expired, and repeated
  drain failure could immediately rearm forever. Fixed with a 48-task ceiling,
  terminal-record-gated lifecycle commands, bounded close receipts and cleanup
  compensation, pre-slot wire-intent replay, and finite delayed recovery that
  refuses after its budget. The real headed gate also proves a 25-second drain
  remains concurrent with another RPC and settles during window shutdown.
- MODERATE - FIXED (2026-08-13). Terminal/session ownership conflation.
  The browser automatically called `close_task` after a terminal record, while
  terminal callback failure discarded browser authority before cleanup could be
  retried. Fixed by presenting terminal truth first, retaining it on callback
  failure, and automatically releasing only observation/session authority.
  Explicit `close_task` alone drops the plan and task; release and close share
  stepwise, race-safe cleanup and bounded same-payload recovery.
- SEVERE - FIXED (2026-08-13). Cross-layer discriminator drift. Real plan
  terminal records were rejected by the browser. The workflow emits its
  registered `sync-plan` kind, but the client
  validator and its synthetic headed witness expected the invented alias
  `plan`; every real terminal drain therefore entered transport recovery and
  never presented completion. Fixed by validating the exact workflow kind and
  deriving the installed-wheel fixture from `PLAN_KIND`; the real WebView2 gate
  now crosses that production identity before terminal release.
- MINOR - FIXED (2026-08-13). Primary-failure diagnostic loss. Decisive startup
  diagnostics were missing after logging configuration. The outer host catch
  entered teardown without first
  recording the initiating exception, so a completed finalizer could close the
  only configured handler while retaining merely secondary cleanup evidence.
  Fixed with one typed `startup.failed` traceback before fail-closed teardown;
  diagnostic failure cannot replace the native report or exit status, and
  pre-logging failures continue to use only the native startup reporter.
- MODERATE - FIXED (2026-08-13). TOCTOU pathname and window substitution.
  Startup validated resolved app paths and found an activation window by title,
  then used both after a replacement opportunity. Fixed by holding non-reparse,
  delete-denying handles on the app root, logs, WebView2 directory, and both
  ready database mains for process lifetime, and by requiring the found HWND's
  process image to match the current executable or venv base interpreter before
  activation. A malicious same-principal process can still squat the mutex or
  spoof an accepted base interpreter; the primitive is not a same-principal
  security boundary.
- MODERATE - FIXED (2026-08-13). Receipt/shutdown lifecycle race. Service
  close could mark the facade closed and clear session receipts while a retry
  was already reading or replaying one, returning authority after shutdown had
  begun. Cause: the close transition did not share the receipt lifecycle gate
  used by receipt lookup and publication. Fixed by performing the close mark
  and receipt-map clearing under that gate; an in-flight replay must now finish
  before shutdown invalidates receipt state.
- MINOR - FIXED (2026-08-13). Duplicated command-policy drift. Timeout and
  retry metadata in Python could differ from the behavior hand-coded in
  `bridge.js`, while malformed command names could inject control text into
  diagnostic records. Fixed with an exact dual-declaration policy mirror test,
  bounded lowercase-snake command validation, log-safe command projection,
  explicit same-payload bounded release retry, and continued refusal of hidden
  `mirror` at the desktop payload boundary.

### M1 Hardening

- MODERATE - FIXED (2026-08-27). Adapter exception graph retention. Failed
  single-flight starts retained original or retry-cleanup exceptions; observer
  workers and cleanup leaked control exceptions or aborted later stream closes.
  Invalid or post-validation-mutated planning returns could acquire compensation
  custody. Fixed with closed failure codes, per-stream contained cleanup, Boolean
  observer failure, and one-time exact `PlanSession` field snapshots before
  compensation. Callers receive fresh unchained failures and cleanup remains
  retryable; weak-reference regressions cover starts/replays, mutation, multi-
  stream close, observer wait, unsubscribe, and rollback.
- SEVERE - FIXED (2026-08-13). Publisher lifetime-control omission. The
  appearance-publication UI-thread deadlock remedy was not lifecycle-bounded.
  The 2026-08-12 fix moved synchronous pywebview DOM
  calls to a daemon worker, but a wedged renderer can retain that worker/window
  indefinitely after the one-second close join. Its whole-style-attribute write
  is also blocked by the shipped CSP and would clobber unrelated properties if
  allowed. Fixed by replacing the worker with UI-thread asynchronous
  host-to-page WebView2 publication and fixed validated CSSOM sinks.
- SEVERE - SUPERSEDED (2026-08-12). UI-thread re-entrant deadlock. The
  first loaded desktop window could apply its native backdrop and then stop
  responding before publishing theme, accent, and material state to the page.
  Cause: NamiSync marshaled pywebview's synchronous public DOM API onto the
  WinForms UI thread; the pinned WebView2 backend scheduled its script
  continuation back to that same thread and waited. Fixed by retaining UI-thread
  marshaling only for native DWM/controller work and serializing public DOM
  publication on the owned background publisher, with a regression that refuses
  native-UI reentry and proves publication occurs on that worker.
- MINOR - FIXED (2026-08-03). Prerequisite error conflation. A missing .NET
  Framework release key was reported as missing WebView2, obscuring the actual
  .NET 4.6.2 prerequisite. Cause: the side-effect-free detector returned one
  boolean and tests omitted the absent-key state, where pywebview 6.2.1 itself
  raises `UnboundLocalError`. Fixed with one typed registry probe that reports
  .NET, WebView2, or detection-failure reasons; malformed/unreadable values
  recommend repair. Tests pin the single read, intentional upstream divergence,
  and refusal messages. Windows 11 includes .NET Framework 4.8, so this state
  is unsupported-installation diagnostics rather than a normal user path.
- MODERATE - FIXED (2026-08-01). Fallback-import side effects. Refusing a
  missing WebView2 runtime wrote Internet Explorer feature-control keys first:
  `webview.start()` imported pywebview's MSHTML fallback before NamiSync's
  renderer check. Fixed with a read-only, pywebview-compatible registry preflight
  before `create_window`, repeated before initialization, and behavior-tested
  against the pinned upstream detector. A configured fixed runtime bypasses
  Edge-channel discovery but not the shared .NET/netfx prerequisite read; the
  synchronous Edge Chromium check remains defense in depth. The
  `86.0.622.0` argument is pywebview's WinForms compatibility gate, not a
  NamiSync security-patch minimum.
- SEVERE - FIXED (2026-07-31). Partial-initialization state loss. Pywebview swallowed
  synchronous event-handler failures, so a failed `before_load` installer left
  dispatch closed without actionable host state and could retry after a partial
  subscription. Fixed with explicit pending/attached/failed state, one sticky
  attachment attempt, attachment-specific fail-closed dispatch, and a
  host-visible error state.
- SEVERE - FIXED (2026-07-31). Host popup-policy bypass. Pywebview's earlier
  `NewWindowRequested` handler opened attacker-chosen URLs in the default
  browser before NamiSync could handle them. Fixed by pinning
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False` before native startup, alongside
  disabled file URLs, downloads, remote debugging, and debug mode; native popup
  and navigation guards remain defense in depth.
- MODERATE - FIXED (2026-07-31). Incomplete navigation interception. Top-level
  `NavigationStarting` does not observe iframes, so weakened or late CSP left no
  native frame control. Fixed by attaching `FrameNavigationStarting` and
  canceling every frame navigation while retaining first-in-`head`
  `frame-src 'none'` for initial parsing.
- MODERATE - FIXED (2026-07-31). Startup error conflation. Broad
  `WebViewException` handling mislabeled unrelated startup failures as missing
  WebView2, despite pywebview's silent MSHTML fallback; asset-origin code could
  also trim `window.real_url` incorrectly. Fixed by refusing non-Edge-Chromium
  during `initialized`, preserving unrelated exceptions, and deriving origin
  from the complete URL with `urlsplit`.
- SEVERE - FIXED (2026-07-30). UI thread-affinity violation. `CoreWebView2`
  access from pywebview's setup worker could hang rather than raise a
  cross-thread error, preventing host startup. Cause: the initial mock treated
  the managed WinForms control as an ordinary Python object. Fixed with one
  idempotent synchronous `before_load` callback that accesses and subscribes
  native events only on the WinForms UI thread before exposing application calls.
- SEVERE - FIXED (2026-07-30). Wrapper/native state divergence. After canceling an
  off-origin request, WebView2 retained the packaged document but pywebview
  reported the rejected URL, indefinitely locking out the trusted-page bridge.
  Cause: the bridge treated wrapper navigation intent as committed document
  authority. Fixed with a lock-protected native `CoreWebView2.Source` snapshot,
  updated on the UI thread and read by dispatch workers without marshaling.

- MODERATE - FIXED (2026-07-30). Failed-join ownership loss. A blocked sink that
  exceeded the observer join timeout was removed from retained observation
  state; after the first service close raised, the next close returned cached
  success while that observer thread could still be alive. Cause: both observer
  and service treated a failed join as an irreversible first attempt; fixed by
  retaining unjoined observations and retrying their close before the service
  may return cached success.
- MODERATE - FIXED (2026-07-30). Shutdown-state conflation. Once dispatcher
  shutdown completed, a runtime/history close exception made every later
  service close fail immediately; the runtime also discarded the store whose
  writer close failed. Cause: dispatcher completion and dependency closure
  shared one cache state, while runtime closure became irreversible before its
  dependency succeeded; fixed by caching dispatcher completion separately,
  serializing close attempts, retrying only runtime closure, and retaining the
  store/open state after a failed close.
- MODERATE - FIXED (2026-07-30). Receipt/session lifecycle race. A retry could
  replay a session after dispatcher close but before receipt removal, while the
  inverse admit/close interleaving could publish a receipt for an already
  closed session. Cause: dispatcher retention and service receipt
  lookup/publication/removal had separate synchronization; fixed with one
  lifecycle gate and retained-session checks around all three transitions.
- MODERATE - FIXED (2026-07-30). Partial-shutdown admission gap. After an incomplete
  shutdown correctly kept runtime dependencies alive for a later close retry,
  public plan, settings, inventory, integrity, history, and observation calls
  could still reach those dependencies and recreate cleared process state.
  Cause: `_closed` guarded receipt-bearing commands but not the complete domain
  facade; fixed with a shared open check while retaining only session
  status/control and shutdown cleanup after closure begins.
- MODERATE - FIXED (2026-07-30). Shutdown-phase conflation. A shutdown
  deadline permanently cached `complete=False` and still closed runtime/history,
  so non-cooperative workers could finalize through closed dependencies and a
  later `close()` could not recover. Cause: admission closure, dependency
  closure, and completed shutdown were one irreversible flag; fixed by keeping
  runtime open after an incomplete dispatcher result and allowing close to
  retry until completion.

## DATABASE AND INVENTORY

### Database artifact ownership and rollback

- SEVERE - FIXED (2026-08-13). TOCTOU rollback-unlink race. Failed
  fresh-pair initialization compared a reserved artifact's identity and then
  unlinked its pathname, so a replacement between those operations could be
  deleted; `KeyboardInterrupt` and `SystemExit` also bypassed rollback. Fixed
  with Windows reservation leases and `ReOpenFile` from the retained
  reservation for exact-object disposition, cleanup for every
  `BaseException`, retryable handle release, and explicit incomplete-cleanup
  notes. Foreign replacements are retained and normal startup still never
  invokes the destructive development reset.

### M1 Hardening

- MODERATE - FIXED (2026-08-27). Historical correspondence amplification.
  Every plan loaded all retained pairs and identity aliases for a mapping's two
  locations, so a small current scan could materialize an arbitrarily large
  historical graph before planning and exhaust the desktop process. Cause: the
  runtime used the general mapping snapshot reader without passing current scan
  scope. Fixed with current target-key and source/target-identity selection,
  400-subject streamed queries under one read snapshot, identity-indexed
  disqualification limited to identities relevant now, and restored canonical
  pair order. Nullable target identity, current alias, and multi-link safety
  semantics remain unchanged; unrelated history is not planning input.
- MODERATE - FIXED (2026-08-27). Unbounded integrity candidate population.
  Fresh full and selected-path integrity, stale-plus-completed scope, and saved
  resume could materialize an arbitrary eligible ledger population before any
  custody refusal, risking process exhaustion and partial downstream work.
  Cause: general inventory getters and Python post-filtering owned selection,
  so batching bounded parameters but not total rows or one complete union.
  Fixed with the separately typed candidate fact, SQL-side mode eligibility,
  one-snapshot streamed reads capped at the first row beyond 120,000, exact
  saved order/missing checks, stale identity deduplication, and workflow
  settlement that starts no verifier work. The independently modeled retained-
  byte and codec-envelope axes remain checkpoint-4 work.
- MODERATE - FIXED (2026-08-26). Ambient snapshot placement. File admission
  copied complete database/WAL contents into an environment-selected temporary
  directory, which could place private validation data outside the required
  local, non-cloud-synced database storage. Fixed by creating the owned child
  beside its database and refusing creation failure without fallback. Both
  roles retain source-artifact no-mutation and cleanup-error behavior; the
  immutable no-sidecar path still needs no scratch space. DATABASE records
  writable-parent and full-copy costs, directory side effects, and crash leftovers.
- MODERATE - FIXED (2026-08-26). Reader-lifetime admission amplification.
  Repeated inventory and history requests opened a new repository each time,
  rehashing complete main/WAL artifacts even for small result pages. Fixed by
  retaining one fully admitted reader per role in the local runtime, with
  serialized queries, fresh request transactions, and explicit close ownership.
  Query failures retire the reader; failed close retains ownership and blocks
  new use until cleanup is retried. Standalone, pair, and writer admission are
  unchanged. First-open work still scales with database size; DATABASE records
  its logical I/O and fixture axes without claiming a latency or memory bound.
- MODERATE - FIXED (2026-08-26). WAL-blind admission. A database whose WAL
  changed its contract marker could pass main-only admission, then refuse in a
  normal reader after creating source SHM. Cause: immutable SQLite ignores WAL
  truth. Fixed with shared private main/WAL validation before repository or
  existing-initializer opens, lexical journal refusal, and content/identity
  drift checks. Tests pin missing-SHM and poisoned-WAL refusal without source
  mutation, cleanup failures, and peer drift. Evidence is point-in-time, not a
  lease over later ordinary SQLite use.
- MODERATE - FIXED (2026-08-26). Metadata self-certification. Exact schema
  markers could admit databases with missing or poisoned objects; later queries
  failed, and initialization could silently add missing tables while preserving
  hostile same-name definitions. Cause: role admission trusts metadata without
  comparing topology. Fixed by activating the exact catalog comparator in
  reader validation and shared initializer/repository/pair preflight before
  repair DDL. Both roles reject missing, extra, or poisoned definitions without
  mutation; only declared exact optional statistics tables are exempt.
- MODERATE - FIXED (2026-08-10). Message-based error classification. The
  serialized writer retried any `OperationalError` whose message contained
  "busy" or "locked", delaying unrelated failures and reporting them as lock
  exhaustion. Cause: retry policy parsed human-readable exception prose. Fixed
  by accepting only primary `SQLITE_BUSY`/`SQLITE_LOCKED` result codes, masking
  extended codes to their primary value, and failing misleading message text
  immediately within the original recording-error boundary.
- MODERATE - FIXED (2026-08-09). Result-precedence inversion. A
  retained `hash-mismatch` marker could be projected as ordinary `modified`
  while current stat or identity also drifted. Cause: the repository returned
  metadata drift before consulting the stronger invalidation even though
  storage and stale selection preserved it correctly. Fixed by projecting a
  present row with current evidence as mismatched before ordinary drift, while
  unavailable evidence remains unverified; the public view is regression-tested
  at the intermediate drift state.
- MODERATE - FIXED (2026-08-08). Post-materialization selection bound. Frozen
  resume and stale-before integrity selection loaded every row for a location
  and filtered in Python, making small checks O(location size). Cause: the
  repository exposed canonical-path batching but no location-scoped row-ID
  read, and the workflow reused the full-inventory getter. Fixed with ordered
  canonical row-ID lookup in 400-ID chunks under one read snapshot, direct stale
  rows plus exact completed-row fetches, and refusal of missing/foreign saved
  identifiers. Intentional full Verify All remains a full-location operation.
- SEVERE - FIXED (2026-08-08). Sticky invalidation omission. A verified
  file could change, be rescanned, and retain an apparently current
  `last_verified_at`; stale selection then omitted it and inventory presented a
  false verified state. Cause: observation updates preserved attestation without
  durably recording that current stat/identity contradicted it. Fixed in ledger
  v3 with a sticky metadata-drift/hash-mismatch marker, schema constraints,
  stale-query inclusion, negative verifier recording, and verified/modified/
  mismatched projections. Hash mismatch dominates later metadata drift, and
  only a successful guarded evidence write clears the marker.
- MODERATE - FIXED (2026-08-04). Split contention-budget enforcement. Serialized database
  contention could outlive
  its configured retry bound: waiting for the in-process writer lock was
  unbounded, each SQLite attempt retained the full busy timeout, and retry sleep
  was not capped to the remaining allowance. Cause: only the outer retry loop
  consulted its deadline. Fixed with one monotonic contention budget spanning
  local-lock acquisition, per-attempt `busy_timeout`, and backoff, including an
  explicit zero-budget single immediate attempt and no positive-budget attempt
  after expiry. Transaction work after acquiring the write lock remains outside
  this contention budget.
- SEVERE - FIXED (2026-07-30). Incomplete-evidence authority leak. Non-authoritative
  full integrity verification.
  A full or stale-scope refresh with a global enumeration failure still entered
  the verifier and returned completed. Cause: the incomplete-scan refusal was
  conditional on exact selected paths; fixed by refusing every incomplete
  unbounded refresh and retaining only the fully explained exact-subject
  exception.
- MODERATE - FIXED (2026-07-30). Cross-batch snapshot fracture. Selecting
  more than 400 canonical keys could observe old rows in one batch and a newer
  concurrent commit in the next, producing a state that never existed. Cause:
  each bounded SELECT ran in its own autocommit snapshot; fixed with one explicit
  read transaction spanning all batches.
- MODERATE - FIXED (2026-07-30). State-transition asymmetry. A completed
  exact PATHS refresh did not mark an absent prior unsupported row missing, and
  missing-to-unsupported reappearance failed to set `reappeared_at`. Cause: the
  exact absent update filtered only `present` and unsupported upsert lacked the
  present path's transition marker; fixed by reconciling both visible states
  and applying the same reappearance transition.

## VERIFIER

### M1 Hardening

- MODERATE - FIXED (2026-08-22). Verify-phase admission split. Linked
  post-copy Progress admitted only readable candidates while its terminal
  `PhaseResult` also counted selected items with missing evidence, allowing a
  live `0/0` phase to end at `0/N`. Cause: reporter totals came from the
  filtered candidate set rather than the full workflow continuation. Fixed by
  carrying complete selected-item admission into the verifier, centralizing
  its physical-read budget across direct and resumed execution, and covering
  missing-only, mixed overrun, pause, cancel, and exceptional control paths.
- MODERATE - FIXED (2026-08-22). Continuation authority-axis loss. Paused
  standalone integrity custody retained processed bytes and item completion but
  discarded the verifier's expanded physical-read budget and aggregate
  recording degradation, so paused cancellation or an early resumed failure
  could report a contradictory tight total and recover `DEGRADED` to `OK`.
  Cause: the exact v1 continuation serialized only item-local work state. Fixed
  with strict integrity continuation v2, a monotonic selection-owned byte-total
  high-water, one-way aggregate recording, reporter propagation across resume
  and overshoot, and exact paused-cancel/setup-failure regressions. Reliable
  outcomes and recorded evidence remain the durable-truth authority.
- MINOR - FIXED (2026-08-21). Progress namespace misclassification. Post-copy
  verification labeled an originating executor operation id as `integrity`, so
  the field intended to disambiguate opaque row ids pointed consumers at the
  wrong namespace. Cause: the reporter hard-coded its producing module/outcome
  family instead of the identity's lookup owner. Fixed by supplying
  `operation` for linked post-copy candidates and `integrity` for standalone
  rows while retaining `IntegrityOutcome` as the reliable settlement type.
- MODERATE - FIXED (2026-08-21). Unthrottled lifecycle telemetry amplification.
  Item start, stream start, and settlement each forced a Progress event, making
  fast verification emit three fixed snapshots per item while equivalent
  execution could remain within its time throttle. Cause: lifecycle
  transitions were treated as mandatory source deliveries even though Progress
  is lossy state telemetry. Fixed by sending those transitions through the
  ordinary throttle, retaining only forced initial/final successful boundaries
  and one forced pause or cancel boundary, with frozen-clock item-count guards.
- MINOR - FIXED (2026-08-11). Concrete-type dispatch coupling. Engine sent
  only the exact `WindowsUnbufferedReader` class through its reviewed-authority
  open, so a subclass or timing decorator instead received the ordinary
  `open(root, path)` call. Production's exact default type stayed safe, but an
  extension could silently bypass the intended authority-bound route. Fixed
  with a runtime-checkable core reader protocol, a public bound open whose root
  comes only from the authority, structural engine dispatch and unbound
  refusal, and forwarding by the tools timing decorator. Selected-root and
  opened-volume policy remain in engine; final-path and native chain checks
  remain independent.

## CORE AND SECURITY PROTOCOLS

### M1 Hardening

- MODERATE - FIXED (2026-08-27). Typed detail canonicality bypass. A directly
  constructed or subclassed `DetailProjection` could retain duplicate keys,
  mutable or oversized values, hidden graphs, or excess leaves while its wire
  dictionary collapsed to apparently valid last-key truth. Custom mapping item
  streams could create the same first-value/last-wire contradiction. Cause: the
  typed fast path skipped all validation and raw admission did not track seen
  keys. Fixed with exact constructor validation, source-independent base
  snapshots, serialization revalidation, duplicate refusal before omission,
  exact primitive/container checks, and bounded-before-encode key/path refusal.
  Raw diagnostic omission semantics are preserved.
- MODERATE - FIXED (2026-08-27). Full-result diagnostic divergence. Terminal
  summaries omitted oversized or invalid phase/failure diagnostics, while the
  retained `OperationResult` behind them kept the original values through
  settlement, audit, history, and release. Fixed by applying the same
  whole-value rules before the first retained owner and counting only header
  omissions there; item omissions remain summary-local. Bounded header objects
  retain identity, and phase names/count policy is unchanged.
- MODERATE - FIXED (2026-08-27). Diagnostic formatting escape. An ordinary
  workflow exception whose `__str__` raised could escape terminal normalization
  after reliable items had settled, leaving the session without its one final
  outcome. Fixed by omitting the whole failure detail with one witness when
  ordinary formatting fails. `KeyboardInterrupt`, `SystemExit`, and other
  `BaseException` control flow still escapes; overflow refuses before any
  settle, audit, publication, or terminal owner.
- MINOR - FIXED (2026-08-27). Unicode-scalar boundary omission. Free-form
  request/evidence text could contain Python surrogate code units; an explicit
  high/low pair encoded successfully but decoded as one character, violating
  payload identity. Fixed with strict UTF-8 at all four JSON encoders and
  decoded string/key validation before workflow construction. Valid Unicode
  and literal backslashes keep their bytes; the reported raw-encoding collision
  was not a JSON/hash collision. Malformed optional scan-warning detail is
  omitted at construction without dropping code, path, or observations. Frozen
  malformed receipt replay conflicts without writes; no new epoch/reset.
- MINOR - FIXED (2026-08-26). Implicit domain hash projection. Plan and
  recorder hashers descended through arbitrary dataclasses and coerced mapping
  keys, allowing undeclared forms to acquire idempotency identity silently.
  File indexes consequently used numeric rather than canonical text preimages;
  this was a consistency/latent portability defect, not Python precision loss.
  Fixed with explicit owner projections, closed JSON validation, and full-width
  quoted indexes. Epoch 6 separates changed receipts through explicit pair reset;
  old identity-bearing v6 commitments fail re-fingerprinting before execution.
  Valid-Unicode identityless bytes remain stable; frozen malformed vectors stay
  historical evidence under the later strict Unicode-scalar boundary above.
- MODERATE - FIXED (2026-08-26). Projection byte-boundary omission. A
  structurally valid reliable event above 1,048,576 canonical bytes could pass
  Python's public-view validator and the browser, then advance browser state
  despite persistence-envelope refusal. Cause: those validators checked field
  shapes but omitted the shared envelope ceiling. Fixed by reconstructing the
  persistence shape (`seq`, not `sequence`) and applying its UTF-8 byte wall.
  Exact-maximum/plus-one public projections include mixed Unicode; rejected
  batches preserve callbacks, replay cursor, reducer phase, and release state.
- MODERATE - FIXED (2026-08-26). Cross-runtime primitive grammar drift.
  Python and JavaScript admitted different timestamp spellings, and the browser
  normalized impossible dates. Its Unicode guard also admitted a trailing lone
  high surrogate because comparisons with the missing next unit's NaN did not
  reject. Cause: permissive runtime parsers and an incomplete surrogate-pair
  predicate. Fixed with one literal UTC timestamp grammar, real Gregorian
  calendar validation, and mandatory valid low-surrogate pairing before byte
  accounting. Shared positive/negative Python and Node corpora preserve valid
  early/leap dates and non-ASCII text while refusing the divergent inputs.
- MODERATE - FIXED (2026-08-26). Cross-axis validation omission. Item and
  terminal projections could admit recording reasons that contradicted the
  filesystem outcome, or cancellation without matching execute/verify truth,
  even though continuation/full-result contracts rejected those combinations.
  Cause: projection validators checked each closed field independently and
  omitted their relationships. Fixed by sharing the existing recording matrix
  and cancellation rules across core objects and Python decoders and mirroring
  them in browser event/result validation. A literal complete recording matrix
  and cancellation corpus include public-view Node witnesses; valid plain and
  compound cancellation behavior is preserved.
- MINOR - FIXED (2026-08-26). Scalar error-family drift. Shared decimal and
  public event decoders classified malformed strings as wrong types, while
  very long canonical Scalar64 overflow escaped as Python's generic conversion
  error. The native file-id decoder also accepted integer/list coercion and
  carried a redundant optimization-sensitive assertion. Cause: combined
  type/grammar checks and conversion before domain validation. Fixed with
  exact type/grammar/domain error families, bounded-domain comparison before
  conversion, shared public event decoding, and explicit 16-byte unsigned
  construction. Public payload and optimized-mode regressions preserve valid
  full-width identity and unchanged volume/hash/epoch semantics.
- MODERATE - FIXED (2026-08-25). Native file-identity narrowing. Scanner and
  preflight could observe Windows/Python file indexes wider than 64 bits while
  executor and verifier reconstructed only legacy high/low 64-bit fields and
  the ledger stored signed SQLite integers. The same file could therefore
  compare differently across safety boundaries or fail persistence. Cause:
  three consumers owned incompatible native and storage representations.
  Fixed with one complete core-owned `FILE_ID_128` adapter, witnessed NTFS/ReFS
  stat equivalence, canonical full-width text through codecs and ledger v4,
  and removal of legacy high/low handle projection and numeric storage.
- MINOR - FIXED (2026-08-27). Cross-consumer schema acceptance drift. The core
  decoder previously retained v3 history compatibility beside v4 while the live
  browser and canonical history projection accepted different populations.
  Cause: consumer-local compatibility lacked one event/data epoch and removal
  point. Production is exact-v5-only at data epoch 6. Checkpoint 3.3 removes the
  private v3/v4 decoders, exclusive helpers, and positive compatibility fixtures.
  Removal guards and all-family negative cases pin the source boundary;
  co-batched retired-version events preserve the drain cursor and replay.
- MODERATE - FIXED (2026-08-22). Lossy-progress authority conflation. Forced
  control snapshots combined aggregates from an earlier throttled emission with
  live item-attempt state, producing internally contradictory pause/cancel views;
  field-local validation admitted them. Fixed by central field and transition
  semantics, authoritative-live forced snapshots, cross-field v4 invariants,
  self-described phase and opaque attempt identity, and separate
  reporter-transition, settlement-oracle, and browser-reducer regression layers.
- SEVERE - FIXED (2026-08-10). Logical-root authority omission. Verifier
  contexts carried reviewed mount and volume facts but not the exact logical
  root, so a malformed selection could admit one reviewed authority and open a
  different root on the same volume; default native entry points could also run
  unbound. Fixed with one ephemeral `RootAuthority`, exact selection-root
  refusal before state shortcuts/read/record work, and fresh admission before
  each readable item. Production inventory derives authority from its current
  resolution and post-copy from the reviewed plan; opened-handle and final-path
  checks remain independent. Unbound mode is limited to explicit fake/custom
  readers.
- MINOR - FIXED (2026-08-10). Reserved-name coverage gap. Path validation
  rejected ordinary reserved names but admitted `CONIN$`, `CONOUT$`, and the
  superscript-one/two/three COM/LPT aliases recognized by Windows. Those names
  cannot safely participate in the ordinary relative-path contract. Fixed by
  extending the one core reserved-basename set with case- and extension-aware
  coverage; unsupported device namespaces remain refused separately.
- MINOR - FIXED (2026-08-09). Boundary-local diagnostic sanitization. Scanner
  enumeration warnings and executor failed/canceled temp-cleanup wrappers used
  raw exception text, allowing `\\?\` spelling to enter public results or
  durable history despite the shared logical-path contract. Fixed by applying
  logical filename rendering before warning/result construction, including
  copied-backup cleanup notes, with focused public and durable cleanup-detail
  regressions.
- MODERATE - FIXED (2026-08-08). Inconsistent native-path adaptation. A managed
  path over the legacy Windows limit could fail before execution because some
  service, preflight, scanner, executor, or verifier calls used ordinary
  spelling, while native-prefixed errors could leak into durable/user detail.
  Cause: long-path conversion was local and incomplete rather than a shared
  logical/native contract. Fixed end to end with ordinary domain paths,
  conversion at every native I/O boundary, logical diagnostics, and refusal of
  device or ordinary-ambiguous absolute components that could retarget a root.
  SQLite database-file long paths and network-share coordination remain out of
  scope.
- MODERATE - FIXED (2026-07-30). Permissive JSON type coercion. Schema and sequence
  floats were truncated, scalar fields were stringified, and terminal
  `canceled="false"` became true. Cause: the versioned event decoder used
  Python conversion constructors instead of validating transported JSON types;
  fixed with exact integer/boolean/string decoding across envelopes, terminal
  results, phases, and nominal items.
- MODERATE - FIXED (2026-07-30). Incomplete recursive JSON validation. The security spike
  accepted boolean/float schema 1, duplicate keys, exponent-overflow infinity,
  and escaped lone surrogates; a handler could run on the last two before output
  validation noticed them. Cause: validation covered JSON syntax and top-level
  shape but not exact discriminators or recursive request values; fixed with
  duplicate-key rejection, exact schema typing, valid-Unicode checks, and
  recursive finite JSON validation before handler dispatch.

## WORKFLOW AND CLI

### M1 Hardening

- MODERATE - FIXED (2026-08-27). Verify-continuation diagnostic retention.
  Linked execution bounded failure type and message separately, then retained
  their unchecked concatenation in paused verify custody. The continuation also
  retained a caller-owned phase instance, admitting subclass graphs, forged
  counters, later alias mutation, and unchecked encoder projection. Cause:
  terminal normalization ran only at final publication and no canonical owner
  existed for the intermediate whole value. Fixed by bounding executor inputs,
  counting each omission once, snapshotting an exact validated phase at
  admission, and reconstructing the exact continuation again at v6 encoding,
  public execution, and canceled settlement. Pause/resume, cancellation, and
  terminal counters retain the same truth.
- MODERATE - FIXED (2026-08-26). Exceptional terminal attribution loss.
  Exclusion-outcome rejection followed by recording-close failure could publish
  and store a failed terminal with clean recording, then scrub the only exact
  close witness. Cause: exclusion emission escaped workflow failure projection;
  the generic runner could only reconstruct accepted item truth. Fixed with
  one continuation-derived failed projection for ordinary and cancellation
  exits, accepted-only exclusions, and retained first sink-error precedence.
  Close attribution now reaches terminal before scrubbing; public runner and
  real runtime/dispatcher/store regressions cover partial acceptance as well.

- MODERATE - FIXED (2026-08-06). Cleanup-failure suppression. CLI terminal
  cleanup and final shutdown could fail without any visible indication. Cause:
  `_close_terminal` swallowed every exception and all three command paths
  discarded the service shutdown result. Fixed by reporting expected
  cleanup-pending timeouts and unexpected failures to stderr, inspecting every
  final `ShutdownView`, and preserving the settled typed result and exit class.
- MODERATE - FIXED (2026-08-04). Cross-mode result normalization gap. Cancellation
  without post-copy verification re-raised `Canceled` after ledger settlement,
  so the generic runner replaced degraded recording truth with `recording=OK`
  and both modes could omit unexecuted-plan exclusions. Cause: only the compound
  path normalized cancellation and neither branch merged executor output with
  exclusions. Fixed by returning one typed canceled result in both modes,
  preserving `ExecutionSet` recording, merging the complete ordered item stream,
  and omitting the execute phase only when verification was not requested.

- SEVERE - FIXED (2026-07-30). Settlement cleanup omission. A failed
  ledger open or final write while settling a paused or just-resumed execution
  left its exact run token permanently claimed in
  `LocalWorkflowRuntime._execution_started`, even though dispatcher made the
  session terminal. Cause: only successful recorder finish removed the
  process-local claim; fixed by releasing the validated exact start claim in a
  settlement `finally`, including thrown-open and degraded-finish regressions.
- MODERATE - FIXED (2026-07-30). Close-state publication race. One caller
  could mark the runtime closed and block in history-store close; a second
  caller then returned success before the first failed and reopened the runtime.
  Cause: the state lock protected flags but not the dependency-close attempt;
  fixed with a runtime-local close gate that serializes failure and retry.
- SEVERE - FIXED (2026-07-30). Resume-settlement authority confusion. A coherently
  tampered execute/verify continuation was correctly refused before domain work,
  but the refusal tried to reopen recording from the tampered selection. The
  recorder raised a run-token input conflict and left the original ledger run
  unfinished. Cause: resume-failure settlement reused the fresh/open recording
  path even though an earlier continuation had already established the run;
  fixed with a custody-bound finish-existing-run dependency, strict
  same-runtime start-token validation, and real dispatcher plus real-ledger
  pause/resume regressions.
- SEVERE - FIXED (2026-07-30). Plan-generation ABA race. Replacing a plan reset its
  selection revision to zero and discarded mutation receipts, so a lost
  checkbox response, Execute, or destructive confirmation formed against the
  old artifact could apply to a new artifact with identical deterministic
  operation ids. A mutation racing replacement could also report that stale
  state as applied. Cause: artifact identity changed but its concurrency epoch
  did not survive replacement; fixed by monotonically advancing revisions,
  retaining recognized gesture tombstones, checking the current artifact after
  mutation, and returning the new preview as a conflict.
- SEVERE - FIXED (2026-07-30). Typed admission-response mismatch. With
  trash-on-update disabled, typing `execute` returned a
  `confirmation-required` view that the CLI treated as an execution session,
  then crashed with `AttributeError` without updating the target. Cause: the
  facade added a two-step risk handshake without adapting the existing typed
  CLI confirmation; fixed by rendering the exact irreversible-update warning,
  forwarding the typed response as an exact boolean acknowledgement, and
  handling every named admission view defensively.
- MODERATE - FIXED (2026-07-30). Idempotency check/submit race. Two simultaneous
  first deliveries with one plan/inventory/integrity command id could both pass
  receipt lookup and submit separate sessions; the initial closure left
  execution outside that guard, and a plan retry revalidated paths before
  finding its receipt. ID-based retries also reread mutable inventory first.
  Cause: retry protection was applied inconsistently across session-creating
  families; fixed with bounded command-id single-flight guards around every
  family, raw gesture signatures checked before mutable validation, and
  shutdown-safe receipt publication.
- MODERATE - FIXED (2026-07-30). Bulk-selection validation coupling. A single
  safety-disabled operation beneath a folder made the entire folder toggle
  raise, leaving otherwise selectable siblings inert. Cause: node expansion
  passed every descendant into the direct-operation safety validator; fixed by
  expanding folder gestures to toggleable descendants while retaining refusal
  for a disabled operation named directly.
- MODERATE - FIXED (2026-07-30). Permissive schema-version coercion. Inventory
  workflow version strictness.
  Inventory `2.9` and integrity `"1"` payload versions were accepted as current
  schemas. Cause: the shared decoder coerced version values with `int()`; fixed
  by requiring an exact JSON integer and the exact kind-specific version,
  including float, string, and boolean rejection coverage.
- MODERATE - FIXED (2026-07-30). Permissive persisted-field coercion. Inventory
  and integrity continuation fields converted strings, floats, booleans, and
  nulls with `str()`/`int()`/`bool()`, while settings accepted boolean/float
  schema version 1 and duplicate keys used last-key-wins semantics. Cause:
  version checks were hardened without applying the same rule to the remaining
  persisted shape; fixed with exact field/type validation and duplicate-key
  rejection at both boundaries.
- MODERATE - FIXED (2026-07-30). Premature custody acquisition. Opening a
  fresh execution claimed its run token before the dispatcher entered workflow
  work, and fresh commitment/preflight refusal or exception never released it;
  pausing at the runner-entry checkpoint also failed to snapshot `started_at`,
  so later cancel settlement failed. Cause: custody was attached to adapter
  decode rather than actual/snapshotted start; fixed with lazy claim, terminal
  cleanup, and entry-checkpoint pause snapshotting.

- SEVERE - FIXED (2026-07-25). Post-entry exception settlement gap. Exceptions
  during execute-result projection, continuation publication, verify phase
  entry/context creation, or verifier-result aggregation could escape after the
  recorder opened, leaving the logical ledger run unfinished; a resumed
  execute preflight refusal could also be mislabeled as fresh
  `REFUSED+UNRUN`. Cause: only the executor/verifier call itself was guarded and
  runtime discarded whether `started_at` came from a resumed payload; fixed
  with an explicit resumed bit, phase-aware exception results, and one guarded
  finish-once path for every post-entry terminal.
- MODERATE - FIXED (2026-07-25). Persistence/domain wrapper confusion. Reading
  a retained phase passed its `HistoryPhaseSnapshot` wrapper to the phase view
  and raised `AttributeError`; even without phases, the view omitted persisted
  cancellation and derived integrity/headline truth. Cause: the runtime
  projected repository wrappers as domain values and exposed an incomplete run
  view; fixed by unwrapping ordered snapshots, reconstructing the typed result,
  and routing retained classification through the same live result classifier.
- MODERATE - FIXED (2026-07-25). Cancellation/error precedence inversion. A malformed
  registration callback could be converted into a clean canceled terminal.
  Cause: dispatcher checked the already-requested cancel checkpoint before
  raising the captured adapter failure; fixed by giving the detected failure
  precedence and pinning PAUSING-drain/callback-failure races.

### M0 integration

- MODERATE - FIXED (2026-07-21). Rename-origin projection loss. Recase rows rendered
  the source and destination as the same spelling, and move/move-update rows
  likewise omitted the old target path, so review hid the filesystem rename a
  user was approving. Cause: `PlanOperationView` discarded
  `prior_target_rel_path` and the CLI always used the source path as the
  displayed origin; fixed by retaining `prior_target_path` in the workflow read
  model and preferring it as the left side for rename-shaped operations.
- MODERATE - FIXED (2026-07-21). Optional-field canonicalization drift. A plan-request
  payload that omitted `propagate_source_casing` decoded as false and then
  re-encoded with the field present, so one accepted payload did not have a
  byte-stable semantic round trip for an input to `policy_fingerprint`. Cause:
  the newly added flag alone used `.get(..., False)` while every neighboring
  semantic option was required; fixed by requiring the field during decode and
  retaining explicit round-trip coverage.
- MODERATE - FIXED (2026-07-20). Whole-run blocker coupling. One blocked item or an
  incomplete scan refused the whole sync, while simply omitting blockers could
  expose target-only deletion from incomplete source evidence. Cause: workflow
  selected every operation and preflight gated the whole run; fixed with
  commitment-bound safe-subset selection, dependency quarantine, additive-only
  incomplete-scan fallback, and preflight enforcement.
- MODERATE - FIXED (2026-07-20). Excluded-item outcome omission. Blocked plan
  items were absent from results and history because only selected operations
  emitted outcomes. Cause: the outcome model had no blocker state and workflow
  emitted no exclusions; fixed with `BLOCKED`, reasoned `DEFERRED` exclusions,
  itemized history rows, and a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Local symbol shadowing. Every real execution
  crashed while presenting fresh-preflight results, before mutation began.
  Cause: local `refusal_views` shadowed the formatter; fixed by using a distinct
  result variable.
- SEVERE - FIXED (2026-07-19). Untrusted fingerprint reuse. A decoded plan's
  carried fingerprint was compared with its commitment without recomputing the
  content hash, allowing altered payloads to appear authorized. Cause: two
  transported fields were treated as independently derived; fixed by recomputing
  the fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Late boundary validation. Identical
  database paths or overrides inside a managed root were rejected only after
  planning and confirmation. Cause: location validation lived only on the
  execution adapter; fixed by applying it before plan admission.

## SCANNER AND PREFLIGHT

### M1 Hardening

- MODERATE - FIXED (2026-08-10). Intermediate-path authority omission.
  Preflight no-follow checked configured roots but physically resolved subjects
  and trash, and volume-probed/enumerated reclaimable-temp parents, without
  first checking every relative component. An in-root junction could therefore
  redirect read-only evidence, produce a false touched-path observation, or
  credit unsafe temp bytes before the later verdict. Fixed by independently
  re-admitting each plan-bound root and no-follow admitting existing relative
  chains before every later probe; typed authority changes remain pure-verdict
  evidence. Executor final-touch guards still own the residual path-to-use race.
- MODERATE - FIXED (2026-08-10). Intermediate-path authority omission. PATHS and
  SUBTREES joined each requested relative path and no-follow statted only its
  final subject, so an intermediate junction could redirect observation and
  reconciliation outside the location while the result remained complete.
  Fixed by admitting every existing ancestor through the shared root-authority
  primitive before the scanner touches the leaf: unsafe or unavailable chains
  record the selected subject as incomplete unsupported evidence, while a
  missing ancestor remains conclusive selected absence. The exact FULL mounted-
  root exception is not inherited by scoped descendants. Component replacement
  after admission remains part of the documented path-to-use race until native
  traversal becomes handle-relative.
- MODERATE - FIXED (2026-08-09). Trusted-anchor/reparse conflation. A FULL
  scan rejected a location whose root exactly equaled its folder-mounted volume
  anchor because the walker treated the anchor's mount-point reparse tag as an
  untrusted configured-root junction. Inventory failed safely as
  `root_unavailable` before reconciliation. Fixed by requiring exact agreement
  among the resolved root, reviewed/current anchor, and volume-evidence mount,
  then following metadata only for that authorized root so its record uses the
  mounted-volume identity rather than the host mount entry. Final/intermediate
  configured-root reparses, placeholders, invalid followed state, subtree
  starts, and descendants remain refused.
- SEVERE - FIXED (2026-08-09). Lexical/physical root-authority conflation. M6
  changed native
  scanner root normalization to `Path.resolve()`, following a final junction
  before the no-follow check; checking only that leaf still allowed an earlier
  same-volume junction to redirect inventory under the original location.
  Fixed by preserving lexical roots, no-follow checking their configured path
  components, and binding scanner, executor, and per-open verifier work to the
  current reviewed mount and full `VolumeId`. Inventory refuses before
  reconciliation/hash work; scans discard observations if root authority
  changes before return; physical resolution remains separate overlap evidence.
  The final check-to-I/O and swap-away-and-back windows remain until root work
  becomes handle-relative.
- SEVERE - FIXED (2026-07-30). Quadratic ancestry normalization.
  Normalizing
  sibling recursive roots compared every root with every retained root and then
  every exact path with every root; 1,000 sibling roots took about 17 seconds
  and 2,000 took about 69 seconds before dispatcher admission. Cause: repeated
  normalization inside quadratic ancestry scans; fixed with canonical-key
  ancestor-set walks whose normalization count scales with declared path depth,
  plus a deterministic complexity regression and a multi-root global
  incompleteness composition test.

### M0 integration

- MINOR - FIXED (2026-07-21; superseded 2026-08-27). Inconsistent Unicode-
  encoding boundary. Free-form malformed diagnostic text could fail ledger,
  history, or workflow JSON encoding despite path validation. M0 aligned the
  encoders with the then-tolerant plan encoder. The later Unicode-scalar fix
  replaces that fallback with strict encoding and symmetric payload admission:
  optional scan-warning detail is omitted at construction, typed item detail
  retains its counted omission, and required text refuses. Valid observations
  remain recordable without claiming malformed identity text round-trips.
- SEVERE - FIXED (2026-07-20). Pre-validation name normalization. One NTFS, SMB,
  archive, or WSL-originated name outside NamiSync's relative-path contract
  could abort planning; an unpaired surrogate could later crash ID or fingerprint
  encoding. Cause: the walker normalized untrusted names too early, validation
  admitted surrogates, and canonical JSON required UTF-8; fixed with pre-use
  validation, typed escaped evidence, incomplete-scan isolation, surrogate
  rejection, and compatible serializer hardening.
- SEVERE - FIXED (2026-07-19). Native identity-acquisition gap. Windows scan evidence
  could omit an NTFS file identity while fresh observation supplied one, falsely
  refusing sync and disabling correspondence moves. Cause: extended-path
  `DirEntry.stat()` could report inode zero; fixed with an exact-path fallback
  on stable-ID volumes and absent-identity-as-absent-evidence matching.

## PLANNER

### M1 Hardening

- MODERATE - FIXED (2026-08-10). Planner/executor policy drift. Planner
  compared the complete Windows attribute bitmap while executor intentionally
  managed only readonly, hidden, system, and not-content-indexed. ARCHIVE or
  TEMPORARY drift could therefore schedule a content UPDATE on every rerun,
  including repeated trash backups, without ever converging. Fixed with one
  core-owned managed-attribute mask consumed by planner and executor; raw
  attributes remain evidence, every managed-bit drift still updates, and a
  native ARCHIVE-only execute/rescan converges to `NOOP`.

### M0 hardening

- MODERATE - FIXED (2026-07-21). Operation-kind overloading. A
  metadata-equal case-only filename change was represented as `update`, causing
  a full source-content rewrite, capacity charge, and trash backup merely to
  change directory-entry spelling. Cause: the first propagation seam reused the
  only operation that could publish a requested spelling; fixed with an
  explicit zero-byte `recase` operation that carries old/new spellings, uses a
  same-volume non-replacing rename, preserves identity/metadata, records updated
  correspondence, and creates no trash entry.
- MODERATE - FIXED (2026-07-21). Advisory/blocker conflation. A
  case-only source/target filename pair blocked even when source metadata had
  changed, suppressing the required update; canonically equivalent NFC/NFD
  spellings were instead misclassified as unrelated copy/removal work with no
  warning. Cause: the initial casing fix made spelling visibility a conflict
  gate, and planning compared only Windows case keys without a conservative
  canonical-equivalence advisory pass; fixed by retaining normal update/no-op
  semantics under typed non-blocking reasons, preserving target spelling by
  default, adding a fingerprinted source-basename recasing option (available
  through the semantic-settings facade, with no dedicated CLI/UI control), and
  pairing only unique same-parent NFC-equivalent files that are not already
  exact matches.
- MODERATE - FIXED (2026-07-20). Case-folded identity conflation. A pair
  such as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever,
  hiding unconverged target casing. Cause: Windows-key grouping discarded target
  spelling before no-op classification; initially made visible with a typed
  `case_mismatch` blocker. The 2026-07-21 follow-up above retains that typed
  visibility without suppressing content work.
- MODERATE - FIXED (2026-07-19). Incomplete equality predicate. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
