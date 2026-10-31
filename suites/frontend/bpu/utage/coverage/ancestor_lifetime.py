"""Fixed paired semantic definitions, also required by production merge gates."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.utage.model.ancestor_lifetime import PROFILES,RELATIONS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown lifetime status')
    definition=CoverGroupDef('utage_distinct_ancestor_learning_lifetime_v1',(CoverPointDef('obligation',{
        '.'.join((profile,relation,rule)):Bin.values('.'.join((profile,relation,rule)))
        for profile in PROFILES for relation in RELATIONS for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.distinct-ancestor-learning.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.completed:raise ValueError('one declared lifetime witness')
        self.groups['reached'].sample(dict(obligation='.'.join((self.program.profile,self.program.relation,rule))),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('incomplete lifetime')
        for rule in RULES:self.groups['checked'].sample(dict(obligation='.'.join((self.program.profile,self.program.relation,rule))))
        self.closed=True
