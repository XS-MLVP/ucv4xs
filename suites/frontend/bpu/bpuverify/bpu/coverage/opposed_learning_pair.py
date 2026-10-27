"""Both real learning lifetimes must close before checked credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.coverage.direction_turnaround import RULES
from bpuverify.bpu.model.tage.opposed_learning_pair import PROGRAMS


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared opposed-learning lifetime status required')
    bins={p.name+'.'+rule:Bin.values(p.name+'.'+rule) for p in PROGRAMS for rule in RULES}
    return CoverGroupDef('bpu_opposed_learning_pair_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.opposed-learning-pair.'+status,
        contract='two original prediction epochs -> independent current learning -> actual services -> fresh consumers')


class Coverage:
    def __init__(self,program):
        if program not in PROGRAMS:raise ValueError('unknown semantic opposed-learning pair')
        self.program=program
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        if status not in self.groups or rule not in RULES:raise ValueError('declared opposed-learning obligation required')
        self.groups[status].sample(dict(obligation=self.program.name+'.'+rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-opposed-learning-pair.json')
