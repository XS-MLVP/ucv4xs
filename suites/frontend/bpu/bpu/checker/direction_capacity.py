"""Retouch at full capacity must forward without evicting another obligation."""
from suites.frontend.bpu.bpu.checker.direction_service import DirectionServiceChecks
from suites.frontend.bpu.bpu.model.tage.service import FULL_RETAINED_RETOUCH,RETAINED_CAPACITY


class DirectionCapacityChecks(DirectionServiceChecks):
    observe_retention=True

    def __init__(self,pipeline,coverage,*,program=FULL_RETAINED_RETOUCH):
        super().__init__(pipeline,coverage,program=program)
        self.expected_offers=()
        self.offered=[]
        self.full_event_tick=None
        self.initial_overflows=None

    def arm(self,sources):
        super().arm(sources)
        self.expected_offers=tuple(tuple(dict(row=read.rows[self.table],valid=1,
            tag=read.entries[self.table][owner].tag,
            counter=max(0,min(7,read.entries[self.table][owner].counter+(-1,1)[owner]))) for owner in range(2))
            for read in (self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read for source in sources))
        self.initial_overflows=self.pipeline.model.sources.tage.cache[self.table,self.bank].overflows

    def capture_state(self,event,row):
        super().capture_state(event,row)
        if self.failure is not None or not self.holding:return
        try:
            self.check(True,len(row['dirty'])==2 and all(len(way)==RETAINED_CAPACITY for way in row['dirty']),
                'actual retained capacity has two complete owner vectors')
            incoming=row['incoming']
            flags=tuple(port['valid'] for port in incoming)
            self.check(True,flags in ((0,0),(1,1)),'both logical owner updates enter together')
            if not any(flags):return
            ordinal=len(self.offered)
            self.check(True,ordinal<len(self.expected_offers),'no extra incoming learning proposal')
            self.check(self.expected_offers[ordinal],tuple(port['bits'] for port in incoming),
                'full incoming payload order derived from the original semantic sources')
            # Fullness is an actual event precondition, not public acceptance.
            if ordinal==RETAINED_CAPACITY:
                self.check(((1,)*RETAINED_CAPACITY,)*2,tuple(tuple(way) for way in row['dirty']),
                    'all eight actual retained entries are dirty at the capacity boundary')
                self.qualify_full_event(ordinal,row)
                self.full_event_tick=event.tick
                for rule in self.rules[:2]:self.coverage.record('reached',rule,event.tick)
            self.offered.append(event.tick)
        except Exception as error:self.failure=error

    def credit_inputs(self,tick):
        # Public acceptance alone proves neither fullness nor retained-key hit.
        pass

    def qualify_full_event(self,ordinal,row):
        self.check(self.expected_offers[0],self.expected_offers[ordinal],'full hit keeps the first logical keys')

    def check_capacity_effect(self):
        self.check(self.initial_overflows,self.pipeline.model.sources.tage.cache[self.table,self.bank].overflows,
            'no overwritten dirty obligation is allowed in this semantic program')

    def pending(self):
        self.raise_failure()
        self.check(len(self.expected_offers),len(self.offered),'every source produced exactly one complete retained proposal')
        self.check(True,self.full_event_tick is not None,'an actual full-capacity event is mandatory')
        self.check_capacity_effect()
        super().pending()
