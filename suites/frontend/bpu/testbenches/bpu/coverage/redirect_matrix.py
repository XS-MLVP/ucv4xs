"""Guard matrix credit only after actual acceptance, recovery and drain."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import REDIRECT_CASES
from suites.frontend.bpu.testbenches.shared.coverage.exports import write_functional_coverage


class RedirectMatrixCoverage:
    def __init__(self, case):
        if case not in REDIRECT_CASES:
            raise ValueError('undeclared recovery class')
        self.case = case
        self.groups = {role: CoverGroupDef('bpu_guard_outcomes_v1', (
            CoverPointDef('class', {c.label: Bin.values(c.label) for c in REDIRECT_CASES}),
        )).instantiate(f'kunminghu_v3.bpu.guard-outcomes.{role}') for role in ('reached', 'checked')}

    def record(self, role, **witness):
        self.groups[role].sample({'class': self.case.label}, metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-guard-outcomes.json')
