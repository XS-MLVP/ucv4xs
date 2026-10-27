from bpuverify.bpu.coverage.common_query import lifetime_coverage as common_query_lifetime
from bpuverify.uras.coverage.semantic import held_call_coverage as uras_held_call_lifetime
from bpuverify.bpu.coverage.sc_admission import context_burst_lifetime_coverage as sc_context_burst_lifetime
from bpuverify.bpu.coverage.sc_loop_experience import lifetime_coverage as sc_loop_experience_lifetime
from bpuverify.bpu.coverage.joint_direction_learning import lifetime_coverage as joint_direction_learning_lifetime
from bpuverify.bpu.coverage.joint_originals import lifetime_coverage as joint_originals_lifetime
from bpuverify.bpu.coverage.statistical_prefix import lifetime_coverage as statistical_prefix_lifetime
from bpuverify.bpu.coverage.statistical_prefix import context_lifetime_coverage as sc_context_lifetime
from bpuverify.bpu.coverage.statistical_prefix import concurrent_context_lifetime_coverage as sc_concurrent_context_lifetime
from bpuverify.bpu.coverage.ahead_working_set import prefix_lifetime_coverage as ahead_prefix_working_set_lifetime
from bpuverify.bpu.coverage.sc_early_learning import lifetime_coverage as sc_early_learning_lifetime
from bpuverify.bpu.coverage.sc_admission import lifetime_coverage as sc_admission_lifetime
from bpuverify.bpu.coverage.sc_admission import burst_lifetime_coverage as sc_feedback_burst_lifetime
from bpuverify.bpu.coverage.sc_admission import read_only_lifetime_coverage as sc_read_no_write_lifetime
from bpuverify.bpu.coverage.history_working_set import short_path_retention_coverage as short_path_retention_lifetime
from bpuverify.bpu.coverage.history_working_set import short_path_mixed_coverage as short_path_mixed_lifetime
from bpuverify.utage.coverage.predecessor_retention import lifetime_coverage as predecessor_retention_lifetime
from bpuverify.bpu.coverage.indirect_path_ownership import lifetime_coverage as indirect_path_lifetime
from bpuverify.bpu.coverage.conditional_prefix import lifetime_coverage as conditional_prefix_lifetime
from bpuverify.bpu.coverage.main_cold_original_order import lifetime_coverage as main_cold_original_order_lifetime
from bpuverify.bpu.coverage.main_original_order import lifetime_coverage as main_original_order_lifetime
from bpuverify.ras.coverage.commit_action import lifetime_coverage as ras_commit_action_lifetime
from bpuverify.bpu.coverage.miss_authority import lifetime_coverage as miss_authority_lifetime
"""Acceptance for matrices split into independent process-local contributions."""
from toffee import CoverageDatabase

from bpuverify.tage.coverage.dual import tage_dual_shadow_coverage_model
from bpuverify.tage.coverage.retained import tage_retained_owner_coverage_model
from bpuverify.bpu.coverage.abtb.supplemental import CounterCoverage
from bpuverify.bpu.coverage.alignment import coverage as alignment_coverage
from bpuverify.bpu.coverage.sc.used import used_coverage, history_coverage
from bpuverify.bpu.coverage.sc.bounds import bounds_coverage
from bpuverify.bpu.coverage.ras_micro import micro_coverage
from bpuverify.bpu.coverage.tage.selector import selector_coverage,routing_coverage
from bpuverify.bpu.coverage.tage.aging import aging_coverage, RULES as AGING_RULES
from bpuverify.bpu.coverage.ittage import directory_coverage, DIRECTORY_RULES
from bpuverify.bpu.coverage.ittage_aging import aging_coverage as ittage_aging_coverage, RULES as ITTAGE_AGING_RULES
from bpuverify.uras.coverage.semantic import semantic_coverage as uras_semantic_coverage, RULES as URAS_RULES
from bpuverify.ittage.coverage.semantic import target_coverage as ittage_target_coverage, RULES as ITTAGE_TARGET_RULES
from bpuverify.sc.coverage.semantic import semantic_coverage as sc_semantic_coverage, RULES as SC_SEMANTIC_RULES
from bpuverify.sc.coverage.eligibility import EligibilityCoverage
from bpuverify.sc.coverage.original_feedback import FeedbackCoverage
from bpuverify.sc.coverage.original_enable import EnableCoverage
from bpuverify.bpu.coverage.recovery_arbitration import RecoveryCoverage
from bpuverify.utage.coverage.learning_retention import LearningRetentionCoverage
from bpuverify.bpu.coverage.short_context_ownership import ShortContextCoverage,ShortDirectionCoverage
from bpuverify.bpu.coverage.main_sibling import lifetime_coverage as main_sibling_lifetime
from bpuverify.bpu.coverage.ras_nested_recursion import lifetime_coverage as ras_nested_lifetime
from bpuverify.utage.coverage.enable_lifetime import lifetime_coverage as utage_enable_lifetime
from bpuverify.bpu.coverage.ras_wrapped_recursion import lifetime_coverage as ras_wrapped_lifetime
from bpuverify.bpu.coverage.ras_layered_recursion import lifetime_coverage as ras_layered_lifetime
from bpuverify.bpu.coverage.ras_adjacent_recursion import lifetime_coverage as ras_adjacent_lifetime
from bpuverify.bpu.coverage.opposed_learning_pair import lifetime_coverage as opposed_learning_pair_lifetime
from bpuverify.bpu.coverage.interior_prefix_learning import lifetime_coverage as interior_prefix_learning_lifetime
from bpuverify.bpu.coverage.service_relearning import lifetime_coverage as service_relearning_lifetime
from bpuverify.bpu.coverage.shared_saturation import lifetime_coverage as shared_saturation_lifetime
from bpuverify.bpu.coverage.main_accepted_recovery import lifetime_coverage as main_accepted_recovery_lifetime
from bpuverify.bpu.coverage.main_coincident_recovery import lifetime_coverage as main_coincident_recovery_lifetime
from bpuverify.bpu.coverage.main_duplicate_cleanup import lifetime_coverage as main_duplicate_cleanup_lifetime
from bpuverify.mbtb.coverage.reset_lifetime import lifetime_coverage as mbtb_reset_lifetime
from bpuverify.ubtb.coverage.reset_lifetime import lifetime_coverage as ubtb_reset_lifetime
from bpuverify.mbtb.coverage.query_reset import lifetime_coverage as mbtb_query_lifetime
from bpuverify.ubtb.coverage.query_reset import lifetime_coverage as ubtb_query_lifetime
from bpuverify.bpu.coverage.joint_lifetime import lifetime_coverage as joint_lifetime
from bpuverify.mbtb.coverage.cleanup_reset import lifetime_coverage as cleanup_reset_lifetime
from bpuverify.utage.coverage.read_lifetime import lifetime_coverage as utage_read_lifetime
from bpuverify.utage.coverage.read_lifetime import late_replacement_coverage as utage_late_replacement_lifetime
from bpuverify.bpu.coverage.short_context_ownership import working_set_coverage as short_cross_branch_lifetime
from bpuverify.bpu.coverage.short_competition import lifetime_coverage as short_competition_lifetime
from bpuverify.utage.coverage.ancestor_lifetime import lifetime_coverage as utage_ancestor_lifetime
from bpuverify.utage.coverage.query_cohort import lifetime_coverage as query_cohort_lifetime
from bpuverify.utage.coverage.query_identity import lifetime_coverage as query_identity_lifetime
from bpuverify.utage.coverage.selective_protection import lifetime_coverage as selective_protection_lifetime
from bpuverify.utage.coverage.delayed_agreement import lifetime_coverage as delayed_agreement_lifetime
from bpuverify.bpu.coverage.neutral_recovery import lifetime_coverage as neutral_recovery_lifetime
from bpuverify.bpu.coverage.block_entry_learning import lifetime_coverage as block_entry_learning_lifetime
from bpuverify.bpu.coverage.entry_protection import lifetime_coverage as entry_protection_lifetime
from bpuverify.bpu.coverage.short_revisit import lifetime_coverage as short_revisit_lifetime
from bpuverify.bpu.coverage.cross_block_learning import lifetime_coverage as cross_block_learning_lifetime
from bpuverify.bpu.coverage.late_correction_learning import lifetime_coverage as late_correction_learning_lifetime
from bpuverify.bpu.coverage.competing_correction import lifetime_coverage as competing_correction_lifetime
from bpuverify.utage.coverage.delayed_protection import lifetime_coverage as delayed_protection_lifetime
from bpuverify.utage.coverage.long_protection import lifetime_coverage as long_protection_lifetime
from bpuverify.bpu.coverage.working_set_replacement import lifetime_coverage as working_set_replacement_lifetime
from bpuverify.utage.coverage.learning_persistence import lifetime_coverage as learning_persistence_lifetime
from bpuverify.utage.coverage.catalog import utage_shadow_ring_coverage_model
from bpuverify.utage.coverage.supplemental import utage_partial_wrap_coverage_model
from bpuverify.common.coverage.pipeline_ownership import ownership_coverage, PROFILES as OWNERSHIP_PROFILES
from bpuverify.ras.coverage.semantic import semantic_coverage as ras_action_coverage, ROLES as RAS_ACTION_ROLES
from bpuverify.utage.coverage.semantic import semantic_coverage as utage_semantic_coverage, BOUNDARY_RULES as UTAGE_BOUNDARY_RULES, TYPE_RULES as UTAGE_TYPE_RULES
from bpuverify.abtb.coverage.semantic import semantic_coverage as abtb_semantic_coverage, RULES as ABTB_SEMANTIC_RULES
from bpuverify.mbtb.coverage.semantic import semantic_coverage as mbtb_semantic_coverage, RULES as MBTB_SEMANTIC_RULES
from bpuverify.tage.coverage.semantic import semantic_coverage as tage_semantic_coverage, RULES as TAGE_SEMANTIC_RULES
from bpuverify.bpu.coverage.tage.learning import learning_coverage, RULES as TAGE_LEARNING_RULES
from bpuverify.bpu.coverage.tage.fast_routing import routing_coverage as fast_routing_coverage, RULES as FAST_ROUTING_RULES
from bpuverify.bpu.coverage.tage.alternate import alternate_coverage, RULES as ALTERNATE_RULES
from bpuverify.bpu.coverage.tage.interleaved import interleaved_coverage, RULES as INTERLEAVED_RULES
from bpuverify.bpu.coverage.pipeline import pipeline_coverage, RULES as PIPELINE_RULES
from bpuverify.bpu.coverage.ras_redo import redo_coverage, RULES as RAS_REDO_RULES
from bpuverify.bpu.coverage.ras_return_recovery import return_recovery_coverage, RULES as RAS_RETURN_RULES, STORAGES
from bpuverify.bpu.coverage.micro_capacity import capacity_coverage, RULES as MICRO_CAPACITY_RULES
from bpuverify.bpu.coverage.micro_forwarding import forwarding_coverage, RULES as MICRO_FORWARDING_RULES
from bpuverify.bpu.coverage.main_learning import learning_coverage as main_learning_coverage, RULES as MAIN_LEARNING_RULES
from bpuverify.bpu.coverage.direction_learning import direction_coverage, RULES as DIRECTION_RULES
from bpuverify.bpu.coverage.direction_forwarding import forwarding_coverage as direction_forwarding_coverage, RULES as DIRECTION_FORWARDING_RULES
from bpuverify.bpu.coverage.direction_service import service_coverage as direction_service_coverage, RULES as DIRECTION_SERVICE_RULES
from bpuverify.bpu.coverage.direction_useful import useful_coverage as direction_useful_coverage, RULES as DIRECTION_USEFUL_RULES
from bpuverify.bpu.coverage.indirect_learning import indirect_coverage, RULES as INDIRECT_RULES
from bpuverify.bpu.coverage.indirect_service import service_coverage as indirect_service_coverage, RULES as INDIRECT_SERVICE_RULES, CLASSES as INDIRECT_CLASSES
from bpuverify.bpu.coverage.main_service import main_service_coverage, RULES as MAIN_SERVICE_RULES, MODES as MAIN_SERVICE_MODES
from bpuverify.bpu.coverage.common_history import common_history_coverage, RULES as COMMON_HISTORY_RULES, FAMILIES as COMMON_HISTORY_FAMILIES
from bpuverify.bpu.coverage.main_rewrite import main_rewrite_coverage, RULES as MAIN_REWRITE_RULES
from bpuverify.bpu.coverage.ras_reuse import ras_reuse_coverage, RULES as RAS_REUSE_RULES
from bpuverify.bpu.coverage.ras_neutral_gap import neutral_gap_coverage, RULES as RAS_NEUTRAL_GAP_RULES
from bpuverify.bpu.coverage.direction_capacity import capacity_coverage as direction_capacity_coverage, RULES as DIRECTION_CAPACITY_RULES
from bpuverify.bpu.coverage.direction_replacement import replacement_coverage as direction_replacement_coverage, RULES as DIRECTION_REPLACEMENT_RULES
from bpuverify.bpu.coverage.direction_migration import migration_coverage as direction_migration_coverage, RULES as DIRECTION_MIGRATION_RULES
from bpuverify.bpu.coverage.direction_burst import burst_coverage as direction_burst_coverage, RULES as DIRECTION_BURST_RULES
from bpuverify.bpu.coverage.ahead_learning import ahead_learning_coverage, RULES as AHEAD_LEARNING_RULES
from bpuverify.bpu.coverage.early_direction import direction_coverage as early_direction_coverage, RULES as EARLY_DIRECTION_RULES, CLASSES as EARLY_DIRECTION_CLASSES
from bpuverify.bpu.coverage.early_opposition import opposition_coverage as early_opposition_coverage, RULES as EARLY_OPPOSITION_RULES
from bpuverify.bpu.coverage.early_positive import positive_coverage as early_positive_coverage, RULES as EARLY_POSITIVE_RULES
from bpuverify.mbtb.coverage.catalog import mbtb_replacement_coverage_model,mbtb_multi_hit_cleanup_coverage_model,mbtb_entry_keys_coverage_model
from bpuverify.mbtb.coverage.two_key_lifetime import lifetime_coverage as two_key_lifetime
from bpuverify.mbtb.coverage.cleanup_lifetime import lifetime_coverage as cleanup_lifetime
from bpuverify.mbtb.coverage.shared_service import lifetime_coverage as shared_service_lifetime
from bpuverify.bpu.coverage.selective_learning import lifetime_coverage as selective_learning_lifetime
from bpuverify.utage.coverage.cross_branch_protection import lifetime_coverage as cross_branch_protection_lifetime
from bpuverify.utage.coverage.returning_original import lifetime_coverage as returning_original_lifetime
from bpuverify.utage.coverage.dual_source import lifetime_coverage as dual_source_lifetime
from bpuverify.utage.coverage.saved_vector import lifetime_coverage as saved_vector_lifetime
from bpuverify.bpu.coverage.joint_stream import lifetime_coverage as joint_stream_lifetime
from bpuverify.utage.coverage.displaced_branch import lifetime_coverage as displaced_branch_lifetime
from bpuverify.utage.coverage.instruction_confidence import lifetime_coverage as instruction_confidence_lifetime
from bpuverify.sc.coverage.neutral_boundary import lifetime_coverage as sc_neutral_boundary_lifetime
from bpuverify.bpu.coverage.superseding_recovery import lifetime_coverage as superseding_recovery_lifetime
from bpuverify.bpu.coverage.owned_return_stack import lifetime_coverage as owned_return_stack_lifetime
from bpuverify.sc.coverage.catalog import sc_same_way_feedback_coverage_model
from bpuverify.mbtb.coverage.catalog import mbtb_cleanup_overlap_coverage_model
from bpuverify.common.pytest.regression import PROFILES


def validate_parallel_case_coverage(report, *, profile='production'):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    database = CoverageDatabase.from_dict(report)
    counter = CounterCoverage()
    mbtb_physical = mbtb_replacement_coverage_model()
    entry_keys_physical = mbtb_entry_keys_coverage_model()
    cleanup_physical = mbtb_cleanup_overlap_coverage_model()
    source_lifetimes = tuple(group for factory in (
        EligibilityCoverage, FeedbackCoverage, EnableCoverage, RecoveryCoverage, LearningRetentionCoverage,
        ShortContextCoverage,ShortDirectionCoverage)
        for group in factory(None).groups.values()) + tuple(
            factory(status) for factory in (main_sibling_lifetime, ras_nested_lifetime,
                utage_enable_lifetime, ras_wrapped_lifetime, ras_layered_lifetime, ras_adjacent_lifetime, opposed_learning_pair_lifetime, interior_prefix_learning_lifetime, shared_saturation_lifetime, service_relearning_lifetime, main_accepted_recovery_lifetime, main_duplicate_cleanup_lifetime,
                mbtb_reset_lifetime, ubtb_reset_lifetime,
                mbtb_query_lifetime, ubtb_query_lifetime, joint_lifetime, cleanup_reset_lifetime,
                utage_read_lifetime, utage_ancestor_lifetime,
                query_cohort_lifetime, query_identity_lifetime, selective_protection_lifetime, long_protection_lifetime, delayed_protection_lifetime, delayed_agreement_lifetime, neutral_recovery_lifetime, block_entry_learning_lifetime, entry_protection_lifetime, short_revisit_lifetime, cross_block_learning_lifetime, late_correction_learning_lifetime, competing_correction_lifetime, working_set_replacement_lifetime, learning_persistence_lifetime, miss_authority_lifetime, ras_commit_action_lifetime, main_original_order_lifetime, main_cold_original_order_lifetime, indirect_path_lifetime, conditional_prefix_lifetime, common_query_lifetime, statistical_prefix_lifetime, sc_early_learning_lifetime, sc_admission_lifetime, predecessor_retention_lifetime, sc_feedback_burst_lifetime, sc_read_no_write_lifetime, short_path_retention_lifetime, sc_context_lifetime, sc_concurrent_context_lifetime, ahead_prefix_working_set_lifetime) for status in ('reached', 'checked'))
    source_lifetimes += tuple(factory(status) for factory in (uras_held_call_lifetime,sc_context_burst_lifetime,short_path_mixed_lifetime,utage_late_replacement_lifetime,short_cross_branch_lifetime,short_competition_lifetime,sc_loop_experience_lifetime,joint_direction_learning_lifetime,joint_originals_lifetime,main_coincident_recovery_lifetime,two_key_lifetime,cleanup_lifetime,shared_service_lifetime,selective_learning_lifetime,cross_branch_protection_lifetime,returning_original_lifetime,dual_source_lifetime,saved_vector_lifetime,joint_stream_lifetime,displaced_branch_lifetime,instruction_confidence_lifetime)
                              for status in ('reached', 'checked'))
    source_lifetimes += tuple(sc_neutral_boundary_lifetime(status) for status in ('reached', 'checked'))
    source_lifetimes += tuple(superseding_recovery_lifetime(status) for status in ('reached', 'checked'))
    source_lifetimes += tuple(owned_return_stack_lifetime(status) for status in ('reached', 'checked'))
    # Always retain/validate every physical schema, including unhit cells.
    for expected in (*counter.physical_groups, mbtb_physical, entry_keys_physical, cleanup_physical):
        actual = database.groups.get(expected.instance)
        if actual is None or actual.definition.digest != expected.definition.digest:
            raise ValueError(f'missing or changed parallel matrix schema: {expected.instance}')
    for factory in (tage_dual_shadow_coverage_model, tage_retained_owner_coverage_model,
                    lambda: counter.semantic,
                    *((lambda: counter.transitions,) if profile == 'physical' else ()),
                    *((lambda: mbtb_physical,) if profile == 'physical' else ()),
                    *((lambda: entry_keys_physical,) if profile == 'physical' else ()),
                    *((lambda: cleanup_physical,) if profile == 'physical' else ()),
                    mbtb_multi_hit_cleanup_coverage_model,
                    sc_same_way_feedback_coverage_model,
                    utage_shadow_ring_coverage_model, utage_partial_wrap_coverage_model,
                    alignment_coverage, used_coverage, history_coverage,
                    lambda: bounds_coverage('reached'), lambda: bounds_coverage('checked'),
                    lambda: micro_coverage('reached'), lambda: micro_coverage('checked'),
                    *(lambda family=family,status=status:selector_coverage(family,status)
                        for family in ('update','selection') for status in ('reached','checked')),
                    lambda:routing_coverage('reached'),lambda:routing_coverage('checked'),
                    *(lambda family=family,status=status:aging_coverage(family,status)
                        for family in AGING_RULES for status in ('reached','checked')),
                    *(lambda family=family,status=status:directory_coverage(family,status)
                        for family in DIRECTORY_RULES for status in ('reached','checked')),
                    *(lambda family=family,status=status:ittage_aging_coverage(family,status)
                        for family in ITTAGE_AGING_RULES for status in ('reached','checked')),
                    *(lambda status=status:uras_semantic_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:ittage_target_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:sc_semantic_coverage(status) for status in ('reached','checked')),
                    *(lambda group=group:group for group in source_lifetimes),
                    *(lambda dut=dut,status=status:ownership_coverage(dut,status)
                        for dut in OWNERSHIP_PROFILES for status in ('reached','checked')),
                    *(lambda status=status:ras_action_coverage(status) for status in ('reached','checked')),
                    *(lambda family=family,status=status:utage_semantic_coverage(family,status)
                        for family in ('boundary','resolved-type') for status in ('reached','checked')),
                    *(lambda status=status:abtb_semantic_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:tage_semantic_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:learning_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:fast_routing_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:fast_routing_coverage(status,'later-first') for status in ('reached','checked')),
                    *(lambda status=status:alternate_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:interleaved_coverage(status) for status in ('reached','checked')),
                    *(lambda family=family,status=status:pipeline_coverage(family,status)
                        for family in PIPELINE_RULES for status in ('reached','checked')),
                    *(lambda calls=calls,status=status:redo_coverage(calls,status)
                        for calls in RAS_REDO_RULES for status in ('reached','checked')),
                    *(lambda calls=calls,storage=storage,status=status:return_recovery_coverage(calls,storage,status)
                        for calls in RAS_RETURN_RULES for storage in STORAGES for status in ('reached','checked')),
                    *(lambda status=status:capacity_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:forwarding_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:main_learning_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_forwarding_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_service_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_useful_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:indirect_coverage(status) for status in ('reached','checked')),
                    *(lambda table=table,status=status:indirect_service_coverage(table,status)
                        for table in INDIRECT_CLASSES for status in ('reached','checked')),
                    *(lambda mode=mode,status=status:main_service_coverage(mode,status)
                        for mode in MAIN_SERVICE_MODES for status in ('reached','checked')),
                    *(lambda family=family,status=status:common_history_coverage(family,status)
                        for family in COMMON_HISTORY_FAMILIES for status in ('reached','checked')),
                    *(lambda status=status:main_rewrite_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:ras_reuse_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:neutral_gap_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_capacity_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:direction_replacement_coverage(status) for status in ('reached','checked')),
                    *(lambda origin=origin,status=status:direction_migration_coverage(origin,status)
                        for origin in (0,1) for status in ('reached','checked')),
                    *(lambda origin=origin,status=status:direction_burst_coverage(origin,status)
                        for origin in (0,1) for status in ('reached','checked')),
                    *(lambda status=status:ahead_learning_coverage(status) for status in ('reached','checked')),
                    *(lambda tag_class=tag_class,status=status:early_direction_coverage(tag_class,status)
                        for tag_class in EARLY_DIRECTION_CLASSES for status in ('reached','checked')),
                    *(lambda status=status:early_opposition_coverage(status) for status in ('reached','checked')),
                    *(lambda status=status:early_positive_coverage(status) for status in ('reached','checked')),
                    *(lambda family=family,status=status:mbtb_semantic_coverage(family,status)
                        for family in MBTB_SEMANTIC_RULES for status in ('reached','checked'))):
        expected = factory()
        actual = database.groups.get(expected.instance)
        if actual is None or actual.definition.digest != expected.definition.digest:
            raise ValueError(f'missing or changed parallel matrix schema: {expected.instance}')
        try:
            actual.assert_coverage(100.0)
        except AssertionError as error:
            raise ValueError(f'incomplete parallel matrix: {expected.instance}: {error}') from error
    return dict(regression_profile=profile,
        source_lifetimes={group.instance:dict(full_required=True,
            coverage=database.groups[group.instance].coverage) for group in source_lifetimes},
        semantic=dict(total_bins=48, coverage=database.groups[counter.semantic.instance].coverage,
                      full_required=True),
        physical=dict(total_bins=12288, coverage=database.groups[counter.transitions.instance].coverage,
                      full_required=profile == 'physical'),
        threshold_votes=dict(total_bins=52,full_required=True,
            reached=database.groups[bounds_coverage('reached').instance].cross_coverage('way_rule'),
            checked=database.groups[bounds_coverage('checked').instance].cross_coverage('way_rule')),
        micro_ras=dict(total_bins=4,full_required=True,
            reached=database.groups[micro_coverage('reached').instance].coverage,
            checked=database.groups[micro_coverage('checked').instance].coverage),
        tage_selector={family:dict(rule_bins=6 if family=='update' else 2,
            confidence_bins=2,full_required=True,
            reached=database.groups[selector_coverage(family,'reached').instance].coverage,
            checked=database.groups[selector_coverage(family,'checked').instance].coverage)
            for family in ('update','selection')},
        tage_selector_routing=dict(total_bins=8,full_required=True,
            reached=database.groups[routing_coverage('reached').instance].coverage,
            checked=database.groups[routing_coverage('checked').instance].coverage),
        tage_useful_aging={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[aging_coverage(family,'reached').instance].coverage,
            checked=database.groups[aging_coverage(family,'checked').instance].coverage)
            for family,rules in AGING_RULES.items()},
        ittage_region_directory={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[directory_coverage(family,'reached').instance].coverage,
            checked=database.groups[directory_coverage(family,'checked').instance].coverage)
            for family,rules in DIRECTORY_RULES.items()},
        ittage_useful_aging={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[ittage_aging_coverage(family,'reached').instance].coverage,
            checked=database.groups[ittage_aging_coverage(family,'checked').instance].coverage)
            for family,rules in ITTAGE_AGING_RULES.items()},
        uras_semantic_events=dict(rule_bins=len(URAS_RULES),full_required=True,
            reached=database.groups[uras_semantic_coverage('reached').instance].coverage,
            checked=database.groups[uras_semantic_coverage('checked').instance].coverage),
        ittage_full_target_learning=dict(rule_bins=len(ITTAGE_TARGET_RULES),full_required=True,
            reached=database.groups[ittage_target_coverage('reached').instance].coverage,
            checked=database.groups[ittage_target_coverage('checked').instance].coverage),
        sc_history_semantics=dict(rule_bins=len(SC_SEMANTIC_RULES),full_required=True,
            reached=database.groups[sc_semantic_coverage('reached').instance].coverage,
            checked=database.groups[sc_semantic_coverage('checked').instance].coverage),
        ras_pop_and_push=dict(role_bins=len(RAS_ACTION_ROLES),full_required=True,
            reached=database.groups[ras_action_coverage('reached').instance].coverage,
            checked=database.groups[ras_action_coverage('checked').instance].coverage),
        utage_semantics={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[utage_semantic_coverage(family,'reached').instance].coverage,
            checked=database.groups[utage_semantic_coverage(family,'checked').instance].coverage)
            for family,rules in (('boundary',UTAGE_BOUNDARY_RULES),('resolved-type',UTAGE_TYPE_RULES))},
        abtb_write_ownership=dict(rule_bins=len(ABTB_SEMANTIC_RULES),full_required=True,
            reached=database.groups[abtb_semantic_coverage('reached').instance].coverage,
            checked=database.groups[abtb_semantic_coverage('checked').instance].coverage),
        tage_history_ownership=dict(rule_bins=len(TAGE_SEMANTIC_RULES),full_required=True,
            reached=database.groups[tage_semantic_coverage('reached').instance].coverage,
            checked=database.groups[tage_semantic_coverage('checked').instance].coverage),
        tage_sparse_learning=dict(rule_bins=len(TAGE_LEARNING_RULES),full_required=True,
            reached=database.groups[learning_coverage('reached').instance].coverage,
            checked=database.groups[learning_coverage('checked').instance].coverage),
        tage_raw_qualified_routing=dict(rule_bins=len(FAST_ROUTING_RULES),full_required=True,
            reached=database.groups[fast_routing_coverage('reached').instance].coverage,
            checked=database.groups[fast_routing_coverage('checked').instance].coverage),
        tage_late_branch_discovery=dict(rule_bins=len(FAST_ROUTING_RULES),full_required=True,
            reached=database.groups[fast_routing_coverage('reached','later-first').instance].coverage,
            checked=database.groups[fast_routing_coverage('checked','later-first').instance].coverage),
        tage_alternate_hierarchy=dict(rule_bins=len(ALTERNATE_RULES),full_required=True,
            reached=database.groups[alternate_coverage('reached').instance].coverage,
            checked=database.groups[alternate_coverage('checked').instance].coverage),
        tage_interleaved_resolve=dict(rule_bins=len(INTERLEAVED_RULES),full_required=True,
            reached=database.groups[interleaved_coverage('reached').instance].coverage,
            checked=database.groups[interleaved_coverage('checked').instance].coverage),
        owned_pipeline={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[pipeline_coverage(family,'reached').instance].coverage,
            checked=database.groups[pipeline_coverage(family,'checked').instance].coverage)
            for family,rules in PIPELINE_RULES.items()},
        ras_redo_boundaries={str(calls):dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[redo_coverage(calls,'reached').instance].coverage,
            checked=database.groups[redo_coverage(calls,'checked').instance].coverage)
            for calls,rules in RAS_REDO_RULES.items()},
        ras_return_recovery={f'{calls}.{storage}':dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[return_recovery_coverage(calls,storage,'reached').instance].coverage,
            checked=database.groups[return_recovery_coverage(calls,storage,'checked').instance].coverage)
            for calls,rules in RAS_RETURN_RULES.items() for storage in STORAGES},
        micro_capacity=dict(rule_bins=len(MICRO_CAPACITY_RULES),full_required=True,
            reached=database.groups[capacity_coverage('reached').instance].coverage,
            checked=database.groups[capacity_coverage('checked').instance].coverage),
        micro_positive_forwarding=dict(rule_bins=len(MICRO_FORWARDING_RULES),full_required=True,
            reached=database.groups[forwarding_coverage('reached').instance].coverage,
            checked=database.groups[forwarding_coverage('checked').instance].coverage),
        owned_main_learning=dict(rule_bins=len(MAIN_LEARNING_RULES),full_required=True,
            reached=database.groups[main_learning_coverage('reached').instance].coverage,
            checked=database.groups[main_learning_coverage('checked').instance].coverage),
        owned_direction_learning=dict(rule_bins=len(DIRECTION_RULES),full_required=True,
            reached=database.groups[direction_coverage('reached').instance].coverage,
            checked=database.groups[direction_coverage('checked').instance].coverage),
        owned_direction_forwarding=dict(rule_bins=len(DIRECTION_FORWARDING_RULES),full_required=True,
            reached=database.groups[direction_forwarding_coverage('reached').instance].coverage,
            checked=database.groups[direction_forwarding_coverage('checked').instance].coverage),
        owned_direction_service=dict(rule_bins=len(DIRECTION_SERVICE_RULES),full_required=True,
            reached=database.groups[direction_service_coverage('reached').instance].coverage,
            checked=database.groups[direction_service_coverage('checked').instance].coverage),
        owned_direction_useful=dict(rule_bins=len(DIRECTION_USEFUL_RULES),full_required=True,
            reached=database.groups[direction_useful_coverage('reached').instance].coverage,
            checked=database.groups[direction_useful_coverage('checked').instance].coverage),
        owned_indirect_learning=dict(rule_bins=len(INDIRECT_RULES),full_required=True,
            reached=database.groups[indirect_coverage('reached').instance].coverage,
            checked=database.groups[indirect_coverage('checked').instance].coverage),
        owned_indirect_service={label:dict(rule_bins=len(INDIRECT_SERVICE_RULES),full_required=True,
            reached=database.groups[indirect_service_coverage(table,'reached').instance].coverage,
            checked=database.groups[indirect_service_coverage(table,'checked').instance].coverage)
            for table,label in INDIRECT_CLASSES.items()},
        owned_main_service={mode:dict(rule_bins=len(MAIN_SERVICE_RULES),full_required=True,
            reached=database.groups[main_service_coverage(mode,'reached').instance].coverage,
            checked=database.groups[main_service_coverage(mode,'checked').instance].coverage)
            for mode in MAIN_SERVICE_MODES},
        owned_common_history={family:dict(rule_bins=len(COMMON_HISTORY_RULES),full_required=True,
            reached=database.groups[common_history_coverage(family,'reached').instance].coverage,
            checked=database.groups[common_history_coverage(family,'checked').instance].coverage)
            for family in COMMON_HISTORY_FAMILIES},
        owned_main_rewrite=dict(rule_bins=len(MAIN_REWRITE_RULES),full_required=True,
            reached=database.groups[main_rewrite_coverage('reached').instance].coverage,
            checked=database.groups[main_rewrite_coverage('checked').instance].coverage),
        ras_reclaimed_versions=dict(rule_bins=len(RAS_REUSE_RULES),full_required=True,
            reached=database.groups[ras_reuse_coverage('reached').instance].coverage,
            checked=database.groups[ras_reuse_coverage('checked').instance].coverage),
        ras_neutral_gap=dict(rule_bins=len(RAS_NEUTRAL_GAP_RULES),full_required=True,
            reached=database.groups[neutral_gap_coverage('reached').instance].coverage,
            checked=database.groups[neutral_gap_coverage('checked').instance].coverage),
        owned_direction_capacity=dict(rule_bins=len(DIRECTION_CAPACITY_RULES),full_required=True,
            reached=database.groups[direction_capacity_coverage('reached').instance].coverage,
            checked=database.groups[direction_capacity_coverage('checked').instance].coverage),
        owned_direction_replacement=dict(rule_bins=len(DIRECTION_REPLACEMENT_RULES),full_required=True,
            reached=database.groups[direction_replacement_coverage('reached').instance].coverage,
            checked=database.groups[direction_replacement_coverage('checked').instance].coverage),
        owned_direction_migration={str(origin):dict(rule_bins=len(DIRECTION_MIGRATION_RULES),full_required=True,
            reached=database.groups[direction_migration_coverage(origin,'reached').instance].coverage,
            checked=database.groups[direction_migration_coverage(origin,'checked').instance].coverage) for origin in (0,1)},
        owned_direction_burst={str(origin):dict(rule_bins=len(DIRECTION_BURST_RULES),full_required=True,
            reached=database.groups[direction_burst_coverage(origin,'reached').instance].coverage,
            checked=database.groups[direction_burst_coverage(origin,'checked').instance].coverage) for origin in (0,1)},
        owned_ahead_learning=dict(rule_bins=len(AHEAD_LEARNING_RULES),full_required=True,
            reached=database.groups[ahead_learning_coverage('reached').instance].coverage,
            checked=database.groups[ahead_learning_coverage('checked').instance].coverage),
        owned_early_direction={tag_class:dict(rule_bins=len(EARLY_DIRECTION_RULES),full_required=True,
            reached=database.groups[early_direction_coverage(tag_class,'reached').instance].coverage,
            checked=database.groups[early_direction_coverage(tag_class,'checked').instance].coverage)
            for tag_class in EARLY_DIRECTION_CLASSES},
        owned_early_opposition=dict(rule_bins=len(EARLY_OPPOSITION_RULES),full_required=True,
            reached=database.groups[early_opposition_coverage('reached').instance].coverage,
            checked=database.groups[early_opposition_coverage('checked').instance].coverage),
        owned_early_positive=dict(rule_bins=len(EARLY_POSITIVE_RULES),full_required=True,
            reached=database.groups[early_positive_coverage('reached').instance].coverage,
            checked=database.groups[early_positive_coverage('checked').instance].coverage),
        mbtb_semantics={family:dict(rule_bins=len(rules),full_required=True,
            reached=database.groups[mbtb_semantic_coverage(family,'reached').instance].coverage,
            checked=database.groups[mbtb_semantic_coverage(family,'checked').instance].coverage)
            for family,rules in MBTB_SEMANTIC_RULES.items()},
        mbtb_entry_key_physical=dict(total_bins=576,
            coverage=database.groups[entry_keys_physical.instance].cross_coverage('all_dimensions'),
            full_required=profile == 'physical'),
        mbtb_cleanup_physical=dict(total_bins=144,
            coverage=database.groups[cleanup_physical.instance].cross_coverage('all_dimensions'),
            full_required=profile == 'physical'),
        mbtb_replacement_physical=dict(total_bins=24576,
            coverage=database.groups[mbtb_physical.instance].cross_coverage('all_dimensions'),
            full_required=profile == 'physical'))
