"""Logical ownership and visibility obligations, without physical axes."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage

RULES = ('two-original-providers-migrate-together', 'original-pair-needs-no-reread',
         'opposed-old-proposals-arrive-together', 'pending-counters-belong-to-new-owners',
         'fresh-old-consumers-before-service', 'retire-both-current-owner-results-once',
         'clean-reactivation-keeps-latest-counters', 'all-consumers-and-originals-preserved')


class DualMigrationCoverage:
    def __init__(self):
        self.groups = {status: CoverGroupDef('bpu_owned_dual_migration_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),
        )).instantiate('kunminghu_v3.bpu.owned-dual-migration.' + status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown semantic evidence role or rule')
        self.groups[status].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-dual-migration.json')
