"""Distinct stale owners overlap; current versions, not old snapshots, compose."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.direction_burst import DirectionBurstChecks
from bpuverify.bpu.coverage.direction_burst import DirectionBurstCoverage
from bpuverify.bpu.model.tage.migration import PC,POSITION,TARGET,PATHS
from bpuverify.bpu.model.tage.stale_burst import SOURCE_COUNT,COMMIT_COUNTERS
from tests.bpu.scoreboard.test_direction_migration import migration_program,request,values
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via


def burst_program(original_way=1):
    sources=[]
    model,event,anchor,_=migration_program(original_way,retained_sources=sources)
    before={name:via(model,event,anchor,path) for name,path in PATHS.items()}
    return model,event,anchor,tuple(sources),before


def learn_burst(model,event,sources):
    idle=quiet(model,event)
    tage=model.sources.tage;commits=tage.commits;path=[]
    context=model.sources.snapshot(sources[0]).read.context
    def step(events):
        previous=tage.commits
        model.advance(events)
        if tage.commits!=previous:
            assert tage.commits==previous+1
            path.append(tage.lookup_snapshot(PC,context).matches(POSITION)[-1][2])
    for source in sources:
        feedback=request(source,True,False)
        assert not model.sources.feedback_for(feedback).reread
        step(replace(idle,feedback=feedback))
    for _ in range(16):
        if not model.sources.main_pending():break
        step(idle)
    else:raise AssertionError('owned burst effects did not retire')
    assert tage.commits==commits+SOURCE_COUNT
    return tuple(path)


@pytest.mark.parametrize('original_way',(0,1))
def test_four_distinct_old_sources_compound_as_5_6_7_7_through_the_new_owner(original_way):
    model,event,anchor,sources,before=burst_program(original_way)
    assert len(sources)==len({id(s) for s in sources})==len({id(s.history) for s in sources})==SOURCE_COUNT
    assert all(values(model,s)==(3,(7,original_way,5,0)) for s in sources)
    assert values(model,before['original'])==(2,(7,1-original_way,4,0))
    metadata=tuple(model.sources.defined_metadata(s) for s in sources)
    assert learn_burst(model,event,sources)==COMMIT_COUNTERS
    after={name:via(model,event,anchor,path) for name,path in PATHS.items()}
    assert values(model,after['original'])==(3,(7,1-original_way,7,0))
    assert values(model,after['newcomer'])==(3,(7,original_way,5,1))
    assert values(model,after['blocker'])==(3,None)
    assert tuple(model.sources.defined_metadata(s) for s in sources)==metadata


def fixture(original_way=1):
    model,event,anchor,tokens,before=burst_program(original_way)
    sources=tuple(NS(token=token,prediction_tick=100+10*i,meta_tick=104+10*i) for i,token in enumerate(tokens))
    profile={name:NS(token=token,prediction_tick=300+10*i,meta_tick=304+10*i)
        for i,(name,token) in enumerate(before.items())}
    retired=[]
    pipeline=NS(model=model,raise_failure=lambda:None,board=Scoreboard('distinct-stale-burst-contract'),
        source_token=lambda source:source.token,last_resolution_controls=(606,event.enabled),retire_source=retired.append,
        corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionBurstChecks(pipeline,DirectionBurstCoverage(original_way),original_way)
    # Preparation effects were checked by the independent program above; this
    # fixture isolates callback/association errors at its completed boundary.
    checks.prepared_labels=[step.label for step in checks.intents]
    checks.original=sources[0]
    checks.original_metadata=tuple(model.sources.defined_metadata(tokens[0]).items())
    for source in sources:checks.retain_source(source)
    row=dict(reset=0,reads=({'valid':0,'mask':0},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),incoming=tuple(dict(valid=0,bits={}) for _ in range(2)))
    return checks,profile,row,(model,event,anchor),retired


def armed(original_way=1):
    checks,profile,row,program,retired=fixture(original_way)
    checks.arm(profile)
    return checks,profile,row,program,retired


def observations(checks,row):
    active=deepcopy(row);active['training']['valid']=1
    for index in range(SOURCE_COUNT):checks.capture_state(NS(tick=600+2*index),active)
    proposal=deepcopy(row)
    proposal['incoming'][checks.original_way].update(valid=1,bits=deepcopy(checks.proposal))
    for index in range(SOURCE_COUNT):checks.capture_state(NS(tick=608+2*index),proposal)
    return tuple((600+2*index,request(source.token,True,False)) for index,source in enumerate(checks.sources))


def accepted(checks,row):checks.accepted(observations(checks,row))


def commit_and_query(checks,program):
    for index,counter in enumerate(COMMIT_COUNTERS):
        checks.write_accepted(1-checks.original_way,NS(accepted_tick=610+2*index,value=dict(checks.commit,counter=counter)))
    model,event,anchor=program
    assert learn_burst(model,event,tuple(source.token for source in checks.sources))==COMMIT_COUNTERS
    return {name:NS(token=via(model,event,anchor,path),prediction_tick=650+10*i,meta_tick=654+10*i)
        for i,(name,path) in enumerate(PATHS.items())}


@pytest.mark.parametrize('original_way',(0,1))
def test_credit_waits_for_all_four_versions_and_all_three_consumers(original_way):
    checks,_,row,program,retired=armed(original_way)
    accepted(checks,row)
    assert checks.coverage.groups['checked'].coverage==0
    new=commit_and_query(checks,program)
    for name in ('original','blocker'):checks.consumed(name,new[name])
    assert not checks.closed and not retired and checks.coverage.groups['checked'].coverage==0
    checks.consumed('newcomer',new['newcomer']);checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())
    assert len(retired)==SOURCE_COUNT+len(PATHS) and len(set(retired))==len(retired)


@pytest.mark.parametrize('fault',('missing-source','reordered-source','duplicate-receipt','late-source','wrong-first',
    'wrong-old-counter','repeated-arm','missing-preparation'))
def test_distinct_source_history_and_migration_preconditions_are_mandatory(fault):
    checks,profile,_,_,_=fixture()
    if fault=='missing-source':checks.sources.pop()
    elif fault=='reordered-source':checks.sources.reverse()
    elif fault=='late-source':checks.sources[-1].meta_tick=profile['original'].prediction_tick
    elif fault=='wrong-first':checks.original=checks.sources[1]
    elif fault=='missing-preparation':checks.prepared_labels.pop()
    elif fault=='repeated-arm':checks.arm(profile)
    elif fault=='wrong-old-counter':
        value=checks.value
        checks.value=lambda source:(3,(7,1,4,0)) if source is checks.original else value(source)
    else:
        source=checks.sources[0];checks.sources=[];checks.saved_metadata=[]
        checks.retain_source(source)
        alias=NS(token=source.token,prediction_tick=200,meta_tick=204)
        with pytest.raises(AssertionError):checks.retain_source(alias)
        assert checks.coverage.groups['checked'].coverage==0
        return
    state=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError) as first:checks.arm(profile)
    assert checks.pipeline.model.sources.tage.state()==state and checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value


@pytest.mark.parametrize('fault',('reset','reread','wrong-port','both-ports','wrong-row','wrong-tag',
    'wrong-counter','invalid-entry','proposal-before-input','proposal-gap','extra-proposal','extra-input'))
def test_bad_observed_burst_latches_first_error_without_repairing_golden(fault):
    checks,_,row,_,_=armed()
    events=observations(checks,row) if fault in ('extra-input','extra-proposal') else None
    if events is None:
        active=deepcopy(row);active['training']['valid']=1
        for index in range(SOURCE_COUNT):checks.capture_state(NS(tick=600+index*2),active)
    actual=deepcopy(row)
    actual['incoming'][1].update(valid=1,bits=deepcopy(checks.proposal))
    tick=608
    if fault=='reset':actual['reset']=1
    elif fault=='reread':actual['reads'][1]['valid']=1
    elif fault=='wrong-port':actual['incoming']=tuple(reversed(actual['incoming']))
    elif fault=='both-ports':actual['incoming'][0].update(valid=1,bits=deepcopy(checks.proposal))
    elif fault=='proposal-before-input':tick=600
    elif fault=='proposal-gap':checks.capture_state(NS(tick=608),actual);tick=612
    elif fault=='extra-input':actual=deepcopy(row);actual['training']['valid']=1;tick=616
    elif fault=='extra-proposal':tick=616
    else:actual['incoming'][1]['bits']['valid' if fault=='invalid-entry' else fault.removeprefix('wrong-')]^=1
    state=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=tick),actual)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==state and checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value


@pytest.mark.parametrize('fault',('missing-fourth','duplicate-origin','wrong-origin','wrong-target','wrong-direction',
    'wrong-enable','reread-outcome','input-gap','unobserved-input','missing-proposal','duplicate-acceptance'))
def test_each_public_acceptance_matches_its_own_original_request(fault):
    checks,_,row,_,_=armed();events=list(observations(checks,row))
    tick,resolution=events[-1]
    if fault=='missing-fourth':events.pop()
    elif fault=='duplicate-origin':events[-1]=(tick,events[0][1])
    elif fault=='wrong-origin':events[-1]=(tick,replace(resolution,origin=None))
    elif fault=='wrong-target':events[-1]=(tick,replace(resolution,branches=(replace(resolution.branches[0],target=TARGET+2),)))
    elif fault=='wrong-direction':events[-1]=(tick,request(checks.sources[-1].token,False,False))
    elif fault=='reread-outcome':events[-1]=(tick,request(checks.sources[-1].token,True,True))
    elif fault=='wrong-enable':checks.pipeline.last_resolution_controls=(tick,(False,)*7)
    elif fault=='input-gap':events[-1]=(tick+2,resolution);checks.input_ticks[-1]+=2
    elif fault=='unobserved-input':checks.input_ticks.pop()
    elif fault=='missing-proposal':checks.proposal_ticks.pop()
    elif fault=='duplicate-acceptance':checks.accepted(tuple(events))
    with pytest.raises(AssertionError):checks.accepted(tuple(events))
    assert checks.coverage.groups['checked'].coverage==0 and not checks.closed


@pytest.mark.parametrize('fault',('before-proposal','old-owner','wrong-row','wrong-tag','invalid-entry',
    'old-snapshot-six','lost-update','saturated-wrap','saturated-backstep','retirement-gap','extra-commit'))
def test_each_current_version_commits_once_with_independently_composed_counter(fault):
    checks,_,row,_,_=armed();accepted(checks,row)
    index=0;way=0
    if fault in ('lost-update','saturated-wrap','saturated-backstep','retirement-gap','extra-commit'):
        stop=SOURCE_COUNT if fault=='extra-commit' else 3 if fault in ('saturated-wrap','saturated-backstep') else 1
        for i in range(stop):checks.write_accepted(way,NS(accepted_tick=610+2*i,value=dict(checks.commit,counter=COMMIT_COUNTERS[i])))
        index=stop
    transfer=NS(accepted_tick=610+2*index,value=dict(checks.commit,counter=COMMIT_COUNTERS[min(index,3)]))
    if fault=='before-proposal':transfer.accepted_tick=608
    elif fault=='old-owner':way=1
    elif fault=='old-snapshot-six':transfer.value['counter']=6
    elif fault=='lost-update':transfer.value['counter']=5
    elif fault=='saturated-wrap':transfer.value['counter']=0
    elif fault=='saturated-backstep':transfer.value['counter']=6
    elif fault=='retirement-gap':transfer.accepted_tick+=2
    elif fault!='extra-commit':transfer.value['valid' if fault=='invalid-entry' else fault.removeprefix('wrong-')]^=1
    with pytest.raises(AssertionError):checks.write_accepted(way,transfer)
    assert not checks.closed and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-last-commit','old-consumer','wrong-history','wrong-counter','wrong-neighbour',
    'missing-repair','extra-repair','missing-neighbour','missing-displaced-key','duplicate-consumer',
    'fourth-metadata-rebased','missing-metadata-snapshot','missing-retained-owner'))
def test_final_consumption_requires_every_effect_neighbour_and_immutable_original(fault):
    checks,_,row,program,retired=armed();accepted(checks,row);new=commit_and_query(checks,program)
    if fault=='missing-last-commit':checks.written.pop()
    elif fault=='old-consumer':new['original']=checks.before['original']
    elif fault=='wrong-history':new['original']=new['newcomer']
    elif fault in ('wrong-counter','wrong-neighbour'):
        value=checks.value
        def corrupted(source):
            if fault=='wrong-counter' and source is new['original']:return (3,(7,0,6,0))
            if fault=='wrong-neighbour' and source is new['newcomer']:return (3,(7,1,5,0))
            return value(source)
        checks.value=corrupted
    elif fault=='missing-repair':checks.pipeline.corrections_for_source=lambda source:()
    elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda source:((source.prediction_tick+2,2),(source.prediction_tick+4,3))
    elif fault=='duplicate-consumer':checks.consumed('original',new['original'])
    elif fault=='fourth-metadata-rebased':checks.saved_metadata[-1]=()
    elif fault=='missing-metadata-snapshot':checks.saved_metadata.pop()
    elif fault=='missing-retained-owner':checks.sources.pop()
    if fault in ('missing-neighbour','missing-displaced-key'):
        absent='newcomer' if fault=='missing-neighbour' else 'blocker'
        for name,source in new.items():
            if name!=absent:checks.consumed(name,source)
        with pytest.raises(AssertionError):checks.finish()
    else:
        with pytest.raises(AssertionError):
            for name in ('original','blocker','newcomer'):checks.consumed(name,new[name])
    assert not retired and not checks.closed and checks.coverage.groups['checked'].coverage==0


def test_burst_case_keeps_timing_concurrency_and_golden_logic_in_support_layers():
    for file in ('bpuverify/bpu/case/direction_burst.py','tests/bpu/testcase/test_direction_burst.py'):
        for node in ast.walk(ast.parse(Path(file).read_text())):
            assert not isinstance(node,(ast.Assert,ast.ClassDef))
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
                assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
