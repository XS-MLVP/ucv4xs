"""Native duplicate creation, destination clear and both consumers must close."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.bpu.model.main_duplicate_cleanup import Program,IDENTITIES,OVERLAPS,PREPARATIONS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared duplicate cleanup status required')
    bins={Program(i,o,p).label+'.'+r:Bin.values(Program(i,o,p).label+'.'+r) for i in IDENTITIES for o in OVERLAPS for p in PREPARATIONS for r in RULES}
    return CoverGroupDef('bpu_main_duplicate_cleanup_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.main-duplicate-cleanup.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.seen:raise ValueError('one witness per duplicate cleanup obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness);self.seen.add(rule)

    def finish(self):
        if self.closed or self.seen!=set(RULES):raise AssertionError('incomplete duplicate cleanup has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
