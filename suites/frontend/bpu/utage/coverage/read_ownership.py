"""Semantic ownership obligations, paired reach and complete comparison."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.utage.model.read_ownership import RULES


class ReadOwnershipCoverage:
    def __init__(self):
        self.groups = {status: CoverGroupDef('utage_inflight_learning_ownership_v1', (
            CoverPointDef('obligation', {rule: Bin.values(rule) for rule in RULES}),
        )).instantiate(f'kunminghu_v3.utage.inflight-learning-ownership.{status}')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(obligation=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output / 'functional-coverage-inflight-learning-ownership.json')
