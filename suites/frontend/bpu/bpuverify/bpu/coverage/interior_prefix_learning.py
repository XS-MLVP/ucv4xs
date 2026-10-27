"""Preserve all15 existing lifetime obligations and add two discriminators."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.coverage.direction_turnaround import RULES as ORIGINAL_RULES
from bpuverify.bpu.model.tage.interior_prefix_learning import PROGRAMS

RULES=(*ORIGINAL_RULES,'every-original-prefix-hint-interior','declared-learning-boundary')


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared lifecycle coverage status required')
    bins={p.name+'.'+rule:Bin.values(p.name+'.'+rule) for p in PROGRAMS for rule in RULES}
    return CoverGroupDef('bpu_interior_prefix_learning_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.interior-prefix-learning.'+status)


class Coverage:
    def __init__(self,program):
        if program not in PROGRAMS:raise ValueError('declared complete-prefix program required')
        self.program=program;self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        if status not in self.groups or rule not in RULES:raise ValueError('declared obligation required')
        self.groups[status].sample(dict(obligation=self.program.name+'.'+rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-interior-prefix-learning.json')
