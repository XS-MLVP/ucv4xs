"""Per-class reached versus independently checked public outcomes."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.testbenches.shared.coverage.exports import write_functional_coverage
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import RESIDENCY_CASES


class LearningMatrixCoverage:
    def __init__(self, case, family):
        cases = {'payload': PAYLOAD_CASES, 'residency': RESIDENCY_CASES}[family]
        if case not in cases:
            raise ValueError('undeclared learning case')
        self.case, self.family, self.reached = case, family, False
        label = lambda c: c.coverage_label if family == 'payload' else c.label
        self.label = label(case)
        self.groups = {role: CoverGroupDef(f'mbtb_{family}_matrix_v1', (
            CoverPointDef('class', {label(c): Bin.values(label(c)) for c in cases}),
        )).instantiate(f'kunminghu_v3.mbtb.{family}-matrix.{role}') for role in ('reached', 'checked')}

    def record(self, role, **witness):
        if role == 'reached':
            self.reached = True
        elif role != 'checked' or not self.reached:
            raise ValueError('checked outcome requires actual reached input')
        self.groups[role].sample({'class': self.label}, metadata=dict(parameter_case=self.case.label, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / f'functional-coverage-{self.family}-matrix.json')
