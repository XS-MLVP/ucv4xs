from suites.frontend.bpu.testbenches.bpu.coverage.common_query import lifetime_coverage as common_query_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.common_query import OBLIGATIONS as COMMON_QUERY_OBLIGATIONS
from suites.frontend.bpu.testbenches.bpu.coverage.statistical_prefix import lifetime_coverage as statistical_prefix_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.statistical_prefix import context_lifetime_coverage as sc_context_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.statistical_prefix import concurrent_context_lifetime_coverage as sc_concurrent_context_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.ahead_working_set import prefix_lifetime_coverage as ahead_prefix_working_set_lifetime
from suites.frontend.bpu.testbenches.bpu.model.ahead_working_set import PREFIX_PROFILES as AHEAD_PREFIX_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.ahead_working_set import PREFIX_RULES as AHEAD_PREFIX_RULES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import CONCURRENT_CONTEXT_PROFILES as SC_CONCURRENT_CONTEXT_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import CONCURRENT_CONTEXT_RULES as SC_CONCURRENT_CONTEXT_RULES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import CONTEXT_PROFILES as SC_CONTEXT_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import CONTEXT_RULES as SC_CONTEXT_RULES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import PROFILES as STATISTICAL_PREFIX_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.statistical_prefix import RULES as STATISTICAL_PREFIX_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_early_learning import lifetime_coverage as sc_early_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_early_learning import PROFILES as SC_EARLY_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.sc_early_learning import RULES as SC_EARLY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_admission import lifetime_coverage as sc_admission_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import PROFILES as SC_ADMISSION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import RULES as SC_ADMISSION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_admission import burst_lifetime_coverage as sc_feedback_burst_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import BURST_PROFILES as SC_BURST_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import BURST_RULES as SC_BURST_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_admission import read_only_lifetime_coverage as sc_read_no_write_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import READ_ONLY_PROFILES as SC_READ_ONLY_PROFILES
from suites.frontend.bpu.testbenches.bpu.coverage.history_working_set import short_path_retention_coverage as short_path_retention_lifetime
from suites.frontend.bpu.testbenches.bpu.model.history_working_set import SHORT_PROFILES as SHORT_PATH_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.history_working_set import SHORT_RULES as SHORT_PATH_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.history_working_set import short_path_mixed_coverage as short_path_mixed_lifetime
from suites.frontend.bpu.testbenches.bpu.model.history_working_set import SHORT_MIXED_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.history_working_set import SHORT_MIXED_RULES
from suites.frontend.bpu.testbenches.utage.coverage.predecessor_retention import lifetime_coverage as predecessor_retention_lifetime
from suites.frontend.bpu.testbenches.utage.model.predecessor_retention import Program as PredecessorProgram
from suites.frontend.bpu.testbenches.utage.model.predecessor_retention import PROFILES as PREDECESSOR_PROFILES
from suites.frontend.bpu.testbenches.utage.model.predecessor_retention import MODES as PREDECESSOR_MODES
from suites.frontend.bpu.testbenches.utage.model.predecessor_retention import RULES as PREDECESSOR_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_path_ownership import lifetime_coverage as indirect_path_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.conditional_prefix import lifetime_coverage as conditional_prefix_lifetime
from suites.frontend.bpu.testbenches.bpu.model.indirect_path_ownership import PROFILES as INDIRECT_PATH_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.indirect_path_ownership import RULES as INDIRECT_PATH_RULES
from suites.frontend.bpu.testbenches.bpu.model.conditional_prefix import PROFILES as CONDITIONAL_PREFIX_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.conditional_prefix import RULES as CONDITIONAL_PREFIX_RULES
from suites.frontend.bpu.testbenches.ras.model.commit_action import Program as CommitActionProgram
from suites.frontend.bpu.testbenches.ras.model.commit_action import RULES as COMMIT_ACTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.main_cold_original_order import lifetime_coverage as main_cold_original_order_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.main_original_order import lifetime_coverage as main_original_order_lifetime
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import Program as OriginalOrderProgram
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import ORDERS as ORIGINAL_ORDERS
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import PHASES as ORIGINAL_PHASES
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import COUNTERS as ORIGINAL_COUNTERS
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import RULES as ORIGINAL_ORDER_RULES
from suites.frontend.bpu.testbenches.ras.coverage.commit_action import lifetime_coverage as ras_commit_action_lifetime
from suites.frontend.bpu.testbenches.bpu.model.miss_authority import Program as MissAuthorityProgram
from suites.frontend.bpu.testbenches.bpu.model.miss_authority import RULES as MISS_AUTHORITY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.miss_authority import lifetime_coverage as miss_authority_lifetime
"""No-DUT contracts for independent scheduling without coverage dilution."""
from itertools import product
from functools import lru_cache
from types import SimpleNamespace

import pytest
from toffee import CoverGroup, CoverageDatabase

from suites.frontend.bpu.testbenches.tage.coverage.dual import DUAL_MODES
from suites.frontend.bpu.testbenches.tage.coverage.dual import tage_dual_shadow_coverage_model
from suites.frontend.bpu.testbenches.tage.coverage.retained import tage_retained_owner_coverage_model
from suites.frontend.bpu.testbenches.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.bpu.testbenches.bpu.coverage.abtb.supplemental import CELLS
from suites.frontend.bpu.testbenches.bpu.coverage.abtb.supplemental import PATHS
from suites.frontend.bpu.testbenches.bpu.coverage.abtb.supplemental import cell_label
from suites.frontend.bpu.testbenches.bpu.coverage.alignment import coverage as alignment_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.sc.used import used_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.sc.used import history_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.sc.used import KINDS as USED_KINDS
from suites.frontend.bpu.testbenches.bpu.coverage.sc.bounds import bounds_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.sc.bounds import RULES as THRESHOLD_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_micro import micro_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ras_micro import RULES as MICRO_RAS_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.selector import selector_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.selector import routing_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.selector import UPDATE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.aging import aging_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.aging import RULES as AGING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ittage import directory_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ittage import DIRECTORY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ittage_aging import aging_coverage as ittage_aging_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ittage_aging import RULES as ITTAGE_AGING_RULES
from suites.frontend.bpu.testbenches.uras.coverage.semantic import semantic_coverage as uras_semantic_coverage
from suites.frontend.bpu.testbenches.uras.coverage.semantic import RULES as URAS_RULES
from suites.frontend.bpu.testbenches.uras.coverage.semantic import held_call_coverage as uras_held_call_lifetime
from suites.frontend.bpu.testbenches.uras.coverage.semantic import HELD_PROFILES as URAS_HELD_PROFILES
from suites.frontend.bpu.testbenches.uras.coverage.semantic import HELD_RULES as URAS_HELD_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_admission import context_burst_lifetime_coverage as sc_context_burst_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import CONTEXT_BURST_PROFILES as SC_CONTEXT_BURST_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.sc_admission import CONTEXT_BURST_RULES as SC_CONTEXT_BURST_RULES
from suites.frontend.bpu.testbenches.ittage.coverage.semantic import target_coverage as ittage_target_coverage
from suites.frontend.bpu.testbenches.ittage.coverage.semantic import RULES as ITTAGE_TARGET_RULES
from suites.frontend.bpu.testbenches.sc.coverage.semantic import semantic_coverage as sc_semantic_coverage
from suites.frontend.bpu.testbenches.sc.coverage.semantic import RULES as SC_SEMANTIC_RULES
from suites.frontend.bpu.testbenches.sc.coverage.eligibility import EligibilityCoverage
from suites.frontend.bpu.testbenches.sc.coverage.eligibility import PROFILES as SC_ELIGIBILITY_PROFILES
from suites.frontend.bpu.testbenches.sc.coverage.eligibility import RULES as SC_ELIGIBILITY_RULES
from suites.frontend.bpu.testbenches.sc.coverage.original_feedback import FeedbackCoverage
from suites.frontend.bpu.testbenches.sc.coverage.original_feedback import PROFILES as SC_FEEDBACK_PROFILES
from suites.frontend.bpu.testbenches.sc.coverage.original_feedback import RULES as SC_FEEDBACK_RULES
from suites.frontend.bpu.testbenches.sc.coverage.original_enable import EnableCoverage
from suites.frontend.bpu.testbenches.sc.coverage.original_enable import PROFILES as SC_ENABLE_PROFILES
from suites.frontend.bpu.testbenches.sc.coverage.original_enable import RULES as SC_ENABLE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.recovery_arbitration import RecoveryCoverage
from suites.frontend.bpu.testbenches.bpu.coverage.recovery_arbitration import PROFILES as RECOVERY_PROFILES
from suites.frontend.bpu.testbenches.bpu.coverage.recovery_arbitration import RULES as RECOVERY_RULES
from suites.frontend.bpu.testbenches.utage.coverage.learning_retention import LearningRetentionCoverage
from suites.frontend.bpu.testbenches.utage.coverage.learning_retention import MODES as RETENTION_MODES
from suites.frontend.bpu.testbenches.utage.coverage.learning_retention import RULES as RETENTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.short_context_ownership import ShortContextCoverage
from suites.frontend.bpu.testbenches.bpu.coverage.short_context_ownership import ShortDirectionCoverage
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import DIRECTION_PROFILES as SHORT_DIRECTION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import DIRECTION_RULES as SHORT_DIRECTION_RULES
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import PROFILES as SHORT_CONTEXT_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import RULES as SHORT_CONTEXT_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.main_sibling import lifetime_coverage as main_sibling_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.main_sibling import RULES as MAIN_SIBLING_RULES
from suites.frontend.bpu.testbenches.bpu.model.main_sibling import PHASES as MAIN_SIBLING_PHASES
from suites.frontend.bpu.testbenches.bpu.model.main_sibling import ORIGINS as MAIN_SIBLING_ORIGINS
from suites.frontend.bpu.testbenches.bpu.coverage.ras_nested_recursion import lifetime_coverage as ras_nested_lifetime
from suites.frontend.bpu.testbenches.bpu.model.ras.nested_recursion import PROFILES as RAS_NESTED_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.ras.nested_recursion import RULES as RAS_NESTED_RULES
from suites.frontend.bpu.testbenches.utage.coverage.enable_lifetime import lifetime_coverage as utage_enable_lifetime
from suites.frontend.bpu.testbenches.utage.model.enable_lifetime import TABLES as UTAGE_ENABLE_TABLES
from suites.frontend.bpu.testbenches.utage.model.enable_lifetime import PHASES as UTAGE_ENABLE_PHASES
from suites.frontend.bpu.testbenches.utage.model.enable_lifetime import RULES as UTAGE_ENABLE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_wrapped_recursion import lifetime_coverage as ras_wrapped_lifetime
from suites.frontend.bpu.testbenches.bpu.model.ras.wrapped_recursion import PROFILES as RAS_WRAPPED_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.ras.wrapped_recursion import RULES as RAS_WRAPPED_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_layered_recursion import lifetime_coverage as ras_layered_lifetime
from suites.frontend.bpu.testbenches.bpu.model.ras.layered_recursion import PROFILES as RAS_LAYERED_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.ras.layered_recursion import RULES as RAS_LAYERED_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_adjacent_recursion import lifetime_coverage as ras_adjacent_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.opposed_learning_pair import lifetime_coverage as opposed_learning_pair_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.interior_prefix_learning import lifetime_coverage as interior_prefix_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.interior_prefix_learning import RULES as INTERIOR_PREFIX_RULES
from suites.frontend.bpu.testbenches.bpu.model.tage.interior_prefix_learning import PROGRAMS as INTERIOR_PREFIX_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.coverage.service_relearning import lifetime_coverage as service_relearning_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.service_relearning import RULES as SERVICE_RELEARNING_RULES
from suites.frontend.bpu.testbenches.bpu.model.tage.service_relearning import PROGRAMS as SERVICE_RELEARNING_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.coverage.shared_saturation import lifetime_coverage as shared_saturation_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.shared_saturation import RULES as SHARED_SATURATION_RULES
from suites.frontend.bpu.testbenches.bpu.model.tage.shared_saturation import PROGRAMS as SHARED_SATURATION_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.coverage.main_accepted_recovery import lifetime_coverage as main_accepted_recovery_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.main_coincident_recovery import lifetime_coverage as main_coincident_recovery_lifetime
from suites.frontend.bpu.testbenches.bpu.model.main_coincident_recovery import PROGRAMS as COINCIDENT_RECOVERY_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.main_coincident_recovery import RULES as COINCIDENT_RECOVERY_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.two_key_lifetime import lifetime_coverage as two_key_lifetime
from suites.frontend.bpu.testbenches.mbtb.model.two_key_programs import SEMANTIC_PROGRAMS as TWO_KEY_PROGRAMS
from suites.frontend.bpu.testbenches.mbtb.model.two_key_programs import RULES as TWO_KEY_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.cleanup_lifetime import lifetime_coverage as cleanup_lifetime
from suites.frontend.bpu.testbenches.mbtb.model.cleanup_programs import SEMANTIC_PROGRAMS as CLEANUP_PROGRAMS
from suites.frontend.bpu.testbenches.mbtb.model.cleanup_programs import RULES as CLEANUP_LIFETIME_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.shared_service import lifetime_coverage as shared_service_lifetime
from suites.frontend.bpu.testbenches.mbtb.model.shared_service import PROGRAMS as SHARED_SERVICE_PROGRAMS
from suites.frontend.bpu.testbenches.mbtb.model.shared_service import RULES as SHARED_SERVICE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.selective_learning import lifetime_coverage as selective_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.tage.selective_learning import ALL_PROGRAMS as SELECTIVE_LEARNING_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.tage.selective_learning import RULES as SELECTIVE_LEARNING_RULES
from suites.frontend.bpu.testbenches.utage.coverage.cross_branch_protection import lifetime_coverage as cross_branch_protection_lifetime
from suites.frontend.bpu.testbenches.utage.model.cross_branch_protection import PROGRAMS as UTAGE_CROSS_BRANCH_PROGRAMS
from suites.frontend.bpu.testbenches.utage.model.cross_branch_protection import RULES as UTAGE_CROSS_BRANCH_RULES
from suites.frontend.bpu.testbenches.utage.coverage.returning_original import lifetime_coverage as returning_original_lifetime
from suites.frontend.bpu.testbenches.utage.model.returning_original import PROGRAMS as RETURNING_ORIGINAL_PROGRAMS
from suites.frontend.bpu.testbenches.utage.model.returning_original import RULES as RETURNING_ORIGINAL_RULES
from suites.frontend.bpu.testbenches.utage.coverage.dual_source import lifetime_coverage as dual_source_lifetime
from suites.frontend.bpu.testbenches.utage.model.dual_source import OBLIGATIONS as DUAL_SOURCE_OBLIGATIONS
from suites.frontend.bpu.testbenches.utage.coverage.saved_vector import lifetime_coverage as saved_vector_lifetime
from suites.frontend.bpu.testbenches.utage.model.saved_vector import OBLIGATIONS as SAVED_VECTOR_OBLIGATIONS
from suites.frontend.bpu.testbenches.bpu.coverage.joint_stream import lifetime_coverage as joint_stream_lifetime
from suites.frontend.bpu.testbenches.bpu.model.joint_stream import PROFILES as JOINT_STREAM_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.joint_stream import RULES as JOINT_STREAM_RULES
from suites.frontend.bpu.testbenches.utage.coverage.displaced_branch import lifetime_coverage as displaced_branch_lifetime
from suites.frontend.bpu.testbenches.utage.model.displaced_branch import OBLIGATIONS as DISPLACED_BRANCH_OBLIGATIONS
from suites.frontend.bpu.testbenches.utage.coverage.instruction_confidence import lifetime_coverage as instruction_confidence_lifetime
from suites.frontend.bpu.testbenches.utage.model.instruction_confidence import OBLIGATIONS as INSTRUCTION_CONFIDENCE_OBLIGATIONS
from suites.frontend.bpu.testbenches.sc.coverage.neutral_boundary import lifetime_coverage as sc_neutral_boundary_lifetime
from suites.frontend.bpu.testbenches.sc.model.neutral_boundary import PROFILES as SC_NEUTRAL_PROFILES
from suites.frontend.bpu.testbenches.sc.model.neutral_boundary import RULES as SC_NEUTRAL_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.superseding_recovery import lifetime_coverage as superseding_recovery_lifetime
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import PROFILES as SUPERSEDING_RECOVERY_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import RULES as SUPERSEDING_RECOVERY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.owned_return_stack import lifetime_coverage as owned_return_stack_lifetime
from suites.frontend.bpu.testbenches.bpu.model.owned_return_stack import OBLIGATIONS as OWNED_RETURN_STACK_OBLIGATIONS
from suites.frontend.bpu.testbenches.sc.coverage.catalog import sc_same_way_feedback_coverage_model
from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import mbtb_cleanup_overlap_coverage_model
from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import mbtb_entry_keys_coverage_model
from suites.frontend.bpu.testbenches.bpu.coverage.main_duplicate_cleanup import lifetime_coverage as main_duplicate_cleanup_lifetime
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import Program as DuplicateCleanupProgram
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import IDENTITIES as DUPLICATE_CLEANUP_IDENTITIES
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import OVERLAPS as DUPLICATE_CLEANUP_OVERLAPS
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import PREPARATIONS as DUPLICATE_CLEANUP_PREPARATIONS
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import RULES as DUPLICATE_CLEANUP_RULES
from suites.frontend.bpu.testbenches.bpu.model.main_accepted_recovery import Program as AcceptedRecoveryProgram
from suites.frontend.bpu.testbenches.bpu.model.main_accepted_recovery import FATES as ACCEPTED_RECOVERY_FATES
from suites.frontend.bpu.testbenches.bpu.model.main_accepted_recovery import MOMENTS as ACCEPTED_RECOVERY_MOMENTS
from suites.frontend.bpu.testbenches.bpu.model.main_accepted_recovery import RULES as ACCEPTED_RECOVERY_RULES
from suites.frontend.bpu.testbenches.bpu.model.tage.opposed_learning_pair import PROGRAMS as OPPOSED_PAIR_PROGRAMS
from suites.frontend.bpu.testbenches.bpu.coverage.direction_turnaround import RULES as OPPOSED_PAIR_RULES
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import Program as AdjacentRecursionProgram
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import DEPTHS as RAS_ADJACENT_DEPTHS
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import RELATIONS as RAS_ADJACENT_RELATIONS
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import RULES as RAS_ADJACENT_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.reset_lifetime import lifetime_coverage as mbtb_reset_lifetime
from suites.frontend.bpu.testbenches.mbtb.model.reset_lifetime import PROFILES as MBTB_RESET_PROFILES
from suites.frontend.bpu.testbenches.mbtb.model.reset_lifetime import RULES as MBTB_RESET_RULES
from suites.frontend.bpu.testbenches.ubtb.coverage.reset_lifetime import lifetime_coverage as ubtb_reset_lifetime
from suites.frontend.bpu.testbenches.mbtb.coverage.query_reset import lifetime_coverage as mbtb_query_lifetime
from suites.frontend.bpu.testbenches.ubtb.coverage.query_reset import lifetime_coverage as ubtb_query_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.joint_lifetime import lifetime_coverage as joint_lifetime
from suites.frontend.bpu.testbenches.mbtb.coverage.cleanup_reset import lifetime_coverage as cleanup_reset_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.read_lifetime import lifetime_coverage as utage_read_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.read_lifetime import late_replacement_coverage as utage_late_replacement_lifetime
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import LateReplacementProgram
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import REBUILD_PROFILES
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import REBUILD_RULES
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import MODES as REBUILD_MODES
from suites.frontend.bpu.testbenches.bpu.coverage.short_context_ownership import working_set_coverage as short_cross_branch_lifetime
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import WORKING_SET_PROFILES as CROSS_BRANCH_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_context_ownership import WORKING_SET_RULES as CROSS_BRANCH_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.short_competition import lifetime_coverage as short_competition_lifetime
from suites.frontend.bpu.testbenches.bpu.model.short_competition import PROFILES as SHORT_COMPETITION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_competition import RULES as SHORT_COMPETITION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.sc_loop_experience import lifetime_coverage as sc_loop_experience_lifetime
from suites.frontend.bpu.testbenches.bpu.model.sc_loop_experience import PROFILES as SC_LOOP_EXPERIENCE_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.sc_loop_experience import RULES as SC_LOOP_EXPERIENCE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.joint_direction_learning import lifetime_coverage as joint_direction_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.joint_direction_learning import PROFILES as JOINT_DIRECTION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.joint_direction_learning import RULES as JOINT_DIRECTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.joint_originals import lifetime_coverage as joint_originals_lifetime
from suites.frontend.bpu.testbenches.bpu.model.joint_originals import PROFILES as JOINT_ORIGINALS_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.joint_originals import RULES as JOINT_ORIGINALS_RULES
from suites.frontend.bpu.testbenches.utage.coverage.ancestor_lifetime import lifetime_coverage as utage_ancestor_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.query_cohort import lifetime_coverage as query_cohort_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.query_identity import lifetime_coverage as query_identity_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.selective_protection import lifetime_coverage as selective_protection_lifetime
from suites.frontend.bpu.testbenches.utage.coverage.delayed_agreement import lifetime_coverage as delayed_agreement_lifetime
from suites.frontend.bpu.testbenches.bpu.coverage.neutral_recovery import lifetime_coverage as neutral_recovery_lifetime
from suites.frontend.bpu.testbenches.bpu.model.neutral_recovery import PROFILES as NEUTRAL_RECOVERY_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.neutral_recovery import rules as neutral_recovery_rules
from suites.frontend.bpu.testbenches.bpu.coverage.block_entry_learning import lifetime_coverage as block_entry_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.block_entry_learning import PROFILES as BLOCK_ENTRY_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.block_entry_learning import RULES as BLOCK_ENTRY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.entry_protection import lifetime_coverage as entry_protection_lifetime
from suites.frontend.bpu.testbenches.bpu.model.entry_protection import PROFILES as ENTRY_PROTECTION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.entry_protection import rules as entry_protection_rules
from suites.frontend.bpu.testbenches.bpu.coverage.short_revisit import lifetime_coverage as short_revisit_lifetime
from suites.frontend.bpu.testbenches.bpu.model.short_revisit import PROFILES as SHORT_REVISIT_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_revisit import rules as short_revisit_rules
from suites.frontend.bpu.testbenches.bpu.coverage.cross_block_learning import lifetime_coverage as cross_block_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.cross_block_learning import PROFILES as CROSS_BLOCK_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.cross_block_learning import RULES as CROSS_BLOCK_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.late_correction_learning import lifetime_coverage as late_correction_learning_lifetime
from suites.frontend.bpu.testbenches.bpu.model.late_correction_learning import PROFILES as LATE_CORRECTION_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.late_correction_learning import RULES as LATE_CORRECTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.competing_correction import lifetime_coverage as competing_correction_lifetime
from suites.frontend.bpu.testbenches.bpu.model.competing_correction import PROFILES as COMPETING_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.competing_correction import RULES as COMPETING_RULES
from suites.frontend.bpu.testbenches.utage.model.delayed_agreement import PROGRAMS as DELAYED_AGREEMENT_PROGRAMS
from suites.frontend.bpu.testbenches.utage.model.delayed_agreement import RULES as DELAYED_AGREEMENT_RULES
from suites.frontend.bpu.testbenches.utage.coverage.delayed_protection import lifetime_coverage as delayed_protection_lifetime
from suites.frontend.bpu.testbenches.utage.model.delayed_protection import PROGRAMS as DELAYED_PROTECTION_PROGRAMS
from suites.frontend.bpu.testbenches.utage.model.delayed_protection import RULES as DELAYED_PROTECTION_RULES
from suites.frontend.bpu.testbenches.utage.coverage.long_protection import lifetime_coverage as long_protection_lifetime
from suites.frontend.bpu.testbenches.utage.model.long_protection import Program as LongProtectionProgram
from suites.frontend.bpu.testbenches.utage.model.long_protection import MODES as LONG_PROTECTION_MODES
from suites.frontend.bpu.testbenches.utage.model.long_protection import LIFETIMES as LONG_PROTECTION_LIFETIMES
from suites.frontend.bpu.testbenches.utage.model.long_protection import RULES as LONG_PROTECTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.working_set_replacement import lifetime_coverage as working_set_replacement_lifetime
from suites.frontend.bpu.testbenches.utage.model.query_cohort import PROFILES as COHORT_PROFILES
from suites.frontend.bpu.testbenches.utage.model.query_cohort import ANCESTRIES as COHORT_ANCESTRIES
from suites.frontend.bpu.testbenches.utage.model.query_cohort import RULES as COHORT_RULES
from suites.frontend.bpu.testbenches.utage.model.query_identity import Program as IdentityProgram
from suites.frontend.bpu.testbenches.utage.model.query_identity import MODES as IDENTITY_MODES
from suites.frontend.bpu.testbenches.utage.model.query_identity import RULES as IDENTITY_RULES
from suites.frontend.bpu.testbenches.utage.model.selective_protection import Program as ProtectionProgram
from suites.frontend.bpu.testbenches.utage.model.selective_protection import MODES as PROTECTION_MODES
from suites.frontend.bpu.testbenches.utage.model.selective_protection import RULES as PROTECTION_RULES
from suites.frontend.bpu.testbenches.bpu.model.working_set_replacement import Program as ReplacementProgram
from suites.frontend.bpu.testbenches.bpu.model.working_set_replacement import KINDS as REPLACEMENT_KINDS
from suites.frontend.bpu.testbenches.utage.coverage.learning_persistence import lifetime_coverage as learning_persistence_lifetime
from suites.frontend.bpu.testbenches.utage.model.learning_persistence import Program as PersistenceProgram
from suites.frontend.bpu.testbenches.utage.model.learning_persistence import PROFILES as PERSISTENCE_PROFILES
from suites.frontend.bpu.testbenches.utage.model.learning_persistence import MODES as PERSISTENCE_MODES
from suites.frontend.bpu.testbenches.utage.model.learning_persistence import RULES as PERSISTENCE_RULES
from suites.frontend.bpu.testbenches.utage.coverage.catalog import utage_shadow_ring_coverage_model
from suites.frontend.bpu.testbenches.utage.coverage.supplemental import utage_partial_wrap_coverage_model
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import PROFILES as READ_PROFILES
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import RELATIONS as READ_RELATIONS
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import RULES as READ_RULES
from suites.frontend.bpu.testbenches.utage.model.ancestor_lifetime import RULES as ANCESTOR_RULES
from suites.frontend.bpu.testbenches.mbtb.model.query_reset import MODES as QUERY_RESET_MODES
from suites.frontend.bpu.testbenches.mbtb.model.query_reset import RULES as QUERY_RESET_RULES
from suites.frontend.bpu.testbenches.bpu.model.joint_lifetime import MODES as JOINT_MODES
from suites.frontend.bpu.testbenches.bpu.model.joint_lifetime import RULES as JOINT_RULES
from suites.frontend.bpu.testbenches.mbtb.model.cleanup_reset import PROFILES as CLEANUP_RESET_PROFILES
from suites.frontend.bpu.testbenches.mbtb.model.cleanup_reset import RULES as CLEANUP_RESET_RULES
from suites.frontend.bpu.testbenches.ubtb.model.reset_lifetime import PROFILES as UBTB_RESET_PROFILES
from suites.frontend.bpu.testbenches.ubtb.model.reset_lifetime import RULES as UBTB_RESET_RULES
from suites.frontend.bpu.testbenches.shared.coverage.pipeline_ownership import ownership_coverage
from suites.frontend.bpu.testbenches.ubtb.coverage.pipeline_ownership import PROFILES as UBTB_OWNERSHIP_PROFILES
from suites.frontend.bpu.testbenches.mbtb.coverage.pipeline_ownership import PROFILES as MBTB_OWNERSHIP_PROFILES
from suites.frontend.bpu.testbenches.ittage.coverage.pipeline_ownership import PROFILES as ITTAGE_OWNERSHIP_PROFILES
OWNERSHIP_PROFILES = {'ubtb': UBTB_OWNERSHIP_PROFILES, 'mbtb': MBTB_OWNERSHIP_PROFILES,
                      'ittage': ITTAGE_OWNERSHIP_PROFILES}
from suites.frontend.bpu.testbenches.shared.coverage.pipeline_ownership import RULES as OWNERSHIP_RULES
from suites.frontend.bpu.testbenches.ras.coverage.semantic import semantic_coverage as ras_action_coverage
from suites.frontend.bpu.testbenches.ras.coverage.semantic import ROLES as RAS_ACTION_ROLES
from suites.frontend.bpu.testbenches.utage.coverage.semantic import semantic_coverage as utage_semantic_coverage
from suites.frontend.bpu.testbenches.utage.coverage.semantic import BOUNDARY_RULES as UTAGE_BOUNDARY_RULES
from suites.frontend.bpu.testbenches.utage.coverage.semantic import TYPE_RULES as UTAGE_TYPE_RULES
from suites.frontend.bpu.testbenches.abtb.coverage.semantic import semantic_coverage as abtb_semantic_coverage
from suites.frontend.bpu.testbenches.abtb.coverage.semantic import RULES as ABTB_SEMANTIC_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.semantic import semantic_coverage as mbtb_semantic_coverage
from suites.frontend.bpu.testbenches.mbtb.coverage.semantic import RULES as MBTB_SEMANTIC_RULES
from suites.frontend.bpu.testbenches.tage.coverage.semantic import semantic_coverage as tage_semantic_coverage
from suites.frontend.bpu.testbenches.tage.coverage.semantic import RULES as TAGE_SEMANTIC_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.learning import learning_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.learning import RULES as TAGE_LEARNING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.fast_routing import routing_coverage as fast_routing_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.fast_routing import RULES as FAST_ROUTING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.alternate import alternate_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.alternate import RULES as ALTERNATE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.tage.interleaved import interleaved_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.tage.interleaved import RULES as INTERLEAVED_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.pipeline import pipeline_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.pipeline import RULES as PIPELINE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_redo import redo_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ras_redo import RULES as RAS_REDO_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_return_recovery import return_recovery_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ras_return_recovery import RULES as RAS_RETURN_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_return_recovery import STORAGES
from suites.frontend.bpu.testbenches.bpu.coverage.micro_capacity import capacity_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.micro_capacity import RULES as MICRO_CAPACITY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.micro_forwarding import forwarding_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.micro_forwarding import RULES as MICRO_FORWARDING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.main_learning import learning_coverage as main_learning_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.main_learning import RULES as MAIN_LEARNING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_learning import direction_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_learning import RULES as DIRECTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_forwarding import forwarding_coverage as direction_forwarding_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_forwarding import RULES as DIRECTION_FORWARDING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_service import service_coverage as direction_service_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_service import RULES as DIRECTION_SERVICE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_useful import useful_coverage as direction_useful_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_useful import RULES as DIRECTION_USEFUL_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_learning import indirect_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_learning import RULES as INDIRECT_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_service import service_coverage as indirect_service_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_service import RULES as INDIRECT_SERVICE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_service import CLASSES as INDIRECT_CLASSES
from suites.frontend.bpu.testbenches.bpu.coverage.main_service import main_service_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.main_service import main_service_rules
from suites.frontend.bpu.testbenches.bpu.coverage.main_service import RULES as MAIN_SERVICE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.main_service import MODES as MAIN_SERVICE_MODES
from suites.frontend.bpu.testbenches.bpu.coverage.common_history import common_history_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.common_history import RULES as COMMON_HISTORY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.common_history import FAMILIES as COMMON_HISTORY_FAMILIES
from suites.frontend.bpu.testbenches.bpu.coverage.main_rewrite import main_rewrite_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.main_rewrite import RULES as MAIN_REWRITE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_reuse import ras_reuse_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ras_reuse import RULES as RAS_REUSE_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ras_neutral_gap import neutral_gap_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ras_neutral_gap import RULES as RAS_NEUTRAL_GAP_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_capacity import capacity_coverage as direction_capacity_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_capacity import RULES as DIRECTION_CAPACITY_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_replacement import replacement_coverage as direction_replacement_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_replacement import RULES as DIRECTION_REPLACEMENT_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_migration import migration_coverage as direction_migration_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_migration import RULES as DIRECTION_MIGRATION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.direction_burst import burst_coverage as direction_burst_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.direction_burst import RULES as DIRECTION_BURST_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.ahead_learning import ahead_learning_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.ahead_learning import RULES as AHEAD_LEARNING_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.early_direction import direction_coverage as early_direction_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.early_direction import RULES as EARLY_DIRECTION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.early_direction import CLASSES as EARLY_DIRECTION_CLASSES
from suites.frontend.bpu.testbenches.bpu.coverage.early_opposition import opposition_coverage as early_opposition_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.early_opposition import RULES as EARLY_OPPOSITION_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.early_positive import positive_coverage as early_positive_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.early_positive import RULES as EARLY_POSITIVE_RULES
from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import mbtb_replacement_coverage_model
from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import mbtb_multi_hit_cleanup_coverage_model
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.replacement_scenario import TOUCH_MODES
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.replacement_scenario import PHASES as MBTB_REPLACEMENT_PHASES
from suites.frontend.bpu.testbenches.mbtb.tests.regression import MBTB_REPRESENTATIVE_INDICES
from suites.frontend.bpu.testbenches.bpu.model.alignment import ALL_CASES
from suites.frontend.bpu.testbenches.bpu.model.alignment import PHASES


from suites.frontend.bpu.testbenches.tage.tests.testcase import test_dual_shadow as DUAL
from suites.frontend.bpu.testbenches.tage.tests.testcase import test_retained_owner as RETAINED
from suites.frontend.bpu.tools import parallel_coverage as GATE


DUAL_TEST = DUAL.test_dual_feedback_retains_independent_counters_across_companion_states
RETAINED_TEST = RETAINED.test_captured_way_feedback_updates_retained_owner_at_every_depth
KINDS = ('dual', 'retained')
EXTRA_MATRICES = {
    'sc_legacy_same_way': (sc_same_way_feedback_coverage_model,
        dict(phase=('both_qualified','opposite_cancelled','single_branch_control','both_slots_alias')),None,4),
    'utage_legacy_shadow_ring': (utage_shadow_ring_coverage_model,
        dict(mode=('adjacent','serial'),phase=('resident','same_index_bypass','ring_wrapped'),table=range(2),bank=range(4),row=range(8)),
        'mode_phase_table_bank_row',384),
    'utage_legacy_partial_wrap': (utage_partial_wrap_coverage_model,
        dict(mode=('serial','adjacent'),bank=range(4),phase=('old_slot2_payload','all_retained_neighbors')),'all_dimensions',16),
    'mbtb_legacy_cleanup': (mbtb_multi_hit_cleanup_coverage_model,
        dict(phase=('resident_after_other_set','public_double_hit','single_survivor','other_set_preserved')),None,4),
    **{f'ras_neutral_gap_{status}':(lambda status=status:neutral_gap_coverage(status),
        dict(rule=RAS_NEUTRAL_GAP_RULES),None,len(RAS_NEUTRAL_GAP_RULES)) for status in ('reached','checked')},
    **{f'ras_reclaimed_versions_{status}':(lambda status=status:ras_reuse_coverage(status),
        dict(rule=RAS_REUSE_RULES),None,len(RAS_REUSE_RULES)) for status in ('reached','checked')},
    **{f'main_rewrite_{status}':(lambda status=status:main_rewrite_coverage(status),
        dict(rule=MAIN_REWRITE_RULES),None,len(MAIN_REWRITE_RULES)) for status in ('reached','checked')},
    **{f'common_history_{family}_{status}':(lambda family=family,status=status:common_history_coverage(family,status),
        dict(rule=COMMON_HISTORY_RULES),None,len(COMMON_HISTORY_RULES))
        for family in COMMON_HISTORY_FAMILIES for status in ('reached','checked')},
    **{f'main_service_{mode}_{status}':(lambda mode=mode,status=status:main_service_coverage(mode,status),
        dict(rule=main_service_rules(mode)),None,len(main_service_rules(mode))) for mode in MAIN_SERVICE_MODES for status in ('reached','checked')},
    **{f'indirect_learning_{status}':(lambda status=status:indirect_coverage(status),dict(rule=INDIRECT_RULES),None,len(INDIRECT_RULES))
        for status in ('reached','checked')},
    **{f'indirect_service_{table}_{status}':(lambda table=table,status=status:indirect_service_coverage(table,status),
        dict(rule=INDIRECT_SERVICE_RULES),None,len(INDIRECT_SERVICE_RULES)) for table in INDIRECT_CLASSES for status in ('reached','checked')},
    'direction_useful_reached': (lambda:direction_useful_coverage('reached'),dict(rule=DIRECTION_USEFUL_RULES),None,len(DIRECTION_USEFUL_RULES)),
    'direction_useful_checked': (lambda:direction_useful_coverage('checked'),dict(rule=DIRECTION_USEFUL_RULES),None,len(DIRECTION_USEFUL_RULES)),
    'early_positive_reached': (lambda:early_positive_coverage('reached'),dict(rule=EARLY_POSITIVE_RULES),None,len(EARLY_POSITIVE_RULES)),
    'early_positive_checked': (lambda:early_positive_coverage('checked'),dict(rule=EARLY_POSITIVE_RULES),None,len(EARLY_POSITIVE_RULES)),
    'early_opposition_reached': (lambda:early_opposition_coverage('reached'),dict(rule=EARLY_OPPOSITION_RULES),None,len(EARLY_OPPOSITION_RULES)),
    'early_opposition_checked': (lambda:early_opposition_coverage('checked'),dict(rule=EARLY_OPPOSITION_RULES),None,len(EARLY_OPPOSITION_RULES)),
    'owned_ahead_reached': (lambda:ahead_learning_coverage('reached'),dict(rule=AHEAD_LEARNING_RULES),None,len(AHEAD_LEARNING_RULES)),
    'owned_ahead_checked': (lambda:ahead_learning_coverage('checked'),dict(rule=AHEAD_LEARNING_RULES),None,len(AHEAD_LEARNING_RULES)),
    'mbtb_replacement_physical': (mbtb_replacement_coverage_model,
        dict(index=tuple(range(256)),align=(0,1),upper=(0,1),mode=TOUCH_MODES,phase=MBTB_REPLACEMENT_PHASES),
        'all_dimensions',24576),
    'abtb_semantic_reached': (lambda: abtb_semantic_coverage('reached'),dict(rule=ABTB_SEMANTIC_RULES),None,len(ABTB_SEMANTIC_RULES)),
    'abtb_semantic_checked': (lambda: abtb_semantic_coverage('checked'),dict(rule=ABTB_SEMANTIC_RULES),None,len(ABTB_SEMANTIC_RULES)),
    'utage_boundary_reached': (lambda: utage_semantic_coverage('boundary','reached'),dict(rule=UTAGE_BOUNDARY_RULES),None,len(UTAGE_BOUNDARY_RULES)),
    'utage_boundary_checked': (lambda: utage_semantic_coverage('boundary','checked'),dict(rule=UTAGE_BOUNDARY_RULES),None,len(UTAGE_BOUNDARY_RULES)),
    'utage_type_reached': (lambda: utage_semantic_coverage('resolved-type','reached'),dict(rule=UTAGE_TYPE_RULES),None,len(UTAGE_TYPE_RULES)),
    'utage_type_checked': (lambda: utage_semantic_coverage('resolved-type','checked'),dict(rule=UTAGE_TYPE_RULES),None,len(UTAGE_TYPE_RULES)),
    'ras_action_reached': (lambda: ras_action_coverage('reached'),dict(role=RAS_ACTION_ROLES),None,len(RAS_ACTION_ROLES)),
    'ras_action_checked': (lambda: ras_action_coverage('checked'),dict(role=RAS_ACTION_ROLES),None,len(RAS_ACTION_ROLES)),
    'sc_semantic_reached': (lambda: sc_semantic_coverage('reached'),dict(rule=SC_SEMANTIC_RULES),None,len(SC_SEMANTIC_RULES)),
    'sc_semantic_checked': (lambda: sc_semantic_coverage('checked'),dict(rule=SC_SEMANTIC_RULES),None,len(SC_SEMANTIC_RULES)),
    'alignment': (alignment_coverage,
        dict(case=tuple(case.label for case in ALL_CASES), phase=tuple(row[0] for row in PHASES)),
        'legal_case_phase', 7840),
    'sc_used': (used_coverage, dict(bank=(0, 1), way=range(8), kind=USED_KINDS),
        'physical_used_feedback', 48),
    'sc_history': (history_coverage,
        dict(bank=(0, 1), way=range(8), direction=('forward', 'backward'), kind=USED_KINDS),
        'physical_used_nonzero_history', 96),
    'sc_threshold_reached': (lambda: bounds_coverage('reached'),
        dict(way=range(8),rule=THRESHOLD_RULES),'way_rule',104),
    'sc_threshold_checked': (lambda: bounds_coverage('checked'),
        dict(way=range(8),rule=THRESHOLD_RULES),'way_rule',104),
    'micro_ras_reached': (lambda: micro_coverage('reached'),dict(rule=MICRO_RAS_RULES),None,4),
    'micro_ras_checked': (lambda: micro_coverage('checked'),dict(rule=MICRO_RAS_RULES),None,4),
}
for family,factory,profiles,rules in (
    ('sc_original_eligibility',EligibilityCoverage,SC_ELIGIBILITY_PROFILES,SC_ELIGIBILITY_RULES),
    ('sc_original_feedback',FeedbackCoverage,SC_FEEDBACK_PROFILES,SC_FEEDBACK_RULES),
    ('sc_original_enable',EnableCoverage,SC_ENABLE_PROFILES,SC_ENABLE_RULES),
    ('bpu_original_recovery',RecoveryCoverage,RECOVERY_PROFILES,RECOVERY_RULES),
    ('utage_learning_retention',LearningRetentionCoverage,RETENTION_MODES,RETENTION_RULES),
    ('bpu_short_context',ShortContextCoverage,SHORT_CONTEXT_PROFILES,SHORT_CONTEXT_RULES),
    ('bpu_short_direction',ShortDirectionCoverage,SHORT_DIRECTION_PROFILES,SHORT_DIRECTION_RULES)):
    obligations=tuple(profile+'.'+rule for profile in profiles for rule in rules)
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'{family}_{status}']=(
            lambda factory=factory,status=status:factory(None).groups[status],
            dict(obligation=obligations),None,len(obligations))
for dut, profiles in OWNERSHIP_PROFILES.items():
    obligations = tuple(profile + '.' + rule for profile in profiles for rule in OWNERSHIP_RULES)
    for status in ('reached', 'checked'):
        EXTRA_MATRICES[f'{dut}_pipeline_ownership_{status}'] = (
            lambda dut=dut,status=status:ownership_coverage(dut,status,profiles=OWNERSHIP_PROFILES),
            dict(obligation=obligations),None,len(obligations))
for family, factory, obligations in (
    ('main_cold_original_order', main_cold_original_order_lifetime, tuple(OriginalOrderProgram(order,phase,counter).label+'.'+rule
        for order in ORIGINAL_ORDERS for phase in ORIGINAL_PHASES for counter in ORIGINAL_COUNTERS for rule in ORIGINAL_ORDER_RULES)),
    ('main_original_order', main_original_order_lifetime, tuple(OriginalOrderProgram(order,phase,counter).label+'.'+rule
        for order in ORIGINAL_ORDERS for phase in ORIGINAL_PHASES for counter in ORIGINAL_COUNTERS for rule in ORIGINAL_ORDER_RULES)),
    ('ras_commit_action', ras_commit_action_lifetime, tuple(CommitActionProgram(action).label + '.' + rule
        for action in (1,2,3) for rule in COMMIT_ACTION_RULES)),
    ('miss_authority', miss_authority_lifetime, tuple(MissAuthorityProgram(allocate, same).label + '.' + rule
        for allocate in (False, True) for same in (False, True) for rule in MISS_AUTHORITY_RULES)),
    ('learning_persistence', learning_persistence_lifetime, tuple(PersistenceProgram(profile, mode).label + '.' + rule
        for profile in PERSISTENCE_PROFILES for mode in PERSISTENCE_MODES for rule in PERSISTENCE_RULES)),
    ('main_sibling_lifetime', main_sibling_lifetime,
        tuple(phase+'.'+origin+'.'+rule for phase in MAIN_SIBLING_PHASES
              for origin in MAIN_SIBLING_ORIGINS for rule in MAIN_SIBLING_RULES)),
    ('ras_nested_lifetime', ras_nested_lifetime,
        tuple(str(count)+'.'+rule for count in RAS_NESTED_PROFILES for rule in RAS_NESTED_RULES)),
    ('utage_enable_lifetime', utage_enable_lifetime,
        tuple(str(table)+'.'+phase+'.'+rule for table in UTAGE_ENABLE_TABLES
              for phase in UTAGE_ENABLE_PHASES for rule in UTAGE_ENABLE_RULES)),
    ('ras_wrapped_lifetime', ras_wrapped_lifetime,
        tuple(str(count)+'.'+rule for count in RAS_WRAPPED_PROFILES for rule in RAS_WRAPPED_RULES)),
    ('opposed_learning_pair', opposed_learning_pair_lifetime,
        tuple(p.name+'.'+rule for p in OPPOSED_PAIR_PROGRAMS for rule in OPPOSED_PAIR_RULES)),
    ('interior_prefix_learning', interior_prefix_learning_lifetime,
        tuple(p.name+'.'+rule for p in INTERIOR_PREFIX_PROGRAMS for rule in INTERIOR_PREFIX_RULES)),
    ('service_relearning', service_relearning_lifetime,
        tuple(p.name+'.'+rule for p in SERVICE_RELEARNING_PROGRAMS for rule in SERVICE_RELEARNING_RULES)),
    ('shared_saturation', shared_saturation_lifetime,
        tuple(p.name+'.'+rule for p in SHARED_SATURATION_PROGRAMS for rule in SHARED_SATURATION_RULES)),
    ('selective_direction_learning', selective_learning_lifetime,
        tuple(p.name+'.'+rule for p in SELECTIVE_LEARNING_PROGRAMS for rule in SELECTIVE_LEARNING_RULES)),
    ('cross_branch_protection', cross_branch_protection_lifetime,
        tuple(p.label+'.'+rule for p in UTAGE_CROSS_BRANCH_PROGRAMS for rule in UTAGE_CROSS_BRANCH_RULES)),
    ('returning_original', returning_original_lifetime,
        tuple(p.label+'.'+rule for p in RETURNING_ORIGINAL_PROGRAMS for rule in RETURNING_ORIGINAL_RULES)),
    ('dual_source', dual_source_lifetime, DUAL_SOURCE_OBLIGATIONS),
    ('saved_vector', saved_vector_lifetime, SAVED_VECTOR_OBLIGATIONS),
    ('joint_stream', joint_stream_lifetime, tuple(p+'.'+r for p in JOINT_STREAM_PROFILES for r in JOINT_STREAM_RULES)),
    ('displaced_branch', displaced_branch_lifetime, DISPLACED_BRANCH_OBLIGATIONS),
    ('instruction_confidence', instruction_confidence_lifetime, INSTRUCTION_CONFIDENCE_OBLIGATIONS),
    ('superseding_recovery', superseding_recovery_lifetime,
        tuple(p+'.'+r for p in SUPERSEDING_RECOVERY_PROFILES for r in SUPERSEDING_RECOVERY_RULES)),
    ('owned_return_stack', owned_return_stack_lifetime, OWNED_RETURN_STACK_OBLIGATIONS),
    ('sc_neutral_boundary', sc_neutral_boundary_lifetime,
        tuple(a+'.'+b+'.'+rule for a,b in SC_NEUTRAL_PROFILES for rule in SC_NEUTRAL_RULES)),
    ('main_accepted_recovery', main_accepted_recovery_lifetime,
        tuple(AcceptedRecoveryProgram(f,m).label+'.'+r for f in ACCEPTED_RECOVERY_FATES for m in ACCEPTED_RECOVERY_MOMENTS for r in ACCEPTED_RECOVERY_RULES)),
    ('main_coincident_recovery', main_coincident_recovery_lifetime,
        tuple(p.label+'.'+r for p in COINCIDENT_RECOVERY_PROGRAMS for r in COINCIDENT_RECOVERY_RULES)),
    ('mbtb_two_key_lifetime', two_key_lifetime,
        tuple(p.label+'.'+r for p in TWO_KEY_PROGRAMS for r in TWO_KEY_RULES)),
    ('mbtb_cleanup_lifetime', cleanup_lifetime,
        tuple(p.label+'.'+r for p in CLEANUP_PROGRAMS for r in CLEANUP_LIFETIME_RULES)),
    ('mbtb_shared_service',shared_service_lifetime,
        tuple(p.label+'.'+r for p in SHARED_SERVICE_PROGRAMS for r in SHARED_SERVICE_RULES)),
    ('main_duplicate_cleanup', main_duplicate_cleanup_lifetime,
        tuple(DuplicateCleanupProgram(i,o,p).label+'.'+r for i in DUPLICATE_CLEANUP_IDENTITIES for o in DUPLICATE_CLEANUP_OVERLAPS for p in DUPLICATE_CLEANUP_PREPARATIONS for r in DUPLICATE_CLEANUP_RULES)),
    ('ras_layered_lifetime', ras_layered_lifetime,
        tuple(str(count)+'.'+rule for count in RAS_LAYERED_PROFILES for rule in RAS_LAYERED_RULES)),
    ('ras_adjacent_lifetime', ras_adjacent_lifetime,
        tuple(AdjacentRecursionProgram(depth,relation).label+'.'+rule
              for depth in RAS_ADJACENT_DEPTHS for relation in RAS_ADJACENT_RELATIONS for rule in RAS_ADJACENT_RULES)),
    ('mbtb_reset_lifetime', mbtb_reset_lifetime,
        tuple(profile+'.'+rule for profile in MBTB_RESET_PROFILES for rule in MBTB_RESET_RULES)),
    ('ubtb_reset_lifetime', ubtb_reset_lifetime,
        tuple(profile+'.'+rule for profile in UBTB_RESET_PROFILES for rule in UBTB_RESET_RULES)),
    ('mbtb_query_lifetime',mbtb_query_lifetime,tuple(mode+'.'+rule for mode in QUERY_RESET_MODES for rule in QUERY_RESET_RULES)),
    ('ubtb_query_lifetime',ubtb_query_lifetime,tuple(mode+'.'+rule for mode in QUERY_RESET_MODES for rule in QUERY_RESET_RULES)),
    ('bpu_joint_lifetime',joint_lifetime,tuple(mode+'.'+rule for mode in JOINT_MODES for rule in JOINT_RULES)),
    ('mbtb_cleanup_reset_lifetime',cleanup_reset_lifetime,tuple(profile+'.'+rule for profile in CLEANUP_RESET_PROFILES for rule in CLEANUP_RESET_RULES)),
    ('utage_read_lifetime',utage_read_lifetime,tuple('.'.join((p,r,o)) for p in READ_PROFILES for r in READ_RELATIONS for o in READ_RULES)),
    ('utage_ancestor_lifetime',utage_ancestor_lifetime,tuple('.'.join((p,r,o)) for p in READ_PROFILES for r in READ_RELATIONS for o in ANCESTOR_RULES))):
    for status in ('reached', 'checked'):
        EXTRA_MATRICES[f'{family}_{status}'] = (
            lambda factory=factory,status=status: factory(status),
            dict(obligation=obligations), None, len(obligations))

# Declaration-only collection: never instantiate CoverGroup while importing tests.
for family, factory, obligations in (
    ('uras_held_call', uras_held_call_lifetime, tuple(p+'.'+r for p in URAS_HELD_PROFILES for r in URAS_HELD_RULES)),
    ('sc_context_burst', sc_context_burst_lifetime, tuple(p+'.'+r for p in SC_CONTEXT_BURST_PROFILES for r in SC_CONTEXT_BURST_RULES)),
    ('common_query_history', common_query_lifetime, COMMON_QUERY_OBLIGATIONS),
    ('statistical_prefix', statistical_prefix_lifetime, tuple(p+'.'+r for p in STATISTICAL_PREFIX_PROFILES for r in STATISTICAL_PREFIX_RULES)),
    ('sc_context', sc_context_lifetime, tuple(p+'.'+r for p in SC_CONTEXT_PROFILES for r in SC_CONTEXT_RULES)),
    ('sc_concurrent_context', sc_concurrent_context_lifetime, tuple(p+'.'+r for p in SC_CONCURRENT_CONTEXT_PROFILES for r in SC_CONCURRENT_CONTEXT_RULES)),
    ('ahead_prefix_working_set',ahead_prefix_working_set_lifetime,tuple(p+'.'+r for p in AHEAD_PREFIX_PROFILES for r in AHEAD_PREFIX_RULES)),
    ('sc_early_learning', sc_early_learning_lifetime, tuple(p+'.'+r for p in SC_EARLY_PROFILES for r in SC_EARLY_RULES)),
    ('sc_admission', sc_admission_lifetime, tuple(p+'.'+r for p in SC_ADMISSION_PROFILES for r in SC_ADMISSION_RULES)),
    ('sc_feedback_burst', sc_feedback_burst_lifetime, tuple(p+'.'+r for p in SC_BURST_PROFILES for r in SC_BURST_RULES)),
    ('sc_read_no_write', sc_read_no_write_lifetime, tuple(p+'.'+r for p in SC_READ_ONLY_PROFILES for r in SC_ADMISSION_RULES)),
    ('short_path_retention', short_path_retention_lifetime, tuple(p+'.'+r for p in SHORT_PATH_PROFILES for r in SHORT_PATH_RULES)),
    ('short_path_mixed', short_path_mixed_lifetime, tuple(p+'.'+r for p in SHORT_MIXED_PROFILES for r in SHORT_MIXED_RULES)),
    ('utage_late_replacement', utage_late_replacement_lifetime, tuple(LateReplacementProgram(p,m).label+'.'+r
        for p in REBUILD_PROFILES for m in REBUILD_MODES for r in REBUILD_RULES)),
    ('short_cross_branch',short_cross_branch_lifetime,tuple(p+'.'+r for p in CROSS_BRANCH_PROFILES for r in CROSS_BRANCH_RULES)),
    ('short_competition',short_competition_lifetime,tuple(p+'.'+r for p in SHORT_COMPETITION_PROFILES for r in SHORT_COMPETITION_RULES)),
    ('sc_loop_experience',sc_loop_experience_lifetime,tuple(p+'.'+r for p in SC_LOOP_EXPERIENCE_PROFILES for r in SC_LOOP_EXPERIENCE_RULES)),
    ('joint_direction_learning',joint_direction_learning_lifetime,tuple(p+'.'+r for p in JOINT_DIRECTION_PROFILES for r in JOINT_DIRECTION_RULES)),
    ('joint_originals',joint_originals_lifetime,tuple(p+'.'+r for p in JOINT_ORIGINALS_PROFILES for r in JOINT_ORIGINALS_RULES)),
    ('predecessor_retention', predecessor_retention_lifetime, tuple(PredecessorProgram(p,m,t).label+'.'+r
        for p in PREDECESSOR_PROFILES for m in PREDECESSOR_MODES for t in (False,True) for r in PREDECESSOR_RULES)),
    ('indirect_path_ownership', indirect_path_lifetime, tuple(p+'.'+r for p in INDIRECT_PATH_PROFILES for r in INDIRECT_PATH_RULES)),
    ('conditional_prefix', conditional_prefix_lifetime, tuple(p+'.'+r for p in CONDITIONAL_PREFIX_PROFILES for r in CONDITIONAL_PREFIX_RULES)),
    ('query_cohort', query_cohort_lifetime, tuple('.'.join((p, a, r))
        for p in COHORT_PROFILES for a in COHORT_ANCESTRIES for r in COHORT_RULES)),
    ('query_identity', query_identity_lifetime, tuple(IdentityProgram(owner, mode).label + '.' + rule
        for owner in (0, 1) for mode in IDENTITY_MODES for rule in IDENTITY_RULES)),
    ('selective_protection', selective_protection_lifetime, tuple(ProtectionProgram(owner, mode).label + '.' + rule
        for owner in (0, 1) for mode in PROTECTION_MODES for rule in PROTECTION_RULES)),
    ('delayed_agreement', delayed_agreement_lifetime,
        tuple(p.label+'.'+rule for p in DELAYED_AGREEMENT_PROGRAMS for rule in DELAYED_AGREEMENT_RULES)),
    ('neutral_recovery', neutral_recovery_lifetime,
        tuple(profile+'.'+rule for profile in NEUTRAL_RECOVERY_PROFILES for rule in neutral_recovery_rules(profile))),
    ('block_entry_learning', block_entry_learning_lifetime,
        tuple(profile+'.'+rule for profile in BLOCK_ENTRY_PROFILES for rule in BLOCK_ENTRY_RULES)),
    ('entry_protection', entry_protection_lifetime,
        tuple(profile+'.'+rule for profile in ENTRY_PROTECTION_PROFILES for rule in entry_protection_rules(profile))),
    ('short_revisit', short_revisit_lifetime,
        tuple(profile+'.'+rule for profile in SHORT_REVISIT_PROFILES for rule in short_revisit_rules(profile))),
    ('cross_block_learning', cross_block_learning_lifetime,
        tuple(profile+'.'+rule for profile in CROSS_BLOCK_PROFILES for rule in CROSS_BLOCK_RULES)),
    ('late_correction_learning', late_correction_learning_lifetime,
        tuple(profile+'.'+rule for profile in LATE_CORRECTION_PROFILES for rule in LATE_CORRECTION_RULES)),
    ('competing_correction', competing_correction_lifetime,
        tuple(profile+'.'+rule for profile in COMPETING_PROFILES for rule in COMPETING_RULES)),
    ('delayed_protection', delayed_protection_lifetime,
        tuple(p.label+'.'+rule for p in DELAYED_PROTECTION_PROGRAMS for rule in DELAYED_PROTECTION_RULES)),
    ('long_protection', long_protection_lifetime, tuple(LongProtectionProgram(owner, mode,life).label + '.' + rule
        for owner in (0, 1) for mode in LONG_PROTECTION_MODES for life in LONG_PROTECTION_LIFETIMES for rule in LONG_PROTECTION_RULES)),
    ('working_set_replacement', working_set_replacement_lifetime, tuple(ReplacementProgram(kind).label + '.' + rule
        for kind in REPLACEMENT_KINDS for rule in ReplacementProgram(kind).rules)),
):
    for status in ('reached', 'checked'):
        EXTRA_MATRICES[f'{family}_{status}'] = (
            lambda factory=factory,status=status: factory(status),
            dict(obligation=obligations), None, len(obligations))
for family,rules in (('update',UPDATE_RULES),('selection',('provider','alternate'))):
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'tage_selector_{family}_{status}']=(
            lambda family=family,status=status:selector_coverage(family,status),
            dict(rule=rules,alt_conf=(0,1)),None,len(rules)*2)
for family,rules in AGING_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'tage_aging_{family}_{status}']=(
            lambda family=family,status=status:aging_coverage(family,status),dict(rule=rules),None,len(rules))
for status in ('reached','checked'):
    EXTRA_MATRICES[f'tage_selector_routing_{status}']=(
        lambda status=status:routing_coverage(status),dict(index=tuple(range(16))),None,16)
for family,rules in DIRECTORY_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'ittage_directory_{family}_{status}']=(
            lambda family=family,status=status:directory_coverage(family,status),dict(rule=rules),None,len(rules))
for family,rules in ITTAGE_AGING_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'ittage_aging_{family}_{status}']=(
            lambda family=family,status=status:ittage_aging_coverage(family,status),dict(rule=rules),None,len(rules))
for status in ('reached','checked'):
    EXTRA_MATRICES[f'tage_interleaved_{status}']=(
        lambda status=status:interleaved_coverage(status),dict(rule=INTERLEAVED_RULES),None,len(INTERLEAVED_RULES))
    EXTRA_MATRICES[f'tage_alternate_{status}']=(
        lambda status=status:alternate_coverage(status),dict(rule=ALTERNATE_RULES),None,len(ALTERNATE_RULES))
    EXTRA_MATRICES[f'tage_fast_routing_{status}']=(
        lambda status=status:fast_routing_coverage(status),dict(rule=FAST_ROUTING_RULES),None,len(FAST_ROUTING_RULES))
    EXTRA_MATRICES[f'tage_late_discovery_{status}']=(
        lambda status=status:fast_routing_coverage(status,'later-first'),dict(rule=FAST_ROUTING_RULES),None,len(FAST_ROUTING_RULES))
    EXTRA_MATRICES[f'tage_learning_{status}']=(
        lambda status=status:learning_coverage(status),dict(rule=TAGE_LEARNING_RULES),None,len(TAGE_LEARNING_RULES))
    EXTRA_MATRICES[f'tage_semantic_{status}']=(
        lambda status=status:tage_semantic_coverage(status),dict(rule=TAGE_SEMANTIC_RULES),None,len(TAGE_SEMANTIC_RULES))
    EXTRA_MATRICES[f'uras_semantic_{status}']=(
        lambda status=status:uras_semantic_coverage(status),dict(rule=URAS_RULES),None,len(URAS_RULES))
    EXTRA_MATRICES[f'ittage_target_{status}']=(
        lambda status=status:ittage_target_coverage(status),dict(rule=ITTAGE_TARGET_RULES),None,len(ITTAGE_TARGET_RULES))
for family,rules in MBTB_SEMANTIC_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'mbtb_semantic_{family}_{status}']=(
            lambda family=family,status=status:mbtb_semantic_coverage(family,status),
            dict(rule=rules),None,len(rules))
for family,rules in PIPELINE_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'owned_pipeline_{family}_{status}']=(
            lambda family=family,status=status:pipeline_coverage(family,status),
            dict(rule=rules),None,len(rules))
for calls,rules in RAS_REDO_RULES.items():
    for status in ('reached','checked'):
        EXTRA_MATRICES[f'ras_redo_{calls}_{status}']=(
            lambda calls=calls,status=status:redo_coverage(calls,status),dict(rule=rules),None,len(rules))
for calls,rules in RAS_RETURN_RULES.items():
    for storage in STORAGES:
        for status in ('reached','checked'):
            EXTRA_MATRICES[f'ras_return_{calls}_{storage}_{status}']=(
                lambda calls=calls,storage=storage,status=status:return_recovery_coverage(calls,storage,status),
                dict(rule=rules),None,len(rules))
for status in ('reached','checked'):
    for tag_class in EARLY_DIRECTION_CLASSES:
        EXTRA_MATRICES[f'early_direction_{tag_class}_{status}']=(
            lambda tag_class=tag_class,status=status:early_direction_coverage(tag_class,status),
            dict(rule=EARLY_DIRECTION_RULES),None,len(EARLY_DIRECTION_RULES))
    EXTRA_MATRICES[f'micro_capacity_{status}']=(
        lambda status=status:capacity_coverage(status),dict(rule=MICRO_CAPACITY_RULES),None,len(MICRO_CAPACITY_RULES))
    EXTRA_MATRICES[f'micro_forwarding_{status}']=(
        lambda status=status:forwarding_coverage(status),dict(rule=MICRO_FORWARDING_RULES),None,len(MICRO_FORWARDING_RULES))
    EXTRA_MATRICES[f'main_learning_{status}']=(
        lambda status=status:main_learning_coverage(status),dict(rule=MAIN_LEARNING_RULES),None,len(MAIN_LEARNING_RULES))
    EXTRA_MATRICES[f'direction_learning_{status}']=(
        lambda status=status:direction_coverage(status),dict(rule=DIRECTION_RULES),None,len(DIRECTION_RULES))
    EXTRA_MATRICES[f'direction_forwarding_{status}']=(
        lambda status=status:direction_forwarding_coverage(status),dict(rule=DIRECTION_FORWARDING_RULES),None,len(DIRECTION_FORWARDING_RULES))
    EXTRA_MATRICES[f'direction_service_{status}']=(
        lambda status=status:direction_service_coverage(status),dict(rule=DIRECTION_SERVICE_RULES),None,len(DIRECTION_SERVICE_RULES))
    EXTRA_MATRICES[f'direction_capacity_{status}']=(
        lambda status=status:direction_capacity_coverage(status),dict(rule=DIRECTION_CAPACITY_RULES),None,len(DIRECTION_CAPACITY_RULES))
    EXTRA_MATRICES[f'direction_replacement_{status}']=(
        lambda status=status:direction_replacement_coverage(status),dict(rule=DIRECTION_REPLACEMENT_RULES),None,len(DIRECTION_REPLACEMENT_RULES))
    for origin in (0,1):
        EXTRA_MATRICES[f'direction_migration_{origin}_{status}']=(
            lambda origin=origin,status=status:direction_migration_coverage(origin,status),dict(rule=DIRECTION_MIGRATION_RULES),None,len(DIRECTION_MIGRATION_RULES))
        EXTRA_MATRICES[f'direction_burst_{origin}_{status}']=(
            lambda origin=origin,status=status:direction_burst_coverage(origin,status),dict(rule=DIRECTION_BURST_RULES),None,len(DIRECTION_BURST_RULES))


def scope(kind):
    if kind == 'dual':
        axes = dict(bank=range(4), depth=range(4), mode=DUAL_MODES)
        return DUAL, DUAL_TEST, tage_dual_shadow_coverage_model, 'write_tage_dual_shadow_coverage', axes
    axes = dict(bank=range(4), origin=range(2), depth=range(4), mode=('pending', 'clean'))
    return RETAINED, RETAINED_TEST, tage_retained_owner_coverage_model, 'write_tage_retained_owner_coverage', axes


def cases(axes):
    return [dict(zip(axes, values, strict=True)) for values in product(*axes.values())]


@pytest.mark.parametrize('kind', KINDS)
def test_pytest_exposes_the_exact_original_independent_matrix(kind):
    module, test, factory, writer, axes = scope(kind)
    actual = {mark.args[0]: tuple(mark.args[1]) for mark in test.pytestmark
              if mark.name == 'parametrize'}
    assert actual == {axis: tuple(values) for axis, values in axes.items()}
    assert len(cases(actual)) == (128 if kind == 'dual' else 64)
    assert {mark.args[0] for mark in test.pytestmark if mark.name == 'feature'} == {
        'BPU-TAGE-035' if kind == 'dual' else 'BPU-TAGE-034'}


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', KINDS)
async def test_all_partial_contributions_merge_to_the_identical_serial_full_schema(kind, monkeypatch):
    module, test, factory, writer, axes = scope(kind)
    merged = CoverageDatabase()
    serial = factory()
    calls, contributions = [], []
    agent = SimpleNamespace()
    async def check(received, **coordinates):
        assert received is agent
        calls.append(coordinates)
    def capture(group, root):
        contributions.append(group)
        assert len(calls) == len(contributions), 'only export after the scenario passes'
        assert group.definition.digest == factory().definition.digest
        assert not group.covered
        assert group.cross_coverage('all_dimensions') == pytest.approx(100 / len(cases(axes)))
        merged.merge(CoverageDatabase([group]))
    monkeypatch.setattr(module, 'check_case', check)
    monkeypatch.setattr(module, writer, capture)
    for coordinates in cases(axes):
        await test(agent, **coordinates)
        for phase in ('native', 'forward', 'reverse'):
            serial.sample(dict(**coordinates, phase=phase))
    assert calls == cases(axes)
    actual = merged[serial.instance]
    actual.assert_coverage(100.0)
    # Independent pytest items have distinct evidence origins, unlike the old
    # one-group serial loop. Only identity/provenance bookkeeping may differ;
    # every schema field, bin counter and acceptance field must remain equal.
    assert len(actual.report()['origins']) == len(cases(axes))
    assert len(serial.report()['origins']) == 1
    def semantic(value):
        if isinstance(value, dict):
            return {key: semantic(item) for key, item in value.items()
                    if key not in ('origins', 'active_origin', 'snapshot_id', 'provenance')}
        if isinstance(value, list):
            return [semantic(item) for item in value]
        return value
    assert semantic(actual.report()) == semantic(serial.report())
    # Parsing revalidates evidence/counter/origin consistency as well.
    CoverageDatabase.from_dict(merged.report())


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', KINDS)
async def test_failed_scenario_exports_no_credit(kind, monkeypatch):
    module, test, factory, writer, axes = scope(kind)
    async def fail(*args, **kwargs):
        raise AssertionError('native comparison failed')
    writes = []
    monkeypatch.setattr(module, 'check_case', fail)
    monkeypatch.setattr(module, writer, lambda *args: writes.append(args))
    with pytest.raises(AssertionError, match='native comparison failed'):
        await test(object(), **cases(axes)[0])
    assert not writes


@lru_cache(maxsize=2)
def fake_abtb_report(missing_path=False):
    """Synthetic gate contract only; never exported as DUT evidence."""
    group = CounterCoverage().transitions
    for bank, entry_set, way in CELLS:
        cell = cell_label(bank, entry_set, way)
        for cause, paths in PATHS.items():
            for path in paths:
                if missing_path and (bank, entry_set, way, cause, path) == (3, 63, 3, 'later_taken', 'dec0_0'):
                    continue
                group.sample(dict(cell=cell, path=cause + '.' + path), details=False)
    return group.report()


def full_report(*, missing_kind=None, missing_phase=False, missing_abtb_path=False, missing_extra_bin=None,
                representative_only=False, missing_semantic_path=False):
    groups = []
    for kind in KINDS:
        module, test, factory, writer, axes = scope(kind)
        if missing_kind == kind:
            continue
        group = factory()
        for index, coordinates in enumerate(cases(axes)):
            for phase in ('native', 'forward', 'reverse'):
                if missing_phase and kind == 'dual' and index == 0 and phase == 'reverse':
                    continue
                group.sample(dict(**coordinates, phase=phase))
        groups.append(group)
    if missing_kind != 'abtb':
        counter = CounterCoverage()
        if not representative_only:
            counter.transitions = CoverGroup.from_report(fake_abtb_report(missing_abtb_path))
        for way in range(4):
            for cause, paths in PATHS.items():
                for path in paths:
                    if missing_semantic_path and (way, cause, path) == (3, 'later_taken', 'dec0_0'):
                        continue
                    counter.semantic.sample(dict(way=way, path=cause + '.' + path), details=False)
                    if representative_only:
                        counter.transitions.sample(dict(cell=cell_label(0, 0, way),
                            path=cause + '.' + path), details=False)
        groups.extend(counter.groups)
    for kind, (factory, axes, cross, _) in EXTRA_MATRICES.items():
        if kind == missing_kind:
            continue
        group = factory()
        for index, coordinates in enumerate(cases(axes)):
            if (representative_only and kind == 'mbtb_replacement_physical'
                    and coordinates['index'] not in MBTB_REPRESENTATIVE_INDICES):
                continue
            missing=(index==0 if cross is not None or len(axes)==1 else coordinates['rule']==axes['rule'][0])
            if kind == missing_extra_bin and missing:
                continue
            group.sample(coordinates)
        groups.append(group)
    replicas=mbtb_entry_keys_coverage_model()
    from suites.frontend.bpu.testbenches.mbtb.model.two_key_programs import programs
    for p in programs('production' if representative_only else 'physical'):
        for phase in ('prepared','updated','revisited'):replicas.sample(dict(p.sample(),phase=phase),details=False)
    groups.append(replicas)
    cleanup=mbtb_cleanup_overlap_coverage_model()
    from suites.frontend.bpu.testbenches.mbtb.model.cleanup_programs import programs as cleanup_programs
    for p in cleanup_programs('production' if representative_only else 'physical'):
        for phase in ('prepared','overlapped','revisited'):cleanup.sample(dict(p.sample(),phase=phase),details=False)
    groups.append(cleanup)
    return CoverageDatabase(groups).report()


def test_production_merge_gate_accepts_complete_semantics_and_keeps_physical_schema():
    result = GATE.validate_parallel_case_coverage(full_report())
    assert len(result['source_lifetimes']) == 166
    assert all(row == dict(full_required=True, coverage=100)
               for row in result['source_lifetimes'].values())


@pytest.mark.parametrize('missing', (*KINDS, 'abtb', *EXTRA_MATRICES))
def test_missing_matrix_is_rejected(missing):
    with pytest.raises(ValueError, match='missing or changed parallel matrix schema'):
        GATE.validate_parallel_case_coverage(full_report(missing_kind=missing))


def test_one_missing_phase_still_fails_the_full_run_gate():
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(full_report(missing_phase=True))


def test_one_missing_later_taken_saturation_bin_rejects_full_publication():
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(full_report(missing_abtb_path=True), profile='physical')


@pytest.mark.parametrize('kind', EXTRA_MATRICES)
def test_one_missing_new_requirement_bin_rejects_full_publication(kind):
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(full_report(missing_extra_bin=kind),
            profile='physical' if kind == 'mbtb_replacement_physical' else 'production')


@pytest.mark.parametrize('kind', EXTRA_MATRICES)
def test_new_requirement_denominators_are_complete_and_counts_are_fresh(kind):
    factory, axes, cross, denominator = EXTRA_MATRICES[kind]
    group = factory()
    for sample in cases(axes):
        group.sample(sample)
    assert len(cases(axes)) == denominator
    assert (group.coverage if cross is None else group.cross_coverage(cross)) == 100
    assert (factory().coverage if cross is None else factory().cross_coverage(cross)) == 0


def test_final_fake_full_run_covers_all_original_required_bins():
    report = full_report()
    database = CoverageDatabase.from_dict(report)
    assert len(database.groups) == 326
    for group in database.groups.values():
        if group.instance.endswith(('counter_write_reset_all_cells', 'counter_reset_priority_all_cells')):
            continue  # Neither profile claims reset/priority closure.
        matrix = next((cross for factory, _, cross, _ in EXTRA_MATRICES.values()
                       if factory().instance == group.instance),
            'way_path_matrix' if group.instance.endswith('counter_semantic_paths') else
            'physical_path_matrix' if group.instance.endswith('integrated_abtb_counter_paths_all_cells') else 'all_dimensions')
        assert (group.coverage if matrix is None else group.cross_coverage(matrix)) == 100
        group.assert_coverage(100)


def test_production_accepts_representatives_without_shrinking_physical_denominator():
    result = GATE.validate_parallel_case_coverage(full_report(representative_only=True))
    assert result['semantic'] == dict(total_bins=48, coverage=100, full_required=True)
    assert result['physical'] == dict(total_bins=12288, coverage=100 / 256, full_required=False)
    assert result['mbtb_replacement_physical'] == dict(total_bins=24576,coverage=100 / 128,full_required=False)
    assert result['threshold_votes'] == dict(total_bins=52,full_required=True,reached=100,checked=100)
    assert result['micro_ras'] == dict(total_bins=4,full_required=True,reached=100,checked=100)
    assert result['tage_raw_qualified_routing'] == dict(rule_bins=5,full_required=True,reached=100,checked=100)
    assert result['tage_late_branch_discovery'] == dict(rule_bins=5,full_required=True,reached=100,checked=100)
    assert result['tage_alternate_hierarchy'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['tage_interleaved_resolve'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_pipeline'] == {family:dict(rule_bins=len(rules),full_required=True,reached=100,checked=100)
        for family,rules in PIPELINE_RULES.items()}
    assert result['ras_redo_boundaries'] == {str(calls):dict(rule_bins=len(rules),full_required=True,reached=100,checked=100)
        for calls,rules in RAS_REDO_RULES.items()}
    assert result['ras_return_recovery'] == {f'{calls}.{storage}':dict(rule_bins=len(rules),full_required=True,reached=100,checked=100)
        for calls,rules in RAS_RETURN_RULES.items() for storage in STORAGES}
    assert result['micro_capacity'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['micro_positive_forwarding'] == dict(rule_bins=5,full_required=True,reached=100,checked=100)
    assert result['owned_main_learning'] == dict(rule_bins=5,full_required=True,reached=100,checked=100)
    assert result['owned_direction_learning'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_direction_forwarding'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_direction_service'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_direction_useful'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_indirect_learning'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_indirect_service'] == {label:dict(rule_bins=6,full_required=True,reached=100,checked=100)
        for label in INDIRECT_CLASSES.values()}
    assert result['owned_main_service'] == {mode:dict(rule_bins=6,full_required=True,reached=100,checked=100)
        for mode in MAIN_SERVICE_MODES}
    assert result['owned_common_history'] == {family:dict(rule_bins=6,full_required=True,reached=100,checked=100)
        for family in COMMON_HISTORY_FAMILIES}
    assert result['owned_main_rewrite'] == dict(rule_bins=8,full_required=True,reached=100,checked=100)
    assert result['ras_reclaimed_versions'] == dict(rule_bins=8,full_required=True,reached=100,checked=100)
    assert result['ras_neutral_gap'] == dict(rule_bins=8,full_required=True,reached=100,checked=100)
    assert result['owned_direction_capacity'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_direction_replacement'] == dict(rule_bins=6,full_required=True,reached=100,checked=100)
    assert result['owned_direction_migration'] == {str(origin):dict(rule_bins=6,full_required=True,reached=100,checked=100) for origin in (0,1)}
    assert result['owned_direction_burst'] == {str(origin):dict(rule_bins=6,full_required=True,reached=100,checked=100) for origin in (0,1)}
    assert result['owned_ahead_learning'] == dict(rule_bins=7,full_required=True,reached=100,checked=100)
    assert result['owned_early_direction'] == {tag_class:dict(rule_bins=8,full_required=True,reached=100,checked=100)
        for tag_class in EARLY_DIRECTION_CLASSES}
    assert result['owned_early_opposition'] == dict(rule_bins=14,full_required=True,reached=100,checked=100)
    assert result['owned_early_positive'] == dict(rule_bins=20,full_required=True,reached=100,checked=100)
    assert result['tage_selector']=={family:dict(rule_bins=6 if family=='update' else 2,
        confidence_bins=2,full_required=True,reached=100,checked=100) for family in ('update','selection')}
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(full_report(representative_only=True), profile='physical')


def test_only_mbtb_physical_hole_is_optional_in_production_not_in_physical():
    report = full_report(missing_extra_bin='mbtb_replacement_physical')
    result = GATE.validate_parallel_case_coverage(report)
    assert result['mbtb_replacement_physical']['coverage'] < 100
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(report, profile='physical')


@pytest.mark.parametrize('profile', ('production', 'physical'))
def test_semantic_saturation_is_required_in_both_profiles(profile):
    with pytest.raises(ValueError, match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(full_report(missing_semantic_path=True), profile=profile)


def test_unknown_profile_cannot_relax_acceptance():
    with pytest.raises(ValueError, match='unknown regression profile'):
        GATE.validate_parallel_case_coverage({}, profile='invalid')


@pytest.mark.parametrize('family,status',tuple(product(('update','selection'),('reached','checked'))))
def test_selector_gate_requires_both_confidence_contexts_without_a_physical_cross(family,status):
    database=CoverageDatabase.from_dict(full_report())
    group=selector_coverage(family,status)
    rules=UPDATE_RULES if family=='update' else ('provider','alternate')
    for rule in rules:group.sample(dict(rule=rule,alt_conf=1))
    report=database.report()
    report['groups']=[group.report() if item['instance']==group.instance else item for item in report['groups']]
    with pytest.raises(ValueError,match='incomplete parallel matrix'):
        GATE.validate_parallel_case_coverage(report)
