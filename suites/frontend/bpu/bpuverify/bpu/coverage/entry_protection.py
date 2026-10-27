"""Atomic original-source protection obligations, never a physical grid."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.entry_protection import PROFILES,rules


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('declared protection lifecycle required')
    return CoverGroupDef('bpu_entry_protection_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in rules(p)}),)).instantiate(
            'kunminghu_v3.bpu.entry-protection.'+status)


class Coverage:
    def __init__(self,profile):
        if profile not in PROFILES: raise ValueError('declared entry protection profile required')
        self.profile=profile; self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.reached={}; self.compared={}; self.closed=False
    def record(self,status,rule,tick):
        if self.closed or status not in self.groups or rule not in rules(self.profile): raise ValueError('open protection obligation required')
        if status=='checked': self.compared[rule]=tick; return
        if rule not in self.reached:
            self.reached[rule]=tick; self.groups[status].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
    def finish(self):
        if self.closed or set(self.reached)!=set(rules(self.profile)) or set(self.compared)!=set(rules(self.profile)):
            raise AssertionError('all actual source/protection obligations required before checked credit')
        for rule,tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
        self.closed=True
    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-entry-protection.json')
