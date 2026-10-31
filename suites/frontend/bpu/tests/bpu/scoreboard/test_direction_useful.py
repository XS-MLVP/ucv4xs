"""Own-event preparation and checker faults. Synthetic cycles earn no DUT credit."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast

import pytest
from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.direction_useful import DirectionUsefulChecks
from suites.frontend.bpu.bpu.coverage.direction_useful import DirectionUsefulCoverage
from suites.frontend.bpu.bpu.model.pipeline import Resolution,Outcome,Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,POSITIONS,resolved_path
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC,STREAM_POSITION,learning_inflight
from suites.frontend.bpu.bpu.model.tage.useful_service import PROGRAM,main_preparation,pending_useful,occupancy
from tests.bpu.scoreboard.test_direction_forwarding import resolution,values
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit
from tests.bpu.scoreboard.test_direction_service import two_history_program,via,streaming_query


def prepared_program():
    model,event,anchor,_=two_history_program();idle=quiet(model,event)
    event=replace(event,enabled=tuple(False if index==3 else value for index,value in enumerate(event.enabled)))
    for _ in range(3):model.advance(replace(idle,enabled=event.enabled))
    for path,expected in main_preparation():
        source=revisit(model,event,anchor,PC)
        decision=model.sources.snapshot(source,resolved=True).late.branch
        assert path[0][2]==(decision.position!=POSITIONS[0] or not decision.taken)
        model.advance(replace(quiet(model,event),feedback=resolution(source,path)))
        assert values(model,revisit(model,event,anchor,PC))==expected
    idle=quiet(model,event)
    event=replace(event,enabled=tuple(True if index==3 else value for index,value in enumerate(event.enabled)))
    for _ in range(3):model.advance(replace(idle,enabled=event.enabled))
    tokens=(revisit(model,event,anchor,PC),via(model,event,anchor),revisit(model,event,anchor,PC),via(model,event,anchor))
    return model,event,anchor,tokens


def learn_under_reads(model,event,anchor,tokens):
    loop=revisit(model,event,anchor,STREAM_PC)
    model.advance(replace(quiet(model,event),feedback=Resolution(loop.history,loop.pc,
        (Outcome(STREAM_POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True),),origin=loop)))
    quiet(model,event)
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    for token in tokens:
        feedback=resolution(token,resolved_path())
        assert not model.sources.feedback_for(feedback).reread
        model.advance(replace(event,feedback=feedback))
    for _ in range(16):
        cycle=model.advance(event)
        assert cycle.fires[0] and cycle.next_pc%4==PC%4
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('semantic useful learning did not mature')


def test_useful_sequence_is_not_entry_forwarding_or_a_newest_metadata_accumulation():
    model,event,anchor,tokens=prepared_program();reads=tuple(model.sources.snapshot(token).read for token in tokens)
    old=tuple(deepcopy(model.sources.defined_metadata(token)) for token in tokens)
    assert all(values(model,token)==(PROGRAM.initial_base,PROGRAM.initial_counters) for token in tokens)
    assert all(tuple(read.matches(p)[-1][3] for p in POSITIONS)==PROGRAM.initial_useful for read in reads)
    learn_under_reads(model,event,anchor,tokens)
    plan=tuple(dict(row=read.rows[7],value=1) for read in reads)
    assert pending_useful(model.sources.tage,7,0)==(plan,())
    assert model.sources.tage.useful_queue[7,0,0].drops==0
    for read in reads:
        current=model.sources.tage.lookup_snapshot(PC,read.context)
        assert tuple(current.matches(p)[-1][2:] for p in POSITIONS)==((2,0),(5,1))
    quiet(model,event)
    for read in reads:
        current=model.sources.tage.lookup_snapshot(PC,read.context)
        assert tuple(current.matches(p)[-1][2:] for p in POSITIONS)==((0,1),(7,1))
    assert tuple(model.sources.defined_metadata(token) for token in tokens)==old
    assert values(model,revisit(model,event,anchor,PC))==(PROGRAM.final_base,PROGRAM.final_counters)


def state_row(plan,count=0):
    return dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),flushes=(0,0),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        writes=(dict(valid=int(count>0),ready=0,bits=deepcopy(plan[0])),dict(valid=0,ready=0,bits=dict(row=0,value=0))),
        incoming=tuple(dict(valid=0,ready=int(count<4 if way==0 else True),bits=dict(row=0,value=0)) for way in range(2)),
        queues=(dict(enqueue=count%4,dequeue=0,full=int(count==4)),dict(enqueue=0,dequeue=0,full=0)))


def fixture():
    model,event,anchor,tokens=prepared_program();retired=[]
    sources=tuple(NS(token=token,prediction_tick=100+10*index,meta_tick=104+10*index) for index,token in enumerate(tokens))
    pipeline=NS(model=model,board=Scoreboard('useful-service-contract'),last_tick=220,
        source_token=lambda source:source.token,raise_failure=lambda:None,retire_source=retired.append,
        last_resolution_controls=(206,event.enabled),corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionUsefulChecks(pipeline,DirectionUsefulCoverage())
    events=tuple((200+2*index,resolution(token,resolved_path())) for index,token in enumerate(tokens))
    return checks,sources,events,(model,event,anchor,tokens),retired


def accepted_fixture():
    checks,sources,events,program,retired=fixture();checks.arm(sources);checks.begin_read_window()
    model,event,anchor,tokens=program;learn_under_reads(model,event,anchor,tokens)
    for tick,_ in events:
        row=state_row(checks.plan);row['training']['valid']=1;checks.capture_state(NS(tick=tick),row)
    checks.accepted_burst(events)
    return checks,events,program,retired


def pending_fixture():
    checks,events,program,retired=accepted_fixture()
    for index,payload in enumerate(checks.plan):
        row=state_row(checks.plan,index);row['incoming'][0].update(valid=1,bits=deepcopy(payload));row['writes'][0]['valid']=1
        checks.capture_state(NS(tick=210+2*index),row)
    row=state_row(checks.plan,4);checks.capture_state(NS(tick=220),row)
    return checks,row,program,retired


def old_consumers(checks,program):
    model,event,anchor,_=program
    a=streaming_query(model,event,anchor.history,PC,anchor.pc+4)
    middle=streaming_query(model,event,anchor.history,PC+0x80,anchor.pc+4)
    b=streaming_query(model,event,middle.history,PC,PC+0x84)
    return (NS(token=a,prediction_tick=230,meta_tick=234),NS(token=b,prediction_tick=240,meta_tick=244))


def released_fixture():
    checks,row,program,retired=pending_fixture();checks.pending()
    for source in old_consumers(checks,program):checks.old_consumed(source)
    checks.release();return checks,row,program,retired


def committed_fixture():
    checks,row,program,retired=released_fixture()
    for index,payload in enumerate(checks.plan):checks.write_accepted(0,NS(accepted_tick=260+2*index,value=deepcopy(payload)))
    model,event,anchor,_=program;quiet(model,event)
    empty=state_row(checks.plan);empty['reads'][0]['valid']=0
    for port in empty['writes']:port.update(valid=0,ready=1)
    checks.capture_state(NS(tick=276),empty)
    consumers=(NS(token=revisit(model,event,anchor,PC),prediction_tick=280,meta_tick=284),
        NS(token=via(model,event,anchor),prediction_tick=290,meta_tick=294))
    return checks,empty,consumers,retired


def test_checked_credit_waits_for_four_actual_commits_and_both_fresh_history_consumers():
    checks,_,consumers,retired=committed_fixture()
    assert checks.coverage.groups['checked'].coverage==0
    checks.new_consumed(consumers[0])
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    checks.new_consumed(consumers[1]);checks.finish()
    assert checks.closed and len(retired)==6 and len(set(retired))==6
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


def test_prepared_disagreement_without_a_real_resolved_acceptance_is_not_an_event():
    checks,sources,_,_,_=fixture();checks.arm(sources);checks.begin_read_window()
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    checks,events,_,_=accepted_fixture()
    assert checks.coverage.groups['reached'].coverage==pytest.approx(100/3)
    point=checks.coverage.groups['reached'].report()['points'][0]
    assert all(entry['first']['tick']==events[-1][0] for origins in point['provenance'].values() for entry in origins.values())
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing','duplicate','order','base','counter','useful-target','useful-neighbour','reread-hint'))
def test_source_qualification_is_independent_and_not_an_observed_expected_seed(fault):
    checks,sources,_,_,_=fixture()
    if fault=='missing':sources=sources[:3]
    elif fault=='duplicate':sources=(sources[0],sources[1],sources[0],sources[3])
    elif fault=='order':sources=(sources[1],sources[0],*sources[2:])
    elif fault in ('base','counter'):
        original=checks.values
        checks.values=lambda source:(original(source)[0],((2,2),(2,5)) if fault=='base' else ((3,2),(3,5)))
    elif fault.startswith('useful-'):checks.useful=lambda source:(1,1) if fault=='useful-target' else (0,0)
    else:
        method=checks.pipeline.model.sources.defined_metadata
        def altered(token):
            fields=method(token);slot=next(key.split('.')[0] for key in fields if key.endswith('providerTakenCtr_value') and fields[key]==2)
            return dict(fields,**{slot+'.useProvider':0})
        checks.pipeline.model.sources.defined_metadata=altered
    with pytest.raises(AssertionError):checks.arm(sources)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('reset','flush','read-gap','reread','ready','not-concurrent','wrong-bank',
    'wrong-owner','wrong-row','wrong-value','not-ready','extra-proposal','nonadjacent'))
def test_wrong_service_state_or_proposal_latches_the_first_error(fault):
    checks,_,_,_=accepted_fixture();row=state_row(checks.plan)
    if fault=='reset':row['reset']=1
    elif fault=='flush':row['flushes']=(1,0)
    elif fault=='read-gap':row['reads'][0]['valid']=0
    elif fault=='reread':row['reads'][1]['valid']=1
    elif fault=='ready':row['writes'][0]['ready']=1
    elif fault in ('not-concurrent','wrong-bank'):
        row['training']['valid']=1
        row['prediction']['valid' if fault=='not-concurrent' else 'pc']^=1
    else:
        row['incoming'][0].update(valid=1,bits=deepcopy(checks.plan[0]))
        if fault=='wrong-owner':row['incoming'][1]['valid']=1
        elif fault in ('wrong-row','wrong-value'):row['incoming'][0]['bits'][fault.removeprefix('wrong-')]^=1
        elif fault=='not-ready':row['incoming'][0]['ready']=0
        elif fault=='extra-proposal':checks.proposals=[(210+2*i,p) for i,p in enumerate(checks.plan)]
        else:checks.proposals=[(206,checks.plan[0])];row['incoming'][0]['bits']=deepcopy(checks.plan[1])
    checks.capture_state(NS(tick=210),row)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing','nonadjacent','origin','too-early','disabled','input-tick','taken','target','action'))
def test_wrong_accepted_input_cannot_borrow_a_source_or_earn_checked_credit(fault):
    checks,events,_,_=accepted_fixture();checks.accepted=()
    events=list(events)
    if fault=='missing':events.pop()
    elif fault=='nonadjacent':events[1]=(204,events[1][1])
    elif fault=='origin':events[0]=(200,replace(events[0][1],origin=None))
    elif fault=='too-early':events[0]=(102,events[0][1])
    elif fault=='disabled':checks.pipeline.last_resolution_controls=(206,(False,)*7)
    elif fault=='input-tick':checks.input_ticks[0]+=1
    else:
        before=events[0][1];branch=before.branches[0]
        altered=replace(branch,**{fault:not branch.taken if fault=='taken' else branch.target^1 if fault=='target' else type(branch.action)(1)})
        events[0]=(200,replace(before,branches=(altered,*before.branches[1:])))
    with pytest.raises(AssertionError):checks.accepted_burst(tuple(events))
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-accept','still-learning','lost-effect','drop','missing-proposal','early-effect',
    'hidden-commit','lost-front','wrong-depth','wrong-boundary'))
def test_pending_proof_requires_actual_full_retention_at_the_independent_boundary(fault):
    checks,row,_,_=pending_fixture();tage=checks.pipeline.model.sources.tage
    if fault=='missing-accept':checks.accepted=()
    elif fault=='still-learning':tage.offers={(-1,-1):('not-mature',)}
    elif fault=='lost-effect':tage.useful_queue[7,0,0].pending.pop()
    elif fault=='drop':tage.useful_queue[7,0,0].drops=1
    elif fault=='missing-proposal':checks.proposals.pop()
    elif fault=='early-effect':checks.proposals[0]=(198,checks.proposals[0][1])
    elif fault=='hidden-commit':checks.written=[(210,checks.plan[0])]
    elif fault=='lost-front':row['writes'][0]['bits']['row']^=1
    elif fault=='wrong-depth':row['queues'][0]['full']=0
    else:checks.pipeline.last_tick+=2
    with pytest.raises(AssertionError):checks.pending()
    assert not checks.pending_checked and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('release-early','old-receipt','same-history','early-useful','counter','repair'))
def test_each_history_must_really_consume_old_values_before_read_release(fault):
    checks,_,program,_=pending_fixture();checks.pending();source=old_consumers(checks,program)[0]
    if fault=='release-early':
        checks.old_consumed(source)
        with pytest.raises(AssertionError):checks.release()
        return
    if fault=='old-receipt':source=checks.sources[0]
    elif fault=='same-history':checks.old_consumed(source)
    elif fault=='early-useful':checks.useful=lambda _:(1,1)
    elif fault=='counter':checks.values=lambda source:(source.token,((2,3),(0,7)))
    else:checks.pipeline.corrections_for_source=lambda _:()
    with pytest.raises(AssertionError):checks.old_consumed(source)
    assert checks.release_tick is None and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('before-release','wrong-port','wrong-row','wrong-value','wrong-order','duplicate'))
def test_every_useful_effect_needs_its_own_full_sdk_service_receipt(fault):
    checks,_,_,_=released_fixture();transfer=NS(accepted_tick=260,value=deepcopy(checks.plan[0]));way=0
    if fault=='before-release':transfer.accepted_tick=checks.release_tick
    elif fault=='wrong-port':way=1
    elif fault in ('wrong-row','wrong-value'):transfer.value[fault.removeprefix('wrong-')]^=1
    elif fault=='wrong-order':transfer.value=deepcopy(checks.plan[1])
    else:checks.written=[(250+2*i,p) for i,p in enumerate(checks.plan)]
    with pytest.raises(AssertionError):checks.write_accepted(way,transfer)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-write','missing-history','duplicate-history','early-read','lost-useful','overaccumulated-useful',
    'lost-neighbour','counter','repair','extra-service','hidden-depth','rebased-old-metadata'))
def test_closure_requires_all_commits_correct_new_consumers_and_immutable_originals(fault):
    checks,row,consumers,retired=committed_fixture();source=consumers[0]
    if fault=='missing-history':
        checks.new_consumed(source)
        with pytest.raises(AssertionError):checks.finish()
        assert not retired
        return
    if fault=='missing-write':checks.written.pop()
    elif fault=='duplicate-history':checks.new_consumed(source)
    elif fault=='early-read':source.prediction_tick=checks.written[-1][0]
    elif fault in ('lost-useful','overaccumulated-useful','lost-neighbour'):
        checks.useful=lambda _:{'lost-useful':(0,1),'overaccumulated-useful':(2,1),'lost-neighbour':(1,0)}[fault]
    elif fault=='counter':checks.values=lambda source:(source.token,((2,3),(2,5)))
    elif fault=='repair':checks.pipeline.corrections_for_source=lambda _:()
    elif fault=='extra-service':row['writes'][1]['valid']=1
    elif fault=='hidden-depth':row['queues'][0]['enqueue']=1
    else:
        checks.new_consumed(source);source=consumers[1];checks.original_metadata=()
    with pytest.raises(AssertionError):checks.new_consumed(source)
    assert not checks.closed and not retired and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('enqueue,dequeue,full,expected',((0,0,0,0),(0,0,1,4),(1,3,1,2),(3,0,0,3)))
def test_pointer_observation_distinguishes_full_from_empty_without_seeding_the_model(enqueue,dequeue,full,expected):
    assert occupancy(dict(enqueue=enqueue,dequeue=dequeue,full=full))==expected


@pytest.mark.parametrize('bad',(-1,4,True+4))
def test_invalid_pointer_observation_is_rejected(bad):
    with pytest.raises(ValueError):occupancy(dict(enqueue=bad,dequeue=0,full=0))


def test_case_contains_no_sampling_tasks_edges_delays_or_comparison_engine():
    tree=ast.parse(Path('bpu/case/direction_useful.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
