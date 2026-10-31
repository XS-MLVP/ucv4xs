"""Independent programs and corrupted actuals; no DUT/native coverage credit."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest
from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.ahead import live_values,fast_values
from suites.frontend.bpu.bpu.checker.ahead_learning import AheadLearningChecks
from suites.frontend.bpu.bpu.coverage.ahead_learning import AheadLearningCoverage,RULES
from suites.frontend.bpu.bpu.model.ahead_learning import PC,OTHER,NEW_TARGET,EDGES
from suites.frontend.bpu.bpu.model.pipeline import Redirect,Resolution,Outcome
from suites.frontend.bpu.bpu.model.selection import Kind,StackAction
from tests.bpu.scoreboard.test_ahead_sources import prepared,quiet


def metadata(frame,enabled=True):
    return dict(valid=int(enabled and frame is not None and frame.valid),row=0 if frame is None else frame.read.row,
        banks=0 if frame is None else 1<<frame.read.bank,entries=tuple(dict(hit=int(hit),position=e.position,
        kind=e.kind,action=e.action,target_low=e.target) for hit,e in zip((False,)*4 if frame is None else frame.hits,
        (NS(position=0,kind=0,action=0,target=0),)*4 if frame is None else frame.read.entries,strict=True)))


def actual_live(sources,enabled=True):
    frame=sources.ahead.frame
    if frame is None:
        return dict(meta=metadata(None,False),entries=tuple(dict(valid=0) for _ in range(4)),
            micro=tuple(dict(valid=0) for _ in range(4)))
    active=enabled and frame.valid
    entries=[];micro=[]
    for e,hit,counter in zip(frame.read.entries,frame.hits,frame.counters,strict=True):
        entries.append(dict(valid=int(active and hit),taken=int(counter>=2),position=e.position,
            target=(frame.pc//(1<<22))*(1<<22)+e.target,kind=e.kind,action=e.action))
        micro.append(dict(valid=int(active and hit),taken=int(counter>=2),kind=e.kind,strong=int(counter in (0,3))))
    return dict(meta=metadata(frame,enabled),entries=tuple(entries),micro=tuple(micro))


def actual_fast(sources,cycle):
    token,choice=cycle.tokens[2],cycle.decisions[2]
    if token is None:return dict(valid=0)
    saved=sources.snapshot(token);branch=choice.branch
    return dict(valid=1,pc=token.pc,target=branch.target,taken=int(branch.taken),position=branch.position,
        kind=int(branch.kind),action=int(branch.action),meta=metadata(saved.frame,saved.enabled))


def feedback(token,target):
    return Resolution(token.history,token.pc,(Outcome(EDGES[token.pc][0],target,Kind.INDIRECT,True,mispredict=True),)+(None,)*7,origin=token)


class Program:
    """Synthetic observer mirrors callbacks only after independent model steps."""
    def __init__(self):
        self.model,self.event,self.anchor,originals=prepared()
        self.tick=1000;self.retired=[];self.corrections={}
        self.checks=AheadLearningChecks(AheadLearningCoverage())
        self.checks.pipeline=NS(model=self.model,board=Scoreboard('ahead-contract'),raise_failure=lambda:None,
            source_token=lambda source:source.token,retire_source=self.retired.append,
            corrections_for_source=lambda source:tuple(self.corrections.get(source.token.sequence,())))
        for index,token in enumerate(originals):
            source=NS(token=token,prediction_tick=20+20*index,meta_tick=24+20*index)
            self.checks.accepted(source,(source.meta_tick+2,feedback(token,EDGES[token.pc][1])),EDGES[token.pc][1])

    def step(self,events=None,*,after_advance=None):
        events=self.event if events is None else events
        cycle=self.model.evaluate(events);self.tick+=2
        checks=self.checks
        checks.candidates({},events,cycle,self.model,'synthetic',None)
        checks.reached(self.tick)
        for token,stage,repair in ((cycle.tokens[1],2,cycle.middle_repair),(cycle.tokens[2],3,cycle.final_repair)):
            if token is not None and repair:self.corrections.setdefault(token.sequence,[]).append((self.tick,stage))
        wanted,observed=live_values(self.model.sources,cycle.enabled[1],actual_live(self.model.sources,cycle.enabled[1]))
        assert wanted==observed
        expected,actual=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        assert expected==actual
        self.model.advance(events)
        if after_advance is not None:after_advance(self,cycle)
        checks.checked(self.tick)
        return cycle

    def settle(self):
        idle=replace(self.event,prediction_ready=False)
        for _ in range(128):
            self.step(idle)
            if self.model.stages[1:]==(None,None) and not self.model.sources.main_pending():return idle
        raise AssertionError('synthetic independent program did not quiesce')

    def loop(self):
        idle=self.settle();self.step(replace(idle,redirect=Redirect(self.anchor.history,self.anchor.pc+4,PC,True)))
        for _ in range(256):
            cycle=self.step();token=cycle.metadata
            if self.checks.consumed==set(EDGES) and token is not None and token.pc==OTHER and token.early.source=='ahead':
                source=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick)
                self.settle();return source
        raise AssertionError('both real ahead consumers were not independently reached')

    def update(self,source):
        self.checks.updating(source)
        idle=self.settle();request=feedback(source.token,NEW_TARGET)
        self.step(replace(idle,feedback=request));event=self.tick,request
        self.settle();self.checks.accepted(source,event,NEW_TARGET)

    def corrected(self,*,after_advance=None):
        for _ in range(64):
            cycle=self.step(after_advance=after_advance)
            if cycle.metadata is not None and cycle.metadata.pc==NEW_TARGET:
                source=NS(token=cycle.metadata,prediction_tick=self.tick-4,meta_tick=self.tick)
                self.settle();return source
        raise AssertionError('post-replay consumer did not retire')

    def fallback(self,source):
        self.event=replace(self.event,enabled=(False,False,True,False,False,False,False))
        idle=self.settle()
        self.step(replace(idle,redirect=Redirect(source.token.history,source.token.pc+4,PC,True)))
        for _ in range(32):
            cycle=self.step()
            if cycle.metadata is not None and cycle.metadata.pc==PC:
                consumer=NS(token=cycle.metadata,prediction_tick=self.tick-4,meta_tick=self.tick)
                self.settle();return consumer
        raise AssertionError('disabled Main fallback consumer did not retire')


def test_complete_program_compares_original_fasttrain_and_all_targets_before_credit():
    program=Program();old=program.loop()
    before=program.model.sources.snapshot(old.token)
    program.update(old)
    new=program.corrected()
    checks=program.checks
    assert checks.coverage.groups['checked'].coverage==0 and not program.retired
    assert program.model.sources.snapshot(old.token)==before
    checks.final_consumer(new);checks.fallback(program.fallback(new));checks.finish()
    assert checks.closed and len(program.retired)==5
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


def test_ahead_snapshot_is_not_an_ordinary_lookup_at_the_current_pc_history():
    from suites.frontend.bpu.abtb.model.semantic import coordinate
    program=Program();source=program.loop()
    frame=program.model.sources.snapshot(source.token).frame
    assert (frame.read.bank,frame.read.row)!=coordinate(source.token.pc,source.token.history.history%16)


@pytest.mark.parametrize('fault',('valid','target','taken','position','kind','action','meta-hit','meta-position','meta-kind','meta-action','target-low',
    'micro-valid','micro-taken','micro-kind','strong','row','banks','meta-valid'))
def test_actual_validity_cannot_hide_corrupted_live_predictions_or_source_metadata(fault):
    program=Program();program.loop()
    # A held request owns a real ahead hit, independent of these actuals.
    actual=actual_live(program.model.sources)
    way=next(i for i,e in enumerate(actual['entries']) if e['valid'])
    if fault in ('row','banks'):actual['meta'][fault]^=1
    elif fault=='meta-valid':actual['meta']['valid']=0
    elif fault=='target-low':actual['meta']['entries'][way]['target_low']^=1
    elif fault.startswith('meta-'):actual['meta']['entries'][way][fault.removeprefix('meta-')]^=1
    elif fault.startswith('micro-'):actual['micro'][way][fault.removeprefix('micro-')]^=1
    elif fault=='strong':actual['micro'][way]['strong']^=1
    else:actual['entries'][way][fault]^=1
    wanted,observed=live_values(program.model.sources,True,actual)
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=wanted,actual=observed)


@pytest.mark.parametrize('fault',('valid','pc','target','taken','position','kind','action','meta-valid','row','banks','source-hit'))
def test_fasttrain_payload_and_frozen_original_metadata_are_compared_independently(fault):
    program=Program();program.loop()
    for _ in range(16):
        cycle=program.model.evaluate(program.event)
        if cycle.metadata is not None and program.model.sources.fast_feedback(cycle.metadata,cycle.decisions[2]) is not None:break
        program.step()
    else:raise AssertionError('no independently qualified fast feedback')
    actual=actual_fast(program.model.sources,cycle)
    if fault=='meta-valid':actual['meta']['valid']=0
    elif fault in ('row','banks'):actual['meta'][fault]^=1
    elif fault=='source-hit':actual['meta']['entries'][0]['hit']^=1
    else:actual[fault]^=1
    wanted,observed=fast_values(program.model.sources,cycle,actual)
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=wanted,actual=observed)


@pytest.mark.parametrize('fault',('missing-origin','too-early','empty-path','extra-branch','wrong-position','wrong-target','wrong-kind','wrong-direction','wrong-error','wrong-action'))
def test_accepted_learning_has_one_complete_branch_from_its_declared_original(fault):
    program=Program();checks=program.checks
    source=checks.original_sources[PC];request=feedback(source.token,OTHER);tick=source.meta_tick+2
    if fault=='missing-origin':request=replace(request,origin=None)
    elif fault=='too-early':tick=source.meta_tick
    elif fault=='empty-path':request=replace(request,branches=(None,)*8)
    elif fault=='extra-branch':request=replace(request,branches=(request.branches[0],replace(request.branches[0],position=6,mispredict=False)))
    else:
        field,value={'wrong-position':('position',5),'wrong-target':('target',OTHER+2),'wrong-kind':('kind',Kind.DIRECT),
            'wrong-direction':('taken',False),'wrong-error':('mispredict',False),'wrong-action':('action',StackAction.CALL)}[fault]
        request=replace(request,branches=(replace(request.branches[0],**{field:value}),)+(None,)*7)
    checks.learned.clear()
    with pytest.raises(AssertionError) as first:checks.accepted(source,(tick,request),OTHER)
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-both-consumers','wrong-pc','not-ahead','wrong-old-target','duplicate-plan'))
def test_retraining_must_declare_the_actual_old_ahead_source_before_sending(fault):
    program=Program();source=program.loop();checks=program.checks
    if fault=='no-both-consumers':checks.consumed.remove(PC)
    elif fault=='duplicate-plan':checks.updating(source)
    else:
        token=source.token
        if fault=='wrong-pc':token=replace(token,pc=PC)
        else:token=replace(token,early=replace(token.early,**({'source':'micro'} if fault=='not-ahead' else {'branch':replace(token.early.branch,target=PC+2)})))
        checks.pipeline.source_token=lambda _:token
    with pytest.raises(AssertionError):checks.updating(source)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('reloaded-sram','wrong-rematch','duplicate-repair'))
def test_late_correction_preserves_the_original_replay_read_identity(fault):
    program=Program();program.update(program.loop());checks=program.checks
    def corrupt(program,cycle):
        if not cycle.final_repair:return
        frame=program.model.sources.ahead.frame
        if fault=='reloaded-sram':program.model.sources.ahead.frame=replace(frame,read=deepcopy(frame.read))
        elif fault=='wrong-rematch':program.model.sources.ahead.frame=replace(frame,pc=PC)
        else:checks.repair=(program.tick-2,cycle.metadata)
    with pytest.raises(AssertionError):program.corrected(after_advance=corrupt)
    assert not checks.closed and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-repair','old-consumer','wrong-consumer','wrong-read-owner','metadata-rebased','extra-repair','duplicate-consumer'))
def test_post_replay_consumer_and_immutable_original_are_required_before_credit(fault):
    program=Program();old=program.loop();program.update(old);new=program.corrected();checks=program.checks
    if fault=='missing-repair':checks.repair=None
    elif fault=='old-consumer':new=NS(token=new.token,prediction_tick=checks.repair[0],meta_tick=new.meta_tick)
    elif fault=='wrong-consumer':new=old
    elif fault=='wrong-read-owner':checks.replay_read=deepcopy(checks.replay_read)
    elif fault=='metadata-rebased':checks.old_metadata=()
    elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda _:((program.tick,3),)
    else:checks.final_consumer(new)
    with pytest.raises(AssertionError):checks.final_consumer(new)
    assert not checks.closed and not program.retired and checks.coverage.groups['checked'].coverage==0


def test_finish_cannot_credit_missing_qualified_fasttrain_or_consumer_state():
    program=Program();program.update(program.loop());new=program.corrected();checks=program.checks
    checks.final_consumer(new);checks.fast.remove(PC)
    with pytest.raises(AssertionError):checks.finish()
    assert not program.retired and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-new-consumer','old-consumer','still-enabled','wrong-main','extra-repair','duplicate'))
def test_disabled_fallback_requires_a_fresh_owner_and_exact_main_repair(fault):
    program=Program();program.update(program.loop());new=program.corrected();checks=program.checks
    checks.final_consumer(new);consumer=program.fallback(new)
    if fault=='missing-new-consumer':checks.new_source=None
    elif fault=='old-consumer':consumer=NS(token=consumer.token,prediction_tick=new.meta_tick,meta_tick=consumer.meta_tick)
    elif fault=='still-enabled':
        saved=program.model.sources.snapshot(consumer.token)
        program.model.sources.ahead_reads[consumer.token.history.sequence]=replace(saved,enabled=True)
    elif fault=='wrong-main':
        token=replace(consumer.token,middle=replace(consumer.token.middle,branch=replace(consumer.token.middle.branch,target=PC)))
        checks.pipeline.source_token=lambda _:token
    elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda _:((consumer.prediction_tick+2,2),(consumer.prediction_tick+4,3))
    else:checks.fallback(consumer)
    with pytest.raises(AssertionError):checks.fallback(consumer)
    assert not checks.closed and not program.retired and checks.coverage.groups['checked'].coverage==0


def test_case_and_reference_do_not_import_signal_access_or_schedule_framework_tasks():
    for file in ('bpu/case/ahead_learning.py','tests/bpu/testcase/test_ahead_learning.py','bpu/model/ahead_sources.py'):
        for node in ast.walk(ast.parse(Path(file).read_text())):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
                assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','memory_signal'}
