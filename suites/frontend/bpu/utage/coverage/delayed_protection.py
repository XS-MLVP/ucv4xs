"""Whole original-correctness cohort, independent of physical coordinates."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.utage.model.delayed_protection import PROGRAMS, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('declared protection lifecycle required')
    bins = {p.label+'.'+rule:Bin.values(p.label+'.'+rule) for p in PROGRAMS for rule in RULES}
    return CoverGroupDef('utage_delayed_protection_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.utage.delayed-protection.'+status)


class Coverage:
    def __init__(self, program):
        if program not in PROGRAMS: raise ValueError('declared original-correctness program required')
        self.program = program; self.completed = {}; self.closed = False
        self.groups = {s:lifetime_coverage(s) for s in ('reached', 'checked')}
    def reach(self, rule, **witness):
        if self.closed or rule not in RULES or rule in self.completed: raise ValueError('one declared protection obligation required')
        self.completed[rule] = witness
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule), metadata=witness)
    def finish(self):
        if self.closed or set(self.completed) != set(RULES): raise AssertionError('incomplete original-correctness cohort')
        for rule, witness in self.completed.items():
            self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule), metadata=witness)
        self.closed = True
    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-delayed-protection.json')
