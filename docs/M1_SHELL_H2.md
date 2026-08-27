# Stage 6 Slices 5–6 and Early Slice 7 Implementation Plan

> Active execution checklist ratified on 2026-08-24. `docs/M1_BRIDGE.md` owns
> the exact accepted protocol and `docs/M1_SHELL.md` owns the Stage 6 shell
> sequence; this file is the newest checkpoint reslice and owns the detailed
> acceptance, review, and test boundary for checkpoints 0-12.

Delivery status (2026-08-27): checkpoints 0–3 and the independently reviewed
3R remediation are complete, including the separately reviewed checkpoint-3.3
legacy-source removal. Checkpoint 4 is in its pre-model ownership audit;
checkpoints 5–12 remain pending. No checkpoint-4 command or control is active.

The 2026-08-27 sorting and rebaseline additions below are accepted requirements
for checkpoints 7/9 and 10 respectively, not implemented behavior. New views
and explicit sorting reset use canonical path-key order.

## Main objectives

- Deliver the complete Setup → Plan → Execute → Inventory/Integrity workflow, including typed paths, remembered locations, bounded file lists, execution controls, full recorded hashes, and modification times.
- Establish exact event-v5 recording truth: item-local recording degradation remains separate from filesystem outcome and task-wide recording issues.
- Replace the one-session bridge model with process-live tasks that retain reviewable results across navigation and support later manual verification.
- Pull forward Slice 7 lifecycle, retention, shutdown, and event/history epoch work while deferring the history page, global settings page, drag-and-drop, and remaining cosmetic state.

## Locked contract map

The exact accepted target is not duplicated in this checklist.
`M1_BRIDGE.md`'s file map and mapped DR-BR records own field shapes, wire
schemas, command rows, authority order, refusal precedence, and bridge gates.
`DEFENSE.md` §1.3 owns the numeric and retained-resource hard walls. The
locked-contract summaries below define scope and dependencies; the checkpoint
section retains detailed acceptance and test categories without redefining the
exact schemas or hard-wall values. A conflict is resolved in the owning mapped
decision record, not by treating this prose as a second authority.

### Recording and evidence scope

- Keep filesystem outcome, item-local recording status, task recording issues,
  and history audit as independent truth axes.
- A committed item receipt is final; later task or audit degradation cannot
  rewrite it or suppress durable evidence.
- Process-local execution continuation may carry transient evidence only until
  terminal settlement. Retained task views and JavaScript use the bounded
  projections accepted in the bridge records.
- Execution review classifies evidence from one ledger-current snapshot.
  Plans expose no hashes, and current inventory/integrity detail labels
  provenance rather than presenting coincidental state as execution evidence.

### Protocol and persistence scope

- Checkpoint 2 changes only the process-local execution continuation.
  Checkpoint 3 is the coordinated core-event, terminal-summary, bridge-
  validator, ledger, history, CLI, and compatibility cutover with three
  independently testable landing stops.
- The exact `TerminalSummary`, refusal fact, recording fields, database epoch,
  scalar codec, checked-arithmetic policy, and reset posture are owned by the
  mapped bridge decisions and `DEFENSE.md` §1.3.
- Protocol targets are accepted but inactive until their implementation
  checkpoint; current-version documentation remains truthful until then.
- Every checkpoint that activates command rows updates BR-G-32's exact ordered
  production-table test and the JavaScript policy mirror in the same commit.
  Checkpoints 4 and 6 also advance BR-G-46's two reopened map revisions; later
  command additions remain ordinary BR-G-32 revisions.

### Setup, paths, and remembered locations

- Setup freezes every semantic option used by a plan; JavaScript never
  normalizes filters or rereads mutable defaults for an admitted task.
- Picker, typed, and remembered inputs share one workflow-owned local-directory
  admission path and create only bounded, purpose-bound process-local slots.
  Every real start freshly re-admits its roots.
- Desktop admission accepts the reviewed local Windows directory domain and
  rejects file leaves, remote/device spellings, reparses, placeholders, and
  unusable volume facts with typed action-guiding results.
- Recents come only from eligible ledger runs, remain distinct from current
  reachability, and are revalidated when activated. Multi-pair creation is
  serial browser orchestration over ordinary single-task starts.

### Task, review, and retention scope

- A process-live task owns at most one current session while retaining
  separately named compact plan, execution, inventory, integrity, and post-copy
  results across navigation.
- Lifecycle, result, selection, view, and browser request authorities remain
  distinct. One task-operation owner serializes effect-owning lifecycle work;
  the exact claim, lease, epoch, publication, release, and close ordering lives
  only in the mapped bridge records.
- Reliable item facts update compact overlays; terminal transport uses the
  accepted bounded summary rather than sending a full result item collection
  to JavaScript. Producer/core and presentation omission witnesses remain
  separate.
- Plan and inventory trees are server-owned, immutable-generation projections
  with bounded search, filters, windows, anchors, and action scope. A complete
  candidate publishes atomically or not at all.
- Task and projection retention obey `DEFENSE.md` §1.3. The bridge records own
  the complete charged graph, reservation mechanics, retry receipts,
  tombstones, publication-fault behavior, and exact capacity results.
- Setup, plan/execution, inventory/integrity, and task-lifecycle command
  families land only in their named checkpoints. Exact command names, request
  shapes, retry classes, deadlines, and activation rows remain in
  `M1_BRIDGE.md`.

## Committable checkpoints

### Checkpoint execution protocol

The ordered checkpoint list is also the recovery protocol for an implementer
who has no session context. Before starting a checkpoint, confirm that the
preceding row in `M1_SHELL.md` is complete, inventory every existing worktree
change, and reread that checkpoint's mapped `M1_BRIDGE.md` decisions and BR-G
gates plus any `DEFENSE.md` wall it cites. Do not absorb, rewrite, or commit
unrelated or already-started work merely to obtain a clean tree.

Except where a checkpoint lists multiple mandatory commits, its `Commit:` line
names the required activation/closure commit; it does not require all
preparatory work to be compressed into one commit. Preparatory commits may add
types, independent validators, fixtures, backend machinery, or browser code
only while the accepted target remains unreachable from every production
dispatcher, command map, persistence reader, and rendered control. The closure
commit makes the checkpoint coherent at once: no production row points at a
partial backend or UI, and every replaced row loses its old alias in that same
commit. A checkpoint may be `in progress` at a documented safe stop, but it is
not `complete` until this closure lands.

Run focused tests while editing. Before an activation/closure commit, run every
affected producer and consumer department and the ordinary suite for a shared
or cross-department contract; run `lint-imports` when dependency boundaries
move and the installed headed witnesses when a user surface activates. A BR-G
gate closes only with the exact production entry point, counterexample, and
collected `test_br_g_<number>_*` nodes required by `M1_BRIDGE.md`; skipped,
xfail, comment-only, dormant, or uncollected evidence does not count. Record
measurement fixtures and validators before observing acceptance evidence, as
required by `DEFENSE.md`.

If a gate or adversarial review exposes a policy defect, land the policy and
persistent regression in a separate commit, invalidate affected evidence, and
rerun the gate from its declared entry state. Do not weaken a gate or silently
retune a constant to preserve green. At closure, update the checkpoint row in
`M1_SHELL.md`, every owning document's active/inactive wording, and any gate
status changed by the checkpoint in the same commit. When work stops before
the next checkpoint closes, replace `HANDOFF.md` with the exact safe stop,
verification already run, dirty-file ownership, and next command; checkpoint
12 remains the one integrated CHANGELOG and final-documentation closure.

### 0. Ratify the reslice and protocols

This checkpoint was intentionally relanded as five ordered documentation
commits so each authority remains independently reviewable:

1. `docs(bridge): accept the stage 6 second-half contracts`
2. `docs(gui): reslice the stage 6 second half`
3. `docs(defense): record the stage 6 scalar and retention walls`
4. `docs: point component docs at the accepted contracts`
5. `docs: record the stage 6 ratification`

This five-commit boundary supersedes the original single checkpoint-0 commit
shape for atomicity and serviceability; it does not change later checkpoint
numbers or implementation dependencies.

- **Objective:** Make active documentation the decision authority before implementation.
- **Acceptance:** Re-slice M1_SHELL/M1_BRIDGE; place the exact accepted command,
  protocol, ownership, and retention target in the mapped `M1_BRIDGE.md`
  decision records; keep the normative scalar and containment walls in
  `DEFENSE.md`; and reduce other active documents to behavior summaries or
  ownership pointers. Rewrite BR-G-36, BR-G-39, BR-G-41, and BR-G-45; add
  BR-G-47 for Setup/location admission and BR-G-48 for recording/evidence
  handoff.
- **Regression watch:** Find every positive v3/v4 compatibility statement, picker-only claim, nullable `start_plan`, one-session task assumption, full-terminal transport promise, UI-state recent, numeric mtime, and immutable operation-attestation proposal.
- **Tests:** Documentation links/anchors, contract-source locators, targeted
  consistency searches, test-manifest validation, and `git diff --check`.
- **Docs/review:** Update the authorities and replace component restatements
  with links. Keep `TESTS.md` free of a parallel checkpoint/case catalog, mark
  target contracts accepted-but-not-active until their checkpoint, and conduct
  independent architecture/security review.

### 1. Pin recording-axis settlement truth

Commit: `test(executor): pin typed recording settlement truth`

- **Objective:** Establish the expected executor behavior before changing producer contracts.
- **Acceptance:** Extend only the oracle's pre-production typed projection and focused tests; do not change the protected scenario/row manifest, normalized trace, baseline JSON, or semantic hash pin. Pin the four-way matrix exactly: `success.all-nine` COPY = filesystem succeeded, recording `ok`, null reason; `record.copy-failure` = filesystem succeeded, recording `degraded`, `record-write-failed`; `failure.copy-prepublish-cleanup-ok` = filesystem failed, recording `ok`, null reason; and `failure.byte-published.copy` = filesystem failed, recording `degraded`, `unrecorded-mutation`. Also pin `recording.pre-destructive-flush-refusal` to item reason `recording-prerequisite-failed`; `recording.final-flush-degradation` to a successful recording-`ok` item plus only task issue `final-flush-failed`; and `recording.sticky-aggregate-degradation` to a degraded first item, `ok` second item, and sticky degraded aggregate.
- **Regression watch:** Do not change filesystem outcomes, retry traces, journal retirement, durable-state interpretation, recorder order, pause/cancel behavior, or existing baseline facts.
- **Tests:** Executor and tools departments; run `.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3` and require all scenarios/rows, identical normalized traces, no skip, and no unresolved finding.
- **Docs/review:** Update EXECUTOR and TOOLS. Review the new oracle projection separately from production changes.

### 2. Attribute executor recording degradation internally

Commit: `refactor(executor): attribute recording degradation by scope`

- **Objective:** Introduce typed internal item/task attribution without redesigning settlement or changing the live core-event v4 wire yet.
- **Acceptance:** `_record()` returns a typed observation; `ExecutionSet` retains sparse degraded operation IDs/reasons and task issues; identityless transient evidence is tied to that operation’s recording failure. Final flush and restoration divergence remain task-scoped. Advance the exact process-local workflow execution payload to v6 in this checkpoint so attribution and permitted transient attestations survive real dispatcher pause/resume; payload v5 is refused after the cutover. On every terminal path dispatcher nulls the opaque continuation payload reference before publishing/storing the terminal record.
- **Regression watch:** Guard `_Settled`, `_SettlementReduction`, `_record`, `_flush_before_destructive`, `_settle`, publication reducers, resumed-directory restoration, and reliable-emission-before-continuation ordering. No global degradation may assign item status.
- **Tests:** Executor plus workflow/dispatcher neighborhood; first-row-fails/second-commits, committed-copy/later-item-fails, prepublication failure, apply-raised-but-state-matches, rowless immediate linked verify, pause/resume, paused→resumed→terminal payload scrubbing on success/failure/cancel and delayed release, and event-sink rejection. Repeat the settlement oracle three times.
- **Docs/review:** Update EXECUTOR, RECORDER, and WORKFLOWS. Adversarially compare filesystem/recorder traces before and after.

### 3. Stage the exact event-v5 cutover

Commits, in order:

1. `refactor(protocol): prepare dormant event v5 consumers`
2. `feat(protocol): publish exact core event v5`
3. `refactor(protocol): remove legacy event compatibility`

**Complete (2026-08-27).** Checkpoint 3.3 removes the private older-version
decoders, their exclusive helpers, and positive fixtures. Independent review
closed two test-quality findings before acceptance: the reintroduction witness
now isolates the source-removal guard, and retired-version batches include a
valid prefix. Core/interfaces passed 2,428 tests with one privilege skip; the
required-Node ordinary suite passed 4,524 with four privilege skips and 28
headed deselections. All 11 import rules held, and the protected settlement
oracle passed 30 scenarios three times with identical traces and baseline
parity. Frozen measurement and epoch-5 artifacts were unchanged. Later
product/follow/retention gates remain open.

- **Objective:** Publish the new truth contract across every producer and consumer and remove legacy machinery.
- **Position and safe stops:** Keep this checkpoint before checkpoint 4.
  Checkpoint 4's retained task/result model already consumes the exact v5
  `TerminalSummary`, recording axes, and database epoch; moving the cut behind
  checkpoint 7 would build checkpoints 4–7 against a disposable v4 task
  contract. The first commit adds strict v5-specific consumers, validators,
  fixtures, and direct test seams, but keeps every production current-version
  constant, dispatcher, allowlist, history/database reader, and browser route
  exact-v4. The v5 path is unreachable except by its explicit tests, so this
  stop changes neither emitted/persisted behavior nor accepted production
  input. The second commit atomically switches every producer and live consumer
  dispatcher and performs the coordinated database epoch/reset cut; its safe
  stop is a fully working exact-v5 runtime with now-unreachable, read-only v3/v4
  branches still present in source. The third deletes those branches and
  positive fixtures, freezes the one exact version, and closes the checkpoint.
  Never make v5 reachable from production before the coordinated switch, land
  a producer switch before its consumers, or delete compatibility before the
  v5 runtime passes.
- **Acceptance:** Implement the mapped recording, reliable-event,
  terminal-summary, review-limit, scalar-codec, file-identity, and persistence
  decisions from `M1_BRIDGE.md` and `DEFENSE.md` §1.3 across core producers,
  JavaScript, dispatcher views, history, CLI, and service. Store full-width
  Windows file indexes as canonical `FileIndex128` text, obtain native identity
  through the core-owned complete `FILE_ID_128` adapter, and remove the legacy
  64-bit handle projection and numeric SQLite representation. Preserve the
  checkpoint-2 continuation boundary, keep bridge-only presentation omissions
  separate, perform the coordinated database epoch/reset cut, and delete all
  positive compatibility paths for superseded core-event versions.
- **Regression watch:** Whole-batch malformed-event rejection, cursor
  immutability, Gap recovery, Progress identity/monotonicity, terminal
  precedence, history audit degradation, Boolean-as-integer mistakes, unsafe-
  number or narrowed-file-identity leakage, reachable logical-byte/timestamp
  refusal, and stale development databases.
- **Tests:** At the first stop, prove production dispatch and persistence stay
  exact-v4, no production route can select v5, and the directly addressed v5
  consumer/validator helpers accept and reject the exact target. At the second,
  run Core,
  executor, verifier, database, workflows, dispatcher, and interfaces
  departments; strict codec/payload round trips and wrong-version refusal;
  every detail/reason/review-limit population/axis variant, key, nullability,
  cardinality, and signed-64 bound; plan logical-byte refusal and scanner
  scalar-warning behavior; full-width `FileIndex128` codec/database round trips;
  shared native-identity adapter use by scanner, preflight, executor, and
  verifier; NTFS/ReFS equivalence witnesses for any retained `st_ino` fast path;
  values above signed 64-bit and unsigned 64-bit in test doubles; absence of
  legacy high/low narrowing and numeric file-index storage; exact refused/unrun
  review-limit invariants, `TerminalSummary` copy, history all-null-or-exact
  group, terminal hash/repeated-finalization/reconstruction/CLI parity, and
  absence of presentation omissions from history; arbitrary-object/raw-int
  rejection; diagnostic omission without truncation and checked core-versus-
  presentation witness separation; exact maximum reliable envelope accepted
  plus one structurally over-limit rejection before sequence/queue mutation;
  maximum head drained alone under the bridge ceiling; duplicate-key and scalar
  corpora; startup/CLI reset guidance; required Node validator/reducer;
  ordinary suite; current-source v5 event/custody drift runs. At the final stop,
  prove source/fixtures contain no positive v3/v4 compatibility and repeat the
  ordinary suite plus the settlement oracle. Frozen old measurement artifacts
  remain untouched historical evidence.
- **Docs/review:** Mark v5 active in CORE, DATABASE, HISTORY, TESTS, M1_BRIDGE, INTERFACES, and README. Repeat the settlement oracle three times and independently inspect removal completeness.

### 3R. Remediate independent checkpoint-review findings

**Complete (2026-08-27).** All accepted findings from the independent review of
checkpoints 1–3.2 and its follow-ups are closed in 24 separately reviewed
planning, repair, and closure commits (`989617a` through `bba64ec`).
The temporary 3R hold was lifted before checkpoint 3.3 began.

| Checkpoint | Delivered issue or boundary | Commit |
| --- | --- | --- |
| 3R.0 / follow-up plan | Freeze remediation scope, ordering, and independent review boundaries. | `989617a`, `77bfc5f` |
| 3R.1 | Restore authoritative settlement attribution and unconditional reducer gates. | `15c628c` |
| 3R.2 | Pin execution-v6's closed recording vocabulary and contradictory-state refusal. | `306de50` |
| 3R.3 | Retain committed receipts and exact pending settlement across reliable-sink rejection. | `1fc5e5b` |
| 3R.4 | Retain prerequisite cause; backstop validation cannot mask an external error or retire inconsistent evidence. | `1e794e7` |
| 3R.5 | Contain diagnostic-rendering faults without losing recording truth. | `8f6d8f8` |
| 3R.6 | Preserve recording-close and accepted-item truth on compound workflow failure. | `f15a82d` |
| 3R.7 | Normalize scalar/file-id type, grammar, range, and optimized-mode boundaries. | `bd05ff7` |
| 3R.8 | Enforce one exact v5 outcome/recording/cancellation matrix across Python and JavaScript. | `f96804b` |
| 3R.9 | Align timestamp grammar and canonical reliable-envelope size checks. | `04d5fb8` |
| 3R.10 | Validate complete task updates before queue/cursor mutation or custody release. | `e4fd539` |
| 3R.11 | Harden live-route, private-seam, and real Python-to-JavaScript source gates. | `ec4e9c8` |
| 3R.12 | Establish exact database topology comparison and independent negative fixtures. | `7956834` |
| 3R.13 | Activate complete WAL-aware admission without mutating source database evidence. | `d7673b7` |
| 3R.13a | Replay retained settlement unchanged on cancellation. | `76d897b` |
| 3R.13b | Amortize full admission through bounded runtime-owned reader lifetimes. | `544f249` |
| 3R.13c | Keep private validation copies beside the required local database. | `6cdfd08` |
| 3R.S5 | Separate payload-free stored projections from process-local live continuation. | `3a1b409` |
| 3R.14 | Hash explicit closed canonical projections and enforce the coordinated epoch-6 reset boundary. | `4b2af38` |
| 3R.15a | Correct the timestamp comment and live schema-constant name. | `d05995d` |
| 3R.15 | Reconcile active documentation, findings, and integrated verification. | `0886c17` |
| 3R.15b | Rename the live v5 validator family and its exact source gates. | `1c2ca16` |
| 3R.14a | Enforce Unicode-scalar JSON boundaries while preserving valid bytes and optional-warning containment. | `bba64ec` |

[BUGS.md](BUGS.md) owns the causal findings, fixes, and residual boundaries;
component documents own the resulting contracts. The full former checkpoint
clauses remain in `74abbc6:docs/M1_SHELL_H2.md`; original reviewer reports
remain in `d7673b7:docs/HANDOFF.md`. Do not recreate those reports here.

The closing ordinary run passed 4,498 tests with four Windows privilege skips
and 28 headed deselections; required Node ran, all 11 import rules held, and
the settlement oracle passed 30 scenarios three times with identical traces.
That receipt closed 3R, not later product/headed/resource gates or the private
legacy source seam subsequently removed in checkpoint 3.3. [HANDOFF.md](HANDOFF.md) carries the
restart boundary and separately deferred context.

Protected settlement traces/baseline/semantic hash, frozen epoch-5 witnesses,
and frozen transport evidence remain unchanged; the repaired gate authority
remains protected. S5 and identity design holds are
resolved; current persistence/reset and M2 recovery constraints live in
[DATABASE.md](DATABASE.md) and [DISPATCHER.md](DISPATCHER.md).

### 4. Install task-centric lifecycle and compact artifacts

Commits, in order:

1. `test(web): pin task artifact reservation model`
2. `feat(web): install dormant task lifecycle`
3. `feat(web): retain multi-session task artifacts`

**In progress (2026-08-27), before the first mandatory commit.** Independent
source audits found that the current complete graph cannot yet justify a
frozen reservation floor. The dispatcher exception-retention prerequisite
is fixed separately in `74135b5`; the native reply lifetime prerequisite now
passes all eight installed transport/native-host witnesses. The independent
standalone-integrity candidate wall is ratified in `2818686`, and the linked
verify-continuation diagnostic boundary is now closed without selecting a
codec or task-reservation ceiling. None of these changes freezes the model or
closes BR-G-45. Resolve
the following before accepting the first model commit:

A fresh checkpoint-4.1 derivation was rejected and discarded before commit.
It multiplied the one aggregate plan-domain and informational walls across
several aliases, summed sequential scanner/planner/observer/preflight peaks as
simultaneous owners, priced retained event graphs as wire bytes, and selected
codec/native/browser constants without a source-derived representation. Its
internally consistent totals are invalid and must not be recovered from Git,
session context, or interruption stashes. The next derivation must split actual
phase unions, identity-deduplicate aggregate artifacts, use named limits rather
than repeated literals, and reject every unused constant and opaque fixed blob.

The same audit found finite-model prerequisites beyond the earlier path list:
the desktop task cap does not yet bind dispatcher subscribers/sessions or all
runtime/service maps; inventory scan/query/tree construction precedes complete
admission; the standalone-integrity retained-byte wall is declared but not
enforced; and bridge response projection, outstanding document posts, and
CLR/WebView2/browser copies lack one complete bound and retirement witness.
The direct verifier chunk seam found in the same audit is now closed by one
exact public 4 MiB maximum, so the model charges at most one aligned native
buffer and one Python bytes copy per open stream. The remaining blockers are
OPEN in [BUGS.md](BUGS.md). Close them structurally or place them behind an
exact enforced desktop-only premise before freezing numerical charges. A
timeout or composition convention is not a retirement witness.

Canonical typed-detail admission is now structurally closed: exact-base
construction validates the complete bounded shape, admission takes a fresh
base snapshot, duplicate raw items refuse before omission, and wire projection
revalidates owned state. This is a prerequisite fix, not a frozen model.

Residual service-observer and task-recovery exception retention is also
structurally closed. Raw close, reobserve, validation, and stale-unsubscribe
failures plus unadmitted current views retire before dependency shutdown or
task-condition reconciliation; closed failure state preserves only cleanup,
generation, interruption, and retry truth. This remains a prerequisite fix,
not a reservation-model acceptance.

The narrow planning-source wall is now structurally closed across both scans,
prior correspondence, planner policy/assignment/operations, observation, and
preflight. Independent raw populations fail at first excess; declared hostile
inputs/results are detached and revalidated at each distinct seam; and only
unavoidable shallow slots retained together in the final scan, plan, world,
and verdict graphs commit to the session ledger. Correspondence inputs are
already bounded by admitted scans and its hostile result is captured exactly
once. First excess is typed `REFUSED+UNRUN` with no saved or partial plan.

This prerequisite deliberately excludes construction builders, sorting/index
storage, selection/exclusion and preview values, callback overlap, codec/text
and native/browser copies, complete-tree projection, and speculative future
owners. Those costs, complete-object constants, formula, fixture, validator,
and BR-G-45 evidence remain checkpoint 4. Dispatcher pre-run and cancellation-
settlement exception owners are now closed independently. Refusal authority is
also closed narrowly: only an exact PLAN fact issued by the current workflow's
opaque admission family becomes `REFUSED+UNRUN`; workflow takes a fresh core
snapshot, consumes the issuer, retires the raw signal, and saves no artifact.
Phase delivery, correspondence, nested module collaborators, destination
policy, and mutated preflight input cannot claim that authority. Ordinary
exception ownership is deliberately not claimed by this prerequisite.

Checkpoint 4 must treat the following live seams as mandatory model inputs. It
may eliminate an owner before downstream work or charge its exact simultaneous
graph with a finite retirement condition; no acceptance may assume release:

`core.session.run_session` is now structurally closed for emitter mutation-plus-
raise, work errors superseded by accumulator truth, consumed pause/cancel, and
audit failures. It retires traceback/cause/context for nested exception-group
members too. Unsuperseded process-fatal exceptions and arbitrary custom
exception state leave with their caller and are not retained task artifacts.

Planner and sync-workflow phase frames are now structurally closed too.
Escaping public identities keep their established types/messages, the one
required logical-byte cause survives without its frames, consumed execution
errors become typed details, and recording keeps only closed issue state.
Truthy context suppression, hostile diagnostics/notes, path-cause projection,
and repeated exclusion delivery have independent regressions. Path-message and
other callback/construction transients remain checkpoint-4 model inputs.

- Dispatcher admission, cleanup, persistence, and custody release: audit-
  factory fallback, rollback/stream/hub/store cleanup, thread-start failure,
  stale-lease release, and drop-only catches that can retain external aliases.
- `TaskRegistry.replay_start`, `_start_owner`, and `_attempt_compensation`:
  primary start failure overlapping cleanup, compensation, or retry truth.
- `NamiSyncService.start_plan` and `Dispatcher.subscribe`: public chained path/
  subscription exceptions that retain raw causes. Preserve current public
  types, messages, path redaction, custody, and retry truth while eliminating
  or charging them.

Checkpoint-4 regressions for these seams assert public status, item, counter,
retry, and identity behavior plus externally held lifecycle release. They do
not freeze private counters, handler timing, or callback choreography.

- Linked execution can retain both 120,000 operation and 120,000 integrity
  outcomes, plus the dispatcher accumulator and shallow audit/store wrappers.
  Full-result header diagnostics now share the terminal summary's whole-value
  bounds, but the summary still does not bound the raw item collection or the
  additional workflow/audit owners behind it.
- Serialization expands the complete schema occurrence graph, not just path
  strings: shared dependency tuples, metadata/evidence, and per-candidate
  absolute roots can become distinct lists, strings, and decoded objects.
  Keep this future-copy liability separate from the identity-deduplicated
  retained-domain walls; a constant multiple of those walls alone is unsound.
- Original history-observer payloads, delayed audit finalization, callback
  retry, and remaining exception tracebacks are real owners. Observation-stream
  history and dispatcher worker frames now have explicit release witnesses;
  exact worker retirement remains fenced through thread exit. Every remaining
  owner needs an explicit finite charge and retirement condition, or structural
  elimination, before a completion reservation may be released.
- The complete-graph validator must classify non-slotted instance dictionaries,
  mapping-proxy backing stores, mutable-container high-water capacity, `Path`
  caches, all declared detail entries, and native/browser serialization copies.
  The frozen transport instrument is not that validator and remains untouched.
- Standalone integrity now has a separately named 120,000-row/192-MiB candidate
  wall with honest post-refresh `FAILED+RAN` policy, but repository, workflow,
  service, and retirement enforcement remain incomplete. Enforce it before
  receipt, tree, repository, resolver, native, or result work; stale unions and
  saved resume selections must refuse as complete populations rather than
  truncate.
- `VerifyContinuation.execute_phase` now owns a fresh exact base snapshot;
  executor diagnostics and their combined phase value use the existing
  whole-value policy with exact omission accounting. Construction, v6 encode/
  decode, direct workflow entry, and canceled settlement revalidate that
  boundary, and the raw executor result retires before the continuation sink.
  Continuation codecs still project or parse the complete graph before any
  whole-envelope ceiling; derive their pre-projection and pre-parse ceilings
  from the frozen occurrence model.
- Planning roots/profiles/evidence/filter/assignment values are now captured
  from declared exact fields at hostile seams. Only their final shallow
  collection slots participate in the source prerequisite; complete object,
  text/codec, construction, and callback costs remain model work. Other task
  paths, mount/inventory values, and runtime `_inventory_details` still need
  exact task/session retirement or a separately charged bounded owner before
  completion capacity can be released.

These are source-derived counterexamples and enforcement prerequisites, not
memory measurements or a substitute maximum fixture. No numerical model,
fixture, or acceptance evidence has been frozen or calibrated yet.

- **Objective:** Remove the one-session assumption before adding production surfaces.
- **Position and safe stops:** The first commit freezes the complete analytical
  artifact graph, per-artifact constants, aggregate formula, maximum fixtures,
  independent validator, and typed reservation/refusal expectations before any
  result is measured or surface is reachable. The second installs the task
  registry, ownership/lifecycle machinery, bounded artifacts, and dormant UI
  consumers while the production nine-row command map and current one-session
  behavior remain exact. The third is the activation/closure commit: it
  switches the command map to the exact 12 rows, removes replaced aliases,
  exposes the coherent task rail and controls, and proves the predeclared model
  without changing its constants. Any defect in that model follows the
  checkpoint execution protocol and restarts its evidence; it is never folded
  into the activation commit by amendment.
- **Acceptance:** Implement the mapped one-current-session task model,
  lifecycle and result authorities, owner claim, transactional observation
  attachment, task reads/control, exact-session release, task close, compact
  overlays/results, bounded terminal summaries, and page rehydration. Apply the
  exact publication and overlay invariants from `M1_BRIDGE.md`, and enforce the
  complete conservative pre-surface reservation floor from `DEFENSE.md` §1.3;
  checkpoint 11 calibrates and proves that already-active containment model.
  Revise the production command mapping from nine to 12 unique rows: retain the
  four bootstrap/cosmetic and two current Setup rows while replacing three
  current task/session rows with the six checkpoint-4 task rows.
- **Regression watch:** No task lock across facade, JSON, database, or filesystem work; non-atomic issue/retirement classification and lease acquisition; normal named publication advancing the task epoch; same-revision start/start, control/start, control/close, start/close, and release/successor races; claim-owner and attach/start compensation; terminal-event versus terminal-record race; stale drain/release; pinned-generation release or eviction; observer-thread and close-long-poll deadlock; receipts released before task close; references retaining full results; uncharged read/native/callback copies; capacity failure during release/close; mutation rows accidentally taking the lifecycle claim.
- **Tests:** At the first stop, prove the independent validator rejects every
  constant, formula, root-class, and refusal-boundary drift before retaining
  evidence. At the second, prove the exact current nine-row production map and
  one-session behavior remain reachable while every new task command and
  rendered control is unreachable. At activation, run the dispatcher/
  interfaces/service neighborhood; competing starts and
  unpublished-task claims; control/start/close/release interleavings; atomic
  lookup, issue, retirement, claim, lease, and epoch decisions; publication-
  versus-close barriers; exact overlay/result revision invariants; no mixing of
  plan, execution, inventory, integrity, or post-copy generations; every
  bridge/defense-owned population and retention refusal boundary; old/new
  diagnostic and artifact overlap; pinned-generation replacement/eviction;
  handler-saturation reconciliation; start/control/release/close replay and
  tombstones; byte-aware drain; reinjection; delayed terminal cleanup; and
  shutdown during observation. Python and JavaScript policy mirrors freeze the
  exact 12-row mapping with no retained alias for a replaced task/session row.
- **Docs/review:** Update ARCHITECTURE, M1_BRIDGE, DESKTOP_UI, INTERFACES, and DISPATCHER. Review the complete ownership graph and initial BR-G-45 analytical model; land the checkpoint-4 BR-G-32 command-table and BR-G-46 command-map revisions together.

### 5. Unify probing, recents, and typed directory admission

Commit: `feat(workflows): unify location probing and recent locations`

- **Objective:** Give Setup and inventory one workflow-owned location-candidate pipeline.
- **Acceptance:** Add `LocationCandidate`, typed probe states, fresh binding resolution, the exact supported-volume predicate, bounded ledger recent queries, deterministic indexes, process-secret HMAC recent ids with current-top-five/active-mapping revalidation, and common picker/typed/recent admission. Existing inventory binding uses the shared workflow without weakening scanner/preflight/executor re-probes.
- **Regression watch:** Accidental `abspath` of relative input, reparse following, UNC/mapped-network admission, stale mount hints, clone ambiguity, probing that enumerates children, raw path/exception leakage, and treating `RootAuthority` as cached authorization.
- **Tests:** Core/database/workflow/interface neighborhood; every parser rejection class; file-leaf rejection; long/slash paths; root/leaf reparse and placeholder; missing/offline/remount/ambiguous volume; five/five/five query bounds and `EXPLAIN QUERY PLAN`; activation races, slot expiry, and purpose mismatch.
- **Docs/review:** Update DEFENSE, ARCHITECTURE, DATABASE, INVENTORY, WORKFLOWS, and FEATURES. Perform an adversarial parser and TOCTOU review.

### 6. Build frozen Setup and serial multi-pair creation

Commit: `feat(web): add frozen setup and serial task creation`

- **Objective:** Deliver the initial Setup page and exact Setup bridge rows.
- **Acceptance:** Render typed/picker fields, probed recents/pairs, all implemented semantic controls, disabled ADS, raw bounded inputs admitted to backend-canonical complete snapshots, immediate path invalidation, admission freeze, truthful slotless partial-pair refusal, standalone inventory-task creation, and serial best-effort pair creation. Add explicit Plan again through `activate_task_pair` followed by ordinary `start_plan`: resolve the retained plan's reviewed volume identities, publish two slots only when both accept, reuse its frozen Setup options, and create a new default-selection task without background replanning or authorization carry-forward. No Setup edit writes global defaults and JavaScript owns no filter normalization. Replace the two current Setup rows with the eight checkpoint-6 rows, producing 18 unique commands with the six checkpoint-4 and four retained bootstrap/cosmetic rows.
- **Regression watch:** Default-settings race, hidden `null` fallback, filter amplification, stale slots, drive-letter reuse, task close or plan-generation change during reviewed-pair resolution, display text promoted to path authority, double click, command-ID reuse after edits, automatic retry with a new ID, background task creation, selection carry-forward, partial pair activation, navigation/reinjection, and unsafe filesystem labels in the DOM.
- **Tests:** Exact 18-row Python/JS command policy mirrors and key validators; filter bounds/canonicalization; mixed batch successes/refusals; exact `slot-claimed` busy guidance; one-slot and atomic two-slot `slot_capacity_full` under all/partially pinned capacity with no native probing or partial slot; `recent_unavailable`; task-pair resolved/remounted/missing/offline/ambiguous identities; exact replay before and after task close; plan-generation and slot-expiry races; lost response both before and after task publication, with post-publication lookup using the bounded route rather than expired/consumed slots; document replacement; admitted-task recovery; settings fingerprint/commitment; headed typed/paste/picker/recent/Plan-again flows and hostile text.
- **Docs/review:** Update DESKTOP_UI, M1_BRIDGE, M1_SHELL, FEATURES, and INTERFACES. Close BR-G-47 only after headed evidence and parser review; land BR-G-32's checkpoint-6 exact-table revision and close BR-G-46's reopened command-map clause only after that revision passes.

### 7. Deliver bounded plan review and execution admission

Commit: `feat(web): add bounded plan review and selection`

- **Objective:** Complete the Slice 5 plan/review half.
- **Acceptance:** Implement the bridge-owned bounded plan projection, view,
  window, anchor/detail, selection, review-header, notice, overlay, and move-peer
  contracts. Project each immutable operation exactly once, preserve
  path-versus-member authority for same-target groups, and keep selection,
  rollups, counts, risk, and action scope independent of filters and windows.
  Review-time facts remain context; every committed nonempty current selection
  attaches and fresh-preflights after authority/confirmation checks. Publish a
  complete bounded plan and notice generation or no new artifact, preserving
  the prior complete plan where the mapped replacement policy requires it. Keep
  selection frozen while an attempt starts or runs; submission failure and a
  terminal unrun result return it to reviewing with one revision advance, while
  the first ran result freezes it permanently. A retry uses a fresh start command
  and commitment; replay of the old command returns only its original attempt.
  At this checkpoint's closure, an execution started from the plan remains
  usable through checkpoint 4's task rail, generic live state, pause/resume/
  cancel controls, bounded terminal summary, and an action-guiding generic
  "Execution did not start" state that returns an unrun selection to review.
  Rich item overlays and ledger evidence remain checkpoint 8 work. If that
  complete generic path is not available, keep both the `start_execution` row
  and rendered Execute gesture dormant until checkpoint 8 rather than expose a
  blind execution start.
- **Regression watch:** Rebuilding trees per window, operation-scaled responses, client-derived hierarchy/domain status, filter-dependent selection, synthetic ancestors, move annotations, stale selection/view revisions, double execution, failed or terminal-unrun admission leaving selection frozen, reopening without a revision advance, stale pre-commit mutation after reopening, replay creating a second authorization, and treating zero-byte ran work as unrun.
- **Tests:** Planner/workflow/interface neighborhood and the exact BR-G plan
  fixtures/boundaries in `M1_BRIDGE.md`; first-excess/no-partial publication;
  review-header rehydration and revision guards; capacity fact availability;
  reviewed-versus-fresh preflight behavior; typed notice merge, omission, and
  action exclusion; same-target grouping and exactly-once operation projection;
  folder/group selection and rollups; stale/replayed mutations; submission-
  failure and terminal-unrun revision transitions; edited-subset execution-
  refusal retry with a new commitment; permanent freeze at the first ran result;
  checkpoint-4 task-rail/live/control/terminal usability before checkpoint 8;
  search/filter/facet/window/dependency boundaries; move-peer
  positive and suppression cases; off-window follow; destructive confirmation;
  hostile DOM; latency/memory; and headed production witnesses.
- **Docs/review:** Update PLANNER, WORKFLOWS, M1_BRIDGE, M1_SHELL, and DESKTOP_UI. Close BR-G-15, BR-G-35, BR-G-37, plan BR-G-32, and the plan portion of BR-G-42 after adversarial selection/reopening review.

#### 7.A Shared sibling sorting and complete plan integration

- **Accepted contract:** Implement [Bridge sibling sorting](M1_BRIDGE.md#sibling-sorting-accepted-checkpoints-7-and-9),
  its exact `TreeSort`, raw row metadata, and update-view request/response
  shapes. New views start canonical path-key order. The user may choose
  filename, size, or mtime in either direction; reset returns to path-key order.
  Shared machinery and the full production plan path land here; checkpoint 9
  supplies the full inventory consumer. No immediate implementation is implied
  by this documentation addition.
- **Acceptance — complete ordering:** Sort entire immediate sibling sets in
  the complete server projection before visibility derivation and windowing.
  Preserve every NodeId, parent identity, subtree, same-target member, move
  peer, notice, and canonical lookup. Keep one immutable canonical tree and one
  current presentation ordering, with a shared comparator/permutation path.
  Its validator must reject duplicate/missing nodes and broken hierarchy rather
  than simply dropping the prior canonical-source-index monotonicity check.
  Follow the exact basename, raw integer, null-last, and canonical-tie rules;
  do not sort formatted labels, infer folder mtimes, or use copied-work bytes
  as file size. Publish coherent frame indexes and guarded anchors atomically.
- **Acceptance — authority:** Sorting is view state only. Assert unchanged
  effective selection, canonical user-deselection provenance, selection digest
  and revision, plan fingerprint, risk/counts/rollups, immutable operation and
  dependency order, execution commitment, result/lifecycle authority, and
  recursive action scope. A view change must not start work, write evidence,
  or reinterpret a selected folder as only its visible/sorted members.
- **Acceptance — state/bridge:** Required column/direction state is validated
  and echoed through existing update/open/window views, including exact replay,
  conflicts and rehydration. A changed sort-only intent advances view revision
  once; identical intent/reset-default is no-op; changes of state still count
  when row order coincides. Unrelated view gestures preserve sort. New views
  are canonical, existing views retain process-live state across navigation and
  reconstruction, and different tasks/views are independent. Sort/reset
  invalidates old numeric windows/anchors/focus indexes; apply the documented
  offset-zero policy or identity-based plan follow. Delayed replies cannot
  restore an older order or activate a different row through an old index.
- **Acceptance — future GUI independence:** The production command, exact
  validators, server state, raw size/mtime fields, all sort choices, and reset
  work at this checkpoint, even if the mtime column/reset affordance is not yet
  placed in the 48rem table. Later GUI layout must use these contracts without
  reopening tree building or the bridge. This is not permission to ship only
  an unreachable helper, test-only route, or page-local sorter.
- **Regression watch:** Per-page/global-flat sorting; mutable canonical
  indexes; lost same-path operations; reparented descendants; locale/natural
  sort; lexical numeric or float/date precision loss; null-first descending;
  unstable ties; selection/execution reordering; synthetic folder dates;
  search/collapse silently resetting sort; stale-anchor application; replay
  undoing a newer intent; and uncharged per-sort caches or staging copies.
- **Tests — independent ordering oracle:** Build real workflow trees with more
  than 1,024 siblings, nested and empty containers, same-target operation groups,
  move ghosts, duplicate/pathless informational leaves, and parents outside a
  returned window. Independently authored expected NodeId sequences must cover
  every permitted sort/direction and exact reset, shuffled construction input,
  ties, all-unavailable and mixed keys. Concatenate windows across 255/256 and
  later boundaries, including byte-limited short pages; assert no loss/duplicate,
  complete subtree contiguity, exact parent/child/sibling frames, counts, and
  item/node anchor results. Comparator-only or hand-built DTO tests do not close
  this gate; include production plan open/update/window/anchor commands.
- **Tests — discriminating keys:** Use mixed-case/Unicode and `file2`/`file10`
  names, hostile layout-control text, equal basenames on distinct operations,
  numbers 0/9/10/100/null, adjacent values around `2**53`, adjacent nanoseconds,
  and the signed-64 maximum. Choose names/canonical ties that make lexical or
  rounded numeric comparisons fail visibly. Cover file MOVE/NOOP/DELETE with
  zero copied bytes but nonzero file size; own-directory mtime versus absent
  stat, groups and synthetic ancestors; descendant changes must not invent or
  update a folder's mtime. Unknown/status/progress columns, missing/extra keys,
  wrong types/directions, and descending path-key refuse before traversal or
  state mutation in Python and required Node contracts.
- **Tests — authority/races/scale:** Compare complete canonical authority before
  and after every sort under selection, search/filter/collapse, live execution
  and terminal overlays. Race two sorts, sort versus other view edits, delayed
  windows/anchors, replacement/eviction and close; prove atomic publication,
  current-state replay, retained previous view on failure, and no stale browser
  success or failure before payload access. Instrument unchanged windows to
  prove no sorting/rebuild/native work, and changed views to prove one complete
  derivation, not a family of retained variants. Include sorting keys,
  permutations and old/new overlap in BR-G-42/45's existing predeclared fixture,
  memory, and changed-view budgets; do not select a new budget after observing.
- **Verification/review:** Run workflow/planner/interface consumers, existing
  structural and selection regressions, required Node and ordinary gates, plus
  installed production plan witnesses. Exercise latent choices through the real
  production command path even when no visible column control exists. Update
  BR-G-32's exact schemas/mirror without changing command counts, extend
  BR-G-34/35/36/37 and plan BR-G-42 evidence, and independently review ordering,
  immutable authority, and retention. Keep inventory closure pending until 9.A.

### 8. Deliver execution review and ledger-current evidence

Commit: `feat(web): add execution review and ledger evidence`

- **Objective:** Complete live execution, retained review, and trustworthy full-hash display.
- **Acceptance:** Attach execution atomically; render v5 progress, pause/resume/cancel, indexed follow, terminal axes, item/task recording issues, and retained file-list windows whose plan rows carry an exact `ExecutionOverlay` while leaving the separate post-copy overlay untouched. Render `filesystem="refused"` plus `disposition="unrun"` as the generic “Execution did not start” review state with reopened selection controls; do not expose preflight terminology or infer a cause from those axes alone. Add one batched transactional operation/run/inventory evidence query and bounded per-item detail including the item omission witness.
- **Regression watch:** Live-versus-terminal overlay disagreement, Gap loss, later task failure suppressing earlier evidence, unrecorded item borrowing another inventory hash, N+1 queries, canonical target collisions, latest-writer confusion, diagnostic amplification, and premature session release.
- **Tests:** Executor/database/workflow/interface neighborhood; all filesystem/
  recording combinations; exact overlay invariants; separate omission axes;
  committed item followed by later task/audit failure; scope match/change/
  invalidation/missing; full digest and no plan hash; Gap-plus-terminal
  reconciliation; generic refused-filesystem/unrun messaging and reopened-
  control revision;
  navigate away/back; the bridge-owned maximum result overlay;
  and post-copy replacement leaving execution byte-identical.
- **Docs/review:** Update EXECUTOR, RECORDER, DATABASE, WORKFLOWS, INTERFACES, M1_BRIDGE, and DESKTOP_UI. Close the execution portion of BR-G-36 and relevant BR-G-48 cases after executor and bridge reviews.

### 9. Deliver inventory projections and current evidence

Commit: `feat(web): add inventory projections and evidence`

- **Objective:** Complete the Slice 6 inventory surface.
- **Acceptance:** Implement the bridge-owned bounded inventory projection,
  location/completeness view, search/filter/collapse, windows, warnings, rollups,
  details, actions, revisions, and omission witnesses. Build the domain tree
  before informational warnings, keep warnings outside path/action scope, and
  publish a complete bounded generation or preserve the prior complete refresh
  generation. Keep ledger verification and ordinary-integrity overlays
  independent, show overflow rather than clamp it, label current hash/time
  evidence truthfully, and return typed admission/action refusals.
- **Regression watch:** Full-location reload per window, stale `view_id`/row ID, patch/rebuild races, acknowledgment count drift, hidden rows changing rollups, LRU eviction deleting task identity, unsafe SQLite integers, and treating a stale hash as current.
- **Tests:** Database/workflow/verifier/interface neighborhood and the exact
  BR-G inventory fixtures/boundaries in `M1_BRIDGE.md`; first-excess/no-partial
  publication and refresh preservation; cache pin/evict/refusal; location and
  revision shapes; concurrent projection/result replacement; search/filter/
  hiding counts; rollup overflow; paging; recursive scope and warning-detail
  refusal; diagnostic omission and stable warning identities; domain/action
  isolation; independent ledger/integrity overlays; hash provenance; scalar
  boundary/display; memory/latency; and hostile DOM witnesses.
- **Docs/review:** Update INVENTORY, DATABASE, M1_BRIDGE, M1_SHELL, and DESKTOP_UI. Close BR-G-22, BR-G-23, BR-G-38, inventory BR-G-32, inventory BR-G-42, and the inventory portion of BR-G-39 after projection-race review.

#### 9.A Full inventory sorting integration

- **Acceptance:** Use checkpoint 7's same sorter and exact Bridge contract in
  production inventory open/update/window flows. The complete slim projection
  supplies raw keys **before** any window/detail query; do not fetch metadata
  only for visible rows or perform per-subject I/O to sort. Project each real
  directory's own observed mtime when available; structural ancestors and
  unavailable metadata remain null, never descendant-derived. Keep recorded
  observation, provenance, and integrity overlays distinct. New views/reset use
  path-key order, with every explicit column/direction and raw mtime field fully
  supported even if its GUI control/column remains latent.
- **Acceptance — replacement:** Refresh/rebuild retains the live view's chosen
  sort and recomputes ordering against the newly published raw facts. Publish
  projection, derived sequence, windows, and indexes as one coherent captured
  authority; stale sort/build work cannot overwrite a newer projection or view
  intent. Preserve local acknowledgment patching, independent views, pins/LRU,
  complete-predecessor retention on refusal, and the offset-zero sort policy.
  No sorting operation writes the ledger or changes recursive refresh/integrity
  scope, candidate order, selection, rollups, warnings, or verification truth.
- **Regression watch:** Plan-only sorter left unused by inventory; different
  comparator/tie/null rules; size/mtime fetched after windowing; full-location
  reload per window/sort; wrong folder timestamps; accidental missing-row nulls;
  old ordering paired with new metadata; sort lost on patch/refresh/eviction;
  and view order leaking into recursive action or verifier candidate order.
- **Tests:** Reuse 7.A's independent ordering/numeric/Unicode/window oracle on
  real repository → workflow projection → production inventory bridge output,
  with present, missing/acknowledged, unsupported, warning, real directory, and
  structural ancestor rows. Cover every permitted column/direction and reset,
  including all-null folders and last-known missing-row metadata; reject
  descending path-key order. Cross sort
  with search/filter/collapse/hide-acknowledged; assert exact frame/offset data
  and unchanged counts/rollups, canonical descendant scope and admitted order.
  Race sort with acknowledge/restore, refresh/integrity completion, projection
  rebuild/eviction and task close; reject stale windows and preserve the last
  complete generation. Prove same-view sort survives reconstruction while a
  new independent view remains canonical. Instrument one complete structure
  query per build, bounded detail/window work, no sort-time native or N+1
  reads, and no resort on unchanged windows. Run the shared wide/tie/null scale
  variants, six-view retention and seventh-view eviction under BR-G-42/45.
- **Verification/review:** Run database/workflow/verifier/interface consumers,
  required Node and ordinary gates, and installed production inventory command
  witnesses including latent sort/reset/mtime support. Extend BR-G-22/23/34/38/39
  and inventory BR-G-32/42 without relaxing existing limits. Independently review
  projection replacement, raw-data provenance, and authority preservation.

### 10. Deliver integrity and deferred post-copy verification

Commit: `feat(web): add integrity and post-copy verification`

- **Objective:** Complete integrity controls and same-task manual verification without persistent operation-time hashes.
- **Acceptance:** Add baseline/verify/rebaseline actions and a distinct no-rescan post-copy workflow. `start_integrity` carries receipted `current_evidence_acknowledged:boolean`, required true exactly for rebaseline and false for baseline/verify; every other combination is invalid before claim, scope resolution, ledger, or native work. Automatic linked verification remains the original compound session using transient evidence. Ordinary integrity publishes only the inventory row's `integrity_outcome` overlay; manual exact verification publishes only the plan row's separate `post_copy` overlay. These overlays never substitute for ledger-derived state or rewrite execution truth; successful conditional integrity recording still updates ledger evidence. Each manual exact attempt attaches a new dispatcher/history session identity and conditionally reads/writes against the original execution `runs.run_token`; it neither opens a new ledger scope nor reuses an earlier history identity. Under the owner claim, start first performs the atomic handoff classification and returns blocked/all-already-verified without native probing; only a ready subset triggers fresh target admission, followed by one final atomic classification that either freezes the still-ready rows or returns the new assessment. A failed, canceled, or partial attempt may be retried for the newly ready remainder, atomically replacing only the task's prior post-copy result/overlay after the old/new overlap is reserved. A race returns exact conflict, the five typed `ready`/`already_verified`/`eligible_incomplete`/`unrecorded`/`superseded` counts plus reason, or typed candidate refusal without inventing a task/view/count.
- **Handoff policy:** Every applicable selected byte-producing operation must have a filesystem-successful terminal outcome, but unrelated non-byte-operation failure does not falsify a copied file's evidence and aggregate recording may be degraded. The five counts partition applicable selected byte-producing work; failed, canceled, or unreached work increments `eligible_incomplete`. Same-scope copy evidence is `ready`; same-scope readback/verify evidence with non-null `last_verified_at` is `already-verified` and increments `already_verified`; any incomplete, unrecorded, or superseded applicable item blocks exact admission. `post-settlement-state-diverged` also blocks because execution applicability is no longer trustworthy, regardless of the five counts; final-flush, finish, or close degradation alone remains admissible when every eligible row is committed and current. Positive `ready` with optional already-verified siblings starts only the ready subset; a nonempty all-already-verified set reports that without starting work; absent divergence, all five counts zero blocks as `no-applicable-items`. Otherwise offer ordinary “verify current state,” which may refresh and establish a new scope.
- **Regression watch:** Reusing ordinary `run_integrity()` for exact handoff—it refreshes and destroys scope continuity; classification/admission races; mixing exact and current candidates; canonical target duplicates; stale mount choice; verifier recording degradation; result-ID misalignment; mutation of the original execution result.
- **Tests:** Exact true-rebaseline/false-baseline/false-verify acknowledgement starts and receipt replay; false rebaseline, true baseline/verify, missing, and non-Boolean rejection before claim/scope/ledger/native work; ready, mixed ready/already-verified, all-already-verified, superseded by scan/run/rebaseline, missing/invalidation/unrecorded/offline, failed execution, final-flush-degraded but fully committed execution, last-moment conditional-recording race, pause/resume/cancel followed by a same-scope remaining-subset retry and old/new post-copy reservation, whole-object live replacement over overlapping/disjoint candidate indexes with prior settled membership retained until terminal, projection invalidation-before-outcome, and current-state fallback.
- **Docs/review:** Update VERIFIER, WORKFLOWS, INVENTORY, DATABASE, M1_BRIDGE, and DESKTOP_UI. Close the remaining BR-G-39 and BR-G-48 cases after a dedicated handoff/race review.

#### 10.A Rebaseline missing evidence without comparison semantics

- **Accepted protocol:** Implement the [three-operation policy table](VERIFIER.md#standalone-operation-policy-checkpoint-10-target).
  A fresh rebaseline admits eligible selected files both with and without prior
  evidence. Hash current content and conditionally create/replace evidence;
  unchanged content is still `baselined`, never a verified match. Baseline's
  missing-only admission and verify's compare-or-first-baseline policy remain
  unchanged. Compare-and-accept for matching rebaseline content is outside M1.
- **Acceptance:** Preserve explicit selected scope and the existing required
  rebaseline acknowledgement even when every selected row has null evidence.
  Keep the mode `REBASELINE`; do not adapt it per row. Successful replacement
  clears verification freshness and conditional invalidation/reappearance in
  the same transaction. Prior evidence, including null, participates in the
  conditional write. Keep all fresh-subject/read-stability, scope, custody,
  recording-axis, and exact-candidate continuation guarantees. Change only
  fresh admission where current engine/recorder paths already satisfy this
  contract; no schema, wire-version, or automatic post-copy-policy redesign.
- **Regression watch:** Dropping null-evidence rows; skipping a read/write on
  equal content; reporting `verified` or retaining `last_verified_at` after
  rebaseline; weakened acknowledgement for null evidence; overwriting evidence
  created after selection; mode filters dropping pending resumed rows; adding
  newcomers on resume; and treating receipt replay as content comparison.
- **Tests:** Start from mixed selections containing no evidence, baseline-only,
  repeatedly verified, changed-stat, and stable-stat/different-digest subjects.
  Assert admitted ids, actual read/hash counts, exact outcomes, recorder mode,
  old/new evidence, freshness, and phase headline for **all three operations**.
  Include all-null and mixed explicit rebaseline through workflow, service/CLI,
  and production bridge; engine-only success is insufficient. Retain repeated
  baseline's zero verifier-work control and null-baseline verify's incomplete
  headline. Prove equal-content rebaseline really reads/replaces and clears
  prior verification freshness, while no evidence appears before a stable read.
  Use real-ledger null-to-present races, conditional stale/conflict/error and
  rollback fixtures, invalidation/reappearance atomicity, and independent
  recording degradation. Exercise mixed-state pause/resume/cancel with exact
  ordered candidate retention, completed-item nonrepetition, and byte/status
  high-water preservation. Extend acknowledgement/malformed-intent/receipt
  replay cases to all-null and mixed scopes. Retain manual exact post-copy
  supersession by rebaseline and automatic linked-verification controls.
- **Verification/review:** Run verifier, workflows, database, dispatcher and
  interfaces consumers plus the ordinary suite with required Node; include
  installed production integrity controls at checkpoint closure. Independently
  review the policy matrix and conditional-recording races. Update current
  versus accepted wording in VERIFIER, WORKFLOWS, INVENTORY, COMMANDLINE,
  FEATURES, and Bridge only when this checkpoint activates it.

### 11. Close early Slice 7 lifecycle and scale

Closure commit: `feat(web): close task lifecycle and retention budgets`

- **Objective:** Prove cleanup, shutdown, and retained-task containment across the completed surfaces.
- **Acceptance:** Calibrate and verify without post-selecting or silently
  changing the checkpoint-4-frozen analytical constants; prove the aggregate
  task guarantee and count wall owned by `DEFENSE.md` §1.3, plus
  reservation/shrink/refusal, live closing, terminal presentation/release
  retry, explicit close, repeated create/release/close, complete response/native/
  browser transients, and concurrent shutdown. Any policy defect lands
  separately, revises the enforced constant before a new run, and resets the
  evidence run. The named commit lands only after any such fix commits and is
  the final evidence/status closure, not the sole allowed commit for checkpoint
  11.
- **Regression watch:** Silent eviction, count-only enforcement, uncharged receipts/string pools/full results/native copies, diagnostic bypass, browser callback copies, blocked close handlers, cleanup before terminal record, task rail reconstructed from dispatcher sessions, and authority surviving declared release points.
- **Tests:** BR-G-41 lifecycle tests; BR-G-45 complete artifact-root and
  aggregate-retention instrumentation, including the accepted maximum handler
  and terminal-reconciler reservations; maximum-task guarantee plus refusal;
  repeated cycles; live/paused/terminal close; delayed terminal at handler
  saturation; issue/close barriers racing readers, durable mutations,
  replacement pins, and `next_events` long-polls; shutdown during starts/drains/
  close; current-source event/custody; plan/inventory scale gates and installed
  headed witnesses.
- **Docs/review:** Update DEFENSE measurement authority, M1_BRIDGE, M1_SHELL, TESTS, INTERFACES, and DESKTOP_UI with predeclared fixtures/budgets and evidence. Close BR-G-41 and BR-G-45 only after independent artifact-graph and shutdown reviews.

### 12. Overall adversarial and documentation sweep

Commit: `docs(gui): close stage 6 surface verification`

- **Objective:** Reconcile the reslice as one system and land any discovered fixes separately before final documentation.
- **Acceptance:** No v3/v4 runtime machinery, dormant bridge rows, operation-time hash persistence, path ingress outside the shared admission workflow, unbounded task/result response, stale documentation, or undeclared task artifact remains.
- **Regression review:** Executor settlement/order; per-item versus task recording truth; stale bridge actions and lost responses; exact request/result keys; origin/readiness/handler-capacity rules; path-parser abuse; unsafe scalars; DOM text/layout safety; projection races; manual-handoff supersession; memory-budget bypass; shutdown and cleanup authority.
- **Tests:** Settlement oracle three identical runs; ordinary `pytest -q`; headed interfaces with cleared default addopts; complete suite with `-o "addopts="`; `lint-imports`; `git diff --check`; installed-wheel v5 bridge and product-DOM gates; every `test_br_g_*` collected with no unsupported skip/xfail; final BR-G-42/45 evidence.
- **Docs/review:** Reconcile ARCHITECTURE, DEFENSE, FEATURES, README, all owning documents, M1_BRIDGE/M1_SHELL gate status, and TESTS. Extend one CHANGELOG task across checkpoints and replace HANDOFF at closure. Use a separate reviewer for the final security, executor, bridge, and requirement-drift audit.

## Explicit deferrals

- History page, history bridge pagination, BR-G-40, history BR-G-42, and SH-G-9.
- Global settings mutation page; Setup only reads defaults and freezes per-task overrides.
- Drag-and-drop and file-scoped planning.
- Geometry, column layout, durable tree-expansion, and other nonappearance UI-state consumers. Deferred layout must not postpone checkpoint-7/9 sorting commands, raw size/mtime facts, or reset support.
- Status/progress sorting, global flat sorting, and durable sort preferences are excluded from M1.
- Compare-and-accept behavior for genuine matches during rebaseline is deferred beyond M1; checkpoint 10 always hashes and replaces/creates evidence.
- Human-gesture provenance against compromised trusted JavaScript.
- Desktop task survival across process closure/restart.
- GUI Break 2 cohesion work, release packaging, BR-G-43/44, and SH-G-15.

## Checkpoint 0 audit issue and resolution record

This is the historical review record for checkpoint 0's first ratification and
reconciliation round, not current delivery status or a separate contract
authority. States below describe that ratification: “Accepted target” meant the
named implementation checkpoint had not yet activated the documented
resolution. Current progress is recorded at the top of this checklist.

### Runtime and cross-contract findings

| Issue or incompatibility | Resolution | State |
| --- | --- | --- |
| Execution preflight could observe selection or review facts that were not the exact committed review authority. | Commit the current nonempty revisioned selection, bind its digest and provenance, rederive it before execution admission, and publish any fresh refusal as execution-attempt truth without rewriting the reviewed plan. | Accepted target, checkpoints 7–8. |
| Plan immutability, selection after an unrun attempt, and selection after consumed execution authority had been collapsed into one permanent freeze. | Keep the plan immutable; return selection to `reviewing` at a new revision after submission failure or a terminal unrun result; freeze selection permanently when the first attempt reports `disposition=ran`. | Accepted target, checkpoints 7–8. |
| An unrun task could need a genuinely new plan, but it had no recent ledger run and its reviewed display path was unsafe to reuse after drive-letter reassignment. | Add identity-resolving `activate_task_pair`; explicit **Plan again** activates two fresh slots and starts a new task with the old frozen setup, default selection, and no copied authorization. | Accepted target, checkpoint 6. |
| User deselection, dependency fallout, and safety exclusion could collapse into one omitted-operation meaning. | Retain canonical `user_deselected` provenance separately, dependency-close only that set, and derive typed excluded outcomes from the reviewed plan plus provenance. | Existing direction retained; desktop admission lands at checkpoint 7. |
| Filesystem success and recording success were conflated, so a recorder failure could misstate durable mutation truth. | Keep filesystem, integrity, recording, and audit axes independent; add item-local recording degradation and ordered task-wide recording issues without rewriting committed filesystem outcomes. | Accepted target, checkpoints 1–3 and 8. |
| Item-local recorder failure and task-wide open/flush/finish/close failure lacked a stable attribution boundary. | Pin the four-way settlement matrix in the oracle, then add sparse typed item attribution and centrally reduced task issues before changing the event wire. | Accepted target; checkpoint 1 oracle work is in progress. |
| Operation-time copy evidence was being treated as if it could become a durable task artifact. | Keep copy attestations transient inside the same live execution continuation; durable evidence comes only from committed ledger facts and never enters retained tasks or JavaScript. | Accepted target, checkpoint 2. |
| Python’s additive v3/v4 compatibility decoder, exact live-v4 JavaScript validator, and canonical history projection accepted different shapes. | Make the current asymmetry explicit only until a coordinated exact event cut; then use one exact event schema and reset the database pair rather than retain a legacy decoder. | Accepted target, checkpoint 3. |
| Ledger, history, event, and evidence epochs could be upgraded independently and leave a mixed readable-looking pair. | Advance them as one coordinated reset boundary; reject old, mixed, markerless, incomplete, or orphan-sidecar pairs before commands with archive/delete guidance and no automatic migration. | Accepted target, checkpoint 3. |
| Byte counts and filesystem timestamps could cross Python, SQLite, JSON, and JavaScript with incompatible integer precision or coercion. | Use one nonnegative signed-64 arithmetic domain, checked accumulation, and canonical decimal bridge representation; keep opaque native file indexes as non-arithmetic text. | Accepted target; exact walls and the reachable-versus-assertion classification live only in Bridge/Defense. |
| Native identity had three incompatible widths: Python `st_ino` could carry 128 bits, executor/verifier handle probes narrowed to 64, and SQLite stored a signed integer. | Use the complete Windows `FILE_ID_128` through one core-owned adapter and canonical `FileIndex128` text in codecs and the reset ledger; retain a stat fast path only behind executable NTFS/ReFS equivalence evidence. | Accepted target, checkpoint 3; exact domain lives in Bridge/Defense. |
| Reachable timestamp and aggregate-logical-byte failures had arithmetic walls but no exact scanner or pre-publication outcome. | Add the path-local scalar scanner warning and the plan/domain `logical-bytes` review-limit witness; reuse existing typed unavailable/unreadable outcomes at later native probes. | Accepted target, checkpoint 3; exact outcomes live in Bridge. |
| Reliable terminal transport could retain or send an unbounded full result collection. | Transport an item-free bounded terminal summary, update compact overlays before queueing, and retain the full terminal result only under dispatcher custody until reconciliation/release. | Accepted target, checkpoints 3–4. |
| The existing one-session desktop model could not retain a reviewed plan and later results while sessions came and went. | Introduce process-live tasks with one current session and separately named bounded plan, execution, inventory, integrity, and post-copy result slots. | Accepted target, checkpoint 4. |
| Concurrent control/start/release/close commands had no single effect owner, so identical retries and competing commands could both progress. | Use one task-operation owner claim with exact-intent replay/join, typed busy/conflict observations, and owner-only publication or compensation. | Accepted target, checkpoint 4. |
| A review candidate could be staged, rejected, or throw after staging and leave partial overlays, indexes, charges, or stale browser state. | Use an exact staged-result matrix, precharged rejection latch, atomic generation publication, complete compensation to prior/null truth, and one sticky task publication issue with fixed recovery guidance. | Accepted target, checkpoint 4. |
| Reads, replacement, projection eviction, and task close could race on mutable task or generation state. | Add checked task publication epochs, ordinary/cleanup leases, immutable generation pins, write-intent drain, and unpinned-only eviction with revision rechecks after outside work. | Accepted target, checkpoints 4 and 11. |
| Terminal callbacks and close could lose reconciliation capacity or release a successor session. | Pre-reserve a terminal reconciler/callback lease, key release to exact task/session identity, and retain bounded release/close tombstones for retry authority. | Accepted target, checkpoint 4. |
| Shutdown or busy close could strand long polls, observers, pins, or cleanup work while reporting the task closed. | Seal admission, wake/cancel long polls, cancel and reconcile the exact session, drain ordinary then cleanup leases, and only then remove the task and materialize its close tombstone. | Accepted target, checkpoints 4 and 11. |
| Task artifacts, projections, receipts, slots, handlers, responses, and tombstones had incomplete or mutually inconsistent containment rules. | Enforce permanent/transient reservations before surface work, bounded task/projection/receipt/slot stores, non-evicting earned retry authority, and analytically charged response/handler copies. | Accepted target, checkpoints 4 and 11; exact walls live in Bridge/Defense. |
| Picker-only slots, typed paths, remembered locations, and real work starts risked using different path grammars or cached root evidence. | Route every path source through one workflow-owned literal local-directory admission service, issue purpose-bound expiring slots, and freshly re-admit roots when work actually starts. | Accepted target, checkpoints 5–6. |
| “Recent folders” could be inferred from typing/picking or persisted as cosmetic UI state, overstating prior successful use. | Derive recents only from eligible ledger activity, keep reachability separate from history, revalidate on activation, and never place recents in `ui-state.json`. | Accepted target, checkpoints 5–6. |
| Mutable defaults or Setup edits could change an already reviewed plan, and multi-pair creation lacked partial-failure semantics. | Freeze the complete task-local option/filter snapshot into planning and commitment; create multiple pairs serially with independent success/refusal and no rollback of admitted tasks. | Accepted target, checkpoint 6. |
| Manual post-copy verification could rescan, reuse stale hashes, overwrite execution truth, or attach evidence from another run. | Classify one ledger-current same-run snapshot by run token and operation identity, freshly admit the target, start only a ready subset, and publish into a separate replaceable post-copy result slot. | Accepted target, checkpoint 10. |
| Large plan/inventory views could build partial artifacts, let the browser own complete lists, or erase the last complete view on a refused replacement. | Build complete bounded server-owned candidates, publish atomically, page/window only immutable projections, preserve a complete predecessor on replacement refusal, and return a typed no-partial initial refusal. | Accepted target, checkpoints 4, 7, and 9. |
| Viewport rows, display paths, warnings, and coincidental hashes could be promoted into selection, action, or evidence authority. | Resolve opaque ids and recursive scopes server-side, keep warnings non-actionable, keep paths display-only, and label evidence provenance/currentness explicitly. | Accepted target, checkpoints 7–10. |

### Ratification and publication defects found during review

| Defect | Resolution applied during checkpoint 0 |
| --- | --- |
| Signed-64, terminal-summary, task-claim, epoch, and retention decisions were copied through many component documents, creating parallel truths. | Exact protocol shapes now live in `M1_BRIDGE.md`, exact defense walls in `DEFENSE.md`, and component documents carry only local consequences or pointers. |
| The first enlarged Bridge section was disconnected from the DR-BR records and tried to win conflicts through a blanket precedence sentence. | The Bridge map now assigns every shared register area to explicit DR-BR owners and acts as the sole supersession inventory; unmapped decisions remain untouched and targets remain inactive until their checkpoints. |
| `TESTS.md` duplicated checkpoint, module, command, and case catalogs despite the executable department manifest. | It was nearly reverted and now contains only generic accepted-target routing; `tests/_departments.py`, H2 checkpoint clauses, and owning BR-G gates remain the relevant authorities. |
| `FEATURES.md` carried transport schemas, algorithms, limits, and lifecycle implementation detail instead of product behavior. | It now states user-visible active/unrealized behavior and points technical mechanics to Bridge, Defense, or the owning component document. |
| The exact `mutate_selection` row returned only a revision while local DR prose also promised a selection digest. | The response promise was removed; the digest remains internal commitment authority. |
| Publication-fault prose referred to a fixed “message above” that condensation had deleted. | The exact action-guiding close-and-retry message was restored at the publication contract. |
| Register ownership omitted the history/data-epoch owner, over-assigned history pagination to unrelated result/command registers, and missed newly required BR-G traceability. | Map ownership was narrowed and enumerated; epoch ownership and DR-to-gate rows were reconciled, including recording, retention, location, and command gates. |
| The Setup checkpoint required exact slot-claim guidance, but Bridge retained only the tagged busy result. | Exact wait/reselect renderer guidance was restored beside the `slot-claimed` result. |
| Local DR prose repeated stale workflow/history version numbers and created current-versus-target ambiguity. | Local epoch numbers were replaced with shared-register pointers; remaining v4 statements are explicitly current-source or historical, while the target cut remains accepted but inactive. |
| DR-BR-28 still listed future recents as typed cosmetic UI state, contradicting ledger-derived recents. | Recents were removed from the cosmetic-section list and are explicitly barred from UI state. |
| `HISTORY.md` and `TESTS.md` still required a future mixed-v3/v4 browser-history validator and referenced Core’s removed decoder-debt section. | Current history-v5 compatibility guards are now labelled temporary; checkpoint 3 replaces them with the exact reset target and no legacy browser decoder. |
| Retry and retention clauses allowed replacement of an unrun result, while DR-BR-03 permanently froze the committed selection that any retry needed to change. | Submission failure and terminal `disposition=unrun` now reopen selection at a new revision; the first `disposition=ran` is the authority-consumption boundary. |
| A fresh plan from a refused task had no safe way to reconstruct reviewed roots after drive-letter reuse. | `activate_task_pair` resolves both reviewed volume identities afresh and publishes two slots only when both accept; **Plan again** then starts a new task with the frozen setup. |
| Command arithmetic omitted retained bootstrap/cosmetic rows, BR-G-32 still froze the current nine-row table, and BR-G-46 had no explicit revision boundary. | BR-G-32's exact ordered test advances at every command-activating checkpoint; BR-G-46's map clause is additionally reopened at checkpoints 4 and 6, producing 12 then 18 unique commands and finally 32 target plus four retained rows, 36 total. |

### Pre-checkpoint 1 resolution

The follow-up adversarial pass rechecked the retained findings against their
owning DR-BRs, exact register rows, checkpoint dependencies, and BR-G gates. It
found no second closed retry loop or authority-consumption error. It did expose
two coupled scalar-contract defects—native file-identity narrowing and missing
typed outcomes for reachable timestamp/aggregate failures—which are resolved in
the accepted checkpoint-3 target. The recording/evidence axes retain one-way
settlement authority; task publication, compensation, leases, receipts, and
close keep one effect owner; location and Setup flows never promote display
text or cached probes; and projection windows remain detached from selection,
filesystem, and evidence authority. Four preparatory items are resolved:

- **Command arithmetic:** confirmed from the exact register rather than prose:
  checkpoint row counts are 6/8/8/1/6/3 for checkpoints 4/6/7/8/9/10, 32
  target rows total. The four retained bootstrap/cosmetic rows produce 12 after
  checkpoint 4, 18 after checkpoint 6, and 36 finally. BR-G-32's executable
  exact table advances with every activating checkpoint; BR-G-46 remains
  reopened only for the checkpoint-4 and checkpoint-6 revisions.
- **Scalar reachability:** `DEFENSE.md` §1.3 now distinguishes reachable native
  file-index/timestamp and aggregate-logical-byte cases from impossible single-
  volume capacity and post-admission counter overflow. Reachable boundaries
  use full-width opaque file identity, the path-local scanner warning, and the
  plan/domain logical-byte refusal; impossible cases are assertions, not
  ordinary user-facing failure states.
- **Checkpoint 3:** keep it before checkpoint 4 because the task/result
  foundation consumes v5 terminal, recording, and epoch shapes. Its three
  ordered commits now provide dormant consumer-preparation, producer/reset,
  and legacy-removal stops instead of one indivisible landing.
- **Bug ledger:** record only the newly distinct authorization, location-
  reactivation, file-identity-width, and cross-consumer protocol causal classes.
  Existing split-authority, publication-compensation, retention, and lifecycle
  entries already cover the other reusable classes and are not duplicated.
