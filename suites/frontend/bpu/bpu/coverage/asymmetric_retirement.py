"""Logical identity is independent of simultaneous service ordinal."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage

RULES = ('two-original-providers-migrate-together',
         'fresh-target-and-independent-neighbor-qualified',
         'five-distinct-inputs-accept-in-two-concurrent-bursts',
         'late-learning-updates-each-current-logical-result',
         'all-old-history-consumers-before-service',
         'four-results-service-by-logical-identity-not-lane-pairs',
         'all-new-history-consumers-keep-independent-results',
         'every-input-snapshot-preserved',
         'single-owner-pressure-creates-different-logical-service-orders')


class AsymmetricRetirementCoverage:
    def __init__(self):
        self.groups = {role: CoverGroupDef('bpu_asymmetric_retirement_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),)).instantiate(
                'kunminghu_v3.bpu.asymmetric-retirement.' + role)
            for role in ('reached', 'checked')}

    def record(self, role, rule, **witness):
        if role not in self.groups or rule not in RULES:
            raise ValueError('unknown asymmetric-retirement role or requirement')
        self.groups[role].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-asymmetric-retirement.json')
