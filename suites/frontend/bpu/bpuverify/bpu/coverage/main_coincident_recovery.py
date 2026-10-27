"""Separate paired evidence: old strictly-earlier PASS grants no same-edge credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.model.main_coincident_recovery import PROGRAMS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared same-boundary evidence role required')
    bins={p.label+'.'+r:Bin.values(p.label+'.'+r) for p in PROGRAMS for r in RULES}
    return CoverGroupDef('bpu_main_coincident_recovery_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.main-coincident-recovery.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}
    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.seen:raise ValueError('one witness per same-boundary obligation required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness);self.seen.add(rule)
    def finish(self):
        if self.closed or self.seen!=set(RULES):raise AssertionError('incomplete same-boundary learning/recovery has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
