"""Actual original-neutral cohorts, with atomic end-to-end checked credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.neutral_recovery import PROFILES, rules


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('declared neutral lifecycle required')
    keys = tuple(profile+'.'+rule for profile in PROFILES for rule in rules(profile))
    return CoverGroupDef('bpu_integrated_neutral_recovery_v1', (CoverPointDef('obligation',
        {key:Bin.values(key) for key in keys}),)).instantiate('kunminghu_v3.bpu.neutral-recovery.'+status)


class Coverage:
    def __init__(self):
        self.groups = {status:lifetime_coverage(status) for status in ('reached', 'checked')}
        self.reached = {}; self.compared = {}; self.closed = False
    def record(self, profile, status, rule, tick, **witness):
        if profile not in PROFILES or status not in self.groups or rule not in rules(profile):
            raise ValueError('declared integrated neutral obligation required')
        key = profile, rule
        if status == 'checked': self.compared[key] = dict(tick=tick, **witness); return
        if key not in self.reached:
            self.reached[key] = dict(tick=tick, **witness)
            self.groups['reached'].sample(dict(obligation=profile+'.'+rule), metadata=self.reached[key])
    def finish(self, profile):
        expected = {(profile, rule) for rule in rules(profile)}
        if self.closed or set(self.reached) != expected or set(self.compared) != expected:
            raise AssertionError('all real neutral-boundary obligations required before checked')
        for (name, rule), witness in self.compared.items():
            self.groups['checked'].sample(dict(obligation=name+'.'+rule), metadata=witness)
        self.closed = True
    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-neutral-recovery.json')
