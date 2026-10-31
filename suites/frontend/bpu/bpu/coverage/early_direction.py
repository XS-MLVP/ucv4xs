"""Existing 044 learning requirement, split by semantic tag-width class."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

CLASSES=('byte-tag-control','full-tag-high-bits')
RULES=('cold-main-conditional-discovery','owned-ahead-conditional-consumer',
    'original-source-resolved-not-taken','later-direct-discovered-from-new-source',
    'source-qualified-fasttrain','allocation-proved-by-provider-consumption',
    'negative-provider-new-consumer','original-source-unchanged')


def direction_coverage(tag_class,status):
    if tag_class not in CLASSES or status not in ('reached','checked'):
        raise ValueError('unknown owned early direction coverage scope')
    return CoverGroupDef('bpu_owned_early_direction_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-early-direction.{tag_class}.{status}',
        contract='independent full-width tags and original sources -> natural fastTrain -> fresh negative provider receipt')


class EarlyDirectionCoverage:
    def __init__(self,tag_class):self.groups={status:direction_coverage(tag_class,status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-early-direction.json')
