"""Fixed paired semantic definitions, also required by production merge gates."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.utage.model.read_lifetime import PROFILES,RELATIONS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown lifetime status')
    definition=CoverGroupDef('utage_read_version_lifetime_v1',(CoverPointDef('obligation',{
        '.'.join((profile,relation,rule)):Bin.values('.'.join((profile,relation,rule)))
        for profile in PROFILES for relation in RELATIONS for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.read-version-lifetime.'+status)


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


def late_replacement_coverage(status):
    from bpuverify.utage.model.read_lifetime import REBUILD_PROFILES,REBUILD_RULES,MODES
    if status not in ('reached','checked'):raise ValueError('unknown late-owner status')
    definition=CoverGroupDef('utage_late_owner_rebuild_v1',(CoverPointDef('obligation',{
        '.'.join((profile,mode,rule)):Bin.values('.'.join((profile,mode,rule)))
        for profile in REBUILD_PROFILES for mode in MODES for rule in REBUILD_RULES}),))
    return definition.instantiate('kunminghu_v3.utage.late-owner-rebuild.'+status)


class LateReplacementCoverage:
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={status:late_replacement_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        from bpuverify.utage.model.read_lifetime import REBUILD_RULES
        if self.closed or rule not in REBUILD_RULES or rule in self.completed:raise ValueError('one declared late-owner witness required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.completed.add(rule)

    def finish(self):
        from bpuverify.utage.model.read_lifetime import REBUILD_RULES
        if self.closed or self.completed!=set(REBUILD_RULES):raise AssertionError('incomplete old-owner reconstruction lifetime')
        for rule in REBUILD_RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
