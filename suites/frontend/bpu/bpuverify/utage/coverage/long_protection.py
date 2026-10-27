"""Only a complete original-to-consumer lifetime earns checked credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.utage.model.long_protection import Program,MODES,LIFETIMES,RULES


def lifetime_coverage(status):
    definition=CoverGroupDef('utage_long_provider_protection_v1',(CoverPointDef('obligation',{
        Program(first,mode,lifetime).label+'.'+rule:Bin.values(Program(first,mode,lifetime).label+'.'+rule)
        for first in (0,1) for mode in MODES for lifetime in LIFETIMES for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.long-provider-protection.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.completed:raise ValueError('one witness per declared obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness);self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('incomplete long-provider ownership lifetime')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
