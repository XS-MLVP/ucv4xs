"""Adjacent positive learning must survive a public confidence-depletion probe."""
from toffee import CheckContext,Scoreboard,ScoreboardMode

from suites.frontend.bpu.bpu.model.selection import fallthrough


class MicroForwardingChecks:
    def __init__(self,pipeline,pc,target,position,coverage):
        self.pipeline,self.pc,self.target,self.position = pipeline,pc,target,position
        self.board = Scoreboard('bpu.micro-positive-forwarding')
        self.failure = None
        self.last_source_tick = -1
        self.origins = []
        self.probes = []
        self.accepted = None
        self.coverage = coverage
        self.baseline = self.slot = None

    def check(self,expected,actual,point,*,source=None):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
                sequence_id=None if source is None else source.prediction_tick,
                request=dict(point=point,source=source,reference=self.pipeline.model.sources.micro.state())))
        except Exception as error:
            self.failure = error
            raise

    def source(self,source,*,hit,origin=False,probe=False):
        if type(hit) is not bool or origin and probe:
            raise ValueError('source needs one Boolean prediction intent and a single role')
        self.check(True,source.prediction_tick>self.last_source_tick,'unique increasing source',source=source)
        if probe:
            self.check(True,self.accepted is not None,'accepted adjacent learning precedes proof',source=source)
            self.check(True,len(self.probes)<4,'four distinguishing consumers, no extra proof source',source=source)
            self.check((True,True,True,False)[len(self.probes)],hit,'proof order is fixed by confidence algebra',source=source)
            self.check(True,source.prediction_tick>self.accepted[-1][0],'proof source is newer than both accepts',source=source)
        rows = [row for row in self.pipeline.records if row['tick']==source.prediction_tick]
        self.check(1,len(rows),'exact owned presentation, not a nearby same-PC result',source=source)
        observed = source.prediction
        proof_rule = None
        if probe and len(self.probes)>=2:
            proof_rule = 'three-live-consumers' if len(self.probes)==2 else 'depleted-after-three'
            if observed.start_pc==self.pc:
                self.coverage.record('reached',proof_rule,source.prediction_tick)
        packed = dict(pc=observed.start_pc,target=observed.target,taken=observed.taken,
            position=observed.position,repair2=observed.s2_override,repair3=observed.s3_override)
        self.check(rows[0]['expected']['prediction'],packed,'public source from independently owned token',source=source)
        branch = fallthrough(self.pc).branch
        wanted = (self.target,1,self.position) if hit else (branch.target,0,branch.position)
        self.check((self.pc,*wanted,0,0,self.pc,source.prediction_tick+4),
            (observed.start_pc,observed.target,observed.taken,observed.position,observed.s2_override,
                observed.s3_override,source.meta.perf.start_pc,source.meta_tick),
            'program payload and source metadata',source=source)
        self.last_source_tick = source.prediction_tick
        if origin:self.origins.append(source)
        if probe:
            self.probes.append((source.prediction_tick,hit))
            if proof_rule=='three-live-consumers':
                self.coverage.record('checked',proof_rule,source.prediction_tick)

    def confidence(self):
        model = self.pipeline.model.sources.micro
        slot = model._find(self.pc*2)
        return 0 if slot is None else model.entries[slot].confidence

    def require_weak(self):
        self.check(2,len(self.origins),'two distinct real prediction sources')
        self.check(1,self.confidence(),'independently learned weak entry, no actual counter seed')
        micro = self.pipeline.model.sources.micro
        self.slot = micro._find(self.pc*2)
        self.baseline = tuple(entry.confidence for entry in micro.entries)
        self.check(True,self.pipeline.micro_checked is not None,'native confidence comparison required')
        tick,actual = self.pipeline.micro_checked
        self.check(True,tick>max(source.meta_tick for source in self.origins),'weak state compared after real consumers')
        self.check(self.baseline,actual,'all confidence actuals compared to independently learned weak state')
        self.coverage.record('reached','weak-owner-qualified',tick)
        self.coverage.record('checked','weak-owner-qualified',tick)

    def burst_delivered(self,ticks):
        self.check(True,self.baseline is not None,'qualified weak owner precedes the burst')
        rows = tuple(self.pipeline.resolutions)[-2:]
        self.check(2,len(ticks),'two driver accepts')
        self.check(2,ticks[1]-ticks[0],'driver accepts on adjacent reactor cycles')
        self.check(2,len(rows),'two independently checked real feedback accepts')
        self.check(2,rows[1][0]-rows[0][0],'actual feedback accepts are adjacent')
        expected = (self.pc,((self.target,self.position,2,True,True,0),))
        for _,resolution in rows:
            self.check(expected,(resolution.pc,tuple((branch.target,branch.position,int(branch.kind),branch.taken,
                branch.mispredict,int(branch.action)) for branch in resolution.branches if branch is not None)),
                'both full accepted positive outcomes')
        self.coverage.record('reached','adjacent-same-owner-accepted',rows[-1][0])
        self.coverage.record('checked','adjacent-same-owner-accepted',rows[-1][0])
        self.coverage.record('reached','positive-effects-composed',rows[-1][0])
        self.check(3,self.confidence(),'both positive effects compose before public proof')
        self.check(True,self.pipeline.micro_checked is not None,'settled effect comparison required')
        tick,actual = self.pipeline.micro_checked
        expected = tuple(3 if index==self.slot else value for index,value in enumerate(self.baseline))
        self.check(True,tick>rows[-1][0],'effect comparison follows actual input accepts')
        self.check(expected,actual,'both effects compose without changing another owner')
        self.coverage.record('checked','positive-effects-composed',tick)
        self.accepted = rows

    def finish(self):
        self.check(True,self.accepted is not None,'actual accepted pair required')
        self.check((True,True,True,False),tuple(hit for _,hit in self.probes),
            'two boosts require three real decreases before miss; one lost boost fails early')
        self.check(0,self.confidence(),'reference depleted by actual subsequent consumers')
        self.check(True,self.pipeline.micro_checked is not None,'final depletion was compared')
        tick,actual = self.pipeline.micro_checked
        self.check(True,tick>self.probes[-1][0],'depletion comparison follows the final real probe')
        self.check(0,actual[self.slot],'actual owner is depleted, never seeded into reference')
        self.coverage.record('checked','depleted-after-three',tick)
        self.coverage.finish()
