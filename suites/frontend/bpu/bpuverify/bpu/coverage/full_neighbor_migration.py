"""Full-capacity migrated-hit semantics, without physical slot bins."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.coverage.neighbor_migration import NeighborMigrationCoverage

RULES = ('two-original-providers-migrate-together', 'three-independent-neighbors-and-current-version-qualified',
         'six-distinct-feedbacks-accept-without-reread', 'all-pending-results-survive-read-competition',
         'all-five-old-history-consumers-before-service', 'all-eight-results-retire-through-current-owners',
         'all-five-new-history-consumers-keep-independent-results', 'all-six-input-snapshots-preserved',
         'full-capacity-migrated-hits-preserve-independent-learning')


class FullNeighborMigrationCoverage(NeighborMigrationCoverage):
    rules = RULES

    def __init__(self):
        self.groups = {role: CoverGroupDef('bpu_full_neighbor_migration_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),
        )).instantiate('kunminghu_v3.bpu.full-neighbor-migration.' + role) for role in ('reached', 'checked')}

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-full-neighbor-migration.json')
