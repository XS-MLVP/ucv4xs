"""Full mixed-owner semantic closure is required for checked credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.utage.model.query_identity import Program,MODES,RULES


def lifetime_coverage(status):
    definition=CoverGroupDef('utage_complete_index_alias_v1',(CoverPointDef('obligation',{
        Program(owner,mode).label+'.'+rule:Bin.values(Program(owner,mode).label+'.'+rule)
        for owner in (0,1) for mode in MODES for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.complete-index-alias.' + status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.completed:raise ValueError('one witness per complete-index ownership obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('incomplete full-index ownership cannot obtain checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
