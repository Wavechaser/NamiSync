---
ledger: task_lifecycle_test_disposition
schema: 1
baseline: 5631066
corpus:
  - path: tests/dispatcher/test_dispatcher.py
    vocabulary:
      - AdmissionAttachment
      - _AdmissionCleanup
      - _admission_cleanups
      - _admission_liability_claimed
      - _admission_cleanup_attempt
      - _start_admission_cleanup_worker
      - _join_admission_cleanup_worker
      - attach
      - attachment_rollback
  - path: tests/test_service.py
    vocabulary:
      - SessionObserver
      - _Observation
      - _observations
      - observation_sink
      - session_attachment
      - require_session_attachment
      - _require_session_attachment
      - _session_receipts
      - _receipt_ids_by_session
      - _session_receipt
      - _session_command_guard
      - _remember_session_receipt
      - _detail_owners_by_session
      - _runtime_detail_retirement_started
      - adopt
      - retains_observation
      - unsubscribe
      - close_session
      - drop_plan
  - path: tests/test_bridge_service.py
    vocabulary:
      - observation_sink
      - session_attachment
      - require_session_attachment
      - _require_session_attachment
      - _session_receipts
      - _receipt_ids_by_session
      - _session_receipt
      - _remember_session_receipt
      - _detail_owners_by_session
      - _runtime_detail_retirement_started
      - mutation_receipts
  - path: tests/interfaces/web/test_commands.py
    vocabulary:
      - replay_start
      - start_plan
      - command_id
      - wire_intent
  - path: tests/interfaces/web/test_drain.py
    vocabulary:
      - _StartEntry
      - _TaskReservation
      - attached_session_id
      - _Compensation
      - _TaskCleanup
      - cleanup_pending
      - observation_unsubscribed
      - session_release_started
      - _session_attachment
      - unsubscribe_all
      - unsubscribe
      - close_session
      - drop_plan
      - _commands
      - _reservations
      - _close_receipts
      - _task_capacity
      - start_plan
      - release_terminal_session
      - close_task
  - path: tests/interfaces/web/test_host.py
    vocabulary:
      - TaskRegistry
      - _TaskService
      - require_session_attachment
      - unsubscribe_all
      - begin_close
      - wait_for_handlers
      - close_task
      - _close_hooks
      - _patch_primary
  - path: tests/interfaces/web/test_transport.py
    vocabulary:
      - start_plan
      - replay_start
      - command_id
      - wire_intent
      - slot
semantic_companions:
  tests/test_bridge_service.py:
    - test_br_g_16_concurrent_session_retry_admits_exactly_one_session
    - test_br_g_16_execution_command_id_is_single_flight_across_plans
    - test_br_g_16_id_retry_replays_before_mutable_inventory_resolution
    - test_br_g_16_plan_retry_replays_before_paths_are_revalidated
    - test_br_g_16_close_and_retry_do_not_replay_a_closed_session
  tests/interfaces/web/test_commands.py:
    - test_br_g_32_start_plan_replays_before_volatile_slots_are_resolved
  tests/interfaces/web/test_drain.py:
    - test_sh_g_8_observation_attaches_before_start_returns_and_pending_is_drained
    - test_br_g_33_start_is_singleflight_and_changed_intent_conflicts
    - test_terminal_session_release_refuses_before_record_delivery
    - test_close_task_refuses_before_terminal_record_is_drained
    - test_terminal_event_alone_does_not_earn_release_receipt
  tests/interfaces/web/test_host.py:
    - test_task_registry_has_no_task_model_runtime_admission
  tests/interfaces/web/test_transport.py:
    - test_br_g_32_start_plan_receipt_binds_resolved_intent_not_slot_ids
enumeration:
  ast_nodes:
    - Name.id
    - Attribute.attr
    - keyword.arg
    - Constant[str]
  procedure:
    - Parse only the seven exact corpus paths.
    - Map path-scoped vocabulary hits to their enclosing test FunctionDef or AsyncFunctionDef.
    - Inspect candidate hits for the lifecycle concern; do not treat same-spelling unrelated command tables as lifecycle machinery.
    - Union the exact named semantic companions above.
    - Record shared helper symbols separately; do not expand helpers transitively into behavioral rows.
  false_positive_exclusions:
    - tests/interfaces/web/test_commands.py::_commands
    - tests/interfaces/web/test_host.py::_commands
test_rows_by_path:
  tests/dispatcher/test_dispatcher.py: 15
  tests/test_service.py: 41
  tests/test_bridge_service.py: 18
  tests/interfaces/web/test_commands.py: 1
  tests/interfaces/web/test_drain.py: 42
  tests/interfaces/web/test_host.py: 13
  tests/interfaces/web/test_transport.py: 1
totals:
  test_rows: 131
  helper_rows: 8
allowed_dispositions:
  - mechanism-removed
  - reanchored-owner
  - boundary-retained
initial_disposition: pending
initial_verification: pending
initial_status: pending
---

# Task Lifecycle Test Disposition Ledger

Archived after the lifecycle register closed on 2026-09-03. This ledger is
historical evidence, not active test or implementation authority.

This is the finite LC-0 census for lifecycle-removal test work. A pending
disposition is deliberately unassigned: no row may receive one of the three
allowed dispositions until the implementation makes that decision factual.
Replacement tests are named before an old-owner test is deleted.

## Behavioral test rows

| ID | Exact test | Matched concern | Disposition | Replacement | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TL-DSP-001 | tests/dispatcher/test_dispatcher.py::test_admission_store_accepts_then_raises_and_failed_drop_keeps_metadata_only | dispatcher admission cleanup and retained store liability | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-002 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_releases_graphs_and_refuses_recursive_submit | dispatcher admission cleanup retry and graph retirement | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-003 | tests/dispatcher/test_dispatcher.py::test_admission_liability_refuses_concurrent_submit_without_waiting | dispatcher admission-liability concurrency | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-004 | tests/dispatcher/test_dispatcher.py::test_failed_admission_cleanup_caps_churn_retries_and_releases | dispatcher admission cleanup retry bound | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-005 | tests/dispatcher/test_dispatcher.py::test_shutdown_joins_one_blocked_admission_cleanup_worker_to_deadline | dispatcher cleanup-worker shutdown | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-006 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_worker_start_failure_preserves_exact_owner | dispatcher cleanup-worker start failure | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-007 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_worker_does_not_join_itself_during_shutdown | dispatcher cleanup-worker self-join avoidance | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-008 | tests/dispatcher/test_dispatcher.py::test_observed_admission_emits_pending_before_workflow_can_enter | observed admission publication order | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-009 | tests/dispatcher/test_dispatcher.py::test_observed_attach_failure_is_never_published_or_scheduled | attachment refusal before publication | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-010 | tests/dispatcher/test_dispatcher.py::test_failed_attach_retains_registered_rollback_for_dispatcher_retry | registered attachment rollback retention | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-011 | tests/dispatcher/test_dispatcher.py::test_registered_attachment_callbacks_are_snapshotted_before_prepare | attachment callback snapshot | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-012 | tests/dispatcher/test_dispatcher.py::test_registered_attachment_subclasses_are_rejected_before_prepare | attachment exact-type boundary | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-013 | tests/dispatcher/test_dispatcher.py::test_shutdown_racing_observed_attach_rolls_back_without_scheduling | attachment and shutdown race | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-014 | tests/dispatcher/test_dispatcher.py::test_pending_emission_failure_preserves_error_and_rolls_back_attach | publication failure attachment rollback | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-DSP-015 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_join_failure_does_not_replace_initiating_error | cleanup join failure error precedence | reanchored-owner | same named test remains at the authoritative dispatcher-custody owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-001 | tests/test_service.py::test_observe_returns_finished_record_without_subscribing | terminal observation without subscription | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-002 | tests/test_service.py::test_finish_between_get_and_subscribe_returns_terminal_record | observe terminal race | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-003 | tests/test_service.py::test_unsubscribe_closes_blocking_stream_and_uses_no_poll_timeout | observation release and blocking stream | boundary-retained | tests/test_service.py::test_release_closes_stream_and_waits_for_worker_without_poll_timeout | renamed at the physical observer owner; stream close, no polling, worker completion, and idempotent replay remain explicit | closed |
| TL-SVC-004 | tests/test_service.py::test_close_closes_every_stream_before_joining_observers | observer shutdown order | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-005 | tests/test_service.py::test_observer_close_timeout_retains_thread_for_retry | observer join-timeout retry | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-006 | tests/test_service.py::test_observer_direct_join_failure_retires_private_graph_and_stopped_stream | observer direct join failure retirement | boundary-retained | same named test retains the five failure classes for observer `close` and `release`; the returned-rollback variants are `mechanism-removed` with that capability | close/release still retire private graphs and stopped streams; `adopt` now returns no rollback authority | closed |
| TL-SVC-007 | tests/test_service.py::test_observer_join_failure_retires_stopped_and_retains_only_live_retry | observer retry-state retention | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-008 | tests/test_service.py::test_gap_recovery_resubscribes_from_first_undelivered_sequence | observer gap recovery | boundary-retained | same named delivered-event recovery test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-009 | tests/test_service.py::test_gap_recovery_releases_retired_streams_while_observation_is_live | recovered-stream retirement | boundary-retained | same named delivered-event recovery test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-010 | tests/test_service.py::test_gap_recovery_stop_closes_racing_replacement_outside_observer_lock | recovery and release race | boundary-retained | same named delivered-event recovery test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-011 | tests/test_service.py::test_sink_exception_closes_stream_and_does_not_block_shutdown | sink failure stream release | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-012 | tests/test_service.py::test_observer_failure_retires_private_graph_before_wait_and_cleanup | observer failure graph retirement | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-013 | tests/test_service.py::test_observer_stream_close_base_exception_is_contained | stream-close failure containment | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-014 | tests/test_service.py::test_observer_close_continues_after_private_base_exception_and_retires_all | observer close continuation | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-015 | tests/test_service.py::test_observer_close_failure_traceback_does_not_own_retired_observations | observer failure traceback ownership | boundary-retained | tests/test_service.py::test_observer_close_failure_traceback_does_not_own_retired_subscriptions | renamed with the physical owner; private failure graphs and retired subscriptions remain collectible | closed |
| TL-SVC-016 | tests/test_service.py::test_observer_single_cleanup_retires_after_private_close_base_exception | single observation cleanup retry | reanchored-owner | same named test admits through both `observe` and `adopt`, then releases through the sole physical owner | both admission paths retire the exact subscription and private failure graph through `SessionObserver.release` | closed |
| TL-SVC-017 | tests/test_service.py::test_sink_can_unsubscribe_itself_without_self_join_or_deadlock | callback self-unsubscribe | boundary-retained | tests/test_service.py::test_callback_self_release_retires_atomically_without_self_join | callback self-release removes the exact subscription, closes its stream, avoids self-join, and lets the worker unwind without deadlock | closed |
| TL-SVC-018 | tests/test_service.py::test_adopt_rollback_is_idempotent_and_cannot_remove_replacement | observer adoption rollback identity | reanchored-owner | tests/test_service.py::test_adopt_rejection_closes_offer_and_returns_no_rollback_capability and tests/test_service.py::test_stale_subscription_release_cannot_remove_replacement | returned rollback authority is removed; the observer now closes rejected offers itself, while identity-bound stale release cannot retire a replacement | closed |
| TL-SVC-019 | tests/test_service.py::test_reobserve_replaces_stream_from_exact_positive_sequence | exact reobservation replacement | boundary-retained | same named observer/event boundary test retained at the physical owner | the old subscription is done and its worker is joined before replacement subscribe/adopt begins; exact replay sequence remains seven | closed |
| TL-SVC-020 | tests/test_service.py::test_reobserve_rejects_nonpositive_or_noninteger_sequence | reobservation input boundary | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-021 | tests/test_service.py::test_invalid_reobserve_preserves_existing_observation | failed reobservation custody | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-022 | tests/test_service.py::test_reobserve_terminal_session_installs_no_stream | terminal reobservation | boundary-retained | same named observer/event boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-023 | tests/test_service.py::test_service_shutdown_orders_observer_dispatcher_and_runtime | service shutdown ownership order | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-024 | tests/test_service.py::test_service_default_close_uses_ordered_shutdown_timeout | service close ordering | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-025 | tests/test_service.py::test_incomplete_service_shutdown_keeps_runtime_open_and_can_retry | incomplete service settlement retry | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-026 | tests/test_service.py::test_service_close_retries_an_observer_join_failure | observer release retry during service close | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-027 | tests/test_service.py::test_service_close_retires_private_observer_failure_before_dependency_close | observer failure retirement before dependency close | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-028 | tests/test_service.py::test_runtime_close_failure_can_be_retried_without_repeating_shutdown | runtime close settlement progress | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-029 | tests/test_service.py::test_concurrent_service_close_serializes_dependency_retry | concurrent service settlement | boundary-retained | same named shutdown boundary test retained | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-030 | tests/test_service.py::test_session_close_retires_only_its_exact_runtime_details | exact session detail ownership | reanchored-owner | same named test rewritten against application association and settlement | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-031 | tests/test_service.py::test_failed_session_close_preserves_detail_owner_for_retry | detail-owner retention on close failure | reanchored-owner | same named test rewritten against application settlement retry | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-032 | tests/test_service.py::test_blocked_session_retirement_keeps_details_until_close_returns | detail retirement after dispatcher close | reanchored-owner | same named test rewritten against application settlement ordering | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-033 | tests/test_service.py::test_service_shutdown_preserves_detail_owners_until_runtime_close_succeeds | detail-owner shutdown retention | reanchored-owner | same named test rewritten against aggregate-owned detail liability | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-034 | tests/test_service.py::test_detail_owner_attachment_rolls_back_a_failed_publication | detail-owner publication rollback | reanchored-owner | same named test rewritten against aggregate admission rollback | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-035 | tests/test_service.py::test_detail_owner_attachment_rechecks_service_lifecycle | detail attachment lifecycle recheck | reanchored-owner | same named test rewritten against aggregate lifecycle closure | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-036 | tests/test_service.py::test_detail_owner_rollback_preserves_a_replacement_binding | exact detail-owner rollback identity | mechanism-removed | tests/test_task_lifecycle.py::test_lifecycle_admission_claim_owns_exact_liabilities and tests/test_task_lifecycle.py::test_lifecycle_retained_state_has_no_delivery_or_observer_resources | mutable `_detail_owners_by_session` replacement binding is absent; exact aggregate liabilities and resource exclusions pass | closed |
| TL-SVC-037 | tests/test_service.py::test_detail_owner_attachment_precedes_post_admission_shutdown | detail attachment and shutdown race | mechanism-removed | tests/test_service.py::test_service_shutdown_preserves_detail_owners_until_runtime_close_succeeds and tests/test_task_lifecycle.py::test_lifecycle_admission_claim_owns_exact_liabilities | map introspection is absent; retained shutdown and exact-liability tests pass | closed |
| TL-SVC-038 | tests/test_service.py::test_service_execution_opt_in_reaches_runtime_without_changing_default | execution session/detail association | reanchored-owner | same named test rewritten against application session/detail association | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-039 | tests/test_service.py::test_location_commands_submit_exact_typed_workflow_requests | location-session detail association | reanchored-owner | same named test rewritten against application session/detail association | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-040 | tests/test_service.py::test_selection_mutation_drop_race_does_not_retain_or_replay | plan-selection receipt/effect retirement exclusion | reanchored-owner | same named regression rewritten against the application lifecycle plan token and receipt owner | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-SVC-041 | tests/test_service.py::test_selection_liveness_retry_preserves_concurrent_successor | exact successor preservation during liveness retry | reanchored-owner | same named successor witness rewritten against exact application lifecycle plan tokens | exact name present; dispatcher/service focused run: 224 passed | closed |
| TL-BRS-001 | tests/test_bridge_service.py::test_required_attachment_refuses_execution_before_selection_or_commit | required desktop attachment | reanchored-owner | tests/test_service.py::test_task_association_gates_reobserve_release_and_close_effects | retired attachment contract absent; application association owner test passed in the 224-case dispatcher/service focused run | closed |
| TL-BRS-002 | tests/test_bridge_service.py::test_br_g_16_retry_receipts_apply_mutations_and_multirow_changes_once | mutation receipt idempotency | reanchored-owner | same named test retained and rebuilt against `TaskLifecycle` plan-mutation receipts | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-003 | tests/test_bridge_service.py::test_br_g_16_receipt_identity_mismatches_use_the_exact_typed_boundary | receipt conflict boundary | reanchored-owner | same named test retained against lifecycle-owned selection, visibility, and session receipt conflicts | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-004 | tests/test_bridge_service.py::test_plan_receipt_replay_ignores_sink_and_does_not_reattach | plan receipt replay attachment behavior | reanchored-owner | tests/test_bridge_service.py::test_task_plan_receipt_replay_does_not_recreate_delivery_or_observation | replacement proves one application effect, delivery factory, and observer adoption; bridge/service focused run: 28 passed | closed |
| TL-BRS-005 | tests/test_bridge_service.py::test_observed_plan_attach_failure_leaves_no_receipt_or_submission_artifact | failed observed admission receipt cleanup | reanchored-owner | tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer and tests/test_service.py::test_detail_owner_attachment_rolls_back_a_failed_publication | owner-fault and failed-publication witnesses prove exact liability retirement; focused gate passed | closed |
| TL-BRS-006 | tests/test_bridge_service.py::test_observed_plan_publication_rollback_releases_observer_before_owner | observer and owner rollback order | reanchored-owner | tests/test_service.py::test_observed_start_adoption_rejection_retires_exact_liabilities and tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer | adoption rejection and observer/detail owner faults preserve fixed rollback order and unique effects; focused gate passed | closed |
| TL-BRS-007 | tests/test_bridge_service.py::test_publication_rollback_drains_detail_and_owner_after_observer_failure | composite publication compensation | reanchored-owner | tests/test_service.py::test_whole_admission_rollback_replays_without_duplicate_effect and tests/test_service.py::test_whole_admission_rollback_singleflights_concurrent_callers | whole rollback repeats safely and admits one exact rollback owner under concurrency; focused gate passed | closed |
| TL-BRS-008 | tests/test_bridge_service.py::test_publication_rollback_retries_owner_after_exact_observer_retires | unfinished owner compensation retry | reanchored-owner | tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer | post-effect owner faults replay the whole fixed rollback while each exact transition remains unique; focused gate passed | closed |
| TL-BRS-009 | tests/test_bridge_service.py::test_desktop_attachment_requirement_covers_location_session_admission | desktop attachment across location starts | reanchored-owner | tests/test_service.py::test_location_commands_submit_exact_typed_workflow_requests and tests/test_service.py::test_direct_starts_associate_and_retire_exact_session_receipts | desktop attachment requirement removed; every direct/location session receives application association in the 224-case focused run | closed |
| TL-BRS-010 | tests/test_bridge_service.py::test_br_g_16_shutdown_does_not_repopulate_a_late_session_receipt | receipt publication and shutdown race | reanchored-owner | same named test retained against lifecycle admission-token retirement | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-011 | tests/test_bridge_service.py::test_br_g_16_shutdown_waits_for_an_inflight_receipt_replay | in-flight receipt replay shutdown | reanchored-owner | tests/interfaces/web/test_host.py::test_startup_finalizer_keeps_cosmetics_open_until_handlers_quiesce and tests/interfaces/web/test_host.py::test_handler_wait_timeout_keeps_service_open_until_explicit_retry | raw receipt-lock wait removed; admitted-handler quiescence and retry remain at the host (drain/host run: 180 passed) | closed |
| TL-BRS-012 | tests/test_bridge_service.py::test_br_g_16_close_before_receipt_publication_drops_late_receipt | close before receipt publication | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_task_start_publication_replays_one_receipt and tests/test_service.py::test_direct_start_replay_waits_for_close_and_admits_successor | atomic application publication/replay and close exclusion pass | closed |
| TL-BRS-013 | tests/test_bridge_service.py::test_session_receipt_publication_does_not_reread_dispatcher_after_attach | receipt publication association truth | reanchored-owner | tests/test_bridge_service.py::test_task_receipt_publication_does_not_reread_dispatcher_after_attach | renamed owner test passes with lifecycle association as post-attachment truth; bridge/service run: 28 passed | closed |
| TL-BRS-014 | tests/test_bridge_service.py::test_br_g_16_concurrent_session_retry_admits_exactly_one_session | concurrent session receipt single flight | reanchored-owner | same named test retained against lifecycle command guard and receipt owner | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-015 | tests/test_bridge_service.py::test_br_g_16_execution_command_id_is_single_flight_across_plans | execution receipt scope | reanchored-owner | same named test retained against the application receipt scope | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-016 | tests/test_bridge_service.py::test_br_g_16_id_retry_replays_before_mutable_inventory_resolution | receipt replay before volatile resolution | reanchored-owner | same named test retained against lifecycle replay before runtime resolution | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-017 | tests/test_bridge_service.py::test_br_g_16_plan_retry_replays_before_paths_are_revalidated | plan receipt replay before path validation | reanchored-owner | same named test retained against lifecycle replay before path validation | exact name present; bridge/service focused run: 28 passed | closed |
| TL-BRS-018 | tests/test_bridge_service.py::test_br_g_16_close_and_retry_do_not_replay_a_closed_session | receipt retirement on session close | reanchored-owner | same named test retained against lifecycle session receipt retirement | exact name present; bridge/service focused run: 28 passed | closed |
| TL-CMD-001 | tests/interfaces/web/test_commands.py::test_br_g_32_start_plan_replays_before_volatile_slots_are_resolved | adapter start-response replay | boundary-retained | same named command-boundary test retained | exact name present; commands focused run: 185 passed | closed |
| TL-DRN-001 | tests/interfaces/web/test_drain.py::test_failed_admission_observer_retains_task_capacity_until_dispatcher_retry | failed-admission reservation and cleanup | reanchored-owner | tests/interfaces/web/test_drain.py::test_failed_application_admission_discards_provisional_delivery_state and tests/test_service.py::test_whole_admission_rollback_replays_without_duplicate_effect | adapter provisional discard and application whole-rollback owner passed the focused gate | closed |
| TL-DRN-002 | tests/interfaces/web/test_drain.py::test_br_g_33_integrated_admission_and_visible_overflow_gap | attached delivery and visible gap | boundary-retained | same named delivered-event boundary test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-003 | tests/interfaces/web/test_drain.py::test_sh_g_8_br_g_42_normal_event_envelope_is_bounded_and_lossless | attached delivery capacity boundary | boundary-retained | same named delivered-event boundary test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-004 | tests/interfaces/web/test_drain.py::test_failed_start_raises_fresh_closed_failure_category | failed start-entry replay category | reanchored-owner | same named adapter response-replay failure test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-005 | tests/interfaces/web/test_drain.py::test_invalid_plan_return_cleans_only_independently_attached_session | invalid start compensation scope | reanchored-owner | tests/interfaces/web/test_drain.py::test_invalid_task_start_view_discards_only_provisional_delivery_state and tests/test_service.py::test_observed_start_adoption_rejection_retires_exact_liabilities | adapter discards only provisional state; application retires only exact admission liabilities; focused gate passed | closed |
| TL-DRN-006 | tests/interfaces/web/test_drain.py::test_exact_plan_with_graph_string_is_rejected_and_released | invalid start-result compensation | reanchored-owner | tests/interfaces/web/test_drain.py::test_exact_task_start_with_graph_string_discards_provisional_state and tests/test_service.py::test_observed_start_adoption_rejection_retires_exact_liabilities | exact invalid-view graph retirement and exact application-liability retirement passed the focused gate | closed |
| TL-DRN-007 | tests/interfaces/web/test_drain.py::test_validated_plan_candidate_fields_are_not_reread | start-result identity validation | mechanism-removed | tests/interfaces/web/test_drain.py::test_invalid_task_start_ids_discard_provisional_delivery_state | split `PlanSession` validation/attachment candidate no longer exists; exact application `TaskStartView` invalid-ID rejection passed in the 105-case drain run | closed |
| TL-DRN-008 | tests/interfaces/web/test_drain.py::test_invalid_plan_ids_never_acquire_compensation_authority | compensation authority admission | mechanism-removed | tests/interfaces/web/test_drain.py::test_invalid_task_start_ids_discard_provisional_delivery_state and tests/test_task_lifecycle.py::test_lifecycle_retained_state_has_no_delivery_or_observer_resources | drain compensation authority absent; invalid views create no application call or adapter task (105 drain; 38 lifecycle) | closed |
| TL-DRN-009 | tests/interfaces/web/test_drain.py::test_concurrent_failed_start_retires_private_exception_graph | concurrent failed-start receipt retirement | reanchored-owner | same named adapter response single-flight/graph-retirement test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-010 | tests/interfaces/web/test_drain.py::test_br_g_33_shutdown_wakes_then_unsubscribes_after_handler_barrier | adapter shutdown and observation cleanup | reanchored-owner | tests/interfaces/web/test_drain.py::test_br_g_33_shutdown_wakes_blocked_drain_without_domain_cleanup and tests/interfaces/web/test_host.py::test_disc_b2_delivery_shutdown_wakes_offer_before_observer_release | delivery shutdown remains adapter-local and precedes observer release; drain/host run: 180 passed | closed |
| TL-DRN-011 | tests/interfaces/web/test_drain.py::test_unsubscribe_all_retires_dependency_frames_and_preserves_retry | adapter bulk observation cleanup | mechanism-removed | tests/interfaces/web/test_host.py::test_disc_b2_delivery_shutdown_wakes_offer_before_observer_release, tests/test_task_lifecycle.py::test_disc_b2_adapter_shutdown_wakes_offer_before_service_observer_release, and the delivery-wake portion of tests/interfaces/web/test_transport_headed.py::test_br_g_33_real_next_events_is_concurrent_and_shutdown_wakes_it | `unsubscribe_all` and adapter observation cleanup are absent. The former headed `['unsubscribe', 'b' * 32]` assertion is deleted rather than inverted: the headed node positively proves blocked-drain withdrawal, while the two deterministic DISC-B2 owner tests prove service-close and observer-release ordering. | closed |
| TL-DRN-012 | tests/interfaces/web/test_drain.py::test_br_g_33_close_task_cleanup_order_and_retry_authority | task cleanup order | reanchored-owner | tests/interfaces/web/test_drain.py::test_br_g_33_close_task_delegates_terminal_fact_and_retires_delivery and tests/test_service.py::test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent | adapter delegates one high-level close; application owns the fixed whole-operation sequence; focused gate passed | closed |
| TL-DRN-013 | tests/interfaces/web/test_drain.py::test_terminal_session_release_retains_plan_receipt_and_task_capacity | terminal release retention | reanchored-owner | tests/interfaces/web/test_drain.py::test_terminal_session_release_retains_start_response_replay and tests/test_task_lifecycle.py::test_lifecycle_task_replay_crosses_release_but_joins_task_close | adapter response and application task receipt survive terminal release; focused drain/lifecycle runs passed | closed |
| TL-DRN-014 | tests/interfaces/web/test_drain.py::test_terminal_session_release_lost_response_replay_is_idempotent | terminal release response replay | reanchored-owner | same named adapter response-convergence test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-015 | tests/interfaces/web/test_drain.py::test_delayed_terminal_release_converges_from_close_receipt | terminal release close receipt | reanchored-owner | same named adapter close-tombstone convergence test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-016 | tests/interfaces/web/test_drain.py::test_explicit_close_after_terminal_release_only_drops_plan | post-release task close | reanchored-owner | tests/interfaces/web/test_drain.py::test_explicit_close_after_terminal_release_delegates_both_operations and tests/test_service.py::test_s6_cleanup_replay_repeats_owner_calls_not_effects | adapter delegates release/close; application alone retires the exact plan and repeated calls preserve unique effects; focused gate passed | closed |
| TL-DRN-017 | tests/interfaces/web/test_drain.py::test_release_retries_only_unfinished_session_step | release settlement retry | reanchored-owner | tests/interfaces/web/test_drain.py::test_release_failure_retains_delivery_state_for_high_level_retry and tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects | adapter retains delivery fact while application replays the fixed sequence from current owner truth; completed transitions remain unique | closed |
| TL-DRN-018 | tests/interfaces/web/test_drain.py::test_close_drop_failure_still_proves_terminal_session_release | plan-drop failure after session release | reanchored-owner | tests/interfaces/web/test_drain.py::test_close_failure_retains_delivery_state_for_high_level_retry and tests/test_service.py::test_s6_cleanup_replay_repeats_owner_calls_not_effects | adapter retains delivery state; whole cleanup replay repeats tolerant calls while prior release transitions remain unique | closed |
| TL-DRN-019 | tests/interfaces/web/test_drain.py::test_release_and_close_race_runs_each_cleanup_step_once | release and close compensation race | reanchored-owner | tests/interfaces/web/test_drain.py::test_release_and_close_race_delegates_each_high_level_operation_once and tests/test_service.py::test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers | adapter delegates each operation once; application grants one exact whole-operation settlement claim | closed |
| TL-DRN-020 | tests/interfaces/web/test_drain.py::test_release_settles_a_stale_failed_recovery_without_deadlock | failed recovery settlement | reanchored-owner | same named test retained with one high-level application release and no raw cleanup call | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-021 | tests/interfaces/web/test_drain.py::test_release_settles_stale_successful_recovery_with_one_unsubscribe | successful recovery release | reanchored-owner | tests/interfaces/web/test_drain.py::test_release_settles_stale_successful_recovery_with_one_lifecycle_call | renamed test proves one high-level release after stale recovery; drain focused run: 105 passed | closed |
| TL-DRN-022 | tests/interfaces/web/test_drain.py::test_release_retries_unsubscribe_after_stale_successful_recovery_failure | observation release retry | reanchored-owner | tests/interfaces/web/test_drain.py::test_release_failure_retains_delivery_state_for_high_level_retry and tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects | raw unsubscribe retry is absent from drain; adapter preserves delivery and application repeats tolerant observer release from owner truth | closed |
| TL-DRN-023 | tests/interfaces/web/test_drain.py::test_close_and_delayed_release_race_converges_through_close_receipt | close and delayed release race | reanchored-owner | same named test plus tests/interfaces/web/test_drain.py::test_release_waits_for_post_service_close_receipt_publication and tests/interfaces/web/test_drain.py::test_release_waiting_for_close_publication_wakes_on_close_failure | exact close-publication success/failure barriers passed in the drain focused run | closed |
| TL-DRN-024 | tests/interfaces/web/test_drain.py::test_br_g_33_failed_binding_retains_and_retries_compensation_in_order | failed binding compensation order | reanchored-owner | tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer and tests/test_service.py::test_whole_admission_rollback_singleflights_concurrent_callers | drain compensation is absent; fixed exact-liability rollback order and one concurrent application owner pass | closed |
| TL-DRN-025 | tests/interfaces/web/test_drain.py::test_coherent_return_grants_plan_cleanup_after_task_closes_during_start | start and task-close compensation authority | reanchored-owner | tests/interfaces/web/test_drain.py::test_begin_close_during_factory_discards_provisional_before_publish and tests/test_task_lifecycle.py::test_lifecycle_task_replay_crosses_release_but_joins_task_close | adapter locally discards provisional state while application owns start/close exclusion; focused runs passed | closed |
| TL-DRN-026 | tests/interfaces/web/test_drain.py::test_compensation_interrupt_propagates_without_stranding_the_registry | compensation interruption | reanchored-owner | tests/interfaces/web/test_drain.py::test_interrupted_application_start_discards_provisional_delivery_state and tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer | adapter interruption leaves no provisional state; application rollback owner faults remain retryable with unique transitions | closed |
| TL-DRN-027 | tests/interfaces/web/test_drain.py::test_cleanup_pending_start_retires_private_interruption_graph_before_replay | pending cleanup receipt replay | reanchored-owner | tests/interfaces/web/test_drain.py::test_failed_provisional_start_retires_private_interruption_graph and tests/test_task_lifecycle.py::test_lifecycle_task_start_publication_replays_one_receipt | adapter graph retirement and atomic application receipt publication/replay pass | closed |
| TL-DRN-028 | tests/interfaces/web/test_drain.py::test_replay_compensation_interruption_is_closed_and_remains_retryable | compensation replay interruption | reanchored-owner | tests/interfaces/web/test_drain.py::test_retained_start_response_replays_without_reentering_application and tests/test_service.py::test_whole_admission_rollback_replays_without_duplicate_effect | drain compensation replay is absent; transport response replay and application whole-rollback retry remain separately owned | closed |
| TL-DRN-029 | tests/interfaces/web/test_drain.py::test_concurrent_replays_single_flight_failed_admission_compensation | concurrent compensation replay | reanchored-owner | tests/interfaces/web/test_drain.py::test_concurrent_failed_provisional_start_is_one_response_flight and tests/test_task_lifecycle.py::test_lifecycle_admission_rollback_claim_singleflights_concurrent_callers | adapter response flight and application rollback claim each single-flight at their owner | closed |
| TL-DRN-030 | tests/interfaces/web/test_drain.py::test_br_g_33_close_task_retries_only_unfinished_cleanup_steps | task close settlement replay | reanchored-owner | tests/interfaces/web/test_drain.py::test_close_failure_retains_delivery_state_for_high_level_retry and tests/test_service.py::test_ls_4b_whole_operation_cleanup_replay_converges | adapter retains delivery; application replays the fixed whole operation from current owner truth without duplicate effects | closed |
| TL-DRN-031 | tests/interfaces/web/test_drain.py::test_close_task_lost_response_retry_is_exact_and_idempotent | task-close response replay | reanchored-owner | same named adapter close-tombstone test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-032 | tests/interfaces/web/test_drain.py::test_concurrent_task_close_runs_cleanup_once_and_echoes_both_callers | concurrent task close settlement | reanchored-owner | tests/interfaces/web/test_drain.py::test_concurrent_task_close_is_one_response_flight_and_echoes_both_callers and tests/test_service.py::test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers | adapter response publication and application whole-operation settlement are independently single-flight | closed |
| TL-DRN-033 | tests/interfaces/web/test_drain.py::test_task_capacity_is_hard_and_existing_command_replay_still_converges | task capacity and start replay | reanchored-owner | tests/test_service.py::test_application_refuses_distinct_49th_task_before_lower_effects and tests/interfaces/web/test_drain.py::test_application_task_capacity_and_adapter_response_replay_converge | 48-task effect bound is enforced before lower work; adapter retained-response replay still converges; focused runs passed | closed |
| TL-DRN-034 | tests/interfaces/web/test_drain.py::test_concurrent_capacity_reserves_once_and_same_command_joins | task reservation and start single flight | reanchored-owner | tests/test_service.py::test_application_same_command_joiner_replays_single_48th_task_effect and tests/test_task_lifecycle.py::test_lifecycle_capacity_singleflights_owner_and_joiner_at_limit | application owner/joiner at the exact limit passed without adapter reservation authority | closed |
| TL-DRN-035 | tests/interfaces/web/test_drain.py::test_close_refuses_session_attachment_before_lower_publication | attachment and task-close race | reanchored-owner | tests/interfaces/web/test_drain.py::test_begin_close_during_factory_discards_provisional_before_publish and tests/test_task_lifecycle.py::test_lifecycle_task_replay_crosses_release_but_joins_task_close | adapter factory state is provisional and local; application serializes association/close; focused runs passed | closed |
| TL-DRN-036 | tests/interfaces/web/test_drain.py::test_repeated_task_close_bounds_active_state_and_close_receipts | task and close-receipt retention bounds | reanchored-owner | same named test retained for adapter task-state retirement and 48 close-tombstone LRU; application capacity is proved by TL-DRN-033/034 replacements | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-037 | tests/interfaces/web/test_drain.py::test_task_drain_validates_whole_candidate_before_consuming | adapter drain ownership | reanchored-owner | same named test retained at the adapter queue/drain owner | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-038 | tests/interfaces/web/test_drain.py::test_sh_g_8_observation_attaches_before_start_returns_and_pending_is_drained | observation-before-start delivery order | boundary-retained | same named delivered-event ordering test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-039 | tests/interfaces/web/test_drain.py::test_br_g_33_start_is_singleflight_and_changed_intent_conflicts | adapter start single flight | reanchored-owner | tests/interfaces/web/test_drain.py::test_start_response_is_singleflight_and_wire_policy_conflicts | renamed test proves adapter transport-response single-flight/conflict independently of domain receipt ownership; drain run: 105 passed | closed |
| TL-DRN-040 | tests/interfaces/web/test_drain.py::test_terminal_session_release_refuses_before_record_delivery | terminal delivery prerequisite | boundary-retained | same named delivery-boundary test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-041 | tests/interfaces/web/test_drain.py::test_close_task_refuses_before_terminal_record_is_drained | task close delivery prerequisite | boundary-retained | same named delivery-boundary test retained | exact name present; drain focused run: 105 passed | closed |
| TL-DRN-042 | tests/interfaces/web/test_drain.py::test_terminal_event_alone_does_not_earn_release_receipt | terminal record delivery truth | boundary-retained | same named delivered-event/record boundary test retained | exact name present; drain focused run: 105 passed | closed |
| TL-HST-001 | tests/interfaces/web/test_host.py::test_task_registry_has_no_task_model_runtime_admission | adapter/application ownership boundary | reanchored-owner | tests/interfaces/web/test_host.py::test_task_registry_composition_preserves_one_argument_constructor, tests/interfaces/web/test_commands.py::test_production_command_composition_binds_transport_response_codec_when_supported, tests/interfaces/web/test_drain.py::test_task_response_codec_binding_is_exact_idempotent_and_conflict_safe, and tests/interfaces/web/test_drain.py::test_task_drain_fails_closed_before_response_codec_binding | one-argument registry composition remains domain-free; transport codec binds once at command composition and both drain surfaces fail closed before binding; 369 drain/commands/host tests and all 12 import contracts passed | closed |
| TL-HST-002 | tests/interfaces/web/test_host.py::test_desktop_service_requires_session_attachment | desktop attachment composition | reanchored-owner | tests/interfaces/web/test_host.py::test_desktop_service_uses_no_adapter_attachment_contract | inverse composition witness proves the removed adapter attachment capability is not passed; drain/host run: 180 passed | closed |
| TL-HST-003 | tests/interfaces/web/test_host.py::test_startup_finalizer_quiesces_registry_before_service_close | host quiesce and service-close order | boundary-retained | same named host shutdown-order test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-004 | tests/interfaces/web/test_host.py::test_startup_finalizer_keeps_cosmetics_open_until_handlers_quiesce | handler quiesce ownership | boundary-retained | same named host presentation/handler-order test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-005 | tests/interfaces/web/test_host.py::test_startup_finalizer_preserves_quiesce_error_without_unsafe_service_close | quiesce failure containment | boundary-retained | same named host failure-containment test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-006 | tests/interfaces/web/test_host.py::test_startup_finalizer_retains_every_owner_until_complete_retry | host shutdown owner retention | boundary-retained | same named host retry/custody test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-007 | tests/interfaces/web/test_host.py::test_close_hooks_quiesce_tasks_without_retiring_appearance | close-hook task quiesce | reanchored-owner | same named test retained with adapter-local `begin_close` only; service owns lifecycle teardown later in host order | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-008 | tests/interfaces/web/test_host.py::test_reload_readiness_refusal_records_before_normal_service_close | reload refusal shutdown order | boundary-retained | same named host shutdown-order test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-009 | tests/interfaces/web/test_host.py::test_close_callback_is_nonblocking_and_quiesces_in_exact_order | nonblocking close and quiesce order | boundary-retained | same named host callback/timing test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-010 | tests/interfaces/web/test_host.py::test_handler_wait_timeout_keeps_service_open_until_explicit_retry | handler timeout and service custody | boundary-retained | same named host retry/custody test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-011 | tests/interfaces/web/test_host.py::test_observation_unsubscribe_failure_retains_appearance_until_retry | observation cleanup failure during host close | mechanism-removed | tests/test_service.py::test_service_close_retries_an_observer_join_failure and tests/interfaces/web/test_host.py::test_disc_b2_delivery_shutdown_wakes_offer_before_observer_release | host raw unsubscribe path absent; observer retry and delivery-before-observer shutdown pass at their owners | closed |
| TL-HST-012 | tests/interfaces/web/test_host.py::test_bridge_rejection_precedes_a_blocked_close_status_render | bridge rejection during close | boundary-retained | same named bridge/presentation ordering test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-HST-013 | tests/interfaces/web/test_host.py::test_closing_status_can_render_while_an_admitted_handler_is_still_waiting | admitted handler and closing presentation | boundary-retained | same named presentation/handler concurrency test retained | exact name present; drain/host focused run: 180 passed | closed |
| TL-TRN-001 | tests/interfaces/web/test_transport.py::test_br_g_32_start_plan_receipt_binds_resolved_intent_not_slot_ids | transport start replay resolved intent | boundary-retained | same named bridge-boundary test retained with its fixture rebuilt on `TaskLifecycle` | exact name present; bundled-Node transport run: 124 passed | closed |

## Companion helper rows

Helper rows are not behavioral dispositions. Their orphan action remains
pending until every dependent behavioral row receives its disposition.

| ID | Exact helper symbol | Dependent test group | Orphan action | Status |
| --- | --- | --- | --- | --- |
| TL-HLP-001 | tests/dispatcher/test_dispatcher.py::wait_for_admission_cleanup_attempt | TL-DSP-002, TL-DSP-004, TL-DSP-006, TL-DSP-010; no non-ledger dependents | retained; all four exact dispatcher-owner dependents remain | closed |
| TL-HLP-002 | tests/test_service.py::_detail_lifecycle_service | exact ledger rows TL-SVC-034 through TL-SVC-037 | retained and rewritten for `TaskLifecycle`; current exact dependents are TL-SVC-034, TL-SVC-035, `test_admission_marker_interruption_does_not_repeat_detail_retirement`, and `test_admission_rollback_is_single_flight_across_observer_and_detail` | closed |
| TL-HLP-003 | tests/test_bridge_service.py::_service | TL-BRS-001 through TL-BRS-018; 15 non-ledger dependents | retained and rebuilt with `TaskLifecycle`, admission attachment execution, lifecycle association setup, and the observer's `release` capability; all current references resolve | closed |
| TL-HLP-004 | tests/interfaces/web/test_drain.py::_attach_task_session | TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-033, TL-DRN-035, TL-DRN-036; no non-ledger dependents | removed with adapter session-attachment/compensation authority; exact replacements use `_Service.start_task_plan` delivery factories and application LS-4 tests; symbol search is empty | closed |
| TL-HLP-005 | tests/interfaces/web/test_drain.py::_Service | TL-DRN-004, TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-008, TL-DRN-009, TL-DRN-011, TL-DRN-013, TL-DRN-017, TL-DRN-018, TL-DRN-019, TL-DRN-020, TL-DRN-021, TL-DRN-022, TL-DRN-023, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-030, TL-DRN-032, TL-DRN-033, TL-DRN-034, TL-DRN-035, TL-DRN-036; 7 non-ledger dependents | retained and rewritten as a narrow high-level task lifecycle fake with delivery-factory and terminal-delivery calls; all current references resolve | closed |
| TL-HLP-006 | tests/interfaces/web/test_drain.py::_registry | TL-DRN-004, TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-008, TL-DRN-009, TL-DRN-011, TL-DRN-012, TL-DRN-014, TL-DRN-015, TL-DRN-016, TL-DRN-017, TL-DRN-018, TL-DRN-019, TL-DRN-020, TL-DRN-021, TL-DRN-022, TL-DRN-023, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-030, TL-DRN-031, TL-DRN-032, TL-DRN-035, TL-DRN-037, TL-DRN-038, TL-DRN-039, TL-DRN-040, TL-DRN-041, TL-DRN-042; 22 non-ledger dependents | retained as the adapter fixture factory and updated for exact transport codec binding; all current references resolve in the 369-case drain/commands/host run | closed |
| TL-HLP-007 | tests/interfaces/web/test_host.py::_patch_primary | no ledger-row dependents; 21 non-ledger dependents | retained unchanged in role; exact symbol/reference audit is nonempty and all host dependents pass in the 369-case drain/commands/host run | closed |
| TL-HLP-008 | tests/interfaces/web/test_host.py::_close_hooks | TL-HST-008, TL-HST-009; 10 non-ledger dependents | retained as the adapter quiescence hook fixture; exact symbol/reference audit is nonempty and all host dependents pass in the 369-case drain/commands/host run | closed |

## LC-1b companion disposition

This append-only disposition preserves the LC-1a rows above as historical
evidence. Its finite denominator is the 22 test functions whose exact names
disappeared or changed in `git diff 66e202f -- tests/test_task_lifecycle.py
tests/test_service.py`: 12 lifecycle tests and 10 service tests. Unchanged-name
tests may use the reduced API without receiving a new disposition. A removed
pure-memory marker or cursor fault is not silently recast as supported
behavior; the surviving owner consequence is named separately where one
exists.

| ID | Previous exact test | Disposition | Current owner proof | Closure |
| --- | --- | --- | --- | --- |
| LC1B-TLC-001 | tests/test_task_lifecycle.py::test_ls_4_application_rollback_singleflights_concurrent_callers | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_admission_rollback_claim_singleflights_concurrent_callers | The coarse exact-subject rollback claim, rather than a step cursor, excludes the peer. |
| LC1B-TLC-002 | tests/test_task_lifecycle.py::test_ls_4_partial_admission_compensates_once | reanchored-owner | tests/test_service.py::test_detail_owner_attachment_rolls_back_a_failed_publication; tests/test_service.py::test_detail_owner_attachment_rechecks_service_lifecycle; tests/test_service.py::test_observed_start_adoption_rejection_retires_exact_liabilities; tests/test_service.py::test_ls_4a_admission_rollback_owner_fault_retries_from_observer; tests/test_service.py::test_whole_admission_rollback_replays_without_duplicate_effect; tests/test_task_lifecycle.py::test_lifecycle_admission_claim_owns_exact_liabilities | Failed attachment, rejected adoption, failed publication, and observer/detail faults before and after transition are reanchored to exact liabilities; repeated calls yield one transition and leave unrelated subjects untouched. The retired step-by-step Cartesian harness is not retained. |
| LC1B-TLC-003 | tests/test_task_lifecycle.py::test_lifecycle_retained_state_has_no_delivery_or_observer_resources | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_retained_state_has_no_delivery_or_observer_resources; tests/test_task_lifecycle.py::test_lifecycle_state_has_no_cleanup_step_or_marker_progress | Separate negative-name assertions exclude delivery/observer resources and cleanup-progress vocabulary without freezing unrelated imports or exact field sets. |
| LC1B-TLC-004 | tests/test_task_lifecycle.py::test_lifecycle_task_start_post_marker_retry_replays_one_receipt | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_task_start_publication_replays_one_receipt | Atomic application publication and identical receipt replay replace publication/receipt marker repair. |
| LC1B-TLC-005 | tests/test_task_lifecycle.py::test_lifecycle_admission_owns_liabilities_before_physical_markers | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_admission_claim_owns_exact_liabilities | The whole-operation claim exposes the exact unpublished session/detail liabilities without physical markers. |
| LC1B-TLC-006 | tests/test_task_lifecycle.py::test_lifecycle_observation_claim_serializes_with_settlement | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_whole_settlement_claim_excludes_reobserve_and_same_session_peer | Observation exclusion, same-association serialization, waiter wakeup, and disjoint-association independence are proved at the coarse claim owner. |
| LC1B-TLC-007 | tests/test_task_lifecycle.py::test_lifecycle_pre_marker_observation_retains_release_liability | reanchored-owner | tests/test_task_lifecycle.py::test_observation_claim_retries_from_observer_truth_without_marker_history; tests/test_service.py::test_cleanup_retry_uses_current_owner_truth_not_application_progress | Release is derived from current observer truth and exact association, not an application observation marker. |
| LC1B-TLC-008 | tests/test_task_lifecycle.py::test_lifecycle_interrupted_settlement_wait_restores_exact_state | mechanism-removed | No replacement for injected interruption inside `Condition.wait`; tests/test_task_lifecycle.py::test_lifecycle_close_wakes_settlement_claim_waiter covers the supported close/wakeup consequence. | `SettlementReservation` restoration and bytecode-level wait interruption are outside the LC-1b collaborator-fault domain. |
| LC1B-TLC-009 | tests/test_task_lifecycle.py::test_lifecycle_interrupted_settlement_activation_restores_exact_state | mechanism-removed | No replacement for injected failure inside pure-memory activation; tests/test_task_lifecycle.py::test_lifecycle_whole_settlement_claim_retries_exact_subject covers claim abandon/retry. | Activation, its repair branch, and its progress fields no longer exist. |
| LC1B-TLC-010 | tests/test_task_lifecycle.py::test_lifecycle_close_wakes_settlement_reservation_waiter | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_close_wakes_settlement_claim_waiter | Close wakes the coarse settlement claimant; no reservation layer remains. |
| LC1B-TLC-011 | tests/test_task_lifecycle.py::test_lifecycle_post_activation_failure_retries_first_unfinished_step | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_whole_settlement_claim_retries_exact_subject; tests/test_service.py::test_cleanup_retry_uses_current_owner_truth_not_application_progress | Retry reacquires the exact subject and replays the fixed sequence from owner truth; it does not resume a first-unfinished cursor. |
| LC1B-TLC-012 | tests/test_task_lifecycle.py::test_lifecycle_exact_marker_retry_does_not_repeat_physical_step | mechanism-removed | tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects; tests/test_service.py::test_s6_cleanup_replay_repeats_owner_calls_not_effects | Exact marker replay and cleanup-call uniqueness are removed; retained proof requires unique observable effects while exact cleanup calls may repeat. |
| LC1B-SVC-001 | tests/test_service.py::test_session_close_retires_only_its_exact_runtime_details | reanchored-owner | tests/test_service.py::test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent | The straight-line sequence retires only the exact detail subject and preserves an unrelated association/detail. |
| LC1B-SVC-002 | tests/test_service.py::test_failed_session_close_preserves_detail_owner_for_retry | reanchored-owner | tests/test_service.py::test_cleanup_retry_uses_current_owner_truth_not_application_progress | Dispatcher post-effect failure keeps the exact liability sealed; retry replays from observer release and reaches detail retirement. |
| LC1B-SVC-003 | tests/test_service.py::test_admission_marker_interruption_does_not_repeat_detail_retirement | reanchored-owner | tests/test_service.py::test_whole_admission_rollback_replays_without_duplicate_effect | Repeated whole rollback calls produce one exact detail-removal transition without an acknowledgement marker. |
| LC1B-SVC-004 | tests/test_service.py::test_admission_rollback_is_single_flight_across_observer_and_detail | reanchored-owner | tests/test_service.py::test_whole_admission_rollback_singleflights_concurrent_callers | Two rollback callers share one coarse claim and one observer/detail transition sequence. |
| LC1B-SVC-005 | tests/test_service.py::test_task_start_post_marker_fault_returns_one_replayable_published_view | reanchored-owner | tests/test_task_lifecycle.py::test_lifecycle_task_start_publication_replays_one_receipt; tests/test_bridge_service.py::test_task_plan_receipt_replay_does_not_recreate_delivery_or_observation | Application publication is atomic and both application and bridge replays return the one retained start result without another effect. |
| LC1B-SVC-006 | tests/test_service.py::test_observation_marker_interruption_does_not_cleanup_or_repeat_adoption | mechanism-removed | tests/test_task_lifecycle.py::test_observation_claim_retries_from_observer_truth_without_marker_history | Pure-memory observation-marker failure injection and its immediate repair call are deleted; the exact claim and resulting observer truth remain covered. |
| LC1B-SVC-007 | tests/test_service.py::test_unsubscribe_marker_interruption_does_not_repeat_physical_release | mechanism-removed | tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects | Cleanup-method invocation uniqueness is no longer a contract; observer retirement remains one observable transition under whole replay. |
| LC1B-SVC-008 | tests/test_service.py::test_ls_4b_application_settlement_retries_only_unfinished_step | reanchored-owner | tests/test_service.py::test_ls_4b_whole_operation_cleanup_replay_converges; tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects; tests/test_service.py::test_cleanup_retry_uses_current_owner_truth_not_application_progress; tests/test_service.py::test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent; tests/test_service.py::test_s6_cleanup_replay_repeats_owner_calls_not_effects; tests/test_service.py::test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers | The collective pre/post owner-fault witnesses and deterministic same-association race prove whole-operation retry, exact final absence, and unique effects without a next-step cursor. |
| LC1B-SVC-009 | tests/test_service.py::test_settlement_marker_interruption_does_not_repeat_dispatcher_close | mechanism-removed | tests/test_service.py::test_cleanup_retry_uses_current_owner_truth_not_application_progress; tests/test_service.py::test_cleanup_post_effect_interrupt_replays_calls_not_effects | The dispatcher acknowledgement marker is gone; sealed exact settlement alone treats `SessionNotFound` after a post-effect retry as already absent. |
| LC1B-SVC-010 | tests/test_service.py::test_task_close_post_finalizer_fault_returns_exact_completed_view | mechanism-removed | tests/test_task_lifecycle.py::test_lifecycle_task_replay_crosses_release_but_joins_task_close; tests/test_service.py::test_s6_cleanup_replay_repeats_owner_calls_not_effects | Injected failure inside a pure-memory finalizer and its second-call repair are removed; supported exact-token close replay and unique plan retirement remain covered. |

### LC-1b helper and boundary closure

| ID | Exact helper or boundary group | LC-1b action | Current dependents / terminal observation | Status |
| --- | --- | --- | --- | --- |
| LC1B-HLP-001 | tests/test_task_lifecycle.py::_LifecycleCounts, _LifecycleStream, _CountingOwners, _LifecycleObserver, _LifecycleDispatcher, _FaultLifecycle, _LifecycleRuntime, _lifecycle_service, _assert_lifecycle_terminal_state | removed with the step-by-step `test_ls_4_partial_admission_compensates_once` harness | Exact symbol search is empty; admission refusal and whole-rollback owner proofs are named in LC1B-TLC-002. | closed |
| LC1B-HLP-002 | tests/test_task_lifecycle.py::_publish_lifecycle_session and _publish_lifecycle_task | retained and mechanically adapted to `attach_session` plus atomic `publish_start` | All current references resolve; the helpers retain no removed marker/cursor call. | closed |
| LC1B-HLP-003 | tests/test_service.py::_publish_session and _publish_task_plan | retained and mechanically adapted to atomic application publication | Current service owner and LS-4b tests use the helpers; all references resolve without a marker/cursor API. | closed |
| LC1B-HLP-004 | tests/test_service.py::_detail_lifecycle_service | retained | Exact current dependents are `test_detail_owner_attachment_rolls_back_a_failed_publication`, `test_detail_owner_attachment_rechecks_service_lifecycle`, `test_observed_start_adoption_rejection_retires_exact_liabilities`, `test_whole_admission_rollback_replays_without_duplicate_effect`, `test_ls_4a_admission_rollback_owner_fault_retries_from_observer`, and `test_whole_admission_rollback_singleflights_concurrent_callers`. | closed |
| LC1B-HLP-005 | tests/test_bridge_service.py::_install_plan_effect | fixture-only API adaptation from marker calls to atomic `publish_start` | One `_service` fixture setup and two direct calls from `test_br_g_16_execution_command_id_is_single_flight_across_plans` resolve. No bridge-service test is added, deleted, or renamed. | closed |

`tests/test_bridge_service.py` therefore has no LC-1b behavioral-disposition
row: its existing command/receipt boundary tests remain `boundary-retained`,
and the sole diff is the fixture-only helper adaptation above. No bridge
response, receipt-replay assertion, or boundary expectation is weakened.

LC-1b closes 22 of 22 prior names: 15 are `reanchored-owner`, seven are
`mechanism-removed`, and no changed boundary test required disposition. The
companion denominator has zero pending rows, zero orphaned helpers, fixtures,
or imports, and zero knowingly uncovered supported behavior.

## LC-6 temporary-oracle retirement

These append-only rows dispose the six test definitions and one helper group
deleted with the temporary T1 oracle. They do not rewrite the original census
or the separately counted LC-1b companion.

| ID | Exact deleted test | Disposition | Enduring owner or terminal observation | Status |
| --- | --- | --- | --- | --- |
| TL-AUD-001 | tests/test_task_lifecycle_audit.py::test_real_boundary_capture_is_complete_and_plan_only | reanchored-owner | The finite public set is `test_br_g_32_start_plan_receipt_binds_resolved_intent_not_slot_ids`, `test_br_g_33_next_events_crosses_production_dispatch_as_exact_tagged_views`, `test_terminal_session_release_crosses_dispatch_as_exact_echo`, `test_task_close_crosses_production_dispatch_as_exact_echo`, `test_terminal_session_release_lost_response_replay_is_idempotent`, `test_close_task_lost_response_retry_is_exact_and_idempotent`, `test_ls_1_delivery_has_no_silent_loss_or_duplicate`, `test_br_g_33_gap_retained_tail_and_terminal_record_remain_ordered`, and `test_declined_plan_mutates_neither_files_nor_databases`; the complete public/T2 replacement run passed 32 tests. | closed |
| TL-AUD-002 | tests/test_task_lifecycle_audit.py::test_committed_boundary_baseline_matches_current_capture | mechanism-removed | The frozen temporary comparator retired only after the final normalized output matched SHA-256 `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`. | closed |
| TL-AUD-003 | tests/test_task_lifecycle_audit.py::test_corpus_format_version_is_frozen_for_active_register | mechanism-removed | The corpus and its format version have no consumer after the completed register. | closed |
| TL-AUD-004 | tests/test_task_lifecycle_audit.py::test_normalization_preserves_generated_identity_relationships_and_fixed_ids | mechanism-removed | Normalization retired with the temporary oracle after the final match; exact command-ID replay relationships remain in the public bridge and lifecycle owner tests. | closed |
| TL-AUD-005 | tests/test_task_lifecycle_audit.py::test_boundary_corruption_never_validates | mechanism-removed | The parametrized corruption-sensitivity definition retired with its comparator and baseline; no product boundary test was deleted. | closed |
| TL-AUD-006 | tests/test_task_lifecycle_audit.py::test_capture_io_and_verify_cli_contract | mechanism-removed | The audit tool's capture/verify CLI retired with the tool. This was infrastructure behavior, not the NamiSync CLI boundary. | closed |

| ID | Exact deleted helper group | Disposition | Terminal observation | Status |
| --- | --- | --- | --- | --- |
| TL-AUD-HLP-001 | `BASELINE`, `boundary_capture`, `_mutate_bridge_response`, `_mutate_cli_line`, `_mutate_event_sequence`, `_mutate_fixed_drain_identity`, `_mutate_persisted_hash`, `_mutate_filesystem_manifest` | mechanism-removed | Exact repository search found zero external dependents after deleting the runner, baseline, and self-test. | closed |

LC-6 adds six deleted-test dispositions and one helper-group disposition. All
seven are closed, giving the main ledger 137 behavioral and nine helper rows;
the LC-1b appendix remains separately counted. There are zero orphaned imports,
fixtures, or helpers and zero knowingly uncovered supported behaviors.

The temporary corpus's byte-for-byte full declined-plan stdout snapshot was
intentionally retired by the register. The enduring CLI boundary test preserves
exit 0, exact empty stderr, required user-facing prose, and zero database or
filesystem mutation; it does not elevate the entire stdout byte stream into a
permanent compatibility contract.
