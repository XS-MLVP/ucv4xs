"""Accepted old snapshots remain distinct; pending versions own their effects."""
from bpuverify.bpu.checker.direction_migration import DirectionMigrationChecks
from bpuverify.bpu.model.tage.stale_burst import SOURCE_COUNT,COMMIT_COUNTERS


class DirectionBurstChecks(DirectionMigrationChecks):
    def __init__(self,pipeline,coverage,original_way):
        super().__init__(pipeline,coverage,original_way)
        self.commit_counters=COMMIT_COUNTERS
        self.sources=[]
        self.saved_metadata=[]
        self.proposal_ticks=[]

    def retain_source(self,source):
        self.check(None,self.before,'old sources must be captured before migration qualification')
        self.check(True,len(self.sources)<SOURCE_COUNT,'bounded original-source burst')
        self.check((3,(7,self.original_way,5,0)),self.value(source),'each original source owns old counter5 in the old way')
        if self.sources:
            self.check(True,self.sources[-1].meta_tick<source.prediction_tick,'all old queries are genuine and ordered')
            self.check(self.read(self.sources[0]),self.read(source),'old read contents agree without duplicating a request')
        tokens=[self.pipeline.source_token(s) for s in self.sources]
        token=self.pipeline.source_token(source)
        self.check(True,all(token is not other and token.history is not other.history for other in tokens),
            'distinct original request/checkpoint identities, not repeated receipt aliases')
        self.sources.append(source)
        self.saved_metadata.append(tuple(self.pipeline.model.sources.defined_metadata(token).items()))

    def arm(self,profile):
        self.check(SOURCE_COUNT,len(self.sources),'all old sources must precede any replay acceptance')
        self.check(True,self.sources[0] is self.original,'first captured old source is the declared migration source')
        self.check(True,self.sources[-1].meta_tick<profile['original'].prediction_tick,'every original snapshot predates the current owner')
        super().arm(profile)

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.check(True,self.before is not None,'arm old and current ownership before observation')
            self.check(False,bool(row['reset']),'reset cannot replace an in-flight old-source burst')
            self.check(0,row['reads'][1]['valid'],'every old strong outcome must avoid an SRAM reread')
            if row['training']['valid'] and row['training']['ready']:
                self.check(True,len(self.input_ticks)<SOURCE_COUNT,'no extra public burst input')
                self.input_ticks.append(event.tick)
            ports=row['incoming'];flags=tuple(port['valid'] for port in ports)
            if not any(flags):return
            self.check(tuple(int(way==self.original_way) for way in range(2)),flags,'each proposal preserves the old requested port')
            self.check(True,len(self.proposal_ticks)<SOURCE_COUNT,'no extra internal proposal')
            index=len(self.proposal_ticks)
            self.check(True,index<len(self.input_ticks) and event.tick>self.input_ticks[index],
                'every proposal follows its own observed public acceptance')
            self.check(self.proposal,ports[self.original_way]['bits'],'all proposals derive six from their own old counter five')
            if self.proposal_ticks:self.check(self.proposal_ticks[-1]+2,event.tick,'all old proposals remain adjacent, not hidden serial sends')
            else:self.proposal_tick=event.tick
            self.proposal_ticks.append(event.tick)
            if len(self.proposal_ticks)==SOURCE_COUNT:self.coverage.record('reached',self.rules[2],event.tick)
        except Exception as error:self.failure=error

    def write_accepted(self,way,transfer):
        index=len(self.written)
        self.check(True,index<SOURCE_COUNT and index<len(self.proposal_ticks),'each commit has exactly one compared original proposal')
        self.check(True,transfer.accepted_tick>self.proposal_ticks[index],'commit follows its own proposal')
        if self.written:self.check(self.written[-1][0]+2,transfer.accepted_tick,'unblocked service retires each compared version on adjacent cycles')
        self.check(1-self.original_way,way,'every proposal follows the current retained owner')
        self.check(dict(self.commit,counter=self.commit_counters[index]),transfer.value,
            'current counter composes as 5/6/7/7, never repeated old-snapshot six or wraparound')
        self.written.append((transfer.accepted_tick,way,transfer.value))
        if len(self.written)==SOURCE_COUNT:self.coverage.record('reached',self.rules[3],transfer.accepted_tick)

    def accepted(self,events):
        self.raise_failure()
        self.check(True,self.before is not None,'old owners and migrated state qualified before sending')
        self.check(None,self.replay_event,'one associated old-source burst')
        self.check(SOURCE_COUNT,len(events),'every original request accepted once')
        for index,(source,event) in enumerate(zip(self.sources,events,strict=True)):
            self.checked_outcome(event,source,True,False)
            if index:self.check(events[index-1][0]+2,event[0],'actual public accepts are adjacent')
            self.check(False,self.pipeline.model.sources.feedback_for(event[1]).reread,'old source independently qualifies non-reread learning')
        self.check([event[0] for event in events],self.input_ticks,'all observed accepts match their original owned receipts')
        controls=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(controls[0],bool(controls[1][2] and controls[1][3])),'both predictors actually enabled')
        self.check(SOURCE_COUNT,len(self.proposal_ticks),'all old proposals compared before consumption')
        self.replay_event=tuple(events)
        self.coverage.record('reached',self.rules[1],events[-1][0])

    def check_originals(self):
        self.check(SOURCE_COUNT,len(self.sources),'every original request remains owned until final consumption')
        self.check(SOURCE_COUNT,len(self.saved_metadata),'every original metadata snapshot remains retained')
        for source,metadata in zip(self.sources,self.saved_metadata,strict=True):
            self.check(metadata,tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(source)).items()),
                'every original source remains immutable after all forwarded updates')

    def original_sources(self):return tuple(self.sources)
