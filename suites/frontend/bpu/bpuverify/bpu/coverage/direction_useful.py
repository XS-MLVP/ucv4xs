"""Useful learning is not proved by entry-counter writeback or native hits."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('original-provider-correct-against-base','useful-feedback-accepted-beside-predictions',
    'blocked-useful-effects-retained-in-order','fresh-histories-still-see-old-useful',
    'release-commits-every-useful-effect-once','fresh-histories-consume-committed-useful')


def useful_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown useful service status')
    return CoverGroupDef('bpu_owned_direction_useful_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-useful.{status}',
        contract='qualified original sources -> read-blocked useful learning -> old read -> ordered actual service -> new read')


class DirectionUsefulCoverage:
    rules=RULES
    def __init__(self):self.groups={status:useful_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-useful.json')
