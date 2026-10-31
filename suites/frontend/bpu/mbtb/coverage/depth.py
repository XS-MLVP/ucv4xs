"""Second-depth ownership with a real nonweak peer, independent of axes."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage


RULES = ('fresh-source-depth-owner-control', 'stale-source-depth-owner-with-negative-peer')


def depth_owner_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown depth ownership coverage status')
    return CoverGroupDef('mbtb_second_depth_owner_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.mbtb.depth-owner.{status}',
        contract='verified second-depth resident and negative peer -> exact original acceptance/proposal -> complete preserved consumers')


class DepthOwnerCoverage:
    def __init__(self):
        self.groups = {status: depth_owner_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-depth-owner.json')
