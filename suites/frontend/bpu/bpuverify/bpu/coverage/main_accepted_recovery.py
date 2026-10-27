"""Only complete qualified-input, recovery, service and consumer lifetimes count."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.model.main_accepted_recovery import Program,FATES,MOMENTS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared accepted-learning lifetime status required')
    bins={Program(f,m).label+'.'+r:Bin.values(Program(f,m).label+'.'+r) for f in FATES for m in MOMENTS for r in RULES}
    return CoverGroupDef('bpu_main_accepted_recovery_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.main-accepted-recovery.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.seen:raise ValueError('one witness per declared learning/recovery obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness);self.seen.add(rule)

    def finish(self):
        if self.closed or self.seen!=set(RULES):raise AssertionError('incomplete accepted-learning lifetime has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
