"""Concurrent original owners must compose on one current retained key."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.coverage.direction_service import DirectionServiceCoverage

RULES=('four-distinct-original-snapshots','four-original-inputs-accept-adjacent',
    'four-proposals-retain-old-snapshot','current-owner-compounds-through-saturation',
    'fresh-consumer-keeps-saturated-result','neighbour-and-displaced-key-preserved')


def burst_coverage(original_way,status):
    if type(original_way) is not int or original_way not in (0,1) or status not in ('reached','checked'):
        raise ValueError('unknown stale direction-burst scope')
    return CoverGroupDef('bpu_owned_direction_burst_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-burst.{original_way}.{status}',
        contract='four genuine old sources -> adjacent accepts/proposals -> current-owner 5/6/7/7 -> every fresh consumer')


class DirectionBurstCoverage(DirectionServiceCoverage):
    rules=RULES
    def __init__(self,original_way):self.groups={status:burst_coverage(original_way,status) for status in ('reached','checked')}
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-burst.json')
