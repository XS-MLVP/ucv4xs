"""Paired semantic lifetimes: observation is separate from complete checking."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from bpuverify.bpu.model.main_sibling import PHASES, ORIGINS

RULES = ('qualified-original-source', 'strong-unexecuted-sibling', 'actual-read-blocked-learning', 'declared-version-visibility', 'complete-latest-entry-service', 'unexecuted-sibling-consumer', 'latest-earlier-consumer', 'immutable-originals')


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown lifetime status')
    bins = {value: Bin.values(value) for value in tuple(phase+'.'+origin+'.'+rule for phase in PHASES for origin in ORIGINS for rule in RULES)}
    return CoverGroupDef('bpu_unexecuted_conditional_sibling_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.bpu.unexecuted-conditional-sibling.' + status,
        contract='original input -> qualified semantic effects -> fresh consumers -> complete lifetime comparison')


class Coverage:
    def __init__(self, program):
        self.program, self.seen, self.finished = program, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reached(self, rule, **witness):
        if self.finished or rule not in RULES or rule in self.seen:
            raise ValueError('one witness per declared lifetime obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label + '.' + rule), metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.finished or self.seen != set(RULES):
            raise AssertionError('incomplete lifetime cannot receive checked credit')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=self.program.label + '.' + rule))
        self.finished = True

    def counts(self, status):
        from toffee import CoverageDatabase
        rows = CoverageDatabase(self.groups.values()).report()['groups']
        group, = [row for row in rows if row['instance'].endswith('.' + status)]
        return group['points'][0]['counts']
