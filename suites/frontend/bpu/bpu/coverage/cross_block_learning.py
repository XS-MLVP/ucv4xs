"""Atomic complete cross-block learning lifetimes; no model-only DUT credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.cross_block_learning import PROFILES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('declared lifecycle required')
    return CoverGroupDef('bpu_cross_block_learning_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.cross-block-learning.'+status)


class Coverage:
    def __init__(self,profile):
        if profile not in PROFILES: raise ValueError('declared profile required')
        self.profile=profile; self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.reached={}; self.compared={}; self.closed=False
    def record(self,status,rule,tick):
        if self.closed or status not in self.groups or rule not in RULES: raise ValueError('open obligation required')
        if status=='checked': self.compared[rule]=tick; return
        if rule not in self.reached:
            self.reached[rule]=tick
            self.groups[status].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
    def finish(self):
        if self.closed or set(self.reached)!=set(RULES) or set(self.compared)!=set(RULES):
            raise AssertionError('both actual blocks, original feedback, confirmed learning and new consumer required')
        for rule,tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
        self.closed=True
    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-cross-block-learning.json')
