"""Joint PHR and ahead-index model: oldFoldedPhr precedes current S1 update."""
from collections import Counter
from copy import deepcopy
from bpuverify.bpu.model.phr.model import BpuPhrReference
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.abtb.model.state.counter import touch
from bpuverify.abtb.model.state.counter import victim
from bpuverify.bpu.model.abtb.index import IndexReference


def byte_pc(addr):
    if type(addr) is not int or not 0 <= addr < 1 << 49:
        raise ValueError('Pc.addr must be a representable halfword address')
    return addr << 1


def physical_index(addr, folded6):
    return (byte_pc(addr) & 255) ^ (folded6 & 15)


def rtl_bank_set(addr, folded6):
    low = ((addr & 7) << 1) ^ (folded6 & 15)
    return low & 3, (((addr >> 3) & 15) << 2) | (low >> 2)


def step(history, source, target):
    return ((history << 2) ^ path_hash((source & ~7) + 7, target)) & MASK


def pair_history_before_b(a, b):
    return ((b >> 1) & 15) ^ (((a >> 1) & 3) << 2)


def mainbtb_route(addr, position):
    if type(position) is not int or not 0 <= position < 16:
        raise ValueError('CFI position must be 0..15')
    first_align = (addr >> 3) & 1
    logical = tuple(addr if i == 0 else (addr + 8 * i) & ~7 for i in range(2))
    physical = tuple(logical[(bank - first_align) % 2] for bank in range(2))
    selected = (first_align + (position >> 3)) % 2
    routed = physical[selected]
    return dict(read_start_pc_by_physical_align=physical,
        FTQ_train_start_pc_by_physical_align=physical,
        selected_physical_align=selected, selected_start_pc=routed,
        internal_bank=(routed >> 4) & 1, entry_set=(routed >> 5) & 63,
        tag=(routed >> 11) & 65535, entry_position=position & 7,
        source_offset=addr & 7, aligned_byte_start=byte_pc(addr) & ~15)


def capacity(pairs):
    return Counter((row['selected_physical_align'], row['internal_bank'], row['entry_set'])
        for pair in pairs for addr in pair for row in (mainbtb_route(addr, 7),))


def expected_way_order():
    state, ways = 0, []
    for _ in range(5):
        selected = victim(state)
        ways.append(selected)
        state = touch(state, selected)
    return ways


def plan(bank, entry_set):
    if type(bank) is not int or not 0 <= bank < 4:
        raise ValueError('physical bank must be 0..3')
    if type(entry_set) is not int or not 0 <= entry_set < 64:
        raise ValueError('physical set must be 0..63')
    wanted = entry_set * 4 + bank
    b = 0x40010000 + ((wanted & 240) >> 1)
    for offset in range(128):
        a = 0x40010800 + offset
        before_b = pair_history_before_b(a, b)
        before_a = pair_history_before_b(b, a)
        # S1 A selects next start B, but normalPathHist is oldFoldedPhr:
        # history BEFORE A. This a0 source later indexes the prediction of A.
        peer = physical_index(a, before_b)
        pairs = tuple((a + alias * 256, b + alias * 256) for alias in range(5))
        if physical_index(b, before_a) == wanted and peer != wanted and max(capacity(pairs).values()) <= 2:
            return dict(bank=bank, entry_set=entry_set, physical_index=wanted,
                PC_unit='Pc.addr: halfword; byte address = addr << 1',
                taken_pairs=pairs, conditional_position=7, return_position=7,
                source_before_target_a='B', target_a_tag_source='A',
                low4_history_before_b=before_b, low4_history_before_a=before_a,
                low4_index_source_history=before_a,
                index_history_phase='oldFoldedPhr before current S1 A, not after A-to-B',
                peer_physical_index=peer,
                maximum_MainBTB_residents_per_physical_group=max(capacity(pairs).values()),
                expected_way_order=expected_way_order(),
                exact_runtime_normal_index_phase_NOT_proven=True,
                no_DUT_or_raw_or_hardware_mapping_claim=True)
    raise AssertionError(('no feasible pair', bank, entry_set))


def boundary(model, source=None, target=None):
    idle = dict(start_pc=0, prediction=dict(taken=0, position=0, target=0), valid=0)
    s1 = idle if source is None else dict(start_pc=source,
        prediction=dict(taken=1, position=7, target=target), valid=1)
    return dict(s1=s1, s2=dict(idle, meta=deepcopy(model.meta2)),
        s3=dict(idle, meta=deepcopy(model.meta3)), redirect=dict(valid=0),
        stall=int(source is None), fire0=int(source is not None),
        fire1=int(source is not None), fire2=int(source is not None))


def reference_group(intent, idle_cycles=0):
    checks, index_checks = 0, 0
    for a, b in intent['taken_pairs']:
        model, index, history = BpuPhrReference(), IndexReference(), 0
        index.advance(reset=1, enable=1, fire0=0, fire1=0, fire2=0,
            s2_override=0, s3_override=0, redirect=0, pc=0, folded6=0, tick=0)
        tick = 0
        for cycle in range(32):
            for source, target, wanted in ((a, b, intent['physical_index']),
                    (b, a, intent['peer_physical_index'])):
                if cycle >= 2:
                    assert index.check(dict(valid=1, bankMask=1 << (wanted & 3), setIdx=wanted >> 2), 1)
                    assert index.s2['pc'] == target and index.s2['mode'] == 'normal'
                    index_checks += 1
                tick += 1
                index.advance(reset=0, enable=1, fire0=1, fire1=1, fire2=1,
                    s2_override=0, s3_override=0, redirect=0, pc=target,
                    folded6=model.state['fold1'][2], tick=tick)
                model.advance(boundary(model, source, target), reset=0)
                history = step(history, source, target)
                assert model.logical() == history
                checks += 1
                if cycle >= 1:
                    following = intent['peer_physical_index'] if source == a else intent['physical_index']
                    assert physical_index(source, folds(history)[2]) == following
                    assert history != 0
                for _ in range(idle_cycles):
                    tick += 1
                    index.advance(reset=0, enable=1, fire0=0, fire1=0, fire2=0,
                        s2_override=0, s3_override=0, redirect=0,
                        pc=target, folded6=model.state['fold1'][2], tick=tick)
                    model.advance(boundary(model), reset=0)
                    assert model.logical() == history
                    checks += 1
    return dict(full52_checks=checks, joint_ahead_index_phase_checks=index_checks,
        aliases=5, pair_cycles_per_alias=32, pointer_wrap_exercised_in_model=True,
        runtime_index_snapshot_NOT_proven=True, no_DUT_or_raw_created=True)
