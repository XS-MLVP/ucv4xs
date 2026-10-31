"""Boundary obligations, separate actual reach from complete checked closure."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.early_protection import EDGES, rules


class EarlyProtectionCoverage:
    def __init__(self):
        keys = tuple(mode+'.'+rule for mode in EDGES for rule in rules(mode))
        self.groups = {status: CoverGroupDef('bpu_owned_early_protection_v1', (
            CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.owned-early-protection.'+status)
            for status in ('reached', 'checked')}

    def record(self, mode, status, rule, tick, **witness):
        self.groups[status].sample(dict(obligation=mode+'.'+rule), metadata=dict(tick=tick, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-owned-early-protection.json')
