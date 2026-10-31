"""Compare independently owned results, not a physical bank/rank matrix."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage

RULES = ('two-original-providers-migrate-together', 'independent-neighbor-and-current-version-qualified',
         'four-distinct-feedbacks-accept-without-reread', 'both-logical-results-survive-read-competition',
         'all-old-history-consumers-before-service', 'both-results-retire-through-each-current-owner',
         'all-new-history-consumers-keep-independent-results', 'every-input-snapshot-preserved')


class NeighborMigrationCoverage:
    rules = RULES

    def __init__(self):
        self.groups = {role: CoverGroupDef('bpu_neighbor_migration_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),
        )).instantiate('kunminghu_v3.bpu.neighbor-migration.' + role) for role in ('reached', 'checked')}

    def record(self, role, rule, **witness):
        if role not in self.groups or rule not in self.rules:
            raise ValueError('unknown neighbor-migration evidence role or rule')
        self.groups[role].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-neighbor-migration.json')
