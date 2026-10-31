"""Independent histories accumulate their own learning at retained capacity."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.tage.service import ServiceProgram,FULL_RETAINED_RETOUCH

ORDERS={'rounds':(0,1,2,3)*3,'finish-each':(0,1,2,3,0,0,1,1,2,2,3,3)}


@dataclass(frozen=True,slots=True)
class Program(ServiceProgram):
    name:str

    def __post_init__(self):
        super(Program,self).__post_init__()
        if type(self.name) is not str or self.name not in ORDERS or self.feedback_order!=ORDERS[self.name]:
            raise ValueError('declared shared learning order required')
        if self.paths!=FULL_RETAINED_RETOUCH.paths:
            raise ValueError('one logical retained-capacity program, not physical coordinate variants')

    def counters_after(self,history,count):
        if type(history) is not int or not 0<=history<self.history_count or type(count) is not int or not 0<=count<=3:
            raise ValueError('declared history and its accepted update count required')
        return max(0,2-count),min(7,5+count)


PROGRAMS=tuple(Program(FULL_RETAINED_RETOUCH.paths,order,name) for name,order in ORDERS.items())
