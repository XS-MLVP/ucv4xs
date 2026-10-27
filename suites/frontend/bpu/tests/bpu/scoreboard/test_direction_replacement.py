"""A full miss may lose one old version, never inherit its counter or lose neighbours."""
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace as NS
from pathlib import Path
import ast
import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.direction_replacement import DirectionReplacementChecks
from bpuverify.bpu.coverage.direction_replacement import DirectionReplacementCoverage
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path
from bpuverify.bpu.model.tage.service import (
    FULL_RETAINED_REPLACEMENT,STREAM_PC,STREAM_POSITION,learning_inflight,pending_plan)
from tests.bpu.scoreboard.test_direction_service import additional_history,via,counters,streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import establish,resolution,values
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit


def replacement_program():
    model,event,anchor=establish()
    for path in FULL_RETAINED_REPLACEMENT.paths[1:]:event=additional_history(model,event,anchor,path)
    source=revisit(model,event,anchor,PC)
    model.advance(replace(quiet(model,event),feedback=resolution(source,resolved_path())))
    assert values(model,revisit(model,event,anchor,PC))==((0,3),(1,6))
    sources=tuple(revisit(model,event,anchor,PC) if path is None else via(model,event,anchor,path)
        for path in FULL_RETAINED_REPLACEMENT.paths)
    return model,event,anchor,sources


def pending_replacement_program():
    model,event,anchor,sources=replacement_program()
    loop=revisit(model,event,anchor,STREAM_PC)
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=Resolution(loop.history,loop.pc,
        (Outcome(STREAM_POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True),),origin=loop)))
    quiet(model,event)
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.tage.commits
    before_overflows=model.sources.tage.cache[7,PC%4].overflows
    for source in sources:model.advance(replace(event,feedback=resolution(source,resolved_path())))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('full-miss learning did not mature')
    return model,event,anchor,sources,baseline,before_overflows


def test_full_miss_keeps_new_own_counter_seed_and_all_three_nonvictims_then_drains_eight_writes():
    model,event,anchor,sources,baseline,before_overflows=pending_replacement_program()
    tage=model.sources.tage
    reads=tuple(model.sources.snapshot(source).read for source in sources)
    assert len({read.context for read in reads})==len({read.rows[3] for read in reads})==5
    assert tuple(counters(read) for read in reads)==((1,6),*((2,5),)*4)
    assert before_overflows==0 and tage.commits==baseline and tage.cache[7,PC%4].overflows==2
    plan=pending_plan(tage,7,PC%4)
    assert tuple(tuple(payload['counter'] for payload in way) for way in plan)==((1,)*4,(6,)*4)
    for owner,way in enumerate(plan):
        assert tuple(payload['row'] for payload in way)==tuple(reads[h].rows[3] for h in (4,1,2,3))
        assert all(payload['row']!=reads[0].rows[3] for payload in way)
    assert tuple(counters(tage.lookup_snapshot(PC,read.context)) for read in reads)==((1,6),*((2,5),)*4)
    quiet(model,event)
    assert tage.commits==baseline+8 and pending_plan(tage,7,PC%4)==((),())
    assert tuple(counters(tage.lookup_snapshot(PC,read.context)) for read in reads)==((1,6),)*5


def fixture():
    model,event,anchor,tokens,_,before_overflows=pending_replacement_program()
    consumers=[]
    for path in FULL_RETAINED_REPLACEMENT.paths:
        middle=anchor if path is None else streaming_query(model,event,anchor.history,path,anchor.pc+4)
        consumers.append(streaming_query(model,event,middle.history,PC,middle.pc+4))
    sources=tuple(NS(token=token,prediction_tick=100+10*index,meta_tick=104+10*index) for index,token in enumerate(tokens))
    events=tuple((200+2*index,resolution(token,resolved_path())) for index,token in enumerate(tokens))
    retired=[]
    pipeline=NS(board=Scoreboard('full-retained-replacement-contract'),model=model,last_tick=220,
        initial_overflows=before_overflows,
        last_resolution_controls=(208,event.enabled),source_token=lambda source:source.token,
        raise_failure=lambda:None,retire_source=retired.append,
        corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionReplacementChecks(pipeline,DirectionReplacementCoverage())
    row=dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        writes=tuple(dict(valid=1,ready=0,bits=way[0]) for way in pending_plan(model.sources.tage,7,0)),
        dirty=((1,)*4,)*2,incoming=tuple(dict(valid=0,bits={}) for _ in range(2)))
    old=tuple(NS(token=token,prediction_tick=230+10*index,meta_tick=234+10*index) for index,token in enumerate(consumers))
    return checks,sources,events,row,old,(model,event,anchor),retired


def offer(checks,row,index):
    actual=deepcopy(row)
    actual['incoming']=tuple(dict(valid=1,bits=deepcopy(payload)) for payload in checks.expected_offers[index])
    actual['dirty']=((1,)*min(index,4)+(0,)*max(0,4-index),)*2
    if index==4:
        actual['writes']=tuple(dict(valid=1,ready=0,bits=deepcopy(payload)) for payload in checks.expected_offers[0])
    return actual


def armed():
    checks,sources,events,row,old,program,retired=fixture()
    checks.arm(sources);checks.begin_read_window()
    # Synthetic callbacks replay the burst after pure-model maturation. The
    # diagnostic counter baseline belongs to the saved pre-input boundary,
    # not fixture construction; no model state or DUT state is repaired.
    checks.initial_overflows=checks.pipeline.initial_overflows
    for tick in range(200,218,2):
        actual=deepcopy(row) if tick<208 else offer(checks,row,(tick-208)//2)
        actual['training']['valid']=int(tick<=208)
        checks.capture_state(NS(tick=tick),actual)
    checks.capture_state(NS(tick=220),row)
    checks.accepted_burst(events)
    return checks,row,old,program,retired


def commit_and_query(checks,row,program):
    checks.pipeline.last_tick=300;checks.release()
    for owner in range(2):
        for ordinal,payload in enumerate(checks.expected_plan[owner]):
            checks.write_accepted(owner,NS(accepted_tick=310+2*ordinal,value=deepcopy(payload)))
    model,event,anchor=program
    quiet(model,event)
    tokens=tuple(revisit(model,event,anchor,PC) if path is None else via(model,event,anchor,path)
        for path in FULL_RETAINED_REPLACEMENT.paths)
    actual=deepcopy(row);actual['reads'][0]['valid']=0
    for port in actual['writes']:port.update(valid=0,ready=1)
    checks.capture_state(NS(tick=420),actual)
    return tuple(NS(token=token,prediction_tick=350+10*index,meta_tick=354+10*index) for index,token in enumerate(tokens))


def test_all_six_rules_wait_for_five_old_consumers_eight_survivor_commits_and_five_new_consumers():
    checks,row,old,program,retired=armed();checks.pending()
    assert checks.full_event_tick==216 and checks.program.retained_count==4<checks.program.history_count
    for source in old:checks.old_consumed(source)
    assert checks.coverage.groups['checked'].coverage==50
    new=commit_and_query(checks,row,program)
    for source in new[:4]:checks.new_consumed(source)
    assert not checks.closed and not retired and checks.coverage.groups['checked'].coverage<100
    checks.new_consumed(new[-1]);checks.finish()
    assert len(retired)==10 and all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('fifth-is-old-hit','same-context','same-row','wrong-incoming-seed',
    'wrong-incoming-tag','missing-owner','not-full','missing-victim-version','missing-source'))
def test_fifth_new_key_and_real_fullness_are_preconditions_not_names(fault):
    checks,sources,_,row,_,_,_=fixture()
    if fault=='missing-source':
        with pytest.raises(AssertionError):checks.arm(sources[:-1])
        return
    if fault in ('same-context','same-row'):
        original=checks.pipeline.model.sources.snapshot
        first=original(sources[0].token).read
        def corrupted(token,*,resolved=False):
            value=original(token,resolved=resolved)
            if token is sources[-1].token and not resolved:
                value=replace(value,read=replace(value.read,**(
                    {'context':first.context} if fault=='same-context' else {'rows':first.rows})))
            return value
        checks.pipeline.model.sources.snapshot=corrupted
        with pytest.raises(AssertionError):checks.arm(sources)
        return
    checks.arm(sources);checks.begin_read_window()
    for index in range(4):checks.capture_state(NS(tick=208+2*index),offer(checks,row,index))
    actual=offer(checks,row,4)
    if fault=='fifth-is-old-hit':actual['incoming']=offer(checks,row,0)['incoming']
    elif fault=='wrong-incoming-seed':actual['incoming'][1]['bits']['counter']=7
    elif fault=='wrong-incoming-tag':actual['incoming'][1]['bits']['tag']^=1
    elif fault=='missing-owner':actual['incoming'][0]['valid']=0
    elif fault=='missing-victim-version':actual['writes'][1]['bits']['counter']=6
    else:actual['dirty']=((1,1,0,1),(1,1,1,1))
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=216),actual)
    with pytest.raises(AssertionError) as error:checks.raise_failure()
    assert checks.full_event_tick is None and checks.coverage.groups['checked'].coverage==0
    assert checks.pipeline.model.sources.tage.state()==before
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is error.value


@pytest.mark.parametrize('fault',('zero-loss','extra-loss','retained-victim','lost-nonvictim','victim-counter-inherited','missing-full-proof'))
def test_exact_two_losses_and_every_new_or_surviving_counter_are_independently_required(fault):
    checks,_,_,_,_=armed()
    cache=checks.pipeline.model.sources.tage.cache[7,0]
    if fault=='zero-loss':cache.overflows=checks.initial_overflows
    elif fault=='extra-loss':cache.overflows+=1
    elif fault=='missing-full-proof':checks.full_event_tick=None
    else:
        key,version=next(iter(cache.records.items()))
        if fault=='lost-nonvictim':cache.pending.remove(version.sequence)
        elif fault=='victim-counter-inherited':cache.records[key]=replace(version,write=replace(version.write,entry=replace(version.write.entry,counter=7)))
        else:
            old=checks.pipeline.model.sources.snapshot(checks.pipeline.source_token(checks.sources[0])).read
            cache.records[key]=replace(version,write=replace(version.write,row=old.rows[3]))
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-fifth-old','missing-victim-consumer','missing-new-key-consumer',
    'missing-neighbour-consumer','missing-eighth-write','victim-was-written','wrong-new-seed'))
def test_no_silent_discard_or_partial_survivor_readback_can_close_replacement(fault):
    checks,row,old,program,retired=armed();checks.pending()
    for source in old[:4]:checks.old_consumed(source)
    if fault=='no-fifth-old':
        with pytest.raises(AssertionError):checks.release()
        return
    checks.old_consumed(old[-1]);new=commit_and_query(checks,row,program)
    if fault in ('missing-eighth-write','victim-was-written','wrong-new-seed'):
        if fault=='missing-eighth-write':checks.written[1].pop()
        else:
            original=checks.values
            selected=0 if fault=='victim-was-written' else 4
            def corrupted(source):
                token,values=original(source)
                return (token,(values[0],(0,7))) if source is new[selected] else (token,values)
            checks.values=corrupted
        with pytest.raises(AssertionError):
            for source in new:checks.new_consumed(source)
    else:
        missing={'missing-victim-consumer':0,'missing-new-key-consumer':4,'missing-neighbour-consumer':2}[fault]
        for index,source in enumerate(new):
            if index!=missing:checks.new_consumed(source)
        with pytest.raises(AssertionError):checks.finish()
    assert not retired and not checks.closed and checks.coverage.groups['checked'].coverage==50


def test_public_acceptance_without_five_internal_proposals_does_not_claim_a_full_miss():
    checks,sources,events,row,_,_,_=fixture()
    checks.arm(sources);checks.begin_read_window()
    for tick,_ in events:
        actual=deepcopy(row);actual['training']['valid']=1
        checks.capture_state(NS(tick=tick),actual)
    checks.accepted_burst(events)
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError):checks.pending()


def test_replacement_case_has_no_signal_edges_tasks_or_inline_comparisons():
    tree=ast.parse(Path('bpuverify/bpu/case/direction_replacement.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
