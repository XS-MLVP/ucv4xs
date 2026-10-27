"""Current complete identities, not original hints, own accumulated learning."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode
from bpuverify.bpu.checker.direction_capacity import DirectionCapacityChecks
from bpuverify.bpu.model.tage.shared_saturation import PROGRAMS
from bpuverify.bpu.coverage.shared_saturation import RULES


class Checks(DirectionCapacityChecks):
    def __init__(self,pipeline,coverage,program):
        if program not in PROGRAMS:raise ValueError('declared shared learning program required')
        super().__init__(pipeline,coverage,program=program)
        self.counts=[0]*program.history_count;self.boundaries=[];self.records=None
        self.originals=();self.definitions=();self.keys=();self.compared_consumers={}

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
                self.pipeline.board.name,ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,
                request=dict(point=point,program=self.program.name,current_counts=self.counts,
                    actual_proposals=self.offered,actual_boundaries=self.boundaries,last_actual_records=self.records,
                    actual_services=self.written)))
        except Exception as error:self.failure=error;raise

    def arm(self,sources):
        super().arm(sources)
        self.originals=tuple(deepcopy(source.meta) for source in sources)
        self.definitions=tuple(deepcopy(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))) for s in sources)
        by_history={}
        for history,source in zip(self.program.feedback_order,sources,strict=True):
            token=self.pipeline.source_token(source);read=self.pipeline.model.sources.snapshot(token).read
            by_history[history]=tuple((read.rows[self.table],int(read.entries[self.table][owner].valid),
                read.entries[self.table][owner].tag) for owner in range(2))
        self.keys=tuple(by_history[i] for i in range(self.program.history_count))
        self.check(12,len({id(self.pipeline.source_token(s).history) for s in sources}),'all twelve original prediction owners are independent')
        self.coverage.record('reached',RULES[6],sources[-1].meta_tick)

    def originals_unchanged(self):
        self.check(self.originals,tuple(source.meta for source in self.sources),'every original metadata snapshot stays immutable')
        self.check(self.definitions,tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s)) for s in self.sources),
            'independent original definitions are not rebased to new current values')

    def current(self,row):
        self.check(True,self.records is not None and len(self.records)==2 and all(len(owner)==4 for owner in self.records),
            'complete actual current records required')
        expected=set();actual=set()
        for owner,records in enumerate(self.records):
            for rank,record in enumerate(records):
                if row['dirty'][owner][rank]:
                    self.check(1,record['shadow'],'every actual pending record has a valid retained identity')
                    actual.add((owner,record['row'],record['valid'],record['tag']))
        for history,count in enumerate(self.counts):
            if not count:continue
            counters=self.program.counters_after(history,count)
            for owner,key in enumerate(self.keys[history]):
                expected.add((owner,*key))
                matches=[(rank,record) for rank,record in enumerate(self.records[owner])
                    if record['shadow'] and (record['row'],record['valid'],record['tag'])==key]
                self.check(1,len(matches),'each learned complete identity has exactly one current version')
                rank,record=matches[0]
                self.check(counters[owner],record['counter'],'each current counter accumulates only its own earlier accepted feedback')
                self.check(1,row['dirty'][owner][rank],'a numerical boundary cannot cancel an unserviced learning obligation')
        self.check(expected,actual,'all and only independently learned identities remain pending')

    def capture_state(self,event,packet):
        self.records=deepcopy(packet['records']);row=packet['state'];before=len(self.offered)
        super().capture_state(event,row)
        if self.failure is not None or not self.holding:return
        try:
            if len(self.offered)==before:return
            self.current(row);history=self.program.feedback_order[before]
            if self.counts[history]==2:
                self.boundaries.append(dict(history=history,tick=event.tick,original=(2,5),current=(0,7),
                    input_proposal=deepcopy(tuple(p['bits'] for p in row['incoming'])),all_pending=deepcopy(row['dirty'])))
            self.counts[history]+=1
        except Exception as error:self.failure=error

    def pending(self):
        self.raise_failure();self.check((3,)*4,tuple(self.counts),'every independent history really learned three times')
        self.check(set(range(4)),{row['history'] for row in self.boundaries},'all histories actually reach their own lower and upper boundary')
        self.check(4,len(self.boundaries),'one actual hold proposal per original history')
        self.current(self.last[1]);self.originals_unchanged()
        super().pending()
        for rule in RULES[6:]:self.coverage.record('reached',rule,self.pipeline.last_tick)

    def old_consumed(self,source):
        super().old_consumed(source)
        self.compared_consumers['old.'+str(len(self.old_sources)-1)]=dict(prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)

    def new_consumed(self,source):
        # The inherited final-consumer path retires the originals only after
        # all comparisons. Check immutability before that legitimate retirement.
        self.originals_unchanged();super().new_consumed(source)
        self.compared_consumers['new.'+str(len(self.new_sources)-1)]=dict(prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)

    def snapshot(self):
        return deepcopy(dict(program=self.program.name,closed=self.closed,counts=self.counts,
            accepted_ticks=[tick for tick,_ in self.accepted],actual_proposal_ticks=self.offered,
            actual_boundaries=self.boundaries,actual_services=self.written,consumers=self.compared_consumers,
            original_meta_ticks=[s.meta_tick for s in self.sources],original_snapshots_compared=bool(self.originals),
            expected_pending=self.expected_plan,full_FTQ_source_eligibility_proved=False,
            first_failure_type=None if self.failure is None else type(self.failure).__name__,
            first_failure=None if self.failure is None else str(self.failure)))
