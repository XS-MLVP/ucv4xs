"""Independent event programs plus synthetic faults; no DUT coverage credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard
from bpuverify.bpu.checker.main_rewrite import MainRewriteChecks
from bpuverify.bpu.coverage.main_rewrite import MainRewriteCoverage
from bpuverify.bpu.model.main_rewrite import PC,POSITION,TARGETS,effect,direction
from bpuverify.bpu.model.main_service import PCS,STREAM_PC,entry_plan,counter_payload,entry_payload
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.pipeline import Redirect,Outcome
from bpuverify.bpu.model.selection import Kind,middle_repair,final_repair
from bpuverify.mbtb.model.semantic import Entry,Target
from tests.bpu.scoreboard.test_main_service import establish,feedback,quiet,revisit,streaming_query,raw_counter


def repairs(receipt):
    token=receipt.token;r2=middle_repair(token.early,token.middle)
    r3=final_repair(token.early,token.middle,token.middle,corrected_middle=r2)
    return tuple((receipt.prediction_tick+delay,stage) for delay,stage,active in ((2,2,r2),(4,3,r3)) if active)


def outcome(target):return Outcome(POSITION,target,Kind.INDIRECT,True,mispredict=True)


def program():
    model,event,anchor,_,originals=establish()
    sources=tuple(revisit(model,event,anchor,PC) for _ in range(2))
    idle=quiet(model,event);model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.main.entry_commits,model.sources.main.counter_commits
    requests=tuple(feedback(source,(outcome(target),)) for source,target in zip(sources,TARGETS[:2],strict=True))
    for request in requests:model.advance(replace(event,feedback=request))
    for _ in range(4):model.advance(event)
    return model,event,anchor,sources,originals,requests,baseline


@pytest.mark.parametrize('delta,encoding',((0,0),(1,1),(-1,2)))
def test_signed_logical_region_motion_projects_to_targetcarry_enum_not_twos_complement(delta,encoding):
    target=PC+delta*(1<<20)+0x600
    entry=Entry(1,POSITION,3,0,Target.encode(PC,target))
    assert entry.target.region_delta==delta and entry.target.at(PC)==target
    assert entry_payload(0,entry)['carry']==encoding


def test_distinct_actual_originals_supersede_one_complete_record_not_its_direction_fifo_or_sibling():
    model,event,anchor,sources,originals,requests,baseline=program();main=model.sources.main
    assert sources[0].history is not sources[1].history
    frozen=tuple(source_entries(s.lookup) for s in (*sources,*originals))
    assert entry_plan(main,0,0)==((effect(TARGETS[1]),),())
    assert tuple(counter_payload(p) for p in main.directions[0,0].pending)==(direction(),direction())
    assert (main.entry_commits,main.counter_commits)==baseline
    assert (main.entries[0,0].overflows,main.directions[0,0].drops)==(0,0)
    old=streaming_query(model,event,anchor,PC)
    assert old.middle.branch.position==5 and source_entries(old.lookup)[0][0].kind==1
    quiet(model,event)
    current=revisit(model,event,anchor,PC)
    assert (current.middle.branch.position,current.middle.branch.target)==(POSITION,TARGETS[1])
    assert (main.entry_commits,main.counter_commits)==(baseline[0]+1,baseline[1]+2)
    assert entry_plan(main,0,0)==((),())
    resolve=feedback(current,(outcome(TARGETS[2]),))
    model.advance(replace(quiet(model,event),feedback=resolve));quiet(model,event)
    latest=revisit(model,event,anchor,PC)
    assert latest.middle.branch.target==TARGETS[2]
    assert source_entries(latest.lookup)[0][1]==source_entries(originals[0].lookup)[0][1]
    assert (main.entry_commits,main.counter_commits)==(baseline[0]+2,baseline[1]+3)
    assert source_entries(revisit(model,event,anchor,PCS[1]).lookup)==source_entries(originals[1].lookup)
    assert tuple(source_entries(s.lookup) for s in (*sources,*originals))==frozen


def fixture():
    model,event,anchor,tokens,original_tokens,requests,baseline=program()
    receipts=tuple(NS(token=t,prediction_tick=100+i*10,meta_tick=104+i*10) for i,t in enumerate(tokens))
    originals=tuple(NS(token=t,prediction_tick=70+i*10,meta_tick=74+i*10) for i,t in enumerate(original_tokens))
    retired=[]
    def source(receipt):
        token=receipt.token
        if model.published.get(token.sequence) is not token:raise AssertionError('synthetic receipt lost its exact owned token')
        return token
    pipeline=NS(model=model,last_tick=220,board=Scoreboard('main-complete-version-contract'),raise_failure=lambda:None,
        source_token=source,corrections_for_source=repairs,retire_source=retired.append)
    checks=MainRewriteChecks(pipeline,MainRewriteCoverage());checks.arm(receipts,originals)
    loop=streaming_query(model,event,anchor,STREAM_PC);checks.start(NS(token=loop))
    row=dict(reset=0,initialized=1,read=dict(valid=1,row=24),training=dict(valid=0,ready=1),
        prediction=dict(valid=1,ready=1,pc=STREAM_PC),incoming=tuple(dict(valid=0,bits={}) for _ in range(2)),
        direction=dict(valid=0,ready=1,bits={}),
        writes=(dict(valid=1,ready=0,bits=effect(TARGETS[1])),dict(valid=0,ready=0,bits={}),
            dict(valid=1,ready=0,bits=raw_counter(direction()))),dirty=((1,0),(0,0)),
        queue=dict(enqueue=0,dequeue=0,full=1))
    events=tuple((200+i*2,r) for i,r in enumerate(requests))
    return checks,receipts,events,row,(model,event,anchor),retired


def sample(checks,row,tick):
    checks.pipeline.last_tick=tick;checks.capture_state(NS(tick=tick),deepcopy(row));checks.raise_failure()


def armed():
    checks,receipts,events,row,program,retired=fixture()
    for tick in (200,202,204,220):
        r=deepcopy(row);index=(tick-200)//2
        if index<2:
            r['training']['valid']=1;r['direction']=dict(valid=1,ready=1,bits=raw_counter(direction()))
        index=(tick-202)//2
        if index in (0,1):r['incoming']=(dict(valid=1,bits=effect(TARGETS[index])),dict(valid=0,bits={}))
        sample(checks,r,tick)
    checks.accepted_burst(events);checks.pending()
    return checks,receipts,events,row,program,retired


def test_checked_credit_waits_for_all_actual_services_fresh_consumers_and_clean_reactivation():
    checks,sources,_,row,(model,event,anchor),retired=armed()
    assert checks.coverage.groups['checked'].coverage==0
    old=NS(token=streaming_query(model,event,anchor,PC),prediction_tick=250,meta_tick=254)
    checks.consumed_old(old);checks.release();quiet(model,event)
    for port,tick,value in ((0,280,effect(TARGETS[1])),(2,280,raw_counter(direction())),(2,282,raw_counter(direction()))):
        checks.write_accepted(port,NS(accepted_tick=tick,value=value))
    current=NS(token=revisit(model,event,anchor,PC),prediction_tick=300,meta_tick=304)
    checks.consumed_new(current);checks.reactivate(current)
    assert checks.coverage.groups['checked'].coverage==0
    for tick in (320,322):
        r=deepcopy(row)
        if tick==320:r['direction']=dict(valid=1,ready=1,bits=raw_counter(direction()))
        else:r['incoming']=(dict(valid=1,bits=effect(TARGETS[2])),dict(valid=0,bits={}))
        sample(checks,r,tick)
    model.advance(replace(quiet(model,event),feedback=feedback(current.token,(outcome(TARGETS[2]),))));quiet(model,event)
    for port,value in ((0,effect(TARGETS[2])),(2,raw_counter(direction()))):
        checks.write_accepted(port,NS(accepted_tick=330,value=value))
    checks.consumed_latest(NS(token=revisit(model,event,anchor,PC),prediction_tick=350,meta_tick=354))
    r=deepcopy(row);r['writes']=tuple(dict(valid=0,ready=1,bits={}) for _ in range(3));sample(checks,r,360)
    sibling=NS(token=revisit(model,event,anchor,PCS[1]),prediction_tick=370,meta_tick=374)
    checks.finish(sibling)
    assert checks.closed and all(g.coverage==100 for g in checks.coverage.groups.values()) and len(set(retired))==8


@pytest.mark.parametrize('fault',('intermediate-target','stale-type','wrong-carry','extra-entry','lost-direction','merged-direction','sibling-write','read-gap'))
def test_bad_pending_actual_cannot_repair_the_owned_latest_version_or_receive_checked_credit(fault):
    checks,_,_,row,_,_=armed();r=deepcopy(row)
    if fault=='intermediate-target':r['writes'][0]['bits']=effect(TARGETS[0])
    elif fault=='stale-type':r['writes'][0]['bits']['kind']=1
    elif fault=='wrong-carry':r['writes'][0]['bits']['carry']=0
    elif fault=='extra-entry':r['dirty']=((1,1),(0,0))
    elif fault=='lost-direction':r['writes'][2]['valid']=0
    elif fault=='merged-direction':r['queue']['full']=0;r['queue']['enqueue']=1
    elif fault=='sibling-write':r['writes'][1]['valid']=1
    else:r['read']['valid']=0
    before=deepcopy(checks.pipeline.model.sources.main.state())
    with pytest.raises(AssertionError) as first:sample(checks,r,222)
    with pytest.raises(AssertionError) as second:checks.raise_failure()
    assert first.value is second.value and checks.pipeline.model.sources.main.state()==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('old-version','partial-kind','partial-carry','sibling-port','premature-new-version','before-release','duplicate'))
def test_actual_service_requires_the_complete_latest_declared_version_exactly_once(fault):
    checks,_,_,row,_,_=armed()
    if fault!='before-release':checks.old=object();checks.release()
    port=1 if fault=='sibling-port' else 0;bits=effect(TARGETS[1])
    if fault=='old-version':bits=effect(TARGETS[0])
    elif fault=='partial-kind':bits['kind']=1
    elif fault=='partial-carry':bits['carry']=0
    elif fault=='premature-new-version':bits=effect(TARGETS[2])
    elif fault=='duplicate':checks.write_accepted(0,NS(accepted_tick=230,value=bits))
    before=len(checks.written[port])
    with pytest.raises(AssertionError):checks.write_accepted(port,NS(accepted_tick=232,value=bits))
    assert len(checks.written[port])==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('foreign-origin','wrong-position','wrong-type','not-taken','not-correction','not-adjacent'))
def test_full_original_input_association_is_not_optional(fault):
    checks,_,events,_,_,_=fixture();events=list(events);tick,r=events[1];branch=r.branches[0]
    if fault=='foreign-origin':r=replace(r,origin=replace(r.origin))
    elif fault=='not-adjacent':tick+=2
    else:
        change={'wrong-position':dict(position=5),'wrong-type':dict(kind=Kind.DIRECT),
            'not-taken':dict(taken=False),'not-correction':dict(mispredict=False)}[fault]
        r=replace(r,branches=(replace(branch,**change),))
    checks.inputs=[200,tick];events[1]=(tick,r)
    with pytest.raises(AssertionError):checks.accepted_burst(tuple(events))
    assert not checks.accepted and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-old','no-services','no-clean-source','no-endpoints','forged-source','missing-public-repair'))
def test_no_vacuous_or_unowned_endpoint_can_close_the_contract(fault):
    checks,receipts,_,_,(model,event,anchor),_=armed()
    with pytest.raises(AssertionError):
        if fault=='no-old':checks.release()
        elif fault=='no-services':checks.consumed_new(receipts[0])
        elif fault=='no-clean-source':checks.reactivate(receipts[0])
        elif fault=='no-endpoints':checks.finish(receipts[0])
        elif fault=='forged-source':checks.inspect(NS(token=replace(receipts[0].token)))
        else:
            checks.pipeline.corrections_for_source=lambda _:((999,2),)
            checks.inspect(receipts[0])
    assert checks.coverage.groups['checked'].coverage==0
