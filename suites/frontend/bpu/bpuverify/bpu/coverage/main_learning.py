"""Existing FTQ-learning requirement, now measured as owned hardware events."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES = ('cold-source-learned','main-result-consumed','same-owner-decremented',
         'main-direction-repairs-micro','same-owner-recovered')


def learning_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('unknown owned MainBTB learning status')
    return CoverGroupDef('bpu_owned_main_learning_events_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-main-learning.{status}',
        contract='exact owned public source -> independent MicroBTB/MainBTB learning -> compared source metadata and causal repair')


class MainLearningCoverage:
    def __init__(self):
        self.groups = {status:learning_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,tick):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-main-learning.json')
