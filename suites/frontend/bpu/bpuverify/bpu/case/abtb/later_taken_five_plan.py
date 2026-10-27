"""Five-edge recurrence: vary cadence without weakening physical requirements."""
from collections import Counter
from bpuverify.bpu.model.phr.model import BpuPhrReference
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.model.abtb.alias import boundary
from bpuverify.bpu.model.abtb.alias import mainbtb_route
from bpuverify.bpu.model.abtb.alias import physical_index
from bpuverify.bpu.model.abtb.index import IndexReference
from bpuverify.bpu.case.abtb.later_taken_four_plan import PHASES, checkpoint_route, input_qualified, final_comparison, required_operations, plan as four_node_plan

def programs(intent, alias):
    a, b, c, d = intent['cycles'][alias]
    extra = intent['extra_pcs'][alias]
    return (dict(pc=a, position=6, target=extra, branch_type=1, taken=1), dict(pc=extra, position=7, target=b, branch_type=3, taken=1), dict(pc=b, position=7, target=c, branch_type=3, taken=1), dict(pc=c, position=7, target=d, branch_type=3, taken=1), dict(pc=d, position=7, target=a, branch_type=3, taken=1))

def selected_program(intent, alias, goal):
    if type(goal) is not int or goal not in (0, 3):
        raise ValueError('direction goal must be 0 or 3')
    a, _, _, _ = intent['cycles'][alias]
    return dict(pc=a, target=intent['extra_pcs'][alias], position=6 if goal else 7, branch_type=1 if goal else 3, taken=1)

def capacity(intent):
    rows = [row for alias in range(5) for row in programs(intent, alias)]
    rows.extend((dict(pc=a, position=7) for a, _, _, _ in intent['cycles']))
    return Counter((tuple((mainbtb_route(row['pc'], row['position'])[key] for key in ('selected_physical_align', 'internal_bank', 'entry_set'))) for row in rows))

def edges(intent, alias, goal):
    rows = list(programs(intent, alias))
    rows[0] = selected_program(intent, alias, goal)
    return rows

def steady_indices(intent, alias, goal):
    history, created, result = (0, [], {})
    for cycle in range(3):
        for row in edges(intent, alias, goal):
            if cycle:
                result[row['pc']] = created[-2]
            created.append(physical_index(row['target'], history))
            branch_pc = (row['pc'] & ~7) + row['position']
            history = (history << 2 ^ path_hash(branch_pc, row['target'])) & 15
    return result

def plan(bank, entry_set):
    intent = dict(four_node_plan(bank, entry_set))
    occupied = {pc for cycle in intent['cycles'] for pc in cycle}
    for offset in range(0, 2048, 8):
        extra = [1073828032 + offset + alias * 256 for alias in range(5)]
        if len(set(extra)) != 5 or occupied & set(extra):
            continue
        intent['extra_pcs'] = extra
        residents = capacity(intent)
        if max(residents.values()) > 2:
            continue
        peers, okay = (set(), True)
        for alias, (a, _, _, _) in enumerate(intent['cycles']):
            for goal in (0, 3):
                indices = steady_indices(intent, alias, goal)
                wanted = intent['physical_index']
                if indices[a] != wanted or any((value == wanted for pc, value in indices.items() if pc != a)):
                    okay = False
                    break
                peers.update((value for pc, value in indices.items() if pc != a))
            if not okay:
                break
        if okay:
            intent.update(recurrence_edges=5, resident_branches=30, maximum_MainBTB_residents_per_group=max(residents.values()), peer_physical_indices=sorted(peers), cadence_change_is_not_DUT_coverage=True)
            return intent
    raise AssertionError(('no five-node full-alias layout', bank, entry_set))

def joint_proof(intent, rounds=16):
    full_checks = target_checks = 0
    for alias, (a, _, _, d) in enumerate(intent['cycles']):
        model, index, history = (BpuPhrReference(), IndexReference(), 0)
        index.advance(reset=1, enable=1, fire0=0, fire1=0, fire2=0, s2_override=0, s3_override=0, redirect=0, pc=0, folded6=0, tick=0)
        created, phase_histories, tick, cycle = ([], [], 0, 0)
        for goal in (3, 0, 3):
            for _ in range(rounds):
                for row in edges(intent, alias, goal):
                    source, target, position = (row['pc'], row['target'], row['position'])
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
                    history = (history << 2 ^ path_hash((source & ~7) + position, target)) & MASK
                    assert model.logical() == history
                    if cycle >= 1:
                        assert history != 0
                    full_checks += 1
                cycle += 1
            phase_histories.append(history)
        assert phase_histories[0] != phase_histories[1]
        assert phase_histories[0] == phase_histories[2]
    return dict(full52_checks=full_checks, actual_A_metadata_index_checks=target_checks, aliases=5, recurrence_edges=5, maximum_MainBTB_residents=max(capacity(intent).values()), final_taken_in_both_phases=True, no_DUT_or_raw_created=True)
