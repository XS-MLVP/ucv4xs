"""A feedback subset touches only its own logical learning owner.

Two independent recent-history trees predict different victims before the
same new-history input. No actual slot, PLRU state, or DUT victim is consumed.
"""
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.tage.retouch_replacement import PATHS,OwnerLearning


class OwnerRecency:
    def __init__(self,*,policy='learning'):
        if policy not in ('learning','insertion'):raise ValueError('unknown owner recency policy')
        self.policy=policy
        self.residents=[[None]*4 for _ in range(2)]
        self.latest_group=[None,None]
        self.latest_member=[[None,None] for _ in range(2)]
        self.removed=[[],[]]

    def learn(self,history,owners,initial):
        if type(history) is not int or not 0<=history<5:raise ValueError('unknown history identity')
        if type(owners) is not tuple or any(type(o) is not int for o in owners) or owners not in ((0,),(1,),(0,1)):
            raise ValueError('explicit nonempty feedback subset required')
        if type(initial) is not tuple or len(initial)!=2 or any(type(c) is not int or not 0<=c<=7 for c in initial):
            raise ValueError('two independently owned original counters required')
        for owner in owners:
            residents=self.residents[owner]
            index=next((i for i,r in enumerate(residents) if r is not None and r.history==history),None)
            hit=index is not None
            if not hit:
                index=next((i for i,r in enumerate(residents) if r is None),None)
                if index is None:
                    group=1-self.latest_group[owner]
                    index=2*group+(1-self.latest_member[owner][group])
                    self.removed[owner].append(residents[index].history)
            current=residents[index].counter if hit else initial[owner]
            residents[index]=OwnerLearning(history,max(0,min(7,current+(1 if owner else -1))))
            if not hit or self.policy=='learning':
                group,member=divmod(index,2)
                self.latest_group[owner]=group;self.latest_member[owner][group]=member
        return tuple(tuple(row) for row in self.residents)


@dataclass(frozen=True,slots=True)
class OwnerRecencyProgram:
    name:str
    retouches:tuple
    victims:tuple
    mode:str='overlapped'

    @property
    def victim(self):return self.victims
    @property
    def paths(self):return PATHS
    @property
    def history_count(self):return 5
    @property
    def retained_count(self):return 4
    @property
    def initial_base(self):return (0,3)
    @property
    def empty_state(self):return ((None,)*4,)*2
    @property
    def feedback_order(self):return (0,1,2,3,*(h for h,o in self.retouches),4)

    def initial_counters(self,history):
        if type(history) is not int or not 0<=history<5:raise ValueError('unknown original history')
        return (1,6) if history==0 else (2,5)

    def input_owners(self,index):
        return (self.retouches[index-4][1],) if 4<=index<len(self.feedback_order)-1 else (0,1)

    def branch_outcomes(self,index):return tuple((o,bool(o),False) for o in self.input_owners(index))

    @property
    def main_update_counts(self):
        return tuple(sum(o in self.input_owners(i) for i in range(len(self.feedback_order))) for o in range(2))

    def owner_records(self,snapshot,owner):return snapshot[owner]

    def trace(self,*,policy='learning'):
        model=OwnerRecency(policy=policy)
        snapshots=tuple(model.learn(h,self.input_owners(i),self.initial_counters(h))
                        for i,h in enumerate(self.feedback_order))
        if policy=='learning' and tuple(tuple(v) for v in model.removed)!=tuple((v,) for v in self.victims):
            raise AssertionError('independent predeclared owner victims disagree')
        return snapshots

    def expected_counters(self,history):
        final=self.trace()[-1]
        return tuple(next((r.counter for r in final[o] if r.history==history),self.initial_counters(history)[o])
                     for o in range(2))


PROGRAMS=(
    OwnerRecencyProgram('first-only-protects-a',((0,0),),(2,0)),
    OwnerRecencyProgram('second-only-protects-a',((0,1),),(0,2)),
    OwnerRecencyProgram('first-only-c-reaches-and-holds-boundary',((2,0),(2,0)),(0,0)),
    OwnerRecencyProgram('second-only-d-reaches-and-holds-boundary',((3,1),(3,1)),(0,0)),
    OwnerRecencyProgram('independent-a-then-c',((0,0),(2,1)),(2,0)),
    OwnerRecencyProgram('independent-c-then-a',((2,1),(0,0)),(2,0)),
)
