"""Outcome reversal belongs to the current logical version, not an old hint."""
from dataclasses import dataclass

from bpuverify.bpu.model.tage.dual_migration import provider
from bpuverify.bpu.model.tage.mixed_visibility import PARTIAL_PLAN
from bpuverify.bpu.model.tage.neighbor_migration import HISTORY_PATHS
from bpuverify.bpu.model.tage.asymmetric_retirement import expected_profile
from bpuverify.bpu.model.tage.dual_migration import Step, preparation as initial_preparation

EARLIER_TAKEN = ((0, True, False),)
EARLIER_NOT_TAKEN = ((0, False, False),)
BOTH_NOT_TAKEN = ((0, False, False), (1, False, False))
CAPTURES = {'negative-interior': 'negative-interior', 'negative-bound': 'negative-bound',
            'positive-interior': 'positive-interior', 'positive-bound': 'positive-bound'}


def extra_preparation():
    """Capture correctly predicted opposite outcomes before the migration.

    Wrong outcomes mandate a table reread, so calling them nonreread would
    not test old-source routing at all. These genuine positive/negative
    prediction epochs avoid that substitution. Weak-provider/base agreement
    preserves selectors and useful state without any reference-state writes.
    """
    o='original'
    def state(a,b,ma,mb):return (ma,mb),(provider(0,a),provider(1,b))
    # A1/B5 and base0/3 precede the original save step.
    for index,(b,mb,wrong) in enumerate(((4,2,True),(3,1,True),(2,0,False),(1,0,False),(0,0,False))):
        label={2:'negative-interior',4:'negative-bound'}.get(index,f'negative-epoch-{index}')
        yield Step(label,o,((0,False,False),(1,False,wrong)),state(0,b,0,mb))
    for index,(b,mb) in enumerate(((1,1),(2,2),(3,3))):
        yield Step(f'restore-b-positive-{index}',o,((0,False,False),(1,True,True)),state(0,b,0,mb))
    for index,mb in enumerate((2,1)):
        yield Step(f'align-weak-b-base-{index}',o,((0,False,False),(1,False,True)),
                   ((0,mb),(None,None)),False)
    yield Step('restore-b-through-weak',o,((0,False,False),(1,True,True)),state(0,4,0,2))
    yield Step('restore-b-strong',o,((0,False,False),(1,True,False)),state(0,5,0,3))
    yield Step('restore-a-before-positive',o,((0,True,True),),state(1,5,1,3))
    yield Step('align-original-base',o,((0,False,False),(1,True,False)),((0,3),(None,None)),False)
    yield Step('positive-a-two',o,((0,True,True),),state(2,5,1,3))
    yield Step('positive-a-weak',o,((0,True,True),),state(3,5,2,3))
    yield Step('align-weak-a-base',o,((0,False,True),(1,True,False)),((1,3),(None,None)),False)
    yield Step('positive-a-through-weak',o,((0,True,True),),state(4,5,2,3))
    yield Step('positive-interior',o,EARLIER_TAKEN,state(5,5,3,3))
    yield Step('positive-a-six',o,EARLIER_TAKEN,state(6,5,3,3))
    yield Step('positive-bound',o,EARLIER_TAKEN,state(7,5,3,3))
    for index,(a,ma) in enumerate(((6,2),(5,1),(4,0))):
        yield Step(f'restore-a-negative-{index}',o,((0,False,True),),state(a,5,ma,3))
    for index,ma in enumerate((1,2)):
        yield Step(f'align-descending-weak-a-{index}',o,((0,True,True),),((ma,3),(None,None)),False)
    yield Step('restore-a-through-weak',o,((0,False,True),),state(3,5,1,3))
    yield Step('restore-a-and-temporarily-extend-b',o,((0,False,False),(1,True,False)),state(2,6,0,3))
    yield Step('restore-original-providers',o,((0,False,False),(1,False,True)),state(1,5,0,2))
    yield Step('restore-original-base',o,((0,False,False),(1,True,False)),((0,3),(None,None)),False)


def preparation():
    for step in initial_preparation():
        if step.save:
            yield from extra_preparation()
        yield step


@dataclass(frozen=True)
class TurnaroundProgram:
    name: str
    late_sources: tuple
    late_outcomes: tuple
    late_proposals: tuple
    pending_after: tuple
    target_counters: tuple
    neighbor_counters: tuple
    main_counters: tuple

    @property
    def final_plan(self):
        return self.pending_after[-1]

    def pending_before(self, index):
        if type(index) is not int or not 0 <= index < len(self.late_sources):
            raise ValueError('undeclared direction-turnaround input')
        return PARTIAL_PLAN if index == 0 else self.pending_after[index-1]

    def profile(self, phase, name):
        if phase not in ('initial', 'mixed', 'blocked', 'serviced') or name not in HISTORY_PATHS:
            raise ValueError('undeclared direction-turnaround consumer')
        if phase == 'initial':
            return expected_profile(name, serviced=False)
        if name == 'displaced':
            pair = None, None
        elif name == 'original':
            a, b = self.target_counters if phase == 'serviced' else (0, 5)
            pair = provider(1, a), provider(0, b)
        else:
            a, b = self.neighbor_counters if phase == 'serviced' else (1, 5)
            pair = provider(0, a), provider(1, b)
        main = (0, 3) if phase == 'mixed' else self.main_counters
        return main, pair


TARGET_ONE = ((('target-b', 6),), (('target-a', 1), ('neighbor-b', 6)))
TARGET_DECREASE = ((('target-b', 5),), (('neighbor-b', 6),))
TARGET_BACK = ((('target-b', 6),), (('target-a', 0), ('neighbor-b', 6)))

PROGRAMS = (
    TurnaroundProgram('old-positive-reenters-lower', ('positive-interior',), (EARLIER_TAKEN,),
        ((('target-a', 6), None),), (TARGET_ONE,), (1, 6), (1, 6), (3, 3)),
    TurnaroundProgram('saturated-positive-reenters-lower', ('positive-bound',), (EARLIER_TAKEN,),
        ((('target-a', 7), None),), (TARGET_ONE,), (1, 6), (1, 6), (3, 3)),
    TurnaroundProgram('old-negative-reverses-pending-upper', ('negative-interior',), (BOTH_NOT_TAKEN,),
        ((None, ('target-b', 1)),), (TARGET_DECREASE,), (0, 5), (1, 6), (0, 0)),
    TurnaroundProgram('saturated-negative-reverses-pending-upper', ('negative-bound',), (BOTH_NOT_TAKEN,),
        ((None, ('target-b', 0)),), (TARGET_DECREASE,), (0, 5), (1, 6), (0, 0)),
    TurnaroundProgram('old-negative-cancels-pending-positive', ('positive-interior', 'old-target'),
        (EARLIER_TAKEN, EARLIER_NOT_TAKEN),
        ((('target-a', 6), None), (('target-a', 1), None)),
        (TARGET_ONE, TARGET_BACK), (0, 6), (1, 6), (0, 3)),
    TurnaroundProgram('new-boundary-cancels-pending-positive', ('positive-interior', 'mixed-target'),
        (EARLIER_TAKEN, EARLIER_NOT_TAKEN),
        ((('target-a', 6), None), (None, ('target-a', 0))),
        (TARGET_ONE, TARGET_BACK), (0, 6), (1, 6), (0, 3)),
)
