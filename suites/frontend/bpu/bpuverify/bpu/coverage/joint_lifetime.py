"""Paired complete-lifetime obligations, required by the production merge gate."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.model.joint_lifetime import MODES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown lifetime status')
    definition=CoverGroupDef('bpu_joint_late_sources_v1',(
        CoverPointDef('obligation',{p+'.'+r:Bin.values(p+'.'+r) for p in MODES for r in RULES}),))
    return definition.instantiate('kunminghu_v3.bpu.joint-late-sources.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if rule not in RULES or rule in self.completed or self.closed:
            raise ValueError('unknown, repeated or closed lifetime obligation')
        profile=getattr(self.program,'profile',getattr(self.program,'mode',None))
        self.groups['reached'].sample(dict(obligation=profile+'.'+rule),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        if self.closed or self.completed!=set(RULES):raise AssertionError('incomplete lifetime')
        profile=getattr(self.program,'profile',getattr(self.program,'mode',None))
        for rule in RULES:self.groups['checked'].sample(dict(obligation=profile+'.'+rule))
        self.closed=True
