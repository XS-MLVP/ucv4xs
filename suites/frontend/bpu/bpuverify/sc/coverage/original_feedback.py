"""The three semantic rejection causes are not a bank/way matrix."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.sc.model.eligibility import RULES as QUERY_RULES,GATES

RULES=(*QUERY_RULES,'ignored-original-feedback','fresh-after-rejection')
PROFILES=tuple(mode+'.'+order+'.ignore-'+gate for mode in ('serial','pipelined')
    for order in ('positive-first','negative-first') for gate in GATES)


class FeedbackCoverage:
    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={status:CoverGroupDef('sc_ignored_original_feedback_v1',(
            CoverPointDef('obligation',{profile+'.'+rule:Bin.values(profile+'.'+rule)
                for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.sc.ignored-original-feedback.'+status)
            for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        if rule not in RULES:raise ValueError('unknown original-feedback obligation')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)

    def write(self,path):
        write_functional_coverage(CoverageDatabase(self.groups.values()),path/'functional-ignored-original-feedback.json')
