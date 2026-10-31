"""Distinct correct old predictions cumulatively cross confidence boundaries.

The trace is declared before driving. It is not derived from observed entry
values, dirty bits, hit ranks, original metadata or service receipts.
"""
from collections import Counter

from suites.frontend.bpu.bpu.model.tage.direction_turnaround import (
    CAPTURES as ORIGINAL_CAPTURES,TurnaroundProgram,EARLIER_TAKEN,EARLIER_NOT_TAKEN,BOTH_NOT_TAKEN)
from suites.frontend.bpu.bpu.model.tage.partial_residency import PAIR

CAPTURES={**ORIGINAL_CAPTURES,'restore-a-and-temporarily-extend-b':'negative-a-positive-b'}
SOURCE_PROFILES={'positive-interior':(5,5,(3,3)),'positive-bound':(7,5,(3,3)),
                 'negative-interior':(0,2,(0,0)),'negative-bound':(0,0,(0,0)),
                 'negative-a-positive-b':(2,6,(0,3))}


def _program(name,legs):
    # These are semantic directions and source epochs, not physical slots.
    definitions={
        'increase-a':('positive-interior',EARLIER_TAKEN,(('target-a',6),None)),
        'decrease-b':('negative-interior',BOTH_NOT_TAKEN,(None,('target-b',1))),
        'decrease-a':('negative-a-positive-b',EARLIER_NOT_TAKEN,(('target-a',1),None)),
        'increase-b':('negative-a-positive-b',PAIR,(('target-a',1),('target-b',7))),
    }
    a,b,dirty_a=0,6,False
    sources,outcomes,proposals,plans=[],[],[],[]
    counts=Counter()
    for action,count in legs:
        role,outcome,proposal=definitions[action]
        for _ in range(count):
            sources.append(f'{role}#{counts[role]}');counts[role]+=1
            outcomes.append(outcome);proposals.append(proposal)
            if action=='increase-a':a=min(7,a+1);dirty_a=True
            elif action=='decrease-b':b=max(0,b-1)
            elif action=='decrease-a':a=max(0,a-1);dirty_a=True
            else:a=max(0,a-1);b=min(7,b+1);dirty_a=True
            plans.append(((('target-b',b),),
                          ((('target-a',a),) if dirty_a else ())+(('neighbor-b',6),)))
    main=(3,3) if legs[-1][0]=='increase-a' else (0,0) if legs[-1][0]=='decrease-b' else (0,3)
    return TurnaroundProgram(name,tuple(sources),tuple(outcomes),tuple(proposals),tuple(plans),
                             (a,b),(1,6),main)


PROGRAMS=(
    _program('old-positive-reaches-upper-and-holds',(('increase-a',8),)),
    _program('old-negative-reaches-lower-and-holds',(('decrease-b',7),)),
    _program('upper-hold-then-reverse-to-lower',(('increase-a',8),('decrease-a',8))),
    _program('lower-hold-then-reverse-to-upper',(('decrease-b',7),('increase-b',8))),
)


def source_counts(program):
    if program not in PROGRAMS:raise ValueError('unknown confidence-boundary program')
    counts=Counter(name.split('#')[0] for name in program.late_sources)
    return {role:max(1,counts[role]) for role in SOURCE_PROFILES}
