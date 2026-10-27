"""Behavior denominators retain every concurrent admission requirement."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

from bpuverify.bpu.model.sc_admission import PROFILES,RULES,BURST_PROFILES,BURST_RULES,READ_ONLY_PROFILES
from bpuverify.common.coverage.exports import write_functional_coverage


def lifetime_coverage(state):
    if state not in ('reached','checked'):
        raise ValueError('declared admission lifecycle required')
    return CoverGroupDef('bpu_sc_admission_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.sc-admission.'+state)


class Coverage:
    profiles,rules = PROFILES,RULES
    factory = staticmethod(lifetime_coverage)
    filename = 'functional-coverage-sc-admission.json'

    def __init__(self,profile):
        if profile not in self.profiles:
            raise ValueError('declared SC admission program required')
        self.profile,self.reached,self.closed = profile,{},False
        self.groups = {s:self.factory(s) for s in ('reached','checked')}

    def record(self,rule,tick):
        if self.closed or rule not in self.rules:
            raise ValueError('open declared admission requirement required')
        if rule not in self.reached:
            self.reached[rule] = tick
            self.groups['reached'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))

    def finish(self):
        if self.closed or set(self.reached)!=set(self.rules):
            raise AssertionError('complete original, real arbitration, learning and fresh consumer required')
        for rule,tick in self.reached.items():
            self.groups['checked'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
        self.closed = True

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/self.filename)


def burst_lifetime_coverage(state):
    if state not in ('reached','checked'):
        raise ValueError('declared burst lifecycle required')
    return CoverGroupDef('bpu_sc_feedback_burst_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in BURST_PROFILES for r in BURST_RULES}),)).instantiate(
            'kunminghu_v3.bpu.sc-feedback-burst.'+state)


class BurstCoverage(Coverage):
    profiles,rules = BURST_PROFILES,BURST_RULES
    factory = staticmethod(burst_lifetime_coverage)
    filename = 'functional-coverage-sc-feedback-burst.json'


def read_only_lifetime_coverage(state):
    if state not in ('reached','checked'):
        raise ValueError('declared read-only feedback lifecycle required')
    return CoverGroupDef('bpu_sc_read_no_write_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in READ_ONLY_PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.sc-read-no-write.'+state)


class ReadOnlyCoverage(Coverage):
    profiles = READ_ONLY_PROFILES
    factory = staticmethod(read_only_lifetime_coverage)
    filename = 'functional-coverage-sc-read-no-write.json'


def context_burst_lifetime_coverage(state):
    from bpuverify.bpu.model.sc_admission import CONTEXT_BURST_PROFILES, CONTEXT_BURST_RULES
    if state not in ('reached','checked'):
        raise ValueError('declared distinct-context burst lifecycle required')
    return CoverGroupDef('bpu_sc_context_burst_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in CONTEXT_BURST_PROFILES for r in CONTEXT_BURST_RULES}),)).instantiate(
            'kunminghu_v3.bpu.sc-context-burst.'+state)


class ContextBurstCoverage(Coverage):
    from bpuverify.bpu.model.sc_admission import CONTEXT_BURST_PROFILES, CONTEXT_BURST_RULES
    profiles,rules=CONTEXT_BURST_PROFILES,CONTEXT_BURST_RULES
    factory=staticmethod(context_burst_lifetime_coverage)
    filename='functional-coverage-sc-context-burst.json'
