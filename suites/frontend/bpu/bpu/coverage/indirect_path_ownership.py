"""Atomic original-source obligations; physical copies are not new functions."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.indirect_path_ownership import PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('declared lifecycle required')
    return CoverGroupDef('bpu_indirect_path_ownership_v1', (CoverPointDef('obligation',
        {p + '.' + r: Bin.values(p + '.' + r) for p in PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.indirect-path-ownership.' + status)


class Coverage:
    def __init__(self, profile):
        if profile not in PROFILES: raise ValueError('declared semantic profile required')
        self.profile = profile
        self.groups = {state: lifetime_coverage(state) for state in ('reached', 'checked')}
        self.reached, self.compared, self.closed = {}, {}, False

    def record(self, state, rule, tick):
        if self.closed or state not in self.groups or rule not in RULES: raise ValueError('open semantic obligation required')
        if state == 'checked': self.compared[rule] = tick
        elif rule not in self.reached:
            self.reached[rule] = tick
            self.groups[state].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))

    def finish(self):
        if self.closed or set(self.reached) != set(RULES) or set(self.compared) != set(RULES):
            raise AssertionError('complete original ownership, actual effects and fresh consumer required')
        for rule, tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))
        self.closed = True

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-indirect-path-ownership.json')

    def report(self): return CoverageDatabase(self.groups.values()).report()
