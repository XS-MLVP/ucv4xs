"""Actual SC-to-early instruction lifetimes; no physical coordinate matrix."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

from suites.frontend.bpu.bpu.model.sc_early_learning import PROFILES,RULES
from suites.frontend.bpu.coverage.exports import write_functional_coverage


def lifetime_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('declared lifecycle required')
    return CoverGroupDef('bpu_sc_early_learning_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.sc-early-learning.'+status)


class Coverage:
    def __init__(self,profile):
        if profile not in PROFILES:
            raise ValueError('declared instruction program required')
        self.profile,self.closed = profile,False
        self.reached,self.compared = {},{}
        self.groups = {s:lifetime_coverage(s) for s in ('reached','checked')}

    def record(self,status,rule,tick):
        if self.closed or status not in self.groups or rule not in RULES:
            raise ValueError('open declared lifetime obligation required')
        if status=='checked':
            self.compared[rule]=tick
        elif rule not in self.reached:
            self.reached[rule]=tick
            self.groups[status].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))

    def finish(self):
        if self.closed or set(self.reached)!=set(RULES) or set(self.compared)!=set(RULES):
            raise AssertionError('complete actual guidance, next-state confirmation and natural early consumer required')
        for rule,tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
        self.closed=True

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-sc-early-learning.json')
