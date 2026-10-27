"""Only complete logical lifetimes receive paired checked credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from bpuverify.bpu.model.ras.layered_recursion import Program, PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown recursive lifetime status')
    bins = {str(count)+'.'+rule: Bin.values(str(count)+'.'+rule) for count in PROFILES for rule in RULES}
    return CoverGroupDef('bpu_layered_recursive_return_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.bpu.layered-recursive-return.'+status,
        contract='owned indirect-call redo -> independently counted recursive layers -> complete natural returns -> exact retirement')


class Coverage:
    def __init__(self, program):
        if not isinstance(program, Program):
            raise TypeError('a declared logical recursion program is required')
        self.program, self.seen, self.finished = program, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reached(self, rule, **witness):
        if self.finished or rule not in RULES or rule in self.seen:
            raise ValueError('one witness per declared lifetime obligation')
        self.groups['reached'].sample(dict(obligation=str(self.program.inner_calls) + '.' + rule), metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.finished or self.seen != set(RULES):
            raise AssertionError('incomplete layered-recursive lifetime cannot receive checked credit')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=str(self.program.inner_calls) + '.' + rule))
        self.finished = True
