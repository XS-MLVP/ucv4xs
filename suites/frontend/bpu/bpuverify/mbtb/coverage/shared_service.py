"""Shared-service no-loss obligations, without credit from a mere prepare."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.mbtb.model.shared_service import PROGRAMS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared evidence role required')
    bins={p.label+'.'+r:Bin.values(p.label+'.'+r) for p in PROGRAMS for r in RULES}
    return CoverGroupDef('mbtb_shared_service_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.mbtb.shared-service.'+status)


class Coverage:
    def __init__(self,program):
        self.program=program;self.groups={s:lifetime_coverage(s) for s in ('reached','checked')};self.seen=[]
    def reach(self,rule):
        if rule not in RULES or rule in self.seen:raise ValueError('new declared semantic obligation required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule));self.seen.append(rule)
    def finish(self):
        assert set(self.seen)==set(RULES),'partial shared-service program has no checked credit'
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
