# M1 Bridge and Presentation Contract

**Standing.** This document is the normative authority for the M1 bridge seam:
facade-to-frontend envelopes, command and revision contracts, event/terminal
semantics, presentation data ownership, and the BR-G acceptance gates.
`DEFENSE.md`, `FEATURES.md`, and `ARCHITECTURE.md` outrank it for defense,
product behavior, and cross-system architecture. `M1_PLAN.md` owns milestone
decisions; `M1_SHELL.md` owns host/package sequencing and SH-G gates; and
`DESKTOP_UI.md` owns the user-facing visual contract.

**Scope.** Section 0 states the goals. The shared exact Stage 6 register after
the map centralizes schemas, limits, command rows, and cross-decision authority
ordering that cannot be defined coherently inside one DR-BR record; its
ownership table binds every subsection back to those records. Sections 1–8
retain the decisions, rationale, and rules local to one owner. Section 9 records
only deferred, rejected, and resolved dispositions. Section 10 retains the
normative BR-G gate register and the remaining M1 delivery order; a lane or
slice closes only when all applicable gates and regressions pass. Dated build
status and evidence are recorded under [M1 GUI in the changelog](../CHANGELOG.md#m1-gui).

---

## 0. Goals

Stated first because everything below is a means to one of them, and because a
decision that serves none of them is a decision to cut.

### Product goals

1. **A reviewer can see what is about to happen, at any plan size.** A directory
   rename that decomposes into ten thousand moves must stay reviewable, not
   merely renderable. This is what the node tree, move annotation, and paging
   exist for.
2. **A reviewer can change what is about to happen, precisely.** Deselection is
   dependency-correct, folder-scoped where the user thinks in folders, and never
   silently readmits something the planner refused.
3. **The interface never claims more than the backend observed.** Four truth
   axes stay separable on screen; an incomplete refresh reads as incomplete
   rather than as a clean one; a count that cannot be computed honestly is not
   shown.
4. **Hostile filesystem content is inert and layout-honest on screen.** A
   filename remains raw display data through authority and search, becomes
   visible-marker text for defended layout controls only at its final sink,
   and is never markup, a command argument, or an executable string.
5. **Nothing irreversible happens by accident, and nothing reversible is made
   annoying.** Friction is placed where an action cannot be undone, and
   deliberately withheld everywhere else.

### Engineering goals

1. **Headless authority.** Every authoritative capability the desktop uses is
   reachable at or below `interfaces/service.py`, so a test or a second Python
   adapter can drive it without a browser, and nothing that *decides* anything
   runs in the browser. DR-BR-09 deliberately places the
   flatten/window/search/anchor mechanics in `interfaces/web`: they are
   presentation-only, are tested headlessly at that boundary, and need not be
   reachable through the CLI. What must never be true is a *domain decision*
   the backend cannot make on its own.
2. **The import law survives a second interface.** Nothing in this work
   introduces an upward or sideways import, reconstructs domain structure from
   display strings, or moves path arithmetic above `workflows/`.
3. **One implementation per concept.** Two trees share one builder, two window
   consumers share one flattener, two payload kinds share one validator, plan
   and inventory share one node-identity scheme.
4. **Retry identity and view guards are command-specific.** Every receipted
   bridge gesture is safe to retry under one `command_id`. A command formed
   against a revisioned server view also carries that view's revision and
   refuses stale intent; session creation does not invent a revision, and the
   native folder picker carries neither identity.
5. **Bounded repeated work, not just bounded payloads.** A window request bounds
   its detail query, decode, and per-row allocation. The deliberately
   whole-structure inventory projection and retained-history aggregate are
   separately measured, cached or indexed as specified by DR-BR-16, and paid at
   their stated lifecycle rather than once per viewport scroll. Every supported
   ceiling has recorded time and memory numbers.
6. **No new dormant seams.** A contract lands with its first consumer, matching
   `M1_PLAN.md`'s standing rule. The only inherited exception is a version/schema
   reservation that avoids a second incompatible bump; no Stage 6 cache,
   projection, or presentation helper lands early merely to make Stage 5.5 look
   complete.

### Non-goals

Durable plan/session persistence, cross-process task visibility, history
retention, observer thread multiplexing, and concurrent file execution all
remain deferred exactly as `M1_PLAN.md` §4 leaves them. This document adds
none of them and depends on none of them.

---

## Map of this document

The first table locates the deliberately shared exact register. The second
lists each decision once under the module or layer it binds. A DR-BR record owns
its rationale and local rule; the shared register owns only the exact
cross-cutting shape or ordering identified here. A map entry locates accepted
target authority; it does not activate that target before its named checkpoint.

| Shared exact register | Owning DR-BR records | Authority centralized there |
| --- | --- | --- |
| [Epochs, scalars, and recording](#exact-epochs-scalar-classes-and-recording-views) | DR-BR-14, DR-BR-16, DR-BR-16.2, DR-BR-21, DR-BR-24, DR-BR-27 | Protocol and persistence epochs, numeric grammars, event-v5 recording truth, and production tree/diagnostic walls. |
| [Result and presentation shapes](#exact-shared-result-shapes) | DR-BR-03, DR-BR-06, DR-BR-08, DR-BR-09, DR-BR-11, DR-BR-12, DR-BR-13, DR-BR-14, DR-BR-15, DR-BR-16, DR-BR-16.1, DR-BR-17, DR-BR-18, DR-BR-19, DR-BR-20, DR-BR-21, DR-BR-22, DR-BR-24, DR-BR-27 | Exact DTOs, tree rows, overlays, limits, view revisions, and publication-stage matrix shared by those decisions. |
| [Task and authority ordering](#task-and-authority-ordering) | DR-BR-03, DR-BR-16.1, DR-BR-17, DR-BR-21, DR-BR-22, DR-BR-24, DR-BR-27 | Task/session ownership, claims, receipts, leases, epochs, pins, publication faults, retention, and close barriers. |
| [Command and retry rows](#exact-command-and-retry-rows) | DR-BR-03, DR-BR-05, DR-BR-06, DR-BR-15, DR-BR-16, DR-BR-16.1, DR-BR-17, DR-BR-18, DR-BR-19, DR-BR-20, DR-BR-21, DR-BR-22, DR-BR-24, DR-BR-27 | The Stage 6 exact command rows, payload/result variants, revision order, retry class, and error vocabulary. |
| [Location, evidence, and handoff](#location-evidence-and-handoff-policy) | DR-BR-05, DR-BR-06, DR-BR-14, DR-BR-20, DR-BR-21, DR-BR-27 | Fresh location admission, evidence acknowledgment, recording truth, and post-copy handoff rules. |

| Decision | Binds | Ruling |
| --- | --- | --- |
| [DR-BR-01](#dr-br-01--user-selection-enters-the-facade-as-a-separate-set) | Selection workflow/service | Keep user deselection distinct from safety exclusions and retain its execution provenance. |
| [DR-BR-02](#dr-br-02--reselection-closes-upward-over-the-user-set-only) | Selection workflow | Reselection closes dependencies only within the user-deselected set. |
| [DR-BR-03](#dr-br-03--selection-is-revisioned-and-ran-authority-freezes-it) | Service selection state | Revision selection, reopen it after terminal unrun authority, and freeze it permanently at the first ran result. |
| [DR-BR-04](#dr-br-04--direct-artifact-replacement-discards-selection) | Selection workflow/service | A lower-level direct artifact replacement clears deselection and advances its revision; desktop replanning creates a new immutable-plan task. |
| [DR-BR-05](#dr-br-05--four-runtime-methods-reach-the-facade) | Service facade | Lift the four inventory acknowledgment/staleness reads as typed passthroughs. |
| [DR-BR-06](#dr-br-06--location-commands-accept-opaque-ids) | Service, scanner, recorder | Resolve opaque row/folder ids server-side; freeze recursive scope and fresh location evidence under the shared command contract. |
| [DR-BR-07](#dr-br-07--scanner-ignore-contract-narrowed) | Scanner | Remove unused ignore snapshots while retaining the known filter-visibility gap. |
| [DR-BR-08](#dr-br-08--the-ui-never-computes-means-authority) | Cross-cutting UI | Keep decisions authoritative on the backend while permitting cosmetic client computation. |
| [DR-BR-09](#dr-br-09--node-trees-are-built-in-workflows-not-interfaces) | Workflow node tree | Build shared hierarchy in workflows, below presentation adapters. |
| [DR-BR-10](#dr-br-10--path-helpers-promote-to-corepathingpy) | Core pathing | Promote shared lexical path helpers unchanged into core. |
| [DR-BR-11](#dr-br-11--node-identity-is-deterministic-and-the-plan-tree-is-memoized) | Workflow node tree | Scope deterministic node ids and memoize immutable plan trees. |
| [DR-BR-12](#dr-br-12--folder-selection-is-path-scoped-and-the-tree-owns-the-scope) | Workflow node tree/selection | Derive folder selection and subtree membership from the same index. |
| [DR-BR-13](#dr-br-13--decomposed-moves-render-as-a-paired-annotation) | Plan presentation | Render decomposed moves as paired annotations, not new selection units. |
| [DR-BR-14](#dr-br-14--progress-carries-item-identity-never-a-display-path) | Core events/reporters | Carry item identity in exact event v5; retain item-free terminal recording truth and never join authority on display paths. |
| [DR-BR-15](#dr-br-15--flattened-windows-over-a-stateless-visible-sequence) | Presentation views/web | Derive one server-side visible sequence and return bounded windows. |
| [DR-BR-16](#dr-br-16--paging-bounds-payload-and-must-also-bound-work) | Views, service, database | Bound repeated work with plan memos, inventory projections, and database history pages. |
| [DR-BR-16.1](#dr-br-161--the-inventory-projections-lifecycle) | Service projection cache | Own immutable revisioned projections by opaque view id under a six-entry LRU. |
| [DR-BR-16.2](#dr-br-162--history-is-paged-at-the-database-not-after-it) | Database/history views | Keyset-page bounded history and capture committed traversal watermarks. |
| [DR-BR-17](#dr-br-17--selection-is-server-side-state-the-dom-is-disposable) | Service/web selection | Treat DOM rows as disposable views of server-owned selection. |
| [DR-BR-18](#dr-br-18--search-executes-on-the-backend) | Presentation views | Execute literal search with the server-side view parameters. |
| [DR-BR-19](#dr-br-19--autoscroll-anchors-on-the-nearest-visible-ancestor-or-self) | Presentation views | Resolve follow mode to the nearest visible ancestor-or-self. |
| [DR-BR-20](#dr-br-20--no-inventory-snapshot-token) | Inventory presentation | Re-read at causal boundaries; acknowledgment hides rows without changing counts. |
| [DR-BR-21](#dr-br-21--a-task-is-client-state-sessions-come-and-go-beneath-it) | Web task lifecycle | Let one process-live task retain named bounded review state while exact sessions attach and release beneath it. |
| [DR-BR-22](#dr-br-22--closing-a-busy-task-cancels-waits-then-closes) | Web task lifecycle | Make accepted close a visible, receipted retirement barrier that cancels, reconciles, drains, and tombstones. |
| [DR-BR-23](#dr-br-23--single-instance-activates-the-existing-window) | Desktop host | Activate the existing window instead of starting a second instance. |
| [DR-BR-24](#dr-br-24--bridge-handlers-are-concurrent-and-must-be-synchronized) | Web concurrency | Synchronize claims, leases, epochs, pins, drains, and shutdown without holding adapter locks across facade I/O. |
| [DR-BR-25](#dr-br-25--hostile-name-rendering-is-proven-in-a-real-browser) | Browser verification | Prove hostile-name sinks in installed WebView2 plus static scans. |
| [DR-BR-26](#dr-br-26--the-node-tree-is-a-pure-function) | Workflow node tree/tests | Keep hierarchy construction pure and headlessly testable. |
| [DR-BR-27](#dr-br-27--receipted-commands-are-idempotent-revisioned-view-mutations-are-guarded) | Service/web commands | Use the shared exact command table for family-specific receipts, retries, revision guards, and replay lifetimes. |
| [DR-BR-28](#dr-br-28--cosmetic-persistence-crosses-one-typed-section-channel) | Interface UI state/web commands | Freeze one section-versioned cosmetic channel without admitting semantic or session state. |

---

## Shared exact Stage 6 target register

**Status (2026-08-24): accepted but not active.** This section is the newest
target register for Slices 5-6 and early Slice 7. Each row becomes production-
active only in its named checkpoint; until then the explicitly labeled current-
source allowlist and event-v4 implementation later in this document remain
active. This is not a second decision layer and is not a blanket
precedence rule. It consolidates and supersedes only repeated exact type, wire,
command, lifetime, and ordering fragments assigned by the map above. Those
records continue to own rationale, module placement, user interaction, and any
local rule not centralized by their mapped register. Unmapped decisions are not
superseded. History UI/pagination, global-settings mutation, drag/drop,
remaining cosmetic state, cross-process task survival, GUI Break 2, and release
packaging are outside this reslice.

### Exact epochs, scalar classes, and recording views

**Decision ownership:** DR-BR-14 owns event identity and reporter meaning;
DR-BR-16 owns production serialization and retention walls; DR-BR-16.2 owns
history and data-epoch persistence; and DR-BR-21, DR-BR-24, and DR-BR-27 own
terminal custody, concurrent transport, and exact wire/retry projection
respectively.

Core events cut directly to exact v5 with no public legacy constant or v3/v4
decoder. The bridge envelope remains v1 and every live `SessionEventView`
requires nested `schema_version=5`. The process-local sync-execution payload
is exact v6; the sync-plan payload remains exact v5, and inventory and
standalone-integrity payloads remain exact v2. Its transient copy
attestations may exist only while the same live/paused compound session needs
linked verification or resume. They never enter either database, retained
task artifacts, service presentation values, or JavaScript.

The following primitive grammars are exact:

| Name | Grammar and bound |
| --- | --- |
| `HexId` | 32 lowercase hexadecimal characters |
| `TaskId` / `SlotId` / `ViewId` / `RecentId` / `PairId` | `task-`, `slot-`, `view-`, `recent-`, or `pair-` followed by `HexId` |
| `NodeId` | the fixed 37-ASCII-character spelling `node-` followed by `HexId`, matching the existing BLAKE2b-128 tree identity |
| `SafeInt` | a non-Boolean JSON integer in `0..9_007_199_254_740_991` |
| `PositiveSafeInt` | `SafeInt` greater than zero |
| `Scalar64` | JSON string matching `0|[1-9][0-9]*` whose `BigInt` value is at most `9_223_372_036_854_775_807` |
| `Digest128` | 32 lowercase hexadecimal characters |
| `Digest256` | 64 lowercase hexadecimal characters |
| `PlanFilter` | `copy`, `update`, `move`, `move_update`, `recase`, `mkdir`, `trash`, `delete`, `noop`, `blocked`, or `unsupported` |
| `InventoryFilter` | `present`, `unverified`, `verified`, `modified`, `reappeared`, `unsupported`, `missing`, `mismatched`, `error`, or `acknowledged` |
| `HandoffBlockReason` | `post-settlement-state-diverged`, `eligible-work-incomplete`, `unrecorded-evidence`, `superseded-evidence`, or `no-applicable-items` |
| `ItemRecordingReason` | `record-write-failed`, `unrecorded-mutation`, or `recording-prerequisite-failed` |
| `TaskRecordingIssueReason` | `recording-open-failed`, `final-flush-failed`, `finish-failed`, `recording-close-failed`, or `post-settlement-state-diverged` |
| `CandidateReason` | `relative`, `drive-relative`, `device-path`, `unc`, `mapped-remote`, `ads`, `wildcard`, `invalid-character`, `reserved-name`, `ambiguous-suffix`, `nul`, `invalid-unicode`, `too-long`, `repeated-separator`, `dot-component`, `missing`, `not-directory`, `reparse`, `placeholder`, `access-denied`, `unsupported-drive-type`, `unsupported-filesystem`, `unusable-volume-facts`, `offline`, `ambiguous-volume`, or `changed` |
| `ExecutionStartReason` | `scope-empty` |
| `LocationStartReason` | `candidate-changed` or `scope-empty` |

Production freezes these complete-graph walls:

| Population | Rows | Plan bytes | Inventory bytes |
| --- | ---: | ---: | ---: |
| Domain | 120,000 | 134,217,728 | 201,326,592 |
| Informational | 120,000 | 201,326,592 | 201,326,592 |

Domain means every non-informational row plus backing objects, strings, ids,
containers, indexes, and rollups; informational means the complete plan-notice
or inventory-warning graph. Shared objects are charged once, each full tree is
at most 240,000 rows, and these are production walls rather than diagnostic or
empirical targets.

Closed fields use the exact `.value` sets of `EntryKind`, `OperationKind`,
`OperationReason`, `BlockedReason`, `UnsupportedReason`, `RefusalCode`,
`Outcome`, `Provenance`, `RecordingStatus`, `ExecutionReason`,
`ExclusionReason`, `InventoryPresence`, `InventoryVerificationState`,
`VerificationInvalidationReason`, `IntegrityResult`, `IntegrityReason`,
`ReadStrategy`, `RecordDisposition`, and `ScanWarningCode`; Python and packaged
JavaScript snapshots freeze together and reject unknowns. Only explicitly named
detail/display/label/annotation/error fields are free text, and `phase` is exact
nonempty core authority. `OperationOutcomeReason` is the closed union of
`ExecutionReason` for executor-settled work, `ExclusionReason` for reviewed
skipped/deferred work, and `BlockedReason` for directly blocked work.

Sequences, bounded counts, offsets, count limits, and revisions use `SafeInt`.
Every byte, size, capacity, work, and filesystem-nanosecond value uses internal
checked `0..2^63-1` arithmetic and external `Scalar64`; Python recursively
rejects unsafe native returns and JavaScript validates canonical decimal before
`BigInt`. Opaque row identities remain strings and ledger-v4 file-identity
indexes use canonical unsigned-decimal text.

Ledger v4 and history v6 share `data_epoch=5`, contract ids
`m1-ledger-v4-event-v5-evidence-v1` and
`m1-history-v6-event-v5-recording-v1`, and history event schema 5. Any old,
mixed, one-present, markerless, or orphan-sidecar pair refuses before commands
with coordinated archive/delete guidance; there is no migration or deletion.

Event-v5 item outcomes add `recording`, `recording_reason`,
`recording_detail`, and `detail_omitted_count`; integrity outcomes share the
omission witness. `ok` requires null reason/detail; `degraded` requires an
`ItemRecordingReason` and permits at most 1,024 UTF-8 detail bytes. Ordered
`OperationResult.recording_issues` retains the first `{TaskRecordingIssueReason,
detail}` per reason under the same bound; aggregate recording is degraded iff
an item is degraded or the tuple is nonempty.

`DetailProjection` is an emitter-owned immutable snapshot with at most 32
declared primitive leaves, eight complete path leaves, 64-byte ASCII keys,
bounded tuples/strings, `SafeInt` counts, and signed-64 quantities; arbitrary or
nested objects, `Path`, nonfinite/arbitrary integers, undeclared keys, and
unbounded arrays are invalid. Outer and detail paths are complete valid Unicode
of at most 32,767 UTF-16 units. Over-limit diagnostics become null and increment
the checked omission witness, never truncate.

Event v5 uses an item-free `TerminalSummary` with
`recording_degraded_items`, `omitted_detail_count`, and the exact copied nullable
`review_fact_limit`; only that typed field maps `ResultSummary.review_refusal`.
Reliable outcomes update the compact overlay before queueing; the full result
remains only in the dispatcher terminal record through one reconciliation and
exact-session release. `MAX_RELIABLE_EVENT_CANONICAL_BYTES=1_048_576` is checked
before emitter acceptance or sequence/queue/history mutation and guarantees one
valid head fits the independent bridge-response wall.

### Exact shared result shapes

**Decision ownership:** the map above assigns each DTO family to its DR-BR
domain owner; this subsection is their one shared spelling and invariant table.

Every object below has exactly the named keys. Nullable means JSON `null`, not
absence. Free-form diagnostics are already bounded before construction.

- `SessionRef` = `{session_id:HexId, kind:"sync-plan"|"sync-execution"|
  "inventory"|"baseline"|"verify"|"rebaseline"|"post-copy-verify",
  state:"pending"|"running"|"pausing"|"paused"|"canceling"|"completed"|
  "failed"|"canceled"|"refused"}`.
- `TaskSummary` = `{task_id:TaskId, task_kind:"sync"|"inventory",
  phase:"plan"|"review"|"execute"|"inventory"|"baseline"|"verify"|
  "rebaseline"|"post-copy-verify", lifecycle:"idle"|"pending"|"running"|
  "pausing"|"paused"|"canceling"|"closing"|"completed"|"failed"|
  "canceled"|"refused", lifecycle_revision:SafeInt,
  selection_revision:SafeInt, result_revision:SafeInt,
  current_session:SessionRef|null, label:string, updated_at:string}`. `label`
  is inert display text bounded to 1,024 UTF-8 bytes.
- `ResultSummary` = `{headline:"failed"|"partial"|"refused"|"mismatch"|
  "canceled"|"verification-incomplete"|"degraded"|"all-noop"|"success",
  filesystem:"completed"|"failed"|"canceled"|"refused",
  integrity:"not-run"|"incomplete"|"modified"|"missing"|"mismatch"|
  "baselined"|"verified",recording:"ok"|"degraded",
  audit:"ok"|"degraded",disposition:"ran"|"unrun",canceled:boolean,
  bytes_done:Scalar64,bytes_total:Scalar64,error:string|null,phases:array,
  recording_degraded_items:SafeInt,recording_issues:array,
  omitted_detail_count:SafeInt,presentation_omitted_detail_count:SafeInt,
  review_refusal:ReviewFactLimitExceeded|null}`. `error` is null or at
  most 1,024 UTF-8 bytes. `phases` has 0..3 members and
  `recording_issues` has 0..5. Each phase has exactly
  `{phase:string,status:"completed"|"failed"|"canceled"|"incomplete",
  items_done:SafeInt,items_total:SafeInt|null,
  bytes_done:Scalar64,bytes_total:Scalar64|null,error:string|null}`; each issue
  has exactly `{reason:TaskRecordingIssueReason,detail:string|null}`.
- `ReviewFactLimitExceeded` has exactly
  `{reason:"review_fact_limit_exceeded",tree_kind:"plan"|"inventory",
  population:"domain"|"informational",axis:"rows"|"retained-bytes",
  row_limit:SafeInt|null,byte_limit:Scalar64|null}`. Rows use only
  `row_limit=120000`; retained bytes use only `byte_limit`, equal to
  `"134217728"` for plan/domain and `"201326592"` otherwise. Prospective
  complete-graph collection stops before the first excess with precedence
  domain rows, domain bytes, informational rows, informational bytes; the frozen
  sizer and independent validator charge shared objects once. Initial refusal
  publishes no partial artifact/view, while inventory refresh or fresh-
  execution refusal preserves the complete predecessor and replaces only its
  named summary. The limit changes neither omission axis. Its summary is
  refused/unrun, recording-ok, audit-ok-or-degraded, uncanceled, zero-byte/item/
  omission, with null error and empty phases/issues; every other summary has
  `review_refusal=null`.
- `TaskResults` = `{plan:ResultSummary|null,execution:ResultSummary|null,
  inventory:ResultSummary|null,integrity:ResultSummary|null,
  post_copy_verify:ResultSummary|null}`. A session changes only its named slot:
  plan is one-shot; execution may replace unrun but freezes at first ran;
  inventory, ordinary integrity, and manual post-copy may replace only their own
  slots after full old/new reservation. History keeps each session identity.
  The desktop renders `filesystem="refused"` plus `disposition="unrun"` as the
  generic action state “Execution did not start. Review the selection or plan
  again.” It does not expose preflight terminology or infer a more specific
  cause from those axes alone.
- `SessionEventView` = `{session_id:HexId,sequence:PositiveSafeInt,
  at:string,schema_version:5,body_type:string,body:object}`; `body_type` and
  `body` must be the exact v5 pair owned by `CORE.md`, not independently
  inferred. `SessionRecordView` = `{session_id:HexId,
  kind:SessionRef.kind,state:SessionRef.state,supports_pause:boolean,
  created_at:string,started_at:string|null,ended_at:string|null,
  result:ResultSummary|null}`. Event and record timestamps are bounded service-
  produced ISO-8601 strings; filesystem text never enters them.
- A drain update is exactly `{update_type:"event",event:SessionEventView}` or
  `{update_type:"record",record:SessionRecordView}`.
- `TaskDetail` = `{summary:TaskSummary, setup:PlanSetupOptions|null,
  plan_available:boolean, execution_available:boolean,
  inventory_available:boolean, plan_view_id:ViewId|null,
  inventory_view_id:ViewId|null, plan_view_state_revision:SafeInt,
  inventory_view_state_revision:SafeInt, projection_revision:SafeInt,
  results:TaskResults, diagnostic_bytes:Scalar64,
  omitted_detail_count:SafeInt,presentation_omitted_detail_count:SafeInt,
  publication_issue:"review-publication-protocol-failed"|null}`.
  Sync requires the exact non-null frozen `PlanSetupOptions`; inventory requires
  null Setup. Plan/inventory availability means a complete retained artifact,
  not domain completeness: initial refusal leaves false and replacement refusal
  preserves true. Execution availability means its compact generation exists;
  preflight refusal leaves false and fault disposal of its sole provisional
  generation restores false. View ids are non-null iff the available artifact
  was opened; unopened associated revisions are zero. Projection eviction keeps
  the view id/revisions for rebuild, while unavailable artifacts require null ids
  and zero revisions.
- `publication_issue` is ordinarily null. Stage/result mismatch, consumed
  `stage-rejected`, or escaped-after-stage exception atomically discards the
  stage and exact session's complete provisional overlay/index/diagnostic/
  omission/charge generation; restores prior-settled or outer-null rows;
  preserves dispatcher/history and prior named/result/omission generations plus
  `result_revision`; and fails only lifecycle. Fault kind maps to the same-named
  phase except `sync-plan→plan` and `sync-execution→execute`; `review` is invalid.
  Kind and phase agree before release; phase survives release/rehydration.
  Payload and retained-receipt handling remain first; R/D/exact-L/C remain, new
  M returns stateless `internal_error`, and close alone clears the issue. Drain
  cannot repopulate discarded rows. Issue observation first advances rail,
  panel, and mapped tree request generations (`plan|execute|post-copy-verify`
  versus `inventory|baseline|verify|rebaseline`), then clears/rebuilds the cache;
  older callbacks are inert before payload read. The renderer uses exactly
  `NamiSync could not publish this review safely. Close the task and try again.`
- `result_revision` starts at zero and increments once per atomic named result/
  terminal-frozen overlay publication, including every valid terminal and
  permitted refusal/replacement. Live outcome/progress snapshots do not advance
  it or reflow membership/count/order. A window pins one complete settled and
  one complete live generation; terminal races conflict, live-only races may be
  immediately stale. During integrity/post-copy replacement the old settled
  generation owns membership while ids in the complete new candidate index use
  the whole new object and other ids use outer null—never fallback/field merge;
  terminal freezes and swaps that generation once.
- `PlanSetupInput` and frozen `PlanSetupOptions` have the same exact keys:
  `{deletion_policy:"trash"|"additive",
  trash_on_update:boolean, filters:array-of-string, preserve_created:boolean,
  preserve_acl:boolean, preserve_ads:false,
  propagate_source_casing:boolean, linked_verify:boolean}`. Input filters are
  raw bounded entries: 0..64 entries, each 1..1,024 UTF-8 bytes and at most
  16,384 UTF-8 bytes total. The workflow, never JavaScript, rejects unsafe
  patterns and constructs the frozen canonical array by replacing `/` with
  `\`, preserving case and every other accepted code point, removing exact
  post-replacement duplicates, and sorting by Python/Unicode code-point order;
  matching remains Windows-case-insensitive domain behavior. Receipt identity
  binds both the exact raw wire intent and the resulting canonical snapshot.
- `CandidateAssessment` = `{purpose:"source"|"target"|"inventory",
  state:"accepted"|"invalid"|"missing"|"not-directory"|"reparse"|
  "placeholder"|"remote"|"unsupported-volume"|"offline"|"ambiguous"|
  "unavailable", reason:CandidateReason|null, display:string,
  volume:{serial:string,fs_type:string,label:string|null,
  relative_path:string}|null}`. Accepted requires null reason and non-null
  volume; every nonaccepted state requires null volume and exactly this total
  reason mapping:

  | State | Exact reasons |
  | --- | --- |
  | `invalid` | `relative`, `drive-relative`, `device-path`, `unc`, `ads`, `wildcard`, `invalid-character`, `reserved-name`, `ambiguous-suffix`, `nul`, `invalid-unicode`, `too-long`, `repeated-separator`, `dot-component` |
  | `missing` | `missing` |
  | `not-directory` | `not-directory` |
  | `reparse` | `reparse` |
  | `placeholder` | `placeholder` |
  | `remote` | `mapped-remote` |
  | `unsupported-volume` | `unsupported-drive-type`, `unsupported-filesystem` |
  | `offline` | `offline` |
  | `ambiguous` | `ambiguous-volume` |
  | `unavailable` | `access-denied`, `unusable-volume-facts`, `changed` |

  `changed` means fresh admission no longer matches the accepted slot identity;
  it is never projected as a newly accepted authority. `DRIVE_REMOTE` maps to
  `remote`/`mapped-remote`, while unusable native volume identity or maximum-
  component evidence maps to `unavailable`/`unusable-volume-facts`; neither is
  mislabeled as a filesystem refusal. `CandidateView` adds the
  exact `slot_id:SlotId|null` key; accepted requires a non-null slot and every
  other state requires null. A refused recent- or task-pair activation carries
  two slotless assessments, while an accepted pair carries two slotted candidate
  views.
- `SetupOptionIssue` = `{field:"filters",index:SafeInt|null,
  code:"empty"|"entry-too-large"|"total-too-large"|"absolute"|
  "device-qualified"|"nul"|"invalid-unicode"|"dot-component"}`. An options
  refusal carries 1..65 issues and no free-form parser exception. Each input
  entry contributes at most one issue, chosen by the exact precedence `empty`,
  `invalid-unicode`, `entry-too-large`, `nul`, `device-qualified`, `absolute`,
  `dot-component`. Every entry-local code
  except `total-too-large` requires the exact zero-based input index and orders
  by that index. `total-too-large` requires null index and, when present, is the
  final issue. With at most 64 inputs, the array is a complete projection.
- `PlanStartRefusal` is the exact tagged object
  `{disposition:"refused",reason:"source"|"target"|"pair"|"options",
  source:CandidateAssessment|null,
  target:CandidateAssessment|null,option_issues:[SetupOptionIssue]}`. `options`
  requires null candidates and 1..65 issues; other reasons require both fresh
  slotless assessments, no issues, and precedence source, target, pair. After
  envelope/receipt: options precede slot/claim, retention, and native probing;
  valid options then check slots/claims, reserve task memory, and freshly assess
  the pair. Thus options beat stale roots and `retention_full` beats probing.
- `InventoryStartRefusal` is the exact tagged object
  `{disposition:"refused",reason:"candidate",
  candidate:CandidateAssessment}` with one fresh slotless assessment.
  Task-reservation exhaustion returns the single fixed `retention_full` error
  for either start; it is never a second tagged-refusal spelling.
- `SelectionSummary` = `{selection_revision:SafeInt,selected_count:SafeInt,
  blocked_count:SafeInt,deferred_count:SafeInt,irreversible_count:SafeInt,
  content_bytes:Scalar64}`. Every count and the byte total describe the same
  authoritative effective selection snapshot.
- `RecentLocation` = `{recent_id:RecentId, display:string,
  resolution:"resolved"|"offline"|"missing"|"unavailable"|"ambiguous",
  volume_label:string|null, volume_relative_path:string,
  started_at:string}`. `RecentPair` = `{pair_id:PairId,
  source:RecentLocation,target:RecentLocation,started_at:string}`.
- `SetupView` = `{defaults:PlanSetupOptions,
  recent_sources:[RecentLocation],recent_targets:[RecentLocation],
  recent_pairs:[RecentPair]}` with at most five entries in each recent array.
- `LocationResolutionView` = `{state:"resolved"|"offline"|"missing"|
  "unavailable"|"ambiguous",display:string,volume_label:string|null,
  volume_relative_path:string,reason:CandidateReason|null}`. `resolved` requires
  null reason; otherwise the exact pairs are `offline`/`offline`,
  `missing`/`missing`, `ambiguous`/`ambiguous-volume`, and `unavailable` with
  `access-denied` or `unusable-volume-facts`. Candidate-only lexical, type,
  placeholder, remote, unsupported-volume, and changed reasons are invalid in
  this remembered-location projection.
- `ReviewedLocation` = `{display:string,volume_serial:string,fs_type:string,
  volume_label:string|null,volume_relative_path:string}`. It is the immutable
  location/root spelling and volume evidence reviewed with the plan, not a
  fresh location-resolution claim; `volume_serial` remains opaque text.
- `PlanReviewHeader` = `{source:ReviewedLocation,target:ReviewedLocation,
  fingerprint:Digest256,selection_digest:Digest256,
  required_bytes:Scalar64,free_bytes:Scalar64|null,
  reclaimable_temp_bytes:Scalar64|null,reviewed_preflight_ok:boolean,
  notice_count:SafeInt,presentation_omitted_detail_count:SafeInt}`.
  Roots/fingerprint and reviewed capacity/verdict are immutable initial-review
  truth; digest/required bytes are the current selection. Unavailable capacity
  is null, checked sums never clamp, and an overflowing sum makes preflight
  unavailable. Notice and presentation-omission counts describe the current
  reviewed-plus-last-complete-fresh notice generation, independent of view or
  attempt history.
- `ReviewedStat` = `{kind:EntryKind,size:Scalar64,mtime_ns:Scalar64}`.
- `PlanFilterCounts` has exactly `{all:SafeInt,copy:SafeInt,
  update:SafeInt,move:SafeInt,move_update:SafeInt,recase:SafeInt,
  mkdir:SafeInt,trash:SafeInt,delete:SafeInt,noop:SafeInt,
  blocked:SafeInt,unsupported:SafeInt}`. `InventoryFilterCounts` has exactly
  `{all:SafeInt,present:SafeInt,unverified:SafeInt,verified:SafeInt,
  modified:SafeInt,reappeared:SafeInt,unsupported:SafeInt,missing:SafeInt,
  mismatched:SafeInt,error:SafeInt,acknowledged:SafeInt}`. Each object is
  post-search/pre-filter/collapse/hide. Plan counts cover operation-bearing rows:
  `all`, exact kind, `unsupported`, or other `blocked`; structure, ghosts, and
  notices add none. Inventory counts cover subjects plus warnings but no folders:
  warnings add only all/error, facts may overlap, missing excludes acknowledged,
  and terminal-frozen integrity error joins error. Filters union; empty means no
  domain filter, and plan notices bypass filters but obey search.
- `PlanView` = `{task_id:TaskId,view_id:ViewId,
  view_state_revision:SafeInt,selection_revision:SafeInt,
  result_revision:SafeInt,search:string,filters:[PlanFilter],
  filter_counts:PlanFilterCounts,total_rows:SafeInt,visible_rows:SafeInt,
  total_operations:SafeInt,risk_count:SafeInt,header:PlanReviewHeader}`. `search` is the exact currently accepted literal query
  and is at most 65,536 UTF-8 bytes; `filters` is the unique ordered subset in
  declared `PlanFilter` order. `total_rows` is the complete canonical plan-tree
  row count before view parameters, while `visible_rows` is the exact current
  visible-sequence count after search, filters, and collapse.
  `total_operations` is the immutable canonical count of every operation-
  bearing node, including operation-bearing folders, independent of search,
  filters, collapse, selection, overlays, or informational rows.
- `InventoryView` = `{task_id:TaskId,view_id:ViewId,
  view_state_revision:SafeInt,projection_revision:SafeInt,
  result_revision:SafeInt,
  search:string,filters:[InventoryFilter],hide_acknowledged:boolean,
  filter_counts:InventoryFilterCounts,total_rows:SafeInt,
  visible_rows:SafeInt,warning_count:SafeInt,
  presentation_omitted_detail_count:SafeInt,
  complete:boolean,location:LocationResolutionView}`. The search/filter
  invariants match `PlanView`. `total_rows` is the complete canonical inventory
  projection count before hiding or view parameters; `visible_rows` is the
  exact current sequence count after acknowledged-row visibility, search,
  filters, and collapse. `warning_count` counts every warning in the canonical
  projection, independent of current visibility. New views start with
  `hide_acknowledged=true`; selecting the positive `acknowledged` filter
  requires `hide_acknowledged=false`.
- Every product-tree row contains the flattened exact `TreeRowFrame` keys
  `{node_id:NodeId,display:string,depth:SafeInt,is_container:boolean,
  visible_index:SafeInt,parent_visible_index:SafeInt|null,
  first_child_visible_index:SafeInt|null,position_in_set:PositiveSafeInt,
  set_size:PositiveSafeInt,expanded:boolean|null}`. These are the server-derived
  global visible indexes and filtered sibling facts consumed directly by the
  shipped generic renderer; an index may fall outside the returned window.
  Window rows have contiguous `visible_index` values beginning at `offset`.
  The single root has `depth=0`, null parent, and position/set size `1/1`;
  every nonroot row has a non-null preceding parent whose depth is exactly one
  less. A non-null `first_child_visible_index` names an immediate child of that
  row, not merely a later descendant, and `position_in_set <= set_size`.
  First determine whether an immediate child survives search/filter/hiding
  before collapse. If none does (or the row is a noncontainer), `expanded=null`
  and the child index is null regardless of membership in the collapsed-id
  set. Otherwise `expanded=false` exactly when that container is collapsed and
  has null child index; `expanded=true` exactly when it is expanded and
  `first_child_visible_index=visible_index+1`. The browser never reconstructs any
  of these facts from `depth`, paths, or adjacent rows.
- `ExecutionOverlay` has exactly `{outcome:Outcome|null,
  reason:OperationOutcomeReason|null,recording:"ok"|"degraded"|null,
  recording_reason:ItemRecordingReason|null,
  detail_omitted_count:SafeInt|null,progress_percent:SafeInt|null}`. Before a
  reliable item outcome, all settled fields are null; afterward `outcome`,
  `recording`, and `detail_omitted_count` are non-null and the reason fields
  obey the core item invariants. `progress_percent` is null or `0..100`.
- `IntegrityOverlay` has exactly `{result:IntegrityResult|null,
  reason:IntegrityReason|null,recording:"ok"|"degraded"|null,
  record_disposition:RecordDisposition|null,read_strategy:ReadStrategy|null,
  detail:string|null,detail_omitted_count:SafeInt|null,
  progress_percent:SafeInt|null}`. An unsettled live entry has null settled
  fields. A settled entry has non-null `result`, `recording`, and
  `detail_omitted_count`; its nullable reason, record disposition, read
  strategy, and at-most-1,024-UTF-8-byte detail obey the exact
  `IntegrityOutcome` variant. `progress_percent` is null or `0..100`.
- `PlanRollup` has exactly `{operations:SafeInt,selected:SafeInt,
  unselected:SafeInt,blocked:SafeInt,deferred:SafeInt,
  irreversible:SafeInt,content_bytes:Scalar64,
  selected_content_bytes:Scalar64}`. The four selection counts partition
  `operations`; irreversible and selected bytes cover only the current
  effective selection, while `content_bytes` covers all operations. Every
  value is computed over operation-bearing rows owned by or below the plan
  container, independent of search, filters, collapse, or move annotations. A
  folder includes its own attached singleton operation, any grouped direct
  member children, and descendants; an operation-group includes every direct
  member child.
- `InventoryRollup` has exactly `{items:SafeInt,present:SafeInt,
  unverified:SafeInt,verified:SafeInt,modified:SafeInt,mismatched:SafeInt,
  unsupported:SafeInt,missing:SafeInt,reappeared:SafeInt,
  content_bytes:Scalar64|null,content_bytes_overflow:boolean}`. It covers
  domain subject rows below the folder and excludes warnings. `items` is every
  subject; presence and verification keys match the row's typed facts;
  `missing` includes both acknowledged and unacknowledged missing subjects;
  `reappeared` matches its explicit marker; and facts may overlap.
  Acknowledgment has no rollup field and acknowledged hiding never changes the
  rollup. `content_bytes` sums every non-null subject-row size. Byte
  accumulation is checked signed-64. The
  first otherwise-valid increment that would overflow is not accepted;
  `content_bytes` becomes null and `content_bytes_overflow=true` for that folder
  and each affected ancestor. Otherwise the flag is false and the exact sum is
  non-null. No value clamps or wraps.
- `PlanRow` has exactly all `TreeRowFrame` keys plus
  `{row_kind:"folder"|"operation-group"|"operation"|"move-ghost"|"notice",
  move_peer_id:NodeId|null,
  operation_id:HexId|null,entry_kind:EntryKind|null,
  operation_kind:OperationKind|null,source_path:string|null,
  target_path:string|null,prior_target_path:string|null,
  dependency_count:SafeInt,operation_reason:OperationReason|null,
  blocked_reason:BlockedReason|null,risk:"none"|"reversible"|"irreversible"|null,
  source_expected:ReviewedStat|null,target_expected:ReviewedStat|null,
  prior_target_expected:ReviewedStat|null,intended:ReviewedStat|null,
  selection:"selected"|"unselected"|"mixed"|"disabled"|null,
  exclusion_outcome:Outcome|null,
  selection_reason:ExclusionReason|BlockedReason|null,
  content_bytes:Scalar64|null,rollup:PlanRollup|null,
  execution:ExecutionOverlay|null,
  post_copy:IntegrityOverlay|null,
  notice_kind:"scan-warning"|"preflight-refusal"|null,
  notice_stage:"review"|"execution"|null,
  notice_session_id:HexId|null,
  notice_side:"source"|"target"|null,
  notice_code:ScanWarningCode|RefusalCode|null,
  notice_path:string|null,notice_operation_id:HexId|null,
  notice_detail:string|null,annotation:string|null}`.
  Row invariants are exact:

  | `row_kind` | container / rollup | operation and selection |
  | --- | --- | --- |
  | `folder` | true / required, including all-zero | optional singleton operation; selection derives from rollup |
  | `operation-group` | true / required | null operation and exclusion facts; selection derives from rollup |
  | `operation` | false / null | exactly one operation; selection follows the exclusion table below |
  | `move-ghost` | false / null | null operation, selection, exclusion, and overlays |
  | `notice` | false / null | null operation, selection, exclusion, and overlays; notice fields required as below |

  `operation_id` is non-null exactly for one immutable `PlanOperation`: a
  singleton may inhabit its path row and each exploded member is an immediate
  operation child. Such rows require non-null kind, target, reason, risk, and
  content bytes; nullable paths/stats/blocked reason copy the operation.
  `entry_kind` is the first non-null `.kind` in order `intended`, source,
  target, prior target. A null operation makes all operation-derived fields and
  aligned overlays null and requires `dependency_count=0`; otherwise the count
  is the exact dependency count, including zero.

  | exclusion outcome / reason | operation-row selection |
  | --- | --- |
  | null / null | `selected` |
  | `skipped` / `user-deselected` | `unselected` |
  | `deferred` / `blocked-correspondence`, `blocked-dependency`, or `incomplete-scan` | `disabled` |
  | `blocked` / one `BlockedReason` | `disabled` |

  Every other or one-sided pair is structural failure; an operation is never
  mixed. Container selection is disabled for zero operations, selected when
  all selected, unselected when all unselected, disabled when all blocked or
  deferred, and mixed otherwise. Only an operation-bearing folder may carry
  its own operation's exclusion pair.

  A scan notice is review-stage with null session/operation id and exact side,
  `ScanWarningCode`, and root-as-null path. A preflight notice has a
  `RefusalCode`, optional plan-resolving operation id, and either a subjectless
  null side/path or the exact reviewed-root side and canonical path (empty is
  null). Review stage requires null session; fresh execution stage requires
  its refused session id. Detail is null, empty, or complete at most 1,024 UTF-8
  bytes. Display is exactly `[<stage>] <side-or-plan>:
  <path-or-Plan> — <code>` and excludes detail. Non-notices have all notice
  fields null.

  `move_peer_id` is only a symmetric destination-folder ↔ old-location
  ghost/annotated-folder pair; groups/members never receive it. DR-BR-13 owns
  the exact aggregate-before-suppression endpoint algorithm. Operation risk is
  server-classified (`reversible` preserves displaced state in NamiSync trash;
  `irreversible` does not; `none` has no destructive fact), and
  `risk_count` covers current effective selection only.

  `execution` is non-null on every operation-bearing row exactly after fresh
  preflight and executor admission create its aligned generation; its all-null
  body is admitted/unsettled. `post_copy` is non-null exactly for ids in the
  latest manual post-copy candidate index and is never populated by automatic
  linked verification. Both follow the generation pin/swap rules below.
  Move ghosts/notices are nonactionable; collapse accepts plan containers only.
  Group selection covers direct members, and folder selection covers its own
  operation, grouped members, and descendants, independent of the view.
- Reviewed notices are plan-immutable. While execution remains unrun, its last
  completely published attempt may replace one fresh-preflight notice set and
  refused summary atomically at one revision after charging full old/new and
  provisional overlap. Each row names that session. Row/byte overflow instead
  publishes typed `review_fact_limit`, preserves the prior complete state, and
  exposes no partial causes. The first ran terminal clears the fresh set and
  freezes execution. Reviewed preflight facts set only the initial selection;
  execution fresh-preflights the exact committed current selection after its
  revision/scope/confirmation/retention/claim gates, so the only immediate
  `ExecutionStartReason` is `scope-empty`.
- `PlanDependencyPage` = `{operation_id:HexId,offset:SafeInt,limit:SafeInt,
  total:SafeInt,dependency_ids:[HexId],next_offset:SafeInt|null}`. `limit` is
  1..256 and `offset <= total`. When `offset < total`, `dependency_ids` is the
  next nonempty prefix of at most `limit` exact operation ids and
  `next_offset=offset+dependency_ids.length` unless that equals `total`, in
  which case it is null. `offset=total` returns an empty array and null
  `next_offset`. Dependency ids are never folded into display text.
- `InventoryRow` has exactly all `TreeRowFrame` keys plus
  `{row_kind:"folder"|"file"|"unsupported"|"warning",
  presence:InventoryPresence|null,
  verification_state:InventoryVerificationState|null,size:Scalar64|null,
  mtime_ns:Scalar64|null,acknowledged:boolean|null,reappeared:boolean|null,
  unsupported_reason:UnsupportedReason|null,
  provenance:Provenance|null,current:boolean|null,
  invalidation:VerificationInvalidationReason|null,
  rollup:InventoryRollup|null,
  integrity_outcome:IntegrityOverlay|null,
  warning_code:ScanWarningCode|null,warning_path:string|null,
  warning_detail:string|null,annotation:string|null}`. Exact row invariants:

  | `row_kind` | required facts | null facts |
  | --- | --- | --- |
  | `folder` | container and rollup | every subject, warning, and overlay field |
  | `file` | noncontainer; present/missing presence, verification, acknowledgment, reappeared, currentness | rollup, unsupported reason, warning fields |
  | `unsupported` | noncontainer; unsupported presence/reason plus the other subject facts | rollup and warning fields |
  | `warning` | noncontainer and typed warning code | every subject, rollup, and overlay field |

  A warning path is null exactly at the root; otherwise it is the complete
  relative path. Its display is exactly `[<code>] <path-or-Inventory root>`
  and excludes detail. Warning detail and annotation are null or complete at
  most 1,024 UTF-8 bytes. Nonwarnings have all warning fields null.
  `verification_state` remains ledger truth; `integrity_outcome` is only the
  independently replaceable ordinary-integrity generation. It is non-null
  exactly for subject NodeIds in that attempt's frozen candidate index, starts
  all-null, and follows the generation pin/swap rules below. Linked and
  post-copy verification never populate it. Admission freezes a one-to-one
  workflow-item-id → emitted-domain-NodeId map before native work; unknown or
  duplicate ids, or two ids mapping to one node, are structural producer
  failures and publish no partial candidate.
- `PlanWindow` and `InventoryWindow` each have exactly
  `{offset:SafeInt,limit:SafeInt,total:SafeInt,rows:array,
  next_offset:SafeInt|null}`, with rows of `PlanRow` and `InventoryRow`
  respectively. `limit` is 1..256; `rows` is the longest nonempty prefix
  fitting the complete response-byte ceiling when data remains. `offset` must
  be at most `total`, and `total` equals the owning view's current
  `visible_rows`; `offset=total` returns an empty array and null `next_offset`.
  `next_offset`, when non-null, equals `offset + rows.length`; it is null
  exactly when that sum reaches `total`.
- `ExecutionDetail` has exactly `{item_id:HexId,outcome:Outcome,
  reason:OperationOutcomeReason|null,recording:"ok"|"degraded",
  recording_reason:ItemRecordingReason|null,recording_detail:string|null,
  detail_omitted_count:SafeInt,
  evidence:"not-applicable"|"recorded-copy"|"already-verified"|
  "unrecorded"|"superseded",digest:Digest128|null,
  current_digest:Digest128|null,provenance:Provenance|null,
  size:Scalar64|null,mtime_ns:Scalar64|null,
  invalidation:VerificationInvalidationReason|null}`.
  Recording `ok` requires null recording reason/detail; `degraded` requires a
  non-null `ItemRecordingReason` and permits null or at-most-1,024-UTF-8-byte
  detail. `recorded-copy` and `already-verified` require non-null `digest`,
  provenance, size, and mtime, null `current_digest`/invalidation, and their
  exact allowed copy versus readback/verify provenance. `not-applicable` and
  `unrecorded` require every digest/provenance/stat/invalidation auxiliary to be
  null, so coincidental inventory state cannot look borrowed. `superseded`
  requires null execution digest; its remaining auxiliaries are null or
  describe only the separately labeled current state, and only that variant may
  carry `current_digest` or invalidation.
- `InventoryDetail` has exactly `{node_id:NodeId,
  presence:InventoryPresence,provenance:Provenance|null,current:boolean,
  unsupported_reason:UnsupportedReason|null,reappeared:boolean,
  digest:Digest128|null,
  observed_size:Scalar64|null,observed_mtime_ns:Scalar64|null,
  attested_size:Scalar64|null,attested_mtime_ns:Scalar64|null,
  last_verified_at:string|null,
  invalidation:VerificationInvalidationReason|null,detail:string|null}`.
  `unsupported_reason` is non-null exactly when `presence=unsupported`.
  Only file and unsupported subject rows are detail subjects; a folder detail
  request returns `row_not_actionable` rather than fabricating domain evidence.
  Folder rows remain valid recursive refresh/integrity scopes, while visibility
  changes require an applicable missing subject row. A warning
  row already carries its complete bounded fact in `InventoryRow`; naming a
  warning `NodeId` in detail, refresh, visibility, or integrity commands returns
  fixed `row_not_actionable` for the whole request before any ledger or native
  work.
- `HandoffAssessment` = `{result_revision:SafeInt,ready:SafeInt,
  already_verified:SafeInt,eligible_incomplete:SafeInt,unrecorded:SafeInt,
  superseded:SafeInt,reason:HandoffBlockReason|null}`. Those five counts
  partition every applicable selected byte-producing overlay item. A `ready`
  disposition requires positive `ready`, permits `already_verified`, requires
  the other three counts to be zero, and has null reason. `already-verified`
  requires positive `already_verified`, every other count zero, and null
  reason. `post-settlement-state-diverged` blocks regardless of those counts.
  Absent divergence, all five zero is blocked as `no-applicable-items`. Every
  other block uses the first applicable reason in this exact precedence:
  `eligible-work-incomplete`, `unrecorded-evidence`, then
  `superseded-evidence`.
- `LocationStartRefusal` = `{reason:LocationStartReason,
  candidate:CandidateAssessment|null}`. `candidate-changed` requires the fresh
  non-null assessment and `scope-empty` requires null. Post-copy admission has
  the narrower exact `CandidateStartRefusal` =
  `{reason:"candidate-changed",candidate:CandidateAssessment}` because blocked
  and all-verified classifications have their own assessment-bearing variants.
  Capacity failures are fixed bridge errors, and task-claim contention is the
  separate `busy` result; neither has a second spelling inside a refusal.

### Task and authority ordering

**Decision ownership:** DR-BR-21 owns task/session lifetime, DR-BR-22 owns
close behavior, DR-BR-24 owns concurrency and teardown, and DR-BR-03,
DR-BR-16.1, DR-BR-17, and DR-BR-27 own the narrower authorities named below.

A desktop task is process-live adapter state, owns zero or one current session,
and retains the reviewed plan, selection, separately named compact overlays and
results, sparse reasons/diagnostics, run identity, views, and bounded receipts
until close. Execution becomes immutable at its first ran terminal; before
that, refusal retry replaces only its summary/fresh notices/provisional overlay.
Inventory refresh replaces only its artifact/result/projection, and ordinary
integrity or manual post-copy replaces only its own slot. Every replacement
reserves complete old/new overlap. Browser state owns at most one 256-row
window and reconstructs from `list_tasks`/`get_task`.

The diagnostic budget is 1,024 UTF-8 bytes per complete value and 65,536 across
all currently retained task generations. Stable fact order is established
first; each nonfitting whole value becomes null plus one stable presentation-
omission identity—never truncation. Empty remains distinct from null. Old
diagnostics remain charged until predecessor pins drain; swap releases their
charge but never reprojects frozen details, ids, order, or omissions, and pages
never reapply the budget. `TaskDetail.diagnostic_bytes` is the current charge.
Its two checked de-duplicated omission counts are respectively current producer/
core occurrences and current presentation occurrences; the latter is never
persisted. Generation-local summary/header/view witnesses count only their
owner. Swap replaces those identities atomically; refused replacement preserves
the old identities and its typed-limit summary adds none.

Authorities are checked in this order:

| # | Authority/action |
| ---: | --- |
| 1 | envelope bound, origin/readiness, allowlist, exact payload |
| 2 | retained `command_id` replay/conflict, before every live revision |
| 3 | `L`/`C` release/close tombstone, before live-task absence |
| 4 | exact live task |
| 5 | new task-bound effect-owning `M`: sticky `publication_issue` → stateless `internal_error`; `R`/`D`/`L`/`C` bypass |
| 6 | publication/retirement classification plus precharged lease and epoch capture; pending issue makes ordinary `R`/`M` `bridge_busy`, lets `D` clean up and `L`/`C` join; retirement admits only declared cleanup/replay |
| 7 | supplied exact current session |
| 8 | lifecycle, then named selection/result/view/projection revisions |
| 9 | command-family capacity and one joinable in-progress receipt cell |
| 10 | named permanent plus completion-transient reservation |
| 11 | sole claim, unguessable owner token, visible lifecycle advance |
| 12 | service/facade/database/filesystem work outside task lock |
| 13 | task-object/epoch recheck; token-guarded publish or compensate; release claim, detach response, retain receipt, release lease |

Steps 4 through 6 are one atomic registry/task-lock decision: no issue or
retirement seal can install between classification and lease acquisition, and a
new effect-owning mutation cannot capture a post-issue epoch after bypassing the
sticky issue gate. The same race is rechecked by step 13 before any publication.

One task-wide operation claim covers control, every existing-task start,
terminal release, and close; view/selection/projection mutations use their own
service authority locks. Exact owner replay joins single-flight work; another
command returns its `busy` shape without outside work. Only the token owner may
publish or compensate. Failure closes adopted observer/session state, discards
uninstalled candidates, releases reservation, advances lifecycle, then clears the
claim. Observation is attached before dispatcher scheduling. Selection reports
`committing`/`committed` while execution owns the claim.

New-task starts use an unpublished registry claim keyed by command id, exact
intent, and claimed slot generations. Under registry/slot lock it reserves task
id/bytes and claims slots; `list_tasks` cannot see it until observation is
attached and publication is atomic. Identical delivery joins. A different
command naming a claimed slot returns
`{disposition:"busy",reason:"slot-claimed"}` without task detail or outside
work. Its renderer says exactly `Wait for the other task to finish starting. If
this selection is no longer available, choose the folder again.` Failure
restores still-matching slots, releases reservation/claim, and retains the typed
Setup receipt.

Each live task has a checked `publication_epoch`, mutation-publication seal,
ordinary-retirement seal, final cleanup seal, and checked ordinary/cleanup lease
counts; none is a bridge revision. The 64-handler pool precharges every lease
record and admitted row's worst-case detached DTO, 8,388,608-byte native return,
and callback copy; the browser window is separately charged. Thus admission or
ordinary response construction cannot fail for unreserved capacity.

Except bounded-under-lock `list_tasks`, every handler retaining task state past
lookup acquires its lease atomically with exact object lookup, issue/retirement
classification, and epoch capture; the lease retains that object and charge.
Receipt replay may take a replay lease. Before scheduling, each attachment
separately reserves its owner-callback/reconciler lease plus retry, latch, and
pin bookkeeping; it is outside the handler pool and lasts through callback
retry and cleanup. Publication issue still admits declared reads, drain,
release, and close. After close seals ordinary leases, only `get_task`,
`next_events`, exact-session release/busy observation, and receipt replay/
conflict receive cleanup leases; terminal callback and close owner/replay use
their pre-reserved authorities. Every other request is `task_unavailable`.

Every referenced artifact/overlay/projection generation is read-pinned. Under
its lock, the handler deeply copies the bounded DTO and releases the pin only
after detachment; separately reserved transient copies hold no graph reference.
Replacement declares write intent, blocks new pins, drains admitted pins without
the task lock, then swaps atomically. The old graph, diagnostics, and omission
identities remain charged until then. The six-entry inventory cache counts
charged generations: pinned entries cannot be evicted, a seventh build with all
six pinned is `retention_full`, and charge releases only after the last pin.

`publication_epoch` starts at zero and advances only for publication issue or
accepted close; named publications use only their own revisions/generations.
After outside work and before publication/detachment, recheck the exact object
and epoch. A stale read drops pins and gets at most one allowed fresh lease; a
second race/denial returns its declared conflict or `task_unavailable`, never
stale data. A stale effect-owning mutation publishes no task state, compensates
its candidate/reservation, and settles its receipt `internal_error`; truthful
independent domain/ledger effects remain and are never repeated. Construct the
detached DTO before releasing its pins and lease.

Publication-issue installation is an epoch barrier. Under the publication gate,
the reconciler seals new effect-owning mutations and advances the epoch;
already-published work remains, while losing mutations compensate as above.
It blocks provisional-generation pins, drains admitted short pins without task
lock or its own reconciler lease, discards/releases the provisional generation,
then exposes the issue. Older mutation leases later fail their epoch recheck.
Allowed reads use the advanced epoch; `next_events` uses a cleanup lease, and
release/close join pin-free and begin only after issue reclassification, then
wait for stage/latch reconciliation and cleanup. Issue observation advances
the browser request generation before any pre-seal detached callback may update
the page.

The lifecycle claim does not substitute for a service-owned selection or
projection authority. After winning the task claim and before domain I/O, an
execution or integrity/refresh start atomically rechecks its expected service
revision under that authority's own lock and freezes the selection or indexed
scope (execution marks selection `committing`). If a narrower mutation won
first, the claim owner publishes no work, compensates its reservation/claim,
and returns the declared conflict. If the start won first, a selection mutation
gets `committing`/`committed`, and projection mutation cannot alter the frozen
scope. No start relies only on the earlier adapter snapshot.

Reads take the task lease and exact generation pins above, then snapshot the
named immutable authority without holding the task lock across JSON, database,
facade, or filesystem work. After any such outside work, they recheck the exact
task object, publication epoch, and every named task/session/view revision
before returning a `current`/`opened` value; the one allowed resnapshot applies
only where the row remains readable, otherwise a raced read returns its exact
conflict shape or `task_unavailable` instead of publishing stale data. A
revision conflict is a typed result, not optimistic browser repair. `next_events` and
`release_terminal_session` are exact to `(task_id,session_id)`; a delayed
request for an older session cannot observe, release, or close a newer one.
Every service session start attaches observation before dispatcher
schedulability, with the sink excluded from receipt identity and with the
claim-owner callback as the only publication path.

The retained-task cap is 48 plus an enforced byte budget. Each task owns at
most 4,096 mutation receipts: at most 4,095 ordinary receipts plus one
effect-owning close cell reserved as part of that total. Ordinary mutation
admission cannot consume that cell; saturation of the ordinary cells refuses a
new non-close command as fixed `receipt_capacity_full` and never evicts a
receipt or affects already admitted work. That capacity observation is
necessarily stateless because no receipt cell exists; it performs no outside
work, and a later caller must use a fresh command id. The dedicated cell holds
only an accepted live close's exact intent and `closing` replay until that same
state becomes the global close tombstone, so a task whose ordinary receipt
cells are full remains closable. The analytical maximum task includes one plan
with at most 120,000 total domain rows under the 128-MiB plan-domain hard wall
and 120,000 plan notices under the independent 192-MiB informational wall
(240,000 total plan rows), authoritative selection of at most 120,000
operations, all five
simultaneously populated `TaskResults` slots (`plan`, `execution`, `inventory`,
`integrity`, and `post_copy_verify`), a 120,000-row execution overlay, one
120,000-row ordinary-integrity overlay, one 120,000-row post-copy overlay,
capped sparse diagnostics and receipts, the published-start routing reference,
lifecycle and view state, and a reference to an attached inventory view with
at most 120,000 domain rows under its 192-MiB domain wall and 120,000 warning
rows under its separate 192-MiB informational wall (240,000 total rows).
Retrying an unrun execution refusal charges old/new summaries,
fresh-notice sets, and any provisional overlay; inventory refresh charges both
complete old and new artifact/result/projection, informational, and diagnostic
generations; ordinary-integrity
and manual-post-copy replacement each charge both old and new result-summary
and overlay generations until replacement write intent has excluded new pins,
the last old-generation pin has drained, and the atomic swap releases the old
generation.
Projection nodes themselves belong to the separately bounded six-view cache,
whose entries may each reach 240,000 rows; only an unpinned generation may be
evicted to invalidate/rebuild an open task's view without deleting task
identity. Four combined maximum tasks are always admissible. Before every
artifact-growing session attach, reserve its worst-case permanent delta,
completion-time full result, and separately owned callback/reconciler root;
the fixed handler pool owns detached DTO/native/browser copies. Shrink after the
known charge, never silently evict a task or pinned projection, and return
`retention_full` when either budget would be exceeded.

Each session attachment reserves one of 64 per-task release-tombstone positions
and its globally charged bytes before scheduling. A release tombstone is keyed
by `(task_id,session_id)` and contains the exact returned lifecycle revision,
release time, and expiry; it survives task close for five minutes and is never
evicted early. Global release-tombstone capacity is part of the byte budget, so
new attachment may return `retention_full`, but terminal release cannot fail for
capacity. Identical delayed release returns the stored result; changed session
identity cannot affect a successor; after expiry it returns `task_unavailable`.
Task close materializes the reserved tombstone for any exact session it releases
before removing the task, so a delayed release racing or following close has the
same replay authority.

`close_task` is the special `C` mutation class. Receipt lookup and live
preconditions run first. A lifecycle conflict, a task-wide-claim busy result,
or a different close command observing an already accepted live close is a
stateless no-effect observation and performs no outside work. Only the command
that wins the close claim occupies the dedicated cell; its identical retry
joins/replays, and reuse of that owning id with changed intent is
`command_conflict`. A nonowner command while cleanup is live returns the
current exact `closing` object without consuming the cell. A contained handler
failure before ownership is another stateless no-effect observation; after
ownership, the cell remains authoritative and an uncertainty retry returns the
current `closing`/`closed` effect rather than repeating an error that could hide
cleanup. Acceptance seals ordinary leases and advances `publication_epoch`.
An effect-owning mutation that published first remains authoritative; when the
close seal wins, the mutation follows the stale-mutation compensation and
fixed-`internal_error` rule. The close owner requests cancellation, then waits
without the task lock for older ordinary leases and their generation pins and
reconciles the exact terminal/session release while the allowed cleanup leases
and separately reserved exact terminal callback remain available. After cleanup
it atomically sets the final seal and blocks new cleanup-lease admission, then
wakes/cancels every active `next_events` long-poll and other cleanup waiter,
waits for the last admitted cleanup/replay lease to drain, and
only then removes the task and releases its task, cache-reference, receipt, and
publication-fault roots. `close_task` then atomically replaces that still-full
task charge with a fixed, analytically charged tombstone indexed by both task id
and its owning command id and containing only those ids, exact-intent hash,
closed result, and expiry. It is retained for five minutes—longer than the one
30-second uncertainty retry—and is never evicted early. Closing therefore
cannot fail for lack of retention capacity because it strictly shrinks an
already reserved charge; rapid create/close cycles may instead make a new task
return `retention_full` until tombstones expire. During retention, identical
owning-command replay returns the closed result, reuse of that owning command id
with changed intent returns `command_conflict`, and a different `close_task`
command id naming the tombstoned task idempotently returns the same exact
`{disposition:"closed",task_id:TaskId,lifecycle_revision:SafeInt}` without
creating another receipt or requiring nonexistent `TaskDetail`. After expiry,
either form returns `task_unavailable`.

Setup-family mutations use a separate, charged 128-entry receipt table with a
30-minute TTL. Receipts are never LRU-evicted before that TTL, and exact replays
never repeat native/ledger work. An associated returned slot is pinned against
slot LRU eviction for its first 60 seconds and is replayed while it remains
live; after that pin, an ordinarily evicted or expired slot makes replay return
`slot_unavailable`. Changed intent returns `command_conflict`.
When the table is full, a new mutation returns `receipt_capacity_full`; an
existing receipt remains replayable.

`activate_task_pair` uses that Setup receipt table even though its input names a
retained task. First delivery takes an ordinary task lease and immutable plan-
generation pin, snapshots the exact plan fingerprint and both reviewed location
identities, reserves two slot placeholders, and releases the task lock before
fresh native resolution. Before publishing either slot it rechecks the exact
task object, plan generation, and publication epoch; a close, replacement, or
loss of the retained plan returns `task_unavailable` and publishes no slot. The
receipt binds the wire task id and captured immutable plan identity. Exact replay
consults that receipt before rereading the task and never resolves a later plan.
`start_plan`/`start_inventory` begin there while their task is unpublished. On
successful publication the input slots are atomically consumed and the same
receipt transfers into the new
task's 4,096-entry table and lasts until close; on refusal it remains a Setup
receipt until its ordinary TTL. Transfer is pre-reserved and cannot make an
already-started task lose replay authority. Because a published-start retry has
no `task_id`, one bounded global routing index maps its `command_id` to that same
task-owned receipt. It is an index/reference, not a second receipt, is charged
to the task, and is removed atomically with task close. Receipt lookup consults
the Setup table and then this index before reading slots. Exact intent returns
the original started effect with current task detail, changed intent is
`command_conflict`, and lookup after task close/route removal falls through to
the consumed-slot check and returns `slot_unavailable` without native, ledger,
or dispatcher work.

Candidate intent slots have an independent 32-entry LRU capacity. Before a
typed or picker result can begin native admission, the slot store atomically
evicts enough unpinned entries and reserves one placeholder; recent activation
first revalidates current membership, then does the same. Recent-pair activation
reserves after membership revalidation; task-pair activation reserves after the
immutable plan snapshot. Either pair path atomically reserves two placeholders
or none before native probing. A refusal or exception releases every placeholder,
so partial pair admission creates no slot. If pinned or claimed entries leave
insufficient room, the command returns fixed `slot_capacity_full` before native
admission; a receipted command retains that error in its Setup receipt, while
the interactive picker returns it directly. Slot pressure never relabels a
candidate assessment.

### Exact command and retry rows

**Decision ownership:** DR-BR-27 owns the table and retry/receipt policy; each
row's domain authority remains with the additional DR-BR records named in the
map.

All rows require `OPEN` readiness and the complete 65,536-byte request-envelope
bound. Every complete canonical JSON response, including fixed errors, is at
most 8,388,608 UTF-8 bytes before native-return construction. For this bound,
canonical encoding is `ensure_ascii=False`, sorted keys, comma/colon separators,
and strict finite primitives; it is measurement input, not a second wire shape.
Paged reads use
the longest nonempty row prefix within that ceiling; they never truncate a path
or typed fact. `next_events` applies the same rule to update prefixes before it
commits cursor advancement or removes queue entries: it returns 1..64 updates
when any are available, consumes only the returned prefix, and returns zero only
after its wait ends with no update. The 1,048,576-byte core reliable-envelope
ceiling plus fixed bridge-wrapper/scalar-projection overhead guarantees one
maximum queue head fits; a valid event can never block the drain behind a
singular-overflow branch.
Singular values that cannot fit fail as fixed
`response_too_large` before pywebview construction. The accepted input/path
bounds prove one maximum row fits; the fixed 37-ASCII-character `NodeId`
grammar and 32,767-UTF-16-code-unit plan-path ceiling prove the at-most-16,385
immutable plan ancestors fit. Tests cover the UTF-8 worst case for that UTF-16
ceiling: BMP code points that encode to three bytes per one code unit, plus
astral four-byte code points that consume two code units. The same ceiling and all
native/browser callback copies are charged by BR-G-45.

`R` is a 5,000 ms local read: at most two total identical-payload attempts, the
second immediate only after transport timeout/uncertainty. `M` is a receipted
30,000 ms mutation with the same two-attempt rule; fixed domain results are not
automatically retried, and a confirmed destructive click uses a fresh command
id. `C` is the dedicated close mutation: 30,000 ms, with at most one identical
retry after transport uncertainty; only its accepted effect-owning command is
receipted, while the stateless no-effect observations defined above may be
recomputed. `I` is interactive with no deadline or automatic retry. `D` is one 25,000
ms server wait under a 30,000 ms browser deadline; uncertainty recovery creates
one fresh drain id and uses the exact replay cursor, never retries the old drain
id. `L` is a 30,000 ms exact-session release with at most one identical delayed
recovery attempt in the next 60 seconds and no `command_id`. Handler-produced
`internal_error` is a retained/replayed M result, not a cue to repeat the
effect; `C` follows its accepted-owner state rule above. Python and JavaScript freeze these attempts, timings, and retryable
classes in one policy-mirror test.
`open_plan_view` and `open_inventory_view` are read-class commands because each
task memoizes one current view identity: an identical retry returns that same
view or the current conflict and never allocates a second retained view.

Tagged variants below are separate exact objects: keys named for one variant
are absent from the others. An existing-task M command that can race the sole
task claim additionally returns `{disposition:"busy",task:TaskDetail}` without
outside work. Conflict variants carry only the current named authority or
current task detail; they never perform the work whose stale result they would
need in order to populate success-only fields.
The table shorthand “`D` carries `x`, `y`” means exactly
`{disposition:"D",x:<declared type>,y:<declared type>}` with no implicit keys;
`task`, `view`, `candidate`, `assessment`, and `page` mean `TaskDetail`, the
named view type, `CandidateAssessment`, `HandoffAssessment`, and
`PlanDependencyPage`, respectively. `window` means the exact window shape above;
`detail` means the row-specific named detail type. A named revision always uses
`SafeInt`, and ids use their declared primitive grammar.

| Command (activation) | Exact payload | Exact success result/dispositions | Class and named authority |
| --- | --- | --- | --- |
| `list_tasks` (cp4) | `{}` | `{tasks:[TaskSummary]}`; 0..48 | R; registry snapshot |
| `get_task` (cp4) | `{task_id:TaskId}` | `TaskDetail` | R; task |
| `next_events` (cp4) | `{task_id:TaskId,session_id:HexId,drain_id:HexId,replay_from:PositiveSafeInt|null}` | `{task_id:TaskId,session_id:HexId,drain_id:HexId,updates:array}` with the byte-aware 0..64 exact drain-update prefix | D; task then exact session/cursor; consume only the returned prefix |
| `control_task` (cp4) | `{command_id:HexId,task_id:TaskId,session_id:HexId,expected_lifecycle_revision:SafeInt,action:"pause"|"resume"|"cancel"}` | `{disposition:"applied"|"noop"|"conflict"|"busy",task:TaskDetail}` | M; receipt, task/session, lifecycle/claim |
| `release_terminal_session` (cp4) | `{task_id:TaskId,session_id:HexId}` | `{disposition:"released",task_id:TaskId,session_id:HexId,lifecycle_revision:SafeInt}` or `{disposition:"busy",task:TaskDetail}` | L; task/exact terminal session, claim, or retained release tombstone |
| `close_task` (cp4) | `{command_id:HexId,task_id:TaskId,expected_lifecycle_revision:SafeInt}` | live/retained success is `{disposition:"closing"|"closed",task_id:TaskId,lifecycle_revision:SafeInt}`; live conflict/busy is `{disposition:"conflict"|"busy",task:TaskDetail}`; a nonowner observing accepted live close gets the current closing object; a tombstoned different command id gets the same exact closed object | C; accepted owner cell, live task/lifecycle/claim, or task/command-indexed closed tombstone |
| `read_setup` (cp6) | `{}` | `SetupView` | R; defaults snapshot then bounded recent probes |
| `pick_folder` (cp6) | `{purpose:"source"|"target"|"inventory"}` | cancel `null`, otherwise `CandidateView` | I; common workflow admission then purpose slot |
| `admit_typed_folder` (cp6) | `{command_id:HexId,purpose:"source"|"target"|"inventory",path:string}` | `CandidateView` | M; setup receipt, common workflow admission, purpose slot |
| `activate_recent_location` (cp6) | `{command_id:HexId,recent_id:RecentId,purpose:"source"|"target"|"inventory"}` | `CandidateView` | M; setup receipt, current bounded recent membership, fresh common admission, purpose slot |
| `activate_recent_pair` (cp6) | `{command_id:HexId,pair_id:PairId}` | `{disposition:"accepted",source:CandidateView,target:CandidateView}` or `{disposition:"refused",source:CandidateAssessment,target:CandidateAssessment}` | M; setup receipt, one current snapshot; two slots only when both accept |
| `activate_task_pair` (cp6) | `{command_id:HexId,task_id:TaskId}` | `{disposition:"accepted",source:CandidateView,target:CandidateView}` or `{disposition:"refused",source:CandidateAssessment,target:CandidateAssessment}` | M; setup receipt, exact live sync task and immutable plan generation, reviewed volume identities, fresh common resolution/admission; two slots only when both accept |
| `start_plan` (cp6) | `{command_id:HexId,source_id:SlotId,target_id:SlotId,options:PlanSetupInput}` | `{disposition:"started",session_id:HexId,task:TaskDetail}`, `PlanStartRefusal`, or `{disposition:"busy",reason:"slot-claimed"}` | M; setup/published-start receipt route, native option canonicalization, slots, reserve, fresh pair admission, unpublished owner claim and attached plan start |
| `start_inventory` (cp6) | `{command_id:HexId,inventory_id:SlotId}` | `{disposition:"started",session_id:HexId,task:TaskDetail}`, `InventoryStartRefusal`, or `{disposition:"busy",reason:"slot-claimed"}` | M; setup/published-start receipt route, slot, reserve, fresh admission, unpublished owner claim and attached inventory start |
| `open_plan_view` (cp7) | `{task_id:TaskId,expected_lifecycle_revision:SafeInt}` | `{disposition:"opened",view:PlanView}` or `{disposition:"conflict",lifecycle_revision:SafeInt}` | R; task/lifecycle, immutable plan memo |
| `update_plan_view` (cp7) | `{command_id:HexId,task_id:TaskId,view_id:ViewId,expected_view_state_revision:SafeInt,search:string,filters:[PlanFilter],collapse:{node_id:NodeId,collapsed:boolean}|null}` | `{disposition:"applied"|"noop"|"conflict",view:PlanView}` | M; receipt, task/view, view-state revision |
| `get_plan_window` (cp7) | `{task_id:TaskId,view_id:ViewId,expected_view_state_revision:SafeInt,expected_selection_revision:SafeInt,expected_result_revision:SafeInt,offset:SafeInt,limit:SafeInt}` | `{disposition:"current",view:PlanView,window:PlanWindow}` or `{disposition:"conflict",view:PlanView}` | R; task/view, view-state, selection, result |
| `get_plan_anchor` (cp7) | `{task_id:TaskId,view_id:ViewId,expected_view_state_revision:SafeInt,expected_result_revision:SafeInt,anchor:{anchor_type:"item",item_id:HexId}|{anchor_type:"node",node_id:NodeId}}` | `{disposition:"current",node_id:NodeId,index:SafeInt,ancestor_ids:[NodeId]}` with 0..16,385 strict ancestors ordered parent first through root; `{disposition:"not-visible",view:PlanView}`; or `{disposition:"conflict",view:PlanView}` | R; task/view/view-state/result, shared resolver; node anchors enable off-window move-peer navigation without path derivation, while current search/filter state may hide the complete chain |
| `get_plan_detail` (cp7) | `{task_id:TaskId,view_id:ViewId,operation_id:HexId,offset:SafeInt,limit:SafeInt}` | `{disposition:"current",page:PlanDependencyPage}` | R; immutable task/view/operation dependencies |
| `get_selection_summary` (cp7) | `{task_id:TaskId,expected_selection_revision:SafeInt}` | `{disposition:"current",summary:SelectionSummary}` or `{disposition:"conflict",summary:SelectionSummary}` | R; task/selection |
| `mutate_selection` (cp7) | `{command_id:HexId,task_id:TaskId,expected_selection_revision:SafeInt,changes:[{node_id:NodeId,selected:boolean}]}` with 1..256 unique node ids | `{disposition:"applied"|"noop"|"conflict"|"committing"|"committed",selection_revision:SafeInt}`; the last two never mutate | M; receipt, task/selection; server recursive closure under the service selection lock |
| `start_execution` (cp7) | `{command_id:HexId,task_id:TaskId,expected_lifecycle_revision:SafeInt,expected_selection_revision:SafeInt,destructive_acknowledged:boolean}` | `{disposition:"started",session_id:HexId,task:TaskDetail}`; `{disposition:"confirmation-required"|"conflict"|"busy",task:TaskDetail}`; or `{disposition:"refused",task:TaskDetail,reason:ExecutionStartReason}` | M; receipt, task/lifecycle/selection, reserve/claim, core commitment with frozen linked verify, attached start |
| `get_execution_detail` (cp8) | `{task_id:TaskId,item_id:HexId,expected_result_revision:SafeInt}` | `{disposition:"current",result_revision:SafeInt,detail:ExecutionDetail}` or `{disposition:"conflict",result_revision:SafeInt}` | R; task/result then atomic ledger snapshot |
| `read_post_copy_handoff` (cp10) | `{task_id:TaskId,expected_result_revision:SafeInt}` | `{disposition:"ready"|"already-verified"|"blocked",assessment:HandoffAssessment}` or `{disposition:"conflict",result_revision:SafeInt}` | R; task/result then atomic ledger snapshot |
| `start_post_copy_verify` (cp10) | `{command_id:HexId,task_id:TaskId,expected_lifecycle_revision:SafeInt,expected_result_revision:SafeInt}` | `{disposition:"started",session_id:HexId,task:TaskDetail}`; `{disposition:"already-verified"|"blocked",assessment:HandoffAssessment,task:TaskDetail}`; `{disposition:"refused",refusal:CandidateStartRefusal,task:TaskDetail}`; or `{disposition:"conflict"|"busy",task:TaskDetail}` | M; receipt, task/lifecycle/result, reserve/claim, atomic classification, ready-only fresh root admission, final atomic classification/freeze, attached new session |
| `open_inventory_view` (cp9) | `{task_id:TaskId,expected_lifecycle_revision:SafeInt}` | `{disposition:"opened",view:InventoryView}` or `{disposition:"conflict",lifecycle_revision:SafeInt}` | R; task/lifecycle, projection open/rebuild |
| `update_inventory_view` (cp9) | `{command_id:HexId,task_id:TaskId,view_id:ViewId,expected_view_state_revision:SafeInt,search:string,filters:[InventoryFilter],hide_acknowledged:boolean,collapse:{node_id:NodeId,collapsed:boolean}|null}` | `{disposition:"applied"|"noop"|"conflict",view:InventoryView}` | M; receipt, task/view/view-state |
| `get_inventory_window` (cp9) | `{task_id:TaskId,view_id:ViewId,expected_view_state_revision:SafeInt,expected_projection_revision:SafeInt,expected_result_revision:SafeInt,offset:SafeInt,limit:SafeInt}` | `{disposition:"current",view:InventoryView,window:InventoryWindow}` or `{disposition:"conflict",view:InventoryView}` | R; task/view, view-state, projection, then result overlay |
| `get_inventory_detail` (cp9) | `{task_id:TaskId,view_id:ViewId,node_id:NodeId,expected_projection_revision:SafeInt}` | `{disposition:"current",projection_revision:SafeInt,detail:InventoryDetail}` or `{disposition:"conflict",projection_revision:SafeInt}` | R; task/view/projection then bounded row query |
| `refresh_inventory` (cp9) | `{command_id:HexId,task_id:TaskId,view_id:ViewId,expected_lifecycle_revision:SafeInt,expected_projection_revision:SafeInt,node_ids:[NodeId]}` with 1..256 unique actionable ids | `{disposition:"started",session_id:HexId,task:TaskDetail}`; `{disposition:"conflict"|"busy",task:TaskDetail}`; or `{disposition:"refused",refusal:LocationStartRefusal,task:TaskDetail}` | M; receipt, task/lifecycle/view/projection, reserve/claim, frozen recursive scope and fresh location admission, attached refresh |
| `change_inventory_visibility` (cp9) | `{command_id:HexId,task_id:TaskId,view_id:ViewId,expected_projection_revision:SafeInt,node_id:NodeId,action:"acknowledge"|"restore"}` | `{disposition:"applied"|"noop"|"conflict",projection_revision:SafeInt}` | M; receipt, task/view/projection, conditional ledger command then patch |
| `start_integrity` (cp10) | `{command_id:HexId,task_id:TaskId,view_id:ViewId,expected_lifecycle_revision:SafeInt,expected_projection_revision:SafeInt,mode:"baseline"|"verify"|"rebaseline",current_evidence_acknowledged:boolean,node_ids:[NodeId]}` with 1..256 unique actionable ids | `{disposition:"started",session_id:HexId,selected:SafeInt,task:TaskDetail}`; `{disposition:"conflict"|"busy",task:TaskDetail}`; or `{disposition:"refused",refusal:LocationStartRefusal,task:TaskDetail}` | M; receipt including acknowledgement, task/lifecycle/view/projection, reserve/claim, frozen indexed descendants and fresh location admission, attached start |

`start_integrity.current_evidence_acknowledged` is true exactly for
`mode="rebaseline"`; baseline and verify require false. Missing, non-Boolean,
false-rebaseline, and true-baseline/verify payloads are invalid before receipt,
claim, candidate resolution, ledger, or native work. The exact Boolean remains
part of the receipted intent, so a confirmed replay cannot be changed into an
unconfirmed evidence replacement or a different mode.

Receipt storage retains an intent hash and the smallest immutable effect
identity, never a stale native-return graph. Replay projection is exact:

| Receipted effect | First completed result | Exact-intent replay while retained |
| --- | --- | --- |
| setup admission/activation | candidate assessment plus any slot id | same result while the slot lives; otherwise fixed `slot_unavailable`; no new probe or slot |
| view/visibility mutation | applied/noop/conflict effect | an applied effect becomes `noop`; noop/conflict remains unchanged; each projects the current named revision/view, and visibility preserves its established `applied` → `noop` rule |
| selection mutation | applied/noop/conflict/committing/committed effect | an applied effect becomes `noop`; every no-effect disposition remains unchanged; all carry the current `selection_revision` and never mutate again |
| control | applied/noop/conflict/busy effect | `noop` plus current task when the original effect applied; otherwise the retained disposition plus current task |
| session start | started/refused/confirmation-required/already-verified/blocked/conflict/busy effect and any stable task/session identity | never attaches again; published-start routing finds the task-owned receipt without a task id; started returns the original `session_id` plus current detail for its task even after terminal release or a successor attachment, every no-start disposition remains unchanged with its declared current projection, and confirmation-required repeats until the browser sends acknowledged intent under a fresh command id; provisional Setup busy remains exactly `{disposition:"busy",reason:"slot-claimed"}` |
| accepted close | closing/closed effect and owning command id | current `closing` while cleanup is live, then the closed-tombstone result; once tombstoned, identical intent or a different close command id returns the exact closed object, while only the owning id with changed intent is `command_conflict` |
| M handler-contained internal failure | fixed `internal_error` effect | the same fixed error; it never reruns uncertain work |

When a receipt, accepted-close cell, or tombstone owns a command id, the same id
with any different exact wire intent is `command_conflict`, even if both inputs
canonicalize to the same options. Stateless `receipt_capacity_full` and
nonowning/no-effect `C` observations establish no command-id ownership and are
the only exceptions; after a definite response the browser uses a fresh id. A
receipt lookup precedes mutable task/recent/slot reads. Recomputed current task
detail or revision is presentation only and cannot change the retained effect.
Task receipts last until close; setup, release, and close cells/tombstones use
the exact capacities and lifetimes above.

Plan filters are an ordered duplicate-free subset of `copy`, `update`, `move`,
`move_update`, `recase`, `mkdir`, `trash`, `delete`, `noop`, `blocked`, and
`unsupported`; inventory filters are an ordered duplicate-free subset of
`present`, `unverified`, `verified`, `modified`, `reappeared`, `unsupported`,
`missing`, `mismatched`, `error`, and `acknowledged`. Empty means no domain
filter. Inventory view state separately carries `hide_acknowledged`, initially
true; a filter set containing `acknowledged` is valid only when that Boolean is
false, so the positive acknowledged view cannot be hidden by contradictory
state. Unknown values, non-source order, and duplicate members are invalid
payloads. Searches are
literal valid Unicode bounded by the complete envelope. Node/id arrays reject
duplicates. Selection changes apply in listed order against one locked
selection snapshot; each change applies the server-owned recursive closure,
later overlapping changes may override earlier ones, and the successful batch
advances `selection_revision` once. Domain refusal never leaks raw paths or exception text. The target
adds the fixed error row `retention_full` / `NamiSync is retaining the maximum safe
amount of review data. Close a task or wait for recent retry state to expire,
then try again.` Existing fixed transport,
task, conflict, busy, unavailable, and internal-error rows remain. At
checkpoint 6, `slot_unavailable` becomes the purpose-neutral
`That folder selection is no longer available. Choose the folder again.` The
target additionally fixes `receipt_capacity_full` / `Close a task or wait for
recent retry state to expire, then try again.`, `slot_capacity_full` /
`NamiSync is holding the maximum number of folder selections. Start a task
with an existing selection or wait a minute, then try again.`,
`recent_unavailable` / `That remembered location is no longer available.
Refresh Setup and choose it again.`, `row_not_actionable` / `That row does not
support this action. Choose an actionable folder or file row.`, and `response_too_large` /
`That review value cannot be returned safely. Shorten the path or close the
task and start a new plan.`

### Location, evidence, and handoff policy

**Decision ownership:** DR-BR-06 owns location/scope admission, DR-BR-14 and
DR-BR-21 own retained evidence transport, and DR-BR-05, DR-BR-20, and DR-BR-27
own the facade/view/retry seams.

Typed admission accepts valid Unicode of at most 32,000 UTF-16 code units and
only ordinary absolute drive-rooted local paths. It performs no trimming,
quote removal, URI/shell/environment/tilde expansion, Unicode normalization,
wildcard expansion, or current-directory resolution. It replaces `/` with
`\`, rejects repeated separators and empty/`.`/`..` components, and removes
one trailing separator except at a drive root. It rejects device/extended/UNC,
mapped remote, ADS, wildcard, forbidden Win32 filename characters (`<`, `>`,
`"`, `|`, and U+0001..U+001F), reserved-DOS, ambiguous-suffix, NUL, surrogate,
reparse, placeholder, file-leaf, unsupported drive type/filesystem, unusable
volume facts, and inaccessible input. After lexical validation it classifies
the drive and obtains usable volume identity/filesystem/maximum-component facts
from the drive root. On an otherwise supported volume, any component whose
UTF-16 length exceeds that fresh maximum refuses as `too-long` before component
probing. It then no-follow probes every component and leaf without enumerating
descendants or reading file content. Folder-mounted-volume roots are
deliberately outside desktop M1 because their leaf is a reparse point.

The desktop's `supported-volume` predicate is exact rather than a vague
capability judgment: the native drive type is fixed or removable;
`GetVolumeInformationW` supplies a
nonempty identity and positive maximum-component length; and the uppercase
filesystem name is one of `NTFS`, `REFS`, `EXFAT`, `FAT`, or `FAT32`. Feature
capabilities such as stable file identity, ADS, hard links, and timestamp
granularity remain independently observed and may disable/degrade only their
own behavior. After lexical parsing, `DRIVE_REMOTE` maps to candidate state
`remote` and reason `mapped-remote`; optical, RAM-disk, and unknown/no-root
classes map to `unsupported-volume` / `unsupported-drive-type`. A filesystem
outside the set is `unsupported-volume` / `unsupported-filesystem`, and
unusable native identity or maximum-component facts are `unavailable` /
`unusable-volume-facts`; none is collapsed into a guessed profile.

Picker, typed input, and recent activation call that same workflow service and
then create a 30-minute, 32-entry LRU, purpose-bound intent slot. Editing a
field immediately discards the browser's slot reference; validation occurs on
Enter, blur, paste settlement, or explicit action, not per keystroke. Every
real start freshly repeats admission. Successful plan/inventory-session
admission freezes its Setup row; pre-admission refusal leaves it editable.
`start_plan` admits raw `PlanSetupInput` through the workflow and returns the
canonical frozen `PlanSetupOptions` in task detail; JavaScript neither
canonicalizes nor guesses filter policy.

Recents come only from sync `runs` rows opened after successful preflight and
exclude runs tied to soft-deleted mappings from all three lists. Failed,
canceled, degraded, and unfinished runs still count after row creation.
Queries return five distinct sources, five distinct targets, and five active
pairs ordered by latest `started_at` then deterministic row id. Probe state
never deletes remembered identity. Resolved paths display the current mount;
otherwise the view uses volume identity/label plus stored volume-relative path.
One `read_setup` call captures the bounded recent rows in one ledger snapshot,
deduplicates their location identities, and probes each unique identity once;
source, target, and pair views therefore cannot disagree because one mount
changed midway through the same response.

`RecentId` and `PairId` require no retained lookup map. A process-secret HMAC
over the kind plus durable location identity (or ordered active pair identity)
produces the prefixed 32-hex id. It is stable while that identity remains in the
current process's top-five result and intentionally changes after restart.
Activation opens one current ledger snapshot, rebuilds the bounded active
five/five/five ids, requires the supplied id still be present and its mapping
not soft-deleted, then performs fresh resolution. A stale/top-five-evicted id is
`recent_unavailable`; it never revives an inactive mapping. Receipt lookup still
precedes this revalidation for exact lost-response replay.

`activate_task_pair` does not use recent membership or feed stale `display` text
back through typed-path admission. It requires a retained sync task with one
complete immutable plan, reads the plan review header's source and target volume
identities plus volume-relative paths, and resolves both through the same fresh
candidate service as remembered locations. It returns two truthful slotless
assessments on refusal and publishes two purpose-bound slots only when both
accept. It creates no plan, task, run, recent, commitment, or selection state.
The explicit **Plan again** gesture may orchestrate `activate_task_pair` followed
by `start_plan` using the old task's immutable `TaskDetail.setup`; the new task
has a new request identity and default selection. There is no background task
creation, selection carry-forward, automatic commitment, or automatic execute.

The execution-evidence repository uses one read transaction. It resolves
`runs.run_token` from the retained execution id, joins
`operations.run_id=runs.id`, matches the retained overlay `item_id` to
`operations.op_token`, and matches inventory on
`runs.target_location_id` plus `operations.target_rel_path_key`; it requires
`inventory.scope_token=runs.run_token`. Only filesystem-successful
COPY/UPDATE/MOVE_UPDATE items are eligible; other rows are `not-applicable`.
An eligible success without a committed successful operation is `unrecorded`.
A committed row plus current matching copy provenance is `recorded-copy`; a
current matching readback/verify provenance with non-null `last_verified_at`
is `already-verified`. Missing/currently absent inventory, changed scope,
invalidation, contradictory stat, unsuitable provenance, or duplicate
canonical eligible targets is `superseded`.

Manual exact post-copy verification requires every applicable selected
byte-producing operation to have a filesystem-successful terminal outcome and
no eligible-incomplete, unrecorded, or superseded row. An unrelated non-byte
operation failure does not falsify copied-file evidence. The five exact counts
partition applicable selected byte-producing overlay items: `ready`,
`already_verified`, `eligible_incomplete`, `unrecorded`, and `superseded`.
`post-settlement-state-diverged` blocks it; final-flush/finish/close degradation
does not when every row is complete/current. The new dispatcher/history session
identity conditionally reads/writes against the original execution
`runs.run_token`; it opens no new ledger scope and does not reuse an earlier
history identity. Start orders its outside work exactly: classify atomically
first and return blocked/all-already-verified without native probing; only a
ready subset triggers fresh target admission; after admission, classify once
more and either freeze the still-ready rows or return the new assessment. At
least one applicable selected
byte-producing operation is required. Positive ready work may coexist with
already-verified siblings and starts only the ready subset. All-already-
verified starts no work; zero applicable items is blocked rather than
mislabeled verified. Blocking reasons
are exactly `post-settlement-state-diverged`, `eligible-work-incomplete`,
`unrecorded-evidence`, `superseded-evidence`, and `no-applicable-items`, in that
precedence when multiple facts exist. Otherwise an ordinary refresh/verify-
current fallback may establish a new scope.

---

## 1. Stage 5.5 — Facade Completion

Stage 6 was blocked on gaps in the service surface. They are grouped as one
stage rather than folded into Stage 6 because each is verifiable before a
second interface exists.

### DR-BR-01 — User selection enters the facade as a separate set

`commit_plan` derives its selection from safety alone
(`derive_execution_selection(artifact.plan)`), and no user-chosen subset
exists anywhere. `DESKTOP_UI.md` nonetheless promises a "dependency-closed
selection," and the commitment model already anticipated one: DR-M1-05's
third binding is the selection digest, distinct from the plan and policy
fingerprints.

**Resolution: user deselection is a second, independent input to the same
derivation — not a seed into the same dictionary.**

`derive_execution_selection` computes **safety exclusions** (blocked,
quarantined correspondence, incomplete scan, and their transitive dependents)
from the plan alone. The signature becomes
`derive_execution_selection(plan, *, user_deselected=frozenset())`, and the
two exclusion sources stay separately identifiable throughout. Merging them
into one dictionary would let DR-BR-02's upward reselection clear a
*blocked* or *quarantined* exclusion, silently readmitting an operation the
planner refused. **Safety exclusions are immutable and unreachable by any
user action.**

The final selection is the plan's operations minus the union of both sets,
with the dependency fixpoint run over the union so a dependent of either kind
is excluded correctly.

The service accepts user mutations only for operations that are toggleable
after safety derivation. `user_deselected` is therefore canonical and disjoint
from all safety-derived exclusions; sending a disabled operation id is refused
rather than retained as fake user provenance.

**Outcome semantics.** A user-deselected operation reports `SKIPPED`.
Operations force-excluded *because* a dependency was deselected keep
`DEFERRED` and drive the `partial` headline — the user chose the parent, not
the children, and collapsing that distinction would misreport the run.
`ExclusionReason` gains the stable member
`USER_DESELECTED = "user-deselected"` for the direct choice; reusing
`BLOCKED_DEPENDENCY` would erase exactly the provenance this decision exists
to preserve. Dependency fallout retains `BLOCKED_DEPENDENCY`. Exclusion reason
values remain disjoint from executor reason values so persisted history can
identify excluded rows without parsing detail text.

**That distinction must survive the second-session boundary.** The final
selected-id set cannot reconstruct whether an omitted operation was a direct
user choice or dependency fallout: different user actions can produce the same
runnable set while requiring different `SKIPPED`/`DEFERRED` explanations.
`ExecutionSet` therefore carries the canonical immutable `user_deselected`
operation-id set alongside `selection`; the execution payload and every
execute/verify continuation serialize it. `run_execution` re-derives the
selection and typed exclusions from `(plan, user_deselected)` and refuses a
derived-selection mismatch before preflight. Pause/resume and history then see
the same explanations that were reviewed.

This provenance entered through a **strict workflow-payload version change**,
not an unversioned field addition. The shared epoch register owns the current
and accepted workflow-payload versions; older exact shapes remain rejected.
The plan-request half changes version with the shared envelope even when its
body shape is unchanged. M1 has no durable cross-process queued payloads to
migrate.

This provenance is **not an additional `Commitment` field**. The exact four
fields remain `plan_fingerprint`, `selection_digest`, `committed_at`, and
`linked_verify`; the selection digest authorizes the exact runnable operation
set, while `user_deselected` explains why reviewed operations sit outside it
and cannot grant additional filesystem authority.

**An empty effective selection is refused, not executed.** If user deselection
removes every otherwise selectable operation, `commit_plan` returns the
distinct actionable error "Nothing is selected to synchronize" before
admission. The UI disables Execute with the same reason. This refusal is about
an empty selected set, not about the executor's `SKIPPED` outcome vocabulary.

**`NOOP` remains real selected work.** It confirms observed state and performs
its required recording even though the executor settles it with
`Outcome.SKIPPED`. A nonempty selection containing only `OperationKind.NOOP`
therefore executes and retains the `all-noop` headline. The classifier must not
infer that headline from "every operation outcome is `SKIPPED`": user-deselected
COPY/UPDATE/etc. exclusions also carry that outcome. `all-noop` means the
**effective selection is nonempty and every selected operation kind is
`NOOP`**; user-deselected exclusions do not participate in that predicate.

**Safety-excluded rows render disabled, not merely unchecked.** Because
reselection cannot reach a safety exclusion, a checkbox on a blocked or
quarantined row would be inert — the user clicks and nothing happens, which is
the same failure DR-BR-02 exists to prevent. Those rows present a disabled
control alongside the reason, so the distinction between "you turned this off"
and "the planner refused this" is visible before the click, not after.

### DR-BR-02 — Reselection closes upward, over the user set only

The exclusion fixpoint propagates **downward only**. Deselecting folder `a\b`
removes `MKDIR(a\b)` and every copy beneath it; reselecting
`a\b\important.txt` alone leaves that copy depending on a still-deselected
`MKDIR`, so the fixpoint immediately re-excludes it as `blocked-dependency`.
The user would watch a checkbox go grey the instant they clicked it.

**Resolution:** reselecting an operation also removes its transitive
`dependencies` **from the user-deselected set**. It can never remove a safety
exclusion (DR-BR-01), so reselecting a child whose parent is genuinely
blocked leaves the child excluded, correctly and visibly.

### DR-BR-03 — Selection is revisioned, and ran authority freezes it

Selection is server-side state mutated by concurrent bridge handlers
(DR-BR-17). A lock alone is insufficient: two toggle batches can acquire it in
an order different from the user's clicks, and an execution request can race a
queued preview, committing a selection other than the one on screen.

**Resolution: optimistic concurrency with an explicit revision.**

The shared [result-shape](#exact-shared-result-shapes), [task-authority
ordering](#task-and-authority-ordering), and [command
register](#exact-command-and-retry-rows) own the exact selection DTOs, lifecycle claim,
revision precedence, commitment fields, conflict/busy results, and execution
start row. This record owns selection semantics, the reviewing/committing/
committed transition, and user-confirmation policy.

- Selection state is owned by the **service**, keyed by plan request id, not
  by the web adapter. Ownership below the bridge is what lets execution
  validate atomically.
- Every selection mutation supplies the **expected revision**. On match, the server
  applies it and returns the new revision. The selection digest remains internal
  commitment authority rather than a mutation response field.
  On mismatch it applies nothing and returns an explicit **conflict** with the
  current revision, and the client re-reads. Responses are never silently
  discarded — a late response either applied or reported conflict, so the
  client and server cannot diverge.
- This replaces an earlier "at most one outstanding, discard stale by request
  id" rule, which contradicted itself: discarding a response whose mutation
  already applied would desynchronize the client. At most one mutation is
  outstanding, queued batches merge, and every response is processed.
- The revision increments on every **applied** mutation whether or not the
  effective set moved, because a no-op batch or a deselect-then-reselect cycle
  reproduces an identical digest and digest comparison cannot detect that
  anything was applied. Revision answers "has an accepted mutation advanced
  this view"; digest binds the actual selected set and is what `commit_plan`
  validates.

**Commitment has three states, because admission or an attached attempt can
finish without consuming execution authority.** Freezing straight to permanent
`committed` strands a safe retry: submission may fail before a session exists,
and fresh preflight may terminate an attached execution as `unrun`. Neither
case changes the immutable plan or consumes its authorized operation set.

The transition is:

1. Under the selection lock, validate the expected revision and snapshot the
   effective selection.
2. Mark `committing`, release the lock, construct the immutable commitment, and
   submit.
3. On successful attachment, mark `committed` and keep selection controls frozen
   while that execution is live.
4. On submission failure, atomically return to `reviewing`, advance
   `selection_revision` once even though membership is unchanged, and leave
   Execute available.
5. On a terminal `disposition="unrun"`, atomically publish the complete result
   and fresh-notice generation, clear the active commitment reference, return to
   `reviewing`, and advance `selection_revision` once. The old immutable
   commitment remains part of that session's history.
6. On the first terminal `disposition="ran"`, freeze the selection permanently.
   `ran` means execution authority was consumed, including an all-NOOP,
   metadata-only, failed, partial, or canceled run; it does not require moved
   bytes.

**`committing` always resolves.** The transition to `committed` or revised
`reviewing` sits in a `finally`, and *any* escaping exception takes the failure
branch. The revision advance invalidates a delayed pre-commit selection gesture
instead of letting it arrive after reopening with a still-current revision.

A concurrent Execute observing `committing` must not create a second session —
it is a duplicate of work already in flight, not a new request. A double-click
therefore produces exactly one session. **The second caller is told so**: it
receives a named in-flight response, distinct from both a revision conflict and
an error, which the client renders as "already starting" rather than as a
failure. "Exactly one session exists" is only half a contract; the other half is
what the loser of the race sees.

Mutations against a `committing` selection, a live `committed` attempt, or a
selection permanently frozen by `ran` are refused with a **distinct** response,
not a revision conflict. The client settles silently into the current frozen
state. If that attempt later terminates `unrun`, the reopening revision makes
every delayed pre-commit mutation stale; the client must read the new revision
and use a fresh selection command id.

A retry after `unrun` uses a fresh `start_execution.command_id` and mints a new
immutable commitment with the current authoritative `selection_digest` and a
new `committed_at`. Exact replay of the old start command returns its original
attempt and never creates the new authorization. A genuinely fresh plan still
creates a new task with a new request identity and default selection; the
lower-level direct artifact-replacement guard in DR-BR-04 separately discards
the replaced request's selection as defense in depth.

**The client supplies a revision, never a digest.** JavaScript needs the
revision for stale-view detection and nothing more. The service derives the
selected set and its digest authoritatively when constructing the commitment,
so the binding cannot be shaped by anything the client sends.

**The service/runtime boundary follows that ownership.** Under its selection
lock the service validates the expected revision, snapshots the immutable
`user_deselected` set, and enters `committing`. The runtime receives that
snapshot only; it has no selection revision or client-supplied digest to
validate. It derives the effective set, constructs the commitment and
`ExecutionRequest`, and returns them for dispatcher submission. This keeps the
concurrency state in one owner while the runtime remains the sole constructor
of workflow requests.

The CLI retains its automatic-selection path without acquiring GUI revision
semantics. Omitting `expected_revision` is accepted only while the service
selection is untouched (`revision == 0`, empty `user_deselected`, and
`reviewing`); the web command schema always requires a revision. An adapter
cannot omit the revision after editing a selection and silently commit whatever
state happens to be current.

**No typed confirmation phrase in the GUI.** The CLI's typed `execute` is a
terminal convention and stays there. The safety invariant is the mandatory
two-step — plan and review, then separately commit — not the ritual by which
an interface elicits the second step. A GUI's speedbump is the plan review
itself, and adding a modal after it trains users to dismiss modals, which is
worse than none. Removing the phrase also collapses this decision: the Execute
click *is* the moment of intent, so the revision anchors to it directly and
there is no interval to protect between typing and committing.

The plan's scale is already legible from the status box and the filter counter
chips; restating it on the button would be a third redundant readout, not a
safeguard.

**Confirmation is reserved for the genuinely irreversible.** In M1 the public
request path almost cannot reach one: the `workflows/views.py`
`_require_deletion_policy` validator admits only `trash` and `additive`,
`db/settings.py` refuses persisted semantic defaults that enable `mirror`, and
even a directly constructed `SyncOptions` requires
`internal_mirror_authorized` in `core/planning.py`. Consequently `mirror` is
unreachable through the M1 facade surface, removals go to `.SYNCTRASH` with no
retention sweep to purge them, and execution can be paused or canceled.

The single exception is `UPDATE` while `trash_on_update` is disabled, where
the prior target content is overwritten with no recoverable copy
([`runtime._update`](../namisync/modules/executor/runtime.py) guards the trash
step on that flag). **`MOVE_UPDATE` does not count**: `_move_update` publishes to the
new path and trashes the old one unconditionally, with no `trash_on_update`
guard, so its prior content is always recoverable.

**Risk is computed from the effective selection, server-side.** A modal for a
"plan carrying" such an update would be wrong — if the user deselected every
irreversible update, nothing irreversible remains and no confirmation is
warranted. `preview_selection` therefore returns authoritative primitive
fields alongside the outcome changes:

- `requires_destructive_confirmation`
- `irreversible_update_count`

The frontend renders those facts. It must never inspect operation kinds and
policy flags to reach its own conclusion — that would be authority in the
browser, and it would drift the moment a new irreversible case is added.

**The modal reintroduces a revision interval, so it must validate one.** For
an ordinary selection Execute calls `start_execution(request_id,
expected_revision)` directly and no interval exists. When confirmation is
required:

1. Execute opens the modal for revision `R`.
2. Confirm calls `start_execution` with `R` plus the destructive
   acknowledgement.
3. The service recomputes the effective selection and its risk under the
   selection lock.
4. If the selection moved while the modal was open, execution is refused as
   stale and the modal closes back to review.

The debounce and single-outstanding-mutation rules make that race unlikely
rather than impossible, and an unlikely hole that silently executes an
unconfirmed irreversible write is still worth closing.

Later, a destructive purge or `mirror` joins the same mechanism rather than
adding a second one. Friction scales with irreversibility rather than being a
flat toll, so the dialog carries weight on the rare occasion it appears.

### DR-BR-04 — Direct artifact replacement discards selection

Operation ids are deterministic over intent
(`deterministic_operation_id(kind, source, target, prior_target, reason)`),
so a replan of an unchanged tree reproduces identical ids and a stale
deselected set would silently still apply. That is a trap: the new plan may
contain operations no human reviewed, and carrying the old set forward would
let a checkbox state never applied to *this* plan participate in
`selection_digest`.

**Resolution:** any fresh-preflight discrepancy invalidates that execution
attempt and returns an unrun task to review. The plan artifact remains immutable:
the user may deselect affected operations and retry the remaining reviewed
subset under DR-BR-03, or explicitly create a new plan task when the changed
world warrants a new artifact. The already-implemented lower-level service guard remains:
if a direct facade/runtime caller mutatively replaces an artifact under the same
request id, it discards that request's selection while advancing the request's
revision monotonically. The service retains recognized
mutation command ids as retry tombstones across replacement: a lost-response
retry returns `NOOP` against the new empty selection rather than reapplying old
intent. A new command carrying the old revision conflicts, including an Execute
or destructive acknowledgement formed against the superseded artifact. The UI
never invokes that replacement path. The H2 desktop protocol exposes no in-task
replan command and its task plan slot is immutable after its one complete or
refused publication. Changed Setup starts a new task. The explicit **Plan again**
gesture uses `activate_task_pair` to resolve the old plan's reviewed volume
identities into two fresh Setup slots, then calls `start_plan` with the immutable
old `TaskDetail.setup`; it creates a new request identity and default selection
without copying operation ids or authorization. Required lower-level coverage still
asserts discard, monotonic revision, retry behavior, and the mutation/artifact-
replacement race, while desktop coverage proves an old task's receipts and
selection cannot enter the new task.

### DR-BR-05 — Four runtime methods reach the facade

`acknowledge_inventory`, `restore_inventory`, `list_unacknowledged_missing`,
and `list_stale_inventory` stop at `LocalWorkflowRuntime`. The inventory
context menu and the staleness affordance both need them, and their absence
was an oversight rather than a decision. They lift as passthroughs with view
types, matching every other facade read.

Everything else on the runtime is already lifted or is dispatcher wiring
(`prepare_*`, `open_*`, `audit_observer`) that correctly stays below the
facade.

### DR-BR-06 — Location commands accept opaque ids

**Binding rule.** Desktop location commands send opaque row or folder-node ids,
never paths. The service resolves and validates every id against the named
location, refuses foreign or empty id sets, and unions duplicate subjects before
constructing one workflow request. The CLI path form remains exact-path scope;
recursive CLI scope is not inferred.

**Exact target binding:** the [command register](#exact-command-and-retry-rows) owns
the id-array payloads, named revisions, receipt/claim order, and result variants;
[location, evidence, and handoff](#location-evidence-and-handoff-policy) owns
fresh desktop candidate admission, evidence acknowledgment, and post-copy
classification. This record owns opaque-id resolution plus recursive scope,
scan, recorder, and payload-module behavior.

#### Command and scope contract

- A row id denotes exactly one inventory subject. A folder-node id denotes that
  folder and its complete indexed subtree, independent of the current view
  filter.
- Integrity commands freeze the folder's currently indexed eligible rows into
  exact subjects before admission. An unreadable frozen subject yields one
  visible `unsupported` result and makes verification incomplete while other
  readable subjects continue. Root/location failure, cancellation, or
  incompleteness not attributable to a frozen subject still refuses before
  hashing.
- Folder actions and row actions have distinct labels. No pre-admission
  descendant count is shown because baseline, verify, and rebaseline select
  different eligible subsets. Baseline and verify require no confirmation;
  rebaseline requires explicit confirmation that current evidence will be
  replaced. Every admitted operation reports the actual selected count in
  progress.
- Folder refresh uses `ScanScopeKind.SUBTREES` so new descendants are
  discoverable. A mixed refresh carries both `selected_paths` and
  `subtree_roots` in one session.
- Scope normalization is segment-aware: overlapping roots reduce to minimal
  roots; exact paths beneath a root are redundant; exact paths outside roots
  remain exact; an exact directory-row id does not become recursive; and the
  location's empty root canonicalizes the whole request to `FULL`.
- The invariants are exact: `FULL` carries neither scoped field; `PATHS`
  carries nonempty exact paths and no roots; `SUBTREES` carries at least one
  root and may carry exact paths. Only an explicit full request or the location
  root may normalize to `FULL`.

#### Scan and reconciliation contract

Recursive scope is the full-walk algorithm bounded to roots, not a generalized
exact-path scan. It shares the full-walk helper and therefore inherits every
present and future full-walk incompleteness cause. The helper accepts an
`(absolute_path, relative_prefix)` start, probes the root kind, distinguishes
conclusive absence from `ROOT_UNAVAILABLE`, names the failing relative root,
and shares one visited-directory identity set across all requested roots.

A missing root and a former folder now observed as a file are conclusive; prior
descendants may become missing. A file placeholder or file reparse point is a
conclusive unsupported subject. A directory placeholder, directory reparse
point, repeated directory identity, denial, enumeration/stat/type failure,
case collision, or another inherited full-walk uncertainty makes the combined
scan incomplete and withholds all missing inference.

After a complete scan, the recorder handles all three scope kinds explicitly:

- `FULL` reconciles the full location.
- `PATHS` retains exact-key reconciliation.
- `SUBTREES` reconciles the union of remaining exact paths plus every root and
  descendant, considering prior `present` and `unsupported` rows.

Rows outside that union are untouched. Subtree descendants use the indexed,
wildcard-free binary range below, with equality to `:root` tested separately:

```sql
rel_path_key >= :root || '\'
AND rel_path_key < :root || ']'
```

`LIKE` is forbidden because `%` and `_` are legal filename characters.
`inventory_location_presence_idx(location_id, presence, rel_path_key)` must
serve the range; BR-G-27 pins the query plan.

#### Evidence and payload contract

`InventoryDetails` retains typed scan warnings and
`InventoryDetailsView` exposes primitives-only code/path/detail beside
`complete`. Stage 5.5 proves the evidence reaches the facade; Slice 6 must
render incomplete scope and its reason distinctly from a clean refresh.

Inventory workflow payload v2 carries subtree roots separately from exact
paths and rejects v1. The independently versioned integrity payload advances to
strict v2 so paused custody retains its physical-read total high-water and
aggregate recording status beside frozen exact subjects. The shared decoder
accepts explicit `(expected_kind, expected_version)` and rejects wrong-kind or
wrong-version bodies.

Integrity continuation restructuring remains deferred until a late-run pause
benchmark over representative 10k, 100k, and large-folder subject sets proves a
problem. Any replacement must preserve paused/unpaused result and phase truth;
a nested payload alone is not accepted as bounded work.

> **Rationale (non-normative).**
>
> Opaque ids keep paths and subtree interpretation out of JavaScript. Folder
> integrity continues past subject-local unreadability because expansion turns a
> handful of explicit paths into tens of thousands of frozen subjects, while
> non-subject uncertainty still invalidates the whole scope. Refresh cannot
> expand only indexed rows because that would miss newly created descendants.
> The recursive walk shares full-scan completeness so ordinary ignored files do
> not make real subtrees permanently inconclusive, and the literal range avoids
> hostile-name wildcard bugs. Predicted folder counts and the withdrawn nested
> continuation draft were rejected because neither matched workflow-owned
> eligibility nor demonstrated bounded work.

Landed behavior is recorded under
[Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30).

### DR-BR-07 — Scanner ignore contract narrowed

`IgnoreSet.for_owned_paths()`, `IgnoreSet.exact_path_keys`, and
`ScanResult.ignore_snapshot` are removed (landed in `84a7c53`). Once nothing
constructs a non-default `IgnoreSet`, the type is a compile-time constant and
a snapshot of a constant distinguishes nothing. The remaining contract —
`DESKTOP.INI`, `THUMBS.DB`, the owned-temp grammar, and `.SYNCTRASH` — covers
files whose invisibility is intended, so no UI owes the user an explanation
for them.

This narrows a known gap rather than closing it: **filter** exclusions remain
invisible in plan review, because a filtered file never becomes an operation
and therefore has no row. "Why isn't this file being copied?" is currently
unanswerable for filters. Recorded here; resolution belongs with the filter
discussion, not with Stage 6.

---

## 2. Compute Ownership

### DR-BR-08 — "The UI never computes" means authority

The original rule was driven by two goals: the backend must run full
functionality headlessly, and the browser must never hold decision power.
Neither forbids the client from computing things that affect only its own
presentation.

**Resolution — cosmetic versus authoritative describes what a computation
affects, not where it runs.** The client never computes selection semantics,
dependency closure, result classification, or headline precedence. It may
compute purely cosmetic state for itself. Conversely, cosmetic work may
legitimately execute on the backend when that is where the data lives — being
cosmetic is not an argument for running in the browser.

Three client-side computations are sanctioned under this rule, named
explicitly so the rule is not later cited to block them: rendering tri-state
checkboxes from server-supplied outcomes, scrolling to the server-resolved
anchor/index from DR-BR-19, and rendering filter chips from server-supplied
counts.

An earlier draft sanctioned a fourth — applying view filters to
already-materialized rows — which was wrong for the reason DR-BR-18 gives
about search, and for a sharper one. **Filtering a window and windowing a
filter are different operations.** The client holds a slice of the *unfiltered*
sequence, so filtering it yields an arbitrary subset of an arbitrary slice:
"deletions only" would show the deletions in the current viewport rather than
the plan's deletions, and scrolling would reveal more of them. Filters are
server-side view parameters (DR-BR-15). What the client renders is the chips,
never the decision about what passes.

### DR-BR-09 — Node trees are built in `workflows`, not `interfaces`

The import law forbids `interfaces → core`, so the web layer cannot call
`normalize_relative_path` and cannot safely group paths — grouping on display
strings gets Windows case semantics wrong. Anything requiring path arithmetic
must sit at workflows-or-below.

There is also a precedent. DR-M1-07 built the view vocabulary precisely so
interfaces would not reconstruct domain structure by inspecting shape.
Reconstructing a *hierarchy* from path strings in the adapter is that same
anti-pattern one level up.

**Resolution:** one new `workflows/node_tree.py` holds the shared hierarchy
builder — ancestor synthesis, deterministic node ids, ordering, and subtree
rollups — over any collection of path-keyed rows. Plan-specific move grouping
(DR-BR-12) and the inventory projection are thin layers on it. Two trees, one
implementation; a second near-duplicate module is exactly the drift this
project avoids.

| Layer | Compute |
| --- | --- |
| `core/pathing.py` | relative-key `parent` / `depth` / `is_descendant`, common-suffix stripping |
| `core/execution.py` | immutable selected ids plus canonical user-deselection provenance in `ExecutionSet` |
| `core/models.py` | FULL/PATHS/SUBTREES scan scopes; SUBTREES may retain exact paths outside its recursive roots |
| `modules/planner.py` | unchanged behavior; loses its three private path helpers |
| `modules/scanner.py` | unchanged exact selected-path scan plus explicit recursive/mixed subtree scan scope |
| `db/recorder.py` | explicit FULL/PATHS/SUBTREES reconciliation; completed subtree refresh uses indexed literal ranges and marks missing only within its exact-path/root union |
| `workflows/selection.py` | safety exclusions, user deselection, downward cascade, upward closure |
| `workflows/node_tree.py` | ancestor synthesis, node ids, subtree op sets, rollups, id->path lookup; emits the ordered depth/parent-indexed array interfaces flatten |
| `workflows/views.py` | `PlanNodeView`, `InventoryNodeView`, preview projection |
| `workflows/runtime.py` | construct committed requests from authoritative `user_deselected`; no revision or client digest |
| `interfaces/service.py` | selection state/revision and commit transition, `view_id` minting and projection ownership, the four lifts, revision-guarded id-based location commands, tree passthroughs |
| `interfaces/web` | bridge, host, command allowlist, task state and locks, bounded event queue, JSON encoding, collapse/filter/search flattening, windowing, autoscroll lookup |

`interfaces/web` remains the largest new surface by volume, but after this
split it holds no domain-shaped computation — transport and presentation
mechanics only.

**Why flattening is legal above `workflows` when grouping is not.** The two
look similar and are not. Grouping needs `normalize_relative_path` and Windows
case semantics; flattening needs neither, *provided the tree hands up a
structure that has already done the path work*. `workflows/node_tree.py`
therefore emits an **ordered, depth-annotated, parent-indexed array** —
pre-order position, depth, parent index, and subtree extent per node — so
collapse is an index skip, filtering is a predicate over supplied fields, and
search is a casefolded substring test against a display string the workflow
already escaped. None of that re-derives hierarchy from text, which is the
actual prohibition. If a presentation task ever needs a parent, a depth, or a
descendant set that the array does not carry, that is the signal it belongs
below the boundary, not that the boundary should move.

### DR-BR-10 — Path helpers promote to `core/pathing.py`

`_parent`, `_depth`, and `_is_descendant` are private to `planner.py` and are
needed identically by the tree builder. Duplicating them is exactly the drift
this project avoids.

**Resolution:** promote them unchanged, plus one addition for common-suffix
stripping. Two cautions. `core/pathing.py` already exposes `is_path_below`,
which operates on **absolute** paths for root containment — a different
domain from the relative-key descendant test, and the two must not be merged.
And the promotion is a pure relocation: `_depth` counts
`PureWindowsPath(path).parts`, `_parent` returns `None` for `"."`, and any
tidying during the move silently changes planner behavior. The planner's
existing tests are the proof, unchanged.

---

## 3. The Node Tree

### DR-BR-11 — Node identity is deterministic, and the plan tree is memoized

Structural folder nodes have no operation and still need addressing for
collapse state and folder-scoped selection.

*Staged across both stages.* Location-scoped identity lands in Stage 5.5,
because DR-BR-06's id-based location commands cannot validate ownership
without it. Plan-scoped identity and the plan memo land with the plan tree in
Stage 6 slice 5. Same rule, two arrival times.

**Resolution:** preserve the shipped structural/domain-row codec exactly:
`BLAKE2b-128(person=b"NamiSyncNodeV1")` over the ordered three strings
`(tree_kind, scope_identity, canonical_path_key)`, each encoded as
`u32be(UTF-8 byte length) || UTF-8 bytes`. It does not gain a new literal
`"domain"` member. The semantic domain is still separate from informational
leaves, and scope identity remains the plan request id for plan nodes and the
location id for inventory nodes.

One path node may own several distinct plan operations at the same canonical
target key; planner collision truth must not be collapsed to one member. The
path row keeps its `NamiSyncNodeV1` id and remains the sole path-index result.
When it has one direct operation, that operation may inhabit the path row.
When it has two or more, the path row becomes a container with null singular
operation/overlay fields: an already-container path remains `folder`, while a
leaf becomes `operation-group`. Every direct operation is emitted exactly once
as an immediate noncontainer `operation` child whose id is
`BLAKE2b-128(person=b"NamiSyncMemberV1")` over the ordered four length-prefixed
strings `(tree_kind="plan", scope_identity, canonical_path_key,
operation_id)`, using the same `u32be(length)||UTF-8` member encoding. Direct
member children precede ordinary path children and preserve immutable
`Plan.operations` order, with `operation_id` as a defensive tie-breaker.
Their `display` is the exact final component of the operation's
`target_rel_path`; the group uses the existing deterministic path-node display.
The browser's accessible name combines operation kind, exact complete source
(when present), exact complete target, and sibling position, so equal basenames
do not become indistinguishable. Each filesystem component passes through the
same fixed injective layout-control projection, bidi isolation, and text-only
accessible-label sink as every other hostile filename; raw wire/search values
remain byte-exact and no active control reaches layout or accessibility APIs.
The ordinary literal
case-folded display search evaluates each member independently and retains the
group only as an ancestor of a matching member; counts, risk, selection,
dependencies, anchors, and
overlays count or target the operation children, never the group. The group
rollup includes all direct members and descendants, and its checkbox selects
all direct members independent of filter/window state. `node_id_for_path_key`
still returns only the path/group id; a separate one-to-one operation-id index
resolves item anchors to the singleton path row or exploded member row. The
three personalized preimage domains are disjoint, and any digest collision is
a structural failure rather than first-row-wins.

Informational leaves use `BLAKE2b-128(person=b"NamiSyncInfoV1")` over an exact
typed tuple codec. Each member is encoded in order as one of: null = byte
`0x00`; string = byte `0x01 || u32be(UTF-8 byte length) || UTF-8 bytes`; or the
nonnegative duplicate ordinal = byte `0x02 || u64be(value)`. Every string is
already valid Unicode and within its owning field bound, and the ordinal fits
`SafeInt`; no other member type is accepted. An inventory warning binds
`("scan-warning","inventory",location_id,
"inventory",warning_path_or_null,warning_code,bounded_detail_or_null,
duplicate_ordinal)`. A plan scan notice binds
`("scan-warning","plan",request_id,"review",null,source_or_target,
warning_path_or_null,warning_code,bounded_detail_or_null,duplicate_ordinal)`.
A plan preflight notice binds
`("preflight-refusal","plan",request_id,notice_stage,
notice_session_id_or_null,subject_side_or_null,
refusal_path_or_null,refusal_code,operation_id_or_null,
bounded_detail_or_null,duplicate_ordinal)`. Review-stage rows require null
session id; execution-stage rows require their exact session id. All three codecs
render the digest as the unchanged lowercase `node-` plus 32-hex `NodeId`.

Projection occurs before identity. Source `ScanWarning.rel_path` values `None`
and `""` both become typed null; every nonempty path remains its complete
validated relative spelling. Preflight subject root id projects to `"source"`
or `"target"` against the reviewed roots; a subjectless global refusal uses
null, and a foreign root is rejected. The module-provided occurrence sequence
and stable raw kind/stage/session/side/null-first-path/code/operation/detail
key establish deterministic raw-fact order. In that order, empty detail and a
complete at-most-1,024-byte detail are preserved only while the task's remaining
65,536-byte diagnostic allowance admits the whole value; an individually
over-limit or later nonfitting detail becomes null and records one owning
presentation-omission occurrence at named-slot publication. Replacement computes the
allowance while charging every still-retained old generation; replacement does
not reclaim diagnostic bytes before its atomic swap. The collector also
checks the applicable domain and informational row/retained-byte bounds before
each append and returns the typed no-partial refusal before accepting the first
excess row. Final stable
kind/stage/session/side/null-first-path/code/operation/projected-detail ordering
then assigns zero-based ordinals among otherwise identical projected leaves and
derives ids. Null is a typed tuple member and the only root marker; no collidable
string sentinel exists. Distinct details that project to null remain separate
occurrences through their source order and final ordinals. Pages/rebuilds never
reproject or recount any witness.

The bounded collection and publication boundary is exact. Before attachment,
the task service reserves overlap and snapshots a workflow-owned immutable
`ReviewPublicationContext`: tree kind, the frozen domain/informational sizers
and limits, the remaining presentation-diagnostic allowance after charging the
still-retained replaceable slot, and any immutable baseline population retained
from the accepted artifact. The workflow-owned collector consumes domain facts
first and informational facts second and returns either one immutable complete
candidate—rows, ids, indexes, rollups, exact charges, and presentation-omission
occurrence identities together—or one `ReviewFactLimitExceeded`. It never
returns or stages a partial candidate. Scanner/planner/inventory production
feeds this boundary incrementally; no arbitrarily large raw graph may be built
outside its charge.

The service supplies an injected workflow-level `ReviewPublicationSink`
defined below `interfaces` and implemented without any workflow import of
`interfaces.web`. The sink owns at most one reservation-charged candidate for
an exact current `(task_id,session_id,named_slot)`; duplicate, absent-owner, or
foreign-session staging is a structural failure. Its reservation also
precharges one fixed sideband latch for that exact intended tuple. Any rejected
`stage()` call through an armed sink—including a rejected first call and a
duplicate after a valid call—atomically latches private closed reason
`stage-rejected`; no later stage can repair it. A call against no armed intended
tuple is an out-of-band structural refusal that mutates no task and cannot be a
workflow producer for a task terminal. On collection success the
workflow stages the complete candidate before returning its `OperationResult`;
on limit refusal it returns the typed refused result and stages nothing. Once a
fresh execution preflight has passed and staged its complete set, every caught
execution exception or cancellation that produces a terminal is normalized to
a normal `disposition="ran"` result and retains that stage. An exception that
escapes after any stage enters the nonretryable publication-issue disposition
defined above: owner-exact compensation discards and releases the candidate,
and the later real terminal is not reconciled into named task state.

Under the task owner's terminal lock, successful reconciliation validates the
owner/session/slot and atomically installs and consumes that staged candidate
with its omission identities. It first consumes the tuple's latch;
`stage-rejected` is always the nonretryable publication issue. Otherwise:

| session / result | required sink state and publication |
| --- | --- |
| plan or inventory `review_fact_limit` | no stage; canonical refusal; tuple exactly `(sync-plan,plan,plan)` or `(inventory,inventory,inventory)` with either population |
| completed plan/inventory | one complete stage, installed atomically |
| other failed/canceled/refused plan/inventory before completion | no stage; actual summary; initial availability stays false or refresh preserves predecessor |
| execution `review_fact_limit` | no stage; tuple exactly `(sync-execution,plan,plan)` and informational population |
| normal fresh-preflight refusal | complete nonempty fresh-notice stage |
| passed fresh preflight | complete stage, including empty, retained through later completed/failed/canceled execution terminal |
| execution failure/cancellation before candidate completion | no stage; preserve predecessor fresh set |
| ordinary integrity or manual post-copy, any terminal | no stage; replace only its summary/compact overlay |

Every other tuple/population/stage combination is a structural producer fault.
The callback follows the exact publication-issue compensation in Task and
authority ordering, still delivers the actual dispatcher terminal, never
rewrites the result, and never infers refusal from text. Only a transient
callback exception before installation or structural decision retains the
charged entry/latch for idempotent retry; nothing partial is exposed. Owner
compensation, task destruction, close, and shutdown discard/release every
uninstalled entry/latch, and terminal release/close/shutdown complete only when
none remains.

Initial plan/inventory have no baseline. Inventory-refresh population limits
evaluate candidate in place of predecessor, while retention/diagnostics charge
both until swap. Fresh execution evaluates immutable reviewed notices plus the
candidate fresh set in place of its predecessor, again without early reclaim;
an empty successful stage clears the predecessor. Thus result, tree, and task
publication remain one workflow-owned attempt without importing web code.

Inventory warnings attach to the deepest retained strict structural ancestor of
their path, falling back to the inventory root when none exists or the path is
null. Within each container, merge ordinary
domain children and attached warnings by the complete canonical relative path
key; a root warning uses the empty key and therefore precedes nonroot domain
children, a domain child precedes warnings at the same key, and tied warnings
retain their already frozen informational order. Plan notices attach directly
below the plan root as one block after every domain child, in their frozen
informational order, because source and target warning paths are not
interchangeable with destination-tree paths. These total merge rules own
pre-order, sibling positions, windows, and byte-stable memo rebuilds. Every
informational leaf is a noncontainer. This preserves every occurrence,
prevents collision with a domain row or another notice, and retains the fixed
`node-` plus BLAKE2b-128 wire grammar.

The scope component is not decoration. DR-BR-06 promises that a location
command refuses an id belonging to another location, and a path-only id makes
that check impossible: two locations both containing a `docs` folder would
produce the same id, so the service could neither reject the foreign id nor
detect that it had resolved into the wrong tree. Scoping the id is what makes
ownership validation mean anything.

Determinism still buys two things: a concurrent rebuild produces
byte-identical ids so there is no race to lose, and the built tree may be
**memoized per scope** without an invalidation protocol. For plans that memo
is exact — the artifact is immutable and `save_plan` keys by a freshly minted
request id — and it is dropped by `drop_plan`. The memo holds *structure
only*; selection outcomes overlay per request, since those change with every
preview. Inventory scope is not immutable and is handled by DR-BR-16.

They remain opaque in the sense DR-M1-16 requires: the client treats the fixed
digest spelling as an indivisible id rather than deriving path authority from
it, and the server resolves every supplied id through the exact scoped tree it
owns. Knowledge or construction of a spelling grants no authority.

`build_node_tree` and its canonical path index remain structural/domain-only
and one-to-one. The plan/inventory projection interleaves informational leaves
after building that tree, maintains a separate NodeId-only notice index, and
recomputes the projected pre-order/sibling frame. Notice ids never enter
`node_id_for_path_key`, domain subtree membership, selection, or action-scope
resolution; this permits repeated same-path warnings/refusals without
overwriting domain authority. Selection, collapse, dependency detail, and every
inventory action naming an informational leaf return fixed
`row_not_actionable` before outside work; tagged node-anchor navigation alone
may resolve it.

**Synthetic ids never become operation ids.** Folder nodes come in three
flavors — a real `MKDIR`, a real directory-cleanup `DELETE`, or pure
structure. Only the third is synthetic, and giving it an `operation_id` to
make the tree uniform would reach the recorder, history item identity, and
the selection digest simultaneously. Node ids are minted by
`workflows/node_tree.py` and travel no further down: they never enter `core`,
the domain modules, persistence, or execution. Selection resolves them to real
operation ids before anything binds.

### DR-BR-12 — Folder selection is path-scoped, and the tree owns the scope

A folder node frequently has no operation at all: the planner skips `MKDIR`
when the target directory already exists, so copying into an established tree
produces operations with no directory dependency. "Deselect this folder"
therefore cannot mean "deselect this folder's operation."

**Resolution:** it means every operation whose target sits at or under that
path. The tree already computes subtree membership to produce rollups, so
`deselect_node` is a lookup returning an operation-id set, then the ordinary
derivation. One path walk, not two, and no chance of the two disagreeing.

The inventory tree reuses the same structural rule for commands rather than
selection: its folder-node lookup returns every descendant inventory row for
integrity work, while refresh sends the folder path as the recursive subtree
root defined by DR-BR-06. Plan and inventory therefore agree on what a folder
gesture covers without pretending their downstream workflows have the same
input type.

Dependencies exist for exactly two structural reasons, running in opposite
directions: a child depends on the `MKDIR` that creates its parent
(one `MKDIR`, many dependents), and a directory-cleanup `DELETE` depends on
every removal beneath it (one `DELETE`, many dependencies). File `TRASH` and
`DELETE` carry none. A single folder checkbox meaning "everything at or under
this path" is coherent across both, but the resulting tri-state must be
**rendered from what the server returned**, never predicted from sibling
checkbox states — the cascade runs opposite ways in the two subtrees.

### DR-BR-13 — Decomposed moves render as a paired annotation

A folder rename decomposes into one move per file. Left flat, the rows sprawl
across the destination tree indistinguishable from unrelated new content, and
a reviewer must read every source path to notice they share a prefix. At
realistic scale it is unreviewable, and it buries genuinely new content
sitting alongside it.

**Resolution: annotate, do not reclassify.** The destination folder node
carries the move annotation and its rollup; a dimmed, non-interactive row at
the old location points to it, and the two highlight together. The exact
projection expresses that relationship as symmetric `move_peer_id` values on
the destination folder and old-location ghost/existing annotated folder. A
materialized peer highlights directly; activating an off-window peer calls the
tagged node form of `get_plan_anchor`, then requests the returned window. The
browser never derives a peer from paths.

- **The group is the folder node, not a new selection unit.** A destination
  folder may receive both moved files and genuinely new copies in the same
  run; making the group its own unit would let the collapsed row report only
  the moves and silently omit the rest. Its checkbox is the ordinary
  path-scope deselection from DR-BR-12 — no second selection currency.
- **The ghost is an annotation on the old location.** When the old location
  still holds real operations (a partial move where some files stayed and
  were trashed), the existing node is annotated and no ghost is emitted. The
  dimmed row is what renders when the old location would otherwise have no
  node. One mechanism, two renderings.
- **Ancestor synthesis takes the union** of operation target paths and prior
  target paths, since a ghost position may have no other reason to exist.
- **Nested moves suppress the inner ghost.** If a move's old path falls under
  another move's old path, the outer annotation already explains it and the
  inner would be orphaned at a position that no longer exists.
- **Any reused endpoint suppresses inferred grouping.** Compare each move's
  prior-target and target by canonical components and strip their longest
  nonempty common suffix; without one, no group is inferred. Coalesce all
  members with the same ordered canonical remaining-prefix pair before nested
  suppression, so an ordinary multi-file folder move remains one edge and the
  directed candidate graph has at most one edge per ordered endpoint pair.
  Emit a pair only when one non-self edge is the sole incident candidate at
  both endpoints. Many-to-one convergence, one-to-many split, chains, and
  reverse/swap candidates suppress every edge touching the reused endpoint and
  render their literal operations rather than choosing a false scalar peer.
- **No "renamed" label.** The planner never asserts a rename; the grouping is
  inferred from path arithmetic over move operations, and enough unrelated
  files moving between two directories would be labeled falsely. The kind
  column keeps `MOVE` / `MOVE_UPDATE`, and the annotation reads literally —
  "moved from `<old path>`" — true whatever the cause.
- **No minimum-size threshold and no sub-window.** A two-file move gets the
  same treatment as a two-thousand-file move; collapsed it occupies the same
  rows sprawl would. Group children need no separate paging because expanding
  inserts rows into the flattened sequence (DR-BR-15), which the existing
  window already serves.

---

## 4. Paging and Live State

### DR-BR-14 — Progress carries item identity, never a display path

The accepted Stage 6 target is exact core event v5. The source-backed runtime
remains v4 only until protocol checkpoint 3; that compatibility machinery is
then deleted rather than exposed as a legacy desktop mode. Shared field
meanings, reporter transitions, authority order, and Gap behavior are owned by
`ARCHITECTURE.md` §§2.3 and 2.7.

Follow mode anchors on the current operation, but before this extraction
`Progress` carried only `items_done`, `items_total`, `bytes_done`,
`bytes_total`, and `current_path`.
Mapping a running operation to a node would require joining on a display
path — forbidden, ambiguous under escaping, and wrong.

**Resolution:** The exact version-5 `Progress` body carries required `phase`,
the aggregate/path fields, optional `item_id` and `item_type`, optional opaque
`item_attempt_id`, and optional `item_bytes_done` and `item_bytes_total` for an
active byte-stream attempt. This mirrors the nominal `ResultItem` vocabulary
DR-M1-10 established rather than inventing a parallel identity. Both reporters
already own the identity and stream boundaries: the executor knows its current
operation and copy stream, and the verifier knows its current subject and read
stream.

The fields are optional **as a pair** in the Python contract: an identified
progress event supplies a nonempty `item_id` plus `item_type` equal to
`operation` or `integrity`. `Progress.__post_init__` rejects a one-sided pair
or an unknown type, so the bridge never guesses which node-id namespace an
opaque id belongs to. The type names that row-lookup namespace, not the
producer, phase, or reliable outcome class. Standalone verification ids use
`integrity`; post-copy candidates keyed by their originating executor `op_id`
use `operation` even though their reliable settlement remains an
`IntegrityOutcome`.

An attempt id is either absent or exactly 32 lowercase hexadecimal characters.
It requires item identity. The byte fields are likewise optional as a pair,
require the attempt id, use signed-64-domain integers internally and canonical
decimal `Scalar64` strings on the bridge, and reject `done > total`. Identity
may exist without an attempt before stream entry or for non-byte work. An
attempt without byte counters is the active indeterminate shape. Each
byte-pipeline entry mints a fresh opaque attempt id; retry or reconstructed
resume may restart at zero only under that new id, while retained post-byte
continuations do not mint another. If raw work would exceed the admitted
signed-64 item or aggregate total, admission refuses before execution rather
than permitting a later overshoot. Aggregate executor bytes retain their
monotonic high-water; verifier aggregates count all admitted physical read
work.

A settled item is named by its reliable outcome, not by later lossy progress:
later snapshots clear item, attempt, and item-byte fields. `current_path`
remains display-only and may remain after ordinary intermediate settlement.
Executor pause force-emits one coherent authoritative-live snapshot; executor
cancel/exception force-emits live aggregate items and byte high-water after
reliable unwind settlement while clearing nominal item state and
`current_path`. Verifier pause likewise force-emits its live reporter state.
Clients must never reinterpret a retained display path as active identity.

**Exact target binding:** the shared [epoch, scalar, and recording
register](#exact-epochs-scalar-classes-and-recording-views) owns the v5 envelope
cutover, `SessionEventView`/`TerminalSummary` shapes, payload epochs, strict
decode, signed-64 projection, and removal of v3/v4 compatibility. This record
owns why progress carries item identity and the reporter transitions above; it
does not restate that wire table.

The Slice 5 validated projection resolves `item_id` through the tagged
`get_plan_anchor` read. The exact event body is not enriched: the command
derives the ancestor node-id chain and returns its resolved node/index against
the current view. **Never join on `current_path`**, which remains display-only telemetry.

### DR-BR-15 — Flattened windows over a stateless visible sequence

**Binding rule.** The server derives one ordered visible sequence from the
canonical tree projection plus collapsed ids, literal search, and domain-owned
filters. Clients request exact `[offset, limit]` windows; the DOM never owns or
reconstructs the hierarchy.

The shared [result-shape register](#exact-shared-result-shapes) owns exact
`PlanView`/`InventoryView`, row/frame, window, revision, count, rollup, and
overlay fields. This record owns visible-sequence derivation and renderer
request-generation behavior.

#### Sequence contract

- Plan and inventory use the same pure flatten/window shape. One canonical
  projection exists per open view; changing view parameters replaces the
  derived sequence rather than retaining a parameter-keyed cache family.
- Every returned product row includes the generic renderer's exact flattened
  `TreeRowFrame`: `node_id`, global visible/parent/first-child indexes,
  filtered sibling position/set size, `depth`, `is_container`, and `expanded`,
  in addition to its product-domain fields.
- A folder or plan operation-group is visible only when it matches directly or retains a visible
  descendant. Synthetic-only ancestor chains disappear with the annotation they
  hosted. Folder and operation-group rollups describe their view-independent
  operation/domain population,
  while each filter chip reports its search-matching facet population before
  the active filter subset, collapse, or acknowledged hiding.
- A visible container with a retained child reports `expanded=true|false`; a
  leaf, empty root, or direct match with all descendants filtered reports
  `expanded=null` and exposes no disclosure.
- Offset is an exact nonnegative integer and limit is an exact integer from
  1 through 256. Refuse oversize or invalid requests; never return silent
  truncation that looks complete.
- `interfaces/web/visible_sequence.py` remains tree-agnostic and pure. It may
  retain source/visible indexes and accessibility metadata for one derivation,
  but no path authority, domain filter vocabulary, projection lifecycle, or
  active-view cache.
- Search is literal, case-folded display matching. The first Slice 5/6 request
  owner applies a fixed 150 ms trailing debounce, advances generation on every
  search/collapse/filter intent, sends only the final burst value, and ignores
  stale success or failure while leaving the current valid window visible.
  Task-list/rail and task-detail/panel response owners use the same local
  generation rule. A `publication_issue` observation advances those owners and its exact session-
  kind-mapped tree owner before cache disposal/refetch, so an already returned
  native snapshot cannot commit after the fault merely because server view and
  result revisions intentionally stayed unchanged.
  An accepted `closing` observation advances task-list/rail, task-detail/panel,
  and every mounted plan/inventory tree owner before pending-renderer disposal;
  the final `closed` observation advances them again before task removal. A DTO
  detached before either retirement seal is therefore inert before payload read.

#### Renderer contract

The installed renderer uses fixed 28-pixel rows, two spacers, and one tab stop.
Its only data callback is `requestIndex(index, generation)`; the Slice 5/6
owner fetches a window containing that index and commits it under the supplied
generation. Parameter changes call `beginWindowRequest`; a callback does not
mint a second generation.

Passive scroll and one per-tree `ResizeObserver` coalesce into one animation-
frame reconciliation. Missing leading or trailing spacer indexes are requested
once; covered ranges request nothing. Scroll commits preserve `scrollTop` and
reject stale generations before reading payloads. A newer user scroll invalidates
older keyboard or different-index requests, while repeated requests for the same
missing index are suppressed. An unchanged viewport does not autonomously page
again after a valid narrow response.

Before removing a root, its owner calls idempotent `dispose()`, which disconnects
the observer, removes controller-owned listeners, invalidates pending work, and
makes queued frames and later commits inert. Pointer disclosure focuses the row
and requests expansion without triggering row activation; projected terminal
nodes remain inert.

#### Text contract

Workflow nodes, derived sequences, wire windows, and literal search preserve
exact valid Unicode. Only the renderer maps the fixed active layout controls
and marker delimiters from `DEFENSE.md` to visible `⟦U+XXXX⟧` text.
That spelling is not decoded by search and creates no second wire shape. The
bridge bounds the complete serialized request at 65,536 UTF-8 bytes; the pure
helper's search input may not exceed that bound.

> **Rationale (non-normative).**
>
> Per-node lazy expansion was rejected because review defaults expanded and
> would pay one round trip per folder. Row-level windows give scroll a stable
> index and keep payloads bounded. Filtering empty ancestors prevents a skeletal
> tree, unfiltered rollups keep selection meaning stable, and fixed height avoids
> measurement-dependent window geometry. Last-request-wins plus explicit
> disposal prevents stale responses or viewport feedback loops from creating
> authority in JavaScript.

The landed presentation-core realignment and its browser evidence are recorded
under [Complete and harden the accessible desktop foundation](../CHANGELOG.md#complete-and-harden-the-accessible-desktop-foundation-2026-08-12--2026-08-18).

### DR-BR-16 — Paging bounds payload, and must also bound work

**Binding rule.** Windowing must bound repeated query, decode, allocation, and
serialization work, not only response bytes.

The shared [result-shape](#exact-shared-result-shapes) and [task-authority
registers](#task-and-authority-ordering) own byte-aware window limits,
generation pins, projection retention/refusal, and replacement lifetime. This
record owns the work-bounding placement and cache topology.

- Immutable plan trees are memoized per request id.
- Inventory uses one slim all-row structure query per projection and fetches
  full snapshots only for the visible window's row ids.
- History summaries and details page in the database under DR-BR-16.2.
- Flattening remains per-request work. If BR-G-42 demonstrates a need, one
  latest visible-sequence value may be retained per open view and replaced on
  any parameter change; a parameter-keyed cache family is forbidden.
- `preview_selection` retains its
  O(operations × dependency depth) fixpoint and is measured at the declared
  depth under BR-G-42.
- BR-G-42 owns the fixed M1 scale fixtures, reference profile, budgets, and
  evidence tier. Measurements may pass or fail that contract but may not
  redefine it after observation.

Row-level SQL `LIMIT/OFFSET` is not inventory-tree paging: ancestor synthesis
and rollups require the structure, client offsets address the post-filter
visible sequence, and lexical key order is not depth-first pre-order.

#### DR-BR-16.1 — The inventory projection's lifecycle

**Binding rule.** Inventory projections are immutable, revisioned, service-owned
objects identified by opaque `view_id`.

- The service mints `view_id`; the adapter maps its own
  `(task_id, location_id)` to that id. Opening one location in two tasks creates
  independent projections without importing adapter task identity into the
  service.
- A view change, task-owned facade-artifact release, or service shutdown releases
  the projection after its last read pin. Background views remain cached under a
  six-charged-projection least-recently-used cap. Only an unpinned generation is
  evictable; a seventh build with all six pinned returns `retention_full`. Plan-
  tree memos do not share this cap.
- Rebuilds happen outside the service guard and swap immutable references inside
  it. The LRU map and each per-view read-modify-write patch use that same
  service-side synchronization. The adapter `TaskState` lock guards adapter
  state only and is never held across facade I/O.
- Every projection has a monotonic process-local revision returned with its
  windows. A stale revision is refused so structure and detail from different
  generations cannot combine. This is an in-process projection revision, not
  the rejected database snapshot token of DR-BR-20.
- Acknowledge/restore uses pure
  `patch_row(projection, node_id, ...) -> projection` in
  `workflows/node_tree.py`. It shallow-copies the node array, shares unchanged
  nodes and indexes, replaces the one workflow-constructed node, bumps revision,
  and stores atomically. Concurrent patches cannot lose one another; a patch
  against an obsolete base is dropped.
- A session terminal that may affect many rows forces a full rebuild. Rollup
  changes from a future row-local domain patch update only the exact ancestor
  chain. Acknowledgment is deliberately absent from `InventoryRollup`, so its
  patch remains one node and changes only the visible sequence/counts.
- Eviction and causal invalidation share the stale-revision path. An in-flight
  request may finish against its immutable reference; the next request rebuilds
  or refuses stale state.

#### DR-BR-16.2 — History is paged at the database, not after it

**Binding rule.** History reads never materialize unbounded run detail before
windowing.

- `list_summaries(limit)` uses a run query plus fixed phase/aggregate queries
  and never decodes canonical event JSON. The database returns finite
  conditional facts; workflows own selection, integrity, and headline meaning.
- `get_item_page` keyset-pages dense immutable `item_order`;
  `get_event_page` keyset-pages reliable `event_seq`. Both accept limits
  1..256, fetch one raw lookahead row, and decode at most the requested limit.
- The first page captures a committed `through_*` watermark in the same read
  transaction. Later pages reuse it while new history commits. Event watermarks
  are inclusive sparse bounds and need not name a retained row.
- A fresh recovery traversal whose last accepted non-`Gap` cursor is already
  ahead of durability returns one empty terminal page. A later repair omits the
  old watermark and captures a new committed prefix; a reversed fixed interval
  is invalid.
- Terminal phase summaries have a 256-row recording ceiling and may load with a
  summary. Item and event detail may not.
- The service exposes summary, item-page, and event-page methods; CLI detail
  consumes those pages. `history_events_run_item_order_idx`, the composite
  primary key, and `history_events_run_item_aggregate_idx` serve the bounded
  seeks, pinned by query-plan regressions.
- The shared epoch register owns current and accepted history schemas. Durable
  reliable pages repair live gaps; lossy progress gaps remain valid, and
  finalized summaries supply terminal truth.

> **Rationale (non-normative).**
>
> The rejected row-page draft bounded SQL rows but could not construct correct
> tree ancestry, rollups, or visible ordering. Service-owned `view_id` avoids
> keying service state by adapter-owned task identity. Background retention makes
> the LRU meaningful; immutable swaps let active readers finish consistently;
> and shallow copy-on-write prevents a one-row acknowledgment from rebuilding
> hundreds of thousands of nodes. History keyset pages eliminate the former N+1
> full-run materialization without weakening durable gap recovery.

### DR-BR-17 — Selection is server-side state; the DOM is disposable

Virtualization destroys and recycles rows, so selection must not live in them.
Selection is owned by the service (DR-BR-03) and every window response carries
each row's current outcome, so scrolling away and back re-reads authority.

This is the same problem as view filtering, and the same rule covers both:
**a folder deselect applies to every operation under that path regardless of
which rows are currently rendered or currently passing a filter.** Otherwise
"deselect this folder" would quietly mean different things depending on which
chip is lit, with no way for the user to tell.

Interaction is debounced: a click puts the row into an honest *pending* state
rather than an optimistic result, toggles accumulate for roughly 120–150 ms,
and the batch resolves as one revisioned mutation (DR-BR-03). Batching matters
more than the delay, since range selection and folder toggles generate many
toggles per gesture.

`preview_selection` calls `derive_execution_selection` directly and **never**
`get_plan_review` — rebuilding every operation view, both scans' warnings, and
all refusals to answer "which checkboxes changed" is the wrong shape
regardless of how fast it runs.

### DR-BR-18 — Search executes on the backend

With virtualized paging the client holds a viewport, not the plan. Client-side
search would match only materialized rows and get worse as plans grow — broken
before hostile filenames enter the discussion.

Sending a query is not a DR-M1-16 violation. That rule bans JS supplying
**paths** because a path can become filesystem authority; a query never
becomes authority, it selects rows the backend already holds. Structurally it
is a view parameter exactly like the collapsed set, so it composes with
DR-BR-15 rather than needing a parallel code path — and as a backend parameter
it stays available to a headless consumer, which a frontend implementation
would not be.

Four constraints: substring matching only (a user-supplied regex is a
denial-of-service surface for no benefit), matching against the **casefolded
raw display form** rather than the canonical key, no marker decoding or other
query syntax, no trimming or Unicode normalization, and an exact 65,536-UTF-8-byte
query ceiling. The pure presentation seam accepts 65,536 UTF-8 bytes
and refuses 65,537 before walking the node array. The existing 65,536-byte
complete inbound-envelope cap remains the external authority, so JSON overhead
makes an actual bridge query smaller; future non-bridge adapters impose their
own whole-request bound. Responsiveness comes from the 150 ms trailing debounce
and last-intent-wins generation rule in DR-BR-15, not a tiny field limit.

### DR-BR-19 — Autoscroll anchors on the nearest visible ancestor-or-self

One rule removes every special case. If the current operation is visible, it
is the target; if it sits inside a collapsed folder, that folder is the target
and shows an active indicator; expanding moves the target inward; execution
moving on moves it forward. Filtering is absorbed identically, since "visible"
means after collapse and after filtering.

An ancestor chain alone is insufficient under virtualization. If the current
operation is outside the materialized window, none of its ancestors need be in
the DOM; the client could neither scroll to it nor compute the distance shown
by the follow pill.

**Resolution:** the exact Progress body carries only the opaque `item_id` and
its lookup namespace (DR-BR-14). The browser submits that identity through the
tagged item variant of `get_plan_anchor`; the service derives the candidate
node followed by its strict ancestor chain, ordered parent first through the
root, and resolves it
against the same canonical projection and active collapse/filter/search
parameters as DR-BR-15 at the supplied result revision; installation or
clearing of a fresh execution-preflight notice set changes indexes, advances
that revision, and makes the lookup return conflict with current `PlanView`.
If current search/filters remove the subject and every ancestor, the command
returns exact `not-visible` with the current `PlanView`; it does not mutate view
state or invent a root anchor. The browser keeps follow available and offers an
explicit clear-search/filters action through ordinary revisioned
`update_plan_view`. Otherwise the exact response returns the deepest visible
ancestor-or-self separately as `node_id`, its visible-sequence index, and that
node's complete bounded strict-ancestor `ancestor_ids` chain ordered parent
first through root. The node is not repeated in the array; a maximum-depth
singleton path row has at most 16,384 strict ancestors when the root is
included, and an exploded operation member has its path/group parent plus that
chain, for a maximum of 16,385. The client can then request the window containing that
index. This presentation-only lookup creates no second tree or persistent
filtered projection. `PlanWindow` carries no hidden anchor metadata, so the
command table remains the sole wire shape and every lookup uses the same pure
visible-sequence resolver.

Follow mode is on by default and any user scroll that moves the target out of
view turns it off. It re-enables only on explicit action — a persistent pill
showing the distance to the current operation, one click to resume. Silently
re-grabbing the viewport when a row drifts back into view is the standard
log-viewer annoyance and is deliberately not done.

### DR-BR-20 — No inventory snapshot token

A generation token was designed to stop a paging client from stitching two
inventory generations together, then rejected. Recorded with its reasons so it
is not reinvented:

- `PRAGMA data_version` is database-wide, so any unrelated write causes
  spurious restarts, and it does not change for same-connection commits.
- A `COUNT` plus `MAX()` aggregate over mutation timestamps **collides**:
  acknowledging one row while another already carries a later timestamp leaves
  every aggregate identical. A token that can miss a change is worse than none.
- A recorder-maintained counter is exact but needs a schema addition and a
  bump on every write path, where a missed bump is a silent staleness bug.

The deciding argument is that it solves a problem the event stream already
solves better. The client observes the session and re-reads on terminal — a
precise causal signal that says what changed and when. The only case a token
adds is a concurrent write from **another process**, and M1 deliberately has
no cross-process visibility (DR-M1-08). A token would invent partial
cross-process awareness the milestone declined to build.

**Resolution:** re-read on view open, on observed session terminal for that
location, and after an acknowledge or restore. Rendered rows key on `node_id`,
so an externally torn page degrades to a missing or duplicated row that the
next re-read corrects. Severity is low regardless: nothing in this view acts
on display position — acknowledge and restore are node-id keyed, and
verify-selected resolves ids to paths server-side (DR-BR-06). The
cross-process limit is documented alongside the task rail's existing one.

**Never auto-scan.** A refresh is a real filesystem session, and periodic
rescanning would be the scheduled maintenance DR-M1-20 defers. Staleness is
reported through `list_stale_inventory`, not silently repaired.

**Acknowledgment hides and leaves the unacknowledged-missing facet.** The purpose of acknowledging a
missing row is to make "missing" go away, so an acknowledged row leaves the
default view rather than sitting in it wearing a badge. Acknowledgment
participates in **no folder rollup** — the row remains a missing subject in
rollup truth — which is what reduces the projection patch in DR-BR-16.1 to a
single node with no ancestor walk. It remains in inventory `all` and moves from
the unacknowledged `missing` facet into the `acknowledged` facet.

Four consequences follow:

- **Hidden by default is still view state.** `hide_acknowledged` is the
  inventory tree's separate default-true Boolean, applied server-side beside
  the ordered positive filter array through DR-BR-15. The positive
  `acknowledged` filter is valid only when that Boolean is false.
- **Counts stay honest.** Because the default view is a filtered view, the
  acknowledged chip carries its own count. The hidden population is always
  visible even when its rows are not, and the missing chip reports only what
  remains missing and unacknowledged.
- **Acknowledging reflows the list.** The row leaves the visible sequence and
  everything below shifts, so acknowledge refetches its window rather than
  repainting a row in place — a different path from every other row update.
- **Restore is reached through the filter.** The workflow is filter to
  acknowledged, then restore there. This contradicts `ui_mockup/mockup.html`,
  whose context menu enables "Restore acknowledged" on an acknowledged row in
  the default listing; under this rule such a row is never in the default
  listing, and the mockup's menu logic needs revising with the rest of it.

The resulting loop is the intended one: 300 missing, acknowledge ten, they
vanish, the missing chip falls to 290 and the acknowledged chip rises to ten —
missing goes away without pretending the file came back.

---

## 5. Task and Process Lifecycle

### DR-BR-21 — A task is client state; sessions come and go beneath it

A task card outlives its sessions. It holds a plan request id, zero or one
current session id, and retained results per pane. **A task with a reviewed
but unexecuted plan has no live session at all**, so the rail cannot be
derived purely from `list_sessions()` — session-derived fields refresh from
it, but task identity is the adapter's.

**Exact target binding:** [shared result shapes](#exact-shared-result-shapes)
define `TaskSummary`, `TaskDetail`, the five named result slots, and compact
overlay presence. [Task and authority ordering](#task-and-authority-ordering)
defines one-current-session attachment, terminal reconciliation, result
revision, retained receipts, release tombstones, and the task-close boundary.
This record owns the process-live task/session distinction and its presentation
consequences.

`SessionRecordView.state` and `StateChanged` carry the core `pausing` value;
Stage 6 renders it as **Pausing…**, not `running` or prematurely `paused`.
Durable executor retries can remain in that state
while one already-staged operation settles. Repeat pause/resume controls are
disabled during the drain, cancellation remains available, and either `paused`
or a legal terminal state may follow. This is presentation of an existing
bridge value, not a payload/schema addition.

**Terminal delivery releases session authority, not the reviewed task.** Until
the terminal record has been presented successfully, the task retains the
dispatcher record, replay, observation recovery source, and service command
receipt so a lost bridge response remains recoverable without another response
cache or acknowledgment. The browser then calls
`release_terminal_session`, which unsubscribes and closes that dispatcher
session while retaining the task id, request id, start receipt, presentation
state, capacity slot, and plan artifact. Only an explicit `close_task` drops the
plan and removes the adapter task.

The shared register's item-free `TerminalSummary` and compact-overlay rules keep
the full `OperationResult` only in the dispatcher terminal record through one
reconciliation and exact-session release. BR-G-45 owns the complete task,
transient completion, native-return, browser-window, and projection-cache
artifact graph; neither the task-count bound nor successful session release
alone proves byte containment.

For a compound execute-then-verify run, the two phases are one session
producing one result with ordered `PhaseResultView`s. The rail summarizes the
latest phase; the Sync pane reads `phase="execute"` and the Integrity pane
reads `phase="verify"`. Phase counters are never summed (XV-7).

### DR-BR-22 — Closing a busy task cancels, waits, then closes

`Dispatcher.close` raises `SessionNotTerminal` for a live session, and
`NamiSyncService.close_session` calls it unguarded. Closing a running task is
therefore a sequence, not a call.

**Resolution:** the adapter owns the sequence, and the facade keeps its
precondition documented rather than growing a control policy. The exact
`close_task` row, dedicated receipt cell, retirement epoch, ordinary/cleanup
leases, terminal-callback reservation, final seal, release/close tombstones,
and replay results are centralized in [task and authority
ordering](#task-and-authority-ordering) and the [command
register](#exact-command-and-retry-rows).

**Ask first.** Closing a queued or running task requires explicit confirmation
naming what is being stopped. A misclick — or a cat — must not destroy a long-
running transfer, and cancellation is not free: the executor stops mid-plan
and the user replans from the filesystem's new state. Closing an already-
terminal card is unconfirmed, since nothing is lost. The confirmation is GUI-
owned; the CLI does not need it, being already resistant to accidental input,
but nothing prevents it adopting the same prompt.

This is not in tension with DR-BR-03 removing the execute confirmation.
Starting execution begins recoverable work the user can pause or cancel;
closing a running task destroys work already in progress, and no later control
undoes it. The prompt appears where the action is irreversible, which is the
same rule in both places.
After confirmation the accepted owner enters visible **closing**, requests the
service-supported cancel, and remains on the rail until the exact terminal
record is reconciled and the shared close barrier retires all task authority.
The terminal record—not the terminal event—is the cleanup boundary. Ordinary
terminal presentation may release only the exact session while retaining the
task; accepted task close additionally releases the task-owned facade artifact,
presentation projections, receipts, and other roots after its final lease
drain.

That terminal-record distinction is a real race, not pedantry. `SessionObserver` delivers
the `Terminal` event to the sink and only *afterward* calls
`dispatcher.get()` to build the terminal `SessionRecordView`. A client that
drains the event and immediately calls `close_session` removes the dispatcher
record out from under that lookup, and the observer thread takes
`SessionNotFound`. Cleanup therefore triggers on receiving a
`SessionRecordView` whose `result` is not `None`, which the observer emits
once the record is safely read.

Terminal cleanup remains caller-owned. A timeout before the hub gate changes no
stream state and releases the close claim, so an attachment can still succeed
before the adapter retries. Once subscriptions are detached, attach raises
typed `SessionCleanupPending` while `get`/`list` continue to expose the settled
record; the card remains closing until the caller or orderly shutdown retries
cleanup. There is no background reaper, and neither failure path rewrites the
terminal result or its settled history outcome.

If the control is refused or unsupported, the card stays open and says why.
A transient progress flag is never treated as completion. Application
shutdown with a closing card still tears down through DR-BR-24's ordering.

### DR-BR-23 — Single instance activates the existing window

**Resolution:** a named mutex guards the process. A second launch does not
open a window; it attempts to activate the running instance's window through
Win32 and exits successfully. The codebase already uses `ctypes` Win32
bindings in the executor and verifier, so this needs no new dependency and no
IPC channel. If activation fails, the second instance prints a clear message
and exits successfully. Exiting silently, or reporting an error for what is
ordinary user behavior, are both rejected.

Activation is not title-only: the process image owning the discovered HWND must
match `sys.executable` or the venv base interpreter before NamiSync restores or
foregrounds it. The fixed `Local\NamiSync.Desktop` mutex remains predictable.
A malicious same-principal process can squat that name or spoof an accepted
base interpreter, so this prevents accidental duplicate ownership but is not a
same-principal security boundary.

---

## 6. Concurrency

### DR-BR-24 — Bridge handlers are concurrent and must be synchronized

The pinned host creates one thread per exposed-function call before NamiSync
admission. The bridge admits at most 64 handlers past that gate and returns the
fixed `bridge_busy` refusal at saturation. This bounds admitted domain work and
teardown ownership, not raw WebMessage thread creation. The same admission
condition closes the race between admitted handler entry and teardown; no
bridge-global lock spans a command handler.

**Exact target binding:** [task and authority
ordering](#task-and-authority-ordering) owns atomic live-task lookup,
publication/retirement classification, claims, ordinary/cleanup leases,
owner-callback reservations, epochs, generation pins, stale-handler
compensation, retained-memory reservation, and final close. This record owns
why concurrent host callbacks require those mechanisms and the queue,
reinjection, origin, and shutdown rules local to the adapter.

The ceiling is sized for one ordinary long poll per allowed retained task plus
16 shared transient-command positions. Those positions are not
partitioned or reserved: duplicate/superseding drains and other concurrent
calls can consume them, so saturation still produces the bounded, retryable
`bridge_busy` result rather than a per-command availability guarantee.

The product window is constructed with `js_api=None` and receives one
function-table entry named `dispatch`. Pywebview never walks the dispatcher
instance, so private dotted receiver names cannot become an alternate command
surface.

DR-M1-15 established that pywebview's exposed functions run on separate
threads—one newly spawned, unbounded thread per exposed-function call in the
pinned host. `BridgeDispatcher` correctly has no locking, because the spike's
handlers were pure. Every piece of state Stage 6 adds is not, and the runtime
is protected only for what it already owns (`_plans` is lock-guarded).

- **Selection** — owned by the service and revisioned (DR-BR-03). The
  revision is what makes ordering deterministic; a lock alone is not enough.
- **Event queue and drain tracker** — DR-M1-18's ordering guarantee rests on
  "at most one outstanding drain per task," stated as a *client* obligation.
  Two concurrent drains each pop a partial batch and events arrive out of
  order. **An ordering guarantee enforced only by client discipline is not a
  guarantee**; the server holds a per-task drain guard and a second concurrent
  drain waits or is refused explicitly. Each blocking drain has a bounded
  25–30 second wait, returns an empty batch on timeout, and is explicitly woken
  on close so pywebview threads cannot accumulate forever.
- **Progress-only drain linger** — once a drain first observes only queued
  `Progress`, it anchors one 150 ms server deadline capped by the drain's
  original 25-second deadline. Replacement progress never slides that anchor.
  With an active long poll on an otherwise idle task, the first detailed
  `Progress` may therefore wait the full 150 ms; command receipt and reliable
  running-state feedback bypass that linger.
  Reliable events, `Gap`, terminal events/records, close, supersession, or
  recovery wake immediately; a response may include the latest progress before
  the reliable value when sequence order permits. This enables the coalescing
  already promised by the queue without changing retry or cursor semantics.
- **Reliable queue overflow** — the bridge queue is a second bounded handoff
  after the dispatcher's already-bounded `EventStream`, so it must not invent a
  second silent-loss policy. `Progress` is replaceable: a newer snapshot
  replaces an older queued one and may be dropped when reliable data owns the
  capacity. Reliable events and terminal `SessionRecordView`s instead wait for
  bridge capacity on the observer thread. This never blocks the workflow
  producer; if the observer falls far enough behind, the existing upstream
  `EventStream` ejects it with a visible `Gap`, and the observer's established
  resubscribe/terminal-record path reconciles. The bridge does not synthesize a
  competing gap vocabulary.
- **Lost drain response** — adds no acknowledgment protocol, echoed delivery
  cursor, response cache, or server-side per-client receipt. The client knows
  the last non-`Gap` sequence it accepted. Transport/protocol uncertainty or an
  explicit `Gap` takes the existing resubscribe/terminal-record reconciliation
  path from its exact `first_missed_seq`; uncertainty without a `Gap` starts at
  the first sequence after the accepted value. A numeric sequence
  hole is legal because queued/replayed `Progress` may coalesce, and never by
  itself triggers recovery. A lost terminal batch is recovered from the
  retained terminal record; live replaceable progress may arrive late after
  resubscribe but never fabricates continuity.
- **Bridge reinjection** — pywebview reinjects after every
  `NavigationCompleted`, including canceled or failed navigation, and rebuilds
  the in-flight return-callback table. The renderer can trigger this
  repeatedly. `pywebviewready` is therefore repeatable: frontend
  initialization is idempotent and listener registration is not duplicated.
  A current-source contract test pins pywebview 6.2.1's
  `inject_pywebview`: it signals `before_load` before starting the API-injection
  worker that can fire `_pywebviewready`, so host generation renewal precedes
  every production frontend restart.
  Every firing invalidates operational readiness and pauses each nonterminal
  drain; only `shell_ready` and `readiness_echo` use bootstrap readiness.
  Normal calls, automatic retries, and exactly one re-arm per retained drain
  resume after the current host challenge is truthfully echoed. A lost mutation response retries
  with the original gesture `command_id`; a lost drain uses the sequence
  recovery above.
- **Subscription registry** — `SessionObserver.observe` raises when a session
  is already observed, so concurrent task opens must be guarded rather than
  treated as impossible.
- **Shutdown ordering** — stop accepting dispatches, close the task/drain
  registry and wake every outstanding drain **and every reliable producer
  waiting for bridge capacity**, wait for every handler already past that gate
  to return, close every observation, then close the service. Wrong order hangs
  exit, the same failure XV-18 catches one layer down. The quiesce barrier is
  the part an accept-flag alone misses: a dispatch
  that passed the gate a microsecond earlier can still be mid-`start_execution`
  when the service closes, admitting work nobody observes and then cancelling it
  half-applied. The dispatcher already has the pattern to copy — it waits on an
  in-flight admission count before closing — and the bridge needs the same
  counter over its handlers. The wait uses one finite monotonic deadline;
  failure leaves service, logging, app-path leases, and the instance mutex
  owned for retry. Only complete service shutdown permits native owner release.
- **Native document authority** — `CoreWebView2` remains owned by the WinForms
  UI thread. One idempotent synchronous `before_load` callback attaches the
  native handlers and writes a small committed-source snapshot; setup and
  dispatch workers only read that snapshot under its own lock. Pywebview's
  managed `Source`/`get_current_url()` are not authority because a canceled
  navigation can leave them naming the rejected target while native
  `CoreWebView2.Source` remains trusted. This lock is bridge-global and never
  nests inside a `TaskState` or service lock.

The queue substructure of each shared-register `TaskState` remains one bounded
64-update queue, observation generation, and drain claim under one condition;
progress alone is replaceable, while reliable events and records remain ordered
and backpressured. **Never hold a task lock across a facade call, JSON encoding,
or other I/O.** DR-BR-11's deterministic ids avoid a node-table lock site.
BR-G-45 measures the identity-deduplicated replay/subscriber/task-queue graph
and terminal subgraphs; shell-owned SH-G-15 alone measures whole-process and
renderer/runtime growth.

---

## 7. Inherited Bridge Posture

`DEFENSE.md` owns the trust model: the packaged document is trusted code, all
values crossing or rendered by it are untrusted data, and arbitrary code in the
allowed origin is a trusted-base compromise rather than a contained principal.
This section owns the concrete bridge mechanisms beneath that policy.

Unchanged from `M1_PLAN.md` and restated only so this document is
self-contained: exactly one exposed `dispatch(command_json)`, versioned and
schema-validated and allowlisted (DR-M1-15/17); forced Edge Chromium with an
actionable failure and no MSHTML fallback; hardened pywebview settings with
`debug=False`; native `NavigationStarting`, `FrameNavigationStarting`, and
`NewWindowRequested` cancellation plus an independent per-call origin
recheck; no NamiSync-owned `evaluate_js`, `run_js`, `Window.state`, or
JavaScript construction as an application-data channel; opaque ids inbound
and validated raw display text outbound; final filesystem labels project the
fixed defended layout controls to visible injective markers through the sole
`textContent` writer; no `innerHTML`;
NamiSync uses the packaged asset server only for static assets and authorizes
no domain API through it. Pinned
pywebview 6.2.1 internally constructs JavaScript for exposed-function returns,
so its serializer/escaper is audited on every version change and covered by
the real-browser hostile-name round trip.

**The document security policy is normative and fixed.** The packaged
`index.html` carries exactly one Content-Security-Policy `<meta>` element, the
first element in `head`, whose raw ASCII content value is byte-for-byte:

```text
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
```

Both `default-src` and `connect-src` stay `'none'`: the bridge is the only
channel and needs no browser fetch, while the explicit
`script-src`/`style-src`/`img-src 'self'` directives authorize the same-origin
packaged assets. The authored `index.html`, this normative string, and the
static test's expected literal are the three witnesses — no generated HTML and
no production Python constant restate it. `M1_SHELL.md`'s SH-G-7 asserts the
wheel-shipped file equals this policy byte-for-byte.

The Stage 6 reality run refines how that posture is implemented. A pre-window
preparation step hardens pywebview and probes the WebView2 runtime through one
read-only compatibility module behavior-checked against the pinned pywebview
6.2.1 detector; a configured fixed runtime bypasses Edge-channel discovery but
not the shared .NET/netfx prerequisite read. The
start wrapper repeats preparation before pywebview initialization, then its
single zero-argument `initialized` callback refuses a non-Edge-Chromium
renderer before invoking host initialization. The host observes
`window.real_url` after the asset server has selected its random loopback port
and registers one idempotent synchronous `before_load` callback. Native
`CoreWebView2` access and event subscription occur only in `before_load` on the
WinForms UI thread, before pywebview injects application calls. The independent origin recheck
consumes a lock-protected native committed-source snapshot updated by
`SourceChanged`; it never calls pywebview `get_current_url()` from a handler. A
canceled target does not poison the snapshot, while a committed off-origin
native source does. Attachment success/failure is sticky and observable
because pywebview swallows callback exceptions; dispatch stays closed and the
host tears down actionably after failure. The exact origin is reconstructed
from the full `window.real_url` with `urlsplit`, never `rsplit`.

**Slice 2's wire contract is exact.** `assets/bridge.js` sends one JSON string
to `dispatch(command_json)`. Its UTF-8 representation is refused above 65,536
bytes before JSON decoding. Duplicate keys, non-finite numbers, malformed
Unicode, and missing or unknown fields at every defined object level are
invalid. A v1 request has exactly this shape:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "command": "pick_folder",
  "payload": {"purpose": "source"}
}
```

`schema_version` is the JSON integer `1`, not a Boolean. Transport
`request_id` and receipted-gesture `command_id` each match
`^[0-9a-f]{32}$`; a folder slot id matches `^slot-[0-9a-f]{32}$`. They are
opaque, noninterchangeable kinds. The wrapper mints a fresh request id for
every transport attempt. Success and failure return, respectively, exactly:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "ok": true,
  "result": null
}
```

```json
{
  "schema_version": 1,
  "request_id": null,
  "ok": false,
  "error": {
    "code": "invalid_request",
    "message": "The desktop request is invalid."
  }
}
```

The response echoes `request_id` only after that field independently passes
its grammar; otherwise it is `null`. The code/message vocabulary is exact:

| `code` | Fixed `message` |
| --- | --- |
| `invalid_request` | `The desktop request is invalid.` |
| `unsupported_version` | `Restart NamiSync to load a compatible desktop page.` |
| `unknown_command` | `This desktop action is not available.` |
| `invalid_payload` | `The desktop action contains invalid data.` |
| `request_too_large` | `The desktop request is too large.` |
| `slot_unavailable` | `That folder selection is no longer available. Choose both folders again.` |
| `picker_unavailable` | `The folder picker could not open. Try again.` |
| `command_conflict` | `This action no longer matches its first attempt. Start the action again.` |
| `planning_refused` | `NamiSync could not start a plan for those folders. Review both folders and try again.` |
| `task_unavailable` | `That desktop task is no longer available.` |
| `drain_busy` | `That desktop task already has an event request in progress.` |
| `observation_conflict` | `That desktop task is already observing different work.` |
| `bridge_busy` | `NamiSync is busy. Try this action again.` |
| `bridge_unavailable` | `NamiSync is closing or this desktop page is no longer trusted.` |
| `internal_error` | `NamiSync could not complete the desktop action.` |

Retry policy is
owned by the immutable command row and browser wrapper, not returned as handler
data. A structured refusal is definitive. An immutable row may declare one
identical-payload replay after uncertain transport delivery when a receipt or
revision rule makes that replay safe; only an admitted receipted command may
also declare replay after `internal_error`. Messages expose no request body, command payload, real
path, exception text, traceback, Python type, or implementation detail; a
handler exception never crosses pywebview as its native traceback-bearing error
value.

Command readiness is composition-owned. After reserving one of the bridge's 64
handler positions, rechecking exact document trust, bounding and decoding the
envelope, and resolving an allowlisted command name, the bridge calls mandatory
`admit(name)`. Host composition joins that row's declared `BOOTSTRAP` or `OPEN`
phase to the current exact `ReadinessContext`. Refusal, callback failure, or a
malformed verdict returns `bridge_unavailable` before payload validation. A
grant carries an opaque context that the bridge forwards unchanged;
`CommandSpec.invoke` exact-checks its context and phase before its payload
validator. The bridge names no readiness phase or appearance state. Handler
reservation and service/session admission remain separate mechanisms with
their existing lifetimes.

**The bilateral document-readiness rows are exact.** GUI Break 1 and its
hardening own two foundation-only rows outside Slice 2's two domain rows:

| Command | Exact payload | Exact success `result` | Identity / revision | Availability, deadline, and retry |
| --- | --- | --- | --- | --- |
| `shell_ready` | `{}` | `{"acknowledged":true}` | no `command_id`; no revision | `BOOTSTRAP` before `OPEN`; no post-open replay; 5,000 ms; no retry |
| `readiness_echo` | `{"challenge":"<32-lowercase-hex>"}` | `{"acknowledged":true}` for the current challenge after open, otherwise `{"acknowledged":false}` | no `command_id`; no revision | bootstrap plus exact post-open replay; 5,000 ms; after false or transport uncertainty, one retry with the identical payload |

The packaged module installs the fixed neutral readiness receiver before the
appearance receiver and shell DOM, then sends `shell_ready` through the existing
sole `dispatch` function. Native load and shell acknowledgement request
asynchronous initial surface-safety settlement. Only a confirmed safe surface
mints a cryptographic 32-lowercase-hex nonce and posts the exact host message
`{"challenge":"<nonce>","kind":"namisync.readiness.v1"}`. The current page
echoes that nonce with `readiness_echo`; only successful post completion and a
matching echo admit `OPEN` rows. The nonce proves current-generation bilateral
channel liveness only. It is not authorization, is never logged or persisted,
and cannot replace exact-origin trust, handler reservation, or task/session
admission.

Startup checks epoch ownership after every wait. The challenge receiver buffers
monotonic arrivals, including one arriving before the current waiter, and false
or uncertain echo delivery receives at most one identical-payload retry. A
same-origin reload begins a new closed generation before appearance or queued
posts can run; the UI-queued host post rechecks generation currency immediately
before WebView2 delivery. Once open, `shell_ready` is unavailable, while an
exact `readiness_echo` replay may obtain the truthful open result. Refusal or
close makes every row unavailable. The fixed five-second deadline starts at
each native `loaded`; it is product policy, not empirical acceptance evidence.
Appearance publication and enhancement quality are independent after a safe
base surface settles. Only an unconfirmed opaque rollback after native surface
mutation refuses startup.

**The Slice 2 production allowlist has exactly two rows.** Payload and result
schemas in this table are exact; Slice 2 adds no dormant or placeholder command
name.

| Command | Exact payload | Exact success `result` | Identity / revision | Deadline and retry |
| --- | --- | --- | --- | --- |
| `pick_folder` | `{"purpose":"source"}` or `{"purpose":"target"}` | cancel: `null`; selection: `{"id":"slot-<32-lowercase-hex>","display":"<valid Unicode string>"}` | no `command_id`; no revision | interactive native operation; no client deadline and no automatic retry; another gesture is a fresh attempt |
| `start_plan` | `{"command_id":"<32-lowercase-hex>","source_id":"slot-<32-lowercase-hex>","target_id":"slot-<32-lowercase-hex>","deletion_policy":null}` or the same key set with `"trash"` or `"additive"` | Slice 2: `{"request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}`; Slice 3: `{"task_id":"task-<32-lowercase-hex>","request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}` | required `command_id`; no revision because it creates a session rather than acting on a revisioned view; Slice 3's adapter task receipt returns the same task id on replay | 30,000 ms; after uncertain delivery, bridge reincarnation, or `internal_error`, at most one automatic replay has a fresh request id and the identical command, payload, and command id; an exposed manual Retry retains that command id |

`null` consumes the service's current semantic deletion setting; `mirror` is
not accepted here. Automatic replay uses the identical payload. The service
receipt ultimately keys the resolved source/target pair plus deletion policy:
the same resolved intent returns its retained receipt and different resolved
intent under that command id returns `command_conflict`. A JavaScript deadline
does not cancel an already admitted Python handler.

**Slot path ingress is versioned.** In the currently implemented pre-checkpoint-
6 Slice 2 mapping, only the native picker can create a server-side slot. The
accepted checkpoint-6 target replaces that narrow rule with picker, typed, and
remembered-location inputs through the one workflow admission service and adds
the `inventory` purpose; the exact target rows and slot rules above are the
authority for new work. A current Slice 2 slot retains the real path, `source`
or `target` purpose, inert display text, fixed monotonic expiry 30 minutes after
insertion, and LRU recency. Lookup is nonconsuming and updates recency without extending expiry.
Expired entries are swept before insertion or lookup; at most 32 unexpired
entries exist, and an insertion at capacity evicts exactly the least-recently
used entry, with slot id breaking a timestamp tie. `start_plan` resolves and
snapshots both slots under one lock, requires one live purpose-matching source
and target in that same observation, and only then updates both recencies.
Fabricated, expired, evicted, and wrong-purpose ids have the same sanitized
`slot_unavailable` result. The browser receives only `{id, display}`, sends only
ids back, and can never promote `display` to filesystem authority.

An exact `start_plan` replay is checked against its retained wire intent before
these volatile slots are resolved, so an earned receipt survives slot expiry or
eviction. Its identity is the gesture `command_id`, the exact original
source-slot/target-slot/deletion-policy wire intent, and the resolved
source/target/deletion intent. A different wire or resolved intent under the
same command id remains a conflict.

The production command mapping is exactly `shell_ready`,
`readiness_echo`, `pick_folder`, `start_plan`, `next_events`,
`release_terminal_session`, `close_task`, `read_cosmetic_section`, and
`replace_cosmetic_section`.
`test_report` is a test-owned constructor-only harness row: the harness builds
a new immutable mapping from those production rows plus its own
validator, handler, payload, and result schema under `tests/`. No product argv,
environment, page value, or bridge request can enable it, and it has no product
retry class. Later plan, inventory, semantic-settings, and history commands
are not reserved or allowlisted until their owning slices
land each row with its schema, receipt/revision rule, deadline, retry policy,
and gate.

The existing Python/JavaScript command-policy mirror mechanically compares
each production row's availability phase as well as its timeout and retry
class. A browser/server phase drift therefore fails the owning static test
instead of silently changing admission.

`release_terminal_session` accepts exactly `{task_id, session_id}` and returns
those exact echoed ids. It is a mutating lifecycle acknowledgment with no
`command_id` or revision, a 30-second deadline, and finite delayed retries that
retain the identical payload. `close_task` remains the separate explicit
disposal operation.

`bridge.js` exports the neutral browser transport primitive
`dispatchInteractive(command, payload, validator)`. It accepts only a 1--64
ASCII lowercase-snake wire name matching
`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$` and a callable result validator, and performs
one attempt with no client deadline and no automatic retry; payload validation
belongs to the constructor-supplied Python command row. `pickFolder` and the
headed harness's constructor-only `test_report` client share this primitive.
The primitive only formats and submits a request: it neither registers nor
allows the name. The Python mapping remains the sole allowlist, while the
`test_report` literal, validator, payload/result schemas, and handler remain
tests-only and absent from the wheel.

**Slice 3's wire extension is exact.** It adds only `next_events`; the
production mapping then contains `pick_folder`, `start_plan`, and
`next_events`. Its payload is exactly
`{"task_id":"task-<32-lowercase-hex>","session_id":"<32-lowercase-hex>","drain_id":"<32-lowercase-hex>","replay_from":null}`,
or the same keys with a positive integer first-desired sequence. Its result is
exactly the echoed task/session/drain ids plus `updates`, an array of zero to 64
members. Each member is exactly
`{"update_type":"event","event":<SessionEventView>}` or
`{"update_type":"record","record":<SessionRecordView>}`. The server wait is
25 seconds and the browser deadline is 30 seconds. `SessionEventView` is
exactly `session_id`, `sequence`, `at`, `schema_version`, `body_type`, and
`body`; its `schema_version` is the nested core event version `4`, independent
of the containing bridge command/response schema `1`. A terminal record
returned by `start_plan` carries the workflow's exact `kind` value,
`"sync-plan"`; the
browser validates that production identity rather than an adapter-only alias.
Empty timeout success arms
the next ordinary drain. Transport/protocol uncertainty uses a fresh drain id
and `replay_from=last accepted non-Gap sequence + 1`; an ordinary explicit
`Gap` remains visible, stops later updates, and uses its exact positive
`first_missed_seq`;
numeric holes caused by legal progress coalescing do not. The response contains
no acknowledgment, cursor, receipt, `has_more`, or echoed replay value.

When the queued response is progress-only, the server waits at most one fixed
150 ms linger from first progress availability. Further progress replaces the
queued snapshot without extending that deadline. Any reliable event, `Gap`,
terminal event/record, close, supersession, or recovery ends the linger
immediately. This includes the first progress-only response: under an active
long poll it may consume the full 150 ms, while receipt and reliable state
bypass that linger. The 25-second long-poll deadline remains the outer bound.

The browser validates the whole response before applying it. Validation and
application are atomic: if any member, including a Progress body, is malformed,
no callback runs, the accepted-sequence cursor remains unchanged, and reliable
siblings in that batch are not partially consumed. Uncertainty recovery can
then cleanly replay the reliable siblings from both sides of the malformed
event, which are applied exactly once. On an
ordinary or uncertainty-recovery response, the first `Gap` remains visible,
stops application of later updates, and arms recovery from its
`first_missed_seq`. A recovery response may begin with the matching `Gap` whose
`first_missed_seq` equals that attempt's `replay_from`; this proves the prefix
is no longer retained, so the browser preserves the gap, applies the available
tail, and does not loop. A later or different `Gap` becomes a new recovery
point. Accepting a terminal record stops the task's drain loop even when it
follows that matching leading gap; terminal truth never erases the visible
loss.

Validation also preflights the applicable batch through a pure, immutable
Progress reducer before moving the cursor or invoking a callback. Its derived
view is supplied as the optional second `acceptUpdate(update, progressState)`
argument, so existing one-argument consumers remain compatible. Retained state
and the exposed view own only `phase`, `phaseAuthority` (`phase_changed`,
`progress`, or `unknown`), the latest accepted Progress body, and the derived
active item. `PhaseChanged` starts a fresh temporal domain only when its phase
changes; repeating the same reliable phase promotes authority without
discarding aggregate, item, or attempt comparisons. Progress must agree with
reliable `phase_changed` authority. After `Gap`, progress-only authority remains
lossy: a later self-described snapshot with a different phase replaces it and
starts a fresh temporal domain because the intervening reliable phase change
may be outside the retained replay tail. Same-phase Progress still retains all
comparisons. Aggregate item/work counters cannot regress. Known selected-item
admission is fixed,
executor byte admission is fixed once known, and verifier byte admission may
grow; an unknown aggregate total may become known once. One attempt's
determinate counters cannot regress,
change total, or reappear after becoming indeterminate. Attempt comparison is
bounded to the current active item, and a reset token must differ from that
item's current attempt token. A newer lossy snapshot may repoint activity to a
different item without an observed inactive snapshot or reliable outcome: the
intermediate clear is itself replaceable and may have been coalesced away.
That handoff says nothing about settlement, which remains outcome-owned. The
reducer nevertheless rejects adjacent reuse of one non-null attempt token
under two different item identities, because an attempt belongs to exactly one
item.

Reliable matching outcomes clear derived activity even if the later inactive
Progress snapshot was coalesced away. In the compound verify phase, an
`IntegrityOutcome` with the matching plan-operation id clears the active
`operation` identity without reinterpreting the outcome's reliable namespace.
The just-settled identity cannot become active again without an intervening
inactive snapshot, different active identity, or temporal domain.
An authoritative inactive Progress may also clear activity at a reporter's
exception boundary. `Gap` clears phase-dependent Progress state and temporal
comparisons; a later self-described v4 Progress may restore displayable phase
authority without reconstructing missed outcomes. `Terminal` and the terminal
session record clear Progress and remain final truth. A pause state does not
clear activity, and `current_path` never creates or joins identity. Callback
views are frozen copies, so presentation code cannot mutate retained authority.

The adapter queue is exactly 64 updates. A new `Progress` replaces an older
queued progress or is discarded when reliable data owns every slot. Reliable
events and terminal records may evict progress but never another reliable
update; an all-reliable full queue blocks its observation sink until drain or
shutdown. Exactly one drain per task removes up to 64 FIFO entries. A second
marks the incumbent superseded, wakes it, waits
under the same 25-second bound for its claim to release, then returns
`drain_busy`; reinjection therefore has a bounded one-rearm convergence rule.
Unknown/closed or mismatched task/session authority is
`task_unavailable`; a competing observation attach/recovery generation is
`observation_conflict`. Their fixed messages are defined by the table above.

The currently active Slice 3 adapter uses the same retained-task count ceiling.
After a terminal
record has been returned by a drain, `release_terminal_session` stepwise
unsubscribes and closes the session, then refuses further drain/recovery while
retaining the plan, task, start receipt, and capacity slot. `close_task`
completes either unfinished step, drops the plan, and alone removes the task and
start receipt. Its current 48-entry close-receipt LRU proves success to a delayed
retry. Browser drain, session-release, and explicit-close recovery use finite
delayed schedules and become visibly retryable when their budget is exhausted;
no uncertainty path implicitly disposes of the task.

Checkpoint 4 retains that count cap but replaces the current close LRU
with the globally charged, non-evictable five-minute release and close
tombstones defined above. It also closes the BR-G-45 representation decision:
the dispatcher terminal record alone temporarily owns the full result through
terminal reconciliation; the task then retains the compact summary, frozen
overlays, and reviewed artifacts until explicit close, while history retains
the attempt independently. The mechanically derived task/transient byte budget,
not the count cap, enforces that target. Its implementation and evidence remain
open until checkpoints 4 and 11; the contract itself is no longer undecided.

Task start is single-flight per `(command_id, resolved source, resolved target,
deletion policy)`. One provisional adapter task exists while the facade call is
outside the task lock; same-intent callers wait and different intent conflicts.
Success binds and returns one task/request/session triple. Facade, admission, or
attach failure wakes same-intent waiters with the same sanitized refusal and
removes every provisional task/command entry after they release it; no failed
task id is exposed or retained. Failure after facade success compensates by
unsubscribing, closing the session, and dropping its plan outside the task lock.

Normal attachment precedes schedulability. The service plan start accepts an
optional sink excluded from its command-receipt signature. The domain-blind
dispatcher constructs an unpublished record/hub/store row and preopened stream,
passes `(session_id, stream)` to an optional attach callback, and receives an
idempotent rollback. Only after adoption succeeds does it emit `PENDING` while
the session remains unschedulable, then atomically publish the maps, append
pending, and notify the scheduler under its gates. Every exception through
`PENDING` emission and atomic publication takes the same path. Attach is atomic
from dispatcher ownership: it returns rollback only after complete adoption,
or raises after self-reverting every partial observer entry/thread. Once
ownership transferred, dispatcher invokes rollback first so it signals, closes, joins,
and identity-removes that adopted observation, then closes remaining
stream/hub ownership and drops the store row. Cleanup failure never replaces
the initiating error; it remains dispatcher cleanup-pending ownership, makes
shutdown incomplete, and can never become schedulable. Recovery uses
the service observer's explicit positive `from_sequence` resubscribe seam and
replaces one adapter observation generation without holding a task lock over
the facade call. Reobserve returns `SessionRecordView`: nonterminal means the
replacement sink is installed; terminal means no stream was installed and the
registry enqueues that record. Per-task serialization ensures close can clean a
replacement that returned after its generation became stale.

At Slice 2 closure the exact packaged frontend set is `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`. The last owns the strict production
`renderText(element, text)` sink and remains the only `textContent` writer.
Slice 4 adds `renderFilesystemText(element, text)`: it rejects non-strings,
maps the exact `DEFENSE.md` set to injective uppercase `⟦U+XXXX⟧` markers, and
delegates the final write to `renderText`. It is used only for
filesystem-derived `row.display`; generic interface copy is not rewritten.
Browserless transport/render probes and the headed transport page live under
`tests/assets/`, not package data.

The headed gate composes its single `test_report` row only through the same
dispatcher constructor used by production, under a unique test identity and an
absolute physical local page/data root. It automates the real native folder
picker without a foreground-forcing API, localized-label lookup, or synthetic
mouse/keystroke input: UI Automation classifies the exact edit and confirmation
controls, then a visible, enabled, same-dialog/process/thread native `Button`
with control id `1` receives one queued `BM_CLICK` per validated attempt, with
at most one reclassification-bound retry. Exact dialog closure and the later
selected-path assertions prove processing rather than treating `PostMessageW`
admission as selection. The gate proves selected paths stay
behind purpose-bound ids, commits an independent second loopback origin and
verifies zero handler calls, and round-trips the hostile corpus through the real
pinned return transport and production sink. Renderer/log evidence is read from
native `BrowserVersionString`; logs contain neither request bodies,
real paths, hostile sentinels, tracebacks, exception text, nor `NICKNAME`.
The installed-wheel browser scenario also drives the production `bridge.js`
drain manager through stale readiness and generation settlements, identical
`start_plan` replay, numeric holes without recovery, explicit-`Gap` recovery,
busy and malformed refusal budgets, nested hostile-Unicode public views,
the real `sync-plan` terminal-record identity, terminal release without
automatic task close, and task/listener/timer cleanup.

**`ui-state.json` carries cosmetics only.** `M1_PLAN.md` DR-M1-03 established it
as the GUI-owned counterpart to `db/settings.json`. The ratified strict v1 schema
contains only the appearance override; later window geometry, column and sort
state, active filter chips, and file-list treegrid state require explicit typed
section additions whose durable keys are ratified by their owning slice.
Ledger-derived recents never enter UI state. It may **not** hold a plan
request id, a session id, a task identity, a selection, a `view_id`, or a
projection revision. The distinction is not stylistic — anything in the
second list would be a durable session store arriving through the back door,
unreconciled with the process-local truth it would contradict on the next
launch.

### DR-BR-28 — Cosmetic persistence crosses one typed section channel

The bridge thaw adds two generic-shaped commands and one accepted section,
then refreezes the protocol. Future cosmetic sections extend a source-owned
registry with their own bounded value schema; they do not add one bridge
command per widget and do not pass through semantic settings or the service
facade. The v1 appearance value is exactly `{"theme":"system"}`,
`{"theme":"light"}`, or `{"theme":"dark"}`.

| Command | Exact payload | Exact success `result` | Identity / revision | Availability, deadline, and retry |
| --- | --- | --- | --- | --- |
| `read_cosmetic_section` | `{"section":"appearance","value_version":1}` | `{"section":"appearance","value_version":1,"revision":N,"dirty":false-or-true,"value":{"theme":"system-or-light-or-dark"}}` | `READ_ONLY`; `command_id` and request revision metadata forbidden; returns a nonnegative JavaScript-safe process-local section revision | `OPEN`; local 5,000 ms; after transport uncertainty or timeout, at most one retry with the identical payload and a fresh request id |
| `replace_cosmetic_section` | `{"section":"appearance","value_version":1,"expected_revision":N,"value":{"theme":"system-or-light-or-dark"}}` | the read result plus `"disposition":"applied-or-noop-or-conflict"` | `MUTATING`; `command_id` forbidden and request revision metadata required; `expected_revision` is a non-Boolean JavaScript-safe integer | `OPEN`; local 5,000 ms; no automatic replay; after transport uncertainty or timeout, reconcile through `read_cosmetic_section` before another replacement |

Every object is exact: missing or unknown members, another section, a
`value_version` other than the non-Boolean integer `1`, an invalid theme, or a negative, fractional, Boolean, or
greater-than-`9007199254740991` expected revision is `invalid_payload`. No new
bridge error code is added. Each loaded section starts at revision zero;
accepted value changes advance its process-local revision by one and also
advance one private process-local document generation. The document generation
is not persisted or exposed; it orders whole-file snapshots across all current
and future sections. `dirty` is
document-wide because all sections share one atomic file; it covers a pending
or failed save and the session-only fallback used for unsupported forward state.

Replacement is serialized and follows this complete decision table:

- current revision plus a different value updates memory, advances the
  revision, notifies isolated subscribers, and returns `applied` with
  `dirty:true`. When persistence is permitted it schedules the new current
  document generation for the shared writer; forward-version protection instead keeps the
  value session-only without touching the file;
- current revision plus the same clean value returns `noop` without writing;
- current revision plus the same dirty value returns `noop` and explicitly
  schedules the current document generation when persistence is permitted; forward-
  version protection performs no attempt;
- stale revision plus the already-current value returns `noop` without another
  write, making duplicate delivery harmless;
- stale revision plus a different value returns `conflict` without mutation or
  persistence.

A subscriber failure is logged without its exception text, cannot change an
accepted disposition, and cannot prevent other subscribers from observing the
revision. Registration and current-snapshot capture are atomic; callbacks run
outside the state lock, carry the revision, and consumers discard non-newer
delivery so appearance composition has neither a read/subscribe gap nor a
reversed-notification regression. Cosmetic reads and writes never invoke
the service, registry, planner, task state, semantic settings, or plan hashing.
They remain independently degradable and do not participate in readiness.

The on-disk v1 shape is exactly:

```json
{"schema_version":1,"sections":{"appearance":{"value_version":1,"value":{"theme":"system"}}}}
```

The owner reads at most 1 MiB plus one sentinel byte before UTF-8 decoding or
JSON construction and rejects duplicate keys, non-finite values, excessive
nesting, and every unknown or malformed member. Missing state yields clean
defaults and creates no file. The unversioned prototype is recognized only by
its exact top-level key set — `recent_sources`, `recent_targets`, `window`,
`columns`, and `sort`; it and a malformed current document yield dirty defaults
and a sanitized diagnostic, but load itself does not mutate the artifact. A
newer document schema or appearance value
version yields dirty session defaults with persistence blocked for the life of
that owner. An existing artifact that cannot be read likewise yields dirty
session defaults with persistence blocked; the owner never overwrites content
it could not inspect. An older binary never overwrites state it cannot
understand.
Adding a registered section advances the global document schema and starts the
new section at value version one. Changing an existing persisted value shape
advances both the global schema and that section's value version. The canonical
encoded document is checked against the same 1 MiB ceiling before any write.

The single process-local writer waits 250 ms after an explicit schedule. Each
schedule captures the private document generation and the complete typed
document. A newer accepted document generation cancels and replaces a pending attempt before it
starts, so intermediate revisions coalesce; an attempt already in progress is
serialized ahead of the newer snapshot. A completed write may mark the
document clean only when the written document generation is still current.
Every explicit
schedule receives at most one atomic attempt, and a superseded pending schedule
receives none. A failed document generation may be scheduled again only by a later
same-value request carrying that current revision; close never invents that
retry. Failure preserves the accepted session value,
leaves `dirty` true, and logs only a stable event plus exception type. Access
or path failure, full disk, and unclassified I/O end that attempt immediately;
there is no timer retry loop.

Close first stops new cosmetic commands, then cancels a pending timer and waits
for any in-flight atomic replacement. It flushes the current snapshot exactly
once only when its document generation is dirty, persistence-permitted, and
has never been attempted; it does not retry a failed document generation and never writes
unsupported forward state. Missing state is not created merely by launch.
There is no cross-process mutex. Save failure remains a sanitized log event in
this checkpoint; `dirty` is retained for a later settings surface and does not
replace the operational shell status. After uncertain replacement delivery or
timeout, the page performs a guarded section read and
reconciles before enabling another theme change. An unchanged expected
revision remains delivery-ambiguous and disabled. A same-realm bridge
generation waits the prior replacement settlement before its initial read. If
a full document replacement destroys that realm, a later validated native
appearance publication triggers another authoritative section read on the
healthy publication path; this converges a late prior-document mutation but
does not claim a zero-stale interval while publication is pending or degraded.

---

## 8. Verification

### DR-BR-25 — Hostile-name rendering is proven in a real browser

An earlier draft substituted a source scan for a DOM test and conceded it did
not prove filesystem text becomes a text node. That does not satisfy
`DESKTOP_UI.md`'s acceptance requirement that hostile filenames render as
text, and it is weakest exactly where the risk is highest: the starting
mockup renders through `innerHTML` throughout, so the property being asserted
is the one most likely to regress.

**Resolution: both layers, and the DOM test is required.**

- **Staged WebView2 integration tests** drive real page JavaScript through
  `window.pywebview.api.dispatch`, the Python handler, and pinned pywebview's
  internal `evaluate_js` return transport. Slice 2 renders the scanner's
  hostile-name corpus through the production inert-text path in the
  constructor-only harness and reads `.textContent` back byte-for-byte; this
  proves the real return transport and shared sink without pretending the later
  product surfaces exist. Slice 4 separately drives every defended layout
  character plus marker delimiters through the installed production tree and
  proves the exact visible markers in both DOM and Chromium accessibility
  names, no surviving active layout control, unchanged ordinary Unicode/markup-
  like and long labels, and raw opaque ids at callbacks. Slice 5 repeats both
  corpora against the actual plan DOM and slice 6 repeats them against the
  actual inventory DOM. BR-G-32 remains open until those product surfaces prove
  text, not markup, attributes, or script.
- **A broadened static scan** over packaged assets, because scanning only for
  `innerHTML`, `eval`, and `Function(` misses most markup sinks. It also
  rejects `outerHTML`, `insertAdjacentHTML`, `document.write`, `srcdoc`,
  `DOMParser`, `Range.createContextualFragment`, dynamic `setAttribute` names,
  assignment of returned data into `href`, `src`, `style`/`cssText`, or any
  `on*` attribute, plus `eval`, `new Function`, and string-form timers. This
  source scan proves only that NamiSync-owned code constructs no JavaScript;
  it cannot prove or inspect the third-party return transport.

The split evidence has concrete homes:

- `tests/interfaces/web/test_commands.py`, `test_transport.py`, and
  `test_slots.py` own separately discoverable ordinary `test_br_g_32_*` nodes
  for the immutable table, public-view codec manifest, exact envelope/refusal
  boundary, receipt identity, and slot lifecycle. `test_frontend_static.py`
  owns the prefixed packaged-asset sink scan.
- `tests/interfaces/web/test_transport_headed.py::test_br_g_32_hostile_text_crosses_real_return_transport_and_production_text_sink`
  owns the real pinned-pywebview hostile-text return path through the
  constructor-only harness.
- Separate `test_br_g_32_*` nodes in `test_transport_headed.py` own real
  native-picker confinement and independent off-origin dispatch refusal.
- `tests/interfaces/web/test_sync_surface.py::test_br_g_32_plan_dom_hostile_text`
  and
  `tests/interfaces/web/test_inventory_surface.py::test_br_g_32_inventory_dom_hostile_text`
  own the production plan and inventory DOM stages in slices 5 and 6.

Thus Slice 2 closes BR-G-32's transport, picker, origin-refusal, and static-sink
portion of XV-19 without claiming that transport alone proves a later DOM sink.
It also closes SH-G-3. Slice 4 closes the generic filesystem-label sink and
installed-tree portion of XV-19 through SH-G-7/BR-G-34. The production plan and
inventory DOM clauses remain open for Slices 5 and 6, so BR-G-32 as a whole
remains open.

### DR-BR-26 — The node tree is a pure function

Plan review plus collapsed set plus deselected set to an ordered node list,
tested directly in pytest with no bridge involved. It is the largest new
component and must not be entangled with transport, or it becomes untestable
exactly where risk concentrates. Coverage includes a hostile-named directory
move, since grouping does segment arithmetic on canonical keys while
retaining raw display paths for the final presentation sink and the two must
stay consistent.

Because node identity now arrives in Stage 5.5 (DR-BR-11), that stage carries
its own hostile-name case: **inventory** node ids minted from hostile paths,
round-tripped through exact-row and recursive-subtree command resolution plus
foreign-location refusal. The directory-move case above belongs to slice 5 and
does not cover it.

### DR-BR-27 — Receipted commands are idempotent; revisioned-view mutations are guarded

Selection needs both properties in DR-BR-03, but they are not one universal
mutation schema. The [exact command register](#exact-command-and-retry-rows) declares
receipt class, retry policy, payload/result variants, and revision order per
row; [task and authority ordering](#task-and-authority-ordering) owns receipt
capacity, lookup precedence, claims, leases, publication, and retirement.

**Resolution: keep retry identity and stale-view authority orthogonal.**

- A receipted user gesture mints one `command_id` and reuses it byte-for-byte
  after delivery uncertainty. Changed intent under that id is
  `command_conflict`; an unrecognized id alone proceeds to mutable authority
  checks and outside work. Interactive picker, reads, drain recovery, and exact-
  session release use their distinct non-M retry rules from the register.
- Receipt storage follows the command family. Pre-task Setup uses the bounded
  TTL table and unpublished start claim; successful task creation transfers the
  start receipt and its global route into task-owned capacity. Existing-task M
  commands retain their exact effect until task close, including the original
  started `session_id` after terminal-session release or a successor attach.
  The reserved close cell becomes the global close tombstone only after lease
  drain. Exact-session release instead uses its pre-reserved bounded tombstone.
  Recorder receipts remain subordinate durable idempotency for the exact domain
  write; they do not replace the bridge receipt or its task lifetime.
- Replay means *do not repeat the effect*, not necessarily *return the original
  bytes*. The shared replay table defines each current projection: an earlier
  applied view/visibility effect becomes `noop`, a started session retains its
  original identity plus current task detail, and accepted close reports current
  `closing` then the exact tombstoned `closed` object.
- A command formed against selection, lifecycle, view-state, projection, or
  result authority carries only the revisions named by its row. Receipt lookup
  precedes those guards. For a new command the guard and any recursive folder
  expansion/frozen selection are one owning-lock decision, so the admitted
  scope cannot differ from what the checked revision named. Conflict is a typed
  no-effect result; the browser rehydrates rather than guessing or retrying
  stale intent.
- `dispatch` origin authorization is entry-only. Navigation or bridge
  reinjection after admission cannot roll back committed work; uncertain
  delivery reuses the same command id and the browser request-generation rules
  prevent a late response from regaining UI authority.

The recorder's receipt also covers the exact scope it applied.
`record_inventory` hashes DR-BR-06 subtree roots as well as exact paths; an
equal scope token cannot authorize materially different recursive work.

---

## 9. Deferred, Rejected, and Resolved

This section records dispositions only. Live rules remain in their DR-BR section
or BR-G gate; dated delivery and evidence remain in the changelog and owning
artifact documents.

### Rejected

| Proposal | Disposition |
| --- | --- |
| Inventory snapshot token | Rejected — causal rereads plus projection revision cover the owned consistency boundary without a database generation. |
| Per-node lazy expansion | Rejected — expanded review would cost one round trip per folder; bounded visible windows serve the same hierarchy. |
| Move-group thresholds or sub-windows | Rejected — a move is one paired annotation, not a second paging or selection unit. |
| Synthetic operation ids for structural folders | Rejected — scope-qualified node ids represent structure without impersonating operations. |
| Client-side search or filtering | Rejected — the client sees only a window and cannot filter/search the authoritative unmaterialized set. |
| Merge safety exclusions with user deselection | Rejected — reselection could silently readmit planner-refused work. |
| Discard late selection by request id | Rejected — revision conflict is the authoritative concurrency decision. |
| Path-only node ids | Rejected — identical relative paths across scopes would collide. |
| Inventory row-level SQL paging | Rejected — row order cannot express synthesized ancestry, rollups, or the post-filter visible sequence. |
| Freeze selection permanently at commitment | Rejected — failed admission or a terminal unrun attempt would strand a safely editable reviewed subset; permanent freeze begins at ran authority consumption. |
| Typed desktop confirmation phrase | Rejected — ordinary explicit confirmation supplies the intended irreversible-action friction. |
| Stage 5.5 CLI acknowledgment commands | Rejected — ids were undiscoverable and a coherent CLI contract exceeded the facade-lift scope. |
| Release every background projection | Rejected — it makes the LRU cap unreachable and defeats fast task switching. |
| Deep-copy a projection for one-row patch | Rejected — it restores O(n) allocation for a local change. |
| `cli → web` launch import | Rejected — a sibling import violates the interface boundary; the launcher owns selection. |
| Reconstruct deselection reasons from selected ids | Rejected — final membership cannot recover user-choice provenance. |
| Exact-path semantics for folder commands | Rejected — it silently omits descendants and cannot discover new files during refresh. |
| Generalize the exact-path scanner for recursion | Rejected — exact-path ignore semantics make ordinary recursive scopes inconclusive. |
| Restate subtree incompleteness causes | Rejected — a closed copy would drift from the shared full-walk contract. |
| Predict folder-integrity descendant counts | Rejected — each mode owns a different eligibility set. |
| Confirm folder integrity actions | Rejected — the operation is non-destructive, pausable, and cancelable. |
| Client-only autoscroll anchor | Rejected — the target may not be materialized in the DOM. |
| Second bridge reliable-loss protocol | Rejected — dispatcher `Gap` plus durable reconciliation already owns visible loss. |

### Deferred

| Work | Reopen condition |
| --- | --- |
| Integrity continuation restructuring | A late-run 10k/100k/large-folder pause benchmark demonstrates unacceptable cost. |
| Filter-exclusion visibility in plan review | A product slice owns the missing review explanation. |
| Eliminate `get_plan_review` full-view rebuilding | A measured caller still pays it after memoized tree and direct preview paths. |
| Persist selected-kind/integrity history summaries | A later schema-version decision owns the columns; M1 does not add a fallback. |

### Resolved

| Disposition | Landed record |
| --- | --- |
| User selection, subtree scope, partial subject-local integrity, and page size use the contracts in DR-BR-01–06 and DR-BR-15. | [Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30) |
| Recorder mutations use reproducible row receipts; session-creating commands use service-held lifecycle receipts. | [Close the M1 safety and post-refactor audit](../CHANGELOG.md#close-the-m1-safety-and-post-refactor-audit-2026-08-08--2026-08-11) |
| Drain recovery triggers only on explicit `Gap` or uncertain drain failure; legal progress sequence holes do not trigger it. | [Close transport custody and realign the bridge boundary](../CHANGELOG.md#close-transport-custody-and-realign-the-bridge-boundary-2026-08-13--2026-08-14) |
| The 100,000-subject performance fixture and transport-custody authority are governed by BR-G-42; terminal artifacts remain separate under BR-G-45. | [Ratify measurement and documentation authority](../CHANGELOG.md#ratify-measurement-and-documentation-authority-2026-08-14--2026-08-18) |
| Move-ghost filtering removes synthetic-only ancestors with the ghost. | [Complete and harden the accessible desktop foundation](../CHANGELOG.md#complete-and-harden-the-accessible-desktop-foundation-2026-08-12--2026-08-18) |

---

## 10. Delivery

### Packaging

`pywebview` is a required runtime dependency. `nami-sync` and
`python -m namisync` remain CLI-only and point no-subcommand users to
`nami-sync-gui`, which launches without a retained console. Missing or
incompatible WebView2 is refused with an actionable error; MSHTML is not a
fallback.

`interfaces/launcher.py` sits above the sibling CLI and web adapters and
imports only the selected adapter lazily:
`launcher → {cli, web} → service`, while `cli ↮ web`. Explicit CLI work
does not import or initialize `pywebview`; GUI code remains under
`interfaces/web`. BR-G-19 enforces this boundary.

### Stage 5.5 lanes

Stage 5.5 used three disjoint implementation lanes converging on the facade.
The table remains as ownership context for its gates; delivery status is in
[Add scoped review trees and revisioned selection](../CHANGELOG.md#add-scoped-review-trees-and-revisioned-selection-2026-07-30).

| Lane | Owns | Delivery | Depends on |
| --- | --- | --- | --- |
| **A — Tree substrate** | `core/pathing.py`, `workflows/node_tree.py`, `modules/planner.py` | Shared path helpers, hierarchy/index, scoped ids, pure tree tests | — |
| **B — Scan scope** | `core/models.py`, scanner, recorder, inventory workflow | `SUBTREES`, shared walk, literal reconciliation range, inventory v2/warnings | — |
| **C — Selection semantics** | Selection, execution/payload/view/sync workflows | Deselection provenance, payload v4, re-derivation, closure, `all-noop` truth | — |
| **D — Facade** | Service and workflow runtime | Revisions/commitment, inventory lifts, opaque-id commands, receipts, preview | A, B, C |

A, B, and C could land independently; D was the integration point. The table
owns production boundaries, not every later consumer: projection ownership,
`patch_row`, `view_id`, and projection revision belong to Slice 6, while
DR-BR-14 belongs to Stage 6. Stage 5.5 was verified headlessly at the facade and
each owning scanner/recorder/codec/tree boundary; it did not add CLI surface or
desktop presentation.

### Acceptance gates

A BR-G gate is closed only by its stated production entry point and
counterexample. Every gate has a collected `test_br_g_<number>_*` pytest at
each named level; fault injection may replace a dependency, never the unit under
test. A skipped, xfailed, uncollected, or comment-only counterexample leaves the
gate open.

Only a gate-required installed-WebView2 check, source/import scan, or recorded
measurement may supplement pytest. Those artifacts link from the implementation
change. BR-G-42 owns its exact reference profile and budgets below. Gate
headings are organizational, not lane ownership.

**Lane A — tree substrate**

- **BR-G-1 — Node ids are scope-qualified and stable.** Two locations each
  containing `docs\a.txt` produce different node ids; rebuilding either tree
  twice produces byte-identical ids. At integration, a foreign-location id is
  refused by `NamiSyncService`, not filtered. *Not satisfied by* asserting ids
  are unique within one tree, which a path-only id also satisfies; and *not
  satisfied by* testing the service refusal with a syntactically invalid id,
  which never proves ownership is checked. Checkpoint 9 additionally proves a
  same-path domain row, exploded operation members, distinct warnings, and
  repeated otherwise-identical warnings receive stable collision-free ids
  under the exact `NamiSyncNodeV1`, `NamiSyncMemberV1`, and typed
  `NamiSyncInfoV1` codecs plus duplicate ordinal.
- **BR-G-2 — The emitted array carries the structure interfaces need.** Assert
  every node exposes pre-order position, depth, parent index, subtree extent,
  and stable id→position lookup. Stage 6's BR-G-34 then asserts a
  collapse/filter/search pass over it references no path string except for
  display matching. *Not satisfied by* deriving a missing parent or subtree
  boundary inside the presentation layer; the point is that the array makes
  path arithmetic there unnecessary.
- **BR-G-3 — The promotion changed nothing.** The planner's pre-existing test
  file passes unmodified, and a diff of the three helpers shows relocation
  only. *Not satisfied by* new tests written against the promoted helpers,
  which cannot detect a behavior change the planner depended on.

**Lane B — scan scope** (the data-corruption lane)

- **BR-G-4 — Nested roots record their own keys.** A subtree scan rooted at
  `Photos\2024` records `PHOTOS\2024\IMG.JPG`, not `IMG.JPG`. Assert the exact
  stored `rel_path_key` values, not the row count. *Not satisfied by* asserting
  the right number of rows was observed — the prefix bug preserves counts and
  corrupts keys.
- **BR-G-5 — Missing inference is bounded by the completed roots.** In a
  location holding `A\`, `B\`, and `C\`, a completed refresh of `A` alone marks
  the disappeared row under `A` missing and leaves every row under `B` and `C`
  untouched, including rows already `missing`. *Not satisfied by* a
  single-folder fixture, where a whole-location sweep is indistinguishable from
  a bounded one.
- **BR-G-6 — Hostile roots stay literal.** Roots named `100%`, `a_b`, and one
  containing `]` reconcile exactly their own subtrees. *Not satisfied by*
  asserting the query returns rows; assert that a sibling the wildcard would
  have matched is untouched.
- **BR-G-7 — Completeness is inherited, not restated.** A subtree containing
  `THUMBS.DB`, `DESKTOP.INI`, or an owned temp reconciles normally; a file
  placeholder or file reparse remains complete; each of the directory
  placeholder, directory reparse, and repeated-directory-identity conditions
  withholds all missing inference. A junction crossing from one requested root
  into another trips the shared identity guard. A structural test asserts the
  recursive path routes through the shared full-walk helper so a newly added
  incompleteness cause propagates without a doc edit. *Not satisfied by*
  enumerating today's causes only in a subtree-specific implementation or test,
  which reproduces the closed-list bug one layer down.
- **BR-G-8 — Absence and unavailability are distinguished at the root.** A
  deleted root is conclusive and marks its former subtree missing; a
  permission-denied root is `ROOT_UNAVAILABLE`, incomplete, and marks nothing;
  the warning names the failing root. A root that is now a file is recorded as
  a file. *Not satisfied by* testing only the deleted-root case, which passes
  even when both are caught together and treated as absent.
- **BR-G-9 — The receipt covers the scope.** Two `InventoryCommand`s sharing
  `location_id` and `scope_token` but carrying different `subtree_roots` are not
  deduped against each other — concretely, the second raises `TokenConflictError`
  rather than returning a silent `NOOP`. **This gate is checkable only at the
  recorder**, not through `NamiSyncService`: the facade mints
  `request_id = uuid4().hex` per dispatch and `run_inventory` sets
  `scope_token = request.request_id`, so two facade-level refreshes can never
  collide on a receipt key regardless of whether the roots participate in the
  hash. *Not satisfied by* a facade-level test, which passes with the
  payload-hash work not done at all; and *not satisfied by* asserting a replay
  of the identical command is a `NOOP`, which is the naive assertion this gate
  exists to rule out.
- **BR-G-25 — Scope normalization preserves the union's meaning.** A mixed
  request containing exact rows and recursive folders canonicalizes overlapping
  subtree roots by segment ancestry, preserves an exact file outside those
  roots, and does **not** recursively expand an exact directory row. Selecting
  the location root produces `FULL`, not a degenerate `SUBTREES`; duplicate ids
  do not duplicate subjects. Canonicalization work over many sibling roots and
  exact paths remains proportional to the declared path depth rather than
  comparing every path with every root. *Not satisfied by* testing each scope
  form in isolation, where a lossy "convert everything to roots"
  implementation passes; and *not satisfied by* five-item fixtures that hide a
  quadratic admission-time walk.
- **BR-G-26 — Every reconciled presence state takes the intended branch.** A
  completed subtree refresh marks disappeared `present` and `unsupported` rows
  inside its exact-path/root union missing, preserves already-`missing` rows,
  and leaves all rows outside the union byte-for-byte unchanged. An incomplete
  refresh marks none of them missing. If one root in a multi-root request is
  incomplete, missing inference is withheld for the whole combined receipt,
  including a different root that looked conclusively empty. *Not satisfied
  by* counting missing rows without asserting the before/after state of every
  in-scope and out-of-scope fixture row.
- **BR-G-27 — Reconciliation seeks literal ranges through the declared index.**
  The representative subtree predicate is
  `rel_path_key >= root || '\' AND rel_path_key < root || ']'`; an
  `EXPLAIN QUERY PLAN` assertion proves SQLite searches through
  `inventory_location_presence_idx` with the location, presence, and key range
  constrained. The hostile-root fixtures from BR-G-6 execute through this exact
  path. *Not satisfied by* a `LIKE` query with escaping, an index merely present
  in the schema, or a plan that reports a scan.
- **BR-G-28 — Inventory and integrity codecs version independently.** Inventory
  v2 round-trips and rejects v1; integrity v2 round-trips and rejects v1; a wrong-kind
  body is rejected at either version; and the shared validator's version guard
  is proven kind-aware and exact-type (`2.0`, `"2"`, and `true` do not denote
  either v2 contract).
  *Not satisfied by* separate test-only decoders or by testing only the two
  accepted payloads, which misses cross-kind and coercible-version acceptance.

**Lane C — selection semantics**

- **BR-G-10 — Provenance survives the payload.** Current payload v5 round-trips
  `user_deselected` and validated `bytes_done_high_water` through a real pause
  and resume; direct choices settle `SKIPPED` and dependency fallout settles
  `DEFERRED` **after** the round trip, not only before it; versions 1-4 are
  rejected. *Not satisfied by* asserting a field
  encodes and decodes, which a payload that is never consulted also satisfies.
  Additionally: a continuation whose `selection` differs by one operation from
  `derive_execution_selection(plan, user_deselected=…)` is refused before
  execution preflight with no filesystem mutation — and that refusal is injected
  on **an execute resume and a verify resume**, not only on a fresh submission,
  so the resumed run still finishes `FAILED+RAN` rather than a fresh
  `REFUSED+UNRUN` (XV-7's contract). *Not satisfied by* the commitment digest
  check, which compares the carried selection against a digest computed from
  that same carried selection and is therefore circular.
  The pause/resume proof drives the real dispatcher snapshot/reopen path. A
  real-ledger tampered verify continuation must also settle the already-open
  run terminally; it may not re-begin recording from the tampered selection and
  strand the run on a start-token conflict.
- **BR-G-11 — `all-noop` reads kinds, not outcomes.** Run as a **classifier-level
  unit test** over a constructed `OperationResult`/selection pair, not as an
  end-to-end session: the live path may make a divergence unreachable, and a
  gate that cannot express its own counterexample proves nothing. Assert that a
  result whose items are one `NOOP` settling `SKIPPED` plus one user-deselected
  `COPY` settling `SKIPPED` classifies `all-noop`, while one whose items are a
  single user-deselected `COPY` settling `SKIPPED` does **not** — the outcome-based
  predicate cannot tell those apart and the kind-based one must. Separately, a
  selection emptied by user deselection is refused before admission. *Not
  satisfied by* any case in which the current outcome-based predicate returns the
  same answer as the corrected one — the gate must contain at least one input on
  which the two disagree. The corrected predicate's other consumer is
  DR-BR-16.2's retained-history aggregate, which must reach the same verdict from
  persisted `kind`/`reason` columns. In addition to the classifier
  counterexample, a service-level test admits a nonempty all-`NOOP` plan,
  executes it, records its items, and returns `all-noop`; an all-skipped plan is
  refused before admission. *Not satisfied by* treating both as empty work or
  by proving only the pure classifier.
- **BR-G-12 — Safety exclusions are unreachable, and reselection closes upward.**
  On a graph containing both dependency directions, directly deselecting an
  operation adds only that id to `user_deselected`, cascades the effective
  exclusion through every dependent, and labels the fallout
  `BLOCKED_DEPENDENCY`; reselecting a child of a safety-blocked parent leaves
  the child excluded. A mutation naming a safety-excluded or unknown id is
  refused rather than absorbed. Separately — DR-BR-02's half — reselecting a
  deselected file *under a user-deselected folder* also clears that folder's
  `MKDIR` from the user set, so the child is selected in the very next
  derivation rather than immediately re-excluded as `blocked-dependency`.
  *Not satisfied by* storing dependency fallout in `user_deselected`, asserting
  the final selection only after a deselect-only sequence, or exercising the
  blocked-parent case without the upward closure.
- **BR-G-13 — Direct artifact replacement discards.** At the lower-level
  facade/runtime boundary, replacement by an unchanged tree — reproducing
  identical operation ids — after at least one operation has first been
  user-deselected resets the selection, **advances** the revision, and produces
  the default `selection_digest`. A replay of the recognized old gesture is a
  `NOOP`; a new mutation, Execute, or confirmation carrying the old revision
  conflicts. A mutation racing replacement may not return an old-artifact
  `applied` response. *Not satisfied by* replanning an untouched default
  selection, whose digest is allowed to be identical; and *not satisfied by*
  asserting the UI shows a message. This is defense-in-depth for direct service
  callers, not an H2 bridge command; desktop replanning instead creates a new
  immutable-plan task whose default selection is independently covered.
- **BR-G-24 — A folder gesture covers the subtree, not the viewport.** A folder
  deselect over a subtree whose descendants are split by a collapsed ancestor
  removes every operation at or under that path, and the folder's rollup counts
  are identical whether or not descendants are collapsed. *Not satisfied by* a
  fully-expanded fixture, where subtree scope and rendered scope are
  indistinguishable. A safety-disabled descendant is skipped during folder
  expansion rather than refusing the selectable siblings; naming that disabled
  operation directly still refuses. The filter half of this invariant cannot
  be gated until filters exist and is carried by slice 4's gate; this is the
  inventory-side clause's missing twin on the selection side.

**Lane D — facade**

- **BR-G-14 — The revision protocol cannot diverge.** A mutation at a stale
  revision applies nothing and returns conflict with the current revision; a
  no-op batch still advances the revision; a deselect-then-reselect cycle
  advances it while reproducing the prior digest. Submission failure and a
  terminal unrun result each advance it once while preserving membership, so a
  delayed pre-commit gesture conflicts after reopening. *Not satisfied by*
  comparing digests, which cannot observe an applied no-op or a reopened
  authorization epoch.
- **BR-G-15 — Unconsumed execution authority is recoverable.** Fault-inject
  `Dispatcher.submit` to fail; assert the selection returns to `reviewing` at a
  new revision, Execute is available, and no session exists. Then attach an
  execution that terminates with `disposition="unrun"`, including the
  `filesystem="refused"` execution-start-failure witness: publish its complete
  result/notices,
  return to `reviewing` at one new revision, edit the selection, and prove a
  fresh start command mints a new commitment while replay of the old command
  returns only the original attempt. A first ran result—including all-NOOP—must
  freeze permanently. Also assert a concurrent Execute during `committing`
  yields exactly one session. *Not satisfied by* the happy path, treating zero
  bytes as unrun, or reopening without invalidating stale selection intent.
- **BR-G-16 — Mutating commands are retry-safe.** A replayed gesture applies
  exactly once. Assert the actual disposition sequence rather than an equality:
  the first call reports `APPLIED` and the replay reports `NOOP`, because
  `_command_receipt` maps a prior `APPLIED` to `NOOP`; both are success and only
  the first reflows the list (DR-BR-20). A replayed multi-row gesture applies
  each row exactly once without raising. A replayed session-creating command
  yields **one** session, not two, including two concurrent first deliveries of
  the same command id. An id-based retry checks its canonical raw gesture
  receipt before rereading mutable inventory, so a disappeared row or changed
  subtree cannot defeat replay. The folder-integrity freeze is taken inside the
  same single-flight validation that resolves the ids. The service-held receipt
  survives while that session is retained, is removed by `close_session`, and
  is cleared at shutdown without a late admission repopulating it. *Not
  satisfied by* asserting
  acknowledge works, which a non-idempotent implementation also passes on first
  call; and *not satisfied by* asserting the two calls return the same value,
  which is false by construction.
  **The projection-revision clause is deliberately not here** — the cached
  projection is Stage 6 slice 6, and a Stage 5.5 gate over an object Stage 5.5
  does not build is satisfiable by a counter nothing advances. It is BR-G-23.
- **BR-G-17 — CLI compatibility remains explicit.** The original lane merge
  kept `tests/test_cli.py` byte-identical, proving that facade integration did
  not silently rewrite existing expectations. The integrated adversarial pass
  then adds one permanent real-CLI regression for the newly exposed
  `confirmation-required` admission: a typed `execute` on an effective
  irreversible update renders the risk, supplies an exact boolean
  acknowledgement, completes without an admission-view crash, and updates the
  target. Existing M0 sync/history and Stage 5 location-command tests remain
  behaviorally unchanged. An omitted revision is accepted only for an
  untouched default selection. *Not satisfied by* adapting broad expected
  output to hide a signature break; and *not satisfied by* running only the M0
  subset, which never touches location commands or the destructive-risk path.
- **BR-G-20 — Destructive risk is computed from the effective selection.** A plan
  containing one `UPDATE` with `trash_on_update` disabled reports
  `requires_destructive_confirmation` true and `irreversible_update_count` 1;
  deselecting exactly that operation flips the flag false and the count to 0
  with the plan unchanged; a `MOVE_UPDATE` never contributes to either. *Not
  satisfied by* an all-selected fixture, where a flag computed over the plan's
  operations and one computed over the effective selection are
  indistinguishable — which is the specific wrong answer DR-BR-03 names.
  Admission accepts an exact boolean acknowledgement only; a truthy string such
  as `"false"` is rejected rather than bypassing the confirmation.
- **BR-G-21 — The commitment's terminal states are observable.** A mutation
  against a `committing` or `committed` selection returns a response distinct
  from a revision conflict, and the client can tell the two apart without string
  parsing. A concurrent Execute observing `committing` receives a named
  in-flight response rather than an error or a silent drop. `committing` always
  resolves: assert that an exception escaping the submit leaves the state
  `reviewing`, not occupied. *Not satisfied by* asserting only that exactly one
  session exists, which says nothing about what the second caller was told.
- **BR-G-18 — Incompleteness reaches the facade.** An incomplete refresh
  delivers typed warnings with code, path, and detail through
  `InventoryDetailsView`. *Not satisfied by* asserting `complete is False`,
  which is precisely the reduction this work exists to undo.
- **BR-G-29 — Every promised location command crosses the real facade.**
  `acknowledge_inventory`, `restore_inventory`,
  `list_unacknowledged_missing`, and `list_stale_inventory` are each driven
  through `NamiSyncService` and return primitives-only views. Refresh,
  baseline, verify, and rebaseline each accept owned row ids and folder ids,
  union and deduplicate mixed ids, refuse empty and foreign-location
  collections, freeze integrity folders to exact subjects before admission,
  and continue a folder operation past one unreadable frozen subject while
  emitting that subject once as `unsupported` and keeping the run explicitly
  verification-incomplete. Cancellation or non-subject-specific incompleteness
  still refuses before hashing. *Not satisfied by* testing
  `LocalWorkflowRuntime` directly,
  by covering only one of the four lifts or four location commands, or by
  resolving ids in a test helper before calling the service.

**Stage 6 — deferred here because their object does not exist until then**

- **BR-G-22 — The projection patch is a single critical section.** Two concurrent
  acknowledges against one `view_id` both survive in the resulting projection; a
  patch racing a full rebuild never resurrects pre-rebuild structure; a patch
  whose base revision no longer matches is dropped rather than applied over newer
  structure. *Not satisfied by* asserting the swap is atomic, which is true of a
  read-modify-write that has already lost the other writer's patch.
- **BR-G-23 — The revision guard refuses a superseded view.** A command formed
  against a projection revision the server has since advanced is refused as
  stale and the client re-reads; the refusal is distinguishable from a receipt
  replay. *Not satisfied by* a monotonic counter nothing advances, which passes
  every assertion in a test that never invalidates.
- **BR-G-30 — The host assumptions are measured before they become
  architecture.** On supported Python 3.13 and the pinned pywebview range, the
  spike records real `CoreWebView2` reachability, pythonnet event-handler syntax,
  the asset-server origin actually observed at runtime, and off-thread
  `current_url` behavior. It proves that native access/attachment occurs on the
  synchronous WinForms `before_load` callback rather than a setup or bridge
  worker, and that dispatch authority follows cached native committed
  `CoreWebView2.Source` across a canceled off-origin navigation rather than the
  poisoned managed `Source`/`get_current_url()` value. It also records the
  pinned host's internal result-return transport and proves a canceled
  navigation can trigger reinjection/callback loss. Its rerun also invokes
  `window.open('https://example.invalid/')` from the packaged page through
  pywebview's real first popup handler and NamiSync's later guards, proving no
  system browser launch, no document replacement, and a working subsequent
  bridge call. *Not satisfied by*
  documentation lookup, a mock `Window`, a different Python/runtime
  combination, a native property read from a worker, an origin test that never
  attempts and cancels navigation, or a source scan confined to NamiSync code.
- **BR-G-31 — The packaged host keeps its security and process boundaries.**
  A built installation prepares pywebview before `create_window`, using only
  read-only registry access through the upstream-parity compatibility detector
  to reject missing WebView2 before pywebview can import MSHTML, and pins
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False`,
  `ALLOW_FILE_URLS=False`, `ALLOW_DOWNLOADS=False`,
  `REMOTE_DEBUGGING_PORT=None`, and `debug=False` before native startup; opens
  only on Edge Chromium; and attaches top-level navigation, all-frame,
  new-window, and source guards on the UI thread before app data is accepted.
  It makes swallowed attachment failure observable and tears the window down
  actionably; rejects a missing or incompatible WebView2 with an actionable
  message; rejects an off-origin committed native source independently of
  navigation hardening; routes both console/package-module entry points through
  `interfaces/launcher.py` without importing the web adapter; and exposes
  `nami-sync-gui` through that same launcher as a GUI-subsystem entry point.
  No-subcommand console use prints usage and points to the GUI launcher.
  Explicit CLI subcommands do not import or initialize pywebview. A second
  desktop launch activates the existing window
  and exits successfully; activation failure is visible and still non-error.
  The real packaged-page popup composition leaves the page and bridge usable
  without opening a system browser. *Not satisfied by* running from a source
  checkout, guarding only navigation, testing popup handlers separately, or
  importing `web` lazily from `cli`.
- **BR-G-32 — The transport is one allowlisted, inert-data channel.** Slice 2
  proves every public view type round-trips through the production JSON codec
  and the one exposed `dispatch(command_json)`; the two Slice 2 rows are exactly
  `pick_folder` and `start_plan`, and the thaw/refreeze allowlist adds the
  foundation-only readiness rows `shell_ready` and `readiness_echo`, Slice 3's
  `next_events`, plus
  lifecycle-only `release_terminal_session` and `close_task`, and the
  pre-Slice-5 cosmetic rows `read_cosmetic_section` and
  `replace_cosmetic_section`, while
  `test_report` is possible only through test-owned
  constructor composition. Host composition, rather than transport, joins the
  final command mapping to current-document readiness through an exact opaque
  admission verdict; the bridge retains only document trust, request bounds,
  handler reservation, and serialization. Unknown versions, commands,
  fields, malformed opaque ids, and input above 65,536 UTF-8 bytes are refused
  before handler invocation. Errors expose no filesystem path or internals even
  though pywebview otherwise returns Python tracebacks. The native picker keeps
  its path in the bounded server slot table, returns only `{id, display}`,
  accepts only purpose-matching live ids through dispatch, and refuses a
  fabricated id without making display text authoritative. The scanner's
  complete hostile-name corpus crosses page JavaScript, the real pinned
  pywebview return transport, and the production inert-text path in the headed
  harness byte-for-byte, while the broadened DR-BR-25 packaged-asset sink scan
  is empty. Slice 4 adds the final filesystem-label layout projection and exact
  installed DOM/accessibility marker corpus without changing raw transport or
  opaque callback ids. Those clauses close Slice 2's transport, picker,
  origin-refusal, and static-sink portion plus Slice 4's generic tree sink.
  Slice 5 must repeat the corpora in the production plan DOM
  and Slice 6 in the production inventory DOM; BR-G-32 is not wholly closed
  until the latter lands. *Not satisfied by* a direct Python call that bypasses
  dispatch, a benign-name subset, a test-only reimplementation of the sink,
  returning a real picker path, an `innerHTML`-only source scan, or treating the
  Slice 2 harness as proof of a later production surface.
- **BR-G-33 — Event delivery remains ordered, bounded, recoverable, and
  stoppable.** Admission-time observation is adopted before `PENDING` emission;
  `PENDING` reaches that stream while work remains unschedulable, and only then
  are maps/pending publication and scheduler notification atomic. An
  attach/shutdown race rolls back the unpublished session and starts no work. Concurrent drains
  cannot reorder or split one task's sequence;
  progress coalesces behind one fixed 150 ms progress-only deadline without
  displacing or delaying reliable data; a reliable flood reaches
  the existing visible `Gap`/resubscribe path and terminal truth is recovered;
  shutdown refuses new handlers, waits for admitted handlers, and wakes drains
  and capacity-blocked producers before closing observations. A failed drain
  without a `Gap` resubscribes after the last client-accepted non-`Gap`
  sequence. Repeated progress cannot extend the deadline; reliable and terminal
  values wake it immediately. An ordinary explicit `Gap` remains visible, stops later updates,
  and resubscribes from its exact `first_missed_seq`; a recovery response's
  matching leading `Gap` proves the prefix unavailable and permits its retained
  tail without another loop
  and recovers terminal truth without a client acknowledgment, echoed cursor,
  or new server receipt. Numeric sequence holes are legal progress coalescing
  and do not themselves recover. Fault-inject a lost response containing reliable data
  and a separate lost response containing the terminal delivery; both reconcile
  through the production resubscribe/terminal-record path, while replaceable
  progress may coalesce to the latest truthful snapshot. Concurrent
  observe attempts create one subscription or a named refusal, and a
  fault-injected slow facade call proves no `TaskState` lock is held across it.
  Repeated `pywebviewready` firings while a drain is outstanding install one
  listener set, retain at most one drain per task, pause it while the new
  document is presentation-pending, and re-arm delivery exactly once after
  that bridge generation becomes operational. The transport fault gate's
  synthetic return-table loss stays explicitly renderer-only: it resets the
  JavaScript bridge while the already-open native document generation remains
  unchanged, and does not stand in for the separate production startup and
  native reinjection evidence.
  *Not satisfied by* a single drain, a naturally finishing session, one task,
  or a queue that stays below capacity.
- **BR-G-34 — One visible-sequence implementation defines both trees.** The
  same pure flattener produces plan and inventory windows from the ordered array
  under expanded/collapsed, filter, and casefolded-display-substring search
  combinations. Changing parameters replaces one active sequence rather than
  retaining a parameter-keyed family. A container appears only for a directly
  matching node or matching descendant, and collapse hides descendants only
  after matching. Search treats regex metacharacters literally, matches the
  casefolded display form only, accepts 65,536 UTF-8 bytes, and refuses 65,537
  before traversal. The bridge's separate 65,536-byte complete-envelope bound
  and every future external adapter's ingress bound remain authoritative.
  Sparse caller-owned match counts are validated but their domain
  vocabulary is not interpreted here. The default is expanded, fixed row
  height is enforced, 256 rows are accepted, and 257 are refused rather than
  truncated. The workflow-owned canonical product array is consumed directly
  without a second complete DTO copy. Inventory uses the real path-node array
  plus its informational merge; plan uses that same path array plus the exact
  sparse multi-member expansion, retaining original path-node identity where
  no expansion is required and adding only `NamiSyncMemberV1` children/groups.
  Anchor lookup uses the same derived sequence and
  exact deepest-to-root id chain and performs work proportional to chain depth,
  not tree size. Plan and inventory cases must start from real
  `build_node_tree` output, retain path-node identity, and include a real
  same-key multi-operation expansion fixture; hand-built generic arrays alone
  do not close the gate. The positive renderer witness uses the same
  canonical temporary JSON bytes generated through `build_node_tree` ->
  `derive_visible_sequence` -> `window_visible_sequence` ->
  `to_visible_window_view` in both the direct Node probe and installed WebView2
  child. Python, child, and page SHA-256 values must agree. Its cases cover the
  `head`, `next`, `tail`, `empty`, `maximum`, and `layout_control` windows,
  expansion tri-state across the pointer and projected-empty windows, and
  ordinary-Unicode and long-label values in `next`;
  independently authored positive row dictionaries are insufficient evidence.
  The separate renderer-local control corpus tests the fixed sink set without
  pretending invalid Windows filename characters traversed `NodeTree`. The
  bounded window carries the complete exact `TreeRowFrame`, including
  server-derived global visible parent/child indexes and filtered sibling
  accessibility metadata. Boolean expansion exists only
  for a projected parent with a retained immediate child; leaves and filtered-
  empty containers carry `null`. A static assertion proves the
  implementation calls no path helper and reconstructs no parent or descendant
  relationship from display text. *Not
  satisfied by* filtering an already-windowed page, searching the canonical
  key, accepting an arbitrary callable as filter policy, or separate plan and
  inventory flatteners fed the same fixtures. The realignment regressions, full
  20,000-container/100,000-leaf retained-representation witness, and
  deterministic linear field-access guard now pass. These are structural
  evidence, not latency acceptance; broader BR-G-42 product-view measurements
  remain with Slices 5-7. Display strings remain byte-exact in the Python
  sequence/wire/search seam; visible `⟦U+XXXX⟧` layout markers are a final
  renderer projection and marker spelling has no query syntax. The production
  renderer regressions additionally
  cover coalesced leading/trailing spacer paging, exact row-boundary math,
  external-projection priority, keyboard-versus-newer-scroll ordering,
  covered-window cancellation, callback failure, stale-payload refusal before
  access, preserved scroll position, a one-row valid response that cannot
  self-retry for an unchanged viewport, changed-viewport convergence, and a
  fully visible presentation-only active descendant. The installed-wheel SH-G-7 witness sends a native CDP
  mouse-wheel gesture through a four-row viewport, accepts a five-row page
  spanning both viewport edges, and proves the viewport remains nonblank
  while the activation recorder remains empty. Those are functional regressions, not latency
  measurements. The shared manifest binds current Python projection output to
  the installed generic renderer; it neither exercises a Slice 5/6 plan or
  inventory bridge command nor closes their product-DOM or BR-G-42 latency
  gates.
- **BR-G-35 — Plan presentation preserves operation truth while compressing
  moves.** This is also the first consumer that proves a filtered move ghost
  removes its synthetic-only ancestor chain, an ordinary real operation keeps
  its folder visible on its own merits, folder rollups remain the original
  view-independent values, and each filter chip count describes its search-
  matching operation-bearing population before active filters/collapse rather
  than structural-only ancestors or the already-filtered view. The plan tree memo is byte-stable per request and is dropped with the
  plan; selection overlays do not rebuild its structure. Move annotation uses
  the union of target and prior-target ancestors, keeps the ordinary folder
  selection scope and original operation kinds, emits a noninteractive old-path
  ghost only when no real node exists there, annotates the real old node when it
  does, and suppresses nested ghosts. Destination and old-location rows carry
  symmetric `move_peer_id` values; tagged node anchors navigate off-window
  peers without browser path derivation. After nested suppression, only one
  non-self candidate edge that is the sole incident edge at both endpoints is
  emitted. Convergence, split, chain, swap/reverse, self, and every
  reused-endpoint case suppresses all touching inferred groups and leaves
  literal operations; identical ordered endpoint pairs have already coalesced
  and cannot form residual parallel edges. A same-canonical-target collision
  keeps one path/group authority and emits every immutable operation exactly
  once as a member child; group selection/rollup covers all members while
  counts, risk, dependencies, and overlays remain operation-exact. Synthetic
  node ids never enter execution,
  persistence, or a selection digest. The production plan DOM passes DR-BR-25.
  *Not satisfied by* a move-only happy path, a synthetic operation standing in
  for a folder, or a renderer that relabels inferred groups as renames.
- **BR-G-36 — Progress compatibility and follow mode use identity, never
  display paths.** Core serialization, Python bridge projection, and the
  browser require exact event v5 inside `SessionEventView`; no v3/v4 producer,
  tolerant decoder, JavaScript branch, public constant, or positive fixture
  remains after the atomic cutover. One malformed event rejects its complete
  batch without advancing the cursor, and a clean replay delivers the reliable
  siblings. All byte counters use checked signed-64 arithmetic internally and
  canonical decimal strings externally; Boolean, sign, leading zero, exponent,
  fraction, unsafe Python integer, and above-domain values are refused. Both
  reporters project reliable detail through exact variants capped at 32
  primitive leaves/eight paths; diagnostics over 1,024 UTF-8 bytes become null
  with checked omission witnesses rather than truncation. The complete
  reliable envelope is at most 1,048,576 canonical bytes before sequence/queue
  mutation, and its bridge projection always fits as one drain head. Both
  reporters emit the row-namespace pair (`operation` for executor and linked
  post-copy ids, `integrity` for standalone rows), phase self-description, and
  an opaque attempt id at byte-pipeline entry. Retry or reconstructed resume
  resets require a new attempt id. An
  off-window item sends its opaque identity through the exact tagged
  `get_plan_anchor` read; the server derives the chain and returns the deepest
  visible ancestor-or-self, exact visible index, and `ancestor_ids` under
  collapse, filter, and search. No Progress or window variant carries an
  undeclared chain. User scrolling disables follow until explicit resume.
  A static/counterexample test proves `current_path` is never used for identity
  or lookup. **Status: OPEN until checkpoints 3, 7, and 8 jointly close the
  protocol, plan-follow, and execution-review portions.** *Not satisfied by*
  testing only a currently materialized operation, retaining a legacy decoder,
  or joining an id to a matching display path.
- **BR-G-37 — Virtualization cannot own or narrow selection.** Rows destroyed
  and recreated by scrolling recover the server's current selection; a folder
  gesture covers filtered, collapsed, and off-window descendants; tri-state
  values and rollups come from the server; and `preview_selection` calls
  `derive_execution_selection` directly rather than `get_plan_review`. A burst
  of toggles enters visible pending state, batches within the configured
  120–150 ms interval as one mutation and one revision advance, and resolves
  conflict by re-read rather than optimistic local repair. Execute is
  unconfirmed unless the effective selection carries the irreversible risk from
  BR-G-20. *Not satisfied by* a fully materialized, unfiltered tree or one click
  per debounce interval.
- **BR-G-38 — The inventory projection pays whole-location work once per
  lifecycle.** A slim explicit-column query builds one immutable projection per
  `view_id` without constructing full `InventorySnapshot`s; detail queries
  fetch only the visible node ids. Every returned row carries the complete exact
  `TreeRowFrame`; its global indexes and filtered sibling facts remain valid at
  window boundaries without browser reconstruction. Rebuild occurs outside the service lock and
  swaps inside it. Concurrent patches and patch-vs-rebuild races satisfy
  BR-G-22; unchanged node objects and position indexes retain identity after a
  one-row patch; session terminal causes a rebuild. Two views of one location
  remain independent, six projections are retained LRU, and the seventh evicts
  the least-recently-used unpinned one. With all six pinned it instead returns
  `retention_full`; location change, task close, and service shutdown release
  their views only after their last pins. Eviction and invalidation take the same stale-revision
  client path. *Not satisfied by* rebuilding on every page, deep-copying every
  node, guarding only the immutable value rather than the cache map, or testing
  fewer than seven views or omitting the all-six-pinned case.
- **BR-G-39 — Inventory interaction exposes all observed truth and exact
  scope.** The five location-resolution states render distinctly; incomplete
  refresh shows each typed warning's code, inert path, and bounded detail.
  Warning ids use the domain-separated tree kind, location scope, nullable path
  with typed-null root marker, code, bounded-detail, and duplicate-ordinal
  input, cannot collide with domain rows or one another, and
  are informational. Every detail/refresh/visibility/integrity action naming
  one returns fixed `row_not_actionable` before outside work. Current ledger
  `verification_state` and the latest ordinary-integrity `integrity_outcome`
  overlay remain independently projectable and neither overwrites the other. Row
  actions remain exact while folder refresh is recursive and folder integrity
  freezes all indexed descendants regardless of filter. Each integrity action
  reports the count actually selected after mode eligibility. One unreadable
  frozen descendant produces one visible `unsupported` item and an incomplete
  verification axis while every other eligible subject proceeds.
  Acknowledge hides the row by default, changes no ancestor rollup, refetches
  the shifted window only on `APPLIED`, and updates missing/acknowledged chip
  counts; restore is reachable through the acknowledged filter. No view-open or
  timer path auto-scans. Detail reads expose the full current digest only with
  provenance, scope/currentness, invalidation, signed-64 decimal size and
  nanosecond fields, and whole-second local-time rendering. Automatic linked
  verification remains in the execution session. Manual exact post-copy
  verification is a new dispatcher/history session, freshly admits the target,
  performs no refresh or new ledger scope, and conditionally records against
  the original execution run token; superseded or mixed exact/current evidence
  refuses with an ordinary current-state verification alternative. The
  production inventory DOM passes DR-BR-25. **Status: OPEN until checkpoints 9
  and 10 close projection/current-evidence and integrity/handoff behavior.**
  *Not satisfied by* a generic warning chip, displaying an unlabeled stale
  digest, refreshing before exact handoff, or a default view that still
  contains acknowledged rows.
- **BR-G-40 — History work is paged before object decoding and preserves
  classification.** The summary query count is fixed and its indexed primitive
  aggregate produces one fixed-size fact object per run without selecting or
  decoding canonical event JSON; free-form kind/reason values cannot expand
  summary retention, and workflow code, not `db`, interprets those facts. Item
  and reliable-event detail use immutable keyset
  order and one captured committed watermark, terminal phases have an explicit
  256-row ceiling, adjacent headline precedence remains XV-10 exact, and
  retained `all-noop` matches the live kind/reason classifier including
  `USER_DESELECTED`. `EXPLAIN QUERY PLAN`, query-count, and decode-spy
  assertions pin the bounded path. Limits 1 and 256 succeed; 0 and 257 are
  refused rather than truncated.
  *Not satisfied by* a compatibility getter that materializes a whole run, or
  by matching only the final headline of an uncomplicated run.
- **BR-G-41 — Task and process lifecycle lose neither work nor authority.** A
  process-live task exists without live work and serially owns zero or one
  current session. Plan, execution, inventory/integrity, and manual-verification
  sessions may attach beneath it. Under the exact [task-authority
  order](#task-and-authority-ordering), concurrent same-revision starts,
  start/close, and release/successor races prove that identical delivery joins,
  another command returns busy/current authority, only the token owner publishes
  or compensates, and observation precedes scheduling. Task, session, lifecycle,
  selection, result, view, and projection authorities remain independent; an
  older drain/release cannot affect a successor.

  Terminal record/replay authority survives until successful presentation;
  exact-session release then removes it while compact task artifacts survive
  until explicit task close. Closing live work asks once, enters visible
  `closing`, cancels, waits for a terminal **record**, then unsubscribes, closes,
  and releases every task-owned artifact; refusal or delay leaves the task open
  and truthful. Plan-only and already-terminal tasks release immediately.
  The task-authority register's exact receipt, release-tombstone,
  close-tombstone, and expiry bounds make repeated create/release/close cycles
  bounded. Shutdown
  wakes drains, prevents new attachment, and joins observers without holding a
  task lock across facade, JSON, database, or filesystem work. The rail renders
  `pausing` distinctly until `paused` or terminal. Browser navigation or
  reinjection reconstructs through `list_tasks`/`get_task`; no task/session,
  plan, selection, named result/overlay, view, or recent-location authority enters
  `ui-state.json`. **Status: OPEN until checkpoints 4 and 11 close ownership,
  cleanup, and concurrent shutdown.** *Not satisfied by* cleanup triggered by
  the terminal event, a task rail reconstructed from dispatcher sessions, or a
  clean idle shutdown alone.
- **BR-G-42 — The named scale envelope passes fixed budgets.** The
  implementation records every row below against the predeclared fixtures and
  profile. Ordinary pytest proves deterministic shape/query/decode/allocation
  bounds; the owning benchmark records raw samples, source, machine/runtime,
  fixture seed, statistic, run count, p95, and maximum. Sizes and ceilings may
  not be selected after observation.

  **Reference profile and sampling.** Windows 11 Pro build 26200; Intel
  i7-13700K (16 cores/24 logical processors); 63.7 GiB RAM; repository,
  fixtures, and SQLite on a WD_BLACK SN850X 4 TB NVMe; CPython 3.13.14 and
  SQLite 3.50.4; AC power with no unrelated sustained workload. P95 rows use at
  least 30 warm samples; cold maxima use at least five fresh-process or
  cold-projection samples.

  | Fixture | Required shape |
  | --- | --- |
  | Plan | Base: 100,000 operation-bearing rows plus up to 20,000 combined structural-folder/operation-group/move-ghost rows, including every prior-path synthetic ancestor; every immutable operation is represented exactly once and grouped collision members fit inside that combined allowance; information-heavy: add 120,000 plan notices while their complete retained charge stays at or below 192 MiB; dependency/path depth reaches 32 |
  | Inventory | Base: 100,000 subject rows plus up to 20,000 directory rows in one location; information-heavy: add 120,000 warning rows while their complete retained charge stays at or below 192 MiB |
  | History | 50 run summaries covering 1,000,000 retained items, including one 100,000-item run |
  | Projection retention | Six populated 240,000-row information-heavy inventory projections, then a seventh view to force LRU eviction |
  | Events | Four active tasks for 60 seconds at 100 aggregate `Progress` events/s plus 10 aggregate reliable events/s |

  The informational count fixture is deterministic: seed `0x4E414D49`, stable
  typed-code cycling, ASCII indexed relative paths, null detail on the initial
  population, and fixed repeated occurrences to exercise duplicate ordinals.
  Its byte-bound companion keeps the same 120,000-row order and deterministically
  substitutes complete in-bound paths/details from the start until the next
  substitution would exceed the frozen retained-sizer cap; production and the
  independent validator use the checkpoint-4-frozen per-object/string/index
  charges. The maximum-task reservation charges the production 120,000-row
  domain walls, full 128-MiB plan-domain/192-MiB inventory-domain walls, and
  the full row and 192-MiB informational allowances. This count-and-byte profile—not every Cartesian
  combination of maximum path and detail—is the guaranteed fixture; production
  rejects any real informational population whose next complete row exceeds
  either limit before publication.

  The current-source event and custody fixtures use the version-4 Progress
  protocol rather than treating the cadence coordinate as completed items.
  Each task admits 150 reliable items; `items_done` is the number of reliable
  terminal item outcomes emitted before that snapshot, while the independent
  `bytes_done` coordinate advances from 1 through 1,500 and owns coalesced
  cadence/monotonicity sampling. Progress snapshots populate the version-4
  operation identity, opaque attempt identity, and attempt-local byte pair;
  each modeled attempt keeps one token through its chunks and is followed by
  its matching reliable outcome. In the ordinary fixture, terminal results
  retain the same 1,500-byte attempted-work high-water; maximum-no-`Gap`
  remains an outcome-only fixture. This preserves the named 6,000-Progress /
  600-outcome envelope without manufacturing item settlement or publication.
  A source-hashed current-version overlay classifies every retained
  `Envelope`, `SessionEventView`, exact Progress-body field, and reachable body
  mapping without altering the frozen v1 corpus specification.

  | Measurement | Ceiling and authority |
  | --- | --- |
  | Local critical-click feedback | 50 ms maximum; Tier 0 target, Tier 2 Slice 5/6 acceptance |
  | Typed execute/control/one-row receipt, excluding admitted work | 100 ms p95, 250 ms maximum; Tier 0 target, Tier 2 owning-slice acceptance |
  | Freeze/normalize a 100,000-subject scope | 500 ms p95, 1 s maximum; Tier 0 target, Tier 2 owning-slice acceptance |
  | Reliable/terminal delivery under event fixture | 100 ms p95, 250 ms maximum, no `Gap`; current-source Tier 2 timing remains open |
  | Replaceable progress delivery | 1 s p95, 2 s maximum, monotonic after coalescing; current-source Tier 2 timing remains open |
  | Cold 120,000-row base / 240,000-row information-heavy plan projection | 2 s / 4 s maximum; Tier 2 Slice 5 acceptance |
  | Cold 120,000-row base / 240,000-row information-heavy inventory projection | 3 s / 6 s maximum; Tier 2 Slice 6 acceptance |
  | Unchanged-parameter 256-row window | 250 ms p95, 500 ms maximum; Tier 2 Slice 5/6 acceptance |
  | Changed search/filter/collapse plus 256-row window at 240,000 rows | 1.5 s p95, 3 s maximum; Tier 2 Slice 5/6 acceptance |
  | `preview_selection` at depth 32 | 500 ms p95, 1 s maximum; Tier 2 Slice 5 acceptance |
  | Fifty-run/1,000,000-item history summary | 3 s maximum; Tier 2 Slice 7 acceptance |
  | 256-row history detail window | 500 ms p95, 1 s maximum; Tier 2 Slice 7 acceptance |
  | Incremental plan projection memory | 320 MiB maximum (128 MiB base plus 192 MiB informational); Tier 2 Slice 5 acceptance |
  | Incremental inventory projection memory | 384 MiB each, 2,304 MiB for six; Tier 2 Slice 6 acceptance |
  | Identity-deduplicated transport custody | 1,966,080 bytes; frozen protected authority plus Tier 1 live guard |
  | Terminal artifacts plus completed-task retention | Mechanically derive and freeze the byte budget at checkpoint 4 to admit four maximum tasks under the retained-task cap; BR-G-45 implementation/measurement evidence remains open through checkpoints 4 and 11 |

  The 128/192-MiB domain and 192-MiB informational hard walls are frozen
  deterministic complete-graph sizer contracts with an independent validator;
  these Tier-2 process-memory measurements neither derive nor validate them.
  The 100,000-plus-20,000 rows above are performance fixtures, not production
  maxima; first-excess production admission is governed by the 120,000-row and
  matching complete-graph byte walls.

  **Transport-custody clause.** Custody is the identity-deduplicated live graph
  rooted at dispatcher replay deques, subscriber deques, and adapter task
  queues. It includes containers and nonterminal event values. A terminal value
  occupies its queue slot, but the subject-scaled result graph is cut and
  charged to BR-G-45. The instrument reports every root class and their
  deduplicated union; payload bytes and whole-process memory are invalid
  substitutes.

  The frozen `sh-g-8-transport-v1` corpus drives four tasks through the
  production dispatcher/service/task-registry path, covers the ordinary
  60-second rate and exact per-task 128/64/64 maximum no-`Gap` custody shape,
  and requires ordered cleanup plus exact terminal truth. The authoritative
  corpus, calibration, ceiling, holdout, validator, and live-guard files are
  `tests/bridge_transport_custody.py` and
  `tests/interfaces/web/sh_g_8_transport_*`; `TOOLS.md` explains their use.
  The frozen ceiling is 1,966,080 bytes. Calibration never validates its own
  limit, and later representations must select authority anew under
  `DEFENSE.md` §7.

  The v1 calibration, ceiling, and holdout remain immutable historical
  authority. A protocol/body representation change reruns the current-source
  one-child Tier-1 guard against that ceiling; it does not rewrite, extend, or
  promote the old empirical artifacts.

  **Version-4 measurement disposition (2026-08-22).** The clean installed-wheel
  event run at commit `7ea8e08666b9079dbb402711f1380c91ae90ef9e`
  produced `namisync-bridge-event-benchmark-v4-7ea8e08.json` with SHA-256
  `7bb456329fa950fa9c7447bb353590e7902d716233a99c035e58d9467168ab8f`.
  Across the named four-task, 60-logical-second fixture it emitted 6,000
  `Progress` and 600 reliable item events at aggregate rates of
  100.06479228657697 Progress/s and 10.006479228657698 reliable events/s over a
  59.96114979998674-second emission window. The browser delivered 1,497 sampled
  Progress values at 40 ms p95 / 48 ms maximum and 620 sampled
  reliable-plus-terminal values at 3.05 ms p95 / 15 ms maximum, with monotonic
  Progress, no `Gap`, and all four terminal records. The installed runtime was
  CPython 3.13.14, SQLite 3.50.4, Bottle 0.13.4, pywebview 6.2.1,
  pythonnet 3.1.0, and WebView2 151.0.4129.93; both machine and runtime matched
  the declared reference profile. The 40,828,928-byte incremental peak-private
  value remains a whole-runtime diagnostic. Although
  the artifact reports `passed=true` and `event_passed=true`, it also correctly
  reports `sh_g_8_acceptance=incomplete-without-custody`; it is current-version
  event regression and diagnostic evidence, not current-source Tier-2 timing
  acceptance or whole-runtime acceptance.

  The final current-source custody run at commit
  `7ea8e08666b9079dbb402711f1380c91ae90ef9e` produced
  `namisync-bridge-transport-custody-v4-7ea8e08.json` with SHA-256
  `a4ba30a99fb3ccc27a20a1fe436ccb8f19ce10e4d7be70572190629abc84ae9c`.
  Its three fresh children were exact: ordinary custody was 1,378,867 bytes /
  4,901 objects and exact maximum-no-`Gap` custody was 1,536,994 bytes / 5,499
  objects. Those are respectively 2,177 and 2,048 bytes above frozen
  calibration-a, and 587,213 and 429,086 bytes below the unchanged 1,966,080
  ceiling. From 6,000 emitted `Progress` snapshots, ordinary custody delivered
  240 coalesced snapshots and all 600 outcomes, with
  replay/subscriber/adapter queue peaks of 128/0/4; the maximum fixture emitted
  516 outcomes at the exact 128/64/64 queue shape. Neither fixture produced a
  `Gap`. The separate protected one-child live guard also passed.

  The three-child artifact binds source
  `8a06469d79ce3e279892c779e312b2f0e0f16a8a911813d5396920ccc106c6cb`,
  dependency
  `8c0cab9dfa7aeed198ecbd0e66844cd834cf36ca8b32fd6647a53924a200de30`,
  evidence
  `f40fbc942cc4e15fe8eb7026b5d8e8b070932a8cac4d920214f6fc64c247046c`,
  instrument
  `629b50228b6f0604b0ff601e0af56d2c17676480a1a9716facc64b87434e10a9`,
  runtime
  `f94171a6eb2815dd97daec537fd0e226bad28137e66378bf272ec8cf6fa4cc28`,
  runtime qualifier
  `a520cababa83f3c878ca13e2a7f43053b68ed6ee40ccee04aed3834bab05e88e`,
  and corpus
  `a80d908babaff50872cb15bf4f9fa23eb2a054b982a25ac607223208a80787ec`.
  Its exact child artifact SHA-256 values are
  `115004ccb9cd76373b0aa5ca8e834ea51a55c0580e643f2682f522aadc7a2321`,
  `b83d65b8ef2e07037a1f14b077179c7608810bfbad63e5c165c24fc6bdf71d9c`,
  and `cca6f1e07383dcef82d721596e1fadf652b42271b9bfc523ac3d4efa7b7651b6`.
  This deterministic current-source result and the one-child check are Tier-1
  drift evidence only. They neither recalibrate the frozen v1 authority nor
  create a new v4 acceptance claim.

  **Deferred-handoff follow-up (2026-08-22).** The packaged reducer and Python
  executor changed at `4959574`; after the documentation checkpoint at
  `32b226e`, the clean source-authenticated measurements were rerun. The first
  installed-wheel event artifact,
  `namisync-bridge-event-benchmark-handoff.json` (SHA-256
  `938ee77d930df6551db0d12f80e8c5ca63c9c5f4359be79ba8d1cc1d5121185d`),
  retained monotonic Progress, no `Gap`, all four terminal records, and matched
  source/runtime profiles, but reported `event_passed=false`: one sampled
  reliable-plus-terminal delivery reached 476 ms, above the 250 ms maximum.
  Its 620 reliable samples were otherwise 4.05 ms p95; 1,478 sampled Progress
  values were 41 ms p95 / 670 ms maximum. The emission window was
  59.9608865000191 seconds at 100.06523169063 Progress/s and
  10.006523169063 reliable items/s; 44,441,600 incremental private bytes remain
  diagnostic. An immediate clean repeat from the
  same `32b226e7810c3727a960781108dc15c76d58b570` source produced
  `namisync-bridge-event-benchmark-handoff-repeat.json` (SHA-256
  `e0592621237daecab221a9167c1035a0c9d812ebef2b71a0efdb02fdd23d4eff`)
  with `event_passed=true`: 1,493 sampled Progress values at 41 ms p95 / 48 ms
  maximum and 620 reliable-plus-terminal values at 4 ms p95 / 18 ms maximum,
  across 59.9607480000122 seconds at 100.06546282576 Progress/s and
  10.006546282576 reliable items/s. Its 37,826,560 incremental private bytes
  remain diagnostic. It again had no `Gap`, monotonic Progress, and all
  terminals. The failed first diagnostic is retained in the disposition rather
  than replaced by the favorable repeat; neither run creates current-v4 Tier-2
  timing acceptance, and both retain
  `sh_g_8_acceptance=incomplete-without-custody`.

  The post-change one-child current-source custody guard also passed at exactly
  1,378,867 ordinary bytes / 4,901 objects and 1,536,994 maximum-no-`Gap` bytes
  / 5,499 objects. Its artifact SHA-256 is
  `c10e6da519e8889ee7bb8da114608c9485cafb838b142952c1805a6ca0b2846f`;
  source authority is
  `be24b04f61ee1b9b4f14d1d25465aa058fc3f62b98c122d8d3f1cc7023bc1cb7`
  and dependency authority remains
  `8c0cab9dfa7aeed198ecbd0e66844cd834cf36ca8b32fd6647a53924a200de30`.
  The live-guard artifact's `tested_commit` remains its deliberate all-zero
  fixture sentinel; the source authority, not that field, authenticates this
  rerun's production source set.
  The byte/object values are unchanged from the preceding three-child
  characterization and retain 587,213 and 429,086 bytes of margin to the
  historical ceiling. This is a Tier-1 drift rerun only; frozen v1 calibration,
  ceiling, holdout, validator, and retained-sizer authorities were not edited.

  **Status.** The historical v1 representation's event correctness and
  transport custody are closed by the frozen calibration/ceiling and
  independent holdout recorded in
  [Close transport custody and realign the bridge boundary](../CHANGELOG.md#close-transport-custody-and-realign-the-bridge-boundary-2026-08-13--2026-08-14).
  Current-source event timing and the Slice 5–7 product-view rows remain open on
  their owning slices. BR-G-45 terminal retention and shell-owned SH-G-15
  whole-runtime containment are separate gates. *Not satisfied by* changing
  fixtures after measurement, reporting averages in place of the declared
  statistic, using empty history runs or shared short strings, omitting a
  custody root/high-water mark, including terminal artifacts in custody, or
  treating payload/whole-process bytes as the retained transport graph.
- **BR-G-45 — Terminal artifacts and completed-task retention are bounded
  separately.** Checkpoint 4 freezes conservative analytical per-artifact
  constants before any surface/calibration. The exact [task-authority and
  retention register](#task-and-authority-ordering) owns the count/byte caps,
  maximum combined graph, replacement overlaps, handler/callback/window roots,
  projection cache, receipts, pins/leases, and release/close tombstones. Its
  production admission must always fit four canonical maximum combined tasks;
  smaller tasks may consume remaining count and bytes, while first excess
  growth returns `retention_full` without eviction or early truth release.

  Instrumentation walks every production root before presentation, with all
  handler-response reservations occupied, during terminal-callback/release
  retry, through generation pins and both close seals, and after release/close,
  neither omitting nor double-charging shared pools. Irreducible native/renderer
  copies are classified under `DEFENSE.md` §7. The four-task fixture, first
  refused excess phase, terminal reconciliation at handler saturation, repeated
  create/release/close cycles, and concurrent shutdown must match the declared
  release points and budget. **Status: OPEN until checkpoint 11 calibrates,
  verifies, and hardens the checkpoint-4-frozen model.**
  *Not satisfied by* a task-count cap, measuring a summary-only result, omitting
  browser/native transients, clearing truth before retry ends, or selecting a
  ceiling after observing the fixture.
- **BR-G-46 — Command-map revisions and cosmetic state remain exact, bounded,
  and non-authoritative.** The current exact nine-row native mapping and browser
  policy mirror agree on both cosmetic rows, their `OPEN` phase, five-second deadline,
  field requirements, read-only uncertainty replay, and replacement read-
  reconciliation policy.
  Focused tests prove the complete revision decision table, concurrent
  serialization, 250 ms coalescing, single-attempt failure behavior, guarded
  close flush, subscriber isolation/order, the 1 MiB read/write bounds, strict
  and duplicate-key decoding, forward-version preservation, and atomic
  replacement. Fault injection proves an accepted in-memory value survives a
  failed save without leaking path, payload, exception text, or traceback.

  Cosmetic reads and replacements leave semantic `settings.json`, service,
  registry, planner, plan fingerprints, tasks, and sessions untouched;
  pre-`OPEN`, off-origin, oversized, and malformed requests produce no state or
  file mutation. The product loads the initial override before window creation,
  then headed installed-WebView2 evidence proves the selector reconciles only
  accepted state and light/reduced versus dark/forced gallery modes agree across
  native material and page tokens. Raw Windows appearance remains distinct,
  high contrast temporarily wins, and accent/reduced-motion values stay
  system-owned. No bridge oracle or compositor sentinel is required: exact
  native policy/static tests, fault-directed material tests, and the installed
  transport/gallery witnesses jointly own the cosmetic clause. The typed owner,
  exact two-row bridge channel, appearance consumer, and named headed selector
  witness are active; that clause remains complete.

  The Stage 6 command-map clause is **REOPENED**. Checkpoint 4 replaces the three
  current task/session rows with six task rows while retaining current
  `pick_folder`/`start_plan` and the four bootstrap/cosmetic rows: 12 unique
  production commands. Checkpoint 6 replaces those two current Setup rows with
  eight accepted Setup rows, including `activate_task_pair`: 18 unique commands.
  After all checkpoints, the 32 target rows plus the four retained bootstrap/
  cosmetic rows make 36. Python/JavaScript policy mirrors must freeze each exact
  intermediate set and prove removed rows are replacements, not aliases or
  duplicates. **Gate status: open until the checkpoint-4 and checkpoint-6 map
  revisions pass.** *Not
  satisfied by* changing page CSS alone, seeding gallery DOM state after window
  creation, persisting a
  permissive dictionary, retrying failed I/O on a timer, or proving only the
  happy-path file round trip.
- **BR-G-47 — Setup admits one exact local-directory meaning.** Picker, typed
  input, remembered-location activation, and reviewed task-pair activation all pass through the same
  workflow-owned candidate service and produce purpose-bound, 30-minute,
  32-entry process-local slots; every plan or inventory start freshly re-admits
  the root. The whole-string parser accepts only ordinary absolute drive-rooted
  local directories of at most 32,000 UTF-16 code units, canonicalizes `/` to
  `\`, permits and removes one non-root trailing separator, and rejects all
  relative/drive-relative, device/extended, UNC/mapped-remote, ADS, wildcard,
  invalid-character, reserved/ambiguous, NUL/surrogate, repeated-separator, empty/dot-component,
  reparse/placeholder, file-leaf, inaccessible, unsupported-volume, and
  folder-mounted-volume inputs without trimming, expansion, normalization,
  enumeration, or parent substitution. No-follow probing covers every
  component and leaf; start-time probing, not the slot, is authority.

  Supported roots are fixed/removable local drives with usable native volume
  facts and exact filesystem name `NTFS`, `REFS`, `EXFAT`, `FAT`, or `FAT32`;
  network, optical, RAM-disk, unknown/no-root, and all other filesystem names
  refuse. Individual capability flags still control their own feature only.

  Native workflow admission converts raw bounded `PlanSetupInput` into one
  complete frozen `PlanSetupOptions` snapshot, including canonical
  bounded filters, disabled `preserve_ads=false`, and linked verification in
  the core `Commitment`; `start_execution` cannot resupply it. Recents derive
  only from opened ledger runs, exclude soft-deleted mappings from source,
  target, and pair lists, retain unresolved identity, and return deterministic
  five/five/five bounds. Process-secret deterministic HMAC ids require no
  retained recent map; recent activation rechecks current top-five membership
  and active mapping state. Task-pair activation instead pins one immutable plan
  generation and resolves its reviewed volume identities without treating
  `display` as a path. Either refused pair returns two truthful slotless
  assessments and creates no partial slot. An explicit Plan-again gesture may
  chain the resulting slots into a new default-selection task, but no background
  replan or selection carry-forward exists. Serial multi-pair creation reuses one frozen options
  snapshot and stable per-row command ids, admits ordinary starts one at a time,
  never rolls back successes, and recovers admitted tasks after navigation.
  Exact Python/JavaScript schemas, hostile inert text, parser/TOCTOU review, and
  installed headed picker/typed/recent witnesses all pass. **Status: OPEN until
  checkpoints 5 and 6 close the workflow and product surface.** *Not satisfied
  by* picker-only validation, `abspath`, trusting a stale slot or mount hint,
  silently converting a file to its parent, or a batch backend shortcut.
- **BR-G-48 — Recording truth and execution evidence never borrow authority.**
  The settlement oracle and production outcomes cover the complete filesystem
  success/failure × recording success/failure matrix. Each item has an
  independent `ok`/`degraded` recording axis with one typed bounded reason;
  task issues retain only the first observation of each of the five exact
  reasons in observation order. Pre-destructive flush failure refuses before
  mutation; later final-flush, finish, close, audit, or item failures never
  rewrite an already committed item. Aggregate recording is degraded exactly
  when an item is degraded or a task issue exists.

  The [exact item-free terminal shape](#exact-epochs-scalar-classes-and-recording-views)
  is decoded statelessly: recording is degraded exactly when its degraded-item
  count is positive or task issues exist, and decode never fabricates an
  anonymous degraded `OperationResult(items=())`.

  Each event-v5 item owns a closed bounded primitive detail variant and checked
  `detail_omitted_count`; arbitrary mappings/objects and raw out-of-domain
  quantities are structurally impossible. Over-limit diagnostics are omitted
  as null with exact aggregate witness, never truncated, and every complete
  reliable envelope fits the 1,048,576-byte pre-acceptance ceiling.

  One atomic ledger snapshot joins `operations.run_id=runs.id`, exact execution
  `runs.run_token`, overlay identity to `operations.op_token`, current inventory
  by target location plus persisted canonical
  `operations.target_rel_path_key`, and matching inventory scope. Only
  filesystem-successful COPY/UPDATE/MOVE_UPDATE is evidence-eligible. Missing
  committed operation is `unrecorded`; duplicate canonical eligible targets or
  scope/stat/presence/invalidation/provenance conflict is `superseded`;
  same-scope copy evidence is `recorded-copy`; same-scope
  readback/verify evidence is `already-verified` only with non-null
  `last_verified_at`; all else is `not-applicable`. Digests are full lowercase
  32-hex and appear as execution evidence only for recorded-copy or
  already-verified. Manual exact handoff starts a new dispatcher/history session
  against the original run token only when every applicable selected byte-
  producing item succeeded, committed, and is current. Post-settlement
  divergence blocks at task scope; all-already-verified starts no work, a zero-
  applicable execution refuses, and mixed exact/current refuses.
  **Status: OPEN until checkpoints 1–3, 8, and 10 close settlement, protocol,
  review, and handoff.** *Not satisfied by* global degradation assigned to each
  item, first-row-wins, operation-time digest persistence, an N+1 query, or
  ordinary refresh before exact verification.
- **BR-G-43 — Documentation describes the shipped contract, not the plan.**
  `DESKTOP_UI.md`, the focused component documents, README overview/index/
  limitations/changelog, and `ui_mockup/` status agree with the implemented
  behavior and supported scale envelope. A release trace maps every active
  `DESKTOP_UI.md` acceptance item to a BR-G/test or to an explicit, already
  approved deferral; zero items are merely omitted. *Not satisfied by* marking
  this bridge implemented while active documentation still describes the
  pre-bridge CLI or mockup behavior, or by copying an unmapped requirement into
  a new prose checklist.

**Import law, gating every lane**

- **BR-G-19 — The boundary holds.** `lint-imports` passes with the launcher
  contract extension and no new `allow_indirect_imports` exemption; a static
  assertion shows no symbol under `interfaces/` calls
  `normalize_relative_path`, `validate_relative_path`, or any `core` path
  helper. *Not satisfied by* the linter alone, which permits indirect use
  through a re-export.
- **BR-G-44 — The repository closes as one system.** The complete pytest suite,
  including tests excluded by ordinary-development marker defaults, and
  `lint-imports` pass from a clean checkout with the supported interpreter;
  every `test_br_g_*` test is collected, none is skipped/xfail on Windows, and
  `git diff --check` is clean. The narrow gate and watchlist commands are
  diagnostics, not substitutes. *Not satisfied by* running only changed test
  files, deselecting slow/platform tests, or weakening an existing assertion to
  preserve green.

`docs/TESTS.md` and `tests/_departments.py` own gate-test placement and scope;
every bridge gate retains the `test_br_g_<number>_` discovery prefix.

**Decision-to-gate traceability.** This is the completeness check. A DR is not
implemented because its code exists; it is implemented only when every gate in
its row and the applicable regression rows are green.

| Decision | Required gate(s) |
| --- | --- |
| DR-BR-01 | BR-G-10–13, BR-G-20, BR-G-24, BR-G-37, BR-G-40 |
| DR-BR-02 | BR-G-12, BR-G-24, BR-G-37 |
| DR-BR-03 | BR-G-13–15, BR-G-17, BR-G-20, BR-G-21, BR-G-37 |
| DR-BR-04 | BR-G-13, BR-G-46, BR-G-47 |
| DR-BR-05 | BR-G-16, BR-G-18, BR-G-29 |
| DR-BR-06 | BR-G-1, BR-G-4–9, BR-G-18, BR-G-25–29, BR-G-39, BR-G-47, BR-G-48 |
| DR-BR-07 | BR-G-7, BR-G-47, and scanner hostile/completeness regression rows |
| DR-BR-08 | BR-G-19, BR-G-34, BR-G-36, BR-G-37 |
| DR-BR-09 | BR-G-2, BR-G-19, BR-G-34, BR-G-35, BR-G-38 |
| DR-BR-10 | BR-G-2, BR-G-3, BR-G-19 |
| DR-BR-11 | BR-G-1, BR-G-2, BR-G-23, BR-G-35, BR-G-38 |
| DR-BR-12 | BR-G-12, BR-G-24, BR-G-29, BR-G-37, BR-G-39 |
| DR-BR-13 | BR-G-34, BR-G-35 |
| DR-BR-14 | BR-G-32, BR-G-36, BR-G-48 |
| DR-BR-15 | BR-G-2, BR-G-34, BR-G-36 |
| DR-BR-16 | BR-G-27, BR-G-34, BR-G-38, BR-G-40, BR-G-42, BR-G-45 |
| DR-BR-16.1 | BR-G-22, BR-G-23, BR-G-38, BR-G-42, BR-G-45 |
| DR-BR-16.2 | BR-G-11, BR-G-40, BR-G-42, BR-G-48 |
| DR-BR-17 | BR-G-14, BR-G-24, BR-G-37 |
| DR-BR-18 | BR-G-34, BR-G-36 |
| DR-BR-19 | BR-G-34, BR-G-36 |
| DR-BR-20 | BR-G-16, BR-G-23, BR-G-38, BR-G-39 |
| DR-BR-21 | BR-G-35, BR-G-41, BR-G-45, BR-G-48 |
| DR-BR-22 | BR-G-21, BR-G-33, BR-G-41, BR-G-45, BR-G-48 |
| DR-BR-23 | BR-G-31 |
| DR-BR-24 | BR-G-14, BR-G-15, BR-G-21–23, BR-G-33, BR-G-38, BR-G-41, BR-G-42, BR-G-45 |
| DR-BR-25 | BR-G-32, BR-G-35, BR-G-39 |
| DR-BR-26 | BR-G-1–3, BR-G-35 |
| DR-BR-27 | BR-G-9, BR-G-14–16, BR-G-23, BR-G-29, BR-G-33, BR-G-41, BR-G-45, BR-G-47, BR-G-48 |
| DR-BR-28 | BR-G-46 |

BR-G-19, BR-G-43, and BR-G-44 are cross-cutting release gates and therefore
apply to every row even where not repeated. Product goals 1–5 are witnessed,
respectively, by `{34,35,42,47}`, `{12,20,24,37,39,47}`,
`{18,36,39,40,41,48}`, `{6,32,35,39,47}`, and
`{15,20,21,37,39,41,45,48}`.

### Regression watchlist (existing M1)

`docs/TESTS.md` and `tests/_departments.py` own executable scope and command
routing. They supplement the BR-G gates above; changing an existing assertion
is a regression unless its governing DR changes. BR-G-44 still requires the
ordinary suite, import-law check, and diff check with no skipped, xfailed,
xpassed, or uncollected bridge gate on the supported Windows profile.

### Stage 6

The BR-G entries define bridge completion. `M1_SHELL_H2.md` is the sole owner
of the checkpoint 0–12 sequence and review boundaries; each command row above
records only its activation checkpoint. `M1_SHELL.md` owns the broader legacy
slice lineage, host/package closure, and deferrals. Neither delivery plan may
weaken an exact DR, schema, or BR-G gate in this document.
