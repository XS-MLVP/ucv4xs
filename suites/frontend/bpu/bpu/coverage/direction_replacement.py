"""Replacement reachability, discarded-victim isolation and survivor consumers."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.coverage.direction_service import DirectionServiceCoverage

RULES=('all-owner-capacities-occupied','full-miss-admits-own-counter-seed',
    'only-two-victim-obligations-superseded','all-five-histories-see-old-entries',
    'release-retires-eight-surviving-results','victim-new-key-and-all-survivors-consumed')


def replacement_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown direction-replacement status')
    return CoverGroupDef('bpu_owned_direction_replacement_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-replacement.{status}',
        contract='capacity+1 distinct histories -> full miss -> eight survivor commits -> victim/new/all survivors')


class DirectionReplacementCoverage(DirectionServiceCoverage):
    rules=RULES
    def __init__(self):self.groups={status:replacement_coverage(status) for status in ('reached','checked')}
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-replacement.json')
