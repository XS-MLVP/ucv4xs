"""Original-query history obligations; semantic programs, no physical sweep."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.bpu.model.common_query import PROFILES, RULES
from suites.frontend.bpu.coverage.exports import write_functional_coverage

OBLIGATIONS = tuple(profile + '.' + rule for profile in PROFILES for rule in RULES[profile])


def lifetime_coverage(state):
    if state not in ('reached', 'checked'):
        raise ValueError('original-history lifecycle required')
    return CoverGroupDef('bpu_common_query_history_v1', (CoverPointDef('obligation',
        {name: Bin.values(name) for name in OBLIGATIONS}),)).instantiate(
            'kunminghu_v3.bpu.common-query-history.' + state)


class CommonQueryCoverage:
    def __init__(self, profile):
        if profile not in PROFILES:
            raise ValueError('declared original-history program required')
        self.profile = profile
        self.groups = {state: lifetime_coverage(state) for state in ('reached', 'checked')}
        self.reached, self.closed = {}, False

    def record(self, rule, tick):
        if self.closed or rule not in RULES[self.profile]:
            raise ValueError('declared open original-history obligation required')
        if rule not in self.reached:
            self.reached[rule] = tick
            self.groups['reached'].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))

    def finish(self):
        if self.closed or set(self.reached) != set(RULES[self.profile]):
            raise AssertionError('every actual query, recovery, public source and preservation obligation required')
        for rule, tick in self.reached.items():
            self.groups['checked'].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))
        self.closed = True

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / 'functional-coverage-common-query-history.json')
