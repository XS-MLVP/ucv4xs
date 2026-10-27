"""Source/gate lifetime obligations, never physical storage coordinates."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.sc.model.eligibility import RULES as ORIGINAL_RULES

RULES=(*ORIGINAL_RULES,'disabled-use-suppressed','disabled-old-feedback-ignored','reopen-without-relearning')
PROFILES=tuple(mode+'.'+order for mode in ('serial','pipelined') for order in ('positive-first','negative-first'))


class EnableCoverage:
    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={status:CoverGroupDef('sc_original_enable_lifetime_v1',(
            CoverPointDef('obligation',{profile+'.'+rule:Bin.values(profile+'.'+rule)
                for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.sc.original-enable-lifetime.'+status) for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        if rule not in RULES:raise ValueError('unknown SC source/gate lifetime obligation')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)

    def write(self,path):
        write_functional_coverage(CoverageDatabase(self.groups.values()),path/'functional-original-enable-lifetime.json')
