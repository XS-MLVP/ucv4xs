"""Logical access history and learning identity, independent of actual PLRU bits."""
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources
from suites.frontend.bpu.bpu.model.tage.service import FULL_RETAINED_REPLACEMENT,STREAM_PC
from suites.frontend.bpu.tage.model.semantic import TageReference

PATHS=FULL_RETAINED_REPLACEMENT.paths
READ_STREAM=STREAM_PC+(1<<20)


@dataclass(frozen=True,slots=True)
class Learning:
    history:int
    counters:tuple


@dataclass(frozen=True,slots=True)
class OwnerLearning:
    history:int
    counter:int


class LearningRecency:
    """Four logical service positions in two groups; no sampled storage state.

    Victim selection uses the less-recent group and less-recent member. The
    insertion-only alternative is a diagnostic contract, never a tolerance
    fallback for an access-contract comparison.
    """
    def __init__(self,*,policy='learning'):
        if policy not in ('insertion','learning'):raise ValueError('unknown learning retention policy')
        self.policy=policy
        self.slots=[None]*4
        self.last_group=None
        self.last_member=[None,None]
        self.removed=[]

    def learn(self,history,initial):
        if type(history) is not int or not 0<=history<5:raise ValueError('unknown logical history')
        if type(initial) is not tuple or len(initial)!=2 or any(type(c) is not int or not 0<=c<=7 for c in initial):
            raise ValueError('two original confidence values required')
        existing=next((i for i,r in enumerate(self.slots) if r is not None and r.history==history),None)
        index=existing
        if index is None:
            index=next((i for i,r in enumerate(self.slots) if r is None),None)
            if index is None:
                group=1-self.last_group
                index=2*group+(1-self.last_member[group])
                self.removed.append(self.slots[index].history)
        current=initial if existing is None else self.slots[index].counters
        self.slots[index]=Learning(history,(max(0,current[0]-1),min(7,current[1]+1)))
        if existing is None or self.policy=='learning':
            group,member=divmod(index,2)
            self.last_group=group;self.last_member[group]=member
        return tuple(self.slots)


@dataclass(frozen=True,slots=True)
class RetouchProgram:
    name:str
    retouches:tuple
    victim:int
    mode:str='overlapped'

    @property
    def paths(self):return PATHS
    @property
    def history_count(self):return 5
    @property
    def retained_count(self):return 4
    @property
    def initial_base(self):return (0,3)
    @property
    def feedback_order(self):return (0,1,2,3,*self.retouches,4)
    @property
    def retained_histories(self):return tuple(h for h in range(5) if h!=self.victim)
    @property
    def empty_state(self):return (None,)*4

    def branch_outcomes(self,index):return ((0,False,False),(1,True,False))

    def input_owners(self,index):return tuple(branch for branch,_,_ in self.branch_outcomes(index))

    @property
    def main_update_counts(self):
        return tuple(sum(owner in self.input_owners(i) for i in range(len(self.feedback_order))) for owner in range(2))

    def owner_records(self,snapshot,owner):
        return tuple(None if r is None else OwnerLearning(r.history,r.counters[owner]) for r in snapshot)

    def initial_counters(self,history):
        if type(history) is not int or not 0<=history<5:raise ValueError('unknown program history')
        return (1,6) if history==0 else (2,5)

    def trace(self,*,policy='learning'):
        model=LearningRecency(policy=policy)
        result=tuple(model.learn(h,self.initial_counters(h)) for h in self.feedback_order)
        if policy=='learning' and model.removed!=[self.victim]:raise AssertionError('non-discriminating declared victim')
        return result

    def expected_counters(self,history):
        record=next((r for r in self.trace()[-1] if r.history==history),None)
        return self.initial_counters(history) if record is None else record.counters


PROGRAMS=(
    RetouchProgram('protect-a-before-new-history',(0,),2),
    RetouchProgram('a-then-c-before-new-history',(0,2),1),
    RetouchProgram('c-then-a-before-new-history',(2,0),3),
    RetouchProgram('c-retouch-keeps-original-victim',(2,),0),
    RetouchProgram('d-retouch-keeps-original-victim',(3,),0),
    RetouchProgram('settled-a-before-new-history',(0,),2,'settled'),
)


class AccessRecencySources(DirectionSources):
    """Declare the tested contract before any clock or actual observation."""
    def __init__(self):
        super().__init__()
        self.tage=TageReference(retention_policy='learning')
