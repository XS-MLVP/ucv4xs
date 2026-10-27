"""Input-only four-node cycle; associate A with the actual two-beat-old index.

A -> B is conditional and shares its true fall-through destination.
B -> C -> D -> A are unconditional. The index observed with A originates
from C's earlier D request, not from A's current B request.
"""
from collections import Counter
from bpuverify.bpu.model.phr.model import BpuPhrReference
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.model.abtb.alias import boundary
from bpuverify.bpu.model.abtb.alias import mainbtb_route
from bpuverify.bpu.model.abtb.alias import physical_index
from bpuverify.bpu.model.abtb.index import IndexReference

PHASES = (
    ('positive_first', 3, ('inc2_3', 'inc3_3')),
    ('final_not_taken_to_zero', 0, ('dec3_2', 'dec2_1', 'dec1_0', 'dec0_0')),
    ('positive_from_zero', 3, ('inc0_1', 'inc1_2', 'inc2_3', 'inc3_3')),
)
ALL_CASES = tuple((bank, entry_set) for bank in range(4) for entry_set in range(64))


def fall_through(addr):
    """MiniConfig: 32-byte fetch, 16-byte alignment, 4096-byte page.

    Addresses here are Pc.addr halfwords, not byte addresses. Geometric
    formulation is checked independently against generated RTL bit slices.
    """
    if type(addr) is not int or not 0 <= addr < (1 << 49) - 16:
        raise ValueError('non-overflowing halfword Pc.addr required')
    start = addr << 1
    following = (start + 32) & ~15
    crossing = (start >> 12) != (following >> 12)
    target = following & ~4095 if crossing else following
    return dict(target=target >> 1, position=(target - (start & ~15)) // 2 - 1,
        taken=0, branch_type=0, cross_page=crossing)



def programs(cycles):
    return tuple(row for a,b,c,d in cycles for row in (
        dict(pc=a,position=6,target=b,branch_type=1),
        dict(pc=b,position=7,target=c,branch_type=3),
        dict(pc=c,position=7,target=d,branch_type=3),
        dict(pc=d,position=7,target=a,branch_type=3)))


def capacity(cycles):
    result=Counter()
    for row in programs(cycles):
        route=mainbtb_route(row['pc'],row['position'])
        assert route['source_offset']<=route['entry_position']
        result[(route['selected_physical_align'],route['internal_bank'],route['entry_set'])]+=1
    return result


def edges(a,b,c,d,outcome):
    return ((a,b,6 if outcome else fall_through(a)['position'],outcome),
        (b,c,7,1),(c,d,7,1),(d,a,7,1))


def advance_scalar(history,source,target,position,taken):
    return ((history<<2)^path_hash((source&~7)+position,target))&MASK if taken else history


def nonzero_violations(cycles,rounds=16):
    violations=[]
    for alias,(a,b,c,d) in enumerate(cycles):
        history=0
        for cycle,outcome in enumerate([1]*rounds+[0]*rounds+[1]*rounds):
            for edge,(source,target,position,taken) in enumerate(edges(a,b,c,d,outcome)):
                history=advance_scalar(history,source,target,position,taken)
                if cycle>=1 and not history:
                    violations.append(dict(alias=alias,cycle=cycle,edge=edge,taken=taken))
    return violations


def steady_indices(a,b,c,d,outcome):
    history=((a>>1)&15)^(((d>>1)&3)<<2)
    created=[]
    for source,target,position,taken in edges(a,b,c,d,outcome):
        created.append(physical_index(target,history))
        history=advance_scalar(history,source,target,position,taken)&15
    return tuple(created)


def plan(bank,entry_set):
    if type(bank) is not int or not 0<=bank<4:raise ValueError('physical bank must be0..3')
    if type(entry_set) is not int or not 0<=entry_set<64:raise ValueError('physical set must be0..63')
    wanted=entry_set*4+bank
    d=0x40013080+((wanted&240)>>1)
    for salt in range(8):
        for a_extra in range(0,128,8):
            a=0x40011080+a_extra
            b=a+16
            for c_extra in range(0,128,32):
                c=0x400128a0+salt*0x800+c_extra+(wanted&15)*2
                cycles=tuple((a+alias*256,b+alias*256,c+alias*256,d+alias*256) for alias in range(5))
                if len({pc for cycle in cycles for pc in cycle})!=20:continue
                if any(fall_through(x)['target']!=y for x,y,_,_ in cycles):continue
                peers=set()
                for outcome in (0,1):
                    created=steady_indices(a,b,c,d,outcome)
                    assert created[2]==wanted
                    peers.update(created[index] for index in (0,1,3))
                if wanted in peers or max(capacity(cycles).values())>2:continue
                if nonzero_violations(cycles):continue
                return dict(bank=bank,entry_set=entry_set,physical_index=wanted,cycles=cycles,
                    conditional_position=6,return_positions=(7,7,7),branch_programs=programs(cycles),
                    low4_index_source_history=(c>>1)&15,index_request_pc=d,
                    peer_physical_indices=sorted(peers),address_region_salt=salt,
                    maximum_MainBTB_residents_per_group=max(capacity(cycles).values()),
                    PC_unit='halfword Pc.addr; byte address=addr<<1',
                    negative_path='final taken=0; no later fallback in A',
                    actual_A_metadata_index_source='two earlier S1 beats: C requests D using history before C',
                    newly_created_A_to_B_token_is_NOT_current_A_metadata=True,
                    full_PHR_and_UTAGE_tags_NOT_assumed_equal=True,
                    actual_provider_way_and_all256_DUT_scope_NOT_proven=True,no_DUT_or_raw_created=True)
    raise AssertionError(('no capacity-safe finalNT four-node cycle',bank,entry_set))


def scalar_proof(intent,rounds=16):
    if type(rounds) is not int or rounds<14:raise ValueError('at least14 full-history flush rounds required')
    full_checks=target_checks=0
    for a,b,c,d in intent['cycles']:
        history=0
        created=[]
        phase_histories=[]
        cycle=0
        for outcome in (1,0,1):
            for _ in range(rounds):
                for source,target,position,taken in edges(a,b,c,d,outcome):
                    if cycle>=1:
                        actual=created[-2]
                        if source==a:
                            assert actual['index']==intent['physical_index']
                            assert actual['pc']==d and actual['low4']==intent['low4_index_source_history']
                            target_checks+=1
                        else:assert actual['index']!=intent['physical_index']
                    created.append(dict(pc=target,index=physical_index(target,history&63),low4=history&15))
                    before=history
                    history=advance_scalar(history,source,target,position,taken)
                    if not taken:assert history==before
                    if cycle>=1:assert history!=0
                    full_checks+=1
                cycle+=1
            phase_histories.append(history)
        assert phase_histories[0]!=phase_histories[1]
        assert phase_histories[0]==phase_histories[2]
    return dict(scalar_full52_checks=full_checks,target_index_checks=target_checks,
        actual_two_beat_metadata_index_checked=True,aliases=5,phases=3,
        full_history_differs=True,no_DUT_or_raw_created=True)


def joint_reference(intent,idle_cycles=0):
    if type(idle_cycles) is not int or not 0<=idle_cycles<=8:raise ValueError('idle_cycles must be integer0..8')
    full_checks=index_checks=nt_holds=target_checks=0
    for a,b,c,d in intent['cycles']:
        model,index,history=BpuPhrReference(),IndexReference(),0
        index.advance(reset=1,enable=1,fire0=0,fire1=0,fire2=0,
            s2_override=0,s3_override=0,redirect=0,pc=0,folded6=0,tick=0)
        tick=0
        created=[]
        for cycle,outcome in enumerate([1]*16+[0]*16+[1]*16):
            for source,target,position,taken in edges(a,b,c,d,outcome):
                assert model.state['fold1']==folds(history)
                if len(created)>=2:
                    expected=created[-2]
                    index.check(dict(valid=1,bankMask=1<<expected['bank'],setIdx=expected['entry_set']),1)
                    assert index.s2['pc']==expected['pc'] and index.s2['mode']=='normal'
                    index_checks+=1
                if cycle>=1 and source==a:
                    assert index.s2['pc']==d
                    assert (index.s2['entry_set']*4+index.s2['bank'])==intent['physical_index']
                    assert index.s2['folded6']&15==intent['low4_index_source_history']
                    target_checks+=1
                independent_index=physical_index(target,history&63)
                created.append(dict(pc=target,bank=independent_index&3,entry_set=independent_index>>2))
                tick+=1
                index.advance(reset=0,enable=1,fire0=1,fire1=1,fire2=1,
                    s2_override=0,s3_override=0,redirect=0,pc=target,
                    folded6=model.state['fold1'][2],tick=tick)
                inputs=boundary(model,source,target)
                inputs['s1']['prediction'].update(position=position,taken=taken)
                old_pointer=dict(model.state['pointer'])
                old_history=history
                model.advance(inputs,reset=0)
                history=advance_scalar(history,source,target,position,taken)
                assert model.logical()==history
                if not taken:
                    assert model.state['pointer']==old_pointer and history==old_history
                    nt_holds+=1
                if cycle>=1:assert history!=0
                full_checks+=1
                for _ in range(idle_cycles):
                    tick+=1
                    index.advance(reset=0,enable=1,fire0=0,fire1=0,fire2=0,
                        s2_override=0,s3_override=0,redirect=0,pc=target,
                        folded6=model.state['fold1'][2],tick=tick)
                    model.advance(boundary(model),reset=0)
                    assert model.logical()==history
                    full_checks+=1
    return dict(full52_reference_checks=full_checks,joint_index_checks=index_checks,
        actual_A_metadata_index_checks=target_checks,final_NT_history_and_pointer_holds=nt_holds,
        idle_cycles=idle_cycles,positive_finalNT_positive_phases=True,no_DUT_or_raw_created=True)
