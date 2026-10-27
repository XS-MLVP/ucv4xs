"""Independent semantic programs and adversarial actuals; no DUT credit."""
import ast
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard

from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path
from bpuverify.bpu.model.tage.service import STREAM_PC,STREAM_POSITION,learning_inflight,pending_plan
from bpuverify.bpu.model.tage.shared_saturation import PROGRAMS,Program
from bpuverify.bpu.checker.shared_saturation import Checks
from bpuverify.bpu.coverage.shared_saturation import Coverage,RULES,lifetime_coverage
from tests.bpu.scoreboard.test_direction_capacity import capacity_program
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import via,counters,streaming_query
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit


@lru_cache(maxsize=1)
def foundation():return capacity_program()[:3]


def reference(p):
    model,event,anchor=deepcopy(foundation())
    sources=tuple(revisit(model,event,anchor,PC) if p.paths[h] is None else
        via(model,event,anchor,p.paths[h]) for h in p.feedback_order)
    loop=revisit(model,event,anchor,STREAM_PC);idle=quiet(model,event)
    model.advance(replace(idle,feedback=Resolution(loop.history,loop.pc,
        (Outcome(STREAM_POSITION,STREAM_PC,Kind.DIRECT,True,mispredict=True),),origin=loop)))
    quiet(model,event)
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.tage.commits;offers=[]
    def advance(request=None):
        model.advance(replace(event,feedback=request))
        rows=model.sources.tage.offers.get((7,PC%4),())
        if rows:offers.append(tuple((r.way,r.entry.counter) for r in rows))
    for source in sources:
        request=resolution(source,resolved_path());assert not model.sources.feedback_for(request).reread
        advance(request)
    for _ in range(32):
        advance()
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('independent shared learning did not mature')
    assert offers==[((0,1),(1,6))]*12
    assert model.sources.tage.commits==baseline
    assert tuple(tuple(row['counter'] for row in way) for way in pending_plan(model.sources.tage,7,PC%4))==((0,)*4,(7,)*4)
    assert model.sources.tage.cache[7,PC%4].overflows==0
    old=[]
    for path in p.paths:
        middle=anchor if path is None else streaming_query(model,event,anchor.history,path,anchor.pc+4)
        old.append(streaming_query(model,event,middle.history,PC,middle.pc+4))
    assert model.sources.tage.commits==baseline
    assert all(counters(model.sources.snapshot(s).read)==(2,5) for s in old)
    return model,event,anchor,sources,tuple(old),baseline


def fixture(p):
    model,event,anchor,tokens,old,baseline=reference(p)
    sources=tuple(NS(token=token,prediction_tick=100+10*i,meta_tick=104+10*i,
        meta={'resolve':{'sequence':i}}) for i,token in enumerate(tokens))
    retired=[]
    pipeline=NS(board=Scoreboard('shared-saturation-contract'),model=model,last_tick=1040,
        last_resolution_controls=(1022,event.enabled),source_token=lambda s:s.token,
        raise_failure=lambda:None,retire_source=retired.append,
        corrections_for_source=lambda s:((s.prediction_tick+2,2),))
    checks=Checks(pipeline,Coverage(p),p);checks.arm(sources);checks.begin_read_window()
    consumers=tuple(NS(token=t,prediction_tick=1100+10*i,meta_tick=1104+10*i) for i,t in enumerate(old))
    return checks,(model,event,anchor),consumers,retired,baseline


def packet(checks,counts,ordinal=None):
    records=[]
    for owner in range(2):
        records.append(tuple(dict(shadow=int(bool(counts[h])),row=checks.keys[h][owner][0],
            valid=1,tag=checks.keys[h][owner][2],counter=checks.program.counters_after(h,counts[h])[owner]) for h in range(4)))
    row=dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        writes=tuple(dict(valid=int(bool(way)),ready=0,bits=way[0] if way else dict(row=0,valid=0,tag=0,counter=0))
            for way in pending_plan(checks.pipeline.model.sources.tage,7,PC%4)),
        dirty=tuple(tuple(int(bool(count)) for count in counts) for _ in range(2)),
        incoming=tuple(dict(valid=int(ordinal is not None),bits={} if ordinal is None else deepcopy(value))
            for value in (checks.expected_offers[ordinal] if ordinal is not None else ({},{}))))
    return dict(state=row,records=tuple(records))


def armed(p):
    checks,reference,old,retired,baseline=fixture(p);counts=[0]*4
    for tick in range(1000,1032,2):
        ordinal=(tick-1008)//2 if tick>=1008 else None
        actual=packet(checks,counts,ordinal);actual['state']['training']['valid']=int(tick<=1022)
        checks.capture_state(NS(tick=tick),actual)
        if ordinal is not None:counts[p.feedback_order[ordinal]]+=1
    checks.capture_state(NS(tick=1040),packet(checks,counts))
    events=tuple((1000+2*i,resolution(s.token,resolved_path())) for i,s in enumerate(checks.sources))
    checks.accepted_burst(events);checks.pending()
    return checks,reference,old,retired,baseline


def completed(p):
    checks,reference,old,retired,baseline=armed(p)
    for source in old:checks.old_consumed(source)
    assert checks.coverage.groups['checked'].coverage==0
    checks.pipeline.last_tick=1200;checks.release()
    for owner,values in enumerate(checks.expected_plan):
        for rank,value in enumerate(values):checks.write_accepted(owner,NS(accepted_tick=1210+2*rank,value=deepcopy(value)))
    model,event,anchor=reference;quiet(model,event)
    assert model.sources.tage.commits==baseline+8
    assert pending_plan(model.sources.tage,7,PC%4)==((),())
    tokens=tuple(revisit(model,event,anchor,PC) if path is None else via(model,event,anchor,path) for path in p.paths)
    final=packet(checks,(3,)*4)
    final['state']['reads'][0]['valid']=0
    for port in final['state']['writes']:port.update(valid=0,ready=1)
    checks.capture_state(NS(tick=1340),final)
    new=tuple(NS(token=t,prediction_tick=1300+10*i,meta_tick=1304+10*i) for i,t in enumerate(tokens))
    return checks,new,retired


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_each_history_current_value_boundaries_actual_services_and_all_consumers(p):
    checks,new,retired=completed(p)
    for source in new:checks.new_consumed(source)
    checks.finish()
    assert checks.closed and checks.counts==[3]*4 and len(checks.boundaries)==4
    assert len(checks.offered)==len(checks.sources)==len(checks.accepted)==12
    assert len(retired)==16 and len(checks.compared_consumers)==8
    assert checks.coverage.groups['checked'].coverage==50


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
@pytest.mark.parametrize('fault',('counter','dirty','identity','duplicate','proposal','missing-prefix','early-service'))
def test_final_numbers_cannot_hide_a_wrong_intermediate_identity_or_obligation(p,fault):
    checks,_,_,_,_=fixture(p);counts=[0]*4
    for ordinal in range(5):
        checks.capture_state(NS(tick=1008+2*ordinal),packet(checks,counts,ordinal));counts[p.feedback_order[ordinal]]+=1
    row=packet(checks,counts,5)
    if fault=='counter':row['records'][0][0]['counter']^=1
    elif fault=='dirty':row['state']['dirty']=((0,1,1,1),(1,1,1,1))
    elif fault=='identity':row['records'][0][0]['tag']^=1
    elif fault=='duplicate':row['records'][0][1].update(row['records'][0][0])
    elif fault=='proposal':row['state']['incoming'][1]['bits']['counter']^=1
    elif fault=='missing-prefix':row['state']['incoming'][0]['valid']=0
    if fault=='early-service':
        with pytest.raises(AssertionError):checks.write_accepted(0,NS(accepted_tick=1020,value={}))
    else:
        checks.capture_state(NS(tick=1018),row)
        with pytest.raises(AssertionError) as first:checks.raise_failure()
        with pytest.raises(AssertionError) as second:checks.finish()
        assert first.value is second.value
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_missing_actual_proposal_is_not_replaced_by_twelve_acceptance_receipts(p):
    checks,_,_,_,_=armed(p);checks.offered.pop()
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',RULES)
def test_checked_credit_is_atomic_for_the_complete_cohort(missing):
    checks,new,_=completed(PROGRAMS[0])
    for source in new:checks.new_consumed(source)
    checks.coverage.compared.pop(missing)
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_three_final_consumers_cannot_replace_the_fourth(p):
    checks,new,_=completed(p)
    for source in new[:-1]:checks.new_consumed(source)
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_mutating_original_metadata_cannot_be_hidden_by_correct_final_counters(p):
    checks,new,_=completed(p);checks.sources[-1].meta['resolve']['sequence']^=1
    with pytest.raises(AssertionError):checks.new_consumed(new[0])
    assert checks.coverage.groups['checked'].coverage==0


def test_current_record_association_is_by_complete_key_not_rank():
    checks,_,_,_,_=fixture(PROGRAMS[0]);counts=[0]*4
    for ordinal in range(5):
        row=packet(checks,counts,ordinal)
        row['records']=tuple(tuple(reversed(owner)) for owner in row['records'])
        row['state']['dirty']=tuple(tuple(reversed(owner)) for owner in row['state']['dirty'])
        checks.capture_state(NS(tick=1008+ordinal*2),row);counts[checks.program.feedback_order[ordinal]]+=1
    checks.raise_failure();assert len(checks.offered)==5


@pytest.mark.parametrize('history,count',((True,1),(-1,1),(4,1),(0,True),(0,-1),(0,4)))
def test_undeclared_history_or_occurrence_does_not_create_bins(history,count):
    with pytest.raises(ValueError):PROGRAMS[0].counters_after(history,count)


def test_program_and_coverage_are_semantic_not_physical_variants():
    p=PROGRAMS[0]
    with pytest.raises(ValueError):Program(p.paths,p.feedback_order,'bank0')
    with pytest.raises(ValueError):Program(p.paths,tuple(reversed(p.feedback_order)),p.name)
    with pytest.raises(ValueError):lifetime_coverage('physical')
    for history in range(4):assert [p.counters_after(history,n) for n in range(4)]==[(2,5),(1,6),(0,7),(0,7)]


def test_source_is_pure_and_native_case_hides_clock_and_raw_io():
    tree=ast.parse(Path('bpuverify/bpu/model/tage/shared_saturation.py').read_text())
    assert {node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}=={'dataclasses','bpuverify.bpu.model.tage.service'}
    text=Path('tests/bpu/testcase/test_shared_saturation.py').read_text()
    assert not any(s in text for s in ('FallingEdge','RisingEdge','ClockCycles','asyncio.gather','get_','set_','.Set('))
