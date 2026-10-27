"""Paired semantic lifetimes: observation is separate from complete checking."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from bpuverify.bpu.model.ras.wrapped_recursion import PROFILES, RULES, validate


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown lifetime status')
    bins = {value: Bin.values(value) for value in tuple(str(count)+'.'+rule for count in PROFILES for rule in RULES)}
    return CoverGroupDef('bpu_wrapped_recursive_return_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.bpu.wrapped-recursive-return.' + status,
        contract='original input -> qualified semantic effects -> fresh consumers -> complete lifetime comparison')


class Coverage:
    def __init__(self, calls):
        validate(calls)
        self.calls, self.seen, self.finished = calls, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reached(self, rule, **witness):
        if self.finished or rule not in RULES or rule in self.seen:
            raise ValueError('one witness per declared lifetime obligation')
        self.groups['reached'].sample(dict(obligation=str(self.calls) + '.' + rule), metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.finished or self.seen != set(RULES):
            raise AssertionError('incomplete lifetime cannot receive checked credit')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=str(self.calls) + '.' + rule))
        self.finished = True
