"""Full call/correction/return/retirement lifetimes, not physical slot bins."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.model.ras.adjacent_recursion import Program,DEPTHS,RELATIONS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared recursion lifetime status required')
    bins={Program(depth,relation).label+'.'+rule:Bin.values(Program(depth,relation).label+'.'+rule)
        for depth in DEPTHS for relation in RELATIONS for rule in RULES}
    return CoverGroupDef('bpu_adjacent_recursive_return_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.adjacent-recursive-return.'+status,
        contract='near-capacity logical calls -> owned target corrections -> complete natural returns -> exact per-layer retirement')


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.finished=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reached(self,rule,**witness):
        if self.finished or rule not in RULES or rule in self.seen:raise ValueError('one witness per semantic recursive obligation required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.finished or self.seen!=set(RULES):raise AssertionError('incomplete recursive lifetime has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.finished=True
