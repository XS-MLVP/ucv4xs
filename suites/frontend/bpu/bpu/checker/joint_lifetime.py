"""Independent semantic obligations on top of the full per-cycle DUT comparison."""
from copy import deepcopy
from dataclasses import dataclass

from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.joint_lifetime import (
    PC,CONDITION,INDIRECT,CONDITION_TARGET,INDIRECT_TARGET,MAIN_WRONG,RULES)


@dataclass(frozen=True)
class JointFact:
    pc:int
    main_condition_taken:bool
    main_indirect_target:int
    qualified_direction:bool|None
    direction_provider:bool
    direction_uses_provider:bool
    target_provider:bool
    indirect_target:int
    target_confidence:int
    middle:tuple
    final:tuple
    repair_stages:tuple


def expect_fact(fact,*,blocked=False):
    selected=(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,'main') if blocked else (
        INDIRECT,INDIRECT_TARGET,Kind.INDIRECT,'indirect-history')
    middle=(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,'main') if blocked else (
        INDIRECT,MAIN_WRONG,Kind.INDIRECT,'main')
    wanted=JointFact(PC,True,MAIN_WRONG,bool(blocked),True,True,True,INDIRECT_TARGET,3,
        middle,selected,(2,) if blocked else (2,3))
    Scoreboard('bpu.joint-late-semantic').check(expected=wanted,actual=fact,
        context=CheckContext('bpu.joint-late-semantic',ScoreboardMode.DIRECT,
            request=dict(point='conditional blocks or releases its original younger target',blocked=blocked)))


class Checks:
    def __init__(self,pipeline,program,coverage,evidence):
        self.pipeline,self.program,self.coverage,self.evidence=pipeline,program,coverage,evidence
        self.sources,self.accepted=[],[]
        self.late_retention=None
        self.closed=False

    def check(self,expected,actual,point):
        self.pipeline.raise_failure()
        self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
            self.pipeline.board.name,ScoreboardMode.DIRECT,request=dict(point=point,accepted=self.accepted)))

    def save(self,source):
        token=self.pipeline.source_token(source)
        sources=self.pipeline.model.sources
        tagged,target=sources.snapshot(token,resolved=True),sources.target_snapshot(token,resolved=True)
        self.check(True,tagged.owner is target.owner is token.history,'both reads have one exact original owner')
        self.check((PC if sources.tage_enabled else None,PC*2 if target.enabled else None),
            (None if tagged.read is None else tagged.read.pc,None if target.read is None else target.read.pc),
            'each original read exists only for its actually enabled source epoch')
        if any(saved[0] is source for saved in self.sources):return token,tagged,target
        self.check(False,any(saved[0].meta_tick==source.meta_tick for saved in self.sources),
            'a receipt cannot be rebound to another public source object')
        self.sources.append((source,tagged,target,deepcopy(source.meta.resolve),
            deepcopy(sources.defined_metadata(token)),deepcopy(sources.defined_ittage_metadata(token))))
        return token,tagged,target

    def retained_state(self):
        sources=self.pipeline.model.sources
        # Prediction frames and the allocation PRNG continue to advance even
        # while learning is disabled. Preserve learned entries, confidence,
        # selectors, pending versions, recency, maintenance and region owners.
        tage,indirect=sources.tage,sources.indirect
        direction=dict(memory=tage.memory,useful=tage.useful,selectors=tage.selectors,
            caches={key:vars(value) for key,value in tage.cache.items()},
            useful_queues={key:vars(value) for key,value in tage.useful_queue.items()},
            accepted=tage.accepted,info=tage.info,mature=tage.mature,offers=tage.offers,
            useful_offers=tage.useful_offers,tick=tage.tick,aging=tage.aging,clear_cursor=tage.clear_cursor)
        target=dict(memory=indirect.memories,caches=[[vars(value) for value in banks] for banks in indirect.caches],
            regions=vars(indirect.regions),learning=indirect.learning,pending=indirect.normal,
            maintenance=indirect.maintenance,clear_start=indirect.clear_start,tick=indirect.tick)
        return deepcopy(direction),deepcopy(target)

    def accepted_feedback(self,source,event,step,enabled):
        tick,resolution=event
        token=self.pipeline.source_token(source)
        self.check(True,tick>source.meta_tick and resolution.origin is token,'accepted input owns exact original receipt')
        wanted=tuple((b.position,b.target,int(b.kind),b.taken,b.wrong) for b in step.branches)
        actual=tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict) for b in resolution.branches if b is not None)
        self.check((PC,wanted),(resolution.pc,actual),'complete declared executed prefix at actual acceptance')
        controls=self.pipeline.last_resolution_controls
        self.check((tick,enabled,enabled),(controls[0],bool(controls[1][2] and controls[1][3]),
            bool(controls[1][2] and controls[1][5])),'both late learning enables at actual input acceptance')
        if not any(b.kind==Kind.INDIRECT for b in step.branches):
            self.check(None,self.pipeline.model.sources.targets.feedback_for(resolution),
                'unexecuted indirect has no target-learning entitlement')
        self.accepted.append(dict(step=step.name,tick=tick,owner=token.sequence,branches=wanted))
        self.evidence['accepted']=self.accepted

    def fact(self,source):
        token,tagged,target=self.save(source)
        values=token.lookup.values()
        slots={values[f'{slot}.position']:slot for slot in range(4) if values.get(f'{slot}.valid')}
        self.check(True,CONDITION in slots and INDIRECT in slots,'one window retains condition and younger indirect')
        slot=slots[CONDITION]
        wanted=dict(tagged.wanted)
        def choice(value):return value.branch.position,value.branch.target,value.branch.kind,value.source
        prediction=target.prediction
        return JointFact(token.pc,bool(values[f'{slot}.taken']),values[f'{slots[INDIRECT]}.target'],
            bool(wanted[f'{slot}.taken']) if wanted.get(f'{slot}.valid') else None,
            bool(wanted[f'{slot}.has_provider']),bool(wanted[f'{slot}.use_provider']),
            prediction.provider is not None,prediction.target//2,prediction.confidence,
            choice(token.middle),choice(tagged.late),tuple(stage for _,stage in self.pipeline.corrections_for_source(source)))

    def selected(self,source,*,blocked=False):
        fact=self.fact(source)
        expect_fact(fact,blocked=blocked)
        self.check(True,source.prediction_tick>self.accepted[-1]['tick'],'fresh consumer after actual learning')
        self.evidence.setdefault('consumers',[]).append(dict(blocked=blocked,prediction_tick=source.prediction_tick,
            metadata_tick=source.meta_tick,fact=dict(fact.__dict__)))
        return fact

    def finish(self):
        self.check(False,self.closed,'one complete joint lifetime')
        self.check(True,len(self.accepted)>=7 and len(self.sources)>=8,'real setup learning and its fresh consumers')
        sources=self.pipeline.model.sources
        for source,tagged,target,actual,metadata,indirect_meta in self.sources:
            token=self.pipeline.source_token(source)
            self.check(True,sources.snapshot(token,resolved=True) is tagged
                and sources.target_snapshot(token,resolved=True) is target,'original selector-time snapshots remain owned and immutable')
            self.check((actual,metadata,indirect_meta),(source.meta.resolve,sources.defined_metadata(token),
                sources.defined_ittage_metadata(token)),'later learning cannot rebase original actual or reference metadata')
        self.coverage.reach('immutable-original-snapshots',sources=len(self.sources))
        self.coverage.finish()
        for source,*_ in self.sources:self.pipeline.retire_source(source.meta_tick)
        self.closed=True
        self.evidence.update(status='PASS',checked=list(RULES),compared=dict(self.pipeline.counts))
