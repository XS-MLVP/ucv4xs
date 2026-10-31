"""Qualify capacity via genuine public sources, not observed entry/victim bits."""
from toffee import CheckContext,Scoreboard,ScoreboardMode

from suites.frontend.bpu.bpu.model.selection import fallthrough


ROLES = {'cold':False,'initial-resident':True,'protect':True,'evicted':False,'new':True,'survivor':True}


class MicroCapacityChecks:
    def __init__(self,checker,program,coverage):
        self.pipeline,self.program,self.coverage = checker,dict(program),coverage
        self.capacity = checker.model.sources.micro.capacity
        if len(program)!=self.capacity+1:
            raise ValueError('capacity program needs exactly capacity plus one unique PC')
        self.initial,self.new_pc = set(tuple(program)[:-1]),tuple(program)[-1]
        self.board = Scoreboard('bpu.micro-capacity')
        self.sources = []
        self.seen = {status:{role:set() for role in ROLES} for status in ('reached','checked')}
        self.protected = self.victim = self.feedback_before = None
        self.admitted = False
        self.failure = None
        self.last_source_tick = -1
        self.planned_protection = None

    def check(self,expected,actual,point,*,source=None):
        if self.failure is not None:
            raise self.failure
        try:
            self.pipeline.raise_failure()
            self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
                sequence_id=None if source is None else source.prediction_tick,
                request=dict(point=point,source=source,reference=self.pipeline.model.sources.micro.state())))
        except Exception as error:
            self.failure = error
            raise

    def _sample_source(self,status,pc,role,tick):
        seen = self.seen[status]
        seen[role].add(pc)
        rules = []
        if role=='initial-resident' and seen[role]==self.initial:
            rules.append('capacity-resident-readback')
        if role=='protect' and status=='reached':
            rules.append('recent-prediction-protected')
        if role=='evicted':rules.append('victim-absent')
        if role=='new':rules.append('new-entry-consumed')
        if role=='survivor':
            if status=='checked' and pc==self.protected:
                rules.append('recent-prediction-protected')
            if seen[role]==self.initial-{self.victim}:
                rules.append('all-other-records-retained')
        if (status=='checked' and self.admitted and seen['evicted']=={self.victim}
                and seen['new']=={self.new_pc} and seen['survivor']==self.initial-{self.victim}):
            rules.append('full-cache-replacement')
        for rule in rules:
            self.coverage.record(status,rule,tick)

    def source(self,source,pc,role):
        if role not in ROLES or pc not in self.program:
            raise ValueError('unknown capacity source PC or semantic role')
        if role in ('initial-resident','protect','survivor') and pc not in self.initial:
            raise ValueError('resident source cannot name the new allocation')
        if role=='survivor' and (not self.admitted or pc==self.victim):
            raise ValueError('survivor needs an accepted replacement and a non-victim PC')
        if role in ('evicted','new') and (not self.admitted or pc!=(self.victim if role=='evicted' else self.new_pc)):
            raise ValueError('replacement consumer must name its exact accepted owner')
        self.check(True,source.prediction_tick>self.last_source_tick,'one increasing genuine source, never reused',source=source)
        if role=='protect':
            self.check(self.planned_protection,pc,'the touched record was the owned victim before lookup',source=source)
        rows = [row for row in self.pipeline.records if row['tick']==source.prediction_tick]
        self.check(1,len(rows),'exact public prediction tick',source=source)
        observed = source.prediction
        if observed.start_pc==pc:
            self._sample_source('reached',pc,role,source.prediction_tick)
        packed = dict(pc=observed.start_pc,target=observed.target,taken=observed.taken,
            position=observed.position,repair2=observed.s2_override,repair3=observed.s3_override)
        self.check(rows[0]['expected']['prediction'],packed,'public source equals autonomous owned presentation',source=source)
        wanted = (self.program[pc][0],1,self.program[pc][1]) if ROLES[role] else (
            fallthrough(pc).branch.target,0,fallthrough(pc).branch.position)
        self.check((pc,*wanted,0,0,pc,source.prediction_tick+4),
            (observed.start_pc,observed.target,observed.taken,observed.position,observed.s2_override,
                observed.s3_override,source.meta.perf.start_pc,source.meta_tick),
            'program hit/miss and coherent metadata, not final-stage fallthrough',source=source)
        if role=='protect':self.protected = pc
        self._sample_source('checked',pc,role,source.prediction_tick)
        self.sources.append((source.prediction_tick,pc,role))
        self.last_source_tick = source.prediction_tick

    def plan_protection(self,pc):
        micro = self.pipeline.model.sources.micro
        self.check(True,pc in self.initial,'protect an original resident, not a fresh record')
        self.check(micro.victim(),micro._find(pc*2),'touch the independently predicted victim')
        self.planned_protection = pc

    def plan_replacement(self,victim):
        self.check(True,self.protected in self.seen['checked']['protect'],'a real prediction protects this owner')
        self.check(self.initial,self.seen['checked']['initial-resident'],'every capacity record publicly consumed')
        self.check(True,victim in self.initial and victim!=self.protected,'recent prediction changes the owned victim')
        micro = self.pipeline.model.sources.micro
        self.check(self.capacity,sum(bool(entry.confidence) for entry in micro.entries),'all live before replacement')
        self.victim,self.feedback_before = victim,self.pipeline.counts['feedback']

    def replacement_accepted(self):
        self.check(self.feedback_before+1,self.pipeline.counts['feedback'],'exactly one real replacement feedback accepted')
        self.check(True,self.pipeline.last_resolution is not None,'checked accepted feedback, not a planned phase')
        tick,resolution = self.pipeline.last_resolution
        target,position = self.program[self.new_pc]
        self.check((self.new_pc,((target,position,2,True,True,0),)),
            (resolution.pc,tuple((branch.target,branch.position,int(branch.kind),branch.taken,branch.mispredict,
                int(branch.action)) for branch in resolution.branches if branch is not None)),
            'complete accepted replacement outcome')
        micro = self.pipeline.model.sources.micro
        self.check((True,True,False),(micro._find(self.new_pc*2) is not None,micro._find(self.protected*2) is not None,
            micro._find(self.victim*2) is not None),'owned update has one new owner and no protected eviction')
        self.admitted = True
        self.coverage.record('reached','full-cache-replacement',tick)

    def finish(self):
        self.check(True,self.admitted,'real replacement required')
        self.check(self.capacity*3+3,len(self.sources),'complete capacity/readback/replacement source count')
        self.coverage.finish()
