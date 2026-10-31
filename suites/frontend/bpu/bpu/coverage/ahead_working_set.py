"""Semantic program obligations; no physical-coordinate coverage dimension."""
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.ahead_working_set import SIZES, KINDS, LIFETIMES, AheadWorkingSetProgram
from suites.frontend.bpu.bpu.model.ahead_working_set import PREFIX_PROFILES,PREFIX_RULES


def prefix_lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared prefix lifetime required')
    keys=tuple(profile+'.'+rule for profile in PREFIX_PROFILES for rule in PREFIX_RULES)
    return CoverGroupDef('bpu_ahead_prefix_working_set_v1',(CoverPointDef('obligation',
        {key:Bin.values(key) for key in keys}),)).instantiate('kunminghu_v3.bpu.ahead-prefix-working-set.'+status)


class AheadWorkingSetCoverage:
    def __init__(self, program):
        self.program, self.evidence = program, None
        keys = tuple(f'{p.label}.{rule}' for size in SIZES for kinds in KINDS for lifetime in LIFETIMES
            for p in (AheadWorkingSetProgram(size, kinds, lifetime),) for rule in p.rules)
        self.groups = {status: CoverGroupDef('bpu_ahead_working_set_v1', (
            CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.ahead-working-set.' + status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if rule not in self.program.rules:
            raise ValueError('unknown working-set lifetime obligation')
        self.groups[status].sample(dict(obligation=self.program.label + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-ahead-working-set.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('ahead_working_set', json.dumps(self.evidence, ensure_ascii=False)))


class PrefixWorkingSetCoverage(AheadWorkingSetCoverage):
    def __init__(self,program):
        self.program,self.evidence=program,None
        self.groups={status:prefix_lifetime_coverage(status) for status in ('reached','checked')}

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output/'functional-coverage-ahead-prefix-working-set.json')

    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append(('semantic_ahead_prefix_working_set',json.dumps(self.evidence,ensure_ascii=False)))
