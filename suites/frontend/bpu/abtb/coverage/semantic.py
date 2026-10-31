"""Accepted independent write obligations versus successfully checked endpoints."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('same-destination-latest', 'distinct-destinations-retained')


def semantic_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown ABTB semantic coverage status')
    return CoverGroupDef('abtb_semantic_write_ownership_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.abtb.semantic.write-ownership.{status}',
                  contract='accepted public corrections -> destination-owned obligations -> public target comparison')


class SemanticCoverage:
    def __init__(self):
        self.groups = {status: semantic_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-semantic-write-ownership.json')
