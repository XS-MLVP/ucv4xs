"""Actual owned learning -> opposing-base raw/qualified consumers."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES = ('source-qualified-short-learning','promotion-retains-short-alternate',
    'base-only-update-preserves-tage','owned-raw-middle-consumer',
    'owned-alternate-late-repair','owned-strong-provider-retained')


def direction_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown autonomous direction-learning status')
    return CoverGroupDef('bpu_autonomous_direction_learning_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-learning.{status}',
        contract='owned history/MainBTB/TAGE reads -> exact accepted feedback -> compared metadata and every causal repair')


class DirectionCoverage:
    def __init__(self):self.groups={status:direction_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-directions.json')
