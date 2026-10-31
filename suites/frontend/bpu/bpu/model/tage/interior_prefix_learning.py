"""A correctly predicted old NT prefix with no saturated original hints."""
from dataclasses import replace
from suites.frontend.bpu.bpu.model.tage.direction_turnaround import (
    TurnaroundProgram,preparation as original_preparation,CAPTURES,
    EARLIER_TAKEN,EARLIER_NOT_TAKEN,BOTH_NOT_TAKEN)
from suites.frontend.bpu.bpu.model.tage.dual_migration import Step,provider

ORDERS=('positive-then-negative','negative-then-positive')
SCHEDULES=('adjacent-acceptance','after-first-learning')
NEGATIVE='negative-prefix-interior'
SOURCE_CAPTURES=dict(CAPTURES,**{'before:negative-epoch-3':NEGATIVE})


def preparation():
    def state(a,b,ma,mb):return (ma,mb),(provider(0,a),provider(1,b))
    for step in original_preparation():
        if step.name=='negative-epoch-3':
            yield replace(step,expected=state(1,1,0,0))
            yield Step('restore-interior-prefix-a-zero','original',EARLIER_NOT_TAKEN,state(0,1,0,0))
        else:yield step
        if step.name=='negative-interior':
            yield Step('prefix-a-learn-one','original',((0,True,True),),state(1,2,1,0))
            yield Step('prefix-a-learn-two','original',((0,True,True),),state(2,2,2,0))
            yield Step('prefix-main-back-one','original',((0,False,True),),((1,0),(None,None)),False)
            yield Step('prefix-main-back-zero','original',EARLIER_NOT_TAKEN,((0,0),(None,None)),False)


def pending_states(order):
    if order not in ORDERS:raise ValueError('declared arrival order required')
    counters={'target-a':0,'target-b':6,'neighbor-b':6};waiting={'target-b','neighbor-b'};result=[]
    operations=('positive','negative') if order==ORDERS[0] else ('negative','positive')
    for operation in operations:
        updates=(('target-a',1),) if operation=='positive' else (('target-a',-1),('target-b',-1))
        for name,delta in updates:
            counters[name]=max(0,min(7,counters[name]+delta))
            # A valid interior original emits a real write even if the
            # current record is already at its boundary and numerically holds.
            waiting.add(name)
        result.append(tuple(tuple((name,counters[name]) for name in names if name in waiting)
            for names in (('target-b',),('target-a','neighbor-b'))))
    return tuple(result)


class Program(TurnaroundProgram):
    @property
    def schedule(self):return self.name.rsplit('.',1)[1]


def program(order,schedule):
    if type(order) is not str or order not in ORDERS or type(schedule) is not str or schedule not in SCHEDULES:
        raise ValueError('declared original arrival order and learning boundary required')
    positive=('positive-interior',EARLIER_TAKEN,(('target-a',6),None))
    negative=(NEGATIVE,BOTH_NOT_TAKEN,(('target-a',1),('target-b',1)))
    sequence=(positive,negative) if order==ORDERS[0] else (negative,positive)
    return Program(order+'.'+schedule,tuple(item[0] for item in sequence),tuple(item[1] for item in sequence),
        tuple(item[2] for item in sequence),pending_states(order),(0 if order==ORDERS[0] else 1,5),
        (1,6),(0,0) if order==ORDERS[0] else (3,0))


PROGRAMS=tuple(program(order,schedule) for order in ORDERS for schedule in SCHEDULES)
