from copy import deepcopy
from pathlib import Path
import ast
import pytest
from suites.frontend.bpu.bpu.model.phr.model import MASK
from suites.frontend.bpu.bpu.model.phr.model import fold
from suites.frontend.bpu.bpu.model.abtb.alias import capacity
from suites.frontend.bpu.bpu.model.abtb.alias import physical_index
from suites.frontend.bpu.bpu.model.abtb.alias import plan
from suites.frontend.bpu.bpu.model.abtb.alias import reference_group
from suites.frontend.bpu.bpu.model.abtb.alias import rtl_bank_set
from suites.frontend.bpu.bpu.model.abtb.alias import step
from suites.frontend.bpu.bpu.case.abtb.alias_plan import PILOT_CASES
from suites.frontend.bpu.bpu.case.abtb.alias_plan import checkpoint_route
from suites.frontend.bpu.bpu.case.abtb.alias_plan import final_comparison
from suites.frontend.bpu.bpu.case.abtb.alias_plan import input_qualified
from suites.frontend.bpu.bpu.case.abtb.alias_plan import programs
from suites.frontend.bpu.bpu.case.abtb.alias_plan import qualified_fixture

STAGE = Path(__file__).resolve().parent


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('entry_set', range(64))
def test_all_physical_groups_keep_short_real_checkpoint_routes_and_five_alias_pairs(bank, entry_set):
    intent = plan(bank, entry_set)
    pcs = [pc for pair in intent['taken_pairs'] for pc in pair]
    assert max(pcs) - min(pcs) < 3200
    assert len(set(pcs)) == 10 and max(capacity(intent['taken_pairs']).values()) <= 2
    for a, b in intent['taken_pairs']:
        for pc in (a, b):
            route = checkpoint_route(pc)
            assert route['actual_not_taken_checkpoint_targets'][-1] == pc - 1
        for prefix in range(64):
            history = step(step((MASK & ~63) | prefix, a, b), b, a)
            assert rtl_bank_set(b, fold(history, 6, 6)) == (bank, entry_set)
            assert physical_index(b, fold(history, 6, 6)) == entry_set * 4 + bank


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('entry_set', (0, 1, 31, 63))
@pytest.mark.parametrize('idle', (0, 1))
def test_shortened_pair_addresses_preserve_full52_pending_and_pointer_wrap(bank, entry_set, idle):
    result = reference_group(plan(bank, entry_set), idle)
    assert result['full52_checks'] == 320 * (idle + 1)


@pytest.mark.parametrize('bank,entry_set', PILOT_CASES)
def test_pilot_inputs_qualify_without_provider_or_conditional_hit_fields(bank, entry_set):
    intent, source, token = qualified_fixture(bank, entry_set)
    assert input_qualified(source, token, intent, 0)
    assert not input_qualified(source, None, intent, 0)


@pytest.mark.parametrize('bank,entry_set', PILOT_CASES)
@pytest.mark.parametrize('fault', ('source_PC', 'token_PC', 'bank', 'entry_set', 'folded6', 'mode', 'redirect'))
def test_every_source_dimension_is_checked_without_relabeling(bank, entry_set, fault):
    intent, source, token = qualified_fixture(bank, entry_set)
    redirect = 0
    if fault == 'source_PC':
        source['prediction']['start_pc'] ^= 256
    elif fault == 'token_PC':
        token['pc'] ^= 256
    elif fault == 'mode':
        token['mode'] = 'S2_override'
    elif fault == 'redirect':
        redirect = 1
    else:
        token[fault] ^= 1
    assert not input_qualified(source, token, intent, redirect)


@pytest.mark.parametrize('bank,entry_set', PILOT_CASES)
@pytest.mark.parametrize('field', ('valid', 'pc', 'taken', 'position', 'target', 'branch_type'))
def test_final_comparison_detects_each_wrong_associated_S3_field(bank, entry_set, field):
    program = programs(plan(bank, entry_set))[1]
    final = dict(valid=1, pc=program['pc'], taken=1, position=7,
        target=program['target'], branch_type=1)
    rise = dict(tick=40, public_meta=dict(valid=1), abtb=dict(final=deepcopy(final)))
    source = dict(meta_tick=40)
    expected, actual = final_comparison(program, source, rise)
    assert expected == actual
    rise['abtb']['final'][field] ^= 1
    expected, actual = final_comparison(program, source, rise)
    assert expected != actual


@pytest.mark.parametrize('fault', ('tick', 'valid'))
def test_final_comparison_rejects_wrong_metadata_association(fault):
    rise = dict(tick=40, public_meta=dict(valid=1))
    if fault == 'tick':
        rise['tick'] += 1
    else:
        rise['public_meta']['valid'] = 0
    with pytest.raises(ValueError):
        final_comparison({}, dict(meta_tick=40), rise)


@pytest.mark.parametrize('bank,entry_set', ((True, 0), (4, 0), (-1, 0), (0, True),
    (0, 64), (0, -1), (1, 1.0), (1, '0')))
def test_invalid_physical_coordinates_are_not_relabelled(bank, entry_set):
    with pytest.raises(ValueError):
        plan(bank, entry_set)


def test_pilot_covers_four_real_banks_without_claiming_full_matrix_execution():
    assert len(PILOT_CASES) == 4 and {bank for bank, _ in PILOT_CASES} == set(range(4))
    assert (1, 0) in PILOT_CASES


def test_DUT_testcase_contains_only_scenario_intent_not_pin_or_edge_scheduling():
    module = ast.parse((Path(__file__).resolve().parents[2] / 'testcase/test_integrated_abtb_counters.py').read_text())
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call)]
    names = [node.func.id for node in calls if isinstance(node.func, ast.Name)]
    expected = {
        'test_integrated_abtb_five_alias_four_way_reuse': 'five_alias',
        'test_integrated_abtb_true_final_not_taken': 'final_not_taken',
        'test_integrated_abtb_later_taken_four_way_paths': 'later_taken',
    }
    scenarios = [node for node in module.body if isinstance(node, ast.AsyncFunctionDef)]
    assert [node.name for node in scenarios] == list(expected)
    assert names == ['check_counter_case'] * len(expected)
    for scenario in scenarios:
        assert len(scenario.body) == 1
        statement, = scenario.body
        assert isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Await)
        call = statement.value.value
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        assert call.func.id == 'check_counter_case'
        kind = next(keyword.value for keyword in call.keywords if keyword.arg == 'kind')
        assert isinstance(kind, ast.Constant) and kind.value == expected[scenario.name]
    assert not any(isinstance(node, ast.Attribute) and node.attr in ('set', 'get', 'gather') for node in ast.walk(module))


@pytest.mark.parametrize('offset', range(16))
def test_every_half_fetch_offset_has_a_real_preceding_CFI_checkpoint(offset):
    pc = 0x40010000 + offset
    route = checkpoint_route(pc)
    source = route['cold_lead']
    for target in route['actual_not_taken_checkpoint_targets']:
        assert source & ~15 == (target - 1) & ~15 and source <= target - 1
        source = target
    assert source == pc - 1
    assert source & ~7 == (pc - 1) & ~7


@pytest.mark.parametrize('bank,entry_set', PILOT_CASES)
def test_joint_PHR_and_index_pipeline_consumes_old_history_before_S1_update(bank, entry_set):
    intent = plan(bank, entry_set)
    result = reference_group(intent)
    assert result['joint_ahead_index_phase_checks'] == 300
    assert intent['low4_index_source_history'] == intent['low4_history_before_a']


def test_deep_physical_universe_preserves_all256_groups_and_not_only_four_pilots():
    from suites.frontend.bpu.bpu.case.abtb.alias_plan import ALL_CASES
    assert len(ALL_CASES) == len(set(ALL_CASES)) == 256
    assert set(ALL_CASES) == {(bank, entry_set) for bank in range(4) for entry_set in range(64)}
    assert set(PILOT_CASES) <= set(ALL_CASES)


@pytest.mark.parametrize('bank,entry_set', PILOT_CASES)
def test_five_real_alias_programs_preserve_one_group_five_tags_and_four_way_replacement(bank, entry_set):
    intent = plan(bank, entry_set)
    branches = [programs(intent, alias)[1] for alias in range(5)]
    assert len({row['pc'] & ((1 << 24) - 1) for row in branches}) == 5
    assert len({row['target'] & ((1 << 22) - 1) for row in branches}) == 5
    for alias, branch in enumerate(branches):
        a, b = intent['taken_pairs'][alias]
        assert branch['pc'] == a and branch['target'] == b
        source = dict(prediction=dict(start_pc=a))
        token = dict(pc=b, bank=bank, entry_set=entry_set, mode='normal',
            folded6=intent['low4_index_source_history'])
        assert input_qualified(source, token, intent, 0, alias=alias)
        assert not input_qualified(source, token, intent, 0, alias=(alias+1) % 5)
    assert len(set(intent['expected_way_order'][:4])) == 4
    assert intent['expected_way_order'][4] in intent['expected_way_order'][:4]
