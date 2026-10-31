"""Credit only applicable obligations of a complete warm-vector lifetime."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from suites.frontend.bpu.utage.model.dual_source import OBLIGATIONS


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('unknown dual-source coverage status')
    definition = CoverGroupDef('utage_dual_source_v1',(CoverPointDef('obligation',{
        name:Bin.values(name) for name in OBLIGATIONS}),))
    return definition.instantiate('kunminghu_v3.utage.dual-source-prefix.'+status)


class Coverage:
    def __init__(self, program):
        self.program,self.completed,self.closed = program,set(),False
        self.groups = {status:lifetime_coverage(status) for status in ('reached','checked')}
    def reach(self, rule, **witness):
        if self.closed or rule not in self.program.rules or rule in self.completed: raise ValueError('one applicable dual-source obligation required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.completed.add(rule)
    def finish(self):
        if self.closed or self.completed != set(self.program.rules): raise AssertionError('incomplete dual-source prefix lifetime')
        for rule in self.program.rules:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed = True
