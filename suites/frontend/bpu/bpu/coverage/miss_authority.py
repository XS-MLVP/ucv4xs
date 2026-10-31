"""Input qualification is reached; only correct effects and consumers are checked."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.bpu.model.miss_authority import Program,RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):raise ValueError('unknown lifetime status')
    definition=CoverGroupDef('bpu_miss_authority_v1',(CoverPointDef('obligation',{
        Program(allocate,same).label+'.'+rule:Bin.values(Program(allocate,same).label+'.'+rule)
        for allocate in (False,True) for same in (False,True) for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.bpu.miss-authority.' + status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.completed:raise ValueError('one original miss-authority obligation witness required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('an incomplete or failing source-authority case has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
