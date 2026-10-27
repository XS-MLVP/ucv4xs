"""No observed metadata seed; all event credit waits for compared consumers."""
from toffee import CheckContext,ScoreboardMode

from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS
from bpuverify.bpu.coverage.direction_forwarding import RULES


class DirectionForwardingChecks:
    def __init__(self,pipeline,coverage):
        self.pipeline,self.coverage=pipeline,coverage
        self.failure=None
        self.sources=()
        self.accepted=()
        self.saturation_source=None
        self.saturation_event=None
        self.closed=False

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected,actual=actual,
                context=CheckContext(self.pipeline.board.name,ScoreboardMode.DIRECT,
                    request=dict(point=point,sources=self.sources,accepted=self.accepted)))
        except Exception as error:
            self.failure=error
            raise

    def values(self,source):
        token=self.pipeline.source_token(source)
        metadata=self.pipeline.model.sources.defined_metadata(token)
        counters,providers=[],[]
        entries=tuple(entry for row in source_entries(token.lookup) for entry in row)
        for position in POSITIONS:
            matches=[(slot,entry) for slot,entry in enumerate(entries) if entry.hit and entry.position==position]
            if not matches:
                counters.append(None);providers.append(None)
                continue
            self.check(1,len(matches),'one logical Main owner per resolved position')
            slot,entry=matches[0]
            counters.append(entry.counter)
            providers.append(metadata.get(f'{slot}.providerTakenCtr_value'))
        return token,(tuple(counters),tuple(providers))

    def prepared(self,source,expected):
        _,values=self.values(source)
        self.check(expected,values,'hand-derived semantic setup effects')

    def owners(self,token):
        read=self.pipeline.model.sources.snapshot(token).read
        result=[]
        for position in POSITIONS:
            matches=read.matches(position)
            self.check(True,bool(matches),'each logical branch retains a provider')
            result.append(matches[-1][:2])
        return tuple(result)

    def arm(self,sources):
        self.check((),self.sources,'forwarding experiment arms once')
        self.check(2,len(sources),'two complete checked prediction sources')
        tokens=tuple(self.values(source)[0] for source in sources)
        self.check(True,tokens[0] is not tokens[1] and tokens[0].history is not tokens[1].history,
            'different prediction/checkpoint owners, not one duplicated receipt')
        self.check(True,sources[0].meta_tick<sources[1].prediction_tick,'both old reads precede either update')
        first=self.pipeline.model.sources.snapshot(tokens[0]).read
        second=self.pipeline.model.sources.snapshot(tokens[1]).read
        self.check(first,second,'distinct requests own identical old semantic TAGE contents')
        for source,token in zip(sources,tokens,strict=True):
            self.prepared(source,((1,2),(2,5)))
            self.check(((3,0),(3,1)),self.owners(token),'two distinct longest-history logical owners')
            metadata=self.pipeline.model.sources.defined_metadata(token)
            for slot,entry in enumerate(tuple(entry for row in source_entries(token.lookup) for entry in row)):
                if entry.hit and entry.position in POSITIONS:
                    self.check((1,0),(metadata[f'{slot}.useProvider'],metadata[f'{slot}.hasAlt']),
                        'strong provider feedback needs no SRAM reread/alternate')
        self.sources=tuple(sources)

    def check_burst(self,events):
        self.check(2,len(self.sources),'arm before submitting actual learning')
        self.check((),self.accepted,'one burst accepted once')
        self.check(2,len(events),'both exact accepted feedback events')
        self.check(events[0][0]+2,events[1][0],'adjacent accepted cycles, not merely queued together')
        for source,(tick,resolution) in zip(self.sources,events,strict=True):
            self.check(True,tick>source.meta_tick,'actual feedback follows its original public metadata')
            token=self.pipeline.source_token(source)
            self.check(True,resolution.origin is token,'accepted input owns its exact original read')
            self.check((PC,((POSITIONS[0],TARGETS[0],1,False,False,0),(POSITIONS[1],TARGETS[1],1,True,False,0))),
                (resolution.pc,tuple((branch.position,branch.target,int(branch.kind),branch.taken,
                    branch.mispredict,int(branch.action)) for branch in resolution.branches if branch is not None)),
                'complete executed NT prefix plus T tail in each accepted input')
        self.accepted=tuple(events)
        controls=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(controls[0],bool(controls[1][2] and controls[1][3])),
            'real adjacent feedback is accepted with both predictors enabled')

    def accepted_burst(self,events):
        self.check_burst(events)
        for rule in RULES[:-1]:self.coverage.record('reached',rule,events[-1][0])

    def consumed(self,source):
        self.check(2,len(self.accepted),'acceptance precedes new forwarded consumer')
        self.check(True,source.prediction_tick>self.accepted[-1][0],'consumer must be a new post-feedback lookup')
        token,values=self.values(source)
        self.check(((0,3),(0,7)),values,'both forwarded updates, not either single old-metadata effect')
        self.check(((3,0),(3,1)),self.owners(token),'forwarding preserves both original logical provider owners')
        for old in self.sources:
            self.check(True,token is not self.pipeline.source_token(old),'old read cannot count as the new consumer')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),
            'complete actual repair window keeps later T consumer without S3 reversal')
        for rule in RULES[:-1]:self.coverage.record('checked',rule,source.meta_tick)
        self.saturation_source=source

    def accepted_saturated(self,event):
        self.check(True,self.saturation_source is not None,'forwarded saturated consumer precedes its new feedback')
        self.check(None,self.saturation_event,'fresh boundary feedback accepted once')
        tick,resolution=event
        self.check(True,tick>self.saturation_source.meta_tick,'fresh boundary acceptance follows public source')
        self.check(True,resolution.origin is self.pipeline.source_token(self.saturation_source),'fresh boundary feedback source')
        self.check((PC,((POSITIONS[0],TARGETS[0],1,False,False,0),(POSITIONS[1],TARGETS[1],1,True,False,0))),
            (resolution.pc,tuple((branch.position,branch.target,int(branch.kind),branch.taken,branch.mispredict,
                int(branch.action)) for branch in resolution.branches if branch is not None)),
            'both fresh saturation directions')
        controls=self.pipeline.last_resolution_controls
        self.check((tick,True),(controls[0],bool(controls[1][2] and controls[1][3])),
            'fresh boundary feedback is not silently disabled')
        self.coverage.record('reached',RULES[-1],tick)
        self.saturation_event=event

    def retained(self,source):
        self.check(True,self.saturation_event is not None,'fresh saturated feedback accepted before boundary readback')
        tick,_=self.saturation_event
        self.check(True,source.prediction_tick>tick,'boundary readback follows actual feedback')
        token,values=self.values(source)
        self.check(((0,3),(0,7)),values,'fresh saturated update neither wraps nor corrupts its neighbor')
        self.check(((3,0),(3,1)),self.owners(token),'saturation preserves both original provider owners')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'retained final consumer repair window')
        self.coverage.record('checked',RULES[-1],source.meta_tick)
        for old in self.sources:self.pipeline.retire_source(old.meta_tick)
        self.closed=True

    def finish(self):
        self.check(True,self.closed,'both adjacent effects and fresh saturation consumer are required')
        self.coverage.finish()
