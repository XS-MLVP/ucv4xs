"""Complete logical predecessor lifetimes, not coordinates as functional IDs."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.utage.model.predecessor_retention import Program,PROFILES,MODES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('declared predecessor lifetime required')
    return CoverGroupDef('utage_predecessor_retention_v1',(CoverPointDef('obligation',{
        Program(p,m,t).label+'.'+r:Bin.values(Program(p,m,t).label+'.'+r)
        for p in PROFILES for m in MODES for t in (False,True) for r in RULES}),)).instantiate(
            'kunminghu_v3.utage.predecessor-retention.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.reached,self.closed = program,set(),False
        self.groups = {s:lifetime_coverage(s) for s in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.reached:
            raise ValueError('one witness per declared predecessor obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.reached.add(rule)

    def finish(self):
        if self.closed or self.reached!=set(RULES):
            raise AssertionError('complete predecessor learning, actual persistence and new consumers required')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed = True

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-predecessor-retention.json')
