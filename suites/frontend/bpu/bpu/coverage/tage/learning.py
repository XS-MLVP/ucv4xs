"""One semantic feedback beat; resolve slots are witnesses, not coverage axes."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('earlier-correct-provider', 'later-correct-provider', 'sparse-resolve-association', 'two-owned-updates')


def learning_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown TAGE learning coverage status')
    return CoverGroupDef('bpu_tage_sparse_learning_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.tage.semantic-learning.{status}',
        contract='actual accepted two-conditional feedback -> owned counter/useful learning -> checked public metadata')


class LearningCoverage:
    def __init__(self):
        self.groups = {status: learning_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-tage-semantic-learning.json')
