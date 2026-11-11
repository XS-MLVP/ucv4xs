# FTQ 功能点追溯

运行证据：`results/ftq-a0c2a26cb-closeout-seed2b-20261108/cases/ftq/cases.json`（seed 2；`counts={"PASS": 931, "XFAIL": 2}`）

| 功能点 | 用例 | 本次判定 |
|---|---|---|
| FTQ-CQ-001 | `modules/commit_queue/tests/test_commit_queue.py::test_only_call_and_return_actions_enter_the_queue` (PASS) | |
| FTQ-CQ-002 | `modules/commit_queue/tests/test_commit_lane_matrix.py::test_every_memory_slot_accepts_each_lane_priority` (PASS)<br>`modules/commit_queue/tests/test_commit_queue.py::test_lane_packing_preserves_program_order_and_payload` (PASS)<br>`modules/commit_queue/tests/test_commit_stream.py::test_mixed_lane_stream_matches_independent_fifo_model` (PASS)<br>`modules/commit_queue/tests/test_commit_toggle.py::test_call_return_pointer_bits_toggle_in_every_queue_slot` (PASS) | |
| FTQ-CQ-003 | `modules/commit_queue/tests/test_commit_queue.py::test_simultaneous_enqueue_and_dequeue_preserve_fifo_without_bypass` (PASS) | |
| FTQ-CQ-004 | `modules/commit_queue/tests/test_commit_queue.py::test_capacity_guard_never_overwrites_queued_call_returns` (PASS) | |
| FTQ-CQ-005 | `modules/commit_queue/tests/test_commit_queue.py::test_reset_discards_all_pending_actions` (PASS) | |
| FTQ-RQ-001 | `modules/resolve_queue/tests/test_agent_smoke.py::test_agent_round_trip` (PASS)<br>`modules/resolve_queue/tests/test_resolve_flag.py::test_same_index_with_different_pointer_flag_has_separate_identity` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_new_index_creates_one_owned_entry_and_holds_under_backpressure` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_same_index_lanes_merge_and_advance_enqueue_by_unique_entries` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_later_resolve_updates_existing_index_without_duplicate` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_ifu_resolve_is_an_independent_always_accepted_source` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_backend_correct_direct_and_return_resolves_do_not_allocate` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_ready_consumes_exactly_one_entry_and_empty_queue_stays_idle` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_redirect_flushes_younger_entries_and_keeps_older_head` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_bpu_enqueue_at_resident_index_invalidates_stale_speculation` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_reserve_guard_stops_admission_but_preserves_drain` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_reset_discards_pending_resolution_and_reinitializes` (PASS) | |
| FTQ-RQ-002 | `modules/resolve_queue/tests/test_resolve_branch_slots.py::test_one_entry_accepts_all_eight_branch_slots_in_source_order` (PASS)<br>`modules/resolve_queue/tests/test_resolve_lane_matrix.py::test_every_backend_ifu_lane_validity_combination_has_one_owner` (PASS)<br>`modules/resolve_queue/tests/test_resolve_lane_matrix.py::test_same_index_partial_lane_groups_merge_without_duplicate` (PASS)<br>`modules/resolve_queue/tests/test_resolve_lane_matrix.py::test_backend_lane_and_ifu_same_index_merge_in_one_cycle` (PASS)<br>`modules/resolve_queue/tests/test_resolve_model.py::test_random_ownership_sequence_matches_merge_oracle` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_same_index_lanes_merge_and_advance_enqueue_by_unique_entries` (PASS)<br>`modules/resolve_queue/tests/test_resolve_slot_sweep.py::test_every_branch_slot_accepts_every_source_priority` (PASS)<br>`modules/resolve_queue/tests/test_resolve_stream.py::test_all_physical_and_branch_slots_survive_streaming_wrap` (PASS)<br>`modules/resolve_queue/tests/test_resolve_toggle.py::test_all_branch_payload_bits_toggle_in_every_physical_slot` (PASS) | |
| FTQ-RQ-003 | `modules/resolve_queue/tests/test_resolve_lane_matrix.py::test_same_index_partial_lane_groups_merge_without_duplicate` (PASS)<br>`modules/resolve_queue/tests/test_resolve_model.py::test_random_ownership_sequence_matches_merge_oracle` (PASS)<br>`modules/resolve_queue/tests/test_resolve_queue.py::test_later_resolve_updates_existing_index_without_duplicate` (PASS) | |
| FTQ-RQ-004 | `modules/resolve_queue/tests/test_resolve_queue.py::test_ifu_resolve_is_an_independent_always_accepted_source` (PASS) | |
| FTQ-RQ-005 | `modules/resolve_queue/tests/test_resolve_queue.py::test_backend_correct_direct_and_return_resolves_do_not_allocate` (PASS) | |
| FTQ-RQ-006 | `modules/resolve_queue/tests/test_resolve_queue.py::test_ready_consumes_exactly_one_entry_and_empty_queue_stays_idle` (PASS)<br>`modules/resolve_queue/tests/test_resolve_stream.py::test_all_physical_and_branch_slots_survive_streaming_wrap` (PASS) | |
| FTQ-RQ-007 | `modules/resolve_queue/tests/test_resolve_queue.py::test_redirect_flushes_younger_entries_and_keeps_older_head` (PASS) | |
| FTQ-RQ-008 | `modules/resolve_queue/tests/test_resolve_queue.py::test_bpu_enqueue_at_resident_index_invalidates_stale_speculation` (PASS) | |
| FTQ-RQ-009 | `modules/resolve_queue/tests/test_resolve_queue.py::test_reserve_guard_stops_admission_but_preserves_drain` (PASS) | |
| FTQ-RQ-010 | `modules/resolve_queue/tests/test_resolve_queue.py::test_reset_discards_pending_resolution_and_reinitializes` (PASS) | |
| FTQ-RQ-011 | `modules/resolve_queue/tests/test_resolve_overflow.py::test_ninth_branch_resolve_is_dropped_not_overwritten` (XFAIL)<br>`modules/resolve_queue/tests/test_resolve_overflow.py::test_same_cycle_group_overflow_preserves_existing_branch` (XFAIL) | |
| FTQ-TOP-001 | `modules/ftq/tests/test_ftq_core.py::test_reset_initializes_all_queue_owners_and_idles_cleanly` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_accepted_prediction_owns_one_entry_and_writes_backend_pc` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_prefetch_depth_stalls_prediction_admission_without_losing_state` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_prefetch_request_describes_the_owned_entry_and_advances_once` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_mainpipe_request_exposes_fetch_block_and_advances_once` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_prefetch_requires_second_entry_past_pnr_and_same_page` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_prefetch_rejects_cross_page_pair` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_fetch_requires_pnr_page_size_and_real_two_fetch_response` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_fetch_rejects_oversized_pair` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_s2_override_rewrites_owned_entry_and_rewinds_prefetch_fetch` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_s3_override_has_priority_and_meta_advances_pnr` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_backend_redirect_rewinds_all_owners_and_forwards_metadata` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_ifu_return_redirect_uses_redirect_meta_return_address` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_ifu_non_return_uses_explicit_target_and_can_suppress_training` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_commit_pointer_advances_once_per_retired_entry` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_commit_pointer_catches_up_to_a_repeated_retirement_pointer` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_call_return_commit_uses_stored_commit_meta` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_resolve_becomes_training_with_entry_meta_and_first_mispredict_mask` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_train_cache_is_flushed_when_redirect_is_older_than_entry` (PASS) | |
| FTQ-TOP-002 | `modules/ftq/tests/test_ftq_core.py::test_accepted_prediction_owns_one_entry_and_writes_backend_pc` (PASS) | |
| FTQ-TOP-003 | `modules/ftq/tests/test_ftq_core.py::test_prefetch_depth_stalls_prediction_admission_without_losing_state` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_full_ftq_stall_topdown_reason_and_commit_release` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_train_backpressure_ages_into_update_bubble` (PASS) | |
| FTQ-TOP-004 | `modules/ftq/tests/test_ftq_core.py::test_prefetch_request_describes_the_owned_entry_and_advances_once` (PASS) | |
| FTQ-TOP-005 | `modules/ftq/tests/test_ftq_core.py::test_two_prefetch_requires_second_entry_past_pnr_and_same_page` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_prefetch_rejects_cross_page_pair` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_two_prefetch_case_matrix` (PASS) | |
| FTQ-TOP-006 | `modules/ftq/tests/test_ftq_core.py::test_mainpipe_request_exposes_fetch_block_and_advances_once` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_fetch_requires_pnr_page_size_and_real_two_fetch_response` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_fetch_rejects_oversized_pair` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_two_fetch_rejects_cross_page_pair` (PASS) | |
| FTQ-TOP-007 | `modules/ftq/tests/test_ftq_core.py::test_s2_override_rewrites_owned_entry_and_rewinds_prefetch_fetch` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_redirect_cycle_suppresses_prediction_side_effects` (PASS) | |
| FTQ-TOP-008 | `modules/ftq/tests/test_ftq_core.py::test_s3_override_has_priority_and_meta_advances_pnr` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_s3_override_rewinds_already_advanced_prefetch_and_fetch` (PASS) | |
| FTQ-TOP-009 | `modules/ftq/tests/test_ftq_core.py::test_two_prefetch_requires_second_entry_past_pnr_and_same_page` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_two_fetch_requires_pnr_page_size_and_real_two_fetch_response` (PASS) | |
| FTQ-TOP-010 | `modules/ftq/tests/test_ftq_core.py::test_backend_redirect_rewinds_all_owners_and_forwards_metadata` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_ftq_idx_ahead_match_removes_redirect_delay` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_ftq_idx_ahead_mismatch_keeps_registered_redirect` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_backend_redirect_has_priority_over_ifu_redirect` (PASS) | |
| FTQ-TOP-011 | `modules/ftq/tests/test_ftq_core.py::test_ifu_return_redirect_uses_redirect_meta_return_address` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_ifu_non_return_uses_explicit_target_and_can_suppress_training` (PASS) | |
| FTQ-TOP-012 | `modules/ftq/tests/test_ftq_edges.py::test_backend_exception_tags_prefetch_and_fetch_until_three_blocks_pass` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_satp_flush_tags_fetch_without_inventing_an_exception` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_guest_page_fault_maps_to_gpf` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_access_fault_maps_to_af` (PASS) | |
| FTQ-TOP-013 | `modules/ftq/tests/test_ftq_core.py::test_commit_pointer_advances_once_per_retired_entry` (PASS)<br>`modules/ftq/tests/test_ftq_core.py::test_commit_pointer_catches_up_to_a_repeated_retirement_pointer` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_commit_pointer_wraps_and_stops_at_one_lap` (PASS) | |
| FTQ-TOP-014 | `modules/ftq/tests/test_ftq_core.py::test_call_return_commit_uses_stored_commit_meta` (PASS) | |
| FTQ-TOP-015 | `modules/ftq/tests/test_ftq_core.py::test_resolve_becomes_training_with_entry_meta_and_first_mispredict_mask` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_resolve_at_the_training_head_delays_its_own_dequeue` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_first_mispredict_mask_covers_every_branch_slot` (PASS)<br>`modules/ftq/tests/test_ftq_ifu_backend_merge.py::test_four_sources_can_merge_into_one_new_entry_in_one_cycle` (PASS)<br>`modules/ftq/tests/test_ftq_ifu_backend_merge.py::test_ifu_and_backend_resolve_create_the_same_new_entry_in_one_cycle` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_backend_lane_matrix_reaches_training` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_resolve_stream_fills_all_branch_slots` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_commit_lane_sweep_covers_every_queue_slot` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_branch_slot_and_source_priority_sweep` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_commit_queue_guard_and_drain` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_ifu_resolve_hits_resident_entry_in_every_physical_slot` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_same_cycle_same_index_lanes_merge_in_program_order` (PASS)<br>`modules/ftq/tests/test_ftq_integration.py::test_top_level_resolve_guard_limits_admission_and_preserves_order` (PASS) | |
| FTQ-TOP-016 | `modules/ftq/tests/test_ftq_core.py::test_train_cache_is_flushed_when_redirect_is_older_than_entry` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_redirect_at_the_training_index_keeps_that_entry_trainable` (PASS) | |
| FTQ-TOP-017 | `modules/ftq/tests/test_ftq_edges.py::test_high_index_meta_is_retained_for_redirect_train_and_commit` (PASS)<br>`modules/ftq/tests/test_ftq_meta_sweep.py::test_metadata_queues_accept_every_physical_index` (PASS)<br>`modules/ftq/tests/test_ftq_meta_toggle.py::test_every_metadata_bit_accepts_all_ones_and_all_zeros` (PASS) | |
| FTQ-TOP-018 | `modules/ftq/tests/test_ftq_edges.py::test_full_ftq_stall_topdown_reason_and_commit_release` (PASS)<br>`modules/ftq/tests/test_ftq_edges.py::test_train_backpressure_ages_into_update_bubble` (PASS) | |
| FTQ-TOP-019 | `modules/ftq/tests/test_ftq_prefetch_queue.py::test_software_prefetch_issues_source_sw_without_moving_the_fdip_pointer` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_two_queued_prefetch_requests_report_the_declared_case` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_mixed_prefetch_consumes_one_fdip_and_one_queued_request` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_queued_prefetch_wins_when_fdip_runs_past_the_preferred_distance` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_soft_prefetch_queue_capacity_drops_excess_and_keeps_fifo_order` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_enqueue_and_dequeue_on_the_same_edge_keep_queue_order` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_every_enqueue_pointer_phase_and_lane_subset_is_offered` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_every_software_prefetch_address_bit_toggles_in_all_lanes` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_eight_physical_slots_and_pointer_wrap_preserve_fifo_order` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_fdip_lane_source_is_zero_and_sw_source_is_one` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_soft_prefetch_and_backend_resolve_share_one_edge` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_soft_prefetch_and_callret_commit_share_one_edge` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_redirect_suppresses_fdip_but_keeps_a_queued_sw_prefetch` (PASS)<br>`modules/ftq/tests/test_ftq_prefetch_queue.py::test_reset_clears_a_pending_software_prefetch_queue` (PASS) | |

## 检查器与计划自检（不计硬件功能 credit）

- `modules/ftq/tests/checkers/test_commit_contract.py::test_wrong_physical_width_or_direction_is_not_accepted` (PASS)
- `modules/ftq/tests/checkers/test_commit_contract.py::test_unknown_or_missing_physical_field_is_not_an_implicit_zero` (PASS)
- `modules/ftq/tests/checkers/test_commit_contract.py::test_slot_owns_a_frozen_copy_of_the_full_lane_vector` (PASS)
- `modules/ftq/tests/checkers/test_commit_contract.py::test_two_equal_payloads_complete_as_two_ordered_input_identities` (PASS)
- `modules/ftq/tests/checkers/test_commit_contract.py::test_ledger_cannot_claim_closure_by_erasing_or_inventing_identity` (PASS)
- `modules/ftq/tests/checkers/test_commit_input_contract.py::test_callret_rejects_lossy_or_out_of_domain_input_before_encoding` (PASS)
- `modules/ftq/tests/checkers/test_commit_input_contract.py::test_all_pointer_and_action_boundaries_remain_legal` (PASS)
- `modules/ftq/tests/checkers/test_commit_input_contract.py::test_commit_encoder_does_not_accept_unvalidated_duck_typed_payload` (PASS)
- `modules/ftq/tests/checkers/test_commit_input_contract.py::test_rejected_commit_does_not_advance_the_oracle_or_start_a_driver` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_multicycle_wait_keeps_every_intermediate_commit_head` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_missing_commit_output_is_rejected_during_an_uninterrupted_wait` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_corrupt_output_leaves_a_sticky_unreconciled_slot` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_unexpected_idle_output_fails_even_without_an_explicit_training_read` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_late_output_is_checked_by_finish_before_monitors_close` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_actual_input_must_equal_the_planned_input_before_acceptance` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_replayed_phase_tick_cannot_be_associated_by_matching_payload` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_closed_monitor_cannot_be_replaced_by_live_training_reads` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_cancellation_after_the_real_edge_cannot_produce_an_empty_receipt` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_task_switches_do_not_invent_valid_only_commit_edges` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_same_payload_in_different_lanes_and_cycles_has_distinct_input_uids` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_async_reset_cancels_exactly_the_old_epoch_not_a_fresh_equal_payload` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_capacity_rejection_is_explicit_not_a_dropped_completion` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_none_action_is_filtered_without_a_response_obligation` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_invalid_cycle_budget_is_rejected_before_any_input_or_oracle_change` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_finish_cannot_silently_clear_a_still_armed_producer` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_too_small_finish_budget_does_not_claim_unfinished_work_as_completed` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_last_preedge_consumer_is_checked_before_completing_its_uid` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_sdk_ownership_rejects_a_second_driver_even_with_the_same_name` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_sdk_driver_cannot_claim_a_native_output` (PASS)
- `modules/ftq/tests/checkers/test_commit_sampling.py::test_swallowed_public_checker_failure_cannot_become_a_clean_finish` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_resolve_wait_keeps_intermediate_heads_not_just_the_last_edge` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_ftq_multicycle_wait_keeps_both_prefetch_and_fetch_channels` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_topdown_history_is_a_snapshot_not_a_mutable_reasons_mapping` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_resolve_snapshot_distinguishes_visible_and_consumed_heads` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_all_ftq_channels_share_one_phase_and_cannot_overwrite_each_other` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_large_wait_preserves_all_edges_without_overflow_or_unbounded_queues` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_task_switches_do_not_create_unsolicited_ready_fire_edges` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_closed_phase_monitor_cannot_fall_back_to_live_pin_reads` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_removed_channel_leaves_a_sticky_sampling_failure` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_replayed_tick_cannot_be_hidden_by_an_identical_idle_payload` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_cancellation_after_edge_but_before_delivery_cannot_pass_sampling_audit` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_invalid_wait_has_no_clock_or_observation_side_effect` (PASS)
- `modules/ftq/tests/checkers/test_cycle_sampling.py::test_decoder_cannot_smuggle_a_mutable_dataclass_into_a_snapshot` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_prediction_spec_owns_its_metadata_snapshot` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_prediction_spec_rejects_bad_domain_before_an_allocation_plan_is_used` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_allocate_rejects_later_duck_spec_before_any_input_progress` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_invalid_later_plan_options_cannot_change_consumer_levels_or_the_first_entry` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_full_plan_keeps_complete_domain_and_wraps_the_explicit_pointer_flag` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_direct_record_constructor_cannot_alias_mutable_metadata` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_matched_ahead_redirect_preview_is_a_detached_readonly_record` (PASS)
- `modules/ftq/tests/checkers/test_ftq_allocation.py::test_reset_cannot_return_the_old_epoch_redirect_topdown_snapshot` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_equal_callrets_have_distinct_completion_identity_and_input_meta_ancestor` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_reset_cancels_exact_old_epoch_and_does_not_invent_metadata_reset_value` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_wrong_public_response_fails_the_projected_queue_path` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_metadata_written_on_the_edge_is_not_used_for_the_old_completed_head` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_reset_does_not_hide_a_real_metadata_write_from_the_input_owned_image` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_erased_or_invented_lifecycle_evidence_cannot_be_reported_as_closure` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_equal_visible_commits_complete_once_each_not_at_their_preview` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_valid_only_held_lane_is_three_input_offers_not_one` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_reset_records_cancelled_ancestry_before_reusing_equal_payload` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_none_and_preedge_guard_rejections_are_not_silently_counted_as_accepts` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_corrupted_bpu_commit_fails_without_manual_test_assertions` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_wrong_entry_metadata_is_rejected_even_with_equal_ras_action` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_same_ssp_cannot_hide_a_wrong_metadata_owner_in_the_tosw_fields` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_native_reset_slot_meta_write_is_retained_with_its_actual_input_ancestor` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_backend_redirect_does_not_cancel_retired_callret_actions` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_native_old_head_uses_preedge_metadata_and_new_preview_uses_postedge_write` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_finish_checks_the_autonomous_last_response_without_inventing_inputs` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_second_idle_tail_cannot_hide_a_spurious_commit_after_a_correct_first_tail` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_swallowed_automatic_mismatch_is_sticky_at_reset_and_normal_fixture_finish` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_swallowed_public_checker_error_is_sticky_without_any_hardware_work` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_finish_budget_cannot_become_success_by_discarding_pending_uids` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_uninitialized_meta_is_explicit_unknown_not_a_zero_or_identity_match` (PASS)
- `modules/ftq/tests/checkers/test_ftq_commit_transactions.py::test_invalid_finish_budget_leaves_uid_and_clock_unchanged` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_fields.py::test_fixed_legal_comparison_vectors` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_fields.py::test_every_meaningful_field_is_actually_compared` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_handoff_subset_and_retry_root_are_not_guessed_from_payload` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_reset_cancelled_offer_is_not_accepted_or_completed` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_erasing_handoff_evidence_is_detected` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_repeated_rob_targets_do_not_repeat_retirement_and_full_laps_remain_legal` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_fixed_width_backwards_distance_is_characterization_not_signed_queue_age` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_invalid_negative_fetch_extent_is_not_implicitly_python_signed` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_mask_invariant_uses_program_position_not_compressed_lane_order` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_swallowed_prediction_ledger_failure_remains_sticky` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_plan_withdrawal_is_recorded_without_an_invented_acceptance_edge` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_held_equal_predictions_are_distinct_only_after_each_real_acceptance` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_unaccepted_offer_can_be_withdrawn_without_making_up_a_response` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_override_at_ready_zero_revises_one_input_allocation_and_links_request_retry` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_reset_cancelled_offer_and_fresh_equal_payload_never_share_a_retry_root` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_backend_arbitration_does_not_erase_an_already_registered_ifu_resolve` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_matched_ahead_metadata_read_has_the_old_input_ancestor_on_a_write_edge` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_finish_observes_the_second_empty_frontend_tail_slot` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_swallowed_handoff_audit_failure_cannot_be_repaired_into_a_clean_finish` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_lifecycle.py::test_reset_cancels_ifu_resolve_but_checks_old_nonreset_redirect_transport` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_independent_byte_interval_answers` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_onehot_two_prefetch` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_receiver_keeps_registered_ifu_resolve_separate_from_redirect_arbitration` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_matched_ahead_does_not_duplicate_its_source_after_the_accepting_edge` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_ifu_ras_target_is_captured_from_the_input_time_image_not_later_storage` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_training_queue_cache_and_consume_are_three_distinct_stages` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_first_mispredict_mask_follows_position_not_source_lane` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_wrong_public_payload_fails_the_automatic_top_path` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_backpressured_prediction_retains_one_uid_until_acceptance` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_swallowed_frontend_error_cannot_be_reset_or_finished_cleanly` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_finish_cannot_invent_ready_for_accepted_training` (PASS)
- `modules/ftq/tests/checkers/test_ftq_frontend_transactions.py::test_explicit_training_drain_completes_the_original_report_uid` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_redirect_guard_target_is_not_narrowed_to_the_pc_width` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_encoders_reject_duck_typed_objects_before_any_group_is_driven` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_override_cannot_silently_replace_a_missing_pointer_with_zero` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_guard_target_high_bit_reaches_the_real_public_redirect` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_redirect_pc_guard_bit_reaches_the_public_cfi_pc` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_defaultconfig_metadata_geometry_has_fixed_answers_not_live_discovery` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_wrong_native_abi_is_rejected_even_for_formerly_unchecked_metadata` (PASS)
- `modules/ftq/tests/checkers/test_ftq_input_contract.py::test_metadata_prefix_discovery_cannot_silently_accept_a_new_field` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_bad_full_slot_is_rejected_before_a_driver_exists` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_lane_vectors_and_metadata_are_immutable_input_plans` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_sdk_driver_exclusively_owns_every_input_including_reset` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_full_observation_bindings_cover_every_public_output` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_stage_is_preview_not_acceptance_and_task_switches_do_not_make_edges` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_matching_s3_metadata_and_override_are_one_atomic_slot` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_rejected_later_lane_cannot_partly_stage_or_advance_an_earlier_lane` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_consumer_merge_and_complete_payload_withdrawal_do_not_leak_old_lanes` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_replayed_input_receipt_cannot_pass_with_equal_payload` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_real_input_mutation_cannot_be_hidden_by_the_driver_call_return` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_swallowed_input_failure_is_sticky_at_normal_fixture_finish` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_staging_during_an_active_slot_fails_without_writes` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_cancellation_after_edge_does_not_become_a_cancelled_or_accepted_receipt` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_finish_cannot_silently_clear_a_staged_override` (PASS)
- `modules/ftq/tests/checkers/test_ftq_slots.py::test_invalid_cycle_budget_leaves_all_staged_state_and_ticks_unchanged` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_integer_contracts_do_not_silently_accept_bool_or_float` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_metadata_owns_its_snapshot_rather_than_a_mutable_callers_mapping` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_resolve_halfword_coordinate_cannot_lose_a_fiftieth_bit` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_bad_group_write_is_atomic_and_cannot_leave_a_valid_prefix_driven` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_complete_legal_group_is_driven_without_narrowing_the_six_bit_domain` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_equal_driver_labels_cannot_hide_a_second_physical_owner` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_group_claim_rejection_does_not_leak_an_earlier_free_pin` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_two_logical_inputs_cannot_alias_one_claimed_physical_input` (PASS)
- `modules/ftq/tests/checkers/test_input_atomicity.py::test_disjoint_claims_with_equal_component_labels_remain_legal` (PASS)
- `modules/ftq/tests/checkers/test_legal_boundary.py::test_transactions_reject_out_of_domain_values` (PASS)
- `modules/ftq/tests/checkers/test_legal_boundary.py::test_pointer_comparison_matches_circular_semantics` (PASS)
- `modules/ftq/tests/checkers/test_live_control_commit.py::test_commit_observations_are_live_and_comparable` (PASS)
- `modules/ftq/tests/checkers/test_live_control_ftq.py::test_ftq_observations_are_live_and_comparable` (PASS)
- `modules/ftq/tests/checkers/test_oracles.py::test_callret_fifo_detects_reordered_and_corrupted_payloads` (PASS)
- `modules/ftq/tests/checkers/test_oracles.py::test_callret_fifo_guard_is_part_of_the_oracle` (PASS)
- `modules/ftq/tests/checkers/test_oracles.py::test_merge_model_detects_lost_order_and_wrong_flush_scope` (PASS)
- `modules/ftq/tests/checkers/test_oracles.py::test_merge_model_keeps_the_declared_eight_branch_capacity` (PASS)
- `modules/ftq/tests/checkers/test_resolve_schema.py::test_incorrect_physical_width_or_direction_fails_before_driver_claim` (PASS)
- `modules/ftq/tests/checkers/test_resolve_schema.py::test_unknown_or_missing_field_is_not_a_silent_zero_or_new_dce` (PASS)
- `modules/ftq/tests/checkers/test_resolve_schema.py::test_full_slot_cannot_bypass_source_and_control_domains` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_input_owned_order_remains_distinct_for_identical_report_payloads` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_halfword_position_uses_start_alignment_not_raw_offset_only` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_full_branch_row_drops_excess_instead_of_wrap_or_overwrite` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_new_same_index_after_cancellation_has_a_new_entry_uid` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_multiple_held_samples_are_one_pending_report_until_actual_ready` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_simultaneous_sources_and_distinct_flag_get_exact_uids` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_real_output_mutation_fails_the_automatic_path` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_mismatch_swallowed_by_caller_cannot_be_cleared_with_reset` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_finish_does_not_invent_ready_to_discharge_accepted_reports` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_backend_filter_and_capacity_rejection_have_no_response_debt` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_redirect_and_reset_cancel_exact_report_sets_not_new_equal_payloads` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_unknown_late_source_cannot_partially_drive_or_change_the_model` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_sdk_all_input_ownership_cannot_be_duplicated` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_public_reference_error_cannot_be_swallowed_then_reset` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_ready_finish_budget_is_not_a_silent_partial_drain` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_grace_window_cancels_new_younger_reports_at_the_next_declared_boundary` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_cancelled_actual_input_cannot_be_reassociated_to_a_later_source` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_planned_input_and_real_pins_cannot_diverge_silently` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_bad_wait_and_reset_budget_leave_every_uid_and_cycle_unchanged` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_one_slot_services_old_ready_and_new_unrelated_report_atomically` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_same_entry_merge_defers_consumption_even_when_ready_is_already_high` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_same_slot_ready_completion_is_not_relabelled_as_redirect_cancellation` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_input_slot_owns_its_lane_vector_and_rejects_unvalidated_encoder_payloads` (PASS)
- `modules/ftq/tests/checkers/test_resolve_transactions.py::test_entry_start_pc_remains_bound_to_its_first_input_owner` (PASS)
- `modules/ftq/tests/test_plan_audit.py::test_every_plan_point_has_a_test_and_every_test_names_a_point` (PASS)
