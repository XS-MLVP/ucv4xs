"""A complete recovered-vector lifetime is required before checked credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.utage.model.saved_vector import OBLIGATIONS


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('unknown saved-vector status')
    return CoverGroupDef('utage_saved_vector_v1',(CoverPointDef('obligation',{
        name:Bin.values(name) for name in OBLIGATIONS}),)).instantiate('kunminghu_v3.utage.saved-vector.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
    def reach(self,rule):
        if self.closed or rule not in self.program.rules or rule in self.completed: raise ValueError('one declared saved-vector rule required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule))
        self.completed.add(rule)
    def finish(self):
        if self.closed or self.completed!=set(self.program.rules): raise AssertionError('whole recovered-vector lifetime is incomplete')
        for rule in self.program.rules:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
