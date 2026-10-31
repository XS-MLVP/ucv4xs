"""Acceptance for matrices split into independent process-local contributions."""
from toffee import CoverageDatabase

from suites.frontend.icache.tage.coverage.dual import tage_dual_shadow_coverage_model
from suites.frontend.icache.tage.coverage.retained import tage_retained_owner_coverage_model
from suites.frontend.icache.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.icache.bpu.coverage.alignment import coverage as alignment_coverage
from suites.frontend.icache.bpu.coverage.sc.used import used_coverage, history_coverage
from suites.frontend.icache.bpu.coverage.sc.bounds import bounds_coverage
from suites.frontend.icache.bpu.coverage.ras_micro import micro_coverage
from suites.frontend.icache.bpu.coverage.tage.selector import selector_coverage,routing_coverage
from suites.frontend.icache.bpu.coverage.tage.aging import aging_coverage, RULES as AGING_RULES
from suites.frontend.icache.bpu.coverage.ittage import directory_coverage, DIRECTORY_RULES
from suites.frontend.icache.bpu.coverage.ittage_aging import aging_coverage as ittage_aging_coverage, RULES as ITTAGE_AGING_RULES
from suites.frontend.icache.uras.coverage.semantic import semantic_coverage as uras_semantic_coverage, RULES as URAS_RULES
from suites.frontend.icache.ittage.coverage.semantic import target_coverage as ittage_target_coverage, RULES as ITTAGE_TARGET_RULES
from suites.frontend.icache.sc.coverage.semantic import semantic_coverage as sc_semantic_coverage, RULES as SC_SEMANTIC_RULES
from suites.frontend.icache.ras.coverage.semantic import semantic_coverage as ras_action_coverage, ROLES as RAS_ACTION_ROLES
from suites.frontend.icache.utage.coverage.semantic import semantic_coverage as utage_semantic_coverage, BOUNDARY_RULES as UTAGE_BOUNDARY_RULES, TYPE_RULES as UTAGE_TYPE_RULES
from suites.frontend.icache.abtb.coverage.semantic import semantic_coverage as abtb_semantic_coverage, RULES as ABTB_SEMANTIC_RULES
from suites.frontend.icache.mbtb.coverage.semantic import semantic_coverage as mbtb_semantic_coverage, RULES as MBTB_SEMANTIC_RULES
from suites.frontend.icache.tage.coverage.semantic import semantic_coverage as tage_semantic_coverage, RULES as TAGE_SEMANTIC_RULES
from suites.frontend.icache.bpu.coverage.tage.learning import learning_coverage, RULES as TAGE_LEARNING_RULES
from suites.frontend.icache.bpu.coverage.tage.fast_routing import routing_coverage as fast_routing_coverage, RULES as FAST_ROUTING_RULES
from suites.frontend.icache.bpu.coverage.tage.alternate import alternate_coverage, RULES as ALTERNATE_RULES
from suites.frontend.icache.bpu.coverage.tage.interleaved import interleaved_coverage, RULES as INTERLEAVED_RULES
from suites.frontend.icache.bpu.coverage.pipeline import pipeline_coverage, RULES as PIPELINE_RULES
from suites.frontend.icache.bpu.coverage.ras_redo import redo_coverage, RULES as RAS_REDO_RULES
from suites.frontend.icache.bpu.coverage.ras_return_recovery import return_recovery_coverage, RULES as RAS_RETURN_RULES, STORAGES
from suites.frontend.icache.bpu.coverage.micro_capacity import capacity_coverage, RULES as MICRO_CAPACITY_RULES
from suites.frontend.icache.bpu.coverage.micro_forwarding import forwarding_coverage, RULES as MICRO_FORWARDING_RULES
from suites.frontend.icache.bpu.coverage.main_learning import learning_coverage as main_learning_coverage, RULES as MAIN_LEARNING_RULES
from suites.frontend.icache.bpu.coverage.direction_learning import direction_coverage, RULES as DIRECTION_RULES
from suites.frontend.icache.bpu.coverage.direction_forwarding import forwarding_coverage as direction_forwarding_coverage, RULES as DIRECTION_FORWARDING_RULES
from suites.frontend.icache.bpu.coverage.direction_service import service_coverage as direction_service_coverage, RULES as DIRECTION_SERVICE_RULES
from suites.frontend.icache.bpu.coverage.direction_useful import useful_coverage as direction_useful_coverage, RULES as DIRECTION_USEFUL_RULES
from suites.frontend.icache.bpu.coverage.indirect_learning import indirect_coverage, RULES as INDIRECT_RULES
from suites.frontend.icache.bpu.coverage.indirect_service import service_coverage as indirect_service_coverage, RULES as INDIRECT_SERVICE_RULES, CLASSES as INDIRECT_CLASSES
from suites.frontend.icache.bpu.coverage.main_service import main_service_coverage, RULES as MAIN_SERVICE_RULES, MODES as MAIN_SERVICE_MODES
from suites.frontend.icache.bpu.coverage.common_history import common_history_coverage, RULES as COMMON_HISTORY_RULES, FAMILIES as COMMON_HISTORY_FAMILIES
from suites.frontend.icache.bpu.coverage.main_rewrite import main_rewrite_coverage, RULES as MAIN_REWRITE_RULES
from suites.frontend.icache.bpu.coverage.ras_reuse import ras_reuse_coverage, RULES as RAS_REUSE_RULES
from suites.frontend.icache.bpu.coverage.ras_neutral_gap import neutral_gap_coverage, RULES as RAS_NEUTRAL_GAP_RULES
from suites.frontend.icache.bpu.coverage.direction_capacity import capacity_coverage as direction_capacity_coverage, RULES as DIRECTION_CAPACITY_RULES
from suites.frontend.icache.bpu.coverage.direction_replacement import replacement_coverage as direction_replacement_coverage, RULES as DIRECTION_REPLACEMENT_RULES
from suites.frontend.icache.bpu.coverage.direction_migration import migration_coverage as direction_migration_coverage, RULES as DIRECTION_MIGRATION_RULES
from suites.frontend.icache.bpu.coverage.direction_burst import burst_coverage as direction_burst_coverage, RULES as DIRECTION_BURST_RULES
from suites.frontend.icache.bpu.coverage.ahead_learning import ahead_learning_coverage, RULES as AHEAD_LEARNING_RULES
from suites.frontend.icache.bpu.coverage.early_direction import direction_coverage as early_direction_coverage, RULES as EARLY_DIRECTION_RULES, CLASSES as EARLY_DIRECTION_CLASSES
from suites.frontend.icache.bpu.coverage.early_opposition import opposition_coverage as early_opposition_coverage, RULES as EARLY_OPPOSITION_RULES
from suites.frontend.icache.bpu.coverage.early_positive import positive_coverage as early_positive_coverage, RULES as EARLY_POSITIVE_RULES
from suites.frontend.icache.mbtb.coverage.catalog import mbtb_replacement_coverage_model
from suites.frontend.icache.pytest_plugins.regression import PROFILES


def validate_parallel_case_coverage(report, *, profile='production'):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    database = CoverageDatabase.from_dict(report)
    counter = CounterCoverage()
    mbtb_physical = mbtb_replacement_coverage_model()
    # Always retain/validate every physical schema, including unhit cells.
    for expected in (*counter.physical_groups, mbtb_physical):
        actual = database.groups.get(expected.instance)
        if actual is None or actual.definition.digest != expected.definition.digest:
            raise ValueError(f'missing or changed parallel matrix schema: {expected.instance}')
    for factory in (tage_dual_shadow_coverage_model, tage_retained_owner_coverage_model,
                    lambda: counter.semantic,
                    *((lambda: counter.transitions,) if profile == 'physical' else ()),
                    *((lambda: mbtb_physical,) if profile == 'physical' else ()),
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
        mbtb_replacement_physical=dict(total_bins=6144,
            coverage=database.groups[mbtb_physical.instance].cross_coverage('all_dimensions'),
            full_required=profile == 'physical'))
