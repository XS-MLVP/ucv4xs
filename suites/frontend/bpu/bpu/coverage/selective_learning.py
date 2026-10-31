"""Each semantic cohort closes only after services and all consumers compare."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.tage.selective_learning import ALL_PROGRAMS, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('declared coverage lifecycle required')
    bins = {p.name+'.'+r: Bin.values(p.name+'.'+r) for p in ALL_PROGRAMS for r in RULES}
    return CoverGroupDef('bpu_selective_direction_learning_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.bpu.selective-direction-learning.'+status)


class Coverage:
    def __init__(self, program):
        if program not in ALL_PROGRAMS: raise ValueError('declared selective-learning cohort required')
        self.program = program
        self.groups = {s: lifetime_coverage(s) for s in ('reached', 'checked')}
        self.compared = set()

    def reach(self, rule, tick):
        if rule not in RULES: raise ValueError('declared semantic obligation required')
        self.groups['reached'].sample({'obligation': self.program.name+'.'+rule}, metadata={'tick': tick})

    def compare(self, rule, tick):
        self.reach(rule, tick)
        self.compared.add(rule)

    def finish(self, tick):
        if self.compared != set(RULES): raise AssertionError(('incomplete selective-learning cohort', self.compared))
        for rule in RULES:
            self.groups['checked'].sample({'obligation': self.program.name+'.'+rule}, metadata={'tick': tick})

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-selective-direction-learning.json')
