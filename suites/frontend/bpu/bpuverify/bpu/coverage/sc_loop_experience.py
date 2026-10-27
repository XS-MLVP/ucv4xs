"""One bin per complete semantic obligation, not per storage coordinate."""
import json
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.coverage.sc_admission import Coverage as RuleCoverage
from bpuverify.bpu.model.sc_loop_experience import PROFILES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared loop experience evidence role required')
    return CoverGroupDef('bpu_sc_loop_experience_v1',(CoverPointDef('obligation',{
        profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.bpu.sc-loop-experience.'+status)


class Coverage(RuleCoverage):
    profiles,rules=PROFILES,RULES
    factory=staticmethod(lifetime_coverage)
    filename='functional-coverage-sc-loop-experience.json'
    def __init__(self,profile):
        super().__init__(profile)
        self.evidence=None
    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_bpu_sc_loop_experience',json.dumps(self.evidence,sort_keys=True)))
