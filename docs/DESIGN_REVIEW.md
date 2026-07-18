# NamiSync Design Review

Status: all findings reviewed and resolved 2026-07-18 — the 23 original
items, DR-24 from the resolution session's sanity pass, DR-25 through DR-31
from the module-draft propagation review, and DR-32 through DR-37 from the
follow-up quadruple-check. Each item below
carries a **Resolution** note and `FEATURES.md`/`ARCHITECTURE.md` have been
updated to match. The per-module drafts have not yet been re-synced to these
decisions. This file is now the decision log; the authoritative sources
override it where they have since evolved further.

## Severity

- **M0 blocker**: resolve before the walking skeleton mutates user files.
- **Milestone blocker**: resolve before the named later feature is implemented.
- **Documentation defect**: the intended behavior is inferable, but the source
  contract should be corrected before implementation depends on it.

## M0 Blockers

### DR-01 — Mandatory review conflicts with unattended execution

`FEATURES.md` says every sync has a dry-run review, and the current product
direction says human review remains mandatory between plan generation and
committing execution. `ARCHITECTURE.md` nevertheless defines
`run_unattended_sync()` and unattended ingest as a single session with no gate.

Required decision: either remove no-gate execution or define a durable,
explicit preauthorization whose scope, plan fingerprint, expiry, and material
change policy count as the review commitment. A generic CLI flag must not waive
the safety invariant.

**Resolution (2026-07-18):** Commit-to-execute. The user's explicit commitment
of a reviewed plan *is* the durable preauthorization: scope = the
`ExecutionSet` (plan **and** selection, both bound — the commitment carries a
selection digest alongside the plan fingerprint), expiry =
none (uncommitted plans stay plans forever; a committed plan whose world
drifted parks as refused for re-review, never silently re-planned). Committed
plans run immediately when volumes are free, otherwise queue and execute
sequentially in commit order. `run_unattended_sync` is removed; scripted and
queued execution replay commitments, never mint them. The same contract covers
ingest and verification.

### DR-02 — Pause cannot both block and release custody

`Checkpoint.__call__()` says it blocks while paused. The session model says a
pause drains to a boundary, releases all volume locks, and always re-preflights
on resume. A blocked workflow stack cannot safely release custody and later
resume through a fresh preflight without making the checkpoint domain-aware.

Recommended direction: checkpoint raises a typed `PauseRequested` at a safe
boundary; the generic session runner persists/retains an opaque continuation
request, exits the workflow, releases locks, and resume starts a new guarded
continuation. Define which module serializes remaining execution state.

**Resolution (2026-07-18):** As recommended, with one simplification: no
module serializes anything new. `Checkpoint` never blocks; it raises
`PauseRequested` or `Canceled`, both unwinding to the session runner, which
maps them to `PAUSED`/`CANCELED` and releases custody. The continuation *is*
the `ExecutionSet` — its per-op status records what completed — so a paused
execution is exactly a queued job, and resume is the ordinary queue-wakeup
path (observe → preflight → execute remaining). Abandoned mid-copy temps are
reclaimed by ordinary orphaned-temp recovery.

### DR-03 — Exactly-one-terminal ownership is misplaced

The executor is assigned the single-`Terminal` guarantee, but scan, plan,
verify, baseline, import, maintenance, and dummy sessions also require exactly
one terminal event. If both executor and dispatcher wrappers emit terminals,
duplicates are likely.

Recommended direction: the generic session runner owns terminal emission in
one `finally`; modules return typed results and never emit `Terminal` directly.

**Resolution (2026-07-18):** As recommended. A generic `run_session()` in
`core/session.py` (ARCHITECTURE §2.2a) is the only place a `Terminal` is
emitted or pause/cancel resolves; the dispatcher wraps it with lock custody.
Every session kind — scan, plan, execute, verify, import, maintenance, dummy —
inherits exactly-one-terminal from this one function.

### DR-04 — Planner lacks prior correspondence evidence

The pure signature accepts source scan, target scan, options, and scope. That is
insufficient for source-identity rename detection: the planner must know which
source identity corresponded to which target path in the prior accepted state.
The PoC lost move evidence when no-op correspondence was not persisted.

Required change: add an immutable `MappingSnapshot`/correspondence input from a
repository. It must include paired no-ops, retained missing rows, normalized
keys, and ambiguity/hardlink evidence.

**Resolution (2026-07-18):** As required. `plan()` gains a `correspondence:
MappingSnapshot` parameter with exactly that content, read from repositories
by the workflow and passed in immutable, keeping the planner pure and the
layering law intact.

### DR-05 — Pure planner has no capacity input

`Plan.target_free_space` and capacity planning are planner outputs, but the
planner is pure and its signature supplies neither free space nor a capacity
snapshot. Direct `disk_usage()` inside the PoC planner was already identified
as a robustness and duplicated-formula bug.

Required change: pass an immutable `PlanningCapacity` observation into the
planner, or remove observed free space from `Plan` and compute it in a separate
review observation. The required-byte formula remains a pure shared function.

**Resolution (2026-07-18):** The second option. `target_free_space` is removed
from `Plan`; `required_bytes` stays as a pure formula output. Free space is
observed reality, read by `observe()` at review and preflight time and judged
by the one shared capacity formula — never baked into an immutable plan where
it would immediately go stale.

### DR-06 — Filter-drift comparison has no current value

The plan carries `filter_snapshot`, but `preflight(xset, world)` has no current
filter/settings snapshot to compare against. `ObservedWorld` contains only
filesystem observations.

Required change: include semantic configuration in `ExecutionSet` or a
separate immutable `ExecutionEnvironment`; do not read mutable settings inside
pure preflight.

**Resolution (2026-07-18):** `ObservedWorld` gains `current_filters`;
`observe()` snapshots the semantic configuration in effect alongside its
filesystem observations (reading settings is IO too). `preflight()` compares
`plan.filter_snapshot` against `world.current_filters` and stays pure with no
new parameters.

### DR-07 — Attestation identity is ambiguous after copy

`Attestation` has one `file_identity`. A copy-stream digest attests source
bytes, while the durable ledger row describes the newly published target,
whose filesystem identity differs. Persisting the source identity on the
target would corrupt move and drift evidence.

Required change: distinguish content evidence from subject stat evidence, or
construct the final attestation from the digest plus a post-publish target
stat. The source stat remains separate drift evidence.

**Resolution (2026-07-18):** Both halves. `Attestation` splits into
`ContentEvidence` (digest, size, provenance, observed_at) plus a `subject`
`FileStat` — for a copy, the published target re-statted after publish, never
the source's stat. The source's post-read stat lives separately as the drift
guard's evidence.

### DR-08 — Trash-on-update is not transactionally atomic

The proposed update moves the current target to trash before publishing its
replacement. A crash between those operations leaves the live target missing.
The same problem exists inside composite move-update. Deferring the ledger write
prevents a lie but does not preserve availability or per-operation atomicity.

Required decision: define a recoverable update state machine, preferably using
a fully prepared temp plus a Windows replacement primitive with a same-volume
backup where possible. Specify exact startup/rerun reconciliation for every
crash point and never automatically delete the only good version.

**Resolution (2026-07-18):** Displace-then-replace. The live target is
preserved into `.synctrash` by an atomic same-volume hardlink (copy fallback
where the filesystem has no hardlinks), and only then does `os.replace`
publish the prepared temp over the live path — no crash point leaves the
target absent, and the displaced version always survives via the trash link.
Composite move-update publishes the new content at the new path before
trashing the old, so a crash leaves both versions present, never neither.
Fault-injection acceptance criteria cover every interleaving.

### DR-09 — Reliable, non-blocking, bounded delivery is underspecified

Reliable events may never be dropped, and a slow subscriber may never stall
the producer. A bounded in-memory queue cannot guarantee both. M0's
keep-everything replay buffer is also unbounded.

Required decision: choose a limit policy—durable spill, subscriber failure with
an explicit gap, bounded session admission, or controlled backpressure. History
cannot be described as guaranteed audit if its reliable stream may disappear
silently.

**Resolution (2026-07-18):** Split by subscriber class, everything bounded.
The history observer gets guaranteed delivery via bounded producer
backpressure at checkpoint boundaries — never a drop (a synchronous
recorder-style write path was rejected as a third emission path). Any other
reliable subscriber that overruns its bounded queue is ejected with an
explicit `Gap` event, never silently thinned. The M0 replay buffer becomes
bounded per session; late subscribers get current state plus a bounded tail
and detect loss from `seq`.

### DR-10 — Volume label is evidence, not stable identity

`VolumeId` includes label, while known-volume recognition is described as
serial-driven and automatic. Labels can change; cloned serials can collide.

Required change: separate stable key material from mutable corroborating
evidence. Define matching rules for label changes, filesystem reformats,
serial clones, and simultaneous ambiguous mounts.

**Resolution (2026-07-18):** As required. `VolumeId` reduces to stable key
material (serial + fs_type); label moves to a `VolumeEvidence` corroboration
type. Rules: relabel matches anyway and is silently noted; same serial with a
new filesystem is a reformat demanding explicit rebind; two mounted volumes
with one key remain the already-settled explicit-user-choice path.

### DR-11 — Unsupported scan entries have no typed representation

Placeholders must be recorded as `unsupported` without being opened, but
`FileRecord` has no support/entry-state field and warnings alone cannot carry a
reviewable candidate through inventory and planning.

Required change: add a typed support state or a separate unsupported-entry
record. Planner behavior must be explicit: blocked/reviewable, never silently
ignored and never executable.

**Resolution (2026-07-18):** A separate `UnsupportedRecord` collection on
`ScanResult` (not a flag on `FileRecord`, which every consumer could forget to
check). Unsupported entries flow through inventory and plan review as blocked,
never-executable items.

### DR-12 — Parent-directory durability wording conflicts

Architecture calls parent-directory fsync a bone; Features calls it best
effort. Windows directory flushing can fail or be unsupported depending on the
handle/filesystem.

Required decision: define the Windows durability guarantee and how an
unsupported/failed directory flush affects operation outcome and user-visible
warnings. Do not claim power-loss atomicity beyond what was actually flushed.

**Resolution (2026-07-18):** Best-effort is the contract, honestly stated: the
flush is always attempted; a refusal downgrades to a per-operation warning and
never fails the operation; power-loss durability is claimed only for what was
actually flushed. Both docs now use the same wording.

### DR-13 — M0 cross-process volume custody is unclear

Features require deterministic cross-process physical-volume locks. The M0
dispatcher explicitly defers queue-owner persistence but does not clearly say
whether volume locks are real cross-process locks or merely in-process
scheduling. A safe CLI cannot ship with only in-process mutation exclusion.

Required decision: keep durable queue ownership in M2, but require real
cross-process volume locks before the M0 executor can mutate user data.

**Resolution (2026-07-18):** As required. M0 gains real cross-process volume
locks — a named OS mutex or lock file keyed by volume serial, with
abandoned-holder recovery and a process-kill acceptance test — because two CLI
processes exist on day one. The durable queue-owner lock stays M2.

### DR-21 — `ObservedWorld.stats` cannot distinguish roots

The architecture types it as `Mapping[str, FileStat | None]`. Source and target
normally have the same relative path, so a string key is ambiguous and can make
preflight compare an operation against the wrong side.

Required change: key observations by a typed `(root role/root id, rel_path_key)`
subject or operation evidence id. Never concatenate strings with an ad hoc
separator.

**Resolution (2026-07-18):** As required. `ObservedWorld.stats` is keyed by a
typed `Subject(root, rel_path_key)` named tuple.

### DR-22 — Metadata preservation has no evidence shape

Features promise preservation of standard attributes, creation time, ADS where
supported, and optional ACL/owner policy. `FileRecord` and `PlanOperation` as
described carry only size/mtime/identity/link count, so review, preflight, and
executor cannot agree on what metadata was observed or intended.

Required change: define a typed metadata snapshot and preservation policy in the
plan. Decide how unsupported ADS, stream copy failure, creation time, readonly
publish ordering, and ACL opt-in affect outcomes.

**Resolution (2026-07-18):** `FileRecord` gains a typed `MetadataSnapshot`
(attribute bits, creation time where knowable, ADS presence where knowable);
`Plan` gains a snapshotted `PreservationPolicy` (ADS, creation time, ACL as
explicit opt-in). Readonly is applied only after publish; a failed stream copy
on a stream-capable volume is a per-operation warning, never silent.

### DR-24 — Directory operations were only partially specified

Added during the resolution session (not part of the original external
review). Creation (full mkdir chains), cleanup of emptied directories, and
guarded deletion were specified and PoC-hardened, but directory rename/move
had no stated contract — only an implicit per-file decomposition — `DirRecord`
had no defined shape, and directory metadata preservation was absent,
including the ordering trap that child operations churn parent directory
times. The PoC's executor originally handled regular-file operations only and
grew each directory behavior as a bug fix.

**Resolution (2026-07-18):** Decompose + grouped review. A folder rename
decomposes into per-file identity moves, the full mkdir chain, and emptied-dir
cleanup — never a directory-level operation in M0 (the decomposition must
exist regardless, since a folder whose children also changed cannot collapse
into one rename) — and plan review groups the decomposition under the folder
node. `DirRecord` is defined now (metadata plus optional identity) so a future
first-class directory-move op is additive flesh. Created directories receive
source directory metadata; directory timestamps are applied only after the
directory's children settle.

## M1 And Persistence Blockers

### DR-14 — Integrity outcomes do not fit the generic event type

`ItemOutcome.outcome` is the five-value generic `Outcome`, while verifier
consumers need verified, baselined, mismatched, modified, missing, unsupported,
canceled, and error. Encoding these as free-form `kind` or `reason` strings
would recreate the PoC's inconsistent presentation paths.

Required change: add a typed integrity result inside event detail or define a
typed event body dedicated to integrity while retaining generic delivery class.

**Resolution (2026-07-18):** A dedicated typed `IntegrityOutcome` event body
(RELIABLE, first produced in M1) carrying the eight-value `IntegrityResult`
vocabulary, declared in core alongside the other bodies.

### DR-15 — Recorder failure and terminal status are not fully defined

The recorder must fail loudly, yet a bookkeeping failure must not rewrite a
successful filesystem result as though the copy failed. It is unclear whether
the session terminal is `COMPLETED`, `FAILED`, or a successful result with a
durability warning when the ledger is behind.

Required change: define separate filesystem outcome, recording outcome, and
session status aggregation. The UI/history must tell the truth about both.

**Resolution (2026-07-18):** Two-axis result. The terminal `SessionState`
derives from filesystem outcomes alone; `OperationResult` gains a separate
`RecordingStatus` (ok / degraded) that UI, CLI exit detail, and history all
surface prominently. A behind ledger converges on the next scan; neither axis
ever rewrites the other.

### DR-16 — History is optional telemetry and required audit at once

History failures never roll back real work and telemetry may be missed
silently, but every explicit run is described as history-worthy and history is
the audit trail. These are different guarantees.

Required decision: classify history as best-effort activity telemetry or a
required audit record. In either case, observer failure must be surfaced and
must not falsify the filesystem/ledger result.

**Resolution (2026-07-18):** History is audit — guaranteed *delivery* (see
DR-09's backpressure), best-effort *durability* with loud failure. A history
write failure surfaces on the session result but never blocks, fails, or
falsifies filesystem work; a crash loses at most the bounded in-flight
buffer — the same never-wrong-only-behind posture as the ledger. Invariant 4
reworded accordingly.

### DR-17 — Session-store retention semantics are missing

`SessionStore.drop()` exists, while the session table is also the source of
truth for task/status views. The contract does not say when terminal sessions
are dropped, retained, or handed off to history.

Required change: define terminal retention, queue discard, compaction, and the
relationship between session records, GUI tasks, and audit history.

**Resolution (2026-07-18):** Terminal session records are retained until
explicitly closed (the task-card dismissal), then dropped; a queued session
discarded before running writes its history entry first (per FEATURES → Queue
Discard Audit). The session table is the live view; history is the durable
trail.

## Later-Milestone Blockers

### DR-18 — Ingest idempotency and policy snapshots are incomplete

Stateless resume promises to recognize collision-suffixed prior ingests using
target provenance, but the planner input and plan do not define the provenance
index, template/version fingerprint, collision assignment snapshot, or generic
annotation key namespace. Re-running after a template change could duplicate
content or choose a different suffix.

Required change before ingest: define an immutable enrichment/policy snapshot,
stable assignment algorithm, origin annotation schema, and provenance lookup
input. Execution must never recompute a destination.

**Resolution (2026-07-18):** Remains a later-milestone blocker as stated, with
one piece pulled forward into the schema freeze: annotation keys are
dot-namespaced by owning feature (`ingest.origin.*`) from row zero, so ingest
provenance keys can never collide with early ad-hoc labels. The rest of the
snapshot/assignment/lookup contract is deferred to ingest design.

### DR-19 — CLI entry-point priorities conflict

Architecture puts `sync` and `history` in M0 and desktop in M3. Features lists
no `sync` command and says all no-subcommand entry points launch the desktop.
An M0 build therefore has no defined default behavior, and the main M0 command
is absent from the feature list.

Required change: add the sync command contract, specify M0 no-subcommand
behavior, and defer GUI-default behavior until a desktop implementation exists.

**Resolution (2026-07-18):** As required. FEATURES gains a Sync Command
contract (plan → terminal review → commit → execute; a queue-release flag for
scripted use, no flag that plans and executes unreviewed). No-subcommand
prints usage and exits nonzero until the desktop exists; the GUI-default
bullet moved to unrealized work.

### DR-20 — Metadata extractor priority text contradicts itself

Architecture says every protocol ships in M0, then says `MetadataExtractor`
ships with ingest and no extractor exists in M0. It also references a nonexistent
“§7 gap technique” when explaining the deferred `INTERRUPTED` producer.

Required change: say every M0-used protocol gets a degenerate M0 implementation;
latent protocols may be declared without one. Correct or add the missing gap
section reference.

**Resolution (2026-07-18):** As required, verbatim: every protocol *used* in
M0 ships with its degenerate implementation; a latent protocol is declared
shape-only until its first consumer arrives. The phantom "§7 gap technique"
reference now points at that same shape-only rule (§2.7).

### DR-23 — Features still assigns behavior to core

The `PROJECT ARCHITECTURE` feature bullet says core owns sync behavior. The newer
architecture and `AGENTS.md` say core owns contracts while isolated modules own
scanner/planner/executor/verifier behavior.

Required change: update the feature bullet to the newer layering so future work
does not reintroduce the old monolithic core.

**Resolution (2026-07-18):** Done — the FEATURES bullet now reads: core owns
shared contracts and the session machine; isolated modules own sync behavior.

## Propagation-Review Blockers

Seven contract defects found while propagating the resolved decisions into the
per-module drafts (see the propagation session's `HANDOFF.md` for the original
blocker statements).

### DR-25 — Executor self-preflight violated the import law

§4.5 had the executor calling `observe` + `preflight` as its first act while §1
forbids modules from meeting outside workflows.

**Resolution (2026-07-18):** The workflow owns observe → preflight → execute on
every start and every resume, and is the sole pre-mutation preflight. The
executor keeps its own **per-operation** defense: immediately before each
mutation it re-validates that operation's direct preconditions (expected
target state, source evidence at touch, type/emptiness) — preflight is one
stage of TOCTOU prevention, never the last, because the world can change
between preflight and touch. No executor-to-preflight import exists.

### DR-26 — Non-hardlink update fallback was under-specified

No `supports_hardlinks` capability, no backup-copy capacity accounting, no
crash-safety discipline for the backup copy itself.

**Resolution (2026-07-18):** `CapabilityProfile.supports_hardlinks` from the
authoritative `FILE_SUPPORTS_HARD_LINKS` volume flag (no probing, no fs-name
whitelist). The shared capacity formula becomes profile-aware: updates on a
no-hardlink target count the displaced version's backup-copy bytes,
max-concurrency-aware. The backup copy follows the same temp-flush-publish
discipline inside the trash run directory, so a partial backup only ever
exists under a temp name; trash-restore planning ignores exact-shape temp
names, and orphaned trash temps age out with the trash run directory (temp
recovery still never walks `.synctrash`).

### DR-27 — ADS/ACL preservation was unimplementable from `has_ads`

A presence bit cannot drive stream copying or drift detection, no ACL snapshot
existed, and requested-stream copy failure was wrongly specified as a warning.

**Resolution (2026-07-18):** `MetadataSnapshot.streams` is an ADS manifest
(name + size), enumerated only when the mapping's preservation policy requests
ADS — policy-driven scan depth. The executor copies manifest streams and
re-enumerates the source post-copy as part of the drift guard. Streams are
user data: a requested stream that fails to copy on a capable target FAILS the
operation; an ADS-incapable target surfaces at plan time as a reviewable
degradation, before commitment. ACL preservation stays opt-in with honest
semantics: the security descriptor is copied at execution time
(preserve-current, not preserve-scanned), and failure when opted in fails the
operation.

**Superseded in part (2026-07-18):** the ADS half is deferred wholesale by
DR-32; the ACL half stands.

### DR-28 — Non-empty directories had no metadata input

`DirRecord` covered only empty directories while the executor promised
metadata for every created directory — which were also created implicitly, as
unreviewed side effects of file copies.

**Resolution (2026-07-18):** The scanner records every walked directory (it
visits them anyway). The planner emits an explicit mkdir-with-metadata
operation for every directory the plan creates — full chain, file operations
depending on their parent's mkdir — and the executor never creates a directory
implicitly. Kills the PoC's partial-chain bug class by construction and
provides the all-directory records the future directory-move op needs.

### DR-29 — History degradation had no result field; stalled writers were contradictory

`OperationResult` carried only ledger status, and guaranteed delivery plus
bounded memory plus never-blocking cannot survive a writer that stalls
forever.

**Resolution (2026-07-18):** `OperationResult` gains an `audit:
RecordingStatus` axis beside `recording`; invariant 12 becomes axis-separated
truth (filesystem / ledger / audit — no axis rewrites another). Backpressure
waits are capped by a generous injected timeout: a writer that stalls past it
or fails degrades the session's audit axis loudly and blocking stops.
Delivery is guaranteed *unless the result says otherwise* — never silently
absent.

### DR-30 — Pause/cancel result transport and non-execution resume were undefined

Bare control-flow exceptions carry no partial results; scan/verify/baseline/
import had no resume semantics; the runner's "exception still surfaces" implied
a possible second terminal.

**Resolution (2026-07-18):** Exceptions stay payload-free: the session runner
assembles cancel/pause/failure terminal results from the session's own emitted
RELIABLE `ItemOutcome` stream (emit-as-you-go is already law, making unwind
lossless). Pause is a per-kind capability declared at workflow registration
and enforced by the transition table: only kinds with a continuation state
accept it — execution (M0) and the verifier's item-list sessions
(verify/baseline, M1, via the same item-status continuation pattern as
`ExecutionSet`) — while scan/plan and import sessions refuse pause cleanly and
remain cancelable. The runner consumes exceptions: typed detail rides the
`Terminal` and the log, nothing re-raises past it, so a second terminal is
unconstructible. The recorder needs no pause behavior — it is call-driven, and
the pause-drain forced flush commits completed evidence before locks release.

### DR-31 — Queued-discard audit lacked a typed distinction

CANCELED with zero operations was indistinguishable from discarded-before-start
without string parsing.

**Resolution (2026-07-18):** `OperationResult` gains a typed `Disposition`
{`RAN`, `UNRUN`}: a discarded queue entry is CANCELED + UNRUN, a refusal is
naturally UNRUN, and nothing is ever inferred from a zero-length operation
list or a parsed string. No new terminal state, no new transition edges.

## Follow-Up Review Findings

Six findings from the quadruple-check of the resolved authoritative docs.

### DR-32 — Policy-driven ADS scanning was structurally broken; ADS deferred

DR-27's scan-time stream manifests required the scanner to know a mapping's
preservation policy, but a role-free scan cannot infer one and a single
location can participate in mappings with different policies. `StreamInfo`
was also referenced without a defined shape, name syntax, or validation rules.

**Resolution (2026-07-18):** ADS preservation is deferred wholesale to a
latent seam. The `streams` field and `StreamInfo` are removed; `supports_ads`
and `preserve_ads` remain declared but unimplemented and not user-exposed;
FEATURES states the streams-don't-travel limitation loudly. The sketched
future path is executor-time enumeration — the executor already holds the
file, needing no scanner policy input — with the DR-27 failure semantics
(requested-stream loss FAILS the op) preserved as the contract for whenever
the feature lands. Supersedes DR-27's ADS half; the ACL half stands.

**Amended (2026-07-18):** the executor-time path is promoted from sketch to
settled contract (still deferred flesh). Clarifications from the follow-up
discussion: a policy-aware scan would *not* have broken the database's
file-set logic (missing-marking and diffing depend on which files are seen,
not metadata depth) — what it breaks is the one-canonical-observation-per-
location property inventory relies on, plus the mapping-agnostic
`ChangeSource` seam. Executor-time enumeration avoids that tax entirely, and
composes with planning because NTFS timestamps are per-file: an ADS write
bumps the file's mtime, so ordinary metadata diffing already schedules the
update that re-copies streams (test-verified assumption before the feature
ships). Residuals: incapable-target warnings are mapping-level at plan time;
stream bytes are uncounted by capacity; stream content is copied but not
attested (ledger hashes cover the main data stream only); and mtime is an
evadable signal — a writer that suppresses or restores it escapes stream
refresh, so the feature claims no independent ADS-only convergence. The
latent `supports_ads`/`preserve_ads` fields are kept: they follow the
design's declared-but-unreached pattern (like `INTERRUPTED` and `DEFERRED`),
cost one volume-flag read and one unexposed default, and create no
unreachable states for consumers to handle.

### DR-33 — Shared review/execution observation contradicted fresh preflight

§4.4 still said review and execution start could share an `ObservedWorld`
"when close enough in time," contradicting the mandatory fresh observation of
§4.9 and FEATURES.

**Resolution (2026-07-18):** The reuse claim is deleted. Every judging session
observes fresh — review, execution start, resume, and queue wakeup each
observe their own world; closeness in time is not evidence of unchanged state.

### DR-34 — Per-operation re-stat is not atomic against external swaps

A path-based stat followed by a destructive call still permits an external
process to swap the path between them; volume locks coordinate only NamiSync.

**Resolution (2026-07-18):** Guards gain teeth from operation-matched
conditional primitives where the OS provides them: non-replacing rename where
an absent destination is expected, `CREATE_NEW` temp creation, and
`RemoveDirectory`'s inherent atomic emptiness refusal. The sole
non-conditional mutation — update's displace-then-replace pair — carries
explicit residual-risk wording: external writers mutating a target root
mid-execution are outside the safety contract, the window is microseconds,
and the bounded worst case (an externally-swapped file replaced without trash
preservation) never corrupts NamiSync's evidence, since attestation subjects
are always NamiSync's own published files. Fault tests must exercise a swap
*between* guard and destructive call.

**Corrected (2026-07-18):** two claims here were overstated against
Microsoft's own documentation. First, the window is not time-bounded — usually
tiny, but the process can be descheduled between syscalls — so wording and
fault tests bound the residual by *data consequence*, never elapsed time.
Second, `ReplaceFileW` *is* a supported single-call replacement with an
optional backup, recommended over deprecated TxF; it is deliberately not used
because it merges the replaced file's attributes, ACLs, and named streams into
the replacement and documents partial-state failure cases —
hardlink/copy-backup-then-replace is a chosen tradeoff, not the platform's
only primitive. Additionally clarified: conditional primitives guarantee only
their own condition (never source-path identity), so the external-writer
boundary applies to all mutations, with consequence classes stated per
operation family — trash-routed operations at worst preserve the wrong item
recoverably, moves at worst misplace without destroying, and only
update-replace and internal mirror deletes can destroy an external writer's
file, never NamiSync's own displaced version or evidence. Directory renames
inherit only the non-destructive classes, since DR-24's decomposition means
no directory-level mutation exists.

### DR-35 — Audit status and Terminal finalization were circular

History consumed `Terminal` to finalize its row, but `Terminal.result.audit`
had to already report whether that final write succeeded.

**Resolution (2026-07-18):** Bounded two-phase finalization. Before the runner
releases the one immutable `Terminal`, it drains the audit subscriber and
history attempts and acknowledges its final write within the same generous
timeout; success stamps `audit=OK`, timeout or failure stamps `audit=DEGRADED`
and releases blocking. History finalizes from the drain step, never parses the
`Terminal` it acknowledged, and no second terminal exists. The `recording`
axis has no such loop — the recorder is call-driven and its terminal flush
completes before result assembly.

### DR-36 — Runner aggregation lacked an unwind-emission rule; pause mislabeled

Unreached items have emitted nothing when a checkpoint raises mid-run, so
runner-assembled results were incomplete; §2.2a also referred to a pause
Terminal, which does not exist.

**Resolution (2026-07-18):** Lossless unwind is a stated module obligation: an
item-processing module's own `finally` emits a `CANCELED` outcome for the
in-flight item and every unreached selected item before `Canceled` leaves the
module, and emits nothing for them on `PauseRequested` — they remain pending
for resume. The obligation is named in the executor and verifier bones. §2.2a
now says terminal results are assembled for cancel and failure only; pause
emits no terminal.

### DR-37 — Stale pre-resolution wording survived in assertions

`DeliveryClass.RELIABLE`, an events invariant, a dispatcher acceptance
criterion, and FEATURES' Event Delivery Classes still said reliable events are
"never dropped" unconditionally; a database acceptance criterion still said
"two-axis truth."

**Resolution (2026-07-18):** All reworded to the settled semantics: guaranteed
to the audit subscriber under the timeout guard, never *silently* dropped for
anyone (ejection is announced by `Gap`), and "axis-separated truth."

## Required Review Order

1. DR-01 through DR-03: session safety and review boundary.
2. DR-04 through DR-08 plus DR-21/DR-22: plan/execution evidence and atomicity.
3. DR-09 through DR-13: custody, event durability, and platform guarantees.
4. DR-14 through DR-17 before M1 persistence/integrity work.
5. DR-18 through DR-20 and DR-23 before ingest, durable queues, or desktop release.

## PoC Bug Traceability

Every substantive entry in `PoC_import/BUGS.md` was routed to an owning draft
and a regression-oriented acceptance criterion. This table is the review index;
the module files contain the detailed criteria.

| PoC section | Owning drafts | Hardened themes |
| --- | --- | --- |
| Scanner | `SCANNER.md`, `CORE.md` | exact ignores, walk errors, cancellation, junction/reparse cycles, history DB artifacts |
| Planner | `PLANNER.md`, `PREFLIGHT.md` | full mkdir chains, same-plan directory cleanup, metadata-noop limitation, one capacity formula, observed capacity errors |
| Executor | `PREFLIGHT.md`, `EXECUTOR.md`, `RECORDER.md`, `DISPATCHER.md` | continue after independent failure, stale-plan/final guards, composite move-update, move support, chunk cancel, directory durability, empty dirs, scoped preflight, exact temp recovery, byte accounting, incomplete scans, trash volume safety, reclaimable temp capacity |
| Verifier | `VERIFIER.md`, `INVENTORY.md`, `RECORDER.md` | modified vs mismatch, explicit rebaseline, canonical selected paths, reappearance clearing, cache-honest evidence |
| Database | `DATABASE.md`, `RECORDER.md`, `INVENTORY.md`, `HISTORY.md`, `WORKFLOWS.md` | pipeline wiring, filesystem/recording truth split, actual timestamps, persisted identity, conditional writes, bounded transactions, no preview writes, all-path audit, no-op validation, canonical time, role-free inventory, composite location constraints, tombstones, serialized writer, provenance, unexpected-error audit, batched missing sweep, move collisions, writable retention, baseline/current stat separation, detail reads, skipped-move state, O(n) indexing, Windows path keys, guard preservation, paired-noop evidence, batched IO, shared host/time |
| CLI | `COMMANDLINE.md`, `INTERFACES.md`, `WORKFLOWS.md` | real argv entry points, paired ledger/history overrides, activity-aware output and exit status |
| GUI | `DESKTOP_UI.md`, `INTERFACES.md`, `DISPATCHER.md`, `WORKFLOWS.md` | scoped gating, worker/thread lifetime and affinity, layered status, native-control styling, throttled progress, cancelable import, inventory-before-integrity, typed row updates, location-only actions, partial/refused truth, toolkit ownership, context targeting, execution-to-verify handoff, stable layout, immediate metrics, safe shutdown, activity-aware history, actionable invalid input, shared actions, orthogonal plan/inventory state, scoped refresh/results, nonmodal tests |
