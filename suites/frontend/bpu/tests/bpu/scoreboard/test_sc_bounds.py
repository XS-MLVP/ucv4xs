"""Boundary intent and bounded retention preserve every comparison and budget."""
from collections import deque
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.bpu.model.sc.bounds import bounds_plan
from bpuverify.bpu.model.sc.used import INITIAL,MINIMUM,MAXIMUM,threshold_update
from bpuverify.bpu.model.sc.model import NAMES,zero_slots,width
from bpuverify.bpu.checker.sc.full import FullScChecker
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.checker.sc.common_state import CommonStateChecker
from bpuverify.bpu.checker.sc.common_routes import RouteChecker
from bpuverify.bpu.env.phr.observation import BpuPhrObservation
from bpuverify.bpu.model.phr.model import BpuPhrReference
from tests.bpu.scoreboard.test_phr_reference import boundary


@pytest.mark.parametrize('way',range(8))
@pytest.mark.parametrize('side',('lower','upper'))
def test_input_geometry_and_minimal_vote_count_derive_from_semantics(way,side):
    plan=bounds_plan(way,side)
    assert plan['pc']&1==0  # One bank, one key per global threshold register.
    assert len(set(plan['positions']))==2
    assert all((p&7)^(p>>3)==way for p in plan['positions'])
    assert plan['near']==(833 if side=='lower' else 8063)
    value=plan['start']+plan['outward']*(1+2*(plan['approach_requests']-1))
    assert value==plan['near'] and plan['requests']==plan['approach_requests']+11
    values=[INITIAL]*8;values[way]=value
    effects=[dict(counter_update=True,threshold_delta=plan['outward'],way=way)]*2
    rejected=threshold_update(values,effects)
    assert rejected['after']==tuple(values) and rejected['rejected_ways']==(way,)
    assert rejected['candidates'][way]==(831 if side=='lower' else 8065)
    assert rejected['after'][way]!=(MINIMUM if side=='lower' else MAXIMUM)


@pytest.mark.parametrize('way,side',((-1,'lower'),(8,'upper'),(True,'lower'),(1,'middle')))
def test_bad_boundary_intent_fails_before_DUT_access(way,side):
    with pytest.raises(ValueError):bounds_plan(way,side)


def sc_reset_row():
    buffers={name:dict(reset=1,slots=zero_slots(width(name)),
        write=dict(valid=0,bits={}),drain=dict(valid=0,ready=0,bits={})) for name in NAMES}
    return dict(buffers=buffers,t0={},training={},used_pipeline=dict(thresholds=[INITIAL]*8,
        t1_fire=0,t2_write_valid=0),replacement=dict.fromkeys(NAMES,0))


def observation(value,tick):
    return SimpleNamespace(value=value,event=SimpleNamespace(tick=tick))


def test_full_SC_ring_retains_every_tick_count_and_late_register_comparison():
    checker=FullScChecker({},capacity=48,record_limit=2)
    for index in range(40):
        checker.observe(observation(sc_reset_row(),2*index+1))
        checker.observe_controls(observation(sc_reset_row(),2*index+2))
    assert len(checker.records)==len(checker.control_records)==2
    summary=checker.summary()
    assert summary['observed_cycles']==summary['observed_preedge_frames']==40
    broken=sc_reset_row();broken['used_pipeline']['thresholds'][2]^=1
    with pytest.raises(ScoreboardMismatch,match='reset_derived_four_thresholds'):
        checker.observe(observation(broken,81))


def test_full_SC_total_observation_budget_is_not_bypassed_by_ring_eviction():
    checker=FullScChecker({},capacity=6,record_limit=2)
    for index in range(6):
        checker.observe(observation(sc_reset_row(),2*index+1))
        checker.observe_controls(observation(sc_reset_row(),2*index+2))
    with pytest.raises(ScoreboardMismatch,match='bounded_observation_capacity'):
        checker.observe(observation(sc_reset_row(),13))


def phr_reset_row():
    parent={f'{stage}_{field}':0 for stage in ('s1','s2','s3') for field in ('valid','pc','taken','target')}
    return dict(reset=1,boundary=boundary(),state=deepcopy(BpuPhrReference().state),pipeline={},parent=parent,
        phr_meta=dict(pointer=dict(flag=0,value=0),low=0),public_meta=dict(valid=0),
        public_redirect=dict(valid=0),public_prediction=dict(valid=0))


def test_PHR_ring_preserves_counts_and_detects_late_state_corruption():
    checker=BpuPhrChecker(scope='bounded',record_limit=2)
    for index in range(40):checker.observe(observation(phr_reset_row(),index*2+1))
    assert len(checker.records)==2 and checker.summary()['cycles']==40
    row=phr_reset_row();row['state']['cells'][31]=1
    with pytest.raises(ScoreboardMismatch):checker.observe(observation(row,81))


def test_common_history_rings_preserve_counts_and_late_fault_checks():
    checker=CommonStateChecker(record_limit=2)
    route=RouteChecker(SimpleNamespace(raise_failure=lambda:None),record_limit=2)
    row=dict(reset=1,state=dict(valid=0,ghr=0,bw=0))
    routing=dict(enable=0,stage_fire=0,fire=0,pc=0,common=dict(valid=0,ghr=0,bw=0),
        reads={name:dict(valid=0,set_index=0,bank_mask=1) for name in ('globalTable_0','bwTable_0')})
    for index in range(40):
        checker.observe(observation(row,index*2+1));route.observe(observation(routing,index*2+1))
    assert len(checker.records)==len(route.records)==2
    assert checker.summary()['cycles']==route.observed_cycles==40
    broken=deepcopy(row);broken['state']['ghr']=1
    with pytest.raises(ScoreboardMismatch):checker.observe(observation(broken,81))
    broken=deepcopy(routing);broken['reads']['bwTable_0']['valid']=1
    with pytest.raises(ScoreboardMismatch):route.observe(observation(broken,81))


@pytest.mark.parametrize('kind',('phr','sc','common','route'))
@pytest.mark.parametrize('limit',(True,0,1,-1,2.5))
def test_invalid_retention_is_rejected(kind,limit):
    with pytest.raises(ValueError):
        if kind=='phr':BpuPhrChecker(scope='bad',record_limit=limit)
        elif kind=='sc':FullScChecker({},record_limit=limit)
        elif kind=='common':CommonStateChecker(record_limit=limit)
        else:RouteChecker(None,record_limit=limit)


@pytest.mark.parametrize('kind',('phr','sc','common','route'))
def test_default_retention_remains_full_for_existing_reset_replays(kind):
    checker= BpuPhrChecker(scope='default') if kind=='phr' else FullScChecker({}) if kind=='sc' else CommonStateChecker() if kind=='common' else RouteChecker(None)
    assert isinstance(checker.records,list)


@pytest.mark.parametrize('bad',('missing','duplicate'))
async def test_redirect_with_bounded_retention_still_requires_one_actual_accept(bad):
    await check_redirect_window(bad)


async def check_redirect_window(fault=None):
    payload=dict(target=123)
    records=deque([dict(tick=39,public_redirect=dict(valid=0)),dict(tick=41,public_redirect=dict(valid=0))],maxlen=2)
    def check(expected,actual,**context):
        assert expected==actual,context
    checker=SimpleNamespace(records=records,last_tick=41,raise_failure=lambda:None,
        plan=lambda _:None,check=check)
    async def send(value):
        records.append(dict(tick=43,public_redirect=dict(valid=int(fault!='missing'),bits=value)))
        records.append(dict(tick=45,public_redirect=dict(valid=int(fault=='duplicate'),bits=value)))
        checker.last_tick=45
        return SimpleNamespace(tick=45)
    agent=SimpleNamespace(redirect_driver=SimpleNamespace(send=send))
    scope=BpuPhrObservation(agent,checker);scope._active=True;agent._phr_observation=scope
    if fault:
        with pytest.raises(AssertionError,match='acceptance'):await scope.redirect(payload)
    else:
        assert await scope.redirect(payload)==43 and len(records)==2


async def test_redirect_association_uses_tick_not_evicted_list_index():
    await check_redirect_window()


@pytest.mark.parametrize('targets',((-1,0),(0,1<<49),(True,0),(0,1.5),(0,),()))
async def test_explicit_provider_pair_targets_validate_before_driving(targets):
    from bpuverify.bpu.case.sc.role_scenarios import prepare_pair
    with pytest.raises(ValueError):await prepare_pair(None,None,0,None,(1,4),(5,4),targets=targets)


@pytest.mark.parametrize('way',range(8))
@pytest.mark.parametrize('outcomes',((0,0),(0,1),(1,)))
def test_distinct_feedback_branches_keep_metadata_and_report_only_first_mispredict(way,outcomes):
    from bpuverify.bpu.case.sc.bounds import bounds_feedback
    plan=bounds_plan(way,'upper');a,b=plan['positions']
    meta=dict(mbtb_entries=[[dict(rawHit=1,position=a),dict(rawHit=1,position=b)],
        [dict(rawHit=0,position=0),dict(rawHit=0,position=0)]],
        sc=dict(scPred=[0,0,0,0],useScPred=[0,0,0,0],tagePred=[1,1,0,0]))
    before=deepcopy(meta)
    tx=bounds_feedback(plan,SimpleNamespace(meta=SimpleNamespace(resolve=meta)),count=len(outcomes),taken=outcomes)
    assert [branch.position for branch in tx.branches]==[a,b][:len(outcomes)]
    assert [branch.mispredict for branch in tx.branches]==([0] if outcomes==(1,) else [1,0])
    assert [branch.taken for branch in tx.branches]==list(outcomes)
    assert meta==before and tx.resolve_meta==before


@pytest.mark.parametrize('count,taken',((0,0),(3,0),(True,0),(1,2),(1,True),
    (2,(1,0)),(2,(1,1)),(2,(0,)),(2,(0,True))))
def test_bad_feedback_shape_fails_before_metadata_or_driver_access(count,taken):
    from bpuverify.bpu.case.sc.bounds import bounds_feedback
    with pytest.raises(ValueError):bounds_feedback(bounds_plan(0,'lower'),None,count=count,taken=taken)


@pytest.mark.parametrize('way',range(8))
@pytest.mark.parametrize('encoded,expected',((0,(1,0,0)),(63,(0,0,0)),(32,(0,1,1))))
def test_fresh_public_SC_oracle_uses_full_signed_reference_not_observed_decision(way,encoded,expected):
    from bpuverify.bpu.model.sc.bounds import public_decisions
    from bpuverify.bpu.model.sc.full import FullScReference
    from bpuverify.bpu.model.sc.training_path import training_indices
    plan=bounds_plan(way,'lower');ref=FullScReference();pc=plan['pc'];common=dict(valid=1,ghr=0,bw=0,imli=0)
    for table,index in training_indices(pc,0,common).items():
        count=32 if table=='biasTable' else 8
        ref.memories[f'{table}_bank0'][index]=[encoded]*count
    actual=public_decisions(ref,pc,plan['positions'],((0,0,5),(1,0,4)),[INITIAL]*8,common)
    assert actual==(expected,expected)

