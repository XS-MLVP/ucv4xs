"""Only a complete sharing/isolation lifetime receives checked evidence."""
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.bpu.model.short_context_ownership import PROFILES, RULES
from bpuverify.common.coverage.exports import write_functional_coverage


class ShortContextCoverage:
    rules=RULES
    def __init__(self, program):
        self.program, self.evidence = program, None
        obligations = tuple(profile + '.' + rule for profile in PROFILES for rule in RULES)
        self.groups = {status: CoverGroupDef('bpu_short_context_ownership_v1', (
            CoverPointDef('obligation', {item:Bin.values(item) for item in obligations}),
        )).instantiate('kunminghu_v3.bpu.short-context-ownership.' + status,
            contract='two real branch programs -> shared short context -> selective learning -> all original consumers')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in self.rules:
            raise ValueError('unknown short-context evidence obligation')
        self.groups[status].sample(dict(obligation=self.program.profile + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-short-context-ownership.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('short_context_ownership', json.dumps(self.evidence, sort_keys=True)))


from bpuverify.bpu.model.short_context_ownership import DIRECTION_PROFILES,DIRECTION_RULES


def direction_lifetime_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('declared direction lifetime required')
    return CoverGroupDef('bpu_short_context_direction_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in DIRECTION_PROFILES for rule in DIRECTION_RULES}),
        )).instantiate('kunminghu_v3.bpu.short-context-direction.'+status)


class ShortDirectionCoverage(ShortContextCoverage):
    rules=DIRECTION_RULES

    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={state:direction_lifetime_coverage(state) for state in ('reached','checked')}

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-short-context-direction.json')

    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_bpu_short_context_direction',json.dumps(self.evidence,sort_keys=True)))


from bpuverify.bpu.model.short_context_ownership import WORKING_SET_PROFILES,WORKING_SET_RULES


def working_set_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared cross-branch lifetime status required')
    return CoverGroupDef('bpu_short_cross_branch_working_set_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in WORKING_SET_PROFILES for rule in WORKING_SET_RULES}),
        )).instantiate('kunminghu_v3.bpu.short-cross-branch-working-set.'+status)


class ShortCrossBranchCoverage(ShortContextCoverage):
    rules=WORKING_SET_RULES
    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={status:working_set_coverage(status) for status in ('reached','checked')}
    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-short-cross-branch-working-set.json')
    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_bpu_short_cross_branch_working_set',json.dumps(self.evidence,sort_keys=True)))
