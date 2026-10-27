"""Semantic path collisions and delayed-source counter ownership, without RTL."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import ast
import pytest
from types import SimpleNamespace as NS
from toffee import Scoreboard
from bpuverify.bpu.checker.direction_migration import DirectionMigrationChecks
from bpuverify.bpu.coverage.direction_migration import DirectionMigrationCoverage
from bpuverify.bpu.model.pipeline import Outcome,Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.tage.migration import PC,POSITION,TARGET,PATHS,preparation
from tests.bpu.scoreboard.test_direction_sources import prepared,quiet
from tests.bpu.scoreboard.test_direction_service import via


def values(model,source):
    entries=tuple(entry for row in source_entries(source.lookup) for entry in row)
    entry,=tuple(entry for entry in entries if entry.hit and entry.position==POSITION)
    read=model.sources.snapshot(source).read
    matches=() if read is None else read.matches(POSITION)
    return entry.counter,None if not matches else matches[-1]


def request(source,taken,wrong):
    return Resolution(source.history,PC,(Outcome(POSITION,TARGET,Kind.CONDITIONAL,taken,mispredict=wrong),),origin=source)


def migration_program(original_way=1,*,retained_sources=None):
    model,event,anchor=prepared();original=None
    for step in preparation(original_way):
        idle=quiet(model,event)
        if event.enabled[3]!=step.tage_enabled:
            event=replace(event,enabled=tuple(step.tage_enabled if index==3 else value for index,value in enumerate(event.enabled)))
            for _ in range(3):model.advance(replace(idle,enabled=event.enabled))
        source=via(model,event,anchor,PATHS[step.context])
        idle=quiet(model,event)
        final=model.sources.snapshot(source,resolved=True).late.branch
        assert step.wrong==(final.taken!=step.taken),(step,final)
        feedback=request(source,step.taken,step.wrong)
        if step.owner is not None:
            f=model.sources.feedback_for(feedback)
            for _ in range(128):
                if model.sources.tage.allocation_at_next_accept(f)==step.owner:break
                model.advance(idle)
            else:raise AssertionError(('independent allocation opportunity not reached',step))
        model.advance(replace(idle,feedback=feedback))
        after=via(model,event,anchor,PATHS[step.context])
        assert values(model,after)==step.expected,(step,values(model,after))
        if step.label=='original':
            original=after
            if retained_sources is not None:
                from bpuverify.bpu.model.tage.stale_burst import SOURCE_COUNT
                retained_sources.append(after)
                for _ in range(SOURCE_COUNT-1):retained_sources.append(via(model,event,anchor,PATHS['original']))
    return model,event,anchor,original


@pytest.mark.parametrize('original_way',(0,1))
def test_three_path_keys_migrate_normally_and_original_strong_feedback_routes_to_current_owner(original_way):
    model,event,anchor,original=migration_program(original_way)
    before={name:via(model,event,anchor,path) for name,path in PATHS.items()}
    reads={name:model.sources.snapshot(token).read for name,token in before.items()}
    assert len({r.context for r in reads.values()})==3 and {r.rows[3] for r in reads.values()}=={122}
    assert values(model,original)==(3,(3,original_way,5,0))
    assert values(model,before['original'])==(2,(3,1-original_way,4,0))
    assert values(model,before['newcomer'])==(2,(3,original_way,5,1))
    assert values(model,before['blocker'])==(2,None)
    old_meta=model.sources.defined_metadata(original)
    feedback=request(original,True,False)
    assert not model.sources.feedback_for(feedback).reread
    model.advance(replace(quiet(model,event),feedback=feedback))
    after={name:via(model,event,anchor,path) for name,path in PATHS.items()}
    assert values(model,after['original'])==(3,(3,1-original_way,5,0))
    assert values(model,after['newcomer'])==(3,(3,original_way,5,1))
    assert values(model,after['blocker'])==(3,None)
    assert model.sources.defined_metadata(original)==old_meta


@pytest.mark.parametrize('original_way',(0,1))
def test_checker_projects_the_semantic_main_target_and_complete_provider(original_way):
    model,event,anchor,original=migration_program(original_way)
    checks=DirectionMigrationChecks(NS(model=model,raise_failure=lambda:None,board=Scoreboard('migration-contract'),
        source_token=lambda source:source.token),DirectionMigrationCoverage(original_way),original_way)
    assert checks.value(NS(token=original))==(3,(3,original_way,5,0))
    for name,path in PATHS.items():
        token=via(model,event,anchor,path)
        assert checks.value(NS(token=token))==values(model,token)


def fixture(original_way=1):
    model,event,anchor,original=migration_program(original_way)
    old=NS(token=original,prediction_tick=100,meta_tick=104)
    profile={name:NS(token=via(model,event,anchor,path),prediction_tick=200+10*i,meta_tick=204+10*i)
        for i,(name,path) in enumerate(PATHS.items())}
    retired=[]
    pipeline=NS(model=model,raise_failure=lambda:None,board=Scoreboard('migration-contract'),
        source_token=lambda source:source.token,last_resolution_controls=(600,event.enabled),retire_source=retired.append,
        corrections_for_source=lambda source:((source.prediction_tick+2,2),))
    checks=DirectionMigrationChecks(pipeline,DirectionMigrationCoverage(original_way),original_way)
    # The independent program above validates every preparation effect. This
    # synthetic callback fixture starts at its completed boundary, not reset.
    checks.prepared_labels=[step.label for step in checks.intents]
    checks.original=old
    checks.original_metadata=tuple(model.sources.defined_metadata(original).items())
    row=dict(reset=0,reads=({'valid':0,'mask':0},{'valid':0,'mask':0}),
        training=dict(valid=0,ready=1),incoming=tuple(dict(valid=0,bits={}) for _ in range(2)))
    return checks,profile,row,(model,event,anchor),retired


def armed(original_way=1):
    checks,profile,row,program,retired=fixture(original_way)
    checks.arm(profile)
    return checks,profile,row,program,retired


def accepted(checks,row):
    active=deepcopy(row);active['training']['valid']=1
    checks.capture_state(NS(tick=600),active)
    proposal=deepcopy(row)
    proposal['incoming'][checks.original_way].update(valid=1,bits=deepcopy(checks.proposal))
    checks.capture_state(NS(tick=608),proposal)
    checks.accepted((600,request(checks.original.token,True,False)))


def commit_and_query(checks,program):
    checks.write_accepted(1-checks.original_way,NS(accepted_tick=610,value=deepcopy(checks.commit)))
    model,event,anchor=program
    model.advance(replace(quiet(model,event),feedback=request(checks.original.token,True,False)))
    return {name:NS(token=via(model,event,anchor,path),prediction_tick=650+10*i,meta_tick=654+10*i)
        for i,(name,path) in enumerate(PATHS.items())}


@pytest.mark.parametrize('original_way',(0,1))
def test_all_six_rules_require_old_proposal_new_commit_and_each_of_three_fresh_consumers(original_way):
    checks,_,row,program,retired=armed(original_way)
    accepted(checks,row)
    assert checks.coverage.groups['checked'].coverage==0
    new=commit_and_query(checks,program)
    for name in ('original','blocker'):checks.consumed(name,new[name])
    assert not checks.closed and not retired and checks.coverage.groups['checked'].coverage==0
    checks.consumed('newcomer',new['newcomer']);checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values()) and len(retired)==4


@pytest.mark.parametrize('fault',('missing-preparation','missing-original','old-base','old-way','old-counter',
    'current-way','neighbor-useful','blocker-resurrected','history-alias','duplicate-arm'))
def test_old_and_current_timelines_cannot_be_relabelled_into_a_migration(fault):
    checks,profile,_,_,_=fixture()
    if fault=='missing-preparation':checks.prepared_labels.pop()
    elif fault=='missing-original':checks.original=None
    elif fault=='duplicate-arm':checks.arm(profile)
    elif fault=='history-alias':
        original_read=checks.read
        def aliased(source):
            read=original_read(source)
            return replace(read,context=original_read(profile['original']).context) if source is profile['newcomer'] else read
        checks.read=aliased
    else:
        original_value=checks.value
        def corrupted(source):
            value=original_value(source)
            selected=checks.original if fault.startswith('old-') else profile['original'] if fault=='current-way' else profile['newcomer'] if fault=='neighbor-useful' else profile['blocker']
            if source is not selected:return value
            if fault=='old-base':return (1,value[1])
            if fault=='old-way':return (3,(3,0,5,0))
            if fault=='old-counter':return (3,(3,1,4,0))
            if fault=='current-way':return (2,(3,1,4,0))
            if fault=='neighbor-useful':return (2,(3,1,5,0))
            return (2,(3,0,7,0))
        checks.value=corrupted
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError) as first:checks.arm(profile)
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value


@pytest.mark.parametrize('fault',('reread','reset','wrong-port','both-ports','wrong-row','wrong-tag','wrong-counter','invalid-entry','duplicate-proposal'))
def test_bad_actual_proposals_latch_first_error_without_repairing_golden(fault):
    checks,_,row,_,_=armed()
    actual=deepcopy(row)
    actual['incoming'][1].update(valid=1,bits=deepcopy(checks.proposal))
    if fault=='reread':actual['reads'][1]['valid']=1
    elif fault=='reset':actual['reset']=1
    elif fault=='wrong-port':actual['incoming']=tuple(reversed(actual['incoming']))
    elif fault=='both-ports':actual['incoming'][0].update(valid=1,bits=deepcopy(checks.proposal))
    elif fault=='duplicate-proposal':checks.capture_state(NS(tick=608),actual)
    else:actual['incoming'][1]['bits']['valid' if fault=='invalid-entry' else fault.removeprefix('wrong-')]^=1
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=610),actual)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value


@pytest.mark.parametrize('fault',('no-input-proof','wrong-origin','wrong-target','wrong-direction','wrong-enable','reread-outcome'))
def test_acceptance_must_belong_to_the_original_compared_nonreread_source(fault):
    checks,_,row,_,_=armed();active=deepcopy(row);active['training']['valid']=1
    if fault!='no-input-proof':checks.capture_state(NS(tick=600),active)
    feedback=request(checks.original.token,True,False)
    if fault=='wrong-origin':feedback=replace(feedback,origin=None)
    elif fault=='wrong-target':feedback=replace(feedback,branches=(replace(feedback.branches[0],target=TARGET+2),))
    elif fault=='wrong-direction':feedback=replace(feedback,branches=(replace(feedback.branches[0],taken=False),))
    elif fault=='wrong-enable':checks.pipeline.last_resolution_controls=(600,(False,)*7)
    elif fault=='reread-outcome':feedback=replace(feedback,branches=(replace(feedback.branches[0],mispredict=True),))
    with pytest.raises(AssertionError):checks.accepted((600,feedback))
    assert checks.replay_event is None and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('before-proposal','old-owner','old-counter','wrong-tag','wrong-row','invalid-entry','duplicate'))
def test_actual_commit_uses_current_retained_owner_and_latest_counter_not_the_request(fault):
    checks,_,row,_,_=armed();accepted(checks,row)
    transfer=NS(accepted_tick=610,value=deepcopy(checks.commit));owner=0
    if fault=='before-proposal':transfer.accepted_tick=checks.proposal_tick
    elif fault=='old-owner':owner=1
    elif fault=='old-counter':transfer.value['counter']=6
    elif fault=='duplicate':checks.write_accepted(owner,transfer)
    else:transfer.value['valid' if fault=='invalid-entry' else fault.removeprefix('wrong-')]^=1
    with pytest.raises(AssertionError):checks.write_accepted(owner,transfer)
    assert not checks.closed and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-commit','old-consumer','wrong-history','wrong-counter','wrong-useful','missing-repair',
    'extra-repair','missing-neighbour','missing-displaced-key','duplicate-consumer','old-metadata-rebased'))
def test_every_consumer_and_immutable_original_metadata_are_required_before_credit(fault):
    checks,_,row,program,retired=armed();accepted(checks,row);new=commit_and_query(checks,program)
    if fault=='no-commit':checks.written.clear()
    elif fault=='old-consumer':new['original']=checks.before['original']
    elif fault=='wrong-history':new['original']=new['newcomer']
    elif fault in ('wrong-counter','wrong-useful'):
        value=checks.value
        def corrupted(source):
            actual=value(source)
            if fault=='wrong-counter' and source is new['original']:return (3,(3,0,6,0))
            if fault=='wrong-useful' and source is new['newcomer']:return (3,(3,1,5,0))
            return actual
        checks.value=corrupted
    elif fault=='missing-repair':checks.pipeline.corrections_for_source=lambda source:()
    elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda source:((source.prediction_tick+2,2),(source.prediction_tick+4,3))
    elif fault=='duplicate-consumer':checks.consumed('original',new['original'])
    elif fault=='old-metadata-rebased':checks.original_metadata=()
    if fault in ('missing-neighbour','missing-displaced-key'):
        absent='newcomer' if fault=='missing-neighbour' else 'blocker'
        for name,source in new.items():
            if name!=absent:checks.consumed(name,source)
        with pytest.raises(AssertionError):checks.finish()
    else:
        with pytest.raises(AssertionError):
            for name in ('original','blocker','newcomer'):checks.consumed(name,new[name])
    assert not retired and not checks.closed and checks.coverage.groups['checked'].coverage==0


def test_case_keeps_signal_timing_and_task_scheduling_out_of_scenario_code():
    for file in ('bpuverify/bpu/case/direction_migration.py','tests/bpu/testcase/test_direction_migration.py'):
        for node in ast.walk(ast.parse(Path(file).read_text())):
            assert not isinstance(node,(ast.Assert,ast.ClassDef))
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
                assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
