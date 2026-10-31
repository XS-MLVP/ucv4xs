"""Semantic evidence for distinguishable requests, not a physical sweep."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage


PROFILES = {
    'ubtb': ('forward', 'reverse'),
    'mbtb': ('forward', 'reverse'),
    'ittage': ('history-only-forward', 'history-only-reverse',
               'pc-and-history-forward', 'pc-and-history-reverse'),
}
RULES = ('distinct-learning', 'overlapping-originals', 'owned-hits-and-misses',
         'immutable-original-snapshots', 'learning-survives-queries')


def ownership_coverage(dut, status):
    if dut not in PROFILES or status not in ('reached', 'checked'):
        raise ValueError('unknown predictor ownership coverage scope')
    obligations = tuple(profile + '.' + rule for profile in PROFILES[dut] for rule in RULES)
    return CoverGroupDef(dut + '_pipeline_ownership_v1', (
        CoverPointDef('obligation', {value: Bin.values(value) for value in obligations}),
    )).instantiate('kunminghu_v3.' + dut + '.pipeline-ownership.' + status,
        contract='distinct public learning -> overlapping hit/miss requests -> original-owner comparison -> fresh consumers')


class PipelineOwnershipCoverage:
    def __init__(self, dut, profile):
        if dut not in PROFILES or profile not in PROFILES[dut]:
            raise ValueError('unknown predictor ownership program')
        self.dut, self.profile = dut, profile
        self.groups = {status: ownership_coverage(dut, status) for status in ('reached', 'checked')}
        self.evidence = None

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown predictor ownership obligation')
        self.groups[status].sample(dict(obligation=self.profile + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-pipeline-ownership.json')
