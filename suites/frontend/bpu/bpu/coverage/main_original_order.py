"""Only full original-input, service and consumer closure earns checked bins."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from suites.frontend.bpu.bpu.model.main_original_order import Program,ORDERS,PHASES,COUNTERS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared status required')
    bins={Program(order,phase,counter).label+'.'+rule:Bin.values(Program(order,phase,counter).label+'.'+rule)
        for order in ORDERS for phase in PHASES for counter in COUNTERS for rule in RULES}
    return CoverGroupDef('bpu_original_resolution_order_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.original-resolution-order.'+status)


class Coverage:
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}

    def reach(self,rule,**witness):
        if self.closed or rule not in RULES or rule in self.seen:raise ValueError('one witness per declared semantic obligation required')
        self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule),metadata=witness)
        self.seen.add(rule)

    def finish(self):
        if self.closed or self.seen!=set(RULES):raise AssertionError('incomplete original-resolution lifetime has no checked credit')
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
