# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Each entry records `SEVERITY - STATUS (YYYY-MM-DD)`, then a failure-specific
category, the observed behavior and consequence, `Cause: why`, and, when fixed,
the corrective change. The behavior and fix are written in natural prose rather
than as separate labels.

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.
- **Category** names the failure boundary, not a broad outcome such as
  availability or convergence.

Entries are module/function-first, not a project-wide timeline: `##` headings
are owning modules or feature boundaries, and `###` headings are their
functional scope or delivery phase. Add an entry under the module/function that
owns the behavior, retain its relevant subheading, and keep entries newest first
within that section. Do not add date-based sections or append unrelated entries
to a global chronological list.

---

## EXECUTOR

### M1 executor refactor

- MODERATE - FIXED (2026-08-04). A post-publication sharing retry could record
  COPY, UPDATE, or MOVE_UPDATE success for a same-size/same-mtime file that
  replaced NamiSync's target during backoff. Cause: a resumed continuation
  reused its prepared or cached published stat without uniformly re-statting
  the current target before metadata, durability, attestation, and recording;
  MOVE_UPDATE covered only the cached-stat case. Fixed with one shared guard at
  the start of every attempt that entered with an already-published
  continuation. It compares the cached published version when available; before
  that stat is cached it binds kind/size plus stable identity when available
  while allowing publication-damaged mtime to be repaired. Missing or
  identity-detectable replacements settle as `target-drift` with no ledger or
  published evidence.
  Normal first-pass execution performs no additional stat. This is ordinary
  concurrent-drift detection, not adversarial locking: a same-size replacement
  before the stat cache on an identity-weak volume, and mutation after the
  guard, remain outside the safety claim.
- SEVERE - FIXED (2026-08-03). Cancel after a failed UPDATE replace could claim
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
- SEVERE - FIXED (2026-08-03). Cancellation after a published byte operation
  could label COPY or UPDATE `CANCELED` even though the new target was already
  live, omit the mutation from item detail, and leave recording falsely `OK`.
  Cause: the blanket cancel unwind never consulted operation-local retry state;
  fixed by classifying prepared versus published state before temp cleanup,
  settling a published-but-unfinished operation `FAILED` with the typed
  `canceled-after-publish` reason and explicit durable-state detail, degrading
  recording, and never attaching success-only `PublishedCopyEvidence`.
- SEVERE - FIXED (2026-08-03). Cancellation during MOVE_UPDATE's durable retry
  could report `CANCELED` after the new target published, whether the old target
  was still live or had already reached trash. Cause: cancel settlement ignored
  the composite continuation; fixed by reporting the observed `new-and-old` or
  `new-and-trash` state, settling the unfinished operation `FAILED` with
  `canceled-after-publish`, degrading recording, and leaving the next reviewed
  scan/plan to converge without rollback.
- MODERATE - FIXED (2026-08-03). Cancellation after UPDATE created its durable
  backup but before replacement hid that retained old version from the canceled
  item's detail. Cause: cleanup considered only the staged temp and the blanket
  outcome carried no continuation facts; fixed by retaining the backup, removing
  only the owned temp, and reporting its path, backup method, and retained state.
  M1 still has no trash purge: reclamation remains with the deferred
  maintenance-session retention workflow, and cancellation never deletes the
  only recoverable old version.
- SEVERE - FIXED (2026-08-03). Pause after a durable retry sub-step. UPDATE could
  pause after creating its backup but before a retried publish, MOVE_UPDATE
  could pause after publishing the new target but before trashing the old one,
  and post-publish COPY metadata retry had the same collision shape; resume then
  restarted from scan-time guards and rejected the executor's own mutation.
  Cause: retry state was process-local while checkpoints unwound it. Fixed by
  installing validated COPY/UPDATE/MOVE_UPDATE stage continuations at the first
  owned durable boundary, latching pause at retry-backoff checkpoints, reusing
  already-staged bytes through natural settlement, and only then raising
  `PauseRequested`. Cancellation still propagates immediately; policy `Stop`
  suppresses a latched pause and settles later operations `policy-stop`, while
  cancel-only checkpoints keep that status-emission sweep interruptible.
  Production retry sleeps total at most 350 ms (50 + 100 + 200); further latency
  is uncapped I/O on already-staged data, not another file copy.
- MODERATE - FIXED (2026-07-30). Pure-move recording within timestamp
  granularity. A valid MOVE could rename the reviewed target and then degrade
  recording when its timestamp differed exactly from the source while still
  falling within the target volume's equality granularity. Cause: the recorder
  compared a pure rename result to source-derived intended metadata before
  checking the reviewed old-target version; fixed by making
  `prior_target_expected` the complete pure MOVE/RECASE attestation while
  retaining intended-content validation for MOVE_UPDATE.
- SEVERE - FIXED (2026-07-30). Pure rename and directory source revalidation.
  MOVE could rename a reviewed old target after the corresponding source
  subject vanished, MKDIR could create a target for a vanished source
  directory, and MOVE/RECASE recording could bless a substituted post-rename
  target with matching size/mtime. Cause: those handlers skipped the universal
  source point-of-touch guard and accepted intended metadata without binding the
  rename result to the reviewed old target identity; fixed with source guards,
  post-rename version checks, and the same defensive recorder check.
- MODERATE - FIXED (2026-07-25). Post-publish metadata repair. On volumes with
  last-access updates enabled, observing a renamed file could change its access
  time and force the otherwise conditional second metadata rewrite and flush on
  every copy. Cause: executor normalized and compared access time as managed
  metadata; fixed by removing access time from executor policy while retaining
  mtime, creation-time, and standard-attribute repair.

### M0 hardening

- MODERATE - FIXED (2026-07-20). Orphaned temporary-file recovery. Temps left
  by killed or crashed runs accumulated permanently while preflight counted
  their bytes as reclaimable, leaking target capacity and potentially stranding
  a nearly-full sync. Cause: executor removed only the current run's exact
  per-operation temp, while every rerun has a new run id and scanner correctly
  ignores owned temps; fixed with one post-preflight, pre-copy exact-grammar
  sweep over preflight's touched target parents, excluding current-run files and
  `.synctrash`.
- MODERATE - FIXED (2026-07-20). Metadata state validation. Cleanup of a
  directory emptied by same-run moves or trash operations was rejected as target
  drift, preventing folder rename/removal in one run. Cause: the final guard
  compared scan-time mtime and link count that planned child removal changes;
  fixed with a cleanup matcher that validates stable metadata and treats absent
  reviewed identity as absent evidence before atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Platform API permission. Every Windows
  parent-directory flush failed and warned despite successful mutations. Cause:
  `CreateFileW` requested `GENERIC_READ`, while `FlushFileBuffers` requires
  write access; fixed by requesting `GENERIC_WRITE` on the existing directory
  handle.
- MODERATE - FIXED (2026-07-19). Idempotency failure. A transient sharing
  violation after update backup or publish restarted against the operation's own
  mutation, causing false target drift or destination occupancy. Cause: generic
  retry assumed every operation could restart; fixed by validated continuation
  from the last durable sub-step.

## DISPATCHER AND HISTORY

### M1 integrated adversarial review

- MODERATE - FIXED (2026-08-03). Audit backpressure coupled to finalization.
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
- MODERATE - FIXED (2026-08-03). Shutdown allowance visibly long. Deriving
  every audit bound from the generic ten-second serialized-writer retry made
  worst-case service close twenty-two seconds, long enough to read as an
  unresponsive window once Stage 6 calls it during teardown. Cause: history
  finalization reused the ledger's retry bound although it is an independently
  degradable axis whose exhaustion costs one audit row rather than filesystem
  or integrity truth. Fixed by giving history its own five-second retry bound,
  which carries the derived cutoff to six seconds and service close to twelve,
  with tests pinning both the ordering and a shutdown ceiling.
- MODERATE - FIXED (2026-08-02). Audit timeout parity. A history finalization
  that commits after the audit acknowledgement deadline leaves the delivered
  immutable terminal at `audit=degraded` while the retained history row says
  `audit=ok`. Cause: `HistoryObserver.finalize` persists the provisional OK
  value before the audit pump knows whether acknowledgement met its deadline.
  Fixed with one atomic decision latch on the finalization command: the caller
  wins an expired cutoff and any late row carries that degraded axis, while a
  pump that claimed ownership first makes the caller wait for its actual
  success or failure. History now persists the decided `result.audit` value
  inside the existing immutable payload and transaction; no schema, version, or
  corrective write was added. The 2026-08-03 hardening derives the production
  audit cutoff and the service-close allowance from the history writer's retry
  bound rather than from independent literals, with tests pinning the ordering.
- SEVERE - FIXED (2026-07-30). Resumed pre-invocation cancellation. Canceling a
  paused execution just after resume published RUNNING but before
  `invocation.run()` produced a generic canceled terminal while leaving runtime
  custody and the ledger run unfinished. Cause: the dispatcher's initial
  checkpoint bypassed the registration-owned cancellation settlement for an
  already-started attempt; fixed by routing that race through the retained
  payload settlement before terminal publication.
- SEVERE - FIXED (2026-07-30). Audit construction failure isolation. A corrupt
  or unwritable history database raised from the observer factory before the
  session was admitted, preventing filesystem and ledger work even though
  history is an independent axis. Cause: admission isolated observer delivery
  failures but not factory/open failures; fixed with a degraded-audit sentinel
  that preserves admission and yields `audit=degraded`.
- MODERATE - FIXED (2026-07-30). Lifecycle event ordering. A delayed
  `StateChanged(PAUSING)` publication could be overtaken by persisted
  `PAUSED`, leaving existing and late subscribers with a regressed current
  state. Cause: record transitions were locked but their reliable events were
  emitted after releasing the transition lock; fixed with a per-session
  publication gate spanning each transition and matching state event.
- MODERATE - FIXED (2026-07-30). Subscribe/close stream orphan. Subscription
  could capture a terminal session hub, lose a race with explicit close, and
  then append a stream to the already-closed hub; after replay drained, the
  stream never closed. Cause: hub lookup and subscription registration were
  separate critical sections; fixed by registering under the dispatcher
  condition so either subscribe or terminal close wins completely.

## INTERFACES

### M1 Stage 6 host reality spike

- MINOR - FIXED (2026-08-03). Prerequisite misdiagnosis and an overstated
  parity claim. An absent .NET Framework release key made the host report that
  Microsoft Edge WebView2 Runtime needed installing, when the actual missing
  prerequisite was .NET 4.6.2; the same state is also the one place the
  side-effect-free mirror deliberately diverges from pywebview 6.2.1, whose
  `_is_chromium` raises `UnboundLocalError` from a `finally` that closes a
  never-bound `net_key`. Cause: the detector reported one boolean, and the
  parity tests covered an outdated .NET release but never an absent key. Fixed
  with an explicit `missing_dotnet_framework` query and its own install
  message, a documented divergence in the mirror, and regressions pinning both
  the divergence and the message each refusal chooses. Windows 11 ships .NET
  Framework 4.8 in-box, so the state is not reachable on a supported
  installation.
- MODERATE - FIXED (2026-08-01). Missing-WebView2 refusal changed the user's
  registry before reporting that the required renderer was unavailable.
  Pywebview selected its Windows backend during `webview.start()` and imported
  MSHTML as its fallback; the MSHTML module then created and wrote Internet
  Explorer feature-control keys before NamiSync's `initialized` renderer check
  could run. Fixed with a read-only WebView2 runtime registry preflight that the
  host must run before `create_window` and that `start_edge_chromium` repeats
  before pywebview initialization. The 2026-08-03 hardening moves the complete
  pywebview-compatible registry plan into one side-effect-free module and
  behavior-checks it against the pinned upstream detector, including x86's
  plain HKLM path and the upstream version helper's real behavior. The
  `86.0.622.0` argument is preserved because it is pywebview 6.2.1's WinForms
  compatibility gate, not as a NamiSync security-patch minimum. A configured
  fixed runtime bypasses the registry probe, while the synchronous renderer
  check remains defense in depth and gates the host initialization callback.
- SEVERE - FIXED (2026-07-30). Off-thread native-control deadlock.
  `CoreWebView2` access from pywebview's setup worker could hang instead of
  raising a cross-thread error, preventing host startup. Cause: the initial
  mock treated the managed WinForms control like an ordinary Python object;
  fixed by registering one idempotent synchronous `before_load` callback that
  reaches the native control and subscribes its events only on the WinForms UI
  thread before application calls are exposed.
- SEVERE - FIXED (2026-07-30). Trusted-page bridge lockout after canceled
  navigation. WebView2 retained the packaged document after canceling an
  off-origin request, but pywebview's managed `Source` and
  `get_current_url()` reported the rejected target, so the independent origin
  check would reject the still-trusted page indefinitely. Cause: the bridge
  treated wrapper navigation intent as committed native document authority;
  fixed with a lock-protected snapshot of native `CoreWebView2.Source` updated
  on the UI thread and read without marshaling by concurrent dispatch workers.
- SEVERE - FIXED (2026-07-31). Invisible native-guard attachment failure.
  Pywebview logs and swallows exceptions from synchronous event handlers, so a
  failed `before_load` installer left dispatch closed but gave the host no
  actionable state and could retry after a partial subscription. Fixed with
  explicit pending/attached/failed state, one sticky attachment attempt,
  attachment-specific fail-closed dispatch, and host-visible error state.
- SEVERE - FIXED (2026-07-31). New-window system-browser escape. Pywebview's
  own `NewWindowRequested` handler is subscribed before NamiSync's and opened
  attacker-chosen URLs in the user's default browser before the later native
  handler could mark the request handled. Fixed by pinning
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False` before native startup, alongside
  disabled file URLs, downloads, remote debugging, and debug mode; the native
  popup and navigation guards remain defense in depth. The composed handler
  order is covered: pywebview's redirect into the current view reaches the
  native navigation guard, which cancels it while the packaged document and
  bridge remain usable.
- MODERATE - FIXED (2026-07-31). Frame navigation depended only on document
  CSP. Top-level `NavigationStarting` does not observe iframe navigation, so a
  weakened or late CSP would leave no native frame control. Fixed by attaching
  `FrameNavigationStarting` and canceling every frame navigation, while
  retaining first-in-`head` `frame-src 'none'` for initial parsing.
- MINOR - FIXED (2026-07-31). Renderer startup misdiagnosis and fragile asset
  origin derivation. Every exception merely named `WebViewException` was
  rewritten as a missing-WebView2 error even though pywebview silently falls
  back to MSHTML when the runtime is absent; future host code was also likely
  to trim `window.real_url` incorrectly. Fixed by explicitly refusing a
  non-Edge-Chromium renderer during `initialized`, preserving unrelated
  startup exceptions, and deriving the exact origin from the complete URL with
  `urlsplit`.

### M1 integrated adversarial review

- MODERATE - FIXED (2026-07-30). Observer-close retry. A blocked sink that
  exceeded the observer join timeout was removed from retained observation
  state; after the first service close raised, the next close returned cached
  success while that observer thread could still be alive. Cause: both observer
  and service treated a failed join as an irreversible first attempt; fixed by
  retaining unjoined observations and retrying their close before the service
  may return cached success.
- MODERATE - FIXED (2026-07-30). Dependency-close retry. Once dispatcher
  shutdown completed, a runtime/history close exception made every later
  service close fail immediately; the runtime also discarded the store whose
  writer close failed. Cause: dispatcher completion and dependency closure
  shared one cache state, while runtime closure became irreversible before its
  dependency succeeded; fixed by caching dispatcher completion separately,
  serializing close attempts, retrying only runtime closure, and retaining the
  store/open state after a failed close.
- MODERATE - FIXED (2026-07-30). Session-receipt lifetime races. A retry could
  replay a session after dispatcher close but before receipt removal, while the
  inverse admit/close interleaving could publish a receipt for an already
  closed session. Cause: dispatcher retention and service receipt
  lookup/publication/removal had separate synchronization; fixed with one
  lifecycle gate and retained-session checks around all three transitions.
- MODERATE - FIXED (2026-07-30). Closed-facade boundary. After an incomplete
  shutdown correctly kept runtime dependencies alive for a later close retry,
  public plan, settings, inventory, integrity, history, and observation calls
  could still reach those dependencies and recreate cleared process state.
  Cause: `_closed` guarded receipt-bearing commands but not the complete domain
  facade; fixed with a shared open check while retaining only session
  status/control and shutdown cleanup after closure begins.
- MODERATE - FIXED (2026-07-30). Incomplete service shutdown. A shutdown
  deadline permanently cached `complete=False` and still closed runtime/history,
  so non-cooperative workers could finalize through closed dependencies and a
  later `close()` could not recover. Cause: admission closure, dependency
  closure, and completed shutdown were one irreversible flag; fixed by keeping
  runtime open after an incomplete dispatcher result and allowing close to
  retry until completion.

## DATABASE AND INVENTORY

### M1 integrated adversarial review

- SEVERE - FIXED (2026-07-30). Non-authoritative full integrity verification.
  A full or stale-scope refresh with a global enumeration failure still entered
  the verifier and returned completed. Cause: the incomplete-scan refusal was
  conditional on exact selected paths; fixed by refusing every incomplete
  unbounded refresh and retaining only the fully explained exact-subject
  exception.
- MODERATE - FIXED (2026-07-30). Torn multi-batch inventory read. Selecting
  more than 400 canonical keys could observe old rows in one batch and a newer
  concurrent commit in the next, producing a state that never existed. Cause:
  each bounded SELECT ran in its own autocommit snapshot; fixed with one explicit
  read transaction spanning all batches.
- MODERATE - FIXED (2026-07-30). Unsupported-row reconciliation. A completed
  exact PATHS refresh did not mark an absent prior unsupported row missing, and
  missing-to-unsupported reappearance failed to set `reappeared_at`. Cause: the
  exact absent update filtered only `present` and unsupported upsert lacked the
  present path's transition marker; fixed by reconciling both visible states
  and applying the same reappearance transition.

## CORE AND SECURITY PROTOCOLS

### M1 integrated adversarial review

- MODERATE - FIXED (2026-07-30). Coercive event decoding. Schema and sequence
  floats were truncated, scalar fields were stringified, and terminal
  `canceled="false"` became true. Cause: the versioned event decoder used
  Python conversion constructors instead of validating transported JSON types;
  fixed with exact integer/boolean/string decoding across envelopes, terminal
  results, phases, and nominal items.
- MODERATE - FIXED (2026-07-30). Bridge JSON ambiguity. The security spike
  accepted boolean/float schema 1, duplicate keys, exponent-overflow infinity,
  and escaped lone surrogates; a handler could run on the last two before output
  validation noticed them. Cause: validation covered JSON syntax and top-level
  shape but not exact discriminators or recursive request values; fixed with
  duplicate-key rejection, exact schema typing, valid-Unicode checks, and
  recursive finite JSON validation before handler dispatch.

## WORKFLOW AND CLI

### M1 Stage 5.5 adversarial closure

- SEVERE - FIXED (2026-07-30). Canceled-settlement custody release. A failed
  ledger open or final write while settling a paused or just-resumed execution
  left its exact run token permanently claimed in
  `LocalWorkflowRuntime._execution_started`, even though dispatcher made the
  session terminal. Cause: only successful recorder finish removed the
  process-local claim; fixed by releasing the validated exact start claim in a
  settlement `finally`, including thrown-open and degraded-finish regressions.
- MODERATE - FIXED (2026-07-30). Concurrent workflow-runtime close. One caller
  could mark the runtime closed and block in history-store close; a second
  caller then returned success before the first failed and reopened the runtime.
  Cause: the state lock protected flags but not the dependency-close attempt;
  fixed with a runtime-local close gate that serializes failure and retry.
- SEVERE - FIXED (2026-07-30). Resumed-run ledger settlement. A coherently
  tampered execute/verify continuation was correctly refused before domain work,
  but the refusal tried to reopen recording from the tampered selection. The
  recorder raised a run-token input conflict and left the original ledger run
  unfinished. Cause: resume-failure settlement reused the fresh/open recording
  path even though an earlier continuation had already established the run;
  fixed with a custody-bound finish-existing-run dependency, strict
  same-runtime start-token validation, and real dispatcher plus real-ledger
  pause/resume regressions.
- SEVERE - FIXED (2026-07-30). Replan intent ABA. Replacing a plan reset its
  selection revision to zero and discarded mutation receipts, so a lost
  checkbox response, Execute, or destructive confirmation formed against the
  old artifact could apply to a new artifact with identical deterministic
  operation ids. A mutation racing replacement could also report that stale
  state as applied. Cause: artifact identity changed but its concurrency epoch
  did not survive replacement; fixed by monotonically advancing revisions,
  retaining recognized gesture tombstones, checking the current artifact after
  mutation, and returning the new preview as a conflict.
- SEVERE - FIXED (2026-07-30). Irreversible-update CLI admission. With
  trash-on-update disabled, typing `execute` returned a
  `confirmation-required` view that the CLI treated as an execution session,
  then crashed with `AttributeError` without updating the target. Cause: the
  facade added a two-step risk handshake without adapting the existing typed
  CLI confirmation; fixed by rendering the exact irreversible-update warning,
  forwarding the typed response as an exact boolean acknowledgement, and
  handling every named admission view defensively.
- MODERATE - FIXED (2026-07-30). Concurrent retry admission. Two simultaneous
  first deliveries with one plan/inventory/integrity command id could both pass
  receipt lookup and submit separate sessions; the initial closure left
  execution outside that guard, and a plan retry revalidated paths before
  finding its receipt. ID-based retries also reread mutable inventory first.
  Cause: retry protection was applied inconsistently across session-creating
  families; fixed with bounded command-id single-flight guards around every
  family, raw gesture signatures checked before mutable validation, and
  shutdown-safe receipt publication.
- MODERATE - FIXED (2026-07-30). Mixed folder selection. A single
  safety-disabled operation beneath a folder made the entire folder toggle
  raise, leaving otherwise selectable siblings inert. Cause: node expansion
  passed every descendant into the direct-operation safety validator; fixed by
  expanding folder gestures to toggleable descendants while retaining refusal
  for a disabled operation named directly.
- MODERATE - FIXED (2026-07-30). Inventory workflow version strictness.
  Inventory `2.9` and integrity `"1"` payload versions were accepted as current
  schemas. Cause: the shared decoder coerced version values with `int()`; fixed
  by requiring an exact JSON integer and the exact kind-specific version,
  including float, string, and boolean rejection coverage.
- MODERATE - FIXED (2026-07-30). Workflow and settings JSON coercion. Inventory
  and integrity continuation fields converted strings, floats, booleans, and
  nulls with `str()`/`int()`/`bool()`, while settings accepted boolean/float
  schema version 1 and duplicate keys used last-key-wins semantics. Cause:
  version checks were hardened without applying the same rule to the remaining
  persisted shape; fixed with exact field/type validation and duplicate-key
  rejection at both boundaries.
- MODERATE - FIXED (2026-07-30). Pre-recording execution custody. Opening a
  fresh execution claimed its run token before the dispatcher entered workflow
  work, and fresh commitment/preflight refusal or exception never released it;
  pausing at the runner-entry checkpoint also failed to snapshot `started_at`,
  so later cancel settlement failed. Cause: custody was attached to adapter
  decode rather than actual/snapshotted start; fixed with lazy claim, terminal
  cleanup, and entry-checkpoint pause snapshotting.

### M1 post-execution integration

- SEVERE - FIXED (2026-07-25). Compound ledger-run settlement. Exceptions
  during execute-result projection, continuation publication, verify phase
  entry/context creation, or verifier-result aggregation could escape after the
  recorder opened, leaving the logical ledger run unfinished; a resumed
  execute preflight refusal could also be mislabeled as fresh
  `REFUSED+UNRUN`. Cause: only the executor/verifier call itself was guarded and
  runtime discarded whether `started_at` came from a resumed payload; fixed
  with an explicit resumed bit, phase-aware exception results, and one guarded
  finish-once path for every post-entry terminal.
- MODERATE - FIXED (2026-07-25). Retained compound history projection. Reading
  a retained phase passed its `HistoryPhaseSnapshot` wrapper to the phase view
  and raised `AttributeError`; even without phases, the view omitted persisted
  cancellation and derived integrity/headline truth. Cause: the runtime
  projected repository wrappers as domain values and exposed an incomplete run
  view; fixed by unwrapping ordered snapshots, reconstructing the typed result,
  and routing retained classification through the same live result classifier.
- MODERATE - FIXED (2026-07-25). Canceled-settlement adapter failure. A malformed
  registration callback could be converted into a clean canceled terminal.
  Cause: dispatcher checked the already-requested cancel checkpoint before
  raising the captured adapter failure; fixed by giving the detected failure
  precedence and pinning PAUSING-drain/callback-failure races.

### M0 integration

- MODERATE - FIXED (2026-07-21). Rename plan presentation. Recase rows rendered
  the source and destination as the same spelling, and move/move-update rows
  likewise omitted the old target path, so review hid the filesystem rename a
  user was approving. Cause: `PlanOperationView` discarded
  `prior_target_rel_path` and the CLI always used the source path as the
  displayed origin; fixed by retaining `prior_target_path` in the workflow read
  model and preferring it as the left side for rename-shaped operations.
- MODERATE - FIXED (2026-07-21). Fingerprinted option decoding. A plan-request
  payload that omitted `propagate_source_casing` decoded as false and then
  re-encoded with the field present, so one accepted payload did not have a
  byte-stable semantic round trip for an input to `policy_fingerprint`. Cause:
  the newly added flag alone used `.get(..., False)` while every neighboring
  semantic option was required; fixed by requiring the field during decode and
  retaining explicit round-trip coverage.
- SEVERE - FIXED (2026-07-20). Safe partial execution. One blocked item or an
  incomplete scan refused the whole sync, while simply omitting blockers could
  expose target-only deletion from incomplete source evidence. Cause: workflow
  selected every operation and preflight gated the whole run; fixed with
  commitment-bound safe-subset selection, dependency quarantine, additive-only
  incomplete-scan fallback, and preflight enforcement.
- MODERATE - FIXED (2026-07-20). Execution outcome reporting. Blocked plan
  items were absent from results and history because only selected operations
  emitted outcomes. Cause: the outcome model had no blocker state and workflow
  emitted no exclusions; fixed with `BLOCKED`, reasoned `DEFERRED` exclusions,
  itemized history rows, and a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Result presentation crash. Every real execution
  crashed while presenting fresh-preflight results, before mutation began.
  Cause: local `refusal_views` shadowed the formatter; fixed by using a distinct
  result variable.
- MODERATE - FIXED (2026-07-19). Plan integrity validation. A decoded plan's
  carried fingerprint was compared with its commitment without recomputing the
  content hash, allowing altered payloads to appear authorized. Cause: two
  transported fields were treated as independently derived; fixed by recomputing
  the fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Configuration preflight validation. Identical
  database paths or overrides inside a managed root were rejected only after
  planning and confirmation. Cause: location validation lived only on the
  execution adapter; fixed by applying it before plan admission.

## SCANNER AND PREFLIGHT

### M1 Stage 5.5 recursive scope

- SEVERE - FIXED (2026-07-30). Multi-root scope admission cost. Normalizing
  sibling recursive roots compared every root with every retained root and then
  every exact path with every root; 1,000 sibling roots took about 17 seconds
  and 2,000 took about 69 seconds before dispatcher admission. Cause: repeated
  normalization inside quadratic ancestry scans; fixed with canonical-key
  ancestor-set walks whose normalization count scales with declared path depth,
  plus a deterministic complexity regression and a multi-root global
  incompleteness composition test.

### M0 integration

- MINOR - FIXED (2026-07-21). Defensive JSON encoding consistency. Path
  validation prevented unpaired surrogates from reaching ledger/history
  records, but ledger idempotency hashing, history hashing/detail storage, and
  opaque workflow payload encoding would still raise if a malformed code unit
  arrived through free-form detail or a future relaxed boundary. Cause: only
  canonical plan JSON used the defensive final UTF-8 encoding rule; fixed by
  applying the same valid-Unicode-compatible backslash escaping at all three
  module boundaries and round-tripping hostile history detail in tests.
- SEVERE - FIXED (2026-07-20). Unsafe filename isolation. One NTFS, SMB,
  archive, or WSL-originated name outside NamiSync's relative-path contract
  could abort planning; an unpaired surrogate could later crash ID or fingerprint
  encoding. Cause: the walker normalized untrusted names too early, validation
  admitted surrogates, and canonical JSON required UTF-8; fixed with pre-use
  validation, typed escaped evidence, incomplete-scan isolation, surrogate
  rejection, and compatible serializer hardening.
- SEVERE - FIXED (2026-07-19). File identity acquisition. Windows scan evidence
  could omit an NTFS file identity while fresh observation supplied one, falsely
  refusing sync and disabling correspondence moves. Cause: extended-path
  `DirEntry.stat()` could report inode zero; fixed with an exact-path fallback
  on stable-ID volumes and absent-identity-as-absent-evidence matching.

## PLANNER

### M0 hardening

- MODERATE - FIXED (2026-07-21). Opt-in casing propagation cost. A
  metadata-equal case-only filename change was represented as `update`, causing
  a full source-content rewrite, capacity charge, and trash backup merely to
  change directory-entry spelling. Cause: the first propagation seam reused the
  only operation that could publish a requested spelling; fixed with an
  explicit zero-byte `recase` operation that carries old/new spellings, uses a
  same-volume non-replacing rename, preserves identity/metadata, records updated
  correspondence, and creates no trash entry.
- MODERATE - FIXED (2026-07-21). Filename-form advisory execution. A
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
- MODERATE - FIXED (2026-07-20). Case-sensitive name reconciliation. A pair
  such as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever,
  hiding unconverged target casing. Cause: Windows-key grouping discarded target
  spelling before no-op classification; initially made visible with a typed
  `case_mismatch` blocker. The 2026-07-21 follow-up above retains that typed
  visibility without suppressing content work.
- MODERATE - FIXED (2026-07-19). File attribute reconciliation. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
