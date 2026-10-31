"""Own-event programs and synthetic checker faults, not actual DUT coverage."""
from suites.frontend.bpu.models.configuration import TAGE_ALLOCATION_WAIT
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import ast

import pytest
from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.direction_forwarding import DirectionForwardingChecks
from suites.frontend.bpu.bpu.coverage.direction_forwarding import DirectionForwardingCoverage
from suites.frontend.bpu.bpu.model.pipeline import Outcome,Resolution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS,establish_program,resolved_path
from tests.bpu.scoreboard.test_direction_sources import prepared,quiet,revisit


def resolution(source,path):
    return Resolution(source.history,source.pc,tuple(Outcome(POSITIONS[index],TARGETS[index],
        Kind.CONDITIONAL,taken,mispredict=wrong) for index,taken,wrong in path)+(None,)*(8-len(path)),origin=source)


def values(model,source):
    metadata=model.sources.defined_metadata(source)
    entries=tuple(entry for row in source_entries(source.lookup) for entry in row)
    main,tage=[],[]
    for position in POSITIONS:
        match=[(slot,entry) for slot,entry in enumerate(entries) if entry.hit and entry.position==position]
        if not match:main.append(None);tage.append(None)
        else:
            slot,entry=match[0]
            main.append(entry.counter)
            tage.append(metadata.get(f'{slot}.providerTakenCtr_value'))
    return tuple(main),tuple(tage)


def establish(**source_options):
    model,event,anchor=prepared(**source_options)
    for operation,path,owner,expected in establish_program():
        idle=quiet(model,event)
        if operation in ('disable','enable'):
            event=replace(event,enabled=tuple(operation=='enable' if index==3 else value
                for index,value in enumerate(event.enabled)))
            idle=replace(idle,enabled=event.enabled)
            for _ in range(3):model.advance(idle)
            continue
        source=revisit(model,event,anchor,PC)
        idle=quiet(model,event)
        feedback=resolution(source,path)
        # Independently qualify the planned wrong position against the
        # complete owned final decision, not a label in the program.
        decision=model.sources.snapshot(source,resolved=True).late.branch
        actual_taken=next((POSITIONS[index] for index,taken,_ in path if taken),None)
        predicted_position=decision.position if decision.taken else None
        wrong=None
        if actual_taken!=predicted_position:
            wrong=min(position for position in (actual_taken,predicted_position) if position is not None)
        assert tuple(POSITIONS[index] for index,_,is_wrong in path if is_wrong)==(() if wrong is None else (wrong,))
        if operation=='allocate':
            request=model.sources.feedback_for(feedback)
            for _ in range(TAGE_ALLOCATION_WAIT):
                if model.sources.tage.allocation_at_next_accept(request)==owner:break
                model.advance(idle)
            else:raise AssertionError('independent allocation opportunity not reached')
        model.advance(replace(idle,feedback=feedback))
        after=revisit(model,event,anchor,PC)
        assert values(model,after)==expected
    return model,event,anchor


def test_full_semantic_preparation_derives_two_opposite_longest_history_owners_without_state_seeds():
    model,event,anchor=establish()
    first=revisit(model,event,anchor,PC)
    second=revisit(model,event,anchor,PC)
    assert first is not second and first.history is not second.history
    assert model.sources.snapshot(first).read==model.sources.snapshot(second).read
    assert values(model,first)==values(model,second)==((1,2),(2,5))
    assert tuple(model.sources.snapshot(first).read.matches(position)[-1][:2] for position in POSITIONS)==((7,0),(7,1))


def test_adjacent_feedback_uses_immutable_old_hints_but_forwards_both_learning_results():
    model,event,anchor=establish()
    sources=tuple(revisit(model,event,anchor,PC) for _ in range(2))
    original=tuple(model.sources.defined_metadata(source) for source in sources)
    idle=quiet(model,event)
    for source in sources:model.advance(replace(idle,feedback=resolution(source,resolved_path())))
    final=revisit(model,event,anchor,PC)
    assert values(model,final)==((0,3),(0,7))
    assert tuple(model.sources.defined_metadata(source) for source in sources)==original
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=resolution(final,resolved_path())))
    retained=revisit(model,event,anchor,PC)
    assert values(model,retained)==((0,3),(0,7))


def checker_fixture():
    model,event,anchor=establish()
    old=tuple(revisit(model,event,anchor,PC) for _ in range(2))
    sources=tuple(NS(token=token,prediction_tick=100+index*10,meta_tick=104+index*10)
        for index,token in enumerate(old))
    idle=quiet(model,event)
    accepted=tuple((130+index*2,resolution(token,resolved_path())) for index,token in enumerate(old))
    for _,request in accepted:model.advance(replace(idle,feedback=request))
    final=NS(token=revisit(model,event,anchor,PC),prediction_tick=140,meta_tick=144)
    fresh=(150,resolution(final.token,resolved_path()))
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=fresh[1]))
    retained=NS(token=revisit(model,event,anchor,PC),prediction_tick=160,meta_tick=164)
    retired=[]
    pipeline=NS(board=Scoreboard('owned-direction-forwarding-contract'),model=model,
        raise_failure=lambda:None,source_token=lambda value:value.token,last_resolution_controls=(132,event.enabled),
        corrections_for_source=lambda source:((source.prediction_tick+2,2),),retire_source=retired.append)
    checks=DirectionForwardingChecks(pipeline,DirectionForwardingCoverage())
    return checks,sources,accepted,final,fresh,retained,retired


def test_full_event_program_only_closes_after_adjacent_feedback_and_both_new_consumers():
    checks,sources,events,final,fresh,retained,retired=checker_fixture()
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    checks.arm(sources)
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    checks.accepted_burst(events)
    assert checks.coverage.groups['reached'].coverage>0 and checks.coverage.groups['checked'].coverage==0
    checks.consumed(final)
    assert checks.coverage.groups['checked'].coverage<100 and not retired
    checks.pipeline.last_resolution_controls=(150,checks.pipeline.last_resolution_controls[1])
    checks.accepted_saturated(fresh)
    checks.retained(retained)
    checks.finish()
    assert retired==[104,114]
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('duplicate-receipt','duplicate-checkpoint','one-source','overlapping-source-time',
    'wrong-old-counter','wrong-provider-way'))
def test_bad_old_read_sources_cannot_arm_or_earn_any_event_credit(fault):
    checks,sources,_,_,_,_,_=checker_fixture()
    if fault=='duplicate-receipt':sources=(sources[0],sources[0])
    elif fault=='duplicate-checkpoint':sources[1].token=replace(sources[1].token,history=sources[0].token.history)
    elif fault=='one-source':sources=sources[:1]
    elif fault=='overlapping-source-time':sources[1].prediction_tick=sources[0].meta_tick
    elif fault=='wrong-old-counter':
        original=checks.values
        def wrong(source):
            token,_=original(source)
            return token,((1,2),(1,5))
        checks.values=wrong
    else:checks.owners=lambda _:((3,1),(3,0))
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises((AssertionError,ValueError)):checks.arm(sources)
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    assert checks.pipeline.model.sources.tage.state()==before


@pytest.mark.parametrize('fault',('not-adjacent','missing-input','wrong-origin','before-source','disabled',
    'position','target','kind','taken','mispredict','action','pc','missing-prefix','extra-branch'))
def test_invalid_actual_feedback_cannot_receive_learning_credit(fault):
    checks,sources,events,_,_,_,_=checker_fixture()
    checks.arm(sources)
    events=list(events)
    tick,request=events[0]
    if fault=='not-adjacent':events[1]=(events[1][0]+2,events[1][1])
    elif fault=='missing-input':events=events[:1]
    elif fault=='before-source':events=[(10,events[0][1]),(12,events[1][1])]
    elif fault=='wrong-origin':events[0]=(tick,replace(request,origin=None))
    elif fault=='disabled':checks.pipeline.last_resolution_controls=(132,(False,)*7)
    else:
        if fault=='missing-prefix':branches=(None,request.branches[1])
        elif fault=='extra-branch':branches=(*request.branches[:2],replace(request.branches[0],position=12))
        elif fault=='pc':branches=request.branches
        else:
            branch=request.branches[0]
            fields={field:getattr(branch,field) for field in ('position','target','kind','taken','mispredict','action')}
            fields[fault]=int(fields[fault])^1
            branches=(NS(**fields),request.branches[1])
        events[0]=(tick,NS(origin=request.origin,pc=request.pc^int(fault=='pc'),branches=branches))
    with pytest.raises(AssertionError) as first:checks.accepted_burst(tuple(events))
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


@pytest.mark.parametrize('fault',('single-update','only-negative','only-positive','changed-provider','missing-repair',
    'extra-final-repair','wrong-tick','old-source','early-tick'))
def test_incomplete_or_wrong_post_feedback_consumer_keeps_all_checked_credit_empty(fault):
    checks,sources,events,final,_,_,retired=checker_fixture()
    checks.arm(sources)
    checks.accepted_burst(events)
    if fault in ('single-update','only-negative','only-positive'):
        actual={'single-update':(1,6),'only-negative':(0,6),'only-positive':(1,7)}[fault]
        checks.values=lambda source:(source.token,((0,3),actual))
    elif fault=='changed-provider':checks.owners=lambda _:((3,1),(3,0))
    elif fault=='missing-repair':checks.pipeline.corrections_for_source=lambda _:()
    elif fault=='extra-final-repair':checks.pipeline.corrections_for_source=lambda _:((142,2),(144,3))
    elif fault=='wrong-tick':checks.pipeline.corrections_for_source=lambda _:((144,2),)
    elif fault=='old-source':final=sources[0]
    else:final.prediction_tick=events[-1][0]
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError) as first:checks.consumed(final)
    assert checks.pipeline.model.sources.tage.state()==before and not retired
    assert checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


@pytest.mark.parametrize('fault',('unaccepted','wrong-origin','wrong-direction','disabled','old-boundary-source',
    'wrap-counter','extra-repair','provider-moved','early-end'))
def test_saturation_retention_requires_fresh_actual_feedback_and_final_owner_consumption(fault):
    checks,sources,events,final,fresh,retained,retired=checker_fixture()
    checks.arm(sources)
    checks.accepted_burst(events)
    checks.consumed(final)
    checks.pipeline.last_resolution_controls=(150,checks.pipeline.last_resolution_controls[1])
    if fault=='wrong-origin':fresh=(150,replace(fresh[1],origin=None))
    elif fault=='wrong-direction':fresh=(150,replace(fresh[1],branches=(replace(fresh[1].branches[0],taken=True),)))
    elif fault=='disabled':checks.pipeline.last_resolution_controls=(150,(False,)*7)
    if fault in ('wrong-origin','wrong-direction','disabled'):
        with pytest.raises(AssertionError):checks.accepted_saturated(fresh)
    elif fault=='early-end':
        with pytest.raises(AssertionError):checks.finish()
    else:
        if fault!='unaccepted':checks.accepted_saturated(fresh)
        if fault=='old-boundary-source':retained=final
        elif fault=='wrap-counter':checks.values=lambda source:(source.token,((0,3),(7,0)))
        elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda source:((162,2),(164,3))
        elif fault=='provider-moved':checks.owners=lambda _:((2,0),(3,1))
        with pytest.raises(AssertionError):checks.retained(retained)
    assert not retired and not checks.closed and checks.coverage.groups['checked'].coverage<100


def test_program_keeps_executed_prefixes_and_one_wrong_branch_without_case_level_timing():
    for operation,path,owner,expected in establish_program():
        active=[(index,taken,wrong) for index,taken,wrong in path]
        assert sum(wrong for _,_,wrong in active)<=1
        assert [index for index,_,_ in active]==sorted(index for index,_,_ in active)
        assert not any(taken for _,taken,_ in active[:-1])
        assert (owner is not None)==(operation=='allocate')
    tree=ast.parse(Path('bpu/case/direction_forwarding.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
