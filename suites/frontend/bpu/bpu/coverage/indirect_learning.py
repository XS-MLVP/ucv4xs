"""Existing062: autonomous source, retained target, repair and zero-conf retarget."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('cold-indirect-discovers-owned-provider','new-history-source-consumes-independent-target',
    'nonzero-confidence-feedback-retains-old-target','indirect-target-repairs-opposing-main',
    'zero-confidence-learns-new-target','fresh-retargeted-consumer-agrees-with-main')


def indirect_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown indirect learning status')
    return CoverGroupDef('bpu_owned_indirect_learning_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-indirect-learning.{status}',
        contract='own history/Main/ITTAGE -> actual indirect learning -> source-matched S3 repair -> zero-conf retarget -> fresh consumer')


class IndirectLearningCoverage:
    def __init__(self):self.groups={status:indirect_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-indirect-learning.json')
