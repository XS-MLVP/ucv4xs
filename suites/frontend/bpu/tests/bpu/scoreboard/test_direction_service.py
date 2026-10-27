"""Independent learning visibility under uninterrupted same-bank read service."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import ast

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.direction_service import DirectionServiceChecks
from bpuverify.bpu.coverage.direction_service import DirectionServiceCoverage
from bpuverify.bpu.model.direction_sources import context_for
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.forwarding import PC,POSITIONS,resolved_path
from bpuverify.bpu.model.tage.service import STREAM_PC,STREAM_POSITION,VIA_PC,learning_inflight,pending_fronts,pending_plan,secondary_program
from tests.bpu.scoreboard.test_direction_forwarding import establish,resolution,values
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit


def pending_program():
    model,event,anchor=establish()
    old=tuple(revisit(model,event,anchor,PC) for _ in range(2))
    loop=revisit(model,event,anchor,STREAM_PC)
    idle=quiet(model,event)
    request=Resolution(loop.history,loop.pc,(Outcome(STREAM_POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True),),origin=loop)
    model.advance(replace(idle,feedback=request))
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.tage.commits
    for source in old:
        request=resolution(source,resolved_path())
        assert not model.sources.feedback_for(request).reread
        cycle=model.advance(replace(event,feedback=request))
        assert cycle.fires[0] and cycle.next_pc%4==PC%4
    for _ in range(16):
        cycle=model.advance(event)
        assert cycle.fires[0] and cycle.next_pc%4==PC%4
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('owned learning did not mature under same-bank reads')
    return model,event,anchor,old,baseline


def counters(read):return tuple(read.matches(position)[-1][2] for position in POSITIONS)


def via(model,event,anchor,via_pc=VIA_PC):
    middle=revisit(model,event,anchor,via_pc)
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(middle.history,via_pc+4,PC,True)))
    for _ in range(8):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==PC:return cycle.metadata
    raise AssertionError('genuine second-history query not published')


def additional_history(model,event,anchor,via_pc):
    for operation,path,owner,expected in secondary_program():
        idle=quiet(model,event)
        if operation in ('disable','enable'):
            event=replace(event,enabled=tuple(operation=='enable' if index==3 else value
                for index,value in enumerate(event.enabled)))
            for _ in range(3):model.advance(replace(idle,enabled=event.enabled))
            continue
        source=via(model,event,anchor,via_pc)
        idle=quiet(model,event)
        request=resolution(source,path)
        decision=model.sources.snapshot(source,resolved=True).late.branch
        actual_taken=next((POSITIONS[index] for index,taken,_ in path if taken),None)
        predicted=decision.position if decision.taken else None
        wrong=None if actual_taken==predicted else min(position for position in (actual_taken,predicted) if position is not None)
        assert tuple(POSITIONS[index] for index,_,is_wrong in path if is_wrong)==(() if wrong is None else (wrong,)), (
            operation,path,values(model,source),decision)
        if operation=='allocate':
            feedback=model.sources.feedback_for(request)
            for _ in range(128):
                if model.sources.tage.allocation_at_next_accept(feedback)==owner:break
                model.advance(idle)
            else:raise AssertionError('second-history allocation opportunity not reached')
        model.advance(replace(idle,feedback=request))
        assert values(model,via(model,event,anchor,via_pc))==expected
    return event


def two_history_program():
    model,event,anchor=establish()
    event=additional_history(model,event,anchor,VIA_PC)
    sources=(revisit(model,event,anchor,PC),via(model,event,anchor),
        revisit(model,event,anchor,PC),via(model,event,anchor))
    return model,event,anchor,sources


def test_nonreread_feedback_acceptance_does_not_make_pending_learning_visible_through_read_priority():
    model,event,anchor,old,baseline=pending_program()
    tage=model.sources.tage
    assert tage.commits==baseline
    payloads=pending_fronts(tage,3,PC%4)
    assert tuple(row['counter'] for row in payloads)==(0,7)
    assert counters(tage.lookup_snapshot(PC,context_for(old[0].history)))==(2,5)
    for _ in range(4):
        model.advance(event)
        assert pending_fronts(tage,3,PC%4)==payloads and tage.commits==baseline
    # A genuine same-bank query, not an SRAM peek, still owns the old values.
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,PC,True)))
    for _ in range(8):
        cycle=model.advance(event)
        assert cycle.fires[0] and cycle.next_pc%4==PC%4
        if cycle.metadata is not None and cycle.metadata.pc==PC:
            assert counters(model.sources.snapshot(cycle.metadata).read)==(2,5)
            break
    else:raise AssertionError('old-value consumer not published')
    quiet(model,event)
    assert tage.commits==baseline+2
    new=revisit(model,event,anchor,PC)
    assert counters(model.sources.snapshot(new).read)==(0,7)
    assert pending_fronts(tage,3,PC%4)==(None,None)


def test_two_owned_histories_retain_four_pending_versions_and_retire_two_per_owner_after_release():
    model,event,anchor,sources,baseline=pending_two_history_program()
    tage=model.sources.tage
    reads=tuple(model.sources.snapshot(source).read for source in sources)
    assert tage.commits==baseline
    plan=pending_plan(tage,3,PC%4)
    assert tuple(tuple(payload['counter'] for payload in way) for way in plan)==((0,0),(7,7))
    assert all(counters(tage.lookup_snapshot(PC,read.context))==(2,5) for read in reads)
    quiet(model,event)
    assert tage.commits==baseline+4
    assert pending_plan(tage,3,PC%4)==((),())
    assert all(counters(tage.lookup_snapshot(PC,read.context))==(0,7) for read in reads)


def pending_two_history_program():
    model,event,anchor,sources=two_history_program()
    reads=tuple(model.sources.snapshot(source).read for source in sources)
    assert reads[0].context!=reads[1].context and reads[0].rows[3]!=reads[1].rows[3]
    assert reads[0]==reads[2] and reads[1]==reads[3]
    assert all(counters(read)==(2,5) for read in reads)
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
    else:raise AssertionError('owned four-input learning did not mature')
    return model,event,anchor,sources,baseline


def streaming_query(model,event,checkpoint,pc,cfi):
    model.advance(replace(event,redirect=Redirect(checkpoint,cfi,pc,True)))
    for _ in range(8):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==pc:return cycle.metadata
    raise AssertionError('continuous read query did not publish')


def fixture():
    model,event,anchor,tokens,_=pending_two_history_program()
    old_a=streaming_query(model,event,anchor.history,PC,anchor.pc+4)
    mid=streaming_query(model,event,anchor.history,VIA_PC,anchor.pc+4)
    old_b=streaming_query(model,event,mid.history,PC,VIA_PC+4)
    sources=tuple(NS(token=token,prediction_tick=100+index*10,meta_tick=104+index*10) for index,token in enumerate(tokens))
    accepted=tuple((200+index*2,resolution(token,resolved_path())) for index,token in enumerate(tokens))
    retired=[]
    pipeline=NS(board=Scoreboard('direction-service-contract'),model=model,last_tick=220,
        last_resolution_controls=(206,event.enabled),source_token=lambda source:source.token,
        raise_failure=lambda:None,retire_source=retired.append,
        corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionServiceChecks(pipeline,DirectionServiceCoverage())
    row=dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        writes=tuple(dict(valid=1,ready=0,bits=way[0]) for way in pending_plan(model.sources.tage,3,0)))
    consumers=(NS(token=old_a,prediction_tick=230,meta_tick=234),NS(token=old_b,prediction_tick=240,meta_tick=244))
    return checks,sources,accepted,row,consumers,(model,event,anchor),retired


def armed():
    checks,sources,events,row,old,program,retired=fixture()
    checks.arm(sources)
    checks.begin_read_window()
    for tick,_ in events:
        active=deepcopy(row);active['training']['valid']=1
        checks.capture_state(NS(tick=tick),active)
    checks.capture_state(NS(tick=220),row)
    checks.accepted_burst(events)
    return checks,row,old,program,retired


def commit_and_query(checks,row,program):
    for way in range(2):
        for ordinal,payload in enumerate(checks.expected_plan[way]):
            checks.write_accepted(way,NS(accepted_tick=260+2*ordinal,value=deepcopy(payload)))
    model,event,anchor=program
    quiet(model,event)
    sources=(NS(token=revisit(model,event,anchor,PC),prediction_tick=280,meta_tick=284),
        NS(token=via(model,event,anchor),prediction_tick=290,meta_tick=294))
    empty=deepcopy(row)
    empty['reads'][0]['valid']=0
    for port in empty['writes']:port.update(valid=0,ready=1)
    checks.capture_state(NS(tick=300),empty)
    return sources


def test_all_six_events_require_both_old_consumers_four_actual_commits_and_both_new_consumers():
    checks,row,old,program,retired=armed()
    assert checks.coverage.groups['checked'].coverage==0
    checks.pending()
    checks.old_consumed(old[0])
    assert checks.coverage.groups['checked'].coverage==0
    checks.old_consumed(old[1])
    assert checks.coverage.groups['checked'].coverage==50
    checks.release()
    new=commit_and_query(checks,row,program)
    checks.new_consumed(new[0])
    assert checks.coverage.groups['checked'].coverage<100 and not retired
    checks.new_consumed(new[1])
    checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())
    assert len(retired)==6


@pytest.mark.parametrize('fault',('missing-source','duplicate-checkpoint','wrong-order','history-alias',
    'wrong-provider','wrong-base','reread-hint'))
def test_source_qualification_requires_four_ordered_owners_two_distinct_histories_and_strong_hints(fault):
    checks,sources,_,_,_,_,_=fixture()
    if fault=='missing-source':sources=sources[:3]
    elif fault=='duplicate-checkpoint':sources[3].token=replace(sources[3].token,history=sources[1].token.history)
    elif fault=='wrong-order':sources[1].prediction_tick=sources[0].meta_tick
    elif fault=='wrong-provider':checks.owners=lambda _:((3,0),(2,1))
    elif fault=='wrong-base':checks.values=lambda value:(value.token,((0,3),(2,5)))
    elif fault=='reread-hint':
        original=checks.pipeline.model.sources.defined_metadata
        def corrupted(token):
            values=original(token)
            for key in values:
                if key.endswith('.hasAlt'):values[key]=1
            return values
        checks.pipeline.model.sources.defined_metadata=corrupted
    else:
        original=checks.pipeline.model.sources.snapshot
        a=original(sources[0].token).read
        def aliased(token,*,resolved=False):
            saved=original(token,resolved=resolved)
            return saved if resolved else replace(saved,read=a)
        checks.pipeline.model.sources.snapshot=aliased
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError) as first:checks.arm(sources)
    assert checks.pipeline.model.sources.tage.state()==before
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


@pytest.mark.parametrize('fault',('read-gap','wrong-bank','reread','prediction-absent','prediction-stalled','wrong-prediction-bank','reset','write-ready'))
def test_actual_read_and_concurrency_violations_latch_without_credit_or_golden_repair(fault):
    checks,sources,events,row,_,_,_=fixture()
    checks.arm(sources);checks.begin_read_window()
    actual=deepcopy(row)
    actual['training']['valid']=1
    if fault=='read-gap':actual['reads'][0]['valid']=0
    elif fault=='wrong-bank':actual['reads'][0]['mask']=2
    elif fault=='reread':actual['reads'][1].update(valid=1,mask=1)
    elif fault=='prediction-absent':actual['prediction']['valid']=0
    elif fault=='prediction-stalled':actual['prediction']['ready']=0
    elif fault=='wrong-prediction-bank':actual['prediction']['pc']+=1
    elif fault=='reset':actual['reset']=1
    else:actual['writes'][1]['ready']=1
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=200),actual)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==before
    assert checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value


@pytest.mark.parametrize('fault',('valid','ready','row','tag','counter','entry-valid','missing-port'))
def test_bad_blocked_port_payload_is_compared_against_owned_pending_versions(fault):
    checks,row,_,_,_=armed()
    actual=deepcopy(row)
    if fault in ('valid','ready'):actual['writes'][1][fault]^=1
    elif fault=='missing-port':actual['writes']=actual['writes'][:1]
    else:actual['writes'][1]['bits']['valid' if fault=='entry-valid' else fault]^=1
    checks.capture_state(NS(tick=220),actual)
    before=deepcopy(pending_plan(checks.pipeline.model.sources.tage,3,0))
    with pytest.raises(AssertionError):checks.pending()
    assert pending_plan(checks.pipeline.model.sources.tage,3,0)==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('not-adjacent','missing-beat','wrong-origin','wrong-target','wrong-history-order','missing-prediction-proof'))
def test_input_burst_cannot_be_replaced_by_queue_labels_or_aliases(fault):
    checks,sources,events,row,_,_,_=fixture()
    checks.arm(sources);checks.begin_read_window()
    for tick,_ in events:
        active=deepcopy(row);active['training']['valid']=1
        checks.capture_state(NS(tick=tick),active)
    events=list(events)
    if fault=='not-adjacent':events[1]=(204,events[1][1])
    elif fault=='missing-beat':events=events[:3]
    elif fault=='wrong-origin':events[0]=(200,replace(events[0][1],origin=None))
    elif fault=='wrong-target':
        request=events[0][1]
        events[0]=(200,replace(request,branches=(replace(request.branches[0],target=PC+2),*request.branches[1:])))
    elif fault=='wrong-history-order':events[1]=(202,events[2][1])
    else:checks.actual_inputs=checks.actual_inputs[:-1]
    with pytest.raises(AssertionError):checks.accepted_burst(tuple(events))
    assert all(group.coverage==0 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('same-history-twice','old-receipt','premature-new-values','missing-repair','extra-repair','release-before-second'))
def test_both_old_value_consumers_are_required_before_read_release(fault):
    checks,row,old,_,_=armed();checks.pending()
    if fault=='release-before-second':
        checks.old_consumed(old[0])
        with pytest.raises(AssertionError):checks.release()
    else:
        source=old[0]
        if fault=='same-history-twice':checks.old_consumed(source)
        elif fault=='old-receipt':source=checks.sources[0]
        elif fault=='premature-new-values':checks.values=lambda value:(value.token,((0,3),(0,7)))
        elif fault=='missing-repair':checks.pipeline.corrections_for_source=lambda _:()
        else:checks.pipeline.corrections_for_source=lambda value:((value.prediction_tick+2,2),(value.meta_tick,3))
        with pytest.raises(AssertionError):checks.old_consumed(source)
    assert checks.release_tick is None and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('before-release','wrong-port','wrong-row','wrong-tag','wrong-counter','wrong-valid','out-of-order','duplicate'))
def test_every_commit_has_the_exact_owner_history_payload_and_service_order(fault):
    checks,row,old,_,_=armed();checks.pending()
    for source in old:checks.old_consumed(source)
    if fault!='before-release':checks.release()
    transfer=NS(accepted_tick=260,value=deepcopy(checks.expected_plan[0][0]))
    way=0
    if fault=='wrong-port':way=2
    elif fault.startswith('wrong-'):transfer.value[fault.removeprefix('wrong-')]^=1
    elif fault=='out-of-order':transfer.value=deepcopy(checks.expected_plan[0][1])
    elif fault=='duplicate':
        for ordinal,payload in enumerate(checks.expected_plan[0]):
            checks.write_accepted(0,NS(accepted_tick=260+2*ordinal,value=payload))
    with pytest.raises(AssertionError):checks.write_accepted(way,transfer)
    assert not checks.closed and checks.coverage.groups['checked'].coverage<100


@pytest.mark.parametrize('fault',('missing-commit','missing-history-consumer','duplicate-history','old-value','missing-repair','extra-pending','early-read'))
def test_postrelease_credit_requires_all_four_writes_and_both_new_history_consumers(fault):
    checks,row,old,program,retired=armed();checks.pending()
    for source in old:checks.old_consumed(source)
    checks.release()
    new=commit_and_query(checks,row,program)
    if fault=='missing-commit':checks.written[1].pop()
    elif fault=='missing-history-consumer':
        checks.new_consumed(new[0])
        with pytest.raises(AssertionError):checks.finish()
        assert not retired
        return
    elif fault=='duplicate-history':checks.new_consumed(new[0])
    elif fault=='old-value':checks.values=lambda value:(value.token,((0,3),(2,5)))
    elif fault=='missing-repair':checks.pipeline.corrections_for_source=lambda _:()
    elif fault=='extra-pending':checks.last[1]['writes'][0]['valid']=1
    else:new[0].prediction_tick=262
    with pytest.raises(AssertionError):checks.new_consumed(new[0])
    assert not retired and not checks.closed and checks.coverage.groups['checked'].coverage<100


def test_service_case_keeps_sampling_tasks_edges_and_comparisons_in_support_layers():
    tree=ast.parse(Path('bpuverify/bpu/case/direction_service.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
