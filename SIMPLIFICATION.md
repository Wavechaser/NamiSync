# NamiSync Simplification Proposal

Draft, 2026-08-31, revised the same day after review. **This document is a
proposal, not an authority.** It does
not override `DEFENSE.md`, `ARCHITECTURE.md`, or `FEATURES.md`, and it carries
no checkpoint register, delivery order, or acceptance criteria. It is an
itemized record of what an adversarial audit found removable, why, and what
evidence supports each claim. Sequencing, scoping, and ratification are
separate decisions that have not been made.

Scope of the audit behind it: `core/`, `modules/`, `db/`, `workflows/`,
`dispatcher/`, and `interfaces/`, plus their tests, `tools/`, and the planning
documents. HTML and CSS were deliberately excluded; JavaScript was not.

---

## 1. Why this exists

Adding one field to one core dataclass currently requires touching **20 to 27
files** (measured on `PlanOperation.prior_target_rel_path`, `content_bytes`,
and `blocked_reason`). Roughly half of those touch points are marshaling layers
and the tests of marshaling layers rather than domain logic.

The cause is not any single bad decision. It is that trusted, typed, immutable
values are converted, re-validated, re-shaped, and re-checked at every internal
boundary, so each new feature must satisfy every prior representation. One
`Progress` event is schema-validated **six to eight times**, in two languages,
before a pixel moves.

The measured effect on delivery, from `git log`:

| Week | commits | feat | fix | docs | refactor | feat share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-W33 | 134 | 5 | 10 | 20 | 0 | 3% |
| 2026-W34 | 89 | 17 | 27 | 21 | 4 | 19% |
| 2026-W35 | 131 | 1 | 57 | 33 | 25 | 0% |

The last commit that changed something a user can touch was 2026-08-22.

The purpose of this proposal is to reduce the number of standing obligations
each future change must satisfy, because effort alone cannot compensate for a
cost curve that grows with every completed checkpoint.

---

## 2. Explicitly preserved — not in scope for removal

These were raised in an earlier draft and are withdrawn. Each is implemented
work waiting on a blocked consumer, not dead weight. They are recorded here so
the boundary is explicit.

- **Pause and resume, and `ExecuteContinuation`.** Stop-and-replan is
  functionally equivalent but requires rescanning both roots, re-diffing,
  re-reviewing, and re-selecting; that is a materially worse product, not a
  substitute. The machinery is close to integration and blocked only by the
  checkpoint-4 stall. See §5 for the parts of the pause mechanism that are
  genuinely separable from the feature itself.
- **Volume-scoped concurrency.** `FEATURES.md` already ratifies it: sessions
  whose required resources do not overlap may run concurrently. The actual
  arbitration costs 112 lines in `dispatcher.py` plus 163 in `custody.py` and
  is preserved intact. §8 records a performance limit in how the arbitrated
  resource is identified; it is not a safety defect, and the volume remains
  the correct safety resource.
- **`interfaces/web/visible_sequence.py`.** Plan-unaware tree filtering and
  search returning a bounded window is the correct design; server-side
  windowing is necessary once trees reach the 120,000-row target, because the
  full tree cannot be shipped to the browser and filtered there. It has no
  importer because its consumer is checkpoint 7, which has not started.
- **`NamiSyncService.mutate_selection`.** Revision-guarded deselect and
  reselect with `command_id` idempotency receipts is exactly the shape a
  filter-then-deselect interaction needs, including its conflict and no-op
  handling. Blocked on the same checkpoint.
- **The `annotations` table.** Retained. It has named consumers in
  `FEATURES.md`, so §4 asks only whether the schema is reserved now or added
  with the feature that first writes it.

None of the removals proposed below collide with any of these five. The bulk of
what follows is marshaling and re-validation that sits *beneath* these features
rather than inside them. The one genuine interaction — pause versus payload
serialization — resolves in favour of both, but only under the detached
checkpoint described in §5, not by passing live objects across the dispatcher.

---

## 3. Provably dead — no consumer exists and none is blocked

Distinct from §2: no waiting consumer, no `FEATURES.md` entry, and no
checkpoint that would activate it. This section was the least reliable part of
the first draft and is now mostly a record of what it got wrong; the surviving
claim is one unwired reader.

- **`LedgerRepository.get_run()` and its `RunSnapshot`** — zero production
  callers and zero test callers. This is a reader that was built and never
  wired. Note carefully that this does *not* generalize to the table it reads;
  see the correction below.

**Correction to an earlier draft.** Three items previously listed here were
wrong and have been withdrawn:

- **The ledger `runs` and `operations` tables are live, not write-only.** They
  carry durable uncertain-retry protection that nothing else provides:
  `recorder.py:564` compares `start_payload_hash` on a reused run token and
  raises `TokenConflictError` when the input changed; `recorder.py:633`
  validates start/finish ordering and returns `NOOP` on exact finish replay
  while rejecting a changed one; `recorder.py:1573` does the same for each
  operation token, making evidence mutation and its receipt atomic. Because
  they are durable rather than in-memory, they survive the crash-then-retry
  case that is the entire reason for a run token. `M1_SHELL_H2.md` also
  provisions future manual exact verification on a join through the original
  `runs.run_token`. The claim that these tables are what force
  `RecordingStatus` was also wrong: a filesystem publication can succeed while
  a later inventory or evidence write fails, no matter which schema holds the
  evidence. That independent truth axis is a hard-wall consequence, not schema
  baggage, and it stays. What is genuinely available here is consolidation, not
  deletion — see §7.
- **`runtime_profile_match` is live code.** It is a local boolean in
  `tests/bridge_event_benchmark.py:1936` used in benchmark evaluation, not a
  reference to a removed module.
- **`security_spike` is not a dangling reference.** Its one active-document
  occurrence, `M1_SHELL.md:449`, is a completed delivery step recording the
  rename to `bridge.py`. That prose can be archived with the rest of §10's
  resolved history, but it is not a broken pointer.

---

## 4. Contested — retained pending a product decision

- **The `annotations` table.** An earlier draft called this an unnamed table.
  That was wrong, and the error was mine: it has three named consumers in
  `FEATURES.md` — **Origin Provenance** at line 74, where ingest stamps each
  library file's ledger row with its origin evidence "through the generic
  annotations table"; **Generic Annotations** at line 256, which names the
  `(kind, id, key, value)` shape directly and states its purpose as avoiding a
  schema change each time a new place wants a small label; and **Task
  Annotations** at line 293. It is ratified future work, not a guess.

  What remains genuinely open is narrower and is a matter of taste rather than
  correctness: whether to reserve the schema now or add it with the feature
  that first writes to it. The argument for reserving it is that the table sits
  inside the reset-only ledger-v4 epoch boundary, so adding it later is not
  free either — it is a schema-version event unless it lands before the
  boundary closes. The argument against is that ten lines of DDL with an
  unexercised `CHECK` constraint fix a shape before the first real consumer can
  object to it, and ingest is the consumer most likely to have opinions.
  **Decision needed: reserve a future schema, or not.** This is the only item
  in the document whose answer is a preference rather than an inference.

---

## 5. Mechanical — provable identity, no behavior change

Every item here can be verified by inspection, by an equality check, or by an
ownership test. None changes what a user observes.

- **`workflows/payloads.py` (2,822 lines), `_json_envelope.py` (230), and
  `tests/test_payload_roundtrip.py` (1,876).** `payloads.py` has exactly one
  importer, `workflows/runtime.py`, and exists solely to satisfy
  `PreparedSession.payload: bytes`. The observed behavior is `prepare_plan()`
  calling `encode_plan_request(request)` and `open_plan()` immediately calling
  `decode_plan_request(payload)` in the same call chain on the same thread;
  `decode(encode(x)) == x` was verified empirically.
  `InMemorySessionStore.load_all()` deliberately returns nothing, so no payload
  is ever persisted, restored, or crosses a process boundary.

  **This does not make bytes and objects interchangeable, and an earlier draft
  was wrong to imply it did.** The serialization is doing a second job besides
  transport: it produces a *detached snapshot* that crosses thread ownership.
  `ExecutionSet` in `core/execution.py:327` is `@dataclass(slots=True)`, not
  frozen, and its own docstring calls it "mutable continuation state for
  pause/resume" — `status`, `published_evidence`, and `recording_reasons` are
  live dictionaries, and `omitted_detail_count` and `bytes_done_high_water` are
  live counters. Handing that object to the dispatcher would publish queued and
  paused continuation state through aliases, including through dispatcher
  records, and the round-trip equality check that motivated the original claim
  would not have detected it.

  The correct replacement is a **dispatcher-private, detached, immutable
  checkpoint**: share the immutable `Plan` and the `frozenset` selections by
  reference, freeze or copy the mutable maps, evidence, counters, and
  selections at the boundary, keep continuation authority off the public
  `SessionRecord`, and rebuild fresh mutable workflow state on resume. That
  still deletes essentially all of the JSON encoding and the charge accounting
  below, because none of it is needed to detach an object — but the tests that
  justify it are aliasing and ownership tests, not round-trip equality.
- **The `_charge_*` and `_max_*_charge` accounting** — 991 lines in
  `payloads.py` and 323 in `inventory.py`. Hand-written worst-case byte
  analysis of a JSON encoding that only exists to be undone microseconds later.
  It disappears with the encoding it measures.
- **`WorkflowInvocation.snapshot() -> bytes`.** This is the part of the pause
  mechanism that forces every continuation type through the serializer above.
  Returning a detached immutable checkpoint instead preserves pause completely
  and removes the tax; this is the item that makes §2's first entry cheaper
  rather than costlier. The signature stays a snapshot — what changes is that
  it is detached by construction rather than by encoding.
- **`core/event_v5.py` (837 lines) invoked at construction time.**
  `envelope_to_dict` builds a plain dict from an already-typed frozen dataclass
  and then validates that dict against an independently written schema. The
  validator can only fire if `core/events.py` itself is defective, which is the
  rung-3 case `DEFENSE.md` §2.1 says should be validated once at the owning
  module's public return rather than re-checked downstream.
- **The JavaScript twin of that validator** — `assets/bridge.js` lines
  1720–2360, roughly 641 lines, plus 100 lines of hand-mirrored enum arrays.
  `validateSessionEventV5`, `validateProgressV5`, `validateOperationItemV5`,
  `validateTerminalSummaryV5` and their helpers are a second implementation of
  the same schema, kept in sync by dedicated tests and mutation gates. In
  total, 986 of 2,300 function lines in `bridge.js` (42%) are validators — more
  than half the size of the entire user interface, which is 1,843 lines across
  every other JavaScript module combined. The direction being validated is
  Python to JavaScript, meaning the backend checks its own output in a second
  language. The genuinely untrusted direction, JavaScript to Python, is handled
  separately in `bridge.py` and is preserved.
- **The duplicate `envelope_to_dict` call at `workflows/views.py:481`.**
  `session_event_view` re-serializes and re-validates an envelope that was
  already serialized and validated once on the same path.
- **Five of the six-to-eight validation passes per event.** The full observed
  chain for one `Progress`: dataclass `__post_init__`; `envelope_to_dict`
  validation; the duplicate `envelope_to_dict` in `views.py`;
  `validate_session_event_view_v5`; `drain.py:240`; `drain.py:273`, which
  explicitly re-calls `value.__post_init__()` under the comment "Recheck the
  outer contract"; `bridge.py`'s `_VIEW_VALIDATORS` table on the response; and
  the JavaScript port. Only one of these sits at a real trust boundary.
- **The `adopt_*` and `admit_retained_*` family** in `modules/preflight.py` and
  `core/review.py`. `adopt_plan_verdict` re-runs `type(value) is not Verdict`
  on a `Verdict` that `preflight()` in the same module just returned.
  `admit_retained_plan_verdict` charges `len(refusals) * 8` bytes against a
  memory wall `DEFENSE.md` itself lists as accepted but unrealized, using
  pointer-slot counts as a proxy for Python object memory.
- **The `snapshot_*_authority` / `revalidate_*_authority` / `audit_*_authority`
  triplets** in `core/execution.py` and `core/integrity.py` — the same
  re-adoption pattern applied to execution sets, integrity selections, and
  post-copy selections.
- **`VerifyContinuation.__post_init__`, 147 lines.** It re-derives the set of
  successful byte-producing operation ids from the plan in order to check
  inputs the workflow itself constructed. Separately from its length, it
  bundles four unrelated concerns — execute-to-verify phase handoff, filesystem
  status, recording status, and missing-evidence reconciliation — onto the
  pause mechanism. Those are a phase result, not a continuation.

Aggregate measurement for context: across `core/`, `modules/`, `db/`,
`workflows/`, and `dispatcher/`, functions classified as validate, require,
snapshot, revalidate, audit, projection, or fact total **4,625 lines across 241
functions**, roughly 12% of all function lines in those layers.

---

## 6. Over-built relative to the stated threat model

`DEFENSE.md` §2.1 places installed NamiSync Python inside the trusted computing
base and disclaims confidentiality against the same Windows user. The items
below defend against adversaries the model does not admit.

- **The history event chain, specifically.** Unkeyed hashes cannot authenticate
  against the same Windows user who owns the file and can delete it with one
  command; that is the same category as the confidentiality claim `DEFENSE.md`
  §1.1 already declines. But the decisive argument is narrower and stronger:
  **the chain is never reconstructed from stored events on readback.**
  `history.py:1347` loads `event_chain_hash` from the run row,
  `history.py:1541` advances it with each new receipt, and
  `_prefix_projection_hash_from_row` at `history.py:2745` recomputes the prefix
  projection *from that stored column*. Nothing ever recomputes the chain from
  the event rows it is supposed to attest, so a tampered event row and its
  chain column stay mutually consistent. It is an accumulator that carries
  itself.

  Likely removable, then: the chain accumulator and the stored chain hash; the
  chain-derived prefix machinery, replaceable by explicit state, count, and
  watermark validation; and triggers made redundant by the categorical
  append-only triggers that shadow them.

  Still required, and not proposed for removal: stable run, event, and item
  identity; exact replay distinguished from conflicting replay; transactional
  window publication; the durable prefix watermark; the finalized-versus-
  incomplete distinction; and the minimal database constraints that stop the
  official writer from rewriting finalized history. The incremental pump should
  survive independently of the raw event protocol — it is the part that works.
- **Rung-4 forgery defenses.** The plan and inventory review-limit signals
  carry a private same-run admission token, and `bridge.py` uses a module-level
  `_TASK_DRAIN_ADMISSION_ISSUER = object()` sentinel identity-checked on
  `_AdmittedTaskDrainResponse`. Both prove that an in-process value arrived
  through the intended in-process path. An attacker able to construct those
  objects can call the executor directly, so the defense costs a documented
  policy, two signal types, token plumbing in two workflows, and tests, while
  raising no real adversary's cost.
- **The `readiness.py` challenge handshake.** A `secrets.token_hex` nonce so
  the host can verify the identity of the page it itself just loaded, from a
  CSP-locked local origin it itself bound, into a WebView2 instance it itself
  created.
- **`ui_state.py`'s `MAX_SAFE_INTEGER` guard on the appearance revision
  counter.** Unreachable in roughly 285,000 years of continuous theme toggling.
- **The cosmetic revision and conflict protocol** — `expectedRevision`, and
  `applied` / `noop` / `conflict` dispositions — is optimistic concurrency
  control for a three-value enum in a single-window, single-user application.
  The native layer of `appearance.py` (DWM immersive dark mode, accent palette,
  high contrast) is real work and is not proposed for removal; the revisioned
  persistence protocol wrapped around it is.
- **Two of the three 120,000-row walls.** Planning, inventory, and standalone
  integrity each own an independent constant, count semantics, precedence, and
  first-excess behavior for what `DEFENSE.md` describes as one shared support
  target. Either one shared constant, or none.

---

## 7. Structural — collapse rather than delete

These are net reductions achieved by unifying duplicated mechanisms, not by
removing capability. Each is larger and riskier than §5 and would need its own
scoping.

- **Admission-failure recovery in `dispatcher.py`** — 149 lines covering the
  admission liability flag, the admission cleanup worker, its retries, joins,
  and reaping — plus 67 lines of worker generations, stale-attempt handling,
  and per-session publication locks. This is failure recovery *for admission*,
  distinct from the 275 lines of resource arbitration preserved in §2. Note
  that `_admission_liability_claimed` is a single global boolean that
  serializes admission, so it works against the concurrency feature it sits
  beside.
- **Three stacked session machines.** `dispatcher.Dispatcher` owns
  `SessionState`, worker generations, custody, and replay/subscriber/audit
  capacities of 128/64/64. `interfaces/service.py` owns `SessionObserver`,
  `PlanSession`, and `_SessionReceipt`. `web/drain.py` owns `TaskRegistry`,
  `_TaskState`, its own generations, `_DrainClaim`, `_Compensation`,
  `_TaskCleanup`, `_TaskReservation`, and capacities of 64/48/48. The drain
  layer largely re-implements, for the GUI, the subscription and lifecycle the
  dispatcher already provides. Four id namespaces exist across them:
  `[0-9a-f]{32}`, `task-`, `slot-`, and `ack:`.
- **`_DurableState`'s 37 members, in `modules/executor/runtime.py:246`.** An
  earlier draft said 35 and framed this as motivating a journal and central
  reducer. Both were stale: `_EffectJournalEntry` and `_EffectJournal` already
  exist at `runtime.py:441` and `:452`, `ExecutionState.effects` is already a
  journal field at `:615`, and settlement is already reduced centrally. That
  work is done, and the count is 37.

  What is still available is narrower. Six members —
  `MOVE_STATE_UNVERIFIED`, `TRASH_STATE_UNVERIFIED`, `DELETE_STATE_UNVERIFIED`,
  `UPDATE_STATE_UNVERIFIED`, `MKDIR_STATE_UNVERIFIED`, and
  `RECASE_STATE_UNVERIFIED` — carry identical meaning and differ only by an
  operation kind already present on the operation being settled, and the
  `*_STATE_AMBIGUOUS` members repeat the pattern. Folding those is plausible.
  It will **not** by itself collapse the publication, backup and trash,
  old-target, mutation, ambiguity, and recording facts, which are genuinely
  distinct and are most of the enum. The realistic goal is a simpler fact
  algebra and operation vocabulary, not a small enum. Downstream context for
  why it is worth doing at all: `runtime.py` is 4,946 lines and
  `workflows/sync.py`'s `_run_execution` is 1,131 lines in one function.
- **`tools/executor_settlement_audit.py` (8,602 lines) and
  `tests/test_tools_executor_settlement_audit.py` (2,594).** An independent
  oracle re-implementing settlement policy in order to differentially test it —
  roughly 11,200 lines validating about 1,500 lines of settlement. It is a
  rational response to a state space nobody can hold in their head. Retiring it
  is an outcome, not a first step, and the order matters: simplify the fact
  algebra and operation vocabulary; prove identical normalized traces using the
  existing oracle as the reference; replace the procedural oracle with a much
  smaller, independently authored decision table and invariant suite; and only
  then revise `AGENTS.md` and retire the 11,200-line pair. `AGENTS.md`
  currently forbids deleting it during the executor split, so this is a
  deliberate rules change at the end of that sequence, never a quiet one
  alongside it.
- **The ledger replay receipts, as a consolidation rather than a deletion.**
  Per §3 the `runs` and `operations` tables are load-bearing. What is
  repetitive is the *shape*: run start, run finish, and each operation each
  carry their own bespoke payload-hash comparison, conflict error, and NOOP
  path. One generic durable receipt mechanism — token, payload hash, exact
  replay, changed-payload conflict, atomic mutation-plus-receipt — would cover
  all three. This preserves every property §3 defends and is the only defensible
  reduction in this area.
- **Most of the 37 `*View` types.** One concept, a plan operation, currently has
  six representations: `PlanOperation`, the encode/decode/charge trio in
  `payloads.py`, `operation_projection`, `PlanOperationView`,
  `_validate_operation_item` in `event_v5.py`, and `validateOperationItemV5` in
  `bridge.js`. This is the direct mechanism behind the 20-to-27-file change
  amplification in §1.
- **The `MOVE_UPDATE` operation kind.** A rename combined with a content change
  within one scan interval is rare, and copy-plus-trash reaches the same final
  state on the success path. Removing it retires a continuation type, a verdict
  type, and a settlement branch. `MOVE` and `RECASE` are worth keeping:
  renaming a large file instead of recopying it is a real user benefit, and
  `RECASE` is cheap.

  This is an **accepted behavior change, not an identity refactor**, and an
  earlier draft understated that. Copy-plus-trash differs from a single atomic
  operation during partial failure, cancellation, selection, and audit, so the
  new contract has to be stated rather than assumed: the trash step depends on
  a successful copy; a successful copy with a failed trash truthfully leaves
  both paths present rather than reporting a completed move; rerun and replan
  converge from that state; and presentation may relate the two rows to each
  other without pretending they are still one atomic operation. Accepting those
  four consequences is the decision. If they are acceptable the removal is
  sound; if the paired presentation is not acceptable, keep the kind.

---

## 8. A performance observation inside preserved scope

Not a simplification, and — correcting an earlier draft — **not a correctness
defect either.**

`_volume_resource_key(volume)` returns `f"{volume.serial}:{volume.fs_type}"`,
and `VolumeId` is `(serial, fs_type)`, so the scheduler arbitrates on volume
rather than on physical device. Two partitions of one NVMe or spinning disk get
distinct keys and run concurrently, contending for a single device queue; on a
spinning disk that is slower than running them serially.

That is a throughput property, not a safety one. It creates no namespace
collision and no mutation conflict, and `FEATURES.md:84` ratifies exactly this
scope: sessions whose required *volumes* do not overlap may run concurrently.
The implementation matches its contract. The earlier draft also misattributed
its supporting quote — `FEATURES.md:188` ("a real multi-device or small-file
workload leaving relevant devices underutilized") is the gate on **Conditional
Parallel File Execution**, meaning future file-level workers inside one
session, and says nothing about dispatcher session custody.

Nor is the fix local. Volumes can be virtual, composite, or span multiple
extents, so there is no reliable one-to-one volume-to-spindle map to resolve at
binding time. The sound disposition is to leave the volume as the safety
resource permanently, and treat physical extents — if they are ever resolved at
all — as performance hints layered above it. If M1 ever needs to guarantee
parallelism only across proven-disjoint devices, the conservative rule is that
unknown topology serializes, which is a scheduling policy question for a later
milestone rather than a repair to existing code.

---

## 9. Tests

Test mass is largely downstream of the items above; most of it is expected to
shrink with them rather than needing separate work.

Current shape: 2,633 test functions collecting 5,196 tests, averaging **54
lines per test function**, supported by **16 pytest fixtures in the entire
suite**. Private `_record`, `_plan`, `_operation`, `_stat`, and `_scan` helpers
are re-declared four to ten times across files. Roughly 59,000 of 142,873 test
lines (41%) belong to the interface layer.

- **78 tests, 4,131 lines, asserting on `gc` and `weakref`.** These verify
  CPython reference-counting behavior rather than NamiSync behavior.
- **182 of 693 `monkeypatch.setattr` calls target private, underscore-prefixed
  symbols.** This couples tests directly to implementation internals and is a
  principal reason each refactor costs thousands of test lines.
- **6,772 lines of subprocess gate children** — `_component_gallery_child`,
  `_shell_gate_child`, `_native_gate_child`, `_transport_gate_child`, and
  `_materials_gate_child`. These exist because every protocol invariant
  receives a headed browser test and a subprocess gate; they shrink as the
  protocol shrinks.
- **Tests of scaffolding proposed for removal** — `test_payload_roundtrip.py`,
  `tests/core/test_event_v5_consumers.py`, and the Python-to-JavaScript
  vocabulary mirror and v5 mutation-gate tests. These are correct tests of code
  that would no longer exist. One caveat: `test_payload_roundtrip.py` does not
  vanish without replacement. Per §5 the detached-checkpoint design needs
  aliasing and ownership tests in its place — smaller than 1,876 lines, but not
  zero, and they must exist before the encoder is removed rather than after.

---

## 10. Process and planning

The plan documents are not badly reasoned; every gate traces to a real failure
mode someone thought about. The problem is that each individually justified
obligation becomes a permanent tax on every subsequent checkpoint, and the sum
was never priced.

Measured shape of `M1_PLAN.md` §3: stages 1 through 5.5 total 260 specification
lines; Stage 6 is 631 lines and additionally spawned `M1_SHELL.md` (1,334),
`M1_SHELL_H2.md` (950), and `M1_BRIDGE.md` (5,047) — roughly a 30-to-1 ratio.
Within `M1_SHELL.md`, the delivery sequence is 381 lines and the acceptance
gates are 431.

Within `M1_SHELL_H2.md`, checkpoints 0, 1, 2, 3, 3R, and 4P are complete,
totalling 261 specification lines, and **none of them activated a user
surface**. Every feature lives in checkpoints 5 through 10, all pending, all
gated behind checkpoint 4. Checkpoint 4 alone plus its prerequisite is 178
lines, more than checkpoints 5 through 8 combined at 163 — the foundation costs
more to specify than everything it exists to enable.

- **63 of 83 prose-only gates.** There are 48 BR-G gates, 15 SH-G gates, and 20
  DR-M1 decisions, appearing **384 times in documentation, 38 times in tests,
  and once in production code**. A gate with no collected test node is a
  re-reading obligation rather than a check. Those with real
  `test_br_g_<number>_*` nodes should reduce to a one-line pointer; the rest
  are prose.
- **Checkpoint 4's analytical prerequisite.** Its first delivery step requires
  freezing a complete simultaneous owner graph across task, session, runtime,
  service, dispatcher, observers, subscribers, workers, callbacks, retries,
  close, tombstones, and overlapping generations, each with an exact charge or
  finite retirement witness, plus representation-specific charges for
  codec/text/JSON, Python, CLR/WebView2, browser, and native copies.
  `AGENTS.md` states that a quantified criterion closes only when its search
  domain, procedure, and terminal observation are finite; this search domain is
  not finite, because every added type creates a new owner. It has been
  unratified since at least 2026-08-27. Separately, the checkpoint's stated
  objective is to remove the one-session assumption, while the dispatcher
  already runs disjoint-resource sessions concurrently — what checkpoint 4
  actually builds is the task rail and its retention model.
- **The complete retained-byte and owner-graph walls in `DEFENSE.md` §1.3**
  that checkpoint 4 must satisfy. `DEFENSE.md` already marks them accepted but
  unrealized; they are the unclosable term blocking every remaining feature.
- **The headed-witness and BR-G-production-entry requirement at every
  user-surface activation.** The checkpoint execution protocol requires
  installed headed witnesses "when a user surface activates" and, for each BR-G
  gate, an exact production entry point, counterexample, and collected test
  nodes. Checkpoints that touch no user surface skip both clauses. The effect
  is that work closer to the user costs strictly more, which is inverted for a
  product whose stated first principle is that user experience outranks
  technical preference.
- **Roughly 400 lines of resolved history inside active documents** —
  `M1_PLAN.md` §6 sanity-review notes and its resolved-findings list, and
  `M1_SHELL_H2.md`'s checkpoint-0 audit and resolution record. Both sit inside
  documents an implementer is required to reread before every checkpoint.
  `docs/obsolete/` or `CHANGELOG.md` is the right home.

---

## 11. What is not proposed for removal

Stated so the rest is credible.

- `bridge.py`'s WebView2 hardening: origin binding, the navigation guard,
  new-window blocking, CSP enforcement, and the JavaScript-to-Python command
  envelope bound. This is genuine rung-1 security at a genuine trust boundary.
- The native layer of `appearance.py`: DWM attributes, accent palette, and
  high-contrast handling.
- Atomic publication, fresh preflight, the reviewed dry-run plan, and the
  verifier's cache-honest reads. These are the product.
- The ledger `runs` and `operations` tables and their durable replay and
  changed-payload conflict guards, per §3. Only their bespoke per-site shape is
  proposed for consolidation, in §7.
- `RecordingStatus` as an independent truth axis. Filesystem success and
  durable-evidence success can genuinely diverge; that is a hard wall, not
  schema baggage.
- The history properties listed in §6: identity, exact versus conflicting
  replay, transactional window publication, the durable prefix watermark, the
  finalized-versus-incomplete distinction, the minimal write constraints, and
  the incremental pump. Only the self-carrying chain accumulator is in scope.
- The volume as the concurrency safety resource, per §8.
- The five items in §2.
