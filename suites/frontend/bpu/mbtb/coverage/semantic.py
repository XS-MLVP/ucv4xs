"""Logical learning/ownership requirements; offers and successful checks differ."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = {
    'miss': ('unmatched-same-position-isolation', 'unmatched-other-position-control'),
    'owner': ('current-metadata-owner-control', 'stale-metadata-retained-owner'),
    'cleanup': ('nonzero-key-clear-control', 'combined-zero-key-destination-clear'),
    'replacement': ('taken-way0-touches-shared-age', 'taken-way1-touches-shared-age',
                    'not-taken-leaves-age', 'prediction-leaves-age'),
}


def semantic_coverage(family, status):
    if family not in RULES or status not in ('reached', 'checked'):
        raise ValueError('unknown MBTB semantic coverage family/status')
    return CoverGroupDef(f'mbtb_semantic_{family}_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES[family]}),
    )).instantiate(f'kunminghu_v3.mbtb.semantic.{family}.{status}',
        contract='accepted public feedback -> independently owned branch/counter -> public endpoint comparison')


class SemanticCoverage:
    def __init__(self, family):
        self.family = family
        self.groups = {status: semantic_coverage(family, status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / f'functional-coverage-semantic-{self.family}.json')
