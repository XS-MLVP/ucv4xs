"""Do not credit a source lifetime until its entire DUT program passes."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from bpuverify.bpu.model.owned_return_stack import OBLIGATIONS


def lifetime_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('return-stack coverage requires reached or checked')
    return CoverGroupDef('owned_return_stack_v1',(
        CoverPointDef('obligation',{name:Bin.values(name) for name in OBLIGATIONS}),
    )).instantiate('kunminghu_v3.bpu.owned-return-stack.'+status,
        contract='autonomous calls/returns; exact original recovery and retirement; never sampled operation golden inputs')


class OwnedReturnCoverage:
    def __init__(self,program):
        self.program=program
        self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.reached=set()
        self.closed=False

    def record(self,rule,**facts):
        if self.closed or rule not in self.program.rules:
            raise ValueError('undeclared or already closed return-stack obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=facts)
        self.reached.add(rule)

    def finish(self):
        if self.closed or self.reached!=set(self.program.rules):
            raise AssertionError('all owned return-stack obligations and scope exits must pass before checked credit')
        for rule in self.program.rules:
            self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
