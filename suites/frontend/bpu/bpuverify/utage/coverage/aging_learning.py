"""Actual concurrent maintenance reach and fully checked semantic consumers."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.utage.model.aging_learning import RULES


class AgingLearningCoverage:
    def __init__(self):
        rules = tuple(f'{table}-{rule}' for table in ('short', 'long') for rule in RULES)
        self.groups = {status: CoverGroupDef('utage_aging_learning_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in rules}),
        )).instantiate(f'kunminghu_v3.utage.aging-learning.{status}',
            contract='real allocation failures -> adjacent original feedback -> simultaneous maintenance/learning -> common-prestate protection and direction consumers')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-aging-learning.json')
