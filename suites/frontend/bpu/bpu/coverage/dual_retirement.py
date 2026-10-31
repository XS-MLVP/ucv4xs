"""Learning, service and preservation obligations, not physical slot bins."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage

RULES = ('two-original-providers-migrate-together', 'distinct-old-pairs-accept-adjacently',
         'unchanged-original-proposals-remain-adjacent', 'both-current-owners-retire-independent-versions',
         'next-learning-coincides-with-previous-retirement', 'saturated-successor-survives-prior-retirement',
         'fresh-current-and-displaced-consumers-correct', 'all-original-pairs-preserved')


class DualRetirementCoverage:
    def __init__(self):
        self.groups = {role: CoverGroupDef('bpu_dual_retirement_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
        )).instantiate('kunminghu_v3.bpu.dual-retirement.' + role) for role in ('reached', 'checked')}

    def record(self, role, rule, **witness):
        if role not in self.groups or rule not in RULES:
            raise ValueError('unknown dual-retirement evidence role or obligation')
        self.groups[role].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-dual-retirement.json')
