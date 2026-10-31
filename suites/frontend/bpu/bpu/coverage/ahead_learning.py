"""Existing 015/019 requirements strengthened by an independent composed oracle."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('normal-main-discovery','fasttrain-original-source','two-ahead-target-consumers',
    'old-read-across-main-update','s3-target-correction','replayed-new-target-consumed','disabled-ahead-main-fallback')


def ahead_learning_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown owned AheadBTB learning status')
    return CoverGroupDef('bpu_owned_ahead_learning_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-ahead-learning.{status}',
        contract='owned Main discovery -> ahead source fastTrain -> two real S1 consumers -> immutable old read -> S3 replay consumer')


class AheadLearningCoverage:
    def __init__(self):self.groups={status:ahead_learning_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-ahead-learning.json')
