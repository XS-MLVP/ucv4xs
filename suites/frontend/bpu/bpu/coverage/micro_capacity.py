"""Capacity and recency obligations; no physical coordinate denominator."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES = ('capacity-resident-readback','recent-prediction-protected','full-cache-replacement',
         'victim-absent','new-entry-consumed','all-other-records-retained')


def capacity_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('unknown MicroBTB capacity status')
    return CoverGroupDef('bpu_micro_capacity_events_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.micro-capacity.{status}',
        contract='genuine fill and prediction touch -> owned full-cache replacement -> exact public eviction/survivor readback')


class MicroCapacityCoverage:
    def __init__(self):
        self.groups = {status:capacity_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,tick):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-micro-capacity.json')
