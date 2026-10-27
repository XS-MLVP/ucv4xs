"""Paired reset-lifetime obligations; partial execution earns no checked credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from bpuverify.mbtb.model.reset_lifetime import Program, PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown reset lifetime status')
    definition = CoverGroupDef('mbtb_reset_lifetime_v1', (
        CoverPointDef('obligation', {p+'.'+r: Bin.values(p+'.'+r)
                                   for p in PROFILES for r in RULES}),))
    return definition.instantiate('kunminghu_v3.mbtb.reset-lifetime.'+status)


class Coverage:
    def __init__(self, program):
        if not isinstance(program, Program):
            raise TypeError('a declared reset lifetime program is required')
        self.program, self.completed, self.finished = program, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reach(self, rule, **witness):
        if rule not in RULES or rule in self.completed or self.finished:
            raise ValueError('unknown, repeated or closed reset obligation')
        self.groups['reached'].sample(dict(obligation=self.program.profile+'.'+rule), metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.finished or self.completed != set(RULES):
            raise AssertionError('incomplete or already checked reset lifetime')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=self.program.profile+'.'+rule))
        self.finished = True
