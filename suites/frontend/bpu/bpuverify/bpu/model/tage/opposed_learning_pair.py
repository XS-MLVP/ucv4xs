"""Two logical learning effects, not a matrix of storage positions."""
from bpuverify.bpu.model.tage.direction_turnaround import (
    TurnaroundProgram,EARLIER_TAKEN,BOTH_NOT_TAKEN)

ORDERS=('positive-then-negative','negative-then-positive')
BOUNDARIES=('both-interior','positive-at-bound','negative-at-bound','both-at-bound')


def pending_states(order):
    if type(order) is not str or order not in ORDERS:raise ValueError('declared feedback arrival order required')
    operations=('positive','negative') if order==ORDERS[0] else ('negative','positive')
    counters={'target-a':0,'target-b':6,'neighbor-b':6}
    waiting={'target-b','neighbor-b'}
    result=[]
    for operation in operations:
        updates=(('target-a',1),) if operation=='positive' else (('target-a',-1),('target-b',-1))
        for name,delta in updates:
            updated=min(7,max(0,counters[name]+delta))
            if updated!=counters[name]:waiting.add(name)
            counters[name]=updated
        result.append(tuple(tuple((name,counters[name]) for name in owner if name in waiting)
            for owner in (('target-b',),('target-a','neighbor-b'))))
    return tuple(result)


def program(order,boundary):
    if type(boundary) is not str or boundary not in BOUNDARIES:raise ValueError('declared old-confidence boundary required')
    plans=pending_states(order)
    positive_bound=boundary in ('positive-at-bound','both-at-bound')
    negative_bound=boundary in ('negative-at-bound','both-at-bound')
    positive=('positive-bound' if positive_bound else 'positive-interior',EARLIER_TAKEN,
        (('target-a',7 if positive_bound else 6),None))
    # The NT tail includes A's executed NT prefix. After a preceding positive
    # update, A's current1 must return to0 even though its old hint was0.
    negative=('negative-bound' if negative_bound else 'negative-interior',BOTH_NOT_TAKEN,
        (('target-a',0) if order==ORDERS[0] else None,('target-b',0 if negative_bound else 1)))
    sequence=(positive,negative) if order==ORDERS[0] else (negative,positive)
    # Main uses the complete original snapshot, not tagged-cache arithmetic.
    main=(0,0) if order==ORDERS[0] else (3,0)
    return TurnaroundProgram(order+'.'+boundary,tuple(item[0] for item in sequence),
        tuple(item[1] for item in sequence),tuple(item[2] for item in sequence),
        plans,(0 if order==ORDERS[0] else 1,5),(1,6),main)


PROGRAMS=tuple(program(order,boundary) for order in ORDERS for boundary in BOUNDARIES)
