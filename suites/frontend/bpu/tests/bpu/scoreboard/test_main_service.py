"""Public-event programs establish real owners; synthetic tests earn no DUT credit."""
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard

from bpuverify.bpu.model.main_sources import BranchTargetSources,source_entries
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.main_service import PCS,POSITION,PEER_POSITION,STREAM_PC,old_target,new_target,peer_target,entry_plan,target_effect
from tests.bpu.scoreboard.test_semantic_pipeline import boot
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit
from bpuverify.bpu.checker.main_service import MainServiceChecks
from bpuverify.bpu.coverage.main_service import MainServiceCoverage
from bpuverify.bpu.model.main_service import observed_counter,counter_payload

ENABLED=(True,False,True,False,False,False,False)


def prepared():
    model,event=boot(BranchTargetSources());event=replace(event,enabled=ENABLED)
    for _ in range(10):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.lookup is not None:return model,event,cycle.metadata
    raise AssertionError('owned Main source missing')


def feedback(token,branches):return Resolution(token.history,token.pc,tuple(branches),origin=token)


def resolve(model,event,source,*branches):
    idle=quiet(model,event);request=feedback(source,branches)
    model.advance(replace(idle,feedback=request));quiet(model,event)


def pair(pc,target,*,wrong=False):
    return (Outcome(PEER_POSITION,peer_target(pc),Kind.CONDITIONAL,False),
        Outcome(POSITION,target,Kind.INDIRECT,True,mispredict=wrong))


def establish():
    model,event,anchor=prepared()
    stream=revisit(model,event,anchor,STREAM_PC)
    resolve(model,event,stream,Outcome(POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True))
    cold=[]
    for pc in PCS:
        source=revisit(model,event,anchor,pc);cold.append(source)
        resolve(model,event,source,Outcome(POSITION,old_target(pc),Kind.INDIRECT,True,mispredict=True))
        source=revisit(model,event,anchor,pc)
        resolve(model,event,source,Outcome(PEER_POSITION,peer_target(pc),Kind.CONDITIONAL,True,mispredict=True))
        source=revisit(model,event,anchor,pc)
        resolve(model,event,source,Outcome(PEER_POSITION,peer_target(pc),Kind.CONDITIONAL,False,mispredict=True),
            Outcome(POSITION,old_target(pc),Kind.INDIRECT,True))
        source=revisit(model,event,anchor,pc);resolve(model,event,source,*pair(pc,old_target(pc)))
    originals=tuple(revisit(model,event,anchor,pc) for pc in PCS)
    return model,event,anchor,tuple(cold),originals


def streaming_query(model,event,anchor,pc):
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,pc,True)))
    for _ in range(10):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==pc:return cycle.metadata
    raise AssertionError('continuous Main query missing')


def pending_program(*,stale=False):
    model,event,anchor,cold,originals=establish();idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.main.entry_commits,model.sources.main.counter_commits
    sources=cold[-1:] if stale else originals
    pcs=PCS[-1:] if stale else PCS
    requests=tuple(feedback(source,(Outcome(POSITION,new_target(pc),Kind.INDIRECT,True,mispredict=True),)
        if stale else pair(pc,new_target(pc),wrong=True)) for pc,source in zip(pcs,sources,strict=True))
    for request in requests:model.advance(replace(event,feedback=request))
    for _ in range(4):model.advance(event)
    return model,event,anchor,sources,originals,requests,baseline


@pytest.mark.parametrize('stale',(False,True))
def test_two_real_context_targets_and_negative_neighbours_survive_read_pressure_until_service(stale):
    model,event,anchor,sources,originals,requests,baseline=pending_program(stale=stale);main=model.sources.main
    pcs=PCS[-1:] if stale else PCS
    plan=entry_plan(main,0,0)
    assert plan==((),(),(),tuple(target_effect(pc) for pc in pcs))
    assert (main.entry_commits,main.counter_commits)==baseline
    assert main.entries[0,0].overflows==main.directions[0,0].drops==0
    assert len(main.directions[0,0].pending)==len(pcs)
    frozen=tuple(source_entries(token.lookup) for token in sources)
    for pc in pcs:
        old=streaming_query(model,event,anchor,pc)
        assert old.middle.branch.target==old_target(pc)
        assert tuple(e.counter for row in source_entries(old.lookup) for e in row if e.hit)==(0,2)
        assert entry_plan(main,0,0)==plan and (main.entry_commits,main.counter_commits)==baseline
    quiet(model,event)
    assert (main.entry_commits,main.counter_commits)==(baseline[0]+len(pcs),baseline[1]+len(pcs))
    for pc in pcs:
        new=revisit(model,event,anchor,pc)
        assert new.middle.branch.target==new_target(pc)
        assert tuple(e.counter for row in source_entries(new.lookup) for e in row if e.hit)==(0,2)
    assert tuple(source_entries(token.lookup) for token in sources)==frozen
    if stale:
        assert all(not any(e.hit for row in source_entries(t.lookup) for e in row) for t in sources)
    assert entry_plan(main,0,0)==((),(),(),())


def raw_counter(expected):
    return dict(row=expected['row'],mask=expected['mask'],counters=tuple(expected['values'].get(str(w),0) for w in range(4)))


def fixture(*,stale=False,reclassify=False):
    model,event,anchor,cold,current=establish();tokens=cold[-1:] if stale else current
    receipts=tuple(NS(token=t,prediction_tick=100+i*10,meta_tick=104+i*10) for i,t in enumerate(tokens))
    originals=tuple(NS(token=t,prediction_tick=70+i*10,meta_tick=74+i*10) for i,t in enumerate(current))
    retired=[]
    pipeline=NS(model=model,board=Scoreboard('main-service-contract'),last_tick=220,raise_failure=lambda:None,
        source_token=lambda r:r.token,retire_source=retired.append,last_resolution_controls=(200+(len(tokens)-1)*2,ENABLED),
        corrections_for_source=lambda r:((r.prediction_tick+4,3),) if r.prediction_tick>=350 else ())
    if reclassify:
        from bpuverify.bpu.model.selection import middle_repair,final_repair
        def repairs(r):
            t=r.token;r2=middle_repair(t.early,t.middle)
            r3=final_repair(t.early,t.middle,t.middle,corrected_middle=r2)
            return tuple((r.prediction_tick+d,s) for d,s,active in ((2,2,r2),(4,3,r3)) if active)
        pipeline.corrections_for_source=repairs
    checks=MainServiceChecks(pipeline,MainServiceCoverage(stale=stale,reclassify=reclassify),stale=stale,reclassify=reclassify);checks.arm(receipts,originals)
    idle=quiet(model,event);model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    loop=streaming_query(model,event,anchor,STREAM_PC);checks.start(NS(token=loop))
    requests=tuple(feedback(t,(Outcome(PEER_POSITION,new_target(pc),Kind.INDIRECT,True,mispredict=True),) if reclassify else (
        (Outcome(POSITION,new_target(pc),Kind.INDIRECT,True,mispredict=True),)
        if stale else pair(pc,new_target(pc),wrong=True))) for pc,t in zip(checks.pcs,tokens,strict=True))
    for r in requests:model.advance(replace(event,feedback=r))
    for _ in range(4):model.advance(event)
    accepted=tuple((200+i*2,r) for i,r in enumerate(requests))
    row=dict(reset=0,initialized=1,read=dict(valid=1,row=24),training=dict(valid=0,ready=1),
        prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        incoming=tuple(dict(valid=0,bits={}) for _ in range(4)),
        direction=dict(valid=0,ready=1,bits={}),
        writes=tuple(dict(valid=int(way==checks.owner),ready=0,
            bits=deepcopy(checks.plan[checks.owner][0]) if way==checks.owner else {}) for way in range(4))+
            (dict(valid=1,ready=0,bits=raw_counter(checks.counter_plan[0])),),
        dirty=tuple(tuple(int(w==checks.owner and rank<len(tokens)) for rank in range(4)) for w in range(4)),queue=dict(enqueue=len(tokens),dequeue=0,full=0))
    return checks,receipts,accepted,row,(model,event,anchor),retired


def armed(*,stale=False,reclassify=False):
    checks,sources,accepted,row,program,retired=fixture(stale=stale,reclassify=reclassify)
    for tick in (200,202,204,220):
        r=deepcopy(row);index=(tick-200)//2
        if index<len(accepted):
            r['training']['valid']=1
            r['direction']=dict(valid=1,ready=1,bits=raw_counter(checks.counter_plan[index]))
        index=(tick-202)//2
        if index in range(len(checks.plan[checks.owner])):
            r['incoming'][1 if stale else checks.owner].update(valid=1,bits=deepcopy(checks.plan[checks.owner][index]))
        checks.capture_state(NS(tick=tick),r)
    checks.accepted_burst(accepted)
    return checks,checks.last[1],program,retired


def consumers(checks,program,*,committed):
    model,event,anchor=program
    if committed:quiet(model,event)
    for i,pc in enumerate(checks.pcs):
        token=revisit(model,event,anchor,pc) if committed else streaming_query(model,event,anchor,pc)
        checks.consumed(NS(token=token,prediction_tick=(350 if committed else 230)+i*10,
            meta_tick=(354 if committed else 234)+i*10),i,committed=committed)


@pytest.mark.parametrize('stale',(False,True))
def test_complete_semantic_closure_requires_both_resource_services_all_consumers_and_immutable_neighbours(stale):
    checks,row,program,retired=armed(stale=stale);checks.pending()
    assert checks.coverage.groups['checked'].coverage==0
    consumers(checks,program,committed=False);checks.release()
    for port in (3,4):
        effects=checks.counter_plan if port==4 else checks.plan[3]
        for i,effect in enumerate(effects):checks.write_accepted(port,NS(accepted_tick=280+i*2,
            value=raw_counter(effect) if port==4 else deepcopy(effect)))
    empty=deepcopy(row)
    for p in empty['writes']:p.update(valid=0,ready=1)
    checks.capture_state(NS(tick=300),empty);consumers(checks,program,committed=True)
    assert not retired and checks.coverage.groups['checked'].coverage==0
    checks.finish();assert checks.closed and len(retired)==(5 if stale else 8)
    assert all(g.coverage==100 for g in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('reset','uninitialized','read-gap','entry-ready','direction-ready','prediction-valid','prediction-ready','prediction-bank'))
def test_actual_read_pressure_and_parallel_acceptance_are_checked_not_assumed(fault):
    checks,_,_,row,_,_=fixture();actual=deepcopy(row);actual['training']['valid']=1
    if fault=='reset':actual['reset']=1
    elif fault=='uninitialized':actual['initialized']=0
    elif fault=='read-gap':actual['read']['valid']=0
    elif fault=='entry-ready':actual['writes'][3]['ready']=1
    elif fault=='direction-ready':actual['writes'][4]['ready']=1
    elif fault=='prediction-bank':actual['prediction']['pc']+=32
    else:actual['prediction'][fault.split('-')[1]]=0
    before=deepcopy(checks.pipeline.model.sources.main.state());checks.capture_state(NS(tick=200),actual)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.pipeline.model.sources.main.state()==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('row','tag','position','kind','action','carry','offset'))
def test_every_offered_and_serviced_entry_field_is_compared_without_golden_repair(field):
    checks,_,_,row,_,_=fixture();r=deepcopy(row);wrong=deepcopy(checks.plan[3][0]);wrong[field]^=1
    r['incoming'][3].update(valid=1,bits=wrong);checks.capture_state(NS(tick=206),r)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert not checks.proposals and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('wrong-owner','wrong-counter','wrong-row','drop','unmasked-neighbour'))
def test_stale_direction_reset_must_follow_logical_owner_and_preserve_negative_peer(fault):
    checks,_,_,row,_,_=fixture(stale=True);r=deepcopy(row);raw=raw_counter(checks.counter_plan[0])
    if fault=='wrong-owner':raw.update(mask=1,counters=(2,0))
    elif fault=='wrong-counter':raw['counters']=(0,0,0,1)
    elif fault=='wrong-row':raw['row']^=1
    elif fault=='unmasked-neighbour':raw['mask']=3;raw['counters']=(2,2)
    r['direction']=dict(valid=1,ready=int(fault!='drop'),bits=raw);checks.capture_state(NS(tick=204),r)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert not checks.counter_proposals and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-entry','missing-direction','dirty','full','front-target','counter-front','early-effect',
    'early-direction-effect','late-direction-effect','late-entry-effect','entry-gap','early-service','wrong-service','missing-old','missing-new'))
def test_missing_obligations_or_wrong_temporal_visibility_never_receive_checked_credit(fault):
    checks,row,program,_=armed()
    with pytest.raises(AssertionError):
        if fault=='missing-entry':checks.proposals.pop();checks.pending()
        elif fault=='missing-direction':checks.counter_proposals.pop();checks.pending()
        elif fault=='dirty':row['dirty']=((0,0),(1,0));checks.pending()
        elif fault=='full':row['queue']['full']=1;checks.pending()
        elif fault=='front-target':row['writes'][3]['bits']['offset']^=1;checks.pending()
        elif fault=='counter-front':row['writes'][4]['bits']['counters']=(2,0);checks.pending()
        elif fault=='early-effect':checks.proposals[0]=(198,*checks.proposals[0][1:]);checks.pending()
        elif fault in ('early-direction-effect','late-direction-effect'):
            delta=-2 if fault.startswith('early') else 2
            checks.counter_proposals=[(tick+delta,p) for tick,p in checks.counter_proposals];checks.pending()
        elif fault=='late-entry-effect':checks.proposals=[(tick+2,way,p) for tick,way,p in checks.proposals];checks.pending()
        elif fault=='entry-gap':
            checks,_,_,r,_,_=fixture();r['incoming'][3].update(valid=1,bits=checks.plan[3][0]);checks.capture_state(NS(tick=206),r)
            r['incoming'][3]['bits']=checks.plan[3][1];checks.capture_state(NS(tick=210),r);checks.raise_failure()
        elif fault=='early-service':checks.write_accepted(3,NS(accepted_tick=218,value=checks.plan[3][0]))
        elif fault=='wrong-service':
            checks.pending();consumers(checks,program,committed=False);checks.release()
            checks.write_accepted(4,NS(accepted_tick=280,value=dict(row=0,mask=1,counters=(2,0))))
        elif fault=='missing-old':checks.pending();checks.release()
        else:checks.pending();checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_counter_mask_projection_does_not_turn_undefined_neighbour_payload_into_learning_permission():
    expected=dict(row=7,mask=2,values={'1':2})
    assert observed_counter(dict(row=7,mask=2,counters=(3,2)))==expected
    assert observed_counter(dict(row=7,mask=2,counters=(0,2)))==expected
    with pytest.raises(KeyError):observed_counter(dict(row=7,mask=2,values=(0,2)))


@pytest.mark.parametrize('fault',('missing-counter-service','missing-entry-service','duplicate-service','wrong-phase','changed-original'))
def test_final_comparison_cannot_close_with_partial_services_wrong_phase_or_rebased_original(fault):
    checks,row,program,_=armed();checks.pending();consumers(checks,program,committed=False);checks.release()
    for port in (3,4):
        if fault==('missing-counter-service' if port==4 else 'missing-entry-service'):continue
        effects=checks.counter_plan if port==4 else checks.plan[3]
        for i,e in enumerate(effects):checks.write_accepted(port,NS(accepted_tick=280+i*2,value=raw_counter(e) if port==4 else deepcopy(e)))
    empty=deepcopy(row)
    for p in empty['writes']:p.update(valid=0,ready=1)
    checks.capture_state(NS(tick=300),empty)
    with pytest.raises(AssertionError):
        if fault=='duplicate-service':checks.write_accepted(3,NS(accepted_tick=286,value=checks.plan[3][0]))
        elif fault=='wrong-phase':
            checks.pipeline.corrections_for_source=lambda r:((r.prediction_tick+2,2),)
            consumers(checks,program,committed=True)
        elif fault=='changed-original':
            consumers(checks,program,committed=True);checks.snapshots=();checks.finish()
        else:consumers(checks,program,committed=True)
    assert checks.coverage.groups['checked'].coverage==0
