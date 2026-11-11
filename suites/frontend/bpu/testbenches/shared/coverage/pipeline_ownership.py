"""Semantic evidence for distinguishable requests, not a physical sweep."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.testbenches.shared.coverage.exports import write_functional_coverage


RULES = ('distinct-learning', 'overlapping-originals', 'owned-hits-and-misses',
         'immutable-original-snapshots', 'learning-survives-queries')


def ownership_coverage(dut, status, *, profiles):
    if dut not in profiles or status not in ('reached', 'checked'):
        raise ValueError('unknown predictor ownership coverage scope')
    obligations = tuple(profile + '.' + rule for profile in profiles[dut] for rule in RULES)
    return CoverGroupDef(dut + '_pipeline_ownership_v1', (
        CoverPointDef('obligation', {value: Bin.values(value) for value in obligations}),
    )).instantiate('kunminghu_v3.' + dut + '.pipeline-ownership.' + status,
        contract='distinct public learning -> overlapping hit/miss requests -> original-owner comparison -> fresh consumers')


class PipelineOwnershipCoverage:
    def __init__(self, dut, profile, *, profiles):
        if dut not in profiles or profile not in profiles[dut]:
            raise ValueError('unknown predictor ownership program')
        self.dut, self.profile = dut, profile
        self.groups = {status: ownership_coverage(dut, status, profiles=profiles) for status in ('reached', 'checked')}
        self.evidence = None

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown predictor ownership obligation')
        self.groups[status].sample(dict(obligation=self.profile + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-pipeline-ownership.json')
