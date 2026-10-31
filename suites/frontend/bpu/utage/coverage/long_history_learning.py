"""Semantic source/learning obligations, with no physical coordinate matrix."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.utage.model.long_history_learning import MODES, RULES


class LongHistoryLearningCoverage:
    def __init__(self, mode):
        if mode not in MODES: raise ValueError('unknown communication mode')
        self.mode = mode
        self.groups = {status:CoverGroupDef('utage_long_history_learning_v1',(
            CoverPointDef('obligation',{m+'.'+r:Bin.values(m+'.'+r) for m in MODES for r in RULES}),
        )).instantiate('kunminghu_v3.utage.long-history-learning.'+status) for status in ('reached','checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(obligation=self.mode+'.'+rule),metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-long-history-learning.json')
