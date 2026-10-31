"""Warm eligibility and lifetime proof, not bank/way coverage."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.sc.model.eligibility import RULES

PROFILES=tuple(mode+'.'+order for mode in ('serial','pipelined') for order in ('positive-first','negative-first'))


class EligibilityCoverage:
    def __init__(self,program):
        self.program=program
        self.evidence=None
        self.groups={status:CoverGroupDef('sc_warm_eligibility_v2',(
            CoverPointDef('obligation',{profile+'.'+rule:Bin.values(profile+'.'+rule)
                for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.sc.warm-eligibility.'+status,
            contract='real eligible learning -> strong evidence -> original source gate -> fresh restored consumers')
            for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        if rule not in RULES:raise ValueError('unknown warm eligibility obligation')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output/'functional-coverage-warm-eligibility.json')
