"""Closed-form warm correction ownership; no DUT or cycle-reference inputs."""
from bpuverify.common.model.configuration import SC_WAYS, SC_TABLES, RESULT_SLOTS, MAIN_WAYS, SC_MIN_THRESHOLD, SC_MAX_THRESHOLD

from dataclasses import dataclass,replace

from bpuverify.sc.transaction.types import ScBaseBranch,ScLookup,ScBatchTraining,ScBranchFeedback

META=('scBiasLowerBits','scPred','useScPred','sumAboveThres','tageCtr','tagePred','tagePredValid')
FAMILIES=('scPathTakenVec','scGlobalTakenVec','scBWTakenVec','scImliTakenVec','scBiasTakenVec')
GATES=('provider-missing','main-miss','nonconditional')
RULES=('qualified-warm-learning',*GATES,'original-query-ownership','fresh-restoration',
       'retained-learning-strength','immutable-originals')
INITIAL_THRESHOLD=1130


def slot(position):return (position%SC_WAYS)^(position//SC_WAYS)


@dataclass(frozen=True)
class Owner:
    name: str
    pc: int
    first_position: int
    outcome: int

    @property
    def counter(self):return 4 if self.outcome else 3

    @property
    def selector(self):return 3 if self.outcome else 2

    def layout(self,gate='eligible'):
        if gate not in ('eligible',*GATES):raise ValueError('unknown query eligibility')
        positions=(self.first_position, *(p for p in range(32) if slot(p) != slot(self.first_position)))
        branches=tuple(ScBaseBranch(p,self.counter) for p in positions[:RESULT_SLOTS])
        field={'provider-missing':dict(provider_valid=0),'main-miss':dict(mbtb_valid=0),
               'nonconditional':dict(branch_type=2)}.get(gate,{})
        return (replace(branches[0],**field),*branches[1:])


@dataclass(frozen=True)
class Probe:
    ordinal: int
    owner: Owner
    gate: str


@dataclass(frozen=True)
class EligibilityProgram:
    first_direction: int
    mode: str

    def __post_init__(self):
        if type(self.first_direction) is not int or self.first_direction not in (0,1):
            raise ValueError('explicit first-owner direction required')
        if self.mode not in ('serial','pipelined'):raise ValueError('unknown submission mode')

    @property
    def profile(self):return self.mode+('.positive-first' if self.first_direction else '.negative-first')

    @property
    def owners(self):
        return (Owner('a',0x40000040,4,self.first_direction),
                Owner('b',0x40000060,8,1-self.first_direction))

    @property
    def warm_votes(self):
        # Seven learned tables must still beat confidence when provider loss
        # selects the never-trained bias feature. The count is an outcome
        # requirement, not a duration or a loop that polls DUT weights.
        for votes in range(1,32):
            if all(abs((SC_TABLES-1)*(2*(votes if outcome else -votes)+1)+1)>
                   (INITIAL_THRESHOLD+votes*(1 if not outcome else -1))//64 for outcome in (0,1)):
                return votes
        raise AssertionError('no discriminating legal warm state')

    @property
    def probes(self):
        a,b=self.owners
        declarations=[(a,'eligible'),(b,'eligible')]
        for gate in GATES:
            declarations.extend(((a,gate),(b,'eligible'),(a,'eligible'),
                                 (b,gate),(a,'eligible'),(b,'eligible')))
        declarations.extend(((a,'eligible'),(b,'eligible')))
        return tuple(Probe(i,owner,gate) for i,(owner,gate) in enumerate(declarations))

    def request(self,owner,gate='eligible'):
        if owner not in self.owners:raise ValueError('unknown declared branch owner')
        return ScLookup(owner.pc,0,0,branches=owner.layout(gate))

    def actual_input(self,owner,gate='eligible'):
        request=self.request(owner,gate)
        return dict(pc=request.pc,enabled=True,
            history=(0,0,0,0,True),branches=request.branches)

    def thresholds(self,counts,reversals=None):
        reversals={} if reversals is None else reversals
        values=[INITIAL_THRESHOLD]*SC_WAYS
        for owner in self.owners:
            count=counts.get(owner.name,0)
            if type(count) is not int or not 0<=count<=self.warm_votes:
                raise ValueError('warm state advances only by designated original feedback')
            values[slot(owner.first_position)]+=count*(1 if not owner.outcome else -1)
            reverse=reversals.get(owner.name,0)
            if (type(reverse) is not int or not 0<=reverse<=2*self.warm_votes+1
                    or reverse and count!=self.warm_votes):
                raise ValueError('reverse learning needs complete original warm state and bounded real outcomes')
            for step in range(reverse):
                old_weight=(count-step)*(1 if owner.outcome else -1)
                values[slot(owner.first_position)]+=1 if int(old_weight>=0)!=1-owner.outcome else -1
        return tuple(values)

    def expected(self,owner,gate,counts,reversals=None):
        reversals={} if reversals is None else reversals
        layout=owner.layout(gate)
        if owner not in self.owners:raise ValueError('foreign query owner')
        thresholds=self.thresholds(counts,reversals)
        learned=(counts.get(owner.name,0)-reversals.get(owner.name,0))*(1 if owner.outcome else -1)
        selectors=tuple(2*int(branch.provider_valid and branch.tage_counter in (3,4))+
                        int(branch.provider_valid and branch.tage_counter>=4) for branch in layout)
        scores=[]; signs=[]; used=[]; above=[]; components=[]
        for ordinal,(branch,selector) in enumerate(zip(layout,selectors,strict=True)):
            weight=learned if ordinal==0 else 0
            selected=(weight,)*(SC_TABLES-1)+(weight if selector==owner.selector else 0,)
            votes=tuple(2*value+1 for value in selected)
            total=sum(votes)
            eligible=bool(branch.provider_valid and branch.mbtb_valid and branch.branch_type==1)
            # All declared bases have weak confidence3/4. Avoid importing the
            # general cycle predictor as this program's independent oracle.
            strong=abs(total)>thresholds[slot(branch.position)]//64
            scores.append(total);signs.append(int(total>=0));used.append(int(eligible and strong))
            above.append(int(strong if eligible else True))
            components.append(tuple(int(sum(votes[i] for i in indices)>=0) for indices in ((0,1),(2,3),(4,5),(6,),(7,))))
        return dict(takens=tuple(signs),useds=tuple(used),
            meta=dict(scBiasLowerBits=selectors,scPred=tuple(signs),useScPred=tuple(used),
                sumAboveThres=tuple(above),tageCtr=tuple(branch.tage_counter for branch in layout),
                tagePred=tuple(int(branch.tage_counter>=4) for branch in layout),
                tagePredValid=tuple(branch.provider_valid for branch in layout)),
            families={name:tuple(values[i] for values in components) for i,name in enumerate(FAMILIES)}),tuple(scores)

    def feedback(self,owner,meta,*,reverse=False):
        if owner not in self.owners:raise ValueError('unknown original feedback owner')
        if type(reverse) is not bool:raise ValueError('explicit feedback phase required')
        return ScBatchTraining(owner.pc,meta,(ScBranchFeedback(owner.first_position,
            1-owner.outcome if reverse else owner.outcome,0),))

    def reversal_steps(self,owner):
        counts={value.name:self.warm_votes for value in self.owners}
        for votes in range(1,2*self.warm_votes+2):
            expected,_=self.expected(owner,'eligible',counts,{owner.name:votes})
            if expected['useds'][0] and expected['takens'][0]==1-owner.outcome:return votes
        raise AssertionError('declared real opposite outcomes never restored a strong opposite consumer')

    def require_strong_warm_state(self,counts):
        if counts!={owner.name:self.warm_votes for owner in self.owners}:
            raise AssertionError('both owners need their complete qualified feedback')
        for owner in self.owners:
            for gate in ('eligible',*GATES):
                expected,scores=self.expected(owner,gate,counts)
                assert abs(scores[0])>self.thresholds(counts)[slot(owner.first_position)]//64
                assert expected['takens'][0]==owner.outcome

