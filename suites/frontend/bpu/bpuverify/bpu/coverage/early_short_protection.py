"""Semantic short-provider obligations, never physical-address completion."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.early_short_protection import EDGES, rules


class EarlyShortProtectionCoverage:
    def __init__(self):
        keys = tuple(mode+'.'+rule for mode in EDGES for rule in rules(mode))
        self.groups = {status: CoverGroupDef('bpu_owned_short_protection_v1', (
            CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.owned-short-protection.'+status)
            for status in ('reached', 'checked')}

    def record(self, mode, status, rule, tick, **witness):
        self.groups[status].sample(dict(obligation=mode+'.'+rule), metadata=dict(tick=tick, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-owned-short-protection.json')
