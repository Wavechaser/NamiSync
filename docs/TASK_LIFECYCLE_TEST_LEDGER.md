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
  tests/test_service.py: 39
  tests/test_bridge_service.py: 18
  tests/interfaces/web/test_commands.py: 1
  tests/interfaces/web/test_drain.py: 42
  tests/interfaces/web/test_host.py: 13
  tests/interfaces/web/test_transport.py: 1
totals:
  test_rows: 129
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

This is the finite LC-0 census for lifecycle-removal test work. A pending
disposition is deliberately unassigned: no row may receive one of the three
allowed dispositions until the implementation makes that decision factual.
Replacement tests are named before an old-owner test is deleted.

## Behavioral test rows

| ID | Exact test | Matched concern | Disposition | Replacement | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TL-DSP-001 | tests/dispatcher/test_dispatcher.py::test_admission_store_accepts_then_raises_and_failed_drop_keeps_metadata_only | dispatcher admission cleanup and retained store liability | pending | | pending | pending |
| TL-DSP-002 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_releases_graphs_and_refuses_recursive_submit | dispatcher admission cleanup retry and graph retirement | pending | | pending | pending |
| TL-DSP-003 | tests/dispatcher/test_dispatcher.py::test_admission_liability_refuses_concurrent_submit_without_waiting | dispatcher admission-liability concurrency | pending | | pending | pending |
| TL-DSP-004 | tests/dispatcher/test_dispatcher.py::test_failed_admission_cleanup_caps_churn_retries_and_releases | dispatcher admission cleanup retry bound | pending | | pending | pending |
| TL-DSP-005 | tests/dispatcher/test_dispatcher.py::test_shutdown_joins_one_blocked_admission_cleanup_worker_to_deadline | dispatcher cleanup-worker shutdown | pending | | pending | pending |
| TL-DSP-006 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_worker_start_failure_preserves_exact_owner | dispatcher cleanup-worker start failure | pending | | pending | pending |
| TL-DSP-007 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_worker_does_not_join_itself_during_shutdown | dispatcher cleanup-worker self-join avoidance | pending | | pending | pending |
| TL-DSP-008 | tests/dispatcher/test_dispatcher.py::test_observed_admission_emits_pending_before_workflow_can_enter | observed admission publication order | pending | | pending | pending |
| TL-DSP-009 | tests/dispatcher/test_dispatcher.py::test_observed_attach_failure_is_never_published_or_scheduled | attachment refusal before publication | pending | | pending | pending |
| TL-DSP-010 | tests/dispatcher/test_dispatcher.py::test_failed_attach_retains_registered_rollback_for_dispatcher_retry | registered attachment rollback retention | pending | | pending | pending |
| TL-DSP-011 | tests/dispatcher/test_dispatcher.py::test_registered_attachment_callbacks_are_snapshotted_before_prepare | attachment callback snapshot | pending | | pending | pending |
| TL-DSP-012 | tests/dispatcher/test_dispatcher.py::test_registered_attachment_subclasses_are_rejected_before_prepare | attachment exact-type boundary | pending | | pending | pending |
| TL-DSP-013 | tests/dispatcher/test_dispatcher.py::test_shutdown_racing_observed_attach_rolls_back_without_scheduling | attachment and shutdown race | pending | | pending | pending |
| TL-DSP-014 | tests/dispatcher/test_dispatcher.py::test_pending_emission_failure_preserves_error_and_rolls_back_attach | publication failure attachment rollback | pending | | pending | pending |
| TL-DSP-015 | tests/dispatcher/test_dispatcher.py::test_admission_cleanup_join_failure_does_not_replace_initiating_error | cleanup join failure error precedence | pending | | pending | pending |
| TL-SVC-001 | tests/test_service.py::test_observe_returns_finished_record_without_subscribing | terminal observation without subscription | pending | | pending | pending |
| TL-SVC-002 | tests/test_service.py::test_finish_between_get_and_subscribe_returns_terminal_record | observe terminal race | pending | | pending | pending |
| TL-SVC-003 | tests/test_service.py::test_unsubscribe_closes_blocking_stream_and_uses_no_poll_timeout | observation release and blocking stream | pending | | pending | pending |
| TL-SVC-004 | tests/test_service.py::test_close_closes_every_stream_before_joining_observers | observer shutdown order | pending | | pending | pending |
| TL-SVC-005 | tests/test_service.py::test_observer_close_timeout_retains_thread_for_retry | observer join-timeout retry | pending | | pending | pending |
| TL-SVC-006 | tests/test_service.py::test_observer_direct_join_failure_retires_private_graph_and_stopped_stream | observer direct join failure retirement | pending | | pending | pending |
| TL-SVC-007 | tests/test_service.py::test_observer_join_failure_retires_stopped_and_retains_only_live_retry | observer retry-state retention | pending | | pending | pending |
| TL-SVC-008 | tests/test_service.py::test_gap_recovery_resubscribes_from_first_undelivered_sequence | observer gap recovery | pending | | pending | pending |
| TL-SVC-009 | tests/test_service.py::test_gap_recovery_releases_retired_streams_while_observation_is_live | recovered-stream retirement | pending | | pending | pending |
| TL-SVC-010 | tests/test_service.py::test_gap_recovery_stop_closes_racing_replacement_outside_observer_lock | recovery and release race | pending | | pending | pending |
| TL-SVC-011 | tests/test_service.py::test_sink_exception_closes_stream_and_does_not_block_shutdown | sink failure stream release | pending | | pending | pending |
| TL-SVC-012 | tests/test_service.py::test_observer_failure_retires_private_graph_before_wait_and_cleanup | observer failure graph retirement | pending | | pending | pending |
| TL-SVC-013 | tests/test_service.py::test_observer_stream_close_base_exception_is_contained | stream-close failure containment | pending | | pending | pending |
| TL-SVC-014 | tests/test_service.py::test_observer_close_continues_after_private_base_exception_and_retires_all | observer close continuation | pending | | pending | pending |
| TL-SVC-015 | tests/test_service.py::test_observer_close_failure_traceback_does_not_own_retired_observations | observer failure traceback ownership | pending | | pending | pending |
| TL-SVC-016 | tests/test_service.py::test_observer_single_cleanup_retires_after_private_close_base_exception | single observation cleanup retry | pending | | pending | pending |
| TL-SVC-017 | tests/test_service.py::test_sink_can_unsubscribe_itself_without_self_join_or_deadlock | callback self-unsubscribe | pending | | pending | pending |
| TL-SVC-018 | tests/test_service.py::test_adopt_rollback_is_idempotent_and_cannot_remove_replacement | observer adoption rollback identity | pending | | pending | pending |
| TL-SVC-019 | tests/test_service.py::test_reobserve_replaces_stream_from_exact_positive_sequence | exact reobservation replacement | pending | | pending | pending |
| TL-SVC-020 | tests/test_service.py::test_reobserve_rejects_nonpositive_or_noninteger_sequence | reobservation input boundary | pending | | pending | pending |
| TL-SVC-021 | tests/test_service.py::test_invalid_reobserve_preserves_existing_observation | failed reobservation custody | pending | | pending | pending |
| TL-SVC-022 | tests/test_service.py::test_reobserve_terminal_session_installs_no_stream | terminal reobservation | pending | | pending | pending |
| TL-SVC-023 | tests/test_service.py::test_service_shutdown_orders_observer_dispatcher_and_runtime | service shutdown ownership order | pending | | pending | pending |
| TL-SVC-024 | tests/test_service.py::test_service_default_close_uses_ordered_shutdown_timeout | service close ordering | pending | | pending | pending |
| TL-SVC-025 | tests/test_service.py::test_incomplete_service_shutdown_keeps_runtime_open_and_can_retry | incomplete service settlement retry | pending | | pending | pending |
| TL-SVC-026 | tests/test_service.py::test_service_close_retries_an_observer_join_failure | observer release retry during service close | pending | | pending | pending |
| TL-SVC-027 | tests/test_service.py::test_service_close_retires_private_observer_failure_before_dependency_close | observer failure retirement before dependency close | pending | | pending | pending |
| TL-SVC-028 | tests/test_service.py::test_runtime_close_failure_can_be_retried_without_repeating_shutdown | runtime close settlement progress | pending | | pending | pending |
| TL-SVC-029 | tests/test_service.py::test_concurrent_service_close_serializes_dependency_retry | concurrent service settlement | pending | | pending | pending |
| TL-SVC-030 | tests/test_service.py::test_session_close_retires_only_its_exact_runtime_details | exact session detail ownership | pending | | pending | pending |
| TL-SVC-031 | tests/test_service.py::test_failed_session_close_preserves_detail_owner_for_retry | detail-owner retention on close failure | pending | | pending | pending |
| TL-SVC-032 | tests/test_service.py::test_blocked_session_retirement_keeps_details_until_close_returns | detail retirement after dispatcher close | pending | | pending | pending |
| TL-SVC-033 | tests/test_service.py::test_service_shutdown_preserves_detail_owners_until_runtime_close_succeeds | detail-owner shutdown retention | pending | | pending | pending |
| TL-SVC-034 | tests/test_service.py::test_detail_owner_attachment_rolls_back_a_failed_publication | detail-owner publication rollback | pending | | pending | pending |
| TL-SVC-035 | tests/test_service.py::test_detail_owner_attachment_rechecks_service_lifecycle | detail attachment lifecycle recheck | pending | | pending | pending |
| TL-SVC-036 | tests/test_service.py::test_detail_owner_rollback_preserves_a_replacement_binding | exact detail-owner rollback identity | pending | | pending | pending |
| TL-SVC-037 | tests/test_service.py::test_detail_owner_attachment_precedes_post_admission_shutdown | detail attachment and shutdown race | pending | | pending | pending |
| TL-SVC-038 | tests/test_service.py::test_service_execution_opt_in_reaches_runtime_without_changing_default | execution session/detail association | pending | | pending | pending |
| TL-SVC-039 | tests/test_service.py::test_location_commands_submit_exact_typed_workflow_requests | location-session detail association | pending | | pending | pending |
| TL-BRS-001 | tests/test_bridge_service.py::test_required_attachment_refuses_execution_before_selection_or_commit | required desktop attachment | pending | | pending | pending |
| TL-BRS-002 | tests/test_bridge_service.py::test_br_g_16_retry_receipts_apply_mutations_and_multirow_changes_once | mutation receipt idempotency | pending | | pending | pending |
| TL-BRS-003 | tests/test_bridge_service.py::test_br_g_16_receipt_identity_mismatches_use_the_exact_typed_boundary | receipt conflict boundary | pending | | pending | pending |
| TL-BRS-004 | tests/test_bridge_service.py::test_plan_receipt_replay_ignores_sink_and_does_not_reattach | plan receipt replay attachment behavior | pending | | pending | pending |
| TL-BRS-005 | tests/test_bridge_service.py::test_observed_plan_attach_failure_leaves_no_receipt_or_submission_artifact | failed observed admission receipt cleanup | pending | | pending | pending |
| TL-BRS-006 | tests/test_bridge_service.py::test_observed_plan_publication_rollback_releases_observer_before_owner | observer and owner rollback order | pending | | pending | pending |
| TL-BRS-007 | tests/test_bridge_service.py::test_publication_rollback_drains_detail_and_owner_after_observer_failure | composite publication compensation | pending | | pending | pending |
| TL-BRS-008 | tests/test_bridge_service.py::test_publication_rollback_retries_owner_after_exact_observer_retires | unfinished owner compensation retry | pending | | pending | pending |
| TL-BRS-009 | tests/test_bridge_service.py::test_desktop_attachment_requirement_covers_location_session_admission | desktop attachment across location starts | pending | | pending | pending |
| TL-BRS-010 | tests/test_bridge_service.py::test_br_g_16_shutdown_does_not_repopulate_a_late_session_receipt | receipt publication and shutdown race | pending | | pending | pending |
| TL-BRS-011 | tests/test_bridge_service.py::test_br_g_16_shutdown_waits_for_an_inflight_receipt_replay | in-flight receipt replay shutdown | pending | | pending | pending |
| TL-BRS-012 | tests/test_bridge_service.py::test_br_g_16_close_before_receipt_publication_drops_late_receipt | close before receipt publication | pending | | pending | pending |
| TL-BRS-013 | tests/test_bridge_service.py::test_session_receipt_publication_does_not_reread_dispatcher_after_attach | receipt publication association truth | pending | | pending | pending |
| TL-BRS-014 | tests/test_bridge_service.py::test_br_g_16_concurrent_session_retry_admits_exactly_one_session | concurrent session receipt single flight | pending | | pending | pending |
| TL-BRS-015 | tests/test_bridge_service.py::test_br_g_16_execution_command_id_is_single_flight_across_plans | execution receipt scope | pending | | pending | pending |
| TL-BRS-016 | tests/test_bridge_service.py::test_br_g_16_id_retry_replays_before_mutable_inventory_resolution | receipt replay before volatile resolution | pending | | pending | pending |
| TL-BRS-017 | tests/test_bridge_service.py::test_br_g_16_plan_retry_replays_before_paths_are_revalidated | plan receipt replay before path validation | pending | | pending | pending |
| TL-BRS-018 | tests/test_bridge_service.py::test_br_g_16_close_and_retry_do_not_replay_a_closed_session | receipt retirement on session close | pending | | pending | pending |
| TL-CMD-001 | tests/interfaces/web/test_commands.py::test_br_g_32_start_plan_replays_before_volatile_slots_are_resolved | adapter start-response replay | pending | | pending | pending |
| TL-DRN-001 | tests/interfaces/web/test_drain.py::test_failed_admission_observer_retains_task_capacity_until_dispatcher_retry | failed-admission reservation and cleanup | pending | | pending | pending |
| TL-DRN-002 | tests/interfaces/web/test_drain.py::test_br_g_33_integrated_admission_and_visible_overflow_gap | attached delivery and visible gap | pending | | pending | pending |
| TL-DRN-003 | tests/interfaces/web/test_drain.py::test_sh_g_8_br_g_42_normal_event_envelope_is_bounded_and_lossless | attached delivery capacity boundary | pending | | pending | pending |
| TL-DRN-004 | tests/interfaces/web/test_drain.py::test_failed_start_raises_fresh_closed_failure_category | failed start-entry replay category | pending | | pending | pending |
| TL-DRN-005 | tests/interfaces/web/test_drain.py::test_invalid_plan_return_cleans_only_independently_attached_session | invalid start compensation scope | pending | | pending | pending |
| TL-DRN-006 | tests/interfaces/web/test_drain.py::test_exact_plan_with_graph_string_is_rejected_and_released | invalid start-result compensation | pending | | pending | pending |
| TL-DRN-007 | tests/interfaces/web/test_drain.py::test_validated_plan_candidate_fields_are_not_reread | start-result identity validation | pending | | pending | pending |
| TL-DRN-008 | tests/interfaces/web/test_drain.py::test_invalid_plan_ids_never_acquire_compensation_authority | compensation authority admission | pending | | pending | pending |
| TL-DRN-009 | tests/interfaces/web/test_drain.py::test_concurrent_failed_start_retires_private_exception_graph | concurrent failed-start receipt retirement | pending | | pending | pending |
| TL-DRN-010 | tests/interfaces/web/test_drain.py::test_br_g_33_shutdown_wakes_then_unsubscribes_after_handler_barrier | adapter shutdown and observation cleanup | pending | | pending | pending |
| TL-DRN-011 | tests/interfaces/web/test_drain.py::test_unsubscribe_all_retires_dependency_frames_and_preserves_retry | adapter bulk observation cleanup | pending | | pending | pending |
| TL-DRN-012 | tests/interfaces/web/test_drain.py::test_br_g_33_close_task_cleanup_order_and_retry_authority | task cleanup order | pending | | pending | pending |
| TL-DRN-013 | tests/interfaces/web/test_drain.py::test_terminal_session_release_retains_plan_receipt_and_task_capacity | terminal release retention | pending | | pending | pending |
| TL-DRN-014 | tests/interfaces/web/test_drain.py::test_terminal_session_release_lost_response_replay_is_idempotent | terminal release response replay | pending | | pending | pending |
| TL-DRN-015 | tests/interfaces/web/test_drain.py::test_delayed_terminal_release_converges_from_close_receipt | terminal release close receipt | pending | | pending | pending |
| TL-DRN-016 | tests/interfaces/web/test_drain.py::test_explicit_close_after_terminal_release_only_drops_plan | post-release task close | pending | | pending | pending |
| TL-DRN-017 | tests/interfaces/web/test_drain.py::test_release_retries_only_unfinished_session_step | release settlement progress | pending | | pending | pending |
| TL-DRN-018 | tests/interfaces/web/test_drain.py::test_close_drop_failure_still_proves_terminal_session_release | plan-drop failure after session release | pending | | pending | pending |
| TL-DRN-019 | tests/interfaces/web/test_drain.py::test_release_and_close_race_runs_each_cleanup_step_once | release and close compensation race | pending | | pending | pending |
| TL-DRN-020 | tests/interfaces/web/test_drain.py::test_release_settles_a_stale_failed_recovery_without_deadlock | failed recovery settlement | pending | | pending | pending |
| TL-DRN-021 | tests/interfaces/web/test_drain.py::test_release_settles_stale_successful_recovery_with_one_unsubscribe | successful recovery release | pending | | pending | pending |
| TL-DRN-022 | tests/interfaces/web/test_drain.py::test_release_retries_unsubscribe_after_stale_successful_recovery_failure | observation release retry | pending | | pending | pending |
| TL-DRN-023 | tests/interfaces/web/test_drain.py::test_close_and_delayed_release_race_converges_through_close_receipt | close and delayed release race | pending | | pending | pending |
| TL-DRN-024 | tests/interfaces/web/test_drain.py::test_br_g_33_failed_binding_retains_and_retries_compensation_in_order | failed binding compensation order | pending | | pending | pending |
| TL-DRN-025 | tests/interfaces/web/test_drain.py::test_coherent_return_grants_plan_cleanup_after_task_closes_during_start | start and task-close compensation authority | pending | | pending | pending |
| TL-DRN-026 | tests/interfaces/web/test_drain.py::test_compensation_interrupt_propagates_without_stranding_the_registry | compensation interruption | pending | | pending | pending |
| TL-DRN-027 | tests/interfaces/web/test_drain.py::test_cleanup_pending_start_retires_private_interruption_graph_before_replay | pending cleanup receipt replay | pending | | pending | pending |
| TL-DRN-028 | tests/interfaces/web/test_drain.py::test_replay_compensation_interruption_is_closed_and_remains_retryable | compensation replay interruption | pending | | pending | pending |
| TL-DRN-029 | tests/interfaces/web/test_drain.py::test_concurrent_replays_single_flight_failed_admission_compensation | concurrent compensation replay | pending | | pending | pending |
| TL-DRN-030 | tests/interfaces/web/test_drain.py::test_br_g_33_close_task_retries_only_unfinished_cleanup_steps | task close settlement progress | pending | | pending | pending |
| TL-DRN-031 | tests/interfaces/web/test_drain.py::test_close_task_lost_response_retry_is_exact_and_idempotent | task-close response replay | pending | | pending | pending |
| TL-DRN-032 | tests/interfaces/web/test_drain.py::test_concurrent_task_close_runs_cleanup_once_and_echoes_both_callers | concurrent task close settlement | pending | | pending | pending |
| TL-DRN-033 | tests/interfaces/web/test_drain.py::test_task_capacity_is_hard_and_existing_command_replay_still_converges | task capacity and start replay | pending | | pending | pending |
| TL-DRN-034 | tests/interfaces/web/test_drain.py::test_concurrent_capacity_reserves_once_and_same_command_joins | task reservation and start single flight | pending | | pending | pending |
| TL-DRN-035 | tests/interfaces/web/test_drain.py::test_close_refuses_session_attachment_before_lower_publication | attachment and task-close race | pending | | pending | pending |
| TL-DRN-036 | tests/interfaces/web/test_drain.py::test_repeated_task_close_bounds_active_state_and_close_receipts | task and close-receipt retention bounds | pending | | pending | pending |
| TL-DRN-037 | tests/interfaces/web/test_drain.py::test_task_drain_validates_whole_candidate_before_consuming | adapter drain ownership | pending | | pending | pending |
| TL-DRN-038 | tests/interfaces/web/test_drain.py::test_sh_g_8_observation_attaches_before_start_returns_and_pending_is_drained | observation-before-start delivery order | pending | | pending | pending |
| TL-DRN-039 | tests/interfaces/web/test_drain.py::test_br_g_33_start_is_singleflight_and_changed_intent_conflicts | adapter start single flight | pending | | pending | pending |
| TL-DRN-040 | tests/interfaces/web/test_drain.py::test_terminal_session_release_refuses_before_record_delivery | terminal delivery prerequisite | pending | | pending | pending |
| TL-DRN-041 | tests/interfaces/web/test_drain.py::test_close_task_refuses_before_terminal_record_is_drained | task close delivery prerequisite | pending | | pending | pending |
| TL-DRN-042 | tests/interfaces/web/test_drain.py::test_terminal_event_alone_does_not_earn_release_receipt | terminal record delivery truth | pending | | pending | pending |
| TL-HST-001 | tests/interfaces/web/test_host.py::test_task_registry_has_no_task_model_runtime_admission | adapter/application ownership boundary | pending | | pending | pending |
| TL-HST-002 | tests/interfaces/web/test_host.py::test_desktop_service_requires_session_attachment | desktop attachment composition | pending | | pending | pending |
| TL-HST-003 | tests/interfaces/web/test_host.py::test_startup_finalizer_quiesces_registry_before_service_close | host quiesce and service-close order | pending | | pending | pending |
| TL-HST-004 | tests/interfaces/web/test_host.py::test_startup_finalizer_keeps_cosmetics_open_until_handlers_quiesce | handler quiesce ownership | pending | | pending | pending |
| TL-HST-005 | tests/interfaces/web/test_host.py::test_startup_finalizer_preserves_quiesce_error_without_unsafe_service_close | quiesce failure containment | pending | | pending | pending |
| TL-HST-006 | tests/interfaces/web/test_host.py::test_startup_finalizer_retains_every_owner_until_complete_retry | host shutdown owner retention | pending | | pending | pending |
| TL-HST-007 | tests/interfaces/web/test_host.py::test_close_hooks_quiesce_tasks_without_retiring_appearance | close-hook task quiesce | pending | | pending | pending |
| TL-HST-008 | tests/interfaces/web/test_host.py::test_reload_readiness_refusal_records_before_normal_service_close | reload refusal shutdown order | pending | | pending | pending |
| TL-HST-009 | tests/interfaces/web/test_host.py::test_close_callback_is_nonblocking_and_quiesces_in_exact_order | nonblocking close and quiesce order | pending | | pending | pending |
| TL-HST-010 | tests/interfaces/web/test_host.py::test_handler_wait_timeout_keeps_service_open_until_explicit_retry | handler timeout and service custody | pending | | pending | pending |
| TL-HST-011 | tests/interfaces/web/test_host.py::test_observation_unsubscribe_failure_retains_appearance_until_retry | observation cleanup failure during host close | pending | | pending | pending |
| TL-HST-012 | tests/interfaces/web/test_host.py::test_bridge_rejection_precedes_a_blocked_close_status_render | bridge rejection during close | pending | | pending | pending |
| TL-HST-013 | tests/interfaces/web/test_host.py::test_closing_status_can_render_while_an_admitted_handler_is_still_waiting | admitted handler and closing presentation | pending | | pending | pending |
| TL-TRN-001 | tests/interfaces/web/test_transport.py::test_br_g_32_start_plan_receipt_binds_resolved_intent_not_slot_ids | transport start replay resolved intent | pending | | pending | pending |

## Companion helper rows

Helper rows are not behavioral dispositions. Their orphan action remains
pending until every dependent behavioral row receives its disposition.

| ID | Exact helper symbol | Dependent test group | Orphan action | Status |
| --- | --- | --- | --- | --- |
| TL-HLP-001 | tests/dispatcher/test_dispatcher.py::wait_for_admission_cleanup_attempt | TL-DSP-002, TL-DSP-004, TL-DSP-006, TL-DSP-010; no non-ledger dependents | pending | pending |
| TL-HLP-002 | tests/test_service.py::_detail_lifecycle_service | exact ledger rows TL-SVC-034 through TL-SVC-037 | pending | pending |
| TL-HLP-003 | tests/test_bridge_service.py::_service | TL-BRS-001 through TL-BRS-018; 15 non-ledger dependents | pending | pending |
| TL-HLP-004 | tests/interfaces/web/test_drain.py::_attach_task_session | TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-033, TL-DRN-035, TL-DRN-036; no non-ledger dependents | pending | pending |
| TL-HLP-005 | tests/interfaces/web/test_drain.py::_Service | TL-DRN-004, TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-008, TL-DRN-009, TL-DRN-011, TL-DRN-013, TL-DRN-017, TL-DRN-018, TL-DRN-019, TL-DRN-020, TL-DRN-021, TL-DRN-022, TL-DRN-023, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-030, TL-DRN-032, TL-DRN-033, TL-DRN-034, TL-DRN-035, TL-DRN-036; 7 non-ledger dependents | pending | pending |
| TL-HLP-006 | tests/interfaces/web/test_drain.py::_registry | TL-DRN-004, TL-DRN-005, TL-DRN-006, TL-DRN-007, TL-DRN-008, TL-DRN-009, TL-DRN-011, TL-DRN-012, TL-DRN-014, TL-DRN-015, TL-DRN-016, TL-DRN-017, TL-DRN-018, TL-DRN-019, TL-DRN-020, TL-DRN-021, TL-DRN-022, TL-DRN-023, TL-DRN-024, TL-DRN-025, TL-DRN-026, TL-DRN-027, TL-DRN-028, TL-DRN-029, TL-DRN-030, TL-DRN-031, TL-DRN-032, TL-DRN-035, TL-DRN-037, TL-DRN-038, TL-DRN-039, TL-DRN-040, TL-DRN-041, TL-DRN-042; 22 non-ledger dependents | pending | pending |
| TL-HLP-007 | tests/interfaces/web/test_host.py::_patch_primary | no ledger-row dependents; 21 non-ledger dependents | pending | pending |
| TL-HLP-008 | tests/interfaces/web/test_host.py::_close_hooks | TL-HST-008, TL-HST-009; 10 non-ledger dependents | pending | pending |
