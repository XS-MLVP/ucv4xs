"""Behavioral proof obligations, no storage-coordinate cross."""
import json
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.bpu.coverage.sc_admission import Coverage as RuleCoverage
from suites.frontend.bpu.bpu.model.joint_direction_learning import PROFILES,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared joint learning evidence role required')
    return CoverGroupDef('bpu_joint_direction_learning_v1',(CoverPointDef('obligation',{
        p+'.'+r:Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),)).instantiate(
        'kunminghu_v3.bpu.joint-direction-learning.'+status)


class Coverage(RuleCoverage):
    profiles,rules=PROFILES,RULES
    factory=staticmethod(lifetime_coverage)
    filename='functional-coverage-joint-direction-learning.json'
    def __init__(self,profile):
        super().__init__(profile);self.evidence=None
    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_bpu_joint_direction_learning',json.dumps(self.evidence,sort_keys=True)))
