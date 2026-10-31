"""Protection obligations, independently reached and checked; no address axis."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.utage.model.usefulness_events import MODES, RULES


class UsefulnessCoverage:
    def __init__(self, program):
        self.program = program
        self.family = 'initial-protection' if program.rule == 'initial-protection' else 'protection-feedback'
        bins = tuple(f'{table}.initial-protection.serial' for table in (0, 1)) if self.family == 'initial-protection' else tuple(
            f'{table}.{rule}.{mode}' for table in (0, 1) for rule in RULES for mode in MODES)
        self.groups = {status: CoverGroupDef(f'utage_{self.family}_v1', (
            CoverPointDef('event', {key: Bin.values(key) for key in bins}),
        )).instantiate(f'kunminghu_v3.utage.semantic.{self.family}.{status}') for status in ('reached', 'checked')}

    def record(self, status, **witness):
        p = self.program
        self.groups[status].sample(dict(event=f'{p.table}.{p.rule}.{p.mode}'), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / f'functional-coverage-{self.family}.json')
