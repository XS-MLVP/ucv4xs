"""Full retained capacity is an event precondition, not a physical sweep."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.coverage.direction_service import DirectionServiceCoverage

RULES=('all-owner-capacities-occupied','full-hit-keeps-logical-ownership',
    'all-eight-results-retained','all-four-histories-see-old-entries',
    'release-retires-eight-results-once','all-four-histories-consume-commits')


def capacity_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown direction-capacity status')
    return CoverGroupDef('bpu_owned_direction_capacity_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-capacity.{status}',
        contract='four retained histories -> full hit -> old consumers -> eight SDK commits -> new consumers')


class DirectionCapacityCoverage(DirectionServiceCoverage):
    rules=RULES
    def __init__(self):self.groups={status:capacity_coverage(status) for status in ('reached','checked')}
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-capacity.json')
