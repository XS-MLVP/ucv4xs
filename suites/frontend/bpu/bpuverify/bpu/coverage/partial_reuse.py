"""Capacity reuse is an identity/lifetime obligation, not a slot matrix."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.coverage.neighbor_migration import NeighborMigrationCoverage

RULES = ('two-original-providers-migrate-together', 'five-independent-histories-qualified-for-capacity-reuse',
         'initial-four-sources-fill-capacity-without-service', 'exactly-one-neighbor-service-pair-releases-space',
         'fresh-identity-reuses-space-without-eviction', 'old-feedback-updates-current-owner-at-full-capacity',
         'all-six-mixed-visibility-consumers-before-final-service', 'all-ten-services-own-their-original-results',
         'all-six-final-consumers-keep-five-independent-results', 'all-seven-input-snapshots-preserved')


class PartialReuseCoverage(NeighborMigrationCoverage):
    rules = RULES

    def __init__(self):
        self.groups = {role: CoverGroupDef('bpu_partial_service_reuse_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),
        )).instantiate('kunminghu_v3.bpu.partial-service-reuse.' + role) for role in ('reached', 'checked')}

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-partial-service-reuse.json')
