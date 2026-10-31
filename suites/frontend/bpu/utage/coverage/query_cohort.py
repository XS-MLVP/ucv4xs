"""A checked bin needs complete read ages, turnover and fresh consumers."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.utage.model.query_cohort import PROFILES,ANCESTRIES,RULES


def lifetime_coverage(status):
    definition=CoverGroupDef('utage_query_cohort_turnover_v1',(CoverPointDef('obligation',{
        '.'.join((profile,ancestry,rule)):Bin.values('.'.join((profile,ancestry,rule)))
        for profile in PROFILES for ancestry in ANCESTRIES for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.query-cohort-turnover.' + status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.completed:raise ValueError('one semantic obligation witness per original cohort')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('an incomplete version cohort cannot receive checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
