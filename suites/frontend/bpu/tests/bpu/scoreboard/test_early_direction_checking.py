"""Projection mutation and complete pure-program closure; no DUT coverage credit."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.early_direction import live_values,fast_values
from bpuverify.bpu.checker.early_direction_learning import EarlyDirectionChecks
from bpuverify.bpu.coverage.early_direction import EarlyDirectionCoverage,RULES
from bpuverify.bpu.env.early_direction import EarlyDirectionProgram
from bpuverify.bpu.model.pipeline import Redirect,Resolution,Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.main_sources import source_entries
from tests.bpu.scoreboard.test_early_direction_sources import prepare


def raw_metadata(prediction,end=None):
    frame=prediction.frame
    providers=(None,)*4 if frame is None else frame.providers()
    entries=[]
    for way,(base,provider) in enumerate(zip(prediction.bases,providers,strict=True)):
        position=0 if frame is None else frame.positions[way]
        valid=base.valid and base.kind==1 and not prediction.redirect_bubble
        entries.append(dict(valid=int(valid and (end is None or position<=end)),base=int(base.taken),
            strong=int(base.strong),position=position,hit=int(base.valid and provider is not None),
            predicted=int(provider is not None and frame.read.entries[provider].counter>=4),
            provider=0 if provider is None else provider,counter=0 if provider is None else frame.read.entries[provider].counter))
    return dict(entries=tuple(entries),indices=(0,0) if frame is None else frame.read.indices,
        history=(0,)*19 if frame is None else frame.context.folds)


def actual_live(sources,enabled):
    prediction=sources.current_short(enabled);frame=prediction.frame
    providers=(None,)*4 if frame is None else frame.providers()
    return dict(meta=raw_metadata(prediction),hits=tuple(int(provider is not None) for provider in providers),
        useful=tuple(tuple(table.get(index,0) for index in range(512)) for table in sources.short.useful),
        taken=tuple(int(provider is not None and frame.read.entries[provider].counter>=4) for provider in providers))


def actual_fast(sources,cycle):
    token=cycle.tokens[2]
    if token is None:return dict(valid=0)
    branch=cycle.decisions[2].branch;saved=sources.short_snapshot(token)
    return dict(valid=1,pc=token.pc,position=branch.position,taken=int(branch.taken),kind=int(branch.kind),
        meta=raw_metadata(saved.prediction,saved.end_position))


class Program:
    def __init__(self,pc=0x40000000):
        self.model,self.event,self.anchor,original=prepare(pc)
        self.pc=original.pc;self.tick=1000;self.retired=[]
        cold=next(token for token in self.model.published.values() if token.pc==self.pc and token.lookup is not None
            and not any(entry.hit for row in source_entries(token.lookup) for entry in row))
        self.checks=self.make_checks(self.pc,'byte-tag-control' if pc==0x40000000 else 'full-tag-high-bits')
        self.checks.pipeline=NS(model=self.model,board=Scoreboard('short-direction-contract'),raise_failure=lambda:None,
            source_token=lambda source:source.token,retire_source=self.retired.append)
        self.cold=NS(token=cold,prediction_tick=20,meta_tick=24)
        self.original=NS(token=original,prediction_tick=40,meta_tick=44)
        self.checks.accepted(self.cold,(26,self.feedback(cold,2,Kind.CONDITIONAL,True)),'cold')
        self.checks.ahead_consumer(self.original)

    def make_checks(self,pc,tag_class):
        return EarlyDirectionChecks(EarlyDirectionCoverage(tag_class),pc)

    def feedback(self,token,position,kind,taken):
        return Resolution(token.history,self.pc,(Outcome(position,self.pc,kind,taken,mispredict=True),),origin=token)

    def step(self,event=None):
        event=self.event if event is None else event;cycle=self.model.evaluate(event);self.tick+=2
        self.checks.candidates({},event,cycle,self.model,'synthetic',None)
        self.checks.reached(self.tick)
        expected,actual=live_values(self.model.sources,cycle.enabled[1],actual_live(self.model.sources,cycle.enabled[1]))
        assert expected==actual
        expected,actual=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        assert expected==actual
        self.model.advance(event);self.checks.checked(self.tick)
        return cycle

    def quiet(self):
        idle=replace(self.event,prediction_ready=False)
        for _ in range(128):
            self.step(idle)
            if self.model.stages[1:]==(None,None) and not self.model.sources.main_pending():return idle
        raise AssertionError('independent early direction learning did not quiesce')

    def resolve(self,source,position,kind,taken,phase):
        idle=self.quiet();request=self.feedback(source.token,position,kind,taken)
        self.step(replace(idle,feedback=request));accepted=self.tick
        self.quiet();self.checks.accepted(source,(accepted,request),phase)

    def query(self,source):
        idle=self.quiet();self.step(replace(idle,redirect=Redirect(source.token.history,self.pc+4,self.pc,True)))
        for _ in range(32):
            token=self.step().metadata
            if token is not None and token.pc==self.pc:
                result=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick)
                self.quiet();return result
        raise AssertionError('fresh fallback owner did not retire')

    def learned(self):
        self.resolve(self.original,2,Kind.CONDITIONAL,False,'not-taken')
        fallback=self.query(self.original)
        self.resolve(fallback,4,Kind.DIRECT,True,'fallback')
        idle=self.quiet();self.step(replace(idle,redirect=Redirect(fallback.token.history,self.pc+4,self.pc,True)))
        for _ in range(256):
            token=self.step().metadata
            if token is None or token.pc!=self.pc:continue
            values=self.model.sources.short_snapshot(token).prediction.values()
            if any(values.get(f'{way}.valid') and values.get(f'{way}.hit') and not values.get(f'{way}.taken') for way in range(4)):
                result=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick)
                self.quiet();return result
        raise AssertionError('independently learned NT provider did not reach a fresh receipt')


@pytest.mark.parametrize('pc',(0x40000000,0x40000800))
def test_complete_owned_program_requires_new_provider_receipt_before_checked_credit(pc):
    program=Program(pc);consumer=program.learned();checks=program.checks
    assert checks.coverage.groups['checked'].coverage==0 and not program.retired
    if pc==0x40000800:
        frame=program.model.sources.short_snapshot(consumer.token).prediction.frame
        assert any(entry.valid and entry.tag>=256 for entry in frame.read.entries)
    checks.negative_consumer(consumer);checks.finish()
    assert checks.closed and len(program.retired)==4
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('valid','hit','base','strong','position','predicted','provider','counter','indices','history','raw-hit','correction'))
def test_actual_validity_cannot_hide_wrong_live_provider_or_metadata(fault):
    program=Program();program.learned();sources=program.model.sources
    actual=actual_live(sources,True)
    way=next(way for way,entry in enumerate(actual['meta']['entries']) if entry['valid'] and entry['hit'])
    if fault in ('indices','history'):
        values=list(actual['meta'][fault]);values[0]^=1;actual['meta'][fault]=tuple(values)
    elif fault in ('raw-hit','correction'):
        field='hits' if fault=='raw-hit' else 'taken';values=list(actual[field]);values[way]^=1;actual[field]=tuple(values)
    else:actual['meta']['entries'][way][fault]^=1
    expected,observed=live_values(sources,True,actual)
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=expected,actual=observed)


@pytest.mark.parametrize('fault',('valid','pc','position','taken','kind','source-valid','source-base','source-hit','source-position','indices','history'))
def test_fasttrain_uses_original_qualified_metadata_not_live_source(fault):
    program=Program();program.learned()
    for _ in range(32):
        cycle=program.model.evaluate(program.event)
        if cycle.metadata is not None and program.model.sources.short_feedback(cycle.metadata,cycle.decisions[2]) is not None:break
        program.step()
    else:raise AssertionError('no original fastTrain owner')
    actual=actual_fast(program.model.sources,cycle)
    values=program.model.sources.defined_short_metadata(cycle.metadata)
    way=next(way for way in range(4) if f'{way}.position' in values)
    if fault.startswith('source-'):actual['meta']['entries'][way][fault.removeprefix('source-')]^=1
    elif fault in ('indices','history'):
        values=list(actual['meta'][fault]);values[0]^=1;actual['meta'][fault]=tuple(values)
    else:actual[fault]^=1
    expected,observed=fast_values(program.model.sources,cycle,actual)
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=expected,actual=observed)


@pytest.mark.parametrize('fault',('origin','tick','empty','position','kind','taken','target','mispredict','action'))
def test_wrong_resolution_latches_first_failure_without_checked_coverage(fault):
    program=Program();source=program.original;checks=program.checks
    request=program.feedback(source.token,2,Kind.CONDITIONAL,False);tick=1002
    if fault=='origin':request=replace(request,origin=None)
    elif fault=='tick':tick=source.meta_tick
    elif fault=='empty':request=replace(request,branches=())
    else:
        from bpuverify.bpu.model.selection import StackAction
        field,value={'position':('position',3),'kind':('kind',Kind.DIRECT),'taken':('taken',True),
            'target':('target',program.pc+2),'mispredict':('mispredict',False),'action':('action',StackAction.CALL)}[fault]
        request=replace(request,branches=(replace(request.branches[0],**{field:value}),))
    with pytest.raises(AssertionError) as first:checks.accepted(source,(tick,request),'not-taken')
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-consumer','no-allocation','too-early','stale-original','no-fallback'))
def test_incomplete_proof_cannot_receive_final_checked_credit(fault):
    program=Program();consumer=program.learned();checks=program.checks
    if fault=='no-consumer':
        with pytest.raises(AssertionError):checks.finish()
    else:
        if fault=='no-allocation':checks.allocations.clear()
        elif fault=='too-early':consumer=NS(token=consumer.token,prediction_tick=checks.accepted_ticks[-1],meta_tick=consumer.meta_tick)
        elif fault=='no-fallback':checks.fallback=None
        else:checks.old_snapshot=replace(checks.old_snapshot,end_position=15)
        with pytest.raises(AssertionError):
            checks.negative_consumer(consumer);checks.finish()
    assert checks.coverage.groups['checked'].coverage==0 and not program.retired


async def test_wait_delivery_retains_qualified_token_if_monitor_advances_before_resume():
    token=NS(pc=123,sequence=7);checker=NS(last_cycle=NS(metadata=token),s1_accepts={7:90},source_token=lambda _:token)
    calls=[]
    async def wait(name,condition,**kwargs):
        assert condition(checker)
        checker.last_cycle=NS(metadata=None)
    async def transaction(**kwargs):calls.append(kwargs);return 'receipt'
    async def pause():pass
    env=object.__new__(EarlyDirectionProgram);env.pc=123;env.checker=checker
    env.observation=NS(wait=wait);env.agent=NS(next_transaction=transaction);env.pause=pause
    assert await env.consume('event',lambda item:item is token)=='receipt'
    assert calls==[dict(start_pc=123,after_tick=89)]
