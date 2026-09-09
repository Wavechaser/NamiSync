> Archived on 2026-09-06 during documentation ablation. This is historical
> planning/evidence context, not current implementation authority. Current
> subject contracts and the remaining M1 plan live one directory above.
> Original source SHA-256 (before banner and link relocation): CA0625902EBB26A6662D558B68C422D8E795F703D93CF28C93979F5BF880A2CB

# NamiSync Initial Simplification Run

**Standing (2026-09-01): completed delivery record.** This document owns the
closed register, evidence, stop rules, and terminal state for the initial
simplification run. It instantiates `AGENTS.md` **Task Containment And
Recovery**; it does not replace or restate that protocol. The accepted register
was not expanded during implementation.

This is a removal plan. A green suite is necessary but not sufficient because
the same work removes tests and enforcers. Completion therefore requires both
unchanged public behavior and proof that no guarantee lost its last enforcer.
The run fails if complexity is moved into new wrappers, authorities, generic
freezing machinery, duplicate DTOs, compatibility shims, or a replacement
oracle instead of being removed.

---

## 1. Objective and fixed boundary

The run removes two high-fanout mechanisms before any new feature work:

1. Replace process-local workflow JSON payloads with detached immutable domain
   checkpoints.
2. Remove redundant event certification downstream of the domain owner while
   preserving the exact current v5 persisted body.

The behavioral exit is that adding one named domain field no longer requires
editing internal codecs or validators. Source, test, and collected-test counts
are reported trends, never acceptance gates. Atomic outcome, not diff size,
continues to determine commit scope.

### Non-goals

The following are outside every register row even when a removal exposes an
apparently convenient edit:

- the history chain;
- executor fact algebra or settlement restructuring;
- ledger receipt consolidation;
- `MOVE_UPDATE`;
- task-ownership or task-lifecycle restructuring;
- View types beyond the event-certification path in SIM-2;
- a broad `adopt_*`, `snapshot_*_authority`, `revalidate_*_authority`, or
  provenance-token sweep;
- H2 checkpoints 5–8 or any other new feature, including pause/resume
  expansion, volume concurrency changes, `visible_sequence`,
  `mutate_selection`, and annotations.

Existing pause/resume/cancel behavior is a protected regression subject, not a
feature delivered by this run. H2 checkpoint 4 under its former complete owner-
graph and retained-byte rules is retired, not implemented. Later feature work
requires a fresh finite delivery register; this run does not activate a task
surface or any checkpoint-5–8 command or control.

Only five existing BR-G records change in this run: BR-G-10, BR-G-28,
BR-G-33, BR-G-36, and retired BR-G-45. All other gate prose and executable
evidence remain outside the register.

### Architectural decisions

- The four validation rungs in `DEFENSE.md` remain authoritative. External
  validation belongs at filesystem/persistence edges and interface-adapter
  ingress, currently the bridge and CLI and equally any future API.
- Internal contracts are typed domain values. Serialization is allowed only at
  a real process, browser, persistence, or filesystem boundary.
- A concept has at most its domain value and one boundary representation. One
  canonical event body may be wrapped by a separate durable history envelope.
- Dispatcher custody is domain-blind. It holds an opaque checkpoint and does
  not inspect, certify, or reinterpret it.
- Every workflow registration must transfer detached checkpoint custody, treat
  it as read-only, and materialize fresh invocation state on open. Workflow
  constructors establish that obligation; public ownership tests prove it.
- Detachment is a construction property. There is no
  `WorkflowCheckpointAuthority`, `adopt_checkpoint()`, generic checkpoint
  protocol, recursive deep-freeze utility, `deepcopy` framework, pickle, or
  replacement wire format.
- Existing frozen requests are checkpoints where they are already safe.
  Execution may add one narrowly scoped frozen checkpoint that reuses existing
  detached execution and selection snapshots; it must not duplicate their
  fields in another DTO.
- Same-run tokens may retain a freshness or correlation role. They are not
  internal forgery defenses, and removing that role does not authorize losing
  staleness detection.
- Event v5 remains the persistence contract. SIM-2 may remove certification
  but may not change persisted bytes or trigger a data epoch.

---

## 2. Closed checkpoint register

The accepted rows below are the completion denominator. Findings never add a
row.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| `SIM-0` | Ratify this removal contract; close the removal/enforcement ledger; capture stable behavior and v5-body corpora before implementation. | Three identical snapshots with no skipped or unclassified scenario; ordinary suite and import-law baseline; corpus self-test; clean declared diff. | Complete |
| `SIM-1` | Remove process-local workflow payload serialization and replace it with structurally detached semantic checkpoints without changing pause/resume/cancel/settlement behavior or losing real ingress enforcement. | Frozen corpora three times; ownership/aliasing tests; affected departments; ordinary suite; import law; enforcement ledger; test-deletion and relocation audits. | Complete |
| `SIM-2` | Remove redundant event certification while preserving exact v5 persisted bodies, history envelopes, browser delivery/recovery, and reducer behavior. | Frozen corpora three times; byte-for-byte persisted-body check; affected departments and Node probes; ordinary suite; import law; enforcement ledger; test-deletion and relocation audits. | Complete |

### History-admission follow-up register

The closed implementation register above remains unchanged. A post-closeout
review identified one persistence-boundary asymmetry and authorized this
separate finite follow-up before the implementation-time oracle is retired.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| `SIM-F1` | Validate the single event-v5 projection at history admission before persisted-byte serialization, hashing, flushing, or queue mutation, without changing valid persisted bytes, v5-valid receipts under a stricter history byte policy, schema, or data epoch. | Focused invalid-projection no-queue-or-durable-mutation regression; database department; frozen simplification audit with three identical runs and no baseline drift. | Complete |

The existing non-goals still apply. This row does not authorize projector or
EventHub self-certification, another validator, an event representation change,
history migration, or an epoch bump. Persisted-body inequality is the
task-specific stop class; if observed, preserve the work state and stop rather
than updating the frozen baseline.

Verification closed with the focused no-queue-or-durable-mutation regression,
365 passing database-department tests, three identical frozen-audit runs, and
no corpus or baseline drift. No persisted-body inequality was observed.

SIM-0 closed only after its implementation-time corpus and baseline were
committed. No implementation or removable test changed before that point.

---

## 3. Retired implementation-time regression corpora

SIM-0 captured normalized workflow pause/resume/cancel/settlement traces and
canonical event-v5 bytes before removal began. The temporary runner, committed
baseline, and self-test stayed unchanged through SIM-1, SIM-2, and SIM-F1; the
final SIM-F1 check again produced three identical runs with no baseline drift.

Those closed-register artifacts are now retired and deleted. Their enduring
behavior is covered by public workflow/dispatcher ownership tests and focused
history tests. `tests/_event_v5_fixtures.py` remains active shared support for
core, dispatcher, and browser tests; a compact core test compares all seven
body projections plus the review-limit terminal byte-for-byte with those
literal fixtures. No standing corpus rerun, hash, or freeze rule remains.

---

## 4. Regression, defect, and stop routing

A regression during the removal run had two independent limbs:

1. **Behavioral:** the implementation-time corpus produces different output.
2. **Enforcement:** a supported guarantee loses its last enforcer, even with a
   green suite.

For each removed check, the ledger in §5 must name what still enforces the
property or record that the claimed property was not part of the supported
contract.

Route findings through `AGENTS.md`:

- A corpus failure introduced by the active checkpoint was corrected before its
  mergeable commit.
- If the corpus passed but removal exposed a bounded pre-existing defect, that
  defect could land in a separate fix commit only when no stop rule fired.
- Every other finding was logged and deferred.
- A finding never expanded the register.

Classify each unplanned mechanism as `aliasing`, `lost enforcement`,
`representation drift`, or `coverage hole`. Counters are cumulative across this
run. Two findings of one class, or three findings total, stop new work after the
current safety-preserving atomic outcome and require the mechanism table from
`AGENTS.md` before reorganization and review.

In addition to the repository-wide stop classes, stop immediately when:

- resumed execution mutates a checkpoint still in dispatcher custody; this is
  a design failure and must not be patched in place;
- persisted-body inequality is first discovered after an encoder was removed;
  restore the safe state and do not invent an epoch migration; or
- a removed check was the sole enforcer of a `DEFENSE.md` hard wall.

### SIM-1 mechanism stop and reorganization (2026-09-01)

The first adversarial review reached the three-finding stop threshold. Work
stopped before a mergeable SIM-1 commit; the green suite did not waive these
findings.

| Class | Consequence | Owner | Common choke point / reorganization |
| --- | --- | --- | --- |
| `aliasing` | Planning preparation retained the caller's `PlanRequest`; its allowed protocol-typed destination policy could mutate while pending, and the deleted codec had been the only exact identity-policy admission. | `LocalWorkflowRuntime.prepare_plan` | Before resources are derived, require exact `PlanRequest`, `SyncOptions`, and canonical `IdentityDestinationPolicy(name="identity", version="1")`, then retain the callback-free copy from existing planner option-snapshot semantics in one detached `PlanRequest`. Do not add a plan-checkpoint/helper/validator type. |
| `representation drift` | Inventory/integrity `_exact_*_workflow_request` copies were being promoted into checkpoint certifiers and directly tested as such, relocating the removed codec's role. | Inventory/integrity preparation, invocation snapshot, and canceled settlement | Let binding/request constructors produce the checkpoint at prepare; keep the existing workflow-entry copy as the sole run/open materialization; return immutable inventory state directly; construct the next integrity request directly through `replace`; and let canceled settlement read its already-admitted frozen checkpoint without recertification. Move BR-G-28 proof through public runtime preparation/open/snapshot/cancel paths. |
| `coverage hole` | Mechanism-test deletion also removed the last focused wiring for surviving domain guarantees: absence of `worker_count`, invalid execute exclusion cursors, verify completion/order drift, and integrity counter/recording relationships. | Existing planning, execution-continuation, verify-continuation, and integrity-request constructors | Replace every mixed deleted test through direct public domain constructors/properties. Restore only the surviving guarantee; do not preserve a wire version, malformed-JSON path, or codec call order. |

The reorganized SIM-1 repair has three bounded outcomes matching the rows above,
followed by correction of current-contract documentation. Closure requires:

- synchronous planning rejection of subclasses and custom/noncanonical policy,
  post-prepare source-policy mutation that cannot alter custody, and unchanged
  ordinary identity planning;
- a finite search proving `_exact_*_workflow_request` remains only at workflow
  run-entry materialization, zero private-helper checkpoint tests, and public
  prepare/open/reopen/cancel evidence; and
- direct public-domain replacements for every mixed deleted test, including the
  `reported_exclusion_count` Boolean/negative/`MAX_SAFE_INTEGER + 1` matrix,
  with a complete per-name deletion disposition.

No SIM-2 work may start until an independent rereview confirms that these
repairs close the named mechanisms without adding another representation or
certification path.

---

## 5. Closed removal and enforcement ledger

Only the exact mechanisms below may be removed. A newly discovered candidate
is deferred. Private helpers wholly owned by a file listed for deletion travel
with that file; no similarly named helper elsewhere is implied.

| Checkpoint and exact mechanism | Property previously claimed | Disposition | Remaining authority and proof |
| --- | --- | --- | --- |
| SIM-1: complete modules `namisync/workflows/payloads.py` and `namisync/workflows/_json_envelope.py`, including public `encode_plan_request`, `decode_plan_request`, `encode_execution_request`, and `decode_execution_request` | Process-local transport compatibility, byte bounds, and detached continuation state | Remove the internal transport contract. Compatibility and byte bounds are not supported properties inside one process; detachment is real. | Frozen/request constructors enforce domain shape; checkpoint construction snapshots mutable state; ownership tests and the workflow corpus prove detachment and behavior. |
| SIM-1: codec-embedded calls to `core.execution.validate_execution_set` and `workflows.models._exact_verify_continuation` | Mutable execution-overlay validity and exact verify-continuation phase/handoff semantics | **Keep the enforcers.** Move their named invocation to semantic checkpoint construction/open as appropriate; deleting the codec does not delete these checks or their public behavior. | The existing functions remain authoritative; focused construction/open tests plus frozen execute/verify traces prove they still run before unsafe state is used. |
| SIM-1 / BR-G-28: inventory codec entry points `encode_inventory_request`, `decode_inventory_request`, `encode_integrity_request`, `decode_integrity_request`; their codec-only `_charge_inventory_*`, `_charge_integrity_*`, `_payload`, `_json_bytes`, `_mapping`, `_list`, `_unique_object`, `_reject_json_constant`, `_expect_keys`, `_string`, `_integer`, and `_boolean` helpers | Internal inventory/integrity JSON shape, version, wrong-wire-kind separation, and encoded-size admission | Remove. These requests never cross a process or persistence boundary. | Existing frozen workflow-request constructors preserve mode and domain shape; detached checkpoint construction plus real source-population/path and adapter-ingress admission remain. The corpus and public workflow tests prove behavior. |
| SIM-1: `PreparedSession.payload: bytes`, `WorkflowInvocation.snapshot() -> bytes`, `WorkflowRegistration.open(bytes)`, `SessionRecord.payload`, dispatcher `_replace_payload`, and the byte-type branches attached to them | Opaque dispatcher custody and pause detachment | Replace only the representation and names needed to carry an opaque semantic checkpoint. | Frozen checkpoint construction is the enforcer; dispatcher must not inspect it. Mutation-after-snapshot and repeated-open tests prove non-aliasing. |
| SIM-1: `LocalWorkflowRuntime` calls to the eight codec entry points and `_PlanInvocation.snapshot`, `_ExecutionInvocation.snapshot`, `_InventoryInvocation.snapshot`, `_IntegrityInvocation.snapshot` byte returns | Workflow reopen receives a complete request/continuation | Retain snapshot/open behavior while removing encoding. | One checkpoint-construction and one materialization/open path per workflow; frozen traces prove exact observable behavior. |
| SIM-1: internal payload-version, duplicate-key, malformed-JSON, charge-ceiling, and round-trip checks rooted in `tests/test_payload_roundtrip.py` and the codec-only blocks in inventory/resume tests | Compatibility with arbitrary process-local bytes | Not a supported property after the wire form is deleted. | Any test that also covers selection, provenance, freshness, path/population bounds, cancellation, recording, or settlement must be replaced at a public surface or retained. Zero uncovered behavior is permitted. |
| SIM-1: any forgery interpretation attached to plan/inventory same-run signal tokens | Resistance to forged first-party private values | Remove only the unsupported forgery role; do not sweep the token mechanism. | Same-run freshness/correlation remains until separately adjudicated. Exact first-excess behavior and real boundary admission remain tested. |
| SIM-2: the `validate_event_v5_envelope(...)` self-check inside `core.events.envelope_to_dict` | A typed domain producer certifies its own projected output; today the same call is also the sole enforcer of `MAX_RELIABLE_EVENT_CANONICAL_BYTES` | Remove semantic encode-time recertification, not the canonical projector, persistence validator, or byte wall. Before that call is removed, `canonical_event_bytes` must explicitly enforce the maximum before `EventHub` sequence/replay/subscriber mutation. | Supported typed producer paths own live semantics and `envelope_to_dict` is the sole domain-to-v5 projector; one retained `validate_event_v5_envelope` contract is reused at history admission and decode/readback; `canonical_event_bytes` becomes the named byte-wall enforcer; exact bytes and first-excess behavior are frozen. |
| SIM-2: `core.event_v5.validate_session_event_view_v5` and `workflows.views.validate_session_event_view` | Downstream Python layers independently certify event-body semantics | Remove. Trusted internal projections do not independently reinterpret domain truth. | Canonical projector plus history-admission/readback validation; browser transport-envelope checks; frozen body and delivery corpora. |
| SIM-2: the duplicate event-body projection/revalidation in `workflows.views.session_event_view` | Presentation reconstructs and certifies the body | Reuse the one canonical body mapping while retaining the distinct live `sequence` wrapper, persisted `seq` envelope, and durable history envelope. | Exact corpus bytes and public view tests. |
| SIM-2: event-body calls in `interfaces.web.drain._validate_task_observation`, `validate_task_update_view`, and `validate_task_drain_view` | Drain/task layers certify body fields again | Remove only body-semantic certification. Keep task/session matching, wrapper shape, exact-integer positivity, batch, ordering, and lifecycle checks; the bridge response snapshot is the sole Python-side pre-serialization JavaScript-safe upper-bound enforcer, while browser transport admission independently retains PositiveSafeInt. | Reduced transport-wrapper checks and existing drain/recovery/reducer tests. |
| SIM-2: the `SessionEventView` `_VIEW_VALIDATORS` entry and event-semantic traversal in `interfaces.web.bridge`; do not remove validators for unrelated command/result types | Native response traversal certifies trusted event bodies | Remove event semantic recertification while preserving response ownership, JSON bounds, projection, and retained wrapper/record/result validators. | Bridge response budget/ownership checks and browser transport checks remain. |
| SIM-2: JavaScript `validateSessionEventV5`, `validateProgressV5`, `validateOperationItemV5`, `validateTerminalSummaryV5`, and their body-semantic-only private helper closure | Browser independently implements Python's event schema | Replace with one minimal transport-envelope check: plain object, retained exact wrapper shape, v5 marker, matching session, positive safe sequence, recognized body tag, object body, and atomic batch staging. | The supported Python producer path owns body semantics; browser delivery/reducer probes prove transport and behavior. |
| SIM-2: Python-to-JavaScript vocabulary mirrors and v5 body mutation gates | Two independent semantic implementations stay synchronized | Remove only tests of deleted certification. | Valid reducer/lifecycle cases, persistence corruption negatives, receipt/hash checks, and boundary-envelope rejection remain. Zero uncovered behavior is permitted. |

`validate_event_v5_envelope` at history admission/readback, history receipt/hash/
watermark checks, all JavaScript-to-Python command validation, filesystem
freshness, bridge origin/security rules, complete external-request bounds, and
active scalar/population/handler/queue walls are explicitly kept.
`MAX_RELIABLE_EVENT_CANONICAL_BYTES` is likewise kept and must never have a
window in which size is checked only after sequence or queue mutation.

---

## 6. Test deletion rule

Tests traveled with their removed mechanism in the same commit. During SIM-1
and SIM-2, the temporary corpora removed the need for an artificial intermediate
green-suite commit but did not authorize deleting unique coverage.

For every deleted test, record one disposition:

- `mechanism-removed`, when it asserts only the deleted internal contract; or
- `public-replacement`, naming the public-surface test that preserves the real
  guarantee.

A test that is the only node for a surviving gate or `DEFENSE.md` hard wall may
be deleted only through `public-replacement`. The knowingly-uncovered allowance
for this run is **zero**. A test that is eligible for deletion but cannot meet
that rule remains in place and is listed in the checkpoint recap for a later
test-specific removal run.

### SIM-1 deleted-test dispositions

The closed denominator is **99 deleted test functions**: **67
`public-replacement`** and **32 `mechanism-removed`**. Mixed tests are classified
as `public-replacement` when any real guarantee survives; their deleted
wire-only assertions do not create a second disposition.

#### `public-replacement`

`tests/core/test_session_events.py`:

- `test_session_record_payload_exists_only_while_nonterminal` ->
  `test_session_record_checkpoint_exists_only_while_nonterminal`.
- `test_stored_session_record_rejects_payload_and_live_reference_fields` ->
  `test_stored_session_record_rejects_checkpoint_and_live_reference_fields`.
- `test_stored_session_record_can_represent_every_lifecycle_without_payload` ->
  `test_stored_session_record_can_represent_every_lifecycle_without_checkpoint`.

`tests/dispatcher/test_dispatcher.py`:

- `test_pause_releases_custody_and_resume_reopens_snapshotted_payload` ->
  `test_pause_releases_custody_and_resume_reopens_snapshotted_checkpoint`.
- `test_paused_resumed_terminal_paths_scrub_continuation_payload` ->
  `test_paused_resumed_terminal_paths_scrub_continuation_checkpoint`.
- `test_terminal_close_releases_payload_while_scheduler_stays_alive` ->
  `test_terminal_close_releases_checkpoint_while_scheduler_stays_alive`.
- `test_payload_is_passed_to_adapter_without_dispatcher_decoding` ->
  `test_checkpoint_is_passed_to_adapter_by_identity`.
- `test_failed_terminal_store_write_does_not_retain_workflow_payload` ->
  `test_failed_terminal_store_write_does_not_retain_workflow_checkpoint`.

`tests/test_bridge_resume.py`:

- `test_br_g_10_payload_roundtrip_preserves_direct_and_fallout_outcomes` ->
  `test_br_g_10_checkpoint_preserves_direct_and_fallout_outcomes`.
- `test_br_g_10_tampered_real_verify_resume_finishes_the_original_run` ->
  `test_br_g_10_tampered_execute_and_verify_resume_fail_before_preflight`,
  `test_resumed_execute_preflight_refusal_finishes_existing_partial_run`, and
  `test_real_resumed_verify_preflight_refusal_finishes_existing_run`.

`tests/test_bridge_scan_scope.py`:

- `test_br_g_28_inventory_and_integrity_payload_versions_are_kind_aware` ->
  `test_br_g_28_inventory_and_integrity_checkpoints_are_detached_and_exact`.

`tests/test_inventory_workflow.py`:

- `test_inventory_encoders_revalidate_forged_exact_requests_before_projection`
  -> `test_inventory_direct_entries_revalidate_before_resolver_or_ledger_work`,
  `test_workflow_request_id_uses_complete_external_text_wall`, and
  `test_scan_scope_combined_source_population_has_exact_preallocation_wall`.
- `test_inventory_decode_counts_combined_scope_before_text_projection` ->
  `test_scan_scope_combined_source_population_has_exact_preallocation_wall`.
- `test_inventory_payload_decoding_rejects_escaped_surrogates` ->
  `test_inventory_workflow_request_rejects_surrogate_code_units`,
  `test_cli_ingress_rejects_non_exact_or_unencodable_arguments`, and
  `test_br_g_32_strict_prehandler_refusal_matrix_returns_exact_envelopes`.
- `test_inventory_and_integrity_payloads_round_trip_continuation` ->
  `test_br_g_28_inventory_and_integrity_checkpoints_are_detached_and_exact`,
  `test_integrity_snapshot_orders_completed_rows_by_frozen_selection`,
  `test_paused_integrity_snapshot_persists_recorder_close_degradation`, and
  `test_paused_verify_resumes_without_repeating_or_losing_items`.
- `test_integrity_v2_codec_rejects_invalid_authority_scalars` ->
  `test_integrity_checkpoint_enforces_recording_relationships`,
  `test_integrity_request_rejects_boolean_counters`,
  `test_integrity_request_rejects_non_integer_counter_types`, and
  `test_integrity_request_rejects_out_of_domain_counters`.
- `test_integrity_v2_codec_requires_exact_authority_shape` ->
  `test_integrity_continuation_rejects_progress_without_saved_selection`.
- `test_integrity_codec_rejects_progress_without_saved_selection` ->
  `test_integrity_continuation_rejects_progress_without_saved_selection`.
- `test_inventory_preprojection_rejects_combined_scope_n_plus_one` ->
  `test_scan_scope_combined_source_population_has_exact_preallocation_wall`.
- `test_integrity_preprojection_rejects_population_n_plus_one` ->
  `test_integrity_continuation_refuses_excess_before_duplicate_copies`.
- `test_inventory_preprojection_readmits_nested_volume_text` ->
  `test_volume_root_profile_and_warning_source_bounds_are_exact`.

`tests/test_payload_roundtrip.py`:

- `test_plan_request_round_trips_latent_source_casing_policy` ->
  `test_prepare_plan_retains_a_detached_identity_checkpoint`,
  `test_source_casing_propagation_is_opt_in_and_plans_zero_byte_recase`, and
  `test_opt_in_recase_runs_end_to_end_without_copying_or_trashing`.
- `test_plan_request_decode_rejects_n_plus_one_filters` ->
  `test_filter_contract_charges_raw_shape_before_canonicalization`.
- `test_plan_request_requires_fingerprinted_source_casing_policy` ->
  `test_source_casing_propagation_is_opt_in_and_plans_zero_byte_recase`.
- `test_worker_count_is_absent_from_contracts_and_payloads` ->
  `test_plan_domain_contracts_have_no_worker_count`.
- `test_plan_request_encoding_rejects_surrogate_code_units` ->
  `test_cli_ingress_rejects_non_exact_or_unencodable_arguments` and
  `test_br_g_32_strict_prehandler_refusal_matrix_returns_exact_envelopes`.
- `test_plan_request_decoding_rejects_escaped_surrogates` -> those same two
  external-ingress tests.
- `test_execution_request_preserves_the_old_execution_set_keyword` ->
  `test_execution_request_preserves_execution_set_keyword`.
- `test_execution_request_rejects_non_utc_start_times` ->
  `test_execution_request_requires_utc_start`.
- `test_execution_payload_is_a_lossless_round_trip` ->
  `test_execution_checkpoint_detaches_and_reopens_independent_state`.
- `test_execution_validation_requires_exact_content_evidence_shape` ->
  `test_execution_validation_requires_exact_evidence_shape`.
- `test_execution_mutable_contradictions_fail_before_projection` ->
  `test_execution_validation_rejects_mutable_overlay_contradictions`.
- `test_execution_v7_round_trips_the_reported_exclusion_count` ->
  `test_execution_checkpoint_detaches_and_reopens_independent_state`.
- `test_execution_v7_rejects_invalid_reported_exclusion_counts` ->
  `test_execute_continuation_rejects_invalid_reported_exclusion_count`.
- `test_execution_payload_preserves_full_width_file_identity_as_text` ->
  `test_file_index128_text_round_trip_preserves_full_width`.
- `test_execution_payload_file_identity_preserves_exact_error_family` ->
  `test_file_index128_decoder_rejects_numeric_and_noncanonical_values` and
  `test_decimal_decoder_overflow_preserves_exact_error_family`.
- `test_execution_set_byte_high_water_is_bounded_and_strictly_monotonic` and
  `test_execution_set_exposes_public_byte_high_water_state` ->
  `test_execution_byte_high_water_is_bounded_and_monotonic`.
- `test_execution_set_replace_and_equality_use_only_public_high_water` ->
  `test_execution_byte_high_water_is_bounded_and_monotonic` and
  `test_execution_checkpoint_detaches_and_reopens_independent_state`.
- `test_execution_set_rejects_invalid_initial_byte_high_water` ->
  `test_execution_set_rejects_invalid_initial_high_water`.
- `test_execution_payload_round_trips_canonical_user_deselection` ->
  `test_br_g_10_checkpoint_preserves_direct_and_fallout_outcomes`.
- `test_execution_payload_v7_keeps_progress_and_recording_attribution` ->
  `test_execution_checkpoint_detaches_and_reopens_independent_state`.
- `test_execution_payload_v7_pins_closed_recording_reason_vocabularies` ->
  `test_br_g_33_browser_event_vocabulary_matches_python_owners`.
- `test_task_recording_issues_retain_first_reason_in_observation_order` and
  `test_task_recording_issue_omits_overlimit_detail_without_truncation` ->
  `test_task_recording_issues_keep_order_and_omit_overlimit_detail`.
- `test_execution_payload_rejects_invalid_byte_high_water` ->
  `test_execution_set_rejects_invalid_initial_high_water`.
- `test_verify_continuation_is_a_lossless_round_trip` ->
  `test_execution_checkpoint_detaches_and_reopens_independent_state`.
- `test_verify_continuation_rejects_contradictory_truth_axes` ->
  `test_verify_continuation_rejects_truth_candidate_and_evidence_drift`.
- `test_verify_continuation_accepts_only_a_bounded_canonical_execute_error` ->
  `test_verify_continuation_bounds_the_complete_execute_error` and
  `test_verify_continuation_detaches_and_revalidates_execute_phase`.
- `test_verify_continuation_snapshots_phase_subclasses_without_hidden_graphs`,
  `test_verify_continuation_phase_snapshot_breaks_the_source_alias`, and
  `test_verify_continuation_rejects_a_forged_phase_instance` ->
  `test_verify_continuation_detaches_and_revalidates_execute_phase`; the last
  is also covered by `test_run_execution_revalidates_direct_verify_continuations`.
- `test_execution_encoder_revalidates_mutated_verify_phase` ->
  `test_verify_continuation_detaches_and_revalidates_execute_phase`,
  `test_run_execution_revalidates_direct_verify_continuations`, and
  `test_canceled_settlement_revalidates_direct_verify_continuation`.
- `test_verify_continuation_rejects_unknown_completion_and_candidate_drift` ->
  `test_selection_completion_uses_one_index_lookup_without_tuple_scan`,
  `test_verify_continuation_rejects_truth_candidate_and_evidence_drift`, and
  `test_verify_continuation_rejects_candidates_out_of_plan_order`.
- `test_execution_set_rejects_published_evidence_on_non_byte_operation`,
  `test_execution_set_rejects_identityless_evidence_with_only_a_task_issue`,
  `test_execution_set_rejects_record_failure_with_a_durable_identity`,
  `test_execution_set_rejects_recorded_identity_drift_from_run_or_operation`,
  and `test_execution_set_rejects_recorded_identities_from_multiple_locations`
  -> `test_execution_validation_rejects_mutable_overlay_contradictions`.
- `test_execution_set_accepts_identityless_evidence_for_that_record_failure` ->
  `test_execution_validation_accepts_attributed_identityless_evidence`.
- `test_root_contract_rejects_surrogate_code_units` -> same-named test in
  `tests/test_workflow_domain_checkpoints.py`.
- `test_execution_payload_decoding_rejects_escaped_surrogates` ->
  `test_root_contract_rejects_surrogate_code_units`,
  `test_cli_ingress_rejects_non_exact_or_unencodable_arguments`, and
  `test_br_g_32_strict_prehandler_refusal_matrix_returns_exact_envelopes`.
- `test_execution_payload_preserves_scalar_unicode_and_commitment` ->
  `test_cli_ingress_bound_uses_complete_utf8_byte_size`,
  `test_execution_checkpoint_detaches_and_reopens_independent_state`, and
  `test_execution_refuses_plan_content_that_no_longer_matches_fingerprint`.
- `test_decoded_plan_recomputes_the_same_fingerprint` ->
  `test_execution_checkpoint_detaches_and_reopens_independent_state` and
  `test_execution_refuses_plan_content_that_no_longer_matches_fingerprint`.
- `test_round_tripped_committed_set_would_not_refuse` ->
  `test_br_g_10_checkpoint_preserves_direct_and_fallout_outcomes` and
  `test_execution_refuses_plan_content_that_no_longer_matches_fingerprint`.

`tests/test_post_execution_workflow.py`:

- `test_noncompound_execute_exception_uses_execution_continuation_bytes` ->
  `test_noncompound_execute_exception_uses_execution_checkpoint_counters`.
- `test_dispatcher_compound_exclusion_close_failure_survives_payload_scrub` ->
  `test_dispatcher_compound_exclusion_close_failure_survives_checkpoint_scrub`.

#### `mechanism-removed`

`tests/test_inventory_workflow.py`:

- `test_inventory_json_rejects_nested_surrogate_code_units`.
- `test_inventory_payload_preserves_scalar_unicode_and_literal_escapes`.
- `test_inventory_and_integrity_codecs_reject_coercive_or_ambiguous_json`.
- `test_inventory_codec_raw_ceiling_precedes_decode_and_json_parse`.
- `test_inventory_codec_occurrence_ceiling_precedes_projection_without_mutation`.
- `test_inventory_codec_rechecks_exact_final_byte_length`.

`tests/test_payload_roundtrip.py`:

- `test_old_workflow_payload_is_refused_after_contract_change`.
- `test_plan_v5_and_execution_v7_are_independent_exact_payloads`.
- `test_workflow_json_rejects_nested_surrogate_code_units`.
- `test_plan_request_preserves_scalar_unicode_and_literal_escapes`.
- `test_workflow_payload_rejects_non_json_numeric_constants`.
- `test_execution_validation_and_encoding_do_not_rebuild_valid_graphs`.
- `test_execution_encoder_orders_charge_validation_and_projection`.
- `test_execution_payload_requires_exact_byte_high_water_field`.
- `test_execution_payload_v7_rejects_unknown_raw_item_recording_reason`.
- `test_execution_payload_v7_rejects_unknown_raw_task_recording_reason`.
- `test_execution_payload_v7_rejects_aggregate_recording_contradictions`.
- `test_execution_payload_requires_exact_user_deselection_field`.
- `test_execute_and_verify_payloads_have_exact_phase_branches`.
- `test_execution_payload_rejects_missing_unknown_and_contradictory_phase_fields`.
- `test_execution_payload_rejects_partial_recording_identities`.
- `test_verify_continuation_reads_the_source_phase_name_once`.
- `test_execution_v7_refuses_hostile_verify_execute_errors`.
- `test_workflow_payload_raw_ceiling_precedes_decode_and_json_parse`.
- `test_plan_occurrence_ceiling_precedes_json_projection`.
- `test_execution_occurrence_ceiling_precedes_projection_without_mutation`.
- `test_plan_preprojection_readmits_forged_filter_source`.
- `test_workflow_encoder_rechecks_exact_final_byte_length`.
- `test_verify_candidate_walk_charges_every_repeated_root_occurrence`.
- `test_object_layout_charges_each_schema_key_string_occurrence`.
- `test_encoding_is_deterministic_and_order_independent`.

`tests/test_workflows.py`:

- `test_frozen_execution_v6_payload_is_rejected`.

### SIM-2 deleted-test dispositions

The closed denominator is **20 deleted or renamed test functions**: **15
`public-replacement`** and **5 `mechanism-removed`**. The same-name EventHub
byte-wall test only gained a parameterized signature and is not counted as a
deletion. The knowingly-uncovered count is **zero**.

#### `public-replacement`

- `test_dormant_v5_session_view_rejects_another_session` -> the wrong-session
  cases in `test_task_offer_validates_before_queue_or_custody_mutation` and
  `test_br_g_36_node_drain_validates_transport_before_batch_delivery`.
- `test_public_v5_view_enforces_canonical_envelope_byte_ceiling` and
  `test_required_node_reliable_ceiling_uses_the_public_envelope_bytes` ->
  `test_reliable_oversize_refuses_before_sequence_queue_or_audit_mutation`,
  parameterized over ASCII/control-escaped and mixed-Unicode exact-wall bodies.
- `test_live_node_v5_consumer_accepts_and_rejects_the_exact_target`,
  `test_required_node_consumes_real_python_public_view_codec`, and
  `test_required_node_live_events_accept_only_v5_and_canonical_scalars` ->
  `test_required_node_accepts_each_canonical_python_event_projection`,
  `test_br_g_36_node_drain_validates_transport_before_batch_delivery`, and the
  retained persistence-decoder scalar/version cases.
- `test_required_node_operation_truth_matches_public_python_projections` ->
  `test_required_node_operation_result_keeps_cancellation_truth` and the
  retained persisted-Terminal cancellation corpus.
- `test_required_node_uses_the_shared_timestamp_grammar_and_calendar` ->
  `test_required_node_session_record_keeps_timestamp_boundary` and
  `test_v5_timestamp_grammar_and_calendar_are_exact`.
- `test_required_node_preserves_logical_byte_review_facts` ->
  `test_required_node_operation_result_keeps_review_fact_truth` and the
  retained persisted-Terminal review-limit corpus.
- `test_required_node_canonical_byte_inputs_require_real_unicode` ->
  `test_reliable_v5_canonical_bytes_require_real_unicode` and the mixed-Unicode
  EventHub byte-wall parameter.
- `test_br_g_33_browser_event_vocabulary_matches_python_owners` and
  `test_v5_vocabulary_gate_rejects_changed_sets` ->
  `test_browser_bridge_and_public_result_vocabularies_match_python_owners` for
  surviving result/record vocabularies plus the seven production projections
  for live event tags.
- `test_br_g_36_live_event_validator_is_current_only_and_not_for_history` ->
  `test_browser_bridge_and_public_result_vocabularies_match_python_owners`,
  `test_br_g_36_node_drain_validates_transport_before_batch_delivery`, and the
  retained persistence decoder cases.
- `test_br_g_36_node_drain_validates_progress_before_batch_delivery` -> renamed
  `test_br_g_36_node_drain_validates_transport_before_batch_delivery`, which
  retains transport, atomic staging, reducer, replay, and real-producer evidence.
- `test_transport_gate_live_fixtures_match_exact_v5_contract` -> renamed
  `test_transport_gate_live_fixtures_use_typed_public_views`; headed transport
  still consumes the production projection without recertifying body semantics.

#### `mechanism-removed`

- `test_final_protocol_stop_routes_the_live_browser_through_exact_v5`.
- `test_event_route_gate_rejects_in_memory_source_mutations`.
- `test_v5_vocabulary_gate_rejects_changed_detail_classes`.
- `test_br_g_36_browser_progress_validator_owns_the_expanded_exact_shape`.
- `test_v5_progress_gate_rejects_in_memory_active_validator_mutations`.

### Oracle-retirement deleted-test dispositions

This subsection is a historical deletion ledger. Its test names identify what
was removed and do not name live test paths or standing rerun requirements.

The retirement denominator is **3 deleted test functions**: **2
`public-replacement`** and **1 `mechanism-removed`**. This is separate from the
119-function SIM-1/SIM-2 denominator above. The knowingly-uncovered count
remains **zero**.

#### `public-replacement`

- `test_event_corpus_freezes_all_v5_bodies_and_exact_reliable_wall` ->
  `test_canonical_v5_projection_preserves_exact_literal_body_bytes`,
  `test_dormant_reliable_ceiling_accepts_the_exact_bound_and_refuses_one_more`,
  and `test_reliable_oversize_refuses_before_sequence_queue_or_audit_mutation`.
- `test_committed_simplification_corpus_matches_production` ->
  `test_paused_baseline_and_rebaseline_resume_without_repeating_or_losing_items`,
  `test_paused_verify_resumes_without_repeating_or_losing_items`,
  `test_paused_integrity_cancel_uses_exact_continuation_without_reopening`,
  `test_xv_8_pause_resume_runs_linked_verify_and_retains_terminal_history`,
  `test_br_g_10_dispatcher_pause_resume_reopens_the_same_run`,
  `test_dispatcher_paused_execute_cancel_finishes_same_run_without_verify`,
  `test_dispatcher_paused_verify_cancel_uses_runtime_compound_settlement`, and
  the exact-v5 public replacements above.

#### `mechanism-removed`

- `test_frozen_corpus_paths_are_closed_and_present`; the closed-register
  artifact-presence policy ended when the temporary oracle was retired.

---

## 7. Complexity-relocation failure audit

Record the pre-change mechanism graph and repeat it after SIM-1 and SIM-2.
The fixed comparison point is SIM-0 plan commit
`83e5da140444e14111cc5389d0e03caff6eaa877`:

| Path | Pre-change production nodes | Pre-change test/support nodes | Required terminal change |
|---|---|---|---|
| Internal workflow transport | Eight `encode_*_request`/`decode_*_request` entries across `workflows/payloads.py` and `workflows/inventory.py`; shared `_json_envelope.py`; runtime codec calls; byte/charge machinery | Seven referencing files: `test_bridge_resume.py`, `test_bridge_scan_scope.py`, `test_inventory_runtime.py`, `test_inventory_workflow.py`, `test_payload_roundtrip.py`, `test_post_execution_workflow.py`, and `test_workflows.py` | Zero internal codec entries, JSON-envelope helpers, payload limits/charges, or codec references; retained semantic cases use public checkpoint/workflow surfaces. |
| Dispatcher custody | Byte/payload contracts in `core/session.py`, `dispatcher/contracts.py`, `dispatcher/dispatcher.py`, `interfaces/service.py`, `workflows/models.py`, and `workflows/runtime.py` | Payload-oriented custody assertions in the seven files above and dispatcher/session tests | One opaque checkpoint custody path, one construction path and one open/materialization path per workflow; no compatibility alias or generic checkpoint layer. |
| Event certification | Semantic body checks in `core/event_v5.py`, `core/events.py`, `workflows/views.py`, `interfaces/web/drain.py`, `interfaces/web/bridge.py`, and `interfaces/web/assets/bridge.js` | Six referencing support/test files under `tests/core`, `tests/assets`, and `tests/interfaces/web` | One domain-to-v5 projector, one history-boundary validator reused at admission and readback, the explicit reliable-event byte wall, and a minimal browser transport-envelope check; no downstream body-semantic twin. |

The file sets above come from finite `git grep -l` searches for the eight codec
entry names and the named Python/JavaScript event validators at that commit.
Final evidence repeats the same searches at the completed HEAD and records the
remaining symbols; renamed equivalents count as surviving nodes.

### SIM-1 terminal observation (2026-09-01)

- Eight internal codec entry points across three production files, 15 runtime
  codec calls, and 134 codec/JSON helper functions fell to zero. The deleted
  `_json_envelope.py` and `payloads.py` have no remaining imports or aliases.
- Plan, inventory, and standalone-integrity custody reuse their existing frozen
  semantic requests. Execution adds only `ExecutionCheckpoint`, two private
  phase-delta records, and one typed post-copy snapshot helper; the checkpoint
  is referenced only by `workflows/models.py` and `workflows/runtime.py`.
  Searches found no replacement schema, version, JSON/codec, generic freezer,
  checkpoint validator, authority/adoption API, `deepcopy`, or pickle path.
- The two pre-existing inventory `_exact_*_workflow_request` helpers have
  exactly two definitions and two workflow run-entry calls, with no checkpoint
  or test use. Nine runtime `type(checkpoint)` branches perform constant routing
  only; execution reconstruction remains centralized in one `materialize()`.
- Production changed by 288 additions and 4,084 deletions (net -3,796). Test
  source changed by 1,239 additions and 2,873 deletions (net -1,634); the 99
  deleted tests have the complete dispositions in §6. Collected tests moved
  from 5,236 to 5,123. These are trend observations, not acceptance gates.
- At the SIM-1 checkpoint, the temporary audit passed three identical runs and
  its four artifacts matched the committed baseline. Focused checkpoint tests
  passed 948 cases; the affected departments passed 3,699 with one skip; the
  ordinary suite passed 5,091 with four skips and 28 headed deselections.
  Import analysis improved from 77 files/346 dependencies to 75/333 while all
  11 contracts remained kept.
- Independent stop-repair rereview and a separate relocation audit found no
  remaining lost enforcement, replacement certification path, scope drift, or
  new feature work. The three recorded findings stay counted; they were closed,
  not erased from the audit history.

### SIM-2 stop and reorganization record (2026-09-01)

The deletion audit reached the predeclared three-of-any-kind stop threshold:
three mixed-purpose test cuts would have removed surviving coverage along with
the event-body certifier. No additional removal candidate was started. The
current atomic SIM-2 outcome was reorganized around these owners, then
independently rereviewed before broad verification resumed.

| Consequence | Owner retained after reorganization | Common choke point |
| --- | --- | --- |
| The seven-family Node witness used hand-built dictionaries rather than the production projector. | `test_required_node_accepts_each_canonical_python_event_projection` now runs `envelope_from_dict` → `session_event_view` → `to_primitive_view` before Node. | The one Python domain-to-live-view projection path. |
| Event-only vocabulary tests also owned surviving public result/record arrays and bridge schema use. | One narrow static owner test retains only those result/record vocabularies and bridge-envelope assertions. | The surviving public result/record validators and bridge envelope. |
| Removing the browser byte-ceiling matrix left mixed-Unicode first-excess behavior without a pre-mutation witness. | The EventHub hard-wall test now covers both frozen ASCII/control-escaped and mixed-Unicode factories. | `canonical_event_bytes` before every EventHub mutation. |

These are three `coverage hole` findings under one causal mechanism: deleting a
mixed-purpose test as though every assertion belonged to the removed
certifier. Their public replacements landed before any test was deleted from a
mergeable commit. Independent rereview found no remaining last-enforcer loss.

### SIM-2 terminal observation (2026-09-01)

- The downstream Python event-view validators, projector self-certification,
  bridge `_VIEW_VALIDATORS` `SessionEventView` entry, JavaScript semantic event
  validators, and their body-only helper closure are gone. Finite searches find
  none of the deleted names in production or active tests.
- Event flow now has one domain-to-v5 projector, one exact history-boundary
  validator reused at admission and readback, one explicit reliable-byte wall,
  and one browser transport check. The browser retains exact wrapper/session/v5/tag/positive
  SafeInt/body-object admission, Gap routing, atomic staging, and reducer
  behavior; public result/record validators remain separate.
- No database file changed. Event schema 5, ledger 4, history 6, data epoch 6,
  history envelopes, receipts, hashes, and watermarks are unchanged. At SIM-2
  close, the temporary corpus passed three identical runs and its four
  artifacts matched the committed baseline.
- Production changed by 65 additions and 597 deletions (net -532). Test source
  changed by 252 additions and 1,221 deletions (net -969); all 20 deleted or
  renamed functions have dispositions in §6 and knowingly-uncovered remains
  zero. Collected tests moved from 5,123 to 4,913. These are reported trends,
  not acceptance gates.
- Focused event/history/bridge/Node verification passed 1,223 cases. The five
  affected departments passed 3,854 with one skip; the ordinary suite passed
  4,881 with four skips and 28 headed deselections. Import analysis kept all 11
  contracts across 75 files and 334 dependencies, down from the SIM-0 baseline
  of 77 files and 346 dependencies.
- Independent enforcement, JavaScript, and relocation reviews found no new
  codec, authority/adoption type, constructor-hardening sweep, body-semantic
  twin, epoch drift, feature work, or relocated certification mechanism.

Completion requires every statement below:

- No internal workflow JSON schema, payload version, byte ceiling, charge
  calculator, or encode/decode path remains.
- Dispatcher/session custody contains checkpoint objects, not serialized
  continuation bytes.
- There is no new generic freeze, authority, adoption, recertification,
  serialization, compatibility, or checkpoint framework.
- There is no checkpoint DTO duplicating an existing immutable domain value or
  detached snapshot field-for-field.
- Each workflow has one checkpoint construction path and one open/materialize
  path.
- Event flow has one domain-to-v5 projector and one history-boundary validator
  reused at admission and readback, with no downstream Python event-body certifier or JavaScript
  semantic twin.
- The browser retains only its real transport-envelope checks.
- The implementation-time audit was retired instead of becoming standing
  infrastructure or a substitute implementation of what was removed.
- Dependency paths and standing mechanisms are fewer, not renamed or displaced
  into tests, docs, adapters, or generic helpers.

Any failed statement fails the task. Do not compensate with line-count gains.

---

## 8. Finite terminal exit test

After SIM-2, create disposable branch
`codex/simplification-field-probe` from the completed simplification HEAD and
add this scratch-only field:

```python
PlanOperation.simplification_probe: str | None = None
```

A non-null value must participate in domain equality and the existing plan
fingerprint/projection, survive semantic dispatcher checkpoint pause/resume,
and appear in the single `PlanOperationView` boundary projection. It has no
executor-policy effect. Construct probes with `dataclasses.replace` so
mechanical constructor churn cannot dominate the observation.

Count every tracked source and test file required to make the focused public
workflow/dispatcher/view check pass. Test fixtures count; generated artifacts
and caches do not. Record the exact file list and command, then revert the
scratch changes, return to the source branch, and delete the disposable branch.
Nothing from the probe is committed or merged.

- Historical baseline: 20–27 files.
- Declared target: **at most 8 files**.
- More than 8 means the run is incomplete. Record the residual fanout and stop;
  do not expand the register with opportunistic cleanup.

### Terminal result (2026-09-01)

The probe passed from completed implementation HEAD `f73dd98` and was then
fully reverted. The disposable `codex/simplification-field-probe` branch was
deleted without a commit or merge. Exactly six tracked files were required:

- `namisync/core/planning.py`: the frozen domain field and its one canonical
  plan projection;
- `namisync/workflows/models.py`: the single `PlanOperationView` field;
- `namisync/workflows/runtime.py`: the domain-to-view mapping;
- `tests/test_bridge_resume.py`: one real plan -> commit -> dispatcher pause ->
  checkpoint reopen -> resume -> completion check;
- `tests/interfaces/web/_public_view_witnesses.py`: the exact public bridge
  witness for both the operation and containing plan review; and
- `tests/test_core_scanplan.py`: the kept exact-field completeness alarm,
  exercised with a non-null operation so optional default omission could not
  hide an unprojected semantic value.

The scratch test used `dataclasses.replace`. A non-null value changed generated
domain equality and the canonical plan fingerprint, retained its operation id,
appeared in `operation_projection` and `PlanOperationView`, survived both real
`open_execution` calls and paused checkpoint materialization, and had no effect
on successful execution. The canonical projection omitted only the default
`None` value, so the existing epoch-5 plan identity bytes remained unchanged;
their focused full-identity and identityless checks passed without editing the
frozen vector or its hash owner.

No dispatcher, checkpoint, database, persistence decoder, interface codec,
JavaScript validator, executor policy, authority/adoption API, compatibility
layer, or generic helper required a field-specific edit. The exact focused
command was:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_bridge_resume.py::test_br_g_10_dispatcher_pause_resume_reopens_the_same_run tests/interfaces/web/test_transport.py::test_br_g_32_every_approved_public_view_crosses_real_dispatch_exactly tests/test_core_scanplan.py::test_plan_fingerprint_uses_explicit_identity_text tests/test_core_scanplan.py::test_identityless_plan_bytes_preserve_the_epoch5_capture tests/test_core_scanplan.py::test_core_hash_projections_cover_exact_known_dataclasses -q
```

It passed **52 tests**. The measured result is **6 files**, below the declared
maximum of 8 and the historical 20–27-file baseline. After reversal,
`git diff --exit-code` was clean and `simplification_probe` had no match under
`namisync` or `tests`.

---

## 9. Closed verification record

During implementation, each checkpoint ran the temporary audit three times,
the affected producer and consumer departments, the ordinary suite, and
`lint-imports`; SIM-2 also ran the direct Node drain/reducer probes. No headed
witness was required because the run activated and changed no user workflow.
The terminal sweep reconciled every ledger row, proved the zero-uncovered rule,
searched for forbidden replacement mechanisms, measured dependency trends, and
completed the field probe in §8. The temporary audit is now retired; this
section creates no standing rerun instruction.

### Resumption block

- Planning branch: `milestone1-anthony`.
- Planning base: `42fae4d3b498175a4884e64b6995287188f616e3`.
- Committed SIM-0 collection: 5,236 total tests, with 5,208 selected and 28
  deselected.
- Ordinary baseline: 5,204 passed, 4 skipped, 28 deselected, with the bundled
  Node runtime supplied through `NAMISYNC_TEST_NODE`.
- Import baseline: 11 contracts kept, 0 broken across 77 files and 346
  dependencies.
- Current post-follow-up collection: 4,911 total tests, 28 headed deselections,
  and 4,883 ordinary executions.
- Current post-follow-up ordinary result: 4,879 passed and 4 capability-skipped.
  Import analysis: 11 contracts kept, 0 broken across 75 files and 334
  dependencies.
- From the fixed SIM-0 plan comparison `83e5da1` through implementation HEAD
  `f73dd98`, production changed by 373 additions and 4,681 deletions (net
  -4,308), while tests changed by 1,543 additions and 4,094 deletions (net
  -2,551). These totals include bounded CLI-ingress fix `e3683a1` (+20
  production and +52 test lines, no deletions); the SIM-1 and SIM-2 removal
  subtotals otherwise sum exactly. These are terminal trend measurements, not
  acceptance gates.
- Active row: none; the implementation register and §8 exit test are complete.
- Next action: none within this run. Any H2 checkpoint, new feature, or broader
  ownership restructure requires its own finite register and user direction.
- Implementation commits: CLI ingress `e3683a1`, semantic checkpoints
  `370cfa5`, and redundant event-certification removal `f73dd98`.
- The implementation-time simplification runner, committed baseline, and
  self-test were retired after SIM-F1's final three-run match. The shared event
  fixtures and focused public contract tests remain.
- Mechanism counters: aliasing 1; lost enforcement 0; representation drift 1;
  coverage hole 4. The SIM-2 three-of-any-kind stop and reorganization are
  recorded above.
- This closed run is not authority to resume H2 feature work.
