"""Close learning obligations only after a fresh, independently checked receipt."""
from toffee import CheckContext,ScoreboardMode
from suites.frontend.bpu.bpu.coverage.early_direction import RULES
from suites.frontend.bpu.bpu.model.main_sources import source_entries


class EarlyDirectionChecks:
    completion_rules=RULES
    fallback_position = 4
    def __init__(self,coverage,pc):
        self.coverage,self.pc=coverage,pc
        self.conditional_position=2+(pc&8)
        self.fallback_position+=(pc&8)
        self.pipeline=None
        self.cold=self.original=self.fallback=self.consumer=None
        self.old_snapshot=None
        self.accepted_ticks=[]
        self.reached_rules=set()
        self.allocations=set()
        self.pending_fast=False
        self.failure=None
        self.closed=False

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,pc=self.pc,accepted=self.accepted_ticks,allocations=self.allocations)))
        except Exception as error:self.failure=error;raise

    def mark(self,rule,tick):
        self.check(False,self.closed,'coverage cannot advance after closure')
        if rule not in self.reached_rules:self.coverage.record('reached',rule,tick);self.reached_rules.add(rule)

    def accepted(self,source,event,phase):
        token=self.pipeline.source_token(source);tick,resolution=event
        self.check(True,resolution.origin is token and tick>source.meta_tick,'exact original owned feedback')
        branches=tuple(branch for branch in resolution.branches if branch is not None)
        self.check(1,len(branches),'one complete discovery or direction resolution')
        branch=branches[0]
        expected={'cold':(self.conditional_position,1,True),'not-taken':(self.conditional_position,1,False),'fallback':(self.fallback_position,2,True)}[phase]
        self.check((*expected,self.pc,True,0),
            (branch.position,int(branch.kind),branch.taken,branch.target,branch.mispredict,int(branch.action)),
            'semantic branch outcome, not a table update command')
        self.check(self.pc,token.pc,'one declared program PC')
        self.check(True,not self.accepted_ticks or tick>self.accepted_ticks[-1],'ordered feedback acceptance')
        if phase=='cold':
            self.check(None,self.cold,'single cold discovery')
            self.check(False,any(entry.hit for row in source_entries(token.lookup) for entry in row),'genuine own Main miss')
            self.cold=source;rule=RULES[0]
        elif phase=='not-taken':
            self.check(True,self.original is source,'direction resolution was declared before driving')
            self.check(self.old_snapshot,self.pipeline.model.sources.short_snapshot(token),'original source is immutable')
            rule=RULES[2]
        else:
            self.check(None,self.fallback,'single later-branch discovery')
            self.check(True,self.original is not None and source.prediction_tick>self.accepted_ticks[-1],
                'later fallback comes from a new post-resolution request')
            self.check(False,any(entry.hit and entry.position==self.fallback_position for row in source_entries(token.lookup) for entry in row),
                'later branch genuinely absent before discovery')
            self.fallback=source;rule=RULES[3]
        self.accepted_ticks.append(tick);self.mark(rule,tick)

    def ahead_consumer(self,source):
        self.check(None,self.original,'single original ahead consumer')
        self.check(True,self.cold is not None,'Main discovery precedes Ahead learning')
        token=self.pipeline.source_token(source)
        self.check((self.pc,'ahead',self.conditional_position,1,True),
            (token.pc,token.early.source,token.early.branch.position,int(token.early.branch.kind),token.early.branch.taken),
            'a new real Ahead conditional consumer')
        self.check(True,source.prediction_tick>self.accepted_ticks[0],'new owned source after discovery')
        self.original=source;self.old_snapshot=self.pipeline.model.sources.short_snapshot(token)
        self.mark(RULES[1],source.meta_tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        token=cycle.metadata
        self.pending_fast=False
        if token is not None and token.pc==self.pc:
            feedback=model.sources.short_feedback(token,cycle.decisions[2])
            self.pending_fast=feedback is not None and any(source.valid and source.position==self.conditional_position for source in feedback.sources)
        return ()

    def reached(self,tick,*candidates):
        if self.pending_fast:self.mark(RULES[4],tick)

    def checked(self,tick,*candidates):
        # These are expected learning effects, NOT coverage credit on their own.
        for table,index,before,after,role in self.pipeline.model.sources.short.effects:
            if role=='allocate':self.allocations.add((table,index))

    def negative_consumer(self,source):
        self.check(None,self.consumer,'single fresh negative provider consumer')
        self.check(True,self.fallback is not None,'conditional and later branch were independently discovered')
        token=self.pipeline.source_token(source);snapshot=self.pipeline.model.sources.short_snapshot(token)
        values=snapshot.prediction.values()
        ways=[way for way in range(4) if values.get(f'{way}.valid') and values.get(f'{way}.hit')
            and values.get(f'{way}.position')==self.conditional_position and not values.get(f'{way}.taken')]
        self.check(True,bool(ways),'fresh owned valid conditional has an independently learned NT provider')
        self.check(True,source.prediction_tick>self.accepted_ticks[-1],'provider consumer follows later discovery')
        for way in ways:
            provider=values[f'{way}.provider'];index=snapshot.prediction.frame.read.indices[provider]
            self.check(True,(provider,index) in self.allocations,'provider belongs to a real learned allocation')
        self.check(False,token.early.branch.position==self.conditional_position and token.early.branch.taken,'negative provider cannot select the early conditional')
        self.consumer=source
        self.mark(RULES[5],source.meta_tick);self.mark(RULES[6],source.meta_tick)

    def finish(self,*,completion_tick=None):
        self.check(False,self.closed,'single final closure')
        self.check(True,self.consumer is not None,'actual new S3 receipt, not just an expected allocation')
        original=self.pipeline.source_token(self.original)
        self.check(self.old_snapshot,self.pipeline.model.sources.short_snapshot(original),'later training cannot rebase original source')
        tick=self.consumer.meta_tick if completion_tick is None else completion_tick
        self.check(True,tick>=self.consumer.meta_tick,'closure cannot precede its actual consumer')
        self.mark(RULES[7],tick)
        self.check(set(self.completion_rules),self.reached_rules,'all source learning and consumer obligations')
        self.check(False,self.pipeline.model.sources.main_pending(),'logical source learning has matured')
        for source in (self.cold,self.original,self.fallback,self.consumer):self.pipeline.retire_source(source.meta_tick)
        for rule in self.completion_rules:self.coverage.record('checked',rule,tick)
        self.coverage.finish();self.closed=True
