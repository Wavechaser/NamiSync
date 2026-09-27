# M1 Delivery Register

This is the sole active M1 delivery register. Exact contracts and release criteria
remain with [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md),
[BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md),
[FEATURES](FEATURES.md), [TESTS](TESTS.md) and their component owners.
[M1-8's archived register](obsolete/M1_8_DELIVERY.md) retains its finite
R0–R3 and A1–A6/B1–B6 gates. The [archived post-M1-8 study](obsolete/POST_M1_8_ABLATION.md)
retains investigation, rejected proposals and superseded execution recipes;
the decisions still governing delivery are below. Historical observations
certify their recorded build and dependencies only.

## Root admission optimization plan — 2026-09-27

### Main objectives

- Remove repeated root derivation, mount discovery and duplicate admission from
  executor, preflight and verifier while preserving reviewed effects, honest
  verification and recovery behavior.
- Share native evidence primitives in core; let each module own its access
  boundaries, invocation resources and failure policy. Replace repeated
  configured-root ancestry walks with fresh root-object continuity where the
  explicitly proposed contract below applies.
- Establish the verification machinery first: a settlement oracle that freezes
  settlement policy rather than probe multiplicity, plus admission-safety and
  preflight/verifier differential witnesses that pass on the unchanged product.
- Finish RO-0a/RO-0b, RO-1a/RO-1b, RO-2, RO-3a/RO-3b, RO-4 and RO-5 before M1-9
  by default and **before M1-10 activation without exception**. M1-9 can move
  ahead only by an explicit user scheduling decision; that does not waive this
  batch or its M1-10 dependency.

### Scope and decisions

This is the user-requested plan/register, prepared with the `plan-work` skill
against `6a93b038` on `milestone1-adelbert`. It proposes future contracts, not
current behavior or implementation authorization. All nine rows start pending.
The user selected **root continuity with an explicit contract change**, rather
than preserving every configured-root ancestor check at every access.
[PERFORMANCE](PERFORMANCE.md#executor-assessment--2026-09-27) owns the measured
executor/verifier findings and source-derived preflight count. The investigation
commit is `6a93b038`; local raw receipts remain under
`build/executor-assessment-20260927/`. Core/executor measurements initially used
`0e4595e4`; verifier follow-up used `6de6d1c0`. Do not relabel them as candidate
performance or a fresh full-suite baseline.

**Finite scope.** Core `pathing.py`, `root_authority.py`, `file_identity.py` and
the directly affected executor/verifier protocols; executor `runtime.py` and
`native.py`; preflight observation in `modules/preflight.py`; verifier
`engine.py`/`native.py`; composition and invocation lifetimes in
`workflows/runtime.py`, `sync.py`, `inventory.py` and core context factories.
Direct compatibility consumers include scanner, inventory/location resolution,
rigs, custom filesystem/readers and decorators, their tests and helpers.
Verification machinery in scope: `tools/executor_settlement_audit.py`, its
committed baseline and semantic pin, `tests/test_tools_executor_settlement_audit.py`,
EXECUTOR's Settlement Stability Gate text, and new test/tool harnesses for root
swaps and preflight/verifier differentials. Only those seams may change to adopt
the new contract. Shared pathing additionally
requires planner, database, bridge/service and serialization regression coverage.
The regression map and checkpoint sections close this population by mechanism;
a newly discovered owner/effect model requires adjudication, not silent expansion.

**Excluded.** Scanner traversal optimization; planning/UI/bridge redesign;
database schema, stored identity or wire changes; cross-run authorization caches;
global root sessions; generic permission-token frameworks; general handle-relative
traversal; new network/filesystem support; pipeline scheduling, flush batching,
overlapped publication, worker removal, settlement reducer redesign, pause/cancel
merging and buffer-pool work. The small progress-initialization condensation and
verifier buffer-reuse leads remain deferred. M1-9/10 behavior, missing-row
acknowledgement, DOC-2 history rewriting and prior AB deferrals stay separate.

**Sequencing revision.** Verification machinery lands first against the
unchanged product: RO-0a (settlement oracle v2) and RO-0b (admission and
differential witnesses), independent of each other. Current-contract work follows:
RO-1a, then RO-2, RO-3a and RO-4 (each depends only on RO-1a; serialize
shared-file edits), then RO-3b once RO-3a and RO-0a have landed. Record a
measured mechanical-only intermediate revision before RO-1b introduces continuity
across the three consumers. RO-1b, then RO-5, still must finish before M1-10.
Continuity bootstrap, mounted-anchor cases and its AGENTS/DEFENSE contract edits
do not block the mechanical commits. RO-1 is superseded by RO-1a and RO-1b, and
RO-3 by RO-3a (cheaper calls, unchanged public call pattern) and RO-3b (fewer
public calls per step). RO-2/3/4 retain their owners but exclude continuity
adoption until RO-1b.

The RO-3 split follows the oracle boundary. `TracingFileSystem` wraps only the
outer `ExecutorFileSystem` object, so `NativeFileSystem`'s internal self-calls
are invisible to it; RO-1a and RO-3a therefore leave the oracle's byte layer
unchanged. RO-3b removes public-boundary `revalidate_root`/`resolve`/`stat`/
`stat_path` calls from runtime steps, which the current oracle freezes exactly.

The proposed design decisions are:

Decisions 2–5 describe RO-1b only. Immutable fact reuse, fewer native calls and
within-step consolidation are current-contract work in RO-1a/2/3a/3b/4; they do not
wait for continuity-specific witnesses or policy documentation.

1. **Facts are reusable; observations are not permission.** Construct reviewed
   `RootAuthority` facts once per invocation, including prepared lexical spelling
   and chain derivation where useful. Core remains standard-library-only and
   exposes typed stateless observation/comparison primitives. A module-owned
   invocation scope owns live bindings and handles only in RO-1b; earlier rows
   reuse immutable facts while performing current-contract admission. There is no TTL, global
   freshness cache or public `already_admitted=True` escape hatch.
2. **Full admission establishes the binding.** Before using the optimized path,
   validate original spelling and reviewed mount/volume, no-follow the configured
   root chain, and corroborate the opened root with that admission's actual root
   observation. Keep the original root handle open for the invocation. Compare
   fresh pathname evidence with its raw 64-bit volume serial and 128-bit file ID,
   plus ordinary-directory/non-placeholder/non-reparse evidence. Prefer one lstat
   per access on the witnessed CPython/backend mapping: `st_dev`, `st_ino`,
   attributes and reparse tag supply the comparison without another explicit
   handle/ctypes query. Otherwise use a fresh no-follow handle probe; this is a
   backend implementation choice, not a new product capability detector.
   Re-statting only the retained handle cannot detect a replaced pathname.
   Acquire no write authority and permit normal read/write/delete sharing;
   identity retention must not introduce a root rename/delete sharing lock.
   The retained handle exists to prevent recycling of the bound root's file ID
   during the invocation. It also keeps the volume in use: volume lock and safe
   removal can be blocked throughout long verifies and idle retry waits. Sharing
   delete access does not remove this effect. Close on pause and every exit;
   account for device-in-use guidance in RO-1b rather than promising safe removal
   while active. Never release/reacquire the baseline silently during a retry.
3. **Explicit ancestry change.** After that full admission, a fresh probe reaching
   the same ordinary root object may pass even if an ancestor has become another
   alias/reparse route to that object. A different root, missing root, unsafe root
   leaf or changed volume refuses before the next access/effect. This replaces
   repeated configured-root ancestry validation, not descendant checks. Preplaced
   traps at full admission and traps below the bound root remain refused. Update
   ARCHITECTURE, DEFENSE, AGENTS and component docs with this precise distinction
   when implemented; do not claim all ancestors remain ordinary or all races are
   prevented. Existing quiescent-root assumptions and EW dispositions remain.
4. **Use existing capability evidence.** Continuity eligibility is the selected
   reviewed `CapabilityProfile.stable_file_identity`, a local non-UNC root, and
   a logical root distinct from its admitted/reviewed volume anchor. Equal-anchor
   roots (including mounted-folder roots), remote roots and false identity profiles
   retain full admission. Locality must exclude mapped remote drives using existing
   native locality evidence. Do not add a competing runtime identity-capability
   detector or a second filesystem-name allowlist: scanner already derives the
   profile from filesystem type. The profile selects eligibility; it does not prove
   raw stat/handle equivalence or authorize a particular root object. Witness that
   mapping in backend tests and corroborate each actual initial binding.
   Preflight/executor use the reviewed plan profiles; post-copy uses its target
   profile. Standalone verification must carry the admitted refresh's `scan.profile`
   through `bind_verifier_context` and its context factory (currently it carries
   RootAuthority only),
   not infer a new capability in the reader. No durable profile or wire change.
   Custom/fake adapters explicitly supply the scoped or full-admission contract.
   Missing profile uses conservative full admission; an eligible mode's missing,
   malformed, access/query or mismatched evidence refuses rather than downgrading.
   A plan or context without reviewed volume identity or a reviewed anchor is
   ineligible and keeps its current admission (chain-only when no expected
   volume exists); continuity never binds to a volume first observed at
   invocation start. In production this arises from offline scan results, whose
   `UNKNOWN` profile is already ineligible; settlement-oracle and many test plans
   also carry no volume facts, so they cannot witness the continuity mode.
5. **Invocation lifetime, not task lifetime.** Bind independently for each
   `observe()`, `execute()` and verifier invocation. In-invocation retries keep
   the baseline and re-probe; pause/return/cancel/error close every owned handle.
   Resume/wakeup does fresh location resolution/preflight as today and establishes
   a new full binding before touching retained paths. Do not serialize handles,
   bindings or fresh-observation claims into plans, fingerprints, continuation,
   `ObservedWorld`, ledger/history or bridge values. Retained-temp/published
   identity guards remain necessary across this reset.
   A same-object ancestor alias accepted during an invocation can be rejected by
   the next invocation's full ancestry admission. This is deliberate: continuity
   is not a promise to preserve an altered namespace through pause/resume.
6. **One admission per actual access/effect step.** A native operation may consume
   the immediately preceding admission and its stat evidence within that step.
   Derivation and queries comprising the same admission can share it when no
   external callback, wait, content read or effect intervenes. This consolidation
   is allowed under the current contract and belongs in RO-2/3b/4, not behind RO-1b. A recorder call, control callback, stream, retry wait, return/resume
   or filesystem effect ends the step. Subsequent work re-probes. Source and
   target checks remain distinct. The COPY path is not a universal six-probe
   budget; cleanup, backup, metadata and other operation kinds have their own
   boundaries. Prefer a combined operation or private scoped value with explicit
   ownership, never a reusable success flag.
7. **Preserve external identity.** Existing `VolumeId` and persisted
   `FileIdentity.volume_serial` retain their current representation. Raw root
   identity is separate: the current handle adapter truncates the volume serial
   to 32 bits and must not be used as a full-width root binding. File `st_dev`
   can corroborate its own volume on witnessed backends; compare against reviewed
   expectations and refuse mismatch rather than stamping a file with the path's
   volume. Do not generalize the F: NTFS observation to every filesystem.
   Initial admission still matches the plan's existing volume identity: this
   proposal does not detect a pre-invocation remap with a colliding low-32 serial
   merely by adding a subsequently pinned full-width identity. Existing clone
   ambiguity policy remains; stronger review-time identity is outside this batch.
8. **Settlement oracle v2 freezes policy, not probe multiplicity.** User decision
   (2026-09-28): this deliberate refactor migrates the oracle to format v2 and
   overrides EXECUTOR's rule that only a reviewed settlement-policy fix may
   replace the baseline. The override covers exactly RO-0a's format migration;
   EXECUTOR's rule keeps protecting every non-deliberate change, and after RO-0a
   the v2 baseline stays frozen for the rest of this batch. The v1 capture freezes
   every public `ExecutorFileSystem` call in order (1,155 `revalidate_root`, 527
   `resolve`, 352 `stat` and 305 `stat_path` entries at `85ceecea`), their
   `fs:` timeline tokens, first-seen label ordinals and occurrence-counting fault
   predicates. That treats today's probe count as policy and blocks RO-3b/RO-1b
   by construction. v2 keeps byte-identical: effect calls with arguments/results
   and errors, erroring and fault-injected probe calls, recorder/control/backend/
   pacing/emit tokens, outcomes, recording, tree and continuation projections.
   Successful non-mutating probe calls leave the pinned layer and remain only in
   non-gate diagnostic output. Labels are canonicalized after projection by first
   appearance in the retained layer, so dropping a probe renumbers nothing.
   Probe classification is an explicit reviewed list over every public method;
   an unclassified or effect-performing method (including one that creates
   directories) stays in the byte layer. A new guard-before-effect invariant
   replaces what the probe trace loosely stood in for (RO-0a). Effect-call
   signatures and results must stay byte-identical through RO-3b and RO-1b; a
   design needing to change them stops for review rather than re-pinning. The
   oracle remains a settlement-policy authority: it is not extended to witness
   admission safety, which RO-0b's production-shaped sweep owns.

The Windows sources for the proposed native mechanism are
[FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info),
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex).
Identity compares open objects; it is not a cryptographic clone detector or an
atomic binding of a later pathname mutation. Retained handles address identity
lifetime within the invocation. Constant user-space probe count does not promise
constant kernel lookup latency at increasing depth.

[FILE_STORAGE_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_storage_info)
defines the opened file's logical sector size used by RO-4; its equivalence and
alignment witnesses replace path lookup, not unbuffered-read guarantees.
[FSCTL_LOCK_VOLUME](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_lock_volume)
documents refusal while files remain open. RO-1b accounts for that retained-handle
lifetime effect rather than claiming delete sharing permits active volume removal.

**Evidence still required.** RO-1a validates single-observation/native conversion
under current behavior; RO-1b separately closes bootstrap, identity lifetime,
profile propagation and supported-backend witnesses. This is an implementation
matrix, not a new runtime capability authority. RO-4 witnesses handle-derived
sector geometry. No claim that the suggested 25-microsecond lstat or historical
30.4-microsecond handle probe is a universal bound. Widening continuity beyond the
declared profile/locality/anchor predicate, retaining handles through pause,
changing path grammar or stored identity, or relaxing descendant checks needs
user review. Routine helper choices and mechanical reductions need no new policy
decision or AGENTS/DEFENSE wording change.

### Investigation and regression map

| Mechanism / owner and direct consumers | Failure to prevent | Checkpoint witness |
| --- | --- | --- |
| `lexical_absolute_path` currently converts to extended spelling and back; RootAuthority construction repeats this work. Core pathing is used beyond the three modules. | Normalize away an invalid component; alter case/Unicode keys; accept device/ADS/escape spelling; resolve links while doing lexical work; leak native prefixes. | RO-1a: `test_core_scanplan.py`, core root/identity tests, ordinary suite. Preserve validation before normalization, UTF-16 limits, relative-input behavior and existing type/error semantics. |
| `admit_root` currently performs chain-anchor lookup then volume lookup with a second anchor check. Scanner and workflow location/overlap checks consume the same primitives. | Replace two independent observations with a tautological equality; map missing/access/anchor/volume errors to the wrong consumer result. | RO-1a: migrate `test_second_anchor_change_precedes_volume_identity_acceptance` and `test_missing_or_invalid_second_anchor_is_unavailable` to the single-anchor admission mechanism without deleting the underlying refusal consequences, with changed-root/volume and wrong-runtime-root controls; scanner full/scoped bracket regressions. |
| `ApplicationRuntime` retains `_observation_fs` and `_executor_fs` across tasks. Core must not own freshness policy. | Store one task's binding on a shared adapter; cross-contaminate concurrent tasks or resume; leak handles on exception. | RO-1b: overlapping invocations with different roots on the same backend, partial initialization, control exits and fresh resume; no binding on singleton filesystem state. |
| Preflight `observe` deduplicates subjects and already reuses authorities; stat/capacity/temp/trash each admit. Judgment is pure. | Cache observation as authorization; follow a reparse leaf during resolve before checking it; alter recase subject spelling, root gating, absence or reclaimable credit. | RO-2: `test_preflight.py`, execution-review/workflow tests; separate subject error versus root failure, unsafe parent/trash, old-run temp grammar and observed-world identity. |
| Executor guards call native resolve/stat/revalidate repeatedly; `_stat_path` and component classification repeat observations. | Lose a final guard after recorder/copy/retry callbacks; wrong-volume file identity; out-of-root cleanup; change publication/recording order or retry an effect. | RO-3a: native/runtime/ACL/pending-cancel tests with the oracle byte layer unchanged. RO-3b: v2 oracle, guard-before-effect invariant and RO-0b root-swap sweep; COPY/UPDATE/MOVE/MOVE_UPDATE/recase/TRASH/delete/metadata/directory/NOOP paths. |
| Settlement oracle v1 pins every public filesystem probe, its timeline tokens, first-seen label ordinals and occurrence-counting fault predicates (e.g. `second_settlement_probe`). Its plans carry no reviewed volume/anchor, so only chain-only admission runs. | Block legitimate probe removal; after a re-pin, freeze a wrong guard placement; let a fault rule fire on a different probe than intended; mistake oracle passes for production admission-mode evidence. | RO-0a: v1→v2 mechanical projection proof, reviewed probe classification, semantic fault predicates, guard invariant passing on the unchanged product and failing under seeded guard removal. |
| Root/leaf swap refusal is witnessed only by hand-written spy subclasses in `tests/test_executor_runtime.py` that hook `revalidate_root`/`resolve`/`stat` by name. Preflight and verifier have no integrated differential authority. | A consolidated or renamed primitive silently bypasses the spy hook and its test still passes; preflight/verifier projections drift without a named test anticipating the case. | RO-0b: production-shaped swap sweep with non-vacuous refusal assertions; baseline-versus-candidate preflight/verifier projection differentials. |
| Verifier `_classify_subject`, native bound open and `AuthorityBoundVerificationReader`; rigs wrap readers. | A decorator skips admission; a custom reader validates one root but opens another; stale pre-read snapshot crosses callback; buffered fallback or false content evidence. | RO-4: native/engine, tools-verifier, recorder integration and inventory/post-execution tests; bound/unbound/subclass/decorator dispatch, before/after stats and conditional recording. |
| Sync/integrity workflows resolve bindings, open recording, wake queued work, pause/resume and hand post-copy candidates across phases. | Initial binding becomes long-lived authority; refresh drops pending work; handle reaches durable/wire state; cleanup masks the original failure or releases custody early. | RO-3b/4/5: workflow checkpoints, root replacement after recorder barrier, pending published retry, integrity wakeup/refresh, retained post-copy identity and installed execution journey. |
| Root identity only replaces configured ancestry; child relative paths remain externally mutable. | Treat retained root identity as authorization for all descendants; follow a preplaced junction/placeholder; accept a same-volume different root or mount-link ID. | RO-0b root-swap sweep in current and continuity modes; RO-1a/RO-1b and module native and injected boundary matrix; RO-5 adversarial preplaced traps and alternate-path-to-same-root control. |

Finite path matrix: ordinary drive/UNC and valid extended spellings, mixed ordinary
separators, existing relative-input behavior, nonexistent lexical paths, long
total paths and exact UTF-16 limit; reject existing unsupported namespace,
drive-relative/absolute ambiguity as applicable to each public entry point,
empty components, dot/dot-dot, reserved names, ADS, trailing dot/space, NUL and
invalid surrogate cases before any access. Preserve spelling rather than Unicode
normalization. Tests distinguish public path conversion from stricter root ingress.

Finite native matrix: unchanged root; same-volume replacement; changed volume;
same object through changed ancestor route; leaf reparse/placeholder/non-directory;
unsafe/missing relative parent and leaf; ordinary root below a mounted anchor;
root equal to mounted anchor; unsupported ID/query/access errors; two overlapping
invocations; pause/resume and retry; cleanup after partial acquisition. Use real
Windows NTFS cases where available and injected evidence for remap/rare capability
branches. Required native witnesses cannot be reported passed from skipped tests;
record privilege/environment limitations and leave the affected gate open.

Continuity-only identity/lifetime cases belong to RO-1b. They do not block RO-1a
or mechanical rows whose existing-contract witnesses and named gates pass.

The unchanged baseline is the inspected source plus its current behavior tests
and frozen settlement oracle (v1 until RO-0a replaces it with the projected v2
baseline; RO-0a changes no product code). Historical 5,410 ordinary passes at `5e4bf87`,
80 executor rig/pipeline passes and 148 verifier focused passes are provenance,
not a substitute for the fresh pre-change run. Before implementation collect
ordinary suite, import law and the settlement oracle on the actual starting
revision; preserve failures and resolve baseline ownership before proceeding.

### Checkpoint register

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| RO-0a | Settlement oracle v2 pins settlement policy and effects, not successful probe multiplicity, and adds a guard-before-effect invariant. | Plan review and separate implementation authorization | v1→v2 projection proof at the starting revision, audit self-tests with seeded violations, `check --repeat 3` on the new pin. | pending |
| RO-0b | Admission-safety and differential witnesses exist and pass on the unchanged product. | Plan review and separate implementation authorization | Production-shaped root-swap sweep, preflight/verifier differential drivers across the isolated baseline checkout, harness self-tests. | pending |
| RO-1a | Cheaper lexical/native admission primitives under the current ancestry and freshness contract. | RO-0b | Path/native/direct-consumer tests, ordinary/import gates, byte-identical oracle, RO-0b differentials; one anchor discovery, unchanged refusal consequences. | pending |
| RO-2 | Preflight reduces duplicate subject/descendant/parent-volume work with fresh admission per observation step. | RO-1a | Subject/root/temp/trash/recase matrix, preflight differential, workflow preflight and before/after observation measurements. | pending |
| RO-3a | Executor reuses authority facts and makes each existing public filesystem call cheaper without changing the public call pattern. | RO-1a | Executor/workflow/native gates, byte-identical oracle, swap sweep, F:/G: correctness/readback and stage measurements. | pending |
| RO-3b | Executor consolidates root/descendant probes to one admission per access/effect step under the current contract. | RO-3a, RO-0a | Unchanged v2 oracle, guard invariant, swap sweep, executor/workflow/native gates, F:/G: correctness/readback and measurements. | pending |
| RO-4 | Verifier consolidates bound opening, native setup and handle-derived sector geometry without continuity. | RO-1a | Reader/decorator/native/recorder/workflow gates, verifier differential, geometry witness, standalone and post-copy measurements. | pending |
| RO-1b | Adopt invocation-scoped root continuity across core and all three consumers, with existing profile eligibility and explicit lifecycle policy. | RO-2, RO-3b, RO-4; measured mechanical-only revision | Bootstrap/stat-handle equivalence/profile-flow/lifetime tests, full-width opened-volume comparison, continuity-mode swap sweep, differentials, consumer/native/ordinary/import/v2-oracle gates. | pending |
| RO-5 | Integrated workflows, native containment, lifecycle and measured work reduction close the batch. | RO-1b and retained passes from RO-0a/0b/1a/2/3a/3b/4 | Ordinary/import/v2 oracle, selected installed Windows journeys, baseline/intermediate/final measurements, independent adversarial review. | pending |

The nine rows are the completion denominator. Each is an independently reviewable
commit; RO-1b is the atomic shared-policy migration after the independently useful
mechanical commits. A stalled continuity matrix does not undo or block those
commits, but does keep RO-1b/RO-5 and M1-10 open. No checkpoint leaves its own
regression for a later row.

### Detailed checkpoints

#### RO-0a — Settlement oracle v2

**Objective.** Keep the oracle as the settlement-policy authority for this
refactor while removing its dependency on successful probe multiplicity.

**Scope and approach.** Change only `tools/executor_settlement_audit.py`, its
baseline and semantic pin, `tests/test_tools_executor_settlement_audit.py` and
EXECUTOR's Settlement Stability Gate text; no product code. Implement decision 8:
- Declare an explicit probe classification over every public filesystem method
  reached through `TracingFileSystem`. A probe performs no filesystem mutation.
  Unclassified methods, and any method that may create a directory or change
  metadata (for example `trash_destination`), stay in the byte layer.
- Drop successful unfaulted probe entries and their `fs:` begin/end tokens from
  the pinned capture. Keep erroring and fault-fired probe calls, with their
  tokens, in the byte layer. Emit the full trace only as non-gate diagnostic output.
- Canonicalize identity, volume and timestamp labels after projection, by first
  appearance in the retained layer.
- Replace occurrence-counting fault predicates (`second_settlement_probe` and
  any others found) with semantic predicates armed by a named step or token.
  Keep fail-closed consumption of every rule.
- Add the guard-before-effect invariant. It is evaluated over the full,
  unprojected timeline, so it still sees probes that are no longer pinned.
  Declare an effect-to-required-guard table: every target mutation needs a
  target-root admission since the most recent boundary token, and every source
  open needs a source-root admission. Boundary tokens are recorder, control,
  pacing, copy-backend checkpoint/end and emit tokens. Use the tracer's
  `$SOURCE`/`$TARGET` roles. Mutating methods that admit internally, where the
  tracer cannot see the admission (for example `trash_destination`'s own chain
  check), are declared as self-admitting in the table. A native test must witness
  each such internal admission, so the table cannot excuse a missing guard by
  assertion. This table is the initial evidence for EXECUTOR's step/effect table;
  RO-3b maintains it.
- Bump `FORMAT_VERSION` to 2 and replace the baseline and pin together.

**Acceptance criteria.** At the starting revision, the v2 capture equals a
standalone projection function applied to the committed v1 baseline, byte for
byte. Three consecutive v2 runs are identical. The 30-scenario, 70-row manifest
and every independent expectation are unchanged; those expectations reference
only effect tokens, which v2 retains. The guard invariant passes on all rows of
the unchanged product. Non-default baselines remain unpinned diagnostics, and a
dirty or unpinned baseline still cannot satisfy `check`. If the unchanged
product violates the declared guard table, treat it as a finding to adjudicate;
do not silently loosen the table.

**Regression watchlist.** A probe hiding an injected fault; a method misclassified
as a probe that actually mutates; label canonicalization that merges distinct
identities; a semantic predicate firing at a different step than the old ordinal;
an invariant that passes vacuously because boundary tokens are missing from a row.

**Tests and evidence.** Audit self-tests cover the projection function
(v1 fixtures in, expected v2 out), label canonicalization, classification
defaults and predicate arming. Seed violations and require the invariant to
fail: remove the pre-publish target admission, move an admission before a
recorder call, drop the source admission before open. Run `check --repeat 3` on
the new pin, `--dept executor` and `tests/test_tools_executor_settlement_audit.py`.
Retain the v1 capture, the projection output and both hashes as evidence.

**Documentation and handoff.** EXECUTOR's gate describes the v2 layers, the
invariant, the probe list and this refactor-specific override. Non-deliberate
baseline replacement still requires a reviewed policy fix with its regression.
Record the migration and its hashes in this register and HANDOFF.

**Adversarial review.** Independently try to hide a behavior change inside the
dropped layer: a probe whose result changes an outcome, a probe raising
naturally, a mutating call misfiled as a probe. Review each rewritten fault
predicate against its original intent.

**Commit gate.** `test(tools): pin settlement policy separately from probe calls`,
with the tool, baseline, pin, self-tests and EXECUTOR text in one commit.
No product change.

#### RO-0b — Admission-safety and differential witnesses

**Objective.** Give the removal of admissions and the preflight/verifier changes
positive evidence that works in production-shaped modes, before any product change.

**Scope and approach.** Add test/tool harnesses only; no product code.
- **Root-swap sweep.** Build production-shaped plans on the test volume with
  reviewed source/target volume identity, anchor and NTFS profile taken from real
  observation, unlike the oracle's volume-less plans. Cover each operation shape:
  COPY, UPDATE with and without backup, MOVE, MOVE_UPDATE, recase, TRASH, DELETE,
  MKDIR, NOOP, plus cleanup/cancel paths. Run each shape unswapped to enumerate
  its boundary positions (recorder commands, control checkpoints, copy-backend
  checkpoints, retry pacing), then rerun it with a real NTFS swap at each
  position. Swap kinds:
  - the root renamed away and a different directory placed at the same path;
  - an ancestor replaced by a directory junction to another tree;
  - a relative parent or leaf replaced by a junction.

  Directory junctions need no privilege. Assert that no effect lands after the
  swap on the decoy or outside the original root, by inspecting both trees.
  Affected operations must settle truthfully (never false success), and an
  admission-layer refusal must actually fire, unless the swap follows the run's
  last effect. Assign the sweep a department in `tests/_departments.py`.
  Declare its finite shape/position count and runtime.
- **Differential drivers.** One driver module, with identical bytes on both
  sides, is run by each checkout's own venv against identical fixtures. It uses
  only public APIs present at the starting revision and emits canonical
  projections:
  - preflight: `ObservedWorld` plus verdicts;
  - verifier: per-item result, reason, read strategy, bytes and recorder
    commands, for standalone baseline/verify runs and post-copy.

  Fixtures include ordinary files, drift, mismatch, unsafe parent junctions,
  trash present/absent/reparse, old-run temps, recase, missing subjects,
  zero-byte files, unaligned tails and identityless candidates. Normalize only
  declared nondeterministic fields such as run IDs and timings.
- Establish the isolated baseline checkout and venv described in RO-5 here, so
  every later row can run the differentials against it.

**Acceptance criteria.** The sweep and differentials pass on the unchanged
product and are deterministic. Harness self-tests show the sweep fails for a
seeded runtime that skips the pre-publish admission, and the differential fails
for a seeded projection change. Fixtures clean up exactly. A failure of the
unchanged product is a pre-existing finding that follows AGENTS stop/adjudication
rules; never weaken the harness to pass.

**Regression watchlist.** Swap points that miss a boundary; assertions that pass
because nothing was attempted; junction cleanup leaving foreign trees;
differential normalization that hides a real field; baseline driver imports
leaking candidate modules.

**Tests and evidence.** Run the sweep department, the harness self-tests and
both differential sides. Record the baseline checkout revision, interpreter,
dependency versions and driver hash. The existing spy subclasses in
`tests/test_executor_runtime.py` stay; RO-3b migrates them.

**Documentation and handoff.** TESTS describes the new department and its run
level; TOOLS describes the differential driver; PERFORMANCE is unaffected.
Record the baseline checkout location and lifecycle in HANDOFF.

**Adversarial review.** Review whether every declared swap position is actually
reached, and whether a harness bug could observe the original tree while claiming
to check the decoy.

**Commit gate.** `test: add root swap and preflight/verifier differential witnesses`.
No product change; the baseline checkout itself is untracked.

#### RO-1a — Current-contract lexical and native primitives

**Objective.** Deliver reusable cheaper primitives without waiting for root
continuity, retained handles or a new ancestry policy.

**Scope and approach.** Implement direct lexical normalization preserving original
spelling validation and namespace behavior. Split anchor discovery from volume
information queried directly at the admitted anchor: one `GetVolumePathNameW` per
full admission, with the current no-follow chain, expected volume and consumer
failure policy. The returned anchor is that admission's observation, not a fake
second independent probe. Reuse fixed native bindings with call-local buffers and
correct last-error handling. Expose a witnessed stat-to-volume conversion for
single-lstat consumers, keeping existing stored serial/file-ID formats.
Do not introduce pinned root bindings or change the current ancestry policy.

The narrow producer change is explicit: `NativeVolumeInfo.evidence.device_id`
describes the admitted anchor, not a second independent observation after the
chain. Supported stable-input mount/volume/ancestry refusals remain; a live
same-volume re-anchor strictly between the two former lookup points is no longer
claimed detected by that removed second observation. Test that case explicitly
and distinguish it from an unsafe structure present before admission/next final
guard, which must still refuse. This uses DEFENSE's existing quiescent-root and
path-check-to-use boundary, not the later root-continuity policy. Do not retain
a tautological equality or imply complete parity with artificial two-call traces.

**Acceptance criteria.** Same accepted/rejected path language and supported
stable-input root/volume/mount
refusals and no-follow ordering; no lexical filesystem I/O; no scalar/serialized
identity changes. Single-lstat volume evidence describes the observed object and
is compared with expected volume instead of stamped from the pathname. Calls
retaining only a chain contract do not gain an unexpected volume requirement.
Ordinary mounted anchors, UNC and non-Windows development paths retain their
current supported behavior. Native error-stage mapping remains truthful even
though obsolete second-anchor-specific assertions change.

**Regression watchlist.** Normalization hiding invalid components, casing/Unicode
key changes, mounted-anchor empty chains, default/injected probe signatures,
scanner full/scoped brackets, workflow volume overlap/clone policy and loss of
fresh checks through a reused library binding. Observation multiplicity is not
itself the safety contract; removed checks need preserved consequence witnesses.

**Tests and evidence.** Characterize the path and volume mismatch/error matrix;
run `tests/test_core_scanplan.py`, `tests/core/test_root_authority.py`,
`tests/core/test_scalar_identity_contracts.py`, `tests/test_scanner.py`,
`tests/test_workflows.py` and `tests/test_inventory_workflow.py`, then ordinary
suite/imports, the settlement oracle with an unchanged byte layer (only native
internals change), the root-swap sweep and both RO-0b differentials. Reconcile `test_second_anchor_change_precedes_volume_identity_acceptance`
and `test_missing_or_invalid_second_anchor_is_unavailable`: retain changed-volume,
unsafe-chain, wrong-root and missing/error witnesses against the new producer,
without a tautological anchor comparison or requiring continuity bootstrap.
Record the explicit same-volume live-reanchor case above and its changed internal
observation, rather than declaring the obsolete second-probe test equivalent.
If investigation shows a lost supported-path guarantee instead of that excluded
live race, stop the affected reduction for review; other mechanical work proceeds.
Terminal pass is current-contract behavior plus measured removal of repeated
lexical/anchor work; timings are diagnostic rather than a new speed threshold.

**Documentation and handoff.** CORE and component docs describe actual primitive
changes; PERFORMANCE retains attribution and this register records evidence.
No AGENTS/DEFENSE ancestry rewording is a prerequisite or part of this checkpoint.
The future continuity proposal remains only in this register until RO-1b.

**Adversarial review.** Review all pathing consumers and native probe injection;
attempt namespace ambiguity, unsafe root/volume mismatch and path-versus-object
volume disagreement. Confirm native binding reuse caches no filesystem facts.

**Commit gate.** `perf(core): reduce lexical and native admission work` with
required signature adaptations, tests and matching docs. No continuity behavior,
new root lifetime or protected baseline edit in this commit.

#### RO-2 — Preflight observation scope

**Objective.** Reduce repeated subject and parent-volume observation work
while preserving a fresh, scoped observed world for pure judgment.

**Scope and approach.** Keep `observe`'s already-reused reviewed authorities;
prepare immutable lexical facts once and share a current full admission only
inside one observation step. No continuity handle or new root scope is required.
For descendant walks and their callers, eliminate redundant existence/type probes
using one no-follow stat per observed component with explicit FileNotFoundError
handling. Preserve rejection of a reparse/placeholder before resolution.
**Retain root and candidate realpath containment and representability checks**;
they are separate facts from the lstat chain. Share their results only within the
same step, not across observations or callbacks. Retain a distinct final subject
observation when needed after resolution; do not collapse it merely by counting.
In `reclaimable_temp_bytes`, use the already-observed parent's `st_dev` for the
same-volume comparison instead of another `observe_native_volume`/mount lookup.
For the empty parent path observe the root itself freshly. Apply the same
object-volume reuse to trash/subject observations where the ordering matches;
keep compatibility behavior where stat volume evidence is not witnessed.
Retain separately fresh free-space, reclaimable-parent and trash observations.

**Acceptance criteria.** The same remaining distinct subjects/parents are observed;
root failures gate dependent work while relative failures stay local; missing
subjects remain absence. No mutation occurs. Capacity credit, temp ownership,
trash writability/volume checks, recase spelling and ObservedWorld/judge identity
remain unchanged. Current root/ancestry guards remain at each observation boundary.
No root binding is introduced here. Reusing one backend cannot leak prepared
facts between roots/invocations. Parent-volume mismatch prevents reclaimable
credit; missing, access-denied and nondirectory cases retain distinct behavior.

**Regression watchlist.** Present versus missing final leaf, path resolution of
reparse leaves, source/target subject-key collisions, case-sensitive recase,
root versus child error translation, empty target, full-admission fallback and
non-current-run reclaimable temps. No earlier preflight result authorizes execute.

**Tests and evidence.** Extend `tests/test_preflight.py` and
`tests/test_execution_review.py`; run preflight/workflows departments and tools
executor tests, plus RO-1a's changed core cases and the RO-0b preflight
differential against the baseline checkout. Characterize root changes
between subject calls and interleaved invocations on a shared backend. Add
deep child trees, empty/nonempty parent and off-volume-parent controls; attribute
descendant lstat/existence/realpath and per-directory mount calls separately. Measure
`observe` and pure `preflight` separately using the finite profile below; keep
subject/result equality and no-mutation receipts. Terminal pass requires unchanged
verdict/evidence semantics and reduced repeated mount/derivation work on fast paths.

**Documentation and handoff.** PREFLIGHT owns observation boundaries and immutable
fact reuse; WORKFLOWS owns composition; PERFORMANCE owns measurements. Correct the
current prose implying authorities are rebuilt for each call, since `observe`
already reuses them. Record status, raw evidence and fallback cases here/HANDOFF.

**Adversarial review.** Probe root replacement during stat/capacity/trash phases,
malicious relative paths and a leaf that becomes a reparse point before resolution.
Review the module/native handoff for reusable-success bypasses and shared state.

**Commit gate.** `perf(preflight): consolidate subject and parent volume observations`;
tests/docs and independent review close together, with no mutation or refusal
regression deferred to the executor checkpoint.

#### RO-3a — Executor call cost under an unchanged call pattern

**Objective.** Make each existing public filesystem call cheaper without changing
which calls the runtime makes, so the oracle's byte layer stays identical.

**Scope and approach.** Build the two reviewed authorities once per `execute`
invocation and pass those immutable facts through native without reconstructing
them; `revalidate_root` receives the same argument values as today. Inside
`NativeFileSystem` only:
- make `_stat_path` one no-follow observation with corroborated file-volume
  identity;
- classify root components from that same stat rather than following `is_dir`;
- in `_validate_existing_chain`, replace each `lexists` + lstat pair with one
  lstat plus FileNotFoundError handling, and return the observed endpoint/existence
  fact so `resolve(must_exist=True)` need not repeat `lexists`. Do not convert
  access failure into absence;
- adopt RO-1a's single-anchor admission and cached native bindings.

**Keep candidate realpath containment and the resolved-root comparison** inside
`resolve`; the lstat walk alone does not replace those facts. Runtime guard,
resolve and stat call sites are unchanged. Profile and test root depth and
descendant depth separately.

**Acceptance criteria.** Settlement oracle byte layer unchanged; the root-swap
sweep passes. Existing-contract refusals, file-volume mismatch rejection and
error/type classification hold. Tests pinning the second following `is_dir` are
intentionally replaced, with the consequence each one witnessed retained.

**Tests and evidence.** Executor and workflows departments,
`tests/test_tools_executor.py`, real native single-stat volume/type tests, the
unchanged oracle, the sweep, and F:/G: bands with readback and stage attribution.
Record this revision as the first executor measurement point.

**Commit gate.** `perf(executor): reduce native cost of root and path probes`,
with native changes, tests and EXECUTOR/PERFORMANCE text. Any change visible in
the oracle's byte layer means the work belongs in RO-3b.

#### RO-3b — Executor access and effect steps

**Objective.** Remove the remaining repeated admissions without changing the
effect journal, publication durability or recorded outcome meaning.

**Scope and approach.** Keep current full/chain admissions at actual access/effect
steps; no pinned binding or ancestry-policy change is required. Replace repeated
guard/resolve/stat admission inside a step with one native boundary. Explicitly
map these steps:
- source open, temp creation, finalize, post-recorder final guards, publish and
  published observation;
- backup, ACL/metadata repair, trash/move/delete, deferred directories,
  owned-temp sweep, cancellation cleanup, retry and pending-publication
  reconciliation.

Re-probe after callbacks and waits. Do not remove effect-specific stat
comparisons or conditional native primitives. Keep candidate realpath
containment and the resolved-root comparison at most once each within a step.
Reuse a leaf observation for `_stat_path` only within the same ordered step,
where freshness and error semantics are equivalent. Maintain EXECUTOR's
step/effect table and RO-0a's guard-invariant table from the same source. Add
any new public probe primitive to the oracle's reviewed probe list. The effect
calls' arguments and results must not change.

Migrate the name-hooked spy subclasses in `tests/test_executor_runtime.py`
(`ReviewedBindingSwapFileSystem`, `ReviewedSourceSwapFileSystem` and related
classes) to hook the consolidated primitive. Each must assert that its refusal
actually fired, so a bypassed hook cannot pass vacuously.

**Acceptance criteria.** All operation kinds keep exact reviewed scope, expected
source/target checks, atomic same-volume publication and durability-before-recording.
Current root/leaf replacement guards after copy/recorder/retry remain before
subsequent touches, including existing published-decoy witnesses; stronger
same-volume root-object continuity belongs to RO-1b. File-volume mismatch is rejected.
The v2 byte layer and guard invariant pass unchanged, every sweep position
refuses truthfully, and migrated spy tests prove their refusals fired. NOOP, retries, pause,
cancel, capacity failure, recording degradation and pending settlements remain
truthful; no extra effect/replay, leaked invocation state or cleanup outside owned paths.

**Regression watchlist.** UPDATE backup fallback and recovery; readonly/ACL
restoration; source mutation during streaming; recase and case-sensitive occupancy;
MOVE_UPDATE old-target disposition; child-first directory cleanup; post-publish
failure; callback substitutions; capacity failure during cleanup and failed
recorder barriers. Preserve the distinction between already-applied effects and
work still eligible to retry when rebuilding invocation facts on resume.

**Tests and evidence.** Run executor and workflows departments, affected core and
preflight cases and `tests/test_tools_executor.py`. Before and after, run the v2
settlement oracle with its pin unchanged since RO-0a, and the guard invariant.
No baseline or pin edit is authorized. Only additions to the reviewed probe list
are allowed, and they must leave the byte layer unchanged. Run the root-swap
sweep across every declared position and step-boundary injection cases where
existing probes are removed. Run all five F:/G: bands with
readback, the mixed hardlink-update and whole-tree fixtures; retain metadata,
outcomes, bytes/digests, reservations and exact manifest cleanup. Terminal pass
requires preserved effect/recording traces and demonstrated removal of redundant
admission/descendant work; wall-clock reporting includes invocation setup.
Capture this mechanical implementation separately from later RO-1b continuity.

**Documentation and handoff.** EXECUTOR owns the step/effect table and unchanged
settlement policy; ARCHITECTURE/WORKFLOWS own invocation/continuation boundaries;
PERFORMANCE owns before/after results. Record each removed check's retained
consequence witness, not a target call count or a universal six-check rule.

**Adversarial review.** Review each removed call against the guard table and the
sweep position that witnesses its consequence. Beyond the sweep, inject root and
child swaps after every external callback, recorder barrier and retry sleep, then
inspect actual filesystem state plus journal/recorder truth. Check that no
successful probe dropped from the pinned layer changed an outcome. A new
settlement-policy requirement, or a needed effect-signature change, stops this
checkpoint for redesign.

**Commit gate.** `perf(executor): admit roots once per filesystem step`; include
all required native/runtime/protocol/helper adaptations, tests and docs atomically.
Ordinary suite also runs if core/protocol changes expand beyond RO-1a's surface.

#### RO-4 — Verifier opening boundary

**Objective.** Make standalone and post-copy reads use one coherent fresh opening
boundary and reusable native setup without weakening cache-honest attestation.

**Scope and approach.** Reuse reviewed context facts and fixed native bindings.
Combine engine full admission and default native reader's final-touch admission
through an explicit bound-open contract; generic/custom readers retain engine
enforcement unless they implement the complete stronger seam. Migrate structural
dispatch, subclasses, decorators and `tools/verifier_rig.py` together. Share the
immediately consecutive native pre-yield and engine before-read snapshot only
where there is no intervening callback. Keep the size observation after
`on_stream_start`, fresh post-read stat, opened-volume and final-path checks.
Open the subject first, then query `FILE_STORAGE_INFO.LogicalBytesPerSector` on
that same handle. Witness equality with the former `GetDiskFreeSpaceW` value and
valid unbuffered alignment on supported fixtures; the normal path then needs no
sector-related mount lookup. Validate the returned value before alignment/buffer
work. Preserve a narrowly tested legacy geometry path only for documented
unsupported query capability; access/query corruption or invalid geometry must
not silently default or produce a verified result. No buffered fallback or
drive-letter geometry cache. Per-file buffers/hasher bytes remain unchanged.
This row needs no root continuity. Full-64 opened-volume comparison against a
bound root is added with RO-1b, not allowed to block this mechanical commit.

**Acceptance criteria.** Every selected item still binds to the exact reviewed
root, including shortcut/missing/unsupported rows. Bound readers cannot degrade
to unbound opens; wrappers forward all required capability/evidence. Legacy/custom readers without the
stronger bound-open seam retain engine full admission; a reader claiming the seam
with missing or malformed binding refuses rather than falling back. Root/child
substitution, wrong opened volume/path, short/over-read, drift and hash mismatch
retain truthful outcomes and conditional recorder behavior. Direct native-reader
use still refuses unsafe subjects before yielding. No buffered fallback. Pause,
cancel, retry/error and post-copy handoff close all native resources without
retaining resources across invocations or resetting retained progress/selection.

**Regression watchlist.** Callback between before-stat and read; reader subclass
overrides; faulty/missing capability forwarding; identityless candidates;
conditional evidence conflict; mismatch dominance; zero-byte reads; chunk limits
and alignment; absent baseline; same-task post-copy selected subset and resume.

**Tests and evidence.** Run verifier/workflows departments,
`tests/test_tools_verifier.py`, `tests/test_verifier_recorder_integration.py`,
affected core integrity tests and recorder consumer tests. Add direct/default/
decorated/custom reader tests for the new handoff before removing the old probes.
Run the RO-0b verifier differential (standalone and post-copy) against the
baseline checkout. Repeat all five standalone bands and executor readback with exact item/byte/digest
results; include injected callback mutations, native sharing-mode and
handle-sector/path-sector equivalence witnesses, zero/invalid sector values,
small/unaligned tails and documented unsupported-query behavior.
Terminal pass requires the same evidence decisions and fewer repeated opening
probes/setup operations, with no cross-callback snapshot reuse.

**Documentation and handoff.** VERIFIER owns reader capability and observation
semantics, CORE/ARCHITECTURE own protocol meaning, WORKFLOWS owns handoff/resume,
TOOLS describes tap forwarding, and PERFORMANCE records measured attribution.

**Adversarial review.** Use a decorator/subclass that would accidentally hide the
new capability, a custom reader returning wrong-volume evidence, and a callback
that changes the subject. Inspect positive and negative recorder commands as well
as displayed results. Review scope close and partial-open failure paths.

**Commit gate.** `perf(verifier): consolidate bound reader admission and setup`;
the reader protocol, all direct wrappers/fixtures and both workflow paths migrate
in one coherent commit, with no permissive compatibility fallback.

#### RO-1b — Invocation root continuity and consumer adoption

**Objective.** After measuring the independent mechanical gains, replace repeated
configured-root ancestry walks with the explicitly selected root-object contract.

**Scope and approach.** Core provides raw identity/attribute observation and
comparison; preflight, executor and verifier own explicit call-local scopes, never
state on runtime's shared filesystem adapters. Migrate all three consumers in
this checkpoint, not as unfinished adoption hidden in RO-5. Eligibility uses
decision 4's existing profile/locality/non-anchor predicate. Carry selected
profiles through standalone and post-copy context factories without adding
durable/wire fields or a parallel detector.

Bootstrap: perform current full admission, retaining the final root's independent
no-follow identity/attribute observation; open a no-follow directory handle and
compare raw full64 volume/full128 ID and ordinary attributes with that observation
and reviewed/admitted volume. Corroborate final path against the safely resolved
root. Only then pin the baseline handle. Raw `FILE_ID_INFO` or a witnessed
`st_dev`/`st_ino` mapping supplies identity, never the persisted low32 adapter.
Inject changes between chain, stat, volume, open and final-path observations;
partial opens close on failure. These checks retain the declared non-atomic,
quiescent-root limit. Each subsequent access may use one fresh lstat for root
identity/attributes/tag when the same mapping witness covers it; otherwise use a
fresh handle probe. Never probe only the pinned handle or cache a prior success.

Retries retain the baseline; pause/return/error/cancel close it; resume fully
admits anew and still reconciles retained effect identities. At each verifier
open, compare the opened file's raw full64 serial with the bound root's full64
serial (including equal-low32/different-high32 refusal). Keep low32 matching for
the existing reviewed/durable identity and for conservative mode. Do not put the
raw binding in persisted FileStat/attestation or change scanner identity policy.

**Acceptance criteria.** Same ordinary root through a new ancestor route can pass
inside the invocation; another object/volume or unsafe root leaf refuses before
use. Full admission still rejects preplaced ancestry traps; descendant lstat and
realpath checks remain. Profile false/absent, remote and equal-anchor cases retain
full admission; errors in an eligible mode never downgrade. Stat and handle probes
agree in full width on witnessed backends. Bindings are isolated across concurrent
invocations and close exactly once after partial failure and all normal/control
exits. Existing published/temp/selection and recorder/settlement truth is preserved.

The retained handle prevents file-ID recycling, but keeps the volume in use during
long verification and retry waits. This is an explicit lifetime tradeoff, not a
promise of active safe removal. Verify release on pause/cancel/completion and give
actionable guidance: pause or finish the operation, allow I/O to settle, then retry
safe removal; other processes may still hold the volume. Never promise that Close
or a pause request has released handles before settlement. No dismount/eject/lock
experiment against the user's F:/G: data volumes is authorized by this plan.

**Regression watchlist.** Same-low32 wrong volume; profile loss on standalone
context creation; mapped remote drive; root equal to mounted anchor; root/file-ID
reuse; root versus descendant aliases; callback and recorder boundaries; idle
retry waits; pause/resume decoys; custom adapters concealing stronger capability;
unsupported probe versus malformed evidence; close failure masking original error.

**Tests and evidence.** Run affected core/preflight/executor/verifier/workflow
and tools tests, ordinary suite/imports, the v2 settlement oracle with its pin
unchanged since RO-0a (its volume-less plans stay in the ineligible mode, so it
guards settlement, not continuity) and the guard invariant. Run the root-swap
sweep in continuity mode. There the same-object ancestor-alias case flips from
refusal to pass by decision 3, and every other position must still refuse. That
expectation change lands with this commit. Run both RO-0b differentials. Witness NTFS and supported identity-backend mappings (including injected high
bits), stat/handle probe equivalence, explicit eligibility/profile propagation,
bootstrap races and overlapping scopes. Use owned-handle counters/injected device
busy outcomes for lifecycle; an actual volume-lock/eject witness, if needed, uses
only an isolated disposable test volume with separate explicit setup/cleanup.
Review real Windows handle lifetime evidence without claiming F:/G: lock tests.
Terminal pass includes all three consumers, no policy downgrade and measured
continuity-only delta against the saved mechanical revision.

**Documentation and handoff.** This is the row that updates AGENTS, ARCHITECTURE,
CORE, DEFENSE and module/workflow docs for the ancestry change and root lifetime.
DESKTOP_UI (and existing relevant error text where applicable) records device-in-use
guidance; no new eject command, monitor or automatic dismount. PERFORMANCE retains
the intermediate/final measurements; this register and HANDOFF carry readiness.

**Adversarial review.** Review producer plus every consumer adoption as one policy
change. Attempt to use a missing profile as authority, accept a high-bit collision,
share a binding across tasks, reuse a success through callback/resume, hide an
unreleased handle or turn a failed fast-path probe into full-admission success.

**Commit gate.** `perf: adopt invocation-scoped root continuity` with shared
contracts, all three consumers/context factories, tests and policy/lifetime docs
in one coherent checkpoint. No unadopted consumer or cleanup regression is deferred
to RO-5. Mechanical commits and their evidence remain independently usable.

#### RO-5 — Overall final sweep

**Objective.** Prove the integrated change preserves user workflows and removes
the identified repeated work; individually green module rows are insufficient.

**Scope and approach.** Review the full diff and every regression-map row against
the original source and final candidate. Run fresh Plan/review/preflight/Execute,
automatic readback, standalone baseline/verify/rebaseline and live pause/resume/
cancel paths. Include queued wakeup, retained published/temp state, concurrent
tasks sharing runtime adapters and normal Close/shutdown. Preserve current
M1-10 unrealized behavior; this sweep cannot implement it incidentally.

**Acceptance criteria.** Ordinary, import, v2-oracle/guard-invariant, root-swap
sweep and differential gates pass; required
native/installed witnesses execute; all nine rows' resource, refusal and effect
claims have terminal observations. No serialization/schema/event drift, handle
retention beyond invocation or scope widening. Every new finding is resolved
within scope or adjudicated; no supported hard-wall defect is accepted as a
performance tradeoff. Docs describe shipped behavior only after implementation.

**Regression watchlist.** Whole-task binding reuse, preflight-to-executor authority
transfer, manual versus automatic post-copy distinctions, resume with a matching
decoy, clone ambiguity, child reparse traps, misleading unsupported/verified
results, stale current-ledger evidence and cleanup masking the causal failure.

**Tests and evidence.** Exact established commands (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\lint-imports.exe
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3
.\.venv\Scripts\python.exe -m pytest -q -o "addopts=" -m headed tests/interfaces/web/test_setup_headed.py::test_m1_6_installed_setup_flow tests/interfaces/web/test_task_execution_review_headed.py::test_installed_task_execution_review_real_copy_and_capture
git diff --check
```

Focused commands use `--dept core`, `--dept preflight`, `--dept executor`,
`--dept verifier`, `--dept workflows` and `--dept database` as applicable; exact
membership stays in `tests/_departments.py`, including RO-0b's sweep department.
The oracle must report `settlement check passed: 30 scenarios x 3 runs` against
the v2 baseline pinned by RO-0a, with the guard invariant passing. Structural
settlement changes are excluded. After RO-0a, a mismatch requires cause analysis,
not baseline regeneration. The two installed journeys cover Setup/Plan and real-copy execution presentation
through the composed runtime. Pause/resume/cancel, standalone integrity, post-copy
selection, concurrency and cleanup semantics are covered by the named ordinary
workflow/native and injected cases, not claimed from those two headed journeys.
Installed journeys use the built wheel and existing
contained Windows helpers, not a source-only or fake-page substitute. Environment
failures preserve receipts and leave required native evidence open.

**Finite measurement profile.** Reuse the read-only five F: size bands and
separate G: rig-owned targets; retain reverse 4 GiB and mixed hardlink/whole-tree
controls. Add dedicated 1,000 × 4 KiB copies with configured-root depths 1, 8 and
32 while keeping child paths flat, and a separate depth-8 child tree so root
and descendant costs are not conflated. Define generator, manifest, path lengths,
source hash/metadata and exact cleanup before creating fixtures.

Baseline execution is concrete. RO-0b establishes it, because its differentials
need it before any product change. Freeze the pre-RO-1a product revision after
its fresh baseline tests; RO-0a/0b change no product bytes. Create or reuse a
suitable isolated managed worktree at that exact revision, and give it its own Python 3.13 venv with the same pinned dependency
versions as the candidate. Check attached worktrees before creation. Invoke each
side's absolute venv Python with its own checkout as cwd and record both revisions,
interpreter/dependency versions and driver hashes. Never import candidate modules
through PYTHONPATH into the baseline or copy a venv across checkouts. The RO-3a
revision is recorded as an intermediate measurement point. The retained
RO-2/3b/4 mechanical revision is a third runnable reference: capture it before
RO-1b and give it an equally isolated checkout/venv for continuity-only comparison.
Reuse an accounted checkout sequentially if needed, preserving reports and exact
revision pins. Original benchmark receipts alone cannot substitute for these runs.
Use the same external measurement driver bytes where APIs permit; document any
minimal adapter difference and test both adapters' item/byte/timing boundaries.
Give each side fresh unique target/report paths, clean them through rig manifests,
and serialize storage work. Keep the baseline worktree through RO-5 review, then
archive only after processes stop and artifacts are accounted for.

For baseline
and candidate collect five interleaved pairs per main band/depth, alternating
order, with the same driver/profile; serialize storage work. Measure preflight
observation and pure judgment separately, executor including binding lifetime,
standalone verification, and post-copy readback. Keep success/recording/readback,
item/byte/digest, setup/teardown and reservation/resource receipts. Instrument
one separate small and large pass for API/derivation attribution, including
descendant lexists/lstat, retained realpath and reclaimable-parent volume work; do not use
instrumented timings as the headline comparison or sum nested durations.

PERFORMANCE owns fixtures/provenance and DEFENSE §7 owns evidence authority.
These timings remain Tier 0 diagnostics, not a new release SLO or arbitrary
percentage target. Completion requires demonstrated removal of the identified
redundant work and honest before/after results; unexplained timing regression or
failure to improve the intended small/deep workloads requires analysis and user
disposition before closing RO-5, not a manufactured speed claim. Exact API counts
are diagnostic rather than frozen implementation tests. Only RO-1b root-probe count should
cease scaling with configured-root depth in continuity mode; descendant work and
kernel lookup cost remain separate.

**Documentation and handoff.** Reconcile AGENTS, CORE, ARCHITECTURE, DEFENSE,
EXECUTOR, PREFLIGHT, VERIFIER, WORKFLOWS, TOOLS and PERFORMANCE for actual changed
seams; update this register, CHANGELOG and HANDOFF. README changes only if the
phase/roadmap synopsis needs it. Preserve failed receipts and starting/candidate
revisions; account for every fixture and leave the original corpus untouched.

**Adversarial review.** A reviewer separate from implementation checks the complete
diff, same-object alias policy, native matrix, operation-step inventory, custom
adapter migration, concurrency and lifecycle. Required artifact: a closed mapping
from each regression row to tests/receipts plus any explicitly adjudicated residual;
no parallel delivery register or generic safety checklist.

**Commit gate.** `test: close root admission optimization across workflows` only
for needed integration witnesses and matching closeout docs; if no additional test
changes are needed, use `docs: close root admission optimization`. No opportunistic
refactor or baseline rewrite. Batch completion requires RO-5 itself to pass and the
register to account for every accepted row before M1-9/M1-10 scheduling advances.

### Resumption block

- Current state: all nine rows pending. Planning only: no product, test or tool
  changes, optimization benchmarks or new native fixtures in this planning turn.
  The user approved oracle format v2 and its one-time EXECUTOR override (decision 8).
- Next action: review this proposal, then obtain separate implementation
  authorization; check branch/HEAD and unrelated changes, run the fresh baseline,
  and start RO-0a and RO-0b against the unchanged product. Then RO-1a's
  current-contract tests. Do not wait for RO-1b's bootstrap
  or capability witnesses to implement authorized mechanical rows. User has chosen
  the ancestry-to-root-continuity proposal, not authorized implementation.
- Established commands are in RO-5; reuse the existing rig commands and methods
  in PERFORMANCE. Create ignored `build/root-admission-optimization-<date>/` only
  when execution begins, with AGENTS naming/layout/cleanup conventions first.
- Preserve `build/executor-assessment-20260927/`, source corpus, historical oracle
  and frozen baselines; do not overwrite old reports. RO-0a's v1→v2 replacement
  is the only authorized oracle baseline edit in this batch. Keep DOC-2, existing stashes,
  incident/AB evidence and unrelated branches untouched.
- Open evidence: fresh starting suite and isolated baseline checkout/venv;
  v1→v2 projection proof and guard-invariant pass on the unchanged product;
  root-swap sweep and differentials passing on the unchanged product;
  RO-1b profile propagation/bootstrap and stat/handle equivalence witness;
  depth profile; native binding bootstrap/lifetime and custom-adapter migration.
  Existing profile/locality/anchor evidence selects the conservative path; no
  second runtime detector is planned, and probe failures never downgrade.
- Stop for supported data loss/corruption, out-of-root or unauthorized effects,
  false durable/terminal success, replayed mutation, security/hard-wall escape or
  inability to preserve work. AGENTS recurrence and recovery rules apply. A needed
  policy/ownership expansion, inability to preserve current supported behavior,
  or settlement-policy change requires review; never relax a gate for speed.

## Incident repairs and closeout — 2026-09-27

### Authorized cold-admission follow-up

From `0e4595e4`, the user authorized two separate commits on `milestone1`:

| ID | Outcome and finite population | Preserved guarantees / verification | Status |
| --- | --- | --- | --- |
| CLI-DRIFT | Distinguish observed cold-file drift from stable incompatibility and unavailable artifacts; bound validation-only retries and give persistent drift non-destructive retry guidance. Owners: db contracts, workflow pair admission, CLI and their direct repository/history/initializer consumers; focused database/CLI tests and DATABASE behavior documentation. | Cold source nonmutation, fresh-pair creation/rollback, live-owner checks, existing CLI refusal exit, no mutex or task replay. Deterministic transient/persistent drift, stable mismatch, I/O/journal controls, CLI pair/history paths, ordinary suite, import law and independent review. One fix commit. | Complete: `5e4bf87`; 5,410 ordinary passes, 4 privilege skips, 34 headed deselections; 571 focused passes, 27 exact-count controls, 12 import contracts, 151 documentation links; independent review approved. |
| DOC-PRECISION | Correct TESTS' unverified already-visible-notice rationale and scope DATABASE's own-snapshot statement to owner-opened connections. No new internal history-reader validation. | Source comparison, documentation links/diff checks and independent review. One separate documentation commit after the fix. | Complete in this documentation commit; source comparison, links/diff checks and independent review. |

Desktop Setup refusal mapping, cross-process exclusion and unrelated CLI tooling
changes remain excluded. Existing safety/recurrence stops apply. Evidence lives
in `build/cold-admission-followup-20260927/`; root serializes shared delivery
documents. Admission retries must not retry task submission or effects, and
inconclusive observations must never acquire reset advice merely by exhausting
the retry policy.

Implementation boundary: schema owns a shared admission-error base with the
existing mismatch exception as a subtype; contracts owns typed observed drift
and a single three-attempt validation policy. Pair admission retries a complete
single-attempt ledger/history/recheck operation, while standalone consumers
apply the same policy to one role. Cleanup failure or control interruption must
not disappear into retries. Schema errors remain provisional until source
stability is rechecked. Three attempts bound repeated work, not total elapsed
time for reading arbitrarily large files.

Workflow-owned non-destructive guidance passes through DatabaseContractView to
CLI and the existing host startup display. Direct facade/view consumers and
their witnesses are in the finite migration. Typed history admission refusals
use the existing CLI refused exit (3); other history read failures retain exit
4. Stable incompatibility alone retains reset advice. No fresh publication,
reservation, task submission or filesystem effect enters a retry body.

The user authorized four separate reviewed outcomes from `a0205c08`.
Implementation boundaries and the original finite populations are retained in
Git history; component documents own the resulting behavior. Evidence is under
`build/admission-bridge-closeout-20260927/`.

| ID | Delivered outcome | Verification | Commit / status |
| --- | --- | --- | --- |
| IR-DB | Separate strict cold file admission from runtime-owned live SQLite validation. Preserve exact schema/pair/journal/placement refusal, independent role reads, fresh noncreating Plan and truthful effects. DATABASE/DEFENSE own the contract. | Deterministic reader/WAL activity and refusal/lifetime controls; 5,379 ordinary passes, 4 privilege skips, 34 headed deselections; installed Setup passed; 12 import contracts; 87 documentation links; independent review. | Complete: `639b2ea`; `db-review.md`, `db-implementation.md`, `db-ordinary-final.xml`, `db-installed-setup.xml`. |
| IR-BRIDGE | Migrate the optional diagnostic to current scalar/terminal shapes, retain exact reliable-item witnesses, preserve the first report failure and raw incomplete streams, and settle synthetic cancellation through normal host cleanup. BRIDGE/PERFORMANCE own behavior and observations. | 35 focused passes and CRLF page probe; 5,380 ordinary passes, 4 privilege skips, 34 headed deselections; complete installed observation on `639b2ea`; injected rejection retains raw evidence and exits normally. | Complete; independent review approved. The commit carrying this row delivers IR-BRIDGE. `bridge-review.md`, `bridge-ordinary-final.xml`, `bridge-full-final.json`, `bridge-injected-report-failure.json`. |
| IR-CLOSE | Remove AB-7 focus loss from BUGS and retain environmental troubleshooting in TESTS. Retain the enabled-button wait for independent asynchronous-filter sequencing. Retire the unrealized DWM sentinel obligation; no new focus/compositor detector. | Source/evidence review, 86 documentation links and diff checks; independent approval. Product/helper unchanged. | Complete: `e8d3613`; `closeout-review.md`, `closeout-docs-check.json`. |
| IR-DEFER | Shelve AB-8 stack/wrap; retain the unconfirmed renderer/check race, historical limitations and recurrence inspection points in TESTS. | Documentation consistency, 84 links, evidence references and diff checks; independent approval. No CSS/helper/assertion change. | Complete: `8f75f75`; `defer-review.md`, `defer-docs-check.json`. |

The database runtime retains two lazy role connections. Later pair checks and
consumer opens validate current SQL, main identity and journal absence; public
standalone constructors retain cold byte-preserving preflight. Reader retirement,
writer placement and retryable runtime shutdown remain intact.

The bridge driver decodes only its finite 1–1,500 byte coordinates, consumes
item-free terminal facts and independently checks 150 ordered reliable outcomes
per task. Reporting stops on the first rejection, queued counters unwind, and
failure metadata is captured before cleanup. Failure/final milestones and
unfinished timing streams survive clean incomplete exits. The current source
population is the bridge diagnostic package, its focused test module and page
probe; production host/transport and frozen custody JSON are unchanged.

Historical advisory `passed`/`event_passed` remain false in the final native
observation; `status=complete` and `measurement_valid=true` establish the
diagnostic endpoint only. No new timing/custody acceptance is claimed.
Original AB-7 Setup and AB-2/AB-10 causal attribution remains qualified.
All original and intermediate failure receipts are retained.

AB-8 implementation, environment monitoring, GUI changes, automatic mutation
replay, broad schema migration and unrelated M1 work remain excluded. A
pre-existing performance-CLI error suggests an unsupported replacement flag;
BUGS records that separate guidance defect, and reruns use fresh report paths.
No CLI change was included.

## Post-M1-8 reduction plan

AB-1–AB-10 are delivered. The batch reduced duplicate presentation and bridge
work while retaining reviewed effects, truthful results, installed desktop
journeys and the current subject contracts. It made Plan/execution UI latency
and empirical representation-memory measurements optional developer tooling;
enforced bounds, counted-work regressions, release resource checks, transport
custody, and executor settlement retain their separate authority. No speed or
memory improvement is claimed. The table is the completed register; Git,
CHANGELOG and the named ignored evidence hold its chronology and failed receipts.

| Closed outcome | Result and current owner | Commit and evidence |
| --- | --- | --- |
| AB-1 | AGENTS small-change default, concise delivery records and PERFORMANCE methods/results ownership; subject contracts and DEFENSE evidence authority stay separate. | `29d9b8f`; `build/post-m1-8-ablation-20260925/ab1-checks.json` and review. |
| AB-2 | Optional selected performance drivers moved to `tools/performance/` with independent fixture/action checks and truthful incomplete reports; required correctness/release gates retained. [PERFORMANCE](PERFORMANCE.md), [TESTS](TESTS.md), [TOOLS](TOOLS.md), [DEFENSE](DEFENSE.md). | `8ba38ced`; `build/post-m1-8-ablation-20260925/ab2-migration.md`. Historical JSON/contract/authority bytes remain unchanged. |
| AB-3 | Unused historical mapping reader removed; current scan correspondence, unique-pair/hardlink refusal and ledger behavior retained. [DATABASE](DATABASE.md), [PLANNER](PLANNER.md). | Reviewed `c5f1de8`, integrated as `dd23c270`; `build/post-m1-8-ablation-20260925/ab3-integration.md`. |
| AB-4 | Desktop Plan open captures one revision-bound summary and workflow-owned membership without building a full public preview; folder derivation is lazy. Public CLI/API preview and selection authority remain. [INTERFACES](INTERFACES.md), [PRESENTATION](PRESENTATION.md). | `9cfd2a0`; AB-4 verification in `build/post-m1-8-ablation-20260925/`. |
| AB-5 | Bridge response adoption combines repeated traversal over one detached value; complete request, byte, type, identity, prefix and custody checks remain. [BRIDGE](BRIDGE.md). | `1cb75fb`; AB-5 verification in the same evidence root. |
| AB-6 | Genuine document replacement retires page authority and presents a contained restart path while admitted work and worker custody continue. Canceled navigation and same-document history retain their distinct behavior. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Harness prerequisite `f55a7dd`, product `2b4a2214`; AB-6 gesture and verification receipts in the same evidence root. |
| AB-7, AB-7R, AB-7S and corrections | Existing asynchronous admission/completion retains original results for effect/lifecycle commands without elapsed-time mutation abandonment or replay. Bounded observation, late adoption, explicit unavailable/invalid-result feedback, duplicate protection, exact intent fences and pending Close survive. Five revisioned/current-state commands use refresh or fresh choice. One browser attempt/settlement owner replaces duplicate recovery paths. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md). | `6287db0c`, `d4351acd`, `514d71d1`, corrections through `4f1537c2`; `build/post-m1-8-ablation-20260925/ab7-verification.md`, `ab7r-verification.md`, `ab7s-verification.md` and later review receipts. The earlier unexplained Setup/Plan-again observations are not claimed fixed. |
| AB-8 and follow-up | One Python task/session snapshot owns semantic progress and terminal presentation; the page atomically adopts bounded facts. Gap uncertainty, exact scalar identity, item windows/detail, transport replay, local interaction, D4, command recovery and Close remain. A task-list summary can briefly precede snapshot delivery without becoming a second terminal authority; record adoption reconciles them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [INTERFACES](INTERFACES.md). | `7445f70a`, `4ff11a8`; `build/ab8-resume-20260926/` and `build/ab8-followup-20260926/`. Full event-body removal remains a separate protocol decision. The earlier stack/wrap rerun's cause was not established. |
| AB-9 | Duplicate CSS/source/gallery spelling pins retired with behavioral, computed-style, native, accessibility and security witnesses retained; no production asset changed. [TESTS](TESTS.md), [DESKTOP_UI](DESKTOP_UI.md). | `7af07724`; `build/ab9-20260926/verification.md` and `detector-map.md`. |
| AB-10 | Integrated workflow, boundary and evidence sweep; one stale optional execution-UI feedback driver/checker corrected while frozen historical JSON and product semantics stayed unchanged. Required retained gates and final endpoint/installed journeys were accounted by dependency. | `cb57c41a` (first AB-10 commit); `build/ab10-20260926/verification.md`, `reuse-and-raw-evidence.json`, review and link receipts. The bridge-event diagnostic remains incomplete with an unassigned event-v5 fixture migration; it claims no product cause, release gate or performance result. |

Post-closeout consolidation archived the study and pruned the accounted AB-3,
AB-6 gesture, GUI-J and GUI-M2 recovery refs plus the AB-3 worktree. Exact tips
and complete history remain in `build/ab10-20260926/side-recoveries.bundle`;
`preservation.json` and `cleanup.json` record verification and 78 copied evidence
files. All five stashes and the pending DOC-2 branch remain; no remote changed.

The retained user decisions are: unsupported reload with stale-document
containment (D1); no timed mutation-result abandonment or automatic replay, but
recovery of the original result after delivery failure (D2); optional useful
performance measurements without new hard speed targets (D3/E1/D7); unchanged
highlight/focus and range/navigation behavior separate from execution checkboxes
(D4); native Advanced Color mitigation (D5); and the user-owned small-change
classification in [AGENTS](../AGENTS.md) (D7). D6's missing-row
acknowledge/restore desktop capability is accepted and still needs an explicit
delivery allocation when M1-9/10 activates. M1-10's rebaseline confirmation
accepts replacement of content evidence and is a different action. Existing
[FEATURES](FEATURES.md), [INVENTORY](INVENTORY.md),
[PRESENTATION](PRESENTATION.md) and [DESKTOP_UI](DESKTOP_UI.md) own the D6 behavior;
this completed batch neither deletes it nor marks it delivered.

| Rejected or deferred study lead | Current disposition |
| --- | --- |
| L5 producer/retained admission merger | Rejected: independent counter-free populations and cumulative retained charges differ. [DEFENSE](DEFENSE.md) owns bounds. |
| L7 copy diagnostic removal | Rejected: tools consume default-off copy metrics. [TOOLS](TOOLS.md), [EXECUTOR](EXECUTOR.md). |
| L8 continuation/settlement class merger | Rejected: distinct recovery facts and legal states; no safety-equivalent simplification. [EXECUTOR](EXECUTOR.md). |
| L9 CSS replacement for native Advanced Color | Rejected: CSS misses SDR WCG; retain native mitigation. [DESKTOP_UI](DESKTOP_UI.md). |
| L6 Plan-volume/verdict check consolidation; S5 full application-owner merger | Unqualified/deferred. Construction, shape and semantic checks protect different boundaries; lifecycle, service, observer, dispatcher and adapter cleanup have distinct owners. No generic validator, lock or settlement framework is authorized. [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md), [INTERFACES](INTERFACES.md). |
| Full event-body removal; Plan-again tracer retirement; broad projection topology and shared selection-admission/safety cache ideas | Separate deferred decisions, without implementation authority from AB-8 snapshot trimming or the older R7 study. Retain diagnostic/replay consumers, tracer and copy metrics until an activated boundary accounts for them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [TESTS](TESTS.md). |
| Older recording-tail, pause/cancel and mutation-verdict compression ideas | Unscheduled alternatives from the completed narrow-reduction study, not latent checkpoints. Exact mutation/publication/recording order and settlement oracle remain [EXECUTOR](EXECUTOR.md) obligations. |
| Older R7-5–R7-8/R7-G and the blanket AB-7 domain-resend proposal | Old execution denominator retired, not passed. AB-2/4/7 absorb selected outcomes; AB-7R validation rejected blanket receipt equivalence and resend. No old checkpoint or frozen test recipe resumes. Historical detail is in the archived study §13–14. |

Five earlier studies remain historical under `obsolete/`: completed TA/ST/PR/NR
work is accounted in the [archived study §13](obsolete/POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting).
Their still-supported boundary, selection, lifetime, native, history, database,
workflow and executor guarantees are owned by CORE/TESTS/DESKTOP_UI/INTERFACES,
DATABASE/HISTORY, ARCHITECTURE/WORKFLOWS and EXECUTOR respectively; archived
method prescriptions cannot silently reopen them. The old M1-7 R7-1–R7-4
were delivered, RI-1–RI-4 investigated, and later R7 rows suspended/superseded.
The unproven foreign-task Execute-result concern did not establish a supported
misroute; current [BRIDGE](BRIDGE.md) identity adoption remains binding.
In particular, history write admission precedes pending mutation, persisted
readback checks normalization/hash/columns/receipts, old or mixed database pairs
refuse without automatic migration, and executor publication/settlement ordering
remains guarded. CORE/TESTS retain the FailureDetail lifetime guard;
VERIFIER/ARCHITECTURE retain duplicate/unknown integrity-selection refusal and
detached facts; DESKTOP_UI/INTERFACES/BRIDGE retain real native input,
accessibility, privacy and media checks. Representation-specific frozen lists,
query-count pins and superseded private-index prescriptions are historical.

## Completed preparation and MOVE-1

PA-1–PA-3 reconciled five earlier studies and moved them to `obsolete/` in
`0c74ee7`; the current decisions above and the archived study preserve their
dispositions. MOVE-1 (`549f3b4`) restored repeated source moves through current
unique correspondence while current hardlinks, duplicate identities, ambiguous
pairs and incomplete scans remain ineligible. [DATABASE](DATABASE.md),
[PLANNER](PLANNER.md) and [BUGS](BUGS.md) own its behavior; the native/ordinary
receipts remain in `build/move-history-20260925/`. No schema, recorder or
retained-history rewrite was part of MOVE-1.

## M1-8 execution review closure

M1-8 delivered shared Plan/live/terminal status, bounded rows and Details,
current-ledger distinctions, follow/Go, truthful progress/capacity, action
feedback and same-task Retry observation including pending Close. Retry never
restarts execution. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md) and [EXECUTOR](EXECUTOR.md) own the behavior.
P2/R0–R2/post-R2/RC-1 passed A1–A5 and B1–B6: 5,405 ordinary passes/five
skips, 33 installed GUI obligations and 12 imports. Reviewed commits
`4bbf943`, `8f7555b`, `0fc2f5d`, `9e5b080`, `b1f5a07`, `c974447`,
`96a0212`, `9be2930`, `3ea4e6b`; raw and failed receipts are in
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/`.
[PERFORMANCE](PERFORMANCE.md#source-linked-historical-observations) owns the
fixed U-v2 78-attempt observations.

The A6 integration receipt at `build/m1-8-archive-20260924/integration.json`
records non-squash merge `6c00ec731dd176d201e2a2c3a2a53b47652c544e`,
tree `f7691c518a31a160f888db299faa9342bd9a4349`, candidate
`cd2d44a802c665a4f76331b0a15856ef8102f1ac` and
`postmerge_validation: PASS`. It, not later test color, closes A6. The archived
register owns its finite gate; prior failed R2 attempts remain failed. A page
capture alone does not prove native compositor health. Historical recovery
commits were not merge units.

## Remaining checkpoints

Pending rows record accepted future outcomes; implementation still needs user
authorization, active scope and finite verification. A finding does not enlarge a
row; [AGENTS](../AGENTS.md) governs scope changes, stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| RO-0a/RO-0b, RO-1a/RO-1b, RO-2, RO-3a/RO-3b, RO-4, RO-5 | Verification machinery, then the shared root evidence refactor and focused executor/preflight/verifier optimization under the proposed root-continuity contract above. | Nine-row register, settlement oracle v2 and guard invariant, root-swap sweep and differentials, mechanical/intermediate/continuity evidence, native/regression matrix, workflow sweep and paired diagnostic measurements above. | Pending proposal; schedule before M1-9 by default and mandatory before M1-10. Implementation needs separate authorization. |
| M1-9 | Bounded inventory projections, current evidence and the full inventory consumer for sibling sorting. | Complete or prior-complete publication; warnings outside action scope; raw evidence provenance; search/filter/collapse/window/detail, replacement/race and production sort/reset paths; headed witnesses. | Pending; RO-5 precedes activation unless the user explicitly reschedules M1-9. Missing-row acknowledge/restore UI must be explicitly allocated at activation; this row does not silently claim it. |
| M1-10 | Baseline, verify and rebaseline controls plus first same-task manual post-copy verification, without persistent operation-time hashes. Eligible null-evidence files enter rebaseline; every admitted rebaseline hashes and replaces/creates evidence, and a match is not verified. | Confirm acknowledgement admission before claim/native work; all-null/mixed workflow, service/CLI and desktop paths; conditional recording and supersession races; atomic handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; overlay/result identity. Independently review operation matrix and conditional recording. Terminal Verify-remaining/subset retry remains deferred. | Pending; RO-5 completion is a hard activation prerequisite. Rebaseline confirmation is distinct from missing-row acknowledgement. |
| M1-12 | Close integrated lifecycle/retention across activated task surfaces, then complete adversarial, documentation, ordinary and headed verification. This absorbs former M1-11. | Plan-only, execution-only, linked/manual verification, inventory, refused/canceled/degraded/failed tasks across same-document navigation, contained unsupported reload, explicit close and shutdown; admission bounds, stale-response suppression, exact resource release and retained truth. Applicable settlement oracle, ordinary/headed, installed-wheel/product, imports, diff/active-link checks and independent cross-component review. No aggregate-artifact or whole-owner-graph criterion. | Pending. |
| M1-Release | Beta packaging and release closure after delivery rows above. | Installed artifact from clean checkout; frozen specification/dependency/CI, notices and corresponding source; standard-integrity host proof and every applicable BR-G/SH-G gate. [INTERFACES](INTERFACES.md) owns host/package/SH-G; [BRIDGE](BRIDGE.md) owns BR-G. | Pending. |

DOC-2 remains **pending, outside the AB batch**. Its historical branch proposal
removes exactly four superseded compact-plan commits from `milestone1`, preserves
the old tip and opens a draft PR from `milestone1-anthony`. Before any action,
freshly check divergence, remote tip and preservation of all work; unexpected
commits or unaccounted work require adjudication. AB-10 and the documentation
consolidation do not execute, close or authorize DOC-2 history rewriting.

## Delivered product checkpoints

| Closed row | Result and current owner | History/evidence |
| --- | --- | --- |
| M1-4, M1-async | Process-live task creation/navigation/close and bounded asynchronous admission/completion with original effect owners. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `ab453e1`, `675181a`; `build/m1-async/`. No durable task survival claimed. |
| M1-5, M1-6 | Typed location admission, bounded recents, frozen Setup, serial pair and standalone inventory starts, fresh Plan again. [INTERFACES](INTERFACES.md), [WORKFLOWS](WORKFLOWS.md), [BRIDGE](BRIDGE.md). | `e19ed9d`, `76ba7d0`; `build/m1-5/evidence/`, `build/m1-6/`. Hints grant no authorization; no global default mutation or partial-pair start. |
| M1-7 | Bounded Plan review, sibling sorting, committed selection and same-task execution. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Through `5986c57`; `build/m1-7/evidence/p9-full-20260916/`; R7-1–R7-4 later through `95f31e1`, with R7-G retired rather than passed. |
| M1-8-capacity, E, P1, P2, R0–R3 | Stop later operations after recognized capacity failure and current settlement; bounded current-ledger/retained execution review and installed recovery. [EXECUTOR](EXECUTOR.md), [DATABASE](DATABASE.md), [PRESENTATION](PRESENTATION.md), [DESKTOP_UI](DESKTOP_UI.md). | `04947ba`, `7905a1b`, `055325b`, `4bbf943`, exact A6 receipt above and [archived register](obsolete/M1_8_DELIVERY.md). Recorder-only failure remains independent degradation; P2 timing was superseded for final UI by U-v2. |
| GUI-1/S/R/I/D, Plan GUI-P/S/F/H/J/K/L/M/N/O/P, AI-1/2, DOC-1/3 | Task shell, Setup/Settings, bounded batch receipts, Fluent controls/icons, rootless Plan table, server selection/highlighting, search/sort/status and installed polish. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md), [TOOLS](TOOLS.md), [BRIDGE](BRIDGE.md); AGENTS and subject docs own the reconciled rules. | Matching CHANGELOG tasks and commits `27f1a6b` through `2cc0083`. GUI-M2 WIP `af02913` and stash `93414b7` were historical preservation; useful folder-total work was rebuilt in `7cf4448`. |
| GUI-W1/WR1 | Native Advanced Color v3 mitigation for specified dark flyout shadows on WCG/HDR displays. [DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md), [BUGS](BUGS.md). | `c637025`, `build/wcg-review-20260924/`. No Windows compositor fix or WCG-only selector proof claimed; Mica remains required. |

The existing 48-pair bound, serial best effort, per-row options, exact uncertain
retry, keyboard/forced-color and admission guarantees remain active. Clearing
a batch receipt does not close a task. The reported Optics refresh delay remains
unprofiled. No completed row authorizes M1-9 inventory projection, M1-10
integrity controls, M1-12 lifecycle closure or release.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps normal review with visible issues. Canceled/abnormal sessions
retain terminal truth without resume, domain retry or session cleanup. Live
pause/resume remains separate. Busy Close requests best-effort cancellation and
keeps the card until settlement/resource release; it never implies trash purge.
Forced process exit has no durable task/resume guarantee.

Capacity refusal before execution, including queued wakeup, retains the task
without execution, automatic retry or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again and requires fresh review. It
never carries old selection/authorization or changes the old artifact. Removing
source/target entries affects capacity only through that fresh scan.

Recognized operation, cleanup and destructive-prerequisite capacity failure
stops later admission after current settlement. Recorder-only write failure
remains recording degradation with continuation. Generic I/O retains its typed
reason. Yellow capacity presentation cannot hide independent known failures.
Trash-location text is accepted for M1; exact count needs complete outcome
evidence. Location-only Details never promises a count, existence or purge.

Location admission is workflow-owned for typed, picker and recent Setup/inventory
inputs. A remembered location is not authorization; consumers re-probe at use.
Setup freezes semantic plan options in a backend-derived snapshot without
writing global defaults or granting browser text/filter normalization authority.

Plan review preserves operation, selection, scope and fresh-preflight truth
across view gestures. Canonical path-key order and complete-sibling filename,
raw size and raw mtime sorting in both directions with reset are accepted M1
behavior. Sort is process-live view state and cannot change selection,
commitment, dependency/execution order, risk/counts or action scope; hierarchy
and node identity survive. [BRIDGE](BRIDGE.md) and [PRESENTATION](PRESENTATION.md)
own exact validation and scale criteria.

Execution, inventory and post-copy overlays remain distinct from each other
and ledger-derived state; zero-byte work that ran never looks unrun. Inventory
warnings stay outside path/action scope; publication is complete or keeps the
prior complete generation. Baseline, verify and rebaseline remain distinct.
Rebaseline requires acknowledgement, includes eligible selected null-evidence
files, creates/replaces evidence after fresh hash and clears verification
freshness without becoming compare-and-accept. Manual exact post-copy
verification uses atomic handoff classification on a ready subset, preserves
execution truth and reports ineligible outcomes honestly.

Release remains accepted. [INTERFACES](INTERFACES.md#sh-g-release-criteria)
owns open SH-G-15 cold-start/repeated/long-workload resource policy, still without
a numeric budget or acceptance artifact. Enforced request/population limits and
separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status describe shipped behavior;
every active DESKTOP_UI acceptance item maps to its subject check or an
explicitly approved deferral. Omission or copied, unmapped checklists do not
close release. BR-G-44: from a clean checkout, run the complete suite including
ordinary-default exclusions, lint-imports and diff checks; collect/pass every
`test_br_g` case without skip/xfail on Windows. Narrow selections do not
substitute for release evidence. [TESTS](TESTS.md) owns commands and routing.
These obligations remain open, with no product release claimed by AB-10.
