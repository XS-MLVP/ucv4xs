"""Learning must survive other identities, not be repaired by relearning."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage


MODES = ('serial', 'adjacent')
RULES = ('owned-feedback', 'immediate-consumption', 'unrelated-turnover',
         'left-recent-storage', 'late-consumption', 'immutable-originals')


class LearningRetentionCoverage:
    def __init__(self, program):
        self.program = program
        self.evidence = None
        self.groups = {status: CoverGroupDef('utage_learning_retention_v1', (
            CoverPointDef('obligation', {mode + '.' + rule: Bin.values(mode + '.' + rule)
                for mode in MODES for rule in RULES}),
        )).instantiate('kunminghu_v3.utage.learning-retention.' + status,
            contract='owned learning -> immediate consumer -> unrelated learning -> full cache departure -> fresh consumer')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown learning-retention evidence phase or obligation')
        self.groups[status].sample(dict(obligation=self.program.mode + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-learning-retention.json')
