"""Reached action transport is not proof of correct retirement."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.ras.model.commit_action import Program,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown lifetime status')
    definition=CoverGroupDef('ras_original_commit_action_v1',(CoverPointDef('obligation',{
        Program(action).label+'.'+rule:Bin.values(Program(action).label+'.'+rule)
        for action in (1,2,3) for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.ras.original-commit-action.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.seen:raise ValueError('one original commit witness required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.closed or self.seen!=set(RULES):raise AssertionError('incomplete or failed retirement has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
