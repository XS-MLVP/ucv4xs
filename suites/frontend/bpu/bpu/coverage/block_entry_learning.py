"""Reuse eight source-learning obligations; never credit a partial program."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.block_entry_learning import PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('declared lifecycle required')
    return CoverGroupDef('bpu_block_entry_learning_v1',(CoverPointDef('obligation',
        {p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
            'kunminghu_v3.bpu.block-entry-learning.'+status)


class Coverage:
    def __init__(self, profile):
        if profile not in PROFILES: raise ValueError('declared entry profile required')
        self.profile=profile; self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.reached={}; self.compared={}; self.closed=False
    def record(self,status,rule,tick):
        if self.closed or status not in self.groups or rule not in RULES: raise ValueError('open entry obligation required')
        if status == 'checked': self.compared[rule]=tick; return
        if rule not in self.reached:
            self.reached[rule]=tick
            self.groups[status].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
    def finish(self):
        if self.closed or set(self.reached) != set(RULES) or set(self.compared) != set(RULES):
            raise AssertionError('complete actual source learning and fresh consumer required')
        for rule,tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.profile+'.'+rule),metadata=dict(tick=tick))
        self.closed=True
    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-block-entry-learning.json')
