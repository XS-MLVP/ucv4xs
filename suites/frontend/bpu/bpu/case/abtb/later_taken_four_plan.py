"""Input-only resident conditional + later fallback, separate from final NT."""
from suites.frontend.bpu.models.configuration import PHR_STORAGE_BITS, MAIN_WAYS
from collections import Counter
from suites.frontend.bpu.bpu.model.phr.model import BpuPhrReference
from suites.frontend.bpu.bpu.model.phr.model import MASK
from suites.frontend.bpu.bpu.model.phr.model import folds
from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.model.abtb.alias import boundary
from suites.frontend.bpu.bpu.model.abtb.alias import mainbtb_route
from suites.frontend.bpu.bpu.model.abtb.alias import physical_index
from suites.frontend.bpu.bpu.model.abtb.index import IndexReference
from suites.frontend.bpu.bpu.case.abtb.alias_plan import checkpoint_route
from suites.frontend.bpu.bpu.case.abtb.final_not_taken_plan import input_qualified
from suites.frontend.bpu.bpu.case.abtb.final_not_taken_plan import final_comparison
from suites.frontend.bpu.bpu.model.abtb.final_not_taken import steady_indices
from suites.frontend.bpu.bpu.model.abtb.final_not_taken import fall_through
PHASES = (('positive_first', 3, ('inc2_3', 'inc3_3')), ('later_taken_to_zero', 0, ('dec3_2', 'dec2_1', 'dec1_0', 'dec0_0')), ('positive_from_zero', 3, ('inc0_1', 'inc1_2', 'inc2_3', 'inc3_3')))

def programs(intent, alias):
    a, b, c, d = intent['cycles'][alias]
    return (dict(pc=a, position=6, target=b, branch_type=1, taken=1), dict(pc=b, position=7, target=c, branch_type=3, taken=1), dict(pc=c, position=7, target=d, branch_type=3, taken=1), dict(pc=d, position=7, target=a, branch_type=3, taken=1))

def capacity(cycles):
    result = Counter()
    for a, b, c, d in cycles:
        for pc, position in ((a, 6), (a, 7), (b, 7), (c, 7), (d, 7)):
            route = mainbtb_route(pc, position)
            result[tuple((route[key] for key in ('selected_physical_align', 'internal_bank', 'entry_set')))] += 1
    return result

def selected_program(intent, alias, goal):
    if type(goal) is not int or goal not in (0, 3):
        raise ValueError('direction goal must be 0 or 3')
    a, b, _, _ = intent['cycles'][alias]
    return dict(pc=a, target=b, position=6 if goal else 7, branch_type=1 if goal else 3, taken=1)

def plan(bank, entry_set):
    if type(bank) is not int or bank not in range(4):
        raise ValueError('bank must be integer 0..3')
    if type(entry_set) is not int or entry_set not in range(64):
        raise ValueError('set must be integer 0..63')
    wanted = entry_set * 4 + bank
    d = 1073819776 + ((wanted & 240) >> 1)
    for salt in range(16):
        for a_extra in range(0, 256, 8):
            a = 1073811584 + a_extra
            b = a + 16
            for c_extra in range(0, 128, 32):
                c = 1073817760 + salt * 2048 + c_extra + (wanted & 15) * 2
                cycles = tuple(((a + alias * 256, b + alias * 256, c + alias * 256, d + alias * 256) for alias in range(5)))
                if len({pc for cycle in cycles for pc in cycle}) != 20:
                    continue
                peers = set((steady_indices(a, b, c, d, 1)[index] for index in (0, 1, 3)))
                if steady_indices(a, b, c, d, 1)[2] != wanted or wanted in peers or max(capacity(cycles).values()) > MAIN_WAYS:
                    continue
                return dict(bank=bank, entry_set=entry_set, physical_index=wanted, cycles=cycles, conditional_position=6, fallback_position=7, return_positions=(7, 7, 7), low4_index_source_history=c >> 1 & 15, index_request_pc=d, peer_physical_indices=sorted(peers), address_region_salt=salt, maximum_MainBTB_residents_per_group=max(capacity(cycles).values()), PC_unit='halfword Pc.addr; byte address=addr<<1', negative_path='final taken=1 position=7 after conditional position=6; not final NT', no_DUT_or_raw_created=True)
    raise AssertionError(('no capacity-safe later-taken cycle', bank, entry_set))

def required_operations(confirmed, intent, alias, phase, required):
    a, _, _, _ = intent['cycles'][alias]
    return {name: [row for row in confirmed if row['phase'] == phase and row['bank'] == intent['bank'] and (row['set_index'] == intent['entry_set']) and (row['transition'] == name) and (row.get('feedback') is not None) and (row['feedback']['pc'] == a) and (row['feedback']['taken'] == 1) and (row['feedback']['position'] == (7 if name.startswith('dec') else 6))] for name in required}

def joint_proof(intent, rounds=16):
    rounds=max(rounds,(PHR_STORAGE_BITS+7)//8+2)
    full_checks = target_checks = 0
    for a, b, c, d in intent['cycles']:
        model, index, history = (BpuPhrReference(), IndexReference(), 0)
        index.advance(reset=1, enable=1, fire0=0, fire1=0, fire2=0, s2_override=0, s3_override=0, redirect=0, pc=0, folded6=0, tick=0)
        created = []
        tick = 0
        for cycle, goal in enumerate([3] * rounds + [0] * rounds + [3] * rounds):
            for source, target, position in ((a, b, 6 if goal else 7), (b, c, 7), (c, d, 7), (d, a, 7)):
                assert model.state['fold1'] == folds(history)
                if len(created) >= 2:
                    wanted = created[-2]
                    assert index.check(dict(valid=1, bankMask=1 << (wanted & 3), setIdx=wanted >> 2), 1)
                if cycle >= 1:
                    assert (index.s2['entry_set'] * 4 + index.s2['bank'] == intent['physical_index']) == (source == a)
                    if source == a:
                        assert index.s2['pc'] == d
                        assert index.s2['folded6'] & 15 == intent['low4_index_source_history']
                        target_checks += 1
                created.append(physical_index(target, history & 63))
                tick += 1
                index.advance(reset=0, enable=1, fire0=1, fire1=1, fire2=1, s2_override=0, s3_override=0, redirect=0, pc=target, folded6=model.state['fold1'][2], tick=tick)
                inputs = boundary(model, source, target)
                inputs['s1']['prediction'].update(position=position, taken=1)
                model.advance(inputs, reset=0)
                history = (history << 2 ^ path_hash((source & ~15) + position, target)) & MASK
                assert model.logical() == history
                if cycle >= 1:
                    assert history != 0
                full_checks += 1
    return dict(full52_checks=full_checks, actual_A_metadata_index_checks=target_checks, aliases=5, maximum_MainBTB_residents=max(capacity(intent['cycles']).values()), final_taken_in_both_phases=True, no_DUT_or_raw_created=True)
