# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Each entry records `SEVERITY - STATUS (YYYY-MM-DD)`, a failure-specific
category, the observed behavior and consequence, `Cause: why`, and, when fixed,
the corrective change. Write it as one compact paragraph rather than labels for
symptom, cause, and fix.

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.
- **Category** names the causal failure boundary (for example, `TOCTOU sampling
  race`), not a milestone, review gate, test outcome, or broad result such as
  availability or convergence.

Entries are module/function-first, not a project-wide timeline: `##` headings
are owning modules or feature boundaries, and `###` headings are their
functional scope or delivery phase. Add an entry under the module/function that
owns the behavior, retain its relevant subheading, and keep entries newest first
within that section. Do not add date-based sections or append unrelated entries
to a global chronological list. Target 6–12 rendered lines per entry; include
only the test conditions or residual threat boundary needed to explain the
defect, and move implementation-level test choreography out of the log.

---

## EXECUTOR

### M1 Hardening

- MINOR - FIXED (2026-08-06). TOCTOU sampling race. The one-core
  `test_b2_hash_fifo_independently_plateaus_at_32_items` intermittently failed
  although both FIFOs remained capped at 32 items. Cause: separately sampled
  full queues can momentarily straddle a worker's get/put, letting the first
  sample precede reader quiescence. Fixed by freezing three stable full samples
  before signaling and proving no reader advance after two blocked-enqueue
  checkpoints. Delay stress and an injected hidden read validate the gate;
  production queue-cap behavior passed throughout.
- SEVERE - FIXED (2026-08-04). UPDATE target replacement TOCTOU. An external
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
- MODERATE - FIXED (2026-08-04). Backup ownership verification. UPDATE
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
- MODERATE - FIXED (2026-08-04). Copied-backup repair retry. A copied UPDATE
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
- MODERATE - FIXED (2026-08-04). Post-publication target drift. A sharing retry
  could record COPY, UPDATE, or MOVE_UPDATE success for a same-size/same-mtime
  target replaced during backoff. Cause: resumed continuations reused prepared
  or cached stats before metadata, durability, attestation, and recording.
  Fixed with one entry guard that re-stats the target, compares cached evidence
  when available, otherwise binds kind/size and stable identity, and settles
  detectable replacement or absence as `target-drift` without success evidence.
  First-pass execution adds no stat; replacement after the guard, or before a
  cache on an identity-weak volume, remains outside this non-locking guarantee.
- SEVERE - FIXED (2026-08-03). Cancellation publication attribution. Cancel
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
- SEVERE - FIXED (2026-08-03). Canceled-publish settlement. Cancellation after
  a published byte operation
  could label COPY or UPDATE `CANCELED` even though the new target was already
  live, omit the mutation from item detail, and leave recording falsely `OK`.
  Cause: the blanket cancel unwind never consulted operation-local retry state;
  fixed by classifying prepared versus published state before temp cleanup,
  settling a published-but-unfinished operation `FAILED` with the typed
  `canceled-after-publish` reason and explicit durable-state detail, degrading
  recording, and never attaching success-only `PublishedCopyEvidence`.
- SEVERE - FIXED (2026-08-03). MOVE_UPDATE cancellation settlement. Cancellation
  during MOVE_UPDATE's durable retry
  could report `CANCELED` after the new target published, whether the old target
  was still live or had already reached trash. Cause: cancel settlement ignored
  the composite continuation; fixed by reporting the observed `new-and-old` or
  `new-and-trash` state, settling the unfinished operation `FAILED` with
  `canceled-after-publish`, degrading recording, and leaving the next reviewed
  scan/plan to converge without rollback.
- MODERATE - FIXED (2026-08-03). Cancellation backup disclosure. Cancellation
  after UPDATE created its durable
  backup but before replacement hid that retained old version from the canceled
  item's detail. Cause: cleanup considered only the staged temp and the blanket
  outcome carried no continuation facts; fixed by retaining the backup, removing
  only the owned temp, and reporting its path, backup method, and retained state.
  M1 still has no trash purge: reclamation remains with the deferred
  maintenance-session retention workflow, and cancellation never deletes the
  only recoverable old version.
- SEVERE - FIXED (2026-08-03). Retry-continuation pause. Pausing UPDATE after a
  backup, MOVE_UPDATE after publication, or COPY during metadata retry made
  resume reapply scan-time guards and reject NamiSync's own durable state.
  Cause: checkpoints unwound process-local retry state. Fixed by installing
  validated COPY/UPDATE/MOVE_UPDATE continuations at the first owned durable
  boundary, latching pause through settlement, and reusing staged bytes before
  raising `PauseRequested`. Cancellation remains immediate; policy `Stop`
  suppresses a latched pause and settles later operations as `policy-stop`.
- MODERATE - FIXED (2026-07-30). Pure-move attestation. Pure-move recording within timestamp
  granularity. A valid MOVE could rename the reviewed target and then degrade
  recording when its timestamp differed exactly from the source while still
  falling within the target volume's equality granularity. Cause: the recorder
  compared a pure rename result to source-derived intended metadata before
  checking the reviewed old-target version; fixed by making
  `prior_target_expected` the complete pure MOVE/RECASE attestation while
  retaining intended-content validation for MOVE_UPDATE.
- SEVERE - FIXED (2026-07-30). Source and rename revalidation. Pure rename and
  directory source revalidation.
  MOVE could rename a reviewed old target after the corresponding source
  subject vanished, MKDIR could create a target for a vanished source
  directory, and MOVE/RECASE recording could bless a substituted post-rename
  target with matching size/mtime. Cause: those handlers skipped the universal
  source point-of-touch guard and accepted intended metadata without binding the
  rename result to the reviewed old target identity; fixed with source guards,
  post-rename version checks, and the same defensive recorder check.
- MODERATE - FIXED (2026-07-25). Access-time metadata policy. Post-publish
  metadata repair on volumes with
  last-access updates enabled, observing a renamed file could change its access
  time and force the otherwise conditional second metadata rewrite and flush on
  every copy. Cause: executor normalized and compared access time as managed
  metadata; fixed by removing access time from executor policy while retaining
  mtime, creation-time, and standard-attribute repair.

### M0 hardening

- MODERATE - FIXED (2026-07-20). Crash-temp recovery. Temps left
  by killed or crashed runs accumulated permanently while preflight counted
  their bytes as reclaimable, leaking target capacity and potentially stranding
  a nearly-full sync. Cause: executor removed only the current run's exact
  per-operation temp, while every rerun has a new run id and scanner correctly
  ignores owned temps; fixed with one post-preflight, pre-copy exact-grammar
  sweep over preflight's touched target parents, excluding current-run files and
  `.synctrash`.
- MODERATE - FIXED (2026-07-20). Directory cleanup revalidation. Cleanup of a
  directory emptied by same-run moves or trash operations was rejected as target
  drift, preventing folder rename/removal in one run. Cause: the final guard
  compared scan-time mtime and link count that planned child removal changes;
  fixed with a cleanup matcher that validates stable metadata and treats absent
  reviewed identity as absent evidence before atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Windows directory-flush access. Every Windows
  parent-directory flush failed and warned despite successful mutations. Cause:
  `CreateFileW` requested `GENERIC_READ`, while `FlushFileBuffers` requires
  write access; fixed by requesting `GENERIC_WRITE` on the existing directory
  handle.
- MODERATE - FIXED (2026-07-19). Durable retry continuation. A transient sharing
  violation after update backup or publish restarted against the operation's own
  mutation, causing false target drift or destination occupancy. Cause: generic
  retry assumed every operation could restart; fixed by validated continuation
  from the last durable sub-step.

## DISPATCHER AND HISTORY

### M1 Hardening

- MODERATE - FIXED (2026-08-06). Sparse reliable-event pagination. Event-page
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
- MODERATE - FIXED (2026-08-06). Hub-close state ownership. A terminal close
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
- MINOR - FIXED (2026-08-05). Subscriber replay capacity. Subscribing to a hub
  whose retained replay was
  longer than one subscriber's bound produced a stream holding
  `subscriber_capacity + 1` envelopes, so the next reliable event ejected a
  consumer that had not been given a chance to drain. Cause: the truncation
  branch reserved a slot for the leading `Gap` only when a gap was already
  needed before truncating, not when truncation itself created it. Production
  sizing (128-event replay, 64-event subscriber bound) reaches this on any
  session that has emitted more events than the subscriber bound. Fixed by
  recomputing the allowance once truncation forces the gap; a regression pins
  the initial buffer at the bound.
- MODERATE - FIXED (2026-08-05). Broken audit-pump cleanup. A broken audit
  prefix stopped the pump without
  draining its bounded command queue. Each degraded terminal hub could therefore
  retain a full queue of large reliable envelopes; a timed-out flush that later
  succeeded could instead leave the degraded pump alive and idle forever. Fixed
  with an atomic queue-admission/close gate, pre-cleanup command draining with
  waiter completion and balanced task accounting, and a post-flush broken-prefix
  check plus a best-effort stop wakeup for the timeout-boundary race.
  Full-capacity blocking-cleanup, idle-wakeup, and late-flush regressions cover
  these exits.
- MODERATE - FIXED (2026-08-05). Terminal cleanup ownership. Explicit close
  could discard the terminal
  session record, store row, hub owner, and cleanup lock before audit-observer
  cleanup finished, then ignore the hub timeout; shutdown could consequently
  report complete while the only cleanup worker was still blocked. A concurrent
  close could also remove a hub between shutdown's record and hub snapshots.
  Fixed by serializing close/shutdown per session, closing the hub before
  ownership removal, retaining timed-out cleanup for retry, and snapshotting
  hub/lock pairs under the dispatcher condition.
- MODERATE - FIXED (2026-08-05). Shutdown deadline budgeting. Shutdown's shared
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
- MODERATE - FIXED (2026-08-05). Monotonic history commit time. Concurrent
  history observers could advance the
  committed sequence while regressing `last_committed_at`. Cause: commit time
  was sampled before serialized writer ownership, and wall-clock rollback was
  accepted verbatim; the first commit could also precede its RUNNING event.
  Fixed by sampling inside the owned transaction and clamping the logical commit
  timestamp to prior durability, admission, and actual start; tail finalization
  uses that same effective time.
- MODERATE - FIXED (2026-08-05). Unstarted terminal timing. Finalized queued
  cancellations fabricated an
  execution start at admission time even though their disposition was `UNRUN`.
  Cause: finalization replaced a missing observed start with `created_at`, and
  the v4 terminal constraint required every final row to have `started_at`.
  Fixed by retaining the nullable actual-start field, checking an unstarted
  terminal end against `created_at`, and returning an exact reopened terminal
  replay before validating any newly sampled end time. Queued cancellation and
  regressed-clock replay are both covered.
- MODERATE - FIXED (2026-08-05). Summary aggregation bounds. Fixed-query
  history summaries could still
  allocate one Python aggregate object for every distinct free-form item kind
  and reason, so a valid run could defeat the readback memory bound without
  decoding event JSON. Cause: the third summary query grouped all projection
  strings. Fixed with one conditional aggregate fact object per selected run;
  workflows supply finite selection/no-op predicates and retain classification
  policy while SQL returns only bounded primitive counts.
- SEVERE - FIXED (2026-08-05). History crash-window retention. History claimed
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
- MODERATE - FIXED (2026-08-05). History readback bounds. History readback was
  bounded only after
  materialization. `list_recent()` invoked the full-run getter once per run,
  and that getter selected and decoded every item, making a 50-run summary an
  N+1 query path with work and memory proportional to all selected detail.
  Fixed with fixed-query-count primitive summaries, shared live/retained fact
  classification, 1..256-row keyset item/event pages under captured durable
  watermarks, and streamed CLI detail. The unbounded full-run API was removed.
- MODERATE - FIXED (2026-08-04). Audit-pump close budget. Audit-pump close
  could spend the complete
  caller timeout waiting to enqueue its stop command and then spend the complete
  timeout again joining the worker, so the advertised shutdown allowance was
  not an end-to-end bound. Cause: queue and thread APIs each received the
  original duration. Fixed with one monotonic close deadline and recomputed
  remaining time for enqueue and join.
- MODERATE - FIXED (2026-08-04). Event-admission complexity. History event admission recalculated
  `max(event_hashes)` for every new reliable envelope, making a large result
  stream quadratic before finalization and increasing audit-backpressure risk.
  Cause: the duplicate hash map was also used as an ordered-sequence index.
  Fixed by retaining one highest-accepted-sequence scalar while preserving exact
  duplicate idempotency and conflicting/out-of-order rejection.
- MODERATE - FIXED (2026-08-03). Audit-offer isolation. Audit backpressure
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
- MODERATE - FIXED (2026-08-03). History retry budget. Shutdown allowance was
  visibly long: deriving
  every audit bound from the generic ten-second serialized-writer retry made
  worst-case service close twenty-two seconds, long enough to read as an
  unresponsive window once Stage 6 calls it during teardown. Cause: history
  finalization reused the ledger's retry bound although it is an independently
  degradable axis whose exhaustion costs one audit row rather than filesystem
  or integrity truth. Fixed by giving history its own five-second retry bound,
  which carries the derived cutoff to six seconds and service close to twelve,
  with tests pinning both the ordering and a shutdown ceiling.
- MODERATE - FIXED (2026-08-02). Finalization timeout ownership. A finalization
  that committed after its audit acknowledgement deadline delivered
  `audit=degraded` but retained `audit=ok`. Cause: the observer persisted a
  provisional result before the pump knew who owned the deadline. Fixed with an
  atomic finalization decision latch: an expired caller wins degraded truth, or
  a pump owner determines the final result. The immutable payload and its
  existing transaction now persist the decided audit axis; derived writer,
  audit, and close bounds are regression-tested in order.
- SEVERE - FIXED (2026-07-30). Pre-invocation cancellation settlement. Canceling a
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
- MODERATE - FIXED (2026-07-30). Lifecycle publication ordering. A delayed
  `StateChanged(PAUSING)` publication could be overtaken by persisted
  `PAUSED`, leaving existing and late subscribers with a regressed current
  state. Cause: record transitions were locked but their reliable events were
  emitted after releasing the transition lock; fixed with a per-session
  publication gate spanning each transition and matching state event.
- MODERATE - FIXED (2026-07-30). Subscribe-close linearization. Subscription
  could capture a terminal session hub, lose a race with explicit close, and
  then append a stream to the already-closed hub; after replay drained, the
  stream never closed. Cause: hub lookup and subscription registration were
  separate critical sections; fixed by registering under the dispatcher
  condition so either subscribe or terminal close wins completely.

## INTERFACES

### M1 Hardening

- MINOR - FIXED (2026-08-03). WebView2 prerequisite diagnosis. A missing .NET
  Framework release key was reported as missing WebView2, obscuring the actual
  .NET 4.6.2 prerequisite. Cause: the side-effect-free detector returned one
  boolean and tests omitted the absent-key state, where pywebview 6.2.1 itself
  raises `UnboundLocalError`. Fixed with one typed registry probe that reports
  .NET, WebView2, or detection-failure reasons; malformed/unreadable values
  recommend repair. Tests pin the single read, intentional upstream divergence,
  and refusal messages. Windows 11 includes .NET Framework 4.8, so this state
  is unsupported-installation diagnostics rather than a normal user path.
- MODERATE - FIXED (2026-08-01). Renderer preflight side effects. Refusing a
  missing WebView2 runtime wrote Internet Explorer feature-control keys first:
  `webview.start()` imported pywebview's MSHTML fallback before NamiSync's
  renderer check. Fixed with a read-only, pywebview-compatible registry preflight
  before `create_window`, repeated before initialization, and behavior-tested
  against the pinned upstream detector. A configured fixed runtime bypasses the
  probe; the synchronous Edge Chromium check remains defense in depth. The
  `86.0.622.0` argument is pywebview's WinForms compatibility gate, not a
  NamiSync security-patch minimum.
- SEVERE - FIXED (2026-07-31). Native-guard attachment state. Pywebview swallowed
  synchronous event-handler failures, so a failed `before_load` installer left
  dispatch closed without actionable host state and could retry after a partial
  subscription. Fixed with explicit pending/attached/failed state, one sticky
  attachment attempt, attachment-specific fail-closed dispatch, and a
  host-visible error state.
- SEVERE - FIXED (2026-07-31). New-window browser escape. Pywebview's earlier
  `NewWindowRequested` handler opened attacker-chosen URLs in the default
  browser before NamiSync could handle them. Fixed by pinning
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False` before native startup, alongside
  disabled file URLs, downloads, remote debugging, and debug mode; native popup
  and navigation guards remain defense in depth.
- MODERATE - FIXED (2026-07-31). Frame navigation containment. Top-level
  `NavigationStarting` does not observe iframes, so weakened or late CSP left no
  native frame control. Fixed by attaching `FrameNavigationStarting` and
  canceling every frame navigation while retaining first-in-`head`
  `frame-src 'none'` for initial parsing.
- MINOR - FIXED (2026-07-31). Renderer failure classification. Broad
  `WebViewException` handling mislabeled unrelated startup failures as missing
  WebView2, despite pywebview's silent MSHTML fallback; asset-origin code could
  also trim `window.real_url` incorrectly. Fixed by refusing non-Edge-Chromium
  during `initialized`, preserving unrelated exceptions, and deriving origin
  from the complete URL with `urlsplit`.
- SEVERE - FIXED (2026-07-30). UI-thread native-control access. `CoreWebView2`
  access from pywebview's setup worker could hang rather than raise a
  cross-thread error, preventing host startup. Cause: the initial mock treated
  the managed WinForms control as an ordinary Python object. Fixed with one
  idempotent synchronous `before_load` callback that accesses and subscribes
  native events only on the WinForms UI thread before exposing application calls.
- SEVERE - FIXED (2026-07-30). Native navigation authority. After canceling an
  off-origin request, WebView2 retained the packaged document but pywebview
  reported the rejected URL, indefinitely locking out the trusted-page bridge.
  Cause: the bridge treated wrapper navigation intent as committed document
  authority. Fixed with a lock-protected native `CoreWebView2.Source` snapshot,
  updated on the UI thread and read by dispatch workers without marshaling.

- MODERATE - FIXED (2026-07-30). Observer shutdown retry. A blocked sink that
  exceeded the observer join timeout was removed from retained observation
  state; after the first service close raised, the next close returned cached
  success while that observer thread could still be alive. Cause: both observer
  and service treated a failed join as an irreversible first attempt; fixed by
  retaining unjoined observations and retrying their close before the service
  may return cached success.
- MODERATE - FIXED (2026-07-30). Dependency shutdown retry. Once dispatcher
  shutdown completed, a runtime/history close exception made every later
  service close fail immediately; the runtime also discarded the store whose
  writer close failed. Cause: dispatcher completion and dependency closure
  shared one cache state, while runtime closure became irreversible before its
  dependency succeeded; fixed by caching dispatcher completion separately,
  serializing close attempts, retrying only runtime closure, and retaining the
  store/open state after a failed close.
- MODERATE - FIXED (2026-07-30). Session-receipt lifecycle race. A retry could
  replay a session after dispatcher close but before receipt removal, while the
  inverse admit/close interleaving could publish a receipt for an already
  closed session. Cause: dispatcher retention and service receipt
  lookup/publication/removal had separate synchronization; fixed with one
  lifecycle gate and retained-session checks around all three transitions.
- MODERATE - FIXED (2026-07-30). Closed-facade admission. After an incomplete
  shutdown correctly kept runtime dependencies alive for a later close retry,
  public plan, settings, inventory, integrity, history, and observation calls
  could still reach those dependencies and recreate cleared process state.
  Cause: `_closed` guarded receipt-bearing commands but not the complete domain
  facade; fixed with a shared open check while retaining only session
  status/control and shutdown cleanup after closure begins.
- MODERATE - FIXED (2026-07-30). Incomplete service-shutdown retry. A shutdown
  deadline permanently cached `complete=False` and still closed runtime/history,
  so non-cooperative workers could finalize through closed dependencies and a
  later `close()` could not recover. Cause: admission closure, dependency
  closure, and completed shutdown were one irreversible flag; fixed by keeping
  runtime open after an incomplete dispatcher result and allowing close to
  retry until completion.

## DATABASE AND INVENTORY

### M1 Hardening

- MODERATE - FIXED (2026-08-04). SQLite contention deadline. Serialized database
  contention could outlive
  its configured retry bound: waiting for the in-process writer lock was
  unbounded, each SQLite attempt retained the full busy timeout, and retry sleep
  was not capped to the remaining allowance. Cause: only the outer retry loop
  consulted its deadline. Fixed with one monotonic contention budget spanning
  local-lock acquisition, per-attempt `busy_timeout`, and backoff, including an
  explicit zero-budget single immediate attempt and no positive-budget attempt
  after expiry. Transaction work after acquiring the write lock remains outside
  this contention budget.
- SEVERE - FIXED (2026-07-30). Incomplete-scan verification authority. Non-authoritative
  full integrity verification.
  A full or stale-scope refresh with a global enumeration failure still entered
  the verifier and returned completed. Cause: the incomplete-scan refusal was
  conditional on exact selected paths; fixed by refusing every incomplete
  unbounded refresh and retaining only the fully explained exact-subject
  exception.
- MODERATE - FIXED (2026-07-30). Multi-batch read snapshot. Selecting
  more than 400 canonical keys could observe old rows in one batch and a newer
  concurrent commit in the next, producing a state that never existed. Cause:
  each bounded SELECT ran in its own autocommit snapshot; fixed with one explicit
  read transaction spanning all batches.
- MODERATE - FIXED (2026-07-30). Unsupported inventory reconciliation. A completed
  exact PATHS refresh did not mark an absent prior unsupported row missing, and
  missing-to-unsupported reappearance failed to set `reappeared_at`. Cause: the
  exact absent update filtered only `present` and unsupported upsert lacked the
  present path's transition marker; fixed by reconciling both visible states
  and applying the same reappearance transition.

## CORE AND SECURITY PROTOCOLS

### M1 Hardening

- MODERATE - FIXED (2026-07-30). Event JSON type coercion. Schema and sequence
  floats were truncated, scalar fields were stringified, and terminal
  `canceled="false"` became true. Cause: the versioned event decoder used
  Python conversion constructors instead of validating transported JSON types;
  fixed with exact integer/boolean/string decoding across envelopes, terminal
  results, phases, and nominal items.
- MODERATE - FIXED (2026-07-30). Bridge JSON parsing ambiguity. The security spike
  accepted boolean/float schema 1, duplicate keys, exponent-overflow infinity,
  and escaped lone surrogates; a handler could run on the last two before output
  validation noticed them. Cause: validation covered JSON syntax and top-level
  shape but not exact discriminators or recursive request values; fixed with
  duplicate-key rejection, exact schema typing, valid-Unicode checks, and
  recursive finite JSON validation before handler dispatch.

## WORKFLOW AND CLI

### M1 Hardening

- MODERATE - FIXED (2026-08-06). Terminal cleanup observability. CLI terminal
  cleanup and final shutdown could fail without any visible indication. Cause:
  `_close_terminal` swallowed every exception and all three command paths
  discarded the service shutdown result. Fixed by reporting expected
  cleanup-pending timeouts and unexpected failures to stderr, inspecting every
  final `ShutdownView`, and preserving the settled typed result and exit class.
- MODERATE - FIXED (2026-08-04). Cancellation result projection. Cancellation
  without post-copy verification re-raised `Canceled` after ledger settlement,
  so the generic runner replaced degraded recording truth with `recording=OK`
  and both modes could omit unexecuted-plan exclusions. Cause: only the compound
  path normalized cancellation and neither branch merged executor output with
  exclusions. Fixed by returning one typed canceled result in both modes,
  preserving `ExecutionSet` recording, merging the complete ordered item stream,
  and omitting the execute phase only when verification was not requested.

- SEVERE - FIXED (2026-07-30). Run-token custody release. A failed
  ledger open or final write while settling a paused or just-resumed execution
  left its exact run token permanently claimed in
  `LocalWorkflowRuntime._execution_started`, even though dispatcher made the
  session terminal. Cause: only successful recorder finish removed the
  process-local claim; fixed by releasing the validated exact start claim in a
  settlement `finally`, including thrown-open and degraded-finish regressions.
- MODERATE - FIXED (2026-07-30). Runtime-close linearization. One caller
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
- SEVERE - FIXED (2026-07-30). Replan generation ABA. Replacing a plan reset its
  selection revision to zero and discarded mutation receipts, so a lost
  checkbox response, Execute, or destructive confirmation formed against the
  old artifact could apply to a new artifact with identical deterministic
  operation ids. A mutation racing replacement could also report that stale
  state as applied. Cause: artifact identity changed but its concurrency epoch
  did not survive replacement; fixed by monotonically advancing revisions,
  retaining recognized gesture tombstones, checking the current artifact after
  mutation, and returning the new preview as a conflict.
- SEVERE - FIXED (2026-07-30). Irreversible-update confirmation. With
  trash-on-update disabled, typing `execute` returned a
  `confirmation-required` view that the CLI treated as an execution session,
  then crashed with `AttributeError` without updating the target. Cause: the
  facade added a two-step risk handshake without adapting the existing typed
  CLI confirmation; fixed by rendering the exact irreversible-update warning,
  forwarding the typed response as an exact boolean acknowledgement, and
  handling every named admission view defensively.
- MODERATE - FIXED (2026-07-30). Command idempotency race. Two simultaneous
  first deliveries with one plan/inventory/integrity command id could both pass
  receipt lookup and submit separate sessions; the initial closure left
  execution outside that guard, and a plan retry revalidated paths before
  finding its receipt. ID-based retries also reread mutable inventory first.
  Cause: retry protection was applied inconsistently across session-creating
  families; fixed with bounded command-id single-flight guards around every
  family, raw gesture signatures checked before mutable validation, and
  shutdown-safe receipt publication.
- MODERATE - FIXED (2026-07-30). Folder selection isolation. A single
  safety-disabled operation beneath a folder made the entire folder toggle
  raise, leaving otherwise selectable siblings inert. Cause: node expansion
  passed every descendant into the direct-operation safety validator; fixed by
  expanding folder gestures to toggleable descendants while retaining refusal
  for a disabled operation named directly.
- MODERATE - FIXED (2026-07-30). Payload-version type coercion. Inventory
  workflow version strictness.
  Inventory `2.9` and integrity `"1"` payload versions were accepted as current
  schemas. Cause: the shared decoder coerced version values with `int()`; fixed
  by requiring an exact JSON integer and the exact kind-specific version,
  including float, string, and boolean rejection coverage.
- MODERATE - FIXED (2026-07-30). Workflow/settings JSON coercion. Inventory
  and integrity continuation fields converted strings, floats, booleans, and
  nulls with `str()`/`int()`/`bool()`, while settings accepted boolean/float
  schema version 1 and duplicate keys used last-key-wins semantics. Cause:
  version checks were hardened without applying the same rule to the remaining
  persisted shape; fixed with exact field/type validation and duplicate-key
  rejection at both boundaries.
- MODERATE - FIXED (2026-07-30). Execution custody timing. Opening a
  fresh execution claimed its run token before the dispatcher entered workflow
  work, and fresh commitment/preflight refusal or exception never released it;
  pausing at the runner-entry checkpoint also failed to snapshot `started_at`,
  so later cancel settlement failed. Cause: custody was attached to adapter
  decode rather than actual/snapshotted start; fixed with lazy claim, terminal
  cleanup, and entry-checkpoint pause snapshotting.

- SEVERE - FIXED (2026-07-25). Compound run settlement. Exceptions
  during execute-result projection, continuation publication, verify phase
  entry/context creation, or verifier-result aggregation could escape after the
  recorder opened, leaving the logical ledger run unfinished; a resumed
  execute preflight refusal could also be mislabeled as fresh
  `REFUSED+UNRUN`. Cause: only the executor/verifier call itself was guarded and
  runtime discarded whether `started_at` came from a resumed payload; fixed
  with an explicit resumed bit, phase-aware exception results, and one guarded
  finish-once path for every post-entry terminal.
- MODERATE - FIXED (2026-07-25). Retained history projection. Reading
  a retained phase passed its `HistoryPhaseSnapshot` wrapper to the phase view
  and raised `AttributeError`; even without phases, the view omitted persisted
  cancellation and derived integrity/headline truth. Cause: the runtime
  projected repository wrappers as domain values and exposed an incomplete run
  view; fixed by unwrapping ordered snapshots, reconstructing the typed result,
  and routing retained classification through the same live result classifier.
- MODERATE - FIXED (2026-07-25). Adapter failure precedence. A malformed
  registration callback could be converted into a clean canceled terminal.
  Cause: dispatcher checked the already-requested cancel checkpoint before
  raising the captured adapter failure; fixed by giving the detected failure
  precedence and pinning PAUSING-drain/callback-failure races.

### M0 integration

- MODERATE - FIXED (2026-07-21). Rename review presentation. Recase rows rendered
  the source and destination as the same spelling, and move/move-update rows
  likewise omitted the old target path, so review hid the filesystem rename a
  user was approving. Cause: `PlanOperationView` discarded
  `prior_target_rel_path` and the CLI always used the source path as the
  displayed origin; fixed by retaining `prior_target_path` in the workflow read
  model and preferring it as the left side for rename-shaped operations.
- MODERATE - FIXED (2026-07-21). Plan option canonicalization. A plan-request
  payload that omitted `propagate_source_casing` decoded as false and then
  re-encoded with the field present, so one accepted payload did not have a
  byte-stable semantic round trip for an input to `policy_fingerprint`. Cause:
  the newly added flag alone used `.get(..., False)` while every neighboring
  semantic option was required; fixed by requiring the field during decode and
  retaining explicit round-trip coverage.
- SEVERE - FIXED (2026-07-20). Partial-execution safety. One blocked item or an
  incomplete scan refused the whole sync, while simply omitting blockers could
  expose target-only deletion from incomplete source evidence. Cause: workflow
  selected every operation and preflight gated the whole run; fixed with
  commitment-bound safe-subset selection, dependency quarantine, additive-only
  incomplete-scan fallback, and preflight enforcement.
- MODERATE - FIXED (2026-07-20). Plan-outcome reporting. Blocked plan
  items were absent from results and history because only selected operations
  emitted outcomes. Cause: the outcome model had no blocker state and workflow
  emitted no exclusions; fixed with `BLOCKED`, reasoned `DEFERRED` exclusions,
  itemized history rows, and a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Result formatter shadowing. Every real execution
  crashed while presenting fresh-preflight results, before mutation began.
  Cause: local `refusal_views` shadowed the formatter; fixed by using a distinct
  result variable.
- MODERATE - FIXED (2026-07-19). Plan commitment validation. A decoded plan's
  carried fingerprint was compared with its commitment without recomputing the
  content hash, allowing altered payloads to appear authorized. Cause: two
  transported fields were treated as independently derived; fixed by recomputing
  the fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Location preflight validation. Identical
  database paths or overrides inside a managed root were rejected only after
  planning and confirmation. Cause: location validation lived only on the
  execution adapter; fixed by applying it before plan admission.

## SCANNER AND PREFLIGHT

### M1 Hardening

- SEVERE - FIXED (2026-07-30). Recursive-scope normalization complexity.
  Normalizing
  sibling recursive roots compared every root with every retained root and then
  every exact path with every root; 1,000 sibling roots took about 17 seconds
  and 2,000 took about 69 seconds before dispatcher admission. Cause: repeated
  normalization inside quadratic ancestry scans; fixed with canonical-key
  ancestor-set walks whose normalization count scales with declared path depth,
  plus a deterministic complexity regression and a multi-root global
  incompleteness composition test.

### M0 integration

- MINOR - FIXED (2026-07-21). Defensive JSON encoding. Path
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

- MODERATE - FIXED (2026-07-21). Case-propagation operation cost. A
  metadata-equal case-only filename change was represented as `update`, causing
  a full source-content rewrite, capacity charge, and trash backup merely to
  change directory-entry spelling. Cause: the first propagation seam reused the
  only operation that could publish a requested spelling; fixed with an
  explicit zero-byte `recase` operation that carries old/new spellings, uses a
  same-volume non-replacing rename, preserves identity/metadata, records updated
  correspondence, and creates no trash entry.
- MODERATE - FIXED (2026-07-21). Filename-form advisory classification. A
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
- MODERATE - FIXED (2026-07-19). Standard-attribute reconciliation. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
