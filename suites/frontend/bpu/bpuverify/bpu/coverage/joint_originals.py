"""Every semantic obligation, paired reached and completely checked credit."""
import json
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.coverage.sc_admission import Coverage as RuleCoverage
from bpuverify.bpu.model.joint_originals import PROFILES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared evidence role required')
    return CoverGroupDef('bpu_joint_originals_v1',(CoverPointDef('obligation',{
        p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
        'kunminghu_v3.bpu.joint-originals.'+status)


class Coverage(RuleCoverage):
    profiles,rules=PROFILES,RULES
    factory=staticmethod(lifetime_coverage)
    filename='functional-coverage-joint-originals.json'
    def __init__(self,profile):
        super().__init__(profile);self.evidence=None
    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_bpu_joint_originals',json.dumps(self.evidence,sort_keys=True)))
