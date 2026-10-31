"""Four complete human lifetimes, never bank/set bins."""
import json
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.model.short_competition import PROFILES,RULES
from suites.frontend.bpu.coverage.exports import write_functional_coverage


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared competition lifetime status required')
    return CoverGroupDef('bpu_short_branch_competition_v1',(CoverPointDef('obligation',{
        profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.bpu.short-branch-competition.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,**witness):
        if status not in self.groups or rule not in RULES:raise ValueError('declared competition obligation required')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)
    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-short-branch-competition.json')
    def attach_evidence(self,properties):
        if self.evidence is not None:properties.append(('semantic_bpu_short_branch_competition',json.dumps(self.evidence,sort_keys=True)))
