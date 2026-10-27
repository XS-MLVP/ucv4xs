"""History ownership events, separate from successful semantic comparisons."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('context-allocation', 'context-local-learning', 'interleaved-history-routing', 'protected-history-restored')


def semantic_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown TAGE semantic coverage status')
    return CoverGroupDef('tage_semantic_history_ownership_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.tage.semantic.history-ownership.{status}',
                  contract='accepted history-specific events -> independently owned entries -> compared public predictions')


class SemanticCoverage:
    def __init__(self):
        self.groups = {status: semantic_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-semantic-history-ownership.json')
