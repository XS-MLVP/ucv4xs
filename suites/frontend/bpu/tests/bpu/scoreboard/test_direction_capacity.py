"""Closed-form full-hit obligations; pure tests earn no DUT coverage."""
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace as NS
from pathlib import Path
import ast

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.direction_capacity import DirectionCapacityChecks
from bpuverify.bpu.coverage.direction_capacity import DirectionCapacityCoverage
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path
from bpuverify.bpu.model.tage.service import (
    FULL_RETAINED_RETOUCH,ServiceProgram,STREAM_PC,STREAM_POSITION,learning_inflight,pending_plan)
from tests.bpu.scoreboard.test_direction_service import additional_history,via,counters,streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import establish,resolution
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit


def capacity_program():
    model,event,anchor=establish()
    for path in FULL_RETAINED_RETOUCH.paths[1:]:event=additional_history(model,event,anchor,path)
    sources=tuple(revisit(model,event,anchor,PC) if history==0 else
        via(model,event,anchor,FULL_RETAINED_RETOUCH.paths[history]) for history in FULL_RETAINED_RETOUCH.feedback_order)
    return model,event,anchor,sources


def pending_capacity_program():
    model,event,anchor,sources=capacity_program()
    loop=revisit(model,event,anchor,STREAM_PC)
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=Resolution(loop.history,loop.pc,
        (Outcome(STREAM_POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True),),origin=loop)))
    quiet(model,event)
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.tage.commits
    for source in sources:model.advance(replace(event,feedback=resolution(source,resolved_path())))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('owned full-capacity learning did not mature')
    return model,event,anchor,sources,baseline


def test_four_histories_fill_both_owners_and_retouch_composes_without_losing_any_pending_key():
    model,event,anchor,sources,baseline=pending_capacity_program()
    tage=model.sources.tage
    reads=tuple(model.sources.snapshot(source).read for source in sources)
    assert len({read.context for read in reads})==len({read.rows[3] for read in reads})==4
    assert reads[0]==reads[-1] and all(counters(read)==(2,5) for read in reads)
    assert tage.commits==baseline
    plan=pending_plan(tage,7,PC%4)
    assert tuple(tuple(payload['counter'] for payload in way) for way in plan)==((0,1,1,1),(7,6,6,6))
    assert tage.cache[7,PC%4].overflows==0
    assert all(counters(tage.lookup_snapshot(PC,read.context))==(2,5) for read in reads)
    quiet(model,event)
    assert tage.commits==baseline+8 and pending_plan(tage,7,PC%4)==((),())
    for history,read in enumerate(reads[:4]):
        assert counters(tage.lookup_snapshot(PC,read.context))==FULL_RETAINED_RETOUCH.expected_counters(history)


@pytest.mark.parametrize('paths,order',(((),()),([None],(0,)),((None,)*2,(0,1)),
    ((None,PC+1),(0,1)),((None,[]),(0,1)),((None,True),(0,1)),
    ((None,PC+4,PC+8,PC+12,PC+16),(0,1,2,3,4)),
    ((None,PC+4),[0,1]),((None,PC+4),(0,)),((None,),(-1,)),((None,),(True,)),((None,),(1,))))
def test_service_program_rejects_invalid_or_unexercised_history_contracts(paths,order):
    with pytest.raises(ValueError):ServiceProgram(paths,order)


def fixture():
    model,event,anchor,tokens,_=pending_capacity_program()
    old=[]
    for path in FULL_RETAINED_RETOUCH.paths:
        middle=anchor if path is None else streaming_query(model,event,anchor.history,path,anchor.pc+4)
        old.append(streaming_query(model,event,middle.history,PC,middle.pc+4))
    sources=tuple(NS(token=token,prediction_tick=100+10*index,meta_tick=104+10*index) for index,token in enumerate(tokens))
    events=tuple((200+2*index,resolution(token,resolved_path())) for index,token in enumerate(tokens))
    retired=[]
    pipeline=NS(board=Scoreboard('full-retained-capacity-contract'),model=model,last_tick=220,
        last_resolution_controls=(208,event.enabled),source_token=lambda source:source.token,
        raise_failure=lambda:None,retire_source=retired.append,
        corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionCapacityChecks(pipeline,DirectionCapacityCoverage())
    row=dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        writes=tuple(dict(valid=1,ready=0,bits=way[0]) for way in pending_plan(model.sources.tage,7,0)),
        dirty=((1,)*4,)*2,incoming=tuple(dict(valid=0,bits={}) for _ in range(2)))
    consumers=tuple(NS(token=token,prediction_tick=230+10*index,meta_tick=234+10*index) for index,token in enumerate(old))
    return checks,sources,events,row,consumers,(model,event,anchor),retired


def offer(checks,row,ordinal):
    actual=deepcopy(row)
    actual['incoming']=tuple(dict(valid=1,bits=deepcopy(payload)) for payload in checks.expected_offers[ordinal])
    actual['dirty']=((1,)*min(ordinal,4)+(0,)*max(0,4-ordinal),)*2
    return actual


def armed():
    checks,sources,events,row,old,program,retired=fixture()
    checks.arm(sources);checks.begin_read_window()
    for tick in range(200,218,2):
        active=deepcopy(row) if tick<208 else offer(checks,row,(tick-208)//2)
        active['training']['valid']=int(tick<=208)
        checks.capture_state(NS(tick=tick),active)
    checks.capture_state(NS(tick=220),row)
    checks.accepted_burst(events)
    return checks,row,old,program,retired


def retire_and_query(checks,row,program):
    checks.pipeline.last_tick=300
    checks.release()
    for owner in range(2):
        for ordinal,payload in enumerate(checks.expected_plan[owner]):
            checks.write_accepted(owner,NS(accepted_tick=310+ordinal*2,value=deepcopy(payload)))
    model,event,anchor=program
    quiet(model,event)
    new=tuple(revisit(model,event,anchor,PC) if path is None else via(model,event,anchor,path)
        for path in FULL_RETAINED_RETOUCH.paths)
    actual=deepcopy(row)
    actual['reads'][0]['valid']=0
    for port in actual['writes']:port.update(valid=0,ready=1)
    checks.capture_state(NS(tick=400),actual)
    return tuple(NS(token=token,prediction_tick=350+10*index,meta_tick=354+10*index) for index,token in enumerate(new))


def test_all_four_histories_require_old_consumption_eight_sdk_writes_and_distinct_final_counters():
    checks,row,old,program,retired=armed()
    assert checks.full_event_tick==216 and len(checks.offered)==5
    checks.pending()
    for source in old:checks.old_consumed(source)
    assert checks.coverage.groups['checked'].coverage==50
    new=retire_and_query(checks,row,program)
    for source in new[:3]:checks.new_consumed(source)
    assert not checks.closed and not retired
    assert checks.coverage.groups['checked'].coverage<100
    checks.new_consumed(new[-1]);checks.finish()
    assert len(retired)==9 and all(group.coverage==100 for group in checks.coverage.groups.values())


def test_five_public_acceptances_alone_do_not_credit_fullness_or_a_retained_hit():
    checks,sources,events,row,_,_,_=fixture()
    checks.arm(sources);checks.begin_read_window()
    for tick,_ in events:
        active=deepcopy(row);active['training']['valid']=1
        checks.capture_state(NS(tick=tick),active)
    checks.accepted_burst(events)
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError):checks.pending()
    assert checks.full_event_tick is None


@pytest.mark.parametrize('fault',('row','tag','counter','entry-valid','wrong-order','single-owner',
    'missing-port','not-full','short-dirty-vector','fifth-key','extra-proposal'))
def test_actual_capacity_and_complete_input_identity_are_required_without_reseeding_golden(fault):
    checks,sources,_,row,_,_,_=fixture()
    checks.arm(sources);checks.begin_read_window()
    ordinal=4 if fault in ('not-full','short-dirty-vector','fifth-key','extra-proposal') else 0
    for index in range(ordinal):checks.capture_state(NS(tick=208+index*2),offer(checks,row,index))
    actual=offer(checks,row,ordinal)
    if fault in ('row','tag','counter','entry-valid'):actual['incoming'][1]['bits']['valid' if fault=='entry-valid' else fault]^=1
    elif fault=='wrong-order':actual['incoming']=offer(checks,row,1)['incoming']
    elif fault=='single-owner':actual['incoming'][0]['valid']=0
    elif fault=='missing-port':actual['incoming']=actual['incoming'][:1]
    elif fault=='not-full':actual['dirty']=((1,1,1,0),(1,1,1,1))
    elif fault=='short-dirty-vector':actual['dirty']=((1,1,1),(1,1,1,1))
    elif fault=='fifth-key':actual['incoming'][0]['bits']['row']^=1
    else:checks.capture_state(NS(tick=216),actual)
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=220),actual)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==before
    assert checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


@pytest.mark.parametrize('fault',('overwritten-obligation','missing-version','wrong-counter','missing-full-witness'))
def test_pending_must_keep_every_closed_form_history_result_and_the_full_hit_witness(fault):
    checks,_,_,_,_=armed()
    cache=checks.pipeline.model.sources.tage.cache[7,0]
    if fault=='overwritten-obligation':cache.overflows+=1
    elif fault=='missing-full-witness':checks.full_event_tick=None
    else:
        key,version=next(iter(cache.records.items()))
        if fault=='missing-version':cache.pending.remove(version.sequence)
        else:cache.records[key]=replace(version,write=replace(version.write,entry=replace(version.write.entry,counter=3)))
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-fourth-old','missing-fourth-new','missing-eighth-commit','same-result-every-history'))
def test_no_two_history_shortcut_can_close_a_four_history_capacity_experiment(fault):
    checks,row,old,program,retired=armed();checks.pending()
    for source in old[:3]:checks.old_consumed(source)
    if fault=='missing-fourth-old':
        with pytest.raises(AssertionError):checks.release()
        assert checks.release_tick is None
        return
    checks.old_consumed(old[-1])
    new=retire_and_query(checks,row,program)
    if fault=='missing-eighth-commit':
        checks.written[1].pop()
        with pytest.raises(AssertionError):checks.new_consumed(new[0])
    elif fault=='same-result-every-history':
        checks.values=lambda value:(value.token,((0,3),(0,7)))
        checks.new_consumed(new[0])
        with pytest.raises(AssertionError):checks.new_consumed(new[1])
    else:
        for source in new[:3]:checks.new_consumed(source)
        with pytest.raises(AssertionError):checks.finish()
    assert not checks.closed and not retired and checks.coverage.groups['checked'].coverage<100


def test_capacity_case_expresses_intent_and_does_not_implement_a_private_framework():
    tree=ast.parse(Path('bpuverify/bpu/case/direction_capacity.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
