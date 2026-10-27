"""Qualify original reads, corrected learning and the later real consumer."""
from toffee import CheckContext,ScoreboardMode
from bpuverify.bpu.coverage.ahead_learning import RULES
from bpuverify.bpu.model.ahead_learning import PC,OTHER,NEW_TARGET,EDGES
from bpuverify.bpu.model.main_sources import source_entries


class AheadLearningChecks:
    def __init__(self,coverage):
        self.coverage=coverage
        self.pipeline=None
        self.learned=set();self.fast=set();self.consumed=set();self.reached_rules=set()
        self.old_source=self.old_metadata=self.update=None
        self.repair=None;self.replay_read=None;self.new_source=None
        self.fallback_source=None
        self.pending={}
        self.original_sources={}
        self.failure=None
        self.closed=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
                ScoreboardMode.DIRECT,request=dict(point=point,learned=self.learned,fast=self.fast,
                    consumed=self.consumed,update=self.update,repair=self.repair)))
        except Exception as error:self.failure=error;raise

    def mark(self,rule,tick):
        self.raise_failure()
        if rule not in self.reached_rules:self.coverage.record('reached',rule,tick);self.reached_rules.add(rule)

    def updating(self,source):
        token=self.pipeline.source_token(source)
        self.check(None,self.old_source,'one pre-update original read')
        self.check(set(EDGES),self.consumed,'both natural ahead consumers precede retraining')
        self.check((OTHER,'ahead',PC),(token.pc,token.early.source,token.early.branch.target),'real original ahead target retained')
        self.old_source=source
        self.old_metadata=tuple(self.pipeline.model.sources.defined_metadata(token).items())

    def accepted(self,source,event,target):
        token=self.pipeline.source_token(source);tick,resolution=event
        self.check(True,resolution.origin is token and tick>source.meta_tick,'exact original Main learning request')
        position,wanted_target=EDGES[token.pc]
        branches=tuple(b for b in resolution.branches if b is not None)
        self.check(1,len(branches),'one semantic indirect branch')
        self.check((position,target,3,True,True,0),tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict,int(b.action)) for b in branches)[0],
            'complete Main discovery/update outcome')
        if target==wanted_target:
            self.check(False,token.pc in self.learned,'one genuine discovery per loop edge')
            self.check(False,token.early.branch.taken,'discovery starts from a cold original source')
            self.check(False,any(entry.hit for row in source_entries(token.lookup) for entry in row),'independent Main discovery snapshot is a genuine miss')
            self.learned.add(token.pc)
            self.original_sources[token.pc]=source
            if self.learned==set(EDGES):self.mark(RULES[0],tick)
        else:
            self.check((OTHER,NEW_TARGET),(token.pc,target),'only the declared destination changes')
            self.check(None,self.update,'one destination update')
            self.check(True,self.old_source is source,'update belongs to its pre-declared immutable original source')
            self.check(self.old_metadata,tuple(self.pipeline.model.sources.defined_metadata(token).items()),'learning cannot rebase the original read')
            self.update=event
            self.mark(RULES[3],tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        self.pending={}
        third=cycle.metadata
        if third is not None and third.pc in EDGES and third.early.source=='ahead':
            if self.update is None:
                self.check(EDGES[third.pc],(third.early.branch.position,third.early.branch.target),'both original ahead loop targets')
                self.check(EDGES[third.pc],(cycle.decisions[2].branch.position,cycle.decisions[2].branch.target),'independent Main agrees on the complete old loop')
                self.pending['consumer']=third.pc
        if third is not None and third.pc in EDGES and cycle.enabled[1]:
            feedback=model.sources.fast_feedback(third,cycle.decisions[2])
            if feedback is not None:self.pending['fast']=third.pc
        if (self.update is not None and cycle.final_repair and third.pc==OTHER
                and third.early.source=='ahead' and third.early.branch.target==PC):
            self.check(NEW_TARGET,cycle.decisions[2].branch.target,'new independent Main target repairs old ahead destination')
            self.check(True,model.sources.ahead.replay is not None and model.sources.ahead.replay.valid,'S3 has its original replay read')
            self.pending['repair']=(third,model.sources.ahead.replay.read)
        return ()

    def reached(self,tick,*candidates):pass

    def checked(self,tick,*candidates):
        # Invoked only after the full coherent pipeline/metadata/fastTrain
        # comparison. Final checked coverage still waits for the new receipt.
        if 'consumer' in self.pending:
            self.consumed.add(self.pending['consumer'])
            if self.consumed==set(EDGES):self.mark(RULES[2],tick)
        if 'fast' in self.pending:
            self.fast.add(self.pending['fast'])
            if self.fast==set(EDGES):self.mark(RULES[1],tick)
        if 'repair' in self.pending:
            token,read=self.pending['repair']
            self.check(None,self.repair,'one qualified S3 correction')
            self.repair=(tick,token)
            self.replay_read=read
            frame=self.pipeline.model.sources.ahead.frame
            self.check(True,frame.read is read,'S3 rematches the original read, not current SRAM')
            self.check((NEW_TARGET,False),(frame.pc,any(frame.hits)),'new target must not inherit old tag hits')
            self.mark(RULES[4],tick)

    def final_consumer(self,source):
        self.check(None,self.new_source,'one fresh corrected-target consumer')
        self.check(True,self.repair is not None,'new consumer follows a qualified correction')
        token=self.pipeline.source_token(source)
        self.check(True,source.prediction_tick>self.repair[0],'fresh corrected-target request')
        self.check((NEW_TARGET,'fallthrough',False),(token.pc,token.early.source,token.early.branch.taken),'new target consumes miss, not stale old edge')
        frame=self.pipeline.model.sources.snapshot(token).frame
        self.check(True,frame is not None and frame.read is self.replay_read,'consumer retains the replay lookup owner')
        self.check((),self.pipeline.corrections_for_source(source),'no hidden extra repair of the new miss consumer')
        self.check(self.old_metadata,tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(self.old_source)).items()),
            'original feedback metadata never rebases to new target')
        self.new_source=source
        self.mark(RULES[5],source.meta_tick)

    def fallback(self,source):
        self.check(True,self.new_source is not None,'fallback follows the qualified replay consumer')
        self.check(None,self.fallback_source,'one independently checked disabled consumer')
        token=self.pipeline.source_token(source)
        self.check(True,source.prediction_tick>self.new_source.meta_tick,'fresh lookup after disabling AheadBTB')
        self.check((PC,'fallthrough',False),(token.pc,token.early.source,token.early.branch.taken),'disabled early source cannot leak a stale hit')
        self.check(False,self.pipeline.model.sources.snapshot(token).enabled,'disabled lookup owns invalid ahead metadata')
        self.check(EDGES[PC],(token.middle.branch.position,token.middle.branch.target),'independent Main target remains available')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'exact Main-only S2 fallback repair')
        self.fallback_source=source
        self.mark(RULES[6],source.meta_tick)

    def finish(self):
        self.check(False,self.closed,'single final closure')
        self.check(set(RULES),self.reached_rules,'all normal learning, replay and consumer obligations')
        for states in (self.learned,self.fast,self.consumed):self.check(set(EDGES),states,'both independent edges remain qualified')
        self.check(True,self.new_source is not None,'actual post-correction S3 receipt')
        self.check(True,self.fallback_source is not None,'actual disabled Main fallback receipt')
        self.check(False,self.pipeline.model.sources.main_pending(),'all independent BTB effects have retired')
        for source in (*self.original_sources.values(),self.old_source,self.new_source,self.fallback_source):self.pipeline.retire_source(source.meta_tick)
        for rule in RULES:self.coverage.record('checked',rule,self.fallback_source.meta_tick)
        self.coverage.finish();self.closed=True
