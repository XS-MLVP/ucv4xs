"""Independent branch ownership and raw-to-qualified direction consumption."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('opposed-owned-directions','weak-raw-middle-selected','weak-qualified-late-repair',
         'strong-middle-retained','neighbor-unmodified')
DISCOVERIES = ('earlier-first','later-first')


def routing_coverage(status,discovery='earlier-first'):
    if status not in ('reached','checked'):
        raise ValueError('unknown raw/qualified TAGE routing event status')
    if discovery not in DISCOVERIES:
        raise ValueError('unknown branch discovery order')
    suffix = '' if discovery=='earlier-first' else f'.{discovery}'
    return CoverGroupDef('bpu_tage_raw_qualified_routing_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.tage.raw-qualified-routing{suffix}.{status}',
        contract='actual opposed-owner component event -> independent TAGE state -> complete causal override sequence')


class RoutingCoverage:
    def __init__(self,discovery='earlier-first'):
        self.groups = {status:routing_coverage(status,discovery) for status in ('reached','checked')}
        self.discovery = discovery

    def record(self,status,rule,**witness):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,**witness))

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-tage-fast-routing.json')
