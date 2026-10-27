"""Hand-derived pending-operation controls and late comparison faults."""
from copy import deepcopy
from itertools import product
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.uras.model.pipeline import advance, empty_state, return_address, selected_output
from bpuverify.bpu.checker.ras.micro import MicroRasChecker
from bpuverify.bpu.case.ras.early import early_program


def inputs(action=0, **values):
    result = dict(fire1=1, fire2=1, fire3=1, redirect=0, main_top=0x700,
        s1=dict(pc=0x800, position=15, action=action),
        s2=dict(valid=0, pc=0x900, position=7, action=0),
        s3=dict(valid=0, pc=0xa00, position=3, action=0))
    result.update(values)
    return result


@pytest.mark.parametrize('action,s2,s3', tuple(product((0,1,2), repeat=3)))
def test_pending_operations_have_hand_derived_stack_effect(action, s2, s3):
    state = dict(empty_state(), s2_push=int(s2==2), s2_pop=int(s2==1),
        s3_push=int(s3==2), s3_pop=int(s3==1), s2_address=0x500,
        s3_address=0x600, usable=1, address=0x300)
    usable, address, _ = selected_output(state, inputs(action))
    if action == 2:
        expected = (1, 0x810)
    elif action == 1:
        expected = ((1,0x600) if s3==2 else (0,0) if s3==1 else (1,0x700)) if s2==2 else (
            (0,0x300) if s2==1 or s3!=2 else (1,0x700))
    else:
        expected = (1,0x500) if s2==2 else ((1,0x700) if s3==2 else (0,0)) if s2==1 else (
            (0,0x300) if s3==1 else (1,0x600) if s3==2 else (1,0x700))
    assert (usable,address) == expected


def test_three_distinct_calls_then_return_cancels_youngest_not_oldest():
    state = empty_state()
    for pc in (0x800,0x900,0xa00):
        state,_ = advance(state, inputs(2, s1=dict(pc=pc, position=15, action=2)))
    assert (state['s2_address'],state['s3_address'],state['address']) == (0xa10,0x910,0xa10)
    state,route = advance(state,inputs(1))
    assert route == 's1-pop/s2-push/s3-push'
    assert (state['usable'],state['address']) == (1,0x910)


@pytest.mark.parametrize('action', (0,1,2))
def test_S3_correction_flushes_younger_pending_operations(action):
    state = dict(empty_state(),s2_push=1,s3_push=1,s3_address=0x600)
    actual,route = advance(state,inputs(2,s3=dict(valid=1,action=action,pc=0xa00,position=3)))
    assert route == 's3-correction'
    assert tuple(actual[k] for k in ('s2_push','s2_pop','s3_push','s3_pop')) == (0,0,0,0)
    assert (actual['usable'],actual['address']) == ((0,0) if action==1 else (1,0xa04) if action==2 else (1,0x700))


def test_S2_call_correction_held_by_backpressure_retains_correct_return_address():
    state = empty_state()
    corrected = inputs(fire1=0,fire2=0,s2=dict(valid=1,action=2,pc=0x900,position=7))
    state,route = advance(state,corrected)
    assert route=='s2-call-correction' and state['s2_push']==1
    assert state['s2_address']==state['address']==0x908
    state,_=advance(state,inputs(fire1=0,fire2=1))
    assert state['s2_push']==0 and state['s3_push']==1 and state['s3_address']==0x908


def test_neutral_S2_correction_keeps_older_S3_push_but_cancels_younger_call():
    state = dict(empty_state(),s3_push=1,s3_address=0x600)
    actual,route = advance(state,inputs(2,s2=dict(valid=1,action=0,pc=0x900,position=7)))
    assert route=='s2-neutral/s3-push'
    assert (actual['usable'],actual['address'],actual['s2_push'],actual['s3_push'])==(1,0x600,0,0)


def test_redirect_flush_and_one_cycle_recovery_bubble_do_not_fabricate_target():
    state = dict(empty_state(),s2_push=1,s3_pop=1,usable=1,address=0x123)
    state,route = advance(state,inputs(2,redirect=1))
    assert route=='redirect' and state['address']==0x123 and state['usable']==0
    assert not any(state[k] for k in ('s2_push','s2_pop','s3_push','s3_pop'))
    state,_=advance(state,inputs())
    assert (state['usable'],state['address'])==(0,0)
    state,_=advance(state,inputs())
    assert (state['usable'],state['address'])==(1,0x700)


def test_no_fire_holds_visible_output_but_reset_overrides_all_state():
    state = dict(empty_state(),usable=1,address=0x123)
    actual,route=advance(state,inputs(2,fire1=0,fire2=0,fire3=0))
    assert actual==state and route=='hold'
    assert advance(state,inputs(2,redirect=1),reset=1)==(empty_state(),'reset')


@pytest.mark.parametrize('pc,position,wanted', ((0x807,15,0x810),(0x802,7,0x808),((1<<50)-1,15,8)))
def test_halfword_alignment_and_guard_width(pc,position,wanted):
    assert return_address(dict(pc=pc,position=position))==wanted


def replay_checker():
    checker=MicroRasChecker()
    def step(tick,state,reset=0):
        return dict(reset=reset,state=deepcopy(state),inputs=inputs(),
            output={key:state[key] for key in ('usable','address')})
    checker.observe(step(41,empty_state(),reset=1),41)
    checker.observe(step(43,empty_state()),43)
    return checker, step(45,checker.expected)


@pytest.mark.parametrize('field', tuple(empty_state()))
def test_every_late_register_fault_is_an_ordinary_contextual_mismatch(field):
    checker,row=replay_checker()
    row['state'][field]^=1
    with pytest.raises(ScoreboardMismatch,match='all MicroRAS registers'):
        checker.observe(row,45)


@pytest.mark.parametrize('field',('usable','address'))
def test_output_fault_cannot_be_hidden_by_matching_internal_register(field):
    checker,row=replay_checker();row['output'][field]^=1
    with pytest.raises(ScoreboardMismatch,match='complete module output'):
        checker.observe(row,45)


def test_passive_callback_exception_is_latched_and_raised_in_foreground():
    checker,row=replay_checker();row['state']['s3_address']^=1
    checker.capture(SimpleNamespace(value=row,event=SimpleNamespace(tick=45)))
    with pytest.raises(ScoreboardMismatch,match='all MicroRAS registers'):
        checker.raise_failure()


def test_lossy_observation_and_nonreset_origin_are_rejected():
    checker,row=replay_checker()
    with pytest.raises(ScoreboardMismatch,match='lossless cycle observation'):checker.observe(row,47)
    with pytest.raises(ScoreboardMismatch,match='genuine reset'):MicroRasChecker().observe(row,45)


def test_pending_operations_cannot_be_reported_drained():
    checker,_=replay_checker();checker.expected['s2_pop']=1
    with pytest.raises(ScoreboardMismatch,match='pending operations drained'):checker.finish()


@pytest.mark.parametrize('gap',(0,1))
def test_input_geometry_is_three_calls_and_three_returns_not_a_physical_sweep(gap):
    rows=early_program(gap)
    assert [row['action'] for row in rows]==[2,2,2]+([0] if gap else [])+[1,1,1]
    assert all(a['target']==b['pc'] for a,b in zip(rows,rows[1:]))
    calls=[row['pc'] for row in rows if row['action']==2]
    assert [row['target'] for row in rows if row['action']==1]==[pc+16 for pc in reversed(calls)]
    assert len({row['pc'] for row in rows})==len(rows)


@pytest.mark.parametrize('gap',(-1,2,True,'0'))
def test_bad_geometry_fails_before_DUT_access(gap):
    with pytest.raises(ValueError):early_program(gap)

