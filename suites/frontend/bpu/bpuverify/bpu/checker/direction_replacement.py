"""Non-backpressured full miss supersedes exactly one dirty version per owner."""
from bpuverify.bpu.checker.direction_capacity import DirectionCapacityChecks
from bpuverify.bpu.model.tage.service import FULL_RETAINED_REPLACEMENT,RETAINED_CAPACITY


class DirectionReplacementChecks(DirectionCapacityChecks):
    def __init__(self,pipeline,coverage):
        super().__init__(pipeline,coverage,program=FULL_RETAINED_REPLACEMENT)

    def qualify_full_event(self,ordinal,row):
        for owner in range(2):
            keys=tuple((offer[owner]['row'],offer[owner]['tag']) for offer in self.expected_offers[:ordinal+1])
            self.check(RETAINED_CAPACITY+1,len(set(keys)),
                'full miss names a fifth distinct logical key, not a retained-key hit')
        self.check((0,7),tuple(port['counter'] for port in self.expected_offers[0]),'victim has saturated pending counters')
        self.check((1,6),tuple(port['counter'] for port in self.expected_offers[ordinal]),
            'new key starts from its own old read, not the saturated victim')
        self.check(tuple(dict(valid=1,ready=0,bits=payload) for payload in self.expected_offers[0]),
            tuple(row['writes']),'both actual pending victim versions are saturated before the full miss')

    def check_capacity_effect(self):
        self.check(self.initial_overflows+2,self.pipeline.model.sources.tage.cache[self.table,self.bank].overflows,
            'exactly one dirty obligation per owner is superseded at the full miss')
