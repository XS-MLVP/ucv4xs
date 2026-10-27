"""Bound each learned target to its exact independently predicted source."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode

from bpuverify.bpu.coverage.indirect_learning import RULES
from bpuverify.bpu.model.selection import Kind


class IndirectLearningChecks:
    def __init__(self,pipeline,coverage,pc,position,initial,target):
        self.pipeline,self.coverage,self.pc,self.position=pipeline,coverage,pc,position
        self.initial,self.target=initial,target
        self.sources=[];self.metadata=[];self.accepted=[];self.consumers=[];self.closed=False;self.failure=None

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
                self.pipeline.board.name,ScoreboardMode.DIRECT,request=dict(point=point,accepted=self.accepted)))
        except Exception as error:self.failure=error;raise

    def save(self,source):
        token=self.pipeline.source_token(source)
        self.check(self.pc,token.pc,'exact branch source PC')
        self.sources.append(source)
        self.metadata.append(deepcopy(self.pipeline.model.sources.defined_ittage_metadata(token)))
        return token,self.pipeline.model.sources.snapshot(token,resolved=True)

    def accepted_feedback(self,source,event,target):
        token=self.pipeline.source_token(source);tick,resolution=event
        self.check(True,tick>source.meta_tick and resolution.origin is token,'actual input has its original public owner')
        self.check((self.pc,((self.position,target,3,True,True,0),)),
            (resolution.pc,tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict,int(b.action))
                for b in resolution.branches if b is not None)),'complete genuine taken-indirect correction')
        self.check(True,self.pipeline.model.sources.snapshot(token,resolved=True).late.branch.target!=target
            or not self.pipeline.model.sources.snapshot(token,resolved=True).late.branch.taken,
            'backend wrong flag agrees with the original final semantic prediction')
        controls=self.pipeline.last_resolution_controls
        self.check((tick,True),(controls[0],bool(controls[1][2] and controls[1][5])),'Main/ITTAGE actually enabled for feedback')
        self.accepted.append(event)
        ordinal=len(self.accepted)
        self.check(True,ordinal<=4,'one cold discovery, two confidence decrements, one zero-conf retarget')
        self.coverage.record('reached',RULES[0 if ordinal==1 else 4 if ordinal==4 else 2],tick)

    def cold(self,source):
        self.check([],self.sources,'one initial source before learning')
        token,snapshot=self.save(source)
        self.check((None,4),(snapshot.prediction.provider,snapshot.allocation),'independent cold allocation chooses the longest table')
        self.check(False,token.early.branch.taken,'cold source is a genuine fallthrough, not a preinstalled branch')

    def consumed(self,source,*,confidence,main,target,repair):
        self.check(True,bool(self.accepted),'new target consumption follows actual feedback')
        self.check(True,source.prediction_tick>self.accepted[-1][0],'consumer is a fresh post-feedback request')
        token,snapshot=self.save(source);prediction=snapshot.prediction
        self.check((4,None,confidence,0,target*2),
            (prediction.provider,prediction.alternate,prediction.confidence,prediction.useful,prediction.provider_target),
            'independently learned longest provider, exact confidence and full target')
        self.check(None,snapshot.allocation,'longest provider cannot allocate a longer history')
        values=token.lookup.values();branches=tuple(values[f'{slot}.target'] for slot in range(10)
            if values.get(f'{slot}.valid') and values[f'{slot}.position']==self.position)
        self.check((main,),branches,'own Main target is checked independently from ITTAGE')
        self.check((self.position,target,Kind.INDIRECT,True,'indirect-history'),
            (snapshot.late.branch.position,snapshot.late.branch.target,snapshot.late.branch.kind,snapshot.late.branch.taken,snapshot.late.source),
            'associated final S3 selects the independently predicted indirect target')
        expected=((source.prediction_tick+2,2),)+(((source.prediction_tick+4,3),) if repair else ())
        self.check(expected,self.pipeline.corrections_for_source(source),'complete S2/S3 repair window of this exact source')
        self.consumers.append(source)
        if len(self.consumers)==1:self.coverage.record('reached',RULES[1],source.meta_tick)
        if repair:self.coverage.record('reached',RULES[3],source.meta_tick)
        if len(self.consumers)==4:self.coverage.record('reached',RULES[5],source.meta_tick)

    def finish(self):
        self.check((4,4),(len(self.accepted),len(self.consumers)),'every real learning boundary has its own new consumer')
        current=tuple(self.pipeline.model.sources.defined_ittage_metadata(self.pipeline.source_token(source)) for source in self.sources)
        self.check(tuple(self.metadata),current,'old source snapshots remain immutable across target learning')
        tick=self.consumers[-1].meta_tick
        for rule in RULES:self.coverage.record('checked',rule,tick)
        self.coverage.finish()
        for source in self.sources:self.pipeline.retire_source(source.meta_tick)
        self.closed=True
