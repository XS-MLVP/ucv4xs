"""Qualified boundary learning and fully checked recovery are separate."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage


RULES = tuple(f'{boundary}-{phase}' for boundary in ('upper', 'lower')
              for phase in ('approach', 'hold', 'recover'))


class ScBoundaryCoverage:
    def __init__(self):
        self.groups = {status: CoverGroupDef('sc_weight_boundary_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
        )).instantiate(f'kunminghu_v3.sc.weight-boundary.{status}',
            contract='distinct real source -> eligible complete feedback -> per-family endpoint, holds and exact fresh reversal')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-weight-boundary.json')
