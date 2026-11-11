"""A call-stack operation, not the generated pointer/slot implementation."""
from dataclasses import dataclass

A,B,C=(0x40001008,0x40002008,0x40003008)
RULES=('normally-retired-prefix','genuine-original-source','complete-public-input',
       'actual-registered-commit','retained-program-effect','independent-consumers','immutable-source')


@dataclass(frozen=True)
class Program:
    action:int

    def __post_init__(self):
        if type(self.action) is not int or self.action not in (1,2,3):
            raise ValueError('return, call or return-and-call required')

    @property
    def label(self):return {1:'return',2:'call',3:'return-and-call'}[self.action]

    @property
    def stack(self):
        frames=[A,B]
        if self.action&1:frames.pop()
        if self.action&2:frames.append(C)
        return tuple(frames)

    def state(self):
        return dict(action=self.action,label=self.label,original_speculation='call',
            prefix=(A,B),source_address=C,expected_retained_program=self.stack,
            full_FTQ_reachability_proved=False,physical_enumeration=False)


